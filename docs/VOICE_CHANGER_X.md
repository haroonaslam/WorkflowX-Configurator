# Voice ChangerX

`WorkflowX_VoiceChangerX` · **WorkflowX/Audio**

Connect **Load AudioX → Voice ChangerX → Preview Audio** and queue the workflow. Adjust the sliders or type exact values, then queue again to audition. The supplied image/media example includes this chain.

The node has two input sockets: **source audio** (required) and **reference audio** (optional). The six parameter sockets have been removed; use the on-node sliders and value boxes.

## Match Reference

1. Connect the voice you want to change to **source audio**.
2. Connect a clear recording of the target voice to **reference audio**. The recordings do not need to say the same words, though similar speech content and recording conditions improve the comparison.
3. Click **Match Reference**. This queues an analysis of the connected source/reference dependencies and this node, without running unrelated output branches. Upstream generators may need to execute to produce the connected audio.
4. The estimates fill all six sliders as one undoable edit. Fine-tune them, then run the workflow to hear the transformed source through **Preview Audio**.

Matching compares median voiced pitch, the 10th–90th percentile pitch range, aggregate spectral-envelope shape, voiced aperiodicity, and active-speech RMS level. Pitch and pitch variation are relative ratios. Formant shift and brightness are fitted jointly. Breathiness is an aperiodicity-based estimate; output gain approximately matches active-speech level. This matches acoustic characteristics, not speaker identity, accent, or articulation.

Analysis uses up to three separated windows totaling 30 seconds at 24 kHz, choosing the strongest channel of the first batch item. One set of settings then applies to all source channels/batch items. Provide several seconds of clear single-speaker speech; silence, very short clips, or insufficient voiced speech produce an error without changing controls. Flat intonation, short voiced duration, low sample rate, and estimates outside slider limits produce status warnings. Formant estimates with weak evidence remain neutral.

Normal runs do **not** rematch; the optional reference is requested lazily for matching only. A failed, interrupted, or cleared matching job retains the current controls. Manual edits or changed upstream inputs made while matching prevent stale estimates from overwriting newer work. Shared subgraph instances that cannot be identified uniquely must be matched using an unshared node.

## Controls

| Input | Range | Default | Increment | Effect |
|---|---|---|---|---|
| `pitch_shift` | −24…+24 semitones | 0 | 0.01 | Lower/higher pitch at the same duration. |
| `formant_shift` | −12…+12 semitones | 0 | 0.01 | Larger/deeper to smaller/lighter vocal resonance, independent of pitch. |
| `timbre` | −12…+12 dB/octave | 0 | 0.1 | Warm/dark to bright/sharp; spectral tilt around 1 kHz, bounded to ±24 dB. |
| `breathiness` | −100…+100% | 0 | 1 | Reduce/increase the noise component of voiced speech. |
| `pitch_variation` | 0…200% | 100 | 1 | Flatten/preserve/exaggerate intonation around median voiced pitch. |
| `output_gain` | −24…+12 dB | 0 | 0.1 | Gain after reconstruction and level matching. |

**Reset all** restores all controls to neutral values. Numeric widget values remain the saved source of truth. Values survive workflow save/load and duplication. Slider drags and applying a reference match are grouped into single undo operations. Loading older Voice ChangerX workflows renames the original audio connection to source audio and removes obsolete parameter connections while retaining saved slider values.

For a lighter, more feminine character, try a modest positive pitch shift and positive formant shift, then adjust brightness and breathiness by ear. For a deeper, more masculine character, start with modest negative pitch and formant shifts. There is no universal setting: the source voice matters, and large shifts are more likely to sound synthetic. Fine increments allow subtle tuning but do not guarantee equally fine audible differences. This changes acoustics, not accent, articulation, or speaking style.

## Installation

The package declares `pyworld>=0.3.5`, NumPy, and SciPy. Install `requirements.txt` with the **same Python executable that runs ComfyUI**, then restart ComfyUI. For a Windows portable install, use its `python_embeded/python.exe`, not a separate system Python. If pip cannot find a compatible PyWORLD wheel, a C++ build toolchain may be needed.

PyWORLD loads when synthesis or reference analysis is needed. Missing or incompatible installations produce an actionable error on Voice ChangerX without preventing other WorkflowX nodes from loading. Neutral, gain-only, and silent transformation paths do not require PyWORLD.

## Processing and limitations

The node accepts standard `AUDIO` dictionaries containing floating-point tensors `[batch, channels, samples]` and positive integer `sample_rate` values. It returns one `AUDIO` output, retaining other source metadata. Processing uses CPU float64 internally, returning the source tensor's floating dtype and device. API callers use `source_audio`, optional `reference_audio`, and the six numeric parameter names in the controls table. A nonempty hidden `match_request` token requests analysis only, returning the source unchanged plus a `voice_reference_match` UI report containing the token, estimated settings, measurements, and warnings or an error. The button generates a fresh token per request.

PyWORLD Harvest estimates pitch, CheapTrick estimates the spectral envelope, and D4C estimates aperiodicity. Pitch and logarithmic intonation changes leave unvoiced frames unpitched. Formant changes warp the spectral envelope, brightness applies bounded spectral tilt, and breathiness changes voiced-frame aperiodicity. WORLD resynthesizes the modified features.

Each channel is analyzed independently; complex stereo phase relationships may change. Audio below 16 kHz is temporarily resampled. Tiny clips are padded for native analysis; final sample count and sample rate match the input. Silent channels stay silent. Neutral settings bypass reconstruction exactly.

Reconstruction RMS is matched to the source with correction bounded to 0.1–10×, then output gain is applied. If necessary, a common attenuation across each batch item's channels keeps peaks within full scale. This avoids hard clipping but can reduce the requested gain. Neutral bypass does not alter pre-existing peaks.

Best results come from one clear spoken voice. Background music, overlapping speakers, whispers, extreme settings, and pitch-detection errors can produce artifacts. Processing is queued, not live; long recordings require analysis memory proportional to duration. No reference-voice model or embedded player is included.

Algorithm reference: [PyWORLD documentation](https://github.com/JeremyCCHsu/Python-Wrapper-for-World-Vocoder).
