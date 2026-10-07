"""Structured detailer-mask diagnostics and the dedicated overlay viewer."""
from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path

MASKS_TYPE = "DETAILERX_MASKS"
MASKS_VERSION = 1
MASK_KEYS = ("detector", "refined", "blend")


def _copy_image(image):
    import torch
    value=image.detach().cpu()
    return value.clone() if value.dtype==torch.uint8 else (value.clamp(0,1)*255).round().to(torch.uint8)


def _copy_mask(mask):
    import torch
    value=mask.detach().cpu()
    return value.clone() if value.dtype==torch.uint8 else (value.float().clamp(0,1)*255).round().to(torch.uint8)


def make_mask_bundle(stages=(), bypass_reason=None):
    items=[]
    for item in stages:
        debug=item["debug"]
        items.append(dict(
            id=str(item["id"]),name=str(item["name"]),state=str(item.get("state","processed")),
            input=_copy_image(item["input"]),
            masks={key:_copy_mask(debug[key]) for key in MASK_KEYS},
            backend=str(debug.get("backend","")),detector=str(debug.get("detector_model","")),
            classes=[str(value) for value in debug.get("classes",[])],
            region_counts=[int(value) for value in debug.get("region_counts",[])],
            processed_counts=[int(value) for value in debug.get("processed_counts",[])],
            messages=[str(value) for value in debug.get("messages",[])],
        ))
    return dict(type=MASKS_TYPE,version=MASKS_VERSION,stages=items,bypass_reason=str(bypass_reason or ""))


def validate_mask_bundle(bundle):
    import torch
    if not isinstance(bundle,dict) or bundle.get("type")!=MASKS_TYPE:
        raise ValueError("DetailerX Masks requires the detailer_masks output from DetailerX")
    if bundle.get("version")!=MASKS_VERSION:
        raise ValueError(f"Unsupported DetailerX mask bundle version: {bundle.get('version')}")
    if not isinstance(bundle.get("stages"),list):
        raise ValueError("DetailerX mask bundle has an invalid stage list")
    for item in bundle["stages"]:
        image=item.get("input") if isinstance(item,dict) else None
        if not isinstance(image,torch.Tensor) or image.ndim!=4 or image.shape[-1] not in (3,4):
            raise ValueError("DetailerX mask bundle contains an invalid input image batch")
        masks=item.get("masks",{})
        for key in MASK_KEYS:
            mask=masks.get(key)
            if not isinstance(mask,torch.Tensor) or mask.ndim!=3 or tuple(mask.shape)!=tuple(image.shape[:3]):
                raise ValueError(f"DetailerX mask bundle contains an invalid {key} mask batch")
    return bundle


def _save_images(batch,directory,stem,folder_paths):
    import numpy as np
    import torch
    from PIL import Image
    result=[]
    for index,tensor in enumerate(batch):
        value=tensor.detach().cpu()
        array=value.numpy().astype(np.uint8) if value.dtype==torch.uint8 else (value.clamp(0,1).numpy()*255).round().astype(np.uint8)
        mode="RGBA" if array.shape[-1]==4 else "RGB"
        filename=f"{stem}_{index:03d}.png"
        Image.fromarray(array,mode=mode).save(directory/filename,format="PNG",compress_level=1)
        result.append(dict(filename=filename,subfolder=directory.relative_to(Path(folder_paths.get_temp_directory())).as_posix(),type="temp"))
    return result


def _save_masks(batch,directory,stem,folder_paths):
    import numpy as np
    import torch
    from PIL import Image
    result=[]
    for index,tensor in enumerate(batch):
        value=tensor.detach().cpu()
        array=value.numpy().astype(np.uint8) if value.dtype==torch.uint8 else (value.clamp(0,1).numpy()*255).round().astype(np.uint8)
        filename=f"{stem}_{index:03d}.png"
        # CSS image masks use the source alpha channel by default.  A plain
        # grayscale PNG is fully opaque, so it would incorrectly paint the
        # entire image.  Store the diagnostic mask in alpha as well as RGB so
        # Chromium/WebKit render the actual selected region consistently.
        rgba=np.empty((*array.shape,4),dtype=np.uint8)
        rgba[...,:3]=255
        rgba[...,3]=array
        Image.fromarray(rgba,mode="RGBA").save(directory/filename,format="PNG",compress_level=1)
        result.append(dict(filename=filename,subfolder=directory.relative_to(Path(folder_paths.get_temp_directory())).as_posix(),type="temp"))
    return result


class DetailerXMasks:
    @classmethod
    def INPUT_TYPES(cls):return {"required":{"detailer_masks":(MASKS_TYPE,)},"hidden":{"unique_id":"UNIQUE_ID"}}
    RETURN_TYPES=()
    FUNCTION="preview"
    CATEGORY="WorkflowX/Image"
    OUTPUT_NODE=True
    DESCRIPTION="Browse detector, SAM-refined and final feathered masks over the exact image entering each DetailerX detailer."

    def preview(self,detailer_masks,unique_id=None):
        import folder_paths
        bundle=validate_mask_bundle(detailer_masks)
        root=Path(folder_paths.get_temp_directory())/"workflowx_detailer_masks"
        node_key=hashlib.sha256(str(unique_id or "masks").encode()).hexdigest()[:16]
        node_dir=root/node_key
        if node_dir.exists():shutil.rmtree(node_dir)
        node_dir.mkdir(parents=True,exist_ok=True)
        token=uuid.uuid4().hex[:12];stages=[]
        for stage_index,item in enumerate(bundle["stages"]):
            stem=f"{token}_{stage_index:03d}"
            stages.append(dict(id=item["id"],name=item["name"],state=item["state"],
                inputs=_save_images(item["input"],node_dir,f"{stem}_input",folder_paths),
                masks={key:_save_masks(item["masks"][key],node_dir,f"{stem}_{key}",folder_paths) for key in MASK_KEYS},
                backend=item["backend"],detector=item["detector"],classes=item["classes"],
                region_counts=item["region_counts"],processed_counts=item["processed_counts"],messages=item["messages"]))
        return {"ui":{"workflowx_detailer_masks":[dict(version=MASKS_VERSION,stages=stages,bypass_reason=bundle.get("bypass_reason",""))]}}
