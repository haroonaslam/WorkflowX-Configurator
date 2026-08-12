from __future__ import annotations

import base64
import io
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from PIL import Image

from .jsonx_backends import JsonXProviderError
from .jsonx_backends import gemini as gemini_backend
from .jsonx_backends import local_llama as local_llama_backend
from .jsonx_backends import local_models
from .jsonx_backends import ollama as ollama_backend
from .jsonx_backends import openai_compatible as openai_backend
from .jsonx_backends import runtime


PRESETS_PATH = Path(__file__).with_name("presets.json")
OPTIMIZED_CANDIDATE_BUDGET = 16_000
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

DEFAULT_STAGE_ONE_INSTRUCTIONS = """You are LLM to JsonX. Produce one deep, modular, deterministic JSON image prompt.

Rules:
- Return the prompt object itself: valid JSON only, no markdown, commentary, or process metadata.
- Use the supplied JsonX catalog paths as the structural contract. Preset IDs are lookup metadata only and must never appear as output keys or values.
- A catalog entry shown as `scene.environment | env_indoor_home => interior of a modern home` must output `{"scene":{"environment":"interior of a modern home"}}`.
- Never output the incorrect ID-key form `{"scene":{"environment":{"env_indoor_home":"interior of a modern home"}}}`.
- Convert catalog `subject` structure into the repeatable output array `subjects`, even for one subject.
- Catalog sibling paths remain siblings. Do not nest `scene.background` or `scene.depth` inside `scene.environment`.
- Model each distinct visual concept as its own atomic leaf. Never compress several attributes into one broad summary string when catalog child paths exist.
- Build from parent to child to sub-child to leaf. For visible people, independently expand relevant identity, clothing, pose/orientation/body-parts, skin, hair, face, and expression branches. For objects, replace human branches with equally granular object-specific construction, material, surface, condition, placement, and interaction branches.
- Expand scene context into relevant environment, location, time, background, surface, props, and depth leaves. Expand lighting into type, direction, quality, temperature, shadows, highlights, intensity, and sources when visually supportable.
- Expand camera intent into shot/angle/position plus nested lens and exposure leaves when supportable. Keep style, mood, quality, and negative guidance modular.
- Prefer exact preset fit, then a reasonable same-path preset fit, then a deterministic custom value.
- Multiple subjects or primary objects must be separate array items with their own details. Add interactions only when cardinality and framing support them.
- Visibility governs detail: close-ups deeply expand visible face/hair/skin while omitting invisible lower-body detail; medium shots expand visible upper-body branches; full-body framing expands all visible clothing, pose, and body-part branches.
- Resolve contradictions to one visually plausible state. Avoid vague, optional, or choice-oriented wording.
- Do not emit keys such as pipeline_stage, stage, task, debug, reasoning, timestamp, or original_intent."""

DEFAULT_REFINEMENT_INSTRUCTIONS = """You are the JsonX coherence refiner. Refine the supplied draft into the final deep prompt object.

- Return valid prompt-only JSON with no wrapper, markdown, commentary, or process metadata.
- Do not use or request presets during refinement.
- Preserve every valid atomic leaf from the draft while pruning only details impossible for the selected framing.
- Increase hierarchy and detail where the draft used a broad parent value or omitted a visually evident sub-branch. Never replace a detailed subtree with a summary string.
- Resolve contradictions according to explicit user intent, inferred mode, framing visibility, then secondary leaves.
- Keep multiple entities modular and interactions consistent with subject count.
- Enrich materials, textures, surface condition, lighting interaction, camera intent, environment, and visible subject/object properties without flattening the hierarchy.
- Use deterministic wording and never offer alternatives."""

DEFAULT_TEMPLATE_FILL_INSTRUCTIONS = """You are LLM to JsonX operating in Template Fill profile.

Rules:
- Return exactly one valid JSON prompt object with no markdown, wrapper, commentary, or process metadata.
- Use the supplied blank JsonX hierarchy as the output structure. Do not rename, move, wrap, flatten, or invent branches.
- Replace each applicable `null` leaf with one concise, deterministic natural-language visual value.
- Leave a leaf as JSON `null` only when it clearly does not apply, is not visible or supported, or would require guessing.
- Do not use empty strings, placeholder text, arrays, or objects as leaf values. Catalog leaves must remain scalar.
- `subjects` must remain an array of objects. Use one populated object per distinct visible or requested subject; duplicate the supplied subject item structure only when another subject is required.
- Keep independent details in their existing independent leaves. Resolve contradictions and respect framing visibility.
- Preset IDs are lookup metadata only and must never appear as output keys or values."""

TEMPLATE_FILL_PRESET_GUIDANCE = """Preset use is enabled for Template Fill.
- The complete presets.json catalog is supplied verbatim after the blank hierarchy.
- For each applicable leaf, first choose the preset value that faithfully matches the request or image.
- Output the preset's natural-language value, never its internal preset ID.
- If no preset value is suitable, write a custom value in the same concise, deterministic descriptive style as neighboring values for that leaf. Never force an inaccurate preset match."""

TEMPLATE_FILL_NO_PRESET_GUIDANCE = """Preset use is disabled for Template Fill.
- Fill applicable leaves by reasoning from the user instructions and image.
- Use concise, deterministic natural-language visual values.
- Keep `null` only where the leaf genuinely does not apply or lacks support."""

TEMPLATE_FILL_REFINEMENT_GUIDANCE = """Template Fill refinement constraint:
- Improve only coherence, specificity, and wording of existing populated scalar leaves.
- Preserve the populated Stage 1 hierarchy and every existing path. Do not rename, move, flatten, wrap, or add branches.
- You may set an existing leaf to JSON `null` only when it is clearly contradictory, impossible, or unsupported. Omitted paths are treated as unchanged.
- Return the complete refined prompt object as JSON only."""

PRESET_OPEN_WORLD_GUIDANCE = """Preset coverage rule: the JsonX preset catalog is authoritative guidance, not a closed vocabulary.
- First use an exact catalog value when it faithfully expresses the requested or observed concept.
- Otherwise use a semantically close value only when it preserves the specific meaning; never force a merely similar preset that changes, weakens, or generalizes the intent.
- When the correct catalog path exists but none of its preset values is suitable, keep that path and write a concise, deterministic custom natural-language value in the same descriptive style as neighboring preset values.
- A catalog leaf is scalar. When a concept needs nested children beneath a catalog scalar leaf, keep the catalog leaf scalar when applicable and put the expansion in a sibling `<leaf>_details` custom subtree; for example, use `scene.environment_details.*`, not an object inside `scene.environment`.
- When no suitable catalog path exists, place the concept beneath the closest logical JsonX parent and create the smallest coherent nested branch needed to express it. Use descriptive lower_snake_case keys and natural-language visual values; never invent preset IDs or ID-like keys.
- Preserve deep tree structure for custom content. Split independent attributes into separate leaves instead of packing uncovered details into one catch-all string.
- Never omit a requested, visible, or strongly implied concept merely because the preset catalog does not contain it. Reason from the instructions and image, while respecting visibility, coherence, and the prompt-only contract."""

REFINEMENT_OPEN_WORLD_GUIDANCE = """Open-world refinement rule: custom JsonX paths and values are valid prompt content.
- Preserve a coherent custom leaf or subtree when it expresses a concept not covered by the draft's catalog-derived structure.
- Do not delete, flatten, or replace custom content merely because it is not a preset value.
- Keep catalog leaves scalar; move a justified nested expansion beside the leaf as a `<leaf>_details` custom subtree.
- When adding an uncovered detail, use the closest logical parent, descriptive lower_snake_case keys, atomic natural-language values, and the same concise visual wording style as the rest of the prompt."""

DEPTH_GUIDANCE = {
    "deep": (
        "Coverage target: maximize the relevant JsonX tree, subtrees, and atomic leaves. Explore "
        "every root group and child branch that is supported by the instructions, image, or a "
        "strong visual implication, and use the deepest sensible catalog or custom path. Pay "
        "particular attention to subjects[].dress.*, subjects[].pose.*, subjects[].properties.*, "
        "camera.lens.*, and camera.exposure.*. There is no leaf-count target or maximum and no "
        "count should act as a stopping condition. Continue until all relevant independent visual "
        "attributes are represented, but never add unsupported filler merely to enlarge the tree."
    ),
    "exhaustive": (
        "Coverage target: perform an exhaustive relevance pass and maximize tree depth, subtrees, "
        "and atomic leaves across every applicable catalog and reasoned custom branch. Use the "
        "deepest coherent child paths instead of parent-level summaries, and keep expanding until "
        "every visible, requested, or strongly implied independent attribute has its own leaf. "
        "There is no leaf-count target or maximum and no count should act as a stopping condition. "
        "Omit only branches made irrelevant by framing, subject type, coherence, or evidence; never "
        "invent invisible details or padding."
    ),
}


class JsonXGenerationError(ValueError):
    def __init__(self, message: str, diagnostics: dict[str, Any] | None = None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}

def raw_presets_text() -> str:
    """Return the packaged preset source without parsing or reserialization."""
    return PRESETS_PATH.read_bytes().decode("utf-8")


def load_presets() -> dict[str, Any]:
    parsed = json.loads(raw_presets_text().lstrip("\ufeff"))
    if not isinstance(parsed, dict):
        raise ValueError("JsonX presets.json must contain a JSON object.")
    return parsed


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
) -> str:
    catalog = presets or load_presets()
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
    return (
        "JsonX preset schema paths (complete):\n"
        f"{schema}\n\n"
        "Relevant preset candidates (ranked, preset ID => canonical output value):\n"
        f"{candidate_text}"
    )


def build_preset_context(mode: str, user_instructions: str) -> tuple[str, int]:
    mode = str(mode or "optimized").strip().lower()
    raw = raw_presets_text()
    if mode == "full":
        return "JsonX presets.json (verbatim):\n" + raw, len(raw)
    if mode != "optimized":
        raise ValueError(f"Unsupported JsonX preset context mode: {mode}")
    return optimized_preset_context(user_instructions), len(raw)


def template_fill_hierarchy(presets: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the complete live catalog hierarchy with null scalar leaves."""
    catalog = presets if presets is not None else load_presets()

    def blank(value: Any) -> Any:
        if _is_leaf_options(value):
            return None
        if isinstance(value, dict):
            return {str(key): blank(item) for key, item in value.items()}
        return None

    output: dict[str, Any] = {}
    for key, value in catalog.items():
        if key == "subject":
            output["subjects"] = [blank(value)]
        elif key == "interaction_suggestions":
            output["interactions"] = blank(value)
        else:
            output[str(key)] = blank(value)
    return output


def template_fill_context(use_presets: bool) -> tuple[str, int]:
    raw = raw_presets_text()
    hierarchy = json.dumps(template_fill_hierarchy(), ensure_ascii=False, indent=2)
    context = "Blank JsonX hierarchy to fill:\n" + hierarchy
    if use_presets:
        context += "\n\nComplete JsonX presets.json (verbatim):\n" + raw
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


def _set_prompt_path(target: dict[str, Any], tokens: list[str | int], value: Any) -> None:
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
                if existing not in ({}, None, value):
                    raise ValueError("JsonX output contains conflicting values for one canonical path.")
                current[token] = value
            else:
                current = current[token]
            continue
        if not isinstance(current, dict):
            raise ValueError("JsonX canonicalization encountered an invalid object path.")
        if last:
            if token in current and current[token] != value:
                raise ValueError(f"JsonX output contains conflicting values at '{'.'.join(map(str, tokens))}'.")
            current[token] = value
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
        return choices[0] if len(choices) == 1 else None

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
                            )
                            leaf_was_set = True
                            continue
                        resolved_id = choose_id_path(nested_key_text, catalog_path, nested_value)
                        if resolved_id and resolved_id[0] == catalog_path:
                            _set_prompt_path(output, out_tokens, resolved_id[1])
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
                    ):
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
                        _set_prompt_path(output, out_tokens, unresolved[0][1])
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
                    _set_prompt_path(output, out_tokens, ", ".join(str(item) for item in value))
                    return
                leaf_name = str(out_tokens[-1])
                detail_tokens = [*out_tokens[:-1], f"{leaf_name}_details"]
                _set_prompt_path(output, detail_tokens, {"items": value})
                return
            _set_prompt_path(output, out_tokens, value)
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
        elif isinstance(value, str) and value in preset_ids:
            raise ValueError(f"JsonX output still contains internal preset ID '{value}' as a value.")

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


def _custom_instructions(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    if len(text) > 50_000:
        raise ValueError("Custom JsonX backend instructions must be 50,000 characters or fewer.")
    return text


def depth_guidance(detail_level: str) -> str:
    level = str(detail_level or "deep").strip().lower()
    if level not in DEPTH_GUIDANCE:
        raise ValueError(f"Unsupported JsonX detail level: {level}")
    return DEPTH_GUIDANCE[level]


def stage_one_system_prompt(
    preset_context: str,
    has_image: bool,
    instructions: str | None = None,
    detail_level: str = "deep",
) -> str:
    image_rule = (
        "Inspect the provided image and model only visible, relevant details."
        if has_image
        else "No image is provided; derive the scene from the user instructions."
    )
    base = _custom_instructions(instructions, DEFAULT_STAGE_ONE_INSTRUCTIONS)
    return (
        f"{base}\n\nImage rule: {image_rule}\n\n{PRESET_OPEN_WORLD_GUIDANCE}"
        f"\n\n{depth_guidance(detail_level)}\n\n{preset_context}"
    )


def template_fill_system_prompt(
    template_context: str,
    has_image: bool,
    use_presets: bool,
    instructions: str | None = None,
) -> str:
    image_rule = (
        "Inspect the provided image and fill only visible, relevant, or strongly supported details."
        if has_image
        else "No image is provided; fill the hierarchy from the user instructions only."
    )
    base = _custom_instructions(instructions, DEFAULT_TEMPLATE_FILL_INSTRUCTIONS)
    preset_rule = TEMPLATE_FILL_PRESET_GUIDANCE if use_presets else TEMPLATE_FILL_NO_PRESET_GUIDANCE
    return f"{base}\n\nImage rule: {image_rule}\n\n{preset_rule}\n\n{template_context}"


def refinement_system_prompt(
    has_image: bool,
    instructions: str | None = None,
    detail_level: str = "deep",
) -> str:
    image_rule = "Use the reference image as visual evidence." if has_image else "No reference image is provided."
    base = _custom_instructions(instructions, DEFAULT_REFINEMENT_INSTRUCTIONS)
    return (
        f"{base}\n\nImage rule: {image_rule}\n\n{REFINEMENT_OPEN_WORLD_GUIDANCE}"
        f"\n\n{depth_guidance(detail_level)}"
    )


def template_fill_refinement_system_prompt(
    has_image: bool,
    instructions: str | None = None,
    detail_level: str = "deep",
) -> str:
    return (
        refinement_system_prompt(has_image, instructions, detail_level)
        + "\n\n"
        + TEMPLATE_FILL_REFINEMENT_GUIDANCE
    )


def instruction_templates() -> dict[str, Any]:
    return {
        "stage_one": DEFAULT_STAGE_ONE_INSTRUCTIONS,
        "template_fill": DEFAULT_TEMPLATE_FILL_INSTRUCTIONS,
        "refinement": DEFAULT_REFINEMENT_INSTRUCTIONS,
        "generation_profiles": ["adaptive", "template_fill"],
        "default_generation_profile": "adaptive",
        "detail_levels": list(DEPTH_GUIDANCE),
        "default_detail_level": "deep",
    }


def effective_instruction_preview(data: dict[str, Any]) -> dict[str, Any]:
    user_instructions = str(data.get("user_instructions") or "").strip()
    context_mode = str(data.get("preset_context_mode") or "optimized").strip().lower()
    detail_level = str(data.get("detail_level") or "deep").strip().lower()
    generation_profile = str(data.get("generation_profile") or "adaptive").strip().lower()
    if generation_profile not in {"adaptive", "template_fill"}:
        raise ValueError(f"Unsupported JsonX generation profile: {generation_profile}")
    template_use_presets = bool(data.get("template_use_presets", False))
    has_image = bool(data.get("has_image", False))
    if generation_profile == "template_fill":
        preset_context, full_chars = template_fill_context(template_use_presets)
        stage_one = template_fill_system_prompt(
            preset_context,
            has_image,
            template_use_presets,
            data.get("template_fill_instructions"),
        )
        refinement = template_fill_refinement_system_prompt(
            has_image,
            data.get("refinement_instructions"),
            detail_level,
        )
        effective_preset_mode = "full" if template_use_presets else "none"
    else:
        preset_context, full_chars = build_preset_context(context_mode, user_instructions)
        stage_one = stage_one_system_prompt(
            preset_context,
            has_image,
            data.get("stage_one_instructions"),
            detail_level,
        )
        refinement = refinement_system_prompt(
            has_image,
            data.get("refinement_instructions"),
            detail_level,
        )
        effective_preset_mode = context_mode
    return {
        "stage_one": stage_one,
        "refinement": refinement,
        "stage_one_characters": len(stage_one),
        "refinement_characters": len(refinement),
        "full_preset_chars": full_chars,
        "detail_level": detail_level,
        "generation_profile": generation_profile,
        "template_use_presets": template_use_presets,
        "preset_context_mode": effective_preset_mode,
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
    backend = str(data.get("backend") or "gemini").strip().lower()
    images = [image] if image is not None else []
    timeout = max(5.0, min(3600.0, float(data.get("timeout") or 120)))
    if backend == "gemini":
        return gemini_backend.generate(
            str(data.get("api_key") or "").strip(),
            str(data.get("model") or ""),
            system_prompt,
            user_prompt,
            pil_images=images,
            safety_settings=data.get("gemini_safety") if isinstance(data.get("gemini_safety"), dict) else None,
            timeout=timeout,
        )
    if backend == "openai":
        return openai_backend.generate(
            str(data.get("base_url") or ""),
            str(data.get("api_key") or "").strip(),
            str(data.get("model") or ""),
            system_prompt,
            user_prompt,
            pil_images=images,
            timeout=timeout,
            unload_after=bool(data.get("unload_after", False)),
        )
    if backend == "ollama":
        return ollama_backend.generate(
            str(data.get("host") or ""),
            str(data.get("model") or ""),
            system_prompt,
            user_prompt,
            pil_images=images,
            think=bool(data.get("think", False)),
            unload_after=bool(data.get("unload_after", True)),
            timeout=timeout,
        )
    if backend == "local":
        options = data.get("local_options") if isinstance(data.get("local_options"), dict) else {}
        options = dict(options)
        options.setdefault("timeout", timeout)
        return local_llama_backend.generate(
            model=str(data.get("model") or ""),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            pil_images=images,
            mmproj=str(data.get("mmproj") or "none"),
            system_prompt_preset=str(data.get("system_prompt_preset") or "none"),
            additional_model_paths=data.get("additional_model_paths"),
            options=options,
        )
    raise ValueError(f"Unsupported JsonX backend: {backend}")


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


def _parse_and_normalize(raw: str, *, prune_null: bool = False) -> dict[str, Any]:
    parsed = parse_prompt_json(raw)
    canonical = canonicalize_prompt_structure(parsed)
    normalized = validate_canonical_prompt(align_prompt_to_presets(canonical))
    return validate_canonical_prompt(prune_null_leaves(normalized)) if prune_null else normalized


def _parse_or_repair(
    data: dict[str, Any],
    raw: str,
    stage: str = "generation",
    image: Image.Image | None = None,
    prune_null: bool = False,
) -> dict[str, Any]:
    try:
        return _parse_and_normalize(raw, prune_null=prune_null)
    except Exception as first_error:
        catalog = load_presets()
        output_roots = [
            "subjects" if key == "subject" else "interactions" if key == "interaction_suggestions" else key
            for key in catalog
        ]
        subject_branches = list(catalog.get("subject", {})) if isinstance(catalog.get("subject"), dict) else []
        repair_system = (
            "Repair the supplied response with the smallest possible edits into one valid JsonX prompt object. "
            "This is syntax and structure repair, not a new generation or summary. Preserve every recoverable "
            "branch, key, and visual value from the source; never replace a detailed subtree with a broad string. "
            "Return JSON only with no wrapper, markdown, commentary, or process metadata. "
            "The top level must be the prompt object itself, never a catalog, schema, custom_paths, or result wrapper. "
            "Internal preset IDs must not appear as keys or values. Catalog leaves are scalar; when the source "
            "expands a catalog leaf, retain the expansion as a descriptive sibling custom subtree. "
            "The `subjects` value must be an array of objects. Each subject object must retain its own nested "
            "identity, clothing or dress, pose, properties or appearance, face, hair, skin, and expression details "
            "when present. Never turn a subject object into a label string. `interactions` must be an object. "
            "Keep catalog sibling paths as siblings and preserve valid open-world custom paths; "
            "presets are guidance, not an allow-list. "
            f"Catalog-derived output roots include: {', '.join(output_roots)}. "
            f"Catalog subject branches include: {', '.join(subject_branches)}."
        )
        original_instructions = str(data.get("user_instructions") or "").strip()
        repair_user = (
            f"Validation error: {first_error}\n\n"
            f"Original user instructions:\n{original_instructions or '(image-led request)'}\n\n"
            f"Response to minimally repair:\n{raw}"
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
            return _parse_and_normalize(repaired, prune_null=prune_null)
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
    instructions = str(data.get("user_instructions") or "").strip()
    image = _decode_image(data.get("image_b64"))
    if not instructions and image is None:
        raise ValueError("Enter JsonX instructions or connect a readable image.")

    context_mode = str(data.get("preset_context_mode") or "optimized").strip().lower()
    generation_mode = str(data.get("generation_mode") or "fast").strip().lower()
    detail_level = str(data.get("detail_level") or "deep").strip().lower()
    generation_profile = str(data.get("generation_profile") or "adaptive").strip().lower()
    template_use_presets = bool(data.get("template_use_presets", False))
    if generation_mode not in {"fast", "refined"}:
        raise ValueError(f"Unsupported JsonX generation mode: {generation_mode}")
    if generation_profile not in {"adaptive", "template_fill"}:
        raise ValueError(f"Unsupported JsonX generation profile: {generation_profile}")
    depth_guidance(detail_level)

    if generation_profile == "template_fill":
        preset_context, full_preset_chars = template_fill_context(template_use_presets)
        stage_one_prompt = template_fill_system_prompt(
            preset_context,
            image is not None,
            template_use_presets,
            data.get("template_fill_instructions"),
        )
        effective_preset_mode = "full" if template_use_presets else "none"
    else:
        preset_context, full_preset_chars = build_preset_context(context_mode, instructions)
        stage_one_prompt = stage_one_system_prompt(
            preset_context,
            image is not None,
            data.get("stage_one_instructions"),
            detail_level,
        )
        effective_preset_mode = context_mode
    full_context_sent = effective_preset_mode == "full"
    user_prompt = instructions or "Describe the provided image as a complete JsonX prompt."
    if bool(data.get("refresh_vram", False)):
        runtime.refresh_comfy_vram()
    try:
        raw_stage_one = _call_provider(
            data,
            stage_one_prompt,
            user_prompt,
            image,
        )
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
        stage_one = constrain_template_fill_structure(stage_one)

    final_prompt = stage_one
    if generation_mode == "refined":
        refinement_user = (
            f"Original user instructions:\n{user_prompt}\n\n"
            f"JsonX draft to refine:\n{json.dumps(stage_one, ensure_ascii=False, indent=2)}"
        )
        try:
            raw_refined = _call_provider(
                data,
                template_fill_refinement_system_prompt(
                    image is not None,
                    data.get("refinement_instructions"),
                    detail_level,
                )
                if generation_profile == "template_fill"
                else refinement_system_prompt(
                    image is not None,
                    data.get("refinement_instructions"),
                    detail_level,
                ),
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

    return {
        "prompt_json": json.dumps(final_prompt, ensure_ascii=False, indent=2),
        "generation_mode": generation_mode,
        "generation_profile": generation_profile,
        "template_use_presets": template_use_presets,
        "preset_context_mode": effective_preset_mode,
        "detail_level": detail_level,
        "hierarchy_metrics": hierarchy_metrics(final_prompt),
        "full_preset_chars": full_preset_chars,
    }
