import base64
import io
import importlib
import hashlib
import json
import pathlib
import threading
import types

from PIL import Image

from test_packaging import ROOT, _load_package


EXPECTED_PRESET_SHA256 = "EFC4B7C2B24394EF33F632A688DB6FEC9911696395BCA8CABECB6B559B9F0A14"


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
    assert len(raw_bytes) == 125_143
    assert hashlib.sha256(raw_bytes).hexdigest().upper() == EXPECTED_PRESET_SHA256
    assert llm.raw_presets_text() == raw
    assert llm.load_presets() == json.loads(raw.lstrip("\ufeff"))
    assert llm.preset_schema_paths()
    presets = llm.load_presets()
    leaves = llm.flatten_preset_leaves(presets)
    preset_ids = [preset_id for options in leaves.values() for preset_id in options]
    assert len(preset_ids) == len(set(preset_ids)), "JsonX preset IDs must be globally unique"
    assert "negative_prompts" in presets
    assert list(presets).index("camera") < list(presets).index("framing_and_placement")
    assert list(presets).index("framing_and_placement") < list(presets).index("mood")
    assert list(presets["framing_and_placement"]) == list(llm.FRAMING_AND_PLACEMENT_KEYS)
    assert all(
        len(options) == 7
        for options in presets["framing_and_placement"].values()
    )
    tree = api._build_starter_tree(api._new_id_factory(), presets)
    actual_roots = [child["key"] for child in tree["children"]]
    expected_roots = [
        "subjects" if key == "subject" else "interactions" if key == "interaction_suggestions" else key
        for key in presets
    ]
    assert actual_roots == [*expected_roots, "negative"]


def test_jsonx_generation_cancellation_skips_the_provider_call(monkeypatch):
    _package, _api, llm = _modules()
    cancelled = threading.Event()
    cancelled.set()
    monkeypatch.setattr(
        llm,
        "_call_provider",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("provider should not run")),
    )
    try:
        llm.generate_jsonx(
            {
                "user_instructions": "quiet beach portrait",
                "_cancel_event": cancelled,
            }
        )
    except llm.JsonXGenerationCancelled as error:
        assert "cancelled" in str(error).lower()
    else:
        raise AssertionError("Expected JsonX generation cancellation")


def test_jsonx_local_cancellation_reaches_the_isolated_llama_backend(monkeypatch):
    _package, _api, llm = _modules()
    cancelled = threading.Event()
    received = {}

    def fake_generate(**kwargs):
        received.update(kwargs)
        cancelled.set()
        raise RuntimeError("JsonX local generation cancelled.")

    monkeypatch.setattr(llm.local_llama_backend, "generate", fake_generate)
    try:
        llm._call_provider(
            {
                "backend": "local",
                "model": "test.gguf",
                "_cancel_event": cancelled,
            },
            "system",
            "user",
            None,
        )
    except llm.JsonXGenerationCancelled:
        pass
    else:
        raise AssertionError("Expected local JsonX cancellation")
    assert received["cancel_event"] is cancelled


def test_jsonx_cancellation_registry_preserves_an_early_cancel_until_generation_begins():
    _package, api, _llm = _modules()
    generation_id = "jsonx-test-cancel-registry"
    api.JsonXCancellationRegistry.finish(generation_id)
    assert api.JsonXCancellationRegistry.cancel(generation_id) is True
    event = api.JsonXCancellationRegistry.begin(generation_id)
    assert event.is_set()
    api.JsonXCancellationRegistry.finish(generation_id)
    assert not api.JsonXCancellationRegistry.begin(generation_id).is_set()
    api.JsonXCancellationRegistry.finish(generation_id)


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


def test_template_fill_hierarchy_is_dynamic_complete_and_null_leafed():
    _package, _api, llm = _modules()
    presets = {
        "scene": {
            "environment": {"env_home": "home interior"},
            "weather": {"weather_clear": "clear weather"},
        },
        "subject": {
            "identity": {"age": {"age_adult": "adult"}},
            "future_branch": {"detail": {"future_id": "future value"}},
        },
        "interaction_suggestions": {"energy": {"calm": "calm interaction"}},
        "future_root": {"future_leaf": {"future_option": "future value"}},
    }
    assert llm.template_fill_hierarchy(presets) == {
        "scene": {"environment": None, "weather": None},
        "subjects": [{"identity": {"age": None}, "future_branch": {"detail": None}}],
        "interactions": {"energy": None},
        "future_root": {"future_leaf": None},
    }


def test_template_fill_context_sends_no_presets_or_full_verbatim_presets():
    _package, _api, llm = _modules()
    raw = llm.raw_presets_text()
    without_presets, chars_without = llm.template_fill_context(False)
    with_presets, chars_with = llm.template_fill_context(True)
    assert "Blank JsonX hierarchy to fill:" in without_presets
    assert "Complete JsonX presets.json (verbatim):" not in without_presets
    assert raw not in without_presets
    assert with_presets.endswith(raw)
    assert "Complete JsonX presets.json (verbatim):" in with_presets
    assert chars_without == chars_with == len(raw)


def test_framing_map_is_an_opt_in_template_fill_root():
    _package, _api, llm = _modules()
    presets = {
        "scene": {"environment": {"env_home": "home interior"}},
        "framing_and_placement": {
            key: {f"frame_{key}": f"content in {key}"}
            for key in llm.FRAMING_AND_PLACEMENT_KEYS
        },
    }
    disabled = llm.template_fill_hierarchy(presets)
    enabled = llm.template_fill_hierarchy(
        presets,
        enable_framing_and_placement=True,
    )
    assert "framing_and_placement" not in disabled
    assert enabled["framing_and_placement"] == {
        key: None for key in llm.FRAMING_AND_PLACEMENT_KEYS
    }

    context, _chars = llm.template_fill_context(
        False,
        enable_framing_and_placement=True,
    )
    assert '"framing_and_placement"' in context
    assert '"top_left": null' in context
    assert "Complete JsonX presets.json (verbatim):" not in context


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
    assert "sibling `<leaf>_details` custom subtree" in prompt
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
    assert exhaustive["enable_framing_and_placement"] is False
    assert "Framing and placement map is disabled" in exhaustive["stage_one"]

    framed_adaptive = llm.effective_instruction_preview(
        {
            "user_instructions": "portrait on the right third",
            "enable_framing_and_placement": True,
        }
    )
    assert framed_adaptive["enable_framing_and_placement"] is True
    assert "Framing and placement map is enabled and mandatory" in framed_adaptive["stage_one"]
    assert "top_left, top_center, top_right" in framed_adaptive["stage_one"]
    assert "Do not output numeric coordinates or bounding boxes" in framed_adaptive["stage_one"]
    assert "Framing and placement map is enabled and mandatory" in framed_adaptive["refinement"]

    template = llm.effective_instruction_preview(
        {
            "user_instructions": "fill a portrait",
            "generation_profile": "template_fill",
            "template_use_presets": False,
            "preset_context_mode": "full",
            "has_image": True,
            "enable_framing_and_placement": True,
        }
    )
    assert template["generation_profile"] == "template_fill"
    assert template["preset_context_mode"] == "none"
    assert "Blank JsonX hierarchy to fill:" in template["stage_one"]
    assert "Complete JsonX presets.json (verbatim):" not in template["stage_one"]
    assert "Leave a leaf as JSON `null`" in template["stage_one"]
    assert '"framing_and_placement"' in template["stage_one"]
    assert '"bottom_right": null' in template["stage_one"]
    assert "Template Fill refinement constraint" in template["refinement"]
    assert template["enable_framing_and_placement"] is True

    template_with_presets = llm.effective_instruction_preview(
        {
            "generation_profile": "template_fill",
            "template_use_presets": True,
            "preset_context_mode": "optimized",
        }
    )
    assert template_with_presets["preset_context_mode"] == "full"
    assert template_with_presets["stage_one"].endswith(llm.raw_presets_text())
    assert "If no preset value is suitable" in template_with_presets["stage_one"]


def test_natural_instruction_preview_exposes_forced_two_pass_contract():
    _package, _api, llm = _modules()
    templates = llm.instruction_templates()
    assert templates["default_output_format"] == "json"
    assert templates["output_formats"] == ["json", "natural"]
    assert "Return only the final prompt text" in templates["natural_language"]

    adaptive = llm.effective_instruction_preview(
        {
            "user_instructions": "a quiet beach portrait",
            "generation_profile": "adaptive",
            "generation_mode": "fast",
            "output_format": "natural",
            "enable_framing_and_placement": True,
        }
    )
    assert adaptive["output_format"] == "natural"
    assert adaptive["generation_mode"] == "refined"
    assert adaptive["forced_two_pass"] is True
    assert "Return only the final prompt text" in adaptive["refinement"]
    assert "all nine named regions" in adaptive["refinement"]
    assert "Complete JsonX presets.json (verbatim):" not in adaptive["refinement"]

    template = llm.effective_instruction_preview(
        {
            "generation_profile": "template_fill",
            "template_use_presets": True,
            "output_format": "natural",
            "natural_language_instructions": "CUSTOM NATURAL CONTRACT",
        }
    )
    assert template["generation_mode"] == "refined"
    assert template["preset_context_mode"] == "full"
    assert template["refinement"].startswith("CUSTOM NATURAL CONTRACT")
    assert "Complete JsonX presets.json (verbatim):" not in template["refinement"]


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


def test_canonicalizer_preserves_custom_expansion_beside_catalog_scalar_leaf():
    _package, _api, llm = _modules()
    presets = {
        "scene": {"environment": {"env_beach": "sandy beach shoreline"}},
        "subject": {
            "properties": {
                "expression": {"expression_calm": "calm neutral expression"},
            }
        },
        "negative_prompts": {"negative_realistic": "plastic skin, harsh shadows"},
    }
    prompt = {
        "scene": {
            "environment": {
                "setting": "sandy beach shoreline",
                "background_elements": ["calm ocean horizon", "gentle foam waves"],
                "ground_texture": "fine beige sand with footprints",
            }
        },
        "subjects": [
            {
                "expression": {
                    "mood": "calm and introspective",
                    "facial_muscles": "relaxed jaw and soft gaze",
                }
            }
        ],
        "negative_prompts": ["plastic skin", "harsh shadows"],
    }

    assert llm.canonicalize_prompt_structure(prompt, presets) == {
        "scene": {
            "environment_details": {
                "setting": "sandy beach shoreline",
                "background_elements": ["calm ocean horizon", "gentle foam waves"],
                "ground_texture": "fine beige sand with footprints",
            }
        },
        "subjects": [
            {
                "properties": {
                    "expression_details": {
                        "mood": "calm and introspective",
                        "facial_muscles": "relaxed jaw and soft gaze",
                    }
                }
            }
        ],
        "negative_prompts": "plastic skin, harsh shadows",
    }


def test_nested_leaf_detail_names_do_not_collide_with_catalog_siblings():
    _package, _api, llm = _modules()
    presets = {
        "lighting": {
            "shadows": {"shadow_soft": "soft shallow shadows"},
            "highlights": {"highlight_gentle": "gentle highlights"},
            "intensity": {"intensity_moderate": "moderate exposure"},
        }
    }
    prompt = {
        "lighting": {
            "shadows": {
                "intensity": "very soft",
                "definition": "subtle",
                "location": "under chin and arms",
            },
            "highlights": {
                "intensity": "gentle",
                "location": "shoulders and cheekbones",
            },
        }
    }
    assert llm.canonicalize_prompt_structure(prompt, presets) == {
        "lighting": {
            "shadows_details": {
                "intensity": "very soft",
                "definition": "subtle",
                "location": "under chin and arms",
            },
            "highlights_details": {
                "intensity": "gentle",
                "location": "shoulders and cheekbones",
            },
        }
    }


def test_leaf_object_moves_sibling_only_with_explicit_preset_evidence():
    _package, _api, llm = _modules()
    presets = {
        "scene": {
            "environment": {"env_home": "home interior"},
            "background": {"bg_blur": "softly blurred background"},
        }
    }
    assert llm.canonicalize_prompt_structure(
        {"scene": {"environment": {"background": {"bg_blur": "model wording"}}}},
        presets,
    ) == {"scene": {"background": "softly blurred background"}}


def test_unknown_child_stays_inside_established_nested_catalog_branch():
    _package, _api, llm = _modules()
    presets = {
        "subject": {
            "properties": {
                "skin": {"texture": {"skin_natural": "natural skin texture"}},
                "hair": {
                    "color": {"hair_black": "black hair"},
                    "style": {"hair_pony": "low ponytail"},
                },
            }
        }
    }
    prompt = {
        "subjects": [
            {
                "properties": {
                    "skin": {"texture": "visible natural pores"},
                    "hair": {
                        "color": "black",
                        "style": "low ponytail",
                        "texture": "straight with slightly wavy ends",
                    },
                }
            }
        ]
    }
    canonical = llm.canonicalize_prompt_structure(prompt, presets)
    assert canonical["subjects"][0]["properties"]["skin"]["texture"] == "visible natural pores"
    assert canonical["subjects"][0]["properties"]["hair"]["texture"] == (
        "straight with slightly wavy ends"
    )


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


def test_canonicalizer_merges_compatible_duplicate_leaf_aliases():
    _package, _api, llm = _modules()
    presets = {
        "subject": {
            "pose": {
                "contact_points": {
                    "contact_hand_on_knee": "hand resting on own knee",
                    "contact_seated_floor": "seated, contact with floor",
                    "contact_none": "no contact with environment",
                }
            }
        }
    }
    prompt = {
        "subjects": [
            {
                "pose": {
                    "contact_points": "seated on a white towel",
                    "contact_hand_on_knee": "ignored model explanation",
                }
            }
        ]
    }

    assert llm.canonicalize_prompt_structure(prompt, presets) == {
        "subjects": [
            {
                "pose": {
                    "contact_points": "seated on a white towel; hand resting on own knee"
                }
            }
        ]
    }


def test_canonicalizer_uses_parent_context_for_reused_preset_ids():
    _package, _api, llm = _modules()
    presets = {
        "subject": {
            "properties": {
                "hair": {"temple": {"temple_from_reference": "soft hair at temples"}},
                "face": {"temple_width": {"temple_from_reference": "medium temple width"}},
            }
        },
        "mood": {"tension": {"tension_neutral": "neutral emotional tension"}},
        "subject_extra": {"not_used": {"tension_neutral": "unrelated value"}},
    }
    prompt = {
        "subjects": [
            {
                "properties": {
                    "hair": {"temple_from_reference": "ignored model explanation"},
                    "face": {"temple_from_reference": "ignored model explanation"},
                }
            }
        ]
    }

    assert llm.canonicalize_prompt_structure(prompt, presets) == {
        "subjects": [
            {
                "properties": {
                    "hair": {"temple": "soft hair at temples"},
                    "face": {"temple_width": "medium temple width"},
                }
            }
        ]
    }


def test_canonicalizer_accepts_path_scoped_legacy_preset_ids_after_catalog_cleanup():
    _package, _api, llm = _modules()
    canonical = llm.canonicalize_prompt_structure(
        {
            "subjects": [
                {
                    "properties": {
                        "hair": {"temple_from_reference": "legacy model output"},
                        "face": {"temple_from_reference": "legacy model output"},
                    }
                }
            ],
            "interactions": {"type": {"romantic": "legacy model output"}},
        }
    )

    assert canonical["subjects"][0]["properties"]["hair"]["temple"] == (
        "temple hair design from reference image"
    )
    assert canonical["subjects"][0]["properties"]["face"]["temple_width"] == (
        "temple width from reference image"
    )
    assert canonical["interactions"]["type"] == "romantic interaction dynamic"


def test_canonicalizer_keeps_distinct_catalog_choices_and_no_contact_conflicts_invalid():
    _package, _api, llm = _modules()
    presets = {
        "subject": {
            "pose": {
                "contact_points": {
                    "contact_hand_on_knee": "hand resting on own knee",
                    "contact_seated_floor": "seated, contact with floor",
                    "contact_none": "no contact with environment",
                }
            }
        }
    }
    conflicting_ids = {
        "subjects": [
            {
                "pose": {
                    "contact_hand_on_knee": "ignored",
                    "contact_seated_floor": "ignored",
                }
            }
        ]
    }
    conflicting_no_contact = {
        "subjects": [
            {
                "pose": {
                    "contact_points": "no contact with environment",
                    "contact_hand_on_knee": "ignored",
                }
            }
        ]
    }

    for prompt in (conflicting_ids, conflicting_no_contact):
        try:
            llm.canonicalize_prompt_structure(prompt, presets)
        except ValueError as error:
            assert "subjects.0.pose.contact_points" in str(error)
        else:
            raise AssertionError("Expected a true contact-point conflict to remain invalid")


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


def test_natural_word_matching_unrelated_preset_id_is_allowed():
    _package, _api, llm = _modules()
    leaves = {
        "scene.weather.wind": {"wind_still": "still air"},
        "interaction_suggestions.energy": {"calm": "calm interaction"},
    }
    prompt = {"scene": {"weather": {"wind": "calm"}}}
    assert llm.validate_canonical_prompt(prompt, leaves) == prompt

    try:
        llm.validate_canonical_prompt(
            {"interactions": {"energy": "calm"}},
            leaves,
        )
    except ValueError as error:
        assert "interaction_suggestions.energy" in str(error)
    else:
        raise AssertionError("Expected a same-path preset ID to remain invalid")


def test_framing_map_gate_requires_exactly_nine_non_empty_scalar_regions():
    _package, _api, llm = _modules()
    framing = {
        key: f"specific visible content in the {key.replace('_', ' ')} region"
        for key in llm.FRAMING_AND_PLACEMENT_KEYS
    }
    prompt = {"scene": {"environment": "beach"}, "framing_and_placement": framing}
    enabled = llm.enforce_framing_and_placement(prompt, True)
    assert list(enabled["framing_and_placement"]) == list(llm.FRAMING_AND_PLACEMENT_KEYS)
    assert "framing_and_placement" not in llm.enforce_framing_and_placement(prompt, False)

    invalid_maps = [
        None,
        {key: value for key, value in framing.items() if key != "bottom_right"},
        {**framing, "outside_grid": "invalid extra region"},
        {**framing, "center": ""},
        {**framing, "center": {"subject": "nested value"}},
    ]
    for invalid in invalid_maps:
        try:
            llm.enforce_framing_and_placement(
                {"framing_and_placement": invalid},
                True,
            )
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected invalid framing map to fail: {invalid!r}")


def test_framing_map_generation_gate_and_same_provider_repair(monkeypatch):
    _package, _api, llm = _modules()
    framing = {
        key: f"coherent visible image content in the {key.replace('_', ' ')} region"
        for key in llm.FRAMING_AND_PLACEMENT_KEYS
    }
    valid_response = json.dumps(
        {
            "scene": {"environment": "quiet beach"},
            "framing_and_placement": framing,
        }
    )
    calls = []
    responses = iter([valid_response])

    def fake_call(data, system, user, image):
        calls.append((system, user))
        return next(responses)

    monkeypatch.setattr(llm, "_call_provider", fake_call)
    enabled = llm.generate_jsonx(
        {
            "user_instructions": "compose a quiet beach portrait",
            "enable_framing_and_placement": True,
        }
    )
    assert json.loads(enabled["prompt_json"])["framing_and_placement"] == framing
    assert enabled["enable_framing_and_placement"] is True
    assert "Framing and placement map is enabled and mandatory" in calls[0][0]

    calls.clear()
    responses = iter([valid_response])
    disabled = llm.generate_jsonx(
        {
            "user_instructions": "compose a quiet beach portrait",
            "enable_framing_and_placement": False,
        }
    )
    assert "framing_and_placement" not in json.loads(disabled["prompt_json"])
    assert disabled["enable_framing_and_placement"] is False
    assert "Framing and placement map is disabled" in calls[0][0]

    calls.clear()
    responses = iter([
        '{"scene":{"environment":"quiet beach"}}',
        valid_response,
    ])
    repaired = llm.generate_jsonx(
        {
            "user_instructions": "compose a quiet beach portrait",
            "enable_framing_and_placement": True,
        }
    )
    assert len(calls) == 2
    assert "smallest possible edits" in calls[1][0]
    assert "exactly these nine scalar string leaves" in calls[1][0]
    assert len(json.loads(repaired["prompt_json"])["framing_and_placement"]) == 9

    calls.clear()
    refined_framing = dict(framing)
    refined_framing["center"] = "the primary subject forms the coherent central focal region"
    responses = iter([
        valid_response,
        json.dumps(
            {
                "scene": {"environment": "quiet beach"},
                "framing_and_placement": refined_framing,
            }
        ),
    ])
    refined = llm.generate_jsonx(
        {
            "user_instructions": "compose a quiet beach portrait",
            "generation_mode": "refined",
            "enable_framing_and_placement": True,
        }
    )
    assert len(calls) == 2
    assert json.loads(refined["prompt_json"])["framing_and_placement"]["center"] == (
        refined_framing["center"]
    )
    assert "Framing and placement map is enabled and mandatory" in calls[1][0]


def test_template_fill_generation_includes_enabled_framing_map(monkeypatch):
    _package, _api, llm = _modules()
    framing = {
        key: f"complete final-image description for {key.replace('_', ' ')}"
        for key in llm.FRAMING_AND_PLACEMENT_KEYS
    }
    calls = []

    def fake_call(data, system, user, image):
        calls.append(system)
        return json.dumps(
            {
                "scene": {"environment": "studio portrait"},
                "framing_and_placement": framing,
            }
        )

    monkeypatch.setattr(llm, "_call_provider", fake_call)
    result = llm.generate_jsonx(
        {
            "user_instructions": "studio portrait",
            "generation_profile": "template_fill",
            "template_use_presets": False,
            "enable_framing_and_placement": True,
        }
    )
    assert json.loads(result["prompt_json"])["framing_and_placement"] == framing
    assert '"framing_and_placement"' in calls[0]
    assert "Complete JsonX presets.json (verbatim):" not in calls[0]

    calls.clear()
    refined = llm.generate_jsonx(
        {
            "user_instructions": "studio portrait",
            "generation_mode": "refined",
            "generation_profile": "template_fill",
            "template_use_presets": False,
            "enable_framing_and_placement": True,
        }
    )
    assert len(calls) == 2
    assert json.loads(refined["prompt_json"])["framing_and_placement"] == framing
    assert "Template Fill refinement constraint" in calls[1]


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


def test_natural_output_uses_validated_json_then_refined_prose(monkeypatch):
    _package, _api, llm = _modules()
    framing = {
        key: f"visible composition detail in the {key.replace('_', ' ')} region"
        for key in llm.FRAMING_AND_PLACEMENT_KEYS
    }
    monkeypatch.setattr(
        llm,
        "build_preset_context",
        lambda mode, text: ("STAGE_ONE_PRESET_SENTINEL", 42),
    )
    calls = []
    responses = iter(
        [
            json.dumps(
                {
                    "scene": {"environment": "quiet beach", "weather": "soft overcast"},
                    "subjects": [{"identity": {"description": "one seated woman"}}],
                    "negative": {"artifacts": "avoid distorted hands"},
                    "framing_and_placement": framing,
                }
            ),
            "## Scene\nA quiet beach under soft overcast light.\n\n"
            "## Subjects\nOne woman sits calmly in the scene.\n\n"
            "## Avoid\nAvoid distorted hands.",
        ]
    )

    def fake_call(data, system, user, image):
        calls.append((system, user, image))
        return next(responses)

    monkeypatch.setattr(llm, "_call_provider", fake_call)
    result = llm.generate_jsonx(
        {
            "user_instructions": "a seated woman on a quiet beach",
            "generation_mode": "fast",
            "output_format": "natural",
            "enable_framing_and_placement": True,
        }
    )

    assert len(calls) == 2
    assert result["generation_mode"] == "refined"
    assert result["output_format"] == "natural"
    assert result["prompt"].startswith("## Scene")
    assert "prompt_json" not in result
    assert "STAGE_ONE_PRESET_SENTINEL" in calls[0][0]
    assert "STAGE_ONE_PRESET_SENTINEL" not in calls[1][0]
    assert "STAGE_ONE_PRESET_SENTINEL" not in calls[1][1]
    assert "Validated JsonX draft to convert" in calls[1][1]
    assert '"quiet beach"' in calls[1][1]
    assert '"bottom_right"' in calls[1][1]
    assert "Return only the final prompt text" in calls[1][0]
    assert "all nine named regions" in calls[1][0]


def test_template_fill_natural_output_is_two_pass_and_preset_agnostic_in_stage_two(monkeypatch):
    _package, _api, llm = _modules()
    calls = []
    responses = iter(
        [
            json.dumps(
                {
                    "scene": {"environment": "studio", "weather": None},
                    "subjects": [{"identity": {"gender": "woman", "age": None}}],
                }
            ),
            "## Scene\nA controlled studio setting.\n\n## Subjects\nA woman is the sole subject.",
        ]
    )

    def fake_call(data, system, user, image):
        calls.append((system, user))
        return next(responses)

    monkeypatch.setattr(llm, "_call_provider", fake_call)
    result = llm.generate_jsonx(
        {
            "user_instructions": "studio portrait of one woman",
            "generation_profile": "template_fill",
            "template_use_presets": True,
            "output_format": "natural",
        }
    )

    assert len(calls) == 2
    assert result["generation_profile"] == "template_fill"
    assert result["preset_context_mode"] == "full"
    assert result["output_format"] == "natural"
    assert "Complete JsonX presets.json (verbatim):" in calls[0][0]
    assert "Complete JsonX presets.json (verbatim):" not in calls[1][0]
    assert "Template Fill refinement constraint" not in calls[1][0]
    assert '"weather"' not in calls[1][1]
    assert '"age"' not in calls[1][1]


def test_natural_output_validation_and_single_repair(monkeypatch):
    _package, _api, llm = _modules()
    assert llm.validate_natural_prompt("```text\n## Scene\nA quiet beach.\n```") == (
        "## Scene\nA quiet beach."
    )
    assert llm.validate_natural_prompt("<think>hidden</think>\n## Scene\nA quiet beach.").startswith(
        "## Scene"
    )
    for invalid in (
        "",
        '{"scene":"beach"}',
        "Here is the prompt response: a beach",
        "## Scene\n- A quiet beach",
    ):
        try:
            llm.validate_natural_prompt(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected invalid natural output: {invalid!r}")

    calls = []
    responses = iter(
        [
            '{"scene":{"environment":"quiet beach"}}',
            '{"scene":"still json"}',
            "## Scene\nA quiet beach rendered as coherent prose.",
        ]
    )

    def fake_call(data, system, user, image):
        calls.append((data, system, user))
        return next(responses)

    monkeypatch.setattr(llm, "_call_provider", fake_call)
    repaired = llm.generate_jsonx(
        {
            "backend": "local",
            "user_instructions": "quiet beach",
            "output_format": "natural",
            "local_options": {"reasoning": "auto", "temperature": 0.8, "max_tokens": 512},
        }
    )
    assert repaired["prompt"].startswith("## Scene")
    assert len(calls) == 3
    assert "Repair rule" in calls[2][1]
    assert "_gemini_response_mime_type" not in calls[0][0]
    assert calls[1][0]["_gemini_response_mime_type"] == "text/plain"
    assert calls[2][0]["_gemini_response_mime_type"] == "text/plain"
    assert calls[2][0]["local_options"]["reasoning"] == "off"
    assert calls[2][0]["local_options"]["temperature"] == 0.2
    assert calls[2][0]["local_options"]["max_tokens"] == 4096


def test_natural_output_failed_repair_reports_stage_two_diagnostics(monkeypatch):
    _package, _api, llm = _modules()
    responses = iter(
        [
            '{"scene":{"environment":"quiet beach"}}',
            '{"scene":"still json"}',
            '["also", "json"]',
        ]
    )
    monkeypatch.setattr(llm, "_call_provider", lambda *args, **kwargs: next(responses))

    try:
        llm.generate_jsonx(
            {
                "user_instructions": "quiet beach",
                "output_format": "natural",
            }
        )
    except llm.JsonXGenerationError as error:
        assert error.diagnostics["stage"] == "Natural Language Stage 2"
        assert "must be prose, not JSON" in error.diagnostics["initial_error"]
        assert "must be prose, not JSON" in error.diagnostics["repair_error"]
        assert error.diagnostics["repair_response"] == '["also", "json"]'
    else:
        raise AssertionError("Expected failed natural-language repair diagnostics")


def test_template_fill_generation_prunes_nulls_and_uses_its_own_preset_toggle(monkeypatch):
    _package, _api, llm = _modules()
    calls = []

    def fake_call(data, system, user, image):
        calls.append(system)
        return json.dumps(
            {
                "scene": {"environment": "quiet beach", "weather": None},
                "subjects": [
                    {"identity": {"gender": "woman", "age": None}, "pose": {"action": None}}
                ],
                "interactions": {"energy": None},
                "invented_root": {"summary": "must not survive Template Fill"},
            }
        )

    monkeypatch.setattr(llm, "_call_provider", fake_call)
    result = llm.generate_jsonx(
        {
            "user_instructions": "a woman on a quiet beach",
            "generation_profile": "template_fill",
            "template_use_presets": False,
            "preset_context_mode": "full",
        }
    )
    prompt = json.loads(result["prompt_json"])
    assert prompt == {
        "scene": {"environment": "quiet beach"},
        "subjects": [{"identity": {"gender": "woman"}}],
    }
    assert result["generation_profile"] == "template_fill"
    assert result["preset_context_mode"] == "none"
    assert "Blank JsonX hierarchy to fill:" in calls[0]
    assert "Complete JsonX presets.json (verbatim):" not in calls[0]

    constrained = llm.constrain_template_fill_structure(
        {
            "subjects": [
                {"identity": {"gender": "woman"}},
                {"identity": {"gender": "man"}},
            ],
            "invented_root": {"summary": "discarded"},
        },
        {"subjects": [{"identity": {"gender": None}}]},
    )
    assert constrained == {
        "subjects": [
            {"identity": {"gender": "woman"}},
            {"identity": {"gender": "man"}},
        ]
    }

    calls.clear()
    result = llm.generate_jsonx(
        {
            "user_instructions": "a woman on a quiet beach",
            "generation_profile": "template_fill",
            "template_use_presets": True,
            "preset_context_mode": "optimized",
        }
    )
    assert result["preset_context_mode"] == "full"
    assert calls[0].endswith(llm.raw_presets_text())
    assert "If no preset value is suitable" in calls[0]


def test_template_fill_refined_overlays_wording_without_restructuring(monkeypatch):
    _package, _api, llm = _modules()
    responses = iter(
        [
            json.dumps(
                {
                    "scene": {
                        "environment": "beach",
                        "weather": "overcast daylight",
                    },
                    "subjects": [{"identity": {"gender": "woman"}}],
                }
            ),
            json.dumps(
                {
                    "scene": {"environment": "quiet sandy beach shoreline"},
                    "subjects": [{"identity": {"gender": "adult woman"}}],
                    "invented_root": {"summary": "must be ignored"},
                }
            ),
        ]
    )
    calls = []

    def fake_call(data, system, user, image):
        calls.append((system, user))
        return next(responses)

    monkeypatch.setattr(llm, "_call_provider", fake_call)
    result = llm.generate_jsonx(
        {
            "user_instructions": "coherent beach portrait",
            "generation_mode": "refined",
            "generation_profile": "template_fill",
            "template_use_presets": False,
        }
    )
    assert json.loads(result["prompt_json"]) == {
        "scene": {
            "environment": "quiet sandy beach shoreline",
            "weather": "overcast daylight",
        },
        "subjects": [{"identity": {"gender": "adult woman"}}],
    }
    assert "Template Fill refinement constraint" in calls[1][0]
    assert "JsonX draft to refine" in calls[1][1]

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


def test_local_repair_is_constrained_deterministic_and_image_aware(monkeypatch):
    _package, _api, llm = _modules()
    calls = []
    image = llm.Image.new("RGB", (2, 2), "white")

    def fake_call(data, system, user, repair_image):
        calls.append((data, system, user, repair_image))
        return '{"subjects":[{"identity":{"description":"portrait subject"}}]}'

    monkeypatch.setattr(llm, "_call_provider", fake_call)
    repaired = llm._parse_or_repair(
        {
            "backend": "local",
            "user_instructions": "describe the portrait",
            "local_options": {"reasoning": "auto", "temperature": 0.8, "max_tokens": 1024},
        },
        "truncated source",
        "Stage 1",
        image,
    )
    assert repaired["subjects"][0]["identity"]["description"] == "portrait subject"
    repair_data, repair_system, repair_user, repair_image = calls[0]
    assert repair_data["local_options"]["reasoning"] == "off"
    assert repair_data["local_options"]["temperature"] == 0.2
    assert repair_data["local_options"]["max_tokens"] == 4096
    assert repair_image is image
    assert "smallest possible edits" in repair_system
    assert "never a catalog, schema, custom_paths" in repair_system
    assert "Never turn a subject object into a label string" in repair_system
    assert "describe the portrait" in repair_user


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


def test_all_isolated_providers_support_two_pass_natural_image_generation(monkeypatch):
    _package, _api, llm = _modules()
    image = Image.new("RGB", (2, 2), "blue")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    image_b64 = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    provider_modules = {
        "gemini": llm.gemini_backend,
        "openai": llm.openai_backend,
        "ollama": llm.ollama_backend,
        "local": llm.local_llama_backend,
    }

    for backend, provider_module in provider_modules.items():
        calls = []
        responses = iter(
            [
                '{"scene":{"environment":"blue-lit studio"}}',
                "## Scene\nA blue-lit studio rendered as detailed natural-language prompt prose.",
            ]
        )

        def fake_generate(*args, **kwargs):
            calls.append((args, kwargs))
            return next(responses)

        monkeypatch.setattr(provider_module, "generate", fake_generate)
        result = llm.generate_jsonx(
            {
                "backend": backend,
                "model": "test-model",
                "api_key": "test-key",
                "base_url": "http://localhost:1234/v1",
                "host": "http://localhost:11434",
                "user_instructions": "describe the image",
                "image_b64": image_b64,
                "output_format": "natural",
            }
        )
        assert result["output_format"] == "natural"
        assert len(calls) == 2
        assert all(call[1]["pil_images"] for call in calls)


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

    try:
        llm.generate_jsonx(
            {
                "user_instructions": "scene",
                "generation_profile": "template_fill",
                "template_use_presets": True,
                "preset_context_mode": "optimized",
            }
        )
    except ValueError as error:
        assert "Full Presets exceeds" in str(error)
        assert "context length exceeded" in str(error)
    else:
        raise AssertionError("Expected Template Fill full-preset context error to propagate")
    assert contexts == ["full"]


def test_llm_node_defaults_and_output_contract():
    package, _api, _llm = _modules()
    klass = package.NODE_CLASS_MAPPINGS["LLMToJsonX"]
    inputs = klass.INPUT_TYPES()
    assert inputs["required"]["generation_mode"][1]["default"] == "fast"
    assert inputs["required"]["preset_context_mode"][1]["default"] == "optimized"
    assert inputs["optional"]["image"] == ("IMAGE",)
    assert list(inputs["optional"])[-6:] == [
        "ui_state",
        "enable_framing_and_placement",
        "output_format",
        "generation_profile",
        "template_use_presets",
        "detail_level",
    ]
    assert inputs["optional"]["enable_framing_and_placement"][0] == "BOOLEAN"
    assert inputs["optional"]["enable_framing_and_placement"][1]["default"] is False
    assert inputs["optional"]["output_format"][0] == ["json", "natural"]
    assert inputs["optional"]["output_format"][1]["default"] == "json"
    assert inputs["optional"]["generation_profile"][0] == ["adaptive", "template_fill"]
    assert inputs["optional"]["generation_profile"][1]["default"] == "adaptive"
    assert inputs["optional"]["template_use_presets"][0] == "BOOLEAN"
    assert inputs["optional"]["template_use_presets"][1]["default"] is False
    assert inputs["optional"]["detail_level"][0] == ["deep", "exhaustive"]
    assert inputs["optional"]["detail_level"][1]["default"] == "deep"
    assert klass.RETURN_NAMES == ("prompt",)
    assert klass().build(generated_prompt_json='{"scene":{"weather":"clear"}}')[0].startswith("{")
    assert klass().build(
        generated_prompt_json="## Scene\nA detailed natural-language prompt.",
        output_format="natural",
    ) == ("## Scene\nA detailed natural-language prompt.",)
    framing = {
        key: f"visible content in {key.replace('_', ' ')}"
        for key in _llm.FRAMING_AND_PLACEMENT_KEYS
    }
    framed_json = json.dumps({"framing_and_placement": framing})
    framed_output = json.loads(
        klass().build(
            generated_prompt_json=framed_json,
            enable_framing_and_placement=True,
        )[0]
    )
    assert framed_output["framing_and_placement"] == framing
    assert "framing_and_placement" not in json.loads(
        klass().build(
            generated_prompt_json=framed_json,
            enable_framing_and_placement=False,
        )[0]
    )
    try:
        klass().build(
            generated_prompt_json='{"scene":{"weather":"clear"}}',
            enable_framing_and_placement=True,
        )
    except ValueError as error:
        assert "requires a 'framing_and_placement' object" in str(error)
    else:
        raise AssertionError("Expected enabled runtime output without the framing map to fail")


def test_jsonx_instruction_overrides_persist_in_the_comfyui_user_profile(tmp_path):
    _package, api, _llm = _modules()
    original_path = api._jsonx_user_settings_path
    api._jsonx_user_settings_path = lambda: tmp_path / "workflowx" / "jsonx_settings.json"
    try:
        overrides = {
            "stage_one_instructions": "Custom stage one.",
            "template_fill_instructions": "Custom template fill.",
            "refinement_instructions": "Custom refinement.",
            "natural_language_instructions": "Custom natural language.",
        }
        assert api.save_jsonx_user_instruction_overrides(overrides) == overrides
        assert api.load_jsonx_user_instruction_overrides() == overrides
        saved = json.loads(api._jsonx_user_settings_path().read_text(encoding="utf-8"))
        assert saved == {"version": 1, "instruction_overrides": overrides}
        assert "api_key" not in json.dumps(saved)
    finally:
        api._jsonx_user_settings_path = original_path


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


def test_jsonx_additional_model_folders_are_recursive_deduplicated_and_resolved(tmp_path, monkeypatch):
    _package, _api, llm = _modules()
    models = llm.local_models
    comfy_root = tmp_path / "Comfy" / "LLM"
    external = tmp_path / "LM Studio" / "models"
    missing = tmp_path / "missing"
    (comfy_root / "Qwen").mkdir(parents=True)
    (external / "publisher" / "model").mkdir(parents=True)
    (external / "publisher" / "vision").mkdir(parents=True)
    (comfy_root / "Qwen" / "base.gguf").write_bytes(b"base")
    external_model = external / "publisher" / "model" / "shared-model.gguf"
    external_mmproj = external / "publisher" / "vision" / "shared-mmproj.gguf"
    external_model.write_bytes(b"external")
    external_mmproj.write_bytes(b"projector")
    monkeypatch.setattr(models.folder_paths, "models_dir", str(tmp_path / "Comfy"))

    catalog = models.model_catalog([str(external), str(external), str(missing)])
    assert catalog["models"][0] == "Qwen/base.gguf"
    external_options = [item for item in catalog["models"] if isinstance(item, dict)]
    assert len(external_options) == 1
    assert external_options[0]["label"].endswith("publisher/model/shared-model.gguf")
    assert models.full_model_path(external_options[0]["value"], [str(external)]) == external_model
    mmproj_option = next(item for item in catalog["mmproj"] if isinstance(item, dict))
    assert models.full_mmproj_path(mmproj_option["value"], [str(external)]) == external_mmproj
    assert catalog["additional_roots"] == 1
    assert catalog["invalid_paths"] == [str(missing)]

    try:
        models.full_model_path(external_options[0]["value"], [])
    except FileNotFoundError as error:
        assert "no longer configured" in str(error)
    else:
        raise AssertionError("External selection must require its configured browser path")


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


def test_jsonx_gemini_uses_json_for_stage_one_and_plain_text_for_natural_stage_two(monkeypatch):
    _package, _api, llm = _modules()
    mime_types = []

    def fake_generate(*args, **kwargs):
        mime_type = kwargs.get("response_mime_type")
        mime_types.append(mime_type)
        if mime_type == "text/plain":
            return "## Scene\nA quiet beach under soft daylight."
        return '{"scene":{"environment":"quiet beach"}}'

    monkeypatch.setattr(llm.gemini_backend, "generate", fake_generate)
    result = llm.generate_jsonx(
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


def test_jsonx_gemini_backend_writes_requested_plain_text_mime(monkeypatch):
    _package, _api, llm = _modules()
    bodies = []

    class Response:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"candidates": [{"content": {"parts": [{"text": "plain prompt"}]}}]}

    def fake_post(*args, **kwargs):
        bodies.append(kwargs["json"])
        return Response()

    monkeypatch.setattr(llm.gemini_backend.requests, "post", fake_post)
    raw = llm.gemini_backend.generate(
        "test-key",
        "gemini-test",
        "system",
        "user",
        response_mime_type="text/plain",
    )

    assert raw == "plain prompt"
    assert bodies[0]["generationConfig"]["responseMimeType"] == "text/plain"


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
    assert binary.LLAMA_CPP_RELEASE_TAG == "b10252"
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


def test_jsonx_local_backend_detects_embedded_mtp_and_builds_speculative_flags(tmp_path, monkeypatch):
    _package, _api, llm = _modules()
    backend = llm.local_llama_backend
    fake_cli = tmp_path / "llama-cli.exe"
    monkeypatch.setattr(
        backend,
        "ensure_llama_cli_paths",
        lambda: types.SimpleNamespace(cli=fake_cli),
    )

    import struct

    model = tmp_path / "qwen36.gguf"
    key = b"qwen35.nextn_predict_layers"
    model.write_bytes(
        b"GGUF"
        + struct.pack("<IQQ", 3, 0, 1)
        + struct.pack("<Q", len(key))
        + key
        + struct.pack("<II", 4, 1)
    )
    assert backend.model_has_embedded_mtp(model) is True

    command, cleanup_paths = backend.build_command(
        model_path=model,
        mmproj_path=None,
        system_prompt_path=None,
        system_prompt_text="JsonX system",
        pil_images=None,
        prompt="Generate JSON",
        options={"speculative_mode": "auto", "mtp_draft_tokens": 3},
    )
    assert command[command.index("--spec-type") + 1] == "draft-mtp"
    assert command[command.index("--spec-draft-n-max") + 1] == "3"
    assert command[command.index("--reasoning") + 1] == "auto"
    backend._cleanup(cleanup_paths)

    assert backend.normalize_reasoning_mode("none") == "off"
    assert backend.normalize_reasoning_mode("qwen3") == "auto"


def test_jsonx_local_backend_reports_old_runtime_mtp_loader_mismatch(monkeypatch):
    _package, _api, llm = _modules()
    backend = llm.local_llama_backend

    class FakeProcess:
        returncode = 1

    monkeypatch.setattr(backend.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    monkeypatch.setattr(
        backend,
        "_communicate",
        lambda *args, **kwargs: ("", "missing tensor 'blk.64.ssm_conv1d.weight'"),
    )
    try:
        backend.run_llama_cli(["llama-cli", "-m", "qwen-mtp.gguf"], 5)
    except RuntimeError as error:
        assert "embedded MTP layer" in str(error)
        assert "Speculative decoding = Auto or MTP" in str(error)
    else:
        raise AssertionError("Expected an actionable MTP compatibility error")


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
