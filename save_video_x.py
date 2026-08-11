from __future__ import annotations

import datetime
import functools
import itertools
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from string import Template
from typing import Any

import numpy as np
import torch
from PIL import Image
from PIL.PngImagePlugin import PngInfo

import folder_paths

logger = logging.getLogger(__name__)

ENCODE_ARGS = ("utf-8", "backslashreplace")
BASE_FORMATS_DIR = Path(__file__).resolve().parent / "video_formats"
SUPPORTED_VIDEO_FORMATS = ("video/h264-mp4", "video/h265-mp4", "video/av1-webm")
PIXEL_FORMAT_OPTIONS = ("yuv420p (8-bit)", "yuv420p10le (10-bit)")
PIXEL_FORMAT_VALUES = {
    "yuv420p (8-bit)": "yuv420p",
    "yuv420p10le (10-bit)": "yuv420p10le",
}
CRF_QUALITY_OPTIONS = (
    "Draft (CRF 30)",
    "Standard (CRF 23)",
    "Good (CRF 20)",
    "High (CRF 18)",
    "Very High (CRF 16)",
    "Ultra (CRF 14)",
    "Near Lossless (CRF 12)",
    "Archival (CRF 10)",
    "Master (CRF 8)",
    "Lossless",
)
CRF_QUALITY_VALUES = {
    "Draft (CRF 30)": 30,
    "Standard (CRF 23)": 23,
    "Good (CRF 20)": 20,
    "High (CRF 18)": 18,
    "Very High (CRF 16)": 16,
    "Ultra (CRF 14)": 14,
    "Near Lossless (CRF 12)": 12,
    "Archival (CRF 10)": 10,
    "Master (CRF 8)": 8,
}
LOSSLESS_QUALITY_OPTION = "Lossless"
COLOR_RANGE_OPTIONS = ("Auto (format default)", "Full / pc", "Limited / tv")
COLOR_RANGE_VALUES = {
    "Full / pc": "pc",
    "Limited / tv": "tv",
}
AUDIO_BITRATE_OPTIONS = (
    "Source/default",
    "96k",
    "128k",
    "160k",
    "192k",
    "256k",
    "320k",
)
AUDIO_FILTER_OPTIONS = (
    "Denoise light",
    "De-click",
    "High-pass rumble cut",
    "Low-pass hiss cut",
    "De-esser light",
    "Presence boost",
    "Warmth",
    "Brightness",
    "Speech clarity",
    "Stereo widen",
)
AUDIO_FILTERS = {
    "Denoise light": "afftdn=nr=8:nf=-25",
    "De-click": "adeclick",
    "High-pass rumble cut": "highpass=f=80",
    "Low-pass hiss cut": "lowpass=f=12000",
    "De-esser light": "deesser=i=0.2",
    "Presence boost": "equalizer=f=3500:t=q:w=1:g=3",
    "Warmth": "equalizer=f=180:t=q:w=1:g=2",
    "Brightness": "equalizer=f=8000:t=q:w=1:g=2",
    "Speech clarity": "equalizer=f=2500:t=q:w=1:g=3",
    "Stereo widen": "extrastereo=m=1.5",
}
METADATA_PREVIEW_MAX_SIDE = 512


class MultiInput(str):
    def __new__(cls, string: str, allowed_types: list[str] | str = "*"):
        value = super().__new__(cls, string)
        value.allowed_types = allowed_types
        return value

    def __ne__(self, other):
        if self.allowed_types == "*" or other == "*":
            return False
        return other not in self.allowed_types


class ContainsAll(dict):
    def __contains__(self, other):
        return True

    def __getitem__(self, key):
        return super().get(key, (None, {}))


imageOrLatent = MultiInput("IMAGE", ["IMAGE", "LATENT"])
floatOrInt = MultiInput("FLOAT", ["FLOAT", "INT"])


def cached(duration):
    def dec(func):
        cached_ret = None
        cache_time = 0

        @functools.wraps(func)
        def cached_func():
            nonlocal cache_time, cached_ret
            if time.time() > cache_time + duration or cached_ret is None:
                cache_time = time.time()
                cached_ret = func()
            return cached_ret

        return cached_func

    return dec


def flatten_list(items):
    ret = []
    for item in items:
        if isinstance(item, list):
            ret.extend(item)
        else:
            ret.append(item)
    return ret


def iterate_format(video_format, for_widgets=True):
    def indirector(container, index):
        if isinstance(container[index], list) and (
            not for_widgets
            or len(container[index]) > 1
            and not isinstance(container[index][1], dict)
        ):
            value = yield container[index]
            if value is not None:
                container[index] = value
                yield

    for key in video_format:
        if key == "extra_widgets":
            if for_widgets:
                yield from video_format["extra_widgets"]
        elif key.endswith("_pass"):
            for index in range(len(video_format[key])):
                yield from indirector(video_format[key], index)
            if not for_widgets:
                video_format[key] = flatten_list(video_format[key])
        else:
            yield from indirector(video_format, key)


def ffmpeg_suitability(path):
    try:
        version = subprocess.run(
            [path, "-version"], check=True, capture_output=True
        ).stdout.decode(*ENCODE_ARGS)
    except Exception:
        return 0

    score = 0
    for criterion, weight in [
        ("libvpx", 20),
        ("264", 10),
        ("265", 3),
        ("svtav1", 5),
        ("libopus", 1),
    ]:
        if criterion in version:
            score += weight

    copyright_index = version.find("2000-2")
    if copyright_index >= 0:
        copyright_year = version[copyright_index + 6 : copyright_index + 9]
        if copyright_year.isnumeric():
            score += int(copyright_year)
    return score


def find_ffmpeg():
    if "WORKFLOWX_FORCE_FFMPEG_PATH" in os.environ:
        return os.environ.get("WORKFLOWX_FORCE_FFMPEG_PATH")
    if "VHS_FORCE_FFMPEG_PATH" in os.environ:
        return os.environ.get("VHS_FORCE_FFMPEG_PATH")

    paths = []
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        paths.append(get_ffmpeg_exe())
    except Exception:
        logger.debug("imageio_ffmpeg is not available; checking system ffmpeg")

    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg is not None:
        paths.append(system_ffmpeg)
    if os.path.isfile("ffmpeg"):
        paths.append(os.path.abspath("ffmpeg"))
    if os.path.isfile("ffmpeg.exe"):
        paths.append(os.path.abspath("ffmpeg.exe"))

    if not paths:
        logger.error("No valid ffmpeg found.")
        return None
    if len(paths) == 1:
        return paths[0]
    return max(paths, key=ffmpeg_suitability)


ffmpeg_path = find_ffmpeg()
def _ensure_format_folder(folder_name: str) -> None:
    folder_paths.folder_names_and_paths.setdefault(folder_name, ((), {".json"}))
    extensions = folder_paths.folder_names_and_paths[folder_name][1]
    if len(extensions) == 0:
        extensions.add(".json")


_ensure_format_folder("WorkflowX_video_formats")
_ensure_format_folder("VHS_video_formats")


@cached(5)
def get_video_formats():
    format_files: dict[str, str] = {}

    for folder_name in ("WorkflowX_video_formats", "VHS_video_formats"):
        try:
            format_names = folder_paths.get_filename_list(folder_name)
        except Exception:
            format_names = []
        for format_name in format_names:
            try:
                path = folder_paths.get_full_path(folder_name, format_name)
            except Exception:
                path = None
            if path:
                format_files[format_name] = path

    for item in BASE_FORMATS_DIR.iterdir():
        if item.is_file() and item.suffix == ".json":
            format_files[item.stem] = str(item)

    formats = []
    for format_name, path in sorted(format_files.items()):
        format_key = "video/" + Path(format_name).stem
        if format_key not in SUPPORTED_VIDEO_FORMATS:
            continue
        with open(path, "r", encoding="utf-8") as stream:
            video_format = json.load(stream)
        formats.append(format_key)
    return formats, {}


def apply_format_widgets(format_name, kwargs):
    local_path = BASE_FORMATS_DIR / f"{format_name}.json"
    if local_path.exists():
        video_format_path = str(local_path)
    else:
        video_format_path = (
            folder_paths.get_full_path("WorkflowX_video_formats", format_name)
            or folder_paths.get_full_path("VHS_video_formats", format_name)
        )
    with open(video_format_path, "r", encoding="utf-8") as stream:
        video_format = json.load(stream)

    for widget in iterate_format(video_format):
        if widget[0] not in kwargs:
            if len(widget) > 2 and "default" in widget[2]:
                default = widget[2]["default"]
            elif isinstance(widget[1], list):
                default = widget[1][0]
            else:
                default = {"BOOLEAN": False, "INT": 0, "FLOAT": 0, "STRING": ""}[widget[1]]
            kwargs[widget[0]] = default
            logger.warning("Missing input for %s has been set to %s", widget[0], default)

    iterator = iterate_format(video_format, False)
    for widget in iterator:
        while isinstance(widget, list):
            if len(widget) == 1:
                widget = [Template(x).substitute(**kwargs) for x in widget[0]]
                break
            if isinstance(widget[1], dict):
                widget = widget[1][str(kwargs[widget[0]])]
            elif len(widget) > 3:
                widget = Template(widget[3]).substitute(val=kwargs[widget[0]])
            else:
                widget = str(kwargs[widget[0]])
        iterator.send(widget)
    return video_format


def tensor_to_int(tensor, bits):
    tensor = tensor.cpu().numpy() * (2**bits - 1) + 0.5
    return np.clip(tensor, 0, (2**bits - 1))


def tensor_to_shorts(tensor):
    return tensor_to_int(tensor, 16).astype(np.uint16)


def tensor_to_bytes(tensor):
    return tensor_to_int(tensor, 8).astype(np.uint8)


def merge_filter_args(args, ftype="-vf"):
    try:
        start_index = args.index(ftype) + 1
        index = start_index
        while True:
            index = args.index(ftype, index)
            args[start_index] += "," + args[index + 1]
            args.pop(index)
            args.pop(index)
    except ValueError:
        pass


def _crf_value(label: object) -> int:
    return CRF_QUALITY_VALUES.get(str(label), CRF_QUALITY_VALUES["Standard (CRF 23)"])


def _is_lossless_quality(label: object) -> bool:
    return str(label) == LOSSLESS_QUALITY_OPTION


def _pixel_format_value(label: object) -> str:
    return PIXEL_FORMAT_VALUES.get(str(label), PIXEL_FORMAT_VALUES["yuv420p (8-bit)"])


def _selected_audio_filters(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list | tuple):
        raw_items = list(value)
    else:
        text = str(value).strip()
        if not text:
            return []
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError:
            loaded = [part.strip() for part in text.split(",")]
        raw_items = loaded if isinstance(loaded, list) else [loaded]

    selected = []
    for item in raw_items:
        label = str(item).strip()
        if label in AUDIO_FILTERS and label not in selected:
            selected.append(label)
    return selected


def _audio_filter_args(value: object) -> list[str]:
    filters = [AUDIO_FILTERS[label] for label in _selected_audio_filters(value)]
    return ["-af", ",".join(filters)] if filters else []


def _audio_bitrate_args(audio_bitrate: object) -> list[str]:
    bitrate = str(audio_bitrate or "").strip()
    if bitrate and bitrate != "Source/default":
        return ["-b:a", bitrate]
    return []


def _set_arg_value(args: list[Any], flag: str, value: str) -> bool:
    try:
        index = args.index(flag)
    except ValueError:
        return False
    if index + 1 >= len(args):
        return False
    args[index + 1] = value
    return True


def _set_or_add_arg_value(args: list[Any], flag: str, value: str) -> None:
    if not _set_arg_value(args, flag, value):
        args.extend([flag, value])


def _get_arg_value(args: list[Any], flag: str) -> str:
    try:
        index = args.index(flag)
    except ValueError:
        return ""
    if index + 1 >= len(args):
        return ""
    return str(args[index + 1])


def _remove_arg_pair(args: list[Any], flag: str) -> bool:
    removed = False
    while True:
        try:
            index = args.index(flag)
        except ValueError:
            return removed
        del args[index : min(index + 2, len(args))]
        removed = True


def _merge_colon_params(existing: str, additions: dict[str, str]) -> str:
    parts = []
    seen = set()
    for part in str(existing or "").split(":"):
        if not part:
            continue
        key = part.split("=", 1)[0]
        if key in additions:
            parts.append(f"{key}={additions[key]}")
            seen.add(key)
        else:
            parts.append(part)

    for key, value in additions.items():
        if key not in seen:
            parts.append(f"{key}={value}")
    return ":".join(parts)


def _apply_lossless_video_settings(format_ext: str, video_format: dict[str, Any]) -> None:
    main_pass = video_format.get("main_pass")
    if not isinstance(main_pass, list):
        return

    if format_ext == "h264-mp4":
        _set_or_add_arg_value(main_pass, "-crf", "0")
    elif format_ext == "h265-mp4":
        _remove_arg_pair(main_pass, "-crf")
        params = _merge_colon_params(
            _get_arg_value(main_pass, "-x265-params"),
            {"lossless": "1", "log-level": "quiet"},
        )
        _set_or_add_arg_value(main_pass, "-x265-params", params)
    elif format_ext == "av1-webm":
        _remove_arg_pair(main_pass, "-crf")
        params = _merge_colon_params(
            _get_arg_value(main_pass, "-svtav1-params"),
            {"lossless": "1"},
        )
        _set_or_add_arg_value(main_pass, "-svtav1-params", params)


def _apply_output_color_range(video_format: dict[str, Any], color_range: object) -> None:
    output_range = COLOR_RANGE_VALUES.get(str(color_range))
    if output_range is None:
        return

    main_pass = video_format.get("main_pass")
    if not isinstance(main_pass, list):
        return

    if not _set_arg_value(main_pass, "-color_range", output_range):
        main_pass.extend(["-color_range", output_range])

    try:
        vf_index = main_pass.index("-vf")
        vf_value = str(main_pass[vf_index + 1])
    except (ValueError, IndexError):
        return

    out_range = f"out_range={output_range}"
    if "out_range=" in vf_value:
        vf_value = re.sub(r"out_range=[^,:]+", out_range, vf_value)
    elif vf_value.startswith("scale="):
        vf_value += f":{out_range}"
    main_pass[vf_index + 1] = vf_value


def _metadata_pnginfo(prompt: object = None, extra_pnginfo: dict[str, Any] | None = None):
    metadata = PngInfo()
    if prompt is not None:
        metadata.add_text("prompt", json.dumps(prompt))
    if extra_pnginfo is not None:
        for key in extra_pnginfo:
            metadata.add_text(key, json.dumps(extra_pnginfo[key]))
    metadata.add_text("CreationTime", datetime.datetime.now().isoformat(" ")[:19])
    return metadata


def _save_metadata_preview_image(
    first_image: Any,
    full_output_folder: str,
    filename: str,
    counter: int,
    metadata: PngInfo,
) -> str:
    image = Image.fromarray(tensor_to_bytes(first_image))
    image.thumbnail((METADATA_PREVIEW_MAX_SIDE, METADATA_PREVIEW_MAX_SIDE), Image.Resampling.LANCZOS)
    preview_file = f"{filename}_{counter:05}_metadata.png"
    preview_path = os.path.join(full_output_folder, preview_file)
    image.save(preview_path, "PNG", pnginfo=metadata, compress_level=9)
    return preview_path


def ffmpeg_process(args, video_format, video_metadata, file_path, env):
    res = None
    frame_data = yield
    total_frames_output = 0
    if video_format.get("save_metadata", "False") != "False":
        os.makedirs(folder_paths.get_temp_directory(), exist_ok=True)
        metadata_path = os.path.join(folder_paths.get_temp_directory(), "metadata.txt")

        def escape_ffmpeg_metadata(key, value):
            value = str(value)
            value = value.replace("\\", "\\\\")
            value = value.replace(";", "\\;")
            value = value.replace("#", "\\#")
            value = value.replace("=", "\\=")
            value = value.replace("\n", "\\\n")
            return f"{key}={value}"

        with open(metadata_path, "w", encoding="utf-8") as file:
            file.write(";FFMETADATA1\n")
            if "prompt" in video_metadata:
                file.write(
                    escape_ffmpeg_metadata("prompt", json.dumps(video_metadata["prompt"]))
                    + "\n"
                )
            if "workflow" in video_metadata:
                file.write(
                    escape_ffmpeg_metadata(
                        "workflow", json.dumps(video_metadata["workflow"])
                    )
                    + "\n"
                )
            for key, value in video_metadata.items():
                if key not in ["prompt", "workflow"]:
                    file.write(escape_ffmpeg_metadata(key, json.dumps(value)) + "\n")

        metadata_args = (
            args[:1]
            + ["-i", metadata_path]
            + args[1:]
            + ["-metadata", "creation_time=now", "-movflags", "use_metadata_tags"]
        )
        with subprocess.Popen(
            metadata_args + [file_path],
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            env=env,
        ) as proc:
            try:
                while frame_data is not None:
                    proc.stdin.write(frame_data)
                    frame_data = yield
                    total_frames_output += 1
                proc.stdin.flush()
                proc.stdin.close()
                res = proc.stderr.read()
                returncode = proc.wait()
                if returncode != 0:
                    raise Exception(
                        "An error occurred in the ffmpeg subprocess:\n"
                        + res.decode(*ENCODE_ARGS)
                    )
            except BrokenPipeError:
                err = proc.stderr.read()
                if os.path.exists(file_path):
                    raise Exception(
                        "An error occurred in the ffmpeg subprocess:\n"
                        + err.decode(*ENCODE_ARGS)
                    )
                print(err.decode(*ENCODE_ARGS), end="", file=sys.stderr)
                logger.warning("An error occurred when saving with metadata")

    if res != b"":
        with subprocess.Popen(
            args + [file_path], stderr=subprocess.PIPE, stdin=subprocess.PIPE, env=env
        ) as proc:
            try:
                while frame_data is not None:
                    proc.stdin.write(frame_data)
                    frame_data = yield
                    total_frames_output += 1
                proc.stdin.flush()
                proc.stdin.close()
                res = proc.stderr.read()
                returncode = proc.wait()
                if returncode != 0:
                    raise Exception(
                        "An error occurred in the ffmpeg subprocess:\n"
                        + res.decode(*ENCODE_ARGS)
                    )
            except BrokenPipeError:
                res = proc.stderr.read()
                raise Exception(
                    "An error occurred in the ffmpeg subprocess:\n"
                    + res.decode(*ENCODE_ARGS)
                )
    yield total_frames_output
    if len(res) > 0:
        print(res.decode(*ENCODE_ARGS), end="", file=sys.stderr)


def _progress_bar(total):
    try:
        from comfy.utils import ProgressBar

        return ProgressBar(total)
    except Exception:
        class NullProgressBar:
            def __init__(self, total):
                self.total = total

            def update(self, _amount):
                return None

        return NullProgressBar(total)


class SaveVideoX:
    @classmethod
    def INPUT_TYPES(cls):
        ffmpeg_formats, format_widgets = get_video_formats()
        return {
            "required": {
                "images": (imageOrLatent,),
                "frame_rate": (floatOrInt, {"default": 8, "min": 1, "step": 1}),
                "filename_prefix": ("STRING", {"default": "AnimateDiff"}),
                "format": (
                    ffmpeg_formats,
                    {"formats": format_widgets, "default": "video/h264-mp4"},
                ),
                "crf_quality": (CRF_QUALITY_OPTIONS, {"default": "Standard (CRF 23)"}),
                "pixel_format": (PIXEL_FORMAT_OPTIONS, {"default": "yuv420p (8-bit)"}),
                "color_range": (COLOR_RANGE_OPTIONS, {"default": "Auto (format default)"}),
                "save_metadata_preview_image": ("BOOLEAN", {"default": True}),
                "audio_bitrate": (AUDIO_BITRATE_OPTIONS, {"default": "Source/default"}),
                "audio_filters": (
                    "STRING",
                    {
                        "default": "[]",
                        "multiline": False,
                        "options": AUDIO_FILTER_OPTIONS,
                    },
                ),
                "save_output": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "audio": ("AUDIO",),
                "vae": ("VAE",),
            },
            "hidden": ContainsAll(
                {
                    "prompt": "PROMPT",
                    "extra_pnginfo": "EXTRA_PNGINFO",
                }
            ),
        }

    RETURN_TYPES = ("VHS_FILENAMES",)
    RETURN_NAMES = ("Filenames",)
    OUTPUT_NODE = True
    CATEGORY = "WorkflowX_Configurator/Video"
    FUNCTION = "combine_video"

    def combine_video(
        self,
        frame_rate: int,
        images=None,
        latents=None,
        filename_prefix="AnimateDiff",
        format="video/h264-mp4",
        crf_quality="Standard (CRF 23)",
        pixel_format="yuv420p (8-bit)",
        color_range="Auto (format default)",
        save_metadata_preview_image=True,
        audio_bitrate="Source/default",
        audio_filters="[]",
        save_output=True,
        prompt=None,
        extra_pnginfo=None,
        audio=None,
        vae=None,
        **kwargs,
    ):
        if latents is not None:
            images = latents
        if images is None:
            return ((save_output, []),)
        if vae is not None:
            if isinstance(images, dict):
                images = images["samples"]
            else:
                vae = None

        if isinstance(images, torch.Tensor) and images.size(0) == 0:
            return ((save_output, []),)

        num_frames = len(images)
        pbar = _progress_bar(num_frames)
        if vae is not None:
            downscale_ratio = getattr(vae, "downscale_ratio", 8)
            width = images.size(-1) * downscale_ratio
            height = images.size(-2) * downscale_ratio
            frames_per_batch = (1920 * 1080 * 16) // (width * height) or 1

            def batched(iterator, count):
                while batch := tuple(itertools.islice(iterator, count)):
                    yield batch

            def batched_encode(latent_images, vae_obj, batch_size):
                for batch in batched(iter(latent_images), batch_size):
                    image_batch = torch.from_numpy(np.array(batch))
                    yield from vae_obj.decode(image_batch)

            images = batched_encode(images, vae, frames_per_batch)
            first_image = next(images)
            images = itertools.chain([first_image], images)
            while len(first_image.shape) > 3:
                first_image = first_image[0]
        else:
            first_image = images[0]
            images = iter(images)

        output_dir = (
            folder_paths.get_output_directory()
            if save_output
            else folder_paths.get_temp_directory()
        )
        full_output_folder, filename, _, subfolder, _ = folder_paths.get_save_image_path(
            filename_prefix, output_dir
        )
        output_files = []

        metadata = _metadata_pnginfo(prompt=prompt, extra_pnginfo=extra_pnginfo)
        max_counter = 0
        matcher = re.compile(
            f"{re.escape(filename)}_(\\d+)\\D*\\..+", re.IGNORECASE
        )
        for existing_file in os.listdir(full_output_folder):
            match = matcher.fullmatch(existing_file)
            if match:
                max_counter = max(max_counter, int(match.group(1)))
        counter = max_counter + 1

        if save_metadata_preview_image:
            output_files.append(
                _save_metadata_preview_image(
                    first_image,
                    full_output_folder,
                    filename,
                    counter,
                    metadata,
                )
            )

        format_type, format_ext = format.split("/")
        if format_type != "video":
            raise ValueError(f"Save Video X only supports video formats, got {format!r}.")
        if ffmpeg_path is None:
            raise ProcessLookupError(
                "ffmpeg is required for video outputs and could not be found.\n"
                "Install imageio-ffmpeg, place ffmpeg in ComfyUI, or add ffmpeg "
                "to the system path."
            )

        has_alpha = first_image.shape[-1] == 4
        kwargs["has_alpha"] = has_alpha
        kwargs["crf"] = 0 if _is_lossless_quality(crf_quality) else _crf_value(crf_quality)
        kwargs["pix_fmt"] = _pixel_format_value(pixel_format)
        kwargs["save_metadata"] = False
        kwargs["trim_to_audio"] = False
        kwargs["input_color_depth"] = "8bit"
        video_format = apply_format_widgets(format_ext, kwargs)
        video_format["save_metadata"] = "False"
        if _is_lossless_quality(crf_quality):
            _apply_lossless_video_settings(format_ext, video_format)
        _apply_output_color_range(video_format, color_range)

        dim_alignment = video_format.get("dim_alignment", 2)
        if (first_image.shape[1] % dim_alignment) or (
            first_image.shape[0] % dim_alignment
        ):
            to_pad = (
                -first_image.shape[1] % dim_alignment,
                -first_image.shape[0] % dim_alignment,
            )
            padding = (
                to_pad[0] // 2,
                to_pad[0] - to_pad[0] // 2,
                to_pad[1] // 2,
                to_pad[1] - to_pad[1] // 2,
            )
            padfunc = torch.nn.ReplicationPad2d(padding)

            def pad(image):
                image = image.permute((2, 0, 1))
                padded = padfunc(image.to(dtype=torch.float32))
                return padded.permute((1, 2, 0))

            images = map(pad, images)
            dimensions = (
                -first_image.shape[1] % dim_alignment + first_image.shape[1],
                -first_image.shape[0] % dim_alignment + first_image.shape[0],
            )
            logger.warning(
                "Output images were not of valid resolution and have had padding applied"
            )
        else:
            dimensions = (first_image.shape[1], first_image.shape[0])

        if video_format.get("input_color_depth", "8bit") == "16bit":
            images = map(tensor_to_shorts, images)
            i_pix_fmt = "rgba64" if has_alpha else "rgb48"
        else:
            images = map(tensor_to_bytes, images)
            i_pix_fmt = "rgba" if has_alpha else "rgb24"

        file = f"{filename}_{counter:05}.{video_format['extension']}"
        file_path = os.path.join(full_output_folder, file)
        args = [
            ffmpeg_path,
            "-v",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            i_pix_fmt,
            "-color_range",
            "pc",
            "-colorspace",
            "rgb",
            "-color_primaries",
            "bt709",
            "-color_trc",
            video_format.get("fake_trc", "iec61966-2-1"),
            "-s",
            f"{dimensions[0]}x{dimensions[1]}",
            "-r",
            str(frame_rate),
            "-i",
            "-",
        ]

        images = map(lambda value: value.tobytes(), images)
        env = os.environ.copy()
        if "environment" in video_format:
            env.update(video_format["environment"])

        if "pre_pass" in video_format:
            images = [b"".join(images)]
            os.makedirs(folder_paths.get_temp_directory(), exist_ok=True)
            in_args_len = args.index("-i") + 2
            pre_pass_args = args[:in_args_len] + video_format["pre_pass"]
            merge_filter_args(pre_pass_args)
            try:
                subprocess.run(
                    pre_pass_args,
                    input=images[0],
                    env=env,
                    capture_output=True,
                    check=True,
                )
            except subprocess.CalledProcessError as exc:
                raise Exception(
                    "An error occurred in the ffmpeg prepass:\n"
                    + exc.stderr.decode(*ENCODE_ARGS)
                ) from exc

        if "inputs_main_pass" in video_format:
            in_args_len = args.index("-i") + 2
            args = (
                args[:in_args_len]
                + video_format["inputs_main_pass"]
                + args[in_args_len:]
            )

        args += video_format["main_pass"]
        merge_filter_args(args)
        output_process = ffmpeg_process(args, video_format, {}, file_path, env)
        output_process.send(None)

        for image in images:
            pbar.update(1)
            output_process.send(image)

        try:
            total_frames_output = output_process.send(None)
            output_process.send(None)
        except StopIteration:
            total_frames_output = num_frames

        output_files.append(file_path)

        a_waveform = None
        if audio is not None:
            try:
                a_waveform = audio["waveform"]
            except Exception:
                pass
        if a_waveform is not None:
            mux_file = f"{filename}_{counter:05}_audio_mux_{os.getpid()}.{video_format['extension']}"
            mux_file_path = os.path.join(full_output_folder, mux_file)
            if "audio_pass" not in video_format:
                logger.warning(
                    "Selected video format does not have explicit audio support"
                )
                video_format["audio_pass"] = ["-c:a", "libopus"]

            channels = audio["waveform"].size(1)
            min_audio_dur = total_frames_output / frame_rate + 1
            apad = (
                []
                if video_format.get("trim_to_audio", "False") != "False"
                else ["-af", "apad=whole_dur=" + str(min_audio_dur)]
            )
            audio_args = list(video_format["audio_pass"])
            audio_args += _audio_bitrate_args(audio_bitrate)
            audio_args += _audio_filter_args(audio_filters)

            mux_args = [
                ffmpeg_path,
                "-v",
                "error",
                "-n",
                "-i",
                file_path,
                "-ar",
                str(audio["sample_rate"]),
                "-ac",
                str(channels),
                "-f",
                "f32le",
                "-i",
                "-",
                "-c:v",
                "copy",
            ] + audio_args + apad + [
                "-shortest",
                mux_file_path,
            ]

            audio_data = audio["waveform"].squeeze(0).transpose(0, 1).numpy().tobytes()
            merge_filter_args(mux_args, "-af")
            try:
                res = subprocess.run(
                    mux_args, input=audio_data, env=env, capture_output=True, check=True
                )
            except subprocess.CalledProcessError as exc:
                if os.path.exists(mux_file_path):
                    os.remove(mux_file_path)
                raise Exception(
                    "An error occured in the ffmpeg subprocess:\n"
                    + exc.stderr.decode(*ENCODE_ARGS)
                ) from exc
            if res.stderr:
                print(res.stderr.decode(*ENCODE_ARGS), end="", file=sys.stderr)
            os.replace(mux_file_path, file_path)

        preview = {
            "filename": file,
            "subfolder": subfolder,
            "type": "output" if save_output else "temp",
        }
        return {
            "ui": {"images": [preview], "animated": (True,)},
            "result": ((save_output, output_files),),
        }


NODE_CLASS_MAPPINGS = {"WorkflowX_SaveVideoX": SaveVideoX}
NODE_DISPLAY_NAME_MAPPINGS = {"WorkflowX_SaveVideoX": "Save Video X"}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "SaveVideoX"]
