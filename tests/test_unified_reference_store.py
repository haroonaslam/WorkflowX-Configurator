import copy
import importlib.util
import pathlib
import shutil
import sys
import tempfile
import types


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load_module(relative_path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = module_name.rsplit(".", 1)[0]
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _modules():
    package_name = "workflowx_unified_reference_test"
    package = types.ModuleType(package_name)
    package.__path__ = [str(ROOT / "unified_autoprompter")]
    sys.modules[package_name] = package
    profiles = _load_module("unified_autoprompter/profiles.py", f"{package_name}.profiles")
    _load_module("unified_autoprompter/profile_config.py", f"{package_name}.profile_config")
    store = _load_module("unified_autoprompter/reference_store.py", f"{package_name}.reference_store")
    builder = _load_module("unified_autoprompter/prompt_builder.py", f"{package_name}.prompt_builder")
    return profiles, store, builder


def _selected_paths(bundle, profile, generation_type, prompt_format, negative, nsfw, media_count):
    manifest = bundle["manifest"]
    folder = profile["folder"]
    paths = [f"{folder}/split/common.md"]
    generation = manifest["generation_types"][generation_type]
    paths.append(f"{folder}/split/{generation['filename']}")
    if nsfw:
        paths.append(manifest["nsfw_files"][generation["output_medium"]])
    if generation["reference_supported"]:
        reference_file = "with_reference_supported.md" if media_count else "without_reference_supported.md"
    else:
        reference_file = "without_reference_unsupported.md"
    paths.append(f"{folder}/Supporting/{reference_file}")
    prefix = manifest["formats"][prompt_format]["contract_prefix"]
    suffix = "with_negative" if negative else "without_negative"
    paths.append(f"{folder}/Supporting/{prefix}_{suffix}.md")
    return paths


def test_markdown_payload_is_exact_selected_file_join_for_every_enabled_combination():
    _profiles, store, builder = _modules()
    bundle = store.current_bundle()
    checked = 0
    for profile in bundle["manifest"]["profiles"]:
        for generation_type in profile["enabled_generation_types"]:
            for prompt_format in profile["enabled_formats"]:
                negative_states = (False, True) if profile["negative_supported"] else (False,)
                for negative in negative_states:
                    for nsfw in (False, True):
                        for media_count in (0, 1):
                            prompt, activated = builder.assemble_system_prompt(
                                profile["key"],
                                prompt_format,
                                negative,
                                reference_count=media_count,
                                generation_type=generation_type,
                                nsfw_enabled=nsfw,
                            )
                            paths = _selected_paths(
                                bundle, profile, generation_type, prompt_format, negative, nsfw, media_count
                            )
                            paths = [path for path in paths if bundle["files"].get(path, "").strip()]
                            assert prompt == "\n\n".join(bundle["files"][path] for path in paths)
                            assert [item["path"] for item in activated] == paths
                            assert all(set(item) == {"kind", "path"} for item in activated)
                            checked += 1
    assert checked > 200


def test_reference_store_save_reset_and_bootstrap_never_write_original():
    _profiles, store, _builder = _modules()
    with tempfile.TemporaryDirectory() as temporary:
        root = pathlib.Path(temporary) / "reference"
        original = root / "original"
        current = root / "current_use"
        shutil.copytree(ROOT / "unified_autoprompter" / "reference" / "original", original)
        shutil.copytree(original, current)
        store.REFERENCE_ROOT = root
        store.ORIGINAL_ROOT = original
        store.CURRENT_ROOT = current
        original_before = {path.relative_to(original): path.read_bytes() for path in original.rglob("*") if path.is_file()}

        bundle = store.current_bundle()
        common = "SDXL/split/common.md"
        bundle["files"][common] = bundle["files"][common] + "\nmanual current-use edit"
        store.save_current_bundle(bundle)
        assert store.current_bundle()["files"][common].endswith("manual current-use edit")
        assert {path.relative_to(original): path.read_bytes() for path in original.rglob("*") if path.is_file()} == original_before

        missing = current / "WAN 2.2" / "split" / "video-to-video.md"
        missing.unlink()
        store.bootstrap_current_use()
        assert missing.exists()
        assert store.current_bundle()["files"][common].endswith("manual current-use edit")

        store.reset_profile("sdxl")
        assert store.current_bundle()["files"][common] == store.original_bundle()["files"][common]
        assert {path.relative_to(original): path.read_bytes() for path in original.rglob("*") if path.is_file()} == original_before


def test_reference_bundle_rejects_traversal_and_materializes_blank_enabled_path_files():
    _profiles, store, _builder = _modules()
    bundle = store.current_bundle()
    malicious = copy.deepcopy(bundle)
    malicious["files"]["../outside.md"] = "bad"
    try:
        store.validate_bundle(malicious)
    except ValueError as error:
        assert "Unsafe reference path" in str(error)
    else:
        raise AssertionError("Traversal path should have been rejected.")

    blank_path_bundle = copy.deepcopy(bundle)
    path = "WAN 2.2/split/first-last-frame-to-video.md"
    blank_path_bundle["files"].pop(path, None)
    validated = store.validate_bundle(blank_path_bundle)
    assert path in validated["files"]
    assert validated["files"][path] == ""


def test_frontend_uses_markdown_editor_and_separate_reference_schema_handshake():
    source = (ROOT / "web" / "js" / "unified_autoprompter.js").read_text(encoding="utf-8")
    assert "const REFERENCE_SCHEMA_VERSION = 1" in source
    assert "openMarkdownProfileSettings" in source
    assert "Common Profile Rules" in source
    assert "Global NSFW Rules" in source
    assert "Image NSFW rules" in source
    assert "Video NSFW rules" in source
    assert "reference/current_use" in source
    assert "reference_schema_version: REFERENCE_SCHEMA_VERSION" in source
    assert 'modelSettingsBtn.addEventListener("click", openMarkdownProfileSettings)' in source
    for obsolete_fallback in (
        "Write an Ideogram natural-language prompt.",
        "Write a WAN 2.2 video prompt.",
        "Write a MiniMax H3 prompt using the official video guide structure.",
        "Format-specific instructions:",
    ):
        assert obsolete_fallback not in source


def test_reference_root_has_only_original_and_current_use_with_complete_catalogs():
    reference = ROOT / "unified_autoprompter" / "reference"
    assert {path.name for path in reference.iterdir()} == {"original", "current_use"}
    original = reference / "original"
    current = reference / "current_use"
    original_files = {
        path.relative_to(original).as_posix(): path.read_bytes()
        for path in original.rglob("*") if path.is_file()
    }
    current_files = {
        path.relative_to(current).as_posix(): path.read_bytes()
        for path in current.rglob("*") if path.is_file()
    }
    assert current_files == original_files
    assert "manifest.json" in original_files
    assert "nsfw-image.md" in original_files
    assert "nsfw-video.md" in original_files
    assert "SDXL/Supporting/tags_output_without_negative.md" in original_files
    assert "SDXL/Supporting/tags_output_with_negative.md" in original_files


def test_standard_profiles_payload_contains_routing_metadata_not_instruction_text():
    profiles, _store, _builder = _modules()
    payload = profiles.profiles_payload()
    standard = [profile for profile in payload["profiles"] if profile["engine"] == "standard"]
    assert len(standard) == 12
    assert payload["reference_schema_version"] == 1
    for profile in standard:
        assert profile["notes"] == ""
        assert set(profile) == {
            "key", "label", "media_type", "default_format", "negative_supported",
            "json_supported", "notes", "engine", "formats", "default_generation_type",
            "generation_paths", "jsonx_config",
        }
        assert all(set(rule) == {"enabled"} for rule in profile["formats"].values())
        assert all(set(path) == {"label"} for path in profile["generation_paths"].values())


def test_markdown_contracts_preserve_bbox_orders_tags_and_minimax_negative_behavior():
    _profiles, store, _builder = _modules()
    files = store.original_bundle()["files"]
    assert "[y_min,x_min,y_max,x_max]" in files[
        "Ideogram 4/Supporting/json_output_without_negative.md"
    ]
    assert "[x_min,y_min,x_max,y_max]" in files[
        "Krea2/Supporting/json_output_without_negative.md"
    ]
    assert "comma-separated SDXL positive tags" in files[
        "SDXL/Supporting/tags_output_without_negative.md"
    ]
    assert "comma-separated SDXL negative tags" in files[
        "SDXL/Supporting/tags_output_with_negative.md"
    ]
    for folder in ("MiniMax H3 Official", "MiniMax H3 Alternate"):
        off = files[f"{folder}/Supporting/natural_output_without_negative.md"]
        on = files[f"{folder}/Supporting/natural_output_with_negative.md"]
        assert off == on
        assert "Do not generate a separate node negative output" in off


def test_manual_current_use_edit_is_effective_on_next_build_and_reset_all_preserves_customs():
    _profiles, store, builder = _modules()
    with tempfile.TemporaryDirectory() as temporary:
        root = pathlib.Path(temporary) / "reference"
        original = root / "original"
        current = root / "current_use"
        shutil.copytree(ROOT / "unified_autoprompter" / "reference" / "original", original)
        shutil.copytree(original, current)
        store.REFERENCE_ROOT = root
        store.ORIGINAL_ROOT = original
        store.CURRENT_ROOT = current

        common_path = current / "SDXL" / "split" / "common.md"
        common_path.write_bytes(common_path.read_bytes() + b"\nMANUAL FILESYSTEM SENTINEL")
        prompt, activated = builder.assemble_system_prompt(
            "sdxl", "natural", False, generation_type="text_to_image"
        )
        assert "MANUAL FILESYSTEM SENTINEL" in prompt
        assert activated[0]["path"] == "SDXL/split/common.md"

        bundle = store.current_bundle()
        source = next(profile for profile in bundle["manifest"]["profiles"] if profile["key"] == "sdxl")
        custom = copy.deepcopy(source)
        custom.update({"key": "custom_sdxl", "label": "Custom SDXL", "folder": "Custom SDXL", "builtin": False})
        bundle["manifest"]["profiles"].append(custom)
        prefix = "SDXL/"
        for path, text in list(bundle["files"].items()):
            if path.startswith(prefix):
                bundle["files"][f"Custom SDXL/{path[len(prefix):]}"] = text
        bundle["files"]["Custom SDXL/split/common.md"] += "\nCUSTOM SENTINEL"
        store.save_current_bundle(bundle)
        restored = store.reset_all()
        assert any(profile["key"] == "custom_sdxl" for profile in restored["manifest"]["profiles"])
        assert restored["files"]["Custom SDXL/split/common.md"].endswith("CUSTOM SENTINEL")
        assert restored["files"]["SDXL/split/common.md"] == store.original_bundle()["files"]["SDXL/split/common.md"]


def test_wan_text_to_image_uses_image_nsfw_and_video_to_video_can_be_enabled_blank():
    _profiles, store, builder = _modules()
    with tempfile.TemporaryDirectory() as temporary:
        root = pathlib.Path(temporary) / "reference"
        original = root / "original"
        current = root / "current_use"
        shutil.copytree(ROOT / "unified_autoprompter" / "reference" / "original", original)
        shutil.copytree(original, current)
        store.REFERENCE_ROOT = root
        store.ORIGINAL_ROOT = original
        store.CURRENT_ROOT = current

        bundle = store.current_bundle()
        wan = next(profile for profile in bundle["manifest"]["profiles"] if profile["key"] == "wan2_2")
        wan["enabled_generation_types"].extend(["text_to_image", "video_to_video"])
        bundle["files"].pop("WAN 2.2/split/video-to-video.md", None)
        saved = store.save_current_bundle(bundle)
        assert saved["files"]["WAN 2.2/split/video-to-video.md"] == ""

        prompt, activated = builder.assemble_system_prompt(
            "wan2_2", "natural", False,
            generation_type="text_to_image", nsfw_enabled=True,
        )
        paths = [item["path"] for item in activated]
        assert "nsfw-image.md" in paths
        assert "nsfw-video.md" not in paths
        assert saved["files"]["nsfw-image.md"] in prompt

        prompt, activated = builder.assemble_system_prompt(
            "wan2_2", "natural", False,
            generation_type="video_to_video", nsfw_enabled=True,
        )
        paths = [item["path"] for item in activated]
        assert "WAN 2.2/split/video-to-video.md" not in paths
        assert "nsfw-video.md" in paths
        assert "nsfw-image.md" not in paths


def test_atomic_write_failure_restores_previous_current_use_tree():
    _profiles, store, _builder = _modules()
    with tempfile.TemporaryDirectory() as temporary:
        root = pathlib.Path(temporary) / "reference"
        original = root / "original"
        current = root / "current_use"
        shutil.copytree(ROOT / "unified_autoprompter" / "reference" / "original", original)
        shutil.copytree(original, current)
        store.REFERENCE_ROOT = root
        store.ORIGINAL_ROOT = original
        store.CURRENT_ROOT = current
        before = {
            path.relative_to(current): path.read_bytes()
            for path in current.rglob("*") if path.is_file()
        }
        bundle = store.current_bundle()
        bundle["files"]["SDXL/split/common.md"] += "\nSHOULD NOT COMMIT"
        real_replace = store.os.replace
        calls = 0

        def fail_stage_install(source, destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated stage install failure")
            return real_replace(source, destination)

        store.os.replace = fail_stage_install
        try:
            try:
                store.save_current_bundle(bundle)
            except OSError as error:
                assert "simulated stage install failure" in str(error)
            else:
                raise AssertionError("The simulated atomic replacement failure was not raised.")
        finally:
            store.os.replace = real_replace
        after = {
            path.relative_to(current): path.read_bytes()
            for path in current.rglob("*") if path.is_file()
        }
        assert after == before
