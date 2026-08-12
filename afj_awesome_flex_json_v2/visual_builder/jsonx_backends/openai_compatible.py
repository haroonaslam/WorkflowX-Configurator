from __future__ import annotations

import base64
import io
from urllib.parse import urlsplit, urlunsplit

import requests
from PIL import Image

from .errors import JsonXProviderError


DEFAULT_BASE_URL = "http://localhost:1234/v1"
_NON_GENERATION_PREFIXES = (
    "dall-e",
    "gpt-image",
    "omni-moderation",
    "text-embedding",
    "tts-",
    "whisper",
)
_NON_GENERATION_TOKENS = (
    "audio",
    "embedding",
    "moderation",
    "realtime",
    "speech",
    "transcribe",
    "transcription",
)


def _base_url(base_url: str | None) -> str:
    return (base_url or DEFAULT_BASE_URL).strip().rstrip("/")


def _headers(api_key: str | None = "") -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    key = str(api_key or "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _safe_error(response: requests.Response) -> str:
    try:
        error = response.json().get("error", {})
        return str(error.get("message") or response.text[:200])
    except Exception:
        return response.text[:200]


def _looks_like_generation_model(model_id: str) -> bool:
    lowered = model_id.lower()
    if lowered.startswith(_NON_GENERATION_PREFIXES):
        return False
    return not any(token in lowered for token in _NON_GENERATION_TOKENS)


def list_models(
    base_url: str | None,
    api_key: str | None = "",
    timeout: float = 120,
) -> list[dict[str, str]]:
    response = requests.get(
        f"{_base_url(base_url)}/models",
        headers=_headers(api_key),
        timeout=timeout,
    )
    if response.status_code != 200:
        raise JsonXProviderError(
            f"OpenAI-compatible API {response.status_code}: {_safe_error(response)}",
            provider="openai",
            diagnostics={"event": "model_list_error", "http_status": response.status_code},
        )
    fallback = []
    generation_models = []
    for model in response.json().get("data", []):
        model_id = str(model.get("id") or "").strip()
        if not model_id:
            continue
        item = {"id": model_id, "display_name": model_id}
        fallback.append(item)
        if _looks_like_generation_model(model_id):
            generation_models.append(item)
    return sorted(generation_models or fallback, key=lambda item: item["id"])


def _image_data_url(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _extract_text(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        raise JsonXProviderError(
            "OpenAI-compatible server returned no choices.",
            provider="openai",
            diagnostics={"event": "no_choices"},
        )
    message = choices[0].get("message") if isinstance(choices[0], dict) else {}
    content = message.get("content") if isinstance(message, dict) else ""
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        text = "".join(
            str(item.get("text") or "")
            for item in content
            if isinstance(item, dict)
        ).strip()
        if text:
            return text
    raise JsonXProviderError(
        "OpenAI-compatible server returned no text output.",
        provider="openai",
        diagnostics={"event": "empty_response"},
    )


def _lm_studio_unload_url(base_url: str | None) -> str:
    parsed = urlsplit(_base_url(base_url))
    path = parsed.path.rstrip("/")
    if path.endswith("/api/v1"):
        unload_path = f"{path}/models/unload"
    elif path.endswith("/api"):
        unload_path = f"{path}/v1/models/unload"
    else:
        prefix = path[:-3] if path.endswith("/v1") else path
        unload_path = f"{prefix}/api/v1/models/unload"
    if not unload_path.startswith("/"):
        unload_path = f"/{unload_path}"
    return urlunsplit((parsed.scheme, parsed.netloc, unload_path, "", ""))


def _unload(base_url: str | None, api_key: str, model: str, timeout: float) -> None:
    try:
        requests.post(
            _lm_studio_unload_url(base_url),
            headers=_headers(api_key),
            json={"instance_id": model},
            timeout=timeout,
        )
    except Exception:
        pass


def generate(
    base_url: str | None,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    pil_images: list[Image.Image] | None = None,
    timeout: float = 120,
    unload_after: bool = False,
) -> str:
    if not model:
        raise ValueError("No OpenAI-compatible model selected.")
    images = list(pil_images or [])
    content: str | list[dict] = user_prompt
    if images:
        content = [{"type": "text", "text": user_prompt}]
        content.extend(
            {
                "type": "image_url",
                "image_url": {"url": _image_data_url(image), "detail": "auto"},
            }
            for image in images
        )
    body = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        "temperature": 0.7,
    }
    response = requests.post(
        f"{_base_url(base_url)}/chat/completions",
        headers=_headers(api_key),
        json=body,
        timeout=timeout,
    )
    if response.status_code != 200:
        raise JsonXProviderError(
            f"OpenAI-compatible API {response.status_code}: {_safe_error(response)}",
            provider="openai",
            diagnostics={"event": "generation_http_error", "http_status": response.status_code},
        )
    text = _extract_text(response.json())
    if unload_after:
        _unload(base_url, api_key, model, timeout)
    return text
