from __future__ import annotations

import base64
import io
from typing import Any

import requests
from PIL import Image
from ...generation_errors import ProviderHTTPError

from .errors import JsonXProviderError


API_ROOT = "https://api.x.ai/v1"
REASONING_EFFORTS = {"default", "low", "medium", "high", "xhigh"}


class GrokResponse(str):
    diagnostics: dict[str, Any]

    def __new__(cls, value: str, diagnostics: dict[str, Any] | None = None):
        instance = super().__new__(cls, value)
        instance.diagnostics = diagnostics or {}
        return instance


def _headers(api_key: str) -> dict[str, str]:
    if not str(api_key or "").strip():
        raise JsonXProviderError("No xAI API key provided.", provider="grok")
    return {
        "Authorization": f"Bearer {str(api_key).strip()}",
        "Content-Type": "application/json",
    }


def _safe_error(response: requests.Response) -> str:
    try:
        payload = response.json()
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            return str(error.get("message") or error.get("code") or response.text[:300])
        return str(error or response.text[:300])
    except Exception:
        return response.text[:300]


def _reasoning_options(model_id: str) -> list[str]:
    lowered = model_id.lower()
    if "grok-4.6" in lowered:
        return ["default", "low", "medium", "high", "xhigh"]
    if "grok-4.5" in lowered or "reasoning" in lowered:
        return ["default", "low", "medium", "high"]
    return ["default"]


def list_models(api_key: str, timeout: float = 120) -> list[dict[str, Any]]:
    headers = _headers(api_key)
    response = requests.get(f"{API_ROOT}/language-models", headers=headers, timeout=timeout)
    if response.status_code != 200:
        raise JsonXProviderError(
            str(ProviderHTTPError(response.status_code, _safe_error(response), "grok")),
            provider="grok",
            diagnostics={"event": "model_list_error", "http_status": response.status_code},
        )
    context_by_id: dict[str, int] = {}
    try:
        context_response = requests.get(f"{API_ROOT}/models", headers=headers, timeout=timeout)
        if context_response.status_code == 200:
            for item in context_response.json().get("data", []):
                if isinstance(item, dict) and item.get("id") and item.get("context_length") is not None:
                    context_by_id[str(item["id"])] = int(item.get("context_length") or 0)
    except Exception:
        context_by_id = {}
    models: list[dict[str, Any]] = []
    for item in response.json().get("models", []):
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "").strip()
        outputs = [str(value) for value in item.get("output_modalities", [])]
        if not model_id or (outputs and "text" not in outputs):
            continue
        inputs = [str(value) for value in item.get("input_modalities", [])]
        models.append(
            {
                "id": model_id,
                "display_name": model_id,
                "aliases": [str(value) for value in item.get("aliases", []) if str(value)],
                "vision": "image" in inputs,
                "input_modalities": inputs,
                "output_modalities": outputs,
                "context_length": context_by_id.get(model_id, 0),
                "reasoning_options": _reasoning_options(model_id),
            }
        )
    return sorted(models, key=lambda value: value["id"].lower())


def _image_data_url(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode('ascii')}"


def _extract_text(payload: dict[str, Any]) -> str:
    chunks: list[str] = []
    for item in payload.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text":
                chunks.append(str(content.get("text") or ""))
            elif isinstance(content, dict) and content.get("type") == "refusal":
                chunks.append(str(content.get("refusal") or ""))
    text = "".join(chunks).strip()
    if not text:
        raise JsonXProviderError(
            "xAI returned no text output.",
            provider="grok",
            diagnostics={"event": "empty_response", "status": payload.get("status")},
        )
    return text


def _diagnostics(payload: dict[str, Any]) -> dict[str, Any]:
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    input_details = usage.get("input_tokens_details") if isinstance(usage.get("input_tokens_details"), dict) else {}
    output_details = usage.get("output_tokens_details") if isinstance(usage.get("output_tokens_details"), dict) else {}
    return {
        "provider": "grok",
        "model": str(payload.get("model") or ""),
        "status": str(payload.get("status") or ""),
        "input_tokens": int(usage.get("input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "reasoning_tokens": int(output_details.get("reasoning_tokens") or 0),
        "cached_tokens": int(input_details.get("cached_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }


def generate(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    *,
    pil_images: list[Image.Image] | None = None,
    timeout: float = 120,
    response_format: str = "json",
    max_output_tokens: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    reasoning_effort: str = "default",
    prompt_cache_key: str = "",
) -> GrokResponse:
    if not str(model or "").strip():
        raise JsonXProviderError("No Grok model selected.", provider="grok")
    reasoning = str(reasoning_effort or "default").strip().lower()
    if reasoning not in REASONING_EFFORTS:
        raise JsonXProviderError(f"Unsupported Grok reasoning effort: {reasoning_effort}.", provider="grok")
    supported_reasoning = _reasoning_options(str(model))
    if reasoning not in supported_reasoning:
        raise JsonXProviderError(
            f"Grok model '{model}' does not advertise reasoning effort '{reasoning}'. "
            f"Supported values: {', '.join(supported_reasoning)}.",
            provider="grok",
        )
    content: str | list[dict[str, str]] = user_prompt
    if pil_images:
        content = [{"type": "input_text", "text": user_prompt}]
        content.extend({"type": "input_image", "image_url": _image_data_url(image)} for image in pil_images)
    body: dict[str, Any] = {
        "model": str(model).strip(),
        "input": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        "store": False,
        "text": {"format": {"type": "json_object" if response_format == "json" else "text"}},
    }
    if max_output_tokens is not None and int(max_output_tokens) > 0:
        body["max_output_tokens"] = int(max_output_tokens)
    if temperature is not None:
        body["temperature"] = float(temperature)
    if top_p is not None:
        body["top_p"] = float(top_p)
    if reasoning != "default":
        body["reasoning"] = {"effort": reasoning}
    if str(prompt_cache_key or "").strip():
        body["prompt_cache_key"] = str(prompt_cache_key).strip()
    response = requests.post(f"{API_ROOT}/responses", headers=_headers(api_key), json=body, timeout=timeout)
    if response.status_code != 200:
        raise JsonXProviderError(
            str(ProviderHTTPError(response.status_code, _safe_error(response), "grok")),
            provider="grok",
            diagnostics={"event": "generation_http_error", "http_status": response.status_code},
        )
    payload = response.json()
    return GrokResponse(_extract_text(payload), _diagnostics(payload))
