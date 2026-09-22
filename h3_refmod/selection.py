"""Creation-only selection: use original recording frames, never a new FPS."""
import json
import math
import torch
from .media import trim_audio

def video_indices(frame_count,fps,start,duration,frame_limit):
    if not math.isfinite(fps) or fps<=0: raise ValueError('Recording has no valid frame rate.')
    first=max(0,math.ceil(start*fps-1e-7));stop=min(frame_count,math.ceil((start+duration)*fps-1e-7))
    indices=list(range(first,stop))
    if frame_limit:
        if int(frame_limit)!=frame_limit or frame_limit<1: raise ValueError('Frames per video must be a whole number of at least 1.')
        if len(indices)>frame_limit: indices=[indices[i] for i in torch.linspace(0,len(indices)-1,int(frame_limit)).round().long().tolist()]
    return indices

def select_sources(sources,source_ranges='[]',max_voice=10,max_video=15,voice_limit='Unlimited',video_limit='Unlimited',frame_limit=16):
    try: edits=json.loads(source_ranges or '[]')
    except ValueError: raise ValueError('Source selections could not be read. Open Edit source media and save again.')
    if not isinstance(edits,list): raise ValueError('Source selections must be a list.')
    by_name={s['source']:s for s in sources};ordered=[];seen=set()
    if len(by_name)!=len(sources): raise ValueError('Creation source names must be unique.')
    for edit in edits:
        name=edit.get('source')
        if name not in by_name or name in seen: raise ValueError(f'Source unavailable or repeated: {name}. Reopen Edit source media.')
        ordered.append(dict(by_name[name],**{k:v for k,v in edit.items() if k!='source'}));seen.add(name)
    ordered += [s for s in sources if s['source'] not in seen]
    remaining={'audio':float('inf') if voice_limit=='Unlimited' else float(max_voice),'video':float('inf') if video_limit=='Unlimited' else float(max_video)}
    if any(v<0 or math.isnan(v) for v in remaining.values()): raise ValueError('Duration limits cannot be negative.')
    selected=[];reports=[]
    for s in ordered:
        kind=s['kind'];report=dict(source=s['source'],kind=kind)
        if s.get('enabled',True) is False:
            reports.append(dict(report,status='excluded by user',duration=0));continue
        if kind=='image': reports.append(dict(report,status='selected'));selected.append(s);continue
        start=float(s.get('start',0));requested=float(s.get('duration',0));fps=float(s.get('fps',24))
        if not all(math.isfinite(x) and x>=0 for x in (start,requested)): raise ValueError('Recording ranges must be nonnegative numbers.')
        if kind=='video' and (not math.isfinite(fps) or fps<=0): raise ValueError('Recording has no valid frame rate.')
        available=s['data']['waveform'].shape[-1]/s['data']['sample_rate'] if kind=='audio' else len(s['data'])/fps
        if start>=available: raise ValueError(f'{s["source"]}: start lies outside the recording.')
        requested=min(available-start,requested or available-start);duration=min(requested,remaining[kind]);report.update(start=start,requested_duration=requested)
        if duration<=0: reports.append(dict(report,status='omitted by total duration limit',duration=0));continue
        if kind=='audio':
            data=trim_audio(s['data'],start,duration);actual=data['waveform'].shape[-1]/data['sample_rate']
        else:
            indices=video_indices(len(s['data']),fps,start,duration,frame_limit)
            if not indices: reports.append(dict(report,status='omitted: no source frame in selected interval',duration=0));continue
            data=s['data'][indices];actual=duration
            report.update(source_fps=fps,frames_selected=len(indices),source_frame_indices=indices,frame_limit=frame_limit)
        remaining[kind]-=actual;report.update(duration=actual,status='shortened by total duration limit' if actual+1e-6<requested else 'selected')
        reports.append(report);selected.append(dict(s,data=data,range=report,fps=fps))
    return selected,reports
