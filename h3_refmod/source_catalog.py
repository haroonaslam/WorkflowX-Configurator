"""Local directory media previews. Only explicitly listed sources receive preview handles."""
import hashlib
import json
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, ImageOps

KINDS={'image':{'.png','.jpg','.jpeg','.webp','.bmp'},'video':{'.mp4','.mov','.webm','.mkv','.avi'},'audio':{'.wav','.mp3','.flac','.ogg','.m4a','.aac'}}
HANDLES={}
CACHE=Path(tempfile.gettempdir())/'h3rc-source-previews'

def run(command):
    return subprocess.run(command,check=True,capture_output=True,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

def describe_folder(folder):
    root=Path(folder).expanduser().resolve()
    if not root.is_dir(): raise ValueError('Source directory not found.')
    entries=[]
    for p in sorted(root.iterdir(),key=lambda p:p.name.casefold()):
        kind=next((k for k,exts in KINDS.items() if p.suffix.lower() in exts),None)
        if not kind or not p.is_file(): continue
        p=p.resolve();token=secrets.token_urlsafe(24);HANDLES[token]=p
        entry=dict(source=p.name,kind=kind,handle=token)
        if kind=='image':
            try:
                with Image.open(p) as image:
                    entry['dimensions']=list(ImageOps.exif_transpose(image).size)
            except OSError as e:
                entry['preview_error']='Could not inspect this picture. '+str(e)
        if kind!='image':
            try:
                probe=shutil.which('ffprobe')
                if not probe: raise ValueError('FFprobe is needed for recording previews.')
                d=json.loads(run([probe,'-v','error','-show_streams','-show_format','-of','json',str(p)]).stdout)
                stream=next(s for s in d['streams'] if s['codec_type']==kind)
                entry['media_duration']=float(stream.get('duration') if stream.get('duration') not in (None,'N/A') else d.get('format',{}).get('duration',0))
                if kind=='video':
                    n,den=stream.get('avg_frame_rate','0/1').split('/');fps=float(n)/float(den)
                    entry.update(fps=fps,frame_count=int(stream['nb_frames']) if str(stream.get('nb_frames','')).isdigit() else round(entry['media_duration']*fps),dimensions=[int(stream['width']),int(stream['height'])])
            except (ValueError,KeyError,StopIteration,subprocess.SubprocessError) as e:
                entry['preview_error']='Could not inspect this recording. '+str(e)
        entries.append(entry)
    # Bound process-local handles, keeping the latest opened directories available.
    while len(HANDLES)>10000: HANDLES.pop(next(iter(HANDLES)))
    return sorted(entries,key=lambda e:({'image':0,'video':1,'audio':2}[e['kind']],e['source'].casefold()))

def media_path(handle,thumbnail=False,frame=0,playable=False):
    p=HANDLES.get(handle)
    if p is None or not p.is_file(): raise ValueError('Preview expired or file moved. Reopen Edit source media.')
    if not thumbnail and not playable: return p
    kind=next(k for k,exts in KINDS.items() if p.suffix.lower() in exts)
    if kind=='image' and not thumbnail: return p
    if kind=='video' and playable and p.suffix.lower() in ('.mp4','.webm'): return p
    if kind=='audio' and playable and p.suffix.lower() in ('.wav','.mp3','.ogg'): return p
    st=p.stat();key=hashlib.sha256(f'{p}:{st.st_size}:{st.st_mtime_ns}:{frame}:{thumbnail}'.encode()).hexdigest()
    CACHE.mkdir(exist_ok=True);target=CACHE/(key+('.jpg' if thumbnail else '.mp4' if kind=='video' else '.wav'))
    if target.exists(): return target
    stage=target.with_name(target.stem+'.'+secrets.token_hex(4)+target.suffix)
    try:
        if kind=='image':
            with Image.open(p) as image:
                image=ImageOps.exif_transpose(image).convert('RGB');image.thumbnail((480,320));image.save(stage)
        else:
            ffmpeg=shutil.which('ffmpeg')
            if not ffmpeg: raise ValueError('FFmpeg is needed for this preview.')
            cmd=[ffmpeg,'-v','error','-nostdin','-y','-threads','1','-filter_threads','1','-i',str(p)]
            if thumbnail: cmd+=['-vf',f'select=eq(n\\,{max(0,int(frame))}),scale=320:-2','-frames:v','1']
            elif kind=='video': cmd+=['-vf','scale=640:-2','-c:v','libx264','-preset','ultrafast','-crf','28','-c:a','aac','-movflags','+faststart']
            else: cmd+=['-vn','-c:a','pcm_s16le']
            run(cmd+[str(stage)])
        if not stage.exists(): raise ValueError('No preview frame at this position.')
        stage.replace(target)
    finally:
        if stage.exists(): stage.unlink()
    return target
