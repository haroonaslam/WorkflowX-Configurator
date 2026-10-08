from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import threading
from typing import Any

from aiohttp import web
from PIL import Image

from . import deepseek_backend, gemini_backend, grok_backend, local_llama_backend, ollama_backend, openai_backend
from .folder_registry import model_catalog
from . import general
from .audit import AUDIT_ADD_PASS, AUDIT_ONLY, is_json_candidate, normalize_mode as normalize_audit_mode, result_changed as audit_result_changed, validate_result as validate_audit_result
from .generation_errors import log_generation_error
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
from .prompt_io import assemble_prompt, parse_generation_response
from .prompt_presets import (
    PRESET_SCHEMA_VERSION,
    PromptPresetError,
    delete_preset,
    payload as prompt_presets_payload,
    reset_preset,
    save_preset,
)
from .reference_store import (
    REFERENCE_SCHEMA_VERSION,
    audit_block,
    current_bundle,
    original_bundle,
    reset_all as reset_all_references,
    reset_profile as reset_reference_profile,
    save_current_bundle,
)


ROUTE_PREFIX = "/workflowx/unified_autoprompter"
SCHEMA_VERSION = 8


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


async def dispatch_provider(data, system_prompt, user_prompt, pil_images, prompt_format, cancel_event, stage="single"):
    """Dispatch already-built messages; profile and General assembly stay separate."""
    backend = str(data.get("backend") or "gemini")
    timeout = _timeout_seconds(data.get("timeout"))
    loop = asyncio.get_event_loop()
    pil_image = pil_images[0] if pil_images else None
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
                prompt_cache_key=_prompt_cache_key(data, system_prompt, stage=stage),
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
        raise ValueError(f"Unsupported backend: {backend}")

    return raw


async def _run_audit(data: dict[str, Any], candidate: str, cancel_event) -> tuple[str, Any]:
    source = str(candidate or "")
    if not source.strip():
        raise ValueError("There is no prompt text to audit.")
    if cancel_event.is_set():
        raise GenerationCancelled("Generation cancelled.")
    audit_data = {**data, "system_prompt_preset": "none", "target_model": "audit"}
    audit_format = "json" if is_json_candidate(source) else "natural"
    try:
        raw = await dispatch_provider(
            audit_data,
            audit_block(),
            source,
            [],
            audit_format,
            cancel_event,
            stage="audit",
        )
    except Exception as exc:
        if cancel_event.is_set():
            raise GenerationCancelled("Generation cancelled.") from exc
        raise
    if cancel_event.is_set():
        raise GenerationCancelled("Generation cancelled.")
    return validate_audit_result(source, str(raw)), raw



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
        return web.json_response({
            **profiles_payload(),
            "general_schema_version": general.GENERAL_SCHEMA_VERSION,
            "preset_schema_version": PRESET_SCHEMA_VERSION,
        })

    @routes.get(f"{ROUTE_PREFIX}/prompt_presets")
    async def workflowx_unified_prompt_presets(_request):
        try:
            return web.json_response(prompt_presets_payload())
        except Exception as exc:
            return _json_error(str(exc), status=500)

    @routes.post(f"{ROUTE_PREFIX}/prompt_presets")
    async def workflowx_unified_save_prompt_preset(request):
        try:
            data = await request.json()
            return web.json_response({"ok": True, **save_preset(data)})
        except PromptPresetError as exc:
            return _json_error(str(exc))
        except Exception as exc:
            return _json_error(str(exc), status=500)

    @routes.post(f"{ROUTE_PREFIX}/prompt_presets/delete")
    async def workflowx_unified_delete_prompt_preset(request):
        try:
            data = await request.json()
            return web.json_response({"ok": True, **delete_preset(str(data.get("id") or ""))})
        except PromptPresetError as exc:
            return _json_error(str(exc))
        except Exception as exc:
            return _json_error(str(exc), status=500)

    @routes.post(f"{ROUTE_PREFIX}/prompt_presets/reset")
    async def workflowx_unified_reset_prompt_preset(request):
        try:
            data = await request.json()
            return web.json_response({"ok": True, **reset_preset(str(data.get("id") or ""))})
        except PromptPresetError as exc:
            return _json_error(str(exc))
        except Exception as exc:
            return _json_error(str(exc), status=500)

    @routes.get(f"{ROUTE_PREFIX}/general/presets")
    async def general_presets(request):
        return web.json_response({"presets": general.list_presets(), "general_schema_version": general.GENERAL_SCHEMA_VERSION})

    async def general_request(request, *, preview=False):
        data = {}
        generation_id = ""
        cancel_event = None
        try:
            data = await request.json()
            if not isinstance(data, dict):
                raise general.GeneralInputError("Invalid General request.")
            if data.get("general_schema_version") != general.GENERAL_SCHEMA_VERSION or data.get("schema_version") != SCHEMA_VERSION:
                raise general.GeneralInputError("General frontend/backend mismatch. Restart ComfyUI and hard-refresh the browser.")
            audit_mode = normalize_audit_mode(data.get("audit_mode"))
            values = [] if audit_mode == AUDIT_ONLY else _raw_image_values(data)
            if audit_mode == AUDIT_ONLY:
                fields = data.get("fields") if isinstance(data.get("fields"), dict) else {}
                user = str(fields.get("prompt_text") or "")
                if not user.strip():
                    raise general.GeneralInputError("Enter Prompt instructions before using Audit only.")
                system = audit_block()
            else:
                system, user = general.build_inputs(data, len(values))
            images = _decode_image_values(values)
            if len(images) != len(values):
                raise general.GeneralInputError("A connected image could not be read. Refresh or run its source node and try again.")
            # A caller cannot activate a legacy fallback or profile format here.
            provider_data = {**data, "system_prompt_preset": "none", "target_model": "general", "prompt_format": "natural", "generation_type": ""}
            if images:
                backend = str(data.get("backend") or "")
                capabilities = data.get("model_capabilities") or {}
                if isinstance(capabilities, dict) and capabilities.get("vision") is False:
                    raise general.GeneralInputError("The selected model cannot accept images. Choose a vision-capable model or disconnect the images.")
                if backend == "local" and str(data.get("mmproj") or "none").strip().lower() in {"", "none"}:
                    raise general.GeneralInputError("Connected images require a compatible vision mmproj. Select one or disconnect the images.")
                if backend == "deepseek" and not deepseek_backend.is_vision_model(str(data.get("model") or "")):
                    raise general.GeneralInputError("Choose a vision-capable DeepSeek model or disconnect the images.")
            if preview:
                return web.json_response({
                    "system_prompt": system, "user_prompt": user, "images_b64": values,
                    "general_schema_version": general.GENERAL_SCHEMA_VERSION,
                    "local_routing": {"preset": str(data.get("preset") or "none"), "image_count": len(values)},
                    "audit": {"mode": audit_mode, "status": "preview"},
                })
            generation_id = str(data.get("generation_id") or "")
            cancel_event = CancellationRegistry.begin(generation_id)
            if data.get("refresh_vram"):
                await asyncio.get_running_loop().run_in_executor(None, refresh_comfy_vram)
            if audit_mode == AUDIT_ONLY:
                try:
                    audited, raw = await _run_audit(provider_data, user, cancel_event)
                    final = audited
                    audit = {"mode": audit_mode, "status": "completed", "changed": audit_result_changed(user, audited), "error": ""}
                except GenerationCancelled:
                    raise
                except Exception as exc:
                    final = user
                    raw = user
                    audit = {"mode": audit_mode, "status": "failed", "changed": False, "error": str(exc)}
                return web.json_response({
                    "prompt": final,
                    "positive": final,
                    "negative": "",
                    "target_model": "general",
                    "prompt_format": "natural",
                    "audit": audit,
                })
            raw = await dispatch_provider(provider_data, system, user, images, "natural", cancel_event)
            if cancel_event.is_set():
                raise GenerationCancelled("Generation cancelled.")
            final = str(raw)
            audit = {"mode": audit_mode, "status": "not_requested", "changed": False, "error": ""}
            if audit_mode == AUDIT_ADD_PASS:
                try:
                    audit_source = final
                    final, _audit_raw = await _run_audit(provider_data, final, cancel_event)
                    audit = {"mode": audit_mode, "status": "completed", "changed": audit_result_changed(audit_source, final), "error": ""}
                except GenerationCancelled:
                    raise
                except Exception as exc:
                    audit = {"mode": audit_mode, "status": "failed", "changed": False, "error": str(exc)}
            return web.json_response({"prompt": final, "positive": final, "negative": "", "target_model": "general", "prompt_format": "natural", "audit": audit})
        except GenerationCancelled:
            return _json_error("Generation cancelled. Previous output kept.", status=409)
        except general.GeneralInputError as exc:
            return _json_error(str(exc))
        except Exception as exc:
            if cancel_event is not None and cancel_event.is_set():
                return _json_error("Generation cancelled. Previous output kept.", status=409)
            return _json_error(log_generation_error(exc, str(data.get("backend") or "")))
        finally:
            if generation_id:
                CancellationRegistry.finish(generation_id)

    @routes.post(f"{ROUTE_PREFIX}/general/preview")
    async def general_preview(request):
        return await general_request(request, preview=True)

    @routes.post(f"{ROUTE_PREFIX}/general/generate")
    async def general_generate(request):
        return await general_request(request)

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
        if target_model == "general":
            return _json_error("General must use the General generation route. Hard-refresh the browser.")
        if get_profile(target_model).engine != "standard":
            return _json_error("JsonX profiles must use the isolated Unified JsonX generation route.")
        prompt_format = normalize_format(target_model, str(data.get("prompt_format") or ""))
        negative_enabled = bool(data.get("negative_enabled")) and supports_negative(target_model)
        fields = data.get("fields") if isinstance(data.get("fields"), dict) else data
        try:
            audit_mode = normalize_audit_mode(data.get("audit_mode"))
        except ValueError as exc:
            return _json_error(str(exc))
        generation_type = normalize_generation_type(target_model, str(data.get("generation_type") or ""))
        raw_image_values = [] if audit_mode == AUDIT_ONLY else _raw_image_values(data)
        effective_image_values, ignored_image_count = effective_generation_images(
            generation_type, raw_image_values
        )
        pil_images = _decode_image_values(effective_image_values)
        pil_image = pil_images[0] if pil_images else None
        reference_count = len(pil_images)
        if audit_mode != AUDIT_ONLY:
            try:
                validate_generation_image_count(generation_type, reference_count)
            except ValueError as exc:
                return _json_error(str(exc))
        if audit_mode == AUDIT_ONLY:
            system_prompt = audit_block()
            user_prompt = str(fields.get("prompt_text") or "")
            if not user_prompt.strip():
                return _json_error("Enter Prompt instructions before using Audit only.")
        else:
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
            if audit_mode == AUDIT_ONLY:
                try:
                    audited, raw = await _run_audit(data, user_prompt, cancel_event)
                    audit = {"mode": audit_mode, "status": "completed", "changed": audit_result_changed(user_prompt, audited), "error": ""}
                except GenerationCancelled:
                    raise
                except Exception as exc:
                    audited = user_prompt
                    raw = user_prompt
                    audit = {"mode": audit_mode, "status": "failed", "changed": False, "error": str(exc)}
                return web.json_response({
                    "prompt": audited,
                    "positive": audited,
                    "negative": "",
                    "raw": raw,
                    "target_model": target_model,
                    "prompt_format": prompt_format,
                    "negative_enabled": False,
                    "generation_type": generation_type,
                    "nsfw_enabled": False,
                    "connected_image_count": 0,
                    "image_count": 0,
                    "ignored_image_count": 0,
                    "image_state": resolve_image_state(generation_type, 0),
                    "schema_version": SCHEMA_VERSION,
                    "diagnostics": {},
                    "audit": audit,
                })
            raw = await dispatch_provider(data, system_prompt, user_prompt, pil_images, prompt_format, cancel_event)
            if cancel_event.is_set():
                raise GenerationCancelled("Generation cancelled.")
            parsed = parse_generation_response(target_model, prompt_format, str(raw), negative_enabled)
            diagnostics = dict(getattr(raw, "diagnostics", {}) or {})
            if backend == "grok":
                capabilities = data.get("model_capabilities") if isinstance(data.get("model_capabilities"), dict) else {}
                if capabilities.get("context_length") is not None:
                    diagnostics["context_length"] = int(capabilities.get("context_length") or 0)
            audit = {"mode": audit_mode, "status": "not_requested", "changed": False, "error": ""}
            if audit_mode == AUDIT_ADD_PASS:
                try:
                    audit_source = parsed["positive"]
                    audited_positive, _audit_raw = await _run_audit(data, audit_source, cancel_event)
                    parsed["positive"] = audited_positive
                    parsed["prompt"] = assemble_prompt(
                        audited_positive,
                        parsed["negative"],
                        negative_enabled,
                        prompt_format,
                    )
                    audit = {"mode": audit_mode, "status": "completed", "changed": audit_result_changed(audit_source, audited_positive), "error": ""}
                except GenerationCancelled:
                    raise
                except Exception as exc:
                    audit = {"mode": audit_mode, "status": "failed", "changed": False, "error": str(exc)}
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
                    "audit": audit,
                }
            )
        except GenerationCancelled as exc:
            return _json_error(str(exc), status=409)
        except Exception as exc:
            return _json_error(log_generation_error(exc, backend))
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
