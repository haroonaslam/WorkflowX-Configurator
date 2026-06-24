from __future__ import annotations

import os
from pathlib import Path

import folder_paths


LLM_FOLDER = "workflowx_unified_autoprompter_llm_models"
PROMPT_FOLDER = "workflowx_unified_autoprompter_llm_prompts"
NO_MMPROJ = "none"
NO_SYSTEM_PROMPT = "none"
NO_MODELS_FOUND = "No GGUF models found"


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


def model_options() -> list[str]:
    files = _get_filename_list(LLM_FOLDER)
    models = [name for name in files if "mmproj" not in Path(name).name.lower()]
    return models or [NO_MODELS_FOUND]


def mmproj_options() -> list[str]:
    files = _get_filename_list(LLM_FOLDER)
    mmproj = [name for name in files if "mmproj" in Path(name).name.lower()]
    return [NO_MMPROJ] + mmproj


def system_prompt_options() -> list[str]:
    files = _get_filename_list(PROMPT_FOLDER)
    top_level_files = [name for name in files if os.sep not in name and "/" not in name]
    return [NO_SYSTEM_PROMPT] + top_level_files


def full_model_path(name: str) -> Path:
    if name == NO_MODELS_FOUND:
        raise FileNotFoundError(f"No GGUF model files were found in {llm_root()}.")
    path = _get_full_path(LLM_FOLDER, name)
    if path is None:
        raise FileNotFoundError(f"GGUF model not found: {name}")
    return Path(path)


def full_mmproj_path(name: str) -> Path | None:
    if name == NO_MMPROJ:
        return None
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
