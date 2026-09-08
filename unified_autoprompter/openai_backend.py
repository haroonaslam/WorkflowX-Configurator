from __future__ import annotations

import base64
import io
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests
from PIL import Image


DEFAULT_BASE_URL = "http://localhost:1234/v1"
SERVER_TYPES = {"auto", "generic", "lm_studio", "unsloth"}
LIFECYCLE_MODES = {"server_managed", "keep_loaded", "unload_after"}
REASONING_EFFORTS = {"default", "none", "on", "minimal", "low", "medium", "high", "max", "xhigh"}
_NON_GENERATION_PREFIXES = (
    "dall-e", "gpt-image", "omni-moderation", "text-embedding", "tts-", "whisper",
)
_NON_GENERATION_TOKENS = (
    "audio", "embedding", "moderation", "realtime", "speech", "transcribe", "transcription",
)


class ProviderResponse(str):
    diagnostics: dict[str, Any]

    def __new__(cls, value: str, diagnostics: dict[str, Any] | None = None):
        instance = super().__new__(cls, value)
        instance.diagnostics = diagnostics or {}
        return instance


def _base_url(base_url: str | None) -> str:
    return (base_url or DEFAULT_BASE_URL).strip().rstrip("/")


def _server_root(base_url: str | None) -> str:
    parsed = urlsplit(_base_url(base_url))
    path = parsed.path.rstrip("/")
    for suffix in ("/api/v1", "/v1", "/api"):
        if path.endswith(suffix):
            path = path[: -len(suffix)]
            break
    return urlunsplit((parsed.scheme, parsed.netloc, path.rstrip("/"), "", "")).rstrip("/")


def _native_url(base_url: str | None, path: str) -> str:
    return f"{_server_root(base_url)}{path}"


def _headers(api_key: str | None = "") -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    key = str(api_key or "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _err(resp) -> str:
    try:
        payload = resp.json()
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        detail = payload.get("detail") if isinstance(payload, dict) else ""
        message = (error.get("message") if isinstance(error, dict) else "") or detail or resp.text[:200]
    except Exception:
        message = resp.text[:200]
    return f"OpenAI-compatible API {resp.status_code}: {message}"


def _looks_like_generation_model(model_id: str) -> bool:
    lowered = model_id.lower()
    if lowered.startswith(_NON_GENERATION_PREFIXES):
        return False
    return not any(token in lowered for token in _NON_GENERATION_TOKENS)


def _standard_models(payload: Any) -> list[dict[str, Any]]:
    fallback: list[dict[str, Any]] = []
    generation_models: list[dict[str, Any]] = []
    data = payload.get("data", []) if isinstance(payload, dict) else []
    for model in data if isinstance(data, list) else []:
        if not isinstance(model, dict):
            continue
        model_id = str(model.get("id") or "").strip()
        if not model_id:
            continue
        item: dict[str, Any] = {
            "id": model_id,
            "display_name": str(model.get("display_name") or model_id),
        }
        if "loaded" in model:
            item["loaded"] = bool(model.get("loaded"))
        fallback.append(item)
        if _looks_like_generation_model(model_id):
            generation_models.append(item)
    return sorted(generation_models or fallback, key=lambda item: item["id"].lower())


def _lm_studio_models(payload: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    models = payload.get("models", []) if isinstance(payload, dict) else []
    for model in models if isinstance(models, list) else []:
        if not isinstance(model, dict) or model.get("type") == "embedding":
            continue
        model_id = str(model.get("key") or "").strip()
        if not model_id or not _looks_like_generation_model(model_id):
            continue
        item: dict[str, Any] = {
            "id": model_id,
            "display_name": str(model.get("display_name") or model_id),
            "loaded": bool(model.get("loaded_instances")),
        }
        instances = model.get("loaded_instances")
        if isinstance(instances, list) and instances and isinstance(instances[0], dict):
            instance_id = str(instances[0].get("id") or "").strip()
            if instance_id:
                item["instance_id"] = instance_id
        capabilities = model.get("capabilities") if isinstance(model.get("capabilities"), dict) else {}
        item["vision"] = bool(capabilities.get("vision"))
        reasoning = capabilities.get("reasoning") if isinstance(capabilities.get("reasoning"), dict) else {}
        allowed = [str(value) for value in reasoning.get("allowed_options", []) if str(value)]
        if allowed:
            item["reasoning_options"] = allowed
            item["reasoning_default"] = str(reasoning.get("default") or "")
        result.append(item)
    return sorted(result, key=lambda item: item["id"].lower())


def _server_header(response: Any) -> str:
    headers = getattr(response, "headers", {}) or {}
    try:
        return str(headers.get("server") or headers.get("Server") or "").lower()
    except Exception:
        return ""


def _safe_get(url: str, api_key: str | None, timeout: float):
    try:
        response = requests.get(url, headers=_headers(api_key), timeout=timeout)
        return response if response.status_code == 200 else None
    except Exception:
        return None


def _normalize_server_type(value: Any) -> str:
    normalized = str(value or "auto").strip().lower().replace("-", "_")
    normalized = {"lmstudio": "lm_studio", "unsloth_studio": "unsloth"}.get(normalized, normalized)
    return normalized if normalized in SERVER_TYPES else "auto"


def _normalize_lifecycle(value: Any) -> str:
    normalized = str(value or "server_managed").strip().lower().replace("-", "_")
    return normalized if normalized in LIFECYCLE_MODES else "server_managed"


def _normalize_reasoning(value: Any) -> str:
    normalized = str(value or "default").strip().lower().replace("-", "_").replace(" ", "_")
    normalized = {
        "off": "none", "extra_high": "xhigh", "provider_default": "default",
    }.get(normalized, normalized)
    return normalized if normalized in REASONING_EFFORTS else "default"


def _unsloth_reasoning(status_payload: Any) -> dict[str, Any]:
    if not isinstance(status_payload, dict):
        return {}
    options = status_payload.get("reasoning_effort_levels")
    options = [str(value) for value in options] if isinstance(options, list) else []
    return {
        "supported": bool(status_payload.get("supports_reasoning")),
        "style": str(status_payload.get("reasoning_style") or ""),
        "options": options,
        "always_on": bool(status_payload.get("reasoning_always_on")),
        "supports_preserve_thinking": bool(status_payload.get("supports_preserve_thinking")),
        "vision": bool(status_payload.get("supports_vision") or status_payload.get("vision")),
        "active_context": int(status_payload.get("context_length") or status_payload.get("active_context_length") or 0),
        "native_context": int(status_payload.get("native_context_length") or 0),
        "max_context": int(status_payload.get("max_context_length") or 0),
    }


def discover_models(
    base_url: str | None,
    api_key: str | None = "",
    timeout: float = 120,
    server_type: str = "auto",
) -> dict[str, Any]:
    response = requests.get(f"{_base_url(base_url)}/models", headers=_headers(api_key), timeout=timeout)
    if response.status_code != 200:
        raise ValueError(_err(response))
    standard = _standard_models(response.json())
    requested = _normalize_server_type(server_type)
    detected = requested
    status_payload: dict[str, Any] = {}
    lm_payload: dict[str, Any] = {}

    if requested == "auto":
        header = _server_header(response)
        if "unsloth" in header:
            detected = "unsloth"
        elif "lm studio" in header or "lmstudio" in header:
            detected = "lm_studio"
        else:
            unsloth_response = _safe_get(_native_url(base_url, "/api/inference/status"), api_key, timeout)
            if unsloth_response is not None:
                detected = "unsloth"
                payload = unsloth_response.json()
                status_payload = payload if isinstance(payload, dict) else {}
            else:
                lm_response = _safe_get(_native_url(base_url, "/api/v1/models"), api_key, timeout)
                if lm_response is not None:
                    payload = lm_response.json()
                    if isinstance(payload, dict) and isinstance(payload.get("models"), list):
                        detected = "lm_studio"
                        lm_payload = payload
                if detected == "auto":
                    detected = "generic"

    if detected == "unsloth" and not status_payload:
        status_response = _safe_get(_native_url(base_url, "/api/inference/status"), api_key, timeout)
        if status_response is not None:
            payload = status_response.json()
            status_payload = payload if isinstance(payload, dict) else {}
    if detected == "lm_studio" and not lm_payload:
        lm_response = _safe_get(_native_url(base_url, "/api/v1/models"), api_key, timeout)
        if lm_response is not None:
            payload = lm_response.json()
            lm_payload = payload if isinstance(payload, dict) else {}

    models = _lm_studio_models(lm_payload) if lm_payload else standard
    return {
        "models": models or standard,
        "server_type": detected,
        "reasoning": _unsloth_reasoning(status_payload) if detected == "unsloth" else {},
    }


def list_models(base_url: str | None, api_key: str | None = "", timeout: float = 120) -> list[dict[str, Any]]:
    response = requests.get(f"{_base_url(base_url)}/models", headers=_headers(api_key), timeout=timeout)
    if response.status_code != 200:
        raise ValueError(_err(response))
    return _standard_models(response.json())


def _image_data_url(pil_image: Image.Image) -> str:
    buffer = io.BytesIO()
    pil_image.convert("RGB").save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _strip_thinking_blocks(value: str) -> str:
    cleaned = re.sub(r"<think(?:\s[^>]*)?>.*?</think\s*>", "", value, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"\[Start thinking\].*?\[End thinking\]", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    return cleaned.strip()


def _extract_text(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        raise ValueError("OpenAI-compatible server returned no choices.")
    message = choices[0].get("message") if isinstance(choices[0], dict) else {}
    content = message.get("content") if isinstance(message, dict) else ""
    if isinstance(content, str) and content.strip():
        text = _strip_thinking_blocks(content)
        if text:
            return text
    if isinstance(content, list):
        chunks = [item["text"] for item in content if isinstance(item, dict) and isinstance(item.get("text"), str)]
        text = _strip_thinking_blocks("".join(chunks))
        if text:
            return text
    raise ValueError("OpenAI-compatible server returned no text output.")


def _extract_lm_studio_text(payload: dict) -> tuple[str, str, dict[str, Any]]:
    messages = []
    output = payload.get("output", []) if isinstance(payload.get("output"), list) else []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if isinstance(content, str):
            messages.append(content)
        elif isinstance(content, list):
            messages.extend(
                str(part.get("text") or part.get("content") or "")
                for part in content
                if isinstance(part, dict) and (part.get("text") or part.get("content"))
            )
    text = _strip_thinking_blocks("\n".join(messages))
    if not text:
        raise ValueError("LM Studio returned no text output.")
    stats = payload.get("stats") if isinstance(payload.get("stats"), dict) else {}
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    diagnostics = {
        "provider": "lm_studio",
        "model": str(payload.get("model") or ""),
        "input_tokens": int(stats.get("input_tokens") or usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
        "output_tokens": int(
            stats.get("total_output_tokens") or usage.get("output_tokens") or usage.get("completion_tokens") or 0
        ),
        "reasoning_tokens": int(stats.get("reasoning_output_tokens") or usage.get("reasoning_tokens") or 0),
        "tokens_per_second": float(stats.get("tokens_per_second") or stats.get("tok_per_sec") or 0),
        "time_to_first_token": float(
            stats.get("time_to_first_token_seconds") or stats.get("time_to_first_token") or stats.get("ttft") or 0
        ),
        "model_load_time": float(
            stats.get("model_load_time_seconds") or stats.get("model_load_time") or stats.get("load_time") or 0
        ),
    }
    return text, str(payload.get("model_instance_id") or "").strip(), diagnostics


def _console_unload_warning(server_type: str, message: str) -> None:
    safe = " ".join(str(message or "unknown unload error").split())[:300]
    print(f"[WorkflowX Unified] Warning: {server_type} model unload failed; generation output was kept. {safe}", flush=True)


def _lm_studio_instance_id(base_url: str | None, api_key: str, model: str, timeout: float) -> str:
    response = _safe_get(_native_url(base_url, "/api/v1/models"), api_key, timeout)
    if response is None:
        return ""
    for item in _lm_studio_models(response.json()):
        if item.get("id") == model and item.get("instance_id"):
            return str(item["instance_id"])
    return ""


def unload_model(
    base_url: str | None,
    api_key: str | None,
    model: str,
    timeout: float = 120,
    server_type: str = "auto",
    instance_id: str = "",
) -> bool:
    provider = _normalize_server_type(server_type)
    if provider == "auto":
        try:
            provider = str(discover_models(base_url, api_key, timeout, "auto").get("server_type") or "generic")
        except Exception:
            provider = "generic"
    try:
        if provider == "lm_studio":
            resolved = str(instance_id or "").strip() or _lm_studio_instance_id(base_url, str(api_key or ""), model, timeout)
            if not resolved:
                _console_unload_warning("LM Studio", "No loaded instance ID was available.")
                return False
            response = requests.post(
                _native_url(base_url, "/api/v1/models/unload"), headers=_headers(api_key),
                json={"instance_id": resolved}, timeout=timeout,
            )
        elif provider == "unsloth":
            response = requests.post(
                _native_url(base_url, "/api/inference/unload"), headers=_headers(api_key),
                json={"model_path": model}, timeout=timeout,
            )
        else:
            _console_unload_warning("Generic OpenAI-compatible", "The OpenAI API has no model-unload operation.")
            return False
        if 200 <= response.status_code < 300:
            return True
        _console_unload_warning(provider, f"Server returned HTTP {response.status_code}.")
        return False
    except Exception as exc:
        _console_unload_warning(provider, f"{type(exc).__name__}: {exc}")
        return False


def _detect_server_for_generation(base_url: str | None, api_key: str, timeout: float, server_type: str) -> str:
    requested = _normalize_server_type(server_type)
    if requested != "auto":
        return requested
    try:
        return str(discover_models(base_url, api_key, timeout, "auto").get("server_type") or "generic")
    except Exception:
        return "generic"


def _chat_content(user_prompt: str, images: list[Image.Image]) -> str | list[dict[str, Any]]:
    if not images:
        return user_prompt
    content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
    content.extend(
        {"type": "image_url", "image_url": {"url": _image_data_url(image), "detail": "auto"}}
        for image in images
    )
    return content


def _generate_lm_studio_native(
    base_url: str | None,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    images: list[Image.Image],
    timeout: float,
    reasoning: str,
    options: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    lm_reasoning = None if reasoning == "default" else ("off" if reasoning == "none" else reasoning)
    if lm_reasoning is not None and lm_reasoning not in {"off", "on", "low", "medium", "high"}:
        raise ValueError(f"LM Studio does not support reasoning setting '{reasoning}' through its native chat API.")
    input_value: str | list[dict[str, str]] = user_prompt
    if images:
        input_value = [{"type": "message", "content": user_prompt}]
        input_value.extend({"type": "image", "data_url": _image_data_url(image)} for image in images)
    body = {
        "model": model,
        "input": input_value,
        **({"system_prompt": system_prompt} if system_prompt else {}),
        "stream": False,
        "store": False,
    }
    if lm_reasoning is not None:
        body["reasoning"] = lm_reasoning
    for key in (
        "max_output_tokens",
        "context_length",
        "temperature",
        "top_p",
        "top_k",
        "min_p",
        "repeat_penalty",
    ):
        if options.get(key) is not None:
            body[key] = options[key]
    response = requests.post(
        _native_url(base_url, "/api/v1/chat"), headers=_headers(api_key), json=body, timeout=timeout
    )
    if response.status_code != 200:
        raise ValueError(_err(response))
    return _extract_lm_studio_text(response.json())


def generate(
    base_url: str | None,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    pil_image: Image.Image | None = None,
    pil_images: list[Image.Image] | None = None,
    timeout: float = 120,
    unload_after: bool | None = None,
    server_type: str = "auto",
    lifecycle: str = "server_managed",
    reasoning_effort: str = "default",
    provider_options: dict[str, Any] | None = None,
) -> str:
    if not model:
        raise ValueError("No OpenAI-compatible model selected.")
    images = list(pil_images or [])
    if not images and pil_image is not None:
        images = [pil_image]
    lifecycle_mode = _normalize_lifecycle(lifecycle)
    if unload_after is not None:
        lifecycle_mode = "unload_after" if unload_after else "keep_loaded"
    reasoning = _normalize_reasoning(reasoning_effort)
    provider = _detect_server_for_generation(base_url, api_key, timeout, server_type)
    instance_id = ""
    diagnostics: dict[str, Any] = {"provider": provider, "model": model}
    options = provider_options if isinstance(provider_options, dict) else {}

    if provider == "lm_studio":
        text, instance_id, diagnostics = _generate_lm_studio_native(
            base_url, api_key, model, system_prompt, user_prompt, images, timeout, reasoning, options
        )
    else:
        body: dict[str, Any] = {
            "model": model,
            "stream": False,
            "messages": [
                *([{"role": "system", "content": system_prompt}] if system_prompt else []),
                {"role": "user", "content": _chat_content(user_prompt, images)},
            ],
        }
        parameter_map = {
            "max_new_tokens": "max_tokens",
            "temperature": "temperature",
            "top_p": "top_p",
            "top_k": "top_k",
            "min_p": "min_p",
            "repetition_penalty": "repetition_penalty",
            "presence_penalty": "presence_penalty",
        }
        for source, destination in parameter_map.items():
            if options.get(source) is not None:
                body[destination] = options[source]
        if provider == "unsloth" and reasoning != "default":
            if reasoning == "none":
                body["enable_thinking"] = False
                body["reasoning_effort"] = "none"
            elif reasoning == "on":
                body["enable_thinking"] = True
            else:
                body["enable_thinking"] = True
                body["reasoning_effort"] = reasoning
        if provider == "unsloth" and options.get("preserve_thinking") is not None:
            body["preserve_thinking"] = bool(options.get("preserve_thinking"))
        elif provider == "generic" and reasoning != "default":
            if reasoning == "on":
                raise ValueError("Generic OpenAI-compatible servers do not define an 'on' reasoning value.")
            body["reasoning_effort"] = reasoning
        response = requests.post(
            f"{_base_url(base_url)}/chat/completions", headers=_headers(api_key), json=body, timeout=timeout
        )
        if response.status_code != 200:
            raise ValueError(_err(response))
        payload = response.json()
        text = _extract_text(payload)
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        diagnostics = {
            "provider": provider,
            "model": str(payload.get("model") or model),
            "input_tokens": int(usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("completion_tokens") or 0),
            "reasoning_tokens": int((usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0)
            if isinstance(usage.get("completion_tokens_details"), dict)
            else 0,
            "total_tokens": int(usage.get("total_tokens") or 0),
        }

    if lifecycle_mode == "unload_after":
        unload_model(base_url, api_key, model, timeout, provider, instance_id)
    return ProviderResponse(text, diagnostics)
