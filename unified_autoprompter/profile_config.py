from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from .profiles import (
    ALL_FORMATS,
    FORMAT_JSON,
    FORMAT_NATURAL,
    FORMAT_TAGS,
    PromptFormatRule,
    PromptProfile,
    enabled_formats,
)


CONFIG_VERSION = 3
CONFIG_FILENAME = "model_prompt_profiles.json"
DEFAULT_CONFIG_FILENAME = "model_prompt_profiles.defaults.json"
ALLOWED_FORMATS = set(ALL_FORMATS)
ALLOWED_MEDIA_TYPES = {"image", "video"}
KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]*$")


def config_path() -> Path:
    return Path(__file__).with_name(CONFIG_FILENAME)


def default_config_path() -> Path:
    return Path(__file__).with_name(DEFAULT_CONFIG_FILENAME)


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a JSON object.")
    return data


def _atomic_write(path: Path, data: dict[str, Any], backup: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup and path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def _empty_rule(enabled: bool = False) -> PromptFormatRule:
    return PromptFormatRule(
        enabled=enabled,
        common_instructions="",
        output_contract_negative_off="",
        output_contract_negative_on="",
        with_image_reference_instructions="",
        without_image_reference_instructions="",
    )


def _rule_from_dict(data: dict[str, Any] | None) -> PromptFormatRule:
    data = data if isinstance(data, dict) else {}
    return PromptFormatRule(
        enabled=bool(data.get("enabled")),
        common_instructions=str(data.get("common_instructions") or "").strip(),
        output_contract_negative_off=str(data.get("output_contract_negative_off") or "").strip(),
        output_contract_negative_on=str(data.get("output_contract_negative_on") or "").strip(),
        with_image_reference_instructions=str(data.get("with_image_reference_instructions") or "").strip(),
        without_image_reference_instructions=str(data.get("without_image_reference_instructions") or "").strip(),
    )


def _legacy_contract(prompt_format: str, negative_enabled: bool) -> str:
    if prompt_format == FORMAT_JSON:
        if negative_enabled:
            return (
                "Return ONLY JSON with this wrapper shape:\n"
                "{\n"
                '  "prompt_json": { ... target-model prompt object ... },\n'
                '  "negative": "the final negative prompt for downstream negative/NAG nodes"\n'
                "}\n"
                "Do not put the target JSON inside a string."
            )
        return (
            "Return ONLY JSON with this wrapper shape:\n"
            "{\n"
            '  "prompt_json": { ... target-model prompt object ... }\n'
            "}\n"
            "Do not put the target JSON inside a string."
        )
    if negative_enabled:
        return (
            "Return ONLY JSON with this shape:\n"
            "{\n"
            '  "positive": "the final positive prompt",\n'
            '  "negative": "the final negative prompt"\n'
            "}"
        )
    return (
        "Return ONLY JSON with this shape:\n"
        "{\n"
        '  "positive": "the final prompt",\n'
        '  "negative": ""\n'
        "}"
    )


def _migrate_legacy_profile(item: dict[str, Any]) -> dict[str, Any]:
    formats = item.get("formats")
    if isinstance(formats, dict):
        return item
    enabled = [str(value) for value in (formats or [item.get("default_format") or FORMAT_NATURAL]) if str(value) in ALLOWED_FORMATS]
    template = str(item.get("system_prompt_template") or item.get("notes") or "").strip()
    notes = str(item.get("notes") or "").strip()
    migrated_formats = {}
    for format_key in ALL_FORMATS:
        is_enabled = format_key in enabled
        migrated_formats[format_key] = {
            "enabled": is_enabled,
            "common_instructions": template if is_enabled else "",
            "output_contract_negative_off": _legacy_contract(format_key, False) if is_enabled else "",
            "output_contract_negative_on": _legacy_contract(format_key, True) if is_enabled else "",
            "with_image_reference_instructions": (
                "A connected image reference is available. Use it for layout, identity, colors, and visual details while following the format-specific instructions."
                if is_enabled
                else ""
            ),
            "without_image_reference_instructions": (
                "No image reference is available. Build the prompt entirely from the text fields and user intent."
                if is_enabled
                else ""
            ),
        }
    default_format = str(item.get("default_format") or (enabled[0] if enabled else FORMAT_NATURAL))
    if default_format not in enabled and enabled:
        default_format = enabled[0]
    return {
        "key": item.get("key"),
        "label": item.get("label"),
        "media_type": item.get("media_type") or "image",
        "default_format": default_format,
        "negative_supported": bool(item.get("negative_supported", True)),
        "json_supported": bool(item.get("json_supported", FORMAT_JSON in enabled)),
        "notes": notes,
        "formats": migrated_formats,
    }


def _profile_from_dict(data: dict[str, Any]) -> PromptProfile:
    data = _migrate_legacy_profile(data)
    key = str(data.get("key") or "").strip()
    label = str(data.get("label") or key).strip()
    media_type = str(data.get("media_type") or "image").strip()
    default_format = str(data.get("default_format") or FORMAT_NATURAL).strip()
    negative_supported = bool(data.get("negative_supported"))
    json_supported = bool(data.get("json_supported"))
    notes = str(data.get("notes") or "").strip()
    raw_formats = data.get("formats") if isinstance(data.get("formats"), dict) else {}
    formats = {format_key: _rule_from_dict(raw_formats.get(format_key)) for format_key in ALL_FORMATS}
    return PromptProfile(
        key=key,
        label=label,
        media_type=media_type,
        default_format=default_format,
        negative_supported=negative_supported,
        json_supported=json_supported,
        notes=notes,
        formats=formats,
    )


def validate_profile(profile: PromptProfile, seen: set[str] | None = None) -> None:
    if not KEY_PATTERN.match(profile.key):
        raise ValueError(f"Invalid model key: {profile.key!r}. Use lowercase letters, numbers, and underscores.")
    if seen is not None and profile.key in seen:
        raise ValueError(f"Duplicate model key: {profile.key}")
    if not profile.label:
        raise ValueError(f"Profile {profile.key} needs a display label.")
    if profile.media_type not in ALLOWED_MEDIA_TYPES:
        raise ValueError(f"Profile {profile.key} media_type must be image or video.")
    active_formats = enabled_formats(profile)
    if not active_formats:
        raise ValueError(f"Profile {profile.key} needs at least one enabled prompt format.")
    if profile.default_format not in active_formats:
        raise ValueError(f"Profile {profile.key} default format must be enabled.")
    for format_key in active_formats:
        rule = profile.formats[format_key]
        missing = []
        if not rule.common_instructions:
            missing.append("common instructions")
        if not rule.with_image_reference_instructions:
            missing.append("with-image instructions")
        if not rule.without_image_reference_instructions:
            missing.append("without-image instructions")
        if not rule.output_contract_negative_off:
            missing.append("negative-off output contract")
        if not rule.output_contract_negative_on:
            missing.append("negative-on output contract")
        if missing:
            raise ValueError(f"Profile {profile.key} {format_key} is missing: {', '.join(missing)}.")


def validate_profiles(profiles: list[PromptProfile]) -> None:
    seen: set[str] = set()
    for profile in profiles:
        validate_profile(profile, seen)
        seen.add(profile.key)


def _config_to_profiles(data: dict[str, Any]) -> list[PromptProfile]:
    items = data.get("profiles")
    if not isinstance(items, list):
        raise ValueError("profiles must be a list.")
    profiles = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each profile must be an object.")
        profiles.append(_profile_from_dict(item))
    validate_profiles(profiles)
    return profiles


def _profiles_to_config(profiles: list[PromptProfile]) -> dict[str, Any]:
    return {
        "version": CONFIG_VERSION,
        "profiles": [profile.to_dict() for profile in profiles],
    }


def default_config() -> dict[str, Any]:
    return _read_json(default_config_path())


def load_config() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        data = default_config()
        _config_to_profiles(data)
        _atomic_write(path, data, backup=False)
        return data
    try:
        data = _read_json(path)
        profiles = _config_to_profiles(data)
    except Exception:
        data = default_config()
        profiles = _config_to_profiles(data)
    return _profiles_to_config(profiles)


def load_user_profiles() -> list[PromptProfile]:
    return _config_to_profiles(load_config())


def merged_profiles() -> dict[str, PromptProfile]:
    return {profile.key: profile for profile in load_user_profiles()}


def save_config(payload: dict[str, Any]) -> dict[str, Any]:
    profiles = _config_to_profiles(payload if isinstance(payload, dict) else {})
    data = _profiles_to_config(profiles)
    _atomic_write(config_path(), data, backup=True)
    return data


def reset_config() -> dict[str, Any]:
    data = default_config()
    profiles = _config_to_profiles(data)
    data = _profiles_to_config(profiles)
    _atomic_write(config_path(), data, backup=True)
    return data


def profile_config_payload() -> dict[str, Any]:
    config = load_config()
    defaults = default_config()
    default_profiles = _config_to_profiles(defaults)
    profiles = _config_to_profiles(config)
    return {
        "version": CONFIG_VERSION,
        "path": str(config_path()),
        "default_path": str(default_config_path()),
        "profiles": [profile.to_dict() for profile in profiles],
        "default_profiles": [profile.to_dict() for profile in default_profiles],
        "builtin_keys": sorted(profile.key for profile in default_profiles),
        "formats": list(ALL_FORMATS),
        "media_types": sorted(ALLOWED_MEDIA_TYPES),
        "raw": config,
    }
