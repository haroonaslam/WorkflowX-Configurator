import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nodes import (
    GetBoolean,
    GetFloat,
    GetInt,
    GetSampler,
    GetScheduler,
    GetString,
    GetText,
    GroupConfigurator,
    GroupScopes,
    NODE_CLASS_MAPPINGS,
    ConfigSelector,
    ConfigSelectorAdvanced,
    ConfigSelectorX,
    GetRelay,
    LoraX,
    SetFloat,
    SetRelay,
    UnloadModelsByType,
)


def workflow(*nodes, groups=None):
    return {"workflow": {"nodes": list(nodes), "groups": groups or []}}


def set_node(node_id, node_type, key, value, mode=0, pos=None, size=None):
    node = {"id": node_id, "type": node_type, "mode": mode, "widgets_values": [key, value]}
    if pos is not None:
        node["pos"] = pos
    if size is not None:
        node["size"] = size
    return node


def selector_node(node_id, selected_config):
    return {"id": node_id, "type": "KVGC_ConfigSelector", "widgets_values": [selected_config]}


def advanced_selector_node(node_id, selected_config, advanced_state=None):
    widgets_values = [selected_config, "no"]
    if advanced_state is not None:
        widgets_values.append(json.dumps(advanced_state))
    return {
        "id": node_id,
        "type": "KVGC_ConfigSelectorAdvanced",
        "widgets_values": widgets_values,
    }


def selectorx_state(configs, scopes, mute=None, bypass=None):
    return {
        "version": 1,
        "initialized": True,
        "configs": configs,
        "scopes": scopes,
        "advanced": {"mute": mute or {}, "bypass": bypass or {}},
    }


def selectorx_node(node_id, selected_config, state, console_output="no"):
    return {
        "id": node_id,
        "type": "KVGC_ConfigSelectorX",
        "widgets_values": [selected_config, console_output, json.dumps(state)],
    }


def configurator_node(node_id, config_name, config_modes):
    return {
        "id": node_id,
        "type": "KVGC_GroupConfigurator",
        "widgets_values": [config_name, __import__("json").dumps(config_modes)],
    }


def group(title, bounding):
    return {"title": title, "bounding": bounding}


def resolved_digest(type_name, key, config, value):
    payload = {"config": config, "key": key, "type": type_name, "value": value}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return f"workflowx:{encoded}"


def test_all_nodes_registered():
    assert len(NODE_CLASS_MAPPINGS) == 24
    assert "KVGC_SetSampler" in NODE_CLASS_MAPPINGS
    assert "KVGC_GetSampler" in NODE_CLASS_MAPPINGS
    assert "KVGC_SetScheduler" in NODE_CLASS_MAPPINGS
    assert "KVGC_GetScheduler" in NODE_CLASS_MAPPINGS
    assert "KVGC_SetRelay" in NODE_CLASS_MAPPINGS
    assert "KVGC_GetRelay" in NODE_CLASS_MAPPINGS
    assert "KVGC_GroupConfigurator" in NODE_CLASS_MAPPINGS
    assert "KVGC_ConfigSelector" in NODE_CLASS_MAPPINGS
    assert "KVGC_ConfigSelectorAdvanced" in NODE_CLASS_MAPPINGS
    assert "KVGC_ConfigSelectorX" in NODE_CLASS_MAPPINGS
    assert "KVGC_GroupScopes" in NODE_CLASS_MAPPINGS
    assert "KVGC_UnloadModelsByType" in NODE_CLASS_MAPPINGS
    assert "KVGC_LoraX" in NODE_CLASS_MAPPINGS


def test_node_menu_hierarchy_preserves_serialized_types():
    get_set_types = {
        "KVGC_SetInt",
        "KVGC_GetInt",
        "KVGC_SetFloat",
        "KVGC_GetFloat",
        "KVGC_SetString",
        "KVGC_GetString",
        "KVGC_SetText",
        "KVGC_GetText",
        "KVGC_SetBoolean",
        "KVGC_GetBoolean",
        "KVGC_SetSampler",
        "KVGC_GetSampler",
        "KVGC_SetScheduler",
        "KVGC_GetScheduler",
        "KVGC_SetRelay",
        "KVGC_GetRelay",
    }
    deprecated_types = {
        "KVGC_GroupConfigurator",
        "KVGC_GroupScopes",
        "KVGC_ConfigSelector",
        "KVGC_ConfigSelectorAdvanced",
    }

    assert all(
        NODE_CLASS_MAPPINGS[node_type].CATEGORY == "WorkflowX/Get Set Go"
        for node_type in get_set_types
    )
    assert all(
        NODE_CLASS_MAPPINGS[node_type].CATEGORY == "WorkflowX/Deprecated"
        for node_type in deprecated_types
    )
    assert NODE_CLASS_MAPPINGS["KVGC_ConfigSelectorX"].CATEGORY == "WorkflowX/Workflow Config"
    assert NODE_CLASS_MAPPINGS["KVGC_ImageCompareEditX"].CATEGORY == "WorkflowX/Image Compare"


def test_relay_nodes_pass_through_materialized_values():
    payload = {"kind": "MODEL"}
    assert SetRelay().set_value("model", payload) == (payload,)
    assert GetRelay().get_value("model", payload) == (payload,)


def test_unload_models_by_type_inputs_and_passthrough():
    inputs = UnloadModelsByType.INPUT_TYPES()
    assert inputs["required"]["model_type"][0][0] == "Text Encoder"
    assert inputs["optional"]["trigger"][0] == "*"

    payload = {"kind": "prompt"}
    assert UnloadModelsByType._passthrough_value(trigger=payload) is payload
    assert UnloadModelsByType._passthrough_value(conditioning=payload) is payload


def test_unload_models_by_type_classifies_loaded_patchers():
    class TextModel:
        pass

    class DiffusionModel:
        model_sampling = object()

    class AutoencoderKL:
        pass

    class CLIPVisionModelProjection:
        pass

    class OtherModel:
        pass

    class Patcher:
        def __init__(self, model, is_clip=False):
            self.model = model
            self.is_clip = is_clip

    class Loaded:
        def __init__(self, model, is_clip=False):
            self.model = Patcher(model, is_clip=is_clip)

    text = Loaded(TextModel(), is_clip=True)
    diffusion = Loaded(DiffusionModel())
    vae = Loaded(AutoencoderKL())
    clip_vision = Loaded(CLIPVisionModelProjection())
    other = Loaded(OtherModel())

    assert UnloadModelsByType._matches_target(text, "Text Encoder")
    assert UnloadModelsByType._matches_target(diffusion, "Diffusion Model / UNet")
    assert UnloadModelsByType._matches_target(vae, "VAE")
    assert UnloadModelsByType._matches_target(clip_vision, "CLIP Vision")
    assert UnloadModelsByType._matches_target(other, "Other Loaded Models")
    assert UnloadModelsByType._matches_target(text, "All Loaded Models")


def test_lorax_inputs_allow_dynamic_lora_rows():
    inputs = LoraX.INPUT_TYPES()
    assert inputs["required"]["model"] == ("MODEL",)
    assert inputs["optional"]["clip"] == ("CLIP",)
    assert "lora_999" in inputs["optional"]
    assert inputs["optional"]["lora_999"][0] == "*"


def test_lorax_row_parser_accepts_aliases_and_metadata_triggers():
    entry = LoraX._entry_from_value(
        {
            "enabled": True,
            "lora": "SDXL/concept/sample.safetensors",
            "displayName": "Sample",
            "modelStrength": "0.75",
            "metadata": {"civitai": {"trainedWords": ["sample trigger"]}},
        }
    )

    assert entry == {
        "load_name": "SDXL/concept/sample.safetensors",
        "display_name": "Sample",
        "model_strength": 0.75,
        "trigger_words": ["sample trigger"],
    }


def test_lorax_ignores_disabled_or_empty_rows():
    assert LoraX._entry_from_value({"on": False, "lora": "skip.safetensors"}) is None
    assert LoraX._entry_from_value({"on": True, "strength": 1}) is None
    assert LoraX._entry_from_value({"lora": "None", "strength": 1}) is None


def test_lorax_loads_rows_in_order_and_ignores_clip_when_absent():
    original = LoraX.__dict__["_load_lora_for_models"]
    calls = []

    def fake_loader(cls, model, clip, load_name, model_strength, applied_clip_weight):
        calls.append((load_name, model_strength, applied_clip_weight, clip))
        return (f"{model}>{load_name}", clip)

    LoraX._load_lora_for_models = classmethod(fake_loader)
    try:
        result = LoraX().load_loras(
            "MODEL",
            lora_2={
                "on": True,
                "load_name": "B.safetensors",
                "strength": 0.5,
                "trigger_words": ["trigger b"],
            },
            lora_1={
                "on": True,
                "load_name": "folder/A.safetensors",
                "strength": 1.0,
                "trigger_words": ["trigger a"],
            },
            lora_3={"on": True, "load_name": "skip.safetensors", "strength": 0},
        )
    finally:
        LoraX._load_lora_for_models = original

    assert calls == [
        ("folder/A.safetensors", 1.0, 0.0, None),
        ("B.safetensors", 0.5, 0.0, None),
    ]
    assert result == (
        "MODEL>folder/A.safetensors>B.safetensors",
        None,
        "trigger a,, trigger b",
        "<lora:folder/A:1> <lora:B:0.5>",
    )


def test_lorax_uses_model_strength_and_fixed_clip_strength_when_clip_is_connected():
    original = LoraX.__dict__["_load_lora_for_models"]
    calls = []

    def fake_loader(cls, model, clip, load_name, model_strength, applied_clip_weight):
        calls.append((load_name, model_strength, applied_clip_weight, clip))
        return (f"{model}>{load_name}", f"{clip}>{load_name}")

    LoraX._load_lora_for_models = classmethod(fake_loader)
    try:
        result = LoraX().load_loras(
            "MODEL",
            clip="CLIP",
            lora_1={
                "on": True,
                "load_name": "Dual.safetensors",
                "strength": 0.7,
            },
        )
    finally:
        LoraX._load_lora_for_models = original

    assert calls == [("Dual.safetensors", 0.7, 1.0, "CLIP")]
    assert result == (
        "MODEL>Dual.safetensors",
        "CLIP>Dual.safetensors",
        "",
        "<lora:Dual:0.7>",
    )


def test_set_float_widget_preserves_decimal_precision():
    value_input = SetFloat.INPUT_TYPES()["required"]["value"]
    assert value_input == ("FLOAT", {"default": 0.0, "step": 0.01, "round": False})
    assert GetFloat().get_value(
        "cfg",
        extra_pnginfo=workflow(set_node(1, "KVGC_SetFloat", "cfg", 0.987654)),
    ) == (0.987654,)
    assert GetFloat().get_value(
        "cfg",
        "0.987654",
        "Speed",
        resolved_digest("Float", "cfg", "Speed", "0.987654"),
    ) == (0.987654,)


def test_config_selector_accepts_console_output_choice():
    assert ConfigSelector().select("Speed") == ()
    assert ConfigSelector().select("Speed", "yes") == ()

    try:
        ConfigSelector().select("Speed", "maybe")
    except ValueError as exc:
        assert "console_output must be 'no' or 'yes'" in str(exc)
    else:
        raise AssertionError("Expected invalid console_output to raise ValueError")


def test_group_configurator_accepts_ignore_mode():
    assert GroupConfigurator().configure(
        "Speed",
        json.dumps({"Utility": "Ignore", "Draft": "Active"}),
    ) == ()


def test_group_configurator_rejects_invalid_modes():
    try:
        GroupConfigurator().configure("Speed", json.dumps({"Utility": "Disable"}))
    except ValueError as exc:
        assert "invalid mode" in str(exc)
    else:
        raise AssertionError("Expected invalid mode to raise ValueError")


def test_config_selector_advanced_accepts_persisted_state():
    state = {"mute": {"Draft": False}, "bypass": {"Utility": True}}
    assert ConfigSelectorAdvanced().select("Speed", "yes", json.dumps(state)) == ()


def test_config_selector_advanced_rejects_invalid_state():
    try:
        ConfigSelectorAdvanced().select("Speed", "no", json.dumps({"mute": {"Draft": "off"}}))
    except ValueError as exc:
        assert "values must be booleans" in str(exc)
    else:
        raise AssertionError("Expected invalid advanced_state to raise ValueError")


def test_group_scopes_accepts_valid_scope_json():
    assert GroupScopes().configure(
        json.dumps({
            "Draft": "Group Configurator",
            "Utility": "Selector Bypass",
            "Notes": "Ignore",
        })
    ) == ()


def test_group_scopes_rejects_invalid_scope_names():
    try:
        GroupScopes().configure(json.dumps({"Draft": "Hidden"}))
    except ValueError as exc:
        assert "invalid scope" in str(exc)
    else:
        raise AssertionError("Expected invalid scope to raise ValueError")


def test_config_selectorx_accepts_versioned_state_and_console_choice():
    state = selectorx_state(
        [{"name": "Speed", "modes": {"Draft": "Active"}}],
        {"Draft": "Group Configurator"},
    )
    encoded = json.dumps(state)
    assert ConfigSelectorX().select("Speed", "yes", encoded) == ()
    assert ConfigSelectorX().select("", "no", "{}") == ()


def test_config_selectorx_rejects_invalid_state_shapes():
    valid = selectorx_state(
        [{"name": "Speed", "modes": {"Draft": "Active"}}],
        {"Draft": "Group Configurator"},
    )
    cases = [
        ({**valid, "version": 2}, "version must be 1"),
        ({**valid, "version": True}, "version must be 1"),
        (
            {**valid, "configs": [{"name": 1, "modes": {"Draft": "Active"}}]},
            "names must be strings",
        ),
        ({**valid, "configs": [*valid["configs"], valid["configs"][0]]}, "must be unique"),
        (selectorx_state([{"name": "Speed", "modes": {"Draft": "Disable"}}], valid["scopes"]), "invalid mode"),
        (selectorx_state(valid["configs"], {"Draft": "Hidden"}), "invalid scope"),
        (selectorx_state(valid["configs"], valid["scopes"], mute={"Draft": "on"}), "must be booleans"),
    ]
    for state, message in cases:
        try:
            ConfigSelectorX().select("Speed", "no", json.dumps(state))
        except ValueError as exc:
            assert message in str(exc)
        else:
            raise AssertionError(f"Expected invalid SelectorX state to raise ValueError: {state}")

    try:
        ConfigSelectorX().select("Missing", "no", json.dumps(valid))
    except ValueError as exc:
        assert "must match a config" in str(exc)
    else:
        raise AssertionError("Expected an unknown selected config to raise ValueError")

    try:
        ConfigSelectorX().select("Speed", "maybe", json.dumps(valid))
    except ValueError as exc:
        assert "console_output" in str(exc)
    else:
        raise AssertionError("Expected invalid console output to raise ValueError")


def test_get_relay_requires_materialized_or_connected_value():
    try:
        GetRelay().get_value("missing")
    except ValueError as exc:
        assert "No Relay value found for key 'missing'" in str(exc)
    else:
        raise AssertionError("Expected missing relay value to raise ValueError")


def test_typed_workflow_lookups():
    assert GetInt().get_value("seed", extra_pnginfo=workflow(set_node(1, "KVGC_SetInt", "seed", 42))) == (42,)
    assert GetFloat().get_value("cfg", extra_pnginfo=workflow(set_node(1, "KVGC_SetFloat", "cfg", 7.5))) == (7.5,)
    assert GetString().get_value("name", extra_pnginfo=workflow(set_node(1, "KVGC_SetString", "name", "abc"))) == ("abc",)
    assert GetText().get_value("prompt", extra_pnginfo=workflow(set_node(1, "KVGC_SetText", "prompt", "hello\nworld"))) == ("hello\nworld",)
    assert GetBoolean().get_value("enabled", extra_pnginfo=workflow(set_node(1, "KVGC_SetBoolean", "enabled", True))) == (True,)
    assert GetSampler().get_value("sampler", extra_pnginfo=workflow(set_node(1, "KVGC_SetSampler", "sampler", "dpmpp_2m"))) == ("dpmpp_2m",)
    assert GetScheduler().get_value("scheduler", extra_pnginfo=workflow(set_node(1, "KVGC_SetScheduler", "scheduler", "karras"))) == ("karras",)


def test_typed_resolved_values_are_used_when_digest_matches():
    assert GetInt().get_value("seed", "42", "Speed", resolved_digest("Int", "seed", "Speed", "42")) == (42,)
    assert GetFloat().get_value("cfg", "7.5", "Speed", resolved_digest("Float", "cfg", "Speed", "7.5")) == (7.5,)
    assert GetString().get_value("name", "abc", "Speed", resolved_digest("String", "name", "Speed", "abc")) == ("abc",)
    assert GetText().get_value("prompt", "hello\nworld", "Speed", resolved_digest("Text", "prompt", "Speed", "hello\nworld")) == ("hello\nworld",)
    assert GetBoolean().get_value("enabled", "true", "Speed", resolved_digest("Boolean", "enabled", "Speed", "true")) == (True,)
    assert GetSampler().get_value("sampler", "dpmpp_2m", "Speed", resolved_digest("Sampler", "sampler", "Speed", "dpmpp_2m")) == ("dpmpp_2m",)
    assert GetScheduler().get_value("scheduler", "karras", "Speed", resolved_digest("Scheduler", "scheduler", "Speed", "karras")) == ("karras",)


def test_invalid_resolved_digest_falls_back_to_workflow_lookup():
    data = workflow(set_node(1, "KVGC_SetInt", "seed", 12))
    assert GetInt().get_value(
        "seed",
        "42",
        "Speed",
        "not-valid",
        extra_pnginfo=data,
    ) == (12,)


def test_duplicate_uses_highest_node_id():
    data = workflow(
        set_node(1, "KVGC_SetInt", "seed", 1),
        set_node(9, "KVGC_SetInt", "seed", 9),
        set_node(4, "KVGC_SetInt", "seed", 4),
    )
    assert GetInt().get_value("seed", extra_pnginfo=data) == (9,)


def test_muted_set_node_is_ignored():
    data = workflow(
        set_node(10, "KVGC_SetInt", "steps", 4),
        set_node(20, "KVGC_SetInt", "steps", 20, mode=2),
    )
    assert GetInt().get_value("steps", extra_pnginfo=data) == (4,)


def test_bypassed_set_node_is_ignored():
    data = workflow(
        set_node(10, "KVGC_SetFloat", "cfg", 1.0),
        set_node(20, "KVGC_SetFloat", "cfg", 2.5, mode=4),
    )
    assert GetFloat().get_value("cfg", extra_pnginfo=data) == (1.0,)


def test_selected_config_picks_active_group_value():
    data = workflow(
        selector_node(100, "Speed"),
        configurator_node(101, "Speed", {"FasterConfig": "Active", "RealConfig": "Mute"}),
        set_node(10, "KVGC_SetInt", "Steps", 4, pos=[20, 20], size=[100, 60]),
        set_node(20, "KVGC_SetInt", "Steps", 20, pos=[20, 220], size=[100, 60]),
        groups=[
            group("FasterConfig", [0, 0, 300, 140]),
            group("RealConfig", [0, 200, 300, 140]),
        ],
    )
    assert GetInt().get_value("Steps", extra_pnginfo=data) == (4,)


def test_switching_selected_config_changes_lookup_value():
    base_nodes = [
        set_node(10, "KVGC_SetFloat", "CFG", 1.0, pos=[20, 20], size=[100, 60]),
        set_node(20, "KVGC_SetFloat", "CFG", 2.5, pos=[20, 220], size=[100, 60]),
    ]
    groups = [
        group("FasterConfig", [0, 0, 300, 140]),
        group("RealConfig", [0, 200, 300, 140]),
    ]

    faster = workflow(
        selector_node(100, "Speed"),
        configurator_node(101, "Speed", {"FasterConfig": "Active", "RealConfig": "Mute"}),
        *base_nodes,
        groups=groups,
    )
    real = workflow(
        selector_node(100, "Realism"),
        configurator_node(102, "Realism", {"FasterConfig": "Mute", "RealConfig": "Active"}),
        *base_nodes,
        groups=groups,
    )

    assert GetFloat().get_value("CFG", extra_pnginfo=faster) == (1.0,)
    assert GetFloat().get_value("CFG", extra_pnginfo=real) == (2.5,)


def test_advanced_selector_participates_in_selected_config_lookup():
    data = workflow(
        advanced_selector_node(100, "Realism"),
        configurator_node(101, "Realism", {"FasterConfig": "Mute", "RealConfig": "Active"}),
        set_node(10, "KVGC_SetInt", "Steps", 4, pos=[20, 20], size=[100, 60]),
        set_node(20, "KVGC_SetInt", "Steps", 20, pos=[20, 220], size=[100, 60]),
        groups=[
            group("FasterConfig", [0, 0, 300, 140]),
            group("RealConfig", [0, 200, 300, 140]),
        ],
    )
    assert GetInt().get_value("Steps", extra_pnginfo=data) == (20,)


def test_selectorx_only_workflow_resolves_config_and_scoped_groups():
    scopes = {
        "ConfigGroup": "Group Configurator",
        "MuteGroup": "Selector Mute",
        "BypassGroup": "Selector Bypass",
        "IgnoredGroup": "Ignore",
    }
    groups = [
        group("ConfigGroup", [0, 0, 300, 140]),
        group("MuteGroup", [0, 200, 300, 140]),
        group("BypassGroup", [0, 400, 300, 140]),
        group("IgnoredGroup", [0, 600, 300, 140]),
    ]
    values = [
        set_node(10, "KVGC_SetInt", "Choice", 10, pos=[20, 20], size=[100, 60]),
        set_node(20, "KVGC_SetInt", "Choice", 20, pos=[20, 220], size=[100, 60]),
        set_node(30, "KVGC_SetInt", "Choice", 30, pos=[20, 420], size=[100, 60]),
        set_node(40, "KVGC_SetInt", "Choice", 40, pos=[20, 620], size=[100, 60]),
    ]

    active_config = selectorx_state(
        [{"name": "Profile", "modes": {"ConfigGroup": "Active"}}],
        scopes,
    )
    assert GetInt().get_value(
        "Choice",
        extra_pnginfo=workflow(selectorx_node(1, "Profile", active_config), *values[:3], groups=groups),
    ) == (10,)

    mute_enabled = selectorx_state(
        [{"name": "Profile", "modes": {"ConfigGroup": "Mute"}}],
        scopes,
        mute={"MuteGroup": True},
    )
    assert GetInt().get_value(
        "Choice",
        extra_pnginfo=workflow(selectorx_node(1, "Profile", mute_enabled), *values[:3], groups=groups),
    ) == (20,)

    bypass_enabled = selectorx_state(
        [{"name": "Profile", "modes": {"ConfigGroup": "Mute"}}],
        scopes,
        bypass={"BypassGroup": True},
    )
    assert GetInt().get_value(
        "Choice",
        extra_pnginfo=workflow(selectorx_node(1, "Profile", bypass_enabled), *values[:3], groups=groups),
    ) == (30,)

    all_controlled_inactive = selectorx_state(
        [{"name": "Profile", "modes": {"ConfigGroup": "Mute"}}],
        scopes,
    )
    assert GetInt().get_value(
        "Choice",
        extra_pnginfo=workflow(
            selectorx_node(1, "Profile", all_controlled_inactive),
            *values,
            groups=groups,
        ),
    ) == (40,)


def test_populated_selectorx_takes_priority_over_legacy_nodes():
    groups = [
        group("XGroup", [0, 0, 300, 140]),
        group("LegacyGroup", [0, 200, 300, 140]),
    ]
    state = selectorx_state(
        [{"name": "X", "modes": {"XGroup": "Active", "LegacyGroup": "Mute"}}],
        {"XGroup": "Group Configurator", "LegacyGroup": "Group Configurator"},
    )
    data = workflow(
        selectorx_node(1, "X", state),
        selector_node(100, "Legacy"),
        configurator_node(101, "Legacy", {"XGroup": "Mute", "LegacyGroup": "Active"}),
        set_node(10, "KVGC_SetInt", "Choice", 1, pos=[20, 20], size=[100, 60]),
        set_node(20, "KVGC_SetInt", "Choice", 2, pos=[20, 220], size=[100, 60]),
        groups=groups,
    )
    assert GetInt().get_value("Choice", extra_pnginfo=data) == (1,)


def test_highest_id_populated_selectorx_wins_and_empty_x_falls_back_to_legacy():
    groups = [
        group("First", [0, 0, 300, 140]),
        group("Second", [0, 200, 300, 140]),
    ]
    first = selectorx_state(
        [{"name": "FirstConfig", "modes": {"First": "Active", "Second": "Mute"}}],
        {"First": "Group Configurator", "Second": "Group Configurator"},
    )
    second = selectorx_state(
        [{"name": "SecondConfig", "modes": {"First": "Mute", "Second": "Active"}}],
        {"First": "Group Configurator", "Second": "Group Configurator"},
    )
    values = [
        set_node(10, "KVGC_SetInt", "Choice", 1, pos=[20, 20], size=[100, 60]),
        set_node(20, "KVGC_SetInt", "Choice", 2, pos=[20, 220], size=[100, 60]),
    ]
    data = workflow(
        selectorx_node(5, "FirstConfig", first),
        selectorx_node(9, "SecondConfig", second),
        *values,
        groups=groups,
    )
    assert GetInt().get_value("Choice", extra_pnginfo=data) == (2,)

    fallback = workflow(
        selectorx_node(999, "Uninitialized", {}),
        selector_node(5, "Legacy"),
        configurator_node(6, "Legacy", {"First": "Active", "Second": "Mute"}),
        *values,
        groups=groups,
    )
    assert GetInt().get_value("Choice", extra_pnginfo=fallback) == (1,)


def test_selected_config_ignores_stale_workflow_modes():
    data = workflow(
        selector_node(100, "Realism"),
        configurator_node(101, "Realism", {"FasterConfig": "Mute", "RealConfig": "Active"}),
        set_node(10, "KVGC_SetInt", "Steps", 4, mode=0, pos=[20, 20], size=[100, 60]),
        set_node(20, "KVGC_SetInt", "Steps", 20, mode=2, pos=[20, 220], size=[100, 60]),
        groups=[
            group("FasterConfig", [0, 0, 300, 140]),
            group("RealConfig", [0, 200, 300, 140]),
        ],
    )
    assert GetInt().get_value("Steps", extra_pnginfo=data) == (20,)


def test_ignore_mode_treats_group_as_global_for_lookup():
    data = workflow(
        selector_node(100, "Realism"),
        configurator_node(101, "Realism", {"IgnoredConfig": "Ignore", "RealConfig": "Active"}),
        set_node(10, "KVGC_SetInt", "Steps", 4, pos=[20, 20], size=[100, 60]),
        set_node(20, "KVGC_SetInt", "Steps", 20, pos=[20, 220], size=[100, 60]),
        groups=[
            group("IgnoredConfig", [0, 0, 300, 140]),
            group("RealConfig", [0, 200, 300, 140]),
        ],
    )
    assert GetInt().get_value("Steps", extra_pnginfo=data) == (4,)


def test_global_set_node_wins_over_active_group_set_node():
    data = workflow(
        selector_node(100, "Realism"),
        configurator_node(101, "Realism", {"FasterConfig": "Mute", "RealConfig": "Active"}),
        set_node(5, "KVGC_SetInt", "Steps", 12, pos=[500, 500], size=[100, 60]),
        set_node(20, "KVGC_SetInt", "Steps", 20, pos=[20, 220], size=[100, 60]),
        groups=[
            group("FasterConfig", [0, 0, 300, 140]),
            group("RealConfig", [0, 200, 300, 140]),
        ],
    )
    assert GetInt().get_value("Steps", extra_pnginfo=data) == (12,)


def test_global_duplicate_keys_win_by_highest_node_id_before_groups():
    data = workflow(
        selector_node(100, "Realism"),
        configurator_node(101, "Realism", {"RealConfig": "Active"}),
        set_node(5, "KVGC_SetFloat", "CFG", 1.2, pos=[500, 500], size=[100, 60]),
        set_node(6, "KVGC_SetFloat", "CFG", 1.8, pos=[650, 500], size=[100, 60]),
        set_node(20, "KVGC_SetFloat", "CFG", 2.5, pos=[20, 220], size=[100, 60]),
        groups=[
            group("RealConfig", [0, 200, 300, 140]),
        ],
    )
    assert GetFloat().get_value("CFG", extra_pnginfo=data) == (1.8,)


def test_prompt_fallback_lookup():
    prompt = {
        "7": {"class_type": "KVGC_SetBoolean", "inputs": {"key": "enabled", "value": "true"}},
    }
    assert GetBoolean().get_value("enabled", prompt=prompt) == (True,)


def test_missing_key_raises_clear_error():
    try:
        GetInt().get_value("missing", extra_pnginfo=workflow())
    except KeyError as exc:
        assert "No Int value found for key 'missing'" in str(exc)
    else:
        raise AssertionError("Expected missing key to raise KeyError")


if __name__ == "__main__":
    tests = [
        (name, value)
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for name, test in tests:
        test()
        print(f"PASS {name}")
    print(f"{len(tests)} tests passed.")
