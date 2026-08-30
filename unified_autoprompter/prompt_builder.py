from __future__ import annotations

import json
from .profiles import (
    FORMAT_JSON,
    get_profile,
    normalize_format,
    normalize_generation_type,
)
from .reference_store import (
    output_contract_filename,
    resolve_profile_file,
    selected_markdown_blocks,
)

BBOX_LAYOUT_TARGETS = {"ideogram4", "krea2"}


def _clean(value: object) -> str:
    return str(value or "").strip()


def _context_block(data: dict, target_model: str = "") -> str:
    raw_prompt_text = _clean(data.get("raw_prompt_text"))
    prompt_text = _clean(data.get("prompt_text"))
    selected_prompt = raw_prompt_text or prompt_text
    if selected_prompt:
        lines = [selected_prompt]
        if _clean(data.get("detail")):
            lines.append(f"Detail level: {_clean(data.get('detail'))}")
    else:
        # Legacy route/API compatibility. The Unified frontend no longer emits
        # these individual prompt fields.
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
    if target_model in BBOX_LAYOUT_TARGETS:
        layout = _clean(data.get("bbox_layout") or data.get("ideogram_layout"))
        palette = _clean(data.get("ideogram_palette"))
        if layout:
            lines.append(f"Layout JSON: {layout}")
        if palette:
            lines.append(f"Palette: {palette}")
    return "\n".join(lines).strip()


def _effective_negative_enabled(target_model: str, negative_enabled: bool) -> bool:
    return bool(negative_enabled) and bool(get_profile(target_model).negative_supported)


def output_contract(
    target_model: str,
    prompt_format: str,
    negative_enabled: bool,
    generation_type: str = "",
) -> str:
    prompt_format = normalize_format(target_model, prompt_format)
    negative_enabled = _effective_negative_enabled(target_model, negative_enabled)
    filename = output_contract_filename(prompt_format, negative_enabled)
    _path, text = resolve_profile_file(target_model, f"Supporting/{filename}")
    return text


def assemble_system_prompt(
    target_model: str,
    prompt_format: str,
    negative_enabled: bool,
    has_image: bool = False,
    reference_count: int = 0,
    generation_type: str = "",
    nsfw_enabled: bool = False,
) -> tuple[str, list[dict[str, str]]]:
    prompt_format = normalize_format(target_model, prompt_format)
    generation_type = normalize_generation_type(target_model, generation_type)
    reference_count = max(0, int(reference_count or 0))
    if has_image and reference_count == 0:
        reference_count = 1
    negative_enabled = _effective_negative_enabled(target_model, negative_enabled)
    parts: list[str] = []
    activated: list[dict[str, str]] = []

    def add_block(kind: str, relative_path: str, text: str, *, required: bool = False) -> None:
        if not text.strip():
            if required:
                raise ValueError(f"Required Markdown prompt block is empty or missing: {relative_path}.")
            return
        parts.append(text)
        activated.append({
            "kind": kind,
            "path": relative_path,
        })

    for kind, relative_path, text, required in selected_markdown_blocks(
        target_model,
        generation_type,
        prompt_format,
        negative_enabled,
        nsfw_enabled,
        reference_count > 0,
    ):
        add_block(kind, relative_path, text, required=required)
    return "\n\n".join(parts), activated


def render_system_prompt_template(
    target_model: str,
    prompt_format: str,
    negative_enabled: bool,
    has_image: bool = False,
    reference_count: int = 0,
    generation_type: str = "",
    nsfw_enabled: bool = False,
) -> str:
    prompt, _activated = assemble_system_prompt(
        target_model,
        prompt_format,
        negative_enabled,
        has_image=has_image,
        reference_count=reference_count,
        generation_type=generation_type,
        nsfw_enabled=nsfw_enabled,
    )
    return prompt


def build_system_prompt(
    target_model: str,
    prompt_format: str,
    negative_enabled: bool,
    has_image: bool = False,
    reference_count: int = 0,
    generation_type: str = "",
    nsfw_enabled: bool = False,
) -> str:
    return render_system_prompt_template(
        target_model,
        prompt_format,
        negative_enabled,
        has_image=has_image,
        reference_count=reference_count,
        generation_type=generation_type,
        nsfw_enabled=nsfw_enabled,
    )


def build_user_prompt(
    data: dict,
    has_image: bool = False,
    target_model: str = "",
    reference_count: int = 0,
    generation_type: str = "",
) -> str:
    context = _context_block(data, target_model=target_model)
    return context.strip()


def example_payload(target_model: str, prompt_format: str) -> str:
    prompt_format = normalize_format(target_model, prompt_format)
    if prompt_format == FORMAT_JSON:
        return json.dumps({"prompt_json": {}}, indent=2)
    return json.dumps({"positive": "", "negative": ""}, indent=2)
