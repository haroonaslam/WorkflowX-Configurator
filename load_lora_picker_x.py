"""Filesystem-backed multi-LoRA loader with training-checkpoint discovery."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


NODE_ID = "KVGC_LoadLoraPickerX"
CATEGORY = "WorkflowX/Loaders"
LORA_EXTENSIONS = (".safetensors", ".ckpt", ".pt", ".bin")
PICK_ROUTE = "/workflowx_configurator/load_lora_picker_x/pick"
INSPECT_ROUTE = "/workflowx_configurator/load_lora_picker_x/inspect"


class _FlexibleOptionalInputType(dict):
    def __init__(self, input_type: Any, data: dict[str, Any] | None = None) -> None:
        super().__init__(data or {})
        self.input_type = input_type
        self.data = data or {}

    def __getitem__(self, key: str) -> Any:
        return self.data[key] if key in self.data else (self.input_type,)

    def __contains__(self, key: object) -> bool:
        return True


def _normalize_path(value: object) -> str:
    return str(value or "").replace("\\", "/").strip()


def _is_supported(path: str | os.PathLike[str]) -> bool:
    return Path(path).suffix.lower() in LORA_EXTENSIONS


def _resolve_reference(reference: object, folder_paths_module) -> str:
    normalized = _normalize_path(reference)
    if not normalized:
        raise ValueError("A LoRA file is required.")

    candidate = os.path.abspath(os.path.expanduser(normalized))
    if os.path.isfile(candidate):
        resolved = candidate
    else:
        try:
            resolved = folder_paths_module.get_full_path("loras", normalized)
        except Exception as exc:
            raise ValueError(f"Could not resolve LoRA '{normalized}'.") from exc

    if not resolved or not os.path.isfile(resolved):
        raise FileNotFoundError(f"LoRA file was not found: {normalized}")
    resolved = os.path.abspath(resolved)
    if not _is_supported(resolved):
        allowed = ", ".join(LORA_EXTENSIONS)
        raise ValueError(f"Unsupported LoRA file type. Choose one of: {allowed}")
    return resolved


def _registered_lora_roots(folder_paths_module) -> list[str]:
    try:
        roots = folder_paths_module.get_folder_paths("loras")
    except Exception:
        roots = []
    return [os.path.abspath(str(root)) for root in roots if str(root or "").strip()]


def _reference_for_path(path: str, folder_paths_module) -> tuple[str, str]:
    absolute = os.path.abspath(path)
    absolute_case = os.path.normcase(absolute)
    for root in _registered_lora_roots(folder_paths_module):
        try:
            common = os.path.commonpath((os.path.normcase(root), absolute_case))
        except ValueError:
            continue
        if common != os.path.normcase(root):
            continue
        relative = os.path.relpath(absolute, root).replace("\\", "/")
        return relative, "registered"
    return absolute.replace("\\", "/"), "external"


_EXPLICIT_EPOCH_RE = re.compile(
    r"^(?P<base>.+?)(?P<separator>[-_. ]+)(?P<marker>epoch|ep|step|checkpoint|ckpt)(?P<joiner>[-_. ]*)(?P<number>\d+)$",
    re.IGNORECASE,
)
_TRAILING_NUMBER_RE = re.compile(r"^(?P<base>.+?)(?P<separator>[-_. ])(?P<number>\d{3,})$")
_MARKER_KIND = {"ep": "epoch", "epoch": "epoch", "step": "step", "ckpt": "checkpoint", "checkpoint": "checkpoint"}
_KIND_PRIORITY = {"epoch": 0, "step": 1, "checkpoint": 2, "number": 3}


def _parse_epoch_stem(stem: str) -> dict[str, Any] | None:
    explicit = _EXPLICIT_EPOCH_RE.match(stem)
    if explicit:
        marker = explicit.group("marker").lower()
        return {
            "base": explicit.group("base"),
            "kind": _MARKER_KIND[marker],
            "number": int(explicit.group("number")),
            "digits": explicit.group("number"),
        }

    trailing = _TRAILING_NUMBER_RE.match(stem)
    if not trailing:
        return None
    base = trailing.group("base")
    if re.search(r"(?:^|[-_. ])(?:v|version)$", base, re.IGNORECASE):
        return None
    return {
        "base": base,
        "kind": "number",
        "number": int(trailing.group("number")),
        "digits": trailing.group("number"),
    }


def _epoch_label(parsed: dict[str, Any] | None, filename: str, *, final: bool = False) -> str:
    if final:
        return "Final"
    if not parsed:
        return filename
    prefix = {
        "epoch": "Epoch",
        "step": "Step",
        "checkpoint": "Checkpoint",
        "number": "Checkpoint",
    }[parsed["kind"]]
    return f"{prefix} {parsed['digits']}"


def _candidate_groups(directory: Path, extension: str) -> dict[tuple[str, str], list[tuple[Path, dict[str, Any]]]]:
    groups: dict[tuple[str, str], list[tuple[Path, dict[str, Any]]]] = {}
    for sibling in directory.iterdir():
        if not sibling.is_file() or sibling.suffix.lower() != extension.lower():
            continue
        parsed = _parse_epoch_stem(sibling.stem)
        if not parsed:
            continue
        key = (parsed["base"].casefold(), parsed["kind"])
        groups.setdefault(key, []).append((sibling, parsed))
    return groups


def _select_epoch_family(selected_path: str) -> list[tuple[Path, dict[str, Any] | None, bool]]:
    selected = Path(selected_path)
    parsed_selected = _parse_epoch_stem(selected.stem)
    groups = _candidate_groups(selected.parent, selected.suffix)

    if parsed_selected:
        family_key = (parsed_selected["base"].casefold(), parsed_selected["kind"])
        numbered = groups.get(family_key, [])
        base_stem = parsed_selected["base"]
    else:
        eligible = [
            (key, values)
            for key, values in groups.items()
            if key[0] == selected.stem.casefold()
        ]
        if not eligible:
            return [(selected, None, False)]
        eligible.sort(key=lambda item: (-len(item[1]), _KIND_PRIORITY[item[0][1]]))
        family_key, numbered = eligible[0]
        base_stem = selected.stem

    members: list[tuple[Path, dict[str, Any] | None, bool]] = [
        (path, parsed, False) for path, parsed in numbered
    ]
    final_path = selected.parent / f"{base_stem}{selected.suffix}"
    if final_path.is_file():
        members.append((final_path, None, True))

    if not any(os.path.normcase(str(path)) == os.path.normcase(str(selected)) for path, _, _ in members):
        members.append((selected, parsed_selected, False))
    if len(members) < 2:
        return [(selected, parsed_selected, False)]

    members.sort(
        key=lambda item: (
            1 if item[2] else 0,
            int(item[1]["number"]) if item[1] else sys.maxsize,
            item[0].name.casefold(),
        )
    )
    return members


def inspect_lora(reference: object, folder_paths_module) -> dict[str, Any]:
    selected_path = _resolve_reference(reference, folder_paths_module)
    selected_case = os.path.normcase(selected_path)
    options: list[dict[str, Any]] = []
    selected_reference = ""
    for path, parsed, is_final in _select_epoch_family(selected_path):
        load_name, source = _reference_for_path(str(path), folder_paths_module)
        option = {
            "load_name": load_name,
            "absolute_path": str(path.resolve()).replace("\\", "/"),
            "filename": path.name,
            "display_name": path.stem,
            "label": _epoch_label(parsed, path.name, final=is_final),
            "epoch_kind": parsed["kind"] if parsed else ("final" if is_final else "single"),
            "epoch_number": parsed["number"] if parsed else None,
            "source": source,
        }
        if os.path.normcase(str(path.resolve())) == selected_case:
            selected_reference = load_name
        options.append(option)

    selected = next((item for item in options if item["load_name"] == selected_reference), options[0])
    return {
        "selected": selected,
        "options": options,
        "has_epochs": len(options) > 1,
    }


def _open_windows_lora_picker(initial_path: str = "") -> str:
    if os.name != "nt":
        raise RuntimeError("Load Lora PickerX native file selection is currently available on Windows only.")

    script = r"""
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Application]::EnableVisualStyles()
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'Select a LoRA file'
$dialog.Filter = 'LoRA files (*.safetensors;*.ckpt;*.pt;*.bin)|*.safetensors;*.ckpt;*.pt;*.bin|All files (*.*)|*.*'
$dialog.CheckFileExists = $true
$dialog.Multiselect = $false
$dialog.RestoreDirectory = $true
$initial = $env:WORKFLOWX_LORA_PICKER_INITIAL
if ($initial) {
    if (Test-Path -LiteralPath $initial -PathType Leaf) { $dialog.InitialDirectory = Split-Path -LiteralPath $initial -Parent }
    elseif (Test-Path -LiteralPath $initial -PathType Container) { $dialog.InitialDirectory = $initial }
}
$owner = New-Object System.Windows.Forms.Form
$owner.ShowInTaskbar = $false
$owner.TopMost = $true
$owner.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
$owner.Size = New-Object System.Drawing.Size(1, 1)
$owner.Opacity = 0
$owner.Show()
$owner.Activate()
if ($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::Out.Write($dialog.FileName)
}
$owner.Close()
$owner.Dispose()
$dialog.Dispose()
"""
    environment = os.environ.copy()
    environment["WORKFLOWX_LORA_PICKER_INITIAL"] = initial_path
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-STA", "-Command", script],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        creationflags=creation_flags,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "The Windows file picker failed."
        raise RuntimeError(detail)
    return result.stdout.strip()


def _is_loopback_request(request: Any) -> bool:
    remote = str(getattr(request, "remote", "") or "").strip()
    if remote.lower() == "localhost":
        return True
    try:
        address = ipaddress.ip_address(remote)
        if address.is_loopback:
            return True
        return bool(getattr(address, "ipv4_mapped", None) and address.ipv4_mapped.is_loopback)
    except ValueError:
        return False


def register_routes() -> None:
    try:
        from aiohttp import web
        import folder_paths
        from server import PromptServer
    except Exception:
        return

    prompt_server = getattr(PromptServer, "instance", None)
    if prompt_server is None or getattr(prompt_server, "_workflowx_load_lora_picker_x_routes", False):
        return

    @prompt_server.routes.post(PICK_ROUTE)
    async def pick_lora(request):
        if not _is_loopback_request(request):
            return web.json_response({"error": "The native LoRA picker is available only from this computer."}, status=403)
        try:
            payload = await request.json()
            current = payload.get("load_name", "") if isinstance(payload, dict) else ""
            try:
                initial_path = _resolve_reference(current, folder_paths) if current else ""
            except (FileNotFoundError, ValueError):
                initial_path = ""
            selected_path = await asyncio.to_thread(_open_windows_lora_picker, initial_path)
            if not selected_path:
                return web.json_response({"cancelled": True})
            result = await asyncio.to_thread(inspect_lora, selected_path, folder_paths)
            return web.json_response(result)
        except (FileNotFoundError, ValueError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except Exception as exc:
            return web.json_response({"error": f"Could not open the LoRA picker: {exc}"}, status=500)

    @prompt_server.routes.post(INSPECT_ROUTE)
    async def inspect_selected_lora(request):
        if not _is_loopback_request(request):
            return web.json_response({"error": "External LoRA inspection is available only from this computer."}, status=403)
        try:
            payload = await request.json()
            reference = payload.get("load_name") if isinstance(payload, dict) else None
            result = await asyncio.to_thread(inspect_lora, reference, folder_paths)
            return web.json_response(result)
        except (FileNotFoundError, ValueError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except Exception as exc:
            return web.json_response({"error": f"Could not inspect the LoRA: {exc}"}, status=500)

    prompt_server._workflowx_load_lora_picker_x_routes = True


class LoadLoraPickerX:
    DESCRIPTION = "Pick and stack LoRAs from any local path, with sibling training checkpoints selectable per row."
    CATEGORY = CATEGORY
    FUNCTION = "load_loras"
    RETURN_TYPES = ("MODEL", "CLIP", "STRING", "STRING")
    RETURN_NAMES = ("MODEL", "CLIP", "trigger_words", "loaded_loras")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        try:
            from comfy.comfy_types.node_typing import IO

            any_type = IO.ANY
        except Exception:
            any_type = "*"
        return {
            "required": {"model": ("MODEL",)},
            "optional": _FlexibleOptionalInputType(any_type, {"clip": ("CLIP",)}),
        }

    @staticmethod
    def _row_index(key: str) -> int:
        try:
            return int(str(key).rsplit("_", 1)[-1])
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _as_bool(value: Any, default: bool = True) -> bool:
        if value is None:
            return default
        if isinstance(value, str):
            return value.strip().lower() not in {"", "0", "false", "no", "off"}
        return bool(value)

    @staticmethod
    def _as_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _parse_row(cls, value: Any, row_number: int) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        if not cls._as_bool(value.get("on", value.get("enabled", True))):
            return None
        reference = _normalize_path(
            value.get("load_name") or value.get("loadName") or value.get("lora") or value.get("path")
        )
        if not reference or reference.lower() == "none":
            return None
        trigger_words = value.get("trigger_words", value.get("trained_words", []))
        if isinstance(trigger_words, str):
            trigger_words = [part.strip() for part in trigger_words.replace(",,", ",").split(",") if part.strip()]
        elif not isinstance(trigger_words, (list, tuple)):
            trigger_words = []
        return {
            "row_number": row_number,
            "load_name": reference,
            "display_name": str(value.get("display_name") or value.get("filename") or Path(reference).stem),
            "strength_model": cls._as_float(value.get("strength_model", value.get("model_strength", 1.0)), 1.0),
            "strength_clip": cls._as_float(value.get("strength_clip", value.get("clip_strength", 1.0)), 1.0),
            "trigger_words": [str(word).strip() for word in trigger_words if str(word).strip()],
        }

    @classmethod
    def _collect_rows(cls, kwargs: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        indexed = sorted(kwargs.items(), key=lambda item: cls._row_index(str(item[0])))
        for key, value in indexed:
            if not str(key).lower().startswith("lora_"):
                continue
            row_number = cls._row_index(str(key))
            row = cls._parse_row(value, row_number)
            if row:
                rows.append(row)
        return rows

    @classmethod
    def _resolve_path(cls, reference: str) -> str:
        try:
            import folder_paths
        except Exception as exc:
            raise RuntimeError("Load Lora PickerX could not import ComfyUI folder paths.") from exc
        return _resolve_reference(reference, folder_paths)

    @classmethod
    def IS_CHANGED(cls, model: Any = None, clip: Any = None, **kwargs: Any) -> str:
        del model, clip
        fingerprint: list[tuple[Any, ...]] = []
        for row in cls._collect_rows(kwargs):
            reference = row["load_name"]
            try:
                path = cls._resolve_path(reference)
                stat = os.stat(path)
                fingerprint.append((reference, os.path.normcase(path), stat.st_size, stat.st_mtime_ns))
            except (OSError, ValueError, RuntimeError):
                fingerprint.append((reference, "missing"))
        encoded = json.dumps(fingerprint, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def _load_row(cls, model: Any, clip: Any, row: dict[str, Any]) -> tuple[Any, Any]:
        try:
            import comfy.sd
            import comfy.utils
        except Exception as exc:
            raise RuntimeError("Load Lora PickerX could not import ComfyUI's LoRA loader.") from exc

        try:
            path = cls._resolve_path(row["load_name"])
        except (FileNotFoundError, ValueError) as exc:
            raise ValueError(f"Load Lora PickerX row {row['row_number']} could not load '{row['load_name']}': {exc}") from exc
        try:
            lora, metadata = comfy.utils.load_torch_file(path, safe_load=True, return_metadata=True)
        except TypeError:
            lora = comfy.utils.load_torch_file(path, safe_load=True)
            metadata = None
        except Exception as exc:
            raise RuntimeError(f"Load Lora PickerX row {row['row_number']} failed to read '{path}': {exc}") from exc

        clip_strength = row["strength_clip"] if clip is not None else 0.0
        return comfy.sd.load_lora_for_models(
            model,
            clip,
            lora,
            row["strength_model"],
            clip_strength,
            lora_metadata=metadata,
        )

    def load_loras(self, model: Any, clip: Any = None, **kwargs: Any) -> tuple[Any, Any, str, str]:
        loaded: list[str] = []
        trigger_words: list[str] = []
        for row in self._collect_rows(kwargs):
            if row["strength_model"] == 0 and row["strength_clip"] == 0:
                continue
            model, clip = self._load_row(model, clip, row)
            filename = Path(row["load_name"]).name
            loaded.append(
                f"{filename} (model={row['strength_model']:g}, clip={row['strength_clip']:g})"
            )
            trigger_words.extend(row["trigger_words"])
        return model, clip, ",, ".join(trigger_words), " | ".join(loaded)


NODE_CLASS_MAPPINGS = {NODE_ID: LoadLoraPickerX}
NODE_DISPLAY_NAME_MAPPINGS = {NODE_ID: "Load Lora PickerX"}
