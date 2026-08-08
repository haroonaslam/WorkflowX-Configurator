from __future__ import annotations

import base64
import io

import requests
from PIL import Image


API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
SAFETY_FIELDS = (
    ("HARM_CATEGORY_HARASSMENT", "safety_harassment"),
    ("HARM_CATEGORY_HATE_SPEECH", "safety_hate_speech"),
    ("HARM_CATEGORY_SEXUALLY_EXPLICIT", "safety_sexual"),
    ("HARM_CATEGORY_DANGEROUS_CONTENT", "safety_dangerous"),
)
SAFETY_OPTIONS = {
    "BLOCK_DEFAULT",
    "BLOCK_NONE",
    "BLOCK_LOW_AND_ABOVE",
    "BLOCK_MEDIUM_AND_ABOVE",
    "BLOCK_ONLY_HIGH",
}


def _err(resp) -> str:
    try:
        error = resp.json().get("error", {})
        return f"Gemini API {resp.status_code}: {error.get('message', resp.text[:200])}"
    except Exception:
        return f"Gemini API {resp.status_code}: {resp.text[:200]}"


def list_models(api_key: str, timeout: float = 120) -> list[dict[str, str]]:
    if not api_key:
        raise ValueError("No Gemini API key provided.")
    response = requests.get(f"{API_ROOT}/models", params={"key": api_key}, timeout=timeout)
    if response.status_code != 200:
        raise ValueError(_err(response))
    models = []
    for model in response.json().get("models", []):
        if "generateContent" not in (model.get("supportedGenerationMethods") or []):
            continue
        name = model.get("name", "")
        model_id = name.split("/", 1)[-1] if "/" in name else name
        models.append({"id": model_id, "display_name": model.get("displayName", model_id)})
    return sorted(models, key=lambda item: item["id"])


def _image_part(pil_image: Image.Image) -> dict:
    buffer = io.BytesIO()
    pil_image.convert("RGB").save(buffer, format="PNG")
    return {
        "inline_data": {
            "mime_type": "image/png",
            "data": base64.b64encode(buffer.getvalue()).decode("ascii"),
        }
    }


def _build_safety_settings(values: dict[str, str] | None) -> list[dict[str, str]]:
    values = values if isinstance(values, dict) else {}
    settings = []
    for category, field_name in SAFETY_FIELDS:
        threshold = str(values.get(field_name) or "BLOCK_NONE").strip()
        if threshold not in SAFETY_OPTIONS:
            threshold = "BLOCK_NONE"
        if threshold != "BLOCK_DEFAULT":
            settings.append({"category": category, "threshold": threshold})
    return settings


def generate(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    pil_image: Image.Image | None = None,
    pil_images: list[Image.Image] | None = None,
    prompt_format: str = "json",
    safety_settings: dict[str, str] | None = None,
    timeout: float = 120,
) -> str:
    if not api_key:
        raise ValueError("No Gemini API key provided.")
    if not model:
        raise ValueError("No Gemini model selected.")
    parts = [{"text": user_prompt}]
    images = list(pil_images or [])
    if not images and pil_image is not None:
        images = [pil_image]
    for image in images:
        parts.append(_image_part(image))
    generation_config = {"temperature": 0.7}
    if str(prompt_format or "").strip().lower() == "json":
        generation_config["responseMimeType"] = "application/json"
    body = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": generation_config,
    }
    safety = _build_safety_settings(safety_settings)
    if safety:
        body["safetySettings"] = safety
    response = requests.post(f"{API_ROOT}/models/{model}:generateContent", params={"key": api_key}, json=body, timeout=timeout)
    if response.status_code != 200:
        raise ValueError(_err(response))
    candidates = response.json().get("candidates") or []
    if not candidates:
        raise ValueError("Gemini returned no candidates.")
    return "".join(part.get("text", "") for part in candidates[0].get("content", {}).get("parts", []))
