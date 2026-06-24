from __future__ import annotations

import base64
import io

import requests
from PIL import Image


DEFAULT_HOST = "http://localhost:11434"


def _host(host: str) -> str:
    return (host or DEFAULT_HOST).strip().rstrip("/")


def list_models(host: str = DEFAULT_HOST) -> list[dict[str, str]]:
    response = requests.get(f"{_host(host)}/api/tags", timeout=15)
    response.raise_for_status()
    models = []
    for model in response.json().get("models", []):
        name = model.get("name", "")
        if name:
            models.append({"id": name, "display_name": name})
    return sorted(models, key=lambda item: item["id"])


def _image_b64(pil_image: Image.Image) -> str:
    buffer = io.BytesIO()
    pil_image.convert("RGB").save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def generate(
    host: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    pil_image: Image.Image | None = None,
    think: bool = False,
    unload_after: bool = True,
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
    }
    if not think:
        body["think"] = False
    if unload_after:
        body["keep_alive"] = 0
    if pil_image is not None:
        body["messages"][-1]["images"] = [_image_b64(pil_image)]
    response = requests.post(f"{_host(host)}/api/chat", json=body, timeout=600)
    response.raise_for_status()
    return response.json().get("message", {}).get("content", "")
