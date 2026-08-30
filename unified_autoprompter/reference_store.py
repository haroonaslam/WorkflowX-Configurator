from __future__ import annotations

import copy
import json
import os
import re
import shutil
import uuid
from pathlib import Path, PurePosixPath
from typing import Any


REFERENCE_SCHEMA_VERSION = 1
REFERENCE_ROOT = Path(__file__).with_name("reference")
ORIGINAL_ROOT = REFERENCE_ROOT / "original"
CURRENT_ROOT = REFERENCE_ROOT / "current_use"
MANIFEST_FILENAME = "manifest.json"
JSONX_SUBTREE = "JsonX"
NSFW_FILENAMES = {"image": "nsfw-image.md", "video": "nsfw-video.md"}
SUPPORTING_FILENAMES = {
    "with_reference_supported": "with_reference_supported.md",
    "without_reference_supported": "without_reference_supported.md",
    "without_reference_unsupported": "without_reference_unsupported.md",
}
FORMAT_KEYS = ("natural", "json", "tags")
KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]*$")


class ReferenceStoreError(ValueError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes().decode("utf-8"))
    except Exception as exc:
        raise ReferenceStoreError(f"Could not read {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReferenceStoreError(f"{path.name} must contain a JSON object.")
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
        raise ReferenceStoreError(f"Unsafe reference path: {raw!r}.")
    return path.as_posix()


def _safe_folder(value: object) -> str:
    folder = _safe_relative(value)
    if "/" in folder or folder in {"original", "current_use"}:
        raise ReferenceStoreError(f"Profile folder must be one safe directory name: {folder!r}.")
    return folder


def _manifest_profiles(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    profiles = manifest.get("profiles")
    if not isinstance(profiles, list):
        raise ReferenceStoreError("Reference manifest profiles must be an array.")
    return profiles


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    if int(manifest.get("schema_version") or 0) != REFERENCE_SCHEMA_VERSION:
        raise ReferenceStoreError(
            "Unified PrompterX reference schema mismatch. Restart ComfyUI and hard-refresh the browser."
        )
    generation_types = manifest.get("generation_types")
    formats = manifest.get("formats")
    if not isinstance(generation_types, dict) or not generation_types:
        raise ReferenceStoreError("Reference manifest needs generation-type mappings.")
    if not isinstance(formats, dict) or not formats:
        raise ReferenceStoreError("Reference manifest needs output-format mappings.")
    seen_keys: set[str] = set()
    seen_folders: set[str] = set()
    for profile in _manifest_profiles(manifest):
        if not isinstance(profile, dict):
            raise ReferenceStoreError("Every reference profile must be an object.")
        key = str(profile.get("key") or "").strip()
        if not KEY_PATTERN.fullmatch(key) or key in seen_keys:
            raise ReferenceStoreError(f"Invalid or duplicate profile key: {key!r}.")
        seen_keys.add(key)
        folder = _safe_folder(profile.get("folder"))
        if folder in seen_folders:
            raise ReferenceStoreError(f"Duplicate profile folder: {folder!r}.")
        seen_folders.add(folder)
        if str(profile.get("media_type") or "") not in {"image", "video"}:
            raise ReferenceStoreError(f"Profile {key} has an invalid media type.")
        enabled_formats = profile.get("enabled_formats")
        if not isinstance(enabled_formats, list) or not enabled_formats:
            raise ReferenceStoreError(f"Profile {key} needs at least one enabled format.")
        if any(str(item) not in formats for item in enabled_formats):
            raise ReferenceStoreError(f"Profile {key} enables an unknown output format.")
        if str(profile.get("default_format") or "") not in enabled_formats:
            raise ReferenceStoreError(f"Profile {key} default format must be enabled.")
        enabled_types = profile.get("enabled_generation_types")
        if not isinstance(enabled_types, list) or not enabled_types:
            raise ReferenceStoreError(f"Profile {key} needs at least one generation type.")
        if any(str(item) not in generation_types for item in enabled_types):
            raise ReferenceStoreError(f"Profile {key} enables an unknown generation type.")
        if str(profile.get("default_generation_type") or "") not in enabled_types:
            raise ReferenceStoreError(f"Profile {key} default generation type must be enabled.")
    return manifest


def _load_manifest(root: Path) -> dict[str, Any]:
    return validate_manifest(_read_json(root / MANIFEST_FILENAME))


def _markdown_files(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    if not root.exists():
        return files
    for path in sorted(root.rglob("*.md"), key=lambda item: item.as_posix().lower()):
        relative = path.relative_to(root).as_posix()
        if PurePosixPath(relative).parts[0] == JSONX_SUBTREE:
            continue
        files[relative] = _read_text(path)
    return files


def _profile_by_key(manifest: dict[str, Any], key: str) -> dict[str, Any]:
    normalized = str(key or "").strip()
    for profile in _manifest_profiles(manifest):
        if str(profile.get("key") or "") == normalized:
            return profile
    raise ReferenceStoreError(f"Unknown standard Unified PrompterX profile: {normalized}.")


def _profile_files(files: dict[str, str], folder: str) -> dict[str, str]:
    prefix = f"{folder}/"
    return {path: text for path, text in files.items() if path.startswith(prefix)}


def _validate_file_inventory(manifest: dict[str, Any], files: dict[str, Any]) -> dict[str, str]:
    folders = {_safe_folder(item.get("folder")) for item in _manifest_profiles(manifest)}
    normalized: dict[str, str] = {}
    for raw_path, raw_text in files.items():
        path = _safe_relative(raw_path)
        parts = PurePosixPath(path).parts
        is_nsfw = path in set(NSFW_FILENAMES.values())
        is_profile_markdown = (
            len(parts) == 3
            and parts[0] in folders
            and parts[1] in {"split", "Supporting"}
            and parts[2].endswith(".md")
        )
        if not is_nsfw and not is_profile_markdown:
            raise ReferenceStoreError(f"Unsupported reference bundle path: {path}.")
        if not isinstance(raw_text, str):
            raise ReferenceStoreError(f"Reference file {path} must contain text.")
        normalized[path] = raw_text
    for filename in NSFW_FILENAMES.values():
        if not normalized.get(filename, "").strip():
            raise ReferenceStoreError(f"Required global block {filename} is empty or missing.")
    generation_types = manifest["generation_types"]
    formats = manifest["formats"]
    for profile in _manifest_profiles(manifest):
        folder = _safe_folder(profile["folder"])
        required = [
            f"{folder}/split/common.md",
            f"{folder}/Supporting/with_reference_supported.md",
            f"{folder}/Supporting/without_reference_supported.md",
            f"{folder}/Supporting/without_reference_unsupported.md",
        ]
        for path in required:
            if not normalized.get(path, "").strip():
                raise ReferenceStoreError(f"Required model-facing block {path} is empty or missing.")
        negative_states = [False, True] if bool(profile.get("negative_supported")) else [False]
        for format_key in profile["enabled_formats"]:
            prefix = str(formats[format_key].get("contract_prefix") or "").strip()
            if not prefix:
                raise ReferenceStoreError(f"Format {format_key} has no output-contract mapping.")
            for negative in negative_states:
                suffix = "with_negative" if negative else "without_negative"
                path = f"{folder}/Supporting/{prefix}_{suffix}.md"
                if not normalized.get(path, "").strip():
                    raise ReferenceStoreError(f"Enabled output contract {path} is empty or missing.")
        for type_key in profile["enabled_generation_types"]:
            mapping = generation_types[type_key]
            if not str(mapping.get("filename") or "").strip():
                raise ReferenceStoreError(f"Generation type {type_key} has no filename mapping.")
            # Generation-path files are deliberately optional. Missing files are
            # exposed as blank editors and created by the next save.
    return normalized


def validate_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ReferenceStoreError("Reference bundle must be a JSON object.")
    if int(payload.get("reference_schema_version") or 0) != REFERENCE_SCHEMA_VERSION:
        raise ReferenceStoreError(
            "Unified PrompterX reference schema mismatch. Restart ComfyUI and hard-refresh the browser."
        )
    manifest = validate_manifest(copy.deepcopy(payload.get("manifest") or {}))
    files = payload.get("files")
    if not isinstance(files, dict):
        raise ReferenceStoreError("Reference bundle files must be an object.")
    normalized_files = _validate_file_inventory(manifest, files)
    for profile in _manifest_profiles(manifest):
        folder = _safe_folder(profile["folder"])
        for type_key in profile["enabled_generation_types"]:
            filename = str(manifest["generation_types"][type_key]["filename"])
            normalized_files.setdefault(f"{folder}/split/{filename}", "")
    return {
        "reference_schema_version": REFERENCE_SCHEMA_VERSION,
        "manifest": manifest,
        "files": normalized_files,
    }


def _bundle_from_root(root: Path) -> dict[str, Any]:
    manifest = _load_manifest(root)
    return {
        "reference_schema_version": REFERENCE_SCHEMA_VERSION,
        "manifest": manifest,
        "files": _markdown_files(root),
    }


def _write_bundle_tree(root: Path, bundle: dict[str, Any]) -> None:
    root.mkdir(parents=True, exist_ok=False)
    manifest_bytes = (json.dumps(bundle["manifest"], indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    (root / MANIFEST_FILENAME).write_bytes(manifest_bytes)
    for relative, text in bundle["files"].items():
        destination = root.joinpath(*PurePosixPath(relative).parts)
        _write_text(destination, text)


def _replace_current(bundle: dict[str, Any]) -> None:
    validated = validate_bundle(bundle)
    token = uuid.uuid4().hex
    stage = REFERENCE_ROOT / f".current_use.stage-{token}"
    rollback = REFERENCE_ROOT / f".current_use.rollback-{token}"
    try:
        _write_bundle_tree(stage, validated)
        # Unified JsonX deliberately shares the top-level reference root while
        # owning an independently validated and transactionally written
        # subtree. Standard profile saves and resets must preserve it exactly.
        jsonx_source = CURRENT_ROOT / JSONX_SUBTREE
        if not jsonx_source.exists():
            jsonx_source = ORIGINAL_ROOT / JSONX_SUBTREE
        if jsonx_source.exists():
            shutil.copytree(jsonx_source, stage / JSONX_SUBTREE)
        validate_bundle(_bundle_from_root(stage))
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


def bootstrap_current_use() -> None:
    original = _bundle_from_root(ORIGINAL_ROOT)
    if not CURRENT_ROOT.exists():
        _replace_current(original)
        return
    current = _bundle_from_root(CURRENT_ROOT)
    changed = False
    current_profiles = {
        str(profile.get("key") or ""): profile for profile in current["manifest"]["profiles"]
    }
    for profile in original["manifest"]["profiles"]:
        key = str(profile.get("key") or "")
        if key not in current_profiles:
            current["manifest"]["profiles"].append(copy.deepcopy(profile))
            changed = True
    for metadata_key in ("generation_types", "formats", "nsfw_files"):
        source = original["manifest"].get(metadata_key) or {}
        target = current["manifest"].setdefault(metadata_key, {})
        for key, value in source.items():
            if key not in target:
                target[key] = copy.deepcopy(value)
                changed = True
    for path, text in original["files"].items():
        if path not in current["files"]:
            current["files"][path] = text
            changed = True
    if changed:
        _replace_current(current)


def current_bundle() -> dict[str, Any]:
    bootstrap_current_use()
    return _bundle_from_root(CURRENT_ROOT)


def original_bundle() -> dict[str, Any]:
    return _bundle_from_root(ORIGINAL_ROOT)


def save_current_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    bundle = validate_bundle(payload)
    original = original_bundle()
    original_by_key = {
        str(profile.get("key") or ""): profile for profile in original["manifest"]["profiles"]
    }
    submitted_by_key = {
        str(profile.get("key") or ""): profile for profile in bundle["manifest"]["profiles"]
    }
    missing_builtins = sorted(set(original_by_key) - set(submitted_by_key))
    if missing_builtins:
        raise ReferenceStoreError(
            f"Built-in profiles cannot be deleted: {', '.join(missing_builtins)}."
        )
    original_folder_owners = {
        _safe_folder(profile["folder"]): key for key, profile in original_by_key.items()
    }
    for profile in bundle["manifest"]["profiles"]:
        key = str(profile.get("key") or "")
        original_profile = original_by_key.get(key)
        if original_profile:
            profile["builtin"] = True
            profile["folder"] = original_profile["folder"]
        else:
            folder = _safe_folder(profile.get("folder"))
            if folder in original_folder_owners:
                raise ReferenceStoreError(
                    f"Custom profile {key} cannot use built-in folder {folder!r}."
                )
    _replace_current(bundle)
    return current_bundle()


def reset_profile(profile_key: str) -> dict[str, Any]:
    current = current_bundle()
    original = original_bundle()
    original_profile = copy.deepcopy(_profile_by_key(original["manifest"], profile_key))
    key = str(original_profile["key"])
    replaced = False
    for index, profile in enumerate(current["manifest"]["profiles"]):
        if str(profile.get("key") or "") == key:
            current["manifest"]["profiles"][index] = original_profile
            replaced = True
            break
    if not replaced:
        current["manifest"]["profiles"].append(original_profile)
    folder = _safe_folder(original_profile["folder"])
    prefix = f"{folder}/"
    current["files"] = {
        path: text for path, text in current["files"].items() if not path.startswith(prefix)
    }
    current["files"].update(_profile_files(original["files"], folder))
    _replace_current(current)
    return current_bundle()


def reset_all() -> dict[str, Any]:
    current = current_bundle()
    original = original_bundle()
    builtin_keys = {str(profile.get("key") or "") for profile in original["manifest"]["profiles"]}
    custom_profiles = [
        copy.deepcopy(profile)
        for profile in current["manifest"]["profiles"]
        if str(profile.get("key") or "") not in builtin_keys
    ]
    restored = copy.deepcopy(original)
    restored["manifest"]["profiles"].extend(custom_profiles)
    for profile in custom_profiles:
        restored["files"].update(
            _profile_files(current["files"], _safe_folder(profile.get("folder")))
        )
    _replace_current(restored)
    return current_bundle()


def profile_metadata(profile_key: str) -> dict[str, Any]:
    return copy.deepcopy(_profile_by_key(current_bundle()["manifest"], profile_key))


def standard_profiles() -> list[dict[str, Any]]:
    return copy.deepcopy(current_bundle()["manifest"]["profiles"])


def generation_catalog() -> dict[str, dict[str, Any]]:
    return copy.deepcopy(current_bundle()["manifest"]["generation_types"])


def format_catalog() -> dict[str, dict[str, Any]]:
    return copy.deepcopy(current_bundle()["manifest"]["formats"])


def resolve_profile_file(profile_key: str, relative: str) -> tuple[str, str]:
    bundle = current_bundle()
    profile = _profile_by_key(bundle["manifest"], profile_key)
    folder = _safe_folder(profile["folder"])
    path = _safe_relative(f"{folder}/{relative}")
    return path, bundle["files"].get(path, "")


def resolve_global_file(filename: str) -> tuple[str, str]:
    path = _safe_relative(filename)
    if path not in set(NSFW_FILENAMES.values()):
        raise ReferenceStoreError(f"Unknown global reference block: {path}.")
    bundle = current_bundle()
    return path, bundle["files"].get(path, "")


def path_filename(generation_type: str) -> str:
    catalog = generation_catalog()
    try:
        return str(catalog[generation_type]["filename"])
    except KeyError as exc:
        raise ReferenceStoreError(f"Unknown generation type: {generation_type}.") from exc


def output_medium(generation_type: str) -> str:
    catalog = generation_catalog()
    try:
        return str(catalog[generation_type]["output_medium"])
    except KeyError as exc:
        raise ReferenceStoreError(f"Unknown generation type: {generation_type}.") from exc


def reference_supported(generation_type: str) -> bool:
    catalog = generation_catalog()
    try:
        return bool(catalog[generation_type]["reference_supported"])
    except KeyError as exc:
        raise ReferenceStoreError(f"Unknown generation type: {generation_type}.") from exc


def reference_filename(generation_type: str, has_media: bool) -> str:
    if reference_supported(generation_type):
        return (
            SUPPORTING_FILENAMES["with_reference_supported"]
            if has_media
            else SUPPORTING_FILENAMES["without_reference_supported"]
        )
    return SUPPORTING_FILENAMES["without_reference_unsupported"]


def output_contract_filename(prompt_format: str, negative_enabled: bool) -> str:
    formats = format_catalog()
    if prompt_format not in formats:
        raise ReferenceStoreError(f"Unknown output format: {prompt_format}.")
    prefix = str(formats[prompt_format].get("contract_prefix") or "").strip()
    suffix = "with_negative" if negative_enabled else "without_negative"
    return f"{prefix}_{suffix}.md"


def selected_markdown_blocks(
    profile_key: str,
    generation_type: str,
    prompt_format: str,
    negative_enabled: bool,
    nsfw_enabled: bool,
    has_media: bool,
) -> list[tuple[str, str, str, bool]]:
    """Resolve one standard request from a single fresh current-use snapshot.

    Returned tuples are ``(kind, relative_path, exact_text, required)``.
    """

    bundle = current_bundle()
    manifest = bundle["manifest"]
    files = bundle["files"]
    profile = _profile_by_key(manifest, profile_key)
    if generation_type not in profile["enabled_generation_types"]:
        raise ReferenceStoreError(
            f"Generation type '{generation_type}' is not supported by {profile.get('label') or profile_key}."
        )
    if prompt_format not in profile["enabled_formats"]:
        raise ReferenceStoreError(
            f"Output format '{prompt_format}' is not supported by {profile.get('label') or profile_key}."
        )
    folder = _safe_folder(profile["folder"])
    generation = manifest["generation_types"][generation_type]
    blocks: list[tuple[str, str, str, bool]] = []

    def append(kind: str, path: str, required: bool) -> None:
        safe_path = _safe_relative(path)
        blocks.append((kind, safe_path, files.get(safe_path, ""), required))

    append("common", f"{folder}/split/common.md", True)
    append("generation_type", f"{folder}/split/{generation['filename']}", False)
    if nsfw_enabled:
        append("nsfw", manifest["nsfw_files"][generation["output_medium"]], True)
    if generation["reference_supported"]:
        reference_file = (
            SUPPORTING_FILENAMES["with_reference_supported"]
            if has_media
            else SUPPORTING_FILENAMES["without_reference_supported"]
        )
    else:
        reference_file = SUPPORTING_FILENAMES["without_reference_unsupported"]
    append("reference_usage", f"{folder}/Supporting/{reference_file}", True)
    prefix = str(manifest["formats"][prompt_format]["contract_prefix"])
    suffix = "with_negative" if negative_enabled else "without_negative"
    append("output_contract", f"{folder}/Supporting/{prefix}_{suffix}.md", True)
    return blocks
