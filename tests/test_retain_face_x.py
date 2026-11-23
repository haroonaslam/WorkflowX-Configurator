import importlib.util
from pathlib import Path

import pytest
import torch


spec = importlib.util.spec_from_file_location(
    "workflowx_retain_face_test", Path(__file__).resolve().parents[1] / "retain_face_x.py",
)
retain_face = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retain_face)


def test_full_protection_keeps_face_cell_anchored_and_preserves_latent(monkeypatch):
    monkeypatch.setattr(retain_face, "detect_faces", lambda _image: [[8, 8, 9, 9]])
    samples = torch.randn((2, 4, 4, 4))
    original = {"samples": samples, "batch_index": [2, 3]}
    protected, preview = retain_face.RetainFaceX().protect(
        torch.zeros((1, 32, 32, 3)), original, face_margin=0, feather=0,
    )
    assert protected["samples"] is samples
    assert protected["batch_index"] == [2, 3]
    assert "noise_mask" not in original
    assert preview[0, 8, 8] == 1
    assert protected["noise_mask"].shape == (2, 1, 4, 4)
    assert (protected["noise_mask"][:, 0, 1, 1] == 0).all()
    assert (protected["noise_mask"][:, 0, 3, 3] == 1).all()


def test_margin_feather_and_strength_keep_an_opaque_core_at_full_strength(monkeypatch):
    monkeypatch.setattr(retain_face, "detect_faces", lambda _image: [[10, 10, 18, 18], [24, 24, 27, 27]])
    protected, mask = retain_face.RetainFaceX().protect(
        torch.zeros((1, 32, 32, 3)), {"samples": torch.zeros((1, 4, 32, 32))},
        protection_strength=50, face_margin=2, feather=4,
    )
    assert mask[0, 8, 8] == .5
    assert 0 < mask[0, 7, 8] < .5
    assert mask[0, 0, 0] == 0
    assert mask[0, 24, 24] == .5
    torch.testing.assert_close(protected["noise_mask"][:, 0], 1 - mask)


def test_existing_noise_mask_can_only_become_more_restrictive(monkeypatch):
    monkeypatch.setattr(retain_face, "detect_faces", lambda _image: [[16, 16, 24, 24]])
    existing = torch.full((1, 1, 4, 4), .6)
    existing[..., 0, 0] = 0
    latent = {"samples": torch.zeros((1, 4, 4, 4)), "noise_mask": existing}
    protected, _ = retain_face.RetainFaceX().protect(
        torch.zeros((1, 32, 32, 3)), latent, protection_strength=50, face_margin=0, feather=0,
    )
    assert latent["noise_mask"] is existing
    assert protected["noise_mask"][0, 0, 0, 0] == 0
    assert protected["noise_mask"][0, 0, 2, 2] == pytest.approx(.3)
    assert protected["noise_mask"][0, 0, 3, 3] == pytest.approx(.6)


def test_no_face_and_disabled_keep_the_original_latent(monkeypatch, caplog):
    calls = []
    def detect(image):
        calls.append(image)
        return []
    monkeypatch.setattr(retain_face, "detect_faces", detect)
    image = torch.zeros((1, 32, 32, 3))
    latent = {"samples": torch.zeros((1, 4, 4, 4)), "noise_mask": torch.ones((1, 4, 4))}
    disabled, disabled_preview = retain_face.RetainFaceX().protect(image, latent, protection_strength=0)
    assert disabled is latent and not disabled_preview.any() and not calls
    unchanged, preview = retain_face.RetainFaceX().protect(image, latent)
    assert unchanged is latent and not preview.any()
    assert "found no face" in caplog.text


def test_vae_crop_and_mismatched_framing():
    assert retain_face.latent_geometry(515, 773, 64, 96) == (1, 2, 512, 768)
    with pytest.raises(ValueError, match="same framing"):
        retain_face.latent_geometry(512, 768, 64, 64)


@pytest.mark.parametrize("mask_has_time_axis", [False, True])
def test_single_frame_5d_latent_preserves_samples_and_per_image_masks(monkeypatch, mask_has_time_axis):
    from comfy.utils import reshape_mask

    monkeypatch.setattr(retain_face, "detect_faces", lambda _image: [[8, 8, 16, 16]])
    samples = torch.randn((2, 16, 1, 4, 4))
    original_mask = torch.ones((2, 1, 4, 4))
    original_mask[0, 0, 0, 0] = 0
    original_mask[1, 0, 3, 3] = .5
    if mask_has_time_axis:
        original_mask = original_mask.unsqueeze(2)
    latent = {"samples": samples, "noise_mask": original_mask}
    result, preview = retain_face.RetainFaceX().protect(
        torch.zeros((2, 32, 32, 3)), latent, face_margin=0, feather=0,
    )
    mask = result["noise_mask"]
    assert result["samples"] is samples
    assert latent["noise_mask"] is original_mask
    assert mask.shape == (2, 1, 1, 4, 4)
    assert preview.shape == (2, 32, 32)
    assert mask[:, 0, 0, 1, 1].tolist() == [0, 0]
    assert mask[:, 0, 0, 0, 0].tolist() == [0, 1]
    assert mask[:, 0, 0, 3, 3].tolist() == [1, .5]
    assert reshape_mask(mask, samples.shape).shape == samples.shape


def test_multi_frame_video_latent_is_rejected():
    with pytest.raises(ValueError, match="still-image latent"):
        retain_face.RetainFaceX().protect(
            torch.zeros((1, 32, 32, 3)), {"samples": torch.zeros((1, 16, 2, 4, 4))},
        )
