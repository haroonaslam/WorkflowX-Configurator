import base64
import io
import os
import pathlib
import sys
import unittest
from unittest import mock

import torch
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nanobanana_full_api.node import MODEL_VERSIONS, NanoBananaAPINode_V2


def image_base64(colour=(20, 40, 60)):
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), colour).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


class FakeResponse:
    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            error = __import__("requests").exceptions.HTTPError("request failed")
            error.response = self
            raise error


def call_kwargs(**overrides):
    values = dict(
        api_key="widget-secret",
        model_version=MODEL_VERSIONS[0],
        prompt="Create a test image",
        system_prompt="Keep the composition clean.",
        aspect_ratio="16:9",
        seed=123,
        temperature=0.7,
        top_p=0.8,
        candidate_count=2,
        safety_harassment="BLOCK_NONE",
        safety_hate_speech="BLOCK_LOW_AND_ABOVE",
        safety_sexual="BLOCK_MEDIUM_AND_ABOVE",
        safety_dangerous="BLOCK_ONLY_HIGH",
        edit_mode_enabled="yes",
        resolution="4K",
        timeout_seconds=300,
        show_thoughts=True,
        thinking_level="high",
        image_1=torch.full((1, 2, 2, 3), 0.25),
        image_2=None,
        image_3=None,
        image_4=None,
        image_5=None,
        mask=torch.ones((1, 2, 2)),
    )
    values.update(overrides)
    return values


class NanoBananaFullAPITests(unittest.TestCase):
    def setUp(self):
        self.node = NanoBananaAPINode_V2()

    def test_registration_contract_and_model_menu(self):
        inputs = self.node.INPUT_TYPES()
        self.assertEqual(
            inputs["required"]["model_version"][0],
            [
                "gemini-3.1-flash-image",
                "gemini-3-pro-image",
            ],
        )
        self.assertEqual(
            inputs["required"]["resolution"],
            (["1K", "2K", "4K"], {"default": "4K"}),
        )
        self.assertEqual(
            inputs["required"]["timeout_seconds"],
            (
                "INT",
                {
                    "default": 120,
                    "min": 1,
                    "max": 3600,
                    "step": 1,
                    "tooltip": "Maximum time to wait for the Google API response.",
                },
            ),
        )
        self.assertEqual(
            inputs["required"]["show_thoughts"],
            (
                "BOOLEAN",
                {
                    "default": True,
                    "tooltip": "Request and include model thought text in text_output.",
                },
            ),
        )
        self.assertEqual(
            inputs["required"]["thinking_level"],
            (
                ["minimal", "high"],
                {
                    "default": "high",
                    "tooltip": (
                        "Gemini 3.1 Flash Image only. Gemini 3 Pro Image uses "
                        "its model-managed thinking level."
                    ),
                },
            ),
        )
        self.assertEqual(
            self.node.CATEGORY,
            "WorkflowX_Configurator/Image/NanoBanana",
        )
        self.assertEqual(self.node.RETURN_TYPES, ("IMAGE", "STRING"))

    def test_every_model_forwards_all_original_controls(self):
        response_payload = {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {
                        "parts": [
                            {"inlineData": {"mimeType": "image/png", "data": image_base64()}}
                        ]
                    },
                }
            ]
        }
        for model in MODEL_VERSIONS:
            with self.subTest(model=model):
                with mock.patch(
                    "nanobanana_full_api.node.requests.post",
                    return_value=FakeResponse(response_payload),
                ) as post:
                    image, _ = self.node.generate_image_batch(
                        **call_kwargs(model_version=model)
                    )
                self.assertEqual(tuple(image.shape), (1, 2, 2, 3))
                args, kwargs = post.call_args
                url = args[0]
                payload = kwargs["json"]
                headers = kwargs["headers"]

                self.assertEqual(
                    url,
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                )
                self.assertEqual(headers["x-goog-api-key"], "widget-secret")
                self.assertNotIn("widget-secret", url)
                self.assertNotIn("widget-secret", repr(payload))
                self.assertEqual(kwargs["timeout"], 300)
                self.assertEqual(
                    set(payload),
                    {"contents", "generationConfig", "safetySettings"},
                )
                self.assertNotIn("systemInstruction", payload)

                config = payload["generationConfig"]
                self.assertEqual(
                    set(config),
                    {
                        "responseModalities",
                        "temperature",
                        "topP",
                        "seed",
                        "candidateCount",
                        "imageConfig",
                        "thinkingConfig",
                    },
                )
                self.assertEqual(config["responseModalities"], ["TEXT", "IMAGE"])
                self.assertEqual(config["temperature"], 0.7)
                self.assertEqual(config["topP"], 0.8)
                self.assertEqual(config["seed"], 123)
                self.assertEqual(config["candidateCount"], 2)
                self.assertEqual(
                    config["imageConfig"],
                    {"aspectRatio": "16:9", "imageSize": "4K"},
                )
                self.assertNotIn("responseFormat", config)
                if model == "gemini-3.1-flash-image":
                    self.assertEqual(
                        config["thinkingConfig"],
                        {"includeThoughts": True, "thinkingLevel": "HIGH"},
                    )
                else:
                    self.assertEqual(
                        config["thinkingConfig"],
                        {"includeThoughts": True},
                    )
                self.assertEqual(
                    payload["safetySettings"],
                    [
                        {
                            "category": "HARM_CATEGORY_HARASSMENT",
                            "threshold": "BLOCK_NONE",
                        },
                        {
                            "category": "HARM_CATEGORY_HATE_SPEECH",
                            "threshold": "BLOCK_LOW_AND_ABOVE",
                        },
                        {
                            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                            "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                        },
                        {
                            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                            "threshold": "BLOCK_ONLY_HIGH",
                        },
                    ],
                )
                parts = payload["contents"][0]["parts"]
                self.assertEqual(
                    parts[0],
                    {"text": "Keep the composition clean.\n\nUser: Create a test image"},
                )
                self.assertEqual(parts[1], {"text": "image 1"})
                self.assertEqual(parts[2]["inlineData"]["mimeType"], "image/png")
                self.assertEqual(parts[3], {"text": "mask for image 1"})
                self.assertEqual(parts[4]["inlineData"]["mimeType"], "image/png")

    def test_default_system_prompt_preserves_original_prompt_text(self):
        payload, error = self.node._build_payload(
            **{
                key: value
                for key, value in call_kwargs(
                    system_prompt="You are a helpful image generation assistant."
                ).items()
                if key not in {"api_key", "timeout_seconds"}
            }
        )
        self.assertIsNone(error)
        self.assertEqual(
            payload["contents"][0]["parts"][0],
            {"text": "Create a test image"},
        )
        self.assertNotIn("systemInstruction", payload)

    def test_every_resolution_is_forwarded_in_image_config(self):
        for resolution in ("1K", "2K", "4K"):
            with self.subTest(resolution=resolution):
                payload, error = self.node._build_payload(
                    **{
                        key: value
                        for key, value in call_kwargs(resolution=resolution).items()
                        if key not in {"api_key", "timeout_seconds"}
                    }
                )
                self.assertIsNone(error)
                self.assertEqual(
                    payload["generationConfig"]["imageConfig"],
                    {"aspectRatio": "16:9", "imageSize": resolution},
                )

    def test_thinking_config_model_rules_and_disable(self):
        for level, expected in (("minimal", "MINIMAL"), ("high", "HIGH")):
            with self.subTest(model="flash", level=level):
                payload, error = self.node._build_payload(
                    **{
                        key: value
                        for key, value in call_kwargs(
                            model_version="gemini-3.1-flash-image",
                            thinking_level=level,
                        ).items()
                        if key not in {"api_key", "timeout_seconds"}
                    }
                )
                self.assertIsNone(error)
                self.assertEqual(
                    payload["generationConfig"]["thinkingConfig"],
                    {"includeThoughts": True, "thinkingLevel": expected},
                )

        pro_payload, error = self.node._build_payload(
            **{
                key: value
                for key, value in call_kwargs(
                    model_version="gemini-3-pro-image",
                    thinking_level="minimal",
                ).items()
                if key not in {"api_key", "timeout_seconds"}
            }
        )
        self.assertIsNone(error)
        self.assertEqual(
            pro_payload["generationConfig"]["thinkingConfig"],
            {"includeThoughts": True},
        )

        for model in MODEL_VERSIONS:
            with self.subTest(model=model, show_thoughts=False):
                payload, error = self.node._build_payload(
                    **{
                        key: value
                        for key, value in call_kwargs(
                            model_version=model,
                            show_thoughts=False,
                        ).items()
                        if key not in {"api_key", "timeout_seconds"}
                    }
                )
                self.assertIsNone(error)
                self.assertNotIn("thinkingConfig", payload["generationConfig"])

    def test_all_safety_thresholds_and_default_omission(self):
        thresholds = (
            "BLOCK_NONE",
            "BLOCK_LOW_AND_ABOVE",
            "BLOCK_MEDIUM_AND_ABOVE",
            "BLOCK_ONLY_HIGH",
        )
        for threshold in thresholds:
            with self.subTest(threshold=threshold):
                settings = self.node._build_safety_settings(
                    safety_harassment=threshold,
                    safety_hate_speech="BLOCK_DEFAULT",
                    safety_sexual="BLOCK_DEFAULT",
                    safety_dangerous="BLOCK_DEFAULT",
                )
                self.assertEqual(
                    settings,
                    [
                        {
                            "category": "HARM_CATEGORY_HARASSMENT",
                            "threshold": threshold,
                        }
                    ],
                )
        self.assertEqual(
            self.node._build_safety_settings(
                safety_harassment="BLOCK_DEFAULT",
                safety_hate_speech="BLOCK_DEFAULT",
                safety_sexual="BLOCK_DEFAULT",
                safety_dangerous="BLOCK_DEFAULT",
            ),
            [],
        )
        payload, error = self.node._build_payload(
            **{
                key: value
                for key, value in call_kwargs().items()
                if key not in {"api_key", "timeout_seconds"}
            }
            | {
                "safety_harassment": "BLOCK_DEFAULT",
                "safety_hate_speech": "BLOCK_DEFAULT",
                "safety_sexual": "BLOCK_DEFAULT",
                "safety_dangerous": "BLOCK_DEFAULT",
            }
        )
        self.assertIsNone(error)
        self.assertNotIn("safetySettings", payload)

    def test_api_key_precedence_and_missing_key(self):
        with mock.patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "gemini-env", "GOOGLE_API_KEY": "google-env"},
            clear=False,
        ):
            self.assertEqual(self.node._resolve_api_key("widget"), "widget")
            self.assertEqual(self.node._resolve_api_key(""), "gemini-env")
        with mock.patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": "google-env"},
            clear=False,
        ):
            self.assertEqual(self.node._resolve_api_key(""), "google-env")
        with mock.patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""},
            clear=False,
        ):
            image, message = self.node.generate_image_batch(**call_kwargs(api_key=""))
        self.assertEqual(tuple(image.shape), (1, 1, 1, 3))
        self.assertIn("API Key is required", message)

    def test_multi_candidate_thought_and_partial_safety_results(self):
        result = {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {
                        "parts": [
                            {
                                "thought": True,
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": image_base64((255, 0, 0)),
                                },
                            },
                            {"thought": True, "text": "first reasoning"},
                            {"text": "first final"},
                            {
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": image_base64((0, 255, 0)),
                                }
                            },
                        ]
                    },
                },
                {
                    "finishReason": "STOP",
                    "content": {
                        "parts": [
                            {
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": image_base64((0, 0, 255)),
                                }
                            }
                        ]
                    },
                },
                {
                    "finishReason": "SAFETY",
                    "safetyRatings": [
                        {
                            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                            "probability": "HIGH",
                        }
                    ],
                },
            ]
        }
        images, message = self.node._parse_response(result, 3)
        self.assertEqual(images.shape[0], 2)
        self.assertTrue(torch.allclose(images[0, 0, 0], torch.tensor([0.0, 1.0, 0.0])))
        self.assertIn("CANDIDATE 1 THINKING", message)
        self.assertIn("first reasoning", message)
        self.assertIn("CANDIDATE 1 ANSWER", message)
        self.assertIn("first final", message)
        self.assertIn("CANDIDATE 1 RESULT", message)
        self.assertIn("Candidate 3 blocked", message)

    def test_prompt_block_text_only_http_and_timeout_errors(self):
        _, blocked = self.node._parse_response(
            {
                "promptFeedback": {
                    "blockReason": "SAFETY",
                    "safetyRatings": [{"category": "test"}],
                }
            },
            1,
        )
        self.assertIn("Prompt was blocked", blocked)

        _, text_only = self.node._parse_response(
            {
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": "description only"}]},
                    }
                ]
            },
            1,
        )
        self.assertIn("CANDIDATE 1 ANSWER", text_only)
        self.assertIn("description only", text_only)
        self.assertIn("no final image", text_only)

        _, api_error = self.node._parse_response(
            {"error": {"message": "model returned an API error"}},
            1,
        )
        self.assertIn("model returned an API error", api_error)

        with mock.patch(
            "nanobanana_full_api.node.requests.post",
            return_value=FakeResponse(
                {"error": {}},
                status_code=400,
                text="bad request for widget-secret",
            ),
        ):
            _, http_message = self.node.generate_image_batch(**call_kwargs())
        self.assertIn("HTTP Error: 400", http_message)
        self.assertNotIn("widget-secret", http_message)
        self.assertIn("[REDACTED]", http_message)

        with mock.patch(
            "nanobanana_full_api.node.requests.post",
            side_effect=__import__("requests").exceptions.Timeout(),
        ):
            _, timeout_message = self.node.generate_image_batch(**call_kwargs())
        self.assertIn("timed out after 300 seconds", timeout_message)


if __name__ == "__main__":
    unittest.main()
