"""Structured DetailerX stage bundles and their dedicated preview output node."""
from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path


PROCESSOR_IMAGES_TYPE = "DETAILERX_PROCESSOR_IMAGES"
BUNDLE_VERSION = 1

STAGE_LABELS = {
    "upscaler": "Upscaler",
    "face": "Face detailer",
    "breast": "Breast detailer",
    "pussy": "Pussy detailer",
    "hand": "Hand detailer",
    "foot": "Foot detailer",
    "hair": "Hair detailer",
    "anything": "Anything detailer",
    "brightness": "Brightness / Contrast",
    "grain": "Grain",
    "hsv": "HSV",
    "levels": "Levels",
    "sharpen": "Lucy Sharpen",
    "rgb": "RGB",
    "gamma": "Gamma",
    "color_balance": "Color Balance",
    "temperature": "Kelvin White Balance",
    "lens": "Lens Optic Axis",
    "pixel_perturb": "Pixel Perturb",
    "neural_grain": "Neural Grain",
    "lut": "LUT",
    "camera": "Camera Simulator",
    "compression": "Multi-Compression",
    "dlss5": "DLSS5",
}


def _copy_image(image):
    return image.detach().cpu().clone()


def stage_label(name, settings=None):
    if isinstance(settings, dict) and settings.get("label"):
        return str(settings["label"])
    if name.startswith("detailer:"):
        return name.split(":", 1)[1].replace("_", " ").title()
    return STAGE_LABELS.get(name, name.replace("_", " ").title())


def make_bundle(original, stages=(), bypass_reason=None):
    """Create an immutable, process-local bundle consumed by DetailerX Preview."""
    original_copy = _copy_image(original)
    items = []
    for item in stages:
        items.append({
            "id": str(item["id"]),
            "name": str(item["name"]),
            "state": str(item.get("state", "processed")),
            "image": _copy_image(item["image"]),
        })
    return {
        "type": PROCESSOR_IMAGES_TYPE,
        "version": BUNDLE_VERSION,
        "original": original_copy,
        "stages": items,
        "bypass_reason": str(bypass_reason or ""),
    }


def validate_bundle(bundle):
    import torch
    if not isinstance(bundle, dict) or bundle.get("type") != PROCESSOR_IMAGES_TYPE:
        raise ValueError("DetailerX Preview requires the processor_images output from DetailerX")
    if bundle.get("version") != BUNDLE_VERSION:
        raise ValueError(f"Unsupported DetailerX processor bundle version: {bundle.get('version')}")
    original = bundle.get("original")
    if not isinstance(original, torch.Tensor) or original.ndim != 4 or original.shape[-1] not in (3, 4):
        raise ValueError("DetailerX processor bundle has an invalid original image batch")
    stages = bundle.get("stages")
    if not isinstance(stages, list):
        raise ValueError("DetailerX processor bundle has an invalid stage list")
    for item in stages:
        image = item.get("image") if isinstance(item, dict) else None
        if not isinstance(image, torch.Tensor) or image.ndim != 4 or image.shape[-1] not in (3, 4):
            raise ValueError("DetailerX processor bundle contains an invalid stage image batch")
        if image.shape[0] != original.shape[0]:
            raise ValueError("DetailerX processor bundle stages must preserve the original batch size")
    return bundle


def _save_batch(batch, directory, stem, folder_paths):
    import numpy as np
    from PIL import Image
    descriptors = []
    for index, tensor in enumerate(batch):
        array = (tensor.detach().cpu().clamp(0, 1).numpy() * 255.0).round().astype(np.uint8)
        mode = "RGBA" if array.shape[-1] == 4 else "RGB"
        filename = f"{stem}_{index:03d}.png"
        Image.fromarray(array, mode=mode).save(directory / filename, format="PNG", compress_level=1)
        descriptors.append({
            "filename": filename,
            "subfolder": directory.relative_to(Path(folder_paths.get_temp_directory())).as_posix(),
            "type": "temp",
        })
    return descriptors


class DetailerXPreview:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"processor_images": (PROCESSOR_IMAGES_TYPE,)},
                "hidden": {"unique_id": "UNIQUE_ID"}}

    RETURN_TYPES = ()
    FUNCTION = "preview"
    CATEGORY = "WorkflowX/Image"
    OUTPUT_NODE = True
    DESCRIPTION = "Browse named DetailerX processor snapshots and compare each stage with the original or previous stage."

    def preview(self, processor_images, unique_id=None):
        import folder_paths
        bundle = validate_bundle(processor_images)
        root = Path(folder_paths.get_temp_directory()) / "workflowx_detailer_preview"
        node_key = hashlib.sha256(str(unique_id or "preview").encode("utf-8")).hexdigest()[:16]
        node_dir = root / node_key
        if node_dir.exists():
            shutil.rmtree(node_dir)
        node_dir.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex[:12]
        original = _save_batch(bundle["original"], node_dir, f"{token}_original", folder_paths)
        stages = []
        previous = original
        for index, item in enumerate(bundle["stages"]):
            current = _save_batch(item["image"], node_dir, f"{token}_{index:03d}", folder_paths)
            stages.append({
                "id": item["id"], "name": item["name"], "state": item["state"],
                "images": current, "previous": previous,
            })
            previous = current
        payload = {
            "version": BUNDLE_VERSION,
            "original": original,
            "stages": stages,
            "batch_count": len(original),
            "bypass_reason": bundle.get("bypass_reason", ""),
        }
        return {"ui": {"workflowx_detailer_preview": [payload]}}
