from __future__ import annotations

from pathlib import Path

import folder_paths


NO_MMPROJ = "none"
NO_SYSTEM_PROMPT = "none"
NO_MODELS_FOUND = "No GGUF models found"


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


def model_options() -> list[str]:
    files = _relative_files(llm_root(), ".gguf")
    models = [name for name in files if "mmproj" not in Path(name).name.lower()]
    return models or [NO_MODELS_FOUND]


def mmproj_options() -> list[str]:
    files = _relative_files(llm_root(), ".gguf")
    return [NO_MMPROJ] + [name for name in files if "mmproj" in Path(name).name.lower()]


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


def full_model_path(name: str) -> Path:
    if not name or name == NO_MODELS_FOUND:
        raise FileNotFoundError(f"No GGUF model files were found in {llm_root()}.")
    return _resolve(llm_root(), name, "GGUF model")


def full_mmproj_path(name: str) -> Path | None:
    if not name or name == NO_MMPROJ:
        return None
    return _resolve(llm_root(), name, "mmproj GGUF file")


def full_system_prompt_path(name: str) -> Path | None:
    if not name or name == NO_SYSTEM_PROMPT:
        return None
    return _resolve(prompt_root(), name, "system prompt preset")
