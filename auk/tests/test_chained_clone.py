import importlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

import torch


ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType("_auk_chain_tests")
package.__path__ = [str(ROOT / "nodes")]
sys.modules[package.__name__] = package
parser = importlib.import_module("_auk_chain_tests.chain_script")
runtime = types.ModuleType("_auk_chain_tests.runtime")
runtime.encode_instruction = Mock()
runtime.generate = Mock()
mm = types.ModuleType("comfy.model_management")


class Interrupted(BaseException):
    pass


mm.InterruptProcessingException = Interrupted
mm.throw_exception_if_processing_interrupted = Mock()
comfy = types.ModuleType("comfy")
comfy.model_management = mm
api = types.ModuleType("comfy_api.latest")
api.io = types.SimpleNamespace(ComfyNode=object)
with patch.dict(sys.modules, {"_auk_chain_tests.runtime": runtime, "comfy": comfy, "comfy.model_management": mm, "comfy_api": types.ModuleType("comfy_api"), "comfy_api.latest": api}):
    chain = importlib.import_module("_auk_chain_tests.chained_clone")


class ParserTests(unittest.TestCase):
    def test_speaker_inheritance_and_text(self):
        script = 'Starting words\n@VOICE2[Happy] Hello there\n\nStill here\n@voice1 [c-laugh] Back again'
        segments = parser.parse_script(script, 2, True)
        self.assertEqual([s.voice for s in segments], [1, 2, 2, 1])
        self.assertEqual([s.voice_explicit for s in segments], [False, True, False, True])
        self.assertEqual([s.seconds for s in segments], [1, 1, 1, 1])
        self.assertEqual(segments[1].instruction, 'Say the following in a happy tone using the same voice: "Hello there".')
        self.assertEqual([s.voice for s in parser.parse_script(script, 2)], [1, 1, 1, 1])
        self.assertEqual(parser.parse_script('Contact @voice2 tomorrow', 2, True)[0].text, 'Contact @voice2 tomorrow')

    def test_invalid_speaker_prefixes(self):
        for line in ['@voice3 Hello', '@voice2x Hello', '@voice1 @voice2 Hello', '[Happy] @voice2 Hello', '[@voice1] Hello', '@voice1[Happy] @voice2 Hello', '@voice2']:
            for enabled in [False, True]:
                with self.subTest(line=line, enabled=enabled), self.assertRaisesRegex(ValueError, 'Line 2'):
                    parser.parse_script('Good\n' + line, 2, enabled)

    def test_supplied_script(self):
        script = "[Horny] hello there how are you doing (3s)\n[Shy] so what is going on today ? (2.5s)\n[whispers] ok this is interesting but you know what ? this is the right answer and really well done. (7s)\n[laughs] oh really thats interesting. (2s)"
        result = parser.parse_script(script, 2)
        self.assertEqual([s.seconds for s in result], [3, 2.5, 7, 2])
        self.assertIn("in a horny tone", result[0].instruction)
        self.assertIn("while laughing", result[-1].instruction)

    def test_words_tags_and_punctuation(self):
        result = parser.parse_script('\n [sHy][C-WHISPER] Don’t re-write my words (please).\nHello, world!\n', 2)
        self.assertEqual(result[0].line, 2)
        self.assertEqual(result[0].seconds, 2.5)
        self.assertEqual(result[1].seconds, 1)
        self.assertFalse(result[0].explicit)
        self.assertIn("in a shy tone", result[0].instruction)
        self.assertEqual(result[0].conversions[0].tag, "c-whisper")
        self.assertIn("(please).", result[0].instruction)
        self.assertEqual(result[1].instruction, 'Say the following with the same voice: "Hello, world!".')

    def test_decimal_and_quotes(self):
        segment = parser.parse_script(' [Happy] She said "yes" (honestly) (.5 S)', 2)[0]
        self.assertEqual(segment.seconds, .5)
        self.assertTrue(segment.explicit)
        self.assertEqual(segment.text, 'She said "yes" (honestly)')
        self.assertIn(json.dumps(segment.text), segment.instruction)

    def test_custom_rate(self):
        self.assertEqual(parser.parse_script("one two three four", 4)[0].seconds, 1)

    def test_conversion_values_and_order(self):
        segment = parser.parse_script('[wistful][c-speed:1.237][c-volume:-6.25DB][c-pitch:+3.5][c-emotion:quietly disappointed] Hello (2s)', 2)[0]
        self.assertEqual([c.value for c in segment.conversions], [1.237, -6.25, 3.5, 'quietly disappointed'])
        self.assertIn('in a wistful tone using the same voice', segment.instruction)
        self.assertIn('Decrease the volume by 6.25 dB', segment.conversions[1].instruction)
        self.assertIn('Raise the pitch by 3.5 semitones', segment.conversions[2].instruction)

    def test_invalid_conversions_and_styles(self):
        for tag in ['[Happy][Shy]', '[c-whisper][Shy]', '[c-speed]', '[c-speed:0]', '[c-speed:-1]', '[c-speed:nan]', '[c-volume:inf]', '[c-pitch:3db]', '[c-pitch:]', '[c-speed:1.2.3]', '[c-speed:1e3]', '[c-remove: ]', '[c-other]', '[c-whisper:3]']:
            with self.subTest(tag=tag), self.assertRaisesRegex(ValueError, 'Line 2'):
                parser.parse_script('Good\n' + tag + ' Hello', 2)

    def test_concise_instruction_wording(self):
        for tag, wording in [('Happy', 'in a happy tone'), ('whispers', 'while whispering'), ('soft', 'softly'), ('laughs', 'while laughing'), ('wistful', 'in a wistful tone')]:
            with self.subTest(tag=tag):
                segment = parser.parse_script(f'[{tag}] Hello there, how are you?', 2)[0]
                self.assertEqual(segment.instruction, f'Say the following {wording} using the same voice: "Hello there, how are you?".')
                self.assertNotIn('reference audio', segment.instruction)
        expected = {
            'c-emotion:quietly disappointed': 'Change the emotion to quietly disappointed, keeping the same voice.',
            'c-speed:1.25': 'Adjust the speech speed to 1.25x.',
            'c-volume:-6db': 'Decrease the volume by 6 dB, keeping the same voice.',
            'c-pitch:+3.5': 'Raise the pitch by 3.5 semitones, keeping the same voice.',
            'c-laugh': 'Add a laugh at the beginning of the speech, keeping the same voice.',
            'c-remove:humming': 'Remove all humming from the audio, keeping the same voice.',
        }
        for tag, instruction in expected.items():
            with self.subTest(tag=tag):
                self.assertEqual(parser.parse_script(f'[{tag}] Hello', 2)[0].conversions[0].instruction, instruction)

    def test_all_catalog_entries(self):
        for item in parser.CATALOG['conversions']:
            tag = item['tag'] + (':' + str(item['default']) if 'parameter' in item else '')
            self.assertEqual(parser.parse_script(f'[{tag}] Hello', 2)[0].conversions[0].tag, item['tag'])

    def test_invalid_scripts(self):
        for text in ["[Shy hello", "[] hello", "[ ] hello", "[[Shy]] hello", "[Shy]] hello", "[Shy] (2s)", "hello (0s)", "hello (-2s)", "hello (2 seconds)", "hello (2)", "hello (nans)", "hello (3s", "hello (2xs)", "hello (bad s)"]:
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "Line 2"):
                parser.parse_script("good\n" + text, 2)
        for rate in [0, -1, float("nan"), float("inf")]:
            with self.assertRaises(ValueError):
                parser.parse_script("hello", rate)
        with self.assertRaises(ValueError):
            parser.parse_script(" \n", 2)


class ChainTests(unittest.TestCase):
    def test_two_voice_routing_and_conversion_reuse(self):
        second = {'waveform': torch.ones(1, 2, 100) * .5, 'sample_rate': 48000}
        outputs = []
        def generate(*args):
            result = {'waveform': torch.ones(1, 1, round(args[3]*24000)), 'sample_rate':24000}
            outputs.append(result)
            return result
        runtime.generate.side_effect = generate
        audio, report = chain.generate_chain('model','encoder','vae',self.reference,'@voice2 [c-laugh] Hello (1s)\nAgain (1s)\n@voice1 Hi (1s)',2,0,42,32,2,-1,reference_audio_2=second,multi_speaker=True)
        sources = [c.args[3] for c in runtime.encode_instruction.call_args_list]
        self.assertIs(sources[0], second)
        self.assertIs(sources[1], outputs[0])
        self.assertIs(sources[2], second)
        self.assertIs(sources[3], self.reference)
        self.assertEqual([c.args[4] for c in runtime.generate.call_args_list], [42,43,43,44])
        self.assertIn('voice 2 (inherited)', report)
        self.assertEqual(audio['waveform'].shape[-1],84000)

    def test_missing_second_voice_before_generation(self):
        with self.assertRaisesRegex(ValueError, 'Line 2: connect the Voice 2'):
            chain.generate_chain('m','e','v',self.reference,'Hello\n@voice2 Hi',2,0,0,32,2,-1,multi_speaker=True)
        runtime.generate.assert_not_called()
        self.run_chain('@voice2 Hello\nAgain')
        for call in runtime.encode_instruction.call_args_list:
            self.assertIs(call.args[3],self.reference)

    def setUp(self):
        runtime.encode_instruction.reset_mock(side_effect=True)
        runtime.generate.reset_mock(side_effect=True)
        mm.throw_exception_if_processing_interrupted.reset_mock(side_effect=True)
        self.reference = {"waveform": torch.ones(1, 2, 100), "sample_rate": 24000}
        runtime.encode_instruction.return_value = ["conditioning"]
        runtime.generate.side_effect = [
            {"waveform": torch.full((1, 1, 24000), 0.25), "sample_rate": 24000},
            {"waveform": torch.full((1, 1, 12000), 0.75), "sample_rate": 24000},
        ]

    def run_chain(self, script="[Happy] Hello there (1s)\n[whispers] Secret", gap=0, seed=0):
        return chain.generate_chain("model", "encoder", "vae", self.reference, script, 2, gap, seed, 32, 2, -1)

    def test_reference_order_seed_gap_report(self):
        audio, report = self.run_chain(gap=.1, seed=2**64 - 1)
        self.assertEqual(tuple(audio["waveform"].shape), (1, 1, 38400))
        self.assertEqual(audio["sample_rate"], 24000)
        self.assertTrue(torch.all(audio["waveform"][..., :24000] == .25))
        self.assertTrue(torch.all(audio["waveform"][..., 24000:26400] == 0))
        self.assertTrue(torch.all(audio["waveform"][..., 26400:] == .75))
        for call in runtime.encode_instruction.call_args_list:
            self.assertIs(call.args[3], self.reference)
        self.assertEqual([call.args[3] for call in runtime.generate.call_args_list], [1, .5])
        self.assertEqual([call.args[4] for call in runtime.generate.call_args_list], [2**64 - 1, 0])
        self.assertIn("explicit: 1.000s", report)
        self.assertIn("estimated: 0.500s", report)
        self.assertIn("1.100–1.600s", report)

    def test_direct_concat(self):
        audio, _ = self.run_chain()
        self.assertEqual(audio["waveform"].shape[-1], 36000)

    def test_validation_before_inference(self):
        with self.assertRaisesRegex(ValueError, "Line 2"):
            self.run_chain("good (1s)\n[bad")
        runtime.encode_instruction.assert_not_called()
        with self.assertRaises(ValueError):
            self.run_chain(gap=-1)
        self.reference["waveform"] = torch.ones(2, 1, 100)
        with self.assertRaisesRegex(ValueError, "one nonempty"):
            self.run_chain()

    def test_failure_names_segment(self):
        runtime.generate.side_effect = [
            {"waveform": torch.zeros(1, 1, 24000), "sample_rate": 24000},
            RuntimeError("test failure"),
        ]
        with self.assertRaisesRegex(RuntimeError, "segment 2, line 2, original voice: test failure"):
            self.run_chain()

    def test_cancel_between_segments(self):
        mm.throw_exception_if_processing_interrupted.side_effect = [None, Interrupted()]
        with self.assertRaises(Interrupted):
            self.run_chain()
        self.assertEqual(runtime.generate.call_count, 1)

    def test_cancel_during_generation(self):
        runtime.generate.side_effect = Interrupted()
        with self.assertRaises(Interrupted):
            self.run_chain()
        self.assertEqual(runtime.generate.call_count, 1)

    def test_order_reuse_timing_seed_and_neutral(self):
        outputs = []
        def generate(*args):
            audio = {'waveform': torch.full((1, 1, round(args[3] * 24000)), .1 * (len(outputs) + 1)), 'sample_rate': 24000}
            outputs.append(audio)
            return audio
        runtime.generate.side_effect = generate
        audio, report = self.run_chain('[Happy][c-speed:2][c-laugh][c-volume:0][c-pitch:+3.5] Hello (2s)\n[c-speed:1][c-pitch:0] Next (1s)', seed=2**64 - 1)
        self.assertEqual([c.args[3] for c in runtime.generate.call_args_list], [1, 1.5, 1.5, 1])
        self.assertEqual([c.args[4] for c in runtime.generate.call_args_list], [2**64-1, 1, 3, 0])
        sources = [c.args[3] for c in runtime.encode_instruction.call_args_list]
        self.assertIs(sources[0], self.reference)
        self.assertIs(sources[-1], self.reference)
        for i in range(1, 3): self.assertIs(sources[i], outputs[i-1])
        self.assertEqual(audio['waveform'].shape[-1], 60000)
        self.assertEqual(report.count('unchanged'), 3)

    def test_speed_changes_clone_duration_without_edit(self):
        self.run_chain('[c-speed:2] Hello (3s)')
        self.assertEqual([c.args[3] for c in runtime.generate.call_args_list], [1.5])

    def test_whisper_preparation(self):
        prepared = {'waveform': torch.ones(1, 1, 24000), 'sample_rate': 24000}
        with patch.object(chain, 'prepare_audio', return_value=prepared) as prepare:
            self.run_chain('[c-whisper] Hello (1s)')
            self.assertEqual(prepare.call_args.args[1], 'Convert to whisper')
            self.assertIs(runtime.encode_instruction.call_args_list[1].args[3], prepared)

    def test_change_error_and_cancellation(self):
        first = {'waveform': torch.zeros(1, 1, 24000), 'sample_rate': 24000}
        for error in [RuntimeError('failed'), Interrupted()]:
            runtime.generate.side_effect = [first, error]
            with self.assertRaisesRegex(type(error), r'segment 1, line 1, change 1 \[c-laugh\]'):
                self.run_chain('[c-laugh] Hello')

    def test_invalid_conversion_prevents_all_generation(self):
        with self.assertRaisesRegex(ValueError, 'Line 2'):
            self.run_chain('Good\n[c-speed:nan] Bad')
        runtime.generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
