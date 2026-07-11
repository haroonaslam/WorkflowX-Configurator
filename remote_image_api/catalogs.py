"""Canonical Kie and Atlas model contracts packaged with WorkflowX.

The JSON snapshot is derived from GemMobi's offline canonical artifact.  This
module turns it into the compact compatibility profiles used by the runtime and
the richer descriptors consumed by the browser UI.  Keeping both views here
prevents the UI and provider payload builders from maintaining separate lists.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path(__file__).with_name("model_contracts.json")
CONTRACTS = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

LABELS = {
    "wan-2-7": "Wan 2.7",
    "wan-2-7-pro": "Wan 2.7 Pro",
    "grok-imagine": "Grok Imagine",
    "gpt-image-1-5": "GPT Image 1.5",
    "gpt2": "GPT Image 2",
    "seedream-4-5": "Seedream 4.5",
    "seedream-5-lite": "Seedream 5 Lite",
    "seedream-5-pro": "Seedream 5 Pro",
    "nano-banana-2": "Nano Banana 2",
    "nano-banana-pro": "Nano Banana Pro",
    "qwen2": "Qwen Image 2",
    "qwen-image-2-pro": "Qwen Image 2 Pro",
    "flux2-pro": "Flux 2 Pro",
    "kontext": "Flux Kontext",
}

REFERENCE_FIELDS = ("input_urls", "image_urls", "image_input", "image_url", "images", "image")
INTERNAL_FIELDS = {"model", "prompt", "n", "num_images", "enable_base64_output", *REFERENCE_FIELDS}
FIELD_WIDGETS = {
    "aspect_ratio": "aspect_ratio",
    "image_size": "aspect_ratio",
    "resolution": "image_size",
    "size": "image_size",
    "quality": "quality",
    "optimize_prompt_options": "thinking_mode",
}
FIELD_LABELS = {
    "aspect_ratio": "Aspect Ratio",
    "image_size": "Aspect Ratio",
    "resolution": "Resolution",
    "size": "Output Size",
    "quality": "Output Quality",
    "nsfw_checker": "NSFW Checker",
    "thinking_mode": "Thinking Mode",
    "optimize_prompt_options": "Prompt Optimization",
    "watermark": "Watermark",
    "seed": "Fixed Seed",
    "enable_sequential": "Sequential Mode",
    "output_format": "Output Type",
    "enable_pro": "Pro Mode",
    "input_fidelity": "Input Fidelity",
    "enable_web_search": "Web Search",
    "enable_image_search": "Image Search",
    "media_resolution": "Media Resolution",
    "guidance_scale": "Guidance Scale",
    "num_inference_steps": "Inference Steps",
    "enable_safety_checker": "Safety Checker",
}


def _values(field: dict[str, Any] | None) -> list[Any]:
    supported = (field or {}).get("supported_values") or {}
    values = supported.get("frontend_values")
    if values is None:
        values = supported.get("enum")
    return list(values or [])


def _default(field: dict[str, Any] | None, fallback: Any = None) -> Any:
    return ((field or {}).get("default") or {}).get("value", fallback)


def _reference_field(fields: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    for name in REFERENCE_FIELDS:
        if name in fields:
            return name, fields[name]
    return "images", {}


def _profile(provider: str, model_id: str, contract: dict[str, Any]) -> dict[str, Any]:
    fields = contract.get("fields") or {}
    routes = contract.get("routes") or {}
    reference_name, reference = _reference_field(fields)
    ref_values = reference.get("supported_values") or {}
    aspect_field = fields.get("aspect_ratio") or fields.get("image_size")
    size_field = fields.get("resolution") or fields.get("size")
    quality_field = fields.get("quality")
    t2i = ((routes.get("t2i") or routes.get("t2i_or_i2i") or {}).get("model_id"))
    i2i = ((routes.get("i2i") or routes.get("t2i_or_i2i") or {}).get("model_id"))
    unified = t2i if t2i and t2i == i2i else None
    defaults = contract.get("defaults_snapshot") or {}
    custom_size = (size_field or {}).get("supported_values", {}).get("custom_override")
    size_format = (size_field or {}).get("supported_values", {}).get("format")
    if model_id == "gpt2" and provider == "kie":
        custom_size = {
            "enabled_by_field": "gpt2ResolutionOverrideEnabled",
            "width_height_step": 64,
            "min_edge": 64,
            "max_edge": 3840,
            "min_pixels": 655360,
            "max_pixels": 8294400,
            "max_aspect_ratio": 3.0,
            "supports_auto": True,
        }
        size_format = "WxH_or_auto"
    elif model_id == "gpt2" and custom_size:
        custom_size = {**custom_size, "min_edge": custom_size.get("min_edge", 64), "supports_auto": True}
    return {
        "id": model_id,
        "label": LABELS.get(model_id, model_id.replace("-", " ").title()),
        "provider": provider,
        "text_model": None if unified else t2i,
        "image_model": None if unified else i2i,
        "unified_model": unified,
        "routes": routes,
        "request_shape": contract.get("request_shape") or {},
        "fields": fields,
        "defaults_snapshot": defaults,
        "aspect_ratios": _values(aspect_field),
        "sizes": _values(size_field),
        "quality_options": _values(quality_field),
        "max_references": int(ref_values.get("max_items", 1 if reference else 0)),
        "input_image_field": reference_name,
        "single_image": reference_name in ("image", "image_url"),
        "supports_nsfw": "nsfw_checker" in fields,
        "supports_wan": all(name in fields for name in ("thinking_mode", "watermark", "enable_sequential")),
        "supports_seed": "seed" in fields,
        "supports_enable_pro": "enable_pro" in fields,
        "supports_prompt_thinking": "optimize_prompt_options" in fields,
        "supports_input_fidelity": "input_fidelity" in fields,
        "supports_search": "enable_web_search" in fields,
        "supports_kontext": all(name in fields for name in ("guidance_scale", "num_inference_steps")),
        "output_formats": _values(fields.get("output_format")),
        "default_nsfw": _default(fields.get("nsfw_checker"), True),
        "default_thinking": _default(fields.get("thinking_mode"), _default(fields.get("optimize_prompt_options"), True)),
        "default_aspect": _default(aspect_field, "1:1"),
        "default_size": _default(size_field, ""),
        "default_quality": _default(quality_field, "medium"),
        "default_output_format": _default(fields.get("output_format"), "default"),
        "prompt_max_length": (fields.get("prompt", {}).get("supported_values") or {}).get("max_length"),
        "custom_size": custom_size,
        "size_format": size_format,
        "aspect_to_size_map": (size_field or {}).get("supported_values", {}).get("aspect_to_size_map") or {},
        "sends_n": bool((fields.get("n") or {}).get("default", {}).get("send", False)),
        "omit_aspect_i2i": "t2i_only" in (aspect_field or {}).get("send_rules", []),
        "use_aspect_as_size": "image_size" in fields,
    }


PROFILES = {
    provider: [_profile(provider, model_id, contract) for model_id, contract in data["models"].items()]
    for provider, data in CONTRACTS["providers"].items()
}
KIE_PROFILES = PROFILES["kie"]
ATLAS_PROFILES = PROFILES["atlas"]
PROFILE_MAPS = {provider: {profile["id"]: profile for profile in profiles} for provider, profiles in PROFILES.items()}


def ui_fields(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Return serializable controls in canonical field order."""
    controls: list[dict[str, Any]] = []
    seen: set[str] = set()
    for field_id, field in profile["fields"].items():
        if field_id in INTERNAL_FIELDS or field.get("contract_status") == "not-supported":
            continue
        widget = FIELD_WIDGETS.get(field_id, field_id)
        if widget in seen:
            continue
        seen.add(widget)
        supported = field.get("supported_values") or {}
        default = _default(field)
        if field_id == "optimize_prompt_options" and isinstance(default, dict):
            default = default.get("thinking") == "enabled"
        control = {
            "id": field_id,
            "widget": widget,
            "label": FIELD_LABELS.get(field_id, field_id.replace("_", " ").title()),
            "type": "boolean" if field_id == "optimize_prompt_options" else field.get("type", "string"),
            "default": default,
            "options": _values(field),
            "send_rules": list(field.get("send_rules") or []),
            "contract_status": field.get("contract_status", "optional"),
            "minimum": supported.get("min"),
            "maximum": supported.get("max"),
            "step": supported.get("step"),
            "custom_override": supported.get("custom_override"),
            "format": supported.get("format"),
        }
        controls.append(control)
    return controls


def public_catalogs() -> dict[str, list[dict[str, Any]]]:
    """Return the full browser-safe contract view used by the DOM UI."""
    return {
        provider: [
            {
                "id": profile["id"],
                "label": profile["label"],
                "routes": profile["routes"],
                "request_shape": profile["request_shape"],
                "max_references": profile["max_references"],
                "prompt_max_length": profile["prompt_max_length"],
                "default_aspect": profile["default_aspect"],
                "default_size": profile["default_size"],
                "default_quality": profile["default_quality"],
                "default_output_format": profile["default_output_format"],
                "custom_size": profile["custom_size"],
                "size_format": profile["size_format"],
                "aspect_to_size_map": profile["aspect_to_size_map"],
                "controls": ui_fields(profile),
            }
            for profile in profiles
        ]
        for provider, profiles in PROFILES.items()
    }


__all__ = [
    "CONTRACT_PATH", "CONTRACTS", "PROFILES", "KIE_PROFILES", "ATLAS_PROFILES",
    "PROFILE_MAPS", "public_catalogs", "ui_fields",
]
