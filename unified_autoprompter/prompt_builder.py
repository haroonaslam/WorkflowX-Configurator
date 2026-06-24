from __future__ import annotations

import json
import re

from .profiles import FORMAT_JSON, get_profile, normalize_format


def _clean(value: object) -> str:
    return str(value or "").strip()


def _context_block(data: dict, target_model: str = "") -> str:
    fields = [
        ("Idea", data.get("idea")),
        ("Subject", data.get("subject")),
        ("Style", data.get("style")),
        ("Lighting", data.get("lighting")),
        ("Camera / composition", data.get("composition")),
        ("Text / typography", data.get("text")),
        ("Detail level", data.get("detail")),
        ("Reference image note", data.get("image_note")),
    ]
    if target_model == "ideogram4":
        fields.extend([
            ("Ideogram layout JSON / bbox hints", data.get("ideogram_layout")),
            ("Ideogram palette hints", data.get("ideogram_palette")),
        ])
    if get_profile(target_model).media_type == "video":
        fields.extend([
            ("Video duration / frame target", data.get("video_duration_or_frames")),
            ("Motion / action", data.get("motion_action")),
            ("Temporal beats", data.get("temporal_beats")),
            ("Camera movement", data.get("camera_movement")),
            ("Audio / dialogue", data.get("audio_dialogue")),
            ("Reference / control notes", data.get("reference_or_control_notes")),
        ])
    lines = [f"{label}: {_clean(value)}" for label, value in fields if _clean(value)]
    return "\n".join(lines) or "Idea: Invent a strong image or video prompt from scratch."


def negative_instruction(negative_enabled: bool) -> str:
    if negative_enabled:
        return "Generate the negative output only in the contract's negative field. Keep it separate from the positive prompt."
    return "Do not invent a negative prompt. Return an empty negative string when the output contract includes negative."


def output_contract(target_model: str, prompt_format: str, negative_enabled: bool) -> str:
    prompt_format = normalize_format(target_model, prompt_format)
    rule = get_profile(target_model).formats[prompt_format]
    return rule.output_contract_negative_on if negative_enabled else rule.output_contract_negative_off


def _render_template(text: str, values: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            return match.group(0)
        return values[key]

    return re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", replace, text)


def render_system_prompt_template(
    target_model: str,
    prompt_format: str,
    negative_enabled: bool,
    has_image: bool = False,
) -> str:
    prompt_format = normalize_format(target_model, prompt_format)
    profile = get_profile(target_model)
    rule = profile.formats[prompt_format]
    contract = rule.output_contract_negative_on if negative_enabled else rule.output_contract_negative_off
    image_rule = rule.with_image_reference_instructions if has_image else rule.without_image_reference_instructions
    values = {
        "target_label": profile.label,
        "target_key": profile.key,
        "prompt_format": prompt_format,
        "output_contract": contract,
        "negative_instruction": negative_instruction(negative_enabled),
        "notes": profile.notes,
    }
    parts = [
        "You are Unified Autoprompter X.",
        f"Target model: {profile.label}",
        f"Target key: {profile.key}",
        f"Output format: {prompt_format}",
        "",
        "Model notes:",
        profile.notes,
        "",
        "Format-specific instructions:",
        rule.common_instructions,
        "",
        "Image reference mode:",
        image_rule,
        "",
        "Negative prompt handling:",
        negative_instruction(negative_enabled),
        "",
        "Output contract:",
        contract,
        "",
        "Return valid JSON only. No markdown fences, no commentary.",
    ]
    return _render_template("\n".join(parts), values)


def build_system_prompt(
    target_model: str,
    prompt_format: str,
    negative_enabled: bool,
    has_image: bool = False,
) -> str:
    return render_system_prompt_template(target_model, prompt_format, negative_enabled, has_image=has_image)


def build_user_prompt(data: dict, has_image: bool = False, target_model: str = "") -> str:
    context = _context_block(data, target_model=target_model)
    if has_image:
        context += "\nA reference image is provided. Use it according to the selected model and format instructions."
    extra = _clean(data.get("extra_instructions"))
    if extra:
        context += "\nExtra instructions: " + extra
    return context


def example_payload(target_model: str, prompt_format: str) -> str:
    prompt_format = normalize_format(target_model, prompt_format)
    if prompt_format == FORMAT_JSON:
        return json.dumps({"prompt_json": {}}, indent=2)
    return json.dumps({"positive": "", "negative": ""}, indent=2)
