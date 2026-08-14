from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

from aiohttp import web

from . import engine


ROUTE_PREFIX = "/workflowx/unified_autoprompter/jsonx"


class CancellationRegistry:
    """Cancellation is scoped to Unified JsonX browser requests only."""

    _lock = threading.RLock()
    _states: dict[str, tuple[threading.Event, float]] = {}

    @classmethod
    def _prune(cls) -> None:
        cutoff = time.monotonic() - 600
        cls._states = {key: value for key, value in cls._states.items() if value[1] >= cutoff}

    @classmethod
    def begin(cls, generation_id: str) -> threading.Event:
        with cls._lock:
            cls._prune()
            event = threading.Event()
            cls._states[generation_id] = (event, time.monotonic())
            return event

    @classmethod
    def cancel(cls, generation_id: str) -> bool:
        with cls._lock:
            cls._prune()
            event, _ = cls._states.setdefault(generation_id, (threading.Event(), time.monotonic()))
            event.set()
            return True

    @classmethod
    def finish(cls, generation_id: str) -> None:
        with cls._lock:
            cls._states.pop(generation_id, None)


def _instructions_from_fields(fields: Any) -> str:
    data = fields if isinstance(fields, dict) else {}
    items = (
        ("Idea", data.get("idea")),
        ("Subject", data.get("subject")),
        ("Style", data.get("style")),
        ("Lighting", data.get("lighting")),
        ("Camera / composition", data.get("composition")),
        ("Text / typography", data.get("text")),
        ("Detail level", data.get("detail")),
        ("Reference image note", data.get("image_note")),
        ("Connected text", data.get("raw_prompt_text")),
        ("Extra instructions", data.get("extra_instructions")),
    )
    return "\n".join(f"{label}: {str(value).strip()}" for label, value in items if str(value or "").strip())


def _negative_text(prompt: Any) -> str:
    values: list[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)
        elif isinstance(value, str) and value.strip():
            values.append(value.strip())

    if isinstance(prompt, dict):
        collect(prompt.get("negative"))
    return "\n".join(dict.fromkeys(values))


def _request_payload(body: dict[str, Any]) -> dict[str, Any]:
    payload = dict(body)
    payload["user_instructions"] = _instructions_from_fields(body.get("fields"))
    return payload


def _valid_generation_id(value: Any) -> str:
    generation_id = str(value or "").strip()
    if not generation_id or len(generation_id) > 128:
        raise ValueError("Invalid Unified JsonX generation ID.")
    return generation_id


def register_routes(prompt_server) -> None:
    if prompt_server is None or getattr(prompt_server, "_workflowx_unified_jsonx_routes", False):
        return
    routes = prompt_server.routes

    @routes.get(f"{ROUTE_PREFIX}/presets/info")
    async def presets_info(_request):
        raw = engine.raw_presets_text()
        return web.json_response({
            "characters": len(raw),
            "estimated_tokens": max(1, (len(raw) + 3) // 4),
            "schema_paths": len(engine.preset_schema_paths()),
        })

    @routes.get(f"{ROUTE_PREFIX}/instructions")
    async def instruction_templates(_request):
        return web.json_response(engine.instruction_templates())

    @routes.post(f"{ROUTE_PREFIX}/instructions/preview")
    async def instruction_preview(request):
        try:
            body = await request.json()
            body = _request_payload(body if isinstance(body, dict) else {})
            result = await asyncio.get_event_loop().run_in_executor(None, engine.effective_instruction_preview, body)
            return web.json_response(result)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.get(f"{ROUTE_PREFIX}/local/models")
    @routes.post(f"{ROUTE_PREFIX}/local/models")
    async def local_models(request):
        body: dict[str, Any] = {}
        if request.method.upper() == "POST":
            try:
                body = await request.json()
            except Exception:
                body = {}
        return web.json_response(engine.local_models.model_catalog(body.get("additional_model_paths")))

    @routes.post(f"{ROUTE_PREFIX}/gemini/models")
    async def gemini_models(request):
        try:
            body = await request.json()
            timeout = float(body.get("timeout") or 120)
            models = await asyncio.get_event_loop().run_in_executor(
                None, engine.gemini_backend.list_models, str(body.get("api_key") or "").strip(), timeout
            )
            return web.json_response({"models": models})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.post(f"{ROUTE_PREFIX}/openai/models")
    async def openai_models(request):
        try:
            body = await request.json()
            timeout = float(body.get("timeout") or 120)
            models = await asyncio.get_event_loop().run_in_executor(
                None, engine.openai_backend.list_models, str(body.get("base_url") or "").strip(), str(body.get("api_key") or "").strip(), timeout
            )
            return web.json_response({"models": models})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.post(f"{ROUTE_PREFIX}/ollama/models")
    async def ollama_models(request):
        try:
            body = await request.json()
            models = await asyncio.get_event_loop().run_in_executor(
                None, lambda: engine.ollama_backend.list_models(str(body.get("host") or ""), float(body.get("timeout") or 15))
            )
            return web.json_response({"models": models})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.post(f"{ROUTE_PREFIX}/generate")
    async def generate(request):
        generation_id = ""
        try:
            body = await request.json()
            body = _request_payload(body if isinstance(body, dict) else {})
            generation_id = _valid_generation_id(body.get("generation_id"))
            body["_cancel_event"] = CancellationRegistry.begin(generation_id)
            result = await asyncio.get_event_loop().run_in_executor(None, engine.generate_jsonx, body)
            stage_one = result.pop("_stage_one", None)
            result["positive"] = result.get("prompt", "")
            result["negative"] = _negative_text(stage_one)
            return web.json_response(result)
        except engine.JsonXGenerationCancelled:
            return web.json_response({"error": "Unified JsonX generation cancelled.", "cancelled": True}, status=409)
        except engine.JsonXGenerationError as exc:
            return web.json_response({"error": str(exc), "diagnostics": exc.diagnostics}, status=400)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=400)
        finally:
            if generation_id:
                CancellationRegistry.finish(generation_id)

    @routes.post(f"{ROUTE_PREFIX}/cancel")
    async def cancel(request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        try:
            generation_id = _valid_generation_id(body.get("generation_id") if isinstance(body, dict) else "")
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        CancellationRegistry.cancel(generation_id)
        return web.json_response({"cancelled": True, "generation_id": generation_id})

    prompt_server._workflowx_unified_jsonx_routes = True
