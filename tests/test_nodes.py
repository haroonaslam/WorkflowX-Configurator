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
    NODE_CLASS_MAPPINGS,
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
    assert len(NODE_CLASS_MAPPINGS) == 16
    assert "KVGC_SetSampler" in NODE_CLASS_MAPPINGS
    assert "KVGC_GetSampler" in NODE_CLASS_MAPPINGS
    assert "KVGC_SetScheduler" in NODE_CLASS_MAPPINGS
    assert "KVGC_GetScheduler" in NODE_CLASS_MAPPINGS
    assert "KVGC_GroupConfigurator" in NODE_CLASS_MAPPINGS
    assert "KVGC_ConfigSelector" in NODE_CLASS_MAPPINGS


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
