from __future__ import annotations

import os
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
FFMPEG_ENV = "WORKFLOWX_FORCE_FFMPEG_PATH"


def comfyui_root(folder_paths_module=None) -> Path:
    """Return the active ComfyUI root without assuming the launch directory."""
    module = folder_paths_module
    if module is None:
        try:
            import folder_paths as module  # type: ignore
        except Exception:
            module = None

    configured = getattr(module, "base_path", None) if module is not None else None
    if configured:
        return Path(configured).expanduser().resolve()
    return PACKAGE_ROOT.parents[1]


def bundled_ffmpeg_candidates(root: Path | None = None) -> tuple[Path, ...]:
    """Return supported WorkflowX FFmpeg locations, most specific first."""
    filename = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    active_package = PACKAGE_ROOT / "vendor" / "ffmpeg" / filename
    explicit_root = root is not None
    canonical_package = (
        (root or comfyui_root())
        / "custom_nodes"
        / "WorkflowX-Configurator"
        / "vendor"
        / "ffmpeg"
        / filename
    )
    if active_package == canonical_package:
        return (active_package,)
    if explicit_root:
        return (canonical_package, active_package)
    return (active_package, canonical_package)


def activate_workflowx_ffmpeg(
    root: Path | None = None, *, force: bool = False
) -> str | None:
    """Expose the bundled FFmpeg to every WorkflowX subsystem in this process."""
    existing = os.environ.get(FFMPEG_ENV)
    if not force and existing and Path(existing).is_file():
        return existing

    executable = next((path for path in bundled_ffmpeg_candidates(root) if path.is_file()), None)
    if executable is None:
        return existing if existing and Path(existing).is_file() else None

    resolved = str(executable.resolve())
    os.environ[FFMPEG_ENV] = resolved

    vendor_dir = str(executable.parent.resolve())
    path_entries = [entry for entry in os.environ.get("PATH", "").split(os.pathsep) if entry]
    normalized = {os.path.normcase(os.path.abspath(entry)) for entry in path_entries}
    if os.path.normcase(os.path.abspath(vendor_dir)) not in normalized:
        os.environ["PATH"] = os.pathsep.join([vendor_dir, *path_entries])
    return resolved


__all__ = [
    "FFMPEG_ENV",
    "PACKAGE_ROOT",
    "activate_workflowx_ffmpeg",
    "bundled_ffmpeg_candidates",
    "comfyui_root",
]
