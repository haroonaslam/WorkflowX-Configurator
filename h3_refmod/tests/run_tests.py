"""Saved-profile acceptance tests. Run with ComfyUI's Python --comfy-root PATH."""
import argparse,importlib.util,json,sys,tempfile,unittest,hashlib
from pathlib import Path
from unittest.mock import patch
parser=argparse.ArgumentParser();parser.add_argument('--comfy-root',required=True);args=parser.parse_args();sys.path.insert(0,args.comfy_root);sys.argv=['tests','--cpu']
import comfy.options
comfy.options.enable_args_parsing()
p=Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('h3rc',p/'__init__.py',submodule_search_locations=[str(p)]);pkg=importlib.util.module_from_spec(spec);sys.modules['h3rc']=pkg;spec.loader.exec_module(pkg)
import torch
from h3rc import profiles as pr,creation as cr,characters as ch,generation as gen,representations as rp
from h3rc.vendor.py.refmod_core import H3RefMod
class VAE:
    def __init__(self):
        from comfy.ldm.minimax.vae import MiniMaxH3VideoVAE
        self.first_stage_model=MiniMaxH3VideoVAE.__new__(MiniMaxH3VideoVAE);self.inputs=[]
    def encode(self,x):
        self.inputs.append(x.clone());return torch.arange(24*(1 if len(x)==1 else 3)*(x.shape[1]//16)*(x.shape[2]//16),dtype=torch.float32).reshape(1,24,1 if len(x)==1 else 3,x.shape[1]//16,x.shape[2]//16)/100
    def decode(self,z):return torch.full((1 if z.shape[2]==1 else 5,z.shape[3]*16,z.shape[4]*16,3),0.5003)
class Clip:
    def tokenize(self,prompt,**kw):self.prompt=prompt;self.items=kw['minimax_ref_items'];return None
    def encode_from_tokens_scheduled(self,t):return [[torch.zeros(1,1,1),{'minimax_token_tags':[0]}]]
def config():
    d=pr.defaults()
    for g in pr.GROUPS:d[g][0].update(size=64,id='small',name='Small');d[g].append(dict(d[g][0],id='original',name='Original',size=0))
    return d
class Profiles(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.a=patch.object(ch,'roots',return_value=[self.root]);self.b=patch.object(cr,'roots',return_value=[self.root]);self.a.start();self.b.start();self.vae=VAE()
    def tearDown(self):gen._CACHE.clear();self.b.stop();self.a.stop();self.temp.cleanup()
    def create(self,**kw):
        sources=[dict(source='Portrait.png',kind='image',data=torch.full((1,128,96,3),0.5003)),dict(source='Landscape.png',kind='image',data=torch.full((1,64,128,3),0.4)),dict(source='Clip.mp4',kind='video',fps=32,data=torch.rand(23,64,96,3))]
        return cr.create_selected(sources,vae=self.vae,display_name='Profiles',prompt_alias='alice',profiles=config(),**kw)['result'][0]
    def select(self,c,mode=rp.MODES[2],**options):return ch.configure_character(c,visual_references=mode,reference_selection=json.dumps({'character_id':c['character_id'],'modes':{mode:options}}))

    def test_saved_profiles_with_endpoints_both_modes(self):
        from comfy.text_encoders.minimax import MiniMaxH3Tokenizer
        class Text:
            def tokenize_with_weights(self,text,**kw):return [[(text,1.0)]]
        class HybridClip(Clip):
            def __init__(self):
                self.calls=0;self.tokenizer=MiniMaxH3Tokenizer.__new__(MiniMaxH3Tokenizer);self.tokenizer.qwen3vl_32b=Text()
            def encode_from_tokens_scheduled(self,t):self.calls+=1;return super().encode_from_tokens_scheduled(t)
        c=self.create();selected=self.select(c,rp.MODES[1]);hashes={p:Path(p).read_bytes() for p in c['visuals']+[c['path']]}
        refs={'reference_0':dict(kind='image',tag='opening',role='First frame',data=torch.rand(1,64,96,3))}
        for mode in rp.CONDITIONING:
            clip=HybridClip();out=gen.generate(clip,'summary: Quiet.\ndetailed_description: [Shot 1] @alice smiles in @opening.',64,64,22,characters={'character_0':selected},named_references=refs,vae=self.vae,saved_character_conditioning=mode)
            metadata=out[0][0][1];self.assertEqual(clip.calls,1);self.assertEqual(len(metadata['minimax_keyframes']),1)
            for block,entry in zip(metadata['minimax_refs'],selected['selected_references']):self.assertTrue(torch.equal(block['latent'],gen.load_mod(entry['path']).latent[:,:,entry['indices']]))
            from comfy.ldm.minimax.model import PackedLayout
            layout=PackedLayout(1,7,4,4,37,keyframes=metadata['minimax_keyframes'],refs=metadata['minimax_refs'])
            self.assertEqual([x[2] for x in layout.segments][:4],['text','cond','ref_img','ref_img'])
        self.assertTrue(all(Path(p).read_bytes()==b for p,b in hashes.items()))

    def test_profiles_and_atomic_publication(self):
        c=self.create();self.assertEqual(c['version'],4);self.assertEqual(len(c['visuals']),1);self.assertEqual(len(c['profile_layout']['profiles']['picture']),2);self.assertEqual(len(c['profile_layout']['variants']),12);self.assertFalse(list((self.root/'refcharacters').glob('.creating_*')))
        c2=self.create();self.assertNotEqual(c['path'],c2['path'])
    def test_float_precision_and_dimensions(self):
        p=config()['picture'][0];x=torch.full((1,128,96,3),0.5003);y=pr.prepare(x,p);self.assertEqual(y.shape,(1,96,64,3));self.assertLess(float((y[y>0]-.5003).abs().max()),1e-6)
        for method in pr.DOWNSIZE:self.assertTrue(torch.isfinite(pr.prepare(x,dict(p,downsize=method))).all())
    def test_small_source_choices_and_crop(self):
        x=torch.ones(1,32,64,3);p=dict(config()['picture'][0],size=64)
        self.assertEqual(pr.prepare(x,p).shape,(1,32,64,3))
        padded=pr.prepare(x,dict(p,smaller='Pad to target'));self.assertEqual(padded.shape,(1,64,128,3));self.assertEqual(int((padded[:,:,:,0]>0).sum()),32*64)
        for method in ['Enlarge with Lanczos','Enlarge with Nearest exact']:self.assertTrue(bool((pr.prepare(x,dict(p,smaller=method))==1).all()))
        wide=torch.rand(1,64,128,3);self.assertTrue(torch.equal(pr.prepare(wide,dict(p,framing='Crop to fill'),(64,64)),wide[:,:,32:96]))
    def test_missing_model_and_invalid_config_before_encode(self):
        d=config();d['picture'][0].update(smaller=pr.SMALL[-1],model='missing_model')
        with self.assertRaises(ValueError):pr.parse(d)
        self.assertEqual(self.vae.inputs,[])
    def test_source_frame_cap_zero_and_default(self):
        c=self.create(sample_frames=0);self.assertTrue(any(len(x)==23 for x in self.vae.inputs));self.vae.inputs.clear();self.create();self.assertTrue(any(len(x)==16 for x in self.vae.inputs))
    def test_individual_override_and_default(self):
        c=self.create();s=self.select(c,defaults={'image':'small','video':'original'},overrides={'source-2':'original'})
        self.assertEqual([e['profile_id'] for e in s['selected_references']],['small','original','original'])
        s=self.select(c,defaults={'image':'original','video':'small'},overrides={'source-2':'small'});self.assertEqual([e['profile_id'] for e in s['selected_references']],['original','small','small'])
    def test_unavailable_default_does_not_substitute(self):
        c=self.create()
        with self.assertRaisesRegex(ValueError,'default image profile'):self.select(c,defaults={'image':'missing'})
        with self.assertRaisesRegex(ValueError,'individually'):self.select(c,defaults={'image':None})
    def test_different_dimensions_share_profile(self):
        c=self.create();s=self.select(c,defaults={'image':'original','video':'original'});self.assertNotEqual(s['selected_references'][0]['shape'][3:],s['selected_references'][1]['shape'][3:])
    def test_combined_exact_values_no_vae(self):
        c=self.create();s=self.select(c,rp.MODES[3],profile='small',selected=['source-3','source-1'],order=['source-3','source-1'])
        from h3rc.runtime_combined import assemble
        expected=torch.cat([gen.load_mod(e['path']).latent[:,:,e['indices']] for e in s['selected_references']],2)
        self.assertTrue(torch.equal(assemble(s['runtime_combined']),expected));clip=Clip();out=gen.generate(clip,'@alice smiles',64,64,5,characters={'character_0':s},saved_character_conditioning=rp.CONDITIONING[1]);self.assertEqual(len(out[0][0][1]['minimax_refs']),1);self.assertTrue(torch.equal(out[0][0][1]['minimax_refs'][0]['latent'],expected));self.assertEqual(clip.items,[])
    def test_saved_combined_subset_and_reload(self):
        c=self.create();s=self.select(c,rp.MODES[0],profile='original');r=ch.load_character(c['path']);again=self.select(r,rp.MODES[0],profile='original');self.assertEqual(s['runtime_combined']['shape'],again['runtime_combined']['shape'])
        self.assertEqual(len(s['selected_references']),3)
    def test_both_conditioning_modes_and_file_hashes(self):
        c=self.create();before={p:Path(p).read_bytes() for p in c['visuals']+[c['path']]};s=self.select(c,rp.MODES[1]);original=[gen.load_mod(e['path']).latent[:,:,e['indices']] for e in s['selected_references']]
        for mode in rp.CONDITIONING:
            clip=Clip();out=gen.generate(clip,'@alice smiles',64,64,5,characters={'character_0':s},vae=self.vae,saved_character_conditioning=mode)
            for block,z in zip(out[0][0][1]['minimax_refs'],original):self.assertTrue(torch.equal(block['latent'],z))
        self.assertTrue(all(Path(p).read_bytes()==b for p,b in before.items()))
    def test_picture_protection_and_video_only_reduction(self):
        entries=[dict(kind='image',latent=torch.ones(1,24,1,4,4),shape=[1,24,1,4,4]),dict(kind='video',latent=torch.ones(1,24,5,4,4),shape=[1,24,5,4,4])]
        reduced=pr.fit(entries,8);self.assertEqual(reduced[0]['indices'],[0]);self.assertEqual(len(reduced[1]['indices']),1)
        with self.assertRaisesRegex(ValueError,'No pictures were dropped'):pr.fit(entries,3)
    def test_budget_failure_before_text(self):
        c=self.create();s=self.select(c,rp.MODES[1])
        class Fail(Clip):
            def tokenize(self,*a,**kw):raise AssertionError('text encoding began')
        with self.assertRaises(ValueError):gen.generate(Fail(),'@alice',64,64,5,characters={'character_0':s},budget_mode='Manual',manual_reference_budget=1)
    def test_external_and_reject_old_custom(self):
        p=H3RefMod(name='External',kind='image',latent=torch.ones(1,24,1,4,4),latent_t=1,latent_h=4,latent_w=4).save(str(self.root/'external'));c=ch.load_character(p);self.assertTrue(c['external']);s=self.select(c,rp.MODES[1]);self.assertEqual(s['selected_references'][0]['profile_name'],'External')
        before=Path(p).read_bytes();c=ch.save_details(c);self.assertEqual(Path(p).read_bytes(),before)
        old=self.root/'old.character.json';old.write_text(json.dumps({'version':3}));
        with self.assertRaisesRegex(ValueError,'recreated'):ch.load_character(old)
    def test_registered_external_preserves_metadata_and_files(self):
        visual=Path(H3RefMod(name='External',kind='video',latent=torch.ones(1,24,3,4,4),latent_t=3,latent_h=4,latent_w=4).save(str(self.root/'registered')))
        manifest=visual.with_suffix('.character.json')
        for version in (1,2,3):
            manifest.write_text(json.dumps(dict(version=version,character_id='external-id',alias='alice',display_name='Alice',visuals=[visual.name],voices=[],source_ranges=[],descriptor='a woman')))
            before={p:p.read_bytes() for p in (manifest,visual)}
            for path in (manifest,visual):
                c=ch.load_character(path);self.assertTrue(c['external']);self.assertEqual(c['alias'],'alice');self.assertEqual(c['descriptor'],'a woman')
                self.assertEqual(self.select(c,rp.MODES[2])['selected_references'][0]['profile_name'],'External')
            self.assertTrue(all(p.read_bytes()==data for p,data in before.items()))
        data=json.loads(manifest.read_text());data['visual_layout']={'version':1};manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'recreated'):ch.load_character(manifest)
    def test_image_reference_batch_and_file_selection(self):
        from h3rc.media import ImageReference
        import nodes
        image=torch.rand(3,32,32,3);node=ImageReference()
        for choice,indices in [('all',[0,1,2]),('3,1',[2,0])]:
            out=node.select('Connected input','','room','scene',batch_selection=choice,image=image)
            self.assertTrue(torch.equal(out['result'][1],image[indices]))
        for choice in ('0','4','1,1','wrong'):
            with self.assertRaises(ValueError):node.select('Connected input','','room','scene',batch_selection=choice,image=image)
        with patch('h3rc.media.file_path'),patch.object(nodes.LoadImage,'load_image',return_value=(image,)):
            out=node.select('Load file','room.png','room','scene',batch_selection='wrong')
            self.assertTrue(torch.equal(out['result'][1],image))
    def test_associated_images_do_not_create_subjects(self):
        from h3rc.reference_plan import build_plan
        from h3rc.compiler import compile_prompt
        c=self.select(self.create(),rp.MODES[1])
        for role in ('character appearance','association'):
            ref=dict(kind='image',tag='detail',role=role,target='alice',descriptor='a watch',batch_count=1)
            active,rows=build_plan('',characters={'character_0':c},named_references={'reference_0':ref})
            self.assertEqual(len(active),1)
            out,_=compile_prompt('@alice with @detail',active,rows)
            self.assertNotIn('<Subject 2>',out)
            self.assertIn('a watch from <Picture 1>',out)
            if role=='association':self.assertIn('<Picture 1> is a watch belonging to <Subject 1>.',out)
        ref['target']=''
        with self.assertRaisesRegex(ValueError,'associated character'):build_plan('',named_references={'reference_0':ref})
        ref['role']='character appearance'
        active,_=build_plan('',named_references={'reference_0':ref});self.assertEqual(active[0]['alias'],'detail')
    def test_custom_audio_descriptor_and_tag(self):
        from h3rc.media import AudioReference
        from h3rc.reference_plan import build_plan
        from h3rc.compiler import compile_prompt
        audio=dict(waveform=torch.zeros(1,1,1600),sample_rate=16000)
        ref=AudioReference().select('Connected input','','bell','custom',audio=audio,descriptor='a distant bell')['result'][0]
        active,rows=build_plan('',named_references={'reference_0':ref})
        out,_=compile_prompt('[Shot 1] The sound of @bell continues.',active,rows)
        self.assertIn('<Audio 1> is a distant bell.',out)
        self.assertIn('The sound of <Audio 1> continues.',out)
        self.assertEqual(active,[])
        ref['descriptor']=''
        with self.assertRaisesRegex(ValueError,'Descriptor'):build_plan('',named_references={'reference_0':ref})
    def test_atomic_failure_does_not_publish(self):
        d=config();d['combined'][0]['budget']=1
        with self.assertRaises(ValueError):cr.create_selected([dict(source='photo',kind='image',data=torch.ones(1,128,96,3))],vae=self.vae,profiles=d)
        self.assertFalse((self.root/'refcharacters').exists())
    def test_no_obsolete_widget_fields(self):
        self.assertNotIn('runtime_mode',gen.CharacterPicker.INPUT_TYPES()['required']);self.assertNotIn('mode',cr.common_inputs());self.assertIn('profiles',cr.common_inputs())
    def test_native_regular_conditioning(self):
        x=torch.ones(1,64,64,3);clip=Clip();out=gen.generate(clip,'A room from <Picture 1>',64,64,5,vae=self.vae,ref_images={'ref_image_0':x});self.assertEqual(len(out[0][0][1]['minimax_refs']),1);self.assertEqual(len(clip.items),1)
    def test_model_upscale_native_adapter_and_finish(self):
        from comfy_extras.nodes_upscale_model import UpscaleModelLoader,ImageUpscaleWithModel
        x=torch.full((1,32,64,3),0.5003);model=object();settings=dict(config()['picture'][0],size=96,smaller=pr.SMALL[-1],model='test')
        with patch.object(UpscaleModelLoader,'execute',return_value=(model,)) as load,patch.object(ImageUpscaleWithModel,'execute',return_value=(torch.full((1,128,256,3),0.5003),)) as upscale:
            cache={};a=pr.prepare(x,settings,models=cache);pr.prepare(x,settings,models=cache)
            self.assertEqual(load.call_count,1);self.assertEqual(upscale.call_count,2);self.assertIs(upscale.call_args.args[0],model);self.assertEqual(a.shape,(1,96,192,3));self.assertLess(float((a-.5003).abs().max()),1e-6)
    def test_original_size_alignment_is_padding(self):
        x=torch.full((1,35,67,3),0.5003);p=dict(config()['picture'][0],size=0,smaller='Enlarge with Lanczos');y=pr.prepare(x,p)
        self.assertEqual(y.shape,(1,64,96,3));self.assertEqual(int((y[:,:,:,0]>0).sum()),35*67)
    def test_no_common_default_and_explicit_profiles(self):
        c=self.create();c['profile_layout']['variants']=[e for e in c['profile_layout']['variants'] if not (e['group']=='picture' and ((e['source_id']=='source-1' and e['profile_id']=='small') or (e['source_id']=='source-2' and e['profile_id']=='original')))]
        with self.assertRaisesRegex(ValueError,'individually'):self.select(c,rp.MODES[1])
        s=self.select(c,rp.MODES[1],defaults={'image':None},overrides={'source-1':'original','source-2':'small'});self.assertEqual(len(s['selected_references']),2)
        s=self.select(c,rp.MODES[1],selected=['source-1']);self.assertEqual(s['selected_references'][0]['profile_id'],'original')
    def test_omitted_combined_source_requires_explicit_resolution(self):
        c=self.create();e=next(e for e in c['profile_layout']['variants'] if e['group']=='combined' and e['profile_id']=='small' and e['kind']=='video');e['indices']=[]
        s=self.select(c,rp.MODES[0],profile='small');self.assertEqual(len(s['selected_references']),2);self.assertTrue(any('omitted when' in r['status'] for r in s['selection_report']))
        with self.assertRaisesRegex(ValueError,'no saved samples'):self.select(c,rp.MODES[3],profile='small')
    def test_native_mixed_media_conditioning_parity(self):
        class AudioVAE:
            audio_sample_rate=32000
            def encode(self,x):return torch.ones(1,32,2,4)
        image=torch.ones(1,64,64,3);video=torch.ones(5,64,64,3);audio={'waveform':torch.ones(1,2,3200),'sample_rate':32000}
        args=dict(ref_images={'ref_image_2':image},ref_videos={'ref_video_1':video},ref_video_audios={'ref_video_audio_1':audio},ref_audios={'ref_audio_0':audio})
        a,b=Clip(),Clip();prompt='<Picture 1> is the setting. <Audio 2> is background ambience.'
        ours=gen.generate(a,prompt,64,64,5,vae=self.vae,audio_vae=AudioVAE(),**args);native=gen.native.MiniMaxH3ReferenceToVideo.execute(b,prompt,64,64,5,vae=self.vae,audio_vae=AudioVAE(),**args)
        self.assertEqual([i['type'] for i in a.items],['image','audio','video','audio'])
        for actual,expected in zip(ours[0][0][1]['minimax_refs'],native[0][0][1]['minimax_refs']):
            self.assertEqual(actual.keys(),expected.keys())
            for k in actual:
                if isinstance(actual[k],torch.Tensor):self.assertTrue(torch.equal(actual[k],expected[k]))
                else:self.assertEqual(actual[k],expected[k])
    def test_saved_audio_values_and_files_unchanged(self):
        c=self.create();z=torch.arange(1*32*2*12,dtype=torch.float32).reshape(1,32,2,12)/100
        voice=H3RefMod(name='Voice',kind='audio',latent=z,sample_rate=32000).save(str(self.root/'voice'))
        c['voices']=[voice];before=Path(voice).read_bytes();s=self.select(c,rp.MODES[1]);out=gen.generate(Clip(),'@alice: <d>Hello</d>',64,64,5,characters={'character_0':s},saved_character_conditioning=rp.CONDITIONING[1])
        block=next(r for r in out[0][0][1]['minimax_refs'] if r['kind']=='audio');self.assertTrue(torch.equal(block['audio_latent'],gen.load_mod(voice).latent));self.assertEqual(Path(voice).read_bytes(),before)
from h3rc import compiler as cp
def char(alias='alice',voice=None):return dict(alias=alias,character_id=alias,display_name=alias.title(),description='',visuals=[],voice=voice)

class CompilerTests(unittest.TestCase):
    def test_activation_order_plain_names(self):
        a,b=char(),char('bob');self.assertEqual(cp.resolve('Bob @BOB then @alice and @bob',[a,b]),[a,b]);self.assertEqual(cp.resolve('Alice',[a]),[a])
    def test_unknown_and_collision(self):
        with self.assertRaises(ValueError):cp.resolve('@unknown',[char()])
        with self.assertRaises(ValueError):cp.resolve('@alice',[char(),{**char(),'character_id':'other'}])
    def test_dialogue_and_escape(self):
        text='[Shot 1] @alice smiles. @alice: <d>[English] Email @unknown and @@literal.</d> @@outside'
        active=cp.resolve(text,[char()]);out,_=cp.compile_prompt(text,active,[])
        self.assertIn('<Subject 1> (S1):',out);self.assertIn('Email @unknown and @@literal.',out);self.assertIn('@outside',out)
    def test_independent_numbering(self):
        refs=[dict(kind='image',owner='alice'),dict(kind='image',owner='bob'),dict(kind='audio',owner='bob')]
        out,report=cp.compile_prompt('@alice greets @bob. @bob: <d>Hi</d>',[char(),char('bob')],refs)
        self.assertEqual([r['label'] for r in refs],['<Picture 1>','<Picture 2>','<Audio 1>']);self.assertIn('<Subject 2> (S1)',out)
    def test_no_false_reference_definitions_in_dialogue(self):
        cp.compile_prompt('@alice: <d>subject_definitions: literal</d>',[char()],[])
        with self.assertRaises(ValueError):cp.compile_prompt('subject_definitions: x',[],[])
    def test_missing_association_and_bad_manual_speaker(self):
        cp.compile_prompt('<Audio 1> is ambience. @alice',[char()],[dict(kind='audio',owner='')])
        with self.assertRaises(ValueError):cp.compile_prompt('@alice: (S9) <d>Hi</d>',[char()],[])
    def test_voice_tags_without_colons(self):
        refs=[dict(kind='audio',owner='alice',role='character voice',category='saved'),dict(kind='audio',target='bob',tag='recording',role='character voice',category='named')]
        out,report=cp.compile_prompt('@recording sighs. @alice-voice breathes. @bob-voice speaks <d>@unknown stays literal</d>. @alice says hello.',[char(),char('bob')],refs)
        self.assertIn('<Subject 2> (S1) sighs.',out)
        self.assertIn('<Subject 1> (S2) breathes.',out)
        self.assertIn('<Subject 2> (S1) speaks',out)
        self.assertIn('<d>@unknown stays literal</d>',out)
        self.assertIn('<Subject 1> says hello.',out)
        self.assertIn('@alice-voice -> <Subject 1> (S2)',report)
        with self.assertRaises(ValueError):cp.compile_prompt('@alice-voice sighs',[char()],[])
        with self.assertRaisesRegex(ValueError,'reserved'):cp.compile_prompt('',[char()],refs+[dict(kind='image',tag='alice-voice')])
    def test_explicit_reference_indicators(self):
        for kind,markers in [('image',['fully_preserved','partially_preserved','attribute_transfer','weak_reference']),('video',['fully_preserved','partially_preserved','attribute_transfer','weak_reference']),('audio',['reference','weak_reference','partially_copy','fully_copy'])]:
            for marker in markers:
                ref=dict(kind=kind,category='named',tag='source',role='custom',descriptor='the reference content',reference_type=marker,retain='the texture',change='the background',instructions='Retain: the texture Change: the background')
                out,_=cp.compile_prompt('@source',[],[ref])
                self.assertIn(marker+' - ',out)
                self.assertIn('is the reference content.',out)
                self.assertIn('Retain: the texture',out)
    def test_invalid_reference_label(self):
        with self.assertRaises(ValueError):cp.compile_prompt('<Picture 2> is shown',[],[dict(kind='image')])
    def test_catalog_metadata_does_not_leak_into_prompt(self):
        c=char('ben');c.update(display_name='minimaxh3_benaffleck_v1_refmod',description='RefMod dataset benaffleck',retain='identity',change='wear a red jacket.')
        out,report=cp.compile_prompt('@ben smiles.',[c],[dict(kind='video',owner='ben')])
        self.assertIn('<Subject 1> is a character; identity from <Video 1>.',out)
        self.assertIn('Retain: identity Change: wear a red jacket.',out)
        self.assertNotIn('refmod',out.lower());self.assertNotIn('dataset',out.lower())
        self.assertIn('@ben -> <Subject 1>',report)
    def test_identity_descriptor_and_generation_changes(self):
        c=char();c.update(descriptor='a South Asian woman',change='Wear a red jacket.')
        out,_=cp.compile_prompt('@alice smiles',[c],[dict(kind='video',owner='alice')])
        self.assertIn('<Subject 1> is a South Asian woman; identity from <Video 1>.',out)
        self.assertIn('Wear a red jacket.',out)
    def test_generated_section_order(self):
        p='summary:\nGreeting.\ndetailed_description:\n[Shot 1] @alice: <d>Hello.</d>'
        out,_=cp.compile_prompt(p,[char()],[])
        self.assertLess(out.index('summary:'),out.index('retention_analysis:'))
        self.assertLess(out.index('retention_analysis:'),out.index('detailed_description:'))


class Endpoints(unittest.TestCase):
    def ref(self,role='First frame',tag='start',data=None):
        return dict(kind='image',role=role,tag=tag,target='disconnected',data=torch.rand(1,64,64,3) if data is None else data)
    def plan(self,refs):
        from h3rc.reference_plan import build_plan
        from h3rc.endpoints import split
        active,rows=build_plan('',named_references={f'reference_{i}':r for i,r in enumerate(refs)})
        ends,ordinary=split(rows);return active,ordinary,ends
    def test_endpoint_roles_and_validation(self):
        from h3rc.media import IMAGE_ROLES
        self.assertTrue({'First frame','Last frame'}<=set(IMAGE_ROLES))
        a,r,e=self.plan([self.ref()]);self.assertEqual(a,[]);self.assertEqual(r,[]);self.assertEqual(e[0]['target'],'')
        with self.assertRaisesRegex(ValueError,'@start and @other'):self.plan([self.ref(),self.ref(tag='other')])
        with self.assertRaisesRegex(ValueError,'exactly one'):self.plan([self.ref(data=torch.rand(2,64,64,3))])
    def test_pure_prompts_and_preserved_text(self):
        from h3rc.endpoints import prompt_for
        for refs in ([self.ref()],[self.ref('Last frame','end')],[self.ref(),self.ref('Last frame','end')]):
            a,r,e=self.plan(refs);text='summary:\nQuiet room.\ndetailed_description:\n[Shot 1] @@literal. <d>@untouched: [Shot 99]</d>\n[Shot 3] Still.\noverall_soundscape:\nWind.\nnon_diegetic_music:\nNone.'
            out,report=prompt_for(text,a,r,e,64,64,124)
            self.assertIn('integrated_multimodal_description:\nQuiet room.',out);self.assertIn('<d>@untouched: [Shot 99]</d>',out);self.assertIn('@literal',out);self.assertNotIn('subject_definitions:',out)
            if any(x['role']=='Last frame' for x in refs):self.assertIn('Shot 3',out.split('integrated_multimodal_description:')[0]);self.assertEqual(e[-1]['frame_index'],123)
        with self.assertRaisesRegex(ValueError,'not both'):prompt_for('detailed_description: a\nintegrated_multimodal_description: b',a,r,e,64,64,5)
    def test_reference_only_exact_parity(self):
        from h3rc.endpoints import prompt_for
        text='summary:\nQuiet.\ndetailed_description:\n[Shot 1] @@example.'
        self.assertEqual(prompt_for(text,[],[],[],64,64,5),cp.compile_prompt(text,[],[]))
    def test_generation_native_endpoint_parity(self):
        from comfy_extras import nodes_minimax_h3 as native
        class EndpointClip(Clip):
            def tokenize(self,prompt,**kw):self.prompt=prompt;self.items=kw;return None
        for roles in [('First frame',),('Last frame',),('First frame','Last frame')]:
            refs=[self.ref(role,role.split()[0].lower()) for role in roles];vae=VAE();clip=EndpointClip()
            out=gen.generate(clip,'summary: Quiet.\ndetailed_description: [Shot 1] Still.',64,64,22,vae=vae,named_references={f'reference_{i}':r for i,r in enumerate(refs)})
            kwargs={'first_frame' if r['role']=='First frame' else 'last_frame':r['data'] for r in refs}
            original=native.MiniMaxH3ImageToVideo.execute(EndpointClip(),VAE(),out[2],64,64,22,**kwargs)
            ours=out[0][0][1]['minimax_keyframes'];expected=original[0][0][1]['minimax_keyframes']
            self.assertEqual([x['resolved_frame_index'] for x in ours],[x['resolved_frame_index'] for x in expected])
            self.assertTrue(all(torch.equal(x['latent'],y['latent']) for x,y in zip(ours,expected)));self.assertNotIn('minimax_refs',out[0][0][1]);self.assertEqual(len(clip.items['images']),len(refs))
    def test_crop_float_and_budget_preflight(self):
        from h3rc import endpoints as ep
        a,r,e=self.plan([self.ref(data=torch.rand(1,64,128,3))]);ep.context(e,64,64,22);vae=VAE();ep.encode(e,vae,64,64)
        self.assertTrue(torch.equal(vae.inputs[0],e[0]['data'][:,:,32:96]));self.assertEqual(e[0]['tokens'],4)
        with self.assertRaisesRegex(ValueError,'full H3'):gen.generate(Clip(),'Still',64,64,22,named_references={'reference_0':self.ref()})
        class Never(Clip):
            def tokenize(self,*a,**k):raise AssertionError('Text encoding started')
        with self.assertRaisesRegex(ValueError,'budget'):gen.generate(Never(),'Still',64,64,22,vae=VAE(),named_references={'reference_0':self.ref()},budget_mode='Manual',manual_reference_budget=1)
    def test_hybrid_native_tokenizer_order(self):
        from h3rc import endpoints as ep
        from comfy.text_encoders.minimax import MiniMaxH3Tokenizer
        class Text:
            def tokenize_with_weights(self,text,**kw):return [[(text,1.0)]]
        tokenizer=MiniMaxH3Tokenizer.__new__(MiniMaxH3Tokenizer);tokenizer.qwen3vl_32b=Text()
        clip=type('C',(),{'tokenizer':tokenizer})()
        picture=torch.rand(1,64,64,3);a,r,e=self.plan([self.ref(),dict(kind='image',role='scene',tag='room',descriptor='a room',data=picture)])
        out,_=ep.prompt_for('@room. @start.',a,r,e,64,64,22);self.assertIn('<Picture 1>',out);self.assertIn('opening-frame image',out);self.assertNotIn('<Picture 2>',out)
        r[0]['item']=dict(type='image',data=picture);e[0]['pixels']=e[0]['data']
        tokens=ep.tokenize(clip,out,r,e)['qwen3vl_32b'][0];texts=[t[0] for t in tokens if isinstance(t[0],str)];images=[t[0]['data'] for t in tokens if isinstance(t[0],dict)]
        self.assertEqual(texts[:2],['<Picture 1>: ','opening-frame image: ']);self.assertIs(images[0],picture);self.assertIs(images[1],e[0]['data']);self.assertIsInstance(tokenizer.qwen3vl_32b,Text)

if __name__=='__main__':unittest.main(argv=['tests'],verbosity=2)
