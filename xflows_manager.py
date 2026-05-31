import copy
import base64
import hashlib
import io
import json
import os
import re
import shutil
import time
import uuid
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from aiohttp import web

import folder_paths
from server import PromptServer


NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

ROUTE_PREFIX = "/xflows"
METADATA_VERSION = 1
IGNORED_WORKFLOW_NAMES = {".index.json"}
EXPORT_FILE_NAMES = {
    "workflows": "workflowx_workflows.zip",
    "metadata": "workflowx_xflows_metadata.json",
    "prompts": "workflowx_xprompts.json",
    "presets": "workflowx_presets.json",
    "node_snips": "workflowx_xnodes.json",
    "manifest": "workflowx_manifest.json",
}
MODEL_EXTENSIONS = {".ckpt", ".pt", ".pt2", ".bin", ".pth", ".safetensors", ".pkl", ".sft", ".gguf"}
EXTRA_MODEL_FOLDERS = (
    "TTS",
    "LLM",
    "ipadapter",
    "instantid",
    "inpaint",
    "pulid",
    "reactor",
    "animatediff_models",
    "video_models",
)
MODEL_FOLDER_ALLOWLIST = {
    "checkpoints",
    "loras",
    "vae",
    "text_encoders",
    "diffusion_models",
    "clip_vision",
    "style_models",
    "embeddings",
    "diffusers",
    "vae_approx",
    "controlnet",
    "gligen",
    "upscale_models",
    "latent_upscale_models",
    "hypernetworks",
    "photomaker",
    "model_patches",
    "audio_encoders",
    "background_removal",
    "frame_interpolation",
    "geometry_estimation",
    "optical_flow",
    "detection",
}
VIEW_ONLY_KEYS = {
    "pos",
    "size",
    "flags",
    "order",
    "color",
    "bgcolor",
    "selected",
    "collapsed",
    "pinned",
}


def _user_root() -> Path:
    return Path(folder_paths.get_user_directory()) / "default"


def _workflow_root() -> Path:
    return _user_root() / "workflows"


def _manager_root() -> Path:
    return _user_root() / "xflows_manager"


def _metadata_path() -> Path:
    return _manager_root() / "metadata.json"


def _trash_root() -> Path:
    return _manager_root() / "trash"


def _prompt_library_path() -> Path:
    return _manager_root() / "prompt_library.json"


def _preset_snippets_path() -> Path:
    return _manager_root() / "preset_snippets.json"


def _node_snips_path() -> Path:
    return _manager_root() / "node_snips.json"


def _legacy_manager_root() -> Path:
    return _user_root() / "workflow_manager"


def _legacy_metadata_path() -> Path:
    return _legacy_manager_root() / "metadata.json"


def _migrate_legacy_metadata() -> None:
    target = _metadata_path()
    legacy = _legacy_metadata_path()
    if target.exists() or not legacy.exists():
        return
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy, target)
    except Exception:
        pass


def _now_ms() -> int:
    return int(time.time() * 1000)


def _normalize_slashes(value: str) -> str:
    return value.replace("\\", "/")


def _normalize_token(value: str) -> str:
    value = _normalize_slashes(value).lower()
    value = os.path.splitext(value)[0]
    value = re.sub(r"[^a-z0-9]+", "", value)
    return value


def _clean_tag(value: str) -> str:
    value = _normalize_slashes(str(value)).strip()
    base = os.path.basename(value) or value
    suffix = Path(base).suffix.lower()
    if suffix in MODEL_EXTENSIONS or suffix == ".json":
        value = Path(base).stem
    else:
        value = base
    value = re.sub(r"\s+", " ", value)
    return value[:72]


def _tag_map(values) -> dict[str, str]:
    if not isinstance(values, list):
        return {}
    tags = {}
    for value in values:
        tag = _clean_tag(value)
        if tag:
            tags[tag.lower()] = tag
    return tags


def _merged_tag_fields(record: dict, auto_tags: list[str]) -> tuple[list[str], list[str], list[str]]:
    auto_by_key = _tag_map(auto_tags)
    manual_by_key = _tag_map(record.get("manual_tags"))
    hidden_by_key = _tag_map(record.get("hidden_auto_tags"))

    hidden_by_key = {
        key: auto_by_key[key]
        for key in hidden_by_key
        if key in auto_by_key and key not in manual_by_key
    }
    visible_auto = [
        tag
        for key, tag in auto_by_key.items()
        if key not in hidden_by_key
    ]
    manual_tags = sorted(manual_by_key.values(), key=str.lower)
    hidden_auto_tags = sorted(hidden_by_key.values(), key=str.lower)
    all_tags = sorted({*visible_auto, *manual_tags}, key=str.lower)
    return manual_tags, hidden_auto_tags, all_tags


def _json_response(data, status: int = 200):
    return web.json_response(data, status=status, dumps=lambda value: json.dumps(value, ensure_ascii=False))


def _load_metadata() -> dict:
    _migrate_legacy_metadata()
    path = _metadata_path()
    if not path.exists():
        return {"version": METADATA_VERSION, "workflows": {}}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        backup = path.with_suffix(f".broken-{int(time.time())}.json")
        try:
            shutil.copy2(path, backup)
        except Exception:
            pass
        return {"version": METADATA_VERSION, "workflows": {}}

    if not isinstance(data, dict):
        data = {}
    workflows = data.get("workflows")
    if not isinstance(workflows, dict):
        workflows = {}
    return {"version": METADATA_VERSION, "workflows": workflows}


def _save_metadata(data: dict) -> None:
    root = _manager_root()
    root.mkdir(parents=True, exist_ok=True)
    data["version"] = METADATA_VERSION
    tmp = _metadata_path().with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, _metadata_path())


def _library_path(name: str) -> Path:
    paths = {
        "prompts": _prompt_library_path(),
        "presets": _preset_snippets_path(),
        "node_snips": _node_snips_path(),
    }
    if name not in paths:
        raise ValueError("unknown library")
    return paths[name]


def _default_library(name: str) -> dict:
    if name == "prompts":
        return {"version": METADATA_VERSION, "prompts": []}
    if name == "presets":
        return {"version": METADATA_VERSION, "categories": []}
    if name == "node_snips":
        return {"version": METADATA_VERSION, "snips": []}
    raise ValueError("unknown library")


def _load_library(name: str) -> dict:
    path = _library_path(name)
    if not path.exists():
        return _default_library(name)
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        backup = path.with_suffix(f".broken-{int(time.time())}.json")
        try:
            shutil.copy2(path, backup)
        except Exception:
            pass
        return _default_library(name)
    if not isinstance(data, dict):
        data = {}
    default = _default_library(name)
    if name == "prompts" and not isinstance(data.get("prompts"), list):
        data["prompts"] = []
    if name == "presets" and not isinstance(data.get("categories"), list):
        data["categories"] = []
    if name == "node_snips" and not isinstance(data.get("snips"), list):
        data["snips"] = []
    data["version"] = METADATA_VERSION
    for key, value in default.items():
        data.setdefault(key, value)
    return data


def _save_library(name: str, data: dict) -> None:
    root = _manager_root()
    root.mkdir(parents=True, exist_ok=True)
    data["version"] = METADATA_VERSION
    path = _library_path(name)
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, path)


def _json_bytes(data: dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def _file_payload(name: str, data: bytes, mime: str) -> dict:
    return {
        "name": name,
        "mime": mime,
        "encoding": "base64",
        "size": len(data),
        "content": base64.b64encode(data).decode("ascii"),
    }


def _workflow_rel(path: Path) -> str:
    return _normalize_slashes(str(path.relative_to(_workflow_root())))


def _exportable_workflows() -> list[Path]:
    return [path for path in _walk_workflows() if path.name not in IGNORED_WORKFLOW_NAMES]


def _export_manifest() -> dict:
    prompts = _load_library("prompts").get("prompts", [])
    presets = _load_library("presets").get("categories", [])
    node_snips = _load_library("node_snips").get("snips", [])
    workflows = _exportable_workflows()
    return {
        "version": METADATA_VERSION,
        "generated_at": _now_ms(),
        "files": EXPORT_FILE_NAMES,
        "counts": {
            "workflows": len(workflows),
            "metadata_records": len(_load_metadata().get("workflows", {})),
            "prompts": len(prompts),
            "preset_categories": len(presets),
            "preset_snippets": sum(len(category.get("snippets", [])) for category in presets if isinstance(category, dict)),
            "node_snips": len(node_snips),
        },
        "roots": {
            "workflows": str(_workflow_root()),
            "manager": str(_manager_root()),
        },
    }


def _workflows_zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in _exportable_workflows():
            archive.write(path, _workflow_rel(path))
    return buffer.getvalue()


def _selected_parts(value) -> set[str]:
    allowed = {"workflows", "metadata", "prompts", "presets", "node_snips"}
    if isinstance(value, dict):
        selected = {key for key, enabled in value.items() if enabled}
    elif isinstance(value, list):
        selected = {str(item) for item in value}
    else:
        selected = set()
    return selected & allowed


def _export_files(selected: set[str]) -> list[dict]:
    files = [_file_payload(EXPORT_FILE_NAMES["manifest"], _json_bytes(_export_manifest()), "application/json")]
    if "workflows" in selected:
        files.append(_file_payload(EXPORT_FILE_NAMES["workflows"], _workflows_zip_bytes(), "application/zip"))
    if "metadata" in selected:
        files.append(_file_payload(EXPORT_FILE_NAMES["metadata"], _json_bytes(_load_metadata()), "application/json"))
    if "prompts" in selected:
        files.append(_file_payload(EXPORT_FILE_NAMES["prompts"], _json_bytes(_load_library("prompts")), "application/json"))
    if "presets" in selected:
        files.append(_file_payload(EXPORT_FILE_NAMES["presets"], _json_bytes(_load_library("presets")), "application/json"))
    if "node_snips" in selected:
        files.append(_file_payload(EXPORT_FILE_NAMES["node_snips"], _json_bytes(_load_library("node_snips")), "application/json"))
    return files


def _decode_import_files(files) -> dict[str, bytes]:
    if not isinstance(files, list):
        raise ValueError("files must be a list")
    decoded = {}
    for file in files:
        if not isinstance(file, dict):
            continue
        name = Path(str(file.get("name") or "")).name
        if name not in EXPORT_FILE_NAMES.values():
            continue
        content = file.get("content")
        if not isinstance(content, str):
            raise ValueError(f"{name} is missing file content")
        try:
            decoded[name] = base64.b64decode(content, validate=True)
        except Exception as exc:
            raise ValueError(f"{name} is not valid base64") from exc
    return decoded


def _parse_import_json(files: dict[str, bytes], part: str) -> dict | None:
    name = EXPORT_FILE_NAMES[part]
    if name not in files:
        return None
    try:
        data = json.loads(files[name].decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"{name} is not valid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{name} must contain a JSON object")
    return data


def _validate_metadata_import(data: dict) -> dict:
    if not isinstance(data.get("workflows"), dict):
        raise ValueError("workflow metadata must contain a workflows object")
    data = copy.deepcopy(data)
    data["version"] = METADATA_VERSION
    return data


def _validate_library_import(data: dict, name: str) -> dict:
    data = copy.deepcopy(data)
    if name == "prompts" and not isinstance(data.get("prompts"), list):
        raise ValueError("XPrompts import must contain a prompts array")
    if name == "presets" and not isinstance(data.get("categories"), list):
        raise ValueError("Presets import must contain a categories array")
    if name == "node_snips" and not isinstance(data.get("snips"), list):
        raise ValueError("XNodes import must contain a snips array")
    data["version"] = METADATA_VERSION
    return data


def _safe_import_workflow_path(name: str) -> str | None:
    normalized = _normalize_slashes(name.strip())
    if not normalized or normalized.endswith("/"):
        return None
    path = Path(normalized)
    if path.is_absolute() or path.drive:
        raise ValueError(f"unsafe workflow path in zip: {name}")
    parts = path.parts
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError(f"unsafe workflow path in zip: {name}")
    if path.name in IGNORED_WORKFLOW_NAMES:
        return None
    if path.suffix.lower() != ".json":
        return None
    return _normalize_slashes(str(path))


def _validate_workflow_zip(data: bytes) -> list[dict]:
    entries = []
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
            for info in archive.infolist():
                rel = _safe_import_workflow_path(info.filename)
                if rel is None:
                    continue
                entries.append({"path": rel, "data": archive.read(info)})
    except zipfile.BadZipFile as exc:
        raise ValueError("workflowx_workflows.zip is not a valid zip file") from exc
    return entries


def _validate_import_bundle(files: dict[str, bytes], selected: set[str]) -> dict:
    bundle = {}
    if "workflows" in selected:
        zip_name = EXPORT_FILE_NAMES["workflows"]
        if zip_name not in files:
            raise ValueError(f"{zip_name} is required")
        bundle["workflows"] = _validate_workflow_zip(files[zip_name])
    if "metadata" in selected:
        data = _parse_import_json(files, "metadata")
        if data is None:
            raise ValueError(f"{EXPORT_FILE_NAMES['metadata']} is required")
        bundle["metadata"] = _validate_metadata_import(data)
    if "prompts" in selected:
        data = _parse_import_json(files, "prompts")
        if data is None:
            raise ValueError(f"{EXPORT_FILE_NAMES['prompts']} is required")
        bundle["prompts"] = _validate_library_import(data, "prompts")
    if "presets" in selected:
        data = _parse_import_json(files, "presets")
        if data is None:
            raise ValueError(f"{EXPORT_FILE_NAMES['presets']} is required")
        bundle["presets"] = _validate_library_import(data, "presets")
    if "node_snips" in selected:
        data = _parse_import_json(files, "node_snips")
        if data is None:
            raise ValueError(f"{EXPORT_FILE_NAMES['node_snips']} is required")
        bundle["node_snips"] = _validate_library_import(data, "node_snips")
    return bundle


def _import_preview(files: dict[str, bytes]) -> dict:
    detected = {}
    errors = []
    try:
        if EXPORT_FILE_NAMES["workflows"] in files:
            workflows = _validate_workflow_zip(files[EXPORT_FILE_NAMES["workflows"]])
            detected["workflows"] = {"count": len(workflows), "file": EXPORT_FILE_NAMES["workflows"]}
    except ValueError as exc:
        errors.append(str(exc))
    for part, key in (("metadata", "workflows"), ("prompts", "prompts"), ("presets", "categories"), ("node_snips", "snips")):
        try:
            data = _parse_import_json(files, part)
            if data is not None:
                values = data.get(key, {})
                detected[part] = {
                    "count": len(values) if hasattr(values, "__len__") else 0,
                    "file": EXPORT_FILE_NAMES[part],
                }
        except ValueError as exc:
            errors.append(str(exc))
    return {"detected": detected, "errors": errors}


def _backup_import_targets(selected: set[str], workflow_entries: list[dict]) -> Path:
    backup_root = _manager_root() / "import_backups" / time.strftime("%Y%m%d-%H%M%S")
    backup_root.mkdir(parents=True, exist_ok=True)
    if "workflows" in selected:
        workflow_backup = backup_root / "workflows"
        for entry in workflow_entries:
            source = (_workflow_root() / entry["path"]).resolve()
            if source.exists():
                target = (workflow_backup / entry["path"]).resolve()
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    if "metadata" in selected and _metadata_path().exists():
        shutil.copy2(_metadata_path(), backup_root / EXPORT_FILE_NAMES["metadata"])
    if "prompts" in selected and _prompt_library_path().exists():
        shutil.copy2(_prompt_library_path(), backup_root / EXPORT_FILE_NAMES["prompts"])
    if "presets" in selected and _preset_snippets_path().exists():
        shutil.copy2(_preset_snippets_path(), backup_root / EXPORT_FILE_NAMES["presets"])
    if "node_snips" in selected and _node_snips_path().exists():
        shutil.copy2(_node_snips_path(), backup_root / EXPORT_FILE_NAMES["node_snips"])
    return backup_root


def _apply_import_bundle(selected: set[str], bundle: dict) -> dict:
    workflow_entries = bundle.get("workflows", [])
    backup_root = _backup_import_targets(selected, workflow_entries)
    workflow_root = _workflow_root().resolve()
    imported_counts = {}
    if "workflows" in selected:
        for entry in workflow_entries:
            target = (workflow_root / entry["path"]).resolve()
            if os.path.commonpath([str(workflow_root), str(target)]) != str(workflow_root):
                raise ValueError(f"unsafe workflow path: {entry['path']}")
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(target.suffix + ".tmp")
            tmp.write_bytes(entry["data"])
            os.replace(tmp, target)
        imported_counts["workflows"] = len(workflow_entries)
    if "metadata" in selected:
        _save_metadata(bundle["metadata"])
        imported_counts["metadata_records"] = len(bundle["metadata"].get("workflows", {}))
    if "prompts" in selected:
        _save_library("prompts", bundle["prompts"])
        imported_counts["prompts"] = len(bundle["prompts"].get("prompts", []))
    if "presets" in selected:
        _save_library("presets", bundle["presets"])
        imported_counts["preset_categories"] = len(bundle["presets"].get("categories", []))
    if "node_snips" in selected:
        _save_library("node_snips", bundle["node_snips"])
        imported_counts["node_snips"] = len(bundle["node_snips"].get("snips", []))
    scan_result = _scan(prune=True) if "workflows" in selected else None
    return {
        "backup_path": str(backup_root),
        "imported": imported_counts,
        "workflows": scan_result.get("workflows", []) if scan_result else None,
        "folders": scan_result.get("folders", []) if scan_result else _folders(),
    }


def _new_library_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _clean_title(value: str, fallback: str = "Untitled") -> str:
    title = str(value or "").strip()
    title = re.sub(r"\s+", " ", title)
    return (title or fallback)[:140]


def _clean_body_text(value: str) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n")[:200000]


def _clean_library_tags(values) -> list[str]:
    return sorted(_tag_map(values).values(), key=str.lower)


def _find_entry(items: list[dict], entry_id: str) -> dict | None:
    for item in items:
        if isinstance(item, dict) and item.get("id") == entry_id:
            return item
    return None


def _upsert_prompt(payload: dict) -> dict:
    data = _load_library("prompts")
    prompts = data.setdefault("prompts", [])
    entry_id = str(payload.get("id") or "").strip()
    existing = _find_entry(prompts, entry_id) if entry_id else None
    now = _now_ms()
    if existing is None:
        existing = {
            "id": _new_library_id("prompt"),
            "created_at": now,
            "use_count": 0,
            "favorite": False,
        }
        prompts.append(existing)
    existing["title"] = _clean_title(payload.get("title"), "Untitled prompt")
    existing["text"] = _clean_body_text(payload.get("text"))
    existing["tags"] = _clean_library_tags(payload.get("tags"))
    if "favorite" in payload:
        existing["favorite"] = bool(payload.get("favorite"))
    existing["updated_at"] = now
    _save_library("prompts", data)
    return existing


def _delete_prompt(entry_id: str) -> bool:
    data = _load_library("prompts")
    before = len(data.setdefault("prompts", []))
    data["prompts"] = [entry for entry in data["prompts"] if entry.get("id") != entry_id]
    changed = len(data["prompts"]) != before
    if changed:
        _save_library("prompts", data)
    return changed


def _touch_prompt(entry_id: str) -> dict | None:
    data = _load_library("prompts")
    entry = _find_entry(data.setdefault("prompts", []), entry_id)
    if entry is None:
        return None
    entry["use_count"] = int(entry.get("use_count", 0) or 0) + 1
    entry["last_used_at"] = _now_ms()
    _save_library("prompts", data)
    return entry


def _upsert_preset_category(payload: dict) -> dict:
    data = _load_library("presets")
    categories = data.setdefault("categories", [])
    entry_id = str(payload.get("id") or "").strip()
    existing = _find_entry(categories, entry_id) if entry_id else None
    now = _now_ms()
    if existing is None:
        existing = {"id": _new_library_id("cat"), "created_at": now, "snippets": []}
        categories.append(existing)
    existing["name"] = _clean_title(payload.get("name"), "New category")
    existing["updated_at"] = now
    _save_library("presets", data)
    return existing


def _delete_preset_category(entry_id: str) -> bool:
    data = _load_library("presets")
    before = len(data.setdefault("categories", []))
    data["categories"] = [entry for entry in data["categories"] if entry.get("id") != entry_id]
    changed = len(data["categories"]) != before
    if changed:
        _save_library("presets", data)
    return changed


def _upsert_preset_snippet(category_id: str, payload: dict) -> dict | None:
    data = _load_library("presets")
    category = _find_entry(data.setdefault("categories", []), category_id)
    if category is None:
        return None
    snippets = category.setdefault("snippets", [])
    entry_id = str(payload.get("id") or "").strip()
    existing = _find_entry(snippets, entry_id) if entry_id else None
    now = _now_ms()
    if existing is None:
        existing = {"id": _new_library_id("snippet"), "created_at": now, "use_count": 0}
        snippets.append(existing)
    existing["text"] = _clean_body_text(payload.get("text"))
    existing["updated_at"] = now
    category["updated_at"] = now
    _save_library("presets", data)
    return existing


def _delete_preset_snippet(category_id: str, entry_id: str) -> bool:
    data = _load_library("presets")
    category = _find_entry(data.setdefault("categories", []), category_id)
    if category is None:
        return False
    snippets = category.setdefault("snippets", [])
    before = len(snippets)
    category["snippets"] = [entry for entry in snippets if entry.get("id") != entry_id]
    changed = len(category["snippets"]) != before
    if changed:
        category["updated_at"] = _now_ms()
        _save_library("presets", data)
    return changed


def _touch_preset_snippet(category_id: str, entry_id: str) -> dict | None:
    data = _load_library("presets")
    category = _find_entry(data.setdefault("categories", []), category_id)
    if category is None:
        return None
    snippet = _find_entry(category.setdefault("snippets", []), entry_id)
    if snippet is None:
        return None
    snippet["use_count"] = int(snippet.get("use_count", 0) or 0) + 1
    snippet["last_used_at"] = _now_ms()
    _save_library("presets", data)
    return snippet


def _upsert_node_snip(payload: dict) -> dict:
    data = _load_library("node_snips")
    snips = data.setdefault("snips", [])
    entry_id = str(payload.get("id") or "").strip()
    existing = _find_entry(snips, entry_id) if entry_id else None
    now = _now_ms()
    if existing is None:
        existing = {
            "id": _new_library_id("snip"),
            "created_at": now,
            "use_count": 0,
            "favorite": False,
        }
        snips.append(existing)
    payload_data = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    snip_type = str(payload.get("type") or payload_data.get("type") or "node").strip().lower()
    if snip_type not in {"node", "group"}:
        snip_type = "node"
    existing["title"] = _clean_title(payload.get("title"), "Untitled snip")
    existing["type"] = snip_type
    existing["tags"] = _clean_library_tags(payload.get("tags"))
    existing["payload"] = payload_data
    if "favorite" in payload:
        existing["favorite"] = bool(payload.get("favorite"))
    existing["updated_at"] = now
    _save_library("node_snips", data)
    return existing


def _delete_node_snip(entry_id: str) -> bool:
    data = _load_library("node_snips")
    before = len(data.setdefault("snips", []))
    data["snips"] = [entry for entry in data["snips"] if entry.get("id") != entry_id]
    changed = len(data["snips"]) != before
    if changed:
        _save_library("node_snips", data)
    return changed


def _touch_node_snip(entry_id: str) -> dict | None:
    data = _load_library("node_snips")
    entry = _find_entry(data.setdefault("snips", []), entry_id)
    if entry is None:
        return None
    entry["use_count"] = int(entry.get("use_count", 0) or 0) + 1
    entry["last_used_at"] = _now_ms()
    _save_library("node_snips", data)
    return entry


def _safe_rel_path(value: str, *, require_json: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("path is required")
    original = value.strip()
    if Path(original).is_absolute() or original.startswith(("/", "\\")):
        raise ValueError("absolute paths are not allowed")
    rel = _normalize_slashes(original)
    if "\x00" in rel or rel.startswith("../") or "/../" in rel or rel == "..":
        raise ValueError("unsafe path")
    parts = Path(rel).parts
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("unsafe path")
    if require_json and Path(rel).suffix.lower() != ".json":
        raise ValueError("workflow path must end with .json")
    return rel


def _safe_folder(value: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("folder must be a string")
    raw = value.strip()
    if Path(raw).is_absolute() or raw.startswith(("/", "\\")):
        raise ValueError("absolute folders are not allowed")
    folder = _normalize_slashes(raw).strip("/")
    if not folder:
        return ""
    return _safe_rel_path(folder)


def _safe_folder_name(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("folder name is required")
    name = value.strip()
    if any(char in name for char in ('/', '\\', ':', '*', '?', '"', '<', '>', '|', '\x00')):
        raise ValueError("folder name contains invalid characters")
    if name in (".", ".."):
        raise ValueError("unsafe folder name")
    return name[:120]


def _resolve_workflow_file(rel_path: str) -> Path:
    rel = _safe_rel_path(rel_path, require_json=True)
    root = _workflow_root().resolve()
    target = (root / rel).resolve()
    if os.path.commonpath([str(root), str(target)]) != str(root):
        raise ValueError("unsafe path")
    return target


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 2
    while True:
        candidate = parent / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _walk_workflows() -> list[Path]:
    root = _workflow_root()
    if not root.exists():
        return []
    files = []
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            if filename in IGNORED_WORKFLOW_NAMES or not filename.lower().endswith(".json"):
                continue
            files.append(Path(dirpath) / filename)
    return sorted(files, key=lambda path: str(path).lower())


def _extract_strings(value) -> list[str]:
    strings = []
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            stripped = item.strip()
            if stripped.startswith("data:"):
                continue
            if len(stripped) > 4000:
                base64_chars = sum(1 for char in stripped if char.isalnum() or char in "+/=\r\n")
                if base64_chars / max(len(stripped), 1) > 0.95:
                    continue
            if stripped:
                strings.append(item)
        elif isinstance(item, dict):
            stack.extend(item.values())
            stack.extend(item.keys())
        elif isinstance(item, list):
            stack.extend(item)
    return strings


def _workflow_nodes(data) -> list[dict]:
    if isinstance(data, dict) and isinstance(data.get("nodes"), list):
        return [node for node in data["nodes"] if isinstance(node, dict)]
    workflow = data.get("workflow") if isinstance(data, dict) else None
    if isinstance(workflow, dict) and isinstance(workflow.get("nodes"), list):
        return [node for node in workflow["nodes"] if isinstance(node, dict)]
    return []


def _model_paths_for_folder(folder_name: str) -> list[Path]:
    paths = []
    mapped = folder_paths.map_legacy(folder_name)
    if mapped in folder_paths.folder_names_and_paths:
        for base in folder_paths.get_folder_paths(mapped):
            paths.append(Path(base))
    else:
        paths.append(Path(folder_paths.models_dir) / folder_name)
    return paths


def _build_model_index() -> dict:
    folder_names = (set(folder_paths.folder_names_and_paths.keys()) & MODEL_FOLDER_ALLOWLIST) | set(EXTRA_MODEL_FOLDERS)
    entries = []
    by_norm = {}
    for folder_name in sorted(folder_names):
        for base in _model_paths_for_folder(folder_name):
            if not base.exists():
                continue
            for dirpath, _, filenames in os.walk(base):
                for filename in filenames:
                    suffix = Path(filename).suffix.lower()
                    if suffix and suffix not in MODEL_EXTENSIONS:
                        continue
                    full = Path(dirpath) / filename
                    try:
                        rel = _normalize_slashes(str(full.relative_to(base)))
                    except ValueError:
                        rel = filename
                    basename = Path(filename).stem
                    norm = _normalize_token(filename)
                    if not norm:
                        continue
                    entry = {
                        "folder": folder_name,
                        "name": basename,
                        "filename": filename,
                        "relative": rel,
                        "norm": norm,
                    }
                    entries.append(entry)
                    by_norm.setdefault(norm, []).append(entry)
    return {"entries": entries, "by_norm": by_norm}


def _add_tag(tags: set[str], value: str) -> None:
    tag = _clean_tag(value)
    if tag:
        tags.add(tag)


def _detect_models(strings: list[str], model_index: dict) -> list[dict]:
    detected = {}
    candidate_strings = []
    for value in strings:
        value = _normalize_slashes(value)
        lower = value.lower()
        if any(ext in lower for ext in MODEL_EXTENSIONS) or "/" in value or "\\" in value:
            candidate_strings.append(value)

    for value in candidate_strings:
        basename_norm = _normalize_token(os.path.basename(value))
        for entry in model_index["by_norm"].get(basename_norm, []):
            detected[(entry["folder"], entry["name"])] = entry

    normalized_candidates = [_normalize_token(value) for value in candidate_strings]
    for entry in model_index["entries"]:
        if len(entry["norm"]) < 7:
            continue
        if any(entry["norm"] in candidate for candidate in normalized_candidates):
            detected[(entry["folder"], entry["name"])] = entry

    return sorted(detected.values(), key=lambda entry: (entry["folder"], entry["name"].lower()))


def _analyze_workflow(data, model_index: dict) -> dict:
    nodes = _workflow_nodes(data)
    node_types = [str(node.get("type", "")) for node in nodes if node.get("type")]
    node_type_text = " ".join(node_types).lower()
    strings = _extract_strings(data)
    string_text = "\n".join(strings).lower()
    all_text = f"{node_type_text}\n{string_text}"
    detected_models = _detect_models(strings, model_index)

    tags = set()
    for entry in detected_models:
        _add_tag(tags, entry["name"])
        folder = entry["folder"].replace("_", " ")
        if folder == "loras":
            _add_tag(tags, "lora")
        elif folder == "checkpoints":
            _add_tag(tags, "checkpoint")
        elif folder == "diffusion_models":
            _add_tag(tags, "diffusion model")
        elif folder == "controlnet":
            _add_tag(tags, "controlnet")
        elif folder == "upscale_models":
            _add_tag(tags, "upscaler")
        elif folder in {"TTS", "audio_encoders"}:
            _add_tag(tags, "audio")
        _add_tag(tags, folder)

    load_image_count = sum(1 for value in node_types if value.lower() == "loadimage" or "load image" in value.lower())
    if load_image_count:
        _add_tag(tags, "image input")
    if load_image_count > 1 or "imagebatch" in node_type_text or "multi reference" in all_text or "reference image" in all_text:
        _add_tag(tags, "multi reference")
    if "controlnet" in all_text or "t2iadapter" in all_text or "t2i_adapter" in all_text:
        _add_tag(tags, "controlnet")
    if "inpaint" in all_text:
        _add_tag(tags, "inpaint")
    if "outpaint" in all_text:
        _add_tag(tags, "outpaint")
    if "faceswap" in all_text or "face swap" in all_text or "reactor" in all_text:
        _add_tag(tags, "face swap")
    if "pose" in all_text or "openpose" in all_text:
        _add_tag(tags, "pose")
    if "upscale" in all_text or "supir" in all_text or "seedvr" in all_text or "rtx" in all_text:
        _add_tag(tags, "upscale")
    if "video" in all_text or "vhs_" in node_type_text or "wan2" in all_text or "ltx" in all_text:
        _add_tag(tags, "video")
    if "audio" in all_text or "tts" in all_text or "voice" in all_text or "rvc" in all_text or "chatterbox" in all_text:
        _add_tag(tags, "audio")
    if "gemini" in all_text or "bytedance" in all_text or "api node" in all_text or "openai" in all_text:
        _add_tag(tags, "api")
    if "loraloader" in node_type_text or "lora" in all_text:
        _add_tag(tags, "lora")
    if "checkpointloader" in node_type_text or "checkpoint" in all_text:
        _add_tag(tags, "checkpoint")
    if "unetloader" in node_type_text or "diffusion model" in all_text or "diffusion_models" in all_text:
        _add_tag(tags, "diffusion model")
    if "saveimage" in node_type_text:
        _add_tag(tags, "image output")
    if "videocombine" in node_type_text or "savevideo" in node_type_text:
        _add_tag(tags, "video output")

    tag_lower = {tag.lower() for tag in tags}
    if "video" in tag_lower and "image input" in tag_lower:
        _add_tag(tags, "image to video")
    elif "video" in tag_lower:
        _add_tag(tags, "text to video")
    elif "image input" in tag_lower and "inpaint" in tag_lower:
        _add_tag(tags, "image to image")
    elif "image input" in tag_lower:
        _add_tag(tags, "image to image")
    elif "image output" in tag_lower:
        _add_tag(tags, "text to image")

    node_counts = Counter(node_types)
    return {
        "auto_tags": sorted(tags, key=str.lower),
        "detected_models": detected_models,
        "node_types": sorted(node_counts.keys(), key=str.lower),
        "node_type_counts": dict(sorted(node_counts.items())),
        "node_count": len(nodes),
    }


def _canonicalize_workflow(data) -> dict:
    data = copy.deepcopy(data)
    nodes = _workflow_nodes(data)
    node_id_map = {}
    canonical_nodes = []
    sorted_nodes = sorted(nodes, key=lambda node: (str(node.get("type", "")), str(node.get("id", ""))))
    for index, node in enumerate(sorted_nodes):
        if "id" in node:
            node_id_map[node["id"]] = index
        canonical = {key: value for key, value in node.items() if key not in VIEW_ONLY_KEYS and key != "id"}
        canonical_nodes.append(_strip_view_fields(canonical))

    links = data.get("links") if isinstance(data, dict) else []
    canonical_links = []
    if isinstance(links, list):
        for link in links:
            if isinstance(link, list) and len(link) >= 6:
                canonical_links.append([
                    node_id_map.get(link[1], link[1]),
                    link[2],
                    node_id_map.get(link[3], link[3]),
                    link[4],
                    link[5],
                ])
    return {"nodes": canonical_nodes, "links": sorted(canonical_links, key=lambda item: json.dumps(item, sort_keys=True))}


def _strip_view_fields(value):
    if isinstance(value, dict):
        return {key: _strip_view_fields(val) for key, val in sorted(value.items()) if key not in VIEW_ONLY_KEYS}
    if isinstance(value, list):
        return [_strip_view_fields(item) for item in value]
    return value


def _hash_json(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _near_signature(analysis: dict) -> str:
    tags = [tag.lower() for tag in analysis["auto_tags"] if tag.lower() not in {"image output", "video output"}]
    models = [f'{model["folder"]}:{model["name"].lower()}' for model in analysis["detected_models"]]
    payload = {
        "node_types": analysis["node_type_counts"],
        "tags": sorted(tags),
        "models": sorted(models),
    }
    return _hash_json(payload)


def _entry_from_file(path: Path, model_index: dict) -> dict:
    root = _workflow_root()
    rel = _normalize_slashes(str(path.relative_to(root)))
    raw = path.read_bytes()
    content_hash = _sha256_bytes(raw)
    parse_error = None
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except Exception as exc:
        data = {}
        parse_error = str(exc)

    analysis = _analyze_workflow(data, model_index) if parse_error is None else {
        "auto_tags": ["parse error"],
        "detected_models": [],
        "node_types": [],
        "node_type_counts": {},
        "node_count": 0,
    }
    canonical_hash = _hash_json(_canonicalize_workflow(data)) if parse_error is None else content_hash
    stat = path.stat()
    return {
        "path": rel,
        "name": path.stem,
        "file_name": path.name,
        "folder": _normalize_slashes(str(path.parent.relative_to(root))) if path.parent != root else "",
        "size": stat.st_size,
        "mtime": int(stat.st_mtime * 1000),
        "content_hash": content_hash,
        "canonical_hash": canonical_hash,
        "near_signature": _near_signature(analysis),
        "parse_error": parse_error,
        **analysis,
    }


def _merge_entries_with_metadata(entries: list[dict], metadata: dict, *, prune: bool) -> dict:
    old_records = metadata.get("workflows", {})
    records_by_hash = defaultdict(list)
    for old_path, record in old_records.items():
        content_hash = record.get("content_hash")
        if content_hash:
            records_by_hash[content_hash].append((old_path, record))

    used_old_paths = set()
    workflows = {}
    for entry in entries:
        rel = entry["path"]
        record = old_records.get(rel)
        if record is not None:
            used_old_paths.add(rel)
        else:
            candidates = records_by_hash.get(entry["content_hash"], [])
            record = None
            for old_path, candidate in candidates:
                if old_path not in used_old_paths:
                    record = candidate
                    used_old_paths.add(old_path)
                    break
        if not isinstance(record, dict):
            record = {}

        manual_tags, hidden_auto_tags, all_tags = _merged_tag_fields(record, entry["auto_tags"])
        merged = {
            **entry,
            "manual_tags": manual_tags,
            "hidden_auto_tags": hidden_auto_tags,
            "favorite": bool(record.get("favorite", False)),
            "run_count": int(record.get("run_count", 0) or 0),
            "last_run_at": record.get("last_run_at"),
            "last_used_at": record.get("last_used_at"),
            "modified_runs": int(record.get("modified_runs", 0) or 0),
        }
        merged["all_tags"] = all_tags
        workflows[rel] = merged

    if not prune:
        for old_path, record in old_records.items():
            if old_path not in workflows and old_path not in used_old_paths:
                workflows[old_path] = record

    return {"version": METADATA_VERSION, "workflows": workflows}


def _merge_entry_with_record(entry: dict, record: dict) -> dict:
    if not isinstance(record, dict):
        record = {}
    manual_tags, hidden_auto_tags, all_tags = _merged_tag_fields(record, entry["auto_tags"])
    merged = {
        **entry,
        "manual_tags": manual_tags,
        "hidden_auto_tags": hidden_auto_tags,
        "favorite": bool(record.get("favorite", False)),
        "run_count": int(record.get("run_count", 0) or 0),
        "last_run_at": record.get("last_run_at"),
        "last_used_at": record.get("last_used_at"),
        "modified_runs": int(record.get("modified_runs", 0) or 0),
    }
    merged["all_tags"] = all_tags
    return merged


def _folders() -> list[str]:
    root = _workflow_root()
    folders = {""}
    if root.exists():
        for dirpath, dirnames, _ in os.walk(root):
            rel = _normalize_slashes(str(Path(dirpath).relative_to(root))) if Path(dirpath) != root else ""
            folders.add(rel)
            for dirname in dirnames:
                child = _normalize_slashes(str((Path(dirpath) / dirname).relative_to(root)))
                folders.add(child)
    return sorted(folders, key=str.lower)


def _scan(prune: bool = False) -> dict:
    model_index = _build_model_index()
    entries = [_entry_from_file(path, model_index) for path in _walk_workflows()]
    metadata = _load_metadata()
    merged = _merge_entries_with_metadata(entries, metadata, prune=prune)
    if prune:
        _save_metadata(merged)
    workflows = list(merged["workflows"].values())
    workflows = [item for item in workflows if item.get("path") in {entry["path"] for entry in entries}]
    workflows.sort(key=lambda item: item["path"].lower())
    return {
        "workflow_root": str(_workflow_root()),
        "metadata_path": str(_metadata_path()),
        "folders": _folders(),
        "workflows": workflows,
        "count": len(workflows),
        "generated_at": _now_ms(),
    }


def _workflow_record(path: str) -> dict:
    metadata = _load_metadata()
    rel = _safe_rel_path(path, require_json=True)
    return metadata.setdefault("workflows", {}).setdefault(rel, {})


async def _read_json_request(request) -> dict:
    try:
        body = await request.json()
    except Exception:
        body = {}
    return body if isinstance(body, dict) else {}


@PromptServer.instance.routes.get(f"{ROUTE_PREFIX}/workflows")
async def get_workflows(_request):
    return _json_response(_scan(prune=False))


@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/sync")
async def sync_workflows(_request):
    return _json_response(_scan(prune=True))


@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/refresh")
async def refresh_workflow(request):
    body = await _read_json_request(request)
    try:
        rel = _safe_rel_path(body.get("path", ""), require_json=True)
        path = _resolve_workflow_file(rel)
    except ValueError as exc:
        return _json_response({"error": str(exc)}, status=400)
    if Path(rel).name in IGNORED_WORKFLOW_NAMES:
        return _json_response({"error": "ignored workflow-manager metadata file", "path": rel}, status=400)
    if not path.exists():
        return _json_response({"error": "workflow not found", "path": rel}, status=404)

    try:
        entry = _entry_from_file(path, _build_model_index())
    except Exception as exc:
        return _json_response({"error": f"failed to refresh workflow: {exc}", "path": rel}, status=500)

    metadata = _load_metadata()
    workflows = metadata.setdefault("workflows", {})
    merged = _merge_entry_with_record(entry, workflows.get(rel, {}))
    workflows[rel] = merged
    _save_metadata(metadata)
    return _json_response({"ok": True, "workflow": merged, "folders": _folders(), "generated_at": _now_ms()})


@PromptServer.instance.routes.get(f"{ROUTE_PREFIX}/workflow")
async def get_workflow(request):
    try:
        path = _resolve_workflow_file(request.rel_url.query.get("path", ""))
    except ValueError as exc:
        return _json_response({"error": str(exc)}, status=400)
    if not path.exists():
        return _json_response({"error": "workflow not found"}, status=404)
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except Exception as exc:
        return _json_response({"error": f"failed to read workflow: {exc}"}, status=500)
    return _json_response({"path": _normalize_slashes(str(path.relative_to(_workflow_root()))), "workflow": data})


@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/run")
async def record_run(request):
    body = await _read_json_request(request)
    try:
        rel = _safe_rel_path(body.get("path", ""), require_json=True)
    except ValueError as exc:
        return _json_response({"error": str(exc)}, status=400)
    metadata = _load_metadata()
    record = metadata.setdefault("workflows", {}).setdefault(rel, {})
    record["run_count"] = int(record.get("run_count", 0) or 0) + 1
    record["last_run_at"] = _now_ms()
    record["last_used_at"] = record["last_run_at"]
    if body.get("modified"):
        record["modified_runs"] = int(record.get("modified_runs", 0) or 0) + 1
    _save_metadata(metadata)
    return _json_response({"ok": True, "path": rel, "run_count": record["run_count"]})


@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/tags")
async def update_tags(request):
    body = await _read_json_request(request)
    try:
        rel = _safe_rel_path(body.get("path", ""), require_json=True)
    except ValueError as exc:
        return _json_response({"error": str(exc)}, status=400)
    metadata = _load_metadata()
    record = metadata.setdefault("workflows", {}).setdefault(rel, {})
    auto_by_key = _tag_map(record.get("auto_tags"))
    manual_by_key = _tag_map(record.get("manual_tags"))
    hidden_by_key = _tag_map(record.get("hidden_auto_tags"))

    if isinstance(body.get("set"), list):
        manual_by_key = _tag_map(body["set"])
    if isinstance(body.get("set_manual"), list):
        manual_by_key = _tag_map(body["set_manual"])
    if isinstance(body.get("set_hidden_auto_tags"), list):
        hidden_by_key = _tag_map(body["set_hidden_auto_tags"])
    elif isinstance(body.get("hidden_auto_tags"), list):
        hidden_by_key = _tag_map(body["hidden_auto_tags"])

    for tag in body.get("add", []) if isinstance(body.get("add"), list) else []:
        cleaned = _clean_tag(tag)
        if cleaned:
            manual_by_key[cleaned.lower()] = cleaned
            hidden_by_key.pop(cleaned.lower(), None)
    for tag in body.get("remove", []) if isinstance(body.get("remove"), list) else []:
        cleaned = _clean_tag(tag)
        key = cleaned.lower()
        manual_by_key.pop(key, None)
        if key in auto_by_key:
            hidden_by_key[key] = auto_by_key[key]
    for tag in body.get("hide_auto", []) if isinstance(body.get("hide_auto"), list) else []:
        cleaned = _clean_tag(tag)
        key = cleaned.lower()
        if key in auto_by_key and key not in manual_by_key:
            hidden_by_key[key] = auto_by_key[key]
    for tag in body.get("unhide_auto", []) if isinstance(body.get("unhide_auto"), list) else []:
        cleaned = _clean_tag(tag)
        hidden_by_key.pop(cleaned.lower(), None)

    hidden_by_key = {
        key: auto_by_key[key]
        for key in hidden_by_key
        if key in auto_by_key and key not in manual_by_key
    }
    record["manual_tags"] = sorted(manual_by_key.values(), key=str.lower)
    record["hidden_auto_tags"] = sorted(hidden_by_key.values(), key=str.lower)
    visible_auto_tags = [
        tag
        for key, tag in auto_by_key.items()
        if key not in hidden_by_key
    ]
    record["all_tags"] = sorted({*visible_auto_tags, *record["manual_tags"]}, key=str.lower)
    _save_metadata(metadata)
    return _json_response({
        "ok": True,
        "path": rel,
        "manual_tags": record["manual_tags"],
        "hidden_auto_tags": record["hidden_auto_tags"],
        "all_tags": record["all_tags"],
    })


@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/favorite")
async def update_favorite(request):
    body = await _read_json_request(request)
    try:
        rel = _safe_rel_path(body.get("path", ""), require_json=True)
    except ValueError as exc:
        return _json_response({"error": str(exc)}, status=400)
    metadata = _load_metadata()
    record = metadata.setdefault("workflows", {}).setdefault(rel, {})
    record["favorite"] = bool(body.get("favorite"))
    _save_metadata(metadata)
    return _json_response({"ok": True, "path": rel, "favorite": record["favorite"]})


@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/move")
async def move_workflow(request):
    body = await _read_json_request(request)
    try:
        rel = _safe_rel_path(body.get("path", ""), require_json=True)
        folder = _safe_folder(body.get("folder", ""))
        source = _resolve_workflow_file(rel)
    except ValueError as exc:
        return _json_response({"error": str(exc)}, status=400)
    if not source.exists():
        return _json_response({"error": "workflow not found"}, status=404)
    target_dir = (_workflow_root() / folder).resolve()
    if os.path.commonpath([str(_workflow_root().resolve()), str(target_dir)]) != str(_workflow_root().resolve()):
        return _json_response({"error": "unsafe folder"}, status=400)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = _unique_path(target_dir / source.name)
    shutil.move(str(source), str(target))

    new_rel = _normalize_slashes(str(target.relative_to(_workflow_root())))
    metadata = _load_metadata()
    workflows = metadata.setdefault("workflows", {})
    record = workflows.pop(rel, {})
    workflows[new_rel] = record
    _save_metadata(metadata)
    return _json_response({"ok": True, "old_path": rel, "path": new_rel})


@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/folder")
async def create_folder(request):
    body = await _read_json_request(request)
    try:
        parent = _safe_folder(body.get("parent", ""))
        name = _safe_folder_name(body.get("name", ""))
    except ValueError as exc:
        return _json_response({"error": str(exc)}, status=400)

    root = _workflow_root().resolve()
    target = (root / parent / name).resolve()
    if os.path.commonpath([str(root), str(target)]) != str(root):
        return _json_response({"error": "unsafe folder"}, status=400)
    if target.exists() and not target.is_dir():
        return _json_response({"error": "a file exists with that name"}, status=409)
    target.mkdir(parents=True, exist_ok=True)
    rel = _normalize_slashes(str(target.relative_to(root)))
    return _json_response({"ok": True, "folder": rel, "folders": _folders()})


@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/delete")
async def delete_workflow(request):
    body = await _read_json_request(request)
    try:
        rel = _safe_rel_path(body.get("path", ""), require_json=True)
        source = _resolve_workflow_file(rel)
    except ValueError as exc:
        return _json_response({"error": str(exc)}, status=400)
    if not source.exists():
        return _json_response({"error": "workflow not found"}, status=404)
    target_dir = (_trash_root() / Path(rel).parent).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = _unique_path(target_dir / source.name)
    shutil.move(str(source), str(target))
    metadata = _load_metadata()
    metadata.setdefault("workflows", {}).pop(rel, None)
    _save_metadata(metadata)
    return _json_response({"ok": True, "path": rel, "trash_path": str(target)})


@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/duplicates")
async def duplicates(_request):
    data = _scan(prune=False)
    workflows = data["workflows"]
    exact = _duplicate_groups(workflows, "content_hash")
    canonical = _duplicate_groups(workflows, "canonical_hash")
    near = _duplicate_groups(workflows, "near_signature")
    return _json_response({"exact": exact, "canonical": canonical, "near": near, "generated_at": _now_ms()})


@PromptServer.instance.routes.get(f"{ROUTE_PREFIX}/export-import/manifest")
async def export_import_manifest(_request):
    return _json_response(_export_manifest())


@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/export-import/export")
async def export_import_export(request):
    body = await _read_json_request(request)
    selected = _selected_parts(body.get("parts"))
    if not selected:
        return _json_response({"error": "select at least one export item"}, status=400)
    return _json_response({
        "ok": True,
        "manifest": _export_manifest(),
        "files": _export_files(selected),
    })


@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/export-import/preview")
@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/export-import/import/preview")
async def export_import_preview(request):
    body = await _read_json_request(request)
    try:
        files = _decode_import_files(body.get("files"))
        preview = _import_preview(files)
    except ValueError as exc:
        return _json_response({"error": str(exc)}, status=400)
    return _json_response({"ok": True, **preview})


@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/export-import/import")
async def export_import_import(request):
    body = await _read_json_request(request)
    selected = _selected_parts(body.get("parts"))
    if not selected:
        return _json_response({"error": "select at least one import item"}, status=400)
    try:
        files = _decode_import_files(body.get("files"))
        bundle = _validate_import_bundle(files, selected)
        result = _apply_import_bundle(selected, bundle)
    except ValueError as exc:
        return _json_response({"error": str(exc)}, status=400)
    return _json_response({"ok": True, **result, "generated_at": _now_ms()})


@PromptServer.instance.routes.get(f"{ROUTE_PREFIX}/library/all")
async def get_library_all(_request):
    return _json_response({
        "prompts": _load_library("prompts").get("prompts", []),
        "presets": _load_library("presets").get("categories", []),
        "node_snips": _load_library("node_snips").get("snips", []),
        "generated_at": _now_ms(),
    })


@PromptServer.instance.routes.get(f"{ROUTE_PREFIX}/library/prompts")
async def get_library_prompts(_request):
    return _json_response({"prompts": _load_library("prompts").get("prompts", [])})


@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/library/prompts/upsert")
async def upsert_library_prompt(request):
    body = await _read_json_request(request)
    entry = _upsert_prompt(body)
    return _json_response({"ok": True, "prompt": entry, "prompts": _load_library("prompts").get("prompts", [])})


@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/library/prompts/delete")
async def delete_library_prompt(request):
    body = await _read_json_request(request)
    entry_id = str(body.get("id") or "").strip()
    if not entry_id:
        return _json_response({"error": "id is required"}, status=400)
    _delete_prompt(entry_id)
    return _json_response({"ok": True, "prompts": _load_library("prompts").get("prompts", [])})


@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/library/prompts/use")
async def use_library_prompt(request):
    body = await _read_json_request(request)
    entry_id = str(body.get("id") or "").strip()
    if not entry_id:
        return _json_response({"error": "id is required"}, status=400)
    entry = _touch_prompt(entry_id)
    if entry is None:
        return _json_response({"error": "prompt not found"}, status=404)
    return _json_response({"ok": True, "prompt": entry})


@PromptServer.instance.routes.get(f"{ROUTE_PREFIX}/library/presets")
async def get_library_presets(_request):
    return _json_response({"categories": _load_library("presets").get("categories", [])})


@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/library/presets/category/upsert")
async def upsert_library_preset_category(request):
    body = await _read_json_request(request)
    entry = _upsert_preset_category(body)
    return _json_response({"ok": True, "category": entry, "categories": _load_library("presets").get("categories", [])})


@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/library/presets/category/delete")
async def delete_library_preset_category(request):
    body = await _read_json_request(request)
    entry_id = str(body.get("id") or "").strip()
    if not entry_id:
        return _json_response({"error": "id is required"}, status=400)
    _delete_preset_category(entry_id)
    return _json_response({"ok": True, "categories": _load_library("presets").get("categories", [])})


@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/library/presets/snippet/upsert")
async def upsert_library_preset_snippet(request):
    body = await _read_json_request(request)
    category_id = str(body.get("category_id") or "").strip()
    if not category_id:
        return _json_response({"error": "category_id is required"}, status=400)
    entry = _upsert_preset_snippet(category_id, body)
    if entry is None:
        return _json_response({"error": "category not found"}, status=404)
    return _json_response({"ok": True, "snippet": entry, "categories": _load_library("presets").get("categories", [])})


@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/library/presets/snippet/delete")
async def delete_library_preset_snippet(request):
    body = await _read_json_request(request)
    category_id = str(body.get("category_id") or "").strip()
    entry_id = str(body.get("id") or "").strip()
    if not category_id or not entry_id:
        return _json_response({"error": "category_id and id are required"}, status=400)
    _delete_preset_snippet(category_id, entry_id)
    return _json_response({"ok": True, "categories": _load_library("presets").get("categories", [])})


@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/library/presets/snippet/use")
async def use_library_preset_snippet(request):
    body = await _read_json_request(request)
    category_id = str(body.get("category_id") or "").strip()
    entry_id = str(body.get("id") or "").strip()
    if not category_id or not entry_id:
        return _json_response({"error": "category_id and id are required"}, status=400)
    entry = _touch_preset_snippet(category_id, entry_id)
    if entry is None:
        return _json_response({"error": "snippet not found"}, status=404)
    return _json_response({"ok": True, "snippet": entry})


@PromptServer.instance.routes.get(f"{ROUTE_PREFIX}/library/node-snips")
async def get_library_node_snips(_request):
    return _json_response({"snips": _load_library("node_snips").get("snips", [])})


@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/library/node-snips/upsert")
async def upsert_library_node_snip(request):
    body = await _read_json_request(request)
    entry = _upsert_node_snip(body)
    return _json_response({"ok": True, "snip": entry, "snips": _load_library("node_snips").get("snips", [])})


@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/library/node-snips/delete")
async def delete_library_node_snip(request):
    body = await _read_json_request(request)
    entry_id = str(body.get("id") or "").strip()
    if not entry_id:
        return _json_response({"error": "id is required"}, status=400)
    _delete_node_snip(entry_id)
    return _json_response({"ok": True, "snips": _load_library("node_snips").get("snips", [])})


@PromptServer.instance.routes.post(f"{ROUTE_PREFIX}/library/node-snips/use")
async def use_library_node_snip(request):
    body = await _read_json_request(request)
    entry_id = str(body.get("id") or "").strip()
    if not entry_id:
        return _json_response({"error": "id is required"}, status=400)
    entry = _touch_node_snip(entry_id)
    if entry is None:
        return _json_response({"error": "node snip not found"}, status=404)
    return _json_response({"ok": True, "snip": entry})


def _duplicate_groups(workflows: list[dict], key: str) -> list[dict]:
    grouped = defaultdict(list)
    for workflow in workflows:
        value = workflow.get(key)
        if value:
            grouped[value].append(workflow)
    groups = []
    for value, items in grouped.items():
        if len(items) < 2:
            continue
        groups.append({
            "signature": value,
            "count": len(items),
            "workflows": [
                {
                    "path": item["path"],
                    "name": item.get("name"),
                    "folder": item.get("folder"),
                    "auto_tags": item.get("auto_tags", []),
                    "run_count": item.get("run_count", 0),
                }
                for item in sorted(items, key=lambda workflow: workflow["path"].lower())
            ],
        })
    return sorted(groups, key=lambda group: (-group["count"], group["workflows"][0]["path"].lower()))
