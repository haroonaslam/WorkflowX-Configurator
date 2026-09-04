"""Backend for Load AudioX.

The normal output is ComfyUI's AUDIO dictionary.  MP3/WAV are companion file
encodings; channel/rate/effect changes are applied to the returned PCM master.
The recovery code is deliberately narrow and never modifies the source file.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import mmap
import os
import re
import shutil
import struct
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import torch

import folder_paths


HIDDEN_INPUT = "LoadAudioXState"
MAX_FABRICATED_SECONDS = 3600.0
MAX_STATE_SECONDS = 86400.0
MAX_INPUT_BYTES = 8 * 1024 * 1024 * 1024
MIN_DECODE_SECONDS = 0.05
ENCODE_ARGS = ("utf-8", "backslashreplace")

AUDIO_EXTENSIONS = {
    ".wav", ".wave", ".mp3", ".flac", ".ogg", ".oga", ".opus",
    ".m4a", ".m4b", ".aac", ".3ga", ".amr", ".awb", ".wma",
    ".aiff", ".aif", ".alac", ".ac3", ".mka",
}
VIDEO_EXTENSIONS = {
    ".mp4", ".m4v", ".mov", ".3gp", ".3g2", ".mkv", ".webm",
    ".avi", ".wmv", ".asf", ".flv", ".mpeg", ".mpg", ".ts",
    ".mts", ".m2ts",
}
MEDIA_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS
MP3_BITRATES = ("64k", "96k", "128k", "160k", "192k", "256k", "320k")
WAV_DEPTHS = ("16-bit", "24-bit", "32-bit float")
CHANNEL_MODES = ("Source", "Mono", "Stereo")
SAMPLE_RATE_VALUES = {
    "Source": 0,
    "8 kHz": 8000,
    "16 kHz": 16000,
    "22.05 kHz": 22050,
    "24 kHz": 24000,
    "32 kHz": 32000,
    "44.1 kHz": 44100,
    "48 kHz": 48000,
    "96 kHz": 96000,
}

BASE_FILTERS = (
    "Denoise light", "De-click", "High-pass rumble cut", "Low-pass hiss cut",
    "De-esser light", "Presence boost", "Warmth", "Brightness",
    "Speech clarity", "Stereo widen", "Noise gate", "Voice compressor",
)

DEFAULT_STATE: dict[str, Any] = {
    "version": 1,
    "file": "",
    "start": 0.0,
    "length": 5.0,
    "when_unwired": "whole",
    "when_short": "silence",
    "format": "wav",
    "wav_depth": "16-bit",
    "mp3_bitrate": "192k",
    "channels": "Source",
    "sample_rate": "Source",
    "repair_mode": "auto",
    "filters": [],
    "gain_db": 0.0,
    "normalize": "Off",
    "target_lufs": -16.0,
    "limiter": False,
    "trim_silence": False,
    "silence_threshold_db": -50.0,
    "minimum_silence": 0.1,
    "fade_in": 0.0,
    "fade_out": 0.0,
    "save_output": False,
    "filename_prefix": "audio/LoadAudioX",
}


def _finite(value: object, fallback: float, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return fallback
    if not math.isfinite(number):
        return fallback
    return max(low, min(high, number))


def parse_state(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        raw = value
    else:
        try:
            raw = json.loads(str(value or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            raw = {}
    if not isinstance(raw, dict):
        raw = {}
    state = dict(DEFAULT_STATE)
    state["file"] = str(raw.get("file", "")) if isinstance(raw.get("file", ""), str) else ""
    state["start"] = _finite(raw.get("start"), 0.0, 0.0, MAX_STATE_SECONDS)
    state["length"] = _finite(raw.get("length"), 5.0, 0.0, MAX_STATE_SECONDS)
    state["when_unwired"] = "length" if raw.get("when_unwired") == "length" else "whole"
    state["when_short"] = "loop" if raw.get("when_short") == "loop" else "silence"
    state["format"] = "mp3" if str(raw.get("format", "")).lower() == "mp3" else "wav"
    state["wav_depth"] = raw.get("wav_depth") if raw.get("wav_depth") in WAV_DEPTHS else "16-bit"
    state["mp3_bitrate"] = raw.get("mp3_bitrate") if raw.get("mp3_bitrate") in MP3_BITRATES else "192k"
    state["channels"] = raw.get("channels") if raw.get("channels") in CHANNEL_MODES else "Source"
    state["sample_rate"] = raw.get("sample_rate") if raw.get("sample_rate") in SAMPLE_RATE_VALUES else "Source"
    state["repair_mode"] = "off" if raw.get("repair_mode") == "off" else "auto"
    filters = raw.get("filters", [])
    if isinstance(filters, str):
        try:
            filters = json.loads(filters)
        except (ValueError, json.JSONDecodeError):
            filters = [part.strip() for part in filters.split(",")]
    state["filters"] = [name for name in BASE_FILTERS if isinstance(filters, list) and name in filters]
    state["gain_db"] = _finite(raw.get("gain_db"), 0.0, -24.0, 24.0)
    state["normalize"] = raw.get("normalize") if raw.get("normalize") in ("Off", "Peak", "EBU R128") else "Off"
    state["target_lufs"] = _finite(raw.get("target_lufs"), -16.0, -30.0, -5.0)
    state["limiter"] = raw.get("limiter") is True
    state["trim_silence"] = raw.get("trim_silence") is True
    state["silence_threshold_db"] = _finite(raw.get("silence_threshold_db"), -50.0, -90.0, -10.0)
    state["minimum_silence"] = _finite(raw.get("minimum_silence"), 0.1, 0.0, 10.0)
    state["fade_in"] = _finite(raw.get("fade_in"), 0.0, 0.0, 60.0)
    state["fade_out"] = _finite(raw.get("fade_out"), 0.0, 0.0, 60.0)
    state["save_output"] = raw.get("save_output") is True
    prefix = raw.get("filename_prefix", DEFAULT_STATE["filename_prefix"])
    state["filename_prefix"] = str(prefix or DEFAULT_STATE["filename_prefix"])[:512]
    return state


def normalize_relative_path(value: object) -> str:
    raw = str(value or "").replace("\\", "/").strip()
    drive, _tail = os.path.splitdrive(raw)
    parts = raw.split("/")
    if not raw or raw.startswith("/") or drive or "\x00" in raw:
        raise ValueError("Invalid media path")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("Invalid media path")
    return "/".join(parts)


def resolve_media_path(value: object, folder_paths_module=None) -> tuple[str, Path]:
    module = folder_paths if folder_paths_module is None else folder_paths_module
    relative = normalize_relative_path(value)
    if Path(relative).suffix.lower() not in MEDIA_EXTENSIONS:
        raise ValueError("Unsupported audio or video file type")
    root = Path(module.get_input_directory()).resolve()
    candidate = (root / Path(*relative.split("/"))).resolve()
    try:
        contained = os.path.commonpath((str(root), str(candidate))) == str(root)
    except ValueError:
        contained = False
    if not contained:
        raise ValueError("Media path escapes the ComfyUI input directory")
    if not candidate.is_file():
        raise ValueError(f"Media file not found: {relative}")
    if candidate.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("Media file exceeds the 8 GiB Load AudioX safety limit")
    return relative, candidate


def list_media_files(folder_paths_module=None) -> list[str]:
    module = folder_paths if folder_paths_module is None else folder_paths_module
    root = Path(module.get_input_directory())
    if not root.is_dir():
        return []
    found: list[str] = []
    for path in root.rglob("*"):
        try:
            if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS:
                found.append(path.relative_to(root).as_posix())
        except OSError:
            continue
    return sorted(found, key=str.casefold)


def find_ffmpeg() -> str | None:
    candidates: list[str] = []
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        candidates.append(get_ffmpeg_exe())
    except Exception:
        pass
    system = shutil.which("ffmpeg")
    if system:
        candidates.append(system)
    return next((path for path in candidates if path and os.path.isfile(path)), None)


def _probe_with_av(path: Path) -> dict[str, Any]:
    import av
    with av.open(str(path)) as container:
        if not container.streams.audio:
            raise ValueError("No audio stream found")
        stream = container.streams.audio[0]
        rate = int(stream.codec_context.sample_rate or 0)
        channels = int(stream.codec_context.channels or 0)
        duration = 0.0
        if stream.duration is not None and stream.time_base is not None:
            duration = float(stream.duration * stream.time_base)
        elif container.duration is not None:
            duration = float(container.duration / av.time_base)
        return {
            "codec": str(stream.codec_context.name or "unknown"),
            "sample_rate": rate,
            "channels": channels,
            "duration": max(0.0, duration),
            "audio_streams": len(container.streams.audio),
            "video_streams": len(container.streams.video),
            "container": str(container.format.name or "unknown"),
        }


def _probe_with_ffmpeg(path: Path, ffmpeg: str) -> dict[str, Any]:
    result = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True)
    text = result.stderr.decode(*ENCODE_ARGS)
    line = next((line for line in text.splitlines() if "Audio:" in line), "")
    if not line:
        raise ValueError("No audio stream found")
    rate_match = re.search(r"(\d+)\s*Hz", line)
    channel_match = re.search(r"\b(mono|stereo|(\d+)\s+channels?)\b", line, re.I)
    codec_match = re.search(r"Audio:\s*([^,\s]+)", line)
    channels = 1 if channel_match and channel_match.group(1).lower() == "mono" else 2
    if channel_match and channel_match.group(2):
        channels = int(channel_match.group(2))
    return {
        "codec": codec_match.group(1) if codec_match else "unknown",
        "sample_rate": int(rate_match.group(1)) if rate_match else 48000,
        "channels": channels,
        "duration": 0.0,
        "audio_streams": 1,
        "video_streams": 0,
        "container": path.suffix.lower().lstrip("."),
    }


def probe_media(path: Path, ffmpeg: str | None = None) -> dict[str, Any]:
    try:
        return _probe_with_av(path)
    except Exception:
        executable = ffmpeg or find_ffmpeg()
        if not executable:
            raise ValueError("Unable to inspect audio and FFmpeg was not found")
        return _probe_with_ffmpeg(path, executable)


def _normal_decode(path: Path) -> tuple[torch.Tensor, int]:
    from comfy_extras.nodes_audio import load
    waveform, sample_rate = load(str(path))
    if waveform.ndim == 3 and waveform.shape[0] == 1:
        waveform = waveform.squeeze(0)
    if waveform.ndim != 2 or waveform.shape[-1] < 1:
        raise ValueError("No audio frames decoded")
    return waveform.float().cpu(), int(sample_rate)


def _tolerant_decode(path: Path, metadata: dict[str, Any], ffmpeg: str) -> tuple[torch.Tensor, int, str]:
    rate = int(metadata.get("sample_rate") or 48000)
    channels = max(1, int(metadata.get("channels") or 1))
    command = [
        ffmpeg, "-hide_banner", "-v", "warning",
        "-fflags", "+genpts+ignidx+discardcorrupt", "-err_detect", "ignore_err",
        "-i", str(path), "-map", "0:a:0", "-vn", "-sn", "-dn",
        "-ac", str(channels), "-ar", str(rate), "-c:a", "pcm_f32le", "-f", "f32le", "-",
    ]
    result = subprocess.run(command, capture_output=True)
    stderr = result.stderr.decode(*ENCODE_ARGS).strip()[-12000:]
    if result.returncode != 0 and not result.stdout:
        raise ValueError(stderr or "FFmpeg could not decode the audio stream")
    samples = np.frombuffer(result.stdout, dtype="<f4")
    usable = samples.size - (samples.size % channels)
    if usable < max(1, int(rate * MIN_DECODE_SECONDS) * channels):
        raise ValueError(stderr or "FFmpeg decoded no usable audio frames")
    array = samples[:usable].reshape(-1, channels).T.copy()
    return torch.from_numpy(array), rate, stderr


def _box_header(data, offset: int, limit: int) -> tuple[bytes, int, int, int] | None:
    if offset < 0 or offset + 8 > limit:
        return None
    size, kind = struct.unpack_from(">I4s", data, offset)
    header = 8
    if size == 1:
        if offset + 16 > limit:
            return None
        size = int(struct.unpack_from(">Q", data, offset + 8)[0])
        header = 16
    elif size == 0:
        size = limit - offset
    if size < header:
        return None
    return kind, size, header, offset + size


def _iter_boxes(data, start: int, limit: int) -> Iterable[tuple[bytes, int, int, int, int]]:
    position = start
    while position + 8 <= limit:
        parsed = _box_header(data, position, limit)
        if parsed is None:
            break
        kind, size, header, declared_end = parsed
        yield kind, position, header, declared_end, min(declared_end, limit)
        if declared_end <= position or declared_end > limit:
            break
        position = declared_end


def _children(data, parent: tuple[bytes, int, int, int, int]) -> list[tuple[bytes, int, int, int, int]]:
    _kind, start, header, _declared, actual = parent
    return list(_iter_boxes(data, start + header, actual))


def _find_child_path(data, parent, names: tuple[bytes, ...]):
    current = parent
    for name in names:
        current = next((box for box in _children(data, current) if box[0] == name), None)
        if current is None:
            return None
    return current


def _descriptor_length(data, offset: int, limit: int) -> tuple[int, int] | None:
    value = 0
    for count in range(4):
        if offset + count >= limit:
            return None
        byte = data[offset + count]
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, count + 1
    return None


def _aac_config_from_esds(data, start: int, end: int) -> tuple[int, int, int, bytes] | None:
    rates = (96000, 88200, 64000, 48000, 44100, 32000, 24000, 22050, 16000, 12000, 11025, 8000, 7350)
    position = start
    while position + 3 <= end:
        if data[position] != 0x05:
            position += 1
            continue
        parsed = _descriptor_length(data, position + 1, end)
        if parsed is None:
            position += 1
            continue
        length, used = parsed
        payload = position + 1 + used
        if length < 2 or payload + length > end:
            position += 1
            continue
        asc = bytes(data[payload:payload + length])
        object_type = asc[0] >> 3
        rate_index = ((asc[0] & 0x07) << 1) | (asc[1] >> 7)
        channels = (asc[1] >> 3) & 0x0F
        if object_type in (1, 2, 3, 4) and rate_index < len(rates) and channels in range(1, 8):
            return object_type, rate_index, channels, asc
        position += 1
    return None


def _shortest_period(values: list[int], maximum: int = 64) -> list[int] | None:
    for size in range(1, min(maximum, len(values) // 3) + 1):
        pattern = values[:size]
        if all(value == pattern[index % size] for index, value in enumerate(values)):
            return pattern
    return None


def inspect_truncated_aac(path: Path) -> dict[str, Any]:
    """Inspect the narrow, provable audio-only truncated-STSZ recovery case."""
    with path.open("rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
        file_size = len(data)
        top = list(_iter_boxes(data, 0, file_size))
        mdats = [box for box in top if box[0] == b"mdat"]
        mdat = mdats[0] if len(mdats) == 1 else None
        moov = next((box for box in top if box[0] == b"moov"), None)
        if mdat is None or moov is None:
            raise ValueError("Safe AAC reconstruction requires exactly one readable mdat and one moov")
        tracks = [box for box in _children(data, moov) if box[0] == b"trak"]
        if len(tracks) != 1:
            raise ValueError("Safe AAC reconstruction requires exactly one track")
        track = tracks[0]
        track_bytes = bytes(data[track[1]:track[4]])
        if any(marker in track_bytes for marker in (b"vide", b"enca", b"encv", b"sinf", b"cenc", b"pssh")):
            raise ValueError("Interleaved, video, or encrypted MP4 tracks cannot be safely reconstructed")
        mdia = _find_child_path(data, track, (b"mdia",))
        if mdia is None:
            raise ValueError("The damaged file has no readable audio track metadata")
        handlers = [box for box in _children(data, mdia) if box[0] == b"hdlr"]
        if not handlers or b"soun" not in bytes(data[handlers[0][1]:handlers[0][4]]):
            raise ValueError("The damaged MP4 track is not an audio track")
        stbl = _find_child_path(data, mdia, (b"minf", b"stbl"))
        if stbl is None:
            raise ValueError("The damaged file has no readable sample table")
        stsz = next((box for box in _children(data, stbl) if box[0] == b"stsz"), None)
        stsd = next((box for box in _children(data, stbl) if box[0] == b"stsd"), None)
        if stsz is None or stsd is None or stsz[3] <= file_size:
            raise ValueError("The AAC sample-size table is not truncated in a supported way")
        payload = stsz[1] + stsz[2]
        if payload + 12 > file_size:
            raise ValueError("The AAC sample-size header is incomplete")
        sample_size = int(struct.unpack_from(">I", data, payload + 4)[0])
        sample_count = int(struct.unpack_from(">I", data, payload + 8)[0])
        if sample_size or sample_count < 1 or sample_count > 10_000_000:
            raise ValueError("The damaged AAC sample count is unsupported")
        entry_start = payload + 12
        available_count = min(sample_count, max(0, (file_size - entry_start) // 4))
        sizes = [int(struct.unpack_from(">I", data, entry_start + 4 * index)[0]) for index in range(available_count)]
        if len(sizes) < 16 or any(size < 1 or size > 8184 for size in sizes):
            raise ValueError("Too few trustworthy AAC sample sizes survived")
        pattern = _shortest_period(sizes)
        if pattern is None:
            raise ValueError("The surviving AAC sample sizes do not form a safe repeatable pattern")
        predicted = [pattern[index % len(pattern)] for index in range(sample_count)]
        mdat_payload = mdat[1] + mdat[2]
        mdat_end = min(mdat[3], file_size)
        payload_length = mdat_end - mdat_payload
        if payload_length <= 0 or sum(predicted) != payload_length:
            raise ValueError("The inferred AAC sizes do not exactly match the intact media payload")
        stsd_bytes = bytes(data[stsd[1]:stsd[4]])
        esds_offset = stsd_bytes.find(b"esds")
        if b"mp4a" not in stsd_bytes or esds_offset < 4:
            raise ValueError("The damaged track is not supported AAC-in-MP4")
        esds_start = stsd[1] + esds_offset - 4
        esds = _box_header(data, esds_start, file_size)
        if esds is None:
            raise ValueError("The AAC codec configuration is incomplete")
        config = _aac_config_from_esds(data, esds_start + esds[2] + 4, min(esds[3], file_size))
        if config is None:
            raise ValueError("The AAC AudioSpecificConfig could not be read safely")
        object_type, rate_index, channels, asc = config
        return {
            "sample_count": sample_count,
            "known_sample_count": available_count,
            "pattern": pattern,
            "sizes": predicted,
            "mdat_payload": mdat_payload,
            "object_type": object_type,
            "rate_index": rate_index,
            "sample_rate": (96000, 88200, 64000, 48000, 44100, 32000, 24000, 22050, 16000, 12000, 11025, 8000, 7350)[rate_index],
            "channels": channels,
            "audio_specific_config": asc.hex(),
        }


def _adts_header(object_type: int, rate_index: int, channels: int, payload_size: int) -> bytes:
    profile = object_type - 1
    frame_length = payload_size + 7
    if profile not in range(4) or rate_index not in range(13) or channels not in range(1, 8) or frame_length > 8191:
        raise ValueError("Unsupported AAC parameters for ADTS recovery")
    return bytes((
        0xFF, 0xF1,
        (profile << 6) | (rate_index << 2) | (channels >> 2),
        ((channels & 3) << 6) | (frame_length >> 11),
        (frame_length >> 3) & 0xFF,
        ((frame_length & 7) << 5) | 0x1F,
        0xFC,
    ))


def recover_truncated_aac(path: Path, destination: Path) -> dict[str, Any]:
    info = inspect_truncated_aac(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    try:
        with path.open("rb") as source, partial.open("wb") as output:
            source.seek(info["mdat_payload"])
            for size in info["sizes"]:
                payload = source.read(size)
                if len(payload) != size:
                    raise ValueError("The AAC payload ended before the inferred sample table")
                output.write(_adts_header(info["object_type"], info["rate_index"], info["channels"], size))
                output.write(payload)
        os.replace(partial, destination)
    finally:
        try:
            partial.unlink(missing_ok=True)
        except OSError:
            pass
    return info


def _safe_token(value: object) -> str:
    token = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "api"))[:80]
    return token or "api"


def _temp_root(folder_paths_module=None) -> Path:
    module = folder_paths if folder_paths_module is None else folder_paths_module
    getter = getattr(module, "get_temp_directory", None)
    root = Path(getter() if callable(getter) else tempfile.gettempdir()) / "workflowx_load_audio_x"
    root.mkdir(parents=True, exist_ok=True)
    return root


def clean_stale_cache(folder_paths_module=None, max_age_seconds: float = 7 * 86400) -> int:
    """Remove only old Load AudioX artifacts and abandoned atomic partials."""
    root = _temp_root(folder_paths_module)
    cutoff = time.time() - max(0.0, max_age_seconds)
    removed = 0
    for path in root.rglob("*"):
        try:
            if path.is_file() and (path.name.endswith(".part") or path.stat().st_mtime < cutoff):
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def decode_source(path: Path, *, unique_id: object = None, allow_repair: bool = True, ffmpeg: str | None = None) -> tuple[torch.Tensor, int, dict[str, Any]]:
    executable = ffmpeg or find_ffmpeg()
    metadata = probe_media(path, executable)
    status = {**metadata, "repair": "none", "warning": ""}
    try:
        waveform, rate = _normal_decode(path)
        return waveform, rate, status
    except Exception as normal_error:
        status["normal_error"] = str(normal_error)
    if executable:
        try:
            waveform, rate, warning = _tolerant_decode(path, metadata, executable)
            status["repair"] = "tolerant decode"
            status["warning"] = warning
            return waveform, rate, status
        except Exception as tolerant_error:
            status["tolerant_error"] = str(tolerant_error)
    if not allow_repair:
        inspect_truncated_aac(path)
        raise ValueError("Audio needs repair before it can be previewed")
    if not executable:
        raise ValueError("FFmpeg is required to recover this audio")
    recovered = _temp_root() / f"repair_{_safe_token(unique_id)}.aac"
    info = recover_truncated_aac(path, recovered)
    repaired_meta = {
        "sample_rate": info["sample_rate"],
        "channels": info["channels"],
    }
    waveform, rate, warning = _tolerant_decode(recovered, repaired_meta, executable)
    expected = info["sample_count"] * 1024 / float(rate)
    actual = waveform.shape[-1] / float(rate)
    if abs(actual - expected) > max(0.1, 2048 / float(rate)):
        raise ValueError("Recovered AAC duration did not match the reconstructed sample table")
    status["repair"] = "reconstructed truncated AAC sample table"
    status["warning"] = warning
    status["recovery"] = {key: info[key] for key in ("sample_count", "known_sample_count", "pattern")}
    return waveform, rate, status


def _window_plan(total: int, rate: int, start_seconds: float, duration_seconds: float) -> dict[str, int]:
    start = min(total, max(0, int(round(start_seconds * rate))))
    available = total - start
    wanted = available if duration_seconds <= 0 else max(0, int(round(duration_seconds * rate)))
    return {"start": start, "wanted": wanted, "take": min(wanted, available)}


def _fill_to_length(waveform: torch.Tensor, wanted: int, mode: str) -> torch.Tensor:
    if waveform.shape[-1] >= wanted:
        return waveform[..., :wanted]
    missing = wanted - waveform.shape[-1]
    if mode == "loop" and waveform.shape[-1] > 0:
        indexes = torch.arange(missing, device=waveform.device) % waveform.shape[-1]
        return torch.cat((waveform, waveform.index_select(-1, indexes)), dim=-1)
    padding = torch.zeros((*waveform.shape[:-1], missing), dtype=waveform.dtype, device=waveform.device)
    return torch.cat((waveform, padding), dim=-1)


def _trim_boundary_silence(waveform: torch.Tensor, rate: int, threshold_db: float, minimum_seconds: float) -> torch.Tensor:
    if waveform.shape[-1] < 1:
        return waveform
    threshold = 10.0 ** (threshold_db / 20.0)
    active = waveform.abs().amax(dim=0) > threshold
    indexes = active.nonzero(as_tuple=False).flatten()
    if indexes.numel() == 0:
        return waveform[..., :0]
    first, last = int(indexes[0]), int(indexes[-1]) + 1
    minimum = int(round(minimum_seconds * rate))
    if first < minimum:
        first = 0
    if waveform.shape[-1] - last < minimum:
        last = waveform.shape[-1]
    return waveform[..., first:last]


def _filter_chain(state: dict[str, Any], rate: int, channels: int) -> tuple[list[str], list[str]]:
    selected = set(state["filters"])
    warning: list[str] = []
    nyquist_safe = max(100, int(rate * 0.45))
    frequency = lambda value: min(value, nyquist_safe)
    mapping = {
        "Denoise light": "afftdn=nr=8:nf=-25",
        "De-click": "adeclick",
        "High-pass rumble cut": f"highpass=f={frequency(80)}",
        "Low-pass hiss cut": f"lowpass=f={frequency(12000)}",
        "De-esser light": "deesser=i=0.2",
        "Presence boost": f"equalizer=f={frequency(3500)}:t=q:w=1:g=3",
        "Warmth": f"equalizer=f={frequency(180)}:t=q:w=1:g=2",
        "Brightness": f"equalizer=f={frequency(8000)}:t=q:w=1:g=2",
        "Speech clarity": f"equalizer=f={frequency(2500)}:t=q:w=1:g=3",
        "Stereo widen": "extrastereo=m=1.5",
        "Voice compressor": "acompressor=threshold=0.125:ratio=3:attack=20:release=250:makeup=1.5",
        "Noise gate": "agate=threshold=0.02:ratio=2:attack=20:release=250",
    }
    chain: list[str] = []
    for name in BASE_FILTERS:
        if name not in selected:
            continue
        if name == "Stereo widen" and channels < 2:
            warning.append("Stereo widen was skipped for mono output")
            continue
        chain.append(mapping[name])
    if state["gain_db"]:
        chain.append(f"volume={state['gain_db']:.3f}dB")
    if state["normalize"] == "EBU R128":
        chain.append(f"loudnorm=I={state['target_lufs']:.1f}:TP=-1.5:LRA=11")
    return chain, warning


def _convert_with_ffmpeg(waveform: torch.Tensor, source_rate: int, target_rate: int, target_channels: int, state: dict[str, Any], ffmpeg: str) -> tuple[torch.Tensor, list[str]]:
    effects, warnings = _filter_chain(state, target_rate, target_channels)
    layout = "mono" if target_channels == 1 else "stereo"
    chain = [f"aresample={target_rate}", f"aformat=sample_fmts=fltp:channel_layouts={layout}", *effects]
    command = [
        ffmpeg, "-hide_banner", "-v", "error", "-f", "f32le", "-ar", str(source_rate),
        "-ac", str(waveform.shape[0]), "-i", "-",
    ]
    command += ["-af", ",".join(chain)]
    command += ["-ar", str(target_rate), "-ac", str(target_channels), "-c:a", "pcm_f32le", "-f", "f32le", "-"]
    payload = waveform.transpose(0, 1).contiguous().numpy().astype("<f4", copy=False).tobytes()
    result = subprocess.run(command, input=payload, capture_output=True)
    if result.returncode != 0:
        raise ValueError("Audio processing failed: " + result.stderr.decode(*ENCODE_ARGS).strip())
    samples = np.frombuffer(result.stdout, dtype="<f4")
    usable = samples.size - samples.size % target_channels
    if usable <= 0:
        raise ValueError("Audio processing produced no samples")
    output = torch.from_numpy(samples[:usable].reshape(-1, target_channels).T.copy())
    return output, warnings


def _apply_peak_normalization(waveform: torch.Tensor) -> torch.Tensor:
    peak = float(waveform.abs().max()) if waveform.numel() else 0.0
    target = 10.0 ** (-1.0 / 20.0)
    return waveform * (target / peak) if peak > 1e-9 else waveform


def _apply_fades(waveform: torch.Tensor, rate: int, fade_in: float, fade_out: float) -> torch.Tensor:
    length = waveform.shape[-1]
    if length < 1:
        return waveform
    count_in = min(length, int(round(fade_in * rate)))
    count_out = min(length, int(round(fade_out * rate)))
    output = waveform.clone()
    if count_in > 0:
        output[..., :count_in] *= torch.linspace(0.0, 1.0, count_in, dtype=output.dtype)
    if count_out > 0:
        output[..., -count_out:] *= torch.linspace(1.0, 0.0, count_out, dtype=output.dtype)
    return output


def process_audio(waveform: torch.Tensor, source_rate: int, state: dict[str, Any], seconds: object = None, ffmpeg: str | None = None) -> tuple[torch.Tensor, int, dict[str, Any]]:
    executable = ffmpeg or find_ffmpeg()
    if not executable:
        raise ValueError("Load AudioX requires FFmpeg for conversion and encoding")
    fixed_duration = seconds is not None or state["when_unwired"] == "length"
    duration = 0.0 if not fixed_duration else (
        state["length"] if seconds is None else _finite(seconds, 0.0, 0.0, MAX_STATE_SECONDS)
    )
    available_seconds = waveform.shape[-1] / float(source_rate)
    if duration > MAX_FABRICATED_SECONDS and duration > available_seconds:
        raise ValueError("Requested audio would fabricate more than one hour beyond the source")
    plan = _window_plan(waveform.shape[-1], source_rate, state["start"], duration)
    selected = waveform[..., plan["start"]:plan["start"] + plan["take"]]
    if state["trim_silence"]:
        selected = _trim_boundary_silence(selected, source_rate, state["silence_threshold_db"], state["minimum_silence"])
    if fixed_duration and plan["wanted"] > 0:
        selected = _fill_to_length(selected, plan["wanted"], state["when_short"])
    if selected.shape[-1] < 1:
        raise ValueError("The selected range contains no usable audio")
    source_channels = selected.shape[0]
    if state["channels"] == "Mono":
        target_channels = 1
    elif state["channels"] == "Stereo":
        target_channels = 2
    else:
        target_channels = source_channels if source_channels in (1, 2) else 2
    target_rate = SAMPLE_RATE_VALUES[state["sample_rate"]] or source_rate
    converted, warnings = _convert_with_ffmpeg(selected, source_rate, target_rate, target_channels, state, executable)
    target_samples = int(round((plan["wanted"] / source_rate) * target_rate)) if fixed_duration and plan["wanted"] else converted.shape[-1]
    converted = _fill_to_length(converted, max(1, target_samples), "silence")
    if state["normalize"] == "Peak":
        converted = _apply_peak_normalization(converted)
    if state["limiter"]:
        converted = converted.clamp(-0.95, 0.95)
    converted = _apply_fades(converted, target_rate, state["fade_in"], state["fade_out"])
    converted = converted.clamp(-1.0, 1.0).contiguous()
    return converted, target_rate, {
        "source_channels": source_channels,
        "channels": target_channels,
        "sample_rate": target_rate,
        "duration": converted.shape[-1] / float(target_rate),
        "warnings": warnings,
    }


def _destination(state: dict[str, Any], unique_id: object, folder_paths_module=None) -> Path:
    module = folder_paths if folder_paths_module is None else folder_paths_module
    extension = state["format"]
    if state["save_output"]:
        output_root = module.get_output_directory()
        folder, filename, counter, _subfolder, _prefix = module.get_save_image_path(state["filename_prefix"], output_root)
        return Path(folder) / f"{filename}_{counter:05}.{extension}"
    root = _temp_root(module) / "converted"
    root.mkdir(parents=True, exist_ok=True)
    token = _safe_token(unique_id)
    return root / f"node_{token}.{extension}"


def encode_audio(waveform: torch.Tensor, rate: int, state: dict[str, Any], destination: Path, ffmpeg: str | None = None) -> None:
    executable = ffmpeg or find_ffmpeg()
    if not executable:
        raise ValueError("FFmpeg is required to encode audio")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    codec_args = (
        ["-c:a", "libmp3lame", "-b:a", state["mp3_bitrate"], "-f", "mp3"]
        if state["format"] == "mp3"
        else ["-c:a", {"16-bit": "pcm_s16le", "24-bit": "pcm_s24le", "32-bit float": "pcm_f32le"}[state["wav_depth"]], "-f", "wav"]
    )
    payload = waveform.transpose(0, 1).contiguous().numpy().astype("<f4", copy=False).tobytes()
    command = [
        executable, "-hide_banner", "-v", "error", "-y", "-f", "f32le", "-ar", str(rate),
        "-ac", str(waveform.shape[0]), "-i", "-", *codec_args, str(partial),
    ]
    try:
        result = subprocess.run(command, input=payload, capture_output=True)
        if result.returncode != 0:
            raise ValueError("Audio encoding failed: " + result.stderr.decode(*ENCODE_ARGS).strip())
        os.replace(partial, destination)
    finally:
        try:
            partial.unlink(missing_ok=True)
        except OSError:
            pass


def waveform_peaks(waveform: torch.Tensor, buckets: int = 320) -> list[float]:
    if waveform.shape[-1] < 1:
        return []
    mono = waveform.abs().amax(dim=0)
    if mono.numel() < buckets:
        mono = torch.nn.functional.pad(mono, (0, buckets - mono.numel()))
    length = mono.numel()
    edges = torch.linspace(0, length, buckets + 1).long()
    peaks = [float(mono[edges[index]:max(edges[index] + 1, edges[index + 1])].max()) for index in range(buckets)]
    maximum = max(peaks, default=0.0)
    return [value / maximum for value in peaks] if maximum > 1e-7 else peaks


def _preview_file(waveform: torch.Tensor, rate: int, node_id: object, ffmpeg: str) -> tuple[Path, dict[str, str]]:
    state = parse_state({"format": "mp3", "mp3_bitrate": "128k"})
    subfolder = Path("workflowx_load_audio_x") / "previews"
    path = _temp_root().parent / subfolder / f"node_{_safe_token(node_id)}.mp3"
    encode_audio(waveform, rate, state, path, ffmpeg)
    return path, {"filename": path.name, "subfolder": subfolder.as_posix(), "type": "temp"}


def analyze_file(relative: str, node_id: object, repair: bool) -> dict[str, Any]:
    _relative, path = resolve_media_path(relative)
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise ValueError("FFmpeg was not found")
    try:
        waveform, rate, status = decode_source(path, unique_id=node_id, allow_repair=repair, ffmpeg=ffmpeg)
    except Exception as exc:
        recoverable = False
        detail = str(exc)
        try:
            recovery = inspect_truncated_aac(path)
            recoverable = True
            detail = f"Truncated AAC table; {recovery['known_sample_count']} of {recovery['sample_count']} sizes survived"
        except Exception:
            pass
        return {"ok": False, "error": str(exc), "recoverable": recoverable, "detail": detail}
    _path, preview = _preview_file(waveform, rate, node_id, ffmpeg)
    duration = waveform.shape[-1] / float(rate)
    return {
        "ok": True,
        "file": relative,
        "duration": duration,
        "sample_rate": rate,
        "channels": waveform.shape[0],
        "codec": status.get("codec", "unknown"),
        "container": status.get("container", "unknown"),
        "repair": status.get("repair", "none"),
        "warning": status.get("warning", ""),
        "peaks": waveform_peaks(waveform),
        "preview": preview,
    }


async def files_handler(_request):
    from aiohttp import web
    files = await asyncio.to_thread(list_media_files)
    return web.json_response({"files": files}, headers={"Cache-Control": "no-store"})


async def _json_body(request) -> dict[str, Any]:
    try:
        body = await request.json()
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}


async def analyze_handler(request):
    from aiohttp import web
    body = await _json_body(request)
    result = await asyncio.to_thread(analyze_file, str(body.get("file", "")), body.get("node_id"), False)
    return web.json_response(result, status=200 if result.get("ok") else 422, headers={"Cache-Control": "no-store"})


async def repair_handler(request):
    from aiohttp import web
    body = await _json_body(request)
    result = await asyncio.to_thread(analyze_file, str(body.get("file", "")), body.get("node_id"), True)
    return web.json_response(result, status=200 if result.get("ok") else 422, headers={"Cache-Control": "no-store"})


class LoadAudioX:
    DESCRIPTION = (
        "Loads, previews, trims, repairs common damaged audio, converts channels/sample rate, "
        "applies audio cleanup, and emits processed ComfyUI AUDIO plus an MP3/WAV path."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "seconds": ("FLOAT", {"forceInput": True, "min": 0.0, "step": 0.001, "tooltip": "Optional fixed output duration."}),
            },
            "hidden": {HIDDEN_INPUT: ("STRING", {"default": "{}"}), "unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("AUDIO", "STRING")
    RETURN_NAMES = ("audio", "converted_path")
    OUTPUT_TOOLTIPS = (
        "Trimmed and fully processed PCM audio for downstream ComfyUI nodes.",
        "Absolute path to the converted MP3 or WAV file.",
    )
    FUNCTION = "load_audio"
    CATEGORY = "WorkflowX/Audio"
    OUTPUT_NODE = True

    def load_audio(self, seconds=None, LoadAudioXState="{}", unique_id=None):
        state = parse_state(LoadAudioXState)
        relative, path = resolve_media_path(state["file"])
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            raise ValueError("Load AudioX requires FFmpeg, but no executable was found")
        waveform, source_rate, decode_status = decode_source(
            path, unique_id=unique_id, allow_repair=state["repair_mode"] == "auto", ffmpeg=ffmpeg
        )
        processed, output_rate, process_status = process_audio(waveform, source_rate, state, seconds, ffmpeg)
        destination = _destination(state, unique_id)
        encode_audio(processed, output_rate, state, destination, ffmpeg)
        if not state["save_output"]:
            other = "mp3" if state["format"] == "wav" else "wav"
            try:
                destination.with_suffix(f".{other}").unlink(missing_ok=True)
            except OSError:
                pass
        status = {
            "file": relative,
            "codec": decode_status.get("codec", "unknown"),
            "source_sample_rate": source_rate,
            "source_channels": waveform.shape[0],
            "repair": decode_status.get("repair", "none"),
            "warning": " · ".join(filter(None, [decode_status.get("warning", ""), *process_status["warnings"]])),
            "format": state["format"],
            "sample_rate": output_rate,
            "channels": processed.shape[0],
            "duration": round(process_status["duration"], 4),
            "saved": state["save_output"],
            "path": str(destination.resolve()),
            "warnings": process_status["warnings"],
        }
        return {
            "ui": {"workflowx_load_audio_x": [status]},
            "result": ({"waveform": processed.unsqueeze(0), "sample_rate": output_rate}, str(destination.resolve())),
        }

    @classmethod
    def IS_CHANGED(cls, seconds=None, LoadAudioXState="{}", **_kwargs):
        state = parse_state(LoadAudioXState)
        try:
            _relative, path = resolve_media_path(state["file"])
            stat_result = path.stat()
            payload = json.dumps({"state": state, "seconds": seconds}, sort_keys=True, separators=(",", ":"))
            return hashlib.sha256(f"{stat_result.st_mtime_ns}:{stat_result.st_size}:{payload}".encode()).hexdigest()
        except Exception:
            return float("nan")

    @classmethod
    def VALIDATE_INPUTS(cls, LoadAudioXState="{}", **_kwargs):
        state = parse_state(LoadAudioXState)
        try:
            resolve_media_path(state["file"])
        except (OSError, ValueError) as exc:
            return str(exc)
        return True


NODE_CLASS_MAPPINGS = {"WorkflowX_LoadAudioX": LoadAudioX}
NODE_DISPLAY_NAME_MAPPINGS = {"WorkflowX_LoadAudioX": "Load AudioX"}


__all__ = [
    "BASE_FILTERS", "DEFAULT_STATE", "LoadAudioX", "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS", "analyze_file", "decode_source", "encode_audio",
    "clean_stale_cache", "inspect_truncated_aac", "list_media_files", "parse_state", "process_audio",
    "recover_truncated_aac", "resolve_media_path", "waveform_peaks",
]
