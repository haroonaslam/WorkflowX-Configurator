import base64
import io
import importlib
import hashlib
import json
import pathlib
import types

from PIL import Image

from test_packaging import ROOT, _load_package


EXPECTED_PRESET_SHA256 = "F8DF0D674C501534C544C4769570F40BE2DAF5559896C5648B1343D7F4E2B247"


def _modules():
    package = _load_package()
    base = package.__name__
    api = importlib.import_module(f"{base}.afj_awesome_flex_json_v2.visual_builder.api")
    llm = importlib.import_module(f"{base}.afj_awesome_flex_json_v2.visual_builder.jsonx_llm")
    return package, api, llm


def _find_child(node, key):
    return next(item for item in node.get("children", []) if item.get("key") == key)


def test_provided_presets_are_the_verbatim_jsonx_source():
    _package, api, llm = _modules()
    path = ROOT / "afj_awesome_flex_json_v2" / "visual_builder" / "presets.json"
    raw_bytes = path.read_bytes()
    raw = raw_bytes.decode("utf-8")
    assert len(raw_bytes) == 116_717
    assert hashlib.sha256(raw_bytes).hexdigest().upper() == EXPECTED_PRESET_SHA256
    assert llm.raw_presets_text() == raw
    assert llm.load_presets() == json.loads(raw.lstrip("\ufeff"))
    assert llm.preset_schema_paths()
    presets = llm.load_presets()
    assert "negative_prompts" in presets
    tree = api._build_starter_tree(api._new_id_factory(), presets)
    actual_roots = [child["key"] for child in tree["children"]]
    expected_roots = [
        "subjects" if key == "subject" else "interactions" if key == "interaction_suggestions" else key
        for key in presets
    ]
    assert actual_roots == [*expected_roots, "negative"]


def test_starter_tree_discovers_future_root_subject_and_interaction_categories():
    _package, api, _llm = _modules()
    presets = {
        "scene": {"weather": {"clear": "clear sky"}},
        "subject": {
            "identity": {"age": {"adult": "adult"}},
            "new_subject_branch": {"detail": {"new_id": "new value"}},
        },
        "interaction_suggestions": {"energy": {"calm": "calm interaction"}},
        "future_root": {"future_leaf": {"future_id": "future value"}},
    }
    tree = api._build_starter_tree(api._new_id_factory(), presets)
    subjects = _find_child(tree, "subjects")
    assert _find_child(subjects["item_template"], "new_subject_branch")
    interactions = _find_child(tree, "interactions")
    energy = _find_child(interactions, "energy")
    assert energy["preset_path"] == "interaction_suggestions.energy"
    assert energy["options"] == {"calm": "calm interaction"}
    assert _find_child(tree, "future_root")
    assert tree["children"][-1]["key"] == "negative"


def test_importer_and_randomizer_follow_future_catalog_paths(monkeypatch):
    package, api, _llm = _modules()
    node_module = importlib.import_module(
        f"{package.__name__}.afj_awesome_flex_json_v2.visual_builder.node"
    )
    presets = {
        "future_root": {
            "future_leaf": {
                "future_one": "future value one",
                "future_two": "future value two",
            }
        }
    }
    monkeypatch.setattr(api, "load_visual_presets", lambda: presets)

    converted = api.convert_prompt_object_to_template(
        {"future_root": {"future_leaf": "future value one"}}
    )
    assert converted["ok"] is True
    root = converted["data"]["tree"]
    future_group = api._find_group_child(root, "future_root")
    future_field = api._find_group_child(future_group, "future_leaf")
    assert future_field["preset_path"] == "future_root.future_leaf"
    assert "options" not in future_field

    live_tree = api._build_starter_tree(api._new_id_factory(), presets)
    live_field = api._find_group_child(api._find_group_child(live_tree, "future_root"), "future_leaf")
    live_field["value"] = "future value one"
    by_path, by_leaf = node_module._build_preset_maps(presets)

    class LastChoice:
        @staticmethod
        def choice(values):
            return values[-1]

    warnings, logs = node_module._apply_randomize_rules(
        live_tree,
        "future_root.future_leaf | preset | future value one",
        LastChoice(),
        by_path,
        by_leaf,
    )
    assert warnings == []
    assert live_field["value"] == "future value two"
    assert "randomized via preset" in logs[0]


def test_optimized_and_full_preset_context_modes_have_distinct_contracts():
    _package, _api, llm = _modules()
    raw = llm.raw_presets_text()
    full, full_chars = llm.build_preset_context("full", "red dress at night")
    optimized, optimized_chars = llm.build_preset_context("optimized", "red dress at night")
    assert full.endswith(raw)
    assert full_chars == optimized_chars == len(raw)
    assert "JsonX preset schema paths (complete)" in optimized
    assert "subject.dress.top.color" in optimized
    assert "=>" in optimized
    assert len(optimized) < len(full)


def test_deep_instruction_contract_and_effective_preview():
    _package, _api, llm = _modules()
    prompt = llm.stage_one_system_prompt("CATALOG", True, detail_level="deep")
    assert "parent to child to sub-child to leaf" in prompt
    assert "subjects[].dress.*" in prompt
    assert "subjects[].pose.*" in prompt
    assert "subjects[].properties.*" in prompt
    assert "camera.lens.*" in prompt
    assert "maximize the relevant JsonX tree, subtrees, and atomic leaves" in prompt
    assert "There is no leaf-count target or maximum" in prompt
    assert "no count should act as a stopping condition" in prompt
    assert "not a closed vocabulary" in prompt
    assert "none of its preset values is suitable" in prompt
    assert "closest logical JsonX parent" in prompt
    assert "Never omit a requested, visible, or strongly implied concept" in prompt
    assert "CATALOG" in prompt

    exhaustive = llm.effective_instruction_preview(
        {
            "user_instructions": "detailed portrait",
            "preset_context_mode": "optimized",
            "detail_level": "exhaustive",
            "has_image": True,
            "stage_one_instructions": "CUSTOM STAGE ONE",
            "refinement_instructions": "CUSTOM STAGE TWO",
        }
    )
    assert exhaustive["stage_one"].startswith("CUSTOM STAGE ONE")
    assert "perform an exhaustive relevance pass" in exhaustive["stage_one"]
    assert "There is no leaf-count target or maximum" in exhaustive["stage_one"]
    assert "JsonX preset schema paths (complete)" in exhaustive["stage_one"]
    assert exhaustive["refinement"].startswith("CUSTOM STAGE TWO")
    assert "custom JsonX paths and values are valid prompt content" in exhaustive["refinement"]
    assert exhaustive["detail_level"] == "exhaustive"
    assert exhaustive["stage_one_characters"] == len(exhaustive["stage_one"])


def test_custom_instructions_are_transient_and_generation_receives_depth(monkeypatch):
    _package, _api, llm = _modules()
    monkeypatch.setattr(llm, "build_preset_context", lambda mode, text: ("context", 42))
    calls = []

    def fake_call(data, system, user, image):
        calls.append(system)
        return '{"scene":{"weather":"clear"}}'

    monkeypatch.setattr(llm, "_call_provider", fake_call)
    result = llm.generate_jsonx(
        {
            "user_instructions": "clear scene",
            "detail_level": "exhaustive",
            "stage_one_instructions": "CUSTOM DEEP CONTRACT",
        }
    )
    assert calls[0].startswith("CUSTOM DEEP CONTRACT")
    assert "perform an exhaustive relevance pass" in calls[0]
    assert "no count should act as a stopping condition" in calls[0]
    assert result["detail_level"] == "exhaustive"
    assert result["hierarchy_metrics"] == {
        "leaf_count": 1,
        "branch_count": 2,
        "max_depth": 2,
        "root_groups": 1,
    }


def test_preset_alignment_resolves_ids_and_same_path_values():
    _package, _api, llm = _modules()
    presets = {
        "scene": {"weather": {"wx_clear": "clear sky, no clouds"}},
        "subject": {"identity": {"age": {"age_adult": "adult, mature appearance"}}},
        "interaction_suggestions": {"energy": {"energy_calm": "calm, relaxed energy"}},
    }
    prompt = {
        "scene": {
            "weather": "wx_clear",
            "custom_atmosphere": {"particle_behavior": "ribbons of glowing pollen orbit the doorway"},
        },
        "subjects": [{"identity": {"age": "age_adult"}}],
        "interactions": {"energy": "energy_calm"},
        "custom": "unchanged",
    }
    assert llm.align_prompt_to_presets(prompt, presets) == {
        "scene": {
            "weather": "clear sky, no clouds",
            "custom_atmosphere": {"particle_behavior": "ribbons of glowing pollen orbit the doorway"},
        },
        "subjects": [{"identity": {"age": "adult, mature appearance"}}],
        "interactions": {"energy": "calm, relaxed energy"},
        "custom": "unchanged",
    }


def test_unmatched_known_path_value_and_new_custom_subtree_remain_verbatim():
    _package, _api, llm = _modules()
    presets = {
        "scene": {"weather": {"wx_clear": "clear sky, no clouds"}},
        "subject": {"identity": {"age": {"age_adult": "adult, mature appearance"}}},
    }
    prompt = {
        "scene": {
            "weather": "electrified violet storm with upward-falling rain",
            "atmospheric_anomaly": {
                "rain_direction": "rain streams upward from the ground",
                "electrical_pattern": "branching violet arcs suspended between droplets",
            },
        }
    }

    canonical = llm.canonicalize_prompt_structure(prompt, presets)
    assert llm.align_prompt_to_presets(canonical, presets) == prompt


def test_canonicalizer_converts_internal_id_keys_and_subject_alias():
    _package, _api, llm = _modules()
    presets = {
        "scene": {
            "environment": {"env_home": "home interior"},
            "background": {"bg_blur": "softly blurred background"},
        },
        "subject": {
            "pose": {"action": {"pose_wave": "waving toward camera"}},
        },
    }
    prompt = {
        "scene": {
            "environment": {
                "env_home": "model-modified home text",
                "background": {"bg_blur": "model-modified blur text"},
            },
        },
        "subject": {
            "pose": {"action": {"pose_wave": "model-modified wave text"}},
        },
    }

    assert llm.canonicalize_prompt_structure(prompt, presets) == {
        "scene": {
            "environment": "home interior",
            "background": "softly blurred background",
        },
        "subjects": [{"pose": {"action": "waving toward camera"}}],
    }


def test_prompt_parser_enforces_prompt_only_json_contract():
    _package, _api, llm = _modules()
    assert llm.parse_prompt_json('```json\n{"prompt_json":{"scene":{"weather":"clear"}}}\n```') == {
        "scene": {"weather": "clear"}
    }
    assert llm.parse_prompt_json('Here is the result:\n```json\n{"scene":{"weather":"clear"}}\n```') == {
        "scene": {"weather": "clear"}
    }
    assert llm.parse_prompt_json('<think>drafting the schema</think>\n{"scene":{"weather":"clear"}}\nDone.') == {
        "scene": {"weather": "clear"}
    }
    for raw in (
        '[]',
        '{"subjects":{}}',
        '{"subjects":["person"]}',
        '{"interactions":[]}',
        '{"scene":{},"pipeline_stage":1}',
        '{"prompt":{"scene":{}},"scene":{}}',
        '{"scene":{"weather":"clear"}} {"scene":{"weather":"rain"}}',
        '```json\n{"scene":{"weather":"clear"}}\n```\n```json\n{"scene":{"weather":"rain"}}\n```',
    ):
        try:
            llm.parse_prompt_json(raw)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected invalid JsonX prompt: {raw}")

    normalized = llm._parse_and_normalize('{"scene":{"environment":"env_indoor_home"}}')
    assert normalized["scene"]["environment"] == "interior of a modern home, natural lived-in environment"


def test_fast_and_refined_generation_call_counts_and_repair(monkeypatch):
    _package, _api, llm = _modules()
    monkeypatch.setattr(llm, "build_preset_context", lambda mode, text: ("context", 42))
    monkeypatch.setattr(llm, "align_prompt_to_presets", lambda prompt: prompt)

    calls = []
    responses = iter(['{"scene":{"weather":"clear"}}'])

    def fake_call(data, system, user, image):
        calls.append((system, user, image))
        return next(responses)

    monkeypatch.setattr(llm, "_call_provider", fake_call)
    result = llm.generate_jsonx({"user_instructions": "clear scene", "generation_mode": "fast"})
    assert json.loads(result["prompt_json"])["scene"]["weather"] == "clear"
    assert len(calls) == 1

    calls.clear()
    responses = iter(['{"scene":{"weather":"clear"}}', '{"scene":{"weather":"crisp and clear"}}'])
    result = llm.generate_jsonx({"user_instructions": "clear scene", "generation_mode": "refined"})
    assert json.loads(result["prompt_json"])["scene"]["weather"] == "crisp and clear"
    assert len(calls) == 2

    calls.clear()
    responses = iter(["not json", '{"scene":{"weather":"repaired"}}'])
    result = llm.generate_jsonx({"user_instructions": "clear scene", "generation_mode": "fast"})
    assert json.loads(result["prompt_json"])["scene"]["weather"] == "repaired"
    assert len(calls) == 2


def test_failed_repair_exposes_transient_raw_diagnostics(monkeypatch):
    _package, _api, llm = _modules()
    monkeypatch.setattr(llm, "_call_provider", lambda *args, **kwargs: "still not json")

    try:
        llm._parse_or_repair({}, "first malformed response", "Stage 1")
    except llm.JsonXGenerationError as error:
        assert "Stage 1" in str(error)
        assert error.diagnostics["raw_response"] == "first malformed response"
        assert error.diagnostics["repair_response"] == "still not json"
        assert error.diagnostics["initial_error"]
        assert error.diagnostics["repair_error"]
    else:
        raise AssertionError("Expected invalid generation diagnostics")


def test_repair_contract_preserves_open_world_custom_content(monkeypatch):
    _package, _api, llm = _modules()
    calls = []

    def fake_call(data, system, user, image):
        calls.append(system)
        return '{"scene":{"custom_atmosphere":{"particle_motion":"glowing pollen spirals upward"}}}'

    monkeypatch.setattr(llm, "_call_provider", fake_call)
    repaired = llm._parse_or_repair({}, "malformed", "Stage 1")
    assert repaired["scene"]["custom_atmosphere"]["particle_motion"] == "glowing pollen spirals upward"
    assert "presets are guidance, not an allow-list" in calls[0]


def test_jsonx_refreshes_comfy_vram_once_before_generation(monkeypatch):
    _package, _api, llm = _modules()
    refreshes = []
    monkeypatch.setattr(llm.runtime, "refresh_comfy_vram", lambda: refreshes.append(True) or "ok")
    monkeypatch.setattr(llm, "build_preset_context", lambda mode, text: ("context", 42))
    monkeypatch.setattr(
        llm,
        "_call_provider",
        lambda *args, **kwargs: '{"scene":{"weather":"clear"}}',
    )

    llm.generate_jsonx({"user_instructions": "clear scene", "refresh_vram": True})

    assert refreshes == [True]


def test_all_provider_paths_receive_text_and_optional_image(monkeypatch):
    _package, _api, llm = _modules()
    image = Image.new("RGB", (2, 2), "red")
    provider_modules = {
        "gemini": llm.gemini_backend,
        "openai": llm.openai_backend,
        "ollama": llm.ollama_backend,
        "local": llm.local_llama_backend,
    }

    for backend, provider_module in provider_modules.items():
        calls = []

        def fake_generate(*args, **kwargs):
            calls.append((args, kwargs))
            return '{"scene":{"weather":"clear"}}'

        monkeypatch.setattr(provider_module, "generate", fake_generate)
        payload = {
            "backend": backend,
            "model": "test-model",
            "api_key": "test-key",
            "base_url": "http://localhost:1234/v1",
            "host": "http://localhost:11434",
            "gemini_safety": {
                "safety_harassment": "BLOCK_ONLY_HIGH",
                "safety_hate_speech": "BLOCK_MEDIUM_AND_ABOVE",
                "safety_sexual": "BLOCK_LOW_AND_ABOVE",
                "safety_dangerous": "BLOCK_DEFAULT",
            },
        }
        assert llm._call_provider(payload, "system", "text only", None)
        assert calls[-1][1]["pil_images"] == []
        if backend == "gemini":
            assert calls[-1][1]["safety_settings"] == payload["gemini_safety"]
        assert llm._call_provider(payload, "system", "with image", image)
        assert calls[-1][1]["pil_images"] == [image]


def test_refined_image_generation_passes_image_to_both_stages(monkeypatch):
    _package, _api, llm = _modules()
    image = Image.new("RGB", (2, 2), "blue")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    image_b64 = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")

    monkeypatch.setattr(llm, "build_preset_context", lambda mode, text: ("context", 42))
    monkeypatch.setattr(llm, "align_prompt_to_presets", lambda prompt: prompt)
    images = []
    responses = iter(['{"scene":{"weather":"clear"}}', '{"scene":{"weather":"clear blue"}}'])

    def fake_call(data, system, user, stage_image):
        images.append(stage_image)
        return next(responses)

    monkeypatch.setattr(llm, "_call_provider", fake_call)
    result = llm.generate_jsonx(
        {
            "user_instructions": "refine this image",
            "image_b64": image_b64,
            "generation_mode": "refined",
        }
    )
    assert json.loads(result["prompt_json"])["scene"]["weather"] == "clear blue"
    assert len(images) == 2
    assert all(stage_image is not None for stage_image in images)


def test_provider_context_limit_errors_propagate_without_fallback(monkeypatch):
    _package, _api, llm = _modules()
    contexts = []

    def full_context(mode, text):
        contexts.append(mode)
        return ("complete raw catalog", 123)

    monkeypatch.setattr(llm, "build_preset_context", full_context)
    monkeypatch.setattr(
        llm,
        "_call_provider",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("context length exceeded")),
    )
    try:
        llm.generate_jsonx({"user_instructions": "scene", "preset_context_mode": "full"})
    except ValueError as error:
        assert "Full Presets exceeds" in str(error)
        assert "Optimized Presets" in str(error)
        assert "context length exceeded" in str(error)
    else:
        raise AssertionError("Expected the provider context-limit error to propagate")
    assert contexts == ["full"]


def test_llm_node_defaults_and_output_contract():
    package, _api, _llm = _modules()
    klass = package.NODE_CLASS_MAPPINGS["LLMToJsonX"]
    inputs = klass.INPUT_TYPES()
    assert inputs["required"]["generation_mode"][1]["default"] == "fast"
    assert inputs["required"]["preset_context_mode"][1]["default"] == "optimized"
    assert inputs["optional"]["image"] == ("IMAGE",)
    assert klass().build(generated_prompt_json='{"scene":{"weather":"clear"}}')[0].startswith("{")


def test_jsonx_provider_package_has_no_unified_autoprompter_dependency():
    provider_root = ROOT / "afj_awesome_flex_json_v2" / "visual_builder" / "jsonx_backends"
    jsonx_files = [
        ROOT / "afj_awesome_flex_json_v2" / "visual_builder" / "jsonx_llm.py",
        ROOT / "afj_awesome_flex_json_v2" / "visual_builder" / "api.py",
        *provider_root.glob("*.py"),
    ]
    offenders = [
        str(path.relative_to(ROOT))
        for path in jsonx_files
        if "unified_autoprompter" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_jsonx_local_model_discovery_is_recursive_and_independent(tmp_path, monkeypatch):
    _package, _api, llm = _modules()
    models = llm.local_models
    root = tmp_path / "LLM"
    (root / "Gemma").mkdir(parents=True)
    (root / "Qwen" / "vision").mkdir(parents=True)
    (root / "prompts" / "nested").mkdir(parents=True)
    (root / "Gemma" / "gemma-4b.gguf").write_bytes(b"model")
    (root / "Qwen" / "qwen-vision.gguf").write_bytes(b"model")
    (root / "Qwen" / "vision" / "qwen-mmproj.gguf").write_bytes(b"projector")
    (root / "prompts" / "nested" / "jsonx.txt").write_text("system", encoding="utf-8")
    monkeypatch.setattr(models.folder_paths, "models_dir", str(tmp_path))

    assert models.model_options() == ["Gemma/gemma-4b.gguf", "Qwen/qwen-vision.gguf"]
    assert models.mmproj_options() == ["none", "Qwen/vision/qwen-mmproj.gguf"]
    assert models.system_prompt_options() == ["none", "nested/jsonx.txt"]
    assert models.full_model_path("Qwen/qwen-vision.gguf").is_file()


def test_jsonx_gemini_empty_candidates_is_diagnosed_without_retry(monkeypatch):
    _package, _api, llm = _modules()
    calls = []

    class EmptyCandidatesResponse:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {
                "promptFeedback": {
                    "blockReason": "SAFETY",
                    "blockReasonMessage": "The request was blocked by provider policy.",
                    "safetyRatings": [{"category": "TEST", "blocked": True}],
                }
            }

    def fake_post(*args, **kwargs):
        calls.append((args, kwargs))
        return EmptyCandidatesResponse()

    monkeypatch.setattr(llm.gemini_backend.requests, "post", fake_post)
    monkeypatch.setattr(llm, "build_preset_context", lambda mode, text: ("context", 42))
    try:
        llm.generate_jsonx(
            {
                "backend": "gemini",
                "api_key": "secret-key-never-diagnosed",
                "model": "gemini-test",
                "user_instructions": "clear scene",
            }
        )
    except llm.JsonXGenerationError as error:
        assert "no candidates" in str(error).lower()
        assert error.diagnostics["provider"] == "gemini"
        assert error.diagnostics["event"] == "no_candidates"
        assert error.diagnostics["prompt_feedback"]["blockReason"] == "SAFETY"
        assert "secret-key-never-diagnosed" not in json.dumps(error.diagnostics)
    else:
        raise AssertionError("Expected an empty-candidate JsonX provider error")
    assert len(calls) == 1


def test_isolated_remote_provider_model_lists(monkeypatch):
    _package, _api, llm = _modules()

    class Response:
        status_code = 200
        text = ""

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    gemini_pages = iter(
        [
            Response(
                {
                    "models": [
                        {
                            "name": "models/gemini-z",
                            "displayName": "Gemini Z",
                            "supportedGenerationMethods": ["generateContent"],
                        },
                        {
                            "name": "models/embed-only",
                            "supportedGenerationMethods": ["embedContent"],
                        },
                    ],
                    "nextPageToken": "page-2",
                }
            ),
            Response(
                {
                    "models": [
                        {
                            "name": "models/gemini-a",
                            "displayName": "Gemini A",
                            "supportedGenerationMethods": ["generateContent"],
                        }
                    ]
                }
            ),
        ]
    )
    monkeypatch.setattr(llm.gemini_backend.requests, "get", lambda *args, **kwargs: next(gemini_pages))
    assert [item["id"] for item in llm.gemini_backend.list_models("secret")] == [
        "gemini-a",
        "gemini-z",
    ]

    monkeypatch.setattr(
        llm.openai_backend.requests,
        "get",
        lambda *args, **kwargs: Response(
            {"data": [{"id": "qwen-chat"}, {"id": "text-embedding-test"}]}
        ),
    )
    assert llm.openai_backend.list_models("http://localhost:1234/v1") == [
        {"id": "qwen-chat", "display_name": "qwen-chat"}
    ]

    monkeypatch.setattr(
        llm.ollama_backend.requests,
        "get",
        lambda *args, **kwargs: Response(
            {"models": [{"name": "qwen3:latest"}, {"name": "gemma3:latest"}]}
        ),
    )
    assert [item["id"] for item in llm.ollama_backend.list_models()] == [
        "gemma3:latest",
        "qwen3:latest",
    ]


def test_jsonx_local_backend_uses_dedicated_cache_and_short_temp_files(tmp_path, monkeypatch):
    _package, _api, llm = _modules()
    backend = llm.local_llama_backend
    binary = importlib.import_module(f"{backend.__package__}.llama_binary")
    assert binary.VENDOR_ROOT == ROOT / "vendor" / "jsonx-llama.cpp"
    assert "unified" not in str(binary.VENDOR_ROOT).lower()

    fake_cli = tmp_path / "llama-cli.exe"
    monkeypatch.setattr(
        backend,
        "ensure_llama_cli_paths",
        lambda: types.SimpleNamespace(cli=fake_cli),
    )
    long_system_prompt = "JsonX full presets\n" + ("structured preset content " * 8000)
    command, cleanup_paths = backend.build_command(
        model_path=tmp_path / "model.gguf",
        mmproj_path=None,
        system_prompt_path=None,
        system_prompt_text=long_system_prompt,
        pil_images=None,
        prompt="Generate one valid JSON object.",
        options={"ctx_size": 65536},
    )
    assert "-sys" not in command
    system_path = pathlib.Path(command[command.index("-sysf") + 1])
    assert system_path.read_text(encoding="utf-8") == long_system_prompt
    assert system_path in cleanup_paths
    assert max(len(part) for part in command) < 1000
    backend._cleanup(cleanup_paths)
    assert all(path is None or not path.exists() for path in cleanup_paths)


def test_jsonx_local_backend_cleans_files_when_process_start_fails(tmp_path, monkeypatch):
    _package, _api, llm = _modules()
    backend = llm.local_llama_backend
    cleanup = tmp_path / "jsonx-system.txt"
    cleanup.write_text("temporary", encoding="utf-8")
    monkeypatch.setattr(
        backend.subprocess,
        "Popen",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("process start failed")),
    )
    try:
        backend.run_llama_cli(["missing-jsonx-llama-cli"], 5, cleanup_paths=(cleanup,))
    except OSError as error:
        assert "process start failed" in str(error)
    else:
        raise AssertionError("Expected process startup failure")
    assert not cleanup.exists()


def test_jsonx_local_backend_cleans_files_when_generation_is_cancelled(tmp_path, monkeypatch):
    _package, _api, llm = _modules()
    backend = llm.local_llama_backend
    cleanup = tmp_path / "jsonx-cancelled.txt"
    cleanup.write_text("temporary", encoding="utf-8")

    class FakeProcess:
        returncode = None

        @staticmethod
        def poll():
            return None

        @staticmethod
        def terminate():
            return None

        @staticmethod
        def kill():
            return None

        @staticmethod
        def wait(timeout=None):
            return 1

    monkeypatch.setattr(backend.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    monkeypatch.setattr(
        backend,
        "_communicate",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("generation cancelled")),
    )
    try:
        backend.run_llama_cli(["jsonx-llama-cli"], 5, cleanup_paths=(cleanup,))
    except RuntimeError as error:
        assert "cancelled" in str(error)
    else:
        raise AssertionError("Expected cancellation")
    assert not cleanup.exists()
