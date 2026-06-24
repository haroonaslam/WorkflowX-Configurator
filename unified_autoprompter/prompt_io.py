from __future__ import annotations

import json
import re
from typing import Any

from .profiles import FORMAT_JSON, FORMAT_TAGS, normalize_format


def assemble_prompt(positive: str, negative: str = "", negative_enabled: bool = False, prompt_format: str = "natural") -> str:
    positive = str(positive or "").strip()
    negative = str(negative or "").strip()
    if prompt_format == FORMAT_JSON:
        return positive
    if negative_enabled and negative:
        return f"Positive:\n{positive}\n\nNegative:\n{negative}"
    return positive


def build_outputs(
    target_model: str,
    prompt_format: str,
    positive: str = "",
    negative: str = "",
    final_prompt: str = "",
    negative_enabled: bool = False,
) -> tuple[str, str, str]:
    prompt_format = normalize_format(target_model, prompt_format)
    negative_enabled = bool(negative_enabled)
    positive = str(positive or "").strip()
    negative = str(negative or "").strip() if negative_enabled else ""
    final_prompt = str(final_prompt or "").strip()

    if final_prompt:
        prompt = final_prompt
    else:
        prompt = assemble_prompt(positive, negative, negative_enabled, prompt_format)
    return (prompt, positive, negative)


def build_layout_apply_outputs(layout_json: str, negative: str = "", negative_enabled: bool = False) -> tuple[str, str, str]:
    prompt = str(layout_json or "").strip()
    kept_negative = str(negative or "").strip() if negative_enabled else ""
    return (prompt, prompt, kept_negative)


def extract_json_object(text: str) -> dict[str, Any] | None:
    text = str(text or "").strip()
    if not text:
        return None

    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()

    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(text[start:index + 1])
                except json.JSONDecodeError:
                    return None
                return parsed if isinstance(parsed, dict) else None
    return None


def normalize_prompt_json(target_model: str, prompt_format: str, payload: Any) -> str:
    if isinstance(payload, str):
        parsed = extract_json_object(payload)
        if parsed is None:
            return payload.strip()
        payload = parsed

    if not isinstance(payload, dict):
        payload = {}
    return json.dumps(payload, indent=2, ensure_ascii=False)


def parse_generation_response(target_model: str, prompt_format: str, raw_text: str, negative_enabled: bool) -> dict[str, str]:
    prompt_format = normalize_format(target_model, prompt_format)
    raw_text = str(raw_text or "").strip()
    parsed = extract_json_object(raw_text)

    positive = ""
    negative = ""
    final_prompt = ""

    if isinstance(parsed, dict):
        if prompt_format == FORMAT_JSON:
            prompt_json = parsed.get("prompt_json")
            if isinstance(prompt_json, str):
                final_prompt = normalize_prompt_json(target_model, prompt_format, prompt_json)
            elif isinstance(prompt_json, dict):
                final_prompt = normalize_prompt_json(target_model, prompt_format, prompt_json)
            elif "positive" not in parsed and "negative" not in parsed:
                final_prompt = normalize_prompt_json(target_model, prompt_format, parsed)
            if negative_enabled:
                negative = str(parsed.get("negative") or "").strip()
            positive = final_prompt
        else:
            positive = str(parsed.get("positive") or parsed.get("prompt") or "").strip()
            if negative_enabled:
                negative = str(parsed.get("negative") or "").strip()
    else:
        positive = raw_text

    if prompt_format == FORMAT_TAGS and positive:
        positive = ", ".join(part.strip() for part in re.split(r",|\n", positive) if part.strip())

    if prompt_format == FORMAT_JSON and not final_prompt:
        final_prompt = normalize_prompt_json(target_model, prompt_format, positive or raw_text)
        positive = final_prompt

    final_prompt = final_prompt or assemble_prompt(positive, negative, negative_enabled, prompt_format)
    return {
        "prompt": final_prompt,
        "positive": positive,
        "negative": negative,
    }
