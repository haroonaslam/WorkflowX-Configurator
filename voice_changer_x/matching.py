"""Approximate, non-parallel acoustic reference matching. No speaker model is used."""

from __future__ import annotations

import math

import numpy as np
from scipy.signal import resample_poly

from . import CONTROLS, _world, validate_audio


ANALYSIS_RATE = 24000
WINDOW_SECONDS = 10
MAX_WINDOWS = 3


def analyze_voice(audio, label, world=None):
    waveform, rate = validate_audio(audio, label)
    if waveform.shape[-1] / rate < 0.5:
        raise ValueError(f"{label}: provide at least half a second of clear spoken audio (several seconds recommended).")
    # A shared set of sliders describes one voice. Avoid phase cancellation when
    # choosing a channel; pool separated windows rather than joining waveforms.
    samples = waveform[0].detach().cpu().double().numpy()
    channel = int(np.argmax(np.mean(samples ** 2, axis=1)))
    samples = samples[channel]
    width = min(len(samples), WINDOW_SECONDS * rate)
    count = min(MAX_WINDOWS, math.ceil(len(samples) / width))
    # Two full windows would overlap on an 11-second clip; split instead.
    width = min(width, len(samples) // count)
    starts = np.linspace(0, len(samples) - width, count).astype(int)
    windows = [samples[start:start + width] for start in starts]
    peak = max(float(np.max(np.abs(window))) for window in windows)
    if peak < 1e-7:
        raise ValueError(f"{label}: audio is silent; provide a clear spoken voice.")
    world = world or _world()
    pitches, envelopes, noises, active_samples = [], [], [], []
    frame_period = 5.0
    divisor = math.gcd(rate, ANALYSIS_RATE)
    for original in windows:
        # Gate in short blocks before normalizing for pitch/noise analysis.
        block = max(1, round(rate * 0.02))
        padded = np.pad(original, (0, (-len(original)) % block))
        blocks = padded.reshape(-1, block)
        rms = np.sqrt(np.mean(blocks ** 2, axis=1))
        active = rms > max(1e-7, float(rms.max()) * 0.01)
        if not active.any():
            continue
        active_samples.append(blocks[active].ravel())
        gain = 0.1 / max(1e-12, float(np.sqrt(np.mean(blocks[active] ** 2))))
        working = original * gain
        if rate != ANALYSIS_RATE:
            working = resample_poly(working, ANALYSIS_RATE // divisor, rate // divisor)
        working = np.ascontiguousarray(working, dtype=np.float64)
        f0, times = world.harvest(working, ANALYSIS_RATE, f0_floor=50.0, f0_ceil=800.0, frame_period=frame_period)
        frame_blocks = np.minimum((times * rate / block).astype(int), len(active) - 1)
        voiced = (f0 > 0) & active[frame_blocks]
        if not voiced.any():
            continue
        spectrum = world.cheaptrick(working, f0, times, ANALYSIS_RATE, fft_size=2048)
        noise = world.d4c(working, f0, times, ANALYSIS_RATE, fft_size=2048)
        pitches.append(f0[voiced])
        db = 10 * np.log10(np.maximum(spectrum[voiced], 1e-16))
        # Equal frame weights keep occasional loud vowels from dominating timbre.
        envelopes.append(db - np.mean(db, axis=1, keepdims=True))
        noises.append(noise[voiced])
    voiced_count = sum(len(pitch) for pitch in pitches)
    if voiced_count < 40:
        raise ValueError(f"{label}: too little reliably voiced speech. Use a longer clear recording without music or overlapping speakers.")
    pitch = np.concatenate(pitches)
    log_pitch = 12 * np.log2(pitch)
    active_signal = np.concatenate(active_samples)
    warnings = []
    if voiced_count * frame_period / 1000 < 1:
        warnings.append(f"{label}: less than one second of voiced speech; estimates may be unstable.")
    if waveform.shape[0] > 1:
        warnings.append(f"{label}: analyzed the first batch item; settings apply to the whole batch.")
    if len(samples) / rate > WINDOW_SECONDS * MAX_WINDOWS:
        warnings.append(f"{label}: sampled up to 30 seconds across the recording.")
    if rate < 16000:
        warnings.append(f"{label}: low sample rate limits timbre and formant estimates.")
    return {
        "median_pitch_hz": float(np.median(pitch)),
        "pitch_range_semitones": float(np.percentile(log_pitch, 90) - np.percentile(log_pitch, 10)),
        "active_rms_dbfs": float(20 * np.log10(max(1e-12, np.sqrt(np.mean(active_signal ** 2))))),
        "voiced_seconds": voiced_count * frame_period / 1000,
        "analyzed_seconds": sum(len(window) for window in windows) / rate,
        "channel": channel,
        "band_limit": min(6000, rate / 2 * 0.95),
        "frequencies": np.linspace(0, ANALYSIS_RATE / 2, 1025),
        "envelope_db": np.median(np.concatenate(envelopes), axis=0),
        "aperiodicity": np.median(np.concatenate(noises), axis=0),
        "warnings": warnings,
    }


def fit_envelope(source, reference):
    """Jointly fit frequency scaling and spectral tilt, removing level offset."""
    frequencies = source["frequencies"]
    band = (frequencies >= 250) & (frequencies <= min(source["band_limit"], reference["band_limit"]))
    if np.count_nonzero(band) < 20:
        raise ValueError("Recordings have too little frequency bandwidth for reference matching.")
    f = frequencies[band]
    x = np.log2(f / 1000)
    centered = x - x.mean()
    target = reference["envelope_db"][band]

    def candidate(shift):
        warped = np.interp(f / (2 ** (shift / 12)), frequencies, source["envelope_db"])
        difference = target - warped
        tilt = float(np.clip(np.dot(centered, difference - difference.mean()) / np.dot(centered, centered), -12, 12))
        residual = difference - np.clip(tilt * x, -24, 24)
        residual -= np.median(residual)
        # Trim the largest errors: unmatched phonemes should not set the whole fit.
        loss = float(np.mean(np.sort(residual ** 2)[:max(1, int(len(residual) * 0.9))]))
        return loss, float(shift), tilt

    coarse = min((candidate(shift) for shift in np.arange(-12, 12.001, 0.1)), key=lambda item: (item[0], abs(item[1])))
    best = min((candidate(shift) for shift in np.arange(max(-12, coarse[1] - 0.1), min(12, coarse[1] + 0.1) + 0.005, 0.01)), key=lambda item: (item[0], abs(item[1])))
    baseline = candidate(0)
    weak = baseline[0] - best[0] < max(0.02, baseline[0] * 0.02)
    if weak:
        best = baseline
    return best[1], best[2], weak and baseline[0] > 0.1


def estimate_settings(source, reference):
    warnings = [*source.get("warnings", []), *reference.get("warnings", [])]
    shift, tilt, weak_formants = fit_envelope(source, reference)
    if weak_formants:
        warnings.append("Formant estimate was inconclusive; formant shift was left neutral.")
    source_range = source["pitch_range_semitones"]
    if source_range < 0.25:
        variation = 100.0
        if reference["pitch_range_semitones"] >= 0.25:
            warnings.append("Source pitch is nearly flat; pitch variation cannot recreate the reference's intonation.")
    else:
        variation = 100 * reference["pitch_range_semitones"] / source_range

    frequencies = source["frequencies"]
    band = (frequencies >= 1000) & (frequencies <= min(source["band_limit"], reference["band_limit"], 5000))
    weights = 10 ** ((reference["envelope_db"][band] - np.max(reference["envelope_db"][band])) / 10)
    source_noise = float(np.average(source["aperiodicity"][band], weights=weights))
    target_noise = float(np.average(reference["aperiodicity"][band], weights=weights))
    breathiness = 100 * (target_noise - source_noise) / max(1e-6, (1 - source_noise) * 0.8 if target_noise >= source_noise else source_noise * 0.95)
    raw = {
        "pitch_shift": 12 * math.log2(reference["median_pitch_hz"] / source["median_pitch_hz"]),
        "formant_shift": shift,
        "timbre": tilt,
        "breathiness": breathiness,
        "pitch_variation": variation,
        "output_gain": reference["active_rms_dbfs"] - source["active_rms_dbfs"],
    }
    settings = {}
    limited = []
    for name, value in raw.items():
        _, minimum, maximum, step, _ = CONTROLS[name]
        if not math.isfinite(value):
            raise ValueError(f"Could not estimate {name} from these recordings.")
        if value < minimum - step / 2 or value > maximum + step / 2:
            limited.append(name.replace("_", " "))
        decimals = max(0, round(-math.log10(step)))
        settings[name] = round(float(np.clip(value, minimum, maximum)), decimals)
    if limited:
        warnings.append("Control limits reached: " + ", ".join(limited) + ".")
    return {"settings": settings, "warnings": warnings}


def match_reference(source_audio, reference_audio):
    if reference_audio is None:
        raise ValueError("Connect reference audio before clicking Match Reference.")
    world = _world()
    source = analyze_voice(source_audio, "Source audio", world)
    reference = analyze_voice(reference_audio, "Reference audio", world)
    report = estimate_settings(source, reference)
    public_keys = ("median_pitch_hz", "pitch_range_semitones", "active_rms_dbfs", "voiced_seconds", "analyzed_seconds", "channel")
    report["source"] = {key: source[key] for key in public_keys}
    report["reference"] = {key: reference[key] for key in public_keys}
    return report
