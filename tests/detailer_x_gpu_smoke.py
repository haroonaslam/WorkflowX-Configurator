"""Opt-in GPU checks; imports ComfyUI core without loading custom node packs.

python tests/detailer_x_gpu_smoke.py [--sampling-checkpoint /path/model.safetensors]
"""
import argparse
import copy
import json
import sys
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument("--sampling-checkpoint",type=Path)
parser.add_argument("--compare-reference",action="store_true",help="Optional comparison against locally installed Impact Pack")
parser.add_argument("--preset",default="qwen21",help="Built-in preset for the optional sampling checkpoint")
parser.add_argument("--rgba-vae",type=Path,help="Optional real RGBA VAE encode/decode regression")
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root.parents[1]),str(root)]
sys.argv=[sys.argv[0],"--disable-xformers"]
import torch
from skimage import data
from detailer_x import processing as p
from detailer_x.config import DEFAULTS, BUILTINS

def check(name,image,expected):
    assert tuple(image.shape)==expected,(name,image.shape,expected)
    assert torch.isfinite(image).all(),name
    print(json.dumps({"stage":name,"shape":list(image.shape),"finite":True}),flush=True)

image=torch.from_numpy(data.astronaut().copy()).float()[None]/255
with torch.inference_mode():
    out=p.upscale(image,DEFAULTS["upscaler"])
    check("upscale",out,(1,768,768,3))
    regions=p.detections(image[0],DEFAULTS["face"])
    assert len(regions)>0,"No face found in smoke-test portrait"
    mask=p.sam_masks(image[0],regions,DEFAULTS["face"],DEFAULTS["sam"])
    assert mask.shape==(512,512) and mask.max()>0
    print(json.dumps({"stage":"detector+SAM","detections":len(regions),"mask_pixels":int(mask.sum())}),flush=True)
    for mode,size in [("1x (DLAA / native)",512),("1.5x (Quality)",768)]:
        settings=dict(DEFAULTS["dlss5"],upscaling_mode=mode)
        if size>512: settings["model_preset"]="J"
        result=p.dlss(image,settings)
        check("DLSS5 "+mode,result,(1,size,size,3))
    if args.sampling_checkpoint:
        import nodes
        import comfy.sd
        model,clip,vae=comfy.sd.load_checkpoint_guess_config(str(args.sampling_checkpoint),output_vae=True,output_clip=True)[:3]
        positive=nodes.CLIPTextEncode().encode(clip,"photograph of an astronaut, natural skin detail")[0]
        negative=nodes.CLIPTextEncode().encode(clip,"blur, artifacts")[0]
        settings=dict(DEFAULTS["face"],**BUILTINS[args.preset]["values"]["face"])
        settings.update(guide_size=512,max_size=512)
        output=p.detail(image,settings,DEFAULTS["sam"],model,clip,vae,positive,negative)
        check("diffusion face detail",output,(1,512,512,3))
        assert not torch.equal(image,output),"Detailing made no change"
        if args.compare_reference:
            import inspect
            import types
            sys.path.insert(0,str(root.parent/"ComfyUI-Impact-Pack/modules"))
            package=types.ModuleType("detailerx_reference_subpack")
            package.__path__=[str(root.parent/"ComfyUI-Impact-Subpack/modules")]
            sys.modules[package.__name__]=package
            from detailerx_reference_subpack.subpack_nodes import UltralyticsDetectorProvider
            from server import PromptServer
            from aiohttp import web
            PromptServer.instance=types.SimpleNamespace(routes=web.RouteTableDef(),send_sync=lambda *a,**k:None,add_on_prompt_handler=lambda *a:None)
            import impact.impact_server
            from impact.impact_pack import FaceDetailer,SAMLoader
            detector=UltralyticsDetectorProvider().doit("bbox/face_yolov8m.pt")[0]
            sam=SAMLoader().load_model("sam_vit_b_01ec64.pth","Prefer GPU")[0]
            values=dict(settings,image=image,model=model,clip=clip,vae=vae,positive=positive,negative=negative,
                bbox_detector=detector,sam_model_opt=sam,wildcard=settings["prompt"])
            values={k:v for k,v in values.items() if k in inspect.signature(FaceDetailer.doit).parameters}
            reference=FaceDetailer().doit(**values)[0]
            error=(output-reference).abs()
            print(json.dumps({"stage":"Impact comparison","mean_absolute_error":float(error.mean()),"max_absolute_error":float(error.max())}),flush=True)
            assert error.mean()<.025,"Detailer output diverges materially from reference"
            sam.to("cpu")
            del sam,detector,values
        import comfy.model_management as mm
        mm.unload_all_models()
        del model,clip,vae
        import gc
        gc.collect()
    if args.rgba_vae:
        import comfy.sd
        import comfy.utils
        vae=comfy.sd.VAE(sd=comfy.utils.load_torch_file(str(args.rgba_vae)))
        for channels in (3,4):
            source=p.resize(image,128,128)
            if channels==4:source=torch.cat((source,torch.full_like(source[...,:1],.6)),-1)
            latent=vae.encode(source[...,:3])
            decoded=vae.decode(latent)
            assert decoded.shape[-1]==4,decoded.shape
            result=p.with_alpha(source,p.decoded_rgb(decoded).cpu())
            check("RGBA VAE normalization "+str(channels),result,(1,128,128,channels))
            if channels==4:assert torch.equal(source[...,3],result[...,3])
        import comfy.model_management as mm
        mm.unload_all_models()
        del vae
        import gc
        gc.collect()
print("DetailerX GPU smoke checks passed",flush=True)
