"""Backend implementation for the WorkflowX Load ImageX node and picker."""

from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image, ImageOps, ImageSequence, UnidentifiedImageError

import folder_paths


CATALOG_TTL_SECONDS = 5.0
THUMBNAIL_SIZE = (128, 128)
THUMBNAIL_QUALITY = 76
THUMBNAIL_FORMAT_VERSION = "load-image-x-jpeg-v1"
CACHE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60

_catalog_lock = threading.RLock()
_catalog_items: list[dict[str, Any]] = []
_catalog_etag = ""
_catalog_expires_at = 0.0
_thumbnail_locks: dict[str, asyncio.Lock] = {}
_prune_started = False


def _is_within(root: Path, candidate: Path) -> bool:
    try:
        return os.path.commonpath((str(root), str(candidate))) == str(root)
    except ValueError:
        return False


def normalize_relative_path(value: object) -> str:
    """Return a safe, POSIX-style path relative to ComfyUI's input root."""
    raw = str(value or "").replace("\\", "/").strip()
    if not raw or raw.startswith("/") or "\x00" in raw:
        raise ValueError("Invalid image path")
    drive, _tail = os.path.splitdrive(raw)
    parts = raw.split("/")
    if drive or any(part in ("", ".", "..") for part in parts):
        raise ValueError("Invalid image path")
    if parts[-1].endswith(("[input]", "[output]", "[temp]")):
        raise ValueError("Annotated paths are not supported")
    return "/".join(parts)


def resolve_input_path(value: object, folder_paths_module=None) -> tuple[str, Path]:
    if folder_paths_module is None:
        folder_paths_module = folder_paths
    relative = normalize_relative_path(value)
    root = Path(folder_paths_module.get_input_directory()).resolve()
    candidate = (root / Path(*relative.split("/"))).resolve()
    if not _is_within(root, candidate):
        raise ValueError("Image path escapes the ComfyUI input directory")
    return relative, candidate


def _version_for(relative: str, stat_result: os.stat_result) -> str:
    payload = (
        f"{THUMBNAIL_FORMAT_VERSION}\0{relative}\0"
        f"{stat_result.st_size}\0{stat_result.st_mtime_ns}"
    ).encode("utf-8", "surrogatepass")
    return hashlib.sha256(payload).hexdigest()[:24]


def build_catalog(folder_paths_module=None) -> tuple[list[dict[str, Any]], str]:
    """Recursively scan input/ and return image metadata plus a stable ETag."""
    if folder_paths_module is None:
        folder_paths_module = folder_paths
    root = Path(folder_paths_module.get_input_directory()).resolve()
    if not root.is_dir():
        return [], hashlib.sha256(b"").hexdigest()

    candidates: list[str] = []
    for current, directories, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        directories[:] = sorted(
            directory
            for directory in directories
            if not (current_path / directory).is_symlink()
        )
        for filename in filenames:
            source = current_path / filename
            try:
                resolved = source.resolve()
            except OSError:
                continue
            if not source.is_file() or not _is_within(root, resolved):
                continue
            candidates.append(source.relative_to(root).as_posix())

    image_paths = folder_paths_module.filter_files_content_types(candidates, ["image"])
    items: list[dict[str, Any]] = []
    for relative in image_paths:
        try:
            normalized, source = resolve_input_path(relative, folder_paths_module)
            stat_result = source.stat()
        except (OSError, ValueError):
            continue
        folder, separator, name = normalized.rpartition("/")
        items.append(
            {
                "path": normalized,
                "name": name if separator else normalized,
                "folder": folder if separator else "",
                "version": _version_for(normalized, stat_result),
            }
        )

    items.sort(key=lambda item: (item["path"].casefold(), item["path"]))
    digest = hashlib.sha256()
    for item in items:
        digest.update(item["path"].encode("utf-8", "surrogatepass"))
        digest.update(b"\0")
        digest.update(item["version"].encode("ascii"))
        digest.update(b"\0")
    return items, digest.hexdigest()


def get_catalog(force: bool = False) -> tuple[list[dict[str, Any]], str]:
    global _catalog_items, _catalog_etag, _catalog_expires_at
    now = time.monotonic()
    with _catalog_lock:
        if not force and _catalog_etag and now < _catalog_expires_at:
            return [dict(item) for item in _catalog_items], _catalog_etag

    items, etag = build_catalog()
    with _catalog_lock:
        _catalog_items = [dict(item) for item in items]
        _catalog_etag = etag
        _catalog_expires_at = time.monotonic() + CATALOG_TTL_SECONDS
    return [dict(item) for item in items], etag


def invalidate_catalog() -> None:
    global _catalog_expires_at
    with _catalog_lock:
        _catalog_expires_at = 0.0


def thumbnail_cache_dir(folder_paths_module=None) -> Path:
    if folder_paths_module is None:
        folder_paths_module = folder_paths
    base = Path(folder_paths_module.get_user_directory())
    return base / "workflowx" / "cache" / "load_image_x"


def thumbnail_cache_path(relative: str, stat_result: os.stat_result, folder_paths_module=None) -> Path:
    if folder_paths_module is None:
        folder_paths_module = folder_paths
    version = _version_for(relative, stat_result)
    key = hashlib.sha256(f"{relative}\0{version}".encode("utf-8", "surrogatepass")).hexdigest()
    return thumbnail_cache_dir(folder_paths_module) / f"{key}.jpg"


def generate_thumbnail(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with Image.open(source) as opened:
            frame = ImageOps.exif_transpose(opened.copy())
            resampling = getattr(Image, "Resampling", Image).LANCZOS
            frame.thumbnail(THUMBNAIL_SIZE, resampling)
            if "A" in frame.getbands() or (
                frame.mode == "P" and "transparency" in frame.info
            ):
                rgba = frame.convert("RGBA")
                background = Image.new("RGB", rgba.size, (30, 30, 30))
                background.paste(rgba, mask=rgba.getchannel("A"))
                thumbnail = background
            else:
                thumbnail = frame.convert("RGB")

            with tempfile.NamedTemporaryFile(
                prefix="load_image_x_",
                suffix=".tmp",
                dir=destination.parent,
                delete=False,
            ) as temporary:
                temporary_name = temporary.name
            thumbnail.save(
                temporary_name,
                format="JPEG",
                quality=THUMBNAIL_QUALITY,
                optimize=True,
            )
        os.replace(temporary_name, destination)
        temporary_name = None
    finally:
        if temporary_name:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass


def prune_thumbnail_cache(folder_paths_module=None, now: float | None = None) -> int:
    if folder_paths_module is None:
        folder_paths_module = folder_paths
    cache_dir = thumbnail_cache_dir(folder_paths_module)
    if not cache_dir.is_dir():
        return 0
    cutoff = (time.time() if now is None else now) - CACHE_MAX_AGE_SECONDS
    removed = 0
    for candidate in cache_dir.glob("*.jpg"):
        try:
            if candidate.stat().st_mtime < cutoff:
                candidate.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def _start_prune() -> None:
    global _prune_started
    if _prune_started:
        return
    _prune_started = True
    try:
        asyncio.create_task(asyncio.to_thread(prune_thumbnail_cache))
    except RuntimeError:
        _prune_started = False


class LoadImageX:
    DESCRIPTION = (
        "Load an image from ComfyUI input/ or any nested input folder. "
        "Use Browse Thumbnails for a searchable, cached folder grid."
    )

    @classmethod
    def INPUT_TYPES(cls):
        items, _etag = get_catalog()
        return {
            "required": {
                "image": (
                    [item["path"] for item in items],
                    {
                        "image_upload": True,
                        "tooltip": "Image from ComfyUI input/ or one of its subfolders.",
                    },
                )
            }
        }

    CATEGORY = "WorkflowX_Configurator/Image"
    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "mask")
    FUNCTION = "load_image"

    def load_image(self, image: str):
        _relative, image_path = resolve_input_path(image)
        with Image.open(image_path) as opened:
            output_images = []
            output_masks = []
            first_size: tuple[int, int] | None = None

            for source_frame in ImageSequence.Iterator(opened):
                frame = ImageOps.exif_transpose(source_frame.copy())
                if frame.mode == "I":
                    frame = frame.point(lambda pixel: pixel * (1 / 255))
                rgb = frame.convert("RGB")
                if first_size is None:
                    first_size = rgb.size
                if rgb.size != first_size:
                    continue

                image_array = np.asarray(rgb).astype(np.float32) / 255.0
                output_images.append(torch.from_numpy(image_array).unsqueeze(0))

                if "A" in frame.getbands():
                    alpha = np.asarray(frame.getchannel("A")).astype(np.float32) / 255.0
                    mask = 1.0 - torch.from_numpy(alpha)
                elif frame.mode == "P" and "transparency" in frame.info:
                    alpha = np.asarray(frame.convert("RGBA").getchannel("A")).astype(np.float32) / 255.0
                    mask = 1.0 - torch.from_numpy(alpha)
                else:
                    mask = torch.zeros((rgb.height, rgb.width), dtype=torch.float32)
                output_masks.append(mask.unsqueeze(0))

                if opened.format == "MPO":
                    break

        if not output_images:
            raise ValueError(f"Image contains no loadable frames: {image}")
        if len(output_images) == 1:
            return output_images[0], output_masks[0]
        return torch.cat(output_images, dim=0), torch.cat(output_masks, dim=0)

    @classmethod
    def IS_CHANGED(cls, image: str):
        _relative, image_path = resolve_input_path(image)
        digest = hashlib.sha256()
        with image_path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    @classmethod
    def VALIDATE_INPUTS(cls, image: str):
        try:
            _relative, image_path = resolve_input_path(image)
        except ValueError as exc:
            return str(exc)
        if not image_path.is_file():
            return f"Invalid image file: {image}"
        return True


async def catalog_handler(request):
    force = str(request.rel_url.query.get("refresh", "")).lower() in {"1", "true", "yes"}
    items, etag = await asyncio.to_thread(get_catalog, force)
    quoted_etag = f'"{etag}"'
    headers = {"Cache-Control": "no-cache", "ETag": quoted_etag}
    if request.headers.get("If-None-Match") == quoted_etag:
        from aiohttp import web

        return web.Response(status=304, headers=headers)

    _start_prune()
    from aiohttp import web

    return web.json_response({"items": items, "total": len(items)}, headers=headers)


async def thumbnail_handler(request):
    from aiohttp import web

    requested_path = request.rel_url.query.get("path", "")
    try:
        relative, source = resolve_input_path(requested_path)
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=400)
    if not source.is_file():
        return web.json_response({"error": "Image not found"}, status=404)

    try:
        stat_result = await asyncio.to_thread(source.stat)
    except OSError:
        return web.json_response({"error": "Image not found"}, status=404)
    version = _version_for(relative, stat_result)
    requested_version = request.rel_url.query.get("v", "")
    if requested_version and requested_version != version:
        return web.json_response({"error": "Image changed; refresh the catalog"}, status=409)

    cache_path = thumbnail_cache_path(relative, stat_result)
    lock_key = str(cache_path)
    lock = _thumbnail_locks.get(lock_key)
    if lock is None:
        lock = _thumbnail_locks[lock_key] = asyncio.Lock()

    try:
        async with lock:
            if not cache_path.is_file():
                await asyncio.to_thread(generate_thumbnail, source, cache_path)
        payload = await asyncio.to_thread(cache_path.read_bytes)
    except (OSError, UnidentifiedImageError, ValueError):
        return web.json_response({"error": "Unable to create thumbnail"}, status=415)

    _start_prune()
    return web.Response(
        body=payload,
        content_type="image/jpeg",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": f'"{version}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


NODE_CLASS_MAPPINGS = {"WorkflowX_LoadImageX": LoadImageX}
NODE_DISPLAY_NAME_MAPPINGS = {"WorkflowX_LoadImageX": "Load ImageX"}


__all__ = [
    "LoadImageX",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "build_catalog",
    "catalog_handler",
    "generate_thumbnail",
    "get_catalog",
    "normalize_relative_path",
    "prune_thumbnail_cache",
    "resolve_input_path",
    "thumbnail_cache_path",
    "thumbnail_handler",
]
