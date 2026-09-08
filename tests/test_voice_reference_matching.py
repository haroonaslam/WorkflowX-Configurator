import numpy as np
import pytest
import torch

from test_voice_changer_x import audio, voice
from voice_changer_x_test import matching


def profile(pitch=150., spread=4., gain=-20.):
    f = np.linspace(0, 12000, 1025)
    # Three broad resonances, rather than individual pitch harmonics.
    power = 1e-5 + sum(amplitude * np.exp(-0.5 * ((f - center) / width) ** 2)
                       for amplitude, center, width in [(1, 700, 120), (.7, 1600, 180), (.4, 2900, 220)])
    return dict(median_pitch_hz=pitch, pitch_range_semitones=spread, active_rms_dbfs=gain,
                frequencies=f, envelope_db=10*np.log10(power), aperiodicity=np.full_like(f, .2),
                band_limit=6000, warnings=[])


def test_identical_profiles_produce_neutral_settings():
    source = profile()
    report = matching.estimate_settings(source, source)
    assert report["settings"] == {name: spec[0] for name, spec in voice.CONTROLS.items()}


def test_pitch_variation_and_level_estimates_are_relative():
    source, target = profile(), profile(pitch=300, spread=6, gain=-14)
    settings = matching.estimate_settings(source, target)["settings"]
    assert settings["pitch_shift"] == 12
    assert settings["pitch_variation"] == 150
    assert settings["output_gain"] == 6


def test_joint_fit_recovers_formant_scaling_and_brightness():
    source, target = profile(), profile()
    f = source["frequencies"]
    target["envelope_db"] = np.interp(f / 2**(2.5/12), f, source["envelope_db"]) + np.clip(2*np.log2(np.maximum(f,50)/1000),-24,24)
    settings = matching.estimate_settings(source, target)["settings"]
    assert settings["formant_shift"] == pytest.approx(2.5, abs=.15)
    assert settings["timbre"] == pytest.approx(2, abs=.2)


@pytest.mark.parametrize("amount", [-60, 40])
def test_breathiness_inverts_the_transform_approximately(amount):
    source, target = profile(), profile()
    target["aperiodicity"] = source["aperiodicity"] + ((1-source["aperiodicity"])*.8 if amount > 0 else source["aperiodicity"]*.95) * amount/100
    assert matching.estimate_settings(source, target)["settings"]["breathiness"] == amount


def test_flat_pitch_and_limits_report_uncertainty():
    source, target = profile(spread=0), profile(pitch=1200, gain=0)
    report = matching.estimate_settings(source, target)
    assert report["settings"]["pitch_variation"] == 100
    assert report["settings"]["pitch_shift"] == 24
    assert report["settings"]["output_gain"] == 12
    assert any("nearly flat" in warning for warning in report["warnings"])
    assert any("limits reached" in warning for warning in report["warnings"])


def test_real_analysis_identical_audio_and_different_sample_rates():
    pytest.importorskip("pyworld")
    source = audio(length=24000)
    report = matching.match_reference(source, source)
    assert report["settings"] == {name: spec[0] for name, spec in voice.CONTROLS.items()}
    resampled = audio(rate=48000,length=48000)
    cross_rate = matching.match_reference(source, resampled)
    assert cross_rate["settings"]["pitch_shift"] == pytest.approx(0, abs=.1)
    assert abs(cross_rate["settings"]["formant_shift"]) < .5


def test_gain_estimation_ignores_leading_and_trailing_silence():
    pytest.importorskip("pyworld")
    source = audio(length=24000)
    target = {**source, "waveform": torch.nn.functional.pad(source["waveform"]*.5,(12000,12000))}
    report = matching.match_reference(source,target)
    assert report["settings"]["output_gain"] == pytest.approx(-6, abs=.2)


@pytest.mark.parametrize("samples", [torch.zeros(1,1,24000), torch.ones(1,1,10)*.1])
def test_silence_and_short_reference_fail_without_estimates(samples):
    with pytest.raises(ValueError):
        matching.analyze_voice({"sample_rate":24000,"waveform":samples},"Reference audio")


def test_unvoiced_noise_fails_cleanly():
    class Unvoiced:
        def harvest(self, samples, rate, **kwargs):
            times = np.arange(0,len(samples)/rate,.005)
            return np.zeros_like(times),times
    with pytest.raises(ValueError,match="reliably voiced"):
        matching.analyze_voice(audio(length=24000),"Reference audio",Unvoiced())


def test_match_request_emits_settings_and_source_passthrough():
    pytest.importorskip("pyworld")
    source = audio(length=24000)
    result = voice.VoiceChangerX().transform(source, reference_audio=source, match_request="unique-request")
    report = result["ui"]["voice_reference_match"][0]
    assert report["request_id"] == "unique-request"
    assert set(report["settings"]) == set(voice.CONTROLS)
    assert result["result"][0] is source
