"""Local, model-free voice transformation for ComfyUI."""

from __future__ import annotations

import importlib
import math
import numbers


# name: default, minimum, maximum, step, description
CONTROLS = {
    "pitch_shift": (0.0, -24.0, 24.0, 0.01, "Pitch shift in semitones; duration stays unchanged."),
    "formant_shift": (0.0, -12.0, 12.0, 0.01, "Resonance shift in semitones: negative = larger/deeper, positive = smaller/lighter."),
    "timbre": (0.0, -12.0, 12.0, 0.1, "Brightness in dB/octave: negative = warmer/darker, positive = brighter. Tilt is bounded to +/-24 dB."),
    "breathiness": (0.0, -100.0, 100.0, 1.0, "Relative noise adjustment on voiced speech: negative = less airy, positive = more airy."),
    "pitch_variation": (100.0, 0.0, 200.0, 1.0, "Intonation range: 0% = flat voiced pitch, 100% = original, 200% = exaggerated."),
    "output_gain": (0.0, -24.0, 12.0, 0.1, "Output gain in dB. Peaks above full scale are attenuated to prevent clipping."),
}


def _world():
    try:
        return importlib.import_module("pyworld")
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "Voice ChangerX requires PyWORLD. Install it in ComfyUI's Python environment "
            "with: python -m pip install pyworld . Then restart ComfyUI."
        ) from exc


def validate_audio(audio, label="source audio"):
    import torch

    prefix = f"Voice ChangerX {label}"
    if not isinstance(audio, dict):
        raise ValueError(f"{prefix}: expected ComfyUI AUDIO with waveform and sample_rate.")
    waveform, rate = audio.get("waveform"), audio.get("sample_rate")
    if not isinstance(waveform, torch.Tensor) or waveform.ndim != 3 or not waveform.is_floating_point() or min(waveform.shape[:2]) < 1:
        raise ValueError(f"{prefix}: waveform must be a floating tensor shaped [batch, channels, samples].")
    if isinstance(rate, bool) or not isinstance(rate, numbers.Integral) or rate <= 0:
        raise ValueError(f"{prefix}: sample_rate must be a positive integer.")
    if not torch.isfinite(waveform).all():
        raise ValueError(f"{prefix}: waveform contains NaN or infinite samples.")
    return waveform, int(rate)


def transform_features(f0, spectrum, aperiodicity, rate, pitch_shift, formant_shift, timbre, breathiness, pitch_variation):
    """Transform independent WORLD features without modifying the analysis arrays."""
    import numpy as np

    pitch = f0.copy()
    voiced = pitch > 0
    if voiced.any():
        log_pitch = np.log2(pitch[voiced])
        center = np.median(log_pitch)
        pitch[voiced] = np.clip(2 ** (center + (log_pitch - center) * pitch_variation / 100 + pitch_shift / 12), 20, rate / 4)

    frequencies = np.linspace(0, rate / 2, spectrum.shape[1])
    envelope = spectrum.copy()
    if formant_shift:
        source_frequencies = frequencies / (2 ** (formant_shift / 12))
        # Log-power interpolation avoids negative powers and keeps resonances smooth.
        for index, frame in enumerate(spectrum):
            envelope[index] = np.exp(np.interp(source_frequencies, frequencies, np.log(np.maximum(frame, 1e-16)), right=math.log(1e-16)))
    if timbre:
        tilt_db = np.clip(timbre * np.log2(np.maximum(frequencies, 50) / 1000), -24, 24)
        envelope *= 10 ** (tilt_db / 10)  # WORLD's envelope is power, not amplitude.

    noise = aperiodicity.copy()
    if breathiness and voiced.any():
        amount = breathiness / 100
        if amount > 0:
            noise[voiced] += (1 - noise[voiced]) * amount * 0.8
        else:
            noise[voiced] *= 1 + amount * 0.95
    return pitch, np.maximum(envelope, 1e-16), np.clip(noise, 0.001, 1 - 1e-12)


def _fit_length(samples, length):
    import numpy as np
    return np.pad(samples[:length], (0, max(0, length - len(samples))))


def _process_channel(samples, rate, controls, world):
    import numpy as np
    from scipy.signal import resample_poly

    original_length = len(samples)
    if original_length == 0 or not np.any(samples):
        return samples.copy()
    source_rms = np.sqrt(np.mean(samples ** 2))
    working_rate = max(rate, 16000)
    divisor = math.gcd(rate, working_rate)
    working = resample_poly(samples, working_rate // divisor, rate // divisor) if rate < working_rate else samples
    working_length = len(working)
    # Guard the native analysis on tiny clips. Keep source timing by padding at the end.
    working = np.ascontiguousarray(_fit_length(working, max(working_length, int(working_rate * 0.1))), dtype=np.float64)
    f0, times = world.harvest(working, working_rate, f0_floor=50.0, f0_ceil=800.0, frame_period=5.0)
    spectrum = world.cheaptrick(working, f0, times, working_rate)
    noise = world.d4c(working, f0, times, working_rate)
    features = transform_features(f0, spectrum, noise, working_rate, **{k: v for k, v in controls.items() if k != "output_gain"})
    output = world.synthesize(*features, working_rate, frame_period=5.0)
    output = _fit_length(output, working_length)
    if rate < working_rate:
        output = resample_poly(output, rate // divisor, working_rate // divisor)
    output = _fit_length(output, original_length)
    if not np.isfinite(output).all():
        raise RuntimeError("Voice ChangerX: synthesis produced non-finite samples; reduce the transformation amounts.")
    rms = np.sqrt(np.mean(output ** 2))
    if rms > 1e-12:
        output *= np.clip(source_rms / rms, 0.1, 10.0)
    return output


class VoiceChangerX:
    CATEGORY = "WorkflowX/Audio"
    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    FUNCTION = "transform"
    OUTPUT_NODE = True  # Allows the Match Reference button to queue this node alone.
    DESCRIPTION = "Fine-control local voice changer using PyWORLD. Match Reference compares connected source and reference speech and fills editable sliders with approximate acoustic adjustments. Connect output to Preview Audio to audition."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "source_audio": ("AUDIO", {"tooltip": "The voice to transform."}),
            **{name: ("FLOAT", {"default": d, "min": lo, "max": hi, "step": step, "round": step, "tooltip": tip})
               for name, (d, lo, hi, step, tip) in CONTROLS.items()},
        }, "optional": {
            "reference_audio": ("AUDIO", {"lazy": True, "tooltip": "Optional target voice. Click Match Reference to estimate slider settings."}),
        }, "hidden": {"match_request": ("STRING", {"default": ""})}}

    def check_lazy_status(self, source_audio, reference_audio=None, match_request="", **kwargs):
        return ["reference_audio"] if match_request and reference_audio is None else []

    def transform(self, source_audio, pitch_shift=0.0, formant_shift=0.0, timbre=0.0, breathiness=0.0, pitch_variation=100.0, output_gain=0.0, reference_audio=None, match_request=""):
        import numpy as np
        import torch

        controls = dict(pitch_shift=pitch_shift, formant_shift=formant_shift, timbre=timbre,
                        breathiness=breathiness, pitch_variation=pitch_variation, output_gain=output_gain)
        if match_request:
            # Analysis-only requests never replace the waveform with the reference.
            # Return structured errors so the button can retain all existing edits.
            try:
                from .matching import match_reference
                report = match_reference(source_audio, reference_audio)
            except (ValueError, RuntimeError, ImportError, OSError) as exc:
                report = {"error": str(exc)}
            return {"ui": {"voice_reference_match": [{"request_id": str(match_request), **report}]}, "result": (source_audio,)}
        for name, value in controls.items():
            _, minimum, maximum, _, _ = CONTROLS[name]
            if isinstance(value, bool) or not isinstance(value, numbers.Real) or not math.isfinite(value) or not minimum <= value <= maximum:
                raise ValueError(f"Voice ChangerX: {name} must be a finite number between {minimum} and {maximum}.")
        waveform, rate = validate_audio(source_audio)
        if all(controls[k] == spec[0] for k, spec in CONTROLS.items()):
            return (source_audio,)

        samples = waveform.detach().cpu().double().numpy()
        output = samples.copy()
        needs_world = any(controls[k] != CONTROLS[k][0] for k in CONTROLS if k != "output_gain")
        if needs_world and samples.size and np.any(samples):
            world = _world()
            for batch in range(samples.shape[0]):
                for channel in range(samples.shape[1]):
                    output[batch, channel] = _process_channel(samples[batch, channel], int(rate), controls, world)
        output *= 10 ** (output_gain / 20)
        # One attenuation per batch preserves inter-channel balance.
        if output.size:
            peaks = np.max(np.abs(output), axis=(1, 2), keepdims=True)
            output /= np.maximum(peaks, 1.0)
        result = torch.from_numpy(output).to(dtype=waveform.dtype, device=waveform.device)
        return ({**source_audio, "waveform": result, "sample_rate": int(rate)},)


NODE_CLASS_MAPPINGS = {"WorkflowX_VoiceChangerX": VoiceChangerX}
NODE_DISPLAY_NAME_MAPPINGS = {"WorkflowX_VoiceChangerX": "Voice ChangerX"}
