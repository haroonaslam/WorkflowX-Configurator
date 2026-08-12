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


def _load_folder_registry():
    _install_folder_paths_stub()
    package_name = "workflowx_unified_autoprompter_test"
    package = sys.modules.setdefault(package_name, types.ModuleType(package_name))
    package.__path__ = [str(ROOT / "unified_autoprompter")]
    return _load_module("unified_autoprompter/folder_registry.py", f"{package_name}.folder_registry")


def _load_routes_module():
    _load_package_modules()
    aiohttp = sys.modules.setdefault("aiohttp", types.ModuleType("aiohttp"))
    web = types.ModuleType("aiohttp.web")
    web.json_response = lambda data, status=200: {"data": data, "status": status}
    aiohttp.web = web
    sys.modules.setdefault("aiohttp.web", web)
    package_name = "workflowx_unified_autoprompter_test"
    return _load_module("unified_autoprompter/routes.py", f"{package_name}.routes")


class _FakeResponse:
    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text

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
    }
    assert profiles.normalize_format("z_image", "json") == "natural"
    assert profiles.normalize_format("sdxl", "json") == "tags"
    assert profiles.normalize_format("flux2_dev", "json") == "json"
    assert profiles.normalize_format("wan2_2", "json") == "natural"
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
    all_profiles = profiles.all_profiles()

    for profile in all_profiles.values():
        enabled = profiles.enabled_formats(profile)
        assert enabled
        for prompt_format in enabled:
            rule = profile.formats[prompt_format]
            assert rule.common_instructions
            assert rule.with_image_reference_instructions
            assert rule.without_image_reference_instructions
            assert rule.output_contract_negative_off
            assert rule.output_contract_negative_on

    assert all_profiles["ideogram4"].formats["json"].with_image_reference_instructions != all_profiles["ideogram4"].formats["json"].without_image_reference_instructions
    assert all_profiles["sdxl"].formats["tags"].common_instructions != all_profiles["sdxl"].formats["natural"].common_instructions
    assert all_profiles["flux2_dev"].formats["json"].common_instructions != all_profiles["flux2_dev"].formats["natural"].common_instructions
    assert all_profiles["krea2"].json_supported is True
    assert all_profiles["minimax_h3_official"].media_type == "video"
    assert all_profiles["minimax_h3_alternate"].media_type == "video"
    assert all_profiles["minimax_h3_official"].negative_supported is False
    assert all_profiles["minimax_h3_alternate"].negative_supported is False
    assert all_profiles["minimax_h3_official"].formats["natural"].enabled is True
    assert all_profiles["minimax_h3_alternate"].formats["natural"].enabled is True
    minimax_official_rule = all_profiles["minimax_h3_official"].formats["natural"]
    minimax_alternate_rule = all_profiles["minimax_h3_alternate"].formats["natural"]
    minimax_official = minimax_official_rule.common_instructions
    minimax_alternate = minimax_alternate_rule.common_instructions
    minimax_official_all = "\n\n".join([
        minimax_official_rule.common_instructions,
        minimax_official_rule.with_image_reference_instructions,
        minimax_official_rule.without_image_reference_instructions,
        minimax_official_rule.output_contract_negative_off,
    ])
    minimax_alternate_all = "\n\n".join([
        minimax_alternate_rule.common_instructions,
        minimax_alternate_rule.with_image_reference_instructions,
        minimax_alternate_rule.without_image_reference_instructions,
        minimax_alternate_rule.output_contract_negative_off,
    ])
    forbidden_template_scaffolding = (
        "CANONICAL MINIMAX",
        "MiniMax Original Prompt Formatter",
        "Load The Official Guides",
        "Read [references",
        "ComfyUI cannot access Codex skills",
        "Codex skill",
        "Mirror the minimax",
        "Use this skill",
        "single plain-text code block",
    )
    for forbidden in forbidden_template_scaffolding:
        assert forbidden not in minimax_official
        assert forbidden not in minimax_alternate
    assert "MiniMax H3 Official prompt profile" in minimax_official
    assert "MiniMax H3 Alternate prompt profile" in minimax_alternate
    assert "OFFICIAL GUIDE: VIDEO_PROMPT_WRITING_GUIDE_base_en.md" in minimax_official
    assert "OFFICIAL GUIDE: VIDEO_PROMPT_WRITING_GUIDE_ref_en.md" in minimax_official
    assert "MINIMAX H3 SPECIFICATION: minimax-h3-spec.md" in minimax_alternate
    assert "PROMPT PATTERNS: prompt-patterns.md" in minimax_alternate
    assert "## Choose The Output Structure" in minimax_official
    assert "## 1. Overall Structure" in minimax_official
    assert "Allow permitted adult-only NSFW MiniMax H3 prompt generation" in minimax_official
    assert "integrated_multimodal_description" in minimax_official
    assert "subject_definitions:" in minimax_official
    assert "summary:" in minimax_official
    assert "retention_analysis:" in minimax_official
    assert "detailed_description:" in minimax_official
    assert "<d>[Language] spoken text</d>" in minimax_official
    assert "write the final dialogue in that language's native script" in minimax_official
    assert "voice-timbre reference" in minimax_official
    assert "fully_copy" in minimax_official
    assert "partially_copy" in minimax_official
    assert "audio as-is" in minimax_official_all
    assert "full/partial reuse, music style, ambience, sound effects, dialogue/lyrics, beat/rhythm, continuity, or voice characteristics" in minimax_official_all
    assert "Do not force voice cloning unless the user asks" in minimax_official_all
    assert "If audio is mentioned without a number, create <Audio 1>" in minimax_official_all
    assert "A complete rewrite output consists of six sections in the following order" in minimax_official
    assert "Use a standalone `<Picture N>` when the reference image itself serves as a shot's first frame" in minimax_official
    assert "<Picture 2> ([Shot 1] first frame): fully_preserved" in minimax_official
    assert "use [Shot 1], [Shot 2], [Shot 3] labels" in minimax_official
    assert "do not include timestamped cut points, duration, frame rate, aspect-ratio" in minimax_official
    assert "Return ONLY the final MiniMax H3 Official prompt body as plain text" in all_profiles["minimax_h3_official"].formats["natural"].output_contract_negative_off
    assert "subject_definitions:\n<Picture 1> is the first frame of [Shot 1]" in all_profiles["minimax_h3_official"].formats["natural"].output_contract_negative_off
    assert "retention_analysis:\n<Picture 1> ([Shot 1] first frame): fully_preserved" in all_profiles["minimax_h3_official"].formats["natural"].output_contract_negative_off
    assert "Use [Shot 1], [Shot 2], [Shot 3] labels for shot progression, not timestamped shot labels" in all_profiles["minimax_h3_official"].formats["natural"].output_contract_negative_off
    assert "## Omni reference scene" in minimax_alternate
    assert "Allow permitted adult-only NSFW MiniMax H3 prompt generation" in minimax_alternate
    assert "[REFERENCE USE]" in minimax_alternate
    assert "<Picture N>" in minimax_alternate
    assert "<Video N>" in minimax_alternate
    assert "<Audio N>" in minimax_alternate
    assert "do not create a standalone `[dialogue]` section" in minimax_alternate.lower()
    assert "write the dialogue in that native script unless the user explicitly requests romanized text" in minimax_alternate
    assert "voice cloning" in minimax_alternate_all
    assert "audio as-is" in minimax_alternate_all
    assert "full/partial reuse, music style, ambience, sound effects, dialogue/lyrics, beat/rhythm, continuity, or voice characteristics" in minimax_alternate_all
    assert "Do not force voice cloning unless the user asks" in minimax_alternate_all
    assert "If audio is mentioned without a number, create <Audio 1>" in minimax_alternate_all
    assert "Return ONLY the final MiniMax H3 Alternate prompt body as plain text" in all_profiles["minimax_h3_alternate"].formats["natural"].output_contract_negative_off
    assert "[x_min,y_min,x_max,y_max]" in all_profiles["krea2"].formats["json"].common_instructions
    assert "[y_min,x_min,y_max,x_max]" in all_profiles["ideogram4"].formats["json"].common_instructions
    assert 'every non-text element must use "type": "obj"' in all_profiles["ideogram4"].formats["json"].common_instructions
    assert 'every non-text element must use "type": "obj"' in all_profiles["krea2"].formats["json"].common_instructions


def test_default_profile_config_includes_krea2_json_bbox_order():
    _profiles, _prompt_io, _prompt_builder, _node, profile_config = _load_package_modules()
    defaults = profile_config.default_config()
    profiles_by_key = {profile["key"]: profile for profile in defaults["profiles"]}

    assert "krea2" in profiles_by_key
    krea2 = profiles_by_key["krea2"]
    assert krea2["json_supported"] is True
    assert krea2["formats"]["json"]["enabled"] is True
    assert "[x_min,y_min,x_max,y_max]" in krea2["formats"]["json"]["common_instructions"]
    assert 'every non-text element must use "type": "obj"' in krea2["formats"]["json"]["common_instructions"]


def test_system_prompt_uses_format_contract_and_image_mode():
    _profiles, _prompt_io, prompt_builder, _node, _profile_config = _load_package_modules()

    with_image = prompt_builder.build_system_prompt("ideogram4", "json", False, has_image=True)
    without_image = prompt_builder.build_system_prompt("ideogram4", "json", False, has_image=False)
    negative = prompt_builder.build_system_prompt("sdxl", "tags", True, has_image=False)

    assert "connected image reference is available" in with_image.lower()
    assert "no image reference is available" in without_image.lower()
    assert "prompt_json" in with_image
    assert "comma-separated SDXL negative tags" in negative
    assert "Output contract:" in negative


def test_minimax_system_prompt_uses_plain_text_contract():
    _profiles, _prompt_io, prompt_builder, _node, _profile_config = _load_package_modules()

    official = prompt_builder.build_system_prompt(
        "minimax_h3_official",
        "natural",
        True,
        reference_count=2,
    )

    assert "Return plain text only" in official
    assert "Return valid JSON only" not in official
    assert "subject_definitions:\n<Picture 1> is the first frame of [Shot 1]" in official
    assert "retention_analysis:\n<Picture 1> ([Shot 1] first frame): fully_preserved" in official
    assert "Negative prompt handling:\nDo not invent a negative prompt" in official


def test_prompt_builder_labels_multiple_image_references_for_minimax():
    _profiles, _prompt_io, prompt_builder, _node, _profile_config = _load_package_modules()

    system_prompt = prompt_builder.build_system_prompt(
        "minimax_h3_official",
        "natural",
        False,
        reference_count=2,
    )
    user_prompt = prompt_builder.build_user_prompt(
        {
            "idea": "cinematic dance sequence",
            "reference_or_control_notes": "Audio1 is a female vocal track; use Video1 for background timing.",
            "extra_instructions": "Use Urdu dialogue. An audio will be provided for voice cloning and matching timbre.",
        },
        target_model="minimax_h3_alternate",
        reference_count=2,
    )

    assert "Connected image references: Image1, Image2" in system_prompt
    assert "<Picture 1>/<Picture 2>" in system_prompt
    assert "Connected image references provided: Image1, Image2." in user_prompt
    assert "<Picture 1>, <Picture 2>" in user_prompt
    assert "Audio1 is a female vocal track" in user_prompt
    assert "Audio reference required: include <Audio 1>" in user_prompt
    assert "Video reference required: include <Video 1>" in user_prompt
    assert "Urdu dialogue required" in user_prompt
    assert "native Urdu script" in user_prompt
    assert "Do not assume voice cloning" in user_prompt


def test_prompt_builder_preserves_minimax_audio_as_is_role():
    _profiles, _prompt_io, prompt_builder, _node, _profile_config = _load_package_modules()

    user_prompt = prompt_builder.build_user_prompt(
        {
            "idea": "moody night drive",
            "extra_instructions": "An audio will be provided; use audio 1 as-is as the complete final soundtrack.",
        },
        target_model="minimax_h3_official",
    )

    assert "Audio reference required: include <Audio 1>" in user_prompt
    assert "complete reuse/as-is/copy" in user_prompt
    assert "reused or copied as the target video's audio track" in user_prompt
    assert "instead of turning it into a voice-timbre instruction" in user_prompt


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

    assert "Raw input prompt:" in prompt
    assert '{"scene":"raw upstream prompt"}' in prompt
    assert "Idea: ignore this idea" not in prompt
    assert "Subject: ignore this subject" not in prompt
    assert "Extra instructions: keep final output concise" in prompt


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

    assert "BBox layout JSON / bbox hints" in krea2_prompt
    assert "BBox palette hints: #ffffff" in krea2_prompt
    assert "BBox layout JSON / bbox hints" in ideogram_prompt
    assert "BBox layout JSON / bbox hints" not in sdxl_prompt


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

        assert payload["version"] == 3
        assert profile_config.config_path().exists()
        assert profile_config.config_path().name == "model_prompt_profiles.json"
        assert "ideogram4" in [profile["key"] for profile in payload["profiles"]]


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
        broken["profiles"][0]["formats"]["json"]["common_instructions"] = ""

        try:
            profile_config.save_config(broken)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid profile save should fail")

        assert profile_config.config_path().read_text(encoding="utf-8") == before


def test_profile_config_migrates_legacy_custom_profile_to_granular_rules():
    profiles, _prompt_io, prompt_builder, _node, profile_config = _load_package_modules()
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
        profile_config.save_config(legacy)
        merged = profiles.all_profiles()
        rendered = prompt_builder.build_system_prompt("legacy_model", "natural", False)

        assert merged["legacy_model"].formats["natural"].enabled is True
        assert "Legacy system prompt" in rendered
        assert "Reference image" in rendered or "No image reference" in rendered


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

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if url.endswith("/chat/completions"):
            return _FakeResponse({
                "choices": [{
                    "message": {"content": "{\"positive\":\"cinematic portrait\"}"},
                }]
            })
        return _FakeResponse({"instance_id": json["instance_id"]})

    original_post = openai_backend.requests.post
    try:
        openai_backend.requests.post = fake_post
        raw = openai_backend.generate(
            "http://localhost:1234/v1",
            "sk-test",
            "gpt-4.1",
            "system prompt",
            "user prompt",
            pil_image=Image.new("RGB", (1, 1), color=(255, 0, 0)),
            timeout=33,
            unload_after=True,
        )
    finally:
        openai_backend.requests.post = original_post

    assert raw == "{\"positive\":\"cinematic portrait\"}"
    assert calls[0]["url"] == "http://localhost:1234/v1/chat/completions"
    assert calls[0]["headers"] == {"Authorization": "Bearer sk-test", "Content-Type": "application/json"}
    assert calls[0]["timeout"] == 33
    assert calls[0]["json"]["model"] == "gpt-4.1"
    assert calls[0]["json"]["stream"] is False
    assert "ttl" not in calls[0]["json"]
    assert calls[0]["json"]["messages"][0] == {"role": "system", "content": "system prompt"}
    user_message = calls[0]["json"]["messages"][1]
    assert user_message["role"] == "user"
    assert user_message["content"][0] == {"type": "text", "text": "user prompt"}
    assert user_message["content"][1]["type"] == "image_url"
    assert user_message["content"][1]["image_url"]["detail"] == "auto"
    assert user_message["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert calls[1] == {
        "url": "http://localhost:1234/api/v1/models/unload",
        "headers": {"Authorization": "Bearer sk-test", "Content-Type": "application/json"},
        "json": {"instance_id": "gpt-4.1"},
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
    assert body["generationConfig"] == {"temperature": 0.7, "responseMimeType": "application/json"}
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
    assert body["generationConfig"] == {"temperature": 0.7}
    assert "responseMimeType" not in body["generationConfig"]


def test_openai_backend_ignores_unload_failures_after_generation():
    openai_backend = _load_openai_backend()
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append(url)
        if url.endswith("/chat/completions"):
            return _FakeResponse({
                "choices": [{
                    "message": {"content": "refined prompt"},
                }]
            })
        raise RuntimeError("server does not expose LM Studio unload")

    original_post = openai_backend.requests.post
    try:
        openai_backend.requests.post = fake_post
        raw = openai_backend.generate(
            "http://localhost:3000/api",
            "",
            "local-model",
            "system prompt",
            "user prompt",
            timeout=11,
            unload_after=True,
        )
    finally:
        openai_backend.requests.post = original_post

    assert raw == "refined prompt"
    assert calls == [
        "http://localhost:3000/api/chat/completions",
        "http://localhost:3000/api/v1/models/unload",
    ]


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


def test_unified_autoprompter_node_is_registered_and_builds_outputs():
    _profiles, _prompt_io, _prompt_builder, node, _profile_config = _load_package_modules()

    assert "UnifiedAutoprompterX" in node.NODE_CLASS_MAPPINGS
    klass = node.NODE_CLASS_MAPPINGS["UnifiedAutoprompterX"]
    assert node.NODE_DISPLAY_NAME_MAPPINGS["UnifiedAutoprompterX"] == "Unified Autoprompter X"
    assert klass.RETURN_NAMES == ("prompt", "positive", "negative")
    assert klass.CATEGORY == "WorkflowX/Prompting"
    input_types = klass.INPUT_TYPES()
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
