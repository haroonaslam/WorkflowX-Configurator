import copy
import importlib
import json
import pathlib
import shutil
import sys
import tempfile

from test_unified_autoprompter import ROOT, _load_package_modules


def _modules():
    _load_package_modules()
    store = importlib.import_module(
        "workflowx_unified_autoprompter_test.jsonx_profile.reference_store"
    )
    engine = importlib.import_module(
        "workflowx_unified_autoprompter_test.jsonx_profile.engine"
    )
    routes = importlib.import_module(
        "workflowx_unified_autoprompter_test.jsonx_profile.routes"
    )
    store.REFERENCE_ROOT = ROOT / "unified_autoprompter" / "reference"
    store.ORIGINAL_ROOT = store.REFERENCE_ROOT / "original" / "JsonX"
    store.CURRENT_ROOT = store.REFERENCE_ROOT / "current_use" / "JsonX"
    return store, engine, routes


def _payload(routes, **overrides):
    body = {
        "target_model": "jsonx",
        "generation_type": "text_to_image",
        "output_format": "json",
        "generation_profile": "adaptive",
        "generation_mode": "fast",
        "preset_context_mode": "optimized",
        "detail_level": "deep",
        "template_use_presets": False,
        "enable_framing_and_placement": False,
        "nsfw_enabled": False,
        "fields": {"prompt_text": "A detailed portrait.", "detail": "high"},
        "images_b64": [],
    }
    body.update(overrides)
    return routes._request_payload(body)


def test_jsonx_original_and_current_are_complete_exact_independent_trees():
    store, _engine, _routes = _modules()
    original = store.original_bundle()
    current = store.current_bundle()
    assert original == current
    assert original["jsonx_reference_schema_version"] == 1
    assert set(original["manifest"]["file_map"]) == set(store.REQUIRED_FILE_KEYS)
    assert len(original["files"]) == len(store.REQUIRED_FILE_KEYS)
    assert all(text.strip() for text in original["files"].values())
    assert "{{SCHEMA_PATHS}}" in store.block("jsonx", "template_adaptive_ranked", original)[1]
    assert "{{PRESET_CATALOG}}" in store.block("jsonx", "template_adaptive_full", original)[1]
    assert store.presets("jsonx", original)
    assert store.block("jsonx", "presets_full", original)[1].encode("utf-8") == (
        ROOT / "unified_autoprompter" / "jsonx_profile" / "presets.json"
    ).read_bytes()


def test_jsonx_preview_contracts_are_last_and_stage_two_receives_no_presets():
    store, engine, routes = _modules()
    for generation_profile, context_mode, use_presets in (
        ("adaptive", "optimized", False),
        ("adaptive", "full", False),
        ("template_fill", "optimized", False),
        ("template_fill", "optimized", True),
    ):
        data = _payload(
            routes,
            generation_profile=generation_profile,
            preset_context_mode=context_mode,
            template_use_presets=use_presets,
            generation_mode="refined",
        )
        preview = engine.effective_instruction_preview(data)
        stage_one_contract = store.block("jsonx", "contract_stage_one_json")[1]
        assert preview["stage_one"].endswith(stage_one_contract)
        assert preview["refinement"].endswith(
            store.block("jsonx", "contract_stage_two_json")[1]
        )
        preset_text = store.preset_text("jsonx")
        assert preset_text not in preview["refinement"]
        assert "presets/full-presets.md" not in "\n".join(
            preview["activated_files"]["stage_two"]
        )


def test_jsonx_four_image_states_keep_authoring_media_and_select_one_reference_file():
    _store, engine, routes = _modules()
    cases = (
        ("image_to_image", ["image"], "reference_with_supported"),
        ("image_to_image", [], "reference_without_supported"),
        ("text_to_image", ["image"], "reference_without_unsupported"),
        ("text_to_image", [], "reference_without_unsupported"),
    )
    for generation_type, images, semantic in cases:
        data = _payload(routes, generation_type=generation_type, images_b64=images)
        preview = engine.effective_instruction_preview(data)
        assert data["images_b64"] == images
        expected = f"profiles/jsonx/{data['_jsonx_reference_bundle']['manifest']['file_map'][semantic]}"
        selected = [path for path in preview["activated_files"]["stage_one"] if "/references/" in path]
        assert selected == [expected]


def test_jsonx_negative_output_collects_the_authoritative_plural_branch_deterministically():
    _store, engine, routes = _modules()
    stage_one = {
        "scene": {"environment": "studio"},
        "negative_prompts": {
            "quality": "blur",
            "nested": ["artifacts", "blur", ""],
        },
    }
    assert routes._negative_text(stage_one) == "blur\nartifacts"
    prose = engine.natural_prompt_from_validated_jsonx(stage_one)
    assert "## Avoid\nAvoid blur. artifacts. blur." in prose


def test_jsonx_save_reset_and_standard_store_operations_preserve_each_other():
    standard_package = "workflowx_unified_autoprompter_test"
    store, _engine, _routes = _modules()
    standard_store = importlib.import_module(f"{standard_package}.reference_store")
    with tempfile.TemporaryDirectory() as temporary:
        reference = pathlib.Path(temporary) / "reference"
        shutil.copytree(ROOT / "unified_autoprompter" / "reference" / "original", reference / "original")
        shutil.copytree(ROOT / "unified_autoprompter" / "reference" / "current_use", reference / "current_use")
        store.REFERENCE_ROOT = reference
        store.ORIGINAL_ROOT = reference / "original" / "JsonX"
        store.CURRENT_ROOT = reference / "current_use" / "JsonX"
        standard_store.REFERENCE_ROOT = reference
        standard_store.ORIGINAL_ROOT = reference / "original"
        standard_store.CURRENT_ROOT = reference / "current_use"

        jsonx_bundle = store.current_bundle()
        jsonx_path = "profiles/jsonx/paths/stage-one-adaptive.md"
        jsonx_bundle["files"][jsonx_path] += "\nJSONX CURRENT SENTINEL"
        store.save_current_bundle(jsonx_bundle)
        standard_store.reset_all()
        assert store.current_bundle()["files"][jsonx_path].endswith("JSONX CURRENT SENTINEL")

        standard_path = "SDXL/split/common.md"
        standard_before = standard_store.current_bundle()["files"][standard_path]
        jsonx_bundle = store.current_bundle()
        jsonx_bundle["files"][jsonx_path] += "\nSECOND SENTINEL"
        store.save_current_bundle(jsonx_bundle)
        assert standard_store.current_bundle()["files"][standard_path] == standard_before


def test_jsonx_bootstrap_adds_new_required_files_to_builtin_and_custom_without_overwriting_edits():
    store, _engine, _routes = _modules()
    with tempfile.TemporaryDirectory() as temporary:
        reference = pathlib.Path(temporary) / "reference"
        shutil.copytree(ROOT / "unified_autoprompter" / "reference" / "original", reference / "original")
        shutil.copytree(ROOT / "unified_autoprompter" / "reference" / "current_use", reference / "current_use")
        store.REFERENCE_ROOT = reference
        store.ORIGINAL_ROOT = reference / "original" / "JsonX"
        store.CURRENT_ROOT = reference / "current_use" / "JsonX"

        manifest_path = store.CURRENT_ROOT / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        builtin = manifest["profiles"][0]
        custom = copy.deepcopy(builtin)
        custom.update({"key": "jsonx_custom", "label": "JsonX Custom", "folder": "profiles/jsonx_custom", "builtin": False})
        manifest["profiles"].append(custom)
        missing_relative = manifest["file_map"].pop("contract_natural_repair")
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        builtin_root = store.CURRENT_ROOT / pathlib.PurePosixPath(builtin["folder"])
        custom_root = store.CURRENT_ROOT / pathlib.PurePosixPath(custom["folder"])
        shutil.copytree(builtin_root, custom_root)
        (builtin_root / pathlib.PurePosixPath(missing_relative)).unlink()
        (custom_root / pathlib.PurePosixPath(missing_relative)).unlink()
        sentinel_path = custom_root / "paths" / "stage-one-adaptive.md"
        sentinel_path.write_text(sentinel_path.read_text(encoding="utf-8") + "\nCUSTOM SENTINEL", encoding="utf-8")

        upgraded = store.current_bundle()
        assert upgraded["files"]["profiles/jsonx_custom/paths/stage-one-adaptive.md"].endswith("CUSTOM SENTINEL")
        assert upgraded["files"][f"profiles/jsonx/{missing_relative}"].strip()
        assert upgraded["files"][f"profiles/jsonx_custom/{missing_relative}"].strip()


def test_jsonx_duplicate_and_reset_all_round_trip_exact_profile_files():
    store, _engine, _routes = _modules()
    with tempfile.TemporaryDirectory() as temporary:
        reference = pathlib.Path(temporary) / "reference"
        shutil.copytree(ROOT / "unified_autoprompter" / "reference" / "original", reference / "original")
        shutil.copytree(ROOT / "unified_autoprompter" / "reference" / "current_use", reference / "current_use")
        store.REFERENCE_ROOT = reference
        store.ORIGINAL_ROOT = reference / "original" / "JsonX"
        store.CURRENT_ROOT = reference / "current_use" / "JsonX"

        bundle = store.current_bundle()
        source = bundle["manifest"]["profiles"][0]
        duplicate = copy.deepcopy(source)
        duplicate.update({"key": "jsonx_copy", "label": "JsonX Copy", "folder": "profiles/jsonx_copy", "builtin": False})
        bundle["manifest"]["profiles"].append(duplicate)
        source_prefix = f"{source['folder']}/"
        for path, text in list(bundle["files"].items()):
            if path.startswith(source_prefix):
                bundle["files"][f"{duplicate['folder']}/{path[len(source_prefix):]}"] = text
        custom_path = "profiles/jsonx_copy/paths/stage-one-adaptive.md"
        bundle["files"][custom_path] += "\nDUPLICATE SENTINEL"

        saved = store.save_current_bundle(bundle)
        assert saved["files"][custom_path].endswith("DUPLICATE SENTINEL")
        restored = store.reset_all()
        assert any(profile["key"] == "jsonx_copy" for profile in restored["manifest"]["profiles"])
        assert restored["files"][custom_path].endswith("DUPLICATE SENTINEL")
        assert store.original_bundle()["manifest"]["profiles"] == [source]


def test_jsonx_atomic_save_failure_restores_previous_current_tree(monkeypatch):
    store, _engine, _routes = _modules()
    with tempfile.TemporaryDirectory() as temporary:
        reference = pathlib.Path(temporary) / "reference"
        shutil.copytree(ROOT / "unified_autoprompter" / "reference" / "original", reference / "original")
        shutil.copytree(ROOT / "unified_autoprompter" / "reference" / "current_use", reference / "current_use")
        store.REFERENCE_ROOT = reference
        store.ORIGINAL_ROOT = reference / "original" / "JsonX"
        store.CURRENT_ROOT = reference / "current_use" / "JsonX"
        before = store.current_bundle()
        changed = copy.deepcopy(before)
        path = "profiles/jsonx/paths/stage-one-adaptive.md"
        changed["files"][path] += "\nSHOULD ROLL BACK"
        real_replace = store.os.replace

        def fail_stage_install(source, destination):
            if ".JsonX.stage-" in str(source) and pathlib.Path(destination) == store.CURRENT_ROOT:
                raise OSError("simulated atomic install failure")
            return real_replace(source, destination)

        monkeypatch.setattr(store.os, "replace", fail_stage_install)
        try:
            store.save_current_bundle(changed)
        except OSError as error:
            assert "simulated atomic install failure" in str(error)
        else:
            raise AssertionError("The simulated atomic install failure must propagate.")
        assert store.current_bundle() == before


def test_jsonx_invalid_templates_presets_and_paths_are_rejected_before_write():
    store, _engine, _routes = _modules()
    bundle = store.current_bundle()
    profile = bundle["manifest"]["profiles"][0]
    prefix = profile["folder"]

    invalid_template = copy.deepcopy(bundle)
    path = f"{prefix}/{bundle['manifest']['file_map']['template_adaptive_ranked']}"
    invalid_template["files"][path] = "{{SCHEMA_PATHS}}"
    try:
        store.validate_bundle(invalid_template)
    except ValueError as error:
        assert "requires exactly these tokens" in str(error)
    else:
        raise AssertionError("Missing ranked template tokens must be rejected.")

    invalid_presets = copy.deepcopy(bundle)
    preset_path = f"{prefix}/{bundle['manifest']['file_map']['presets_full']}"
    invalid_presets["files"][preset_path] = '{"subject":{"a":{"same":"one"},"b":{"same":"two"}}}'
    try:
        store.validate_bundle(invalid_presets)
    except ValueError as error:
        assert "conflicts between" in str(error)
    else:
        raise AssertionError("Conflicting preset IDs must be rejected.")

    traversal = copy.deepcopy(bundle)
    traversal["files"]["../outside.md"] = "bad"
    try:
        store.validate_bundle(traversal)
    except ValueError as error:
        assert "Unsafe JsonX reference path" in str(error)
    else:
        raise AssertionError("Traversal must be rejected.")


def test_jsonx_frontend_uses_private_markdown_editor_and_reference_handshake():
    source = (ROOT / "web" / "js" / "unified_autoprompter.js").read_text(encoding="utf-8")
    assert "const JSONX_REFERENCE_SCHEMA_VERSION = 1" in source
    assert "openJsonXMarkdownProfileSettings" in source
    assert "Path Settings" in source
    assert "Adaptive ranked context" in source
    assert "Complete JsonX preset catalog" in source
    assert "reference/current_use/JsonX" in source
    assert "jsonx_reference_schema_version:JSONX_REFERENCE_SCHEMA_VERSION" in source
    assert 'openMarkdownProfileSettings("jsonx", peer.key)' in source
    assert 'openMarkdownProfileSettings("standard", peer.key)' in source
    assert 'profiles.filter((profile) => profile.engine === "jsonx")' in source
    assert 'profiles.filter((profile) => profile.engine !== "jsonx")' in source
    assert "openModelSettingsModalV6" not in source
    assert "stage_one_instructions" not in source


def test_jsonx_runtime_has_no_legacy_preset_or_cross_engine_prompt_imports():
    root = ROOT / "unified_autoprompter" / "jsonx_profile"
    engine = (root / "engine.py").read_text(encoding="utf-8")
    store = (root / "reference_store.py").read_text(encoding="utf-8")
    assert "PRESETS_PATH" not in engine
    assert "DEFAULT_STAGE_ONE_INSTRUCTIONS" not in engine
    assert "jsonx_llm" not in engine + store
    assert "from ..reference_store" not in store
    assert "jsonx_profile/presets.json" not in engine
