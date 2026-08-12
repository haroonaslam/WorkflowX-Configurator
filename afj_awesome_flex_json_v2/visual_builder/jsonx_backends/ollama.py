from __future__ import annotations

import base64
import io

import requests
from PIL import Image

from .errors import JsonXProviderError


DEFAULT_HOST = "http://localhost:11434"


def _host(host: str | None) -> str:
    return (host or DEFAULT_HOST).strip().rstrip("/")


def list_models(host: str = DEFAULT_HOST, timeout: float = 15) -> list[dict[str, str]]:
    response = requests.get(f"{_host(host)}/api/tags", timeout=timeout)
    if response.status_code != 200:
        raise JsonXProviderError(
            f"Ollama API {response.status_code}: {response.text[:200]}",
            provider="ollama",
            diagnostics={"event": "model_list_error", "http_status": response.status_code},
        )
    models = []
    for model in response.json().get("models", []):
        name = str(model.get("name") or "")
        if name:
            models.append({"id": name, "display_name": name})
    return sorted(models, key=lambda item: item["id"])


def _image_b64(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def generate(
    host: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    pil_images: list[Image.Image] | None = None,
    think: bool = False,
    unload_after: bool = True,
    timeout: float = 600,
) -> str:
    if not model:
        raise ValueError("No Ollama model selected.")
    body = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "options": {"temperature": 0.7},
        "think": bool(think),
    }
    if unload_after:
        body["keep_alive"] = 0
    images = list(pil_images or [])
    if images:
        body["messages"][-1]["images"] = [_image_b64(image) for image in images]
    response = requests.post(f"{_host(host)}/api/chat", json=body, timeout=timeout)
    if response.status_code != 200:
        raise JsonXProviderError(
            f"Ollama API {response.status_code}: {response.text[:200]}",
            provider="ollama",
            diagnostics={"event": "generation_http_error", "http_status": response.status_code},
        )
    payload = response.json()
    content = str(payload.get("message", {}).get("content") or "").strip()
    if not content:
        raise JsonXProviderError(
            "Ollama returned no text output.",
            provider="ollama",
            diagnostics={"event": "empty_response", "done_reason": payload.get("done_reason")},
        )
    return content
