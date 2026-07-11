"""Current Gemini image generation API node.

Derived from haroonaslam/ComfyUI_NanoBanana_Full_API at commit
a1a21b936229fc6d37421d8c78d8622498378c9e. The WorkflowX version keeps the
original node ID and socket contract while updating the supported models and
REST request shape.
"""

from __future__ import annotations

import base64
import io
import logging
import os
from typing import Any

import numpy as np
import requests
import torch
from PIL import Image


logger = logging.getLogger("WorkflowX_Configurator.NanoBanana")

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL_VERSIONS = (
    "gemini-3.1-flash-image",
    "gemini-3-pro-image",
)
RESOLUTIONS = ("1K", "2K", "4K")
SAFETY_OPTIONS = (
    "BLOCK_DEFAULT",
    "BLOCK_NONE",
    "BLOCK_LOW_AND_ABOVE",
    "BLOCK_MEDIUM_AND_ABOVE",
    "BLOCK_ONLY_HIGH",
)
SAFETY_FIELDS = (
    ("HARM_CATEGORY_HARASSMENT", "safety_harassment"),
    ("HARM_CATEGORY_HATE_SPEECH", "safety_hate_speech"),
    ("HARM_CATEGORY_SEXUALLY_EXPLICIT", "safety_sexual"),
    ("HARM_CATEGORY_DANGEROUS_CONTENT", "safety_dangerous"),
)


class NanoBananaAPINode_V2:
    """Generate or edit images through Google's current Gemini image models."""

    @classmethod
    def INPUT_TYPES(cls):
        aspect_ratio_options = [
            "1:1",
            "16:9",
            "9:16",
            "4:3",
            "3:4",
            "3:2",
            "2:3",
            "21:9",
            "5:4",
            "4:5",
        ]
        return {
            "required": {
                "api_key": (
                    "STRING",
                    {
                        "multiline": False,
                        "password": True,
                        "default": "",
                        "tooltip": (
                            "Google Gemini API key. When blank, GEMINI_API_KEY then "
                            "GOOGLE_API_KEY are checked."
                        ),
                    },
                ),
                "model_version": (list(MODEL_VERSIONS), {"default": MODEL_VERSIONS[0]}),
                "prompt": (
                    "STRING",
                    {"multiline": True, "default": "A majestic golden retriever, watercolor style"},
                ),
                "system_prompt": (
                    "STRING",
                    {"multiline": True, "default": "You are a helpful image generation assistant."},
                ),
                "aspect_ratio": (aspect_ratio_options, {"default": "1:1"}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 2147483647}),
                "temperature": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.1},
                ),
                "top_p": (
                    "FLOAT",
                    {"default": 0.95, "min": 0.0, "max": 1.0, "step": 0.05},
                ),
                "candidate_count": ("INT", {"default": 1, "min": 1, "max": 10}),
                "safety_harassment": (list(SAFETY_OPTIONS), {"default": "BLOCK_DEFAULT"}),
                "safety_hate_speech": (list(SAFETY_OPTIONS), {"default": "BLOCK_DEFAULT"}),
                "safety_sexual": (list(SAFETY_OPTIONS), {"default": "BLOCK_DEFAULT"}),
                "safety_dangerous": (list(SAFETY_OPTIONS), {"default": "BLOCK_DEFAULT"}),
                "edit_mode_enabled": (["no", "yes"], {"default": "no"}),
                "resolution": (list(RESOLUTIONS), {"default": "4K"}),
                "timeout_seconds": (
                    "INT",
                    {
                        "default": 120,
                        "min": 1,
                        "max": 3600,
                        "step": 1,
                        "tooltip": "Maximum time to wait for the Google API response.",
                    },
                ),
                "show_thoughts": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Request and include model thought text in text_output.",
                    },
                ),
                "thinking_level": (
                    ["minimal", "high"],
                    {
                        "default": "high",
                        "tooltip": (
                            "Gemini 3.1 Flash Image only. Gemini 3 Pro Image uses "
                            "its model-managed thinking level."
                        ),
                    },
                ),
            },
            "optional": {
                "mask": ("MASK",),
                "image_1": ("IMAGE",),
                "image_2": ("IMAGE",),
                "image_3": ("IMAGE",),
                "image_4": ("IMAGE",),
                "image_5": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image_batch", "text_output")
    FUNCTION = "generate_image_batch"
    CATEGORY = "WorkflowX_Configurator/Image/NanoBanana"
    DESCRIPTION = (
        "Generate or edit images with Gemini 3.1 Flash Image or Gemini 3 Pro Image "
        "at 1K, 2K, or 4K resolution."
    )

    @staticmethod
    def _resolve_api_key(widget_value: object) -> str:
        return (
            str(widget_value or "").strip()
            or os.getenv("GEMINI_API_KEY", "").strip()
            or os.getenv("GOOGLE_API_KEY", "").strip()
        )

    @staticmethod
    def _request_url(model_version: str) -> str:
        return f"{API_ROOT}/{model_version}:generateContent"

    @staticmethod
    def _redact(message: object, secret: str) -> str:
        text = str(message or "")
        return text.replace(secret, "[REDACTED]") if secret else text

    @staticmethod
    def tensor_to_base64(image_tensor):
        """Convert a ComfyUI IMAGE or MASK tensor to a base64 PNG."""
        if image_tensor is None:
            return None
        try:
            if image_tensor.dim() == 4 and image_tensor.shape[3] == 1:
                img_tensor = image_tensor[0].squeeze(2)
            elif image_tensor.dim() == 3:
                img_tensor = image_tensor[0]
            elif image_tensor.dim() == 4 and image_tensor.shape[3] == 3:
                img_tensor = image_tensor[0]
            else:
                raise ValueError("Tensor shape not recognized for image or mask conversion.")

            if img_tensor.dim() == 2:
                img_np = (img_tensor.detach().cpu().clamp(0.0, 1.0).numpy() * 255.0).astype(np.uint8)
                img_pil = Image.fromarray(img_np, "L")
            elif img_tensor.dim() == 3 and img_tensor.shape[2] == 3:
                img_np = (img_tensor.detach().cpu().clamp(0.0, 1.0).numpy() * 255.0).astype(np.uint8)
                img_pil = Image.fromarray(img_np, "RGB")
            else:
                raise ValueError("Tensor content (channels) not supported for image or mask encoding.")

            buffer = io.BytesIO()
            img_pil.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("ascii")
        except Exception as exc:
            logger.warning("[NanoBanana] Failed to encode input tensor: %s", exc)
            return None

    @staticmethod
    def base64_to_tensor(base64_data):
        """Convert base64 image data to a ComfyUI IMAGE tensor."""
        try:
            image_bytes = base64.b64decode(base64_data)
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            image_np = np.array(image).astype(np.float32) / 255.0
            return torch.from_numpy(image_np).unsqueeze(0)
        except Exception as exc:
            logger.warning("[NanoBanana] Failed to decode API image: %s", exc)
            return None

    def _build_parts(
        self,
        prompt: str,
        edit_mode_enabled: str,
        mask=None,
        image_1=None,
        image_2=None,
        image_3=None,
        image_4=None,
        image_5=None,
    ) -> tuple[list[dict[str, Any]] | None, str | None]:
        parts: list[dict[str, Any]] = [{"text": str(prompt or "")}]
        image_inputs = (image_1, image_2, image_3, image_4, image_5)

        for index, image_tensor in enumerate(image_inputs, start=1):
            if image_tensor is None:
                continue
            encoded = self.tensor_to_base64(image_tensor)
            if not encoded:
                return None, f"ERROR: Failed to encode input image_{index}."
            parts.append({"text": f"image {index}"})
            parts.append({"inlineData": {"mimeType": "image/png", "data": encoded}})

        if edit_mode_enabled == "yes" and mask is not None:
            encoded_mask = self.tensor_to_base64(mask)
            if not encoded_mask:
                return None, "ERROR: Failed to encode input mask."
            # Keep the source node's natural-language relationship between image 1 and its mask.
            parts.append({"text": "mask for image 1"})
            parts.append({"inlineData": {"mimeType": "image/png", "data": encoded_mask}})

        return parts, None

    @staticmethod
    def _build_safety_settings(**values: str) -> list[dict[str, str]]:
        settings = []
        for category, field_name in SAFETY_FIELDS:
            threshold = values[field_name]
            if threshold != "BLOCK_DEFAULT":
                settings.append({"category": category, "threshold": threshold})
        return settings

    def _build_payload(
        self,
        *,
        model_version: str,
        prompt: str,
        system_prompt: str,
        aspect_ratio: str,
        seed: int,
        temperature: float,
        top_p: float,
        candidate_count: int,
        safety_harassment: str,
        safety_hate_speech: str,
        safety_sexual: str,
        safety_dangerous: str,
        edit_mode_enabled: str,
        resolution: str,
        show_thoughts: bool,
        thinking_level: str,
        mask=None,
        image_1=None,
        image_2=None,
        image_3=None,
        image_4=None,
        image_5=None,
    ) -> tuple[dict[str, Any] | None, str | None]:
        full_prompt = str(prompt or "")
        normalized_system_prompt = str(system_prompt or "").strip()
        if (
            normalized_system_prompt
            and normalized_system_prompt.lower()
            != "you are a helpful image generation assistant."
        ):
            full_prompt = f"{system_prompt}\n\nUser: {prompt}"

        parts, error = self._build_parts(
            full_prompt,
            edit_mode_enabled,
            mask=mask,
            image_1=image_1,
            image_2=image_2,
            image_3=image_3,
            image_4=image_4,
            image_5=image_5,
        )
        if error:
            return None, error

        payload: dict[str, Any] = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "temperature": float(temperature),
                "topP": float(top_p),
                "seed": int(seed),
                "candidateCount": int(candidate_count),
                "imageConfig": {
                    "aspectRatio": aspect_ratio,
                    "imageSize": resolution,
                },
            },
        }
        if bool(show_thoughts):
            thinking_config: dict[str, Any] = {"includeThoughts": True}
            if model_version == "gemini-3.1-flash-image":
                thinking_config["thinkingLevel"] = str(thinking_level).upper()
            payload["generationConfig"]["thinkingConfig"] = thinking_config

        safety_settings = self._build_safety_settings(
            safety_harassment=safety_harassment,
            safety_hate_speech=safety_hate_speech,
            safety_sexual=safety_sexual,
            safety_dangerous=safety_dangerous,
        )
        if safety_settings:
            payload["safetySettings"] = safety_settings
        return payload, None

    @staticmethod
    def _safety_message(candidate_index: int, candidate: dict[str, Any]) -> str:
        message = f"Candidate {candidate_index} blocked. Reason: SAFETY."
        for rating in candidate.get("safetyRatings", []):
            message += (
                f"\n  - Category: {rating.get('category')}, "
                f"Probability: {rating.get('probability')}"
            )
        return message

    def _parse_response(self, result: dict[str, Any], candidate_count: int):
        dummy_image = torch.zeros((1, 1, 1, 3))

        prompt_feedback = result.get("promptFeedback") or {}
        if prompt_feedback.get("blockReason"):
            return (
                dummy_image,
                "ERROR: Prompt was blocked by safety filter.\n"
                f"Reason: {prompt_feedback.get('blockReason')}\n"
                f"Details: {prompt_feedback.get('safetyRatings', '')}",
            )

        candidates = result.get("candidates") or []
        if not candidates:
            error_message = (result.get("error") or {}).get(
                "message", "No candidates returned from API."
            )
            return dummy_image, f"ERROR: API Error: {error_message}"

        output_images = []
        output_texts = []
        for candidate_index, candidate in enumerate(candidates, start=1):
            finish_reason = candidate.get("finishReason")
            if finish_reason == "SAFETY":
                output_texts.append(self._safety_message(candidate_index, candidate))
                continue
            if finish_reason not in (None, "STOP"):
                output_texts.append(
                    f"WARN: Candidate {candidate_index} finished unexpectedly. "
                    f"Reason: {finish_reason}"
                )
                continue

            parts = (candidate.get("content") or {}).get("parts") or []
            candidate_images = 0
            thought_images = 0
            thought_text_parts = []
            answer_text_parts = []
            for part in parts:
                is_thought = bool(part.get("thought"))
                inline_data = part.get("inlineData") or part.get("inline_data")
                if inline_data and str(
                    inline_data.get("mimeType") or inline_data.get("mime_type") or ""
                ).startswith("image/"):
                    if is_thought:
                        thought_images += 1
                    else:
                        image_tensor = self.base64_to_tensor(inline_data.get("data"))
                        if image_tensor is not None:
                            output_images.append(image_tensor)
                            candidate_images += 1
                        else:
                            output_texts.append(
                                f"ERROR: Candidate {candidate_index} final image data "
                                "could not be decoded."
                            )
                if part.get("text"):
                    target = thought_text_parts if is_thought else answer_text_parts
                    target.append(str(part["text"]))

            thought_text = "\n".join(thought_text_parts).strip()
            answer_text = "\n".join(answer_text_parts).strip()
            if thought_text:
                output_texts.append(
                    f"=== CANDIDATE {candidate_index} THINKING ===\n{thought_text}"
                )
            elif thought_images:
                output_texts.append(
                    f"INFO: Candidate {candidate_index} returned {thought_images} "
                    "thought image(s) and no thought text."
                )
            if answer_text:
                output_texts.append(
                    f"=== CANDIDATE {candidate_index} ANSWER ===\n{answer_text}"
                )
            if candidate_images == 0:
                output_texts.append(
                    f"INFO: Candidate {candidate_index} returned no final image."
                )
            else:
                output_texts.append(
                    f"=== CANDIDATE {candidate_index} RESULT ===\n"
                    f"Generated {candidate_images} final image(s)."
                )

        if not output_images:
            return dummy_image, "\n".join(output_texts) or (
                "ERROR: No images were generated and no text was returned."
            )

        batch_tensor = torch.cat(output_images, dim=0)
        final_text = "\n".join(output_texts) or (
            f"Image(s) generated successfully ({len(output_images)} of {candidate_count})."
        )
        return batch_tensor, final_text

    def generate_image_batch(
        self,
        api_key,
        model_version,
        prompt,
        system_prompt,
        aspect_ratio,
        seed,
        temperature,
        top_p,
        candidate_count,
        safety_harassment,
        safety_hate_speech,
        safety_sexual,
        safety_dangerous,
        edit_mode_enabled,
        resolution,
        timeout_seconds,
        show_thoughts,
        thinking_level,
        mask=None,
        image_1=None,
        image_2=None,
        image_3=None,
        image_4=None,
        image_5=None,
    ):
        dummy_image = torch.zeros((1, 1, 1, 3))
        resolved_key = self._resolve_api_key(api_key)
        if not resolved_key:
            return (
                dummy_image,
                "ERROR: API Key is required. Enter it in the node or set "
                "GEMINI_API_KEY / GOOGLE_API_KEY.",
            )

        payload, error = self._build_payload(
            model_version=model_version,
            prompt=prompt,
            system_prompt=system_prompt,
            aspect_ratio=aspect_ratio,
            seed=seed,
            temperature=temperature,
            top_p=top_p,
            candidate_count=candidate_count,
            safety_harassment=safety_harassment,
            safety_hate_speech=safety_hate_speech,
            safety_sexual=safety_sexual,
            safety_dangerous=safety_dangerous,
            edit_mode_enabled=edit_mode_enabled,
            resolution=resolution,
            show_thoughts=show_thoughts,
            thinking_level=thinking_level,
            mask=mask,
            image_1=image_1,
            image_2=image_2,
            image_3=image_3,
            image_4=image_4,
            image_5=image_5,
        )
        if error:
            return dummy_image, error

        api_url = self._request_url(model_version)
        headers = {"Content-Type": "application/json", "x-goog-api-key": resolved_key}
        logger.info(
            "[NanoBanana] model=%s edit_mode=%s candidates=%s parts=%s timeout=%ss",
            model_version,
            edit_mode_enabled,
            candidate_count,
            len(payload["contents"][0]["parts"]),
            timeout_seconds,
        )

        try:
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=int(timeout_seconds),
            )
            response.raise_for_status()
            image, message = self._parse_response(response.json(), int(candidate_count))
            return image, self._redact(message, resolved_key)
        except requests.exceptions.HTTPError as exc:
            response = exc.response
            status_code = getattr(response, "status_code", "unknown")
            details = self._redact(getattr(response, "text", ""), resolved_key)
            return dummy_image, f"ERROR: HTTP Error: {status_code}\nDetails: {details}"
        except requests.exceptions.Timeout:
            return (
                dummy_image,
                f"ERROR: API request timed out after {int(timeout_seconds)} seconds. "
                "Try a smaller batch or check the network.",
            )
        except Exception as exc:
            return dummy_image, (
                "ERROR: An unexpected error occurred: "
                f"{self._redact(exc, resolved_key)}"
            )
