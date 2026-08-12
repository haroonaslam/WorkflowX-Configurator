from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import folder_paths


LLM_FOLDER = "workflowx_unified_autoprompter_llm_models"
PROMPT_FOLDER = "workflowx_unified_autoprompter_llm_prompts"
NO_MMPROJ = "none"
NO_SYSTEM_PROMPT = "none"
NO_MODELS_FOUND = "No GGUF models found"
EXTERNAL_PREFIX = "external:"
MAX_ADDITIONAL_ROOTS = 16


def llm_root() -> Path:
    return Path(folder_paths.models_dir) / "LLM"


def prompt_root() -> Path:
    return llm_root() / "prompts"


def register_folders() -> None:
    llm_root().mkdir(parents=True, exist_ok=True)
    prompt_root().mkdir(parents=True, exist_ok=True)
    folder_paths.folder_names_and_paths[LLM_FOLDER] = ([str(llm_root())], {".gguf"})
    folder_paths.folder_names_and_paths[PROMPT_FOLDER] = ([str(prompt_root())], {".txt"})


def _get_filename_list(folder: str) -> list[str]:
    getter = getattr(folder_paths, "get_filename_list", None)
    if callable(getter):
        try:
            return list(getter(folder))
        except Exception:
            return []
    roots, extensions = folder_paths.folder_names_and_paths.get(folder, ([], set()))
    out = []
    for root in roots:
        root_path = Path(root)
        if not root_path.exists():
            continue
        for path in root_path.rglob("*"):
            if path.is_file() and path.suffix.lower() in extensions:
                out.append(str(path.relative_to(root_path)).replace("\\", "/"))
    return sorted(out)


def _get_full_path(folder: str, name: str) -> str | None:
    getter = getattr(folder_paths, "get_full_path", None)
    if callable(getter):
        path = getter(folder, name)
        if path:
            return path
    roots, _extensions = folder_paths.folder_names_and_paths.get(folder, ([], set()))
    for root in roots:
        path = Path(root) / name
        if path.exists():
            return str(path)
    return None


def normalize_additional_roots(value: Any) -> tuple[list[Path], list[str]]:
    if isinstance(value, str):
        raw_items = value.replace("\r", "\n").replace(";", "\n").split("\n")
    elif isinstance(value, (list, tuple)):
        raw_items = value
    else:
        raw_items = []
    roots: list[Path] = []
    invalid: list[str] = []
    seen: set[str] = set()
    for item in raw_items[:MAX_ADDITIONAL_ROOTS]:
        raw = str(item or "").strip().strip('"')
        if not raw:
            continue
        try:
            resolved = Path(raw).expanduser().resolve()
        except OSError:
            invalid.append(raw)
            continue
        key = str(resolved).casefold()
        if key in seen:
            continue
        seen.add(key)
        if not resolved.is_dir():
            invalid.append(raw)
            continue
        roots.append(resolved)
    return roots, invalid


def _root_id(root: Path) -> str:
    return hashlib.sha256(str(root).casefold().encode("utf-8")).hexdigest()[:16]


def _relative_gguf(root: Path) -> list[str]:
    if not root.exists():
        return []
    return sorted(
        str(path.relative_to(root)).replace("\\", "/")
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() == ".gguf"
    )


def _external_option(root: Path, relative: str) -> dict[str, str]:
    label_root = root.name or str(root)
    return {
        "value": f"{EXTERNAL_PREFIX}{_root_id(root)}:{relative}",
        "label": f"{label_root} (external) / {relative}",
    }


def model_catalog(additional_roots: Any = None) -> dict[str, Any]:
    files = _get_filename_list(LLM_FOLDER)
    models: list[str | dict[str, str]] = []
    mmproj: list[str | dict[str, str]] = [NO_MMPROJ]
    seen_files: set[str] = set()
    for name in files:
        full_path = _get_full_path(LLM_FOLDER, name)
        if full_path:
            try:
                seen_files.add(str(Path(full_path).resolve()).casefold())
            except OSError:
                pass
        if "mmproj" in Path(name).name.lower():
            mmproj.append(name)
        else:
            models.append(name)

    roots, invalid = normalize_additional_roots(additional_roots)
    for root in roots:
        for name in _relative_gguf(root):
            full = (root / name).resolve()
            key = str(full).casefold()
            if key in seen_files:
                continue
            seen_files.add(key)
            option = _external_option(root, name)
            if "mmproj" in Path(name).name.lower():
                mmproj.append(option)
            else:
                models.append(option)

    return {
        "models": models or [NO_MODELS_FOUND],
        "mmproj": mmproj,
        "system_prompts": system_prompt_options(),
        "invalid_paths": invalid,
        "additional_roots": len(roots),
    }


def model_options(additional_roots: Any = None) -> list[str | dict[str, str]]:
    return model_catalog(additional_roots)["models"]


def mmproj_options(additional_roots: Any = None) -> list[str | dict[str, str]]:
    return model_catalog(additional_roots)["mmproj"]


def system_prompt_options() -> list[str]:
    files = _get_filename_list(PROMPT_FOLDER)
    top_level_files = [name for name in files if os.sep not in name and "/" not in name]
    return [NO_SYSTEM_PROMPT] + top_level_files


def _resolve_external(name: str, additional_roots: Any, kind: str) -> Path:
    payload = str(name)[len(EXTERNAL_PREFIX):]
    root_id, separator, relative = payload.partition(":")
    if not separator or not root_id or not relative:
        raise FileNotFoundError(f"Invalid external {kind} selection.")
    roots, _invalid = normalize_additional_roots(additional_roots)
    matches = [root for root in roots if _root_id(root) == root_id]
    if len(matches) != 1:
        raise FileNotFoundError(
            f"External {kind} folder is no longer configured. Refresh the local model list."
        )
    candidate = (matches[0] / relative).resolve()
    try:
        candidate.relative_to(matches[0])
    except ValueError as exc:
        raise FileNotFoundError(f"Invalid external {kind} path.") from exc
    if not candidate.is_file():
        raise FileNotFoundError(f"{kind} not found: {relative}")
    return candidate


def full_model_path(name: str, additional_roots: Any = None) -> Path:
    if name == NO_MODELS_FOUND:
        raise FileNotFoundError(f"No GGUF model files were found in {llm_root()}.")
    if str(name).startswith(EXTERNAL_PREFIX):
        return _resolve_external(name, additional_roots, "GGUF model")
    path = _get_full_path(LLM_FOLDER, name)
    if path is None:
        raise FileNotFoundError(f"GGUF model not found: {name}")
    return Path(path)


def full_mmproj_path(name: str, additional_roots: Any = None) -> Path | None:
    if name == NO_MMPROJ:
        return None
    if str(name).startswith(EXTERNAL_PREFIX):
        return _resolve_external(name, additional_roots, "mmproj GGUF file")
    path = _get_full_path(LLM_FOLDER, name)
    if path is None:
        raise FileNotFoundError(f"mmproj GGUF file not found: {name}")
    return Path(path)


def full_system_prompt_path(name: str) -> Path | None:
    if name == NO_SYSTEM_PROMPT:
        return None
    path = _get_full_path(PROMPT_FOLDER, name)
    if path is None:
        raise FileNotFoundError(f"System prompt preset not found: {name}")
    return Path(path)


register_folders()
