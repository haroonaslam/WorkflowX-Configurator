import copy
import json
import os


_INVALID_TEMPLATE_CHARS = set('<>:"/\\|?*')
_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


def _base_dir():
    return os.path.dirname(__file__)


def _presets_path():
    return os.path.join(_base_dir(), "presets.json")


def _templates_dir():
    return os.path.join(_base_dir(), "templates")


def _ensure_templates_dir():
    path = _templates_dir()
    os.makedirs(path, exist_ok=True)
    return path


def _template_name_error(name):
    raw = str(name or "")
    if not raw.strip():
        return "Template name is required."

    if raw != raw.strip():
        return "Template name cannot start or end with whitespace."

    if raw in {".", ".."}:
        return "Template name cannot be '.' or '..'."

    if raw.endswith(".") or raw.endswith(" "):
        return "Template name cannot end with '.' or space."

    if any(ord(ch) < 32 for ch in raw):
        return "Template name contains control characters."

    bad = sorted({ch for ch in raw if ch in _INVALID_TEMPLATE_CHARS})
    if bad:
        return f"Template name contains invalid characters: {' '.join(bad)}"

    root_name = raw.split(".")[0].upper()
    if root_name in _RESERVED_NAMES:
        return f"Template name '{raw}' uses a reserved Windows filename."

    return None


def _template_file_path(name):
    err = _template_name_error(name)
    if err:
        return None, err

    folder = _ensure_templates_dir()
    path = os.path.normpath(os.path.join(folder, f"{name}.json"))
    folder_norm = os.path.normpath(folder)
    if not path.startswith(folder_norm):
        return None, "Template name resolves outside templates directory."
    return path, None


def _is_leaf_options(node):
    if not isinstance(node, dict) or not node:
        return False
    return all(isinstance(v, str) for v in node.values())


def _new_id_factory():
    state = {"i": 0}

    def _next(prefix="node"):
        state["i"] += 1
        return f"{prefix}_{state['i']}"

    return _next


def _field_node(next_id, key, label=None, value="", options=None, preset_path=""):
    out = {
        "id": next_id("field"),
        "node_type": "field",
        "key": str(key or ""),
        "label": str(label or key or ""),
        "value": str(value or ""),
        "expanded": False,
    }
    if isinstance(options, dict) and options:
        out["options"] = copy.deepcopy(options)
        out["preset_path"] = preset_path
        out["origin_preset_path"] = preset_path
    return out


def _group_node(next_id, key, label=None, children=None, expanded=False, preset_path=""):
    out = {
        "id": next_id("group"),
        "node_type": "group",
        "key": str(key or ""),
        "label": str(label or key or ""),
        "expanded": bool(expanded),
        "children": list(children or []),
    }
    if preset_path:
        out["origin_preset_path"] = preset_path
    return out


def _array_node(next_id, key, label=None, item_template=None, items=None, expanded=False, preset_path="", item_preset_path=""):
    out = {
        "id": next_id("array"),
        "node_type": "array",
        "key": str(key or ""),
        "label": str(label or key or ""),
        "expanded": bool(expanded),
        "item_template": item_template,
        "items": list(items or []),
    }
    if preset_path:
        out["origin_preset_path"] = preset_path
    if item_preset_path:
        out["item_preset_path"] = item_preset_path
    return out


def _clone_with_fresh_ids(node, next_id):
    cloned = copy.deepcopy(node)

    def walk(cur):
        if not isinstance(cur, dict):
            return
        cur["id"] = next_id(str(cur.get("node_type") or "node"))
        for child in cur.get("children") or []:
            walk(child)
        for item in cur.get("items") or []:
            walk(item)
        if isinstance(cur.get("item_template"), dict):
            walk(cur["item_template"])

    walk(cloned)
    return cloned


def _build_nodes_from_preset_object(next_id, key, value, preset_path):
    if _is_leaf_options(value):
        return _field_node(next_id, key, key, "", options=value, preset_path=preset_path)

    if isinstance(value, dict):
        children = []
        for child_key, child_val in value.items():
            child_path = f"{preset_path}.{child_key}" if preset_path else child_key
            children.append(_build_nodes_from_preset_object(next_id, child_key, child_val, child_path))
        return _group_node(next_id, key, key, children=children, expanded=False, preset_path=preset_path)

    return _field_node(next_id, key, key, "")


def _build_subject_item_template(next_id, subject_preset):
    identity = _build_nodes_from_preset_object(next_id, "identity", subject_preset.get("identity") or {}, "subject.identity")
    dress = _build_nodes_from_preset_object(next_id, "dress", subject_preset.get("dress") or {}, "subject.dress")
    pose = _build_nodes_from_preset_object(next_id, "pose", subject_preset.get("pose") or {}, "subject.pose")
    properties = _build_nodes_from_preset_object(next_id, "properties", subject_preset.get("properties") or {}, "subject.properties")

    common = _group_node(
        next_id,
        "common",
        "common",
        children=[
            _field_node(next_id, "id", "id", ""),
            _field_node(next_id, "name", "name", ""),
        ],
        expanded=False,
    )

    return _group_node(
        next_id,
        "subject",
        "subject",
        children=[common, identity, dress, pose, properties],
        expanded=False,
        preset_path="subject",
    )


def _build_starter_tree(next_id, presets):
    subject_preset = presets.get("subject") if isinstance(presets.get("subject"), dict) else {}
    subject_template = _build_subject_item_template(next_id, subject_preset)
    first_subject = _clone_with_fresh_ids(subject_template, next_id)

    children = [
        _build_nodes_from_preset_object(next_id, "scene", presets.get("scene") or {}, "scene"),
        _array_node(
            next_id,
            "subjects",
            "subjects",
            item_template=subject_template,
            items=[first_subject],
            expanded=False,
            preset_path="subjects",
            item_preset_path="subject",
        ),
        _group_node(next_id, "interactions", "interactions", children=[], expanded=False),
        _build_nodes_from_preset_object(next_id, "style", presets.get("style") or {}, "style"),
        _build_nodes_from_preset_object(next_id, "lighting", presets.get("lighting") or {}, "lighting"),
        _build_nodes_from_preset_object(next_id, "camera", presets.get("camera") or {}, "camera"),
        _build_nodes_from_preset_object(next_id, "mood", presets.get("mood") or {}, "mood"),
        _build_nodes_from_preset_object(next_id, "quality", presets.get("quality") or {}, "quality"),
        _group_node(next_id, "negative", "negative", children=[_field_node(next_id, "text", "text", "")], expanded=False),
    ]
    return _group_node(next_id, "prompt", "prompt", children=children, expanded=True)


def _flatten_preset_leaves(node, prefix="", out=None):
    if out is None:
        out = {}

    if not isinstance(node, dict):
        return out

    if _is_leaf_options(node):
        out[prefix] = copy.deepcopy(node)
        return out

    for key, val in node.items():
        next_prefix = f"{prefix}.{key}" if prefix else key
        _flatten_preset_leaves(val, next_prefix, out)
    return out


def _find_group_child(group_node, key):
    for child in group_node.get("children") or []:
        if str(child.get("key") or "") == key:
            return child
    return None


def _format_field_value(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _clear_values(node):
    if not isinstance(node, dict):
        return
    node_type = node.get("node_type")
    if node_type == "field":
        node["value"] = ""
        return
    for child in node.get("children") or []:
        _clear_values(child)
    for item in node.get("items") or []:
        _clear_values(item)
    if isinstance(node.get("item_template"), dict):
        _clear_values(node["item_template"])


def _attach_field_options_if_match(field_node, canonical_path, preset_leaf_map):
    if field_node.get("node_type") != "field":
        return
    if isinstance(field_node.get("options"), dict) and field_node.get("options"):
        return
    options = preset_leaf_map.get(canonical_path)
    if isinstance(options, dict) and options:
        field_node["options"] = copy.deepcopy(options)
        field_node["preset_path"] = canonical_path
        if not field_node.get("origin_preset_path"):
            field_node["origin_preset_path"] = canonical_path


def _build_item_template_from_node(node, next_id):
    template = _clone_with_fresh_ids(node, next_id)
    _clear_values(template)
    return template


def _new_custom_value_item(next_id, canonical_item_path, preset_leaf_map):
    options = preset_leaf_map.get(f"{canonical_item_path}.value")
    value_field = _field_node(next_id, "value", "value", "", options=options, preset_path=f"{canonical_item_path}.value")
    return _group_node(next_id, "item", "item", children=[value_field], expanded=False, preset_path=canonical_item_path)


def _record_created_field(stats, has_options):
    if has_options:
        stats["created_preset_fields"] += 1
    else:
        stats["created_custom_fields"] += 1


def _make_node_from_value(next_id, key, value, canonical_path, preset_leaf_map, stats):
    if isinstance(value, list):
        item_path = canonical_path[:-1] if canonical_path.endswith("s") else f"{canonical_path}_item"
        items = []
        for item_val in value:
            if isinstance(item_val, dict):
                items.append(_make_node_from_value(next_id, "item", item_val, item_path, preset_leaf_map, stats))
            elif isinstance(item_val, list):
                items.append(_make_node_from_value(next_id, "item", item_val, item_path, preset_leaf_map, stats))
            else:
                item = _new_custom_value_item(next_id, item_path, preset_leaf_map)
                _apply_primitive_to_item(next_id, item, item_val, item_path, preset_leaf_map, stats)
                items.append(item)

        if items:
            item_template = _build_item_template_from_node(items[0], next_id)
        else:
            item_template = _new_custom_value_item(next_id, item_path, preset_leaf_map)
            _clear_values(item_template)

        return _array_node(
            next_id,
            key,
            key,
            item_template=item_template,
            items=items,
            expanded=False,
            preset_path=canonical_path,
            item_preset_path=item_path,
        )

    if isinstance(value, dict):
        group = _group_node(next_id, key, key, children=[], expanded=False, preset_path=canonical_path)
        _apply_prompt_object_to_group(next_id, group, value, canonical_path, preset_leaf_map, stats)
        return group

    options = preset_leaf_map.get(canonical_path)
    _record_created_field(stats, bool(options))
    return _field_node(
        next_id,
        key,
        key,
        _format_field_value(value),
        options=options,
        preset_path=canonical_path if options else "",
    )


def _apply_primitive_to_item(next_id, item_node, value, canonical_item_path, preset_leaf_map, stats):
    if not isinstance(item_node, dict):
        return

    if item_node.get("node_type") == "field":
        _attach_field_options_if_match(item_node, canonical_item_path, preset_leaf_map)
        item_node["value"] = _format_field_value(value)
        return

    if item_node.get("node_type") == "group":
        value_node = _find_group_child(item_node, "value")
        if value_node is None:
            options = preset_leaf_map.get(f"{canonical_item_path}.value")
            value_node = _field_node(
                next_id,
                "value",
                "value",
                "",
                options=options,
                preset_path=f"{canonical_item_path}.value" if options else "",
            )
            _record_created_field(stats, bool(options))
            item_node.setdefault("children", []).append(value_node)
        _attach_field_options_if_match(value_node, f"{canonical_item_path}.value", preset_leaf_map)
        value_node["value"] = _format_field_value(value)


def _apply_value_to_node(next_id, node, value, canonical_path, preset_leaf_map, stats):
    if not isinstance(node, dict):
        return

    node_type = node.get("node_type")
    if node_type == "field":
        _attach_field_options_if_match(node, canonical_path, preset_leaf_map)
        node["value"] = _format_field_value(value)
        return

    if node_type == "group":
        if isinstance(value, dict):
            _apply_prompt_object_to_group(next_id, node, value, canonical_path, preset_leaf_map, stats)
        return

    if node_type != "array":
        return
    if not isinstance(value, list):
        return

    node["items"] = []
    item_path = str(
        node.get("item_preset_path")
        or (node.get("item_template") or {}).get("origin_preset_path")
        or (canonical_path[:-1] if canonical_path.endswith("s") else f"{canonical_path}_item")
    )
    for item_val in value:
        if isinstance(node.get("item_template"), dict):
            item_node = _clone_with_fresh_ids(node["item_template"], next_id)
        else:
            item_node = _new_custom_value_item(next_id, item_path, preset_leaf_map)
            _clear_values(item_node)

        if isinstance(item_val, dict) or isinstance(item_val, list):
            _apply_value_to_node(next_id, item_node, item_val, item_path, preset_leaf_map, stats)
        else:
            _apply_primitive_to_item(next_id, item_node, item_val, item_path, preset_leaf_map, stats)

        node["items"].append(item_node)


def _apply_prompt_object_to_group(next_id, group, obj, canonical_path, preset_leaf_map, stats):
    if not isinstance(obj, dict):
        return

    original_children = list(group.get("children") or [])
    selected = []

    for key, value in obj.items():
        key_str = str(key)
        child_path = f"{canonical_path}.{key_str}" if canonical_path else key_str
        child = _find_group_child(group, key_str)
        if child is None:
            child = _make_node_from_value(next_id, key_str, value, child_path, preset_leaf_map, stats)
            group.setdefault("children", []).append(child)
        else:
            _apply_value_to_node(next_id, child, value, child_path, preset_leaf_map, stats)
        selected.append(child)

    if selected:
        selected_ids = {id(x) for x in selected}
        remainder = [x for x in original_children if id(x) not in selected_ids]
        group["children"] = selected + remainder


def _count_tree_fields(tree):
    total = 0
    non_empty = 0
    preset_bound = 0
    custom = 0

    def walk(node):
        nonlocal total, non_empty, preset_bound, custom
        if not isinstance(node, dict):
            return

        node_type = node.get("node_type")
        if node_type == "field":
            total += 1
            value = str(node.get("value") or "").strip()
            if value:
                non_empty += 1
                if isinstance(node.get("options"), dict) and node.get("options"):
                    preset_bound += 1
                else:
                    custom += 1
            return

        for child in node.get("children") or []:
            walk(child)
        for item in node.get("items") or []:
            walk(item)
        if isinstance(node.get("item_template"), dict):
            walk(node["item_template"])

    walk(tree)
    return {
        "total_fields": total,
        "non_empty_fields": non_empty,
        "non_empty_preset_fields": preset_bound,
        "non_empty_custom_fields": custom,
    }


def _looks_like_afj_template_payload(obj):
    if not isinstance(obj, dict):
        return False
    if "tree" in obj and isinstance(obj.get("tree"), dict):
        return True
    if "randomizer_checked" in obj:
        return True
    return False


def load_visual_presets():
    try:
        with open(_presets_path(), "r", encoding="utf-8-sig") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"[AFJ] WARNING: Failed to load presets: {e}")
        return {}


def _tree_contains_options(node):
    if isinstance(node, dict):
        if "options" in node:
            return True
        for val in node.values():
            if _tree_contains_options(val):
                return True
        return False
    if isinstance(node, list):
        return any(_tree_contains_options(x) for x in node)
    return False


def _strip_options_from_tree(node):
    if isinstance(node, dict):
        node.pop("options", None)
        for val in node.values():
            _strip_options_from_tree(val)
        return
    if isinstance(node, list):
        for item in node:
            _strip_options_from_tree(item)


def _normalize_template_data(data, reject_embedded_options=True):
    if not isinstance(data, dict):
        return None, "Template data must be an object."

    tree = data.get("tree")
    if not isinstance(tree, dict):
        return None, "Template data must include a tree object."

    checked = data.get("randomizer_checked")
    if checked is None:
        checked = []
    if not isinstance(checked, list):
        return None, "randomizer_checked must be an array when provided."

    tree_copy = copy.deepcopy(tree)
    if reject_embedded_options and _tree_contains_options(tree_copy):
        return None, "Legacy templates with embedded options are not supported. Recreate or re-import the template."

    return {
        "tree": tree_copy,
        "randomizer_checked": list(checked),
    }, None


def load_visual_templates():
    folder = _ensure_templates_dir()
    out = {}

    for filename in sorted(os.listdir(folder)):
        if not filename.lower().endswith(".json"):
            continue
        path = os.path.join(folder, filename)
        if not os.path.isfile(path):
            continue

        name = filename[:-5]
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[AFJ] WARNING: Failed to load template '{filename}': {e}")
            continue

        norm, err = _normalize_template_data(data, reject_embedded_options=True)
        if norm is None:
            print(f"[AFJ] WARNING: Ignoring template file '{filename}': {err}")
            continue
        out[name] = norm

    return out


def save_visual_template(name, data):
    path, err = _template_file_path(name)
    if err:
        raise ValueError(err)

    norm, err = _normalize_template_data(data, reject_embedded_options=False)
    if norm is None:
        raise ValueError(err or "Template data must include a valid tree object and optional randomizer_checked array.")

    # Template files are structure+values+metadata only; option catalogs stay dynamic via presets.json.
    _strip_options_from_tree(norm["tree"])

    with open(path, "w", encoding="utf-8") as f:
        json.dump(norm, f, indent=2, ensure_ascii=False)


def delete_visual_template(name):
    path, err = _template_file_path(name)
    if err:
        raise ValueError(err)
    if os.path.exists(path):
        os.remove(path)


def convert_prompt_object_to_template(prompt_obj):
    if not isinstance(prompt_obj, dict):
        return {
            "ok": False,
            "error": "Prompt payload must be a JSON object.",
            "report": "Conversion failed: payload is not a JSON object.",
            "warnings": [],
        }

    if _looks_like_afj_template_payload(prompt_obj):
        return {
            "ok": False,
            "error": "Use final prompt JSON only, not AFJ metadata/template payload.",
            "report": "Conversion failed: detected AFJ metadata payload (tree/randomizer_checked).",
            "warnings": [],
        }

    presets = load_visual_presets()
    next_id = _new_id_factory()
    root = _group_node(next_id, "prompt", "prompt", children=[], expanded=True)
    preset_leaf_map = _flatten_preset_leaves(presets)

    stats = {
        "created_preset_fields": 0,
        "created_custom_fields": 0,
    }
    _apply_prompt_object_to_group(next_id, root, prompt_obj, "", preset_leaf_map, stats)
    counts = _count_tree_fields(root)

    report_lines = [
        "Conversion completed.",
        f"Non-empty fields: {counts['non_empty_fields']}",
        f"Preset-backed non-empty fields: {counts['non_empty_preset_fields']}",
        f"Custom non-empty fields: {counts['non_empty_custom_fields']}",
        f"Created new preset-backed fields: {stats['created_preset_fields']}",
        f"Created new custom fields: {stats['created_custom_fields']}",
    ]

    stored_tree = copy.deepcopy(root)
    _strip_options_from_tree(stored_tree)

    return {
        "ok": True,
        "error": "",
        "report": "\n".join(report_lines),
        "warnings": [],
        "summary": counts,
        "data": {
            "tree": stored_tree,
            "randomizer_checked": [],
        },
    }


def convert_prompt_json_text_to_template(source_prompt_json):
    text = str(source_prompt_json or "").strip()
    if not text:
        return {
            "ok": False,
            "error": "Prompt JSON is required.",
            "report": "Conversion failed: prompt JSON input is empty.",
            "warnings": [],
        }

    try:
        prompt_obj = json.loads(text)
    except Exception as e:
        return {
            "ok": False,
            "error": f"Invalid JSON: {e}",
            "report": f"Conversion failed: invalid JSON ({e}).",
            "warnings": [],
        }

    return convert_prompt_object_to_template(prompt_obj)


def validate_prompt_payload(payload):
    errors = []
    warnings = []

    prompt = payload
    if isinstance(payload, dict) and "prompt" in payload and isinstance(payload.get("prompt"), dict):
        # Backward-compatible fallback for older wrapper payloads.
        prompt = payload["prompt"]

    if not isinstance(prompt, dict):
        return {
            "ok": False,
            "errors": [{"code": "invalid_payload", "message": "Prompt payload must be an object."}],
            "warnings": [],
        }

    subjects = prompt.get("subjects")
    if subjects is not None and not isinstance(subjects, list):
        errors.append({"code": "subjects_not_array", "path": "subjects", "message": "subjects must be an array when present."})

    if isinstance(subjects, list):
        seen = set()
        for i, subject in enumerate(subjects):
            if not isinstance(subject, dict):
                errors.append({"code": "subject_not_object", "path": f"subjects[{i}]", "message": "Each subject must be an object."})
                continue
            sid = str(subject.get("id", "")).strip()
            if sid:
                if sid in seen:
                    warnings.append(
                        {
                            "code": "duplicate_subject_id",
                            "path": f"subjects[{i}].id",
                            "message": f"Duplicate subject id '{sid}'.",
                        }
                    )
                seen.add(sid)

    interactions = prompt.get("interactions")
    if interactions is not None and not isinstance(interactions, dict):
        warnings.append(
            {
                "code": "interactions_not_object",
                "path": "interactions",
                "message": "interactions is expected to be an object group in v4.",
            }
        )

    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings}


def register_visual_builder_routes(app):
    from aiohttp import web

    route_paths = {r.resource.canonical for r in app.router.routes()}

    async def presets_handler(request):
        return web.json_response(load_visual_presets())

    async def templates_handler(request):
        return web.json_response(load_visual_templates())

    async def save_template_handler(request):
        body = await request.json()
        name = str(body.get("name") or "")
        data = body.get("data")

        if not name.strip():
            return web.json_response({"ok": False, "error": "Template name is required."}, status=400)
        if not isinstance(data, dict):
            return web.json_response({"ok": False, "error": "Template data must be an object."}, status=400)

        try:
            save_visual_template(name, data)
        except ValueError as e:
            return web.json_response({"ok": False, "error": str(e)}, status=400)
        except Exception as e:
            return web.json_response({"ok": False, "error": f"Failed to save template: {e}"}, status=500)

        return web.json_response({"ok": True, "name": name})

    async def delete_template_handler(request):
        body = await request.json()
        name = str(body.get("name") or "")
        if not name.strip():
            return web.json_response({"ok": False, "error": "Template name is required."}, status=400)

        try:
            delete_visual_template(name)
        except ValueError as e:
            return web.json_response({"ok": False, "error": str(e)}, status=400)
        except Exception as e:
            return web.json_response({"ok": False, "error": f"Failed to delete template: {e}"}, status=500)
        return web.json_response({"ok": True, "name": name})

    async def validate_handler(request):
        body = await request.json()
        return web.json_response(validate_prompt_payload(body))

    async def import_convert_handler(request):
        body = await request.json()
        source_prompt_json = body.get("source_prompt_json")
        prompt_obj = body.get("prompt")

        if isinstance(source_prompt_json, str):
            result = convert_prompt_json_text_to_template(source_prompt_json)
        elif isinstance(prompt_obj, dict):
            result = convert_prompt_object_to_template(prompt_obj)
        else:
            result = {
                "ok": False,
                "error": "source_prompt_json (string) is required.",
                "report": "Conversion failed: missing source_prompt_json string.",
                "warnings": [],
            }
        return web.json_response(result)

    if "/fluxvisual/presets" not in route_paths:
        app.router.add_get("/fluxvisual/presets", presets_handler)
    if "/fluxvisual/templates" not in route_paths:
        app.router.add_get("/fluxvisual/templates", templates_handler)
    if "/fluxvisual/templates/save" not in route_paths:
        app.router.add_post("/fluxvisual/templates/save", save_template_handler)
    if "/fluxvisual/templates/delete" not in route_paths:
        app.router.add_post("/fluxvisual/templates/delete", delete_template_handler)
    if "/fluxvisual/validate" not in route_paths:
        app.router.add_post("/fluxvisual/validate", validate_handler)
    if "/fluxvisual/import/convert" not in route_paths:
        app.router.add_post("/fluxvisual/import/convert", import_convert_handler)

    print("[AFJ] Registered /fluxvisual API routes.")
