from __future__ import annotations

from collections import OrderedDict
from fnmatch import fnmatchcase
import os
from pathlib import Path, PurePosixPath
import threading
from typing import Callable, Iterable

from .workflowx_paths import activate_workflowx_ffmpeg, comfyui_root


REPO_ID = "haslam/WorkflowX-DL"
REVISION = "main"
PLUGIN_PREFIX = "custom_nodes/WorkflowX-Configurator"

CATEGORY_PATTERNS: OrderedDict[str, tuple[str, ...]] = OrderedDict(
    (
        ("dlss5", (
            f"{PLUGIN_PREFIX}/detailer_x/assets/dlss5/**",
            f"{PLUGIN_PREFIX}/detailer_x/vendor/dlss/native/bin/**",
        )),
        ("luts", (f"{PLUGIN_PREFIX}/detailer_x/assets/luts/**",)),
        ("neural_grain", (f"{PLUGIN_PREFIX}/detailer_x/assets/neural_grain/**",)),
        ("sam_models", (f"{PLUGIN_PREFIX}/detailer_x/assets/sams/**",)),
        ("detectors", (f"{PLUGIN_PREFIX}/detailer_x/assets/ultralytics/**",)),
        ("upscalers", (f"{PLUGIN_PREFIX}/detailer_x/assets/upscale_models/**",)),
        ("ffmpeg", (f"{PLUGIN_PREFIX}/vendor/ffmpeg/**",)),
        ("llama_cpp", (f"{PLUGIN_PREFIX}/vendor/llama.cpp/**",)),
        ("sam3", ("models/checkpoints/sam3.1_multiplex_fp16.safetensors",)),
        ("auk", (
            "models/diffusion_models/auk_base_bf16.safetensors",
            "models/text_encoders/qwen_omni_bf16.safetensors",
            "models/vae/auk_vae.safetensors",
        )),
    )
)

CATEGORY_LABELS = {
    "dlss5": "DLSS 5 runtime",
    "luts": "DetailerX LUTs",
    "neural_grain": "Neural Grain",
    "sam_models": "SAM and SAM 2.1",
    "detectors": "Ultralytics detectors",
    "upscalers": "DetailerX upscaler",
    "ffmpeg": "WorkflowX FFmpeg",
    "llama_cpp": "llama.cpp runtime",
    "sam3": "SAM3 checkpoint",
    "auk": "AuK models",
}

_DOWNLOAD_LOCK = threading.Lock()


def selected_categories(download_all: bool, choices: dict[str, object]) -> tuple[str, ...]:
    if download_all:
        return tuple(CATEGORY_PATTERNS)
    return tuple(name for name in CATEGORY_PATTERNS if bool(choices.get(name, False)))


def patterns_for(categories: Iterable[str]) -> tuple[str, ...]:
    patterns: list[str] = []
    for category in categories:
        for pattern in CATEGORY_PATTERNS[category]:
            if pattern not in patterns:
                patterns.append(pattern)
    return tuple(patterns)


def _safe_repo_files(files: Iterable[str]) -> list[str]:
    safe: list[str] = []
    for filename in files:
        normalized = str(filename).replace("\\", "/")
        path = PurePosixPath(normalized)
        if path.is_absolute() or ".." in path.parts:
            raise RuntimeError(f"Unsafe path returned by {REPO_ID}: {filename!r}")
        if normalized != ".gitattributes":
            safe.append(normalized)
    return safe


def matching_repo_files(files: Iterable[str], patterns: Iterable[str]) -> list[str]:
    allowed = tuple(patterns)
    return sorted(
        filename
        for filename in _safe_repo_files(files)
        if any(fnmatchcase(filename, pattern) for pattern in allowed)
    )


def _activate_downloaded_ffmpeg(root: Path) -> str | None:
    path = activate_workflowx_ffmpeg(root, force=True)
    if not path:
        return None
    try:
        from . import save_video_x

        save_video_x.ffmpeg_path = path
    except Exception:
        pass
    return path


def download_categories(
    root: Path,
    categories: tuple[str, ...],
    *,
    force_download: bool = False,
    max_workers: int = 4,
    list_repo_files_fn: Callable[..., list[str]] | None = None,
    snapshot_download_fn: Callable[..., str] | None = None,
) -> str:
    if not categories:
        raise ValueError("Select at least one category or enable Download all.")

    try:
        if list_repo_files_fn is None or snapshot_download_fn is None:
            from huggingface_hub import HfApi, snapshot_download

            list_repo_files_fn = list_repo_files_fn or HfApi().list_repo_files
            snapshot_download_fn = snapshot_download_fn or snapshot_download
    except ImportError as exc:
        raise RuntimeError(
            "WorkflowX Downloader requires huggingface-hub. Install WorkflowX dependencies "
            "and restart ComfyUI."
        ) from exc

    root = Path(root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    patterns = patterns_for(categories)
    repo_files = list_repo_files_fn(
        repo_id=REPO_ID,
        repo_type="model",
        revision=REVISION,
        token=os.environ.get("HF_TOKEN") or None,
    )
    matched = matching_repo_files(repo_files, patterns)
    if not matched:
        raise RuntimeError("The selected categories did not match any repository files.")

    with _DOWNLOAD_LOCK:
        snapshot_download_fn(
            repo_id=REPO_ID,
            repo_type="model",
            revision=REVISION,
            local_dir=str(root),
            allow_patterns=matched,
            force_download=bool(force_download),
            max_workers=max(1, min(int(max_workers), 16)),
            token=os.environ.get("HF_TOKEN") or None,
        )

    missing = [filename for filename in matched if not (root / Path(filename)).is_file()]
    if missing:
        preview = ", ".join(missing[:3])
        suffix = "" if len(missing) <= 3 else f" (+{len(missing) - 3} more)"
        raise RuntimeError(f"Download finished with {len(missing)} missing files: {preview}{suffix}")

    ffmpeg_path = _activate_downloaded_ffmpeg(root) if "ffmpeg" in categories else None
    labels = ", ".join(CATEGORY_LABELS[name] for name in categories)
    status = [
        f"WorkflowX download complete: {len(matched)} files verified.",
        f"Categories: {labels}.",
        f"ComfyUI root: {root}",
    ]
    if ffmpeg_path:
        status.append(f"WorkflowX FFmpeg active: {ffmpeg_path}")
    return "\n".join(status)


class WorkflowXDownloader:
    @classmethod
    def INPUT_TYPES(cls):
        category_inputs = {
            name: (
                "BOOLEAN",
                {"default": False, "label_on": "download", "label_off": "skip"},
            )
            for name in CATEGORY_PATTERNS
        }
        return {
            "required": {
                "download_all": (
                    "BOOLEAN",
                    {"default": False, "label_on": "all categories", "label_off": "selected only"},
                ),
                **category_inputs,
                "force_download": (
                    "BOOLEAN",
                    {"default": False, "label_on": "replace", "label_off": "reuse existing"},
                ),
                "max_workers": ("INT", {"default": 4, "min": 1, "max": 16, "step": 1}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("status",)
    FUNCTION = "download"
    CATEGORY = "WorkflowX/Utilities"
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(cls, **_kwargs):
        return float("nan")

    def download(
        self,
        download_all=False,
        force_download=False,
        max_workers=4,
        **choices,
    ):
        categories = selected_categories(bool(download_all), choices)
        status = download_categories(
            comfyui_root(),
            categories,
            force_download=bool(force_download),
            max_workers=int(max_workers),
        )
        return (status,)


NODE_CLASS_MAPPINGS = {"WorkflowX_Downloader": WorkflowXDownloader}
NODE_DISPLAY_NAME_MAPPINGS = {"WorkflowX_Downloader": "WorkflowX Downloader"}


__all__ = [
    "CATEGORY_LABELS",
    "CATEGORY_PATTERNS",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "REPO_ID",
    "REVISION",
    "WorkflowXDownloader",
    "download_categories",
    "matching_repo_files",
    "patterns_for",
    "selected_categories",
]
