import importlib.util
import json
import pathlib
import sys
import tempfile
import types

from PIL import Image


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _install_folder_paths_stub():
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.models_dir = str(ROOT / ".test_models")
    folder_paths.folder_names_and_paths = {}
    folder_paths.get_filename_list = lambda _folder: []
    folder_paths.get_full_path = lambda _folder, _name: None
    folder_paths.get_user_directory = lambda: str(ROOT / ".test_user")
    sys.modules.setdefault("folder_paths", folder_paths)


def _load_module(relative_path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = module_name.rsplit(".", 1)[0]
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_package_modules():
    _install_folder_paths_stub()
    package_name = "workflowx_unified_autoprompter_test"
    package = types.ModuleType(package_name)
    package.__path__ = [str(ROOT / "unified_autoprompter")]
    sys.modules.setdefault(package_name, package)
    profiles = _load_module("unified_autoprompter/profiles.py", f"{package_name}.profiles")
    profile_config = _load_module("unified_autoprompter/profile_config.py", f"{package_name}.profile_config")
    _load_module("unified_autoprompter/reference_store.py", f"{package_name}.reference_store")
    prompt_io = _load_module("unified_autoprompter/prompt_io.py", f"{package_name}.prompt_io")
    prompt_builder = _load_module("unified_autoprompter/prompt_builder.py", f"{package_name}.prompt_builder")
    node = _load_module("unified_autoprompter/node.py", f"{package_name}.node")
    return profiles, prompt_io, prompt_builder, node, profile_config


def _load_openai_backend():
    _install_folder_paths_stub()
    package_name = "workflowx_unified_autoprompter_test"
    package = sys.modules.setdefault(package_name, types.ModuleType(package_name))
    package.__path__ = [str(ROOT / "unified_autoprompter")]
    return _load_module("unified_autoprompter/openai_backend.py", f"{package_name}.openai_backend")


def _load_gemini_backend():
    _install_folder_paths_stub()
    package_name = "workflowx_unified_autoprompter_test"
    package = sys.modules.setdefault(package_name, types.ModuleType(package_name))
    package.__path__ = [str(ROOT / "unified_autoprompter")]
    return _load_module("unified_autoprompter/gemini_backend.py", f"{package_name}.gemini_backend")


def _load_grok_backend():
    _install_folder_paths_stub()
    package_name = "workflowx_unified_autoprompter_test"
    package = sys.modules.setdefault(package_name, types.ModuleType(package_name))
    package.__path__ = [str(ROOT / "unified_autoprompter")]
    return _load_module("unified_autoprompter/grok_backend.py", f"{package_name}.grok_backend")


def _load_deepseek_backend():
    _install_folder_paths_stub()
    package_name = "workflowx_unified_autoprompter_test"
    package = sys.modules.setdefault(package_name, types.ModuleType(package_name))
    package.__path__ = [str(ROOT / "unified_autoprompter")]
    return _load_module("unified_autoprompter/deepseek_backend.py", f"{package_name}.deepseek_backend")


def _load_folder_registry():
    _install_folder_paths_stub()
    package_name = "workflowx_unified_autoprompter_test"
    package = sys.modules.setdefault(package_name, types.ModuleType(package_name))
    package.__path__ = [str(ROOT / "unified_autoprompter")]
    return _load_module("unified_autoprompter/folder_registry.py", f"{package_name}.folder_registry")


def _load_routes_module():
    _load_package_modules()
    import aiohttp.web  # noqa: F401 - use the real package to avoid leaking a process-global test stub
    package_name = "workflowx_unified_autoprompter_test"
    return _load_module("unified_autoprompter/routes.py", f"{package_name}.routes")


class _FakeResponse:
    def __init__(self, payload, status_code=200, text="", headers=None):
        self._payload = payload
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._payload


def _with_temp_profile_paths(profile_config):
    tmp = tempfile.TemporaryDirectory()
    root = pathlib.Path(tmp.name)
    profile_config.config_path = lambda: root / "model_prompt_profiles.json"
    profile_config.default_config_path = lambda: ROOT / "unified_autoprompter" / "model_prompt_profiles.defaults.json"
    return tmp


def test_prompt_profiles_capture_allowed_formats_and_negative_rules():
    profiles, _prompt_io, _prompt_builder, _node, _profile_config = _load_package_modules()

    assert set(profiles.profile_options()) == {
        "ideogram4",
        "sdxl",
        "qwen_image",
        "flux1_dev",
        "flux2_dev",
        "flux_klein",
        "z_image",
        "wan2_2",
        "ltx_2_3",
        "minimax_h3_official",
        "minimax_h3_alternate",
        "krea2",
        "jsonx",
    }
    assert profiles.normalize_format("z_image", "json") == "natural"
    assert profiles.normalize_format("sdxl", "json") == "tags"
    assert profiles.normalize_format("flux2_dev", "json") == "json"
    assert profiles.normalize_format("wan2_2", "json") == "natural"
    assert profiles.normalize_format("jsonx", "tags") == "json"
    assert profiles.normalize_format("ltx_2_3", "tags") == "natural"
    assert profiles.normalize_format("minimax_h3_official", "json") == "natural"
    assert profiles.normalize_format("minimax_h3_alternate", "tags") == "natural"
    for profile in profiles.profile_options():
        if profile in {"minimax_h3_official", "minimax_h3_alternate"}:
            assert profiles.supports_negative(profile) is False
        else:
            assert profiles.supports_negative(profile) is True


def test_granular_defaults_cover_enabled_formats_and_image_modes():
    profiles, _prompt_io, _prompt_builder, _node, _profile_config = _load_package_modules()
    store = importlib.import_module("workflowx_unified_autoprompter_test.reference_store")
    bundle = store.current_bundle()
    assert len(bundle["manifest"]["profiles"]) == 12
    assert "video_to_video" in bundle["manifest"]["generation_types"]
    for metadata in bundle["manifest"]["profiles"]:
        folder = metadata["folder"]
        assert bundle["files"][f"{folder}/split/common.md"].strip()
        for filename in store.SUPPORTING_FILENAMES.values():
            assert bundle["files"][f"{folder}/Supporting/{filename}"].strip()
        for generation_type in metadata["enabled_generation_types"]:
            assert generation_type in bundle["manifest"]["generation_types"]
        for prompt_format in metadata["enabled_formats"]:
            prefix = bundle["manifest"]["formats"][prompt_format]["contract_prefix"]
            assert bundle["files"][f"{folder}/Supporting/{prefix}_without_negative.md"].strip()
    all_profiles = profiles.all_profiles()
    assert set(all_profiles["jsonx"].generation_paths) == {"text_to_image", "image_to_image"}
    assert all_profiles["minimax_h3_official"].negative_supported is False
    assert all_profiles["krea2"].json_supported is True


def test_default_profile_config_includes_krea2_json_bbox_order():
    _profiles, _prompt_io, _prompt_builder, _node, profile_config = _load_package_modules()
    defaults = profile_config.default_config()
    profiles_by_key = {profile["key"]: profile for profile in defaults["profiles"]}

    assert "krea2" in profiles_by_key
    krea2 = profiles_by_key["krea2"]
    assert krea2["json_supported"] is True
    assert krea2["formats"]["json"]["enabled"] is True
    common = "\n\n".join((
        krea2["formats"]["json"]["common_rules"]["text"],
        krea2["formats"]["json"]["common_guide"]["text"],
    ))
    assert "[x_min,y_min,x_max,y_max]" in common
    assert 'every non-text element must use "type": "obj"' in common


def test_default_minimax_profiles_include_timing_context_and_reference_boundaries():
    _profiles, _prompt_io, _prompt_builder, _node, profile_config = _load_package_modules()
    defaults = profile_config.default_config()
    profiles_by_key = {profile["key"]: profile for profile in defaults["profiles"]}

    official = profiles_by_key["minimax_h3_official"]
    alternate = profiles_by_key["minimax_h3_alternate"]
    for profile in (official, alternate):
        common = "\n\n".join((
            profile["formats"]["natural"]["common_rules"]["text"],
            profile["formats"]["natural"]["common_guide"]["text"],
        ))
        assert "visible and audible" in common or "camera-visible and microphone-audible facts" in common
        assert "5.00-second" in common
        assert "same-camera action change" in common
        assert "Context Loop" in common
    first_contract = official["generation_paths"]["first_frame_to_video"]["output_contracts"]["natural"]["negative_off"]
    reference_path = official["generation_paths"]["reference_to_video"]
    assert "For the target video, at 0.00 seconds" in first_contract
    reference_guide = reference_path["path_guide"]["text"]
    alternate_guide = alternate["generation_paths"]["reference_to_video"]["path_guide"]["text"]
    assert "bounded role" in reference_guide
    assert "explicitly exclude incidental" in alternate_guide


def test_system_prompt_uses_format_contract_and_image_mode():
    _profiles, _prompt_io, prompt_builder, _node, _profile_config = _load_package_modules()

    with_image = prompt_builder.build_system_prompt(
        "ideogram4", "json", False, has_image=True, generation_type="image_to_image",
    )
    without_image = prompt_builder.build_system_prompt(
        "ideogram4", "json", False, has_image=False, generation_type="text_to_image",
    )
    negative = prompt_builder.build_system_prompt(
        "sdxl", "tags", True, has_image=False, generation_type="text_to_image",
    )

    assert "connected reference" in with_image.lower()
    assert "references actually supplied" not in without_image.lower()
    assert "prompt_json" in with_image
    assert "comma-separated SDXL negative tags" in negative
    assert "Unified Autoprompter" not in negative
    assert "Target key" not in negative


def test_v7_system_prompt_has_exact_selected_block_order_and_optional_nsfw():
    _profiles, _prompt_io, prompt_builder, _node, _profile_config = _load_package_modules()
    store = importlib.import_module("workflowx_unified_autoprompter_test.reference_store")
    bundle = store.current_bundle()
    profile = next(item for item in bundle["manifest"]["profiles"] if item["key"] == "wan2_2")
    generation_type = "first_frame_to_video"
    folder = profile["folder"]
    common = bundle["files"][f"{folder}/split/common.md"]
    path = bundle["files"][f"{folder}/split/first-frame-to-video.md"]
    reference = bundle["files"][f"{folder}/Supporting/without_reference_supported.md"]
    contract = bundle["files"][f"{folder}/Supporting/natural_output_without_negative.md"]
    nsfw = bundle["files"]["nsfw-video.md"]
    expected_without_nsfw = "\n\n".join([
        common, path, reference,
        contract,
    ])
    expected_with_nsfw = "\n\n".join([
        common, path, nsfw, reference,
        contract,
    ])

    assert prompt_builder.build_system_prompt(
        "wan2_2", "natural", False, generation_type=generation_type,
    ) == expected_without_nsfw
    assert prompt_builder.build_system_prompt(
        "wan2_2", "natural", False, generation_type=generation_type, nsfw_enabled=True,
    ) == expected_with_nsfw
    for noise in (
        "Unified Autoprompter", "Target model:", "Target key:", "Model notes:",
        "Format-specific instructions:", "Text to Image", "Reference to Video",
    ):
        assert noise not in expected_with_nsfw


def test_generation_image_validation_only_enforces_authoring_media_ceiling():
    profiles, _prompt_io, _prompt_builder, _node, _profile_config = _load_package_modules()
    for generation_type in profiles.ALL_GENERATION_TYPES:
        for count in (0, 1, 2, profiles.MAX_AUTHORING_IMAGES):
            profiles.validate_generation_image_count(generation_type, count)
        try:
            profiles.validate_generation_image_count(generation_type, profiles.MAX_AUTHORING_IMAGES + 1)
        except ValueError as error:
            assert "at most" in str(error)
        else:
            raise AssertionError(f"Expected {generation_type} above the authoring limit to fail.")


def test_four_state_image_routing_keeps_connected_authoring_evidence():
    profiles, _prompt_io, _prompt_builder, _node, _profile_config = _load_package_modules()

    for generation_type in ("text_to_image", "text_to_video"):
        submitted, ignored = profiles.effective_generation_images(
            generation_type, ["image-1", "image-2"]
        )
        submitted_count, ignored_count = profiles.effective_generation_image_count(
            generation_type, 2
        )
        assert submitted == ["image-1", "image-2"]
        assert ignored == 0
        assert (submitted_count, ignored_count) == (2, 0)
        assert profiles.resolve_image_state(generation_type, 2) == profiles.IMAGE_STATE_UNSUPPORTED_WITH_IMAGE_GUIDANCE
        assert profiles.resolve_image_state(generation_type, 0) is None
        profiles.validate_generation_image_count(generation_type, len(submitted))

    submitted, ignored = profiles.effective_generation_images(
        "reference_to_video", ["image-1", "image-2"]
    )
    assert submitted == ["image-1", "image-2"]
    assert ignored == 0
    assert profiles.resolve_image_state("reference_to_video", 2) == profiles.IMAGE_STATE_SUPPORTED_WITH_IMAGE
    assert profiles.resolve_image_state("reference_to_video", 0) == profiles.IMAGE_STATE_SUPPORTED_WITHOUT_IMAGE
    profiles.validate_generation_image_count("reference_to_video", len(submitted))


def test_ui_only_block_metadata_never_reaches_model_prompt():
    _profiles, _prompt_io, prompt_builder, _node, profile_config = _load_package_modules()
    with _with_temp_profile_paths(profile_config):
        config = profile_config.default_config()
        profile = next(item for item in config["profiles"] if item["key"] == "ideogram4")
        profile["formats"]["natural"]["common_rules"]["title"] = "UI TITLE SENTINEL"
        profile["formats"]["natural"]["common_rules"]["source"] = "UI SOURCE SENTINEL"
        path = profile["generation_paths"]["text_to_image"]
        path["path_rules"]["title"] = "PATH TITLE SENTINEL"
        path["path_rules"]["source"] = "PATH SOURCE SENTINEL"
        profile_config.save_config(config)

        system = prompt_builder.build_system_prompt(
            "ideogram4", "natural", False, generation_type="text_to_image"
        )
        for sentinel in (
            "UI TITLE SENTINEL", "UI SOURCE SENTINEL",
            "PATH TITLE SENTINEL", "PATH SOURCE SENTINEL",
        ):
            assert sentinel not in system


def test_live_and_default_profile_catalogs_are_byte_identical():
    original = ROOT / "unified_autoprompter" / "reference" / "original"
    current = ROOT / "unified_autoprompter" / "reference" / "current_use"
    original_files = {
        path.relative_to(original): path.read_bytes()
        for path in original.rglob("*") if path.is_file()
    }
    current_files = {
        path.relative_to(current): path.read_bytes()
        for path in current.rglob("*") if path.is_file()
    }
    assert current_files == original_files


def test_v7_canonical_contracts_are_path_specific_and_fully_visible():
    catalog_text = (ROOT / "unified_autoprompter" / "model_prompt_profiles.defaults.json").read_text(encoding="utf-8")
    current = json.loads(catalog_text)
    current_by_key = {profile["key"]: profile for profile in current["profiles"]}
    assert current["version"] == 7
    for profile in current_by_key.values():
        for path in profile["generation_paths"].values():
            assert set(path["image_state_blocks"]) == {
                "supported_with_image",
                "supported_without_image",
                "unsupported_with_image_guidance",
            }
            for block in path["image_state_blocks"].values():
                assert block["title"] and block["text"] and block["source"]

    updated_guidance = (
        "Inspect the connected images as visual guidance for prompt authoring. "
        "Use relevant visible evidence from reference in connection with user's given description to infer intent. "
        "Do not emit Picture/Image reference commentary, or language implying that the downstream generator will receive the images."
    )
    assert catalog_text.count(updated_guidance) == len(current_by_key)
    assert "Translate relevant visible evidence into a self-contained text prompt" not in catalog_text

    official = current_by_key["minimax_h3_official"]["generation_paths"]
    official_expectations = {
        "text_to_video": (
            "integrated_multimodal_description:\n...\n\noverall_soundscape:",
            "non_diegetic_music:",
        ),
        "first_frame_to_video": (
            "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.",
            "integrated_multimodal_description:",
        ),
        "first_last_frame_to_video": (
            "How the reference pictures align with the target video",
            "Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video",
        ),
        "last_frame_to_video": (
            "How the reference pictures align with the target video",
            "<Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video",
        ),
        "reference_to_video": (
            "subject_definitions:\n...\n\nsummary:\n...\n\nretention_analysis:",
            "detailed_description:",
        ),
    }
    for path_name, expected_clauses in official_expectations.items():
        contract = official[path_name]["output_contracts"]["natural"]
        assert contract["negative_off"] == contract["negative_on"]
        for clause in expected_clauses:
            assert clause in contract["negative_off"]
        assert "Return ONLY" in contract["negative_off"]

    alternate = current_by_key["minimax_h3_alternate"]["generation_paths"]
    assert "[SCENE]" in alternate["text_to_video"]["output_contracts"]["natural"]["negative_off"]
    assert "[REFERENCE USE]" in alternate["first_frame_to_video"]["output_contracts"]["natural"]["negative_off"]
    assert "[BOUNDARY FRAMES]" in alternate["first_last_frame_to_video"]["output_contracts"]["natural"]["negative_off"]
    assert "<Video 1> defines" in alternate["reference_to_video"]["output_contracts"]["natural"]["negative_off"]
    assert len({
        path["output_contracts"]["natural"]["negative_off"]
        for path in alternate.values()
    }) == 4


def test_v7_profiles_expose_one_rules_and_one_full_guide_field_with_source_sentinels():
    catalog = json.loads(
        (ROOT / "unified_autoprompter" / "model_prompt_profiles.defaults.json").read_text(encoding="utf-8")
    )
    sentinels = {
        "ideogram4": "## Text and typography",
        "sdxl": "## Prompt anatomy",
        "qwen_image": "## Prompt enhancement",
        "flux1_dev": "## Structured natural-language prompting",
        "flux2_dev": "## Complex scene construction",
        "flux_klein": "## Concise high-signal prompting",
        "krea2": "## Prompt expansion",
        "z_image": "## Fluent prompt enhancement",
        "wan2_2": "## Prompt extension objective",
        "ltx_2_3": "## Temporal anatomy",
        "minimax_h3_official": "## Shots, timing, and Context Loop",
        "minimax_h3_alternate": "## Shot construction",
        "jsonx": "## Structural coherence",
    }
    for profile in catalog["profiles"]:
        searchable = []
        for rule in profile["formats"].values():
            if not rule["enabled"]:
                continue
            assert "common_blocks" not in rule
            assert set(rule) == {"enabled", "common_rules", "common_guide"}
            assert rule["common_rules"]["text"].strip()
            assert rule["common_guide"]["text"].strip()
            searchable.append(rule["common_guide"]["text"])
        for path in profile["generation_paths"].values():
            assert "instruction_blocks" not in path
            assert path["path_rules"]["text"].strip()
            assert path["path_guide"]["text"].strip()
            searchable.append(path["path_guide"]["text"])
        assert sentinels[profile["key"]] in "\n".join(searchable)


def test_v7_reverse_payload_audit_selects_each_guide_once_and_excludes_other_paths():
    _profiles, _prompt_io, prompt_builder, _node, _profile_config = _load_package_modules()
    store = importlib.import_module("workflowx_unified_autoprompter_test.reference_store")
    bundle = store.current_bundle()
    for profile in bundle["manifest"]["profiles"]:
        for format_key in profile["enabled_formats"]:
            for path_key in profile["enabled_generation_types"]:
                prompt, activated = prompt_builder.assemble_system_prompt(
                    profile["key"], format_key, False,
                    reference_count=1, generation_type=path_key, nsfw_enabled=True,
                )
                paths = [item["path"] for item in activated]
                assert prompt == "\n\n".join(bundle["files"][path] for path in paths)
                assert [item["kind"] for item in activated] == [
                    "common", "generation_type", "nsfw", "reference_usage", "output_contract",
                ] or [item["kind"] for item in activated] == [
                    "common", "nsfw", "reference_usage", "output_contract",
                ]
                for forbidden in (
                    "activated_blocks", "routing decision", "selected output contract",
                    "implementation JSON", "process metadata", "think step by step",
                ):
                    assert forbidden not in prompt


def test_v7_image_profile_path_guides_are_model_specific_and_krea_schema_is_not_ideogram():
    catalog = json.loads(
        (ROOT / "unified_autoprompter" / "model_prompt_profiles.defaults.json").read_text(encoding="utf-8")
    )
    profiles = {profile["key"]: profile for profile in catalog["profiles"]}
    image_keys = (
        "ideogram4", "sdxl", "qwen_image", "flux1_dev", "flux2_dev",
        "flux_klein", "krea2", "z_image",
    )
    for path_key in ("text_to_image", "image_to_image"):
        guides = [profiles[key]["generation_paths"][path_key]["path_guide"]["text"] for key in image_keys]
        assert len(set(guides)) == len(guides)

    krea = profiles["krea2"]
    krea_text = "\n".join(
        rule["common_rules"]["text"] + "\n" + rule["common_guide"]["text"]
        for rule in krea["formats"].values() if rule["enabled"]
    )
    krea_contract = krea["generation_paths"]["text_to_image"]["output_contracts"]["json"]["negative_off"]
    assert "high_level_description" not in krea_text + krea_contract
    assert "style_description" not in krea_text + krea_contract
    assert "Ideogram" not in krea_text + krea_contract
    assert "compositional_deconstruction" in krea_contract
    assert '"description": "complete final Krea2 visual description"' in krea_contract


def test_v7_invalid_explicit_profile_path_and_format_do_not_silently_fallback():
    profiles, _prompt_io, prompt_builder, _node, _profile_config = _load_package_modules()
    for call, expected in (
        (lambda: profiles.get_profile("missing_profile"), "Unknown Unified PrompterX profile"),
        (lambda: profiles.normalize_generation_type("ideogram4", "text_to_video"), "not supported"),
        (lambda: prompt_builder.build_system_prompt("wan2_2", "natural", False, generation_type="image_to_image"), "not supported"),
    ):
        try:
            call()
        except ValueError as error:
            assert expected in str(error)
        else:
            raise AssertionError("Expected an explicit invalid selection to fail.")


def test_v7_forward_source_concept_audit_covers_common_and_path_guides():
    catalog = json.loads(
        (ROOT / "unified_autoprompter" / "model_prompt_profiles.defaults.json").read_text(encoding="utf-8")
    )
    profiles = {profile["key"]: profile for profile in catalog["profiles"]}
    common_sentinels = {
        "ideogram4": ("Literal natural-language prompting", "Text and typography"),
        "sdxl": ("Prompt anatomy", "Negative guidance"),
        "qwen_image": ("Prompt enhancement", "multilingual content"),
        "flux1_dev": ("Structured natural-language prompting", "Typography"),
        "flux2_dev": ("Complex scene construction", "Visual consistency"),
        "flux_klein": ("Concise high-signal prompting", "Relationship clarity"),
        "krea2": ("Prompt expansion", "Composition and physical description"),
        "z_image": ("Fluent prompt enhancement", "Text and language fidelity"),
        "wan2_2": ("Prompt extension objective", "Motion and camera", "Continuity"),
        "ltx_2_3": ("Temporal anatomy", "Motion and physical acting", "Dialogue and audio"),
        "minimax_h3_official": ("Shots, timing, and Context Loop", "Reference and dialogue syntax"),
        "minimax_h3_alternate": ("Shot construction and timing", "Reference labels and ownership"),
    }
    for profile_key, sentinels in common_sentinels.items():
        profile = profiles[profile_key]
        guides = "\n".join(
            rule["common_guide"]["text"] for rule in profile["formats"].values() if rule["enabled"]
        )
        for sentinel in sentinels:
            assert sentinel in guides

    path_sentinels = {
        ("qwen_image", "image_to_image"): ("addition, deletion, replacement", "preserve all unrelated regions"),
        ("flux2_dev", "image_to_image"): ("Map each supplied source", "incidental people"),
        ("wan2_2", "first_last_frame_to_video"): ("opening state", "required destination"),
        ("ltx_2_3", "first_frame_to_video"): ("frame zero", "subsequent motion"),
        ("minimax_h3_official", "reference_to_video"): ("six-field method", "retention_analysis"),
        ("minimax_h3_official", "last_frame_to_video"): ("only the final frame", "5.00"),
        ("minimax_h3_alternate", "reference_to_video"): ("Bounded reference authority", "SOURCE MASTER"),
    }
    for (profile_key, path_key), sentinels in path_sentinels.items():
        guide = profiles[profile_key]["generation_paths"][path_key]["path_guide"]["text"]
        for sentinel in sentinels:
            assert sentinel in guide


def test_v6_to_v7_migration_preserves_custom_rules_and_installs_guides_and_new_global_path():
    _profiles, _prompt_io, _prompt_builder, _node, profile_config = _load_package_modules()
    with _with_temp_profile_paths(profile_config):
        old = profile_config.default_config()
        old["version"] = 6
        old["nsfw_rules"].pop("last_frame_to_video", None)
        for candidate in old["profiles"]:
            candidate["generation_paths"].pop("last_frame_to_video", None)
            for format_rule in candidate["formats"].values():
                rules = format_rule.pop("common_rules")
                format_rule.pop("common_guide")
                format_rule["common_blocks"] = [rules] if rules["text"] else []
            for path_rule in candidate["generation_paths"].values():
                rules = path_rule.pop("path_rules")
                path_rule.pop("path_guide")
                path_rule["instruction_blocks"] = [rules]
        ideogram = next(profile for profile in old["profiles"] if profile["key"] == "ideogram4")
        ideogram["formats"]["natural"]["common_blocks"][0]["text"] = "CUSTOM V6 RULE"
        profile_config.config_path().write_text(json.dumps(old), encoding="utf-8")
        migrated = profile_config.load_config()
        current = next(profile for profile in migrated["profiles"] if profile["key"] == "ideogram4")
        assert migrated["version"] == 7
        assert "CUSTOM V6 RULE" in current["formats"]["natural"]["common_rules"]["text"]
        assert current["formats"]["natural"]["common_guide"]["text"].strip()
        assert "last_frame_to_video" in migrated["nsfw_rules"]
        assert profile_config.config_path().with_name("model_prompt_profiles.v6.backup.json").exists()


def test_global_nsfw_rules_are_detailed_and_only_selected_path_is_injected():
    _profiles, _prompt_io, prompt_builder, _node, _profile_config = _load_package_modules()
    store = importlib.import_module("workflowx_unified_autoprompter_test.reference_store")
    bundle = store.current_bundle()
    image_rule = bundle["files"]["nsfw-image.md"]
    video_rule = bundle["files"]["nsfw-video.md"]
    assert image_rule.strip() and video_rule.strip()

    selected = "text_to_video"
    enabled = prompt_builder.build_system_prompt(
        "minimax_h3_official", "natural", False,
        generation_type=selected, nsfw_enabled=True,
    )
    disabled = prompt_builder.build_system_prompt(
        "minimax_h3_official", "natural", False,
        generation_type=selected, nsfw_enabled=False,
    )
    assert video_rule in enabled
    assert video_rule not in disabled
    assert image_rule not in enabled


def test_minimax_system_prompt_uses_plain_text_contract():
    _profiles, _prompt_io, prompt_builder, _node, _profile_config = _load_package_modules()

    official = prompt_builder.build_system_prompt(
        "minimax_h3_official",
        "natural",
        True,
        reference_count=2,
        generation_type="reference_to_video",
    )

    assert "Return only the final MiniMax H3 Official prompt body as plain text" in official
    assert "Return valid JSON only" not in official
    assert "subject_definitions" in official
    assert "detailed_description" in official
    assert "Do not generate a separate node negative output" in official
    assert "Target model" not in official
    assert "Profile notes" not in official


def test_prompt_builder_labels_multiple_image_references_for_minimax():
    _profiles, _prompt_io, prompt_builder, _node, _profile_config = _load_package_modules()

    system_prompt = prompt_builder.build_system_prompt(
        "minimax_h3_official",
        "natural",
        False,
        reference_count=2,
        generation_type="reference_to_video",
    )
    user_prompt = prompt_builder.build_user_prompt(
        {
            "prompt_text": "Cinematic dance sequence with Urdu dialogue; use Audio 1 for matching timbre.",
            "detail": "high",
        },
        target_model="minimax_h3_alternate",
        reference_count=2,
        generation_type="reference_to_video",
    )

    assert "Treat each reference as bounded evidence" in system_prompt
    assert "Picture 1, Picture 2" not in user_prompt
    assert "matching timbre" in user_prompt
    assert "Detail level: high" in user_prompt


def test_prompt_builder_preserves_minimax_audio_as_is_role():
    _profiles, _prompt_io, prompt_builder, _node, _profile_config = _load_package_modules()

    user_prompt = prompt_builder.build_user_prompt(
        {
            "prompt_text": (
                "A moody night drive. An audio will be provided; "
                "use audio 1 as-is as the complete final soundtrack."
            ),
        },
        target_model="minimax_h3_official",
    )

    assert "use audio 1 as-is as the complete final soundtrack" in user_prompt
    assert "Audio reference required" not in user_prompt


def test_output_assembly_matches_contract_for_positive_and_negative():
    _profiles, prompt_io, _prompt_builder, _node, _profile_config = _load_package_modules()

    prompt, positive, negative = prompt_io.build_outputs(
        "sdxl",
        "tags",
        positive="portrait, rim light",
        negative="blur, extra fingers",
        negative_enabled=True,
    )

    assert positive == "portrait, rim light"
    assert negative == "blur, extra fingers"
    assert prompt == "Positive:\nportrait, rim light\n\nNegative:\nblur, extra fingers"


def test_output_assembly_preserves_negative_for_every_profile():
    profiles, prompt_io, _prompt_builder, _node, _profile_config = _load_package_modules()

    for profile in profiles.profile_options():
        prompt_format = profiles.normalize_format(profile, "natural")
        prompt, positive, negative = prompt_io.build_outputs(
            profile,
            prompt_format,
            positive="positive prompt",
            negative="negative prompt",
            negative_enabled=True,
        )

        assert positive == "positive prompt"
        if profile in {"minimax_h3_official", "minimax_h3_alternate"}:
            assert negative == ""
            assert prompt == "positive prompt"
            continue
        assert negative == "negative prompt"
        if prompt_format == "json":
            assert prompt == "positive prompt"
        else:
            assert prompt == "Positive:\npositive prompt\n\nNegative:\nnegative prompt"


def test_minimax_raw_response_preserves_section_formatting():
    _profiles, prompt_io, _prompt_builder, _node, _profile_config = _load_package_modules()
    raw = (
        "subject_definitions:\n"
        "<Picture 1> is the first frame of [Shot 1].\n"
        "<Picture 2> is the last-frame anchor for [Shot 1].\n"
        "<Subject 1> is the subject from both pictures.\n"
        "<Audio 1> is the voice-timbre reference for <Subject 1> (S1).\n\n"
        "summary:\n"
        "[reference generation + audio reference] The target video uses the references.\n\n"
        "retention_analysis:\n"
        "<Picture 1> ([Shot 1] first frame): fully_preserved - first-frame composition is retained.\n\n"
        "detailed_description:\n"
        "[Shot 1] The scene begins from <Picture 1>.\n\n"
        "overall_soundscape:\n"
        "Room tone continues.\n\n"
        "non_diegetic_music:\n"
        "N/A"
    )

    parsed = prompt_io.parse_generation_response(
        "minimax_h3_official",
        "natural",
        raw,
        negative_enabled=True,
    )

    assert parsed["prompt"] == raw
    assert parsed["positive"] == raw
    assert parsed["negative"] == ""
    assert "\n\nsummary:\n" in parsed["positive"]


def test_minimax_json_string_literal_response_is_unwrapped_to_plain_text():
    _profiles, prompt_io, _prompt_builder, _node, _profile_config = _load_package_modules()
    plain = (
        "subject_definitions:\n"
        "<Picture 1> is the first frame of [Shot 1].\n\n"
        "summary:\n"
        "The target video follows the reference.\n\n"
        "retention_analysis:\n"
        "<Picture 1> ([Shot 1] first frame): fully_preserved - composition is retained.\n\n"
        "detailed_description:\n"
        "[Shot 1] The scene begins from <Picture 1>.\n\n"
        "overall_soundscape:\n"
        "Room tone continues.\n\n"
        "non_diegetic_music:\n"
        "N/A"
    )
    raw = json.dumps(plain)

    parsed = prompt_io.parse_generation_response(
        "minimax_h3_official",
        "natural",
        raw,
        negative_enabled=True,
    )
    prompt, positive, negative = prompt_io.build_outputs(
        "minimax_h3_official",
        "natural",
        positive=raw,
        final_prompt=raw,
        negative="ignored",
        negative_enabled=True,
    )

    assert parsed["prompt"] == plain
    assert parsed["positive"] == plain
    assert prompt == plain
    assert positive == plain
    assert negative == ""
    assert "\\n" not in parsed["prompt"]
    assert not parsed["prompt"].startswith('"')


def test_generation_response_normalizes_ideogram_and_flux_json():
    _profiles, prompt_io, _prompt_builder, _node, _profile_config = _load_package_modules()

    ideogram = prompt_io.parse_generation_response(
        "ideogram4",
        "json",
        '{"prompt_json":{"high_level_description":"poster","compositional_deconstruction":{"elements":[]}}}',
        negative_enabled=False,
    )
    flux = prompt_io.parse_generation_response(
        "flux2_dev",
        "json",
        '{"prompt_json":{"scene":"rainy street","subjects":[{"description":"detective"}]}}',
        negative_enabled=False,
    )

    assert '"high_level_description": "poster"' in ideogram["prompt"]
    assert ideogram["positive"] == ideogram["prompt"]
    assert '"scene": "rainy street"' in flux["prompt"]
    assert flux["negative"] == ""


def test_bbox_json_response_normalizes_semantic_element_types():
    _profiles, prompt_io, _prompt_builder, _node, _profile_config = _load_package_modules()
    raw = json.dumps({
        "prompt_json": {
            "high_level_description": "portrait",
            "compositional_deconstruction": {
                "elements": [
                    {"type": "person", "bbox": [100, 200, 800, 700], "desc": "subject"},
                    {"type": "text", "bbox": [820, 100, 900, 500], "text": "SALE", "desc": "label"},
                ],
            },
        }
    })

    ideogram = prompt_io.parse_generation_response("ideogram4", "json", raw, negative_enabled=False)
    krea = prompt_io.parse_generation_response("krea2", "json", raw, negative_enabled=False)

    assert json.loads(ideogram["positive"])["compositional_deconstruction"]["elements"][0]["type"] == "obj"
    assert json.loads(ideogram["positive"])["compositional_deconstruction"]["elements"][1]["type"] == "text"
    assert json.loads(krea["positive"])["compositional_deconstruction"]["elements"][0]["type"] == "obj"


def test_disable_color_palette_strips_json_output_without_mutating_response():
    _profiles, prompt_io, _prompt_builder, _node, _profile_config = _load_package_modules()
    raw = json.dumps({
        "high_level_description": "portrait",
        "style_description": {
            "medium": "photograph",
            "color_palette": ["#FFFFFF", "#111111"],
        },
        "compositional_deconstruction": {
            "elements": [
                {
                    "type": "obj",
                    "bbox": [100, 200, 800, 700],
                    "desc": "subject",
                    "color_palette": ["#FAD6B1"],
                }
            ],
        },
    })

    prompt, positive, negative = prompt_io.build_outputs(
        "ideogram4",
        "json",
        positive=raw,
        final_prompt=raw,
        negative="",
        negative_enabled=False,
        disable_color_palette=True,
    )
    parsed_prompt = json.loads(prompt)
    parsed_positive = json.loads(positive)

    assert "color_palette" not in parsed_prompt["style_description"]
    assert "color_palette" not in parsed_prompt["compositional_deconstruction"]["elements"][0]
    assert parsed_positive == parsed_prompt
    assert negative == ""
    assert "color_palette" in raw


def test_json_generation_response_keeps_wrapper_negative_for_downstream_nodes():
    _profiles, prompt_io, _prompt_builder, _node, _profile_config = _load_package_modules()

    parsed = prompt_io.parse_generation_response(
        "flux2_dev",
        "json",
        '{"prompt_json":{"scene":"rainy street"},"negative":"blur, jitter"}',
        negative_enabled=True,
    )

    assert parsed["prompt"] == parsed["positive"]
    assert '"scene": "rainy street"' in parsed["prompt"]
    assert parsed["negative"] == "blur, jitter"


def test_video_prompt_builder_includes_video_fields_only_for_video_profiles():
    _profiles, _prompt_io, prompt_builder, _node, _profile_config = _load_package_modules()
    fields = {
        "idea": "cinematic chase",
        "video_duration_or_frames": "5 seconds at 24fps",
        "motion_action": "runner vaults over a barrier",
        "temporal_beats": "start wide, push in, final close-up",
        "camera_movement": "handheld tracking shot",
        "audio_dialogue": "heavy breathing and distant sirens",
        "reference_or_control_notes": "use reference image for character identity",
    }

    wan_prompt = prompt_builder.build_user_prompt(fields, target_model="wan2_2")
    image_prompt = prompt_builder.build_user_prompt(fields, target_model="sdxl")

    assert "Video duration / frame target: 5 seconds at 24fps" in wan_prompt
    assert "Motion / action: runner vaults over a barrier" in wan_prompt
    assert "Audio / dialogue: heavy breathing and distant sirens" in wan_prompt
    assert "Video duration / frame target" not in image_prompt
    assert "Motion / action" not in image_prompt


def test_prompt_builder_uses_simplified_prompt_text_and_retains_detail_level():
    _profiles, _prompt_io, prompt_builder, _node, _profile_config = _load_package_modules()

    prompt = prompt_builder.build_user_prompt(
        {
            "prompt_text": "A five-second locked shot of a woman walking along a beach.",
            "detail": "very high",
            "idea": "legacy value must not be merged",
        },
        target_model="wan2_2",
    )

    assert prompt.startswith("A five-second locked shot")
    assert "Detail level: very high" in prompt
    assert "legacy value must not be merged" not in prompt


def test_prompt_builder_uses_connected_raw_prompt_text_as_context():
    _profiles, _prompt_io, prompt_builder, _node, _profile_config = _load_package_modules()

    prompt = prompt_builder.build_user_prompt(
        {
            "idea": "ignore this idea",
            "subject": "ignore this subject",
            "raw_prompt_text": '{"scene":"raw upstream prompt"}',
            "extra_instructions": "keep final output concise",
        },
        target_model="flux2_dev",
    )

    assert '{"scene":"raw upstream prompt"}' in prompt
    assert "Idea: ignore this idea" not in prompt
    assert "Subject: ignore this subject" not in prompt
    assert "keep final output concise" not in prompt


def test_connected_raw_prompt_text_overrides_manual_text_but_keeps_detail_level():
    _profiles, _prompt_io, prompt_builder, _node, _profile_config = _load_package_modules()

    prompt = prompt_builder.build_user_prompt(
        {
            "prompt_text": "manual prompt should be ignored",
            "raw_prompt_text": "connected prompt wins",
            "detail": "balanced",
        },
        target_model="flux2_dev",
    )

    assert prompt.startswith("connected prompt wins")
    assert "manual prompt should be ignored" not in prompt
    assert "Detail level: balanced" in prompt


def test_prompt_builder_adds_bbox_layout_hints_for_bbox_targets_only():
    _profiles, _prompt_io, prompt_builder, _node, _profile_config = _load_package_modules()
    fields = {
        "idea": "poster",
        "bbox_layout": '{"compositional_deconstruction":{"elements":[]}}',
        "ideogram_palette": "#ffffff",
    }

    krea2_prompt = prompt_builder.build_user_prompt(fields, target_model="krea2")
    ideogram_prompt = prompt_builder.build_user_prompt(
        {"idea": "poster", "ideogram_layout": fields["bbox_layout"]},
        target_model="ideogram4",
    )
    sdxl_prompt = prompt_builder.build_user_prompt(fields, target_model="sdxl")

    assert "Layout JSON:" in krea2_prompt
    assert "Palette: #ffffff" in krea2_prompt
    assert "Layout JSON:" in ideogram_prompt
    assert "Layout JSON:" not in sdxl_prompt


def test_wan_and_ltx_response_parsing_for_positive_and_negative():
    _profiles, prompt_io, _prompt_builder, _node, _profile_config = _load_package_modules()

    wan = prompt_io.parse_generation_response(
        "wan2_2",
        "natural",
        '{"positive":"A tracking shot of a runner crossing a neon alley.","negative":"jitter, flicker"}',
        negative_enabled=True,
    )
    ltx = prompt_io.parse_generation_response(
        "ltx_2_3",
        "natural",
        '{"positive":"A detailed chronological shot of a performer entering frame.","negative":""}',
        negative_enabled=False,
    )

    assert wan["prompt"] == "Positive:\nA tracking shot of a runner crossing a neon alley.\n\nNegative:\njitter, flicker"
    assert wan["negative"] == "jitter, flicker"
    assert ltx["prompt"] == "A detailed chronological shot of a performer entering frame."
    assert ltx["negative"] == ""


def test_profile_config_loads_and_recreates_node_local_json_when_missing():
    _profiles, _prompt_io, _prompt_builder, _node, profile_config = _load_package_modules()
    with _with_temp_profile_paths(profile_config):
        payload = profile_config.profile_config_payload()

        assert payload["version"] == 7
        assert profile_config.config_path().exists()
        assert profile_config.config_path().name == "model_prompt_profiles.json"
        assert "ideogram4" in [profile["key"] for profile in payload["profiles"]]


def test_profile_config_backs_up_prior_schema_and_installs_v7_defaults():
    _profiles, _prompt_io, _prompt_builder, _node, profile_config = _load_package_modules()
    with _with_temp_profile_paths(profile_config):
        old = {"version": 4, "profiles": [{"key": "development-era"}]}
        profile_config.config_path().write_text(json.dumps(old), encoding="utf-8")
        loaded = profile_config.load_config()
        backup = profile_config.config_path().with_name("model_prompt_profiles.v4.backup.json")
        assert loaded["version"] == 7
        assert backup.exists()
        assert json.loads(backup.read_text(encoding="utf-8")) == old
        assert {profile["key"] for profile in loaded["profiles"]} >= {"ideogram4", "sdxl"}
        assert "jsonx" not in {profile["key"] for profile in loaded["profiles"]}


def test_profile_config_appends_new_default_profiles_without_overwriting_existing_config():
    _profiles, _prompt_io, _prompt_builder, _node, profile_config = _load_package_modules()
    with _with_temp_profile_paths(profile_config):
        custom = profile_config.default_config()
        custom["profiles"] = [
            {
                **custom["profiles"][0],
                "notes": "user edited ideogram notes",
            }
        ]
        profile_config.config_path().write_text(json.dumps(custom), encoding="utf-8")

        loaded = profile_config.load_config()
        profiles_by_key = {profile["key"]: profile for profile in loaded["profiles"]}

        assert profiles_by_key["ideogram4"]["notes"] == "user edited ideogram notes"
        assert "minimax_h3_official" in profiles_by_key
        assert "minimax_h3_alternate" in profiles_by_key


def test_profile_config_rejects_invalid_save_without_overwriting_prior_config():
    _profiles, _prompt_io, _prompt_builder, _node, profile_config = _load_package_modules()
    with _with_temp_profile_paths(profile_config):
        valid = profile_config.default_config()
        profile_config.save_config(valid)
        before = profile_config.config_path().read_text(encoding="utf-8")
        broken = json.loads(before)
        broken["profiles"][0]["formats"]["json"]["common_rules"]["text"] = ""

        try:
            profile_config.save_config(broken)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid profile save should fail")

        assert profile_config.config_path().read_text(encoding="utf-8") == before


def test_profile_config_rejects_development_era_profile_without_v7_paths():
    _profiles, _prompt_io, _prompt_builder, _node, profile_config = _load_package_modules()
    with _with_temp_profile_paths(profile_config):
        legacy = {
            "profiles": [{
                "key": "legacy_model",
                "label": "Legacy Model",
                "formats": ["natural"],
                "default_format": "natural",
                "negative_supported": True,
                "json_supported": False,
                "media_type": "image",
                "notes": "Legacy notes.",
                "system_prompt_template": "Legacy system prompt for {target_label}. {output_contract}",
            }]
        }
        try:
            profile_config.save_config(legacy)
        except ValueError as error:
            assert "generation path" in str(error)
        else:
            raise AssertionError("Development-era profile data must not be silently migrated into schema v7.")


def test_apply_layout_output_contract_uses_raw_json_as_prompt_and_positive():
    _profiles, prompt_io, _prompt_builder, _node, _profile_config = _load_package_modules()
    layout = '{"high_level_description":"poster"}'

    prompt, positive, negative = prompt_io.build_layout_apply_outputs(
        layout,
        negative="blur",
        negative_enabled=True,
    )
    prompt2, positive2, negative2 = prompt_io.build_layout_apply_outputs(
        layout,
        negative="blur",
        negative_enabled=False,
    )

    assert prompt == layout
    assert positive == layout
    assert negative == "blur"
    assert prompt2 == layout
    assert positive2 == layout
    assert negative2 == ""


def test_openai_backend_lists_compatible_models_with_optional_auth():
    openai_backend = _load_openai_backend()
    calls = []

    def fake_get(url, headers, timeout):
        calls.append((url, headers, timeout))
        return _FakeResponse({
            "data": [
                {"id": "text-embedding-3-large"},
                {"id": "gpt-image-1"},
                {"id": "gpt-4.1"},
                {"id": "o3-mini"},
            ]
        })

    original_get = openai_backend.requests.get
    try:
        openai_backend.requests.get = fake_get
        models = openai_backend.list_models("http://localhost:1234/v1", "", timeout=42)
        models_with_key = openai_backend.list_models("http://localhost:3000/api", "sk-test", timeout=12)
    finally:
        openai_backend.requests.get = original_get

    assert calls == [
        ("http://localhost:1234/v1/models", {"Content-Type": "application/json"}, 42),
        (
            "http://localhost:3000/api/models",
            {"Content-Type": "application/json", "Authorization": "Bearer sk-test"},
            12,
        ),
    ]
    assert models == [
        {"id": "gpt-4.1", "display_name": "gpt-4.1"},
        {"id": "o3-mini", "display_name": "o3-mini"},
    ]
    assert models_with_key == models


def test_openai_backend_generates_chat_completions_text_with_optional_image():
    openai_backend = _load_openai_backend()
    calls = []

    def fake_get(url, headers, timeout):
        assert url == "http://localhost:1234/api/v1/models"
        return _FakeResponse({
            "models": [{
                "key": "gpt-4.1",
                "display_name": "Local GPT 4.1",
                "loaded_instances": [{"id": "instance-gpt-4.1"}],
            }]
        })

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if url.endswith("/api/v1/chat"):
            return _FakeResponse({
                "model_instance_id": "instance-gpt-4.1",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "{\"positive\":\"cinematic portrait\"}"}]}],
            })
        return _FakeResponse({"status": "unloaded"})

    original_get = openai_backend.requests.get
    original_post = openai_backend.requests.post
    try:
        openai_backend.requests.get = fake_get
        openai_backend.requests.post = fake_post
        raw = openai_backend.generate(
            "http://localhost:1234/v1",
            "sk-test",
            "gpt-4.1",
            "system prompt",
            "user prompt",
            pil_image=Image.new("RGB", (1, 1), color=(255, 0, 0)),
            timeout=33,
            server_type="lm_studio",
            lifecycle="unload_after",
        )
    finally:
        openai_backend.requests.get = original_get
        openai_backend.requests.post = original_post

    assert raw == "{\"positive\":\"cinematic portrait\"}"
    assert calls[0]["url"] == "http://localhost:1234/api/v1/chat"
    assert calls[0]["headers"] == {"Authorization": "Bearer sk-test", "Content-Type": "application/json"}
    assert calls[0]["timeout"] == 33
    assert calls[0]["json"]["model"] == "gpt-4.1"
    assert calls[0]["json"]["stream"] is False
    assert calls[0]["json"]["store"] is False
    assert calls[0]["json"]["system_prompt"] == "system prompt"
    assert calls[0]["json"]["input"][0] == {"type": "message", "content": "user prompt"}
    assert calls[0]["json"]["input"][1]["type"] == "image"
    assert calls[0]["json"]["input"][1]["data_url"].startswith("data:image/png;base64,")
    assert calls[1] == {
        "url": "http://localhost:1234/api/v1/models/unload",
        "headers": {"Authorization": "Bearer sk-test", "Content-Type": "application/json"},
        "json": {"instance_id": "instance-gpt-4.1"},
        "timeout": 33,
    }


def test_openai_backend_generates_chat_completions_with_multiple_images():
    openai_backend = _load_openai_backend()
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "json": json})
        return _FakeResponse({"choices": [{"message": {"content": "refined prompt"}}]})

    original_post = openai_backend.requests.post
    try:
        openai_backend.requests.post = fake_post
        raw = openai_backend.generate(
            "http://localhost:1234/v1",
            "",
            "vision-model",
            "system prompt",
            "user prompt",
            pil_images=[
                Image.new("RGB", (1, 1), color=(255, 0, 0)),
                Image.new("RGB", (1, 1), color=(0, 255, 0)),
            ],
        )
    finally:
        openai_backend.requests.post = original_post

    assert raw == "refined prompt"
    content = calls[0]["json"]["messages"][1]["content"]
    assert content[0] == {"type": "text", "text": "user prompt"}
    assert [item["type"] for item in content[1:]] == ["image_url", "image_url"]


def test_gemini_backend_sends_safety_defaults_and_multiple_images():
    gemini_backend = _load_gemini_backend()
    calls = []

    def fake_post(url, params, json, timeout):
        calls.append({"url": url, "params": params, "json": json, "timeout": timeout})
        return _FakeResponse({"candidates": [{"content": {"parts": [{"text": "{\"positive\":\"ok\"}"}]}}]})

    original_post = gemini_backend.requests.post
    try:
        gemini_backend.requests.post = fake_post
        raw = gemini_backend.generate(
            "gem-key",
            "gemini-test",
            "system prompt",
            "user prompt",
            prompt_format="json",
            pil_images=[
                Image.new("RGB", (1, 1), color=(255, 0, 0)),
                Image.new("RGB", (1, 1), color=(0, 255, 0)),
            ],
            safety_settings={
                "safety_harassment": "BLOCK_NONE",
                "safety_hate_speech": "BLOCK_NONE",
                "safety_sexual": "BLOCK_NONE",
                "safety_dangerous": "BLOCK_NONE",
            },
            timeout=77,
        )
    finally:
        gemini_backend.requests.post = original_post

    assert raw == "{\"positive\":\"ok\"}"
    body = calls[0]["json"]
    assert calls[0]["url"].endswith("/models/gemini-test:generateContent")
    assert calls[0]["params"] == {"key": "gem-key"}
    assert calls[0]["timeout"] == 77
    assert body["contents"][0]["parts"][0] == {"text": "user prompt"}
    assert body["generationConfig"] == {"responseMimeType": "application/json"}
    assert len([part for part in body["contents"][0]["parts"] if "inline_data" in part]) == 2
    assert body["safetySettings"] == [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]


def test_gemini_backend_omits_json_mime_for_natural_outputs():
    gemini_backend = _load_gemini_backend()
    calls = []

    def fake_post(url, params, json, timeout):
        calls.append({"url": url, "params": params, "json": json, "timeout": timeout})
        return _FakeResponse({"candidates": [{"content": {"parts": [{"text": "plain MiniMax prompt"}]}}]})

    original_post = gemini_backend.requests.post
    try:
        gemini_backend.requests.post = fake_post
        raw = gemini_backend.generate(
            "gem-key",
            "gemini-test",
            "system prompt",
            "user prompt",
            prompt_format="natural",
            timeout=77,
        )
    finally:
        gemini_backend.requests.post = original_post

    assert raw == "plain MiniMax prompt"
    body = calls[0]["json"]
    assert "generationConfig" not in body


def test_grok_backend_discovers_language_models_and_context_capabilities():
    grok_backend = _load_grok_backend()
    calls = []

    def fake_get(url, headers, timeout):
        calls.append(url)
        assert headers["Authorization"] == "Bearer xai-test"
        if url.endswith("/language-models"):
            return _FakeResponse({"models": [
                {
                    "id": "grok-4.6-vision",
                    "input_modalities": ["text", "image"],
                    "output_modalities": ["text"],
                    "aliases": ["grok-latest"],
                },
                {"id": "grok-image-only", "input_modalities": ["text"], "output_modalities": ["image"]},
            ]})
        if url.endswith("/models"):
            return _FakeResponse({"data": [{"id": "grok-4.6-vision", "context_length": 131072}]})
        raise AssertionError(url)

    original_get = grok_backend.requests.get
    try:
        grok_backend.requests.get = fake_get
        models = grok_backend.list_models("xai-test", timeout=31)
    finally:
        grok_backend.requests.get = original_get

    assert calls == ["https://api.x.ai/v1/language-models", "https://api.x.ai/v1/models"]
    assert models == [{
        "id": "grok-4.6-vision",
        "display_name": "grok-4.6-vision",
        "aliases": ["grok-latest"],
        "vision": True,
        "input_modalities": ["text", "image"],
        "output_modalities": ["text"],
        "context_length": 131072,
        "reasoning_options": ["default", "low", "medium", "high", "xhigh"],
    }]


def test_grok_backend_uses_responses_structured_output_cache_and_sanitized_usage():
    grok_backend = _load_grok_backend()
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return _FakeResponse({
            "model": "grok-4.6-vision",
            "status": "completed",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "{\"prompt_json\":{}}"}]}],
            "usage": {
                "input_tokens": 120,
                "output_tokens": 44,
                "total_tokens": 164,
                "input_tokens_details": {"cached_tokens": 80},
                "output_tokens_details": {"reasoning_tokens": 12},
            },
        })

    original_post = grok_backend.requests.post
    try:
        grok_backend.requests.post = fake_post
        raw = grok_backend.generate(
            "xai-secret",
            "grok-4.6-vision",
            "selected system rules",
            "user prompt",
            pil_images=[Image.new("RGB", (1, 1), color=(1, 2, 3))],
            timeout=42,
            prompt_format="json",
            max_output_tokens=2048,
            temperature=0.4,
            top_p=0.9,
            reasoning_effort="xhigh",
            prompt_cache_key="stable-cache-key",
        )
    finally:
        grok_backend.requests.post = original_post

    assert raw == '{"prompt_json":{}}'
    call = calls[0]
    assert call["url"] == "https://api.x.ai/v1/responses"
    assert call["headers"]["Authorization"] == "Bearer xai-secret"
    body = call["json"]
    assert body["store"] is False
    assert body["text"] == {"format": {"type": "json_object"}}
    assert body["reasoning"] == {"effort": "xhigh"}
    assert body["prompt_cache_key"] == "stable-cache-key"
    assert body["max_output_tokens"] == 2048
    assert body["temperature"] == 0.4
    assert body["top_p"] == 0.9
    assert body["input"][0] == {"role": "system", "content": "selected system rules"}
    assert body["input"][1]["content"][0] == {"type": "input_text", "text": "user prompt"}
    assert body["input"][1]["content"][1]["type"] == "input_image"
    for forbidden in ("tools", "web_search", "x_search", "citations", "conversation", "encrypted_reasoning"):
        assert forbidden not in body
    assert raw.diagnostics == {
        "provider": "grok", "model": "grok-4.6-vision", "status": "completed",
        "input_tokens": 120, "output_tokens": 44, "reasoning_tokens": 12,
        "cached_tokens": 80, "total_tokens": 164,
    }


def test_grok_backend_rejects_reasoning_effort_not_supported_by_model():
    grok_backend = _load_grok_backend()
    try:
        grok_backend.generate("xai-test", "grok-plain", "system", "user", reasoning_effort="xhigh")
    except ValueError as error:
        assert "does not advertise" in str(error)
    else:
        raise AssertionError("Unsupported Grok reasoning effort must fail before dispatch.")


def test_deepseek_backend_discovers_text_and_vision_models_with_current_limits():
    backend = _load_deepseek_backend()
    calls = []

    def fake_get(url, headers, timeout):
        calls.append({"url": url, "headers": headers, "timeout": timeout})
        return _FakeResponse({"object": "list", "data": [
            {"id": "deepseek-v4-pro", "object": "model", "owned_by": "deepseek"},
            {"id": "deepseek-v4-flash", "object": "model", "owned_by": "deepseek"},
            {"id": "deepseek-v4-flash-vision-exp", "object": "model", "owned_by": "deepseek"},
        ]})

    original_get = backend.requests.get
    try:
        backend.requests.get = fake_get
        models = backend.list_models("deepseek-secret", timeout=27)
    finally:
        backend.requests.get = original_get

    assert calls == [{
        "url": "https://api.deepseek.com/models",
        "headers": {"Authorization": "Bearer deepseek-secret", "Content-Type": "application/json"},
        "timeout": 27,
    }]
    assert [model["id"] for model in models] == [
        "deepseek-v4-flash", "deepseek-v4-flash-vision-exp", "deepseek-v4-pro",
    ]
    for model in models:
        assert model["context_length"] == 1_000_000
        assert model["max_output_tokens"] == 384 * 1024
        assert model["thinking_options"] == ["default", "enabled", "disabled"]
        assert model["reasoning_options"] == ["default", "low", "high", "max"]
    assert next(model for model in models if model["id"].endswith("vision-exp"))["vision"] is True
    assert next(model for model in models if model["id"] == "deepseek-v4-pro")["vision"] is False


def test_deepseek_backends_use_chat_completions_and_keep_reasoning_private():
    standard = _load_deepseek_backend()
    _load_package_modules()
    engine = importlib.import_module("workflowx_unified_autoprompter_test.jsonx_profile.engine")
    private = engine.deepseek_backend

    for backend in (standard, private):
        calls = []

        def fake_post(url, headers, json, timeout):
            calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
            return _FakeResponse({
                "model": "deepseek-v4-flash",
                "system_fingerprint": "fp_test",
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": '{"prompt_json":{}}', "reasoning_content": "private chain"},
                }],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 25,
                    "prompt_cache_hit_tokens": 80,
                    "prompt_cache_miss_tokens": 20,
                    "total_tokens": 125,
                    "completion_tokens_details": {"reasoning_tokens": 9},
                },
            })

        original_post = backend.requests.post
        try:
            backend.requests.post = fake_post
            kwargs = {
                "timeout": 41,
                "max_tokens": 4096,
                "thinking": "enabled",
                "reasoning_effort": "max",
                "temperature": 0.2,
                "top_p": 0.8,
            }
            if backend is standard:
                kwargs["prompt_format"] = "json"
            else:
                kwargs["response_format"] = "json"
            raw = backend.generate(
                "deepseek-secret", "deepseek-v4-flash", "selected system", "user prompt", **kwargs
            )
        finally:
            backend.requests.post = original_post

        assert raw == '{"prompt_json":{}}'
        body = calls[0]["json"]
        assert calls[0]["url"] == "https://api.deepseek.com/chat/completions"
        assert body["messages"] == [
            {"role": "system", "content": "selected system"},
            {"role": "user", "content": "user prompt"},
        ]
        assert body["stream"] is False
        assert body["response_format"] == {"type": "json_object"}
        assert body["thinking"] == {"type": "enabled"}
        assert body["reasoning_effort"] == "max"
        assert body["max_tokens"] == 4096
        assert "temperature" not in body
        assert "top_p" not in body
        assert "reasoning_content" not in str(raw)
        assert raw.diagnostics["cache_hit_tokens"] == 80
        assert raw.diagnostics["cache_miss_tokens"] == 20
        assert raw.diagnostics["reasoning_tokens"] == 9
        assert raw.diagnostics["finish_reason"] == "stop"


def test_deepseek_non_thinking_sampling_and_image_rejection_are_explicit():
    backend = _load_deepseek_backend()
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append(json)
        return _FakeResponse({
            "model": "deepseek-v4-pro",
            "choices": [{"finish_reason": "stop", "message": {"content": "final prompt"}}],
            "usage": {},
        })

    original_post = backend.requests.post
    try:
        backend.requests.post = fake_post
        raw = backend.generate(
            "deepseek-secret", "deepseek-v4-pro", "system", "user",
            thinking="disabled", reasoning_effort="max", temperature=0.3, top_p=0.75,
        )
    finally:
        backend.requests.post = original_post
    assert raw == "final prompt"
    assert calls[0]["thinking"] == {"type": "disabled"}
    assert calls[0]["temperature"] == 0.3
    assert calls[0]["top_p"] == 0.75
    assert "reasoning_effort" not in calls[0]

    try:
        backend.generate(
            "deepseek-secret", "deepseek-v4-flash", "system", "user",
            pil_images=[Image.new("RGB", (1, 1))],
        )
    except ValueError as error:
        assert "does not accept image input" in str(error)
    else:
        raise AssertionError("A text-only DeepSeek model must reject image input before dispatch.")


def test_deepseek_vision_model_sends_ordered_inline_images_in_both_isolated_backends():
    standard = _load_deepseek_backend()
    _load_package_modules()
    engine = importlib.import_module("workflowx_unified_autoprompter_test.jsonx_profile.engine")

    for backend in (standard, engine.deepseek_backend):
        calls = []

        def fake_post(url, headers, json, timeout):
            calls.append(json)
            return _FakeResponse({
                "model": "deepseek-v4-flash-vision-exp",
                "choices": [{"finish_reason": "stop", "message": {"content": "vision prompt"}}],
                "usage": {},
            })

        original_post = backend.requests.post
        try:
            backend.requests.post = fake_post
            kwargs = {
                "pil_images": [Image.new("RGB", (2, 2), "red"), Image.new("RGB", (2, 2), "blue")],
                "image_detail": "low",
            }
            kwargs["prompt_format" if backend is standard else "response_format"] = "natural"
            raw = backend.generate(
                "deepseek-secret",
                "deepseek-v4-flash-vision-exp",
                "system",
                "inspect both images",
                **kwargs,
            )
        finally:
            backend.requests.post = original_post

        assert raw == "vision prompt"
        content = calls[0]["messages"][1]["content"]
        assert content[0] == {"type": "text", "text": "inspect both images"}
        assert len(content) == 3
        assert all(item["type"] == "image_url" for item in content[1:])
        assert all(item["image_url"]["url"].startswith("data:image/png;base64,") for item in content[1:])
        assert all(item["image_url"]["detail"] == "low" for item in content[1:])


def test_unified_jsonx_dispatches_through_its_private_deepseek_adapter():
    _load_package_modules()
    engine = importlib.import_module("workflowx_unified_autoprompter_test.jsonx_profile.engine")
    calls = []

    def fake_generate(api_key, model, system_prompt, user_prompt, **kwargs):
        calls.append((api_key, model, system_prompt, user_prompt, kwargs))
        return '{"scene":{"environment":"coastal beach"}}'

    original = engine.deepseek_backend.generate
    try:
        engine.deepseek_backend.generate = fake_generate
        raw = engine._call_provider(
            {
                "backend": "deepseek",
                "api_key": "deepseek-secret",
                "model": "deepseek-v4-pro",
                "timeout": 44,
                "deepseek_max_tokens": 4096,
                "deepseek_thinking": "enabled",
                "deepseek_reasoning_effort": "high",
                "deepseek_temperature": 0.4,
                "deepseek_top_p": 0.9,
                "_deepseek_response_format": "json",
            },
            "jsonx system",
            "jsonx user",
            None,
        )
    finally:
        engine.deepseek_backend.generate = original

    assert raw == '{"scene":{"environment":"coastal beach"}}'
    assert calls == [(
        "deepseek-secret",
        "deepseek-v4-pro",
        "jsonx system",
        "jsonx user",
        {
            "pil_images": [],
            "timeout": 44.0,
            "response_format": "json",
            "max_tokens": 4096,
            "thinking": "enabled",
            "reasoning_effort": "high",
            "temperature": 0.4,
            "top_p": 0.9,
            "image_detail": "default",
        },
    )]


def test_grok_prompt_cache_key_excludes_user_content_and_credentials():
    routes = _load_routes_module()
    base = {
        "grok_prompt_cache": "auto",
        "target_model": "wan2_2",
        "generation_type": "text_to_video",
        "prompt_format": "natural",
        "api_key": "secret-one",
        "fields": {"prompt_text": "first private prompt"},
    }
    changed_private_data = {
        **base,
        "api_key": "secret-two",
        "fields": {"prompt_text": "different private prompt"},
        "images_b64": ["private-image"],
    }
    first = routes._prompt_cache_key(base, "stable selected rules", "single")
    second = routes._prompt_cache_key(changed_private_data, "stable selected rules", "single")
    different_rules = routes._prompt_cache_key(base, "changed selected rules", "single")
    assert first == second
    assert first != different_rules
    assert routes._prompt_cache_key({**base, "grok_prompt_cache": "off"}, "stable selected rules") == ""


def test_openai_backend_ignores_unload_failures_after_generation(capsys):
    openai_backend = _load_openai_backend()
    calls = []

    def fake_get(url, headers, timeout):
        return _FakeResponse({
            "models": [{
                "key": "local-model",
                "loaded_instances": [{"id": "loaded-local-model"}],
            }]
        })

    def fake_post(url, headers, json, timeout):
        calls.append(url)
        if url.endswith("/api/v1/chat"):
            return _FakeResponse({
                "model_instance_id": "loaded-local-model",
                "output": [{"type": "message", "content": "refined prompt"}],
            })
        raise RuntimeError("server does not expose LM Studio unload")

    original_get = openai_backend.requests.get
    original_post = openai_backend.requests.post
    try:
        openai_backend.requests.get = fake_get
        openai_backend.requests.post = fake_post
        raw = openai_backend.generate(
            "http://localhost:3000/api",
            "",
            "local-model",
            "system prompt",
            "user prompt",
            timeout=11,
            server_type="lm_studio",
            lifecycle="unload_after",
        )
    finally:
        openai_backend.requests.get = original_get
        openai_backend.requests.post = original_post

    assert raw == "refined prompt"
    assert calls == [
        "http://localhost:3000/api/v1/chat",
        "http://localhost:3000/api/v1/models/unload",
    ]
    warning = capsys.readouterr().out
    assert "Warning: lm_studio model unload failed" in warning
    assert "generation output was kept" in warning


def test_openai_backend_auto_discovers_lm_studio_models_and_capabilities():
    openai_backend = _load_openai_backend()
    calls = []

    def fake_get(url, headers, timeout):
        calls.append(url)
        if url == "http://localhost:1234/v1/models":
            return _FakeResponse({"data": [{"id": "fallback-model"}]})
        if url.endswith("/api/inference/status"):
            return _FakeResponse({}, status_code=404)
        if url.endswith("/api/v1/models"):
            return _FakeResponse({
                "models": [{
                    "key": "reasoning-vision-model",
                    "display_name": "Reasoning Vision Model",
                    "capabilities": {
                        "vision": True,
                        "reasoning": {
                            "allowed_options": ["off", "low", "medium", "high"],
                            "default": "medium",
                        },
                    },
                    "loaded_instances": [{"id": "instance-123"}],
                }]
            })
        raise AssertionError(url)

    original_get = openai_backend.requests.get
    try:
        openai_backend.requests.get = fake_get
        discovery = openai_backend.discover_models("http://localhost:1234/v1", server_type="auto")
    finally:
        openai_backend.requests.get = original_get

    assert discovery["server_type"] == "lm_studio"
    assert discovery["models"] == [{
        "id": "reasoning-vision-model",
        "display_name": "Reasoning Vision Model",
        "loaded": True,
        "instance_id": "instance-123",
        "vision": True,
        "reasoning_options": ["off", "low", "medium", "high"],
        "reasoning_default": "medium",
    }]
    assert calls == [
        "http://localhost:1234/v1/models",
        "http://localhost:1234/api/inference/status",
        "http://localhost:1234/api/v1/models",
    ]


def test_openai_backend_auto_discovers_unsloth_reasoning_capabilities():
    openai_backend = _load_openai_backend()

    def fake_get(url, headers, timeout):
        if url == "http://localhost:8000/v1/models":
            return _FakeResponse({"data": [{"id": "unsloth-model"}]})
        if url.endswith("/api/inference/status"):
            return _FakeResponse({
                "supports_reasoning": True,
                "reasoning_style": "effort",
                "reasoning_effort_levels": ["none", "low", "medium", "high", "xhigh"],
                "reasoning_always_on": False,
                "supports_preserve_thinking": True,
            })
        raise AssertionError(url)

    original_get = openai_backend.requests.get
    try:
        openai_backend.requests.get = fake_get
        discovery = openai_backend.discover_models("http://localhost:8000/v1", server_type="auto")
    finally:
        openai_backend.requests.get = original_get

    assert discovery["server_type"] == "unsloth"
    assert discovery["models"] == [{"id": "unsloth-model", "display_name": "unsloth-model"}]
    assert discovery["reasoning"]["supported"] is True
    assert discovery["reasoning"]["style"] == "effort"
    assert discovery["reasoning"]["options"] == ["none", "low", "medium", "high", "xhigh"]
    assert discovery["reasoning"]["always_on"] is False
    assert discovery["reasoning"]["supports_preserve_thinking"] is True


def test_openai_backends_send_unsloth_reasoning_and_unload_independently():
    standard_backend = _load_openai_backend()
    _load_package_modules()
    engine = importlib.import_module("workflowx_unified_autoprompter_test.jsonx_profile.engine")
    private_backend = engine.openai_backend

    for backend in (standard_backend, private_backend):
        calls = []

        def fake_post(url, headers, json, timeout):
            calls.append({"url": url, "json": json})
            if url.endswith("/chat/completions"):
                return _FakeResponse({
                    "choices": [{"message": {"content": "<think>hidden</think>usable prompt"}}]
                })
            return _FakeResponse({"status": "unloaded"})

        original_post = backend.requests.post
        try:
            backend.requests.post = fake_post
            raw = backend.generate(
                "http://localhost:8000/v1",
                "",
                "unsloth-model",
                "system prompt",
                "user prompt",
                server_type="unsloth",
                lifecycle="unload_after",
                reasoning_effort="xhigh",
            )
        finally:
            backend.requests.post = original_post

        assert raw == "usable prompt"
        assert calls[0]["url"] == "http://localhost:8000/v1/chat/completions"
        assert calls[0]["json"]["enable_thinking"] is True
        assert calls[0]["json"]["reasoning_effort"] == "xhigh"
        assert calls[1] == {
            "url": "http://localhost:8000/api/inference/unload",
            "json": {"model_path": "unsloth-model"},
        }


def test_openai_backends_use_lm_studio_native_reasoning_and_instance_unload():
    standard_backend = _load_openai_backend()
    _load_package_modules()
    engine = importlib.import_module("workflowx_unified_autoprompter_test.jsonx_profile.engine")
    private_backend = engine.openai_backend

    for backend in (standard_backend, private_backend):
        calls = []

        def fake_post(url, headers, json, timeout):
            calls.append({"url": url, "json": json})
            if url.endswith("/api/v1/chat"):
                return _FakeResponse({
                    "model_instance_id": "instance-native-1",
                    "model": "lm-model",
                    "output": [
                        {"type": "reasoning", "content": "private reasoning"},
                        {"type": "message", "content": "final visible prompt"},
                    ],
                    "stats": {
                        "input_tokens": 101,
                        "total_output_tokens": 52,
                        "reasoning_output_tokens": 11,
                        "tokens_per_second": 24.5,
                        "time_to_first_token_seconds": 0.4,
                        "model_load_time_seconds": 1.75,
                    },
                })
            return _FakeResponse({"status": "unloaded"})

        original_post = backend.requests.post
        try:
            backend.requests.post = fake_post
            raw = backend.generate(
                "http://localhost:1234/v1",
                "",
                "lm-model",
                "system prompt",
                "user prompt",
                server_type="lm_studio",
                lifecycle="unload_after",
                reasoning_effort="none",
            )
        finally:
            backend.requests.post = original_post

        assert raw == "final visible prompt"
        assert raw.diagnostics == {
            "provider": "lm_studio",
            "model": "lm-model",
            "input_tokens": 101,
            "output_tokens": 52,
            "reasoning_tokens": 11,
            "tokens_per_second": 24.5,
            "time_to_first_token": 0.4,
            "model_load_time": 1.75,
        }
        assert calls[0]["url"] == "http://localhost:1234/api/v1/chat"
        assert calls[0]["json"]["reasoning"] == "off"
        assert calls[1] == {
            "url": "http://localhost:1234/api/v1/models/unload",
            "json": {"instance_id": "instance-native-1"},
        }


def test_openai_generic_unload_is_console_warning_only(capsys):
    openai_backend = _load_openai_backend()
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append(url)
        return _FakeResponse({"choices": [{"message": {"content": "successful prompt"}}]})

    original_post = openai_backend.requests.post
    try:
        openai_backend.requests.post = fake_post
        raw = openai_backend.generate(
            "http://localhost:9000/v1",
            "",
            "generic-model",
            "system prompt",
            "user prompt",
            server_type="generic",
            lifecycle="unload_after",
        )
    finally:
        openai_backend.requests.post = original_post

    assert raw == "successful prompt"
    assert calls == ["http://localhost:9000/v1/chat/completions"]
    warning = capsys.readouterr().out
    assert "Generic OpenAI-compatible model unload failed" in warning
    assert "generation output was kept" in warning


def test_refresh_comfy_vram_unloads_all_models_and_cache():
    routes = _load_routes_module()
    calls = []
    comfy = types.ModuleType("comfy")
    model_management = types.ModuleType("comfy.model_management")

    def unload_all_models():
        calls.append("unload_all_models")

    def soft_empty_cache(**kwargs):
        calls.append(("soft_empty_cache", kwargs))

    model_management.unload_all_models = unload_all_models
    model_management.soft_empty_cache = soft_empty_cache
    original_comfy = sys.modules.get("comfy")
    original_model_management = sys.modules.get("comfy.model_management")
    try:
        sys.modules["comfy"] = comfy
        sys.modules["comfy.model_management"] = model_management
        status = routes.refresh_comfy_vram()
    finally:
        if original_comfy is None:
            sys.modules.pop("comfy", None)
        else:
            sys.modules["comfy"] = original_comfy
        if original_model_management is None:
            sys.modules.pop("comfy.model_management", None)
        else:
            sys.modules["comfy.model_management"] = original_model_management

    assert calls == ["unload_all_models", ("soft_empty_cache", {"force": True})]
    assert "unloaded all models" in status
    assert "emptied cache" in status


def test_unified_additional_model_folders_are_recursive_and_safely_resolved(tmp_path):
    registry = _load_folder_registry()
    external = tmp_path / "LM Studio" / "models"
    nested = external / "publisher" / "Qwen"
    nested.mkdir(parents=True)
    model = nested / "qwen.gguf"
    projector = nested / "qwen-mmproj.gguf"
    model.write_bytes(b"model")
    projector.write_bytes(b"projector")

    catalog = registry.model_catalog(f'"{external}"; {external}')
    model_option = next(item for item in catalog["models"] if isinstance(item, dict))
    mmproj_option = next(item for item in catalog["mmproj"] if isinstance(item, dict))
    assert model_option["label"].endswith("publisher/Qwen/qwen.gguf")
    assert registry.full_model_path(model_option["value"], [str(external)]) == model
    assert registry.full_mmproj_path(mmproj_option["value"], [str(external)]) == projector
    assert catalog["additional_roots"] == 1

    try:
        registry.full_model_path(model_option["value"], [str(tmp_path / "other")])
    except FileNotFoundError as error:
        assert "no longer configured" in str(error)
    else:
        raise AssertionError("External selection must not resolve outside configured roots")


def test_unified_frontend_keeps_additional_model_folders_in_browser_storage():
    source = (ROOT / "web" / "js" / "unified_autoprompter.js").read_text(encoding="utf-8")
    assert "workflowx_unified_autoprompter_additional_local_model_paths" in source
    assert "Additional model folders (; separated)" in source
    assert "additional_model_paths: additionalLocalModelPaths" in source
    serializable_section = source.split("function serializableState(state)", 1)[1].split(
        "function positiveAndNegativePrompt", 1
    )[0]
    assert "additional_local_model_paths" not in serializable_section


def test_unified_frontend_collapses_provider_model_settings_and_refits_the_node():
    source = (ROOT / "web" / "js" / "unified_autoprompter.js").read_text(encoding="utf-8")
    assert 'buildDom("details", "workflowx-uap-model-settings")' in source
    assert 'buildDom("summary", "", "Model settings")' in source
    assert "modelSettingsBody.appendChild(geminiPanel)" in source
    assert "modelSettingsBody.appendChild(deepseekPanel)" in source
    assert "modelSettingsBody.appendChild(openaiPanel)" in source
    assert "modelSettingsBody.appendChild(ollamaPanel)" in source
    assert "modelSettingsBody.appendChild(localPanel)" in source
    assert "model_settings_open: Boolean(saved.model_settings_open)" in source
    assert 'modelSettingsDetails.addEventListener("toggle"' in source
    assert "scheduleVisibleContentResize();" in source
    assert 'modelSettingsBtn.textContent = "Profile settings"' in source
    assert 'modelSettingsBtn.addEventListener("click", openMarkdownProfileSettings)' in source
    assert 'const REFERENCE_SCHEMA_VERSION = 1' in source
    assert '"Common Profile Rules"' in source
    assert "openJsonXSettingsModal" not in source
    assert "Unified JsonX Settings" not in source
    assert "measureVisibleContentHeight" in source
    assert "const clone = wrap.cloneNode(true)" in source
    assert "wrap.scrollHeight" not in source


def test_unified_frontend_uses_one_persisted_prompt_editor_and_detail_selector():
    source = (ROOT / "web" / "js" / "unified_autoprompter.js").read_text(encoding="utf-8")
    input_surface = source.split('const promptArea = createTextarea(7);', 1)[1].split(
        'const connectedInputRow = buildDom("div", "workflowx-uap-row");', 1
    )[0]
    default_state = source.split("function defaultState(node)", 1)[1].split(
        "function serializableState(state)", 1
    )[0]

    assert 'field(wrap, "Prompt instructions", promptArea)' in input_surface
    assert 'field(wrap, "Detail level", detailSelect)' in input_surface
    for removed_label in (
        '"Idea"', '"Subject"', '"Style"', '"Lighting"', '"Camera / composition"',
        '"Text / typography"', '"Reference image note"', '"Video duration / frames"',
        '"Camera movement"', '"Motion / action"', '"Temporal beats"',
        '"Audio / dialogue"', '"Reference / control notes"', '"Extra instructions"',
    ):
        assert removed_label not in input_surface
    assert 'prompt_text: saved.prompt_text || ""' in default_state
    assert "idea: saved.idea" not in default_state
    assert "promptArea.placeholder = promptInstructionsPlaceholder(profile)" in source
    assert "prompt_text: state.prompt_text" in source
    assert "const hasTextSeed = Boolean(rawPromptText || String(state.prompt_text || \"\").trim())" in source


def test_unified_jsonx_field_compiler_uses_prompt_text_and_connected_override():
    _load_package_modules()
    routes = importlib.import_module("workflowx_unified_autoprompter_test.jsonx_profile.routes")

    manual = routes._instructions_from_fields({"prompt_text": "manual scene", "detail": "high"})
    connected = routes._instructions_from_fields({
        "prompt_text": "manual scene",
        "raw_prompt_text": "connected scene",
        "detail": "concise",
    })

    assert manual == "manual scene\nDetail level: high"
    assert connected == "connected scene\nDetail level: concise"
    assert "manual scene" not in connected


def test_unified_jsonx_request_payload_keeps_images_as_text_path_authoring_guidance():
    _load_package_modules()
    routes = importlib.import_module("workflowx_unified_autoprompter_test.jsonx_profile.routes")

    text_payload = routes._request_payload({
        "target_model": "jsonx",
        "generation_type": "text_to_image",
        "images_b64": ["image-1", "image-2"],
        "fields": {"prompt_text": "describe a scene", "detail": "high"},
    })
    assert text_payload["images_b64"] == ["image-1", "image-2"]
    assert text_payload["image_b64"] == "image-1"
    assert text_payload["_connected_image_count"] == 2
    assert text_payload["_ignored_image_count"] == 0
    assert text_payload["_submitted_image_count"] == 2
    assert text_payload["_image_state"] == "unsupported_with_image_guidance"
    engine = importlib.import_module("workflowx_unified_autoprompter_test.jsonx_profile.engine")
    preview = engine.effective_instruction_preview(text_payload)
    assert "combine relevant visible evidence" in preview["stage_one"]
    assert "image-reference commentary" in preview["stage_one"]

    image_payload = routes._request_payload({
        "target_model": "jsonx",
        "generation_type": "image_to_image",
        "images_b64": ["image-1", "image-2"],
        "fields": {"prompt_text": "describe the images", "detail": "high"},
    })
    assert image_payload["images_b64"] == ["image-1", "image-2"]
    assert image_payload["_ignored_image_count"] == 0
    assert image_payload["_submitted_image_count"] == 2
    assert image_payload["_image_state"] == "supported_with_image"


def test_connected_local_images_require_a_vision_mmproj_in_both_engines():
    _load_package_modules()
    engine = importlib.import_module("workflowx_unified_autoprompter_test.jsonx_profile.engine")
    image = Image.new("RGB", (8, 8), "white")
    try:
        engine._call_provider(
            {"backend": "local", "model": "model.gguf", "mmproj": "none"},
            "system",
            "user",
            [image],
        )
    except ValueError as error:
        assert "vision mmproj" in str(error)
    else:
        raise AssertionError("JsonX local generation must reject images without a vision mmproj.")

    standard_routes = (ROOT / "unified_autoprompter" / "routes.py").read_text(encoding="utf-8")
    frontend = (ROOT / "web" / "js" / "unified_autoprompter.js").read_text(encoding="utf-8")
    assert "Connected authoring images require a vision mmproj" in standard_routes
    assert "Connected authoring images require a compatible vision mmproj" in frontend


def test_unified_jsonx_profile_editor_shows_effective_packaged_instructions():
    source = (ROOT / "web" / "js" / "unified_autoprompter.js").read_text(encoding="utf-8")
    assert '`${JSONX_ROUTE}/reference_config`' in source
    assert "openJsonXMarkdownProfileSettings" in source
    assert "Complete JsonX preset catalog" in source
    assert "Adaptive ranked context" in source
    assert "Ranked presets — Recommended" in source
    assert "Full preset catalog" in source
    assert "JsonX construction method" in source
    assert "Natural output always uses two passes" in source
    assert "contextMode.disabled = !adaptive" in source
    assert "presets.disabled = adaptive" in source
    assert "depth.disabled = !adaptive && !templateRefinedJson" in source
    setup_names = [
        "Adaptive Balanced", "Adaptive Polished", "Adaptive Max",
        "Template Flex", "Template Catalog", "Custom",
    ]
    setup_source = source[source.index("const setupPresets ="):source.index("const matchingSetupPreset =")]
    setup_positions = [setup_source.index(f'"{name}"') for name in setup_names]
    assert setup_positions == sorted(setup_positions)
    assert 'overviewField("JsonX setup preset", setupPreset)' in source
    assert 'setupPreset.value = "custom"' in source

    _load_package_modules()
    engine = importlib.import_module("workflowx_unified_autoprompter_test.jsonx_profile.engine")
    templates = engine.instruction_templates()
    assert templates["jsonx_reference_schema_version"] == 1
    for key in ("stage_one_adaptive", "stage_one_template_fill", "stage_two_json_refinement", "stage_two_natural_conversion"):
        assert templates["editors"][key].strip()


def test_unified_jsonx_profiles_persist_engine_and_profile_owned_configuration():
    profiles, _prompt_io, _prompt_builder, _node, _profile_config = _load_package_modules()
    payload = profiles.profiles_payload()
    jsonx = next(profile for profile in payload["profiles"] if profile["key"] == "jsonx")
    assert jsonx["engine"] == "jsonx"
    assert jsonx["jsonx_config"]["generation_profile"] == "adaptive"
    assert set(jsonx["jsonx_config"]) == {
        "generation_profile", "generation_mode", "preset_context_mode",
        "template_use_presets", "enable_framing_and_placement", "detail_level",
    }


def test_unified_frontend_routes_shared_controls_to_isolated_jsonx_state():
    source = (ROOT / "web" / "js" / "unified_autoprompter.js").read_text(encoding="utf-8")
    assert 'return profile?.engine === "jsonx"' in source
    assert '`${jsonx ? JSONX_ROUTE : ROUTE}/gemini/models`' in source
    assert '`${jsonx ? JSONX_ROUTE : ROUTE}/deepseek/models`' in source
    assert '`${jsonx ? JSONX_ROUTE : ROUTE}/openai/models`' in source
    assert '`${jsonx ? JSONX_ROUTE : ROUTE}/ollama/models`' in source
    assert '`${jsonx ? JSONX_ROUTE : ROUTE}/local/models`' in source
    assert "persistJsonXProviderFromControls" in source
    assert "workflowx_unified_jsonx_gemini_api_key" in source
    assert "workflowx_unified_jsonx_openai_api_key" in source
    assert 'if (isJsonXProfile()) {\n      persistJsonXProviderFromControls();\n      return;' in source


def test_unified_preview_and_bbox_docks_follow_canvas_widget_stacking():
    source = (ROOT / "web" / "js" / "unified_autoprompter.js").read_text(encoding="utf-8")
    assert 'const widgetHost = root?.closest?.(".dom-widget")' in source
    assert 'layerHost?.classList?.contains("isolate")' in source
    assert "dock.style.zIndex = ownerZ" in source
    assert "if (!canvasLayer && dock.parentElement !== document.body)" in source
    assert "if (canvasLayer) return" in source
    assert "node.__workflowXUapRoot = wrap" in source


def test_unified_frontend_defers_custom_ui_until_workflow_state_is_configured():
    source = (ROOT / "web" / "js" / "unified_autoprompter.js").read_text(encoding="utf-8")
    registration = source.split("app.registerExtension({", 1)[1]
    created = registration.split('chainCallback(nodeType.prototype, "onNodeCreated"', 1)[1].split(
        'chainCallback(nodeType.prototype, "onConfigure"', 1
    )[0]
    configured = registration.split('chainCallback(nodeType.prototype, "onConfigure"', 1)[1]

    assert "setTimeout(() => setupUnifiedAutoprompter(this), 0)" in created
    assert "this.__workflowXUapRestoreState?.()" in configured
    assert "else setupUnifiedAutoprompter(this)" in configured
    assert "setupUnifiedAutoprompter(this);" not in created
    assert "function restoreWorkflowStateFromWidgets()" in source
    assert "Object.assign(state, defaultState(node), runtimeState)" in source
    assert "node.__workflowXUapRestoreState = restoreWorkflowStateFromWidgets" in source


def test_unified_frontend_exposes_provider_aware_openai_controls_and_discovery():
    source = (ROOT / "web" / "js" / "unified_autoprompter.js").read_text(encoding="utf-8")
    for label in (
        "Grok API",
        "DeepSeek API",
        "OpenAI Compatible",
        "LM Studio",
        "Unsloth Studio",
        "Ollama",
        "Local GGUF",
        "Server managed",
        "Keep loaded",
        "Unload after generation",
        "Provider / model default",
    ):
        assert label in source
    assert 'openai_server_type: normalizeOpenAIServerType(openaiServerTypeSelect.value)' in source
    assert 'openai_lifecycle: normalizeOpenAILifecycle(openaiLifecycleSelect.value)' in source
    assert 'openai_reasoning_effort: normalizeOpenAIReasoning(openaiReasoningSelect.value)' in source
    assert 'state.openai_model = (openaiModelSelect.value || openaiModelInput.value || "").trim()' in source
    assert "let openaiDiscoveryScope = null" in source
    assert 'const discoveryScope = isJsonXProfile() ? "jsonx" : "standard"' in source
    assert 'openaiDetectedServerType = "auto"' in source
    assert 'body: JSON.stringify({' in source
    assert "const FRONTEND_SCHEMA_VERSION = 7" in source
    assert 'field(topGrid, "Provider", providerSelect)' in source
    assert 'field(topGrid, "Generation type", generationTypeSelect)' in source
    assert "NSFW instructions" in source
    assert "Restart ComfyUI and hard-refresh the browser" in source
    assert '`${jsonx ? JSONX_ROUTE : ROUTE}/grok/models`' in source
    assert '`${jsonx ? JSONX_ROUTE : ROUTE}/deepseek/models`' in source
    assert '`${jsonx ? JSONX_ROUTE : ROUTE}/${kind}/models`' in source
    assert "syncGrokReasoningOptions" in source
    assert "syncDeepSeekControls" in source
    assert "deepseek-v4-flash-vision-exp" in source
    assert "Image detail" in source
    assert "Provider Default" in source
    for action in (
        "Fetch Gemini models",
        "Fetch xAI models",
        "Fetch DeepSeek models",
        "Fetch OpenAI-compatible models",
        "Fetch Ollama models",
    ):
        assert action in source
    assert '`Fetch ${kind === "lm_studio" ? "LM Studio" : "Unsloth Studio"} models`' in source
    assert "Fetch xAI language models" not in source


def test_unified_frontend_uses_effective_images_and_transparent_profile_editor_contracts():
    source = (ROOT / "web" / "js" / "unified_autoprompter.js").read_text(encoding="utf-8")
    markdown_surface = source.split("async function openMarkdownProfileSettings(forceEngine", 1)[1].split("function normalizeBoxFromBbox", 1)[0]
    assert "function effectiveGenerationImages" in source
    assert "const submitted = connected" in source
    assert 'imageState: rule?.supportsImages' in source
    assert "activeProviderPayload(true, images)" in source
    assert "activeProviderPayload(false, images)" in source
    assert "activated_blocks" in source
    assert "Local routing only" in source
    assert "Exact system text" in source
    assert 'const nsfwMode = buildDom("button", "", "Global NSFW Rules")' in source
    assert 'let editorMode = "profiles"' in source
    assert "function renderGlobalNsfw()" in source
    nsfw_surface = markdown_surface.split("function renderGlobalNsfw()", 1)[1].split("function renderPreview", 1)[0]
    assert '"nsfw-image.md"' in nsfw_surface
    assert '"nsfw-video.md"' in nsfw_surface
    assert "GENERATION_TYPES" not in nsfw_surface
    assert "function renderReferences(profile)" in source
    path_surface = markdown_surface.split("function renderPaths(profile)", 1)[1].split("function renderReferences", 1)[0]
    reference_surface = markdown_surface.split("function renderReferences(profile)", 1)[1].split("function renderContracts", 1)[0]
    assert "Supporting/" not in path_surface
    assert "with_reference_supported.md" in reference_surface
    assert "without_reference_supported.md" in reference_surface
    assert "without_reference_unsupported.md" in reference_surface
    assert '["references", "Reference Usage"]' in source
    assert '["common", "Common Profile Rules"]' in source
    assert "Exactly one profile-wide output contract" in source
    assert "${profile.key} · ${profile.engine}" not in source
    for marker in (
        "workflowx-uap-settings-card",
        "workflowx-uap-condition-badge",
        "Reference Usage",
        "Exact output contract",
        "reference/current_use",
    ):
        assert marker in source


def test_unified_frontend_v7_has_one_rules_and_guide_editor_and_all_jsonx_instruction_surfaces():
    source = (ROOT / "web" / "js" / "unified_autoprompter.js").read_text(encoding="utf-8")
    markdown_surface = source.split("async function openMarkdownProfileSettings(forceEngine", 1)[1].split("function normalizeBoxFromBbox", 1)[0]
    common_surface = markdown_surface.split("function renderCommon(profile)", 1)[1].split("function renderPaths", 1)[0]
    path_surface = markdown_surface.split("function renderPaths(profile)", 1)[1].split("function renderReferences", 1)[0]
    assert 'profilePath(profile, "split/common.md")' in common_surface
    assert common_surface.count("addExactEditor(") == 1
    assert "pathFile(profile, activePath)" in path_surface
    assert path_surface.count("addExactEditor(") == 1
    assert "common_rules" not in markdown_surface
    assert "common_guide" not in markdown_surface
    assert "path_rules" not in markdown_surface
    assert "path_guide" not in markdown_surface
    assert '["last_frame_to_video", "Last Frame to Video", 1, 1]' in source
    jsonx_surface = source.split("async function openJsonXMarkdownProfileSettings(requestedProfileKey", 1)[1].split(
        "async function openMarkdownProfileSettings(forceEngine", 1
    )[0]
    for key in (
        "stage_one_adaptive",
        "stage_one_template_fill",
        "stage_two_json_refinement",
        "stage_two_natural_conversion",
        "repair_json",
        "repair_natural",
        "user_stage_one",
        "user_json_refinement",
        "user_natural_conversion",
        "user_json_repair",
        "user_natural_repair",
        "depth_deep",
        "depth_exhaustive",
        "framing_json_enabled",
        "framing_json_disabled",
        "template_presets_enabled",
        "template_presets_disabled",
        "template_adaptive_ranked",
        "template_adaptive_full",
        "presets_full",
        "contract_stage_one_json",
        "contract_stage_two_natural",
    ):
        assert key in jsonx_surface


def test_unified_jsonx_workflow_state_snapshots_provider_models_and_profile_config_without_secrets():
    source = (ROOT / "web" / "js" / "unified_autoprompter.js").read_text(encoding="utf-8")
    provider_snapshot = source.split("function workflowJsonXProviderSettings", 1)[1].split(
        "function normalizeUnifiedReasoning", 1
    )[0]
    serializable = source.split("function serializableState(state)", 1)[1].split(
        "function positiveAndNegativePrompt", 1
    )[0]

    for field in ("backend", "gemini_model", "openai_model", "ollama_model", "local_model", "local_options"):
        assert field in provider_snapshot
    for private_field in ("api_key", "gemini_key", "openai_key", "additional_model_paths", "openai_base_url", "ollama_host"):
        assert private_field not in provider_snapshot

    assert "jsonx_provider: workflowJsonXProviderSettings(saved.jsonx_provider)" in source
    assert "jsonx_profile_configs: Object.fromEntries(Object.entries(" in source
    assert "jsonxBehaviorConfig(value)" in source
    assert "jsonx_provider: workflowJsonXProviderSettings(rest.jsonx_provider)" not in serializable
    assert '"jsonx_provider"' in serializable
    assert "result.jsonx_profile_configs" in serializable
    assert '"grok"' in serializable
    assert '"deepseek"' in serializable
    assert '"lm_studio"' in serializable
    assert '"unsloth"' in serializable
    assert "const jsonx = effectiveJsonXConfig();" in source
    assert 'localModelSelect.addEventListener("change", () => {\n' in source
    local_model_handler = source.split('localModelSelect.addEventListener("change", () => {', 1)[1].split("});", 1)[0]
    assert "persistModelSelection();" in local_model_handler
    assert "syncPreview();" in local_model_handler


def test_unified_profile_editor_uses_close_for_discard_and_explains_ambiguous_controls():
    source = (ROOT / "web" / "js" / "unified_autoprompter.js").read_text(encoding="utf-8")

    assert 'buildDom("button", "workflowx-uap-btn", "Revert")' in source
    assert source.count('close.title = "Close without saving editor changes"') == 2
    assert source.count("resetOne.title = \"Immediately restore the selected built-in") == 2
    assert source.count("resetAll.title = \"Immediately restore all built-in") == 2
    assert 'cancelJsonXBtn.title = "Stop the active generation and keep the previous output"' in source
    assert 'modelSettingsBtn.title = "Edit prompt profiles and JsonX generation settings"' in source


def test_unified_jsonx_profile_is_private_and_has_the_expected_contract():
    root = ROOT / "unified_autoprompter" / "jsonx_profile"
    assert (root / "presets.json").read_bytes() == (
        ROOT / "afj_awesome_flex_json_v2" / "visual_builder" / "presets.json"
    ).read_bytes()
    sources = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    assert "afj_awesome_flex_json_v2" not in sources
    assert "unified_autoprompter.gemini_backend" not in sources
    assert (root / "backends" / "grok.py").exists()
    private_grok = (root / "backends" / "grok.py").read_text(encoding="utf-8")
    assert "unified_autoprompter.grok_backend" not in private_grok
    assert "from ...grok_backend" not in private_grok
    assert (root / "backends" / "deepseek.py").exists()
    private_deepseek = (root / "backends" / "deepseek.py").read_text(encoding="utf-8")
    assert "unified_autoprompter.deepseek_backend" not in private_deepseek
    assert "from ...deepseek_backend" not in private_deepseek
    assert "vendor\" / \"unified-jsonx-llama.cpp" in sources
    route_source = (root / "routes.py").read_text(encoding="utf-8")
    assert 'ROUTE_PREFIX = "/workflowx/unified_autoprompter/jsonx"' in route_source
    assert 'f"{ROUTE_PREFIX}/generate"' in route_source
    assert 'f"{ROUTE_PREFIX}/deepseek/models"' in route_source
    assert "result[\"positive\"] = result.get(\"prompt\", \"\")" in route_source
    assert "_negative_text(stage_one)" in route_source


def test_unified_jsonx_profile_selected_canonical_blocks_reach_stage_one_only():
    _load_package_modules()
    routes = importlib.import_module("workflowx_unified_autoprompter_test.jsonx_profile.routes")
    engine = importlib.import_module("workflowx_unified_autoprompter_test.jsonx_profile.engine")
    store = importlib.import_module("workflowx_unified_autoprompter_test.jsonx_profile.reference_store")
    payload = routes._request_payload({
        "target_model": "jsonx",
        "generation_type": "image_to_image",
        "images_b64": ["image-1"],
        "fields": {"prompt_text": "Create a detailed portrait.", "detail": "high"},
        "generation_profile": "adaptive",
        "generation_mode": "refined",
        "output_format": "natural",
        "preset_context_mode": "optimized",
        "detail_level": "deep",
        "nsfw_enabled": True,
    })
    preview = engine.effective_instruction_preview(payload)
    stage_one = preview["stage_one"]
    ordered = [
        store.block("jsonx", "stage_one_adaptive")[1],
        store.block("jsonx", "generation_image_to_image")[1],
        store.block("jsonx", "reference_with_supported")[1],
        store.shared_nsfw_image()[1],
        store.block("jsonx", "adaptive_image_with")[1],
        store.block("jsonx", "adaptive_open_world")[1],
        store.block("jsonx", "depth_deep")[1],
        store.block("jsonx", "framing_json_disabled")[1],
        store.block("jsonx", "contract_stage_one_json")[1],
    ]
    assert all(ordered[index] in stage_one for index in range(len(ordered)))
    assert [stage_one.index(text) for text in ordered] == sorted(stage_one.index(text) for text in ordered)
    assert store.block("jsonx", "reference_with_supported")[1] not in preview["refinement"]
    assert preview["activated_files"]["stage_one"][-1].endswith("contracts/stage-one-json.md")


def test_unified_jsonx_natural_validator_normalizes_provider_formatting():
    _load_package_modules()
    engine = importlib.import_module("workflowx_unified_autoprompter_test.jsonx_profile.engine")

    fenced = "```prose\n## Scene\nA quiet beach under soft daylight.\n```"
    assert engine.validate_natural_prompt(fenced) == "## Scene\nA quiet beach under soft daylight."

    formatted = (
        "Here is the detailed natural-language prompt:\n"
        "## Scene\n"
        "- A quiet beach\n"
        "- Soft overcast daylight\n\n"
        "## Camera\n"
        "1. An eye-level portrait\n"
        "2. Shallow depth of field"
    )
    normalized = engine.validate_natural_prompt(formatted)
    assert normalized == (
        "## Scene\n"
        "A quiet beach. Soft overcast daylight.\n\n"
        "## Camera\n"
        "An eye-level portrait. Shallow depth of field."
    )

    for invalid in (
        '{"scene":"quiet beach"}',
        "Prompt prose followed by {\"scene\": \"quiet beach\"}",
        "Analysis: I will convert the prompt next.",
    ):
        try:
            engine.validate_natural_prompt(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected invalid Unified JsonX natural output: {invalid!r}")


def test_unified_jsonx_gemini_uses_json_then_plain_text_for_natural_output(monkeypatch):
    _load_package_modules()
    engine = importlib.import_module("workflowx_unified_autoprompter_test.jsonx_profile.engine")
    mime_types = []

    def fake_generate(*args, **kwargs):
        mime_type = kwargs.get("response_mime_type")
        mime_types.append(mime_type)
        if mime_type == "text/plain":
            return "## Scene\nA quiet beach under soft daylight."
        return '{"scene":{"environment":"quiet beach"}}'

    monkeypatch.setattr(engine.gemini_backend, "generate", fake_generate)
    result = engine.generate_jsonx(
        {
            "backend": "gemini",
            "api_key": "test-key",
            "model": "gemini-test",
            "user_instructions": "quiet beach",
            "output_format": "natural",
        }
    )

    assert mime_types == ["application/json", "text/plain"]
    assert result["prompt"].startswith("## Scene")
    assert "natural_fallback" not in result


def test_unified_jsonx_gemini_backend_honors_plain_text_mime(monkeypatch):
    _load_package_modules()
    engine = importlib.import_module("workflowx_unified_autoprompter_test.jsonx_profile.engine")
    bodies = []

    def fake_post(*args, **kwargs):
        bodies.append(kwargs["json"])
        return _FakeResponse({"candidates": [{"content": {"parts": [{"text": "plain prompt"}]}}]})

    monkeypatch.setattr(engine.gemini_backend.requests, "post", fake_post)
    raw = engine.gemini_backend.generate(
        "test-key",
        "gemini-test",
        "system",
        "user",
        response_mime_type="text/plain",
    )

    assert raw == "plain prompt"
    assert bodies[0]["generationConfig"]["responseMimeType"] == "text/plain"


def test_unified_jsonx_natural_uses_validated_draft_after_two_invalid_provider_responses(monkeypatch):
    _load_package_modules()
    engine = importlib.import_module("workflowx_unified_autoprompter_test.jsonx_profile.engine")
    calls = []
    responses = iter(
        [
            '{"scene":{"environment":"quiet beach"}}',
            '{"scene":"still json"}',
            '["also", "json"]',
        ]
    )
    def fake_call(data, *args, **kwargs):
        calls.append(data)
        return next(responses)

    monkeypatch.setattr(engine, "_call_provider", fake_call)

    result = engine.generate_jsonx(
        {
            "backend": "local",
            "user_instructions": "quiet beach",
            "output_format": "natural",
        }
    )

    assert result["prompt"] == "## Scene\nquiet beach."
    assert result["natural_fallback"] is True
    assert result["diagnostics"]["stage"] == "Natural Language Stage 2"
    assert "_gemini_response_mime_type" not in calls[0]
    assert calls[1]["_gemini_response_mime_type"] == "text/plain"
    assert calls[2]["_gemini_response_mime_type"] == "text/plain"
    assert engine.validate_natural_prompt(result["prompt"]) == result["prompt"]


def test_unified_jsonx_frontend_reports_natural_validation_reasons():
    source = (ROOT / "web" / "js" / "unified_autoprompter.js").read_text(encoding="utf-8")
    assert 'diagnostics.initial_error&&`Initial: ${diagnostics.initial_error}`' in source
    assert 'diagnostics.repair_error&&`Repair: ${diagnostics.repair_error}`' in source
    assert 'data.natural_fallback?" · used canonical JsonX prose fallback.":"."' in source


def test_unified_local_mtp_runtime_and_frontend_controls_are_isolated():
    binary = (ROOT / "unified_autoprompter" / "llama_binary.py").read_text(encoding="utf-8")
    backend = (ROOT / "unified_autoprompter" / "local_llama_backend.py").read_text(encoding="utf-8")
    frontend = (ROOT / "web" / "js" / "unified_autoprompter.js").read_text(encoding="utf-8")
    assert 'LLAMA_CPP_RELEASE_TAG = "b10252"' in binary
    assert "pinned_install = VENDOR_ROOT / LLAMA_CPP_RELEASE_TAG / spec.key" in binary
    assert '"--spec-type", "draft-mtp"' in backend
    assert '"--spec-draft-n-max"' in backend
    assert '"workflowx-uap-system-"' in backend
    assert "Speculative: Auto (detect embedded MTP)" in frontend
    assert "workflowx_unified_jsonx_provider_settings" in frontend


def test_unified_autoprompter_node_is_registered_and_builds_outputs():
    _profiles, _prompt_io, _prompt_builder, node, _profile_config = _load_package_modules()

    assert "UnifiedAutoprompterX" in node.NODE_CLASS_MAPPINGS
    klass = node.NODE_CLASS_MAPPINGS["UnifiedAutoprompterX"]
    assert node.NODE_DISPLAY_NAME_MAPPINGS["UnifiedAutoprompterX"] == "Unified Autoprompter X"
    assert klass.RETURN_NAMES == ("prompt", "positive", "negative")
    assert klass.CATEGORY == "WorkflowX/Prompting"
    input_types = klass.INPUT_TYPES()
    assert input_types["required"]["generation_type"][0] == (
        "text_to_image", "image_to_image", "text_to_video", "first_frame_to_video",
        "first_last_frame_to_video", "last_frame_to_video", "reference_to_video", "video_to_video",
    )
    assert input_types["required"]["nsfw_enabled"][0] == "BOOLEAN"
    assert input_types["required"]["nsfw_enabled"][1]["default"] is False
    assert input_types["required"]["enable_bbox_json_input"][0] == "BOOLEAN"
    assert input_types["required"]["enable_text_input"][0] == "BOOLEAN"
    assert input_types["required"]["refresh_vram"][0] == "BOOLEAN"
    assert input_types["required"]["disable_color_palette"][0] == "BOOLEAN"
    assert input_types["optional"]["image"] == ("IMAGE",)
    assert input_types["optional"]["image_1"] == ("IMAGE",)
    assert input_types["optional"]["image_8"] == ("IMAGE",)
    assert input_types["optional"]["bbox_json"][0] == "STRING"
    assert input_types["optional"]["bbox_json"][1]["forceInput"] is True
    assert input_types["optional"]["raw_prompt_text"][0] == "STRING"
    assert input_types["optional"]["raw_prompt_text"][1]["forceInput"] is True

    instance = klass()
    result = instance.build(
        target_model="sdxl",
        prompt_format="tags",
        negative_enabled=True,
        enable_bbox_json_input=True,
        enable_text_input=True,
        disable_color_palette=False,
        generated_positive="cinematic portrait",
        generated_negative="low quality",
        image="ignored frontend overlay",
        image_1="ignored second frontend overlay",
        bbox_json="ignored frontend sync input",
        raw_prompt_text="ignored frontend generation input",
    )
    assert result == (
        "Positive:\ncinematic portrait\n\nNegative:\nlow quality",
        "cinematic portrait",
        "low quality",
    )


if __name__ == "__main__":
    tests = [
        (name, value)
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for name, test in tests:
        test()
        print(f"PASS {name}")
