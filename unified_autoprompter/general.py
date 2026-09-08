"""Direct authoring inputs, independent of all profile builders and contracts."""
from __future__ import annotations

from pathlib import Path
from .folder_registry import prompt_root

GENERAL_SCHEMA_VERSION = 1


class GeneralInputError(ValueError):
    pass


def preset_path(name: str) -> Path:
    root = prompt_root().resolve()
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts or ":" in name or relative.suffix.lower() != ".txt":
        raise GeneralInputError("Choose a .txt preset from the preset dropdown and refresh the list.")
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise GeneralInputError("The selected preset is missing or outside the presets folder. Refresh Use preset and select it again.")
    return candidate


def list_presets() -> list[str]:
    root = prompt_root()
    if not root.is_dir():
        return []
    names = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() == ".txt":
            name = path.relative_to(root).as_posix()
            try:
                preset_path(name)
            except GeneralInputError:
                continue
            names.append(name)
    return sorted(names, key=str.casefold)


def build_inputs(data: dict, image_count: int) -> tuple[str, str]:
    if image_count > 9:
        raise GeneralInputError("General accepts at most nine connected images.")
    fields = data.get("fields") if isinstance(data.get("fields"), dict) else data
    connected = str(fields.get("raw_prompt_text") or "")
    user = connected if connected.strip() else str(fields.get("prompt_text") or "")
    if not user.strip() and not image_count:
        raise GeneralInputError("Enter a prompt or connect an image before generating.")
    name = str(data.get("preset") or "none")
    system = ""
    if name != "none":
        try:
            system = preset_path(name).read_bytes().decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise GeneralInputError("The preset could not be read as UTF-8 text. Check the file and try again.") from exc
    return system, user
