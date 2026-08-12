from __future__ import annotations

import base64
import io
from typing import Any

import requests
from PIL import Image

from .errors import JsonXProviderError


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


def _safe_error(response: requests.Response) -> str:
    try:
        error = response.json().get("error", {})
        return str(error.get("message") or response.text[:200])
    except Exception:
        return response.text[:200]


def list_models(api_key: str, timeout: float = 120) -> list[dict[str, str]]:
    if not api_key:
        raise ValueError("No Gemini API key provided.")
    models: list[dict[str, str]] = []
    page_token = ""
    while True:
        params = {"key": api_key, "pageSize": 1000}
        if page_token:
            params["pageToken"] = page_token
        response = requests.get(f"{API_ROOT}/models", params=params, timeout=timeout)
        if response.status_code != 200:
            raise JsonXProviderError(
                f"Gemini API {response.status_code}: {_safe_error(response)}",
                provider="gemini",
                diagnostics={"event": "model_list_error", "http_status": response.status_code},
            )
        payload = response.json()
        for model in payload.get("models", []):
            if "generateContent" not in (model.get("supportedGenerationMethods") or []):
                continue
            name = str(model.get("name") or "")
            model_id = name.split("/", 1)[-1] if "/" in name else name
            if model_id:
                models.append(
                    {"id": model_id, "display_name": str(model.get("displayName") or model_id)}
                )
        page_token = str(payload.get("nextPageToken") or "")
        if not page_token:
            break
    unique = {item["id"]: item for item in models}
    return sorted(unique.values(), key=lambda item: item["id"])


def _image_part(image: Image.Image) -> dict[str, Any]:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    return {
        "inline_data": {
            "mime_type": "image/png",
            "data": base64.b64encode(buffer.getvalue()).decode("ascii"),
        }
    }


def _safety_settings(values: dict[str, str] | None) -> list[dict[str, str]]:
    values = values if isinstance(values, dict) else {}
    settings = []
    for category, field_name in SAFETY_FIELDS:
        threshold = str(values.get(field_name) or "BLOCK_NONE").strip()
        if threshold not in SAFETY_OPTIONS:
            threshold = "BLOCK_NONE"
        if threshold != "BLOCK_DEFAULT":
            settings.append({"category": category, "threshold": threshold})
    return settings


def _feedback_diagnostics(payload: dict[str, Any], event: str) -> dict[str, Any]:
    feedback = payload.get("promptFeedback")
    candidates = payload.get("candidates") or []
    candidate_details = []
    for candidate in candidates[:3]:
        if not isinstance(candidate, dict):
            continue
        candidate_details.append(
            {
                "finish_reason": candidate.get("finishReason"),
                "finish_message": candidate.get("finishMessage"),
                "safety_ratings": candidate.get("safetyRatings") or [],
            }
        )
    return {
        "event": event,
        "prompt_feedback": feedback if isinstance(feedback, dict) else {},
        "candidates": candidate_details,
    }


def _feedback_message(payload: dict[str, Any]) -> str:
    feedback = payload.get("promptFeedback")
    if not isinstance(feedback, dict):
        return "Gemini returned no candidates and provided no prompt feedback."
    reason = feedback.get("blockReason") or "unspecified"
    detail = feedback.get("blockReasonMessage") or feedback.get("blockReasonDetails") or ""
    suffix = f": {detail}" if detail else ""
    return f"Gemini returned no candidates (block reason: {reason}){suffix}."


def generate(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    pil_images: list[Image.Image] | None = None,
    safety_settings: dict[str, str] | None = None,
    timeout: float = 120,
) -> str:
    if not api_key:
        raise ValueError("No Gemini API key provided.")
    if not model:
        raise ValueError("No Gemini model selected.")
    parts: list[dict[str, Any]] = [{"text": user_prompt}]
    parts.extend(_image_part(image) for image in (pil_images or []))
    body: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0.7, "responseMimeType": "application/json"},
    }
    safety = _safety_settings(safety_settings)
    if safety:
        body["safetySettings"] = safety
    response = requests.post(
        f"{API_ROOT}/models/{model}:generateContent",
        params={"key": api_key},
        json=body,
        timeout=timeout,
    )
    if response.status_code != 200:
        raise JsonXProviderError(
            f"Gemini API {response.status_code}: {_safe_error(response)}",
            provider="gemini",
            diagnostics={"event": "generation_http_error", "http_status": response.status_code},
        )
    payload = response.json()
    candidates = payload.get("candidates") or []
    if not candidates:
        raise JsonXProviderError(
            _feedback_message(payload),
            provider="gemini",
            diagnostics=_feedback_diagnostics(payload, "no_candidates"),
        )
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(str(part.get("text") or "") for part in parts if isinstance(part, dict)).strip()
    if not text:
        raise JsonXProviderError(
            "Gemini returned a candidate with no text output.",
            provider="gemini",
            diagnostics=_feedback_diagnostics(payload, "candidate_without_text"),
        )
    return text
