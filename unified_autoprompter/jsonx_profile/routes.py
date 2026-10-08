from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

from aiohttp import web

from . import engine
from . import reference_store
from ..profiles import (
    get_profile,
    normalize_format,
    normalize_generation_type,
)
from ..prompt_presets import resolve_text as resolve_prompt_presets


ROUTE_PREFIX = "/workflowx/unified_autoprompter/jsonx"
SCHEMA_VERSION = 8


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
    selected_prompt = str(data.get("raw_prompt_text") or data.get("prompt_text") or "").strip()
    if selected_prompt:
        items = (("", selected_prompt), ("Detail level", data.get("detail")))
    else:
        # Legacy route/API compatibility for callers that still submit the old
        # structured field collection.
        items = (
            ("Idea", data.get("idea")),
            ("Subject", data.get("subject")),
            ("Style", data.get("style")),
            ("Lighting", data.get("lighting")),
            ("Camera / composition", data.get("composition")),
            ("Text / typography", data.get("text")),
            ("Detail level", data.get("detail")),
            ("Reference image note", data.get("image_note")),
            ("Extra instructions", data.get("extra_instructions")),
        )
    instructions = "\n".join(
        f"{label}: {str(value).strip()}" if label else str(value).strip()
        for label, value in items
        if str(value or "").strip()
    )
    resolved, _activated = resolve_prompt_presets(instructions)
    return resolved


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
        for key in ("negative", "negative_prompts", "negative_prompt", "avoid"):
            collect(prompt.get(key))
    return "\n".join(dict.fromkeys(values))


def _request_payload(body: dict[str, Any]) -> dict[str, Any]:
    payload = dict(body)
    profile = get_profile(str(body.get("target_model") or body.get("profile_key") or "jsonx"))
    if profile.engine != "jsonx":
        raise ValueError("The selected profile is not a JsonX engine profile.")
    generation_type = normalize_generation_type(profile.key, str(body.get("generation_type") or ""))
    images = body.get("images_b64") if isinstance(body.get("images_b64"), list) else []
    if not images and str(body.get("image_b64") or "").strip():
        images = [body.get("image_b64")]
    connected_images = [item for item in images if str(item or "").strip()]
    if len(connected_images) > 9:
        raise ValueError("Unified JsonX accepts at most nine connected authoring images.")
    output_format = normalize_format(profile.key, str(body.get("output_format") or ""))
    image_state = (
        "supported_with_image" if generation_type == "image_to_image" and connected_images
        else "supported_without_image" if generation_type == "image_to_image"
        else "unsupported_with_image_guidance" if connected_images
        else None
    )
    payload["generation_type"] = generation_type
    payload["output_format"] = output_format
    payload["profile_key"] = profile.key
    payload["images_b64"] = connected_images
    payload["image_b64"] = connected_images[0] if connected_images else ""
    payload["has_image"] = bool(connected_images)
    payload["_connected_image_count"] = len(connected_images)
    payload["_ignored_image_count"] = 0
    payload["_submitted_image_count"] = len(connected_images)
    payload["_image_state"] = image_state
    payload["user_instructions"] = _instructions_from_fields(body.get("fields"))
    return payload


def _require_schema(body: dict[str, Any]) -> None:
    supplied = int(body.get("schema_version") or 0)
    if supplied != SCHEMA_VERSION:
        raise ValueError(
            f"Unified schema mismatch (frontend {supplied or 'missing'}, backend {SCHEMA_VERSION}). "
            "Restart ComfyUI and hard-refresh the browser."
        )
    reference_supplied = int(body.get("jsonx_reference_schema_version") or 0)
    if reference_supplied != reference_store.JSONX_REFERENCE_SCHEMA_VERSION:
        raise ValueError(
            "Unified JsonX reference schema mismatch "
            f"(frontend {reference_supplied or 'missing'}, backend "
            f"{reference_store.JSONX_REFERENCE_SCHEMA_VERSION}). Restart ComfyUI and hard-refresh the browser."
        )


def _valid_generation_id(value: Any) -> str:
    generation_id = str(value or "").strip()
    if not generation_id or len(generation_id) > 128:
        raise ValueError("Invalid Unified JsonX generation ID.")
    return generation_id


def register_routes(prompt_server) -> None:
    if prompt_server is None or getattr(prompt_server, "_workflowx_unified_jsonx_routes", False):
        return
    routes = prompt_server.routes

    @routes.get(f"{ROUTE_PREFIX}/reference_config")
    async def reference_config(_request):
        try:
            return web.json_response({
                "current": reference_store.current_bundle(),
                "original": reference_store.original_bundle(),
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.post(f"{ROUTE_PREFIX}/reference_config")
    async def save_reference_config(request):
        try:
            body = await request.json()
            saved = reference_store.save_current_bundle(body if isinstance(body, dict) else {})
            return web.json_response({"ok": True, "current": saved})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.post(f"{ROUTE_PREFIX}/reference_config/reset_profile")
    async def reset_reference_profile(request):
        try:
            body = await request.json()
            saved = reference_store.reset_profile(str((body or {}).get("profile_key") or ""))
            return web.json_response({"ok": True, "current": saved})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.post(f"{ROUTE_PREFIX}/reference_config/reset_all")
    async def reset_all_references(_request):
        try:
            saved = reference_store.reset_all()
            return web.json_response({"ok": True, "current": saved})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.get(f"{ROUTE_PREFIX}/presets/info")
    async def presets_info(request):
        profile_key = str(request.query.get("profile_key") or "jsonx")
        raw = engine.raw_presets_text(profile_key)
        return web.json_response({
            "characters": len(raw),
            "estimated_tokens": max(1, (len(raw) + 3) // 4),
            "schema_paths": len(engine.preset_schema_paths(engine.load_presets(profile_key))),
        })

    @routes.get(f"{ROUTE_PREFIX}/instructions")
    async def instruction_templates(request):
        return web.json_response(engine.instruction_templates(str(request.query.get("profile_key") or "jsonx")))

    @routes.post(f"{ROUTE_PREFIX}/instructions/preview")
    async def instruction_preview(request):
        try:
            body = await request.json()
            _require_schema(body if isinstance(body, dict) else {})
            body = _request_payload(body if isinstance(body, dict) else {})
            result = await asyncio.get_event_loop().run_in_executor(None, engine.effective_instruction_preview, body)
            result["connected_image_count"] = body.get("_connected_image_count", 0)
            result["image_count"] = body.get("_submitted_image_count", 0)
            result["ignored_image_count"] = body.get("_ignored_image_count", 0)
            result["image_state"] = body.get("_image_state")
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
            discovery = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: engine.openai_backend.discover_models(
                    str(body.get("base_url") or "").strip(),
                    str(body.get("api_key") or "").strip(),
                    timeout,
                    str(body.get("server_type") or "auto"),
                ),
            )
            return web.json_response(discovery)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.post(f"{ROUTE_PREFIX}/lm_studio/models")
    async def lm_studio_models(request):
        try:
            body = await request.json()
            discovery = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: engine.openai_backend.discover_models(
                    str(body.get("base_url") or "").strip(),
                    str(body.get("api_key") or "").strip(),
                    float(body.get("timeout") or 120),
                    "lm_studio",
                ),
            )
            return web.json_response(discovery)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.post(f"{ROUTE_PREFIX}/unsloth/models")
    async def unsloth_models(request):
        try:
            body = await request.json()
            discovery = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: engine.openai_backend.discover_models(
                    str(body.get("base_url") or "").strip(),
                    str(body.get("api_key") or "").strip(),
                    float(body.get("timeout") or 120),
                    "unsloth",
                ),
            )
            return web.json_response(discovery)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.post(f"{ROUTE_PREFIX}/grok/models")
    async def grok_models(request):
        try:
            body = await request.json()
            models = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: engine.grok_backend.list_models(
                    str(body.get("api_key") or "").strip(), float(body.get("timeout") or 120)
                ),
            )
            return web.json_response({"models": models})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.post(f"{ROUTE_PREFIX}/deepseek/models")
    async def deepseek_models(request):
        try:
            body = await request.json()
            models = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: engine.deepseek_backend.list_models(
                    str(body.get("api_key") or "").strip(), float(body.get("timeout") or 120)
                ),
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
            _require_schema(body if isinstance(body, dict) else {})
            body = _request_payload(body if isinstance(body, dict) else {})
            generation_id = _valid_generation_id(body.get("generation_id"))
            body["_cancel_event"] = CancellationRegistry.begin(generation_id)
            result = await asyncio.get_event_loop().run_in_executor(None, engine.generate_jsonx, body)
            stage_one = result.pop("_stage_one", None)
            result["positive"] = result.get("prompt", "")
            result["negative"] = _negative_text(stage_one)
            result["connected_image_count"] = body.get("_connected_image_count", 0)
            result["image_count"] = body.get("_submitted_image_count", 0)
            result["ignored_image_count"] = body.get("_ignored_image_count", 0)
            result["image_state"] = body.get("_image_state")
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
