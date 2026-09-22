"""One ordered reference plan for native conditioning and browser diagnostics."""
import json
from .characters import metadata, voice_paths, asset_stats
from .compiler import resolve
from .optimization import visual_cost


def ordered(values):
    return [(k,v) for k,v in sorted((values or {}).items(),key=lambda kv:int(kv[0].rsplit('_',1)[-1])) if v is not None and v is not False]


def fingerprint(value):
    return json.dumps({k:v for k,v in value.items() if k not in ('data','soundtrack','statistics','preview')},sort_keys=True,default=str)


def build_plan(prompt,characters=None,ref_images=None,ref_videos=None,ref_video_audios=None,ref_audios=None,named_references=None):
    from .characters import configure_character
    active=resolve('',[c if 'runtime_shapes' in c else configure_character(c,use_saved_voice=c.get('use_voice',True)) for _,c in ordered(characters)])
    rows=[]; namespace={c['alias']:('character',c['character_id']) for c in active}
    def regular(kind,socket,data,**extra):
        rows.append(dict(kind=kind,socket=socket,source=socket,owner='',category='raw',data=data,**extra))
    for name,data in ordered(ref_images): regular('image',name,data)
    videos=dict(ordered(ref_videos));sounds=dict(ordered(ref_video_audios))
    for name in sounds:
        if 'ref_video_'+name.rsplit('_',1)[-1] not in videos: raise ValueError(f'{name}: connect its matching reference video or disconnect the soundtrack.')
    for name,data in videos.items():
        audio='ref_video_audio_'+name.rsplit('_',1)[-1]
        if audio in sounds: regular('audio',audio,sounds[audio],paired=True)
        regular('video',name,data)
    for name,data in ordered(ref_audios): regular('audio',name,data)
    def register(ref):
        tag=ref['tag'].lower(); fp=fingerprint(ref)
        if tag in namespace:
            if namespace[tag]==('reference',fp): return False
            raise ValueError(f'Conflicting @{tag}. Each character/reference needs a unique tag; repeated references must have identical settings.')
        namespace[tag]=('reference',fp);return True
    for socket,ref in ordered(named_references):
        if not ref.get('enabled',True): continue
        if ref.get('role') in ('First frame','Last frame'):
            prior=next((r for r in rows if r.get('endpoint') and r['role']==ref['role']),None)
            if prior: raise ValueError(f'{ref["role"]} is connected twice: @{prior["tag"]} and @{ref["tag"]}.')
        if not register(ref): continue
        kind=ref['kind']; tag=ref['tag'].lower(); role=ref['role']
        if kind=='image' and role in ('First frame','Last frame'):
            count=len(ref['data']) if ref.get('data') is not None else int(ref.get('batch_count',1))
            if count!=1: raise ValueError(f'@{tag}: {role} requires exactly one selected image.')
            prior=next((r for r in rows if r.get('endpoint') and r['role']==role),None)
            if prior: raise ValueError(f'{role} is connected twice: @{prior["tag"]} and @{tag}.')
            rows.append(dict(ref,tag=tag,owner='',target='',endpoint=True,category='endpoint',socket=socket));continue
        reusable=kind=='image' and role=='character appearance' and not ref.get('target')
        if reusable:
            active.append(dict(alias=tag,character_id='temporary:'+tag,display_name=tag,description=ref.get('instructions',''),descriptor=ref.get('descriptor',''),
                retain=ref.get('retain',''),change=ref.get('change',''),reference_type=ref.get('reference_type'),preservation=ref.get('preservation','Automatic by role'),preservation_text=ref.get('preservation_text',''),visuals=[],voices=[],temporary=True,is_character=role=='character appearance',role=role,target=ref.get('target','')))
        sound=ref.get('soundtrack')
        if sound:
            if not register(sound): raise ValueError('A paired soundtrack must have its own unique tag.')
            rows.append(dict(sound,owner=sound.get('target',''),category='named',paired=True,socket=socket+'.audio',tag=sound['tag'].lower()))
        if kind=='image':
            data=ref.get('data'); batches=len(data) if data is not None else int(ref.get('batch_count',1))
            for i in range(batches):
                rows.append(dict(ref,data=data[i:i+1] if data is not None else None,owner=tag if reusable else '',category='named',socket=socket,asset_index=i))
        else:
            rows.append(dict(ref,owner=tag if reusable else '',category='named',socket=socket))
    for c in active:
        if c.get('temporary'): continue
        combined=c.get('runtime_combined')
        if combined:
            rows.append(dict(kind='video',owner=c['alias'],source='Runtime combined video',path=c['visuals'][0],is_voice=False,category='saved',role='saved character appearance',
                shape=combined['shape'],tokens=combined['tokens'],original_tokens=c['original_visual_tokens'],runtime_combined=combined,
                runtime_dimensions=combined['dimensions'],selection_name='Runtime combined video',representation='runtime combined'))
        for i,path in enumerate([] if combined else c['visuals']):
            selected=c.get('selected_references',[{}]*len(c['visuals']))[i]
            stat=asset_stats(path)
            if selected.get('original_shape',stat['shape'])!=stat['shape']: raise ValueError('A saved visual changed after selection. Refresh the character and review Choose references.')
            shape=c.get('runtime_shapes',[None]*len(c['visuals']))[i] or stat['shape']
            rows.append(dict(kind=stat['kind'],owner=c['alias'],source=path,path=path,is_voice=False,category='saved',role='saved character appearance',
                shape=shape,indices=selected.get('indices'),selection_name=selected.get('name','Saved reference'),representation=selected.get('representation','legacy'),original_shape=stat['shape'],original_tokens=stat['visual_tokens'],tokens=visual_cost(shape),
                original_dimensions=selected.get('original_dimensions'),saved_dimensions=selected.get('saved_dimensions'),runtime_dimensions=selected.get('runtime_dimensions')))
        if c.get('use_voice',True):
            for path in voice_paths(c):
                stat=asset_stats(path,True)
                rows.append(dict(kind='audio',owner=c['alias'],target=c['alias'],role='character voice',mode='reference',source=path,path=path,is_voice=True,
                                 category='saved',tokens=stat['audio_tokens'],original_tokens=stat['audio_tokens'],duration=stat['shape'][-1]/40))
    # Character targets exclude scene/prop/style content subjects.
    targets={c['alias'] for c in active if not c.get('temporary') or c.get('is_character')}
    voice_sources={}
    for r in rows:
        target=r.get('target','')
        if r.get('role')=='custom':
            text=str(r.get('descriptor','')).strip()
            if not text: raise ValueError(f'@{r.get("tag")}: Custom reference needs a Descriptor.')
            if any(x in text for x in ('@','<','>','\n','\r')): raise ValueError('Custom reference Descriptor must be plain text without tags or newlines.')
        if r.get('role')=='association':
            if not target: raise ValueError(f'@{r.get("tag")}: Association needs an associated character.')
            if not str(r.get('descriptor','')).strip(): raise ValueError(f'@{r.get("tag")}: Association needs a Descriptor explaining what the picture shows.')
        if target and target not in targets: raise ValueError(f'@{r.get("tag",r.get("owner"))}: associated character @{target} is not connected.')
        if r.get('role')=='character voice':
            if not target: raise ValueError(f'@{r.get("tag", "voice")}: select an associated character.')
            source='saved collection' if r['category']=='saved' else '@'+r['tag']
            if target in voice_sources and voice_sources[target]!=source:
                raise ValueError(f'@{target} has multiple voice sources ({voice_sources[target]}, {source}). Disable Use saved voice or disconnect the extra voice.')
            voice_sources[target]=source
    return active,rows
