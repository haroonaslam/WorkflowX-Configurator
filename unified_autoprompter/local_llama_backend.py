from __future__ import annotations

import base64
import os
import re
import shlex
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from PIL import Image

from .folder_registry import (
    NO_MMPROJ,
    NO_MODELS_FOUND,
    NO_SYSTEM_PROMPT,
    full_mmproj_path,
    full_model_path,
    full_system_prompt_path,
)
from .llama_binary import ensure_llama_cli_paths


PROMPT_ECHO_END = "... (truncated)"
PROMPT_PADDING = " " * 501
PERF_RE = re.compile(r"\[\s*Prompt:\s*[^|\]]+\|\s*Generation:\s*[^\]]+\]")
MMPROJ_EMBEDDING_MISMATCH_RE = re.compile(
    r"mismatch between text model \(n_embd = (?P<model>\d+)\) and mmproj \(n_embd = (?P<mmproj>\d+)\)",
    flags=re.IGNORECASE,
)
START_THINKING = "[Start thinking]"
END_THINKING = "[End thinking]"
LLAMA_RANDOM_SEED = -1
LLAMA_SEED_MODULUS = 2**32
MAX_LLAMA_SEED = LLAMA_SEED_MODULUS - 1


def _write_temp_text_file(prefix: str, text: str) -> Path:
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=".txt")
    os.close(fd)
    text_path = Path(path)
    text_path.write_text(text, encoding="utf-8", newline="\n")
    return text_path


def _write_prompt_file(prompt: str) -> Path:
    return _write_temp_text_file("workflowx-uap-prompt-", str(prompt).strip() + PROMPT_PADDING)


def _pil_to_temp_png(pil_image: Image.Image) -> Path:
    fd, path = tempfile.mkstemp(prefix="workflowx-uap-image-", suffix=".png")
    os.close(fd)
    out = Path(path)
    pil_image.convert("RGB").save(out, format="PNG")
    return out


def image_b64_to_pil(image_b64: str | None) -> Image.Image | None:
    if not image_b64:
        return None
    data = str(image_b64)
    if "," in data:
        data = data.split(",", 1)[1]
    raw = base64.b64decode(data)
    from io import BytesIO

    return Image.open(BytesIO(raw)).convert("RGB")


def split_extra_args(extra_args: str) -> list[str]:
    if not extra_args or not extra_args.strip():
        return []
    parts = shlex.split(extra_args, posix=(os.name != "nt"))
    return [part.strip("\"'") for part in parts]


def normalize_llama_seed(seed: int) -> int:
    seed = int(seed)
    if seed == LLAMA_RANDOM_SEED:
        return LLAMA_RANDOM_SEED
    if 0 <= seed <= MAX_LLAMA_SEED:
        return seed
    return seed % LLAMA_SEED_MODULUS


def _int_value(value: Any, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def _float_value(value: Any, default: float, minimum: float | None = None, maximum: float | None = None) -> float:
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
    model_path: Path,
    mmproj_path: Path | None,
    system_prompt_path: Path | None,
    system_prompt_text: str,
    pil_image: Image.Image | None,
    prompt: str,
    options: dict[str, Any],
) -> tuple[list[str], tuple[Path | None, ...]]:
    cleanup_paths: list[Path | None] = []
    cli_paths = ensure_llama_cli_paths()
    image_paths: list[Path] = []
    if pil_image is not None:
        if mmproj_path is None:
            raise ValueError("Reference image input requires a selected mmproj GGUF file.")
        image_path = _pil_to_temp_png(pil_image)
        image_paths.append(image_path)
        cleanup_paths.append(image_path)

    prompt_path = _write_prompt_file(prompt)
    cleanup_paths.append(prompt_path)
    memory_mode = str(options.get("memory_mode") or "auto")
    reasoning = str(options.get("reasoning") or "auto")

    command = [
        str(cli_paths.cli),
        "-m", str(model_path),
        "-n", str(_int_value(options.get("max_tokens"), 768, 32, 8192)),
        "--temp", str(_float_value(options.get("temperature"), 0.7, 0.0, 2.0)),
        "--top-p", str(_float_value(options.get("top_p"), 0.9, 0.0, 1.0)),
        "--top-k", str(_int_value(options.get("top_k"), 40, 0, 10000)),
        "--repeat-penalty", str(_float_value(options.get("repeat_penalty"), 1.05, 0.0, 5.0)),
        "-c", str(_int_value(options.get("ctx_size"), 8192, 512, 262144)),
        "--seed", str(normalize_llama_seed(_int_value(options.get("seed"), LLAMA_RANDOM_SEED))),
        "--single-turn",
        "--reasoning", reasoning,
    ]

    if memory_mode in {"gpu_layers", "gpu_and_cpu_moe_layers"}:
        command.extend(["-ngl", str(_int_value(options.get("n_gpu_layers"), 99, 0, 999))])
    if memory_mode in {"cpu_moe_layers", "gpu_and_cpu_moe_layers"}:
        command.extend(["--n-cpu-moe", str(_int_value(options.get("n_cpu_moe_layers"), 0, 0, 999))])

    direct_system_prompt = str(system_prompt_text or "")
    if direct_system_prompt.strip():
        command.extend(["-sys", direct_system_prompt])
    elif system_prompt_path is not None:
        command.extend(["-sysf", str(system_prompt_path)])

    command.extend(["-f", str(prompt_path)])

    if image_paths:
        command.extend(["--mmproj", str(mmproj_path)])
        command.extend(["--image", ",".join(str(path) for path in image_paths)])

    command.extend(split_extra_args(str(options.get("extra_args") or "")))
    return command, tuple(cleanup_paths)


def generate(
    model: str,
    system_prompt: str,
    user_prompt: str,
    pil_image: Image.Image | None = None,
    mmproj: str = NO_MMPROJ,
    system_prompt_preset: str = NO_SYSTEM_PROMPT,
    options: dict[str, Any] | None = None,
) -> str:
    if not model or model == NO_MODELS_FOUND:
        raise ValueError("Select a local GGUF model from ComfyUI/models/LLM.")

    options = options or {}
    model_path = full_model_path(model)
    mmproj_path = full_mmproj_path(mmproj or NO_MMPROJ)
    preset_path = full_system_prompt_path(system_prompt_preset or NO_SYSTEM_PROMPT)
    command, cleanup_paths = build_command(
        model_path=model_path,
        mmproj_path=mmproj_path,
        system_prompt_path=preset_path,
        system_prompt_text=system_prompt,
        pil_image=pil_image,
        prompt=user_prompt,
        options=options,
    )
    response, _thinking, _perf = run_llama_cli(
        command,
        timeout_seconds=_int_value(options.get("timeout"), 180, 5, 3600),
        cleanup_paths=cleanup_paths,
    )
    return response


def run_llama_cli(
    command: list[str],
    timeout_seconds: int,
    cleanup_paths: tuple[Path | None, ...] = (),
) -> tuple[str, str, str]:
    process = None
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
        stdout, stderr = _communicate_with_interrupt(process, timeout_seconds)
        result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    except BaseException:
        if process is not None:
            _stop_process(process)
        raise
    finally:
        for path in cleanup_paths:
            if path and path.exists():
                path.unlink()

    if result.returncode != 0:
        stderr = result.stderr.strip()
        message = _parse_llama_error(stderr)
        if message:
            raise RuntimeError(message)
        raise RuntimeError(
            f"llama.cpp inference failed with exit code {result.returncode}:\n{stderr}"
        )
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


def _communicate_with_interrupt(process: subprocess.Popen, timeout_seconds: int) -> tuple[str, str]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        if _processing_interrupted():
            _stop_process(process)
            _throw_if_interrupted()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _stop_process(process)
            raise TimeoutError(f"llama.cpp timed out after {timeout_seconds}s")
        try:
            return process.communicate(timeout=min(0.1, remaining))
        except subprocess.TimeoutExpired:
            continue


def _processing_interrupted() -> bool:
    try:
        import comfy.model_management as model_management

        return bool(model_management.processing_interrupted())
    except Exception:
        return False


def _throw_if_interrupted() -> None:
    try:
        import comfy.model_management as model_management

        model_management.throw_exception_if_processing_interrupted()
    except Exception:
        raise RuntimeError("llama.cpp generation was interrupted.")


def _parse_response(text: str) -> tuple[str, str, str]:
    text = str(text or "")
    if PROMPT_ECHO_END in text:
        text = text.split(PROMPT_ECHO_END, 1)[1]

    perf_match = PERF_RE.search(text)
    perf = perf_match.group(0).strip() if perf_match else ""
    content = text[:perf_match.start()] if perf_match else text
    content = content.strip()
    if not content.startswith(START_THINKING):
        return content, "", perf

    thinking_text = content[len(START_THINKING):]
    if END_THINKING not in thinking_text:
        return "", thinking_text.strip(), perf

    thinking, response = thinking_text.split(END_THINKING, 1)
    return response.strip(), thinking.strip(), perf


def _parse_llama_error(stderr: str) -> str:
    match = MMPROJ_EMBEDDING_MISMATCH_RE.search(str(stderr or ""))
    if not match:
        return ""
    return (
        "Selected mmproj does not match the text model "
        f"(model n_embd={match.group('model')}, mmproj n_embd={match.group('mmproj')}). "
        "Choose the mmproj file that belongs to the selected GGUF model."
    )
