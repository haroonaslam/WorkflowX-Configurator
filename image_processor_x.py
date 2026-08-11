from __future__ import annotations

import asyncio
import base64
import io
import json
import math
import os
import random
import re
import tempfile
import uuid
from dataclasses import dataclass
from typing import Any


NODE_TYPE = "WorkflowX_ImageProcessorX"
DISPLAY_NAME = "Image ProcessorX"
CATEGORY = "WorkflowX/Image Compare"
EVENT_NAME = "workflowx.image_processor_x.pause"
ROUTE_ROOT = "/workflowx_configurator/image_processor_x"

NEUTRAL = {
    "brightness": 0.0,
    "contrast": 0.0,
    "exposure": 0.0,
    "highlights": 0.0,
    "shadows": 0.0,
    "whites": 0.0,
    "blacks": 0.0,
    "saturation": 0.0,
    "vibrance": 0.0,
    "temperature": 0.0,
    "tint": 0.0,
    "hue": 0.0,
    "sharpness": 0.0,
    "clarity": 0.0,
    "grain": 0.0,
    "vignette": 0.0,
    "fade": 0.0,
}
CURVE_IDENTITY = [[0, 0], [255, 255]]
LR = 0.2126
LG = 0.7152
LB = 0.0722


def _clamp(value: Any, minimum: float, maximum: float, fallback: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = fallback
    if not math.isfinite(number):
        number = fallback
    return max(minimum, min(maximum, number))


def _round_js(values):
    import numpy as np

    return np.floor(np.asarray(values) + 0.5)


def _merge_adjustments(value: Any) -> dict[str, float]:
    source = value if isinstance(value, dict) else {}
    result = dict(NEUTRAL)
    for key in result:
        result[key] = _clamp(source.get(key, 0), -180 if key == "hue" else -100, 180 if key == "hue" else 100)
    for key in ("sharpness", "grain", "vignette", "fade"):
        result[key] = _clamp(source.get(key, 0), 0, 100)
    return result


def _normalize_curve_points(points: Any) -> list[list[int]]:
    if isinstance(points, str):
        try:
            points = json.loads(points)
        except (TypeError, ValueError):
            points = CURVE_IDENTITY
    if not isinstance(points, list):
        points = CURVE_IDENTITY
    by_x: dict[int, list[int]] = {}
    for point in points:
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            px, py = point[0], point[1]
        elif isinstance(point, dict):
            px, py = point.get("x"), point.get("y")
        else:
            continue
        try:
            x = int(math.floor(_clamp(px, 0, 255) + 0.5))
            y = int(math.floor(_clamp(py, 0, 255) + 0.5))
        except (TypeError, ValueError):
            continue
        by_x[x] = [x, y]
    result = sorted(by_x.values())
    if not result:
        return [point[:] for point in CURVE_IDENTITY]
    if len(result) == 1:
        if result[0][0] <= 127:
            result.append([255, 255])
        else:
            result.insert(0, [0, 0])
    return result


def _normalize_curve(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    channels_source = source.get("channels", source.get("curves", source))
    if not isinstance(channels_source, dict):
        channels_source = {}
    channels = {
        key: _normalize_curve_points(channels_source.get(key, CURVE_IDENTITY))
        for key in ("RGB", "R", "G", "B")
    }
    return {
        "enabled": bool(source.get("enabled", False)),
        "channel": source.get("channel") if source.get("channel") in ("RGB", "R", "G", "B") else "RGB",
        "interpolation": "linear" if source.get("interpolation") == "linear" else "cubic",
        "strength": _clamp(source.get("strength", 100), 0, 200, 100),
        "channels": channels,
    }


def _identity_curve(points: Any) -> bool:
    normalized = _normalize_curve_points(points)
    return normalized == CURVE_IDENTITY


def _curve_neutral(curve: dict[str, Any]) -> bool:
    return curve["strength"] <= 0 or all(_identity_curve(curve["channels"][key]) for key in ("RGB", "R", "G", "B"))


def _normalize_layer(value: Any, index: int) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        "id": str(value.get("id") or f"adj_{index + 1}"),
        "name": str(value.get("name") or f"Adjustment {index + 1}"),
        "visible": value.get("visible") is not False,
        "maskVisible": value.get("maskVisible") is not False,
        "mode": "brush" if value.get("mode") == "brush" else "global",
        "amount": _clamp(value.get("amount", 1), 0, 1, 1),
        "preset": str(value.get("preset") or "Original"),
        "adjustments": _merge_adjustments(value.get("adjustments")),
        "curve": _normalize_curve(value.get("curve", value.get("curves"))),
        "maskData": str(value.get("maskData") or ""),
    }


def parse_processor_state(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        source: dict[str, Any] = {}
    elif isinstance(value, str):
        try:
            source = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Image ProcessorX processor_state is invalid JSON: {exc}") from exc
    elif isinstance(value, dict):
        source = value
    else:
        raise ValueError("Image ProcessorX processor_state must be a JSON object.")
    if not isinstance(source, dict):
        raise ValueError("Image ProcessorX processor_state must be a JSON object.")

    schema_version = source.get("schemaVersion", 1)
    if schema_version != 1:
        raise ValueError(f"Image ProcessorX does not support processor_state schemaVersion {schema_version!r}.")

    layers_source = source.get("adjustmentLayers")
    layers = []
    if isinstance(layers_source, list):
        for index, layer in enumerate(layers_source):
            normalized = _normalize_layer(layer, index)
            if normalized is not None:
                layers.append(normalized)

    if not layers and any(key in source for key in ("adjustments", "adjustmentMode", "adjustmentBrushData")):
        legacy = _normalize_layer(
            {
                "id": "adj_legacy_1",
                "name": "Adjustment 1",
                "mode": source.get("adjustmentMode"),
                "amount": source.get("adjustmentAmount", 1),
                "preset": source.get("adjustmentPreset", "Original"),
                "adjustments": source.get("adjustments"),
                "maskData": source.get("adjustmentBrushData", ""),
            },
            0,
        )
        if legacy is not None:
            layers.append(legacy)

    return {
        "schemaVersion": 1,
        "layerOrder": "1over2" if source.get("layerOrder") == "1over2" else "2over1",
        "topOpacity": _clamp(source.get("topOpacity", 0.65), 0, 1, 0.65),
        "maskData": str(source.get("maskData") or ""),
        "adjustmentLayers": layers,
    }


def _layer_neutral(layer: dict[str, Any]) -> bool:
    if not layer["visible"] or layer["amount"] <= 0:
        return True
    return all(value == 0 for value in layer["adjustments"].values()) and _curve_neutral(layer["curve"])


def _hue_matrix(degrees: float):
    import numpy as np

    angle = degrees * math.pi / 180
    c = math.cos(angle)
    s = math.sin(angle)
    return np.asarray(
        [
            [0.213 + c * 0.787 - s * 0.213, 0.715 - c * 0.715 - s * 0.715, 0.072 - c * 0.072 + s * 0.928],
            [0.213 - c * 0.213 + s * 0.143, 0.715 + c * 0.285 + s * 0.14, 0.072 - c * 0.072 - s * 0.283],
            [0.213 - c * 0.213 - s * 0.787, 0.715 - c * 0.715 + s * 0.715, 0.072 + c * 0.928 + s * 0.072],
        ],
        dtype=np.float32,
    )


def _box_blur_edge(channel):
    import numpy as np

    padded = np.pad(channel, ((1, 1), (1, 1)), mode="edge")
    result = np.zeros_like(channel, dtype=np.float32)
    for dy in range(3):
        for dx in range(3):
            result += padded[dy : dy + channel.shape[0], dx : dx + channel.shape[1]]
    return result / 9.0


def _apply_fx(rgba, adjustments: dict[str, float], amount: float, seed: int = 4517):
    import numpy as np

    if amount <= 0 or all(value == 0 for value in adjustments.values()):
        return rgba
    original = rgba[..., :3].astype(np.float32) / 255.0
    rgb = original.copy()
    lum = LR * rgb[..., 0] + LG * rgb[..., 1] + LB * rgb[..., 2]
    target = lum.copy()
    tone_on = any(adjustments[key] for key in ("exposure", "brightness", "contrast", "blacks", "shadows", "highlights", "whites"))
    if tone_on:
        if adjustments["exposure"]:
            target *= 2 ** (adjustments["exposure"] / 100)
        if adjustments["brightness"]:
            target += adjustments["brightness"] / 200
        if adjustments["contrast"]:
            target = (target - 0.5) * (1 + adjustments["contrast"] / 100) + 0.5
        if adjustments["blacks"]:
            target += (adjustments["blacks"] / 100) * 0.5 * np.clip(1 - 2 * target, 0, 1)
        if adjustments["shadows"]:
            target += (adjustments["shadows"] / 100) * 0.5 * (1 - target) ** 2
        if adjustments["highlights"]:
            target += (adjustments["highlights"] / 100) * 0.5 * target**2
        if adjustments["whites"]:
            target += (adjustments["whites"] / 100) * 0.5 * np.clip(2 * target - 1, 0, 1)
        gain = np.clip(target / np.maximum(lum, 1e-4), 0, 4)
        rgb *= gain[..., None]

    if adjustments["temperature"]:
        offset = adjustments["temperature"] / 100 * 0.1
        rgb[..., 0] += offset
        rgb[..., 2] -= offset
    if adjustments["tint"]:
        rgb[..., 1] += adjustments["tint"] / 100 * 0.1
    if adjustments["saturation"]:
        lum = LR * rgb[..., 0] + LG * rgb[..., 1] + LB * rgb[..., 2]
        rgb = lum[..., None] + (rgb - lum[..., None]) * (1 + adjustments["saturation"] / 100)
    if adjustments["vibrance"]:
        maximum = rgb.max(axis=2)
        minimum = rgb.min(axis=2)
        saturation = np.where(maximum <= 0, 0, (maximum - minimum) / np.maximum(maximum, 1e-12))
        vibrance = adjustments["vibrance"] / 100 * (1 - saturation)
        lum = LR * rgb[..., 0] + LG * rgb[..., 1] + LB * rgb[..., 2]
        rgb = lum[..., None] + (rgb - lum[..., None]) * (1 + vibrance[..., None])
    if adjustments["hue"]:
        rgb = rgb @ _hue_matrix(adjustments["hue"]).T
    if adjustments["clarity"]:
        lum = LR * rgb[..., 0] + LG * rgb[..., 1] + LB * rgb[..., 2]
        middle = 1 - np.abs(2 * lum - 1)
        target = (lum - 0.5) * (1 + adjustments["clarity"] / 100 * 0.5 * middle) + 0.5
        rgb *= np.clip(target / np.maximum(lum, 1e-4), 0, 4)[..., None]
    if adjustments["sharpness"]:
        strength = adjustments["sharpness"] / 100
        for channel in range(3):
            current = rgb[..., channel]
            rgb[..., channel] = current + strength * (current - _box_blur_edge(current))

    height, width = rgb.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width]
    if adjustments["grain"]:
        phase = xx * 12.9898 + yy * 78.233 + seed * 37.719
        hashed = np.sin(phase) * 43758.5453
        hashed -= np.floor(hashed)
        noise = (hashed - 0.5) * adjustments["grain"] / 100 * 0.2
        rgb += noise[..., None]
    if adjustments["vignette"]:
        dx = (xx + 0.5) / width - 0.5
        dy = (yy + 0.5) / height - 0.5
        radius = np.sqrt(dx * dx + dy * dy) / 0.70710678
        vignette = np.clip((radius - 0.5) / 0.5, 0, 1)
        factor = 1 - adjustments["vignette"] / 100 * vignette**2
        rgb *= factor[..., None]
    if adjustments["fade"]:
        multiplier = 1 - adjustments["fade"] / 100 * 0.15
        offset = adjustments["fade"] / 100 * 0.1
        rgb = rgb * multiplier + offset

    mixed = original * (1 - amount) + np.clip(rgb, 0, 1) * amount
    rgba[..., :3] = np.clip(_round_js(mixed * 255), 0, 255).astype(np.uint8)
    return rgba


def _curve_with_bounds(points: Any) -> list[list[int]]:
    result = [point[:] for point in _normalize_curve_points(points)]
    if result[0][0] > 0:
        result.insert(0, [0, result[0][1]])
    if result[-1][0] < 255:
        result.append([255, result[-1][1]])
    return result


def _natural_spline(points: list[list[int]]):
    count = len(points)
    if count < 3:
        return None
    h = [max(1e-6, points[index + 1][0] - points[index][0]) for index in range(count - 1)]
    alpha = [0.0] * count
    lower = [0.0] * count
    mu = [0.0] * count
    z = [0.0] * count
    c = [0.0] * count
    b = [0.0] * (count - 1)
    d = [0.0] * (count - 1)
    for index in range(1, count - 1):
        alpha[index] = 3 / h[index] * (points[index + 1][1] - points[index][1]) - 3 / h[index - 1] * (points[index][1] - points[index - 1][1])
    lower[0] = 1
    for index in range(1, count - 1):
        lower[index] = 2 * (points[index + 1][0] - points[index - 1][0]) - h[index - 1] * mu[index - 1]
        mu[index] = h[index] / max(1e-6, lower[index])
        z[index] = (alpha[index] - h[index - 1] * z[index - 1]) / max(1e-6, lower[index])
    lower[-1] = 1
    for index in range(count - 2, -1, -1):
        c[index] = z[index] - mu[index] * c[index + 1]
        b[index] = (points[index + 1][1] - points[index][1]) / h[index] - h[index] * (c[index + 1] + 2 * c[index]) / 3
        d[index] = (c[index + 1] - c[index]) / (3 * h[index])
    return b, c, d


def _curve_lut(points: Any, interpolation: str):
    import numpy as np

    normalized = _curve_with_bounds(points)
    if _identity_curve(normalized):
        return np.arange(256, dtype=np.uint8)
    coefficients = None if interpolation == "linear" or len(normalized) < 3 else _natural_spline(normalized)
    values = []
    segment = 0
    for x in range(256):
        while segment < len(normalized) - 2 and x > normalized[segment + 1][0]:
            segment += 1
        if x <= normalized[0][0]:
            value = normalized[0][1]
        elif x >= normalized[-1][0]:
            value = normalized[-1][1]
        elif coefficients is None:
            span = max(1e-6, normalized[segment + 1][0] - normalized[segment][0])
            fraction = (x - normalized[segment][0]) / span
            value = normalized[segment][1] + fraction * (normalized[segment + 1][1] - normalized[segment][1])
        else:
            b, c, d = coefficients
            delta = x - normalized[segment][0]
            value = normalized[segment][1] + b[segment] * delta + c[segment] * delta**2 + d[segment] * delta**3
        values.append(max(0, min(255, math.floor(value + 0.5))))
    return np.asarray(values, dtype=np.uint8)


def _apply_curves(rgba, curve: dict[str, Any], amount: float):
    import numpy as np

    strength = _clamp(curve["strength"] / 100 * amount, 0, 2)
    if strength <= 0 or _curve_neutral(curve):
        return rgba
    original = rgba[..., :3].copy()
    changed = original.copy()
    channels = curve["channels"]
    if not _identity_curve(channels["RGB"]):
        lut = _curve_lut(channels["RGB"], curve["interpolation"])
        changed = lut[changed]
    for index, key in enumerate(("R", "G", "B")):
        if not _identity_curve(channels[key]):
            lut = _curve_lut(channels[key], curve["interpolation"])
            changed[..., index] = lut[changed[..., index]]
    result = original.astype(np.float32) + (changed.astype(np.float32) - original) * strength
    rgba[..., :3] = np.clip(_round_js(result), 0, 255).astype(np.uint8)
    return rgba


def _decode_mask(data_url: str, width: int, height: int):
    import numpy as np
    from PIL import Image

    if not data_url:
        return np.zeros((height, width), dtype=np.float32)
    payload = data_url.strip()
    if "," in payload:
        header, payload = payload.split(",", 1)
        if "base64" not in header.lower():
            raise ValueError("Image ProcessorX mask data must be base64 encoded.")
    try:
        raw = base64.b64decode(payload, validate=True)
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception as exc:
        raise ValueError("Image ProcessorX mask data is not a valid image.") from exc
    if image.mode in ("RGBA", "LA"):
        alpha = image.getchannel("A")
    else:
        alpha = image.convert("L")
    if alpha.size != (width, height):
        alpha = alpha.resize((width, height), Image.Resampling.BILINEAR)
    return np.asarray(alpha, dtype=np.float32) / 255.0


def _frame_uint8(frame: Any):
    import numpy as np

    value = frame.detach() if hasattr(frame, "detach") else frame
    value = value.cpu() if hasattr(value, "cpu") else value
    value = value.numpy() if hasattr(value, "numpy") else np.asarray(value)
    array = np.asarray(value)
    if array.ndim != 3 or array.shape[2] < 3:
        raise ValueError("Image ProcessorX expected IMAGE tensors with HxWxC frames.")
    if array.dtype.kind == "f":
        array = array * 255.0
    return np.clip(_round_js(array[..., :3]), 0, 255).astype(np.uint8)


def _rgba(rgb):
    import numpy as np

    alpha = np.full((*rgb.shape[:2], 1), 255, dtype=np.uint8)
    return np.concatenate((rgb.copy(), alpha), axis=2)


def _aspect_fit_rgba(rgb, width: int, height: int, opacity: float):
    import numpy as np
    from PIL import Image

    source_height, source_width = rgb.shape[:2]
    scale = min(width / source_width, height / source_height)
    resized_width = max(1, int(math.floor(source_width * scale + 0.5)))
    resized_height = max(1, int(math.floor(source_height * scale + 0.5)))
    resized = Image.fromarray(rgb, "RGB").resize((resized_width, resized_height), Image.Resampling.BILINEAR)
    canvas = np.zeros((height, width, 4), dtype=np.uint8)
    x = int(math.floor((width - resized_width) / 2 + 0.5))
    y = int(math.floor((height - resized_height) / 2 + 0.5))
    canvas[y : y + resized_height, x : x + resized_width, :3] = np.asarray(resized)
    canvas[y : y + resized_height, x : x + resized_width, 3] = int(math.floor(_clamp(opacity, 0, 1) * 255 + 0.5))
    return canvas


def _source_over(under, top):
    import numpy as np

    alpha = top[..., 3:4].astype(np.float32) / 255.0
    result = top[..., :3].astype(np.float32) * alpha + under[..., :3].astype(np.float32) * (1 - alpha)
    output = under.copy()
    output[..., :3] = np.clip(_round_js(result), 0, 255).astype(np.uint8)
    output[..., 3] = 255
    return output


def _compose_pair(image1, image2, state: dict[str, Any]):
    import numpy as np

    rgb1 = _frame_uint8(image1)
    if image2 is None:
        output = _rgba(rgb1)
    else:
        rgb2 = _frame_uint8(image2)
        if state["layerOrder"] == "1over2":
            top, under = rgb1, rgb2
        else:
            top, under = rgb2, rgb1
        height, width = under.shape[:2]
        output = _rgba(under)
        top_rgba = _aspect_fit_rgba(top, width, height, state["topOpacity"])
        blend_mask = _decode_mask(state["maskData"], width, height)
        top_rgba[..., 3] = np.clip(_round_js(top_rgba[..., 3].astype(np.float32) * (1 - blend_mask)), 0, 255).astype(np.uint8)
        output = _source_over(output, top_rgba)

    height, width = output.shape[:2]
    # The editor stores the visually highest adjustment at index 0 and
    # composites from the bottom of the stack upward.
    for layer in reversed(state["adjustmentLayers"]):
        if _layer_neutral(layer):
            continue
        adjusted = output.copy()
        _apply_fx(adjusted, layer["adjustments"], layer["amount"], 4517)
        _apply_curves(adjusted, layer["curve"], layer["amount"])
        if layer["mode"] == "brush":
            mask = _decode_mask(layer["maskData"], width, height)[..., None]
            mixed = adjusted[..., :3].astype(np.float32) * mask + output[..., :3].astype(np.float32) * (1 - mask)
            output[..., :3] = np.clip(_round_js(mixed), 0, 255).astype(np.uint8)
        else:
            output = adjusted
    return output[..., :3]


def _batch_size(image: Any) -> int:
    shape = getattr(image, "shape", ())
    if len(shape) == 3:
        return 1
    if len(shape) == 4 and int(shape[0]) > 0:
        return int(shape[0])
    raise ValueError("Image ProcessorX expected a non-empty IMAGE tensor batch.")


def _frame(image: Any, index: int):
    return image if len(getattr(image, "shape", ())) == 3 else image[index]


def render_o3(image1: Any, image2: Any | None, processor_state: Any):
    import numpy as np
    import torch

    state = parse_processor_state(processor_state)
    count1 = _batch_size(image1)
    count2 = _batch_size(image2) if image2 is not None else 0
    if image2 is None:
        pairs = [(index, None) for index in range(count1)]
    elif count1 == count2:
        pairs = [(index, index) for index in range(count1)]
    elif count1 == 1:
        pairs = [(0, index) for index in range(count2)]
    elif count2 == 1:
        pairs = [(index, 0) for index in range(count1)]
    else:
        raise ValueError(f"Image ProcessorX cannot pair image batches of size {count1} and {count2}; sizes must match or one must be 1.")

    if image2 is None and all(_layer_neutral(layer) for layer in state["adjustmentLayers"]):
        return image1

    rendered = [_compose_pair(_frame(image1, first), None if second is None else _frame(image2, second), state) for first, second in pairs]
    shapes = {item.shape for item in rendered}
    if len(shapes) != 1:
        raise ValueError("Image ProcessorX produced inconsistent frame sizes and cannot form an IMAGE batch.")
    array = np.stack(rendered).astype(np.float32) / 255.0
    return torch.from_numpy(array)


def _folder_paths_module():
    try:
        import folder_paths
    except Exception:
        return None
    return folder_paths


def _tensor_to_pil(tensor: Any):
    from PIL import Image

    return Image.fromarray(_frame_uint8(_frame(tensor, 0)), "RGB")


def _save_temp_refs(images: list[Any]) -> list[dict[str, str]]:
    folder_paths = _folder_paths_module()
    output_dir = str(folder_paths.get_temp_directory()) if folder_paths is not None else tempfile.gettempdir()
    prefix = "workflowx_image_processor_x_" + "".join(random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(8))
    if folder_paths is not None:
        full_folder, filename, counter, subfolder, _ = folder_paths.get_save_image_path(prefix, output_dir, images[0].width, images[0].height)
    else:
        full_folder, filename, counter, subfolder = output_dir, prefix, 1, ""
    os.makedirs(full_folder, exist_ok=True)
    results = []
    for image in images:
        file = f"{filename}_{counter:05}_.png"
        image.save(os.path.join(full_folder, file), "PNG", compress_level=4)
        results.append({"filename": file, "subfolder": subfolder, "type": "temp"})
        counter += 1
    return results


@dataclass
class PendingSession:
    request_id: str
    node_id: str
    future: asyncio.Future
    images: list[dict[str, str]]
    has_image2: bool
    client_id: str | None
    resolving: bool = False

    def public(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "node_id": self.node_id,
            "images": self.images,
            "has_image2": self.has_image2,
            "status": "paused",
        }


PENDING_SESSIONS: dict[str, PendingSession] = {}


class ImageProcessorXCancelled(RuntimeError):
    pass


def _resolve_pending_session(session: PendingSession, decision: dict[str, Any]) -> bool:
    """Wake a paused node on the event loop that owns its Future.

    ComfyUI may execute async node functions on a worker event loop while route
    handlers run on the prompt-server loop. Future.set_result is not safe across
    those threads, so the resolution must be scheduled on the Future's loop.
    """
    if session.future.done() or session.resolving:
        return False
    session.resolving = True

    def resolve() -> None:
        if not session.future.done():
            session.future.set_result(decision)

    session.future.get_loop().call_soon_threadsafe(resolve)
    return True


class ImageProcessorX:
    DESCRIPTION = "Process one image or compare/composite two images, with Continue and interactive Pause workflow modes."
    CATEGORY = CATEGORY
    FUNCTION = "process"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "image1": ("IMAGE", {"tooltip": "Primary image and O1 output."}),
                "operation_mode": (["Continue", "Pause"], {"default": "Continue"}),
                "output_image": (["O1", "O2", "O3"], {"default": "O1"}),
                "processor_state": ("STRING", {"default": '{"schemaVersion":1}', "multiline": True}),
            },
            "optional": {"image2": ("IMAGE", {"tooltip": "Optional comparison/composite image and O2 output."})},
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    @classmethod
    def IS_CHANGED(cls, operation_mode: str = "Continue", output_image: str = "O1", processor_state: str = "", **_kwargs: Any):
        if operation_mode == "Pause":
            return float("nan")
        return f"{output_image}:{processor_state}"

    async def process(
        self,
        image1: Any,
        operation_mode: str = "Continue",
        output_image: str = "O1",
        processor_state: str = '{"schemaVersion":1}',
        image2: Any | None = None,
        unique_id: Any = None,
    ):
        if operation_mode not in ("Continue", "Pause"):
            raise ValueError(f"Image ProcessorX operation_mode must be Continue or Pause, got {operation_mode!r}.")
        parse_processor_state(processor_state)
        previews = [_tensor_to_pil(image1)]
        if image2 is not None:
            previews.append(_tensor_to_pil(image2))
        image_refs = _save_temp_refs(previews)

        selected = output_image
        state_value: Any = processor_state
        if operation_mode == "Pause":
            loop = asyncio.get_running_loop()
            request_id = uuid.uuid4().hex
            node_id = str(unique_id or "")
            future = loop.create_future()
            client_id = None
            try:
                from server import PromptServer

                client_id = getattr(PromptServer.instance, "client_id", None)
            except Exception:
                PromptServer = None
            session = PendingSession(request_id, node_id, future, image_refs, image2 is not None, client_id)
            PENDING_SESSIONS[request_id] = session
            if PromptServer is not None:
                PromptServer.instance.send_sync(EVENT_NAME, session.public(), client_id)
            try:
                decision = await future
            finally:
                PENDING_SESSIONS.pop(request_id, None)
            if decision.get("cancel"):
                raise ImageProcessorXCancelled("Image ProcessorX was cancelled by the user.")
            selected = decision.get("output_image", selected)
            state_value = decision.get("processor_state", state_value)
            parse_processor_state(state_value)

        if selected == "O1":
            result = image1
        elif selected == "O2":
            if image2 is None:
                raise ValueError("Image ProcessorX output O2 requires image2 to be connected.")
            result = image2
        elif selected == "O3":
            result = render_o3(image1, image2, state_value)
        else:
            raise ValueError(f"Image ProcessorX output_image must be O1, O2, or O3, got {selected!r}.")
        return {
            "ui": {
                "images": image_refs,
                "image_processor_x": [{"status": "complete", "selected_output": selected, "has_image2": image2 is not None}],
            },
            "result": (result,),
        }


def _safe_prefix(value: Any, fallback: str = "ImageProcessorX") -> str:
    normalized = str(value or fallback).replace("\\", "/").split("/")[-1]
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "_", normalized).strip("._-")
    return normalized[:64] or fallback


def _decode_png_data_url(value: Any):
    from PIL import Image

    if not isinstance(value, str):
        return None
    payload = value.strip()
    if "," in payload:
        header, payload = payload.split(",", 1)
        if "base64" not in header.lower():
            return None
    try:
        raw = base64.b64decode(payload, validate=True)
        image = Image.open(io.BytesIO(raw))
        image.load()
        return image
    except Exception:
        return None


def _pnginfo(prompt: Any = None, workflow: Any = None):
    from PIL.PngImagePlugin import PngInfo

    info = PngInfo()
    for key, value in (("prompt", prompt), ("workflow", workflow)):
        if value is not None:
            try:
                info.add_text(key, json.dumps(value))
            except (TypeError, ValueError):
                pass
    return info


def register_routes(app: Any = None) -> None:
    try:
        from aiohttp import web
        from server import PromptServer
    except Exception:
        return
    server = getattr(PromptServer, "instance", None)
    if server is None or getattr(server, "_workflowx_image_processor_x_routes", False):
        return
    routes = getattr(server, "routes", None)
    if routes is None:
        return

    @routes.post(f"{ROUTE_ROOT}/continue")
    async def continue_route(request):
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)
        session = PENDING_SESSIONS.get(str(data.get("request_id") or ""))
        if session is None or session.node_id != str(data.get("node_id") or ""):
            return web.json_response({"error": "pending Image ProcessorX request not found"}, status=404)
        selected = data.get("output_image", "O1")
        if selected not in ("O1", "O2", "O3"):
            return web.json_response({"error": "output_image must be O1, O2, or O3"}, status=400)
        if selected == "O2" and not session.has_image2:
            return web.json_response({"error": "O2 requires image2"}, status=400)
        try:
            parse_processor_state(data.get("processor_state", '{}'))
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        if not _resolve_pending_session(session, {"output_image": selected, "processor_state": data.get("processor_state", '{}')}):
            return web.json_response({"error": "request already completed"}, status=409)
        return web.json_response({"status": "continuing"})

    @routes.post(f"{ROUTE_ROOT}/cancel")
    async def cancel_route(request):
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)
        session = PENDING_SESSIONS.get(str(data.get("request_id") or ""))
        if session is None or session.node_id != str(data.get("node_id") or ""):
            return web.json_response({"error": "pending Image ProcessorX request not found"}, status=404)
        if not _resolve_pending_session(session, {"cancel": True}):
            return web.json_response({"error": "request already completed"}, status=409)
        return web.json_response({"status": "cancelled"})

    @routes.get(f"{ROUTE_ROOT}/status")
    async def status_route(request):
        node_id = str(getattr(request, "query", {}).get("node_id", ""))
        pending = [session.public() for session in PENDING_SESSIONS.values() if not node_id or session.node_id == node_id]
        return web.json_response({"pending": pending})

    @routes.post(f"{ROUTE_ROOT}/save")
    async def save_route(request):
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)
        image = _decode_png_data_url(data.get("image_b64"))
        if image is None:
            return web.json_response({"error": "invalid image data"}, status=400)
        folder_paths = _folder_paths_module()
        if folder_paths is None:
            return web.json_response({"error": "folder_paths unavailable"}, status=500)
        try:
            output_dir = folder_paths.get_output_directory()
            prefix = _safe_prefix(data.get("filename_prefix"))
            full_folder, name, counter, subfolder, _ = folder_paths.get_save_image_path(prefix, output_dir, image.width, image.height)
            os.makedirs(full_folder, exist_ok=True)
            filename = f"{name}_{counter:05}_.png"
            image.save(os.path.join(full_folder, filename), "PNG", pnginfo=_pnginfo(data.get("prompt"), data.get("workflow")))
        except Exception as exc:
            return web.json_response({"error": f"save failed: {exc}"}, status=500)
        return web.json_response({"status": "success", "filename": filename, "subfolder": subfolder})

    @routes.post(f"{ROUTE_ROOT}/prepare")
    async def prepare_route(request):
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)
        image = _decode_png_data_url(data.get("image_b64"))
        if image is None:
            return web.json_response({"error": "invalid image data"}, status=400)
        buffer = io.BytesIO()
        image.save(buffer, "PNG", pnginfo=_pnginfo(data.get("prompt"), data.get("workflow")))
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        prefix = _safe_prefix(data.get("filename_prefix"))
        return web.json_response({"image_b64": f"data:image/png;base64,{encoded}", "suggested_filename": f"{prefix}.png"})

    server._workflowx_image_processor_x_routes = True


NODE_CLASS_MAPPINGS = {NODE_TYPE: ImageProcessorX}
NODE_DISPLAY_NAME_MAPPINGS = {NODE_TYPE: DISPLAY_NAME}
