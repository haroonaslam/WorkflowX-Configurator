import logging
import math
import json

import torch
import comfy.model_management as mm
from comfy_api.latest import io

from . import runtime
from .chain_script import CATALOG, parse_script
from .prompt_enhance import prepare_audio


logger = logging.getLogger(__name__)


def validate_timing(segments, gap_seconds, sound_extra_seconds, speed_timing_multiplier):
    if not math.isfinite(gap_seconds) or gap_seconds < 0:
        raise ValueError("Gap seconds must be finite and nonnegative.")
    if not math.isfinite(sound_extra_seconds) or sound_extra_seconds < 0:
        raise ValueError("Extra sound time must be finite and nonnegative.")
    if not math.isfinite(speed_timing_multiplier) or speed_timing_multiplier <= 0:
        raise ValueError("Speed timing multiplier must be finite and greater than zero.")
    def clone_seconds(segment, piece=None):
        seconds = piece.seconds if piece else segment.seconds
        speeds = [c.value for c in segment.conversions if c.duration == "speed" and not c.unchanged]
        if piece and piece.change and piece.change.duration == "speed" and not piece.change.unchanged:
            speeds.append(piece.change.value)
        if speeds:
            seconds *= speed_timing_multiplier
            for factor in speeds:
                seconds /= factor
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError(f"Line {segment.line}: speed settings produce an invalid duration.")
        return seconds
    # Validate every adjusted duration before the first generation.
    for segment in segments:
        for piece in segment.pieces or (None,):
            clone_seconds(segment, piece)
    return clone_seconds


def generate_chain(model, encoder, vae, reference_audio, script, words_per_second, gap_seconds, seed, steps, guidance, sway, sound_extra_seconds=0.5, reference_audio_2=None, multi_speaker=False, inline_edits=False, speed_timing_multiplier=1.0, _segments=None, _index=0, _cache=None):
    segments = parse_script(script, words_per_second, multi_speaker, inline_edits) if _segments is None else _segments
    clone_seconds = validate_timing(segments, gap_seconds, sound_extra_seconds, speed_timing_multiplier)
    references = {1: reference_audio, 2: reference_audio_2}
    for voice in sorted({segment.voice for segment in segments}):
        line = next(segment.line for segment in segments if segment.voice == voice)
        reference = references[voice]
        if reference is None:
            raise ValueError(f"Line {line}: connect the Voice {voice} recording before generating.")
        waveform = reference["waveform"]
        if waveform.ndim != 3 or waveform.shape[0] != 1 or waveform.shape[1] < 1 or waveform.shape[2] < 1:
            raise ValueError(f"Line {line}: Voice {voice} requires one nonempty reference audio sample.")
        if reference["sample_rate"] <= 0:
            raise ValueError(f"Line {line}: Voice {voice} sample rate must be positive.")
    clips = []
    report = []
    cursor = 0
    sample_rate = 24000
    gap_samples = round(gap_seconds * sample_rate)
    def run_stage(source, instruction, seconds, stage_seed, context, preprocess=None):
        conditioning = None
        try:
            mm.throw_exception_if_processing_interrupted()
            if not math.isfinite(seconds) or seconds <= 0:
                raise ValueError("Requested duration must be finite and greater than zero.")
            cache_key = _cache.key(source, instruction, seconds, stage_seed, steps, guidance, sway, preprocess) if _cache else None
            cached = _cache.get(cache_key) if _cache else None
            if cached is not None:
                return cached
            if preprocess:
                source = prepare_audio(source, preprocess)
            conditioning = runtime.encode_instruction(encoder, model, instruction, source)
            generated = runtime.generate(model, vae, conditioning, seconds, stage_seed, steps, guidance, sway)
            clip = generated["waveform"].detach().cpu()
            if generated["sample_rate"] != sample_rate or clip.ndim != 3 or clip.shape[:2] != (1, 1) or clip.shape[-1] == 0:
                raise ValueError("Expected nonempty mono 24 kHz audio.")
            generated["waveform"] = clip
            if _cache:
                _cache.put(cache_key, generated)
            return generated
        except mm.InterruptProcessingException as error:
            raise mm.InterruptProcessingException(f"{context}: cancelled.") from error
        except Exception as error:
            raise RuntimeError(f"{context}: {error}") from error
        finally:
            del conditioning

    for index, segment in enumerate(segments):
        item_seed = (seed + index + _index) % (2**64)
        logger.info("AuK Chained Clone: segment %s/%s (line %s)", index + 1, len(segments), segment.line)
        context = f"Chained Clone segment {index + 1 + _index}, line {segment.line}"
        if multi_speaker:
            context += f", voice {segment.voice}"
        stage_offset = 0
        if not segment.pieces:
            seconds = clone_seconds(segment)
            generated = run_stage(references[segment.voice], segment.instruction, seconds, item_seed, f"{context}, original voice")
            duration_kind = "explicit" if segment.explicit else "estimated"
            stages = [f"Original voice | {duration_kind}: {segment.seconds:.3f}s | seed: {item_seed} | requested: {seconds:.3f}s | actual: {generated['waveform'].shape[-1] / sample_rate:.3f}s\nInstruction: {segment.instruction}"]
        else:
            parts = []
            stages = []
            piece_cursor = 0
            for piece_index, piece in enumerate(segment.pieces, 1):
                prefix = segment.instruction[:-len(json.dumps(segment.text, ensure_ascii=False)) - 1]
                instruction = prefix + json.dumps(piece.text, ensure_ascii=False) + "."
                piece_seed = (item_seed + stage_offset) % (2**64)
                stage_offset += 1
                piece_context = f"{context}, piece {piece_index}"
                seconds = clone_seconds(segment, piece)
                generated = run_stage(references[segment.voice], instruction, seconds, piece_seed, piece_context + ", original voice")
                stages.append(f"Piece {piece_index} original | seed: {piece_seed} | requested: {seconds:.3f}s | actual: {generated['waveform'].shape[-1] / sample_rate:.3f}s\nInstruction: {instruction}")
                if piece.change:
                    change = piece.change
                    seconds = generated["waveform"].shape[-1] / sample_rate
                    if change.duration == "sound":
                        seconds += sound_extra_seconds
                    edit_seed = (item_seed + stage_offset) % (2**64)
                    stage_offset += 1
                    if not change.unchanged and change.duration != "speed":
                        generated = run_stage(generated, change.instruction, seconds, edit_seed, piece_context + f", inline [{change.tag}]", change.preprocess)
                    stages.append(f"Piece {piece_index} inline | {change.tag} | value: {change.value} | seed: {edit_seed} | requested: {seconds:.3f}s | actual: {generated['waveform'].shape[-1] / sample_rate:.3f}s" + (" | unchanged" if change.unchanged else "") + (f" | cloning duration control; multiplier: {speed_timing_multiplier}" if change.duration == "speed" else f"\nInstruction: {change.instruction}"))
                actual = generated["waveform"].shape[-1] / sample_rate
                stages.append(f"Piece {piece_index} boundary before line conversions: {piece_cursor:.3f}–{piece_cursor + actual:.3f}s")
                piece_cursor += actual
                parts.append(generated["waveform"])
            generated = {"waveform": torch.cat(parts, dim=-1), "sample_rate": sample_rate}
            # The first line conversion follows the last piece stage.
            stage_offset -= 1
        for change_index, change in enumerate(segment.conversions, 1):
            stage_context = f"{context}, change {change_index} [{change.tag}]"
            try:
                mm.throw_exception_if_processing_interrupted()
            except mm.InterruptProcessingException as error:
                raise mm.InterruptProcessingException(f"{stage_context}: cancelled.") from error
            current_seconds = generated["waveform"].shape[-1] / sample_rate
            seconds = current_seconds
            if change.duration == "sound":
                seconds += sound_extra_seconds
            change_seed = (item_seed + stage_offset + change_index) % (2**64)
            if not change.unchanged and change.duration != "speed":
                generated = run_stage(generated, change.instruction, seconds, change_seed, stage_context, change.preprocess)
            actual = generated["waveform"].shape[-1] / sample_rate
            stages.append(f"Change {change_index} | {change.tag} | value: {change.value} | seed: {change_seed} | requested: {seconds:.3f}s | actual: {actual:.3f}s" + (" | unchanged" if change.unchanged else "") + (f" | cloning duration control; multiplier: {speed_timing_multiplier}" if change.duration == "speed" else f"\nInstruction: {change.instruction}"))
        clip = generated["waveform"]
        if index and gap_samples:
            clips.append(clip.new_zeros((1, 1, gap_samples)))
            cursor += gap_samples
        start = cursor / sample_rate
        clips.append(clip)
        cursor += clip.shape[-1]
        report.append(
            f"Segment {index + 1 + _index} | line {segment.line} | voice {segment.voice}" + (" (inherited)" if multi_speaker and not segment.voice_explicit else "") + "\n"
            f"Output: {start:.3f}–{cursor / sample_rate:.3f}s ({clip.shape[-1] / sample_rate:.3f}s)\n"
            + "\n".join(stages)
        )
    try:
        mm.throw_exception_if_processing_interrupted()
    except mm.InterruptProcessingException as error:
        raise mm.InterruptProcessingException(f"{context}, final audio: cancelled.") from error
    audio = {"waveform": torch.cat(clips, dim=-1), "sample_rate": sample_rate}
    return audio, f"{len(segments)} segments | total: {cursor / sample_rate:.3f}s | gap: {gap_samples / sample_rate:.3f}s\n\n" + "\n\n".join(report)


class WorkflowXAuKChainedClone(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        help_text = CATALOG["help"]
        return io.Schema(
            node_id="WorkflowXAuKChainedClone",
            display_name="AuK Chained Clone X",
            category="WorkflowX/Audio/AuK",
            description="Clone each script line independently from the same reference voice, then join the audio in order. Tags request delivery styles; model adherence varies.",
            inputs=[
                io.Custom("WORKFLOWX_AUK_MODEL").Input("model"),
                io.Custom("WORKFLOWX_AUK_ENCODER").Input("encoder"),
                io.Vae.Input("vae"),
                io.Audio.Input("reference_audio", display_name="Voice 1", tooltip="The first speaker's recording. Used for every line when Multi-speaker is off."),
                io.String.Input("script", multiline=True, default="[Happy] Hello there, how are you? (3s)\n[Shy][c-whisper] This is our little secret.", tooltip=help_text["script"]),
                io.Float.Input("words_per_second", default=2.0, min=0.01, max=100, step=0.1, tooltip=help_text["rate"]),
                io.Float.Input("gap_seconds", default=0.0, min=0, max=3600, step=0.05, tooltip=help_text["gap"]),
                io.Int.Input("seed", default=0, min=0, max=0xffffffffffffffff, control_after_generate=True, tooltip=help_text["seed"]),
                io.Int.Input("steps", default=32, min=1, max=1000, tooltip=help_text["steps"]),
                io.Float.Input("guidance", default=2, min=0, max=100, step=0.1, tooltip=help_text["guidance"]),
                io.Float.Input("sway", default=-1, min=-1, max=0, step=0.05, tooltip=help_text["sway"]),
                io.Float.Input("sound_extra_seconds", default=0.5, min=0, max=3600, step=0.05, optional=True, tooltip=help_text["extra"]),
                io.Audio.Input("reference_audio_2", display_name="Voice 2", optional=True, tooltip="The second speaker's recording. Needed when a line uses @voice2 with Multi-speaker on."),
                io.Boolean.Input("multi_speaker", display_name="Multi-speaker", default=False, optional=True, tooltip="Use @voice1 or @voice2 before a line's tags. Unmarked lines continue the previous speaker, starting with Voice 1. Turn off to use Voice 1 for all lines."),
                io.Boolean.Input("inline_edits", display_name="Inline edits", default=False, optional=True, tooltip=help_text["inline"]),
                io.Boolean.Input("review_each_line", display_name="Segment editor", default=False, optional=True, tooltip=help_text["review"]),
                io.Float.Input("speed_timing_multiplier", display_name="Speed timing multiplier", default=1.0, min=0.01, max=100, step=0.05, optional=True, tooltip="Extra room for speech controlled by speed tags. 1 uses the calculated duration; higher values allow more time. Lines without speed changes are unaffected."),
            ],
            hidden=[io.Hidden.unique_id, io.Hidden.extra_pnginfo],
            outputs=[io.Audio.Output(display_name="audio"), io.String.Output(display_name="segment_report")],
        )

    @classmethod
    def fingerprint_inputs(cls, review_each_line=False, **kwargs):
        return float("nan") if review_each_line else "automatic"

    @classmethod
    def execute(cls, model, encoder, vae, reference_audio, script, words_per_second, gap_seconds, seed, steps, guidance, sway, sound_extra_seconds=0.5, reference_audio_2=None, multi_speaker=False, inline_edits=False, review_each_line=False, speed_timing_multiplier=1.0):
        inputs = dict(model=model, encoder=encoder, vae=vae, reference_audio=reference_audio, script=script, words_per_second=words_per_second, gap_seconds=gap_seconds, seed=seed, steps=steps, guidance=guidance, sway=sway, sound_extra_seconds=sound_extra_seconds, reference_audio_2=reference_audio_2, multi_speaker=multi_speaker, inline_edits=inline_edits, speed_timing_multiplier=speed_timing_multiplier)
        if review_each_line:
            from .chain_review import execute_review
            return execute_review(inputs, cls.hidden)
        audio, report = generate_chain(**inputs)
        return io.NodeOutput(audio, report)

class WorkflowXAuKChainedCloneReviewStep(WorkflowXAuKChainedClone):
    _OUTPUT_NODE = None
    _DEPRECATED = None
    """Queue-only review target; never added to the user's workflow canvas."""
    @classmethod
    def define_schema(cls):
        schema = super().define_schema()
        schema.node_id = 'WorkflowXAuKChainedCloneReviewStep'
        schema.display_name = 'AuK review step X (internal)'
        schema.is_output_node = True
        schema.is_deprecated = True
        return schema


class WorkflowXAuKSegmentFinalize(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="WorkflowXAuKSegmentFinalize", display_name="AuK editor assembly X (internal)",
            category="WorkflowX/Audio/AuK", is_output_node=True, is_deprecated=True,
            inputs=[io.Float.Input("gap_seconds", default=0.0, min=0)],
            hidden=[io.Hidden.unique_id, io.Hidden.extra_pnginfo],
            outputs=[io.Audio.Output(display_name="audio"), io.String.Output(display_name="segment_report")])

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        return float('nan')

    @classmethod
    def execute(cls, gap_seconds=0):
        from .chain_review import finalize_editor
        return finalize_editor(gap_seconds, cls.hidden)
