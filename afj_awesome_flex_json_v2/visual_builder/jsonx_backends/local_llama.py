from __future__ import annotations

import os
import re
import shlex
import struct
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from PIL import Image

from .llama_binary import ensure_llama_cli_paths
from .local_models import (
    NO_MMPROJ,
    NO_MODELS_FOUND,
    NO_SYSTEM_PROMPT,
    full_mmproj_path,
    full_model_path,
    full_system_prompt_path,
)


PROMPT_ECHO_END = "... (truncated)"
PROMPT_PADDING = " " * 501
PERF_RE = re.compile(r"\[\s*Prompt:\s*[^|\]]+\|\s*Generation:\s*[^\]]+\]")
MMPROJ_EMBEDDING_MISMATCH_RE = re.compile(
    r"mismatch between text model \(n_embd = (?P<model>\d+)\) and mmproj \(n_embd = (?P<mmproj>\d+)\)",
    flags=re.IGNORECASE,
)
MTP_LOADER_MISMATCH_RE = re.compile(
    r"missing tensor ['\"]blk\.\d+\.ssm_conv1d\.weight['\"]",
    flags=re.IGNORECASE,
)
THINK_RE = re.compile(
    r"^<think(?:\s[^>]*)?>(?P<thinking>.*?)</think\s*>(?P<response>.*)$",
    flags=re.IGNORECASE | re.DOTALL,
)
UNCLOSED_THINK_RE = re.compile(
    r"^<think(?:\s[^>]*)?>(?P<thinking>.*)$",
    flags=re.IGNORECASE | re.DOTALL,
)
START_THINKING = "[Start thinking]"
END_THINKING = "[End thinking]"
LLAMA_RANDOM_SEED = -1
LLAMA_SEED_MODULUS = 2**32
MAX_LLAMA_SEED = LLAMA_SEED_MODULUS - 1
GGUF_METADATA_TYPES = {
    0: ("B", 1),
    1: ("b", 1),
    2: ("H", 2),
    3: ("h", 2),
    4: ("I", 4),
    5: ("i", 4),
    6: ("f", 4),
    7: ("?", 1),
    10: ("Q", 8),
    11: ("q", 8),
    12: ("d", 8),
}
MTP_METADATA_KEYS = (
    "qwen35.nextn_predict_layers",
    "qwen3next.nextn_predict_layers",
)


def _write_temp_text(prefix: str, text: str) -> Path:
    fd, filename = tempfile.mkstemp(prefix=prefix, suffix=".txt")
    os.close(fd)
    path = Path(filename)
    try:
        path.write_text(text, encoding="utf-8", newline="\n")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def _write_temp_image(image: Image.Image) -> Path:
    fd, filename = tempfile.mkstemp(prefix="workflowx-jsonx-image-", suffix=".png")
    os.close(fd)
    path = Path(filename)
    try:
        image.convert("RGB").save(path, format="PNG")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def _cleanup(paths: list[Path | None] | tuple[Path | None, ...]) -> None:
    for path in paths:
        if path is None:
            continue
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def split_extra_args(extra_args: str) -> list[str]:
    if not extra_args or not extra_args.strip():
        return []
    return [part.strip("\"'") for part in shlex.split(extra_args, posix=(os.name != "nt"))]


def normalize_llama_seed(seed: int) -> int:
    number = int(seed)
    if number == LLAMA_RANDOM_SEED:
        return number
    if 0 <= number <= MAX_LLAMA_SEED:
        return number
    return number % LLAMA_SEED_MODULUS


def normalize_reasoning_mode(value: Any) -> str:
    mode = str(value or "auto").strip().lower()
    if mode == "none":
        return "off"
    if mode in {"deepseek", "qwen3"}:
        return "auto"
    return mode if mode in {"auto", "on", "off"} else "auto"


def _read_exact(handle, size: int) -> bytes:
    data = handle.read(size)
    if len(data) != size:
        raise ValueError("Unexpected end of GGUF metadata.")
    return data


def _read_u32(handle) -> int:
    return struct.unpack("<I", _read_exact(handle, 4))[0]


def _read_u64(handle) -> int:
    return struct.unpack("<Q", _read_exact(handle, 8))[0]


def _read_gguf_string(handle, *, capture: bool = True) -> str | None:
    length = _read_u64(handle)
    if length > 16 * 1024 * 1024:
        raise ValueError("GGUF metadata string is unreasonably large.")
    if not capture:
        handle.seek(length, 1)
        return None
    return _read_exact(handle, length).decode("utf-8", errors="replace")


def _read_or_skip_gguf_value(handle, value_type: int, *, capture: bool = False) -> Any:
    primitive = GGUF_METADATA_TYPES.get(value_type)
    if primitive:
        fmt, size = primitive
        raw = _read_exact(handle, size)
        return struct.unpack(f"<{fmt}", raw)[0] if capture else None
    if value_type == 8:
        return _read_gguf_string(handle, capture=capture)
    if value_type == 9:
        element_type = _read_u32(handle)
        count = _read_u64(handle)
        if count > 10_000_000:
            raise ValueError("GGUF metadata array is unreasonably large.")
        primitive_element = GGUF_METADATA_TYPES.get(element_type)
        if primitive_element and not capture:
            handle.seek(primitive_element[1] * count, 1)
            return None
        values = [] if capture else None
        for _index in range(count):
            item = _read_or_skip_gguf_value(handle, element_type, capture=capture)
            if capture:
                values.append(item)
        return values
    raise ValueError(f"Unsupported GGUF metadata value type: {value_type}")


def read_gguf_metadata(model_path: Path, wanted_keys: tuple[str, ...]) -> dict[str, Any]:
    wanted = set(wanted_keys)
    found: dict[str, Any] = {}
    with Path(model_path).open("rb") as handle:
        if _read_exact(handle, 4) != b"GGUF":
            raise ValueError("Selected model is not a GGUF file.")
        version = _read_u32(handle)
        if version not in {2, 3}:
            raise ValueError(f"Unsupported GGUF version: {version}")
        _tensor_count = _read_u64(handle)
        metadata_count = _read_u64(handle)
        if metadata_count > 1_000_000:
            raise ValueError("GGUF metadata entry count is unreasonably large.")
        for _index in range(metadata_count):
            key = _read_gguf_string(handle)
            value_type = _read_u32(handle)
            capture = key in wanted
            value = _read_or_skip_gguf_value(handle, value_type, capture=capture)
            if capture:
                found[key] = value
                break
    return found


def model_has_embedded_mtp(model_path: Path) -> bool:
    try:
        metadata = read_gguf_metadata(model_path, MTP_METADATA_KEYS)
        if metadata:
            return any(int(metadata.get(key) or 0) > 0 for key in MTP_METADATA_KEYS)
    except (OSError, TypeError, ValueError):
        pass
    filename = Path(model_path).stem.lower().replace("_", "-")
    return "mtp" in filename and "no-mtp" not in filename and "nomtp" not in filename


def _int(value: Any, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def _float(
    value: Any,
    default: float,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def build_command(
    *,
    model_path: Path,
    mmproj_path: Path | None,
    system_prompt_path: Path | None,
    system_prompt_text: str,
    pil_images: list[Image.Image] | None,
    prompt: str,
    options: dict[str, Any],
) -> tuple[list[str], tuple[Path | None, ...]]:
    cleanup_paths: list[Path | None] = []
    try:
        cli = ensure_llama_cli_paths().cli
        image_paths = []
        for image in pil_images or []:
            if mmproj_path is None:
                raise ValueError("Reference image input requires a selected mmproj GGUF file.")
            image_path = _write_temp_image(image)
            image_paths.append(image_path)
            cleanup_paths.append(image_path)

        prompt_path = _write_temp_text(
            "workflowx-jsonx-prompt-",
            str(prompt).strip() + PROMPT_PADDING,
        )
        cleanup_paths.append(prompt_path)

        system_path = system_prompt_path
        if str(system_prompt_text or "").strip():
            system_path = _write_temp_text("workflowx-jsonx-system-", system_prompt_text)
            cleanup_paths.append(system_path)

        memory_mode = str(options.get("memory_mode") or "auto")
        speculative_mode = str(options.get("speculative_mode") or "auto").strip().lower()
        if speculative_mode not in {"auto", "off", "mtp"}:
            raise ValueError(f"Unsupported local speculative decoding mode: {speculative_mode}")
        use_mtp = speculative_mode == "mtp" or (
            speculative_mode == "auto" and model_has_embedded_mtp(model_path)
        )
        command = [
            str(cli),
            "-m", str(model_path),
            "-n", str(_int(options.get("max_tokens"), 768, 32, 8192)),
            "--temp", str(_float(options.get("temperature"), 0.7, 0.0, 2.0)),
            "--top-p", str(_float(options.get("top_p"), 0.9, 0.0, 1.0)),
            "--top-k", str(_int(options.get("top_k"), 40, 0, 10000)),
            "--repeat-penalty", str(_float(options.get("repeat_penalty"), 1.05, 0.0, 5.0)),
            "-c", str(_int(options.get("ctx_size"), 8192, 512, 262144)),
            "--seed", str(normalize_llama_seed(_int(options.get("seed"), LLAMA_RANDOM_SEED))),
            "--single-turn",
            "--reasoning", normalize_reasoning_mode(options.get("reasoning")),
        ]
        if use_mtp:
            command.extend(
                [
                    "--spec-type", "draft-mtp",
                    "--spec-draft-n-max", str(_int(options.get("mtp_draft_tokens"), 2, 1, 8)),
                ]
            )
        elif speculative_mode == "off":
            command.extend(["--spec-type", "none"])
        if memory_mode in {"gpu_layers", "gpu_and_cpu_moe_layers"}:
            command.extend(["-ngl", str(_int(options.get("n_gpu_layers"), 99, 0, 999))])
        if memory_mode in {"cpu_moe_layers", "gpu_and_cpu_moe_layers"}:
            command.extend(["--n-cpu-moe", str(_int(options.get("n_cpu_moe_layers"), 0, 0, 999))])
        if system_path is not None:
            command.extend(["-sysf", str(system_path)])
        command.extend(["-f", str(prompt_path)])
        if image_paths:
            command.extend(["--mmproj", str(mmproj_path)])
            command.extend(["--image", ",".join(str(path) for path in image_paths)])
        command.extend(split_extra_args(str(options.get("extra_args") or "")))
        return command, tuple(cleanup_paths)
    except BaseException:
        _cleanup(cleanup_paths)
        raise


def generate(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    pil_images: list[Image.Image] | None = None,
    mmproj: str = NO_MMPROJ,
    system_prompt_preset: str = NO_SYSTEM_PROMPT,
    additional_model_paths: Any = None,
    options: dict[str, Any] | None = None,
) -> str:
    if not model or model == NO_MODELS_FOUND:
        raise ValueError("Select a local GGUF model from the configured model folders.")
    settings = dict(options or {})
    command, cleanup_paths = build_command(
        model_path=full_model_path(model, additional_model_paths),
        mmproj_path=full_mmproj_path(mmproj or NO_MMPROJ, additional_model_paths),
        system_prompt_path=full_system_prompt_path(system_prompt_preset or NO_SYSTEM_PROMPT),
        system_prompt_text=system_prompt,
        pil_images=pil_images,
        prompt=user_prompt,
        options=settings,
    )
    response, thinking, _perf = run_llama_cli(
        command,
        timeout_seconds=_int(settings.get("timeout"), 180, 5, 3600),
        cleanup_paths=cleanup_paths,
    )
    # When a reasoning model exhausts its generation budget before closing the
    # thinking channel, keep that transient text available to JsonX's one repair
    # pass. It is never written to prompt_json and is discarded when a final
    # response exists.
    return response or thinking


def run_llama_cli(
    command: list[str],
    timeout_seconds: int,
    cleanup_paths: tuple[Path | None, ...] = (),
) -> tuple[str, str, str]:
    process: subprocess.Popen | None = None
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
        stdout, stderr = _communicate(process, timeout_seconds)
        result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    except BaseException:
        if process is not None:
            _stop_process(process)
        raise
    finally:
        _cleanup(cleanup_paths)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        mismatch = MMPROJ_EMBEDDING_MISMATCH_RE.search(stderr)
        if mismatch:
            raise RuntimeError(
                "Selected mmproj does not match the text model "
                f"(model n_embd={mismatch.group('model')}, mmproj n_embd={mismatch.group('mmproj')})."
            )
        if MTP_LOADER_MISMATCH_RE.search(stderr):
            raise RuntimeError(
                "The selected GGUF contains an embedded MTP layer that this JsonX llama.cpp "
                "runtime cannot interpret. Update the isolated JsonX runtime and use "
                "Speculative decoding = Auto or MTP.\n\n"
                f"llama.cpp details:\n{stderr}"
            )
        raise RuntimeError(f"JsonX llama.cpp failed with exit code {result.returncode}:\n{stderr}")
    return _parse_response(result.stdout + "\n" + result.stderr)


def _stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def _communicate(process: subprocess.Popen, timeout_seconds: int) -> tuple[str, str]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            import comfy.model_management as model_management

            if model_management.processing_interrupted():
                _stop_process(process)
                model_management.throw_exception_if_processing_interrupted()
        except ImportError:
            pass
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _stop_process(process)
            raise TimeoutError(f"JsonX llama.cpp timed out after {timeout_seconds}s")
        try:
            return process.communicate(timeout=min(0.1, remaining))
        except subprocess.TimeoutExpired:
            continue


def _parse_response(text: str) -> tuple[str, str, str]:
    value = str(text or "")
    if PROMPT_ECHO_END in value:
        value = value.split(PROMPT_ECHO_END, 1)[1]
    perf_match = PERF_RE.search(value)
    perf = perf_match.group(0).strip() if perf_match else ""
    content = (value[:perf_match.start()] if perf_match else value).strip()
    tagged = THINK_RE.fullmatch(content)
    if tagged:
        return tagged.group("response").strip(), tagged.group("thinking").strip(), perf
    unclosed = UNCLOSED_THINK_RE.fullmatch(content)
    if unclosed:
        return "", unclosed.group("thinking").strip(), perf
    if content.startswith(START_THINKING):
        thinking_text = content[len(START_THINKING):]
        if END_THINKING not in thinking_text:
            return "", thinking_text.strip(), perf
        thinking, response = thinking_text.split(END_THINKING, 1)
        return response.strip(), thinking.strip(), perf
    return content, "", perf
