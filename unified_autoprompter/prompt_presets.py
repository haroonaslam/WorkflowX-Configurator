from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any


PRESET_SCHEMA_VERSION = 1
PRESET_ROOT = Path(__file__).with_name("prompt_presets")
ORIGINAL_ROOT = PRESET_ROOT / "original"
CURRENT_ROOT = PRESET_ROOT / "current_use"
PRESET_TYPES = {"character", "scene"}
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$", re.IGNORECASE)
FRONTMATTER_PATTERN = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n|\Z)(.*)\Z", re.DOTALL)
ADAPTATION_SECTION_PATTERN = re.compile(r"(?mi)^##\s+Adaptation guidance\s*$")


class PromptPresetError(ValueError):
    pass


def _editor_sections(markdown: str) -> tuple[str, str]:
    body = str(markdown or "").strip()
    matches = list(ADAPTATION_SECTION_PATTERN.finditer(body))
    if not matches:
        return body, ""
    marker = matches[-1]
    return body[:marker.start()].strip(), body[marker.end():].strip()


def _scalar(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw[0:1] in {'"', "'"}:
        try:
            parsed = json.loads(raw) if raw.startswith('"') else raw[1:-1]
        except Exception as exc:
            raise PromptPresetError("Invalid quoted preset frontmatter value.") from exc
        return str(parsed)
    return raw


def _parse_text(text: str, filename: str) -> dict[str, Any]:
    match = FRONTMATTER_PATTERN.match(text)
    if not match:
        raise PromptPresetError(f"Preset {filename} needs YAML-style frontmatter.")
    metadata: dict[str, str] = {}
    allowed_metadata = {"id", "type", "name", "tag"}
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            raise PromptPresetError(f"Invalid frontmatter line in {filename}: {line!r}.")
        key, value = stripped.split(":", 1)
        normalized_key = key.strip().lower()
        if normalized_key not in allowed_metadata:
            raise PromptPresetError(f"Unknown preset frontmatter field {normalized_key!r} in {filename}.")
        if normalized_key in metadata:
            raise PromptPresetError(f"Duplicate preset frontmatter field {normalized_key!r} in {filename}.")
        metadata[normalized_key] = _scalar(value)
    missing = sorted(allowed_metadata - set(metadata))
    if missing:
        raise PromptPresetError(f"Preset {filename} is missing frontmatter: {', '.join(missing)}.")
    preset_id = metadata.get("id", "").lower()
    preset_type = metadata.get("type", "").lower()
    name = metadata.get("name", "").strip()
    tag = metadata.get("tag", "").strip().lstrip("@").lower()
    markdown = match.group(2).strip()
    if not ID_PATTERN.fullmatch(preset_id) or Path(filename).stem.lower() != preset_id:
        raise PromptPresetError(f"Preset {filename} has an invalid or mismatched id.")
    if preset_type not in PRESET_TYPES:
        raise PromptPresetError(f"Preset {filename} type must be character or scene.")
    if not name or "\n" in name or "\r" in name:
        raise PromptPresetError(f"Preset {filename} needs a one-line name.")
    if not TAG_PATTERN.fullmatch(tag):
        raise PromptPresetError(f"Preset {filename} has an invalid tag.")
    if not markdown:
        raise PromptPresetError(f"Preset {filename} Markdown body cannot be empty.")
    profile_markdown, adaptation_guidance = _editor_sections(markdown)
    return {
        "id": preset_id,
        "type": preset_type,
        "name": name,
        "tag": tag,
        "markdown": markdown,
        "profile_markdown": profile_markdown,
        "adaptation_guidance": adaptation_guidance,
    }


def _parse(path: Path) -> dict[str, Any]:
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise PromptPresetError(f"Could not read preset {path.name} as UTF-8.") from exc
    return _parse_text(text, path.name)


def _render(preset: dict[str, Any]) -> str:
    return "\n".join(
        [
            "---",
            f"id: {json.dumps(str(preset['id']), ensure_ascii=False)}",
            f"type: {json.dumps(str(preset['type']), ensure_ascii=False)}",
            f"name: {json.dumps(str(preset['name']), ensure_ascii=False)}",
            f"tag: {json.dumps(str(preset['tag']), ensure_ascii=False)}",
            "---",
            str(preset["markdown"]).strip(),
            "",
        ]
    )


def _files(root: Path) -> dict[str, Path]:
    if not root.exists():
        return {}
    result: dict[str, Path] = {}
    for path in sorted(root.glob("*.md"), key=lambda item: item.name.casefold()):
        if ID_PATTERN.fullmatch(path.stem.lower()):
            result[path.stem.lower()] = path
    return result


def bootstrap_current_use() -> None:
    CURRENT_ROOT.mkdir(parents=True, exist_ok=True)
    for preset_id, source in _files(ORIGINAL_ROOT).items():
        destination = CURRENT_ROOT / f"{preset_id}.md"
        if not destination.exists():
            shutil.copy2(source, destination)


def list_presets() -> list[dict[str, Any]]:
    bootstrap_current_use()
    builtin_ids = set(_files(ORIGINAL_ROOT))
    presets = []
    tags: dict[str, str] = {}
    for preset_id, path in _files(CURRENT_ROOT).items():
        preset = _parse(path)
        owner = tags.get(preset["tag"])
        if owner:
            raise PromptPresetError(
                f"Duplicate preset tag @{preset['tag']} in {owner}.md and {preset_id}.md."
            )
        tags[preset["tag"]] = preset_id
        preset["builtin"] = preset_id in builtin_ids
        presets.append(preset)
    return sorted(presets, key=lambda item: (item["type"], item["name"].casefold(), item["id"]))


def payload() -> dict[str, Any]:
    return {"preset_schema_version": PRESET_SCHEMA_VERSION, "presets": list_presets()}


def _normalize(data: dict[str, Any], preset_id: str = "") -> dict[str, str]:
    normalized_id = str(preset_id or data.get("id") or "").strip().lower()
    preset_type = str(data.get("type") or "").strip().lower()
    name = str(data.get("name") or "").strip()
    tag = str(data.get("tag") or "").strip().lstrip("@").lower()
    uses_separate_editors = "profile_markdown" in data or "adaptation_guidance" in data
    if uses_separate_editors:
        profile_markdown = str(data.get("profile_markdown") or "").strip()
        adaptation_guidance = str(data.get("adaptation_guidance") or "").strip()
        if not profile_markdown:
            raise PromptPresetError("Preset profile details cannot be empty.")
        if not adaptation_guidance:
            raise PromptPresetError("Preset adaptation guidance cannot be empty.")
        markdown = f"{profile_markdown}\n\n## Adaptation guidance\n\n{adaptation_guidance}"
    else:
        markdown = str(data.get("markdown") or "").strip()
    if normalized_id and not ID_PATTERN.fullmatch(normalized_id):
        raise PromptPresetError("Preset id must use lowercase letters, numbers, underscores, or hyphens.")
    if preset_type not in PRESET_TYPES:
        raise PromptPresetError("Preset type must be character or scene.")
    if not name or "\n" in name or "\r" in name:
        raise PromptPresetError("Preset name must be one non-empty line.")
    if not TAG_PATTERN.fullmatch(tag):
        raise PromptPresetError("Preset tag must use letters, numbers, underscores, or hyphens.")
    if not markdown:
        raise PromptPresetError("Preset Markdown body cannot be empty.")
    if not normalized_id:
        slug = re.sub(r"[^a-z0-9_-]+", "_", tag).strip("_") or "preset"
        normalized_id = f"{slug}_{uuid.uuid4().hex[:8]}"
    return {"id": normalized_id, "type": preset_type, "name": name, "tag": tag, "markdown": markdown}


def save_preset(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise PromptPresetError("Preset request must be an object.")
    bootstrap_current_use()
    preset = _normalize(data)
    for existing in list_presets():
        if existing["tag"] == preset["tag"] and existing["id"] != preset["id"]:
            raise PromptPresetError(f"Tag @{preset['tag']} is already used by {existing['name']}.")
    destination = CURRENT_ROOT / f"{preset['id']}.md"
    temporary = CURRENT_ROOT / f".{preset['id']}.{uuid.uuid4().hex}.tmp"
    try:
        rendered = _render(preset)
        _parse_text(rendered, destination.name)
        temporary.write_bytes(rendered.encode("utf-8"))
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return payload()


def delete_preset(preset_id: str) -> dict[str, Any]:
    normalized = str(preset_id or "").strip().lower()
    if not ID_PATTERN.fullmatch(normalized):
        raise PromptPresetError("Invalid preset id.")
    if normalized in _files(ORIGINAL_ROOT):
        raise PromptPresetError("Built-in presets cannot be deleted; reset them instead.")
    path = CURRENT_ROOT / f"{normalized}.md"
    if not path.is_file():
        raise PromptPresetError("Preset not found.")
    path.unlink()
    return payload()


def reset_preset(preset_id: str) -> dict[str, Any]:
    normalized = str(preset_id or "").strip().lower()
    source = _files(ORIGINAL_ROOT).get(normalized)
    if source is None:
        raise PromptPresetError("Only built-in presets can be reset.")
    CURRENT_ROOT.mkdir(parents=True, exist_ok=True)
    temporary = CURRENT_ROOT / f".{normalized}.{uuid.uuid4().hex}.tmp"
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, CURRENT_ROOT / f"{normalized}.md")
    finally:
        if temporary.exists():
            temporary.unlink()
    return payload()


def resolve_text(text: str) -> tuple[str, list[dict[str, Any]]]:
    value = str(text or "")
    if "@" not in value:
        return value, []
    presets = list_presets()
    by_tag = {preset["tag"].casefold(): preset for preset in presets}
    pattern = re.compile(r"(?<![A-Za-z0-9_@])@([A-Za-z0-9][A-Za-z0-9_-]{0,63})(?![A-Za-z0-9_-])")
    activated: list[dict[str, Any]] = []
    seen: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        preset = by_tag.get(match.group(1).casefold())
        if preset is None:
            return match.group(0)
        if preset["id"] not in seen:
            seen.add(preset["id"])
            activated.append(preset)
        return preset["name"]

    resolved = pattern.sub(replace, value)
    if not activated:
        return value, []
    blocks = [
        f"## {preset['type'].title()} preset: {preset['name']}\n{preset['markdown'].strip()}"
        for preset in activated
    ]
    return "\n\n".join([*blocks, f"## User prompt\n{resolved}"]), activated
