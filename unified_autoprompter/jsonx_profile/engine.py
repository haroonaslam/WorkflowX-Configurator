from __future__ import annotations

import base64
import hashlib
import io
import json
import re
from difflib import SequenceMatcher
from typing import Any

from PIL import Image

from .backends import JsonXProviderError
from .backends import deepseek as deepseek_backend
from .backends import gemini as gemini_backend
from .backends import grok as grok_backend
from .backends import local_llama as local_llama_backend
from .backends import local_models
from .backends import ollama as ollama_backend
from .backends import openai_compatible as openai_backend
from .backends import runtime
from . import reference_store as jsonx_references


OPTIMIZED_CANDIDATE_BUDGET = 16_000
LEGACY_PRESET_ID_ALIASES: dict[str, tuple[tuple[str, str], ...]] = {
    # IDs used before the catalog-wide uniqueness cleanup.  Keep this narrow
    # compatibility table so a cached/old model response still canonicalizes
    # by its intended path; newly generated contexts expose only current IDs.
    "detail_from_reference": (
        ("subject.dress.top.details", "dress_top_detail_from_reference"),
        ("subject.properties.skin.details", "skin_detail_from_reference"),
    ),
    "era_from_reference": (
        ("style.era", "style_era_from_reference"),
        ("mood.time_period_feel", "mood_time_period_from_reference"),
    ),
    "era_contemporary": (
        ("style.era", "style_era_contemporary"),
        ("mood.time_period_feel", "mood_time_period_contemporary"),
    ),
    "era_timeless": (
        ("style.era", "style_era_timeless"),
        ("mood.time_period_feel", "mood_time_period_timeless"),
    ),
    "tension_neutral": (
        ("mood.tension", "mood_tension_neutral"),
        ("subject.pose.body_tension", "pose_body_tension_neutral"),
    ),
    "temple_from_reference": (
        ("subject.properties.hair.temple", "hair_temple_from_reference"),
        ("subject.properties.face.temple_width", "face_temple_from_reference"),
    ),
    "intimate": (
        ("interaction_suggestions.type", "interaction_type_intimate"),
        ("interaction_suggestions.distance", "interaction_distance_intimate"),
    ),
    "passionate": (
        ("interaction_suggestions.type", "interaction_type_passionate"),
        ("interaction_suggestions.energy", "interaction_energy_passionate"),
    ),
    "romantic": (
        ("interaction_suggestions.type", "interaction_type_romantic"),
        ("interaction_suggestions.energy", "interaction_energy_romantic"),
    ),
    "sensual": (
        ("interaction_suggestions.type", "interaction_type_sensual"),
        ("interaction_suggestions.energy", "interaction_energy_sensual"),
    ),
    "erotic": (
        ("interaction_suggestions.type", "interaction_type_erotic"),
        ("interaction_suggestions.energy", "interaction_energy_erotic"),
    ),
}
FORBIDDEN_METADATA_KEYS = {
    "pipeline_stage",
    "base_name",
    "timestamp",
    "authoritative_output",
    "source_stage1_file",
    "original_intent",
    "inferred_mode",
    "framing_visibility_gate",
    "task",
    "stage",
    "debug",
    "reasoning",
}

FRAMING_AND_PLACEMENT_KEYS = (
    "top_left",
    "top_center",
    "top_right",
    "middle_left",
    "center",
    "middle_right",
    "bottom_left",
    "bottom_center",
    "bottom_right",
)

class JsonXGenerationError(ValueError):
    def __init__(self, message: str, diagnostics: dict[str, Any] | None = None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}


class JsonXGenerationCancelled(RuntimeError):
    """A browser-requested cancellation for one active JsonX generation."""


def _raise_if_cancelled(data: dict[str, Any]) -> None:
    event = data.get("_cancel_event")
    try:
        cancelled = bool(event is not None and event.is_set())
    except Exception:
        cancelled = False
    if cancelled:
        raise JsonXGenerationCancelled("JsonX generation cancelled.")


def _profile_key(data: dict[str, Any] | None = None) -> str:
    return str((data or {}).get("profile_key") or (data or {}).get("target_model") or "jsonx").strip()


def _reference_bundle(data: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = (data or {}).get("_jsonx_reference_bundle")
    if isinstance(existing, dict):
        return existing
    bundle = jsonx_references.current_bundle()
    if isinstance(data, dict):
        data["_jsonx_reference_bundle"] = bundle
    return bundle


def raw_presets_text(
    profile_key: str = "jsonx",
    bundle: dict[str, Any] | None = None,
) -> str:
    """Return the active editable preset source without reserialization."""
    return jsonx_references.preset_text(profile_key, bundle)


def load_presets(
    profile_key: str = "jsonx",
    bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return jsonx_references.presets(profile_key, bundle)


def _is_leaf_options(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and bool(value)
        and all(isinstance(item, str) for item in value.values())
    )


def flatten_preset_leaves(
    node: Any,
    prefix: str = "",
    out: dict[str, dict[str, str]] | None = None,
) -> dict[str, dict[str, str]]:
    if out is None:
        out = {}
    if not isinstance(node, dict):
        return out
    if _is_leaf_options(node):
        out[prefix] = dict(node)
        return out
    for key, value in node.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        flatten_preset_leaves(value, path, out)
    return out


def preset_schema_paths(presets: dict[str, Any] | None = None) -> list[str]:
    return list(flatten_preset_leaves(presets or load_presets()).keys())


def _tokens(value: Any) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _candidate_score(query: str, path: str, preset_id: str, value: str) -> float:
    query_text = str(query or "").lower().strip()
    if not query_text:
        return 0.0
    query_tokens = _tokens(query_text)
    haystack = f"{path} {preset_id} {value}".lower()
    haystack_tokens = _tokens(haystack)
    overlap = len(query_tokens & haystack_tokens) / max(1, len(query_tokens))
    phrase = 1.0 if query_text in haystack else 0.0
    token_phrase = max(
        (1.0 for token in query_tokens if len(token) >= 4 and token in haystack),
        default=0.0,
    )
    return overlap * 4.0 + phrase * 3.0 + token_phrase


def optimized_preset_context(
    user_instructions: str,
    presets: dict[str, Any] | None = None,
    candidate_budget: int = OPTIMIZED_CANDIDATE_BUDGET,
    *,
    profile_key: str = "jsonx",
    bundle: dict[str, Any] | None = None,
) -> str:
    catalog = presets or load_presets(profile_key, bundle)
    leaves = flatten_preset_leaves(catalog)
    schema = "\n".join(f"- {path}" for path in leaves)
    ranked: list[tuple[float, int, str, str, str]] = []
    order = 0
    for path, options in leaves.items():
        for preset_id, value in options.items():
            ranked.append(
                (_candidate_score(user_instructions, path, preset_id, value), order, path, preset_id, value)
            )
            order += 1
    ranked.sort(key=lambda item: (-item[0], item[1]))

    candidates: list[str] = []
    used = 0
    for score, _order, path, preset_id, value in ranked:
        if score <= 0:
            break
        line = f"- {path} | {preset_id} => {value}"
        if used + len(line) + 1 > max(0, int(candidate_budget)):
            break
        candidates.append(line)
        used += len(line) + 1

    candidate_text = "\n".join(candidates) or "- No lexical match; use deterministic custom values where necessary."
    return jsonx_references.render_template(
        profile_key,
        "template_adaptive_ranked",
        {
            "SCHEMA_PATHS": schema,
            "RANKED_PRESET_CANDIDATES": candidate_text,
        },
        bundle,
    )[1]


def build_preset_context(
    mode: str,
    user_instructions: str,
    *,
    profile_key: str = "jsonx",
    bundle: dict[str, Any] | None = None,
) -> tuple[str, int]:
    mode = str(mode or "optimized").strip().lower()
    raw = raw_presets_text(profile_key, bundle)
    if mode == "full":
        return jsonx_references.render_template(
            profile_key,
            "template_adaptive_full",
            {"PRESET_CATALOG": raw},
            bundle,
        )[1], len(raw)
    if mode != "optimized":
        raise ValueError(f"Unsupported JsonX preset context mode: {mode}")
    return optimized_preset_context(
        user_instructions,
        profile_key=profile_key,
        bundle=bundle,
    ), len(raw)


def template_fill_hierarchy(
    presets: dict[str, Any] | None = None,
    enable_framing_and_placement: bool = False,
    *,
    profile_key: str = "jsonx",
    bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the active editable blank hierarchy template."""
    del presets
    return jsonx_references.hierarchy_template(
        profile_key,
        enable_framing_and_placement,
        bundle,
    )[2]


def template_fill_context(
    use_presets: bool,
    enable_framing_and_placement: bool = False,
    *,
    profile_key: str = "jsonx",
    bundle: dict[str, Any] | None = None,
) -> tuple[str, int]:
    raw = raw_presets_text(profile_key, bundle)
    _path, context, _hierarchy = jsonx_references.hierarchy_template(
        profile_key,
        enable_framing_and_placement,
        bundle,
    )
    if use_presets:
        full_context = jsonx_references.render_template(
            profile_key,
            "template_adaptive_full",
            {"PRESET_CATALOG": raw},
            bundle,
        )[1]
        context += "\n\n" + full_context
    return context, len(raw)


def _normalize_output_path(path: list[str]) -> str:
    parts = [part for part in path if not str(part).isdigit()]
    if parts and parts[0] == "subjects":
        parts[0] = "subject"
    elif parts and parts[0] == "interactions":
        parts[0] = "interaction_suggestions"
    return ".".join(parts)


def _normalized(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _similarity(left: str, right: str) -> float:
    left_norm = _normalized(left)
    right_norm = _normalized(right)
    if not left_norm or not right_norm:
        return 0.0
    left_tokens = set(left_norm.split())
    right_tokens = set(right_norm.split())
    jaccard = len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))
    sequence = SequenceMatcher(None, left_norm, right_norm).ratio()
    return (jaccard + sequence) / 2.0


def align_prompt_to_presets(
    prompt: dict[str, Any],
    presets: dict[str, Any] | None = None,
    similarity_threshold: float = 0.72,
) -> dict[str, Any]:
    leaves = flatten_preset_leaves(presets or load_presets())

    def walk(value: Any, path: list[str]) -> Any:
        if isinstance(value, dict):
            return {key: walk(item, [*path, str(key)]) for key, item in value.items()}
        if isinstance(value, list):
            return [walk(item, [*path, str(index)]) for index, item in enumerate(value)]
        if not isinstance(value, str):
            return value
        options = leaves.get(_normalize_output_path(path))
        if not options:
            return value
        value_norm = _normalized(value)
        for preset_id, canonical in options.items():
            if value_norm in {_normalized(preset_id), _normalized(canonical)}:
                return canonical
        best_value = value
        best_score = 0.0
        for preset_id, canonical in options.items():
            score = max(_similarity(value, preset_id), _similarity(value, canonical))
            if score > best_score:
                best_score = score
                best_value = canonical
        return best_value if best_score >= similarity_threshold else value

    return walk(prompt, [])


def _preset_id_index(leaves: dict[str, dict[str, str]]) -> dict[str, list[tuple[str, str]]]:
    index: dict[str, list[tuple[str, str]]] = {}
    for path, options in leaves.items():
        for preset_id, value in options.items():
            index.setdefault(preset_id, []).append((path, value))
    for legacy_id, aliases in LEGACY_PRESET_ID_ALIASES.items():
        for path, current_id in aliases:
            value = leaves.get(path, {}).get(current_id)
            if value is not None:
                index.setdefault(legacy_id, []).append((path, value))
    return index


def _schema_prefixes(leaves: dict[str, dict[str, str]]) -> set[str]:
    prefixes = {""}
    for path in leaves:
        parts = path.split(".")
        for length in range(1, len(parts)):
            prefixes.add(".".join(parts[:length]))
    return prefixes


def _resolve_catalog_child(
    current_path: str,
    key: str,
    leaves: dict[str, dict[str, str]],
    prefixes: set[str],
) -> str:
    candidate = f"{current_path}.{key}" if current_path else key
    if candidate in leaves or candidate in prefixes:
        return candidate
    # Once the model is already inside a known nested catalog branch, an
    # unknown child is open-world detail for that branch. Do not globally
    # rebase generic names such as texture/color/style into a different sibling.
    if current_path in prefixes and "." in current_path:
        return candidate
    root = current_path.split(".", 1)[0] if current_path else key
    matches = [
        path
        for path in (*leaves.keys(), *prefixes)
        if path and path.split(".", 1)[0] == root and path.rsplit(".", 1)[-1] == key
    ]
    if not matches:
        return candidate
    current_parts = current_path.split(".") if current_path else []

    def score(path: str) -> tuple[int, int]:
        parts = path.split(".")[:-1]
        shared = 0
        for left, right in zip(parts, current_parts):
            if left != right:
                break
            shared += 1
        return shared, -len(parts)

    ranked = sorted(matches, key=score, reverse=True)
    if len(ranked) == 1 or score(ranked[0]) > score(ranked[1]):
        return ranked[0]
    return candidate


def _output_tokens(catalog_path: str, subject_index: int | None = None) -> list[str | int]:
    parts = catalog_path.split(".") if catalog_path else []
    if parts and parts[0] == "subject":
        if subject_index is None:
            subject_index = 0
        return ["subjects", subject_index, *parts[1:]]
    if parts and parts[0] == "interaction_suggestions":
        return ["interactions", *parts[1:]]
    return parts


def _merge_compatible_leaf_values(
    existing: Any,
    incoming: Any,
    canonical_options: dict[str, str] | None = None,
) -> Any:
    """Combine duplicate mappings to one leaf without hiding real preset conflicts.

    Smaller local models often emit both a direct value and a preset-ID key at
    the parent level.  Both resolve to the same JsonX leaf.  A scalar leaf can
    still carry multiple compatible details (notably pose.contact_points), so
    retain them in a stable order.  Two distinct catalog choices remain an
    error: they are alternatives for one leaf and need the normal repair pass.
    """
    if existing == incoming or _normalized(existing) == _normalized(incoming):
        return existing
    if not isinstance(existing, str) or not isinstance(incoming, str):
        raise ValueError("JsonX output contains conflicting values for one canonical path.")

    option_values = {
        _normalized(option)
        for option in (canonical_options or {}).values()
    }
    existing_is_catalog_value = _normalized(existing) in option_values
    incoming_is_catalog_value = _normalized(incoming) in option_values
    if existing_is_catalog_value and incoming_is_catalog_value:
        raise ValueError("JsonX output contains conflicting catalog values for one canonical path.")

    # A no-contact declaration cannot coexist with a positive contact detail.
    # Keep this narrow; broader natural-language antonym guessing would reject
    # valid compound pose, lighting, and composition descriptions.
    no_contact = re.compile(r"\b(?:no|without)\s+(?:physical\s+)?contact\b", re.IGNORECASE)
    if no_contact.search(existing) or no_contact.search(incoming):
        raise ValueError("JsonX output contains conflicting contact values for one canonical path.")

    return f"{existing}; {incoming}"


def _set_prompt_path(
    target: dict[str, Any],
    tokens: list[str | int],
    value: Any,
    *,
    canonical_options: dict[str, str] | None = None,
) -> None:
    if not tokens:
        raise ValueError("JsonX canonicalization produced an empty output path.")
    current: Any = target
    for index, token in enumerate(tokens):
        last = index == len(tokens) - 1
        next_token = tokens[index + 1] if not last else None
        if isinstance(token, int):
            if not isinstance(current, list):
                raise ValueError("JsonX canonicalization encountered an invalid array path.")
            while len(current) <= token:
                current.append({} if not isinstance(next_token, int) else [])
            if last:
                existing = current[token]
                current[token] = (
                    value
                    if existing in ({}, None)
                    else _merge_compatible_leaf_values(existing, value, canonical_options)
                )
            else:
                current = current[token]
            continue
        if not isinstance(current, dict):
            raise ValueError("JsonX canonicalization encountered an invalid object path.")
        if last:
            existing = current.get(token)
            try:
                current[token] = (
                    value
                    if token not in current or existing is None
                    else _merge_compatible_leaf_values(existing, value, canonical_options)
                )
            except ValueError as error:
                raise ValueError(
                    f"JsonX output contains conflicting values at '{'.'.join(map(str, tokens))}'."
                ) from error
            continue
        expected: Any = [] if isinstance(next_token, int) else {}
        if token not in current:
            current[token] = expected
        elif not isinstance(current[token], type(expected)):
            raise ValueError(f"JsonX output conflicts at '{'.'.join(map(str, tokens[: index + 1]))}'.")
        current = current[token]


def canonicalize_prompt_structure(
    prompt: dict[str, Any],
    presets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    catalog = presets or load_presets()
    leaves = flatten_preset_leaves(catalog)
    prefixes = _schema_prefixes(leaves)
    id_index = _preset_id_index(leaves)
    output: dict[str, Any] = {}

    def choose_id_path(
        preset_id: str,
        current_path: str,
        raw_value: Any,
    ) -> tuple[str, str] | None:
        choices = id_index.get(preset_id) or []
        if not choices:
            return None
        exact = [choice for choice in choices if choice[0] == current_path]
        if len(exact) == 1:
            return exact[0]
        normalized_value = _normalized(raw_value)
        matching_value = [choice for choice in choices if _normalized(choice[1]) == normalized_value]
        if len(matching_value) == 1:
            return matching_value[0]
        root = current_path.split(".", 1)[0] if current_path else ""
        same_root = [choice for choice in choices if choice[0].split(".", 1)[0] == root]
        if len(same_root) == 1:
            return same_root[0]
        # Some catalog IDs are intentionally reused in distinct branches (for
        # example, hair temple vs face temple width).  A model may emit such an
        # ID at the parent level.  Resolve it only when the current hierarchy
        # gives one candidate a strictly closer shared prefix; ties remain
        # ambiguous and are left for the provider repair pass.
        current_parts = current_path.split(".") if current_path else []

        def context_score(choice: tuple[str, str]) -> tuple[int, int]:
            parts = choice[0].split(".")[:-1]
            shared = 0
            for left, right in zip(parts, current_parts):
                if left != right:
                    break
                shared += 1
            return shared, -abs(len(parts) - len(current_parts))

        contextual = sorted(choices, key=context_score, reverse=True)
        if len(contextual) == 1 or context_score(contextual[0]) > context_score(contextual[1]):
            return contextual[0]
        return choices[0] if len(choices) == 1 else None

    def explicitly_references_path(value: Any, target_path: str) -> bool:
        """Require preset evidence before moving content out of a catalog leaf."""
        options = leaves.get(target_path)
        if not options:
            return False
        option_ids = set(options)
        option_values = {_normalized(item) for item in options.values()}

        def references(item: Any) -> bool:
            if isinstance(item, dict):
                return any(
                    str(key) in option_ids
                    or references(nested)
                    for key, nested in item.items()
                )
            if isinstance(item, list):
                return any(references(nested) for nested in item)
            if isinstance(item, str):
                return item in option_ids or _normalized(item) in option_values
            return False

        return references(value)

    def walk(
        value: Any,
        catalog_path: str,
        out_tokens: list[str | int],
        subject_index: int | None = None,
    ) -> None:
        if catalog_path in leaves:
            if isinstance(value, dict):
                unresolved: list[tuple[str, Any]] = []
                leaf_was_set = False
                for nested_key, nested_value in value.items():
                    nested_key_text = str(nested_key)
                    if not isinstance(nested_value, (dict, list)):
                        if nested_key_text in leaves[catalog_path]:
                            _set_prompt_path(
                                output,
                                out_tokens,
                                leaves[catalog_path][nested_key_text],
                                canonical_options=leaves[catalog_path],
                            )
                            leaf_was_set = True
                            continue
                        resolved_id = choose_id_path(nested_key_text, catalog_path, nested_value)
                        if resolved_id and resolved_id[0] == catalog_path:
                            _set_prompt_path(
                                output,
                                out_tokens,
                                resolved_id[1],
                                canonical_options=leaves[catalog_path],
                            )
                            leaf_was_set = True
                            continue
                    sibling_path = _resolve_catalog_child(
                        catalog_path,
                        nested_key_text,
                        leaves,
                        prefixes,
                    )
                    if sibling_path != f"{catalog_path}.{nested_key_text}" and (
                        sibling_path in leaves or sibling_path in prefixes
                    ) and explicitly_references_path(nested_value, sibling_path):
                        walk(
                            nested_value,
                            sibling_path,
                            _output_tokens(sibling_path, subject_index),
                            subject_index,
                        )
                        continue
                    unresolved.append((nested_key_text, nested_value))
                if unresolved:
                    if (
                        not leaf_was_set
                        and len(unresolved) == 1
                        and not isinstance(unresolved[0][1], (dict, list))
                    ):
                        _set_prompt_path(
                            output,
                            out_tokens,
                            unresolved[0][1],
                            canonical_options=leaves[catalog_path],
                        )
                    else:
                        # The catalog leaf remains scalar, but open-world JsonX content may
                        # legitimately expand it. Preserve that hierarchy beside the leaf
                        # rather than flattening it or rejecting otherwise useful detail.
                        leaf_name = str(out_tokens[-1])
                        detail_tokens = [*out_tokens[:-1], f"{leaf_name}_details"]
                        _set_prompt_path(output, detail_tokens, dict(unresolved))
                return
            if isinstance(value, list):
                if all(not isinstance(item, (dict, list)) for item in value):
                    _set_prompt_path(
                        output,
                        out_tokens,
                        ", ".join(str(item) for item in value),
                        canonical_options=leaves[catalog_path],
                    )
                    return
                leaf_name = str(out_tokens[-1])
                detail_tokens = [*out_tokens[:-1], f"{leaf_name}_details"]
                _set_prompt_path(output, detail_tokens, {"items": value})
                return
            _set_prompt_path(
                output,
                out_tokens,
                value,
                canonical_options=leaves[catalog_path],
            )
            return

        if isinstance(value, list):
            _set_prompt_path(output, out_tokens, value)
            return
        if not isinstance(value, dict):
            _set_prompt_path(output, out_tokens, value)
            return

        for key, item in value.items():
            key_text = str(key)
            if not isinstance(item, (dict, list)):
                resolved_id = choose_id_path(key_text, catalog_path, item)
                if resolved_id:
                    resolved_path, canonical_value = resolved_id
                    _set_prompt_path(
                        output,
                        _output_tokens(resolved_path, subject_index),
                        canonical_value,
                        canonical_options=leaves[resolved_path],
                    )
                    continue
            child_path = _resolve_catalog_child(catalog_path, key_text, leaves, prefixes)
            if child_path in leaves or child_path in prefixes:
                child_tokens = _output_tokens(child_path, subject_index)
            else:
                child_tokens = [*out_tokens, key_text]
            walk(item, child_path, child_tokens, subject_index)

    for key, value in prompt.items():
        if key in {"subject", "subjects"}:
            items = value if isinstance(value, list) else [value]
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    raise ValueError(f"JsonX subjects[{index}] must be an object.")
                walk(item, "subject", ["subjects", index], index)
            continue
        if key in {"interactions", "interaction_suggestions"}:
            if not isinstance(value, dict):
                raise ValueError("JsonX interactions must be an object.")
            walk(value, "interaction_suggestions", ["interactions"])
            continue
        walk(value, key, [key])

    return validate_prompt_object(output)


def validate_canonical_prompt(
    prompt: dict[str, Any],
    leaves: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    validate_prompt_object(prompt)
    if "subject" in prompt:
        raise ValueError("JsonX output must use the repeatable 'subjects' array, not singular 'subject'.")
    leaf_map = leaves or flatten_preset_leaves(load_presets())
    preset_ids = set(_preset_id_index(leaf_map))
    prefixes = _schema_prefixes(leaf_map)

    def walk(value: Any, catalog_path: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                key_text = str(key)
                if not catalog_path and key_text == "subjects":
                    child_path = "subject"
                elif not catalog_path and key_text == "interactions":
                    child_path = "interaction_suggestions"
                else:
                    child_path = f"{catalog_path}.{key_text}" if catalog_path else key_text
                if key_text in preset_ids and child_path not in leaf_map and child_path not in prefixes:
                    raise ValueError(f"JsonX output still contains internal preset ID '{key}' as a key.")
                walk(item, child_path)
        elif isinstance(value, list):
            for item in value:
                walk(item, catalog_path)
        elif isinstance(value, str):
            path_options = leaf_map.get(catalog_path, {})
            if value in path_options:
                raise ValueError(
                    f"JsonX output still contains internal preset ID '{value}' "
                    f"as a value at '{catalog_path}'."
                )

    walk(prompt, "")
    return prompt


def _strip_fence(text: str) -> str:
    stripped = str(text or "").strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else stripped


def _strip_reasoning_blocks(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"<think(?:\s[^>]*)?>.*?</think\s*>", "", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(
        r"\[Start thinking\].*?\[End thinking\]",
        "",
        value,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return value.strip()


def _balanced_json_objects(text: str) -> list[str]:
    candidates: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False
    for index, character in enumerate(str(text or "")):
        if start is None:
            if character == "{":
                start = index
                depth = 1
                in_string = False
                escaped = False
            continue
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                candidates.append(str(text)[start : index + 1])
                start = None
    return candidates


def _extract_single_json_text(raw: str) -> str:
    text = _strip_reasoning_blocks(raw)
    exact = _strip_fence(text)
    if exact != text:
        return exact

    fences = re.findall(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fences:
        if len(fences) != 1:
            raise ValueError("LLM response contains multiple fenced JSON candidates.")
        return fences[0].strip()

    try:
        json.loads(text)
        return text
    except Exception:
        pass

    valid_objects: list[str] = []
    for candidate in _balanced_json_objects(text):
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed, dict):
            valid_objects.append(candidate)
    if len(valid_objects) == 1:
        return valid_objects[0]
    if len(valid_objects) > 1:
        raise ValueError("LLM response contains multiple JSON objects; the final prompt is ambiguous.")
    return text


def _find_forbidden_key(value: Any, path: str = "") -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            next_path = f"{path}.{key_text}" if path else key_text
            if key_text.lower() in FORBIDDEN_METADATA_KEYS:
                return next_path
            found = _find_forbidden_key(item, next_path)
            if found:
                return found
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found = _find_forbidden_key(item, f"{path}[{index}]")
            if found:
                return found
    return None


def validate_prompt_object(prompt: Any) -> dict[str, Any]:
    if not isinstance(prompt, dict):
        raise ValueError("JsonX output must be a prompt JSON object.")
    forbidden = _find_forbidden_key(prompt)
    if forbidden:
        raise ValueError(f"JsonX output contains forbidden process metadata at '{forbidden}'.")
    if "subjects" in prompt and not isinstance(prompt["subjects"], list):
        raise ValueError("JsonX 'subjects' must be an array when present.")
    if "subjects" in prompt:
        for index, subject in enumerate(prompt["subjects"]):
            if not isinstance(subject, dict):
                raise ValueError(f"JsonX 'subjects[{index}]' must be an object.")
    if "interactions" in prompt and not isinstance(prompt["interactions"], dict):
        raise ValueError("JsonX 'interactions' must be an object when present.")
    return prompt


def parse_prompt_json(raw: str) -> dict[str, Any]:
    text = _extract_single_json_text(raw)
    try:
        parsed = json.loads(text)
    except Exception as exc:
        raise ValueError("LLM response must be plain JSON or one fenced JSON object.") from exc

    if isinstance(parsed, dict):
        wrapper_keys = {key for key in parsed if key in {"prompt", "prompt_json"}}
        if wrapper_keys and len(parsed) != 1:
            raise ValueError("JsonX output contains a conflicting prompt wrapper and root structure.")
        if len(parsed) == 1 and wrapper_keys:
            key = next(iter(wrapper_keys))
            wrapped = parsed[key]
            if isinstance(wrapped, str):
                try:
                    wrapped = json.loads(_strip_fence(wrapped))
                except Exception as exc:
                    raise ValueError("JsonX prompt wrapper does not contain valid JSON.") from exc
            parsed = wrapped
    return validate_prompt_object(parsed)


def _decode_image(image_b64: Any) -> Image.Image | None:
    if not image_b64:
        return None
    data = str(image_b64)
    if "," in data:
        data = data.split(",", 1)[1]
    try:
        image = Image.open(io.BytesIO(base64.b64decode(data)))
        image.load()
        return image.convert("RGB")
    except Exception:
        return None


def _decode_images(data: dict[str, Any]) -> list[Image.Image]:
    candidates = data.get("images_b64")
    if not isinstance(candidates, list) or not candidates:
        candidates = [data.get("image_b64")]
    return [image for image in (_decode_image(value) for value in candidates) if image is not None]


def _optional_number(value: Any, *, integer: bool = False) -> float | int | None:
    if value is None or value == "" or str(value).strip().lower() in {"default", "provider_default"}:
        return None
    return int(value) if integer else float(value)


def _grok_cache_key(data: dict[str, Any], system_prompt: str) -> str:
    if str(data.get("grok_prompt_cache") or "auto").strip().lower() == "off":
        return ""
    stable = {
        "engine": "unified_jsonx",
        "profile": str(data.get("profile_key") or data.get("target_model") or "jsonx"),
        "generation_type": str(data.get("generation_type") or ""),
        "format": str(data.get("output_format") or "json"),
        "stage": str(data.get("_provider_stage") or "stage_1"),
        "system_sha256": hashlib.sha256(system_prompt.encode("utf-8")).hexdigest(),
    }
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode("utf-8")).hexdigest()


def _joined(blocks: list[str]) -> str:
    return "\n\n".join(blocks)


def _selected_block(
    data: dict[str, Any],
    semantic_key: str,
    activated: list[str],
) -> str:
    path, text = jsonx_references.block(
        _profile_key(data), semantic_key, _reference_bundle(data)
    )
    activated.append(path)
    return text


def _reference_semantic_key(data: dict[str, Any], has_image: bool) -> str:
    generation_type = str(data.get("generation_type") or "text_to_image").strip().lower()
    if generation_type == "image_to_image":
        return "reference_with_supported" if has_image else "reference_without_supported"
    return "reference_without_unsupported"


def _generation_semantic_key(data: dict[str, Any]) -> str:
    generation_type = str(data.get("generation_type") or "text_to_image").strip().lower()
    if generation_type not in {"text_to_image", "image_to_image"}:
        raise ValueError(f"Unsupported JsonX generation type: {generation_type}")
    return f"generation_{generation_type}"


def _stage_one_payload(
    data: dict[str, Any],
    user_instructions: str,
    has_image: bool,
) -> tuple[str, list[str], int, str]:
    generation_profile = str(data.get("generation_profile") or "adaptive").strip().lower()
    detail_level = str(data.get("detail_level") or "deep").strip().lower()
    framing = bool(data.get("enable_framing_and_placement", False))
    use_presets = bool(data.get("template_use_presets", False))
    context_mode = str(data.get("preset_context_mode") or "optimized").strip().lower()
    if generation_profile not in {"adaptive", "template_fill"}:
        raise ValueError(f"Unsupported JsonX generation profile: {generation_profile}")
    if detail_level not in {"deep", "exhaustive"}:
        raise ValueError(f"Unsupported JsonX detail level: {detail_level}")
    activated: list[str] = []
    blocks = [
        _selected_block(
            data,
            "stage_one_template_fill" if generation_profile == "template_fill" else "stage_one_adaptive",
            activated,
        ),
        _selected_block(data, _generation_semantic_key(data), activated),
        _selected_block(data, _reference_semantic_key(data, has_image), activated),
    ]
    if bool(data.get("nsfw_enabled", False)):
        path, text = jsonx_references.shared_nsfw_image()
        activated.append(path)
        blocks.append(text)
    if generation_profile == "template_fill":
        blocks.extend([
            _selected_block(data, "template_image_with" if has_image else "template_image_without", activated),
            _selected_block(data, "template_presets_enabled" if use_presets else "template_presets_disabled", activated),
            _selected_block(data, "framing_json_enabled" if framing else "framing_json_disabled", activated),
        ])
        context, full_chars = template_fill_context(
            use_presets,
            framing,
            profile_key=_profile_key(data),
            bundle=_reference_bundle(data),
        )
        hierarchy_key = "template_fill_with_framing" if framing else "template_fill_without_framing"
        hierarchy_path = jsonx_references.block(
            _profile_key(data), hierarchy_key, _reference_bundle(data)
        )[0]
        activated.append(hierarchy_path)
        if use_presets:
            activated.append(jsonx_references.block(
                _profile_key(data), "template_adaptive_full", _reference_bundle(data)
            )[0])
            activated.append(jsonx_references.block(
                _profile_key(data), "presets_full", _reference_bundle(data)
            )[0])
        blocks.append(context)
        effective_mode = "full" if use_presets else "none"
    else:
        blocks.extend([
            _selected_block(data, "adaptive_image_with" if has_image else "adaptive_image_without", activated),
            _selected_block(data, "adaptive_open_world", activated),
            _selected_block(data, f"depth_{detail_level}", activated),
            _selected_block(data, "framing_json_enabled" if framing else "framing_json_disabled", activated),
        ])
        context, full_chars = build_preset_context(
            context_mode,
            user_instructions,
            profile_key=_profile_key(data),
            bundle=_reference_bundle(data),
        )
        template_key = "template_adaptive_full" if context_mode == "full" else "template_adaptive_ranked"
        activated.append(jsonx_references.block(
            _profile_key(data), template_key, _reference_bundle(data)
        )[0])
        activated.append(jsonx_references.block(
            _profile_key(data), "presets_full", _reference_bundle(data)
        )[0])
        blocks.append(context)
        effective_mode = context_mode
    blocks.append(_selected_block(data, "contract_stage_one_json", activated))
    return _joined(blocks), activated, full_chars, effective_mode


def _stage_two_payload(
    data: dict[str, Any],
    has_image: bool,
    output_format: str,
) -> tuple[str, list[str]]:
    framing = bool(data.get("enable_framing_and_placement", False))
    detail_level = str(data.get("detail_level") or "deep").strip().lower()
    generation_profile = str(data.get("generation_profile") or "adaptive").strip().lower()
    activated: list[str] = []
    if output_format == "natural":
        blocks = [
            _selected_block(data, "stage_two_natural_conversion", activated),
            _selected_block(data, "natural_image_with" if has_image else "natural_image_without", activated),
            _selected_block(data, "framing_natural_enabled" if framing else "framing_natural_disabled", activated),
            _selected_block(data, "contract_stage_two_natural", activated),
        ]
    else:
        blocks = [
            _selected_block(data, "stage_two_json_refinement", activated),
            _selected_block(data, "refinement_image_with" if has_image else "refinement_image_without", activated),
            _selected_block(data, "refinement_open_world", activated),
            _selected_block(data, f"depth_{detail_level}", activated),
            _selected_block(data, "framing_json_enabled" if framing else "framing_json_disabled", activated),
        ]
        if generation_profile == "template_fill":
            blocks.append(_selected_block(data, "template_refinement", activated))
        blocks.append(_selected_block(data, "contract_stage_two_json", activated))
    return _joined(blocks), activated


def _repair_payload(data: dict[str, Any], natural: bool) -> tuple[str, list[str]]:
    activated: list[str] = []
    blocks = [
        _selected_block(data, "repair_natural" if natural else "repair_json", activated),
        _selected_block(data, "contract_natural_repair" if natural else "contract_json_repair", activated),
    ]
    return _joined(blocks), activated


def _render_user_template(
    data: dict[str, Any],
    semantic_key: str,
    **values: str,
) -> str:
    return jsonx_references.render_user_template(
        _profile_key(data),
        semantic_key,
        bundle=_reference_bundle(data),
        **values,
    )[1]


def instruction_templates(profile_key: str = "jsonx") -> dict[str, Any]:
    bundle = jsonx_references.current_bundle()
    profile = jsonx_references.profile_metadata(profile_key)
    editors = {
        key: jsonx_references.block(profile_key, key, bundle)[1]
        for key in jsonx_references.REQUIRED_FILE_KEYS
    }
    return {
        "jsonx_reference_schema_version": jsonx_references.JSONX_REFERENCE_SCHEMA_VERSION,
        "profile": profile,
        "editors": editors,
    }


def stage_one_system_prompt(
    preset_context: str,
    has_image: bool,
    instructions: str | None = None,
    detail_level: str = "deep",
    enable_framing_and_placement: bool = False,
    config: dict[str, Any] | None = None,
) -> str:
    """Compatibility wrapper backed only by active JsonX Markdown."""
    del instructions
    data = dict(config or {})
    data.update({
        "generation_profile": "adaptive",
        "detail_level": detail_level,
        "enable_framing_and_placement": enable_framing_and_placement,
    })
    system, _activated, _chars, _mode = _stage_one_payload(data, "", has_image)
    return system.replace(
        build_preset_context(
            str(data.get("preset_context_mode") or "optimized"),
            "",
            profile_key=_profile_key(data),
            bundle=_reference_bundle(data),
        )[0],
        preset_context,
    )


def effective_instruction_preview(data: dict[str, Any]) -> dict[str, Any]:
    user_instructions = str(data.get("user_instructions") or "").strip()
    output_format = str(data.get("output_format") or "json").strip().lower()
    if output_format not in {"json", "natural"}:
        raise ValueError(f"Unsupported JsonX output format: {output_format}")
    has_image = bool(data.get("has_image", False) or data.get("images_b64") or data.get("image_b64"))
    preview_user = user_instructions or "Describe the provided image as a complete JsonX prompt."
    stage_one, stage_one_files, full_chars, effective_mode = _stage_one_payload(
        data, preview_user, has_image
    )
    stage_two_applicable = output_format == "natural" or str(data.get("generation_mode") or "fast").strip().lower() == "refined"
    stage_two, stage_two_files = (
        _stage_two_payload(data, has_image, output_format)
        if stage_two_applicable
        else ("", [])
    )
    json_repair, json_repair_files = _repair_payload(data, False)
    natural_repair, natural_repair_files = _repair_payload(data, True)
    stage_one_user = _render_user_template(
        data, "user_stage_one", user_instructions=preview_user
    )
    stage_two_user = (
        _render_user_template(
            data,
            "user_natural_conversion" if output_format == "natural" else "user_json_refinement",
            user_instructions=preview_user,
            stage_one_json="{validated Stage 1 JsonX}",
        )
        if stage_two_applicable
        else ""
    )
    json_repair_user = _render_user_template(
        data,
        "user_json_repair",
        validation_error="{validation error}",
        user_instructions=preview_user,
        raw_response="{provider response}",
    )
    natural_repair_user = _render_user_template(
        data,
        "user_natural_repair",
        validation_error="{validation error}",
        user_instructions=preview_user,
        stage_one_json="{validated Stage 1 JsonX}",
        raw_response="{provider response}",
    )
    generation_profile = str(data.get("generation_profile") or "adaptive").strip().lower()
    return {
        "stage_one": stage_one,
        "refinement": stage_two,
        "user": stage_one_user,
        "stage_two_user": stage_two_user,
        "json_repair": json_repair,
        "json_repair_user": json_repair_user,
        "natural_repair": natural_repair,
        "natural_repair_user": natural_repair_user,
        "stage_one_characters": len(stage_one),
        "refinement_characters": len(stage_two),
        "full_preset_chars": full_chars,
        "detail_level": str(data.get("detail_level") or "deep"),
        "generation_profile": generation_profile,
        "generation_mode": "refined" if output_format == "natural" else str(data.get("generation_mode") or "fast"),
        "output_format": output_format,
        "forced_two_pass": output_format == "natural",
        "stage_two_applicable": stage_two_applicable,
        "template_use_presets": bool(data.get("template_use_presets", False)),
        "enable_framing_and_placement": bool(data.get("enable_framing_and_placement", False)),
        "preset_context_mode": effective_mode,
        "activated_files": {
            "stage_one": stage_one_files,
            "stage_two": stage_two_files,
            "json_repair": json_repair_files,
            "natural_repair": natural_repair_files,
        },
    }


def hierarchy_metrics(prompt: dict[str, Any]) -> dict[str, int]:
    leaf_count = 0
    branch_count = 0
    max_depth = 0

    def walk(value: Any, depth: int) -> None:
        nonlocal leaf_count, branch_count, max_depth
        if isinstance(value, dict):
            branch_count += 1
            max_depth = max(max_depth, depth)
            for item in value.values():
                walk(item, depth + 1)
        elif isinstance(value, list):
            branch_count += 1
            max_depth = max(max_depth, depth)
            for item in value:
                walk(item, depth)
        else:
            leaf_count += 1
            max_depth = max(max_depth, depth)

    walk(prompt, 0)
    return {
        "leaf_count": leaf_count,
        "branch_count": branch_count,
        "max_depth": max_depth,
        "root_groups": len(prompt),
    }


def _call_provider(data: dict[str, Any], system_prompt: str, user_prompt: str, image: Image.Image | None) -> str:
    _raise_if_cancelled(data)
    backend = str(data.get("backend") or "gemini").strip().lower()
    images = [value for value in data.get("_pil_images", []) if isinstance(value, Image.Image)]
    if not images and image is not None:
        images = [image]
    timeout = max(5.0, min(3600.0, float(data.get("timeout") or 120)))
    try:
        if backend == "gemini":
            result = gemini_backend.generate(
                str(data.get("api_key") or "").strip(),
                str(data.get("model") or ""),
                system_prompt,
                user_prompt,
                pil_images=images,
                safety_settings=data.get("gemini_safety") if isinstance(data.get("gemini_safety"), dict) else None,
                timeout=timeout,
                response_mime_type=str(data.get("_gemini_response_mime_type") or "application/json"),
            )
        elif backend in {"openai", "lm_studio", "unsloth"}:
            capabilities = data.get("model_capabilities") if isinstance(data.get("model_capabilities"), dict) else {}
            if images and backend in {"lm_studio", "unsloth"} and capabilities.get("vision") is False:
                raise ValueError(f"The selected {backend.replace('_', ' ').title()} model does not accept image input.")
            result = openai_backend.generate(
                str(data.get("base_url") or ""),
                str(data.get("api_key") or "").strip(),
                str(data.get("model") or ""),
                system_prompt,
                user_prompt,
                pil_images=images,
                timeout=timeout,
                unload_after=(
                    bool(data.get("unload_after"))
                    if "openai_lifecycle" not in data and "unload_after" in data
                    else None
                ),
                server_type={"openai": "generic", "lm_studio": "lm_studio", "unsloth": "unsloth"}[backend],
                lifecycle=str(data.get("openai_lifecycle") or "server_managed"),
                reasoning_effort=str(data.get("openai_reasoning_effort") or "default"),
                provider_options=data.get("provider_options") if isinstance(data.get("provider_options"), dict) else None,
            )
        elif backend == "grok":
            capabilities = data.get("model_capabilities") if isinstance(data.get("model_capabilities"), dict) else {}
            if images and capabilities.get("vision") is False:
                raise ValueError("The selected Grok model does not accept image input.")
            result = grok_backend.generate(
                str(data.get("api_key") or "").strip(),
                str(data.get("model") or ""),
                system_prompt,
                user_prompt,
                pil_images=images,
                timeout=timeout,
                response_format=str(data.get("_grok_response_format") or "json"),
                max_output_tokens=_optional_number(data.get("grok_max_output_tokens"), integer=True),
                temperature=_optional_number(data.get("grok_temperature")),
                top_p=_optional_number(data.get("grok_top_p")),
                reasoning_effort=str(data.get("grok_reasoning_effort") or "default"),
                prompt_cache_key=_grok_cache_key(data, system_prompt),
            )
        elif backend == "deepseek":
            if images and not deepseek_backend.is_vision_model(str(data.get("model") or "")):
                raise ValueError(f"The selected DeepSeek model '{data.get('model') or ''}' does not accept image input.")
            result = deepseek_backend.generate(
                str(data.get("api_key") or "").strip(),
                str(data.get("model") or ""),
                system_prompt,
                user_prompt,
                pil_images=images,
                timeout=timeout,
                response_format=str(data.get("_deepseek_response_format") or "json"),
                max_tokens=_optional_number(data.get("deepseek_max_tokens"), integer=True),
                thinking=str(data.get("deepseek_thinking") or "default"),
                reasoning_effort=str(data.get("deepseek_reasoning_effort") or "default"),
                temperature=_optional_number(data.get("deepseek_temperature")),
                top_p=_optional_number(data.get("deepseek_top_p")),
                image_detail=str(data.get("deepseek_image_detail") or "default"),
            )
        elif backend == "ollama":
            result = ollama_backend.generate(
                str(data.get("host") or ""),
                str(data.get("model") or ""),
                system_prompt,
                user_prompt,
                pil_images=images,
                think=bool(data.get("think", False)),
                unload_after=bool(data.get("unload_after", True)),
                timeout=timeout,
                options=data.get("ollama_options") if isinstance(data.get("ollama_options"), dict) else None,
            )
        elif backend == "local":
            options = data.get("local_options") if isinstance(data.get("local_options"), dict) else {}
            options = dict(options)
            options.setdefault("timeout", timeout)
            if images and str(data.get("mmproj") or "none").strip().lower() in {"", "none"}:
                raise ValueError(
                    "Connected authoring images require a vision mmproj for the selected local GGUF model. "
                    "Select a compatible mmproj or disconnect the images."
                )
            result = local_llama_backend.generate(
                model=str(data.get("model") or ""),
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                pil_images=images,
                mmproj=str(data.get("mmproj") or "none"),
                system_prompt_preset=str(data.get("system_prompt_preset") or "none"),
                additional_model_paths=data.get("additional_model_paths"),
                options=options,
                cancel_event=data.get("_cancel_event"),
            )
        else:
            raise ValueError(f"Unsupported JsonX backend: {backend}")
    except Exception:
        _raise_if_cancelled(data)
        raise
    _raise_if_cancelled(data)
    diagnostics = getattr(result, "diagnostics", None)
    if isinstance(diagnostics, dict) and diagnostics:
        diagnostics = dict(diagnostics)
        if backend == "grok":
            capabilities = data.get("model_capabilities") if isinstance(data.get("model_capabilities"), dict) else {}
            if capabilities.get("context_length") is not None:
                diagnostics["context_length"] = int(capabilities.get("context_length") or 0)
        data["_provider_diagnostics"] = diagnostics
    return result


_DROP_NULL = object()


def prune_null_leaves(prompt: dict[str, Any]) -> dict[str, Any]:
    """Remove null leaves and containers made empty by their removal."""

    def prune(value: Any) -> Any:
        if value is None:
            return _DROP_NULL
        if isinstance(value, dict):
            cleaned = {}
            for key, item in value.items():
                result = prune(item)
                if result is not _DROP_NULL:
                    cleaned[key] = result
            return cleaned if cleaned else _DROP_NULL
        if isinstance(value, list):
            cleaned = []
            for item in value:
                result = prune(item)
                if result is not _DROP_NULL:
                    cleaned.append(result)
            return cleaned if cleaned else _DROP_NULL
        return value

    result = prune(prompt)
    return result if isinstance(result, dict) else {}


def constrain_template_fill_structure(
    prompt: dict[str, Any],
    hierarchy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Keep Template Fill content only at paths present in the live blank hierarchy."""
    template = hierarchy if hierarchy is not None else template_fill_hierarchy()

    def constrain(value: Any, shape: Any) -> Any:
        if shape is None:
            return value if not isinstance(value, (dict, list)) else _DROP_NULL
        if isinstance(shape, dict):
            if not isinstance(value, dict):
                return _DROP_NULL
            cleaned = {}
            for key, child_shape in shape.items():
                if key not in value:
                    continue
                child = constrain(value[key], child_shape)
                if child is not _DROP_NULL:
                    cleaned[key] = child
            return cleaned if cleaned else _DROP_NULL
        if isinstance(shape, list):
            if not isinstance(value, list) or not shape:
                return _DROP_NULL
            cleaned = []
            for item in value:
                child = constrain(item, shape[0])
                if child is not _DROP_NULL:
                    cleaned.append(child)
            return cleaned if cleaned else _DROP_NULL
        return _DROP_NULL

    result = constrain(prompt, template)
    return validate_canonical_prompt(result if isinstance(result, dict) else {})


def overlay_template_refinement(
    stage_one: dict[str, Any],
    refined: dict[str, Any],
) -> dict[str, Any]:
    """Apply Stage 2 values only at paths established by Template Fill Stage 1."""

    def overlay(original: Any, update: Any) -> Any:
        if update is None:
            return None
        if isinstance(original, dict):
            if not isinstance(update, dict):
                return original
            return {
                key: overlay(value, update[key]) if key in update else value
                for key, value in original.items()
            }
        if isinstance(original, list):
            if not isinstance(update, list):
                return original
            return [
                overlay(item, update[index]) if index < len(update) else item
                for index, item in enumerate(original)
            ]
        return update if not isinstance(update, (dict, list)) else original

    overlaid = overlay(stage_one, refined)
    return validate_canonical_prompt(prune_null_leaves(overlaid))


def enforce_framing_and_placement(
    prompt: dict[str, Any],
    enabled: bool,
) -> dict[str, Any]:
    """Apply the per-node framing gate and validate the enabled nine-cell map."""
    cleaned = dict(prompt)
    if not enabled:
        cleaned.pop("framing_and_placement", None)
        return cleaned

    framing = cleaned.get("framing_and_placement")
    if not isinstance(framing, dict):
        raise ValueError(
            "JsonX output requires a 'framing_and_placement' object when the 3x3 map is enabled."
        )
    expected = set(FRAMING_AND_PLACEMENT_KEYS)
    actual = set(framing)
    missing = [key for key in FRAMING_AND_PLACEMENT_KEYS if key not in actual]
    extras = [str(key) for key in framing if key not in expected]
    if missing or extras:
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if extras:
            details.append(f"unexpected: {', '.join(extras)}")
        raise ValueError(
            "JsonX 'framing_and_placement' must contain exactly the nine 3x3 grid regions "
            f"({'; '.join(details)})."
        )

    normalized: dict[str, str] = {}
    for key in FRAMING_AND_PLACEMENT_KEYS:
        value = framing[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"JsonX framing region 'framing_and_placement.{key}' must be a non-empty string."
            )
        normalized[key] = value.strip()
    cleaned["framing_and_placement"] = normalized
    return cleaned


def _parse_and_normalize(
    raw: str,
    *,
    prune_null: bool = False,
    enable_framing_and_placement: bool = False,
    presets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parsed = parse_prompt_json(raw)
    canonical = canonicalize_prompt_structure(parsed)
    normalized = validate_canonical_prompt(align_prompt_to_presets(canonical, presets))
    if prune_null:
        normalized = prune_null_leaves(normalized)
    normalized = enforce_framing_and_placement(
        normalized,
        enable_framing_and_placement,
    )
    return validate_canonical_prompt(normalized)


def _parse_or_repair(
    data: dict[str, Any],
    raw: str,
    stage: str = "generation",
    image: Image.Image | None = None,
    prune_null: bool = False,
) -> dict[str, Any]:
    enable_framing_and_placement = bool(
        data.get("enable_framing_and_placement", False)
    )
    presets = data.get("_jsonx_presets")
    if not isinstance(presets, dict):
        presets = load_presets(_profile_key(data), _reference_bundle(data))
        data["_jsonx_presets"] = presets
    try:
        return _parse_and_normalize(
            raw,
            prune_null=prune_null,
            enable_framing_and_placement=enable_framing_and_placement,
            presets=presets,
        )
    except Exception as first_error:
        repair_system, _repair_files = _repair_payload(data, False)
        original_instructions = str(data.get("user_instructions") or "").strip()
        repair_user = _render_user_template(
            data,
            "user_json_repair",
            validation_error=str(first_error),
            user_instructions=original_instructions or "(image-led request)",
            raw_response=raw,
        )
        repair_data = dict(data)
        if str(data.get("backend") or "").strip().lower() == "local":
            local_options = dict(data.get("local_options") or {})
            try:
                current_max_tokens = int(local_options.get("max_tokens") or 0)
            except (TypeError, ValueError):
                current_max_tokens = 0
            local_options.update(
                {
                    "reasoning": "off",
                    "temperature": min(float(local_options.get("temperature") or 0.7), 0.2),
                    "max_tokens": min(8192, max(4096, current_max_tokens)),
                }
            )
            repair_data["local_options"] = local_options
        try:
            repaired = _call_provider(repair_data, repair_system, repair_user, image)
        except JsonXGenerationCancelled:
            raise
        except Exception as repair_call_error:
            provider_diagnostics = getattr(repair_call_error, "diagnostics", {})
            raise JsonXGenerationError(
                f"{stage} response was invalid and the repair call failed: {repair_call_error}",
                {
                    "stage": stage,
                    "initial_error": str(first_error),
                    "raw_response": raw,
                    "repair_error": str(repair_call_error),
                    "repair_response": "",
                    "provider_diagnostics": provider_diagnostics,
                },
            ) from repair_call_error
        try:
            return _parse_and_normalize(
                repaired,
                prune_null=prune_null,
                enable_framing_and_placement=enable_framing_and_placement,
                presets=presets,
            )
        except Exception as repair_error:
            raise JsonXGenerationError(
                f"{stage} response and its repair were not valid canonical JsonX.",
                {
                    "stage": stage,
                    "initial_error": str(first_error),
                    "raw_response": raw,
                    "repair_error": str(repair_error),
                    "repair_response": repaired,
                },
            ) from repair_error


def _normalize_natural_paragraphs(text: str) -> str:
    """Turn Markdown list presentation into paragraphs without changing its words."""
    output: list[str] = []
    pending_items: list[str] = []

    def flush_items() -> None:
        if not pending_items:
            return
        sentences = []
        for item in pending_items:
            value = item.strip()
            if value and value[-1:] not in ".!?;:":
                value += "."
            if value:
                sentences.append(value)
        if sentences:
            output.append(" ".join(sentences))
        pending_items.clear()

    for line in text.splitlines():
        item = re.match(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)(.+?)\s*$", line)
        if item:
            pending_items.append(item.group(1))
            continue
        flush_items()
        output.append(line.rstrip())
    flush_items()
    return "\n".join(output).strip()


def validate_natural_prompt(raw: str) -> str:
    """Normalize one prose response and reject JSON or process-oriented output."""
    text = _strip_reasoning_blocks(raw).strip()
    # Providers use several harmless language labels for a single prose fence.
    # The content contract below, rather than the label, decides whether it is prose.
    fence = re.fullmatch(
        r"```[^\r\n`]*\r?\n(.*?)\r?\n?```",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if fence:
        text = fence.group(1).strip()
    elif "```" in text:
        raise ValueError("Natural-language output must be plain prose or one fenced text block.")

    # A one-line handoff phrase is formatting, not semantic prompt content.
    text = re.sub(
        r"^\s*(?:here(?:'s| is)|certainly|sure)[^\r\n]*(?:prompt|response)[^\r\n]*:?\s*(?:\r?\n)+",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    ).strip()
    if not text:
        raise ValueError("Natural-language output is empty.")

    try:
        json.loads(text)
    except Exception:
        pass
    else:
        raise ValueError("Natural-language output must be prose, not JSON.")

    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character not in "[{":
            continue
        try:
            embedded, _end = decoder.raw_decode(text[index:])
        except Exception:
            continue
        if isinstance(embedded, (dict, list)):
            raise ValueError("Natural-language output contains mixed prose and JSON structure.")
    if re.match(r"^\s*(?:analysis|reasoning|process|debug)\s*:", text, flags=re.IGNORECASE):
        raise ValueError("Natural-language output contains process metadata.")
    return _normalize_natural_paragraphs(text)


def _natural_section_title(key: str) -> str:
    """Format a JsonX root key as a readable prose-section heading."""
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(key or ""))
    words = re.sub(r"[_\-]+", " ", words).strip()
    return words.title() if words else "Prompt"


def _natural_scalar_values(value: Any) -> list[str]:
    """Collect every prompt-bearing leaf in source order without exposing paths."""
    if value is None:
        return []
    if isinstance(value, dict):
        return [item for child in value.values() for item in _natural_scalar_values(child)]
    if isinstance(value, list):
        return [item for child in value for item in _natural_scalar_values(child)]
    if isinstance(value, bool):
        return ["enabled"] if value else []
    text = str(value).strip()
    return [text] if text else []


def natural_prompt_from_validated_jsonx(stage_one: dict[str, Any], user_prompt: str = "") -> str:
    """Render a validated draft as prose when both model conversions fail.

    Canonical leaf values already carry the visual wording that must be preserved;
    JsonX paths remain internal implementation detail and are not exposed.
    """
    sections: list[str] = []
    for key, value in stage_one.items():
        leaves = _natural_scalar_values(value)
        prose = ". ".join(item.rstrip(". ") for item in leaves if item.strip()).strip()
        if not prose:
            continue
        if str(key).strip().lower() in {"negative", "negative_prompt", "negative_prompts", "avoid"}:
            sections.append(f"## Avoid\nAvoid {prose}.")
        else:
            sections.append(f"## {_natural_section_title(str(key))}\n{prose}.")
    if sections:
        return validate_natural_prompt("\n\n".join(sections))

    # A valid Stage 1 normally has leaves. Retain the original request rather
    # than failing a successful generation if a custom schema is empty.
    fallback = str(user_prompt or "").strip() or "Create the image described by the validated draft."
    return validate_natural_prompt(f"## Prompt\n{fallback}")


def _parse_or_repair_natural(
    data: dict[str, Any],
    raw: str,
    stage_one: dict[str, Any],
    user_prompt: str,
    image: Image.Image | None,
) -> str:
    stage = "Natural Language Stage 2"
    try:
        return validate_natural_prompt(raw)
    except Exception as first_error:
        repair_system, _repair_files = _repair_payload(data, True)
        repair_user = _render_user_template(
            data,
            "user_natural_repair",
            validation_error=str(first_error),
            user_instructions=user_prompt,
            stage_one_json=json.dumps(stage_one, ensure_ascii=False, indent=2),
            raw_response=raw,
        )
        repair_data = dict(data)
        repair_data["_gemini_response_mime_type"] = "text/plain"
        repair_data["_deepseek_response_format"] = "text"
        if str(data.get("backend") or "").strip().lower() == "local":
            local_options = dict(data.get("local_options") or {})
            try:
                current_max_tokens = int(local_options.get("max_tokens") or 0)
            except (TypeError, ValueError):
                current_max_tokens = 0
            local_options.update(
                {
                    "reasoning": "off",
                    "temperature": min(float(local_options.get("temperature") or 0.7), 0.2),
                    "max_tokens": min(8192, max(4096, current_max_tokens)),
                }
            )
            repair_data["local_options"] = local_options
        try:
            repaired = _call_provider(repair_data, repair_system, repair_user, image)
        except JsonXGenerationCancelled:
            raise
        except Exception as repair_call_error:
            provider_diagnostics = getattr(repair_call_error, "diagnostics", {})
            raise JsonXGenerationError(
                f"{stage} response was invalid and the repair call failed: {repair_call_error}",
                {
                    "stage": stage,
                    "initial_error": str(first_error),
                    "raw_response": raw,
                    "repair_error": str(repair_call_error),
                    "repair_response": "",
                    "provider_diagnostics": provider_diagnostics,
                },
            ) from repair_call_error
        try:
            return validate_natural_prompt(repaired)
        except Exception as repair_error:
            # Stage 1 is canonical and contains every semantic detail. Do not
            # discard it merely because a provider ignored both prose-only calls.
            data["_natural_fallback_diagnostics"] = {
                "stage": stage,
                "initial_error": str(first_error),
                "repair_error": str(repair_error),
            }
            return natural_prompt_from_validated_jsonx(stage_one, user_prompt)


def _is_context_limit_error(error: Exception) -> bool:
    message = str(error or "").lower()
    markers = (
        "context length",
        "context window",
        "maximum context",
        "max context",
        "token limit",
        "too many tokens",
        "prompt is too long",
        "input is too long",
    )
    return any(marker in message for marker in markers)


def generate_jsonx(data: dict[str, Any]) -> dict[str, Any]:
    _raise_if_cancelled(data)
    data["_jsonx_reference_bundle"] = jsonx_references.current_bundle()
    data["_jsonx_presets"] = load_presets(_profile_key(data), _reference_bundle(data))
    instructions = str(data.get("user_instructions") or "").strip()
    images = _decode_images(data)
    image = images[0] if images else None
    data["_pil_images"] = images
    if not instructions and image is None:
        raise ValueError("Enter JsonX instructions or connect a readable image.")

    context_mode = str(data.get("preset_context_mode") or "optimized").strip().lower()
    requested_generation_mode = str(data.get("generation_mode") or "fast").strip().lower()
    output_format = str(data.get("output_format") or "json").strip().lower()
    generation_mode = "refined" if output_format == "natural" else requested_generation_mode
    detail_level = str(data.get("detail_level") or "deep").strip().lower()
    generation_profile = str(data.get("generation_profile") or "adaptive").strip().lower()
    template_use_presets = bool(data.get("template_use_presets", False))
    enable_framing_and_placement = bool(data.get("enable_framing_and_placement", False))
    if requested_generation_mode not in {"fast", "refined"}:
        raise ValueError(f"Unsupported JsonX generation mode: {requested_generation_mode}")
    if output_format not in {"json", "natural"}:
        raise ValueError(f"Unsupported JsonX output format: {output_format}")
    if generation_profile not in {"adaptive", "template_fill"}:
        raise ValueError(f"Unsupported JsonX generation profile: {generation_profile}")
    if detail_level not in {"deep", "exhaustive"}:
        raise ValueError(f"Unsupported JsonX detail level: {detail_level}")

    stage_one_prompt, stage_one_files, full_preset_chars, effective_preset_mode = (
        _stage_one_payload(data, instructions, image is not None)
    )
    full_context_sent = effective_preset_mode == "full"
    base_user_prompt = instructions or "Describe the provided image as a complete JsonX prompt."
    user_prompt = _render_user_template(
        data,
        "user_stage_one",
        user_instructions=base_user_prompt,
    )
    if bool(data.get("refresh_vram", False)):
        runtime.refresh_comfy_vram()
    _raise_if_cancelled(data)
    try:
        raw_stage_one = _call_provider(
            data,
            stage_one_prompt,
            user_prompt,
            image,
        )
    except JsonXGenerationCancelled:
        raise
    except JsonXProviderError as exc:
        if full_context_sent and _is_context_limit_error(exc):
            raise ValueError(
                "Full Presets exceeds the selected model's context limit. "
                "Select a model or local context size that can accept the complete catalog, "
                "or explicitly switch preset context mode to Optimized Presets. "
                f"Provider error: {exc}"
            ) from exc
        raise JsonXGenerationError(
            str(exc),
            {"stage": "Stage 1", **exc.diagnostics},
        ) from exc
    except Exception as exc:
        if full_context_sent and _is_context_limit_error(exc):
            raise ValueError(
                "Full Presets exceeds the selected model's context limit. "
                "Select a model or local context size that can accept the complete catalog, "
                "or explicitly switch preset context mode to Optimized Presets. "
                f"Provider error: {exc}"
            ) from exc
        raise
    stage_one = _parse_or_repair(
        data,
        raw_stage_one,
        "Stage 1",
        image,
        prune_null=generation_profile == "template_fill",
    )
    if generation_profile == "template_fill":
        stage_one = constrain_template_fill_structure(
            stage_one,
            template_fill_hierarchy(
                enable_framing_and_placement=enable_framing_and_placement,
                profile_key=_profile_key(data),
                bundle=_reference_bundle(data),
            ),
        )

    final_prompt = stage_one
    final_output = json.dumps(stage_one, ensure_ascii=False, indent=2)
    if output_format == "natural":
        natural_user = _render_user_template(
            data,
            "user_natural_conversion",
            user_instructions=base_user_prompt,
            stage_one_json=json.dumps(stage_one, ensure_ascii=False, indent=2),
        )
        try:
            natural_data = dict(data)
            natural_data["_gemini_response_mime_type"] = "text/plain"
            natural_data["_grok_response_format"] = "text"
            natural_data["_deepseek_response_format"] = "text"
            natural_data["_provider_stage"] = "natural_stage_2"
            raw_natural = _call_provider(
                natural_data,
                _stage_two_payload(data, image is not None, "natural")[0],
                natural_user,
                image,
            )
        except JsonXProviderError as exc:
            raise JsonXGenerationError(
                str(exc),
                {"stage": "Natural Language Stage 2", **exc.diagnostics},
            ) from exc
        final_output = _parse_or_repair_natural(
            data,
            raw_natural,
            stage_one,
            base_user_prompt,
            image,
        )
    elif generation_mode == "refined":
        refinement_user = _render_user_template(
            data,
            "user_json_refinement",
            user_instructions=base_user_prompt,
            stage_one_json=json.dumps(stage_one, ensure_ascii=False, indent=2),
        )
        try:
            refined_data = dict(data)
            refined_data["_provider_stage"] = "refined_stage_2"
            raw_refined = _call_provider(
                refined_data,
                _stage_two_payload(data, image is not None, "json")[0],
                refinement_user,
                image,
            )
        except JsonXProviderError as exc:
            raise JsonXGenerationError(
                str(exc),
                {"stage": "Refined Stage 2", **exc.diagnostics},
            ) from exc
        refined_prompt = _parse_or_repair(data, raw_refined, "Refined Stage 2", image)
        final_prompt = (
            overlay_template_refinement(stage_one, refined_prompt)
            if generation_profile == "template_fill"
            else refined_prompt
        )
        final_output = json.dumps(final_prompt, ensure_ascii=False, indent=2)

    result = {
        "prompt": final_output,
        # Route code consumes this only to populate Unified's legacy negative
        # output. It is removed before the HTTP response and never persisted.
        "_stage_one": stage_one,
        "output_format": output_format,
        "generation_mode": generation_mode,
        "generation_profile": generation_profile,
        "template_use_presets": template_use_presets,
        "enable_framing_and_placement": enable_framing_and_placement,
        "preset_context_mode": effective_preset_mode,
        "detail_level": detail_level,
        "hierarchy_metrics": hierarchy_metrics(final_prompt),
        "full_preset_chars": full_preset_chars,
        "activated_files": {
            "stage_one": stage_one_files,
        },
    }
    if output_format == "json":
        result["prompt_json"] = final_output
    natural_fallback_diagnostics = data.get("_natural_fallback_diagnostics")
    if isinstance(natural_fallback_diagnostics, dict):
        result["natural_fallback"] = True
        result["diagnostics"] = natural_fallback_diagnostics
    elif isinstance(data.get("_provider_diagnostics"), dict):
        result["diagnostics"] = data["_provider_diagnostics"]
    return result
