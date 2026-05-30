import copy
import hashlib
import json
import os
import re
import shutil
import time
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

        manual_tags = record.get("manual_tags") if isinstance(record.get("manual_tags"), list) else []
        manual_tags = sorted({_clean_tag(tag) for tag in manual_tags if _clean_tag(tag)}, key=str.lower)
        merged = {
            **entry,
            "manual_tags": manual_tags,
            "favorite": bool(record.get("favorite", False)),
            "run_count": int(record.get("run_count", 0) or 0),
            "last_run_at": record.get("last_run_at"),
            "last_used_at": record.get("last_used_at"),
            "modified_runs": int(record.get("modified_runs", 0) or 0),
        }
        merged["all_tags"] = sorted(set(merged["auto_tags"]) | set(manual_tags), key=str.lower)
        workflows[rel] = merged

    if not prune:
        for old_path, record in old_records.items():
            if old_path not in workflows and old_path not in used_old_paths:
                workflows[old_path] = record

    return {"version": METADATA_VERSION, "workflows": workflows}


def _merge_entry_with_record(entry: dict, record: dict) -> dict:
    if not isinstance(record, dict):
        record = {}
    manual_tags = record.get("manual_tags") if isinstance(record.get("manual_tags"), list) else []
    manual_tags = sorted({_clean_tag(tag) for tag in manual_tags if _clean_tag(tag)}, key=str.lower)
    merged = {
        **entry,
        "manual_tags": manual_tags,
        "favorite": bool(record.get("favorite", False)),
        "run_count": int(record.get("run_count", 0) or 0),
        "last_run_at": record.get("last_run_at"),
        "last_used_at": record.get("last_used_at"),
        "modified_runs": int(record.get("modified_runs", 0) or 0),
    }
    merged["all_tags"] = sorted(set(merged["auto_tags"]) | set(manual_tags), key=str.lower)
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
    tags = set(record.get("manual_tags") if isinstance(record.get("manual_tags"), list) else [])
    for tag in body.get("add", []) if isinstance(body.get("add"), list) else []:
        cleaned = _clean_tag(tag)
        if cleaned:
            tags.add(cleaned)
    for tag in body.get("remove", []) if isinstance(body.get("remove"), list) else []:
        cleaned = _clean_tag(tag)
        tags = {value for value in tags if value.lower() != cleaned.lower()}
    if isinstance(body.get("set"), list):
        tags = {_clean_tag(tag) for tag in body["set"] if _clean_tag(tag)}
    record["manual_tags"] = sorted(tags, key=str.lower)
    _save_metadata(metadata)
    return _json_response({"ok": True, "path": rel, "manual_tags": record["manual_tags"]})


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
