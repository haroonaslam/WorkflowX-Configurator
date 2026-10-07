"""Shared SAM1, SAM2.1 and native ComfyUI SAM3.1 adapters."""
from __future__ import annotations

import logging
from collections import OrderedDict
from pathlib import Path

import numpy as np
import torch

from .assets import resolve

log=logging.getLogger("WorkflowX.DetailerX.SAM")
_CACHE=OrderedDict()
_CACHE_LIMIT=2


def _offload(candidate):
    """Offload torch modules and Comfy ModelPatchers without confusing core state."""
    try:
        import comfy.model_management as mm
        patcher=candidate if hasattr(candidate,"clone_base_uuid") else getattr(candidate,"patcher",None)
        if patcher is not None and hasattr(patcher,"clone_base_uuid"):
            mm.unload_model_and_clones(patcher,unload_additional_models=False)
            return
    except Exception:pass
    try:
        if hasattr(candidate,"to"):candidate.to("cpu")
        elif hasattr(getattr(candidate,"model",None),"to"):candidate.model.to("cpu")
    except Exception:pass


def _cached(key):
    value=_CACHE.get(key)
    if value is not None:_CACHE.move_to_end(key)
    return value


def _remember(key,value,keep=True):
    if not keep:return value
    _CACHE[key]=value;_CACHE.move_to_end(key)
    while len(_CACHE)>_CACHE_LIMIT:
        _,evicted=_CACHE.popitem(last=False)
        for candidate in evicted if isinstance(evicted,tuple) else (evicted,):
            _offload(candidate)
    return value


def _eager_sam2_transforms(base):
    """Build SAM2 preprocessing without torchvision's TorchScript path."""
    import torch.nn as nn
    import torch.nn.functional as functional

    class DetailerXEagerSAM2Transforms(base):
        def __init__(self,resolution,mask_threshold,max_hole_area=0.0,max_sprinkle_area=0.0):
            nn.Module.__init__(self)
            self.resolution=resolution
            self.mask_threshold=mask_threshold
            self.max_hole_area=max_hole_area
            self.max_sprinkle_area=max_sprinkle_area
            self.mean=[0.485,0.456,0.406]
            self.std=[0.229,0.224,0.225]

        def _tensor(self,image):
            from PIL import Image
            array=np.asarray(image) if isinstance(image,Image.Image) else image
            value=torch.as_tensor(np.asarray(array))
            if value.ndim!=3 or value.shape[-1]!=3:
                raise ValueError(f"SAM2 expects an RGB HWC image, received shape {tuple(value.shape)}")
            value=value.permute(2,0,1).contiguous()
            value=value.float().div(255) if value.dtype==torch.uint8 else value.float()
            value=functional.interpolate(value[None],size=(self.resolution,self.resolution),mode="bilinear",align_corners=False,antialias=True)[0]
            mean=value.new_tensor(self.mean)[:,None,None]
            std=value.new_tensor(self.std)[:,None,None]
            return (value-mean)/std

        def __call__(self,image):return self._tensor(image)
        def forward_batch(self,img_list):return torch.stack([self._tensor(image) for image in img_list],dim=0)

    return DetailerXEagerSAM2Transforms


def _make_sam2_predictor(predictor_class,transform_class,model):
    """Construct a DetailerX predictor without mutating the global SAM2 package."""
    class DetailerXSAM2Predictor(predictor_class):
        def __init__(self,sam_model,mask_threshold=0.0,max_hole_area=0.0,max_sprinkle_area=0.0):
            self.model=sam_model
            self._transforms=transform_class(
                resolution=self.model.image_size,mask_threshold=mask_threshold,
                max_hole_area=max_hole_area,max_sprinkle_area=max_sprinkle_area)
            self._is_image_set=False
            self._features=None
            self._orig_hw=None
            self._is_batch=False
            self.mask_threshold=mask_threshold
            self._bb_feat_sizes=[(256,256),(128,128),(64,64)]
    return DetailerXSAM2Predictor(model)


def _device(shared):
    import comfy.model_management as mm
    return torch.device("cpu") if shared.get("device")=="CPU" else mm.get_torch_device()


def _load_spatial(shared):
    backend=shared.get("backend","sam1")
    path=resolve(shared["model"],"sams")
    key=(backend,str(path),path.stat().st_size,path.stat().st_mtime_ns,str(_device(shared)))
    cached=_cached(key)
    if cached is not None:return cached
    if backend=="sam1":
        from segment_anything import sam_model_registry, SamPredictor
        stem=path.name.lower();kind="vit_h" if "vit_h" in stem else "vit_l" if "vit_l" in stem else "vit_b"
        model=sam_model_registry[kind](checkpoint=str(path)).to("cpu")
        result=(SamPredictor(model),model)
    elif backend=="sam2.1":
        try:
            import sys
            vendor=str(Path(__file__).parent/"vendor")
            if vendor not in sys.path: sys.path.insert(0,vendor)
            from sam2.build_sam import build_sam2
            from sam2.sam2_image_predictor import SAM2ImagePredictor
            from sam2.utils.transforms import SAM2Transforms
        except ImportError as exc:
            raise RuntimeError("SAM2.1 support is unavailable. Install WorkflowX requirements or rerun its installer.") from exc
        size=next((v for token,v in (("tiny","sam2.1_hiera_t.yaml"),("small","sam2.1_hiera_s.yaml"),("base","sam2.1_hiera_b+.yaml"),("large","sam2.1_hiera_l.yaml")) if token in path.name.lower()),"sam2.1_hiera_l.yaml")
        model=build_sam2(f"configs/sam2.1/{size}",str(path),device="cpu",apply_postprocessing=False)
        transforms=_eager_sam2_transforms(SAM2Transforms)
        result=(_make_sam2_predictor(SAM2ImagePredictor,transforms,model),model)
    else: raise ValueError(f"Unsupported spatial SAM backend: {backend}")
    return _remember(key,result,shared.get("keep_model_loaded",True))


def spatial_masks(image, regions, settings, shared):
    predictor,model=_load_spatial(shared)
    model.to(_device(shared))
    rgb=np.clip(image.detach().cpu().numpy()*255,0,255).astype(np.uint8)
    predictor.set_image(rgb)
    results=[]
    try:
        for bbox,_,coarse in regions:
            box=np.asarray(bbox,dtype=np.float32)
            if shared.get("backend","sam1")=="sam1":
                masks,scores,_=predictor.predict(box=box,multimask_output=True)
            else:
                masks,scores,_=predictor.predict(box=box[None],multimask_output=True)
                masks=np.asarray(masks).reshape((-1,*coarse.shape));scores=np.asarray(scores).reshape(-1)
            selected=masks[scores>=settings["sam_threshold"]]
            mask=(selected.max(axis=0) if len(selected) else masks[int(np.argmax(scores))]).astype(np.float32)
            results.append(mask)
        return results
    finally:
        model.to("cpu")
        if not shared.get("keep_model_loaded",True):
            for key,value in list(_CACHE.items()):
                if isinstance(value,tuple) and len(value)>1 and value[0] is predictor and value[1] is model:_CACHE.pop(key,None)


def spatial_predictor(shared):
    predictor,model=_load_spatial(shared)
    model.to(_device(shared))
    return predictor,model


def _sam3_checkpoint(identifier):
    import folder_paths
    if identifier.startswith("checkpoint:"):
        name=identifier.split(":",1)[1]
        path=folder_paths.get_full_path("checkpoints",name)
        if path:return name,path
    raise FileNotFoundError(f"SAM3 checkpoint is unavailable: {identifier}")


def _sam3_load(shared):
    import comfy.sd,folder_paths
    name,path=_sam3_checkpoint(shared["model"]);key=("sam3.1",str(path),Path(path).stat().st_mtime_ns)
    cached=_cached(key)
    if cached is not None:return cached
    out=comfy.sd.load_checkpoint_guess_config(path,output_vae=False,output_clip=True,
        embedding_directory=folder_paths.get_folder_paths("embeddings"))
    if out[1] is None:raise RuntimeError("Selected SAM3 checkpoint does not contain its required text encoder")
    result=(out[0],out[1])
    return _remember(key,result,shared.get("keep_model_loaded",True))


def _encode(clip,text):
    tokens=clip.tokenize(text)
    if hasattr(clip,"encode_from_tokens_scheduled"):return clip.encode_from_tokens_scheduled(tokens)
    cond,pooled=clip.encode_from_tokens(tokens,return_pooled=True)
    return [[cond,{"pooled_output":pooled}]]


def _clamp_box(bbox,width,height):
    """Return an integer source-image box, or None for a degenerate proposal."""
    values=np.asarray(bbox,dtype=np.float64).reshape(-1)
    if values.size<4 or not np.isfinite(values[:4]).all():return None
    x1=max(0,min(width,int(np.floor(values[0]))));y1=max(0,min(height,int(np.floor(values[1]))))
    x2=max(0,min(width,int(np.ceil(values[2]))));y2=max(0,min(height,int(np.ceil(values[3]))))
    return None if x2<=x1 or y2<=y1 else (x1,y1,x2,y2)


def _crop_mask_to_full(mask,box,height,width):
    """Normalize a crop-local SAM mask and paste it into a zero full-size mask."""
    result=np.zeros((height,width),dtype=np.float32)
    if box is None:return result
    x1,y1,x2,y2=box;crop_h,crop_w=y2-y1,x2-x1
    value=np.asarray(mask,dtype=np.float32)
    if value.ndim>2:value=value.squeeze()
    if value.size==0:return result
    if value.ndim!=2:raise ValueError(f"SAM3 returned an unsupported crop mask shape: {tuple(value.shape)}")
    if value.shape!=(crop_h,crop_w):
        value=torch.nn.functional.interpolate(torch.from_numpy(value)[None,None],size=(crop_h,crop_w),mode="bilinear",align_corners=False)[0,0].numpy()
    result[y1:y2,x1:x2]=np.clip(value,0,1)
    return result


def sam3(image, regions, settings, shared):
    from nodes import NODE_CLASS_MAPPINGS
    cls=NODE_CLASS_MAPPINGS.get("SAM3_Detect")
    if cls is None:raise RuntimeError("Native SAM3_Detect is unavailable; update ComfyUI or select SAM1/SAM2.1")
    model,clip=_sam3_load(shared);mode=settings.get("sam3_mode","refine_detector")
    conditioning=None
    if mode!="refine_detector":
        concept=settings.get("mask_concept","").strip()
        if not concept:raise ValueError("SAM3 mask concept is empty")
        conditioning=_encode(clip,concept)
    def detect(boxes,visual=None):
        source=image if visual is None else visual
        kwargs=dict(model=model,image=source[None,...,:3],conditioning=conditioning,bboxes=boxes,
            threshold=settings.get("sam3_threshold",.5),refine_iterations=settings.get("sam3_refine_iterations",3),individual_masks=True)
        obj=cls();fn=getattr(obj,getattr(cls,"FUNCTION","execute"));raw=fn(**kwargs);out=getattr(raw,"result",raw)
        masks=tuple(out)[0]
        if masks.ndim==2:masks=masks[None]
        return masks.detach().float().cpu().numpy()
    try:
        if mode!="concept_only":
            aligned=[]
            for bbox,_,_ in regions:
                if mode=="bbox_controlled":
                    h,w=image.shape[:2];clamped=_clamp_box(bbox,w,h)
                    if clamped is None:
                        aligned.append(np.zeros((h,w),np.float32));continue
                    x1,y1,x2,y2=clamped;crop=image[y1:y2,x1:x2]
                    local={"x":0.0,"y":0.0,"width":float(x2-x1),"height":float(y2-y1)}
                    masks=detect([local],crop)
                    combined=np.max(masks,axis=0).astype(np.float32) if len(masks) else np.zeros((y2-y1,x2-x1),np.float32)
                    aligned.append(_crop_mask_to_full(combined,clamped,h,w));continue
                box={"x":float(bbox[0]),"y":float(bbox[1]),"width":float(bbox[2]-bbox[0]),"height":float(bbox[3]-bbox[1])}
                masks=detect([box])
                aligned.append(np.max(masks,axis=0).astype(np.float32) if len(masks) else np.zeros(image.shape[:2],np.float32))
            return regions,aligned
        masks=detect(None)
        h,w=image.shape[:2];generated=[]
        for mask in masks:
            ys,xs=np.where(mask>.5)
            if not len(xs):continue
            bbox=np.array([xs.min(),ys.min(),xs.max()+1,ys.max()+1],dtype=np.int32)
            generated.append((bbox, _crop_region(w,h,bbox,settings["bbox_crop_factor"]), mask.astype(np.float32)))
        return generated,[r[2] for r in generated]
    finally:
        if not shared.get("keep_model_loaded",True):
            for key,value in list(_CACHE.items()):
                if isinstance(value,tuple) and len(value)>1 and value[0] is model and value[1] is clip:_CACHE.pop(key,None)
            try:
                _offload(model);_offload(clip)
                del model,clip
                import comfy.model_management as mm
                mm.soft_empty_cache()
            except Exception:pass


def _crop_region(width,height,box,factor):
    def axis(limit,start,end):
        size=(end-start)*factor;left=int((start+end-size)/2);left=max(0,min(left,limit-size));return int(left),int(min(limit,left+size))
    x1,x2=axis(width,box[0],box[2]);y1,y2=axis(height,box[1],box[3]);return x1,y1,x2,y2
