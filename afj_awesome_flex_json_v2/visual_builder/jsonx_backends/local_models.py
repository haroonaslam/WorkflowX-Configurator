from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import folder_paths


NO_MMPROJ = "none"
NO_SYSTEM_PROMPT = "none"
NO_MODELS_FOUND = "No GGUF models found"
EXTERNAL_PREFIX = "external:"
MAX_ADDITIONAL_ROOTS = 16


def llm_root() -> Path:
    return Path(folder_paths.models_dir) / "LLM"


def prompt_root() -> Path:
    return llm_root() / "prompts"


def _relative_files(root: Path, suffix: str) -> list[str]:
    if not root.exists():
        return []
    return sorted(
        str(path.relative_to(root)).replace("\\", "/")
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() == suffix
    )


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
        path = Path(raw).expanduser()
        try:
            resolved = path.resolve()
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


def _external_option(root: Path, relative: str) -> dict[str, str]:
    label_root = root.name or str(root)
    return {
        "value": f"{EXTERNAL_PREFIX}{_root_id(root)}:{relative}",
        "label": f"{label_root} (external) / {relative}",
    }


def model_catalog(additional_roots: Any = None) -> dict[str, Any]:
    primary = llm_root().resolve()
    roots, invalid = normalize_additional_roots(additional_roots)
    seen_files: set[str] = set()
    models: list[str | dict[str, str]] = []
    mmproj: list[str | dict[str, str]] = [NO_MMPROJ]

    for name in _relative_files(primary, ".gguf"):
        full = (primary / name).resolve()
        seen_files.add(str(full).casefold())
        if "mmproj" in Path(name).name.lower():
            mmproj.append(name)
        else:
            models.append(name)

    for root in roots:
        for name in _relative_files(root, ".gguf"):
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
    return [NO_SYSTEM_PROMPT] + _relative_files(prompt_root(), ".txt")


def _resolve(root: Path, name: str, kind: str) -> Path:
    candidate = (root / str(name)).resolve()
    resolved_root = root.resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise FileNotFoundError(f"Invalid {kind} path: {name}") from exc
    if not candidate.is_file():
        raise FileNotFoundError(f"{kind} not found: {name}")
    return candidate


def _resolve_selection(root: Path, name: str, kind: str) -> Path:
    return _resolve(root, name, kind)


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
    return _resolve_selection(matches[0], relative, kind)


def full_model_path(name: str, additional_roots: Any = None) -> Path:
    if not name or name == NO_MODELS_FOUND:
        raise FileNotFoundError(f"No GGUF model files were found in {llm_root()}.")
    if str(name).startswith(EXTERNAL_PREFIX):
        return _resolve_external(name, additional_roots, "GGUF model")
    return _resolve(llm_root(), name, "GGUF model")


def full_mmproj_path(name: str, additional_roots: Any = None) -> Path | None:
    if not name or name == NO_MMPROJ:
        return None
    if str(name).startswith(EXTERNAL_PREFIX):
        return _resolve_external(name, additional_roots, "mmproj GGUF file")
    return _resolve(llm_root(), name, "mmproj GGUF file")


def full_system_prompt_path(name: str) -> Path | None:
    if not name or name == NO_SYSTEM_PROMPT:
        return None
    return _resolve(prompt_root(), name, "system prompt preset")
