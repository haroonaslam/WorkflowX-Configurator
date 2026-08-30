from __future__ import annotations

import base64
import io
import json
from typing import Any

import requests
from PIL import Image


API_ROOT = "https://api.deepseek.com"
THINKING_MODES = {"default", "enabled", "disabled"}
REASONING_EFFORTS = {"default", "low", "high", "max"}
CURRENT_CONTEXT_LENGTH = 1_000_000
CURRENT_MAX_OUTPUT_TOKENS = 384 * 1024
VISION_MODELS = {"deepseek-v4-flash-vision-exp"}
IMAGE_DETAIL_LEVELS = {"default", "auto", "low", "high", "original"}
MAX_INLINE_IMAGE_BYTES = 32 * 1024 * 1024
MAX_REQUEST_BYTES = 48 * 1024 * 1024


class DeepSeekResponse(str):
    diagnostics: dict[str, Any]

    def __new__(cls, value: str, diagnostics: dict[str, Any] | None = None):
        instance = super().__new__(cls, value)
        instance.diagnostics = diagnostics or {}
        return instance


def _headers(api_key: str) -> dict[str, str]:
    key = str(api_key or "").strip()
    if not key:
        raise ValueError("No DeepSeek API key provided.")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _safe_error(response: requests.Response) -> str:
    try:
        payload = response.json()
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            return str(error.get("message") or error.get("code") or response.text[:300])
        return str(error or response.text[:300])
    except Exception:
        return response.text[:300]


def _model_capabilities(model_id: str) -> dict[str, Any]:
    lowered = str(model_id or "").strip().lower()
    current_v4 = lowered.startswith("deepseek-v4-")
    return {
        "vision": is_vision_model(lowered),
        "input_modalities": ["text", "image"] if is_vision_model(lowered) else ["text"],
        "output_modalities": ["text"],
        "context_length": CURRENT_CONTEXT_LENGTH if current_v4 else 0,
        "max_output_tokens": CURRENT_MAX_OUTPUT_TOKENS if current_v4 else 0,
        "thinking_options": ["default", "enabled", "disabled"],
        "reasoning_options": ["default", "low", "high", "max"],
    }


def is_vision_model(model_id: str) -> bool:
    return str(model_id or "").strip().lower() in VISION_MODELS


def _image_data_url(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    raw = buffer.getvalue()
    if len(raw) > MAX_INLINE_IMAGE_BYTES:
        raise ValueError("A DeepSeek inline image exceeds the 32 MiB per-image limit.")
    return f"data:image/png;base64,{base64.b64encode(raw).decode('ascii')}"


def list_models(api_key: str, timeout: float = 120) -> list[dict[str, Any]]:
    response = requests.get(f"{API_ROOT}/models", headers=_headers(api_key), timeout=timeout)
    if response.status_code != 200:
        raise ValueError(f"DeepSeek API {response.status_code}: {_safe_error(response)}")
    payload = response.json()
    models: list[dict[str, Any]] = []
    for item in payload.get("data", []):
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "").strip()
        if not model_id:
            continue
        models.append(
            {
                "id": model_id,
                "display_name": model_id,
                "owned_by": str(item.get("owned_by") or "deepseek"),
                **_model_capabilities(model_id),
            }
        )
    return sorted(models, key=lambda value: value["id"].lower())


def _effective_thinking(model: str, requested: str) -> str:
    lowered_model = str(model or "").strip().lower()
    if lowered_model == "deepseek-chat":
        return "disabled"
    if lowered_model == "deepseek-reasoner":
        return "enabled"
    return requested


def _diagnostics(payload: dict[str, Any], thinking: str, reasoning_effort: str) -> dict[str, Any]:
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    completion_details = (
        usage.get("completion_tokens_details")
        if isinstance(usage.get("completion_tokens_details"), dict)
        else {}
    )
    choices = payload.get("choices") if isinstance(payload.get("choices"), list) else []
    first = choices[0] if choices and isinstance(choices[0], dict) else {}
    return {
        "provider": "deepseek",
        "model": str(payload.get("model") or ""),
        "finish_reason": str(first.get("finish_reason") or ""),
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "reasoning_tokens": int(completion_details.get("reasoning_tokens") or 0),
        "cache_hit_tokens": int(usage.get("prompt_cache_hit_tokens") or 0),
        "cache_miss_tokens": int(usage.get("prompt_cache_miss_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
        "system_fingerprint": str(payload.get("system_fingerprint") or ""),
        "thinking": thinking,
        "reasoning_effort": reasoning_effort,
    }


def generate(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    *,
    pil_images: list[Image.Image] | None = None,
    timeout: float = 120,
    prompt_format: str = "natural",
    max_tokens: int | None = None,
    thinking: str = "default",
    reasoning_effort: str = "default",
    temperature: float | None = None,
    top_p: float | None = None,
    image_detail: str = "default",
) -> DeepSeekResponse:
    model_id = str(model or "").strip()
    if not model_id:
        raise ValueError("No DeepSeek model selected.")
    images = list(pil_images or [])
    if images and not is_vision_model(model_id):
        raise ValueError(f"The selected DeepSeek model '{model_id}' does not accept image input.")
    detail = str(image_detail or "default").strip().lower()
    if detail not in IMAGE_DETAIL_LEVELS:
        raise ValueError(f"Unsupported DeepSeek image detail level: {image_detail}.")
    thinking_mode = str(thinking or "default").strip().lower()
    if thinking_mode not in THINKING_MODES:
        raise ValueError(f"Unsupported DeepSeek thinking mode: {thinking}.")
    effort = str(reasoning_effort or "default").strip().lower()
    if effort not in REASONING_EFFORTS:
        raise ValueError(f"Unsupported DeepSeek reasoning effort: {reasoning_effort}.")
    effective_thinking = _effective_thinking(model_id, thinking_mode)

    user_content: str | list[dict[str, Any]] = user_prompt
    if images:
        user_content = [{"type": "text", "text": user_prompt}]
        for image in images:
            image_url: dict[str, Any] = {"url": _image_data_url(image)}
            if detail != "default":
                image_url["detail"] = detail
            user_content.append({"type": "image_url", "image_url": image_url})

    body: dict[str, Any] = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
        "response_format": {
            "type": "json_object" if str(prompt_format).strip().lower() == "json" else "text"
        },
    }
    if max_tokens is not None and int(max_tokens) > 0:
        body["max_tokens"] = int(max_tokens)
    if thinking_mode != "default" and model_id.lower() not in {"deepseek-chat", "deepseek-reasoner"}:
        body["thinking"] = {"type": thinking_mode}
    if effective_thinking != "disabled" and effort != "default":
        body["reasoning_effort"] = effort
    if effective_thinking == "disabled":
        if temperature is not None:
            body["temperature"] = float(temperature)
        if top_p is not None:
            body["top_p"] = float(top_p)

    if len(json.dumps(body, ensure_ascii=False).encode("utf-8")) > MAX_REQUEST_BYTES:
        raise ValueError("The DeepSeek request exceeds the 48 MiB inline request-body limit. Use smaller images.")

    response = requests.post(
        f"{API_ROOT}/chat/completions",
        headers=_headers(api_key),
        json=body,
        timeout=timeout,
    )
    if response.status_code != 200:
        raise ValueError(f"DeepSeek API {response.status_code}: {_safe_error(response)}")
    payload = response.json()
    choices = payload.get("choices") if isinstance(payload.get("choices"), list) else []
    first = choices[0] if choices and isinstance(choices[0], dict) else {}
    message = first.get("message") if isinstance(first.get("message"), dict) else {}
    text = str(message.get("content") or "").strip()
    if not text:
        finish = str(first.get("finish_reason") or "unknown")
        raise ValueError(f"DeepSeek returned no final text (finish reason: {finish}).")
    return DeepSeekResponse(text, _diagnostics(payload, effective_thinking, effort))
