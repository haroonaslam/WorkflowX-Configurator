import copy
import json
import random
import re

from .api import convert_prompt_json_text_to_template, load_visual_presets, load_visual_templates


DEFAULT_PROMPT = {}
_PATH_SEGMENT_RE = re.compile(r"^([^\.\[\]]+)(?:\[(\d+)\])?$")

RULES_HELP_TEXT = """AFJ Randomize Rules (one line per field):
path | mode | value

Examples:
scene.environment | preset | indoor photography studio, seamless backdrop
subjects[0].dress.top.color | preset | topcolor_black; topcolor_white; topcolor_red
subjects[0].custom_tag | custom | alpha; beta; gamma

Notes:
- mode is visual only; runtime recomputes mode from field metadata.
- If value equals the template current value:
  - preset-backed fields randomize from preset options
  - custom-only fields remain unchanged
- If value differs from template current value, semicolon-separated values are used as override candidates.
"""


def _compile_tree_node(node):
    if not isinstance(node, dict):
        return None

    node_type = node.get("node_type")

    if node_type == "field":
        value = str(node.get("value") or "").strip()
        return value if value else None

    if node_type == "group":
        out = {}
        for child in node.get("children") or []:
            val = _compile_tree_node(child)
            if val is None:
                continue
            out[str(child.get("key") or "field")] = val
        return out if out else None

    if node_type == "array":
        arr = []
        for item in node.get("items") or []:
            val = _compile_tree_node(item)
            if val is not None:
                arr.append(val)
        return arr if arr else None

    return None


def _parse_exact_indexed_path(path):
    raw = str(path or "").strip()
    if not raw:
        return None

    tokens = []
    for segment in raw.split("."):
        m = _PATH_SEGMENT_RE.fullmatch(segment.strip())
        if not m:
            return None
        key = m.group(1)
        idx = m.group(2)
        tokens.append((key, int(idx) if idx is not None else None))

    return tokens


def _find_group_child(group_node, key):
    for child in group_node.get("children") or []:
        if str(child.get("key") or "") == key:
            return child
    return None


def _resolve_field_by_path(tree_root, path):
    tokens = _parse_exact_indexed_path(path)
    if not tokens:
        return None

    current = tree_root
    if not isinstance(current, dict):
        return None

    root_key = str(current.get("key") or "")
    if tokens and tokens[0][0] == root_key and tokens[0][1] is None:
        tokens = tokens[1:]

    for key, idx in tokens:
        if not isinstance(current, dict) or current.get("node_type") != "group":
            return None

        child = _find_group_child(current, key)
        if child is None:
            return None

        if idx is not None:
            if child.get("node_type") != "array":
                return None
            items = child.get("items") or []
            if idx < 0 or idx >= len(items):
                return None
            current = items[idx]
        else:
            current = child

    if isinstance(current, dict) and current.get("node_type") == "field":
        return current
    return None


def _parse_rule_lines(text):
    entries = []
    parse_issues = []

    for i, raw_line in enumerate(str(text or "").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split("|", 2)
        if len(parts) < 3:
            parse_issues.append({"line": i, "message": "expected 'path | mode | value'"})
            continue

        path = parts[0].strip()
        mode = parts[1].strip()
        value = parts[2].strip()

        if not path:
            parse_issues.append({"line": i, "message": "empty path"})
            continue

        entries.append(
            {
                "line": i,
                "path": path,
                "mode": mode,
                "value": value,
            }
        )

    return entries, parse_issues


def _is_non_empty_field(field_node):
    return str(field_node.get("value") or "").strip() != ""


def _split_override_candidates(value_text):
    vals = [v.strip() for v in str(value_text or "").split(";")]
    return [v for v in vals if v]


def _is_leaf_options(node):
    if not isinstance(node, dict) or not node:
        return False
    return all(isinstance(v, str) for v in node.values())


def _flatten_preset_leaves(node, prefix="", out=None):
    if out is None:
        out = {}
    if not isinstance(node, dict):
        return out
    if _is_leaf_options(node):
        out[prefix] = node
        return out
    for k, v in node.items():
        nxt = f"{prefix}.{k}" if prefix else str(k)
        _flatten_preset_leaves(v, nxt, out)
    return out


def _base_key(key):
    return re.sub(r"_\d+$", "", str(key or "")).lower()


def _build_preset_maps(presets):
    by_path = _flatten_preset_leaves(presets)
    by_leaf = {}
    for path, options in by_path.items():
        leaf = _base_key(path.split(".")[-1] if path else "")
        by_leaf.setdefault(leaf, []).append((path, options))
    return by_path, by_leaf


def _resolve_dynamic_options(field_node, preset_by_path, preset_by_leaf):
    p1 = str(field_node.get("preset_path") or "").strip()
    if p1 and p1 in preset_by_path:
        return preset_by_path[p1]

    p2 = str(field_node.get("origin_preset_path") or "").strip()
    if p2 and p2 in preset_by_path:
        return preset_by_path[p2]

    cands = preset_by_leaf.get(_base_key(field_node.get("key")), [])
    if len(cands) == 1:
        return cands[0][1]

    return None


def _apply_randomize_rules(tree_root, rules_text, rng, preset_by_path, preset_by_leaf):
    warnings = []
    run_logs = []

    entries, parse_issues = _parse_rule_lines(rules_text)
    for issue in parse_issues:
        msg = f"rule line {issue['line']}: {issue['message']}"
        warnings.append(msg)
        run_logs.append(f"line {issue['line']} | error | {issue['message']}")

    for e in entries:
        path = e["path"]
        node = _resolve_field_by_path(tree_root, path)
        if node is None:
            warnings.append(f"rule path not found: {path}")
            run_logs.append(f"{path} | error | path not found")
            continue

        if not _is_non_empty_field(node):
            warnings.append(f"rule path skipped (empty field): {path}")
            run_logs.append(f"{path} | error | field empty in template, skipped")
            continue

        current_value = str(node.get("value") or "")
        typed_value = str(e.get("value") or "")

        resolved_options = _resolve_dynamic_options(node, preset_by_path, preset_by_leaf)
        has_options = isinstance(resolved_options, dict) and bool(resolved_options)
        effective_mode = "preset" if has_options else "custom"
        expected_preset = bool(str(node.get("preset_path") or "").strip() or str(node.get("origin_preset_path") or "").strip())

        has_override = typed_value != current_value

        if not has_override:
            if not has_options:
                if expected_preset:
                    warnings.append(f"rule path skipped (preset options not found): {path}")
                    run_logs.append(f"{path} | error | preset options not found in current presets, skipped")
                else:
                    run_logs.append(f"{path} | custom | template default, no override: {current_value}")
                continue

            candidates = [str(v) for v in resolved_options.values() if str(v).strip()]
            if not candidates:
                warnings.append(f"rule path skipped (empty preset options): {path}")
                run_logs.append(f"{path} | error | preset options empty, skipped")
                continue

            final_value = rng.choice(candidates)
            node["value"] = final_value
            run_logs.append(f"{path} | preset | template default, randomized via preset: {final_value}")
            continue

        override_candidates = _split_override_candidates(typed_value)
        if not override_candidates:
            warnings.append(f"rule path skipped (empty override values): {path}")
            run_logs.append(f"{path} | error | override empty, skipped")
            continue

        if len(override_candidates) == 1:
            final_value = override_candidates[0]
            node["value"] = final_value
            if effective_mode == "preset":
                run_logs.append(f"{path} | preset | override detected single value, using: {final_value}")
            else:
                run_logs.append(f"{path} | custom | Single value override to: {final_value}")
            continue

        final_value = rng.choice(override_candidates)
        node["value"] = final_value
        if effective_mode == "preset":
            run_logs.append(f"{path} | preset | override detected multi value, randomized to: {final_value}")
        else:
            run_logs.append(f"{path} | custom | override detected multi value, randomized to: {final_value}")

    return warnings, run_logs


def _format_run_log(lines):
    if not lines:
        return "log:\n(no applicable rule lines processed)"
    return "log:\n" + "\n".join(lines)


class FluxVisualJsonBuilderNode:
    CATEGORY = "AFJ"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt_json",)
    FUNCTION = "build"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "prompt_json": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": json.dumps(DEFAULT_PROMPT, indent=2, ensure_ascii=False),
                    },
                ),
            },
        }

    def build(self, prompt_json=""):
        text = (prompt_json or "").strip()
        if not text:
            text = json.dumps(DEFAULT_PROMPT, ensure_ascii=False)

        try:
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                parsed = {}
            out = json.dumps(parsed, indent=2, ensure_ascii=False)
        except Exception:
            out = json.dumps(
                {
                    "error": "Invalid JSON in prompt_json input.",
                    "raw_text": text,
                },
                indent=2,
                ensure_ascii=False,
            )

        return (out,)


class FluxTemplateRandomizerNode:
    CATEGORY = "AFJ"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("prompt_json", "run_log")
    FUNCTION = "build"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "template_name": (
                    "STRING",
                    {
                        "multiline": False,
                        "default": "",
                    },
                ),
                "randomize_rules": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                    },
                ),
                "randomize_rules_help": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": RULES_HELP_TEXT,
                    },
                ),
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 2147483647,
                        "step": 1,
                    },
                ),
            },
        }

    @staticmethod
    def _error_payload(message, template_name="", warnings=None):
        payload = {
            "error": message,
            "template_name": template_name,
        }
        if warnings:
            payload["warnings"] = list(warnings)
        return json.dumps(payload, indent=2, ensure_ascii=False)

    def build(
        self,
        template_name="",
        randomize_rules="",
        randomize_rules_help=RULES_HELP_TEXT,
        seed=0,
    ):
        _ = randomize_rules_help  # UI-only helper field.

        name = str(template_name or "").strip()
        if not name:
            prompt_out = self._error_payload("Template name is required.")
            return (prompt_out, _format_run_log(["system | error | Template name is required"]))

        templates = load_visual_templates()
        template_data = templates.get(name)
        if not isinstance(template_data, dict):
            prompt_out = self._error_payload("Selected template was not found.", template_name=name)
            return (prompt_out, _format_run_log([f"system | error | Selected template not found: {name}"]))

        tree = template_data.get("tree")
        if not isinstance(tree, dict):
            prompt_out = self._error_payload("Selected template has no valid tree payload.", template_name=name)
            return (prompt_out, _format_run_log([f"system | error | Selected template has no valid tree payload: {name}"]))

        tree_copy = copy.deepcopy(tree)

        try:
            seed_val = int(seed)
        except Exception:
            seed_val = 0

        rng = random.Random(seed_val) if seed_val > 0 else random.Random()

        preset_by_path, preset_by_leaf = _build_preset_maps(load_visual_presets())
        warnings, run_logs = _apply_randomize_rules(tree_copy, randomize_rules, rng, preset_by_path, preset_by_leaf)

        compiled = _compile_tree_node(tree_copy)
        prompt = compiled if isinstance(compiled, dict) else {}

        if warnings:
            print(f"[AFJTemplateRandomizer] Warnings ({name}):")
            for w in warnings:
                print(f"  - {w}")

        return (json.dumps(prompt, indent=2, ensure_ascii=False), _format_run_log(run_logs))


class AFJPromptTemplateImporterNode:
    CATEGORY = "AFJ"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("template_payload_json",)
    FUNCTION = "build"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "template_name": (
                    "STRING",
                    {
                        "multiline": False,
                        "default": "",
                    },
                ),
                "source_prompt_json": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "{}",
                    },
                ),
                "import_report": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "Paste final prompt JSON and use Open Prompt Template Importer UI for convert/preview/save.",
                    },
                ),
            },
        }

    def build(self, template_name="", source_prompt_json="", import_report=""):
        _ = template_name
        _ = import_report

        result = convert_prompt_json_text_to_template(source_prompt_json)
        if not result.get("ok"):
            payload = {
                "error": result.get("error") or "Conversion failed.",
                "report": result.get("report") or "",
                "warnings": result.get("warnings") or [],
            }
            return (json.dumps(payload, indent=2, ensure_ascii=False),)

        out = result.get("data")
        if not isinstance(out, dict):
            out = {"tree": {}, "randomizer_checked": []}
        return (json.dumps(out, indent=2, ensure_ascii=False),)
