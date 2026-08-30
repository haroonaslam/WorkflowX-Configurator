from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import threading
import traceback
from typing import Any

from aiohttp import web
from PIL import Image

from . import deepseek_backend, gemini_backend, grok_backend, local_llama_backend, ollama_backend, openai_backend
from .folder_registry import model_catalog
from .profile_config import profile_config_payload, reset_config, save_config
from .profiles import (
    effective_generation_image_count,
    effective_generation_images,
    get_profile,
    normalize_format,
    normalize_generation_type,
    profiles_payload,
    resolve_image_state,
    supports_negative,
    validate_generation_image_count,
)
from .prompt_builder import assemble_system_prompt, build_system_prompt, build_user_prompt
from .prompt_io import parse_generation_response
from .reference_store import (
    REFERENCE_SCHEMA_VERSION,
    current_bundle,
    original_bundle,
    reset_all as reset_all_references,
    reset_profile as reset_reference_profile,
    save_current_bundle,
)


ROUTE_PREFIX = "/workflowx/unified_autoprompter"
SCHEMA_VERSION = 7


class GenerationCancelled(RuntimeError):
    pass


class CancellationRegistry:
    _lock = threading.Lock()
    _events: dict[str, threading.Event] = {}

    @classmethod
    def begin(cls, generation_id: str) -> threading.Event:
        event = threading.Event()
        if generation_id:
            with cls._lock:
                cls._events[generation_id] = event
        return event

    @classmethod
    def cancel(cls, generation_id: str) -> bool:
        with cls._lock:
            event = cls._events.get(generation_id)
        if event is None:
            return False
        event.set()
        return True

    @classmethod
    def finish(cls, generation_id: str) -> None:
        if generation_id:
            with cls._lock:
                cls._events.pop(generation_id, None)


def _provider_default_number(value: Any, *, integer: bool = False) -> float | int | None:
    if value is None or value == "" or str(value).strip().lower() in {"default", "provider_default"}:
        return None
    return int(value) if integer else float(value)


def _prompt_cache_key(data: dict[str, Any], system_prompt: str, stage: str = "single") -> str:
    if str(data.get("grok_prompt_cache") or "auto").strip().lower() == "off":
        return ""
    stable = {
        "engine": "standard",
        "profile": str(data.get("target_model") or ""),
        "generation_type": str(data.get("generation_type") or ""),
        "format": str(data.get("prompt_format") or ""),
        "stage": stage,
        "system_sha256": hashlib.sha256(system_prompt.encode("utf-8")).hexdigest(),
    }
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode("utf-8")).hexdigest()


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


def _raw_image_values(data: dict[str, Any]) -> list[str]:
    raw_images = data.get("images_b64")
    if isinstance(raw_images, list) and raw_images:
        candidates = raw_images
    else:
        candidates = [data.get("image_b64")]
    return [str(candidate) for candidate in candidates if str(candidate or "").strip()]


def _decode_image_values(candidates: list[str]) -> list[Image.Image]:
    images = []
    for candidate in candidates:
        image = _decode_image(candidate)
        if image is not None:
            images.append(image)
    return images


def _decode_images(data: dict[str, Any]) -> list[Image.Image]:
    return _decode_image_values(_raw_image_values(data))


def refresh_comfy_vram() -> str:
    try:
        import comfy.model_management as model_management
    except Exception as exc:
        return f"refresh VRAM skipped: could not import ComfyUI model management ({exc})"

    messages = []
    try:
        model_management.unload_all_models()
        messages.append("unloaded all models")
    except Exception as exc:
        messages.append(f"unload_all_models failed: {exc}")
    try:
        model_management.soft_empty_cache(force=True)
        messages.append("emptied cache")
    except TypeError:
        try:
            model_management.soft_empty_cache()
            messages.append("emptied cache")
        except Exception as exc:
            messages.append(f"soft_empty_cache failed: {exc}")
    except Exception as exc:
        messages.append(f"soft_empty_cache failed: {exc}")
    return "; ".join(messages)


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

    @routes.post(f"{ROUTE_PREFIX}/preview")
    async def workflowx_unified_preview(request):
        try:
            data = await request.json()
            if int(data.get("schema_version") or 0) != SCHEMA_VERSION:
                raise ValueError(
                    "Unified PrompterX frontend/backend schema mismatch. Restart ComfyUI and hard-refresh the browser."
                )
            if int(data.get("reference_schema_version") or 0) != REFERENCE_SCHEMA_VERSION:
                raise ValueError(
                    "Unified PrompterX reference schema mismatch. Restart ComfyUI and hard-refresh the browser."
                )
            target_model = str(data.get("target_model") or "ideogram4")
            prompt_format = normalize_format(target_model, str(data.get("prompt_format") or ""))
            generation_type = normalize_generation_type(target_model, str(data.get("generation_type") or ""))
            connected_image_count = max(0, int(data.get("image_count") or 0))
            image_count, ignored_image_count = effective_generation_image_count(
                generation_type, connected_image_count
            )
            validate_generation_image_count(generation_type, image_count)
            negative_enabled = bool(data.get("negative_enabled")) and supports_negative(target_model)
            fields = data.get("fields") if isinstance(data.get("fields"), dict) else data
            system_prompt, activated_blocks = assemble_system_prompt(
                target_model,
                prompt_format,
                negative_enabled,
                has_image=image_count > 0,
                reference_count=image_count,
                generation_type=generation_type,
                nsfw_enabled=bool(data.get("nsfw_enabled")),
            )
            user_prompt = build_user_prompt(
                fields,
                has_image=image_count > 0,
                target_model=target_model,
                reference_count=image_count,
                generation_type=generation_type,
            )
            return web.json_response(
                {
                    "schema_version": SCHEMA_VERSION,
                    "system": system_prompt,
                    "user": user_prompt,
                    "generation_type": generation_type,
                    "connected_image_count": connected_image_count,
                    "image_count": image_count,
                    "ignored_image_count": ignored_image_count,
                    "image_state": resolve_image_state(generation_type, image_count),
                    "activated_blocks": activated_blocks,
                    "nsfw_enabled": bool(data.get("nsfw_enabled")),
                }
            )
        except Exception as exc:
            return _json_error(str(exc))

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

    @routes.get(f"{ROUTE_PREFIX}/reference_config")
    async def workflowx_unified_reference_config(request):
        try:
            return web.json_response({
                "reference_schema_version": REFERENCE_SCHEMA_VERSION,
                "current": current_bundle(),
                "original": original_bundle(),
            })
        except Exception as exc:
            return _json_error(str(exc), status=500)

    @routes.post(f"{ROUTE_PREFIX}/reference_config")
    async def workflowx_unified_save_reference_config(request):
        try:
            data = await request.json()
            bundle = data.get("bundle") if isinstance(data.get("bundle"), dict) else data
            saved = save_current_bundle(bundle)
            return web.json_response({"ok": True, "current": saved})
        except Exception as exc:
            return _json_error(str(exc))

    @routes.post(f"{ROUTE_PREFIX}/reference_config/reset_profile")
    async def workflowx_unified_reset_reference_profile(request):
        try:
            data = await request.json()
            saved = reset_reference_profile(str(data.get("profile_key") or ""))
            return web.json_response({"ok": True, "current": saved})
        except Exception as exc:
            return _json_error(str(exc))

    @routes.post(f"{ROUTE_PREFIX}/reference_config/reset_all")
    async def workflowx_unified_reset_all_references(request):
        try:
            saved = reset_all_references()
            return web.json_response({"ok": True, "current": saved})
        except Exception as exc:
            return _json_error(str(exc))

    @routes.get(f"{ROUTE_PREFIX}/local/models")
    @routes.post(f"{ROUTE_PREFIX}/local/models")
    async def workflowx_unified_local_models(request):
        data = {}
        if str(getattr(request, "method", "GET")).upper() == "POST":
            try:
                data = await request.json()
            except Exception:
                data = {}
        return web.json_response(model_catalog(data.get("additional_model_paths")))

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
            discovery = await loop.run_in_executor(
                None,
                lambda: openai_backend.discover_models(
                    (data.get("base_url") or "").strip(),
                    (data.get("api_key") or "").strip(),
                    timeout,
                    str(data.get("server_type") or "auto"),
                ),
            )
            return web.json_response(discovery)
        except Exception as exc:
            return _json_error(str(exc))

    async def _specialized_openai_models(request, server_type: str):
        try:
            data = await request.json()
            timeout = _timeout_seconds(data.get("timeout"))
            discovery = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: openai_backend.discover_models(
                    (data.get("base_url") or "").strip(),
                    (data.get("api_key") or "").strip(),
                    timeout,
                    server_type,
                ),
            )
            return web.json_response(discovery)
        except Exception as exc:
            return _json_error(str(exc))

    @routes.post(f"{ROUTE_PREFIX}/lm_studio/models")
    async def workflowx_unified_lm_studio_models(request):
        return await _specialized_openai_models(request, "lm_studio")

    @routes.post(f"{ROUTE_PREFIX}/unsloth/models")
    async def workflowx_unified_unsloth_models(request):
        return await _specialized_openai_models(request, "unsloth")

    @routes.post(f"{ROUTE_PREFIX}/grok/models")
    async def workflowx_unified_grok_models(request):
        try:
            data = await request.json()
            models = await asyncio.get_event_loop().run_in_executor(
                None,
                grok_backend.list_models,
                str(data.get("api_key") or "").strip(),
                _timeout_seconds(data.get("timeout")),
            )
            return web.json_response({"models": models})
        except Exception as exc:
            return _json_error(str(exc))

    @routes.post(f"{ROUTE_PREFIX}/deepseek/models")
    async def workflowx_unified_deepseek_models(request):
        try:
            data = await request.json()
            models = await asyncio.get_event_loop().run_in_executor(
                None,
                deepseek_backend.list_models,
                str(data.get("api_key") or "").strip(),
                _timeout_seconds(data.get("timeout")),
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

        if int(data.get("schema_version") or 0) != SCHEMA_VERSION:
            return _json_error(
                "Unified PrompterX frontend/backend schema mismatch. Restart ComfyUI and hard-refresh the browser."
            )
        if int(data.get("reference_schema_version") or 0) != REFERENCE_SCHEMA_VERSION:
            return _json_error(
                "Unified PrompterX reference schema mismatch. Restart ComfyUI and hard-refresh the browser."
            )
        target_model = str(data.get("target_model") or "ideogram4")
        if get_profile(target_model).engine != "standard":
            return _json_error("JsonX profiles must use the isolated Unified JsonX generation route.")
        prompt_format = normalize_format(target_model, str(data.get("prompt_format") or ""))
        negative_enabled = bool(data.get("negative_enabled")) and supports_negative(target_model)
        fields = data.get("fields") if isinstance(data.get("fields"), dict) else data
        generation_type = normalize_generation_type(target_model, str(data.get("generation_type") or ""))
        raw_image_values = _raw_image_values(data)
        effective_image_values, ignored_image_count = effective_generation_images(
            generation_type, raw_image_values
        )
        pil_images = _decode_image_values(effective_image_values)
        pil_image = pil_images[0] if pil_images else None
        reference_count = len(pil_images)
        try:
            validate_generation_image_count(generation_type, reference_count)
        except ValueError as exc:
            return _json_error(str(exc))
        system_prompt = build_system_prompt(
            target_model,
            prompt_format,
            negative_enabled,
            has_image=bool(pil_images),
            reference_count=reference_count,
            generation_type=generation_type,
            nsfw_enabled=bool(data.get("nsfw_enabled")),
        )
        user_prompt = build_user_prompt(
            fields,
            has_image=bool(pil_images),
            target_model=target_model,
            reference_count=reference_count,
            generation_type=generation_type,
        )
        backend = str(data.get("backend") or "gemini")
        timeout = _timeout_seconds(data.get("timeout"))
        loop = asyncio.get_event_loop()
        generation_id = str(data.get("generation_id") or "").strip()
        cancel_event = CancellationRegistry.begin(generation_id)

        try:
            if cancel_event.is_set():
                raise GenerationCancelled("Generation cancelled.")
            if bool(data.get("refresh_vram", False)):
                await loop.run_in_executor(None, refresh_comfy_vram)
            if backend == "gemini":
                raw = await loop.run_in_executor(
                    None,
                    lambda: gemini_backend.generate(
                        (data.get("api_key") or "").strip(),
                        data.get("model") or "",
                        system_prompt,
                        user_prompt,
                        prompt_format=prompt_format,
                        pil_image=pil_image,
                        pil_images=pil_images,
                        safety_settings=data.get("gemini_safety") if isinstance(data.get("gemini_safety"), dict) else None,
                        timeout=timeout,
                    ),
                )
            elif backend in {"openai", "lm_studio", "unsloth"}:
                server_type = {
                    "openai": "generic",
                    "lm_studio": "lm_studio",
                    "unsloth": "unsloth",
                }[backend]
                model_capabilities = data.get("model_capabilities") if isinstance(data.get("model_capabilities"), dict) else {}
                if pil_images and backend in {"lm_studio", "unsloth"} and model_capabilities.get("vision") is False:
                    raise ValueError(f"The selected {backend.replace('_', ' ').title()} model does not accept image input.")
                raw = await loop.run_in_executor(
                    None,
                    lambda: openai_backend.generate(
                        data.get("base_url") or "",
                        (data.get("api_key") or "").strip(),
                        data.get("model") or "",
                        system_prompt,
                        user_prompt,
                        pil_image=pil_image,
                        pil_images=pil_images,
                        timeout=timeout,
                        unload_after=(
                            bool(data.get("unload_after"))
                            if "openai_lifecycle" not in data and "unload_after" in data
                            else None
                        ),
                        server_type=server_type,
                        lifecycle=str(data.get("openai_lifecycle") or "server_managed"),
                        reasoning_effort=str(data.get("openai_reasoning_effort") or "default"),
                        provider_options=data.get("provider_options") if isinstance(data.get("provider_options"), dict) else None,
                    ),
                )
            elif backend == "grok":
                model_capabilities = data.get("model_capabilities") if isinstance(data.get("model_capabilities"), dict) else {}
                if pil_images and model_capabilities.get("vision") is False:
                    raise ValueError("The selected Grok model does not accept image input.")
                raw = await loop.run_in_executor(
                    None,
                    lambda: grok_backend.generate(
                        str(data.get("api_key") or "").strip(),
                        str(data.get("model") or ""),
                        system_prompt,
                        user_prompt,
                        pil_images=pil_images,
                        timeout=timeout,
                        prompt_format=prompt_format,
                        max_output_tokens=_provider_default_number(data.get("grok_max_output_tokens"), integer=True),
                        temperature=_provider_default_number(data.get("grok_temperature")),
                        top_p=_provider_default_number(data.get("grok_top_p")),
                        reasoning_effort=str(data.get("grok_reasoning_effort") or "default"),
                        prompt_cache_key=_prompt_cache_key(data, system_prompt),
                    ),
                )
            elif backend == "deepseek":
                if pil_images and not deepseek_backend.is_vision_model(str(data.get("model") or "")):
                    raise ValueError(f"The selected DeepSeek model '{data.get('model') or ''}' does not accept image input.")
                raw = await loop.run_in_executor(
                    None,
                    lambda: deepseek_backend.generate(
                        str(data.get("api_key") or "").strip(),
                        str(data.get("model") or ""),
                        system_prompt,
                        user_prompt,
                        pil_images=pil_images,
                        timeout=timeout,
                        prompt_format=prompt_format,
                        max_tokens=_provider_default_number(data.get("deepseek_max_tokens"), integer=True),
                        thinking=str(data.get("deepseek_thinking") or "default"),
                        reasoning_effort=str(data.get("deepseek_reasoning_effort") or "default"),
                        temperature=_provider_default_number(data.get("deepseek_temperature")),
                        top_p=_provider_default_number(data.get("deepseek_top_p")),
                        image_detail=str(data.get("deepseek_image_detail") or "default"),
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
                        pil_images=pil_images,
                        think=bool(data.get("think", False)),
                        unload_after=bool(data.get("unload_after", True)),
                        timeout=timeout,
                        options=data.get("ollama_options") if isinstance(data.get("ollama_options"), dict) else None,
                    ),
                )
            elif backend == "local":
                local_options = data.get("local_options")
                local_options = local_options if isinstance(local_options, dict) else {}
                local_options.setdefault("timeout", timeout)
                if pil_images and str(data.get("mmproj") or "none").strip().lower() in {"", "none"}:
                    raise ValueError(
                        "Connected authoring images require a vision mmproj for the selected local GGUF model. "
                        "Select a compatible mmproj or disconnect the images."
                    )
                raw = await loop.run_in_executor(
                    None,
                    lambda: local_llama_backend.generate(
                        model=data.get("model") or "",
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        pil_image=pil_image,
                        pil_images=pil_images,
                        mmproj=data.get("mmproj") or "none",
                        system_prompt_preset=data.get("system_prompt_preset") or "none",
                        additional_model_paths=data.get("additional_model_paths"),
                        options=local_options,
                        cancel_event=cancel_event,
                    ),
                )
            else:
                return _json_error(f"Unsupported backend: {backend}")

            if cancel_event.is_set():
                raise GenerationCancelled("Generation cancelled.")
            parsed = parse_generation_response(target_model, prompt_format, str(raw), negative_enabled)
            diagnostics = dict(getattr(raw, "diagnostics", {}) or {})
            if backend == "grok":
                capabilities = data.get("model_capabilities") if isinstance(data.get("model_capabilities"), dict) else {}
                if capabilities.get("context_length") is not None:
                    diagnostics["context_length"] = int(capabilities.get("context_length") or 0)
            return web.json_response(
                {
                    **parsed,
                    "raw": raw,
                    "target_model": target_model,
                    "prompt_format": prompt_format,
                    "negative_enabled": negative_enabled,
                    "generation_type": generation_type,
                    "nsfw_enabled": bool(data.get("nsfw_enabled")),
                    "connected_image_count": len(raw_image_values),
                    "image_count": reference_count,
                    "ignored_image_count": ignored_image_count,
                    "image_state": resolve_image_state(generation_type, reference_count),
                    "schema_version": SCHEMA_VERSION,
                    "diagnostics": diagnostics,
                }
            )
        except GenerationCancelled as exc:
            return _json_error(str(exc), status=409)
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc))
        finally:
            CancellationRegistry.finish(generation_id)

    @routes.post(f"{ROUTE_PREFIX}/cancel")
    async def workflowx_unified_cancel(request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        generation_id = str(data.get("generation_id") or "").strip()
        return web.json_response({"cancelled": CancellationRegistry.cancel(generation_id)})

    prompt_server._workflowx_unified_autoprompter_routes = True

    # JsonX routes are registered independently from the standard profile
    # pipeline. Importing this private package here keeps normal Unified
    # profiles free from its providers, catalog and runtime state.
    from .jsonx_profile.routes import register_routes as register_jsonx_routes

    register_jsonx_routes(prompt_server)
