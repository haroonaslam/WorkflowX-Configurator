"""Creation-only profile processing. Saved encodings are never resized at runtime."""
import json
import math
import torch
import torch.nn.functional as F
from .resampling import lanczos
from .optimization import visual_cost

DOWNSIZE=['Lanczos','Bicubic','Area','Nearest exact']
SMALL=['Keep size','Pad to target','Enlarge with Lanczos','Enlarge with Nearest exact','Enlarge with an upscale model']
GROUPS=('picture','video','combined')

def defaults():
    return {g:[dict(id='1024',name='1024 short edge',size=1024,enabled=True,downsize='Lanczos',smaller='Pad to target' if g=='combined' else 'Keep size',model='',framing='Fit whole image',budget=0)] for g in GROUPS}

def parse(value):
    config=json.loads(value) if isinstance(value,str) else value
    if not isinstance(config,dict) or set(config)!=set(GROUPS):raise ValueError('Configure Picture, Video and Combined video profiles.')
    result={}
    for group in GROUPS:
        result[group]=[];seen=set()
        for raw in config[group]:
            p=dict(raw)
            if not p.get('enabled',True):continue
            if not isinstance(p.get('id'),str) or not p['id'] or p['id'] in seen:raise ValueError('Profile identifiers must be unique within each list.')
            seen.add(p['id']);p['name']=str(p.get('name','')).strip()
            if not p['name']:raise ValueError('Give each enabled profile a name.')
            for key,default in [('size',1024),('budget',0)]:
                p.setdefault(key,default)
                if isinstance(p[key],bool) or not isinstance(p[key],int) or p[key]<0:raise ValueError('Profile sizes and token limits must be nonnegative whole numbers.')
            if p['size'] and not 32<=p['size']<=32768:raise ValueError('Shorter side must be 32–32768 pixels, or Original size.')
            p.setdefault('downsize','Lanczos');p.setdefault('smaller','Keep size');p.setdefault('framing','Fit whole image');p.setdefault('model','')
            if p['downsize'] not in DOWNSIZE or p['smaller'] not in SMALL or p['framing'] not in ('Fit whole image','Crop to fill'):raise ValueError('Invalid profile resizing settings.')
            if p['smaller']==SMALL[-1]:
                import folder_paths
                if p['model'] not in folder_paths.get_filename_list('upscale_models'):raise ValueError(f'{p["name"]}: choose an installed upscale model.')
            result[group].append(p)
    return result

def aligned(size):return tuple(max(32,math.ceil(n/32)*32) for n in size)

def canvas_for(frames,p,combined=False):
    h,w=frames.shape[1:3];scale=p['size']/min(w,h) if p['size'] else 1
    if scale>1 and p['smaller']=='Keep size' and not combined:scale=1
    return aligned((max(1,round(w*scale)),max(1,round(h*scale))))

def resample(frames,width,height,method):
    if frames.shape[1:3]==(height,width):return frames
    if method=='Lanczos':return lanczos(frames,width,height)
    mode={'Bicubic':'bicubic','Area':'area','Nearest exact':'nearest-exact'}[method]
    options=dict(align_corners=False,antialias=True) if mode=='bicubic' else {}
    return F.interpolate(frames.movedim(-1,1).float(),size=(height,width),mode=mode,**options).movedim(1,-1).clamp(0,1)

def prepare(frames,p,canvas=None,models=None):
    """Resize original pixels once (apart from a model's fixed-factor finish), then crop/pad."""
    h,w=frames.shape[1:3];combined=canvas is not None;cw,ch=canvas or canvas_for(frames,p)
    scale=(max if combined and p['framing']=='Crop to fill' else min)(cw/w,ch/h)
    if not combined and p['size']:scale=min(scale,p['size']/min(w,h))
    if not combined and not p['size']:scale=1
    if scale>1 and p['smaller'] in SMALL[:2]:scale=1
    rw,rh=max(1,round(w*scale)),max(1,round(h*scale));method=p['downsize']
    if scale>1:
        method='Nearest exact' if p['smaller']==SMALL[3] else 'Lanczos'
        if p['smaller']==SMALL[-1]:
            from comfy_extras.nodes_upscale_model import UpscaleModelLoader,ImageUpscaleWithModel
            models={} if models is None else models
            if p['model'] not in models:models[p['model']]=UpscaleModelLoader.execute(p['model'])[0]
            frames=ImageUpscaleWithModel.execute(models[p['model']],frames)[0]
    frames=resample(frames,rw,rh,method)
    x,y=max(0,(rw-cw)//2),max(0,(rh-ch)//2);frames=frames[:,y:y+min(rh,ch),x:x+min(rw,cw),:3]
    dh,dw=ch-frames.shape[1],cw-frames.shape[2]
    return F.pad(frames.movedim(-1,1),(dw//2,dw-dw//2,dh//2,dh-dh//2)).movedim(1,-1) if dh or dw else frames

def tensor(entry):
    if 'latent' in entry:return entry['latent']
    from .generation import load_mod
    return load_mod(entry['path']).latent

def fit(entries,budget=0):
    """Return selected indices only. Picture values and all spatial dimensions are untouched."""
    from .vendor.py.refmod_core import dedup_frame_indices
    result=[dict(e,indices=list(e.get('indices',range(e['shape'][2])))) for e in entries]
    def cost(e):return len(e['indices'])*(e['shape'][3]//2)*(e['shape'][4]//2)
    if not isinstance(budget,int) or isinstance(budget,bool) or budget<0:raise ValueError('Reference-token budget must be a nonnegative whole number.')
    if not budget or sum(map(cost,result))<=budget:return result
    pictures=sum(cost(e) for e in result if e['kind']=='image')
    if pictures>budget:raise ValueError(f'Selected pictures need {pictures:,} tokens, exceeding the {budget:,} allowance. Increase the budget, choose a smaller saved profile, or deselect pictures. No pictures were dropped.')
    for e in result:
        if e['kind']=='video':
            z=tensor(e)[:,:,e['indices']];kept=dedup_frame_indices(z,0.02);e['indices']=[e['indices'][i] for i in kept]
    if sum(map(cost,result))>budget:
        candidates=[(i,j,(e['shape'][3]//2)*(e['shape'][4]//2)) for i,e in enumerate(result) if e['kind']=='video' for j in e['indices']]
        allowance=budget-pictures
        n=min(len(candidates),allowance//min((x[2] for x in candidates),default=1))
        while n:
            picks=torch.linspace(0,len(candidates)-1,n).round().long().tolist()
            if sum(candidates[k][2] for k in picks)<=allowance:break
            n-=1
        chosen=[candidates[k] for k in picks] if n else []
        for i,e in enumerate(result):
            if e['kind']=='video':e['indices']=[j for ri,j,_ in chosen if ri==i]
    if not any(e['indices'] for e in result):raise ValueError('The budget cannot fit one saved video sample. Choose a smaller profile or increase the budget.')
    return result
