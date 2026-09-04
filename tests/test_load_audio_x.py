import hashlib
import importlib.util
import os
import pathlib
import struct
import subprocess
import sys
import types

import pytest
import torch


ROOT = pathlib.Path(__file__).resolve().parents[1]
COMFY_ROOT = ROOT.parents[1]


def _runtime():
    name = "workflowx_load_audio_x_test_runtime"
    if name in sys.modules:
        return sys.modules[name]
    folder_paths = sys.modules.get("folder_paths") or types.ModuleType("folder_paths")
    folder_paths.get_input_directory = getattr(folder_paths, "get_input_directory", lambda: str(COMFY_ROOT / "input"))
    sys.modules["folder_paths"] = folder_paths
    spec = importlib.util.spec_from_file_location(name, ROOT / "load_audio_x" / "runtime.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


lax = _runtime()


def _box(kind: bytes, payload: bytes, extra_declared: int = 0) -> bytes:
    return struct.pack(">I4s", 8 + len(payload) + extra_declared, kind) + payload


def _adts_payloads(data: bytes) -> list[bytes]:
    frames = []
    offset = 0
    while offset + 7 <= len(data):
        assert data[offset] == 0xFF and data[offset + 1] & 0xF0 == 0xF0
        length = ((data[offset + 3] & 3) << 11) | (data[offset + 4] << 3) | (data[offset + 5] >> 5)
        frames.append(data[offset + 7:offset + length])
        offset += length
    return frames


def _synthetic_truncated_m4a(tmp_path: pathlib.Path, ffmpeg: str, *, payload_mismatch=False) -> pathlib.Path:
    adts = tmp_path / "seed.aac"
    subprocess.run([
        ffmpeg, "-hide_banner", "-v", "error", "-f", "lavfi", "-i",
        "sine=frequency=440:sample_rate=48000:duration=0.12", "-ac", "1", "-c:a", "aac",
        "-b:a", "64k", "-f", "adts", str(adts),
    ], check=True)
    payload = _adts_payloads(adts.read_bytes())[1]
    sample_count, known = 30, 18
    media = payload * sample_count + (b"x" if payload_mismatch else b"")
    missing = (sample_count - known) * 4
    esds = _box(b"esds", b"\0\0\0\0" + bytes((0x05, 0x02, 0x11, 0x88)))
    stsd = _box(b"stsd", b"\0" * 8 + b"mp4a" + esds)
    stsz_payload = b"\0" * 4 + struct.pack(">II", 0, sample_count) + b"".join(struct.pack(">I", len(payload)) for _ in range(known))
    stsz = _box(b"stsz", stsz_payload, missing)
    stbl = _box(b"stbl", stsd + stsz, missing)
    minf = _box(b"minf", stbl, missing)
    hdlr = _box(b"hdlr", b"\0" * 8 + b"soun" + b"\0" * 8)
    mdia = _box(b"mdia", hdlr + minf, missing)
    trak = _box(b"trak", mdia, missing)
    moov = _box(b"moov", trak, missing)
    path = tmp_path / "truncated.m4a"
    path.write_bytes(_box(b"ftyp", b"M4A \0\0\0\0M4A ") + _box(b"mdat", media) + moov)
    return path


def test_state_defaults_contract_and_path_containment(tmp_path):
    state = lax.parse_state({"format": "MP3", "channels": "Mono", "sample_rate": "24 kHz"})
    assert state["format"] == "mp3"
    assert state["mp3_bitrate"] == "192k"
    assert state["channels"] == "Mono" and state["sample_rate"] == "24 kHz"
    inputs = lax.LoadAudioX.INPUT_TYPES()
    assert inputs["hidden"]["LoadAudioXState"][0] == "STRING"
    assert inputs["hidden"]["unique_id"] == "UNIQUE_ID"
    assert lax.LoadAudioX.RETURN_TYPES == ("AUDIO", "STRING")
    folder = types.SimpleNamespace(get_input_directory=lambda: str(tmp_path))
    (tmp_path / "ok.wav").write_bytes(b"RIFF")
    assert lax.resolve_media_path("ok.wav", folder)[1] == tmp_path / "ok.wav"
    for unsafe in ("../ok.wav", "/ok.wav", r"C:\ok.wav", r"\\server\share\x.wav"):
        with pytest.raises(ValueError):
            lax.resolve_media_path(unsafe, folder)


@pytest.mark.parametrize("rate", [8000, 16000, 22050, 24000, 32000, 44100, 48000, 96000])
def test_conversion_rates_channels_and_exact_duration(rate):
    ffmpeg = lax.find_ffmpeg()
    if not ffmpeg:
        pytest.skip("FFmpeg unavailable")
    source = torch.linspace(-0.4, 0.4, 48000).repeat(2, 1)
    state = lax.parse_state({"when_unwired": "length", "length": 1.25, "channels": "Mono", "sample_rate": next(name for name, value in lax.SAMPLE_RATE_VALUES.items() if value == rate)})
    output, output_rate, status = lax.process_audio(source, 48000, state, ffmpeg=ffmpeg)
    assert output_rate == rate and output.shape == (1, round(1.25 * rate))
    assert status["channels"] == 1


def test_silence_trim_shrinks_whole_file_but_fixed_duration_is_padded():
    ffmpeg = lax.find_ffmpeg()
    if not ffmpeg:
        pytest.skip("FFmpeg unavailable")
    source = torch.cat((torch.zeros(1, 1000), torch.ones(1, 2000) * .2, torch.zeros(1, 1000)), dim=-1)
    whole = lax.parse_state({"trim_silence": True, "silence_threshold_db": -30, "minimum_silence": 0, "when_unwired": "whole"})
    fixed = lax.parse_state({**whole, "when_unwired": "length", "length": .4})
    assert lax.process_audio(source, 10000, whole, ffmpeg=ffmpeg)[0].shape[-1] == 2000
    assert lax.process_audio(source, 10000, fixed, ffmpeg=ffmpeg)[0].shape[-1] == 4000


def test_stereo_source_conversion_looping_and_all_filters():
    ffmpeg = lax.find_ffmpeg()
    if not ffmpeg:
        pytest.skip("FFmpeg unavailable")
    source = torch.sin(torch.arange(4000).float().mul(2 * 3.14159 * 220 / 16000)).unsqueeze(0) * .2
    state = lax.parse_state({
        "when_unwired": "length", "length": 1, "when_short": "loop", "channels": "Stereo",
        "sample_rate": "24 kHz", "filters": list(lax.BASE_FILTERS), "gain_db": 1,
        "normalize": "EBU R128", "limiter": True, "fade_in": .01, "fade_out": .01,
    })
    output, rate, status = lax.process_audio(source, 16000, state, ffmpeg=ffmpeg)
    assert output.shape == (2, 24000) and rate == 24000
    assert status["warnings"] == [] and float(output.abs().max()) <= .95001


def test_wav_and_mp3_encoding_from_same_master(tmp_path):
    ffmpeg = lax.find_ffmpeg()
    if not ffmpeg:
        pytest.skip("FFmpeg unavailable")
    waveform = torch.sin(torch.arange(12000).float().mul(2 * 3.14159 * 220 / 24000)).unsqueeze(0) * .2
    for format_name in ("wav", "mp3"):
        state = lax.parse_state({"format": format_name, "wav_depth": "24-bit", "mp3_bitrate": "192k"})
        target = tmp_path / f"encoded.{format_name}"
        lax.encode_audio(waveform, 24000, state, target, ffmpeg)
        decoded, rate, _warning = lax._tolerant_decode(target, {"sample_rate": 24000, "channels": 1}, ffmpeg)
        assert target.is_file() and target.stat().st_size > 100
        assert rate == 24000 and decoded.shape[0] == 1 and decoded.shape[-1] > 10000
        assert not (tmp_path / f"encoded.{format_name}.part").exists()


@pytest.mark.parametrize("depth,codec", [("16-bit", "pcm_s16le"), ("24-bit", "pcm_s24le"), ("32-bit float", "pcm_f32le")])
def test_every_wav_depth(depth, codec, tmp_path):
    ffmpeg = lax.find_ffmpeg()
    if not ffmpeg:
        pytest.skip("FFmpeg unavailable")
    target = tmp_path / "depth.wav"
    lax.encode_audio(torch.zeros(1, 2400), 24000, lax.parse_state({"format": "wav", "wav_depth": depth}), target, ffmpeg)
    assert lax.probe_media(target, ffmpeg)["codec"] == codec


@pytest.mark.parametrize("bitrate", lax.MP3_BITRATES)
def test_every_mp3_bitrate(bitrate, tmp_path):
    ffmpeg = lax.find_ffmpeg()
    if not ffmpeg:
        pytest.skip("FFmpeg unavailable")
    target = tmp_path / f"rate-{bitrate}.mp3"
    waveform = torch.sin(torch.arange(48000).float().mul(2 * 3.14159 * 220 / 48000)).unsqueeze(0) * .2
    lax.encode_audio(waveform, 48000, lax.parse_state({"format": "mp3", "mp3_bitrate": bitrate}), target, ffmpeg)
    import av
    with av.open(str(target)) as container:
        actual = int(container.streams.audio[0].codec_context.bit_rate or 0)
    assert abs(actual - int(bitrate[:-1]) * 1000) <= 16000


def test_temporary_destination_is_stable_and_cleans_only_its_sibling(tmp_path):
    folders = types.SimpleNamespace(get_temp_directory=lambda: str(tmp_path))
    wav = lax._destination(lax.parse_state({"format": "wav"}), "node/7", folders)
    mp3 = lax._destination(lax.parse_state({"format": "mp3"}), "node/7", folders)
    assert wav.name == "node_node_7.wav" and mp3.name == "node_node_7.mp3"
    assert wav.parent == mp3.parent
    unrelated = wav.parent / "unrelated.wav"; unrelated.write_bytes(b"keep")
    partial = wav.parent / "old.part"; partial.write_bytes(b"remove")
    assert lax.clean_stale_cache(folders, max_age_seconds=10**9) == 1
    assert unrelated.exists() and not partial.exists()


def test_generated_truncated_stsz_is_recovered_and_unsafe_mismatch_rejected(tmp_path):
    ffmpeg = lax.find_ffmpeg()
    if not ffmpeg:
        pytest.skip("FFmpeg unavailable")
    source = _synthetic_truncated_m4a(tmp_path, ffmpeg)
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    info = lax.inspect_truncated_aac(source)
    assert info["sample_count"] == 30 and info["known_sample_count"] == 18
    assert info["object_type"] == 2 and info["rate_index"] == 3 and info["channels"] == 1
    recovered = tmp_path / "recovered.aac"
    lax.recover_truncated_aac(source, recovered)
    audio, rate, _warning = lax._tolerant_decode(recovered, {"sample_rate": 48000, "channels": 1}, ffmpeg)
    assert rate == 48000 and abs(audio.shape[-1] / rate - 30 * 1024 / rate) < .05
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
    unsafe_dir = tmp_path / "unsafe"; unsafe_dir.mkdir()
    unsafe = _synthetic_truncated_m4a(unsafe_dir, ffmpeg, payload_mismatch=True)
    with pytest.raises(ValueError, match="payload"):
        lax.inspect_truncated_aac(unsafe)


def test_real_acceptance_fixtures_when_present():
    ffmpeg = lax.find_ffmpeg()
    if not ffmpeg:
        pytest.skip("FFmpeg unavailable")
    expected = {
        "Voice 260903_174549.m4a": ("c697a87fcc0da7655ec2113558c72402d75db3eadb7f9e339c841b1b373153c7", 26.84),
        "ManVoice42Sec.mp3": ("56d51737a0f934bb4f1acc9845b438ccb1c6eaa2724663d5f5c7dd36825f5466", 42.0),
    }
    found = 0
    for name, (digest, duration) in expected.items():
        path = COMFY_ROOT / "input" / name
        if not path.is_file():
            continue
        found += 1
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        assert before == digest
        waveform, rate, status = lax.decode_source(path, unique_id="acceptance", ffmpeg=ffmpeg)
        assert abs(waveform.shape[-1] / rate - duration) < .1
        assert status["repair"] != "none"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    if not found:
        pytest.skip("Personal acceptance fixtures are intentionally not in the repository")
