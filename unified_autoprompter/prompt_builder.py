from __future__ import annotations

import json
import re

from .profiles import FORMAT_JSON, get_profile, normalize_format

BBOX_LAYOUT_TARGETS = {"ideogram4", "krea2"}
MINIMAX_H3_TARGETS = {"minimax_h3_official", "minimax_h3_alternate"}


def _clean(value: object) -> str:
    return str(value or "").strip()


def _context_block(data: dict, target_model: str = "") -> str:
    raw_prompt_text = _clean(data.get("raw_prompt_text"))
    if raw_prompt_text:
        return f"Raw input prompt:\n{raw_prompt_text}"

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
    if target_model in BBOX_LAYOUT_TARGETS:
        fields.extend([
            ("BBox layout JSON / bbox hints", data.get("bbox_layout") or data.get("ideogram_layout")),
            ("BBox palette hints", data.get("ideogram_palette")),
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


def _effective_negative_enabled(target_model: str, negative_enabled: bool) -> bool:
    return bool(negative_enabled) and bool(get_profile(target_model).negative_supported)


def output_contract(target_model: str, prompt_format: str, negative_enabled: bool) -> str:
    prompt_format = normalize_format(target_model, prompt_format)
    rule = get_profile(target_model).formats[prompt_format]
    negative_enabled = _effective_negative_enabled(target_model, negative_enabled)
    return rule.output_contract_negative_on if negative_enabled else rule.output_contract_negative_off


def _render_template(text: str, values: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            return match.group(0)
        return values[key]

    return re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", replace, text)


def _reference_summary(reference_count: int = 0, target_model: str = "") -> str:
    if reference_count <= 0:
        return ""
    labels = ", ".join(f"Image{index}" for index in range(1, reference_count + 1))
    summary = f"Connected image references: {labels}. Refer to them by these labels in order."
    if target_model in MINIMAX_H3_TARGETS:
        summary += " For MiniMax H3, map Image1/Image2/etc. to exact <Picture 1>/<Picture 2>/etc. tokens in the final prompt."
    return summary


def _collect_minimax_reference_hints(data: dict) -> str:
    text = "\n".join(
        _clean(data.get(key))
        for key in (
            "raw_prompt_text",
            "audio_dialogue",
            "reference_or_control_notes",
            "extra_instructions",
        )
        if _clean(data.get(key))
    )
    if not text:
        return ""

    lower = text.lower()
    hints: list[str] = []
    audio_numbers = re.findall(r"\baudio\s*[-_#:]?\s*(\d+)\b", lower)
    audio_role_terms = (
        "soundtrack",
        "bgm",
        "music",
        "ambience",
        "ambient sound",
        "sound effect",
        "sound effects",
        "lyrics",
        "dialogue",
        "rhythm",
        "beat",
        "audio continuity",
    )
    voice_audio_terms = (
        "audio" in lower
        or "voice sample" in lower
        or "voice cloning" in lower
        or "voice clone" in lower
        or "voice timbre" in lower
    )
    provided_audio_terms = any(term in lower for term in audio_role_terms) and (
        "provided" in lower or "reference" in lower or "as is" in lower or "reuse" in lower or "copy" in lower
    )
    if voice_audio_terms or provided_audio_terms:
        audio_tokens = sorted({int(number) for number in audio_numbers if number.isdigit()}) or [1]
        tokens = ", ".join(f"<Audio {number}>" for number in audio_tokens)
        hints.append(
            f"Audio reference required: include {tokens} explicitly in the final MiniMax prompt. "
            "Classify the audio role from the user's wording: complete reuse/as-is/copy, partial copy, "
            "voice timbre or delivery reference, music style, ambience, sound effects, dialogue or lyrics, "
            "beat/rhythm, or audio continuity. Do not assume voice cloning unless the user specifically asks "
            "for voice clone, timbre, pitch, tone, cadence, accent, delivery, or a speaker voice. If the user "
            "asks to use audio as-is, state that the audio token is reused or copied as the target video's "
            "audio track instead of turning it into a voice-timbre instruction."
        )

    video_numbers = re.findall(r"\bvideo\s*[-_#:]?\s*(\d+)\b", lower)
    if video_numbers:
        tokens = ", ".join(f"<Video {number}>" for number in sorted({int(number) for number in video_numbers}))
        hints.append(f"Video reference required: include {tokens} explicitly with bounded role(s).")

    if "urdu" in lower or "roman urdu" in lower:
        hints.append(
            "Urdu dialogue required: write spoken Urdu in native Urdu script inside the MiniMax dialogue tag. "
            "Convert Roman Urdu to Urdu script unless the user explicitly asks to keep romanized text."
        )

    if not hints:
        return ""
    return "\nMiniMax required reference/dialogue handling: " + " ".join(hints)


def render_system_prompt_template(
    target_model: str,
    prompt_format: str,
    negative_enabled: bool,
    has_image: bool = False,
    reference_count: int = 0,
) -> str:
    prompt_format = normalize_format(target_model, prompt_format)
    profile = get_profile(target_model)
    rule = profile.formats[prompt_format]
    reference_count = max(0, int(reference_count or 0))
    if reference_count:
        has_image = True
    negative_enabled = _effective_negative_enabled(target_model, negative_enabled)
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
        _reference_summary(reference_count, target_model),
        "",
        "Negative prompt handling:",
        negative_instruction(negative_enabled),
        "",
        "Output contract:",
        contract,
    ]
    if target_model in MINIMAX_H3_TARGETS:
        parts.extend([
            "",
            "Return plain text only. Preserve the required MiniMax section headings, one-reference-per-line definitions, and blank lines between sections. No JSON, no markdown fences, no wrapper keys, no positive/negative labels, no commentary.",
        ])
    else:
        parts.extend([
            "",
            "Return valid JSON only. No markdown fences, no commentary.",
        ])
    return _render_template("\n".join(parts), values)


def build_system_prompt(
    target_model: str,
    prompt_format: str,
    negative_enabled: bool,
    has_image: bool = False,
    reference_count: int = 0,
) -> str:
    return render_system_prompt_template(
        target_model,
        prompt_format,
        negative_enabled,
        has_image=has_image,
        reference_count=reference_count,
    )


def build_user_prompt(data: dict, has_image: bool = False, target_model: str = "", reference_count: int = 0) -> str:
    context = _context_block(data, target_model=target_model)
    reference_count = max(0, int(reference_count or 0))
    if reference_count:
        labels = ", ".join(f"Image{index}" for index in range(1, reference_count + 1))
        context += f"\nConnected image references provided: {labels}."
        if target_model in MINIMAX_H3_TARGETS:
            context += " In the final MiniMax H3 prompt, write them as exact <Picture 1>, <Picture 2>, etc. tokens."
    elif has_image:
        context += "\nA reference image is provided. Use it according to the selected model and format instructions."
    extra = _clean(data.get("extra_instructions"))
    if extra:
        context += "\nExtra instructions: " + extra
    if target_model in MINIMAX_H3_TARGETS:
        context += _collect_minimax_reference_hints(data)
    return context


def example_payload(target_model: str, prompt_format: str) -> str:
    prompt_format = normalize_format(target_model, prompt_format)
    if prompt_format == FORMAT_JSON:
        return json.dumps({"prompt_json": {}}, indent=2)
    return json.dumps({"positive": "", "negative": ""}, indent=2)
