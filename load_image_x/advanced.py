"""Independent backend for the WorkflowX Load ImageX Adv node."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

import numpy as np
import torch
from PIL import Image, ImageOps, ImageSequence

from .runtime import get_catalog, resolve_annotated_image_path


DEFAULT_ADV_STATE: dict[str, Any] = {
    "version": 1,
    "mode": "off",
    "max_mp": 1.0,
    "longest_side": 1024,
    "scale_factor": 1.0,
    "fit_w": 1024,
    "fit_h": 1024,
    "cover_w": 1024,
    "cover_h": 1024,
    "cover_action": "fill",
    "crop_anchor": "center",
    "ratio_preset": "1:1",
    "ratio_w": 1.0,
    "ratio_h": 1.0,
    "pad_color": "#808080",
    "pad_top": 0,
    "pad_bottom": 0,
    "pad_left": 0,
    "pad_right": 0,
    "output_snap": 0,
    "resample": "auto",
    "allow_upscale": False,
    "crop_enabled": False,
    "crop_snap": 0,
    "crop_rect": None,
}

VALID_MODES = {
    "off",
    "max_mp",
    "longest_side",
    "scale_factor",
    "fit_inside",
    "cover",
    "match_ratio",
    "pad",
}
VALID_RESAMPLE = {"auto", "nearest", "bilinear", "bicubic", "lanczos"}
VALID_SNAPS = {0, 8, 16, 32, 64}
VALID_ANCHORS = {
    "top-left",
    "top",
    "top-right",
    "left",
    "center",
    "right",
    "bottom-left",
    "bottom",
    "bottom-right",
}


def parse_adv_state(value: object) -> dict[str, Any]:
    """Parse node state while accepting older or partially saved workflows."""
    state = dict(DEFAULT_ADV_STATE)
    try:
        parsed = json.loads(str(value or ""))
    except (TypeError, ValueError, json.JSONDecodeError):
        return state
    if not isinstance(parsed, dict):
        return state
    for key in DEFAULT_ADV_STATE:
        if key in parsed:
            state[key] = parsed[key]

    if state["mode"] not in VALID_MODES:
        state["mode"] = "off"
    if state["resample"] not in VALID_RESAMPLE:
        state["resample"] = "auto"
    for key in ("output_snap", "crop_snap"):
        try:
            snap = int(state[key])
        except (TypeError, ValueError):
            snap = 0
        state[key] = snap if snap in VALID_SNAPS else 0
    if state["crop_anchor"] not in VALID_ANCHORS:
        state["crop_anchor"] = "center"
    if state["cover_action"] not in {"fill", "crop"}:
        state["cover_action"] = "fill"
    state["allow_upscale"] = bool(state["allow_upscale"])
    state["crop_enabled"] = bool(state["crop_enabled"])
    if not isinstance(state["crop_rect"], dict):
        state["crop_rect"] = None
    return state


def _number(value: object, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if math.isfinite(number) else fallback


def _round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def _bounded_dimension(value: object, fallback: int = 1024) -> int:
    return max(8, min(_round_half_up(_number(value, fallback)), 16384))


def _snap_down(value: int, snap: int) -> int:
    if snap <= 0:
        return value
    return max(8, (int(value) // snap) * snap)


def _snap_nearest(value: int, snap: int, limit: int) -> int:
    if snap <= 0:
        return max(1, min(value, limit))
    if limit < snap:
        return limit
    snapped = max(snap, _round_half_up(value / snap) * snap)
    return min(snapped, (limit // snap) * snap)


def crop_box_from_state(width: int, height: int, state: dict[str, Any]) -> tuple[int, int, int, int] | None:
    """Resolve the normalized crop rectangle to a bounded source-pixel box."""
    if not state.get("crop_enabled"):
        return None
    rect = state.get("crop_rect")
    if not isinstance(rect, dict):
        return None
    try:
        x = max(0.0, min(1.0, float(rect["x"])))
        y = max(0.0, min(1.0, float(rect["y"])))
        w = max(0.0, min(1.0 - x, float(rect["w"])))
        h = max(0.0, min(1.0 - y, float(rect["h"])))
    except (KeyError, TypeError, ValueError):
        return None
    if w <= 0.0 or h <= 0.0:
        return None

    x0 = max(0, min(width - 1, _round_half_up(x * width)))
    y0 = max(0, min(height - 1, _round_half_up(y * height)))
    x1 = max(x0 + 1, min(width, _round_half_up((x + w) * width)))
    y1 = max(y0 + 1, min(height, _round_half_up((y + h) * height)))

    snap = int(state.get("crop_snap", 0) or 0)
    crop_w = _snap_nearest(x1 - x0, snap, width)
    crop_h = _snap_nearest(y1 - y0, snap, height)
    x0 = min(x0, width - crop_w)
    y0 = min(y0, height - crop_h)
    return x0, y0, x0 + crop_w, y0 + crop_h


def _anchor_offset(anchor: str, outer_w: int, outer_h: int, inner_w: int, inner_h: int) -> tuple[int, int]:
    if "left" in anchor:
        x = 0
    elif "right" in anchor:
        x = outer_w - inner_w
    else:
        x = (outer_w - inner_w) // 2
    if "top" in anchor:
        y = 0
    elif "bottom" in anchor:
        y = outer_h - inner_h
    else:
        y = (outer_h - inner_h) // 2
    return max(0, x), max(0, y)


def _image_resample(name: str, factor: float):
    table = {
        "nearest": Image.Resampling.NEAREST,
        "bilinear": Image.Resampling.BILINEAR,
        "bicubic": Image.Resampling.BICUBIC,
        "lanczos": Image.Resampling.LANCZOS,
    }
    if name in table:
        return table[name]
    return Image.Resampling.LANCZOS if factor < 1.0 else Image.Resampling.BILINEAR


def _resize_pair(
    image: Image.Image,
    mask: Image.Image,
    width: int,
    height: int,
    state: dict[str, Any],
) -> tuple[Image.Image, Image.Image]:
    width = max(1, min(int(width), 16384))
    height = max(1, min(int(height), 16384))
    if image.size == (width, height):
        return image, mask
    factor = min(width / image.width, height / image.height)
    return (
        image.resize((width, height), _image_resample(str(state["resample"]), factor)),
        mask.resize((width, height), Image.Resampling.NEAREST),
    )


def _parse_color(value: object) -> tuple[int, int, int]:
    text = str(value or "").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(character * 2 for character in text)
    try:
        if len(text) == 6:
            return tuple(int(text[index:index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        pass
    return 128, 128, 128


def _apply_output_snap(
    image: Image.Image,
    mask: Image.Image,
    state: dict[str, Any],
) -> tuple[Image.Image, Image.Image]:
    snap = int(state.get("output_snap", 0) or 0)
    width = _snap_down(image.width, snap)
    height = _snap_down(image.height, snap)
    return _resize_pair(image, mask, width, height, state)


def apply_resize_mode(
    image: Image.Image,
    mask: Image.Image,
    state: dict[str, Any],
) -> tuple[Image.Image, Image.Image]:
    """Apply the selected resize mode, then the independent output snap."""
    mode = str(state.get("mode", "off"))
    width, height = image.size
    allow_upscale = bool(state.get("allow_upscale"))

    if mode == "max_mp":
        target_mp = max(0.01, min(_number(state.get("max_mp"), 1.0), 64.0))
        factor = math.sqrt((target_mp * 1024 * 1024) / max(1, width * height))
        if not allow_upscale:
            factor = min(factor, 1.0)
        factor = min(factor, 8.0)
        image, mask = _resize_pair(
            image,
            mask,
            _round_half_up(width * factor),
            _round_half_up(height * factor),
            state,
        )
    elif mode == "longest_side":
        target = _bounded_dimension(state.get("longest_side"))
        factor = target / max(width, height)
        if not allow_upscale:
            factor = min(factor, 1.0)
        factor = min(factor, 8.0)
        image, mask = _resize_pair(
            image,
            mask,
            _round_half_up(width * factor),
            _round_half_up(height * factor),
            state,
        )
    elif mode == "scale_factor":
        factor = max(0.01, min(_number(state.get("scale_factor"), 1.0), 8.0))
        if not allow_upscale:
            factor = min(factor, 1.0)
        image, mask = _resize_pair(
            image,
            mask,
            _round_half_up(width * factor),
            _round_half_up(height * factor),
            state,
        )
    elif mode == "fit_inside":
        target_w = _bounded_dimension(state.get("fit_w"))
        target_h = _bounded_dimension(state.get("fit_h"))
        factor = min(target_w / width, target_h / height)
        if not allow_upscale:
            factor = min(factor, 1.0)
        factor = min(factor, 8.0)
        image, mask = _resize_pair(
            image,
            mask,
            _round_half_up(width * factor),
            _round_half_up(height * factor),
            state,
        )
    elif mode == "cover":
        target_w = _bounded_dimension(state.get("cover_w"))
        target_h = _bounded_dimension(state.get("cover_h"))
        anchor = str(state.get("crop_anchor", "center"))
        if state.get("cover_action") == "crop":
            crop_w = min(target_w, width)
            crop_h = min(target_h, height)
            left, top = _anchor_offset(anchor, width, height, crop_w, crop_h)
            image = image.crop((left, top, left + crop_w, top + crop_h))
            mask = mask.crop((left, top, left + crop_w, top + crop_h))
        else:
            factor = max(target_w / width, target_h / height)
            if not allow_upscale and factor > 1.0:
                factor = min(target_w / width, target_h / height, 1.0)
                image, mask = _resize_pair(
                    image,
                    mask,
                    _round_half_up(width * factor),
                    _round_half_up(height * factor),
                    state,
                )
            else:
                factor = min(factor, 8.0)
                scaled_w = _round_half_up(width * factor)
                scaled_h = _round_half_up(height * factor)
                image, mask = _resize_pair(image, mask, scaled_w, scaled_h, state)
                left, top = _anchor_offset(anchor, scaled_w, scaled_h, target_w, target_h)
                image = image.crop((left, top, left + target_w, top + target_h))
                mask = mask.crop((left, top, left + target_w, top + target_h))
    elif mode == "match_ratio":
        ratio_w = max(0.01, _number(state.get("ratio_w"), 1.0))
        ratio_h = max(0.01, _number(state.get("ratio_h"), 1.0))
        target_ratio = ratio_w / ratio_h
        current_ratio = width / height
        if current_ratio > target_ratio:
            crop_w = max(1, _round_half_up(height * target_ratio))
            crop_h = height
        else:
            crop_w = width
            crop_h = max(1, _round_half_up(width / target_ratio))
        left = max(0, (width - crop_w) // 2)
        top = max(0, (height - crop_h) // 2)
        image = image.crop((left, top, left + crop_w, top + crop_h))
        mask = mask.crop((left, top, left + crop_w, top + crop_h))
    elif mode == "pad":
        top = max(0, min(int(_number(state.get("pad_top"), 0)), 8192))
        bottom = max(0, min(int(_number(state.get("pad_bottom"), 0)), 8192))
        left = max(0, min(int(_number(state.get("pad_left"), 0)), 8192))
        right = max(0, min(int(_number(state.get("pad_right"), 0)), 8192))
        new_w = min(16384, width + left + right)
        new_h = min(16384, height + top + bottom)
        left = min(left, new_w - width)
        top = min(top, new_h - height)
        padded_image = Image.new("RGB", (new_w, new_h), _parse_color(state.get("pad_color")))
        padded_mask = Image.new("L", (new_w, new_h), 255)
        padded_image.paste(image, (left, top))
        padded_mask.paste(mask, (left, top))
        image, mask = padded_image, padded_mask

    return _apply_output_snap(image, mask, state)


def process_frame(
    frame: Image.Image,
    state: dict[str, Any],
) -> tuple[Image.Image, Image.Image]:
    oriented = ImageOps.exif_transpose(frame.copy())
    if oriented.mode == "I":
        oriented = oriented.point(lambda pixel: pixel * (1 / 255))
    image = oriented.convert("RGB")
    if "A" in oriented.getbands():
        alpha = np.asarray(oriented.getchannel("A")).astype(np.float32) / 255.0
        mask = Image.fromarray(((1.0 - alpha) * 255).astype(np.uint8), mode="L")
    elif oriented.mode == "P" and "transparency" in oriented.info:
        alpha = np.asarray(oriented.convert("RGBA").getchannel("A")).astype(np.float32) / 255.0
        mask = Image.fromarray(((1.0 - alpha) * 255).astype(np.uint8), mode="L")
    else:
        mask = Image.new("L", image.size, 0)

    crop_box = crop_box_from_state(image.width, image.height, state)
    if crop_box is not None:
        image = image.crop(crop_box)
        mask = mask.crop(crop_box)
    return apply_resize_mode(image, mask, state)


class LoadImageXAdv:
    DESCRIPTION = (
        "Load an image through WorkflowX Browse Thumbnails, optionally crop it "
        "interactively, and apply predictable resize, snap, resample, and padding controls."
    )

    @classmethod
    def INPUT_TYPES(cls):
        items, _etag = get_catalog()
        return {
            "required": {
                "image": (
                    [item["path"] for item in items],
                    {
                        "tooltip": "Selected through the WorkflowX thumbnail browser.",
                        "image_upload": True,
                    },
                ),
                "workflowx_state": (
                    "STRING",
                    {
                        "default": json.dumps(DEFAULT_ADV_STATE, separators=(",", ":")),
                        "multiline": False,
                    },
                ),
            }
        }

    CATEGORY = "WorkflowX/Image Loader"
    RETURN_TYPES = ("IMAGE", "MASK", "MASK", "INT", "INT")
    RETURN_NAMES = ("image", "mask", "inverted_mask", "width", "height")
    OUTPUT_TOOLTIPS = (
        "Processed image batch.",
        "Processed alpha/padding mask.",
        "One minus the processed mask.",
        "Final output width in pixels.",
        "Final output height in pixels.",
    )
    FUNCTION = "load_image"

    def load_image(self, image: str, workflowx_state: str = ""):
        _relative, image_path = resolve_annotated_image_path(image)
        state = parse_adv_state(workflowx_state)
        output_images = []
        output_masks = []
        output_inverted_masks = []
        first_size: tuple[int, int] | None = None
        final_size: tuple[int, int] | None = None

        with Image.open(image_path) as opened:
            for source_frame in ImageSequence.Iterator(opened):
                oriented = ImageOps.exif_transpose(source_frame.copy())
                if first_size is None:
                    first_size = oriented.size
                if oriented.size != first_size:
                    continue
                processed, mask = process_frame(source_frame, state)
                image_array = np.asarray(processed).astype(np.float32) / 255.0
                mask_array = np.asarray(mask).astype(np.float32) / 255.0
                output_images.append(torch.from_numpy(image_array).unsqueeze(0))
                mask_tensor = torch.from_numpy(mask_array).unsqueeze(0)
                output_masks.append(mask_tensor)
                output_inverted_masks.append(1.0 - mask_tensor)
                final_size = processed.size
                if opened.format == "MPO":
                    break

        if not output_images:
            raise ValueError(f"Image contains no loadable frames: {image}")
        if final_size is None:
            raise ValueError(f"Image contains no loadable frames: {image}")
        width, height = final_size
        if len(output_images) == 1:
            return output_images[0], output_masks[0], output_inverted_masks[0], width, height
        return (
            torch.cat(output_images, dim=0),
            torch.cat(output_masks, dim=0),
            torch.cat(output_inverted_masks, dim=0),
            width,
            height,
        )

    @classmethod
    def IS_CHANGED(cls, image: str, workflowx_state: str = ""):
        _relative, image_path = resolve_annotated_image_path(image)
        digest = hashlib.sha256()
        with image_path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        digest.update(str(workflowx_state or "").encode("utf-8"))
        return digest.hexdigest()

    @classmethod
    def VALIDATE_INPUTS(cls, image: str, workflowx_state: str = ""):
        del workflowx_state
        try:
            _relative, image_path = resolve_annotated_image_path(image)
        except ValueError as exc:
            return str(exc)
        if not image_path.is_file():
            return f"Invalid image file: {image}"
        return True


NODE_CLASS_MAPPINGS = {"WorkflowX_LoadImageXAdv": LoadImageXAdv}
NODE_DISPLAY_NAME_MAPPINGS = {"WorkflowX_LoadImageXAdv": "Load ImageX Adv"}


__all__ = [
    "DEFAULT_ADV_STATE",
    "LoadImageXAdv",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "apply_resize_mode",
    "crop_box_from_state",
    "parse_adv_state",
    "process_frame",
]
