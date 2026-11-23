"""Temporary Stage 1 captures for Load ImageX Adv."""

from __future__ import annotations

import asyncio
import io
import re
import shutil
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import folder_paths
import torch
from aiohttp import web
from PIL import Image

from .direct import store_direct_image


SOURCE_NODE_ID = "WorkflowX_ImageXSource"
SOURCE_ROUTE = "/workflowx_configurator/load_image_x/source"


class CaptureChanged(Exception):
    pass


@dataclass(frozen=True)
class Capture:
    directory: Path
    version: str
    count: int

    def frame(self, index: int) -> Path:
        return self.directory / f"{index}.png"


def source_key(workflow_id, node_id):
    workflow_id = str(workflow_id or "")
    node_id = str(node_id if node_id is not None else "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", workflow_id) or not re.fullmatch(r"[0-9]{1,32}", node_id):
        raise ValueError("ImageX Source requires a workflow ID and a source on the main workflow canvas.")
    return workflow_id, node_id


class SourceCaptures:
    def __init__(self):
        self.lock = threading.Lock()
        self.latest = {}

    def publish(self, key, images):
        if images.ndim != 4 or len(images) == 0 or images.shape[-1] not in (1, 3, 4):
            raise ValueError("ImageX Source needs a non-empty batch of ComfyUI images.")
        temp = Path(folder_paths.get_temp_directory()).resolve()
        root = temp / "workflowx_image_x_sources"
        if not root.resolve().is_relative_to(temp):
            raise ValueError("ImageX Source storage escapes ComfyUI temp.")
        root.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(dir=root))
        capture = Capture(directory, uuid4().hex, len(images))
        try:
            for index, frame in enumerate(images):
                pixels = frame.detach().to(device="cpu", dtype=torch.float32)
                pixels = (pixels.clamp(0, 1) * 255).round().to(torch.uint8).numpy()
                if pixels.shape[-1] == 1:
                    pixels = pixels[..., 0]
                Image.fromarray(pixels).save(capture.frame(index), format="PNG", compress_level=1)
            with self.lock:
                previous = self.latest.get(key)
                self.latest[key] = capture
        except BaseException:
            shutil.rmtree(directory, ignore_errors=True)
            raise
        if previous is not None:
            shutil.rmtree(previous.directory, ignore_errors=True)

    def _get(self, key, version=None):
        capture = self.latest.get(key)
        if capture is None or not capture.directory.is_dir():
            raise FileNotFoundError("No temporary capture is available. Run Stage 1 with this ImageX Source, then refresh.")
        if version is not None and capture.version != version:
            raise CaptureChanged("Stage 1 has a newer capture. Choose a frame from the updated batch.")
        return capture

    def describe(self, key):
        with self.lock:
            capture = self._get(key)
            if not capture.frame(0).is_file():
                raise FileNotFoundError("The temporary capture is missing. Run Stage 1 again, then refresh.")
            return {"version": capture.version, "count": capture.count}

    def _frame(self, key, version, index):
        capture = self._get(key, version)
        if not 0 <= index < capture.count:
            raise ValueError("Invalid ImageX Source frame.")
        frame = capture.frame(index)
        if not frame.is_file():
            raise FileNotFoundError("The temporary frame is missing. Run Stage 1 again, then refresh.")
        return frame

    def thumbnail(self, key, version, index):
        with self.lock, Image.open(self._frame(key, version, index)) as image:
            image.thumbnail((192, 192), Image.Resampling.LANCZOS)
            with io.BytesIO() as out:
                image.save(out, format="PNG")
                return out.getvalue()

    def copy(self, key, version, index, slot):
        with self.lock, self._frame(key, version, index).open("rb") as source:
            return store_direct_image(source, slot, folder_paths.get_temp_directory())


captures = SourceCaptures()


class ImageXSource:
    CATEGORY = "WorkflowX/Image Loader"
    FUNCTION = "capture"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    OUTPUT_NODE = True
    DESCRIPTION = "Capture the latest Stage 1 image or batch for manual refresh in Load ImageX Adv."

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"image": ("IMAGE",)},
            "hidden": {"unique_id": "UNIQUE_ID", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    @classmethod
    def IS_CHANGED(cls, **_kwargs):
        return float("nan")

    def capture(self, image, unique_id=None, extra_pnginfo=None):
        workflow = (extra_pnginfo or {}).get("workflow") or {}
        captures.publish(source_key(workflow.get("id"), unique_id), image)
        return (image,)


def register_source_routes(router):
    async def request_capture(request):
        try:
            if request.method == "POST":
                data = await request.json()
                if not isinstance(data, dict):
                    raise ValueError("Invalid ImageX Source request.")
            else:
                data = request.query
            key = source_key(data.get("workflow"), data.get("source"))
            if request.path.endswith("/thumbnail") or request.method == "POST":
                version = data.get("version")
                if not isinstance(version, str) or not re.fullmatch(r"[a-f0-9]{32}", version):
                    raise ValueError("Invalid ImageX Source capture version.")
                index = int(str(data.get("frame", "")))
                if request.method == "POST":
                    result = await asyncio.to_thread(captures.copy, key, version, index, data.get("slot") or "")
                    return web.json_response(result)
                body = await asyncio.to_thread(captures.thumbnail, key, version, index)
                return web.Response(body=body, content_type="image/png", headers={"Cache-Control": "no-store"})
            result = await asyncio.to_thread(captures.describe, key)
            return web.json_response(result, headers={"Cache-Control": "no-store"})
        except CaptureChanged as exc:
            return web.json_response({"error": str(exc)}, status=409)
        except FileNotFoundError as exc:
            return web.json_response({"error": str(exc)}, status=404)
        except (ValueError, TypeError, OSError, Image.DecompressionBombError) as exc:
            return web.json_response({"error": f"ImageX Source refresh failed: {exc}"}, status=400)

    router.add_get(SOURCE_ROUTE, request_capture)
    router.add_get(f"{SOURCE_ROUTE}/thumbnail", request_capture)
    router.add_post(SOURCE_ROUTE, request_capture)
