from __future__ import annotations

import json
import re
from typing import Any


AUDIT_NONE = "none"
AUDIT_ADD_PASS = "add_pass"
AUDIT_ONLY = "audit_only"
AUDIT_MODES = (AUDIT_NONE, AUDIT_ADD_PASS, AUDIT_ONLY)


class AuditValidationError(ValueError):
    pass


def normalize_mode(value: Any) -> str:
    mode = str(value or AUDIT_NONE).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {"no_audit": AUDIT_NONE, "add_audit_pass": AUDIT_ADD_PASS}
    mode = aliases.get(mode, mode)
    if mode not in AUDIT_MODES:
        raise ValueError(f"Unknown audit mode: {value!r}.")
    return mode


def _shape(value: Any) -> Any:
    if isinstance(value, dict):
        return ("dict", tuple((str(key), _shape(item)) for key, item in value.items()))
    if isinstance(value, list):
        return ("list", len(value), tuple(_shape(item) for item in value))
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    return "string"


def _json_value(text: str) -> Any | None:
    raw = str(text or "").strip()
    fence = re.fullmatch(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL | re.IGNORECASE)
    if fence:
        raw = fence.group(1).strip()
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, (dict, list)) else None


def is_json_candidate(text: str) -> bool:
    return _json_value(text) is not None


def result_changed(candidate: str, audited: str) -> bool:
    source = str(candidate or "").strip()
    result = str(audited or "").strip()
    source_json = _json_value(source)
    result_json = _json_value(result)
    if source_json is not None and result_json is not None:
        return source_json != result_json
    return source != result


_STRUCTURE_PATTERNS = (
    re.compile(r"(?m)^\s*(?:#{1,6}\s+[^\r\n]+|\[[A-Z][A-Z0-9 _/-]*\]|(?:Positive|Negative):)\s*$"),
    re.compile(r"<(?:(?:Picture|Video|Audio)\s+\d+|image\d+)>", re.IGNORECASE),
    re.compile(r"\[(?:SHOT\s+\d+|\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?)\]", re.IGNORECASE),
    re.compile(r"(?mi)^\s*(?:SHOT|SCENE|BEAT)\s+\d+(?:\s*[:—-][^\r\n]*)?\s*$"),
    re.compile(r'"(?:[^"\\]|\\.)*"'),
    re.compile(r"(?<!\w)'[^'\r\n]+'(?!\w)"),
)


def _text_signature(text: str) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(match.group(0) for match in pattern.finditer(text)) for pattern in _STRUCTURE_PATTERNS)


def validate_result(candidate: str, audited: str) -> str:
    source = str(candidate or "").strip()
    result = str(audited or "").strip()
    if not result:
        raise AuditValidationError("The audit returned an empty prompt.")
    source_json = _json_value(source)
    if source_json is not None:
        result_json = _json_value(result)
        if result_json is None:
            raise AuditValidationError("The audit changed JSON into non-JSON output.")
        if _shape(source_json) != _shape(result_json):
            raise AuditValidationError("The audit changed the JSON keys, containers, value types, or array lengths.")
        return json.dumps(result_json, ensure_ascii=False, indent=2)
    if _json_value(result) is not None:
        raise AuditValidationError("The audit changed text into JSON output.")
    if _text_signature(source) != _text_signature(result):
        raise AuditValidationError("The audit changed headings, labels, reference tokens, shot markers, or quoted text.")
    if result.startswith("```") or result.endswith("```"):
        raise AuditValidationError("The audit wrapped the prompt in a Markdown fence.")
    return result
