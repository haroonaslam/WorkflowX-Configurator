import importlib
import json
import pathlib
import sys
import types
from fractions import Fraction

import pytest
import torch


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load_runtime():
    package_name = "workflowx_load_video_x_test"
    original_folder_paths = sys.modules.get("folder_paths")
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_input_directory = lambda: str(ROOT)
    folder_paths.filter_files_content_types = lambda files, kinds: [
        value for value in files if pathlib.Path(value).suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}
    ] if "video" in kinds else []
    sys.modules["folder_paths"] = folder_paths
    package = types.ModuleType(package_name)
    package.__path__ = [str(ROOT)]
    sys.modules[package_name] = package
    try:
        return importlib.import_module(f"{package_name}.load_video_x.runtime")
    finally:
        if original_folder_paths is None:
            sys.modules.pop("folder_paths", None)
        else:
            sys.modules["folder_paths"] = original_folder_paths


runtime = _load_runtime()


def _state(**updates):
    state = dict(runtime.DEFAULT_VIDEO_STATE)
    state.update(updates)
    return state


def test_state_validation_and_node_contract(monkeypatch):
    parsed = runtime.parse_video_state(json.dumps({
        "mode": "bad", "short_mode": "legacy-value", "crop_snap": 16,
        "trim_start": -2, "requested_outputs": ["audio", "bad", "video"],
    }))
    assert parsed["mode"] == "off"
    assert "short_mode" not in parsed
    assert parsed["crop_snap"] == 16
    assert parsed["trim_start"] == 0
    assert parsed["requested_outputs"] == ["video", "audio"]
    monkeypatch.setattr(runtime, "list_input_videos", lambda: ["nested/clip.mp4"])
    schema = runtime.LoadVideoXAdv.INPUT_TYPES()
    assert tuple(schema["required"]) == ("video", "workflowx_state")
    assert schema["required"]["video"][1]["video_upload"] is True
    assert tuple(schema["optional"]) == ("seconds",)
    assert runtime.LoadVideoXAdv.RETURN_TYPES == ("VIDEO", "IMAGE", "AUDIO", "INT", "INT")
    assert runtime.LoadVideoXAdv.RETURN_NAMES == ("video", "video_frames", "audio", "width", "height")


def test_package_registers_metadata_route_once():
    module = importlib.import_module(runtime.__package__)
    calls = []
    router = types.SimpleNamespace(add_get=lambda path, handler: calls.append((path, handler)))
    app = types.SimpleNamespace(router=router)
    module.register_routes(app)
    module.register_routes(app)
    assert calls == [("/workflowx_configurator/load_video_x/metadata", runtime.metadata_handler)]


def test_recursive_video_listing_and_safe_path(tmp_path):
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "clip.mp4").write_bytes(b"video")
    (tmp_path / "still.png").write_bytes(b"image")

    class Paths:
        get_input_directory = staticmethod(lambda: str(tmp_path))
        filter_files_content_types = staticmethod(lambda files, kinds: [value for value in files if value.endswith(".mp4")])

    assert runtime.list_input_videos(Paths) == ["nested/clip.mp4"]
    relative, resolved = runtime.resolve_video_path("nested/clip.mp4", Paths)
    assert relative == "nested/clip.mp4" and resolved == (tmp_path / "nested" / "clip.mp4")
    with pytest.raises(ValueError):
        runtime.resolve_video_path("../outside.mp4", Paths)
    with pytest.raises(ValueError):
        runtime.resolve_video_path("still.png", Paths)


def test_frame_aligned_trim_clamps_to_available_source():
    metadata = {"duration": 2.0, "fps": 10.0, "frame_count": 20}
    clamped = runtime.plan_trim(metadata, _state(trim_start=.64), seconds=2.0)
    assert clamped["start_frame"] == 6
    assert clamped["start_time"] == .6
    assert clamped["take_frames"] == 14
    assert clamped["short"] is True
    assert clamped["requested_duration"] == 2.0
    assert clamped["output_duration"] == 1.4
    selected = torch.arange(2 * 2 * 2 * 3, dtype=torch.float32).reshape(2, 2, 2, 3)
    trimmed = runtime._trim_frame_count(selected, {"take_frames": 1})
    assert tuple(trimmed.shape) == (1, 2, 2, 3)
    trimmed_audio = runtime._trim_audio({"waveform": torch.ones((1, 1, 6)), "sample_rate": 4}, 1.0)
    assert trimmed_audio["waveform"].shape[-1] == 4


def test_probe_uses_rotation_aware_dimensions_and_file_version(tmp_path, monkeypatch):
    path = tmp_path / "phone.mov"; path.write_bytes(b"first")
    stream = types.SimpleNamespace(
        average_rate=Fraction(30, 1), base_rate=Fraction(30, 1), duration=60,
        time_base=Fraction(1, 30), frames=60, width=1920, height=1080,
    )

    class Container:
        duration = 2_000_000
        streams = types.SimpleNamespace(video=[stream], audio=[])
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def decode(self, _stream): return iter([types.SimpleNamespace(rotation=90)])

    fake_av = types.ModuleType("av"); fake_av.time_base = 1_000_000; fake_av.open = lambda _path: Container()
    monkeypatch.setitem(sys.modules, "av", fake_av)
    runtime._probe_cached.cache_clear()
    first = runtime.probe_video(path)
    assert (first["width"], first["height"], first["rotation"]) == (1080, 1920, 90)
    assert first["has_audio"] is False
    path.write_bytes(b"second-version")
    second = runtime.probe_video(path)
    assert second["version"] != first["version"]


@pytest.mark.parametrize(
    ("updates", "expected"),
    [
        ({"mode": "off"}, (320, 240)),
        ({"mode": "fit_inside", "fit_w": 100, "fit_h": 100}, (100, 75)),
        ({"mode": "cover", "cover_w": 100, "cover_h": 100, "cover_action": "fill"}, (100, 100)),
        ({"mode": "match_ratio", "ratio_w": 1, "ratio_h": 1}, (240, 240)),
        ({"mode": "pad", "pad_left": 10, "pad_right": 20, "pad_top": 5, "pad_bottom": 15}, (350, 260)),
    ],
)
def test_metadata_dimension_planning_matches_geometry(updates, expected):
    assert runtime.output_dimensions(320, 240, _state(**updates)) == expected


def test_crop_resize_rgb_padding_and_output_snap_apply_to_every_frame():
    frames = torch.zeros((3, 20, 30, 3), dtype=torch.float32)
    result = runtime.transform_frames(frames, _state(
        crop_enabled=True,
        crop_rect={"x": 5 / 30, "y": 4 / 20, "w": 20 / 30, "h": 12 / 20},
        mode="pad", pad_left=2, pad_right=2, pad_top=2, pad_bottom=2,
        pad_color="#ff0000", output_snap=8,
    ))
    assert tuple(result.shape) == (3, 16, 24, 3)
    assert torch.all(result[:, 0, :, 0] == 1)
    assert torch.all(result[:, 0, :, 1:] == 0)


def test_runtime_transform_shapes_match_metadata_planner_for_every_mode():
    cases = [
        {"mode": "off"},
        {"mode": "max_mp", "max_mp": .001},
        {"mode": "longest_side", "longest_side": 16},
        {"mode": "scale_factor", "scale_factor": .5},
        {"mode": "fit_inside", "fit_w": 20, "fit_h": 20},
        {"mode": "cover", "cover_w": 16, "cover_h": 16, "cover_action": "fill"},
        {"mode": "cover", "cover_w": 18, "cover_h": 12, "cover_action": "crop"},
        {"mode": "match_ratio", "ratio_w": 1, "ratio_h": 1},
        {"mode": "pad", "pad_left": 3, "pad_right": 5, "pad_top": 2, "pad_bottom": 6},
    ]
    frames = torch.zeros((2, 24, 32, 3), dtype=torch.float32)
    for updates in cases:
        state = _state(**updates)
        expected = runtime.output_dimensions(32, 24, state)
        transformed = runtime.transform_frames(frames, state)
        assert (transformed.shape[2], transformed.shape[1]) == expected


def test_connected_output_scan_finds_nested_links():
    nodes = {
        "2": {"inputs": {"image": ["1", 1]}},
        "3": {"inputs": {"payload": {"nested": [["1", 2]]}}},
        "4": {"inputs": {"width": ["1", 3]}},
    }
    dynprompt = types.SimpleNamespace(all_node_ids=lambda: list(nodes), get_node=lambda node_id: nodes[node_id])
    assert runtime.connected_media_outputs(dynprompt, "1") == {"video_frames", "audio"}


def test_metadata_only_and_audio_only_skip_video_decode(tmp_path, monkeypatch):
    path = tmp_path / "clip.mp4"; path.write_bytes(b"x")
    metadata = {"width": 16, "height": 8, "duration": 1.0, "fps": 4.0, "frame_count": 4, "has_audio": True}
    monkeypatch.setattr(runtime, "resolve_video_path", lambda _video: ("clip.mp4", path))
    monkeypatch.setattr(runtime, "probe_video", lambda _path: metadata)
    monkeypatch.setattr(runtime, "_decode_video_only", lambda *_args: pytest.fail("video decoder was invoked"))
    monkeypatch.setattr(runtime, "connected_media_outputs", lambda *_args: set())
    result = runtime.LoadVideoXAdv().load_video("clip.mp4", json.dumps(_state()))["result"]
    assert result == (None, None, None, 16, 8)

    audio = {"waveform": torch.zeros((1, 1, 4)), "sample_rate": 4}
    monkeypatch.setattr(runtime, "connected_media_outputs", lambda *_args: {"audio"})
    monkeypatch.setattr(runtime, "_decode_audio_only", lambda *_args: audio)
    result = runtime.LoadVideoXAdv().load_video("clip.mp4", json.dumps(_state()))["result"]
    assert result[0] is None and result[1] is None and result[2] is audio

    monkeypatch.setattr(runtime, "probe_video", lambda _path: {**metadata, "has_audio": False})
    monkeypatch.setattr(runtime, "_decode_audio_only", lambda *_args: None)
    missing = runtime.LoadVideoXAdv().load_video("clip.mp4", json.dumps(_state()))
    assert missing["result"][2] is None
    assert missing["ui"]["workflowx_load_video_x_adv"][0]["has_audio"] is False


def test_lazy_native_and_shared_component_branches(tmp_path, monkeypatch):
    path = tmp_path / "clip.mp4"; path.write_bytes(b"x")
    metadata = {"width": 4, "height": 2, "duration": 1.0, "fps": 2.0, "frame_count": 2, "has_audio": True}
    calls = {"components": 0}
    audio = {"waveform": torch.zeros((1, 1, 8)), "sample_rate": 8}
    components = types.SimpleNamespace(images=torch.zeros((2, 2, 4, 3)), audio=audio)

    class Source:
        def as_trimmed(self, *_args, **_kwargs): return self
        def get_components(self): calls["components"] += 1; return components
        def get_bit_depth(self): return 10
        def get_color_space(self): return "sRGB"

    source = Source()
    class InputImpl:
        VideoFromFile = staticmethod(lambda _path: source)
        VideoFromComponents = staticmethod(lambda components, bit_depth, color_space: (components, bit_depth, color_space))

    class VideoComponents:
        def __init__(self, **values): self.__dict__.update(values)

    latest = types.ModuleType("comfy_api.latest")
    latest.InputImpl = InputImpl; latest.Types = types.SimpleNamespace(VideoComponents=VideoComponents)
    monkeypatch.setitem(sys.modules, "comfy_api", types.ModuleType("comfy_api"))
    monkeypatch.setitem(sys.modules, "comfy_api.latest", latest)
    monkeypatch.setattr(runtime, "resolve_video_path", lambda _video: ("clip.mp4", path))
    monkeypatch.setattr(runtime, "probe_video", lambda _path: metadata)

    monkeypatch.setattr(runtime, "connected_media_outputs", lambda *_args: {"video"})
    result = runtime.LoadVideoXAdv().load_video("clip.mp4", json.dumps(_state()))["result"]
    assert result[0] is source and calls["components"] == 0

    monkeypatch.setattr(runtime, "connected_media_outputs", lambda *_args: {"video", "video_frames"})
    shared_without_transform = runtime.LoadVideoXAdv().load_video("clip.mp4", json.dumps(_state()))["result"]
    assert calls["components"] == 1
    assert shared_without_transform[0][0].images is shared_without_transform[1]

    monkeypatch.setattr(runtime, "connected_media_outputs", lambda *_args: {"video", "video_frames", "audio"})
    result = runtime.LoadVideoXAdv().load_video("clip.mp4", json.dumps(_state(mode="pad", pad_right=1)))["result"]
    assert calls["components"] == 2
    assert tuple(result[1].shape) == (2, 2, 5, 3)
    assert result[2]["sample_rate"] == 8
    assert result[0][1:] == (10, "sRGB")
    assert result[0][0].frame_rate == Fraction(2, 1)
