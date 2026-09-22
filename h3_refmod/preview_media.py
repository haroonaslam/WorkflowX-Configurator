"""Small, portable, silent source overviews; never used as conditioning inputs."""
import shutil
import subprocess
import torch
import torch.nn.functional as F


def video_overview(frames,destination):
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg: return False
    count=min(48,len(frames))
    selected=frames[torch.linspace(0,len(frames)-1,count).round().long()]
    h,w=selected.shape[1:3];scale=min(1,384/max(h,w));size=(max(2,int(h*scale)//2*2),max(2,int(w*scale)//2*2))
    selected=F.interpolate(selected.permute(0,3,1,2).float(),size=size,mode='bilinear',align_corners=False)
    pixels=(selected.permute(0,2,3,1).clamp(0,1)*255).byte().cpu().contiguous().numpy().tobytes()
    command=[ffmpeg,'-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{size[1]}x{size[0]}','-r','6','-i','-',
             '-an','-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(destination)]
    try:
        subprocess.run(command,input=pixels,capture_output=True,check=True,timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except (OSError,subprocess.SubprocessError):
        if destination.exists(): destination.unlink()
        return False
    return True
