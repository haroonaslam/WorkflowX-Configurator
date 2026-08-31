import importlib.util
import pathlib
import sys
import types
from fractions import Fraction

import torch


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load_module(monkeypatch, tmp_path):
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_output_directory = lambda: str(tmp_path / "output")
    folder_paths.get_temp_directory = lambda: str(tmp_path / "temp")

    def get_save_image_path(prefix, output_dir, width, height):
        return str(pathlib.Path(output_dir) / "clips"), "preview", 7, "clips", prefix

    folder_paths.get_save_image_path = get_save_image_path
    monkeypatch.setitem(sys.modules, "folder_paths", folder_paths)

    comfy_api = types.ModuleType("comfy_api")
    latest = types.ModuleType("comfy_api.latest")
    created_videos = []

    class EncodedVideo:
        def __init__(self, components, bit_depth, color_space):
            self.components = components
            self.bit_depth = bit_depth
            self.color_space = color_space

        def save_to(self, path, **kwargs):
            pathlib.Path(path).write_bytes(b"encoded-preview")

    class InputImpl:
        @staticmethod
        def VideoFromComponents(components, bit_depth=8, color_space="sRGB"):
            encoded = EncodedVideo(components, bit_depth, color_space)
            created_videos.append(encoded)
            return encoded

    latest.Types = types.SimpleNamespace(
        VideoContainer=types.SimpleNamespace(MP4="mp4"),
        VideoCodec=types.SimpleNamespace(H264="h264"),
        VideoComponents=lambda **kwargs: types.SimpleNamespace(**kwargs),
    )
    latest.InputImpl = InputImpl
    comfy_api.latest = latest
    monkeypatch.setitem(sys.modules, "comfy_api", comfy_api)
    monkeypatch.setitem(sys.modules, "comfy_api.latest", latest)

    name = f"workflowx_preview_video_x_test_{id(tmp_path)}"
    spec = importlib.util.spec_from_file_location(name, ROOT / "preview_video_x.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    module._test_created_videos = created_videos
    return module


class FakeVideo:
    def __init__(self):
        self.saved = []

    def get_dimensions(self):
        return 640, 360

    def save_to(self, path, **kwargs):
        pathlib.Path(path).write_bytes(b"video")
        self.saved.append((path, kwargs))


def test_preview_video_x_interface(monkeypatch, tmp_path):
    module = _load_module(monkeypatch, tmp_path)
    cls = module.PreviewVideoX
    assert cls.CATEGORY == "WorkflowX/Video"
    assert cls.RETURN_TYPES == ("VIDEO", "VHS_FILENAMES")
    assert cls.OUTPUT_NODE is True
    assert module.NODE_DISPLAY_NAME_MAPPINGS["WorkflowX_PreviewVideoX"] == "Preview Video X"


def test_preview_uses_temp_file_without_persistent_save(monkeypatch, tmp_path):
    module = _load_module(monkeypatch, tmp_path)
    video = FakeVideo()
    result = module.PreviewVideoX().preview_video(video, False, "WorkflowX/test-preview")

    saved_path, options = video.saved[0]
    assert pathlib.Path(saved_path).is_file()
    assert pathlib.Path(saved_path).is_relative_to(tmp_path / "temp")
    assert options == {"format": "mp4", "codec": "h264"}
    assert result["ui"] == {
        "images": [{"filename": "preview_00007_.mp4", "subfolder": "clips", "type": "temp"}],
        "animated": (True,),
    }
    assert result["result"] == (video, (False, [saved_path]))


def test_preview_saves_to_output_when_enabled(monkeypatch, tmp_path):
    module = _load_module(monkeypatch, tmp_path)
    video = FakeVideo()
    result = module.PreviewVideoX().preview_video(video, True, "WorkflowX/saved-preview")

    saved_path, _options = video.saved[0]
    assert pathlib.Path(saved_path).is_relative_to(tmp_path / "output")
    assert result["ui"]["images"][0]["type"] == "output"
    assert result["result"] == (video, (True, [saved_path]))


def test_odd_dimensions_are_padded_only_for_h264_preview(monkeypatch, tmp_path):
    module = _load_module(monkeypatch, tmp_path)

    class OddVideo:
        def get_dimensions(self):
            return 5, 3

        def get_components(self):
            return types.SimpleNamespace(
                images=torch.ones((1, 3, 5, 3)),
                audio={"waveform": torch.ones((1, 1, 100)), "sample_rate": 100},
                frame_rate=Fraction(25, 1),
            )

        def get_color_space(self):
            return "sRGB"

    video = OddVideo()
    result = module.PreviewVideoX().preview_video(video, False, "WorkflowX/odd-preview")

    encoded = module._test_created_videos[0]
    assert tuple(encoded.components.images.shape) == (1, 4, 6, 3)
    assert encoded.bit_depth == 8
    assert encoded.components.audio["sample_rate"] == 100
    assert result["result"][0] is video
