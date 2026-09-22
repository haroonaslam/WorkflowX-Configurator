import importlib
import types
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import torch
from test_chained_clone import parser, chain, runtime, mm, api


class InlineParserTests(unittest.TestCase):
    def test_edit_voice_preservation_whole_line_and_inline(self):
        for tag in ['c-emotion:overwhelmed', 'c-delivery:breathy', 'c-laugh', 'c-breath', 'c-remove:coughs', 'c-volume:-6db', 'c-pitch:3.5', 'c-repair:muffled sound']:
            with self.subTest(tag=tag):
                whole=parser.parse_script(f'[{tag}] Hello there',2)[0].conversions[0]
                inline=parser.parse_script(f'<{tag}>Hello there</{tag.split(":")[0]}>',2,inline_edits=True)[0].pieces[0].change
                self.assertEqual(whole,inline)
                self.assertIn('keeping the same voice',whole.instruction)
        self.assertEqual(parser.parse_conversion('c-emotion:overwhelmed',1).instruction,
            'Change the emotion to overwhelmed, keeping the same voice.')

    def test_explicit_edit_presets(self):
        for item in parser.CATALOG['styles']:
            tag = item['edit_tag']
            whole = parser.parse_script(f'[Happy][{tag}] Hello there', 2)[0]
            local = parser.parse_script(f'[Happy] Before <{tag}>Hello there</{tag.split(":")[0]}> after', 2, inline_edits=True)[0]
            self.assertEqual(local.pieces[1].change, whole.conversions[0])
            self.assertTrue(local.pieces[1].change.tag.startswith('c-'))
        emotion = parser.parse_script('<c-emotion:excited>Hello</c-emotion>', 2, inline_edits=True)[0]
        self.assertEqual(emotion.pieces[0].change.instruction, 'Change the emotion to excited, keeping the same voice.')
        delivery = parser.parse_script('<c-delivery:speaking while laughing>Hello</c-delivery>', 2, inline_edits=True)[0]
        self.assertEqual(delivery.pieces[0].change.duration, 'same')
        self.assertEqual(parser.parse_conversion('c-laugh', 1).duration, 'sound')

    def test_all_catalog_effects(self):
        for item in parser.CATALOG['styles'] + parser.CATALOG['conversions']:
            tag = item['tag'] + (':' + str(item['default']) if item.get('parameter') else '')
            s = parser.parse_script(f'<{tag}>Hello there</{item["tag"]}>', 2, inline_edits=True)[0]
            self.assertEqual(len(s.pieces), 1)
            self.assertNotIn('<', s.instruction)

    def test_allocation_and_alias(self):
        s = parser.parse_script('[Happy] Hello <breath>my dear friend</breath> goodbye (10s)', 2, inline_edits=True)[0]
        self.assertEqual([p.seconds for p in s.pieces], [2,6,2])
        self.assertEqual(s.pieces[1].change.tag, 'c-breath')
        self.assertEqual(s.text, 'Hello my dear friend goodbye')

    def test_invalid(self):
        for text in ['<sad>x</happy>', '<sad><breath>x</breath></sad>', '<unknown>x</unknown>', '<sad></sad>', '<sad>x', '</sad>x', '<c-speed:0>x</c-speed>']:
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, 'Line 2'):
                parser.parse_script('Hi\n'+text,2,inline_edits=True)

    def test_disabled_and_ordinary_angles(self):
        s = parser.parse_script('[Happy] a <unknown>x</unknown> <c-speed:bad>word</c-speed> < 3',2)[0]
        self.assertEqual(s.text,'a x word < 3')
        self.assertFalse(s.pieces)
        self.assertEqual(s.seconds,2.0)

    def test_punctuation_case_and_colons(self):
        s = parser.parse_script('<SAD>She said: hello</sad>, <c-speed:1.25>goodbye</C-SPEED>!',2,inline_edits=True)[0]
        self.assertEqual(len(s.pieces),2)
        self.assertEqual(s.pieces[0].text,'She said: hello, ')


class InlineGenerationTests(unittest.TestCase):
    from test_chained_clone import ChainTests as _Base
    setUp = _Base.setUp
    run_chain = _Base.run_chain
    def test_inline_order_and_sources(self):
        outputs=[]
        def generate(*args):
            out={'waveform':torch.full((1,1,round(args[3]*24000)), (len(outputs)+1)*.01),'sample_rate':24000};outputs.append(out);return out
        runtime.generate.side_effect=generate
        audio,report=chain.generate_chain('m','e','v',self.reference,'[Happy][c-laugh] Hello <sad>my friend</sad> goodbye (4s)',2,0,42,32,2,-1,inline_edits=True)
        calls=runtime.encode_instruction.call_args_list
        self.assertEqual(len(calls),5)
        self.assertIs(calls[0].args[3],self.reference)
        self.assertIs(calls[1].args[3],self.reference)
        self.assertIs(calls[2].args[3],outputs[1])
        self.assertIs(calls[3].args[3],self.reference)
        self.assertEqual([x.args[4] for x in runtime.generate.call_args_list],[42,43,44,45,46])
        self.assertEqual(calls[2].args[2],'Say this in a sad tone, keeping the same voice.')
        self.assertEqual(audio['waveform'].shape[-1],108000)
        self.assertIn('Piece 2 boundary',report)
        self.assertEqual(calls[4].args[3]['waveform'].shape[-1],96000)

    def test_speed_multiplier_validation_and_neutral(self):
        for multiplier in [0, -1, float('nan'), float('inf')]:
            with self.assertRaisesRegex(ValueError, 'Speed timing multiplier'):
                chain.generate_chain('m','e','v',self.reference,'Hello',2,0,0,32,2,-1,speed_timing_multiplier=multiplier)
        runtime.generate.assert_not_called()
        chain.generate_chain('m','e','v',self.reference,'[c-speed:1] Hello there',2,0,0,32,2,-1,speed_timing_multiplier=1.5)
        self.assertEqual(runtime.generate.call_args.args[3],1)

    def test_speed_timing_scopes_multiplier_and_sounds(self):
        runtime.generate.side_effect = lambda *args: {'waveform': torch.zeros(1,1,round(args[3]*24000)), 'sample_rate':24000}
        audio, report = chain.generate_chain('m','e','v',self.reference,
            '[Happy][c-speed:2][c-breath] One two <c-speed:0.5>three four</c-speed>',
            2,0,42,32,2,-1,inline_edits=True,speed_timing_multiplier=1.2)
        self.assertEqual([round(c.args[3],4) for c in runtime.generate.call_args_list], [.6,1.2,2.3])
        self.assertEqual([c.args[4] for c in runtime.generate.call_args_list], [42,43,46])
        calls=runtime.encode_instruction.call_args_list
        self.assertIs(calls[0].args[3],self.reference)
        self.assertIs(calls[1].args[3],self.reference)
        self.assertFalse(any('Adjust the speech speed' in c.args[2] for c in calls))
        self.assertEqual(audio['waveform'].shape[-1],55200)
        self.assertIn('cloning duration control',report)

    def test_disabled_exact_regression(self):
        s='[Happy] Hello there (1s)'
        first=self.run_chain(s)
        calls=runtime.encode_instruction.call_args_list[:]
        self.setUp()
        second=self.run_chain('[Happy] Hello <unknown>there</unknown> (1s)')
        self.assertTrue(torch.equal(first[0]['waveform'],second[0]['waveform']))
        self.assertEqual(first[1],second[1])
        self.assertEqual(calls[0].args[2],runtime.encode_instruction.call_args_list[0].args[2])


class Output:
    def __init__(self,*args,ui=None,**kwargs):self.args=args;self.ui=ui
class Blocker:
    def __init__(self,*args):pass

with patch.dict('sys.modules', {'comfy':types.SimpleNamespace(model_management=mm),'comfy.model_management':mm,'comfy_api.latest':types.SimpleNamespace(io=types.SimpleNamespace(NodeOutput=Output)), 'comfy_execution.graph_utils':types.SimpleNamespace(ExecutionBlocker=Blocker),'server':types.SimpleNamespace(PromptServer=None)}):
    review=importlib.import_module('_auk_chain_tests.chain_review')

class EditorTests(unittest.TestCase):
    def setUp(self):
        self.storage=tempfile.TemporaryDirectory()
        self.storage_patch=patch.object(review,'STORAGE',Path(self.storage.name))
        self.storage_patch.start()
        self.token='a'*32
        self.hidden=types.SimpleNamespace(unique_id='5',extra_pnginfo={'workflowx_auk_review':{'5':{'token':self.token}}})
        self.inputs=dict(model='m',encoder='e',vae='v',reference_audio={'waveform':torch.ones(1,1,100),'sample_rate':24000},reference_audio_2=None,script='Hello (1s)\nGoodbye (1s)',words_per_second=2,gap_seconds=.1,seed=42,steps=32,guidance=2,sway=-1,sound_extra_seconds=.5,multi_speaker=False,inline_edits=False)
        mm.throw_exception_if_processing_interrupted.reset_mock(side_effect=True)
        runtime.encode_instruction.reset_mock(side_effect=True)
        runtime.generate.reset_mock(side_effect=True)
        runtime.generate.side_effect=lambda *args: {'waveform':torch.ones(1,1,round(args[3]*24000))*.1,'sample_rate':24000}
        self.serial=0

    def tearDown(self):
        for session in review.SESSIONS.values():session.close()
        review.SESSIONS.clear()
        self.storage_patch.stop()
        self.storage.cleanup()

    @property
    def session(self):return review.SESSIONS[self.token]

    def request(self,action,index=0,**extra):
        self.serial+=1
        data=dict(token=self.token,action=action,nonce=str(self.serial))
        if action!='run':
            data.update(batch=self.session.batch,revision=self.session.revision,segment=self.session.segments[index]['id'])
        data.update(extra)
        self.hidden.extra_pnginfo['workflowx_auk_review']['5']=data

    def step(self,action='run',index=0,**extra):
        self.request(action,index,**extra)
        with patch.dict('sys.modules', {'_auk_chain_tests.chained_clone':chain}):
            return review.execute_review(self.inputs,self.hidden)

    def finalize(self,gap=.1):
        self.request('finalize')
        return review.finalize_editor(gap,self.hidden)

    def test_continuous_output_progress_and_retention(self):
        progress=[]
        original=review.Session.publish
        def publish(session,*args,**kwargs):
            original(session,*args,**kwargs)
            progress.append(sum(bool(x.get('audio')) for x in session.state['segments']))
        with patch.object(review.Session,'publish',publish):out=self.step()
        self.assertEqual(out.args[0]['waveform'].shape[-1],50400)
        self.assertEqual(runtime.generate.call_count,2)
        self.assertIn(1,progress)
        self.assertIn(2,progress)
        self.assertEqual(len(list(self.session.root.glob('*.pt'))),2)
        self.assertEqual(len(list(self.session.root.glob('*.wav'))),2)
        self.assertEqual(len(list(self.session.root.iterdir())),5)
        self.assertEqual([s['seed'] for s in self.session.segments],[42,43])

    def test_selected_regeneration_settings_and_atomic_replacement(self):
        self.step();old=[s.copy() for s in self.session.segments]
        self.inputs.update(script='Changed words (2s)\nUnrelated change (3s)',steps=7)
        result=self.step('regenerate')
        self.assertIsInstance(result.args[0],Blocker)
        self.assertEqual(runtime.generate.call_count,3)
        self.assertEqual(self.session.segments[1],old[1])
        current=self.session.segments[0]
        self.assertEqual(current['id'],old[0]['id'])
        self.assertEqual(current['settings']['steps'],7)
        self.assertEqual(current['raw'],'Changed words (2s)')
        self.assertNotEqual(current['seed'],old[0]['seed'])
        self.assertFalse((self.session.root/old[0]['file']).exists())
        self.assertEqual(len(list(self.session.root.iterdir())),5)

    def test_finalize_no_generation_current_gap_only(self):
        self.step();calls=runtime.generate.call_count
        self.inputs.update(script='Invalid [ text',steps=1,reference_audio=None)
        result=self.finalize(.4)
        self.assertEqual(runtime.generate.call_count,calls)
        self.assertEqual(result.args[0]['waveform'].shape[-1],57600)
        self.assertIn('output 1.400-2.400s',result.args[1])
        self.assertIn('Hello (1s)',result.args[1])
        self.assertEqual(len(list(self.session.root.iterdir())),5)

    def test_failed_regeneration_keeps_previous_files(self):
        self.step();old=self.session.segments[0].copy()
        runtime.generate.side_effect=RuntimeError('failed')
        with self.assertRaisesRegex(RuntimeError,'segment 1, line 1'):self.step('regenerate')
        self.assertEqual(self.session.segments[0]['file'],old['file'])
        self.assertTrue((self.session.root/old['file']).exists())
        self.assertEqual(len(list(self.session.root.iterdir())),5)
        self.finalize()

    def test_full_run_resets_cache(self):
        self.step();root=self.session.root;ids=[s['id'] for s in self.session.segments]
        self.step()
        self.assertFalse(root.exists())
        self.assertNotEqual(ids,[s['id'] for s in self.session.segments])
        self.assertEqual(runtime.generate.call_count,4)

    def test_local_add_after_three_stable_ids(self):
        self.inputs['script']='One (1s)\nTwo (1s)\nThree (1s)\nFour (1s)'
        self.step();old=[s.copy() for s in self.session.segments]
        self.inputs['script']='One (1s)\nTwo (1s)\nThree (1s)\nAdded (1s)\nFour (1s)'
        self.step('add',2,text='Added (1s)',connected=False)
        self.assertEqual([s['id'] for s in self.session.segments[:3]],[s['id'] for s in old[:3]])
        self.assertEqual(self.session.segments[4]['file'],old[3]['file'])
        self.assertEqual([s['source'] for s in self.session.segments],list(range(5)))
        self.assertFalse(self.session.segments[3]['editor_only'])
        self.assertEqual(runtime.generate.call_count,5)
        self.assertEqual(len(list(self.session.root.iterdir())),11)

    def test_connected_add_source_mapping_and_voice_inheritance(self):
        ref2={'waveform':torch.zeros(1,1,100),'sample_rate':24000}
        self.inputs.update(reference_audio_2=ref2,multi_speaker=True)
        self.step();old=self.session.segments[1].copy()
        self.step('add',0,text='@voice2 New (1s)',connected=True)
        self.assertEqual([s['source'] for s in self.session.segments],[0,None,1])
        self.assertTrue(self.session.segments[1]['editor_only'])
        self.assertEqual(self.session.segments[2],old)
        self.assertIs(runtime.encode_instruction.call_args.args[3],ref2)
        self.inputs['script']='Hello (1s)\nChanged goodbye (1s)'
        self.step('regenerate',2)
        self.assertEqual(self.session.segments[2]['text'],'Changed goodbye')
        self.assertEqual(self.session.segments[2]['voice'],2)
        self.assertEqual(self.session.segments[0]['voice'],1)

    def test_failed_added_slot_retry_and_finalize_block(self):
        self.step();runtime.generate.side_effect=RuntimeError('failure')
        with self.assertRaisesRegex(RuntimeError,'segment 2'):self.step('add',0,text='Extra (1s)',connected=True)
        self.assertEqual(len(self.session.segments),3)
        self.assertNotIn('file',self.session.segments[1])
        with self.assertRaisesRegex(ValueError,'every segment'):self.finalize()
        runtime.generate.side_effect=lambda *args:{'waveform':torch.zeros(1,1,24000),'sample_rate':24000}
        self.step('regenerate',1)
        self.assertEqual(self.finalize().args[0]['waveform'].shape[-1],76800)

    def test_structural_changes_require_run_but_allow_finalize(self):
        self.step();self.inputs['script']+='\nNew line'
        with self.assertRaisesRegex(ValueError,'line count'):self.step('regenerate')
        with self.assertRaisesRegex(ValueError,'line count'):self.step('add',text='New',connected=True)
        self.finalize()
        self.assertEqual(runtime.generate.call_count,2)

    def test_complete_validation_before_inference(self):
        self.inputs.update(script='Hi\n@voice2 Bye',multi_speaker=True)
        with self.assertRaisesRegex(ValueError,'Line 2'):self.step()
        runtime.generate.assert_not_called()
        self.inputs.update(script='Hi\n[c-speed:1e-320] Bye',multi_speaker=False)
        with self.assertRaises(ValueError):self.step()
        runtime.generate.assert_not_called()

    def test_inline_regenerate_does_not_reuse_stages(self):
        self.inputs.update(script='<c-emotion:sad>Hello</c-emotion> (1s)',inline_edits=True)
        self.step();self.step('regenerate')
        self.assertEqual(runtime.generate.call_count,4)
        self.assertEqual(len(list(self.session.root.iterdir())),3)

    def test_expiry_isolation_revision_and_duplicate_actions(self):
        self.step();root=self.session.root;revision=self.session.revision
        with self.assertRaisesRegex(ValueError,'editor changed'):self.step('regenerate',revision=revision-1)
        self.request('finalize');review.finalize_editor(.1,self.hidden)
        duplicate=review.finalize_editor(.1,self.hidden)
        self.assertIsInstance(duplicate.args[0],Blocker)
        self.session.updated=0;review.expire()
        self.assertFalse(root.exists())
        self.assertNotIn(self.token,review.SESSIONS)

    def test_cancel_late_result_cannot_restore_files(self):
        self.step();session=self.session;root=session.root
        def cancelled(*args):
            session.cancelled=True
            return {'waveform':torch.zeros(1,1,24000),'sample_rate':24000}
        runtime.generate.side_effect=cancelled
        with self.assertRaises(mm.InterruptProcessingException):self.step('regenerate')
        self.assertFalse(root.exists())
        self.assertNotIn(self.token,review.SESSIONS)

    def test_initial_failure_retains_completed_previews_only(self):
        runtime.generate.side_effect=[{'waveform':torch.zeros(1,1,24000),'sample_rate':24000},RuntimeError('failure')]
        with self.assertRaisesRegex(RuntimeError,'segment 2'):self.step()
        self.assertEqual(sum(bool(s.get('file')) for s in self.session.segments),1)
        with self.assertRaises(ValueError):self.finalize()

    def test_disk_failure_cleans_replacement(self):
        self.step();old=self.session.segments[0]['file']
        with patch.object(review.sf,'write',side_effect=OSError('disk')):
            with self.assertRaises(OSError):self.step('regenerate')
        self.assertEqual(self.session.segments[0]['file'],old)
        self.assertEqual(len(list(self.session.root.iterdir())),5)

    def test_other_invalid_text_does_not_block_selected_take(self):
        self.step()
        self.inputs['script']='[c-unknown] Other invalid text\nNew goodbye (1s)'
        self.step('regenerate',1)
        self.assertEqual(self.session.segments[1]['text'],'New goodbye')
        self.assertEqual(self.session.segments[0]['raw'],'Hello (1s)')

    def test_busy_session_and_owner_isolation(self):
        self.step();session=self.session
        with session.lock:
            with self.assertRaisesRegex(ValueError,'Wait'):self.step('regenerate')
        session.owner='another-node'
        with self.assertRaisesRegex(ValueError,'another node'):self.step('regenerate')
        session.owner='5'
        self.token='b'*32;self.step()
        self.assertEqual(len(review.SESSIONS),2)
        self.assertIsNot(self.session,session)

    def test_stale_batch_cannot_replace_new_run(self):
        self.step();self.request('regenerate');old=self.hidden.extra_pnginfo['workflowx_auk_review']['5'].copy()
        self.step();ids=[s['id'] for s in self.session.segments]
        self.hidden.extra_pnginfo['workflowx_auk_review']['5']=old
        with patch.dict('sys.modules',{'_auk_chain_tests.chained_clone':chain}):
            with self.assertRaisesRegex(ValueError,'editor changed'):review.execute_review(self.inputs,self.hidden)
        self.assertEqual([s['id'] for s in self.session.segments],ids)
        self.assertEqual(runtime.generate.call_count,4)

    def test_expired_owned_orphan_cleanup_only(self):
        import os
        orphan=review.STORAGE/'batch-orphan';orphan.mkdir();(orphan/'editor-owned').write_text('1')
        other=review.STORAGE/'batch-unowned';other.mkdir();(other/'user-file').write_text('keep')
        os.utime(orphan,(0,0));os.utime(other,(0,0))
        review.expire()
        self.assertFalse(orphan.exists())
        self.assertTrue(other.exists())

    def test_restart_cleanup_preserves_other_live_process(self):
        import json
        orphan=review.STORAGE/'batch-old-process';orphan.mkdir();(orphan/'editor-owned').write_text(json.dumps({'pid':12345}))
        with patch.object(review,'process_running',return_value=True):review.expire()
        self.assertTrue(orphan.exists())
        with patch.object(review,'process_running',return_value=False):review.expire()
        self.assertFalse(orphan.exists())
        self.assertTrue(review.process_running(review.os.getpid()))
