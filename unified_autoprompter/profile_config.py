from __future__ import annotations

import copy
import json
import re
import shutil
from pathlib import Path
from typing import Any

from .profiles import (
    ALL_GENERATION_TYPES,
    ALL_FORMATS,
    ALL_IMAGE_STATES,
    FORMAT_JSON,
    FORMAT_NATURAL,
    FORMAT_TAGS,
    GenerationPathRule,
    InstructionBlock,
    OutputContractRule,
    PromptFormatRule,
    PromptProfile,
    enabled_formats,
)


CONFIG_VERSION = 7
CONFIG_FILENAME = "model_prompt_profiles.json"
DEFAULT_CONFIG_FILENAME = "model_prompt_profiles.defaults.json"
ALLOWED_FORMATS = set(ALL_FORMATS)
ALLOWED_MEDIA_TYPES = {"image", "video"}
ALLOWED_ENGINES = {"standard", "jsonx"}
KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]*$")
LEGACY_NSFW_GENERATION_TYPES = tuple(
    key for key in ALL_GENERATION_TYPES if key != "video_to_video"
)

DEFAULT_JSONX_CONFIG: dict[str, Any] = {
    "generation_profile": "adaptive",
    "generation_mode": "fast",
    "preset_context_mode": "optimized",
    "template_use_presets": False,
    "enable_framing_and_placement": False,
    "detail_level": "deep",
}


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
        common_rules=InstructionBlock("Core Model Rules", "", ""),
        common_guide=InstructionBlock("Profile Guide", "", ""),
    )


def _block_from_dict(
    data: Any,
    *,
    default_title: str = "Instructions",
    default_source: str = "",
) -> InstructionBlock:
    if isinstance(data, InstructionBlock):
        return data
    if isinstance(data, str):
        source: dict[str, Any] = {"text": data}
    else:
        source = data if isinstance(data, dict) else {}
    return InstructionBlock(
        title=str(source.get("title") or default_title).strip(),
        text=str(source.get("text") or "").strip(),
        source=str(source.get("source") or default_source).strip(),
    )


def _blocks_from_value(data: Any, *, default_title: str) -> tuple[InstructionBlock, ...]:
    if isinstance(data, list):
        values = data
    elif data:
        values = [data]
    else:
        values = []
    return tuple(
        _block_from_dict(value, default_title=default_title)
        for value in values
        if isinstance(value, (dict, str))
    )


def _merged_block(
    data: Any,
    *,
    title: str,
    default_source: str,
) -> InstructionBlock:
    """Collapse legacy card arrays into one editable block with internal headings."""

    blocks = _blocks_from_value(data, default_title=title)
    if not blocks:
        return InstructionBlock(title=title, text="", source=default_source)
    sections: list[str] = []
    sources: list[str] = []
    for block in blocks:
        text = block.text.strip()
        if not text:
            continue
        heading = block.title.strip()
        sections.append(f"## {heading}\n{text}" if heading else text)
        if block.source and block.source not in sources:
            sources.append(block.source)
    return InstructionBlock(
        title=title,
        text="\n\n".join(sections).strip(),
        source="; ".join(sources) or default_source,
    )


def _rule_from_dict(data: dict[str, Any] | None) -> PromptFormatRule:
    data = data if isinstance(data, dict) else {}
    common_rules = data.get("common_rules")
    if common_rules is None:
        common_blocks = data.get("common_blocks")
        if common_blocks is None and data.get("common_instructions"):
            common_blocks = [{
            "title": "Core model behavior",
            "text": data.get("common_instructions"),
            "source": "Legacy profile rule",
            }]
        common_rules = _merged_block(
            common_blocks,
            title="Core Model Rules",
            default_source="Migrated profile rules",
        )
    return PromptFormatRule(
        enabled=bool(data.get("enabled")),
        common_rules=_block_from_dict(
            common_rules,
            default_title="Core Model Rules",
            default_source="Profile rules",
        ),
        common_guide=_block_from_dict(
            data.get("common_guide"),
            default_title="Profile Guide",
            default_source="Canonical profile guide",
        ),
    )


def _contract_from_dict(data: Any) -> OutputContractRule:
    source = data if isinstance(data, dict) else {}
    return OutputContractRule(
        negative_off=str(source.get("negative_off") or "").strip(),
        negative_on=str(source.get("negative_on") or "").strip(),
    )


def _generation_path_from_dict(data: Any, generation_type: str) -> GenerationPathRule:
    source = data if isinstance(data, dict) else {}
    raw_contracts = source.get("output_contracts") if isinstance(source.get("output_contracts"), dict) else {}
    path_rules = source.get("path_rules")
    if path_rules is None:
        instruction_blocks = source.get("instruction_blocks")
        if instruction_blocks is None and source.get("instructions"):
            instruction_blocks = [{
            "title": "Generation-path guide",
            "text": source.get("instructions"),
            "source": "Legacy generation-path rule",
            }]
        path_rules = _merged_block(
            instruction_blocks,
            title="Generation Path Rules",
            default_source="Migrated generation-path rules",
        )
    raw_image_states = source.get("image_state_blocks") if isinstance(source.get("image_state_blocks"), dict) else {}
    return GenerationPathRule(
        label=str(source.get("label") or generation_type).strip(),
        path_rules=_block_from_dict(
            path_rules,
            default_title="Generation Path Rules",
            default_source="Generation-path rules",
        ),
        path_guide=_block_from_dict(
            source.get("path_guide"),
            default_title="Generation Path Guide",
            default_source="Canonical generation-path guide",
        ),
        image_state_blocks={
            key: _block_from_dict(
                raw_image_states.get(key),
                default_title=key.replace("_", " ").title(),
            )
            for key in ALL_IMAGE_STATES
        },
        output_contracts={
            format_key: _contract_from_dict(raw_contracts.get(format_key))
            for format_key in ALL_FORMATS
        },
    )


def _jsonx_config_from_dict(data: Any) -> dict[str, Any]:
    source = data if isinstance(data, dict) else {}
    config = dict(DEFAULT_JSONX_CONFIG)
    for key in config:
        if key not in source:
            continue
        if isinstance(config[key], bool):
            config[key] = bool(source[key])
        else:
            config[key] = str(source[key] or "").strip()
    return config


def _migrate_legacy_profile(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize obsolete JsonX records without inventing model-facing text.

    Model-facing instructions are owned exclusively by their Markdown
    reference stores. This legacy JSON loader retains behavior metadata only.
    """

    formats = item.get("formats")
    if isinstance(formats, dict):
        return item
    enabled = [str(value) for value in (formats or [item.get("default_format") or FORMAT_NATURAL]) if str(value) in ALLOWED_FORMATS]
    notes = str(item.get("notes") or "").strip()
    migrated_formats = {}
    for format_key in ALL_FORMATS:
        is_enabled = format_key in enabled
        migrated_formats[format_key] = {
            "enabled": is_enabled,
            "common_rules": {"title": "Core Model Rules", "text": "", "source": ""},
            "common_guide": {"title": "Profile Guide", "text": "", "source": ""},
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
    raw_paths = data.get("generation_paths") if isinstance(data.get("generation_paths"), dict) else {}
    generation_paths = {
        key: _generation_path_from_dict(value, key)
        for key, value in raw_paths.items()
        if key in ALL_GENERATION_TYPES
    }
    default_generation_type = str(data.get("default_generation_type") or "").strip()
    engine = str(data.get("engine") or ("jsonx" if key == "jsonx" else "standard")).strip().lower()
    jsonx_config = _jsonx_config_from_dict(data.get("jsonx_config")) if engine == "jsonx" else {}
    return PromptProfile(
        key=key,
        label=label,
        media_type=media_type,
        default_format=default_format,
        negative_supported=negative_supported,
        json_supported=json_supported,
        notes=notes,
        formats=formats,
        default_generation_type=default_generation_type,
        generation_paths=generation_paths,
        engine=engine,
        jsonx_config=jsonx_config,
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
    if profile.engine not in ALLOWED_ENGINES:
        raise ValueError(f"Profile {profile.key} engine must be standard or jsonx.")
    active_formats = enabled_formats(profile)
    if not active_formats:
        raise ValueError(f"Profile {profile.key} needs at least one enabled prompt format.")
    if profile.default_format not in active_formats:
        raise ValueError(f"Profile {profile.key} default format must be enabled.")
    if not profile.generation_paths:
        raise ValueError(f"Profile {profile.key} needs at least one generation path.")
    if profile.default_generation_type not in profile.generation_paths:
        raise ValueError(f"Profile {profile.key} default generation type must be enabled.")
    for format_key in active_formats:
        rule = profile.formats[format_key]
        if not rule.common_rules.text:
            raise ValueError(f"Profile {profile.key} {format_key} needs non-empty common rules.")
    for generation_type, path in profile.generation_paths.items():
        if generation_type not in ALL_GENERATION_TYPES:
            raise ValueError(f"Profile {profile.key} has an invalid generation path: {generation_type}.")
        if not path.path_rules.text:
            raise ValueError(f"Profile {profile.key} {generation_type} needs non-empty generation-path rules.")
        if set(path.image_state_blocks) != set(ALL_IMAGE_STATES):
            raise ValueError(f"Profile {profile.key} {generation_type} needs all image-state blocks.")
        if any(not block.text for block in path.image_state_blocks.values()):
            raise ValueError(f"Profile {profile.key} {generation_type} image-state blocks cannot be empty.")
        for format_key in active_formats:
            contract = path.output_contracts.get(format_key)
            if not contract or not contract.negative_off or not contract.negative_on:
                raise ValueError(
                    f"Profile {profile.key} {generation_type} {format_key} needs both output contracts."
                )
    if profile.engine == "jsonx":
        if profile.media_type != "image":
            raise ValueError(f"JsonX profile {profile.key} must use image media type.")
        if set(active_formats) - {FORMAT_JSON, FORMAT_NATURAL}:
            raise ValueError(f"JsonX profile {profile.key} supports only json and natural formats.")
        if set(profile.generation_paths) != {"text_to_image", "image_to_image"}:
            raise ValueError(f"JsonX profile {profile.key} must support exactly Text to Image and Image to Image.")
        config = _jsonx_config_from_dict(profile.jsonx_config)
        if config["generation_profile"] not in {"adaptive", "template_fill"}:
            raise ValueError(f"JsonX profile {profile.key} has an invalid generation profile.")
        if config["generation_mode"] not in {"fast", "refined"}:
            raise ValueError(f"JsonX profile {profile.key} has an invalid generation mode.")
        if config["preset_context_mode"] not in {"optimized", "full"}:
            raise ValueError(f"JsonX profile {profile.key} has an invalid preset context mode.")
        if config["detail_level"] not in {"deep", "exhaustive"}:
            raise ValueError(f"JsonX profile {profile.key} has an invalid hierarchy depth.")


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


def _validate_nsfw_rules(value: Any) -> dict[str, InstructionBlock]:
    source = value if isinstance(value, dict) else {}
    result = {
        key: _block_from_dict(
            source.get(key),
            default_title=f"{key.replace('_', ' ').title()} NSFW guidance",
            default_source="Global generation-path guidance",
        )
        for key in LEGACY_NSFW_GENERATION_TYPES
    }
    missing = [key for key, block in result.items() if not block.text]
    if missing:
        raise ValueError(f"NSFW rules are missing generation paths: {', '.join(missing)}.")
    return result


def _profiles_to_config(profiles: list[PromptProfile], nsfw_rules: Any) -> dict[str, Any]:
    blocks = _validate_nsfw_rules(nsfw_rules)
    return {
        "version": CONFIG_VERSION,
        "nsfw_rules": {key: block.to_dict() for key, block in blocks.items()},
        "profiles": [profile.to_dict() for profile in profiles],
    }


def default_config() -> dict[str, Any]:
    return _read_json(default_config_path())


def _migrate_v6_config(data: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    """Preserve v6 rule edits while installing curated v7 guide fields."""

    default_by_key = {
        str(item.get("key") or ""): item
        for item in defaults.get("profiles", [])
        if isinstance(item, dict)
    }
    migrated: list[dict[str, Any]] = []
    for raw in data.get("profiles", []):
        if not isinstance(raw, dict):
            continue
        profile = _profile_from_dict(raw).to_dict()
        default_profile = default_by_key.get(profile["key"])
        if default_profile:
            for format_key, rule in profile["formats"].items():
                default_rule = default_profile.get("formats", {}).get(format_key, {})
                if not str(rule.get("common_guide", {}).get("text") or "").strip():
                    rule["common_guide"] = dict(default_rule.get("common_guide") or {})
            default_paths = default_profile.get("generation_paths", {})
            for path_key, default_path in default_paths.items():
                if path_key not in profile["generation_paths"]:
                    profile["generation_paths"][path_key] = copy.deepcopy(default_path)
                    continue
                path = profile["generation_paths"][path_key]
                if not str(path.get("path_guide", {}).get("text") or "").strip():
                    path["path_guide"] = dict(default_path.get("path_guide") or {})
            if profile.get("engine") == "jsonx":
                profile["jsonx_config"] = {
                    **dict(default_profile.get("jsonx_config") or {}),
                    **dict(profile.get("jsonx_config") or {}),
                }
        migrated.append(profile)
    return {
        "version": CONFIG_VERSION,
        "nsfw_rules": {
            **dict(defaults.get("nsfw_rules") or {}),
            **dict(data.get("nsfw_rules") or {}),
        },
        "profiles": migrated,
    }


def load_config() -> dict[str, Any]:
    path = config_path()
    defaults = default_config()
    if not path.exists():
        data = defaults
        _config_to_profiles(data)
        _validate_nsfw_rules(data.get("nsfw_rules"))
        _atomic_write(path, data, backup=False)
        return data
    try:
        data = _read_json(path)
        if int(data.get("version") or 0) != CONFIG_VERSION:
            old_version = int(data.get("version") or 0)
            backup_path = path.with_name(f"{path.stem}.v{old_version}.backup{path.suffix}")
            if not backup_path.exists():
                shutil.copy2(path, backup_path)
            data = _migrate_v6_config(data, defaults) if old_version == 6 else defaults
            _atomic_write(path, data, backup=False)
        default_profiles = _config_to_profiles(defaults)
        default_nsfw_rules = _validate_nsfw_rules(defaults.get("nsfw_rules"))
        existing_keys = {str(profile.get("key") or "") for profile in data.get("profiles", []) if isinstance(profile, dict)}
        missing_defaults = [profile.to_dict() for profile in default_profiles if profile.key not in existing_keys]
        if missing_defaults:
            data = {
                **data,
                "version": CONFIG_VERSION,
                "nsfw_rules": data.get("nsfw_rules") or default_nsfw_rules,
                "profiles": list(data.get("profiles") or []) + missing_defaults,
            }
        profiles = _config_to_profiles(data)
        nsfw_rules = _validate_nsfw_rules(data.get("nsfw_rules"))
    except Exception:
        data = defaults
        profiles = _config_to_profiles(data)
        nsfw_rules = _validate_nsfw_rules(data.get("nsfw_rules"))
    return _profiles_to_config(profiles, nsfw_rules)


def load_user_profiles() -> list[PromptProfile]:
    return _config_to_profiles(load_config())


def merged_profiles() -> dict[str, PromptProfile]:
    return {profile.key: profile for profile in load_user_profiles()}


def global_nsfw_rules() -> dict[str, str]:
    return {
        key: block.text
        for key, block in _validate_nsfw_rules(load_config().get("nsfw_rules")).items()
    }


def global_nsfw_blocks() -> dict[str, InstructionBlock]:
    return _validate_nsfw_rules(load_config().get("nsfw_rules"))


def save_config(payload: dict[str, Any]) -> dict[str, Any]:
    profiles = _config_to_profiles(payload if isinstance(payload, dict) else {})
    nsfw_rules = _validate_nsfw_rules((payload if isinstance(payload, dict) else {}).get("nsfw_rules"))
    data = _profiles_to_config(profiles, nsfw_rules)
    _atomic_write(config_path(), data, backup=True)
    return data


def reset_config() -> dict[str, Any]:
    data = default_config()
    profiles = _config_to_profiles(data)
    data = _profiles_to_config(profiles, _validate_nsfw_rules(data.get("nsfw_rules")))
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
        "nsfw_rules": {
            key: block.to_dict()
            for key, block in _validate_nsfw_rules(config.get("nsfw_rules")).items()
        },
        "default_nsfw_rules": {
            key: block.to_dict()
            for key, block in _validate_nsfw_rules(defaults.get("nsfw_rules")).items()
        },
        "builtin_keys": sorted(profile.key for profile in default_profiles),
        "formats": list(ALL_FORMATS),
        "generation_types": list(ALL_GENERATION_TYPES),
        "media_types": sorted(ALLOWED_MEDIA_TYPES),
        "raw": config,
    }
