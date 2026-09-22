import json
from pathlib import Path
import torch
import node_helpers
from comfy_api.latest import io
from comfy_extras import nodes_minimax_h3 as native
from .characters import load_character, safe_path
from .compiler import resolve, compile_prompt
from .vendor.py.refmod_core import H3RefMod

_CACHE = {}

def load_mod(path):
    from .bundles import split_entry, load_entry
    p = safe_path(path); _,entry_index=split_entry(path)
    cache_key=str(p)+'#'+str(entry_index)
    s = p.stat()
    side = p.with_suffix('.json')
    import hashlib
    # Windows can report identical timestamps for rapid same-size replacements.
    with p.open('rb') as f: digest=hashlib.file_digest(f,'sha256').digest()
    stamp = (s.st_mtime_ns, s.st_size, digest, side.read_bytes() if side.exists() else b'')
    old = _CACHE.get(cache_key)
    if old is None or old[0] != stamp:
        mod = load_entry(p,entry_index or 0) or H3RefMod.load(str(p.with_suffix('')), device='cpu')
        z = mod.latent
        if mod.kind != 'audio':
            if z.ndim != 5 or tuple(z.shape[:2]) != (1,24) or min(z.shape[2:]) < 1 or z.shape[3] % 2 or z.shape[4] % 2:
                raise ValueError(f'{p.name}: expected H3 visual [1,24,T,H,W] with even spatial dimensions.')
            if (mod.latent_t,mod.latent_h,mod.latent_w) != tuple(z.shape[2:]) or not torch.isfinite(z).all():
                raise ValueError(f'{p.name}: visual metadata does not match its latent, or latent is not finite.')
        else:
            audio_valid(z)
        _CACHE[cache_key] = (stamp, mod)
        while len(_CACHE) > 24: _CACHE.pop(next(iter(_CACHE)))
    return _CACHE[cache_key][1]

def audio_valid(z):
    if not isinstance(z,torch.Tensor) or z.ndim != 4 or tuple(z.shape[:3]) != (1,32,2) or z.shape[-1] < 1 or not torch.isfinite(z).all():
        raise ValueError('Voice latent must be finite H3 audio [1,32,2,T].')

def validate_audio_input(vae, audio):
    if vae is None: raise ValueError('Connect the H3 audio VAE for a regular voice recording.')
    w = audio['waveform']
    if w.ndim != 3 or w.shape[0] != 1 or w.shape[1] not in (1,2) or w.shape[2] < 1 or not torch.isfinite(w).all():
        raise ValueError('Voice recording must be finite mono/stereo audio with a single batch.')
    if int(audio['sample_rate']) <= 0 or getattr(vae, 'audio_sample_rate', 32000) != 32000:
        raise ValueError('Use the 32 kHz H3 audio VAE and a positive source sample rate.')


def encode_voice(vae, audio):
    validate_audio_input(vae, audio)
    z, _ = native._encode_ref_audio(vae, audio)
    audio_valid(z)
    return z

def token_count(block):
    if block['kind'] == 'audio': return int(block['ref_audio_t']) * 2
    return int(block.get('latent_t', 1)) * (int(block['latent_h'])//2) * (int(block['latent_w'])//2) + 2*int(block.get('ref_audio_t',0))

class CaptureClip:
    """Ask the native node to prepare refs without running the text encoder twice."""
    def tokenize(self, prompt, **kwargs):
        self.items = kwargs.get('minimax_ref_items', [])
        return None
    def encode_from_tokens_scheduled(self, tokens):
        return [[None, {}]]

def raw_reference(row, vae, audio_vae, width, height, length, sizing):
    kind = row['kind']; clip = CaptureClip()
    if kind == 'audio':
        z = encode_voice(audio_vae, row['data'])
        return {'type':'audio'}, {'kind':'audio', 'ref_audio_t':z.shape[-1], 'audio_latent':z}
    if vae is None: raise ValueError('Connect the H3 visual VAE for image/video references.')
    kw = {'ref_images': {'ref_image_0': row['data']}} if kind == 'image' else {'ref_videos': {'ref_video_0':row['data']}}
    out = native.MiniMaxH3ReferenceToVideo.execute(clip, '', width, height, length, sizing, vae=vae, **kw)
    return clip.items[0], out[0][0][1]['minimax_refs'][0]

def prepare_saved(path, is_voice, owner, vae, shape=None, indices=None, present=True):
    m = load_mod(path)
    if is_voice:
        z = m.latent if m.kind == 'audio' else m.audio_latent
        if z is None: raise ValueError(f'{Path(path).name} contains no voice.')
        audio_valid(z)
        if m.sample_rate != 32000: raise ValueError('Saved voice uses an incompatible sample rate.')
        block = {'kind':'audio', 'ref_audio_t':z.shape[-1], 'audio_latent':z}
        item = {'type':'audio'}
    else:
        if present and vae is None: raise ValueError('Connect the H3 visual VAE to present saved character visuals to the text encoder.')
        block = m.ref_block(1.0, use_audio=False)
        from .visual_processing import process
        z,processing=process(path,shape or list(m.latent.shape),indices,vae)
        block.update(latent=z,latent_t=z.shape[2],latent_h=z.shape[3],latent_w=z.shape[4])
        item=None
        if present:
            frames = vae.decode(z)
            if frames.ndim == 5: frames = frames[0]
            if frames.ndim != 4: raise ValueError('Unexpected decoded H3 visual shape.')
            if m.kind == 'image': item = {'type':'image', 'data':frames[:1]}
            else:
                idx = list(range(0, frames.shape[0], native.FPS//2))
                item = {'type':'video', 'data':frames[idx], 'timestamps':[i/native.FPS for i in idx]}
    return dict(kind=block['kind'], owner=owner, source=Path(path).name, item=item, block=block, tokens=token_count(block),processing_report=processing if not is_voice else None)

def prepare_combined(description, owner, vae, present):
    from .runtime_combined import assemble
    z,reports=assemble(description,vae,with_report=True)
    block=dict(kind='video',ref_audio_t=0,audio_latent=None,latent=z,latent_t=z.shape[2],latent_h=z.shape[3],latent_w=z.shape[4])
    item=None
    if present:
        if vae is None: raise ValueError('Connect the H3 visual VAE to present the combined video to the text encoder.')
        frames=vae.decode(z)
        if frames.ndim==5: frames=frames[0]
        if frames.ndim!=4: raise ValueError('Unexpected decoded H3 visual shape.')
        idx=list(range(0,len(frames),native.FPS//2))
        item=dict(type='video',data=frames[idx],timestamps=[i/native.FPS for i in idx])
    return dict(kind='video',owner=owner,source='Runtime combined video',item=item,block=block,tokens=token_count(block),processing_report=reports)

class CharacterPicker:
    @classmethod
    def INPUT_TYPES(cls):
        from .representations import MODES
        from .media import transfer_inputs
        return {'required':{'character_path':('STRING',{'default':''}),'use_saved_voice':('BOOLEAN',{'default':True}),'descriptor':('STRING',{'default':''}),**transfer_inputs(),'visual_references':(MODES,),'reference_selection':('STRING',{'default':'{}'})}}
    RETURN_TYPES = ('H3RC_CHARACTER', 'STRING')
    RETURN_NAMES = ('character', 'selected_character')
    FUNCTION = 'pick'
    CATEGORY = 'WorkflowX/Video/H3 Refmod'
    @classmethod
    def IS_CHANGED(cls, **kwargs): return float('nan')
    def pick(self, character_path='', use_saved_voice=True, **settings):
        if not character_path: return None, 'No character selected'
        c = load_character(character_path)
        from .characters import configure_character
        c=configure_character(c,use_saved_voice,**settings)
        return c, f"@{c['alias']} — {c['display_name']}"


class ModReferenceToVideo(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        schema = native.MiniMaxH3ReferenceToVideo.define_schema()
        inputs = list(schema.inputs)
        for item in inputs:
            if item.id == 'vae': item.tooltip = 'Needed to show saved references to the vision-language encoder and to encode regular pictures/videos. Direct-only saved profiles do not need a VAE; their encoded values remain unchanged.'
            if item.id == 'audio_vae': item.tooltip = 'H3 audio VAE; required for regular audio and video soundtracks. Saved voices are already encoded.'
        inputs.insert(3, io.Autogrow.Input('characters', optional=True,
            template=io.Autogrow.TemplatePrefix(input=io.Custom('H3RC_CHARACTER').Input('character',tooltip='Saved character and optional voice from H3 Ref Character Picker. Refer to its @tag in your prompt.'),
                                               prefix='character_', min=0, max=16)))
        inputs.insert(4,io.Autogrow.Input('named_references',optional=True,template=io.Autogrow.TemplatePrefix(
            input=io.Custom('H3RC_REFERENCE').Input('reference',tooltip='Tagged media from an H3 Image, Audio or Video Reference node. Use its @tag in your prompt.'),prefix='reference_',min=0,max=32)))
        inputs.extend([io.Combo.Input('budget_mode',options=['Automatic','Manual']),
                       io.Int.Input('manual_reference_budget',default=20480,min=1,max=1048576),
                       io.Combo.Input('saved_character_conditioning',options=['Vision-language + direct references','Direct references only'],tooltip='Applies to saved characters only. Both modes supply visual data to the generator. The first also shows reconstructed references to the vision-language encoder. Regular media keeps native processing.'),
                       io.Boolean.Input('allow_reference_overflow',default=False,tooltip='Advanced: permit reference counts beyond documented allowances. Successful loading does not establish reliable output quality.')])
        return io.Schema(node_id='H3RCModReferenceToVideo', display_name='H3 Mod Reference to Video',
            category='WorkflowX/Video/H3 Refmod', inputs=inputs,
            outputs=[io.Conditioning.Output(display_name='positive',tooltip='H3 conditioning for the sampler, including your prompt and selected references.'),io.Latent.Output(display_name='latent',tooltip='Empty audiovisual latent for the requested output size and length.'),
                     io.String.Output(display_name='Prompt',tooltip='Final expanded prompt sent to H3. Connect to a text display to inspect it.'),io.String.Output(display_name='assignments',tooltip='Reference labels, character and voice associations, and token costs. Connect to a text display to inspect them.')])

    @classmethod
    def execute(cls, clip, prompt, width, height, length, ref_image_size='match', vae=None, audio_vae=None,
                characters=None, ref_images=None, ref_videos=None, ref_video_audios=None, ref_audios=None, named_references=None, budget_mode='Automatic', manual_reference_budget=20480, saved_character_conditioning='Vision-language + direct references',allow_reference_overflow=False):
        result = generate(clip, prompt, width, height, length, ref_image_size, vae, audio_vae,
                          characters, ref_images, ref_videos, ref_video_audios, ref_audios,
                          named_references=named_references,budget_mode=budget_mode,manual_reference_budget=manual_reference_budget,saved_character_conditioning=saved_character_conditioning,allow_reference_overflow=allow_reference_overflow)
        return io.NodeOutput(*result, ui={'text':[result[3],result[2]]})


def generate(clip,prompt,width,height,length,ref_image_size='match',vae=None,audio_vae=None,
             characters=None,ref_images=None,ref_videos=None,ref_video_audios=None,ref_audios=None,
             named_references=None,budget_mode='Automatic',manual_reference_budget=20480,saved_character_conditioning='Vision-language + direct references',allow_reference_overflow=False):
    from .reference_plan import build_plan,ordered
    if budget_mode not in ('Automatic','Manual'): raise ValueError('Unknown budget mode.')
    budget=manual_reference_budget if budget_mode=='Manual' else None
    active,refs=build_plan(prompt,characters,ref_images,ref_videos,ref_video_audios,ref_audios,named_references)
    from . import endpoints as ep
    endpoints,refs=ep.split(refs)
    ep.prompt_for(prompt,active,refs,endpoints,width,height,length)
    if endpoints: ep.require_vae(vae)
    from .representations import CONDITIONING,validate_counts
    if saved_character_conditioning not in CONDITIONING: raise ValueError('Unknown saved character conditioning mode.')
    counts=validate_counts(refs,allow_reference_overflow)
    present=saved_character_conditioning==CONDITIONING[0]
    saved=sum(r.get('tokens',0) for r in refs)
    if budget is not None and saved>budget: raise ValueError(f'Saved references need {saved:,} tokens; manual budget is {budget:,}. Choose fewer video samples or a smaller saved profile. Nothing changed.')
    if any(r['kind']!='audio' and ('path' not in r or present) for r in refs) and vae is None: raise ValueError('Connect the H3 visual VAE.')
    if any(r['kind']=='audio' and 'path' not in r for r in refs) and audio_vae is None: raise ValueError('Connect the H3 audio VAE.')
    if endpoints: ep.encode(endpoints,vae,width,height)
    def prepare_group(rows,images=None,videos=None,sounds=None,audios=None,group_length=None):
        if not rows: return
        for a in list((sounds or {}).values())+list((audios or {}).values()): validate_audio_input(audio_vae,a)
        capture=CaptureClip()
        out=native.MiniMaxH3ReferenceToVideo.execute(capture,'',width,height,group_length or length,ref_image_size,
            vae=vae,audio_vae=audio_vae,ref_images=images,ref_videos=videos,ref_video_audios=sounds,ref_audios=audios)
        blocks=iter(out[0][0][1].get('minimax_refs',[]))
        for row,item in zip(rows,capture.items,strict=True):
            row['item']=item
            if row.get('paired'): row['tokens']=0
            else: row['block']=next(blocks);row['tokens']=token_count(row['block'])
    raw=[r for r in refs if r['category']=='raw']
    prepare_group(raw,dict(ordered(ref_images)),dict(ordered(ref_videos)),dict(ordered(ref_video_audios)),dict(ordered(ref_audios)))
    named=[r for r in refs if r['category']=='named'];i=0
    while i<len(named):
        r=named[i]
        if r.get('paired'):
            v=named[i+1];prepare_group([r,v],videos={'ref_video_0':v['data']},sounds={'ref_video_audio_0':r['data']},group_length=len(v['data']));i+=2
        elif r['kind']=='image': prepare_group([r],images={'ref_image_0':r['data']});i+=1
        elif r['kind']=='video': prepare_group([r],videos={'ref_video_0':r['data']},group_length=len(r['data']));i+=1
        else: prepare_group([r],audios={'ref_audio_0':r['data']});i+=1
    for row in refs:
        if row.get('runtime_combined'): row.update(prepare_combined(row['runtime_combined'],row['owner'],vae,present))
        elif 'path' in row: row.update(prepare_saved(row['path'],row['is_voice'],row['owner'],vae,row.get('shape'),row.get('indices'),present))
    for row in refs:
        if row.get('category')=='saved' and row['kind']!='audio' and row.get('block',{}).get('latent') is not None:
            actual=list(row['block']['latent'].shape);row['shape']=actual;row['runtime_dimensions']=[actual[4]*16,actual[3]*16]
    total=sum(r['tokens'] for r in refs)+sum(r['tokens'] for r in endpoints)
    expanded,report=ep.prompt_for(prompt,active,refs,endpoints,width,height,length)
    totals={k:sum(r['tokens'] for r in refs if r['category']==k) for k in ('saved','named','raw')}
    voice_total=sum(2*int(r.get('block',{}).get('ref_audio_t',0)) for r in refs)
    original=sum(r.get('original_tokens',r['tokens']) for r in refs)
    report+='\nSaved character conditioning: '+saved_character_conditioning
    report+='\nReference counts: '+json.dumps(counts)
    for character in active:
        if character.get('selection_report'): report+='\n@'+character['alias']+' saved profile selections: '+json.dumps(character['selection_report'])
    for row in refs:
        if row.get('processing_report'): report+='\n'+row.get('selection_name',row.get('source','Reference'))+': '+json.dumps(row['processing_report'])
    for row in refs:
        if row.get('runtime_combined'):
            report+='\nRuntime combined video: '+str(row['runtime_combined']['source_count'])+' selected sources; sent to H3 as one video reference.'
        if row.get('indices') is not None: report+='\n'+row.get('selection_name','Saved reference')+': '+str(len(row['indices']))+' of '+str(row['original_shape'][2])+' saved samples; '+row.get('representation','')
        if row.get('runtime_dimensions'):
            fmt=lambda dims:' × '.join(map(str,dims)) if dims else 'unknown (older package)'
            report+='\nSource: '+fmt(row.get('original_dimensions'))+'; saved: '+fmt(row.get('saved_dimensions'))+'; this generation: '+fmt(row['runtime_dimensions'])
    report+='\nExact reference tokens: '+str(total)+'; original: '+str(original)+'; budget: '+(str(budget) if budget is not None else 'Automatic (no imposed limit)')
    report+='\nCategory subtotals: '+json.dumps(totals)+'; audio tokens (included above): '+str(voice_total)
    character_costs={}
    for c in active:
        if c.get('temporary') and not c.get('is_character'): continue
        visual=sum(r['tokens'] for r in refs if r.get('owner')==c['alias'] and r['kind']!='audio')
        audio=0
        for i,r in enumerate(refs):
            if r['kind']=='audio' and (r.get('target') or r.get('owner'))==c['alias'] and r.get('role')=='character voice':
                audio+=2*int((refs[i+1] if r.get('paired') else r).get('block',{}).get('ref_audio_t',0))
        character_costs['@'+c['alias']]={'visual':visual,'voice':audio,'total':visual+audio}
    report+='\nPer-character tokens: '+json.dumps(character_costs)

    if budget is not None and total>budget: raise ValueError(f'References require {total} tokens; budget {budget}. Nothing dropped.\n{report}')
    report+='\nEndpoint tokens: '+str(sum(r['tokens'] for r in endpoints)) if endpoints else ''
    tokens=ep.tokenize(clip,expanded,refs,endpoints) if endpoints else clip.tokenize(expanded,minimax_ref_items=[r['item'] for r in refs if r.get('item') is not None])
    positive=clip.encode_from_tokens_scheduled(tokens)
    if not any('minimax_token_tags' in m for _,m in positive): raise ValueError('Use the MiniMax H3 text encoder; minimax_token_tags are missing.')
    payload=[r['block'] for r in refs if 'block' in r]
    if payload: positive=node_helpers.conditioning_set_values(positive,{'minimax_refs':payload})
    if endpoints: positive=node_helpers.conditioning_set_values(positive,{'minimax_keyframes':[r['keyframe'] for r in endpoints]})
    latent,_=native._empty_av_latent(width,height,length)
    return positive,latent,expanded,report


class InspectText:
    @classmethod
    def INPUT_TYPES(cls): return {'required':{'text':('STRING',{'forceInput':True})}}
    RETURN_TYPES=('STRING',);FUNCTION='show';CATEGORY='WorkflowX/Video/H3 Refmod';OUTPUT_NODE=True
    def show(self,text): return {'result':(text,),'ui':{'text':[text]}}
