"""Backend for Load VideoX Adv.

The node deliberately keeps output sockets static while inspecting the queued
prompt to determine which media outputs are consumed.  Width/height are always
cheap metadata outputs; native video, decoded frames, and standalone audio are
materialized only when their sockets are connected.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import torch

import folder_paths

from ..load_image_x.advanced import (
    DEFAULT_ADV_STATE,
    crop_box_from_state,
    parse_adv_state,
)
from ..load_image_x.runtime import resolve_input_path


MEDIA_OUTPUTS = {0: "video", 1: "video_frames", 2: "audio"}
DEFAULT_VIDEO_STATE: dict[str, Any] = {
    **DEFAULT_ADV_STATE,
    "version": 1,
    "trim_start": 0.0,
    "trim_end": 0.0,
    # Transient at queue time. It is accepted in saved state for compatibility,
    # but the frontend does not persist it.
    "requested_outputs": [],
}


def _number(value: object, fallback: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if math.isfinite(number) else fallback


def _round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def parse_video_state(value: object) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}

    geometry = parse_adv_state(json.dumps(parsed, separators=(",", ":")))
    state = {**DEFAULT_VIDEO_STATE, **geometry}
    state["trim_start"] = max(0.0, _number(parsed.get("trim_start"), 0.0))
    state["trim_end"] = max(0.0, _number(parsed.get("trim_end"), 0.0))
    requested = parsed.get("requested_outputs", [])
    if not isinstance(requested, list):
        requested = []
    state["requested_outputs"] = [
        name for name in ("video", "video_frames", "audio") if name in requested
    ]
    return state


def list_input_videos(folder_paths_module=None) -> list[str]:
    module = folder_paths if folder_paths_module is None else folder_paths_module
    root = Path(module.get_input_directory())
    if not root.is_dir():
        return []
    candidates = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    ]
    return sorted(
        module.filter_files_content_types(candidates, ["video"]),
        key=lambda value: value.casefold(),
    )


def resolve_video_path(value: object, folder_paths_module=None) -> tuple[str, Path]:
    module = folder_paths if folder_paths_module is None else folder_paths_module
    relative, path = resolve_input_path(value, module)
    if relative not in module.filter_files_content_types([relative], ["video"]):
        raise ValueError("Only supported video files can be loaded")
    if not path.is_file():
        raise ValueError(f"Video file not found: {relative}")
    return relative, path


@lru_cache(maxsize=128)
def _probe_cached(path_text: str, mtime_ns: int, size: int) -> dict[str, Any]:
    del mtime_ns, size
    import av

    with av.open(path_text) as container:
        if not container.streams.video:
            raise ValueError("No video stream found")
        stream = container.streams.video[0]
        fps = float(stream.average_rate) if stream.average_rate else 0.0
        if fps <= 0 and stream.base_rate:
            fps = float(stream.base_rate)
        if fps <= 0:
            fps = 1.0

        duration = 0.0
        if container.duration is not None:
            duration = float(container.duration / av.time_base)
        elif stream.duration is not None and stream.time_base is not None:
            duration = float(stream.duration * stream.time_base)
        elif stream.frames:
            duration = float(stream.frames / fps)

        width, height = int(stream.width), int(stream.height)
        rotation = 0
        try:
            for frame in container.decode(stream):
                rotation = int(round(float(frame.rotation or 0))) % 360
                break
        except Exception:
            rotation = 0
        if rotation in (90, 270):
            width, height = height, width

        frame_count = int(stream.frames or 0)
        if frame_count <= 0 and duration > 0:
            frame_count = max(1, _round_half_up(duration * fps))

        return {
            "width": width,
            "height": height,
            "duration": max(0.0, duration),
            "fps": fps,
            "frame_count": frame_count,
            "has_audio": bool(container.streams.audio),
            "rotation": rotation,
        }


def probe_video(path: Path) -> dict[str, Any]:
    stat_result = path.stat()
    result = dict(_probe_cached(str(path), stat_result.st_mtime_ns, stat_result.st_size))
    result["version"] = f"{stat_result.st_mtime_ns:x}-{stat_result.st_size:x}"
    return result


def plan_trim(metadata: dict[str, Any], state: dict[str, Any], seconds: object = None) -> dict[str, Any]:
    duration = max(0.0, _number(metadata.get("duration"), 0.0))
    fps = max(1e-6, _number(metadata.get("fps"), 1.0))
    frame_count = max(1, int(metadata.get("frame_count") or _round_half_up(duration * fps) or 1))
    frame_step = 1.0 / fps

    start = min(max(0.0, _number(state.get("trim_start"), 0.0)), max(0.0, duration - frame_step))
    start_frame = min(frame_count - 1, max(0, _round_half_up(start * fps)))
    start_time = start_frame / fps
    wired = seconds is not None

    if wired:
        requested_seconds = max(frame_step, _number(seconds, 0.0))
    else:
        end = _number(state.get("trim_end"), 0.0)
        if end <= start_time:
            end = duration
        requested_seconds = max(frame_step, min(duration, end) - start_time)

    target_frames = max(1, _round_half_up(requested_seconds * fps))
    available_frames = max(1, frame_count - start_frame)
    take_frames = min(target_frames, available_frames)
    return {
        "wired": wired,
        "start_frame": start_frame,
        "start_time": start_time,
        "target_frames": target_frames,
        "take_frames": take_frames,
        "take_duration": take_frames / fps,
        "requested_duration": target_frames / fps,
        "output_duration": take_frames / fps,
        "short": take_frames < target_frames,
        "fps": fps,
    }


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


def _bounded_dimension(value: object, fallback: int = 1024) -> int:
    return max(8, min(_round_half_up(_number(value, fallback)), 16384))


def _snap_down(value: int, snap: int) -> int:
    if snap <= 0:
        return value
    return max(8, (int(value) // snap) * snap)


def _parse_color(value: object) -> tuple[float, float, float]:
    text = str(value or "").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(character * 2 for character in text)
    try:
        if len(text) == 6:
            return tuple(int(text[index:index + 2], 16) / 255.0 for index in (0, 2, 4))
    except ValueError:
        pass
    return 128 / 255.0, 128 / 255.0, 128 / 255.0


def _resize_frames(frames: torch.Tensor, width: int, height: int, state: dict[str, Any]) -> torch.Tensor:
    width, height = min(16384, max(1, int(width))), min(16384, max(1, int(height)))
    if (frames.shape[2], frames.shape[1]) == (width, height):
        return frames
    from comfy.utils import common_upscale

    factor = min(width / frames.shape[2], height / frames.shape[1])
    method = str(state.get("resample", "auto"))
    if method == "auto":
        method = "lanczos" if factor < 1.0 else "bilinear"
    if method == "nearest":
        method = "nearest-exact"
    channels_first = frames.movedim(-1, 1)
    return common_upscale(channels_first, width, height, method, "disabled").movedim(1, -1)


def transform_frames(frames: torch.Tensor, state: dict[str, Any]) -> torch.Tensor:
    """Apply Load ImageX Adv geometry to an NHWC video batch."""
    if not isinstance(frames, torch.Tensor) or frames.ndim != 4 or frames.shape[0] < 1:
        raise ValueError("Video contains no decodable frames")
    height, width = int(frames.shape[1]), int(frames.shape[2])
    crop_box = crop_box_from_state(width, height, state)
    if crop_box is not None:
        x0, y0, x1, y1 = crop_box
        frames = frames[:, y0:y1, x0:x1, :]
    height, width = int(frames.shape[1]), int(frames.shape[2])
    mode = str(state.get("mode", "off"))
    allow_upscale = bool(state.get("allow_upscale"))

    def resize_factor(factor: float) -> None:
        nonlocal frames, width, height
        if not allow_upscale:
            factor = min(factor, 1.0)
        factor = min(max(factor, 0.01), 8.0)
        width = min(16384, max(1, _round_half_up(width * factor)))
        height = min(16384, max(1, _round_half_up(height * factor)))
        frames = _resize_frames(frames, width, height, state)

    if mode == "max_mp":
        target = max(0.01, min(_number(state.get("max_mp"), 1.0), 64.0)) * 1024 * 1024
        resize_factor(math.sqrt(target / max(1, width * height)))
    elif mode == "longest_side":
        resize_factor(_bounded_dimension(state.get("longest_side")) / max(width, height))
    elif mode == "scale_factor":
        resize_factor(max(0.01, min(_number(state.get("scale_factor"), 1.0), 8.0)))
    elif mode == "fit_inside":
        resize_factor(min(_bounded_dimension(state.get("fit_w")) / width, _bounded_dimension(state.get("fit_h")) / height))
    elif mode == "cover":
        target_w = _bounded_dimension(state.get("cover_w"))
        target_h = _bounded_dimension(state.get("cover_h"))
        anchor = str(state.get("crop_anchor", "center"))
        if state.get("cover_action") == "crop":
            crop_w, crop_h = min(target_w, width), min(target_h, height)
            left, top = _anchor_offset(anchor, width, height, crop_w, crop_h)
            frames = frames[:, top:top + crop_h, left:left + crop_w, :]
            width, height = crop_w, crop_h
        else:
            factor = max(target_w / width, target_h / height)
            if not allow_upscale and factor > 1.0:
                resize_factor(min(target_w / width, target_h / height, 1.0))
            else:
                factor = min(factor, 8.0)
                scaled_w = min(16384, max(1, _round_half_up(width * factor)))
                scaled_h = min(16384, max(1, _round_half_up(height * factor)))
                frames = _resize_frames(frames, scaled_w, scaled_h, state)
                left, top = _anchor_offset(anchor, scaled_w, scaled_h, target_w, target_h)
                frames = frames[:, top:top + target_h, left:left + target_w, :]
                width, height = target_w, target_h
    elif mode == "match_ratio":
        target = max(0.01, _number(state.get("ratio_w"), 1.0)) / max(0.01, _number(state.get("ratio_h"), 1.0))
        if width / height > target:
            crop_w, crop_h = max(1, _round_half_up(height * target)), height
        else:
            crop_w, crop_h = width, max(1, _round_half_up(width / target))
        left, top = max(0, (width - crop_w) // 2), max(0, (height - crop_h) // 2)
        frames = frames[:, top:top + crop_h, left:left + crop_w, :]
        width, height = crop_w, crop_h
    elif mode == "pad":
        top = max(0, min(int(_number(state.get("pad_top"), 0)), 8192))
        bottom = max(0, min(int(_number(state.get("pad_bottom"), 0)), 8192))
        left = max(0, min(int(_number(state.get("pad_left"), 0)), 8192))
        right = max(0, min(int(_number(state.get("pad_right"), 0)), 8192))
        new_w, new_h = min(16384, width + left + right), min(16384, height + top + bottom)
        left, top = min(left, new_w - width), min(top, new_h - height)
        color = torch.tensor(_parse_color(state.get("pad_color")), dtype=frames.dtype, device=frames.device)
        padded = color.view(1, 1, 1, 3).expand(frames.shape[0], new_h, new_w, 3).clone()
        padded[:, top:top + height, left:left + width, :] = frames
        frames, width, height = padded, new_w, new_h

    snap = int(state.get("output_snap", 0) or 0)
    final_w, final_h = _snap_down(width, snap), _snap_down(height, snap)
    return _resize_frames(frames, final_w, final_h, state).clamp(0.0, 1.0)


def output_dimensions(source_width: int, source_height: int, state: dict[str, Any]) -> tuple[int, int]:
    """Plan dimensions without allocating or decoding a frame."""
    crop_box = crop_box_from_state(source_width, source_height, state)
    if crop_box is None:
        width, height = max(1, source_width), max(1, source_height)
    else:
        x0, y0, x1, y1 = crop_box
        width, height = max(1, x1 - x0), max(1, y1 - y0)
    mode = str(state.get("mode", "off"))
    allow_upscale = bool(state.get("allow_upscale"))

    def scaled(factor: float) -> tuple[int, int]:
        if not allow_upscale:
            factor = min(factor, 1.0)
        factor = min(max(factor, 0.01), 8.0)
        return max(1, _round_half_up(width * factor)), max(1, _round_half_up(height * factor))

    if mode == "max_mp":
        target = max(0.01, min(_number(state.get("max_mp"), 1.0), 64.0)) * 1024 * 1024
        width, height = scaled(math.sqrt(target / max(1, width * height)))
    elif mode == "longest_side":
        width, height = scaled(_bounded_dimension(state.get("longest_side")) / max(width, height))
    elif mode == "scale_factor":
        width, height = scaled(max(0.01, min(_number(state.get("scale_factor"), 1.0), 8.0)))
    elif mode == "fit_inside":
        width, height = scaled(min(
            _bounded_dimension(state.get("fit_w")) / width,
            _bounded_dimension(state.get("fit_h")) / height,
        ))
    elif mode == "cover":
        target_w = _bounded_dimension(state.get("cover_w"))
        target_h = _bounded_dimension(state.get("cover_h"))
        if state.get("cover_action") == "crop":
            width, height = min(target_w, width), min(target_h, height)
        else:
            factor = max(target_w / width, target_h / height)
            if not allow_upscale and factor > 1.0:
                width, height = scaled(min(target_w / width, target_h / height, 1.0))
            else:
                width, height = target_w, target_h
    elif mode == "match_ratio":
        target = max(0.01, _number(state.get("ratio_w"), 1.0)) / max(
            0.01, _number(state.get("ratio_h"), 1.0)
        )
        if width / height > target:
            width = max(1, _round_half_up(height * target))
        else:
            height = max(1, _round_half_up(width / target))
    elif mode == "pad":
        width = min(16384, width
                    + max(0, min(int(_number(state.get("pad_left"), 0)), 8192))
                    + max(0, min(int(_number(state.get("pad_right"), 0)), 8192)))
        height = min(16384, height
                     + max(0, min(int(_number(state.get("pad_top"), 0)), 8192))
                     + max(0, min(int(_number(state.get("pad_bottom"), 0)), 8192)))

    snap = int(state.get("output_snap", 0) or 0)
    return min(16384, _snap_down(width, snap)), min(16384, _snap_down(height, snap))


def _decode_video_only(path: Path, plan: dict[str, Any]) -> torch.Tensor:
    import av

    frames: list[torch.Tensor] = []
    with av.open(str(path)) as container:
        if not container.streams.video:
            raise ValueError("No video stream found")
        stream = container.streams.video[0]
        start_pts = int(plan["start_time"] / stream.time_base)
        end_time = plan["start_time"] + plan["take_duration"]
        end_pts = int(end_time / stream.time_base)
        if start_pts:
            container.seek(start_pts, stream=stream)
        for frame in container.decode(stream):
            if frame.pts is not None and frame.pts < start_pts:
                continue
            if frame.pts is not None and frame.pts >= end_pts:
                break
            array = frame.to_ndarray(format="rgb24")
            if frame.rotation:
                array = np.rot90(array, k=int(round(frame.rotation // 90)), axes=(0, 1)).copy()
            frames.append(torch.from_numpy(array).float() / 255.0)
            if len(frames) >= plan["take_frames"]:
                break
    if not frames:
        raise ValueError("Selected trim contains no decodable video frames")
    return torch.stack(frames)


def _decode_audio_only(path: Path, plan: dict[str, Any]) -> dict[str, Any] | None:
    try:
        from comfy_extras.nodes_audio import load as load_audio
        waveform, sample_rate = load_audio(str(path))
    except ValueError as exc:
        if "audio" in str(exc).lower():
            return None
        raise
    start = max(0, _round_half_up(plan["start_time"] * sample_rate))
    wanted = max(1, _round_half_up(plan["take_duration"] * sample_rate))
    selected = waveform[..., start:start + wanted]
    return {"waveform": selected.unsqueeze(0), "sample_rate": int(sample_rate)}


def _trim_frame_count(frames: torch.Tensor, plan: dict[str, Any]) -> torch.Tensor:
    frames = frames[:plan["take_frames"]]
    if frames.shape[0] < 1:
        raise ValueError("Selected trim contains no video frames")
    return frames


def _trim_audio(audio: object, duration: float) -> object:
    if audio is None:
        return None
    waveform = audio["waveform"]
    sample_rate = int(audio["sample_rate"])
    target = max(1, _round_half_up(duration * sample_rate))
    waveform = waveform[..., :target]
    return {"waveform": waveform, "sample_rate": sample_rate}


def _walk_links(value: object) -> Iterable[tuple[str, int]]:
    if isinstance(value, (list, tuple)):
        if len(value) == 2 and isinstance(value[0], (str, int)) and isinstance(value[1], int):
            yield str(value[0]), value[1]
            return
        for item in value:
            yield from _walk_links(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk_links(item)


def connected_media_outputs(dynprompt: object, unique_id: object) -> set[str] | None:
    if dynprompt is None or unique_id is None:
        return None
    try:
        node_ids = dynprompt.all_node_ids()
    except Exception:
        return None
    source_id = str(unique_id)
    connected: set[str] = set()
    for node_id in node_ids:
        try:
            inputs = dynprompt.get_node(node_id).get("inputs", {})
        except Exception:
            continue
        for linked_id, output_index in _walk_links(inputs):
            if linked_id == source_id and output_index in MEDIA_OUTPUTS:
                connected.add(MEDIA_OUTPUTS[output_index])
    return connected


async def metadata_handler(request):
    from aiohttp import web

    try:
        relative, path = resolve_video_path(request.rel_url.query.get("path", ""))
        metadata = probe_video(path)
    except (OSError, ValueError) as exc:
        return web.json_response({"error": str(exc)}, status=400)
    return web.json_response({"path": relative, **metadata})


class LoadVideoXAdv:
    DESCRIPTION = (
        "Load a video with a visual floating timeline and Load ImageX Adv crop, resize, "
        "snap, resample, upscale, and padding controls. Media is decoded only for connected outputs."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video": (list_input_videos(), {"video_upload": True, "tooltip": "Video in ComfyUI's input folder."}),
                "workflowx_state": ("STRING", {"default": json.dumps(DEFAULT_VIDEO_STATE, separators=(",", ":")), "multiline": False}),
            },
            "optional": {
                "seconds": ("FLOAT", {"forceInput": True, "min": 0.0, "step": 0.001, "tooltip": "Optional fixed trim duration in seconds."}),
            },
            "hidden": {"dynprompt": "DYNPROMPT", "unique_id": "UNIQUE_ID"},
        }

    CATEGORY = "WorkflowX/Video"
    RETURN_TYPES = ("VIDEO", "IMAGE", "AUDIO", "INT", "INT")
    RETURN_NAMES = ("video", "video_frames", "audio", "width", "height")
    OUTPUT_TOOLTIPS = (
        "Trimmed and spatially processed native ComfyUI video.",
        "Trimmed and spatially processed frame batch.",
        "Trimmed source soundtrack, or None when absent.",
        "Final output width in pixels.",
        "Final output height in pixels.",
    )
    FUNCTION = "load_video"

    def load_video(self, video: str, workflowx_state: str = "", seconds=None, dynprompt=None, unique_id=None):
        relative, path = resolve_video_path(video)
        state = parse_video_state(workflowx_state)
        metadata = probe_video(path)
        plan = plan_trim(metadata, state, seconds)
        requested = connected_media_outputs(dynprompt, unique_id)
        if requested is None:
            requested = set(state.get("requested_outputs") or ["video"])

        width, height = output_dimensions(metadata["width"], metadata["height"], state)
        want_video = "video" in requested
        want_frames = "video_frames" in requested
        want_audio = "audio" in requested
        spatial = bool(
            crop_box_from_state(metadata["width"], metadata["height"], state) is not None
            or state.get("mode") != "off"
            or int(state.get("output_snap", 0) or 0) > 0
        )

        native_output = None
        frame_output = None
        audio_output = None
        components = None
        source = None

        if want_video:
            from comfy_api.latest import InputImpl
            source = InputImpl.VideoFromFile(str(path))
            trimmed = source.as_trimmed(plan["start_time"], plan["take_duration"], strict_duration=False)
            if trimmed is None:
                raise ValueError("Selected trim contains no video")
            if not spatial and not want_frames:
                native_output = trimmed
            else:
                components = trimmed.get_components()

        if components is None and want_frames and want_audio:
            from comfy_api.latest import InputImpl
            source = source or InputImpl.VideoFromFile(str(path))
            trimmed = source.as_trimmed(plan["start_time"], plan["take_duration"], strict_duration=False)
            components = trimmed.get_components()

        frames = None
        component_audio = None
        if components is not None:
            frames = components.images
            component_audio = components.audio
        elif want_frames:
            frames = _decode_video_only(path, plan)

        if frames is not None:
            frames = _trim_frame_count(frames, plan)
            frames = transform_frames(frames, state)
            frame_output = frames if want_frames else None

        if want_audio:
            if component_audio is not None:
                audio_output = _trim_audio(component_audio, plan["output_duration"])
            elif components is None:
                audio_output = _decode_audio_only(path, plan)

        if want_video and native_output is None:
            from comfy_api.latest import InputImpl, Types
            if frames is None:
                raise ValueError("Unable to materialize processed video frames")
            embedded_audio = _trim_audio(component_audio, plan["output_duration"])
            native_output = InputImpl.VideoFromComponents(
                Types.VideoComponents(images=frames, audio=embedded_audio, frame_rate=Fraction(metadata["fps"]).limit_denominator(100000)),
                bit_depth=(source.get_bit_depth() if source is not None else 8),
                color_space=(source.get_color_space() if source is not None else "sRGB"),
            )

        status = {
            "file": relative,
            "requested_outputs": sorted(requested),
            "start": round(plan["start_time"], 3),
            "requested_duration": round(plan["requested_duration"], 3),
            "actual_duration": round(plan["output_duration"], 3),
            "wired": plan["wired"],
            "short": plan["short"],
            "has_audio": metadata["has_audio"],
            "width": width,
            "height": height,
        }
        return {"ui": {"workflowx_load_video_x_adv": [status]}, "result": (native_output, frame_output, audio_output, width, height)}

    @classmethod
    def IS_CHANGED(cls, video: str, **_kwargs):
        try:
            _relative, path = resolve_video_path(video)
            stat_result = path.stat()
            return f"{stat_result.st_mtime_ns}:{stat_result.st_size}"
        except Exception:
            return float("nan")

    @classmethod
    def VALIDATE_INPUTS(cls, video: str, **_kwargs):
        try:
            resolve_video_path(video)
        except (OSError, ValueError) as exc:
            return str(exc)
        return True


NODE_CLASS_MAPPINGS = {"WorkflowX_LoadVideoXAdv": LoadVideoXAdv}
NODE_DISPLAY_NAME_MAPPINGS = {"WorkflowX_LoadVideoXAdv": "Load VideoX Adv"}


__all__ = [
    "DEFAULT_VIDEO_STATE",
    "LoadVideoXAdv",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "connected_media_outputs",
    "list_input_videos",
    "output_dimensions",
    "parse_video_state",
    "plan_trim",
    "probe_video",
    "resolve_video_path",
    "transform_frames",
]
