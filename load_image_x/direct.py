"""Replaceable, original-byte temporary image slots for Load ImageX Adv."""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from aiohttp import web
from PIL import Image, ImageSequence


def store_direct_image(source, slot: str, temp_root) -> dict:
    if not re.fullmatch(r"[a-f0-9]{32}", slot):
        raise ValueError("Invalid temporary image slot")
    root = Path(temp_root).resolve()
    directory = root / "workflowx_load_image_x_adv" / slot
    if not directory.resolve().is_relative_to(root):
        raise ValueError("Temporary image directory escapes ComfyUI temp")
    directory.mkdir(parents=True, exist_ok=True)
    # Extensionless: PIL detects the actual format; changing formats leaves no leftovers.
    target = directory / "image"
    pending = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".upload-", delete=False) as handle:
            pending = Path(handle.name)
            source.seek(0)
            while chunk := source.read(1024 * 1024):
                handle.write(chunk)
        with Image.open(pending) as image:
            image.verify()
        with Image.open(pending) as image:
            for frame in ImageSequence.Iterator(image):
                frame.load()
        os.replace(pending, target)
    finally:
        if pending is not None:
            pending.unlink(missing_ok=True)
    return {"name": "image", "subfolder": directory.relative_to(root).as_posix(), "type": "temp"}


async def direct_upload_handler(request):
    import folder_paths
    try:
        post = await request.post()
        upload = post.get("image")
        if not isinstance(upload, web.FileField):
            raise ValueError("Choose, drop, or paste an image")
        result = store_direct_image(upload.file, str(post.get("slot", "")), folder_paths.get_temp_directory())
        return web.json_response(result)
    except (ValueError, OSError, Image.DecompressionBombError) as exc:
        return web.json_response({"error": f"Direct upload failed: {exc}"}, status=400)
