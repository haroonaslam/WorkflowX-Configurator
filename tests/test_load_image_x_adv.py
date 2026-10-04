import importlib.util
import json
import pathlib
import sys
import types
import io

import numpy as np
import pytest
from PIL import Image


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load_modules():
    package_name = "workflowx_load_image_x_adv_test"
    original_folder_paths = sys.modules.get("folder_paths")
    stub = types.ModuleType("folder_paths")
    stub.get_input_directory = lambda: str(ROOT)
    stub.get_user_directory = lambda: str(ROOT / ".test_user")
    stub.filter_files_content_types = lambda files, _types: list(files)
    sys.modules["folder_paths"] = stub
    package = types.ModuleType(package_name)
    package.__path__ = [str(ROOT / "load_image_x")]
    sys.modules[package_name] = package
    try:
        runtime_spec = importlib.util.spec_from_file_location(
            f"{package_name}.runtime",
            ROOT / "load_image_x" / "runtime.py",
        )
        runtime = importlib.util.module_from_spec(runtime_spec)
        sys.modules[runtime_spec.name] = runtime
        runtime_spec.loader.exec_module(runtime)

        advanced_spec = importlib.util.spec_from_file_location(
            f"{package_name}.advanced",
            ROOT / "load_image_x" / "advanced.py",
        )
        advanced = importlib.util.module_from_spec(advanced_spec)
        sys.modules[advanced_spec.name] = advanced
        advanced_spec.loader.exec_module(advanced)
        return advanced
    finally:
        if original_folder_paths is None:
            sys.modules.pop("folder_paths", None)
        else:
            sys.modules["folder_paths"] = original_folder_paths


advanced = _load_modules()
direct_spec = importlib.util.spec_from_file_location("workflowx_direct_test", ROOT / "load_image_x/direct.py")
direct = importlib.util.module_from_spec(direct_spec)
direct_spec.loader.exec_module(direct)


def _encoded(format="PNG", mode="RGBA"):
    stream = io.BytesIO()
    Image.new(mode, (16, 12)).save(stream, format=format)
    stream.seek(0)
    return stream


def test_direct_replacement_is_original_bytes_and_does_not_accumulate(tmp_path):
    first = _encoded()
    result = direct.store_direct_image(first, "a" * 32, tmp_path)
    target = tmp_path / result["subfolder"] / result["name"]
    assert target.read_bytes() == first.getvalue()
    second = _encoded("JPEG", "RGB")
    assert direct.store_direct_image(second, "a" * 32, tmp_path) == result
    assert target.read_bytes() == second.getvalue()
    assert list(target.parent.iterdir()) == [target]
    other = direct.store_direct_image(first, "b" * 32, tmp_path)
    assert other["subfolder"] != result["subfolder"]
    assert target.read_bytes() == second.getvalue()


def test_direct_bad_upload_preserves_previous_and_cleans_partial(tmp_path):
    result = direct.store_direct_image(_encoded(), "a" * 32, tmp_path)
    target = tmp_path / result["subfolder"] / result["name"]
    before = target.read_bytes()
    with pytest.raises(OSError):
        direct.store_direct_image(io.BytesIO(b"broken"), "a" * 32, tmp_path)
    assert target.read_bytes() == before
    assert list(target.parent.iterdir()) == [target]
    with pytest.raises(ValueError):
        direct.store_direct_image(_encoded(), "../escape", tmp_path)


def test_direct_animation_retains_all_frames(tmp_path):
    stream = io.BytesIO()
    Image.new("RGB", (16, 12), "red").save(stream, format="GIF", save_all=True,
        append_images=[Image.new("RGB", (16, 12), "blue")], duration=100, loop=0)
    result = direct.store_direct_image(stream, "a" * 32, tmp_path)
    with Image.open(tmp_path / result["subfolder"] / result["name"]) as image:
        assert image.n_frames == 2


def test_load_mode_migration_and_validation():
    assert advanced.parse_adv_state('{}')["load_mode"] == "normal"
    assert advanced.parse_adv_state('{"load_mode": []}')["load_mode"] == "normal"
    assert advanced.parse_adv_state('{"load_mode": "direct"}')["load_mode"] == "direct"


def test_direct_source_load_hash_and_missing_message(tmp_path, monkeypatch):
    result = direct.store_direct_image(_encoded(), "a" * 32, tmp_path)
    path = tmp_path / result["subfolder"] / result["name"]
    reference = f'{result["subfolder"]}/image [temp]'
    monkeypatch.setattr(advanced, "resolve_annotated_image_path", lambda _: (reference, path))
    node = advanced.LoadImageXAdv()
    before = node.IS_CHANGED(reference)
    image, mask, inverted, w, h = node.load_image(reference)
    assert (w, h) == (16, 12)
    assert tuple(image.shape) == (1, 12, 16, 3)
    assert bool((mask == 1).all())  # Original transparent alpha survives.
    assert bool((inverted == 0).all())
    direct.store_direct_image(_encoded("JPEG", "RGB"), "a" * 32, tmp_path)
    assert node.IS_CHANGED(reference) != before
    path.unlink()
    assert "Temporary image unavailable" in node.VALIDATE_INPUTS(reference)


def _state(**updates):
    state = dict(advanced.DEFAULT_ADV_STATE)
    state.update(updates)
    return state


def _pair(size=(320, 240), color=(20, 40, 60)):
    return Image.new("RGB", size, color), Image.new("L", size, 0)


def test_state_parser_uses_safe_defaults_and_known_enums():
    assert advanced.parse_adv_state("not json") == advanced.DEFAULT_ADV_STATE
    parsed = advanced.parse_adv_state(json.dumps({
        "mode": "unknown",
        "resample": "unknown",
        "crop_snap": 16,
        "output_snap": 13,
        "crop_enabled": 1,
    }))
    assert parsed["mode"] == "off"
    assert parsed["resample"] == "auto"
    assert parsed["crop_snap"] == 16
    assert parsed["output_snap"] == 0
    assert parsed["crop_enabled"] is True


def test_crop_snap_constrains_size_without_snapping_origin():
    state = _state(
        crop_enabled=True,
        crop_snap=16,
        crop_rect={"x": 0.13, "y": 0.07, "w": 0.27, "h": 0.34},
    )
    box = advanced.crop_box_from_state(100, 100, state)
    assert box == (13, 7, 45, 39)
    assert box[0] % 16 != 0
    assert box[1] % 16 != 0
    assert (box[2] - box[0], box[3] - box[1]) == (32, 32)
    assert advanced.crop_box_from_state(100, 100, {**state, "crop_enabled": False}) is None


@pytest.mark.parametrize(
    ("updates", "expected"),
    [
        ({"mode": "off"}, (320, 240)),
        ({"mode": "max_mp", "max_mp": 0.01}, (118, 89)),
        ({"mode": "longest_side", "longest_side": 160}, (160, 120)),
        ({"mode": "scale_factor", "scale_factor": 0.5}, (160, 120)),
        ({"mode": "fit_inside", "fit_w": 100, "fit_h": 100}, (100, 75)),
        ({"mode": "cover", "cover_w": 100, "cover_h": 100, "cover_action": "fill"}, (100, 100)),
        ({"mode": "cover", "cover_w": 100, "cover_h": 80, "cover_action": "crop"}, (100, 80)),
        ({"mode": "match_ratio", "ratio_w": 1, "ratio_h": 1}, (240, 240)),
        ({"mode": "pad", "pad_left": 10, "pad_right": 20, "pad_top": 5, "pad_bottom": 15}, (350, 260)),
    ],
)
def test_resize_modes_produce_expected_dimensions(updates, expected):
    image, mask = _pair()
    output, output_mask = advanced.apply_resize_mode(image, mask, _state(**updates))
    assert output.size == expected
    assert output_mask.size == expected


def test_crop_runs_before_resize_and_output_snap_is_independent():
    image, mask = _pair((200, 100))
    state = _state(
        crop_enabled=True,
        crop_snap=16,
        crop_rect={"x": 0.11, "y": 0.1, "w": 0.51, "h": 0.72},
        mode="scale_factor",
        scale_factor=0.5,
        output_snap=8,
    )
    box = advanced.crop_box_from_state(200, 100, state)
    assert box == (22, 10, 118, 90)
    cropped = image.crop(box)
    cropped_mask = mask.crop(box)
    output, output_mask = advanced.apply_resize_mode(cropped, cropped_mask, state)
    assert output.size == (48, 40)
    assert output_mask.size == (48, 40)


def test_alpha_mask_is_cropped_and_pad_marks_only_new_pixels():
    rgba = np.zeros((20, 30, 4), dtype=np.uint8)
    rgba[..., :3] = (100, 120, 140)
    rgba[..., 3] = 255
    rgba[5:15, 10:20, 3] = 0
    frame = Image.fromarray(rgba, "RGBA")
    state = _state(
        crop_enabled=True,
        crop_rect={"x": 10 / 30, "y": 5 / 20, "w": 10 / 30, "h": 10 / 20},
        mode="pad",
        pad_left=2,
        pad_right=3,
        pad_top=4,
        pad_bottom=1,
    )
    image, mask = advanced.process_frame(frame, state)
    assert image.size == (15, 15)
    mask_array = np.asarray(mask)
    assert np.all(mask_array[:4, :] == 255)
    assert np.all(mask_array[4:14, 2:12] == 255)


def test_load_image_adv_preserves_multiframe_batch(tmp_path, monkeypatch):
    first = Image.new("RGB", (16, 12), (255, 0, 0))
    second = Image.new("RGB", (16, 12), (0, 255, 0))
    path = tmp_path / "animated.gif"
    first.save(path, save_all=True, append_images=[second], duration=20, loop=0)
    monkeypatch.setattr(advanced, "resolve_annotated_image_path", lambda _image: ("animated.gif", path))

    state = _state(mode="longest_side", longest_side=8)
    image, mask, inverted_mask, width, height = advanced.LoadImageXAdv().load_image("animated.gif", json.dumps(state))

    assert tuple(image.shape) == (2, 6, 8, 3)
    assert tuple(mask.shape) == (2, 6, 8)
    assert tuple(inverted_mask.shape) == (2, 6, 8)
    assert np.allclose((mask + inverted_mask).numpy(), 1.0)
    assert (width, height) == (8, 6)


def test_node_schema_has_five_ordered_outputs_and_hidden_upload_input(monkeypatch):
    monkeypatch.setattr(advanced, "get_catalog", lambda: ([{"path": "nested/example.png"}], "etag"))
    inputs = advanced.LoadImageXAdv.INPUT_TYPES()["required"]
    assert tuple(inputs) == ("image", "workflowx_state")
    assert inputs["image"][0] == ["nested/example.png"]
    assert inputs["image"][1]["image_upload"] is True
    assert advanced.LoadImageXAdv.RETURN_TYPES == ("IMAGE", "MASK", "MASK", "INT", "INT")
    assert advanced.LoadImageXAdv.RETURN_NAMES == ("image", "mask", "inverted_mask", "width", "height")
    assert advanced.NODE_DISPLAY_NAME_MAPPINGS["WorkflowX_LoadImageXAdv"] == "Load ImageX Adv"


def test_regular_and_inverted_masks_remain_complementary_after_crop_pad_and_snap(tmp_path, monkeypatch):
    rgba = np.zeros((24, 32, 4), dtype=np.uint8)
    rgba[..., :3] = (40, 80, 120)
    rgba[..., 3] = 255
    rgba[4:20, 8:24, 3] = 64
    path = tmp_path / "alpha.png"
    Image.fromarray(rgba, "RGBA").save(path)
    monkeypatch.setattr(advanced, "resolve_annotated_image_path", lambda _image: ("alpha.png", path))
    state = _state(
        crop_enabled=True,
        crop_rect={"x": 0.125, "y": 0.125, "w": 0.75, "h": 0.75},
        mode="pad",
        pad_left=3,
        pad_right=5,
        pad_top=2,
        pad_bottom=6,
        output_snap=8,
    )

    image, mask, inverted, width, height = advanced.LoadImageXAdv().load_image("alpha.png", json.dumps(state))

    assert tuple(image.shape[1:3]) == (height, width)
    assert tuple(mask.shape[1:]) == (height, width)
    assert np.allclose((mask + inverted).numpy(), 1.0)
    assert torch_all_between_zero_and_one(mask)
    assert torch_all_between_zero_and_one(inverted)


def torch_all_between_zero_and_one(tensor):
    return bool(((tensor >= 0.0) & (tensor <= 1.0)).all())
