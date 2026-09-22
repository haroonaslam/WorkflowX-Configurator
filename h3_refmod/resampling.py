"""Float32 Lanczos in image space; no 8-bit intermediates."""
import numpy as np
import torch
from PIL import Image

def lanczos(frames, width, height):
    if tuple(frames.shape[1:3]) == (height,width): return frames
    result=[]
    for frame in frames:
        data=frame.detach().float().cpu().numpy()
        channels=[np.asarray(Image.fromarray(data[:,:,c]).resize((width,height),Image.Resampling.LANCZOS),dtype=np.float32).copy() for c in range(data.shape[-1])]
        result.append(torch.from_numpy(np.stack(channels,axis=-1)))
    return torch.stack(result).to(frames.device).clamp_(0,1)

def geometry(source, canvas, bounds=None, framing='Fit whole image', allow_upscale=False):
    w,h=source;cw,ch=canvas;bw,bh=bounds or source
    ratio=(max if framing=='Crop to fill' else min)(cw/w,ch/h)
    ratio=min(ratio,bw/w,bh/h) if bounds else ratio
    if not allow_upscale: ratio=min(1.0,ratio)
    rw,rh=max(1,round(w*ratio)),max(1,round(h*ratio))
    return rw,rh

def resize(frames, canvas, framing='Fit whole image', allow_upscale=False, content=None, bounds=None):
    if framing not in ('Fit whole image','Crop to fill'): raise ValueError('Choose Fit whole image or Crop to fill.')
    width,height=canvas
    rw,rh=content or geometry((frames.shape[2],frames.shape[1]),canvas,bounds,framing,allow_upscale)
    frames=lanczos(frames[...,:3],rw,rh)
    # Crop centrally, then pad centrally. Both operations remain in pixel space.
    x,y=max(0,(rw-width)//2),max(0,(rh-height)//2)
    frames=frames[:,y:y+min(rh,height),x:x+min(rw,width)]
    dh,dw=height-frames.shape[1],width-frames.shape[2]
    if dh or dw:
        frames=torch.nn.functional.pad(frames.movedim(-1,1),(dw//2,dw-dw//2,dh//2,dh-dh//2)).movedim(1,-1)
    return frames
