import os
import pathlib
import types

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT))

import load_lora_picker_x as picker


class FolderPaths:
    roots = []

    @classmethod
    def get_folder_paths(cls, folder_name):
        assert folder_name == "loras"
        return [str(root) for root in cls.roots]

    @classmethod
    def get_full_path(cls, folder_name, filename):
        assert folder_name == "loras"
        for root in cls.roots:
            path = pathlib.Path(root) / filename
            if path.is_file():
                return str(path)
        return None


def touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"lora")
    return path


def test_epoch_parser_recognizes_known_patterns_but_not_versions():
    assert picker._parse_epoch_stem("character-epoch-12") == {
        "base": "character",
        "kind": "epoch",
        "number": 12,
        "digits": "12",
    }
    assert picker._parse_epoch_stem("character_step_001500")["kind"] == "step"
    assert picker._parse_epoch_stem("character-000010")["number"] == 10
    assert picker._parse_epoch_stem("character-v2") is None
    assert picker._parse_epoch_stem("character-v0002") is None
    assert picker._parse_epoch_stem("character-12") is None


def test_inspection_groups_epochs_sorts_numerically_and_places_final_last(tmp_path):
    selected = touch(tmp_path / "hero-epoch-10.safetensors")
    touch(tmp_path / "hero-epoch-2.safetensors")
    touch(tmp_path / "hero.safetensors")
    touch(tmp_path / "hero-step-100.safetensors")
    touch(tmp_path / "hero-epoch-5.ckpt")
    touch(tmp_path / "unrelated-epoch-3.safetensors")
    FolderPaths.roots = []

    result = picker.inspect_lora(str(selected), FolderPaths)

    assert result["has_epochs"] is True
    assert [item["label"] for item in result["options"]] == ["Epoch 2", "Epoch 10", "Final"]
    assert result["selected"]["filename"] == "hero-epoch-10.safetensors"
    assert all(item["source"] == "external" for item in result["options"])


def test_selecting_final_chooses_largest_known_family_and_registered_names(tmp_path):
    root = tmp_path / "models" / "loras"
    selected = touch(root / "run" / "hero.safetensors")
    touch(root / "run" / "hero-000001.safetensors")
    touch(root / "run" / "hero-000002.safetensors")
    touch(root / "run" / "hero-step-000100.safetensors")
    FolderPaths.roots = [root]

    result = picker.inspect_lora(str(selected), FolderPaths)

    assert [item["load_name"] for item in result["options"]] == [
        "run/hero-000001.safetensors",
        "run/hero-000002.safetensors",
        "run/hero.safetensors",
    ]
    assert result["selected"]["load_name"] == "run/hero.safetensors"
    assert all(item["source"] == "registered" for item in result["options"])


def test_single_file_disables_epoch_family_and_rejects_unsupported_files(tmp_path):
    selected = touch(tmp_path / "solo.safetensors")
    FolderPaths.roots = []
    result = picker.inspect_lora(str(selected), FolderPaths)
    assert result["has_epochs"] is False
    assert [item["filename"] for item in result["options"]] == ["solo.safetensors"]

    unsupported = touch(tmp_path / "notes.txt")
    with pytest.raises(ValueError, match="Unsupported"):
        picker.inspect_lora(str(unsupported), FolderPaths)


def test_loopback_guard_accepts_only_local_addresses():
    assert picker._is_loopback_request(types.SimpleNamespace(remote="127.0.0.1"))
    assert picker._is_loopback_request(types.SimpleNamespace(remote="::1"))
    assert picker._is_loopback_request(types.SimpleNamespace(remote="::ffff:127.0.0.1"))
    assert picker._is_loopback_request(types.SimpleNamespace(remote="localhost"))
    assert not picker._is_loopback_request(types.SimpleNamespace(remote="192.168.1.20"))
    assert not picker._is_loopback_request(types.SimpleNamespace(remote=None))


@pytest.mark.skipif(os.name != "nt", reason="Windows native picker")
def test_windows_picker_returns_path_and_handles_cancel(monkeypatch):
    calls = []

    def run(*args, **kwargs):
        calls.append((args, kwargs))
        return types.SimpleNamespace(returncode=0, stdout="D:\\runs\\hero.safetensors", stderr="")

    monkeypatch.setattr(picker.subprocess, "run", run)
    assert picker._open_windows_lora_picker("D:/runs") == "D:\\runs\\hero.safetensors"
    assert calls[0][1]["env"]["WORKFLOWX_LORA_PICKER_INITIAL"] == "D:/runs"
    command = calls[0][0][0]
    assert "-STA" in command
    assert "$owner.TopMost = $true" in command[-1]
    assert "$dialog.ShowDialog($owner)" in command[-1]

    monkeypatch.setattr(
        picker.subprocess,
        "run",
        lambda *args, **kwargs: types.SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    assert picker._open_windows_lora_picker() == ""


def test_node_stacks_enabled_rows_with_independent_strengths(monkeypatch):
    calls = []

    def fake_load(cls, model, clip, row):
        calls.append((row["load_name"], row["strength_model"], row["strength_clip"]))
        return f"{model}>{row['load_name']}", f"{clip}>{row['load_name']}"

    monkeypatch.setattr(picker.LoadLoraPickerX, "_load_row", classmethod(fake_load))
    result = picker.LoadLoraPickerX().load_loras(
        "MODEL",
        "CLIP",
        lora_2={
            "on": True,
            "load_name": "B-epoch-2.safetensors",
            "strength_model": 0.5,
            "strength_clip": 0.25,
            "trigger_words": ["hero"],
        },
        lora_1={
            "on": True,
            "load_name": "A-epoch-1.safetensors",
            "strength_model": 1.0,
            "strength_clip": 0.8,
        },
        lora_3={"on": False, "load_name": "disabled.safetensors"},
        lora_4={"on": True, "load_name": "zero.safetensors", "strength_model": 0, "strength_clip": 0},
    )

    assert calls == [
        ("A-epoch-1.safetensors", 1.0, 0.8),
        ("B-epoch-2.safetensors", 0.5, 0.25),
    ]
    assert result[0] == "MODEL>A-epoch-1.safetensors>B-epoch-2.safetensors"
    assert result[2] == "hero"
    assert "A-epoch-1.safetensors (model=1, clip=0.8)" in result[3]


def test_node_uses_zero_clip_strength_without_clip_and_reports_missing_row(tmp_path, monkeypatch):
    selected = touch(tmp_path / "hero.safetensors")
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_full_path = lambda _kind, _name: None
    comfy = types.ModuleType("comfy")
    comfy.sd = types.ModuleType("comfy.sd")
    comfy.utils = types.ModuleType("comfy.utils")
    comfy.utils.load_torch_file = lambda *_args, **_kwargs: ({"weight": object()}, {"meta": "value"})
    calls = []
    comfy.sd.load_lora_for_models = lambda model, clip, lora, sm, sc, lora_metadata=None: (
        calls.append((model, clip, sm, sc, lora_metadata)) or model,
        clip,
    )
    monkeypatch.setitem(sys.modules, "folder_paths", folder_paths)
    monkeypatch.setitem(sys.modules, "comfy", comfy)
    monkeypatch.setitem(sys.modules, "comfy.sd", comfy.sd)
    monkeypatch.setitem(sys.modules, "comfy.utils", comfy.utils)

    row = {
        "row_number": 2,
        "load_name": str(selected),
        "strength_model": 0.7,
        "strength_clip": 0.4,
    }
    assert picker.LoadLoraPickerX._load_row("MODEL", None, row) == ("MODEL", None)
    assert calls == [("MODEL", None, 0.7, 0.0, {"meta": "value"})]

    row["load_name"] = str(tmp_path / "missing.safetensors")
    with pytest.raises(ValueError, match=r"row 2.*missing\.safetensors"):
        picker.LoadLoraPickerX._load_row("MODEL", None, row)


def test_cache_fingerprint_changes_when_file_is_replaced(tmp_path, monkeypatch):
    path = touch(tmp_path / "hero.safetensors")
    monkeypatch.setattr(picker.LoadLoraPickerX, "_resolve_path", classmethod(lambda cls, _reference: str(path)))
    kwargs = {"lora_1": {"on": True, "load_name": str(path)}}
    first = picker.LoadLoraPickerX.IS_CHANGED(**kwargs)
    previous = path.stat().st_mtime_ns
    path.write_bytes(b"different-size")
    os.utime(path, ns=(previous + 10_000_000, previous + 10_000_000))
    second = picker.LoadLoraPickerX.IS_CHANGED(**kwargs)
    assert first != second
