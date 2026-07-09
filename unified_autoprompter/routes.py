from __future__ import annotations

import asyncio
import base64
import io
import traceback
from typing import Any

from aiohttp import web
from PIL import Image

from . import gemini_backend, local_llama_backend, ollama_backend, openai_backend
from .folder_registry import model_options, mmproj_options, system_prompt_options
from .profile_config import profile_config_payload, reset_config, save_config
from .profiles import normalize_format, profiles_payload
from .prompt_builder import build_system_prompt, build_user_prompt
from .prompt_io import parse_generation_response


ROUTE_PREFIX = "/workflowx/unified_autoprompter"


def _timeout_seconds(value: Any, default: float = 120.0) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        timeout = default
    return max(5.0, min(3600.0, timeout))


def _decode_image(image_b64: str | None) -> Image.Image | None:
    if not image_b64:
        return None
    data = str(image_b64)
    if "," in data:
        data = data.split(",", 1)[1]
    try:
        raw = base64.b64decode(data)
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        return None


def _json_error(message: str, status: int = 400):
    return web.json_response({"error": message}, status=status)


def register_routes(app=None) -> None:
    try:
        from server import PromptServer
    except Exception:
        return

    prompt_server = getattr(PromptServer, "instance", None)
    if prompt_server is None or getattr(prompt_server, "_workflowx_unified_autoprompter_routes", False):
        return

    routes = prompt_server.routes

    @routes.get(f"{ROUTE_PREFIX}/profiles")
    async def workflowx_unified_profiles(request):
        return web.json_response(profiles_payload())

    @routes.get(f"{ROUTE_PREFIX}/profile_config")
    async def workflowx_unified_profile_config(request):
        try:
            return web.json_response(profile_config_payload())
        except Exception as exc:
            return _json_error(str(exc), status=500)

    @routes.post(f"{ROUTE_PREFIX}/profile_config")
    async def workflowx_unified_save_profile_config(request):
        try:
            data = await request.json()
            saved = save_config(data)
            return web.json_response({"ok": True, **profile_config_payload(), "raw": saved})
        except Exception as exc:
            return _json_error(str(exc))

    @routes.post(f"{ROUTE_PREFIX}/profile_config/reset")
    async def workflowx_unified_reset_profile_config(request):
        try:
            reset_config()
            return web.json_response({"ok": True, **profile_config_payload()})
        except Exception as exc:
            return _json_error(str(exc))

    @routes.get(f"{ROUTE_PREFIX}/local/models")
    async def workflowx_unified_local_models(request):
        return web.json_response(
            {
                "models": model_options(),
                "mmproj": mmproj_options(),
                "system_prompts": system_prompt_options(),
            }
        )

    @routes.post(f"{ROUTE_PREFIX}/gemini/models")
    async def workflowx_unified_gemini_models(request):
        try:
            data = await request.json()
            timeout = _timeout_seconds(data.get("timeout"))
            loop = asyncio.get_event_loop()
            models = await loop.run_in_executor(
                None,
                gemini_backend.list_models,
                (data.get("api_key") or "").strip(),
                timeout,
            )
            return web.json_response({"models": models})
        except Exception as exc:
            return _json_error(str(exc))

    @routes.post(f"{ROUTE_PREFIX}/openai/models")
    async def workflowx_unified_openai_models(request):
        try:
            data = await request.json()
            timeout = _timeout_seconds(data.get("timeout"))
            loop = asyncio.get_event_loop()
            models = await loop.run_in_executor(
                None,
                openai_backend.list_models,
                (data.get("base_url") or "").strip(),
                (data.get("api_key") or "").strip(),
                timeout,
            )
            return web.json_response({"models": models})
        except Exception as exc:
            return _json_error(str(exc))

    @routes.post(f"{ROUTE_PREFIX}/ollama/models")
    async def workflowx_unified_ollama_models(request):
        try:
            data = await request.json()
            loop = asyncio.get_event_loop()
            models = await loop.run_in_executor(
                None,
                ollama_backend.list_models,
                (data.get("host") or "").strip(),
            )
            return web.json_response({"models": models})
        except Exception as exc:
            return _json_error(str(exc))

    @routes.post(f"{ROUTE_PREFIX}/generate")
    async def workflowx_unified_generate(request):
        try:
            data = await request.json()
        except Exception:
            return _json_error("Invalid request body.")

        target_model = str(data.get("target_model") or "ideogram4")
        prompt_format = normalize_format(target_model, str(data.get("prompt_format") or ""))
        negative_enabled = bool(data.get("negative_enabled"))
        fields = data.get("fields") if isinstance(data.get("fields"), dict) else data
        pil_image = _decode_image(data.get("image_b64"))
        system_prompt = build_system_prompt(target_model, prompt_format, negative_enabled, has_image=pil_image is not None)
        user_prompt = build_user_prompt(fields, has_image=pil_image is not None, target_model=target_model)
        backend = str(data.get("backend") or "gemini")
        timeout = _timeout_seconds(data.get("timeout"))
        loop = asyncio.get_event_loop()

        try:
            if backend == "gemini":
                raw = await loop.run_in_executor(
                    None,
                    lambda: gemini_backend.generate(
                        (data.get("api_key") or "").strip(),
                        data.get("model") or "",
                        system_prompt,
                        user_prompt,
                        pil_image=pil_image,
                        timeout=timeout,
                    ),
                )
            elif backend == "openai":
                raw = await loop.run_in_executor(
                    None,
                    lambda: openai_backend.generate(
                        data.get("base_url") or "",
                        (data.get("api_key") or "").strip(),
                        data.get("model") or "",
                        system_prompt,
                        user_prompt,
                        pil_image=pil_image,
                        timeout=timeout,
                        unload_after=bool(data.get("unload_after", False)),
                    ),
                )
            elif backend == "ollama":
                raw = await loop.run_in_executor(
                    None,
                    lambda: ollama_backend.generate(
                        data.get("host") or "",
                        data.get("model") or "",
                        system_prompt,
                        user_prompt,
                        pil_image=pil_image,
                        think=bool(data.get("think", False)),
                        unload_after=bool(data.get("unload_after", True)),
                    ),
                )
            elif backend == "local":
                local_options = data.get("local_options")
                local_options = local_options if isinstance(local_options, dict) else {}
                local_options.setdefault("timeout", timeout)
                raw = await loop.run_in_executor(
                    None,
                    lambda: local_llama_backend.generate(
                        model=data.get("model") or "",
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        pil_image=pil_image,
                        mmproj=data.get("mmproj") or "none",
                        system_prompt_preset=data.get("system_prompt_preset") or "none",
                        options=local_options,
                    ),
                )
            else:
                return _json_error(f"Unsupported backend: {backend}")

            parsed = parse_generation_response(target_model, prompt_format, raw, negative_enabled)
            return web.json_response(
                {
                    **parsed,
                    "raw": raw,
                    "target_model": target_model,
                    "prompt_format": prompt_format,
                    "negative_enabled": negative_enabled,
                }
            )
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc))

    prompt_server._workflowx_unified_autoprompter_routes = True
