"""Standalone RGB finishing operations. No external node-pack imports."""
import io
import random
import numpy as np
import torch
from PIL import Image
from .assets import resolve


def jpeg(a, quality):
    stream=io.BytesIO()
    Image.fromarray(a).save(stream,format='JPEG',quality=int(quality),optimize=False)
    stream.seek(0)
    with Image.open(stream) as image: return np.array(image.convert('RGB'))


def u8(a): return np.clip(a,0,255).astype(np.uint8)


def whitepoint(t):
    """Kang et al. (2002) Planckian-locus CCT approximation, XYZ with Y=1."""
    if t<=4000: x=-.2661239e9/t**3-.2343580e6/t**2+.8776956e3/t+.179910
    else: x=-3.0258469e9/t**3+2.1070379e6/t**2+.2226347e3/t+.240390
    if t<=2222: y=-1.1063814*x**3-1.34811020*x*x+2.18555832*x-.20219683
    elif t<=4000: y=-.9549476*x**3-1.37418593*x*x+2.09137015*x-.16748867
    else: y=3.0817580*x**3-5.87338670*x*x+3.75112997*x-.37001483
    return np.array([x/y,1,(1-x-y)/y])


def kelvin(rgb, temperature):
    if temperature==6500: return rgb.copy()
    # Bradford adaptation from the source CCT to a neutral 6500 K baseline.
    bradford=np.array([[.8951,.2664,-.1614],[-.7502,1.7135,.0367],[.0389,-.0685,1.0296]])
    to_xyz=np.array([[.4124564,.3575761,.1804375],[.2126729,.7151522,.0721750],[.0193339,.1191920,.9503041]])
    adapt=np.linalg.inv(bradford)@np.diag((bradford@whitepoint(6500))/(bradford@whitepoint(temperature)))@bradford
    matrix=np.linalg.inv(to_xyz)@adapt@to_xyz
    linear=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
    out=np.clip(linear@matrix.T,0,1)
    return np.clip(np.where(out<=.0031308,12.92*out,1.055*out**(1/2.4)-.055),0,1).astype(np.float32)


def balance(rgb,s):
    # Tonal-zone behavior of Image-Effects Color Balance (Apache-2.0).
    lum=rgb@np.array([.299,.587,.114],dtype=np.float32)
    mode=s['adjust_type']
    mask=np.where(lum<.33,1-lum/.33,0) if mode=='shadows' else np.where(lum>.67,(lum-.67)/.33,0) if mode=='highlights' else np.where((lum>=.33)&(lum<=.67),1-np.abs(lum-.5)/.17,0)
    cr,mg,yb=(s[k]/100 for k in ('cyan_red','magenta_green','yellow_blue'))
    out=rgb+mask[...,None]*np.array([cr+mg*.5+yb*.5,-cr*.5-mg+yb*.5,-cr*.5+mg*.5-yb],dtype=np.float32)
    if s['preserve_luminosity']:
        new=out@np.array([.299,.587,.114],dtype=np.float32)
        ratio=np.ones_like(new);np.divide(lum,new,out=ratio,where=new>.001)
        out*=ratio[...,None]
    return np.clip(out,0,1)


def lens(rgb,s):
    # Allor radial optic-axis construction (MIT), with a finite center and
    # exact rectangular output sizes, including odd dimension differences.
    import cv2
    h,w=rgb.shape[:2];mh,mw=(max(h,w),)*2 if s['lens_edge']=='symmetric' else (h,w)
    xx,yy=np.meshgrid(np.linspace(0,1,mw),np.linspace(0,1,mh))
    c=s['lens_curvy'];x=np.abs(xx-.5)**c;y=np.abs(yy-.5)**c
    d={'circle':lambda:((xx-.5)**2+(yy-.5)**2)**(c/2),'square':lambda:np.maximum(x,y),'rectangle':lambda:x+y,'corners':lambda:np.minimum(x,y)}[s['lens_shape']]()
    mask=np.clip(d/max(float(d.max()),1e-8)*(s['lens_zoom']+1),0,1+c)
    top,left=(mh-h)//2,(mw-w)//2;mask=mask[top:top+h,left:left+w].astype(np.float32)
    yy,xx=np.mgrid[:h,:w].astype(np.float32);dx=xx-w//2;dy=yy-h//2
    distance=np.maximum(np.hypot(dx,dy),1e-8)
    mx=(xx-mask*dx/distance*s['lens_aperture']*100).astype(np.float32)
    my=(yy-mask*dy/distance*s['lens_aperture']*100).astype(np.float32)
    shifted=cv2.remap(rgb,mx,my,cv2.INTER_LINEAR)
    k=s['blur_intensity']-1
    if k<=1: return shifted
    blurred=cv2.stackBlur(shifted,(k,k));mask=np.clip(mask,0,1)[...,None]
    return shifted*(1-mask)+blurred*mask


def camera(a,s,seed):
    import cv2
    from scipy.ndimage import convolve
    h,w=a.shape[:2]
    if s['bayer_demosaic'] and min(h,w)>=3:
        bgr=a[...,::-1];m=np.zeros((h,w),np.uint8)
        m[::2,::2]=bgr[::2,::2,0];m[::2,1::2]=bgr[::2,1::2,1]
        m[1::2,::2]=bgr[1::2,::2,1];m[1::2,1::2]=bgr[1::2,1::2,2]
        a=cv2.demosaicing(m,cv2.COLOR_BAYER_RG2BGR)[...,::-1].copy()
    if s['chroma_aberr_strength']>0:
        rng=np.random.default_rng(seed);r,b=rng.normal(0,s['chroma_aberr_strength']*.6,2)
        ry=rng.normal(scale=.3*abs(r));by=rng.normal(scale=.3*abs(b))
        out=a.astype(np.float32)
        for channel,tx,ty in ((0,r,ry),(2,-b,by)):
            out[...,channel]=cv2.warpAffine(out[...,channel],np.float32([[1,0,tx],[0,1,ty]]),(w,h),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
        a=u8(out)
    yy,xx=np.meshgrid(np.linspace(-1,1,h),np.linspace(-1,1,w),indexing='ij')
    radius=np.sqrt(xx*xx+yy*yy)
    a=u8(a.astype(np.float32)*np.clip(1-radius**2*s['vignette_strength'],0,1)[...,None])
    rng=np.random.default_rng(seed);out=a.astype(np.float32)
    if s['iso_noise_scale']>0: out=rng.poisson(np.clip(out*s['iso_noise_scale']*4,0,1e6)).astype(np.float32)/4
    if s['sensor_read_noise']>0: out+=rng.normal(0,s['sensor_read_noise'],out.shape)
    a=u8(out);rng=np.random.default_rng(seed);out=a.astype(np.float32)
    n=int(h*w*s['hot_pixel_prob'])
    if n:
        ys=rng.integers(0,h,n);xs=rng.integers(0,w,n);values=rng.integers(200,256,n)
        for y,x,v in zip(ys,xs,values):out[y,x,:]=v
    if s['banding_strength']>0:out+=(np.sin(np.arange(h)*.5)*255*s['banding_strength'])[:,None,None]
    a=u8(out);k=s['motion_blur_kernel'];k+=1 if k%2==0 else 0
    if k>1:
        kernel=np.zeros((k,k),np.float32);kernel[k//2,:]=1/k
        a=np.stack([u8(convolve(a[...,c].astype(np.float32),kernel,mode='mirror')) for c in range(3)],axis=-1)
    return jpeg(a,s['initial_jpeg_quality'])


def lut(rgb,s):
    from colour.io import read_LUT_IridasCube
    table=read_LUT_IridasCube(str(resolve(s['lut'],'luts')))
    domain=np.array(table.domain);lo,hi=domain[0],domain[1]
    table.table=np.clip(table.table,lo,hi)
    a=rgb*(hi-lo)+lo
    if s['color_space']=='log':a=np.maximum(a,0)**(1/2.2)
    a=table.apply(a)
    if s['color_space']=='log':a=np.maximum(a,0)**2.2
    a=(a-lo)/(hi-lo)
    strength=s['lut_strength']/100
    return u8((rgb*(1-strength)+a*strength)*255).astype(np.float32)/255


def neural(rgb,s,seed):
    from .vendor.grainnet import GrainNet
    import comfy.model_management as mm
    model=GrainNet(block_nb=2,activation='tanh')
    model.load_state_dict(torch.load(resolve('internal:neural_grain/grainnet.pt','neural_grain'),map_location='cpu',weights_only=True))
    device=mm.get_torch_device();model.eval().to(device)
    try:
        image=torch.from_numpy(rgb.copy()).permute(2,0,1)[None].to(device)
        gray=(image*image.new_tensor([.299,.587,.114])[None,:,None,None]).sum(1,keepdim=True)
        # fork_rng restores caller RNG state; GrainNet creates its noise on CPU.
        with torch.inference_mode(),torch.random.fork_rng(devices=[]):
            torch.random.default_generator.manual_seed(seed)
            noisy=model(gray,torch.tensor([[s['grain_size']]],device=device))
            result=(image+s['strength']*(noisy-gray)).clamp(0,1)
        return result[0].permute(1,2,0).cpu().numpy()
    finally: model.to('cpu')


def process(image,name,s):
    from .processing import cancelled
    from .progress import report
    results=[]
    perturb_rng=np.random.default_rng(s.get('seed',0))
    for index,frame in enumerate(image):
        cancelled();report(f'{index+1}/{len(image)} image(s)')
        original=frame.cpu().numpy();rgb=original[...,:3].astype(np.float32)
        a=u8(rgb*255);seed=s.get('seed',0)+index
        if name=='rgb':out=u8(a.astype(np.float32)+[s['R'],s['G'],s['B']])/255
        elif name=='gamma':out=np.round((a/255.)**s['gamma']*255).astype(np.uint8)/255
        elif name=='color_balance':out=balance(rgb,s)
        elif name=='temperature':out=kelvin(rgb,s['kelvin'])
        elif name=='lens':out=lens(rgb,s)
        elif name=='pixel_perturb':out=rgb if s['magnitude']==0 else u8(a.astype(np.float32)+perturb_rng.uniform(-s['magnitude']*255,s['magnitude']*255,a.shape))/255
        elif name=='neural_grain':out=rgb if s['strength']==0 else neural(rgb,s,seed)
        elif name=='lut':out=rgb if s['lut_strength']==0 else lut(a.astype(np.float32)/255,s)
        elif name=='camera':out=camera(a,s,seed)/255
        elif name=='compression':
            rng=random.Random(seed)
            for _ in range(s['cycles']):
                cancelled();a=jpeg(a,rng.randint(min(s['min_quality'],s['max_quality']),max(s['min_quality'],s['max_quality'])))
            out=a/255
        else:raise ValueError(f'Unknown processor {name}')
        out=np.clip(out,0,1).astype(np.float32)
        if original.shape[-1]==4:out=np.concatenate((out,original[...,3:4]),axis=-1)
        results.append(torch.from_numpy(out.copy()))
    return torch.stack(results)
