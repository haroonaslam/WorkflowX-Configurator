"""Profile selection is shared by browser preview and execution."""
import json
from .bundles import expand
from .optimization import visual_cost
MODES=['Saved combined video','Pictures only','Pictures and video clips','Build combined video from selected references']
CONDITIONING=['Vision-language + direct references','Direct references only']

def catalog(character):
    from .characters import asset_stats
    paths=expand(character['visuals']);layout=character.get('profile_layout');result=[]
    if not layout:
        if not character.get('external'):raise ValueError('Recreate this custom character package to use saved profiles.')
        for i,p in enumerate(paths):
            st=asset_stats(p);result.append(dict(id=f'external-{i}',source_id=f'external-{i}',profile_id='external',profile_name='External',group='picture' if st['kind']=='image' else 'video',representation='source',kind=st['kind'],name='External reference',path=p,shape=st['shape'],tokens=st['visual_tokens'],indices=list(range(st['shape'][2]))))
        return result
    if layout.get('version')!=1:raise ValueError('Unsupported saved profile layout.')
    sources={e['id']:e for e in layout['sources']}
    for e in layout['variants']:
        if e['source_id'] not in sources or not 0<=e['entry']<len(paths):raise ValueError('Invalid saved profile source or tensor entry.')
        st=asset_stats(paths[e['entry']]);indices=e['indices']
        if e['kind']!=st['kind'] or e['shape']!=st['shape'] or len(set(indices))!=len(indices) or any(type(i)!=int or not 0<=i<st['shape'][2] for i in indices):raise ValueError('Saved profile data changed. Recreate the package; no alternative was substituted.')
        result.append(dict(sources[e['source_id']],**{k:v for k,v in e.items() if k not in ('source_id','tokens')},source_id=e['source_id'],path=paths[e['entry']],tokens=st['visual_tokens'],representation='combined_source' if e['group']=='combined' else 'source'))
    return result

def select(character,mode=MODES[0],settings='{}'):
    from .profiles import fit
    if mode not in MODES:raise ValueError('Choose a valid reference selection mode.')
    settings=json.loads(settings or '{}') if isinstance(settings,str) else settings
    if not isinstance(settings,dict):raise ValueError('Invalid reference selection settings.')
    if settings.get('character_id') and settings['character_id']!=character['character_id']:raise ValueError('Selection belongs to another character. Reset selection in Choose references.')
    options=settings.get('modes',{}).get(mode,{})
    entries=catalog(character);combined=mode in (MODES[0],MODES[3])
    if character.get('external'):
        if mode==MODES[3]:raise ValueError('External RefMods have no independent source boundaries. Recreate from original media to build subsets.')
        eligible=[e for e in entries if mode!=MODES[1] or e['kind']=='image']
        if options.get('budget',0):raise ValueError('External source boundaries are unknown; protected video-budget reduction is unavailable.')
    else:eligible=[e for e in entries if (e['group']=='combined' if combined else e['group']!='combined' and (mode!=MODES[1] or e['kind']=='image'))]
    if entries and not eligible:raise ValueError('This reference mode has no saved profiles in this package.')
    ids=list(dict.fromkeys(e['source_id'] for e in eligible if e['indices']))
    selected=ids if mode==MODES[0] else options.get('selected',ids)
    if not isinstance(selected,list) or len(set(selected))!=len(selected) or any(i not in ids for i in selected):raise ValueError('Selected sources are unavailable. Review Choose references.')
    if eligible and not selected:raise ValueError('Select at least one reference.')
    order=options.get('order',selected);selected=sorted(selected,key=lambda i:order.index(i) if i in order else len(order)+ids.index(i))
    chosen=[];report=[]
    defaults=options.get('defaults',{});overrides=options.get('overrides',{})
    common={}
    for kind in ('image','video'):
        groups=[{e['profile_id'] for e in eligible if e['source_id']==sid and e['indices']} for sid in selected if any(e['source_id']==sid and e['kind']==kind for e in eligible)]
        common[kind]=set.intersection(*groups) if groups else set()
    combined_profile=options.get('profile')
    if combined and not character.get('external'):
        available=list(dict.fromkeys(e['profile_id'] for e in eligible))
        combined_profile=combined_profile or (available[0] if available else None)
        if combined_profile not in available:raise ValueError('The selected combined profile is unavailable.')
    for sid in selected:
        choices=[e for e in eligible if e['source_id']==sid];kind=choices[0]['kind']
        if combined and not character.get('external'):
            profile=combined_profile
        else:
            default=defaults.get(kind)
            if default is not None and default not in common[kind]:raise ValueError(f'The default {kind} profile is unavailable for all selected sources. Choose another default or Choose profiles individually.')
            explicit=overrides.get(sid)
            profile=explicit or default
            if not profile and kind not in defaults:profile=next((e['profile_id'] for e in choices if e['profile_id'] in common[kind]),None)
            if not profile:raise ValueError(f'{choices[0]["name"]}: choose a saved profile individually.')
        e=next((dict(e) for e in choices if e['profile_id']==profile),None)
        if e is None:raise ValueError(f'{choices[0]["name"]}: selected profile is unavailable.')
        if e['indices']:chosen.append(e)
        elif mode==MODES[0]:report.append(dict(source=e['name'],profile=e['profile_name'],saved_samples=0,retained_samples=0,status='omitted when this combined profile was created'))
        else:raise ValueError(f'{e["name"]}: this profile contains no saved samples for this source. Deselect it or choose another profile.')
    fitted=fit(chosen,options.get('budget',0));result=[]
    for e in fitted:
        report.append(dict(source=e['name'],profile=e['profile_name'],saved_samples=len(next(x for x in chosen if x['source_id']==e['source_id'])['indices']),retained_samples=len(e['indices']),status='retained' if e['indices'] else 'omitted by video budget'))
        if not e['indices']:continue
        e['original_shape']=list(e['shape']);e['shape']=list(e['shape']);e['shape'][2]=len(e['indices']);e['runtime_tokens']=visual_cost(e['shape']);e['saved_dimensions']=[e['shape'][4]*16,e['shape'][3]*16];e['runtime_dimensions']=e['saved_dimensions'];e['processing']='Unchanged saved reference';result.append(e)
    return result,report

def count_status(refs):
    counts={k:sum(r['kind']==k for r in refs) for k in ('image','video','audio')}
    # A synchronized soundtrack belongs to its video's source file.
    total=sum(not r.get('paired',False) for r in refs)
    limits={'image':9,'video':3,'audio':3}
    excess=[f'{counts[k]} {k} references (documented allowance {v})' for k,v in limits.items() if counts[k]>v]
    if total>12: excess.append(f'{total} reference sources (documented allowance 12)')
    breakdown={}
    for r in refs:
        owner='@'+r['owner'] if r.get('owner') else ('Regular references' if r.get('category')=='raw' else 'Named references')
        d=breakdown.setdefault(owner,dict(image=0,video=0,audio=0));d[r['kind']]+=1
    return dict(counts=counts,total=total,over_limit=bool(excess),message='; '.join(excess),breakdown=breakdown)


def validate_counts(refs,allow=False):
    status=count_status(refs)
    if status['over_limit'] and not allow:
        raise ValueError('Too many references: '+status['message']+'. Open Choose references to select fewer sources, or use Combined RefMod video where it resolves the count. Advanced users can explicitly allow counts beyond documented limits.')
    return status
