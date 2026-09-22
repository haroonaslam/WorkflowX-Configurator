"""Selected in-memory media references. Source selection always has explicit precedence."""
import math
from pathlib import Path
from fractions import Fraction
import torch
import folder_paths
from comfy_api.latest import InputImpl, Types
from .characters import alias_value

AUDIO_MODES=['reference','weak_reference','partial reuse','complete-track reuse']
IMAGE_ROLES=['character appearance','association','wardrobe','scene','prop','style','custom','First frame','Last frame']
AUDIO_ROLES=['character voice','ambience','music','sound effect','complete soundtrack']
VIDEO_ROLES=['motion','performance','camera','scene','custom']

def select_image_indices(count, selection):
    if not selection or str(selection).strip().lower()=='all': return list(range(count))
    try: indices=[int(x.strip())-1 for x in str(selection).split(',')]
    except ValueError: raise ValueError('Choose all images or enter image numbers separated by commas, for example 2,1,3.')
    if len(set(indices))!=len(indices) or any(i<0 or i>=count for i in indices):
        raise ValueError(f'Choose each image number once, between 1 and {count}.')
    return indices


def trim_audio(audio,start=0,duration=0):
    if audio is None: return None
    sr=int(audio['sample_rate']); w=audio['waveform']
    if sr<=0 or start<0 or duration<0: raise ValueError('Use a positive sample rate and nonnegative range.')
    first=round(start*sr); end=min(w.shape[-1],first+round(duration*sr)) if duration else w.shape[-1]
    if first>=end: raise ValueError('Audio range contains no samples.')
    return dict(waveform=w[...,first:end],sample_rate=sr)


def select_video(frames,fps=24,audio=None,start=0,duration=0):
    if fps<=0 or start<0 or duration<0: raise ValueError('FPS must be positive; start and duration must be nonnegative.')
    available=len(frames)/fps-start
    seconds=min(available,duration) if duration else available
    n=math.floor(seconds*24+1e-7)
    if n<5: raise ValueError('Selected video must contain at least five H3 frames at 24 FPS.')
    aligned=n-((n-5)%17)
    idx=((torch.arange(aligned,dtype=torch.float64)/24+start)*fps).floor().long().clamp(max=len(frames)-1)
    selected=frames.index_select(0,idx.to(frames.device))
    sound=trim_audio(audio,start,aligned/24) if audio is not None else None
    return selected,sound,dict(start=start,requested_duration=seconds,duration=aligned/24,source_fps=fps,fps=24,
                              requested_frames=n,aligned_frames=aligned,alignment=f'{n} -> {aligned} frames (17k+5)')


def file_path(name):
    p=Path(folder_paths.get_annotated_filepath(name)).resolve()
    allowed=[Path(folder_paths.get_input_directory()).resolve(),Path(folder_paths.get_output_directory()).resolve(),Path(folder_paths.get_temp_directory()).resolve()]
    if not p.is_file() or not any(p.is_relative_to(r) for r in allowed): raise ValueError('Select an existing media file in ComfyUI input, output, or temp.')
    return p


def load_audio(path):
    from comfy_extras.nodes_audio import load
    w,sr=load(str(path)); return dict(waveform=w.unsqueeze(0),sample_rate=sr)


def source_key(source,file,connected):
    if source=='Load file':
        p=file_path(file);st=p.stat();return (str(p),st.st_size,st.st_mtime_ns)
    return id(connected)


def descriptor(kind,tag,role,associated_character='',use_instructions='',audio_mode='reference',**extra):
    target=alias_value(associated_character) if associated_character.strip() else ''
    return dict(kind=kind,tag=alias_value(tag),role=role,target=target,instructions=use_instructions.strip(),**extra)


def common(roles,tag):
    return {'source':(['Connected input','Load file'],),'file':('STRING',{'default':''}),
        'tag':('STRING',{'default':tag}),'role':(roles,), 'associated_character':('STRING',{'default':''}),
        'use_instructions':('STRING',{'default':'','multiline':True})}


PRESERVATION=['Custom','Full','Weak reference']
def transfer_inputs():
    return {'retain':('STRING',{'default':'','multiline':True,'tooltip':'What H3 should keep from this source. Example: facial identity, voice timbre, room layout, or camera movement. Leave blank for the selected role defaults.'}),
            'change':('STRING',{'default':'','multiline':True,'tooltip':'What H3 should change or exclude. Example: change the jacket to red; exclude people; generate new dialogue instead of source words. Does not alter the saved source.'})}

def transfer_text(retain='',change=''):
    return ' '.join(([f'Retain: {retain.strip()}'] if retain.strip() else [])+([f'Change: {change.strip()}'] if change.strip() else []))

def preservation_inputs():
    return {'reference_type':(['partially_preserved','fully_preserved','attribute_transfer','weak_reference'],{'tooltip':'Prompt indicator: fully_preserved keeps the defined content; partially_preserved allows selected changes; attribute_transfer applies features to another subject; weak_reference keeps broad resemblance. Retain and Change describe the details.'}),**transfer_inputs()}


def preservation_settings(settings):
    mode=settings.get('preservation','Custom');retain=settings.get('retain','').strip();change=settings.get('change','').strip()
    if mode not in PRESERVATION: raise ValueError('Unknown visual preservation mode.')
    if mode=='Full': retain=change=''
    return dict(preservation=mode,reference_type=settings.get('reference_type','partially_preserved'),retain=retain,change=change,preservation_text=transfer_text(retain,change))


class ImageReference:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{**common(IMAGE_ROLES,'image_ref'),'batch_selection':('STRING',{'default':'all'}),'descriptor':('STRING',{'default':'','tooltip':'Describe the referenced content, for example: the living room with grey sofa. Its @tag expands to this text followed by the Picture or Video reference label.'}),**preservation_inputs()},'optional':{'image':('IMAGE',)}}
    RETURN_TYPES=('H3RC_REFERENCE','IMAGE','STRING'); RETURN_NAMES=('named_reference','selected_images','selection_report')
    CATEGORY='WorkflowX/Video/H3 Refmod'; FUNCTION='select'
    @classmethod
    def IS_CHANGED(cls,**kw): return float('nan')
    def select(self,source,file,tag,role,associated_character='',use_instructions='',batch_selection='all',image=None,descriptor_text='',**settings):
        if source=='Load file':
            file_path(file)
            import nodes
            image=nodes.LoadImage().load_image(file)[0]
            batch_selection='all'  # Connected-batch selection is inactive in file mode.
        elif source!='Connected input': raise ValueError('Invalid image source.')
        if image is None: raise ValueError('Connect an IMAGE or select Load file.')
        indices=select_image_indices(len(image),batch_selection)
        selected=image[indices]
        if role in ('First frame','Last frame') and len(indices)!=1: raise ValueError(f'@{tag}: {role} requires exactly one selected image. Choose one batch position.')
        ref=descriptor('image',tag,role,associated_character,'',descriptor=settings.get('descriptor',descriptor_text).strip(),**preservation_settings(settings),data=selected,source_dimensions=[selected.shape[2],selected.shape[1]],batch_count=len(selected),source=file if source=='Load file' else 'connected image',source_identity=('image',source,file,tuple(indices),source_key(source,file,image)))
        return output(ref,(selected,),f'@{ref["tag"]}: {len(indices)} selected images; batch positions {[i+1 for i in indices]}')


class AudioReference:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{**common(AUDIO_ROLES+['custom'],'voice_ref'),'reference_type':(['reference','weak_reference','partially_copy','fully_copy'],{'tooltip':'Prompt indicator: reference borrows sound characteristics; weak_reference borrows atmosphere; partially_copy requests selected layers or intervals; fully_copy requests the complete recording as the final soundtrack. Specify details in Retain and Change.'}),'descriptor':('STRING',{'default':'','tooltip':'Describe what this audio represents. For Custom, H3 receives: <Audio N> is your description. Use its @tag in the scene prompt.'}),
            'start_seconds':('FLOAT',{'default':0,'min':0}), 'duration_seconds':('FLOAT',{'default':0,'min':0,'tooltip':'0 uses the remaining recording.'}),**transfer_inputs()},'optional':{'audio':('AUDIO',)}}
    RETURN_TYPES=('H3RC_REFERENCE','AUDIO','STRING'); RETURN_NAMES=('named_reference','selected_audio','selection_report')
    CATEGORY='WorkflowX/Video/H3 Refmod'; FUNCTION='select'
    @classmethod
    def IS_CHANGED(cls,**kw): return float('nan')
    def select(self,source,file,tag,role,associated_character='',use_instructions='',audio_mode='reference',start_seconds=0,duration_seconds=0,audio=None,retain='',change='',**settings):
        if source=='Load file': audio=load_audio(file_path(file))
        elif source!='Connected input': raise ValueError('Invalid audio source.')
        if audio is None: raise ValueError('Connect AUDIO or select Load file.')
        selected=trim_audio(audio,start_seconds,duration_seconds)
        duration=selected['waveform'].shape[-1]/selected['sample_rate']
        ref=descriptor('audio',tag,role,associated_character,transfer_text(retain,change),audio_mode,reference_type=settings.get('reference_type','reference'),descriptor=settings.get('descriptor','').strip() if role=='custom' else '',retain=retain,change=change,data=selected,duration=duration,
            source_range=dict(start=start_seconds,duration=duration),source=file if source=='Load file' else 'connected audio',source_identity=('audio',source,file,start_seconds,duration,source_key(source,file,audio)))
        return output(ref,(selected,),f'@{ref["tag"]}: {start_seconds:.3f}–{start_seconds+duration:.3f}s')


class VideoReference:
    @classmethod
    def INPUT_TYPES(cls):
        req=common(VIDEO_ROLES,'video_ref'); req['source']=(['Connected video','Connected frames','Load file'],)
        req.update(fps=('FLOAT',{'default':24,'min':0.01,'max':1000}),start_seconds=('FLOAT',{'default':0,'min':0}),duration_seconds=('FLOAT',{'default':0,'min':0}),
            use_soundtrack=('BOOLEAN',{'default':False}),audio_tag=('STRING',{'default':'video_sound'}),audio_role=(AUDIO_ROLES,),
            audio_character=('STRING',{'default':''}),audio_instructions=('STRING',{'default':'','multiline':True}))
        req.update({'descriptor':('STRING',{'default':'','tooltip':'Describe the referenced content, for example: the living room with grey sofa. Its @tag expands to this text followed by the Picture or Video reference label.'})})
        req.update(preservation_inputs())
        return {'required':req,'optional':{'video':('VIDEO',),'frames':('IMAGE',),'audio':('AUDIO',)}}
    RETURN_TYPES=('H3RC_REFERENCE','VIDEO','IMAGE','AUDIO','FLOAT','STRING')
    RETURN_NAMES=('named_reference','selected_video','selected_frames','selected_audio','fps','selection_report')
    CATEGORY='WorkflowX/Video/H3 Refmod'; FUNCTION='select'
    @classmethod
    def IS_CHANGED(cls,**kw): return float('nan')
    def select(self,source,file,tag,role,associated_character='',use_instructions='',fps=24,start_seconds=0,duration_seconds=0,
               use_soundtrack=False,audio_tag='video_sound',audio_role='character voice',audio_mode='reference',audio_character='',audio_instructions='',video=None,frames=None,audio=None,descriptor_text='',**settings):
        if source=='Load file': video=InputImpl.VideoFromFile(str(file_path(file)))
        if source in ('Load file','Connected video'):
            if video is None: raise ValueError('Connect VIDEO or choose a video file.')
            c=video.get_components();frames=c.images;audio=c.audio;fps=float(c.frame_rate)
        elif source!='Connected frames': raise ValueError('Invalid video source.')
        if frames is None: raise ValueError('Connect a frame batch.')
        if use_soundtrack and audio is None: raise ValueError('Soundtrack enabled but this source has no audio.')
        identity=source_key(source,file,video if source=='Connected video' else frames)
        frames,sound,report=select_video(frames,fps,audio if use_soundtrack else None,start_seconds,duration_seconds)
        ref=descriptor('video',tag,role,associated_character,'',descriptor=settings.get('descriptor',descriptor_text).strip(),**preservation_settings(settings),data=frames,source=file if source=='Load file' else source,
                       source_range=report,duration=report['duration'],source_identity=('video',source,file,start_seconds,report['duration'],identity))
        if sound is not None:
            ref['soundtrack']=descriptor('audio',audio_tag,audio_role,audio_character,audio_instructions,audio_mode,data=sound,duration=report['duration'],source=ref['source'],source_identity=ref['source_identity'])
        selected=InputImpl.VideoFromComponents(Types.VideoComponents(images=frames,audio=sound,frame_rate=Fraction(24)))
        return output(ref,(selected,frames,sound,24.0),f'@{ref["tag"]}: {report}')


def output(ref,media,report):
    def public(r):
        return {k:v for k,v in r.items() if k not in ('data','soundtrack','source_identity')}
    info=public(ref)
    if ref['kind']=='image': info['batch_count']=len(ref['data'])
    if ref.get('soundtrack'): info['soundtrack']=public(ref['soundtrack'])
    from comfy_api.latest import ui
    if ref['kind']=='image': previews=ui.PreviewImage(media[0]).as_dict()['images']
    elif ref['kind']=='audio': previews=ui.PreviewAudio(media[0]).as_dict()['audio']
    else:
        import uuid
        import torch.nn.functional as F
        frames=ref['data'];h,w=frames.shape[1:3];scale=min(1,640/max(h,w))
        ph=max(2,2*int(h*scale/2));pw=max(2,2*int(w*scale/2))
        small=F.interpolate(frames.movedim(-1,1),size=(ph,pw),mode='bilinear',align_corners=False).movedim(1,-1)
        video=InputImpl.VideoFromComponents(Types.VideoComponents(images=small,audio=ref.get('soundtrack',{}).get('data'),frame_rate=Fraction(24)))
        filename='H3RC_preview_'+uuid.uuid4().hex+'.mp4'
        path=Path(folder_paths.get_temp_directory())/filename;path.parent.mkdir(parents=True,exist_ok=True)
        video.save_to(str(path),crf=28,preset='ultrafast')
        previews=[dict(filename=filename,subfolder='',type='temp')]
    return {'result':(ref,*media,report),'ui':{'text':[report],'h3rc_descriptor':[info],'h3rc_preview':previews}}
