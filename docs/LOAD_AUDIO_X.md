# Load AudioX

`Load AudioX` is registered as `WorkflowX_LoadAudioX` under `WorkflowX/Audio`. It loads audio files or the first audio stream of a video, provides waveform playback and trimming on the node, returns processed ComfyUI `AUDIO`, and writes an MP3 or WAV companion file from the same PCM master.

## Node controls

The node face contains the input-media picker, Upload, gear, Repair, waveform player, draggable trim handles, start and length controls, whole-file/fixed-duration mode, short-input padding mode, output format, WAV depth or MP3 bitrate, channels, and sample rate. A connected `seconds` input overrides the editable length.

The gear popup contains safe automatic recovery and diagnostics, ten Save Video X cleanup/EQ presets plus Voice compressor and Noise gate, gain, peak or EBU R128 normalization, target loudness, limiter, edge-silence trim, threshold and minimum-silence controls, fades, and permanent-save settings.

## Decode and repair behavior

Normal ComfyUI/PyAV decoding is tried first. If it fails or emits no audio, FFmpeg retries the first audio stream with generated timestamps, ignored indexes, corrupt-packet discard, and tolerant decoding. This recovers healthy-but-unusual containers, damaged MP3 frames, broken duration/index metadata, and audio streams in video without decoding video frames.

The structured AAC repair is intentionally narrower. It accepts only an audio-only, unencrypted, single-track AAC MP4/M4A with one intact media payload. The AAC configuration, declared sample count, and surviving sample sizes must support a repeating sequence that consumes the payload exactly. The reconstructed ADTS stream must then fully decode to the expected duration. All other structural corruption is rejected rather than guessed, and the source file is never changed.

## Files

With Permanent save off, each node atomically overwrites one stable converted file in the Load AudioX temp area and removes the obsolete WAV/MP3 sibling after a format change. With it on, the node writes a uniquely numbered file under the configured prefix, which defaults to `audio/LoadAudioX`.
