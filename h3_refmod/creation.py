"""Directory creation of independently encoded resolution profiles."""
import json,os,re,shutil,tempfile,uuid,hashlib
from pathlib import Path
import torch
from .characters import roots,alias_value,save_details,load_character
from .generation import encode_voice
from .vendor.py.refmod_common import load_image_file
from .vendor.py.refmod_core import H3RefMod
from . import profiles

def common_inputs():
    return {'display_name':('STRING',{'default':'My Character'}),'package_name':('STRING',{'default':'','tooltip':'Folder and filename. Blank uses Display name. Existing packages are never overwritten.'}),'prompt_alias':('STRING',{'default':'my_character'}),'descriptor':('STRING',{'default':'','tooltip':'Describe the identity, for example a South Asian woman. This description is used in the H3 prompt.'}),'description':('STRING',{'default':'','multiline':True}),
      'profiles':('STRING',{'default':json.dumps(profiles.defaults())}),
      'sample_frames':('INT',{'default':16,'min':0,'max':100000,'tooltip':'Maximum source frames from EACH video. 16 evenly spaced frames is a compact starting point. 0 uses every frame in the chosen range; FPS is not changed.'}),
      'voice_duration_limit':(['Unlimited','Limited'],),'maximum_total_voice_duration':('FLOAT',{'default':10,'min':0}),
      'video_duration_limit':(['Unlimited','Limited'],),'maximum_total_video_duration':('FLOAT',{'default':15,'min':0}),
      'source_ranges':('STRING',{'default':'[]'})}

def create_selected(sources,vae=None,audio_vae=None,display_name='My Character',package_name='',prompt_alias='my_character',descriptor='',description='',profiles_config=None,profiles=None,sample_frames=16,source_ranges='[]',voice_duration_limit='Unlimited',maximum_total_voice_duration=10,video_duration_limit='Unlimited',maximum_total_video_duration=15):
    from . import profiles as processing
    from .selection import select_sources
    from .bundles import save_bundle
    config=processing.parse(profiles if profiles is not None else profiles_config if profiles_config is not None else processing.defaults())
    if type(sample_frames)!=int or sample_frames<0:raise ValueError('Maximum source frames per video must be a whole number of 0 or more.')
    selected,ranges=select_sources(sources,source_ranges,maximum_total_voice_duration,maximum_total_video_duration,voice_duration_limit,video_duration_limit,sample_frames)
    visuals=[s for s in selected if s['kind']!='audio'];voices=[s for s in selected if s['kind']=='audio']
    if not selected:raise ValueError('Select at least one picture, video or voice recording.')
    if visuals:
        from .visual_processing import require_vae
        require_vae(vae)
    if voices and audio_vae is None:raise ValueError('Connect the H3 audio VAE for selected voice recordings.')
    base=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',package_name.strip() or display_name.strip()).strip(' .')
    if not base or re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',base):raise ValueError('Enter a valid package name.')
    alias=alias_value(prompt_alias);mods=[];variants=[];source_meta=[];combined=[];cache={};models={};reports=[]
    def encode(s,p,group,canvas=None):
        # Only identical source processing may share the same stored encoding.
        pixels=processing.prepare(s['data'],p,canvas,models)
        digest=hashlib.sha256(pixels.detach().float().cpu().contiguous().numpy().tobytes()).hexdigest()
        key=(s['id'],tuple(pixels.shape),digest)
        if key not in cache:
            z=vae.encode(pixels).detach().cpu()
            if z.ndim!=5 or z.shape[:2]!=(1,24) or min(z.shape[2:])<1 or z.shape[3]%2 or z.shape[4]%2 or not torch.isfinite(z).all():raise ValueError('The visual VAE returned incompatible H3 reference data.')
            cache[key]=len(mods);mods.append(H3RefMod(name=s['source'],kind=s['kind'],latent=z,latent_t=z.shape[2],latent_h=z.shape[3],latent_w=z.shape[4],mode='encode'))
        index=cache[key];z=mods[index].latent
        return dict(source_id=s['id'],profile_id=p['id'],profile_name=p['name'],group=group,entry=index,kind=s['kind'],shape=list(z.shape),indices=list(range(z.shape[2])),latent=z)
    for i,s in enumerate(visuals):
        s=dict(s);s['id']=f'source-{i+1}';visuals[i]=s
        source_meta.append(dict(id=s['id'],name=Path(s['source']).stem.replace('_',' '),filename=s['source'],signature=s.get('signature',{}),kind=s['kind'],original_dimensions=[s['data'].shape[2],s['data'].shape[1]],source_range=s.get('range',{})))
        group='picture' if s['kind']=='image' else 'video'
        for p in config[group]:
            e=encode(s,p,group);e=processing.fit([e],p['budget'] if group=='video' else 0)[0];variants.append(e)
            reports.append(dict(source=s['source'],profile=p['name'],group=group,source_frames=len(s['data']),encoded_samples=e['shape'][2],retained_samples=len(e['indices']),dimensions=[e['shape'][4]*16,e['shape'][3]*16]))
    for p in config['combined'] if visuals else []:
        canvas=processing.canvas_for(visuals[0]['data'],p,True)
        entries=[encode(s,p,'combined',canvas) for s in visuals];fitted=processing.fit(entries,p['budget']);variants.extend(fitted)
        combined.append(dict(profile_id=p['id'],dimensions=list(canvas),sources=[e['source_id'] for e in fitted if e['indices']]))
        reports.extend(dict(source=s['source'],profile=p['name'],group='combined',source_frames=len(s['data']),encoded_samples=e['shape'][2],retained_samples=len(e['indices']),dimensions=list(canvas),status='omitted by combined video budget' if not e['indices'] else 'saved') for s,e in zip(visuals,fitted))
    if visuals and not variants:raise ValueError('Enable at least one visual profile.')
    # Encode voice clips separately and without temporal pooling or repeated copies.
    audio_mods=[H3RefMod(name=s['source'],kind='audio',latent=encode_voice(audio_vae,s['data']).detach().cpu(),sample_rate=32000,mode='encode',concept_type='voice') for s in voices]
    parent=roots()[0]/'refcharacters';parent.mkdir(parents=True,exist_ok=True);destination=parent/base;n=2
    while destination.exists():destination=parent/f'{base}_{n}';n+=1
    stage=Path(tempfile.mkdtemp(prefix='.creating_',dir=parent))
    try:
        from PIL import Image
        for s,meta in zip(visuals,source_meta):
            frame=s['data'][len(s['data'])//2].detach().cpu().float().clamp(0,1).numpy()
            image=Image.fromarray((frame*255).astype('uint8'));image.thumbnail((384,256));name=s['id']+'.png';image.save(stage/name);meta['preview']=name
            if s['kind']=='video':
                from .preview_media import video_overview
                name=s['id']+'.mp4'
                if video_overview(s['data'],stage/name):meta['preview_video']=name
        visual_files=[save_bundle(mods,stage/(base+'_visual'))] if mods else []
        audio_files=[save_bundle(audio_mods,stage/(base+'_audio'))] if audio_mods else []
        for e in variants:e['tokens']=len(e['indices'])*(e['shape'][3]//2)*(e['shape'][4]//2);e['dimensions']=[e['shape'][4]*16,e['shape'][3]*16]
        layout=dict(version=1,profiles=config,sources=source_meta,variants=[{k:v for k,v in e.items() if k!='latent'} for e in variants],combined=combined)
        c=dict(version=4,character_id=str(uuid.uuid4()),alias=alias,display_name=display_name,descriptor=descriptor,description=description,visuals=visual_files,voices=audio_files,profile_layout=layout,source_ranges=ranges,preview=str(stage/source_meta[0]['preview']) if source_meta else '',manifest_path=str(stage/(base+'.character.json')))
        save_details(c)
        from comfy_execution.graph import ExecutionBlocker
        image=ExecutionBlocker(None)
        if mods:
            decoded=vae.decode(mods[0].latent)
            if decoded.ndim==5:decoded=decoded[0]
            image=decoded[:1].detach().cpu()
        os.rename(stage,destination)
    finally:
        if stage.exists() and stage.parent.resolve()==parent.resolve() and stage.name.startswith('.creating_'):shutil.rmtree(stage)
    c=load_character(destination/(base+'.character.json'))
    paths='\n'.join(['Metadata: '+c['path']]+['Visual: '+p for p in c['visuals']]+['Audio: '+p for p in c['voices']])
    return {'result':(c,c['path'],image,paths),'ui':{'text':[paths,json.dumps(dict(profiles=reports,source_ranges=ranges),indent=2)]}}

class CreateFolder:
    @classmethod
    def INPUT_TYPES(cls):return {'required':{'folder':('STRING',{'default':''}),**common_inputs()},'optional':{'vae':('VAE',),'audio_vae':('VAE',)}}
    @classmethod
    def IS_CHANGED(cls,folder,**kwargs):
        from .source_catalog import KINDS
        root=Path(folder).expanduser().resolve()
        if not root.is_dir():return float('nan')
        return tuple((p.name,p.stat().st_size,p.stat().st_mtime_ns) for p in sorted(root.iterdir()) if p.is_file() and p.suffix.lower() in set().union(*KINDS.values()))
    RETURN_TYPES=('H3RC_CHARACTER','STRING','IMAGE','STRING');RETURN_NAMES=('character','manifest_path','decoded_image','created_paths');FUNCTION='create';CATEGORY='WorkflowX/Video/H3 Refmod';OUTPUT_NODE=True
    def create(self,folder,vae=None,audio_vae=None,**kwargs):
        from .media import load_audio
        from .source_catalog import KINDS
        from comfy_api.latest import InputImpl
        folder=Path(folder).expanduser().resolve()
        if not folder.is_dir():raise ValueError('Source folder not found.')
        sources=[]
        for p in sorted(folder.iterdir(),key=lambda p:p.name.casefold()):
            if p.is_file() and p.suffix.lower() in KINDS['image']:sources.append(dict(source=p.name,kind='image',data=load_image_file(str(p))))
            elif p.is_file() and p.suffix.lower() in KINDS['video']:
                c=InputImpl.VideoFromFile(str(p)).get_components();sources.append(dict(source=p.name,kind='video',data=c.images,fps=float(c.frame_rate)))
            elif p.is_file() and p.suffix.lower() in KINDS['audio']:sources.append(dict(source=p.name,kind='audio',data=load_audio(p)))
        for s in sources:
            st=(folder/s['source']).stat();s['signature']=dict(size=st.st_size,mtime_ns=st.st_mtime_ns)
        sources.sort(key=lambda s:({'image':0,'video':1,'audio':2}[s['kind']],s['source'].casefold()))
        return create_selected(sources,vae,audio_vae,**kwargs)
