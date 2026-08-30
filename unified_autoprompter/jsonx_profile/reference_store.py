from __future__ import annotations

import copy
import json
import os
import re
import shutil
import string
import uuid
from pathlib import Path, PurePosixPath
from typing import Any


JSONX_REFERENCE_SCHEMA_VERSION = 1
REFERENCE_ROOT = Path(__file__).resolve().parents[1] / "reference"
ORIGINAL_ROOT = REFERENCE_ROOT / "original" / "JsonX"
CURRENT_ROOT = REFERENCE_ROOT / "current_use" / "JsonX"
MANIFEST_FILENAME = "manifest.json"
KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]*$")
TEMPLATE_TOKEN_PATTERN = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")

REQUIRED_FILE_KEYS = (
    "generation_text_to_image",
    "generation_image_to_image",
    "stage_one_adaptive",
    "stage_one_template_fill",
    "stage_two_json_refinement",
    "stage_two_natural_conversion",
    "repair_json",
    "repair_natural",
    "adaptive_image_with",
    "adaptive_image_without",
    "template_image_with",
    "template_image_without",
    "refinement_image_with",
    "refinement_image_without",
    "natural_image_with",
    "natural_image_without",
    "adaptive_open_world",
    "refinement_open_world",
    "depth_deep",
    "depth_exhaustive",
    "framing_json_enabled",
    "framing_json_disabled",
    "framing_natural_enabled",
    "framing_natural_disabled",
    "template_presets_enabled",
    "template_presets_disabled",
    "template_refinement",
    "reference_with_supported",
    "reference_without_supported",
    "reference_without_unsupported",
    "user_stage_one",
    "user_json_refinement",
    "user_natural_conversion",
    "user_json_repair",
    "user_natural_repair",
    "template_adaptive_ranked",
    "template_adaptive_full",
    "template_fill_without_framing",
    "template_fill_with_framing",
    "presets_full",
    "contract_stage_one_json",
    "contract_stage_two_json",
    "contract_stage_two_natural",
    "contract_json_repair",
    "contract_natural_repair",
)

TEMPLATE_REQUIREMENTS = {
    "template_adaptive_ranked": {"SCHEMA_PATHS", "RANKED_PRESET_CANDIDATES"},
    "template_adaptive_full": {"PRESET_CATALOG"},
    "template_fill_without_framing": set(),
    "template_fill_with_framing": set(),
}

USER_TEMPLATE_FIELDS = {
    "user_stage_one": {"user_instructions"},
    "user_json_refinement": {"user_instructions", "stage_one_json"},
    "user_natural_conversion": {"user_instructions", "stage_one_json"},
    "user_json_repair": {"validation_error", "user_instructions", "raw_response"},
    "user_natural_repair": {
        "validation_error",
        "user_instructions",
        "stage_one_json",
        "raw_response",
    },
}


class JsonXReferenceStoreError(ValueError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes().decode("utf-8"))
    except Exception as exc:
        raise JsonXReferenceStoreError(f"Could not read {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise JsonXReferenceStoreError(f"{path.name} must contain a JSON object.")
    return value


def _read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(str(text).encode("utf-8"))


def _safe_relative(value: object) -> str:
    raw = str(value or "").replace("\\", "/")
    path = PurePosixPath(raw)
    if not raw or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise JsonXReferenceStoreError(f"Unsafe JsonX reference path: {raw!r}.")
    return path.as_posix()


def _safe_profile_folder(value: object) -> str:
    folder = _safe_relative(value)
    parts = PurePosixPath(folder).parts
    if len(parts) != 2 or parts[0] != "profiles":
        raise JsonXReferenceStoreError(
            f"JsonX profile folder must be profiles/<name>: {folder!r}."
        )
    return folder


def _profiles(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    profiles = manifest.get("profiles")
    if not isinstance(profiles, list):
        raise JsonXReferenceStoreError("JsonX manifest profiles must be an array.")
    return profiles


def _validate_defaults(profile: dict[str, Any]) -> None:
    defaults = profile.get("defaults")
    if not isinstance(defaults, dict):
        raise JsonXReferenceStoreError(f"JsonX profile {profile.get('key')} needs defaults.")
    allowed = {
        "generation_profile": {"adaptive", "template_fill"},
        "generation_mode": {"fast", "refined"},
        "preset_context_mode": {"optimized", "full"},
        "detail_level": {"deep", "exhaustive"},
    }
    for key, values in allowed.items():
        if str(defaults.get(key) or "") not in values:
            raise JsonXReferenceStoreError(
                f"JsonX profile {profile.get('key')} has invalid {key}."
            )
    for key in ("template_use_presets", "enable_framing_and_placement"):
        if not isinstance(defaults.get(key), bool):
            raise JsonXReferenceStoreError(
                f"JsonX profile {profile.get('key')} has invalid {key}."
            )


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    if int(manifest.get("schema_version") or 0) != JSONX_REFERENCE_SCHEMA_VERSION:
        raise JsonXReferenceStoreError(
            "Unified JsonX reference schema mismatch. Restart ComfyUI and hard-refresh the browser."
        )
    file_map = manifest.get("file_map")
    if not isinstance(file_map, dict):
        raise JsonXReferenceStoreError("JsonX manifest needs a file_map object.")
    missing = sorted(set(REQUIRED_FILE_KEYS) - set(file_map))
    unknown = sorted(set(file_map) - set(REQUIRED_FILE_KEYS))
    if missing or unknown:
        raise JsonXReferenceStoreError(
            f"JsonX file_map mismatch; missing={missing}, unknown={unknown}."
        )
    normalized_paths: set[str] = set()
    for key in REQUIRED_FILE_KEYS:
        path = _safe_relative(file_map[key])
        if path in normalized_paths or not path.endswith(".md"):
            raise JsonXReferenceStoreError(f"Invalid or duplicate JsonX file mapping: {path!r}.")
        normalized_paths.add(path)
    seen_keys: set[str] = set()
    seen_folders: set[str] = set()
    for profile in _profiles(manifest):
        if not isinstance(profile, dict):
            raise JsonXReferenceStoreError("Every JsonX profile must be an object.")
        key = str(profile.get("key") or "").strip()
        if not KEY_PATTERN.fullmatch(key) or key in seen_keys:
            raise JsonXReferenceStoreError(f"Invalid or duplicate JsonX profile key: {key!r}.")
        seen_keys.add(key)
        folder = _safe_profile_folder(profile.get("folder"))
        if folder in seen_folders:
            raise JsonXReferenceStoreError(f"Duplicate JsonX profile folder: {folder!r}.")
        seen_folders.add(folder)
        enabled_formats = profile.get("enabled_formats")
        if not isinstance(enabled_formats, list) or not enabled_formats:
            raise JsonXReferenceStoreError(f"JsonX profile {key} needs enabled formats.")
        if any(value not in {"json", "natural"} for value in enabled_formats):
            raise JsonXReferenceStoreError(f"JsonX profile {key} supports only JSON and Natural.")
        if profile.get("default_format") not in enabled_formats:
            raise JsonXReferenceStoreError(f"JsonX profile {key} default format must be enabled.")
        enabled_types = profile.get("enabled_generation_types")
        if not isinstance(enabled_types, list) or not enabled_types:
            raise JsonXReferenceStoreError(f"JsonX profile {key} needs generation types.")
        if any(value not in {"text_to_image", "image_to_image"} for value in enabled_types):
            raise JsonXReferenceStoreError(f"JsonX profile {key} has an unsupported generation type.")
        if profile.get("default_generation_type") not in enabled_types:
            raise JsonXReferenceStoreError(
                f"JsonX profile {key} default generation type must be enabled."
            )
        _validate_defaults(profile)
    return manifest


def _load_manifest(root: Path) -> dict[str, Any]:
    return validate_manifest(_read_json(root / MANIFEST_FILENAME))


def _markdown_files(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    if not root.exists():
        return files
    for path in sorted(root.rglob("*.md"), key=lambda item: item.as_posix().lower()):
        files[path.relative_to(root).as_posix()] = _read_text(path)
    return files


def _profile_by_key(manifest: dict[str, Any], profile_key: str) -> dict[str, Any]:
    key = str(profile_key or "").strip()
    for profile in _profiles(manifest):
        if str(profile.get("key") or "") == key:
            return profile
    raise JsonXReferenceStoreError(f"Unknown Unified JsonX profile: {key}.")


def _file_path(manifest: dict[str, Any], profile: dict[str, Any], semantic_key: str) -> str:
    try:
        relative = _safe_relative(manifest["file_map"][semantic_key])
    except KeyError as exc:
        raise JsonXReferenceStoreError(f"Unknown JsonX block: {semantic_key}.") from exc
    return _safe_relative(f"{_safe_profile_folder(profile['folder'])}/{relative}")


def _extract_json_object(text: str, label: str) -> dict[str, Any]:
    start = text.find("{")
    if start < 0:
        raise JsonXReferenceStoreError(f"{label} does not contain a JSON object.")
    try:
        value = json.loads(text[start:])
    except Exception as exc:
        raise JsonXReferenceStoreError(f"{label} contains invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise JsonXReferenceStoreError(f"{label} must contain a JSON object.")
    return value


def _validate_preset_catalog(value: dict[str, Any]) -> None:
    seen_ids: dict[str, str] = {}
    leaf_count = 0

    def walk(node: Any, path: str) -> None:
        nonlocal leaf_count
        if not isinstance(node, dict) or not node:
            raise JsonXReferenceStoreError(
                f"JsonX preset branch {path or '<root>'} must be a non-empty object."
            )
        children = list(node.values())
        if all(isinstance(child, str) for child in children):
            leaf_count += 1
            for raw_id, raw_text in node.items():
                preset_id = str(raw_id or "").strip()
                text = str(raw_text or "").strip()
                if not preset_id or not text:
                    raise JsonXReferenceStoreError(
                        f"JsonX preset leaf {path} contains an empty ID or value."
                    )
                prior = seen_ids.get(preset_id)
                if prior is not None:
                    raise JsonXReferenceStoreError(
                        f"JsonX preset ID {preset_id!r} conflicts between {prior} and {path}."
                    )
                seen_ids[preset_id] = path
            return
        direct_text = {
            str(key): str(child).strip()
            for key, child in node.items()
            if isinstance(child, str)
        }
        if direct_text:
            if set(direct_text) != {"additional_information"}:
                raise JsonXReferenceStoreError(
                    f"JsonX preset branch {path or '<root>'} mixes preset values and child objects."
                )
        for key, child in node.items():
            if isinstance(child, str):
                continue
            walk(child, f"{path}.{key}" if path else str(key))

    walk(value, "")
    if not leaf_count or "subject" not in value:
        raise JsonXReferenceStoreError(
            "JsonX presets must contain preset leaves and the subject hierarchy."
        )


def _validate_template_tokens(key: str, text: str) -> None:
    required = TEMPLATE_REQUIREMENTS[key]
    found = TEMPLATE_TOKEN_PATTERN.findall(text)
    if set(found) != required or any(found.count(token) != 1 for token in required):
        raise JsonXReferenceStoreError(
            f"JsonX template {key} requires exactly these tokens: {sorted(required)}."
        )
    residual = re.findall(r"\{\{[^{}]+\}\}", text)
    if len(residual) != len(found):
        raise JsonXReferenceStoreError(f"JsonX template {key} contains an invalid token.")


def _validate_user_template(key: str, text: str) -> None:
    fields: set[str] = set()
    try:
        for _literal, field_name, _format_spec, _conversion in string.Formatter().parse(text):
            if field_name:
                fields.add(field_name)
    except ValueError as exc:
        raise JsonXReferenceStoreError(f"JsonX user template {key} is invalid: {exc}") from exc
    allowed = USER_TEMPLATE_FIELDS[key]
    if not fields.issubset(allowed) or not allowed.issubset(fields):
        raise JsonXReferenceStoreError(
            f"JsonX user template {key} requires exactly these fields: {sorted(allowed)}."
        )


def _validate_file_inventory(manifest: dict[str, Any], files: dict[str, Any]) -> dict[str, str]:
    profile_folders = {_safe_profile_folder(profile["folder"]) for profile in _profiles(manifest)}
    mapped_relatives = {_safe_relative(path) for path in manifest["file_map"].values()}
    normalized: dict[str, str] = {}
    for raw_path, raw_text in files.items():
        path = _safe_relative(raw_path)
        if not isinstance(raw_text, str):
            raise JsonXReferenceStoreError(f"JsonX reference file {path} must contain text.")
        matched = False
        for folder in profile_folders:
            prefix = f"{folder}/"
            if path.startswith(prefix) and path[len(prefix):] in mapped_relatives:
                matched = True
                break
        if not matched:
            raise JsonXReferenceStoreError(f"Unsupported JsonX bundle path: {path}.")
        normalized[path] = raw_text
    for profile in _profiles(manifest):
        for semantic_key in REQUIRED_FILE_KEYS:
            path = _file_path(manifest, profile, semantic_key)
            text = normalized.get(path, "")
            if not text.strip():
                raise JsonXReferenceStoreError(
                    f"Required JsonX model-facing block {path} is empty or missing."
                )
        preset_path = _file_path(manifest, profile, "presets_full")
        try:
            presets = json.loads(normalized[preset_path].lstrip("\ufeff"))
        except Exception as exc:
            raise JsonXReferenceStoreError(f"JsonX presets contain invalid JSON: {exc}") from exc
        if not isinstance(presets, dict) or not presets:
            raise JsonXReferenceStoreError("JsonX presets must contain a non-empty JSON object.")
        _validate_preset_catalog(presets)
        for key in TEMPLATE_REQUIREMENTS:
            _validate_template_tokens(key, normalized[_file_path(manifest, profile, key)])
        for key in ("template_fill_without_framing", "template_fill_with_framing"):
            hierarchy = _extract_json_object(
                normalized[_file_path(manifest, profile, key)], key
            )
            has_framing = "framing_and_placement" in hierarchy
            if has_framing != (key == "template_fill_with_framing"):
                raise JsonXReferenceStoreError(f"JsonX hierarchy template {key} has wrong framing state.")
        for key in USER_TEMPLATE_FIELDS:
            _validate_user_template(key, normalized[_file_path(manifest, profile, key)])
    return normalized


def validate_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise JsonXReferenceStoreError("JsonX reference bundle must be a JSON object.")
    if int(payload.get("jsonx_reference_schema_version") or 0) != JSONX_REFERENCE_SCHEMA_VERSION:
        raise JsonXReferenceStoreError(
            "Unified JsonX reference schema mismatch. Restart ComfyUI and hard-refresh the browser."
        )
    manifest = validate_manifest(copy.deepcopy(payload.get("manifest") or {}))
    files = payload.get("files")
    if not isinstance(files, dict):
        raise JsonXReferenceStoreError("JsonX reference bundle files must be an object.")
    return {
        "jsonx_reference_schema_version": JSONX_REFERENCE_SCHEMA_VERSION,
        "manifest": manifest,
        "files": _validate_file_inventory(manifest, files),
    }


def _bundle_from_root(root: Path) -> dict[str, Any]:
    manifest = _load_manifest(root)
    return {
        "jsonx_reference_schema_version": JSONX_REFERENCE_SCHEMA_VERSION,
        "manifest": manifest,
        "files": _markdown_files(root),
    }


def _write_bundle_tree(root: Path, bundle: dict[str, Any]) -> None:
    root.mkdir(parents=True, exist_ok=False)
    (root / MANIFEST_FILENAME).write_bytes(
        (json.dumps(bundle["manifest"], indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    )
    for relative, text in bundle["files"].items():
        _write_text(root.joinpath(*PurePosixPath(relative).parts), text)


def _replace_current(bundle: dict[str, Any]) -> None:
    validated = validate_bundle(bundle)
    token = uuid.uuid4().hex
    stage = REFERENCE_ROOT / f".JsonX.stage-{token}"
    rollback = REFERENCE_ROOT / f".JsonX.rollback-{token}"
    try:
        _write_bundle_tree(stage, validated)
        validate_bundle(_bundle_from_root(stage))
        CURRENT_ROOT.parent.mkdir(parents=True, exist_ok=True)
        if CURRENT_ROOT.exists():
            os.replace(CURRENT_ROOT, rollback)
        os.replace(stage, CURRENT_ROOT)
    except Exception:
        if not CURRENT_ROOT.exists() and rollback.exists():
            os.replace(rollback, CURRENT_ROOT)
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        if rollback.exists():
            shutil.rmtree(rollback, ignore_errors=True)


def _profile_files(bundle: dict[str, Any], profile: dict[str, Any]) -> dict[str, str]:
    prefix = f"{_safe_profile_folder(profile['folder'])}/"
    return {path: text for path, text in bundle["files"].items() if path.startswith(prefix)}


def bootstrap_current_use() -> None:
    original = validate_bundle(_bundle_from_root(ORIGINAL_ROOT))
    if not CURRENT_ROOT.exists():
        _replace_current(original)
        return
    try:
        current = validate_bundle(_bundle_from_root(CURRENT_ROOT))
    except (JsonXReferenceStoreError, OSError):
        raw_manifest = _read_json(CURRENT_ROOT / MANIFEST_FILENAME)
        raw_files = _markdown_files(CURRENT_ROOT)
        raw_profiles = [
            copy.deepcopy(profile)
            for profile in list(raw_manifest.get("profiles") or [])
            if isinstance(profile, dict)
        ]
        original_profiles = {
            str(profile["key"]): copy.deepcopy(profile)
            for profile in original["manifest"]["profiles"]
        }
        raw_by_key = {
            str(profile.get("key") or ""): profile
            for profile in raw_profiles
            if str(profile.get("key") or "")
        }
        merged_profiles: list[dict[str, Any]] = []
        for key, packaged in original_profiles.items():
            existing = raw_by_key.pop(key, None)
            merged = {**packaged, **copy.deepcopy(existing or {})}
            merged["key"] = key
            merged["folder"] = packaged["folder"]
            merged["builtin"] = True
            merged_profiles.append(merged)
        merged_profiles.extend(copy.deepcopy(profile) for profile in raw_by_key.values())
        current = {
            "jsonx_reference_schema_version": JSONX_REFERENCE_SCHEMA_VERSION,
            "manifest": {
                **copy.deepcopy(original["manifest"]),
                "schema_version": JSONX_REFERENCE_SCHEMA_VERSION,
                "file_map": copy.deepcopy(original["manifest"]["file_map"]),
                "profiles": merged_profiles,
            },
            "files": {},
        }
        old_map = dict(raw_manifest.get("file_map") or {})
        packaged_profile = original["manifest"]["profiles"][0]
        for profile in merged_profiles:
            folder = _safe_profile_folder(profile.get("folder"))
            for semantic_key in REQUIRED_FILE_KEYS:
                mapped = _safe_relative(current["manifest"]["file_map"][semantic_key])
                target = _safe_relative(f"{folder}/{mapped}")
                old_mapped = old_map.get(semantic_key)
                old_target = (
                    _safe_relative(f"{folder}/{_safe_relative(old_mapped)}")
                    if old_mapped
                    else target
                )
                text = raw_files.get(target)
                if text is None:
                    text = raw_files.get(old_target)
                if text is None:
                    source_path = _file_path(original["manifest"], packaged_profile, semantic_key)
                    text = original["files"][source_path]
                current["files"][target] = text
        current = validate_bundle(current)
        _replace_current(current)
        return
    changed = False
    current_profiles = {str(profile["key"]): profile for profile in current["manifest"]["profiles"]}
    for profile in original["manifest"]["profiles"]:
        if str(profile["key"]) not in current_profiles:
            current["manifest"]["profiles"].append(copy.deepcopy(profile))
            changed = True
    for key, value in original["manifest"]["file_map"].items():
        if key not in current["manifest"]["file_map"]:
            current["manifest"]["file_map"][key] = value
            changed = True
    for path, text in original["files"].items():
        if path not in current["files"]:
            current["files"][path] = text
            changed = True
    if changed:
        _replace_current(current)


def current_bundle() -> dict[str, Any]:
    bootstrap_current_use()
    return validate_bundle(_bundle_from_root(CURRENT_ROOT))


def original_bundle() -> dict[str, Any]:
    return validate_bundle(_bundle_from_root(ORIGINAL_ROOT))


def save_current_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    bundle = validate_bundle(payload)
    original = original_bundle()
    original_by_key = {str(profile["key"]): profile for profile in original["manifest"]["profiles"]}
    submitted = {str(profile["key"]): profile for profile in bundle["manifest"]["profiles"]}
    missing = sorted(set(original_by_key) - set(submitted))
    if missing:
        raise JsonXReferenceStoreError(
            f"Built-in JsonX profiles cannot be deleted: {', '.join(missing)}."
        )
    original_folders = {_safe_profile_folder(profile["folder"]): key for key, profile in original_by_key.items()}
    for profile in bundle["manifest"]["profiles"]:
        key = str(profile["key"])
        if key in original_by_key:
            profile["builtin"] = True
            profile["folder"] = original_by_key[key]["folder"]
        elif _safe_profile_folder(profile["folder"]) in original_folders:
            raise JsonXReferenceStoreError(
                f"Custom JsonX profile {key} cannot use a built-in folder."
            )
    _replace_current(bundle)
    return current_bundle()


def reset_profile(profile_key: str) -> dict[str, Any]:
    current = current_bundle()
    original = original_bundle()
    source = copy.deepcopy(_profile_by_key(original["manifest"], profile_key))
    key = str(source["key"])
    current["manifest"]["profiles"] = [
        source if str(profile["key"]) == key else profile
        for profile in current["manifest"]["profiles"]
    ]
    folder = _safe_profile_folder(source["folder"])
    current["files"] = {
        path: text for path, text in current["files"].items() if not path.startswith(f"{folder}/")
    }
    current["files"].update(_profile_files(original, source))
    _replace_current(current)
    return current_bundle()


def reset_all() -> dict[str, Any]:
    current = current_bundle()
    original = original_bundle()
    builtin_keys = {str(profile["key"]) for profile in original["manifest"]["profiles"]}
    custom_profiles = [
        copy.deepcopy(profile)
        for profile in current["manifest"]["profiles"]
        if str(profile["key"]) not in builtin_keys
    ]
    restored = copy.deepcopy(original)
    restored["manifest"]["profiles"].extend(custom_profiles)
    for profile in custom_profiles:
        restored["files"].update(_profile_files(current, profile))
    _replace_current(restored)
    return current_bundle()


def profile_metadata(profile_key: str) -> dict[str, Any]:
    return copy.deepcopy(_profile_by_key(current_bundle()["manifest"], profile_key))


def jsonx_profiles() -> list[dict[str, Any]]:
    return copy.deepcopy(current_bundle()["manifest"]["profiles"])


def block(profile_key: str, semantic_key: str, bundle: dict[str, Any] | None = None) -> tuple[str, str]:
    source = bundle or current_bundle()
    profile = _profile_by_key(source["manifest"], profile_key)
    path = _file_path(source["manifest"], profile, semantic_key)
    text = source["files"].get(path, "")
    if not text.strip():
        raise JsonXReferenceStoreError(f"Required JsonX block {path} is empty or missing.")
    return path, text


def preset_text(profile_key: str, bundle: dict[str, Any] | None = None) -> str:
    return block(profile_key, "presets_full", bundle)[1]


def presets(profile_key: str, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        value = json.loads(preset_text(profile_key, bundle).lstrip("\ufeff"))
    except Exception as exc:
        raise JsonXReferenceStoreError(f"JsonX presets contain invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise JsonXReferenceStoreError("JsonX presets must contain a JSON object.")
    return value


def render_template(
    profile_key: str,
    semantic_key: str,
    replacements: dict[str, str],
    bundle: dict[str, Any] | None = None,
) -> tuple[str, str]:
    path, text = block(profile_key, semantic_key, bundle)
    _validate_template_tokens(semantic_key, text)
    expected = TEMPLATE_REQUIREMENTS[semantic_key]
    if set(replacements) != expected:
        raise JsonXReferenceStoreError(
            f"JsonX template {semantic_key} replacement mismatch."
        )
    rendered = text
    for key, value in replacements.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
    if TEMPLATE_TOKEN_PATTERN.search(rendered):
        raise JsonXReferenceStoreError(f"JsonX template {semantic_key} has unresolved tokens.")
    return path, rendered


def hierarchy_template(
    profile_key: str,
    framing_enabled: bool,
    bundle: dict[str, Any] | None = None,
) -> tuple[str, str, dict[str, Any]]:
    key = "template_fill_with_framing" if framing_enabled else "template_fill_without_framing"
    path, text = block(profile_key, key, bundle)
    return path, text, _extract_json_object(text, key)


def render_user_template(
    profile_key: str,
    semantic_key: str,
    *,
    bundle: dict[str, Any] | None = None,
    **values: str,
) -> tuple[str, str]:
    path, template = block(profile_key, semantic_key, bundle)
    _validate_user_template(semantic_key, template)
    try:
        return path, template.format(**values)
    except (KeyError, ValueError) as exc:
        raise JsonXReferenceStoreError(
            f"Invalid JsonX user-message template {semantic_key}: {exc}"
        ) from exc


def shared_nsfw_image() -> tuple[str, str]:
    path = REFERENCE_ROOT / "current_use" / "nsfw-image.md"
    if not path.exists():
        path = REFERENCE_ROOT / "original" / "nsfw-image.md"
    text = _read_text(path) if path.exists() else ""
    if not text.strip():
        raise JsonXReferenceStoreError("Required shared nsfw-image.md is empty or missing.")
    return "nsfw-image.md", text
