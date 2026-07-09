from __future__ import annotations

import base64
import io

import requests
from PIL import Image


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


def _err(resp) -> str:
    try:
        error = resp.json().get("error", {})
        message = error.get("message") or resp.text[:200]
    except Exception:
        message = resp.text[:200]
    return f"OpenAI-compatible API {resp.status_code}: {message}"


def _looks_like_generation_model(model_id: str) -> bool:
    lowered = model_id.lower()
    if lowered.startswith(_NON_GENERATION_PREFIXES):
        return False
    return not any(token in lowered for token in _NON_GENERATION_TOKENS)


def list_models(base_url: str | None, api_key: str | None = "", timeout: float = 120) -> list[dict[str, str]]:
    response = requests.get(f"{_base_url(base_url)}/models", headers=_headers(api_key), timeout=timeout)
    if response.status_code != 200:
        raise ValueError(_err(response))

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


def _image_data_url(pil_image: Image.Image) -> str:
    buffer = io.BytesIO()
    pil_image.convert("RGB").save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _extract_text(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        raise ValueError("OpenAI-compatible server returned no choices.")
    message = choices[0].get("message") if isinstance(choices[0], dict) else {}
    content = message.get("content") if isinstance(message, dict) else ""
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        chunks = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                chunks.append(item["text"])
        text = "".join(chunks).strip()
        if text:
            return text
    raise ValueError("OpenAI-compatible server returned no text output.")


def generate(
    base_url: str | None,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    pil_image: Image.Image | None = None,
    timeout: float = 120,
    unload_after: bool = False,
) -> str:
    if not model:
        raise ValueError("No OpenAI-compatible model selected.")

    content: str | list[dict] = user_prompt
    if pil_image is not None:
        content = [{"type": "text", "text": user_prompt}]
        content.append({"type": "image_url", "image_url": {"url": _image_data_url(pil_image), "detail": "auto"}})

    body = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        "temperature": 0.7,
    }
    if unload_after:
        body["ttl"] = 0
    response = requests.post(f"{_base_url(base_url)}/chat/completions", headers=_headers(api_key), json=body, timeout=timeout)
    if response.status_code != 200:
        raise ValueError(_err(response))
    return _extract_text(response.json())
