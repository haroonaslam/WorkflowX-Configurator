import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest
import torch


SPEC = importlib.util.spec_from_file_location("voice_changer_x_test", Path(__file__).resolve().parents[1] / "voice_changer_x" / "__init__.py")
voice = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = voice
SPEC.loader.exec_module(voice)


def audio(rate=24000, length=12000):
    time = np.arange(length) / rate
    # A periodic vowel-like source gives Harvest both harmonics and a stable fundamental.
    signal = sum(np.sin(2 * np.pi * 150 * k * time) / k for k in range(1, 12)) * 0.15
    return {"sample_rate": rate, "waveform": torch.tensor(signal, dtype=torch.float32)[None, None, :]}


def test_neutral_is_exact_bypass_and_does_not_load_world(monkeypatch):
    monkeypatch.setattr(voice, "_world", lambda: pytest.fail("unnecessary dependency load"))
    source = audio()
    assert voice.VoiceChangerX().transform(source)[0] is source


def test_gain_only_and_linked_channel_peak_protection(monkeypatch):
    monkeypatch.setattr(voice, "_world", lambda: pytest.fail("gain should not resynthesize"))
    source = {"sample_rate": 24000, "waveform": torch.tensor([[[0.8, -0.8], [0.4, -0.4]]])}
    original = source["waveform"].clone()
    result = voice.VoiceChangerX().transform(source, output_gain=12)[0]["waveform"]
    torch.testing.assert_close(result, torch.tensor([[[1., -1.], [0.5, -0.5]]]))
    assert torch.equal(source["waveform"], original)


def features(**overrides):
    controls = {key: spec[0] for key, spec in voice.CONTROLS.items() if key != "output_gain"}
    controls.update(overrides)
    f = np.linspace(0, 12000, 513)
    spectrum = np.tile(1e-5 + np.exp(-((f - 1000) / 150) ** 2), (4, 1))
    noise = np.full_like(spectrum, 0.2)
    pitch = np.array([100., 200., 400., 0.])
    return voice.transform_features(pitch, spectrum, noise, 24000, **controls)


def test_pitch_shift_and_variation_preserve_unvoiced():
    np.testing.assert_allclose(features(pitch_shift=12)[0], [200, 400, 800, 0])
    np.testing.assert_allclose(features(pitch_variation=0)[0], [200, 200, 200, 0])
    np.testing.assert_allclose(features(pitch_variation=200)[0], [50, 200, 800, 0])


def test_formants_move_without_pitch_change():
    baseline = features()
    shifted = features(formant_shift=12)
    np.testing.assert_equal(shifted[0], baseline[0])
    bins = np.linspace(0, 12000, 513)
    assert abs(bins[shifted[1][0].argmax()] - 2000) < 50
    np.testing.assert_allclose(features(pitch_shift=5)[1], baseline[1])


def test_brightness_and_breathiness_are_bounded_and_directional():
    neutral = features()
    bright = features(timbre=12)
    dark = features(timbre=-12)
    assert bright[1][0, 180] > neutral[1][0, 180] > dark[1][0, 180]
    assert bright[1][0, 10] < neutral[1][0, 10] < dark[1][0, 10]
    for amount in (-100, 100):
        changed = features(breathiness=amount)[2]
        assert np.all((changed > 0) & (changed < 1))
        assert (changed[0, 0] > neutral[2][0, 0]) == (amount > 0)
        np.testing.assert_equal(changed[3], neutral[2][3])


@pytest.mark.parametrize("rate,length", [(24000, 12000), (8000, 1200), (48000, 10), (16000, 1), (24000, 0)])
def test_synthesis_preserves_format_and_finite_bounded_output(rate, length):
    pytest.importorskip("pyworld")
    source = audio(rate, length)
    if 0 < length < 100:
        source["waveform"][..., 0] = 0.05  # Exercise short-clip padding, not the silence bypass.
    source["waveform"] = source["waveform"].repeat(2, 2, 1)
    original = source["waveform"].clone()
    result = voice.VoiceChangerX().transform(source, pitch_shift=4.25, formant_shift=2.1, timbre=1.5, breathiness=10)[0]
    assert result["sample_rate"] == rate
    assert result["waveform"].shape == original.shape
    assert result["waveform"].dtype == original.dtype
    assert torch.isfinite(result["waveform"]).all()
    if length:
        assert result["waveform"].abs().max() <= 1
    assert torch.equal(source["waveform"], original)


def test_actual_pitch_accuracy():
    world = pytest.importorskip("pyworld")
    result = voice.VoiceChangerX().transform(audio(length=24000), pitch_shift=12)[0]
    signal = result["waveform"][0, 0].numpy().astype(np.float64)
    pitch, _ = world.harvest(signal, 24000, f0_floor=60, f0_ceil=800)
    assert np.count_nonzero(pitch) > 100
    assert np.median(pitch[pitch > 0]) == pytest.approx(300, abs=6)


def test_extreme_controls():
    pytest.importorskip("pyworld")
    for sign in (-1, 1):
        result = voice.VoiceChangerX().transform(audio(), pitch_shift=sign*24, formant_shift=sign*12,
                                               timbre=sign*12, breathiness=sign*100, pitch_variation=200, output_gain=12)[0]
        assert torch.isfinite(result["waveform"]).all()
        assert result["waveform"].abs().max() <= 1


def test_silence_skips_dependency(monkeypatch):
    monkeypatch.setattr(voice, "_world", lambda: pytest.fail("silence should not resynthesize"))
    source = {"sample_rate": 24000, "waveform": torch.zeros(1, 2, 100)}
    assert not voice.VoiceChangerX().transform(source, pitch_shift=5)[0]["waveform"].any()


@pytest.mark.parametrize("changes", [{"pitch_shift": float("nan")}, {"formant_shift": 13}, {"timbre": "2"}, {"output_gain": True}])
def test_invalid_controls(changes):
    with pytest.raises(ValueError, match="finite number"):
        voice.VoiceChangerX().transform(audio(), **changes)


@pytest.mark.parametrize("source", [None, {"waveform": torch.zeros(2, 5), "sample_rate": 24000},
    {"waveform": torch.zeros(1, 1, 4), "sample_rate": 0},
    {"waveform": torch.full((1, 1, 4), float("nan")), "sample_rate": 24000}])
def test_invalid_audio(source):
    with pytest.raises(ValueError, match="Voice ChangerX"):
        voice.VoiceChangerX().transform(source)


def test_dependency_error(monkeypatch):
    def unavailable(name):
        raise ImportError(name)
    monkeypatch.setattr(voice.importlib, "import_module", unavailable)
    with pytest.raises(RuntimeError, match="ComfyUI's Python"):
        voice.VoiceChangerX().transform(audio(), pitch_shift=1)


def test_reference_is_only_requested_for_matching():
    node = voice.VoiceChangerX()
    assert node.check_lazy_status(audio()) == []
    assert node.check_lazy_status(audio(), match_request="request") == ["reference_audio"]
    assert node.check_lazy_status(audio(), reference_audio=audio(), match_request="request") == []
    source = audio()
    assert node.transform(source, reference_audio={"invalid": True})[0] is source


def test_match_error_returns_report_without_changing_source():
    source = audio()
    result = voice.VoiceChangerX().transform(source, match_request="test-error")
    report = result["ui"]["voice_reference_match"][0]
    assert report["request_id"] == "test-error"
    assert "Connect reference audio" in report["error"]
    assert "settings" not in report
    assert result["result"][0] is source
