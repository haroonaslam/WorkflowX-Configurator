import copy
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from detailer_x import DetailerX, config, assets
from detailer_x.cache import StageCache, CACHE
from detailer_x.cache import model_signature, digest
from detailer_x import processing as p

def disabled():
    s=copy.deepcopy(config.DEFAULTS)
    for part in s.values():
        if isinstance(part,dict) and "enabled" in part:
            part["enabled"]=False
    return s

@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    CACHE.clear()
    monkeypatch.setattr(p,"cancelled",lambda:None)
    monkeypatch.setattr(importlib.import_module("detailer_x"),"status",lambda *args:None)

def run(s,image=None):
    return DetailerX().process(None,None,None,[],[],torch.rand(1,16,24,3) if image is None else image,json.dumps(s))

def test_roundtrip_and_migration():
    s=config.normalize("{}")
    assert s==config.DEFAULTS
    s["face"]["denoise"]=.23
    assert config.normalize(json.dumps(s))==s
    with pytest.raises(ValueError):config.normalize({"version":4})
    with pytest.raises(ValueError):config.normalize({"face":{"denoise":1.5}})
    with pytest.raises(ValueError):config.normalize({"face":{"enabled":"false"}})
    with pytest.raises(ValueError):config.normalize({"face":{"steps":float("nan")}})

def test_nine_bypass_outputs_and_alpha():
    image=torch.rand(2,16,24,4)
    result=run(disabled(),image)
    assert len(result)==9
    assert all(torch.equal(i,image) for i in result)
    result[-1].zero_()
    assert torch.equal(result[0],image)

def test_cumulative_order_and_reuse(monkeypatch):
    calls=[]
    def fake(image,name,s):
        calls.append(name)
        return image+.01
    monkeypatch.setattr(p,"realism",fake)
    s=disabled()
    for name in config.LEGACY_REALISM:s[name]["enabled"]=True
    image=torch.zeros(1,8,8,3)
    output=run(s,image)
    assert calls==list(config.LEGACY_REALISM)
    assert torch.allclose(output[6],image+.05)
    s["levels"]["white_point"]=248
    calls.clear();run(s,image)
    assert calls==["levels","sharpen"]
    calls.clear();s["cache_epoch"]+=1;run(s,image)
    assert calls==list(config.LEGACY_REALISM)

def test_cache_isolation_eviction():
    cache=StageCache(32)
    a=torch.ones(8)
    cache.put("a",a);a.zero_()
    assert cache.get("a").sum()==8
    cache.get("a").zero_()
    assert cache.get("a").sum()==8
    cache.put("b",torch.ones(8))
    assert cache.get("a") is None and cache.bytes==32
    cache.put("large",torch.ones(100));assert cache.bytes==32
    cache.clear();assert cache.bytes==0

def test_missing_asset_and_traversal():
    with pytest.raises(ValueError):assets.resolve("internal:ultralytics/../../bad.pt","ultralytics")
    with pytest.raises(FileNotFoundError):assets.resolve("internal:ultralytics/bbox/definitely_missing.pt","ultralytics")
    with pytest.raises(ValueError,match="face"):
        s=disabled();s["face"]["enabled"]=True;s["face"]["detector"]="internal:ultralytics/bbox/definitely_missing.pt";run(s)

@pytest.mark.parametrize("name",config.LEGACY_REALISM)
def test_realism_batches_alpha_and_range(name):
    image=torch.rand(2,20,24,4)
    settings=copy.deepcopy(config.DEFAULTS[name])
    if name=="grain":settings.update(seed=42,seed_mode="fixed")
    result=p.realism(image,name,settings)
    assert result.shape==image.shape
    assert torch.equal(result[...,3],image[...,3])
    assert torch.isfinite(result).all() and result.min()>=0 and result.max()<=1
    if name=="grain":assert torch.equal(result,p.realism(image,name,settings))

def test_default_workflow_parity():
    path=ROOT.parents[1]/"user/default/workflows/Qwen2.1 Viggle Custom.json"
    if not path.exists():pytest.skip("Local reference workflow unavailable")
    w=json.loads(path.read_text(encoding="utf-8"))
    byid={n["id"]:n for n in w["nodes"]}
    if not all(n in byid for n in [564,558,556,552,549]):
        pytest.skip("Local workflow no longer contains the original standalone detailer chain")
    keys=["guide_size","guide_size_for","max_size","seed","seed_mode","steps","cfg","sampler_name","scheduler","denoise","feather","noise_mask","force_inpaint","bbox_threshold","bbox_dilation","bbox_crop_factor","sam_detection_hint","sam_dilation","sam_threshold","sam_bbox_expansion","sam_mask_hint_threshold","sam_mask_hint_use_negative","drop_size","prompt","cycle","inpaint_model","noise_mask_feather","tiled_encode","tiled_decode"]
    for name,nid in zip(config.DETAILERS,[564,558,556,552,549]):
        for key,value in zip(keys,byid[nid]["widgets_values"]):assert config.DEFAULTS[name][key]==value,(name,key)
    for name,nid,fields in [("brightness",577,["brightness","contrast","saturation"]),("grain",575,["grain_power","grain_scale","grain_sat"]),("hsv",568,["H","S","V"]),("levels",563,["channel","black_point","white_point","gray_point","output_black_point","output_white_point"]),("sharpen",561,["iterations","kernel_size"])]:
        for key,value in zip(fields,byid[nid]["widgets_values"]):assert config.DEFAULTS[name][key]==value
    assert byid[570]["widgets_values"]==[config.DEFAULTS["sam"]["model"].split("/")[-1],config.DEFAULTS["sam"]["device"]]
    for stage,nid in zip(config.DETAILERS,[569,571,572,573,574]):
        assert config.DEFAULTS[stage]["detector"]=="internal:ultralytics/"+byid[nid]["widgets_values"][0]
    up=dict(config.DEFAULTS["upscaler"]);up.pop("enabled");up["model"]=up["model"].split("/")[-1];up["supersample"]="true" if up["supersample"] else "false"
    assert list(up.values())==byid[566]["widgets_values"]
    dlss_fields=["upscaling_mode","style","preset","intensity","tone","structure","skin","auto_mask","motion","scene_change_threshold","batch_mode","warmup_frames",None,"backend","channel_order","hdr","global_tone","detail","color"]
    for key,value in zip(dlss_fields,byid[598]["widgets_values"]):
        if key:assert config.DEFAULTS["dlss5"][key]==value,key

def test_no_external_custom_pack_imports():
    import ast
    forbidden=("impact","was","comfyroll","layerstyle","rh_dlss")
    for path in (ROOT/"detailer_x").rglob("*.py"):
        tree=ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):names=[a.name for a in node.names]
            elif isinstance(node,ast.ImportFrom):names=[node.module or ""]
            else:continue
            assert not any(n.lower().startswith(forbidden) for n in names),(path,names)

def test_shared_sam_when_face_disabled_and_detail_cache(monkeypatch):
    class Patcher:
        patches_uuid="fixed"
        model_options={}
        object_patches={}
    model,clip,vae=Patcher(),Patcher(),Patcher()
    calls=[]
    monkeypatch.setattr(p,"detail",lambda image,s,sam,*args:(calls.append((s["denoise"],sam["model"])),image+.1)[1])
    s=disabled();s["hand"]["enabled"]=True;s["sam"]["enabled"]=True
    image=torch.zeros(1,8,8,3)
    def execute():return DetailerX().process(model,vae,clip,[],[],image,json.dumps(s))
    execute();assert len(calls)==1 and "sam_vit_b" in calls[0][1]
    execute();assert len(calls)==1
    s["hand"]["denoise"]=.3;execute();assert len(calls)==2
    model.patches_uuid="changed";execute();assert len(calls)==3
    s["sam"]["device"]="CPU";execute();assert len(calls)==4

def test_attention_closure_fingerprints():
    class Patcher:
        patches_uuid="fixed"
        object_patches={}
    settings={"value":1}
    def override():return settings["value"]
    m=Patcher();m.model_options={"fn":override}
    first=digest(model_signature(m,m,m))
    assert first==digest(model_signature(m,m,m))
    settings["value"]=2
    assert first!=digest(model_signature(m,m,m))

def test_cancellation_does_not_publish_partial_cache(monkeypatch):
    s=disabled();s["grain"]["enabled"]=True
    class Interrupted(Exception):pass
    monkeypatch.setattr(p,"realism",lambda *a:(_ for _ in ()).throw(Interrupted()))
    with pytest.raises(RuntimeError):run(s)
    assert CACHE.bytes==0

def test_no_detections_pass_through_batches(monkeypatch):
    monkeypatch.setattr(p,"detections",lambda *a:[])
    s=dict(config.DEFAULTS["face"],prompt="",noise_mask=False)
    image=torch.rand(2,16,24,4)
    assert torch.equal(p.detail(image,s,config.DEFAULTS["sam"],None,None,None,[],[]),image)

@pytest.mark.parametrize("stage",["upscaler",*config.DETAILERS,"dlss5"])
def test_individual_stage_toggle_and_cumulative_outputs(monkeypatch,stage):
    monkeypatch.setattr(p,"upscale",lambda image,*a:image+.1)
    monkeypatch.setattr(p,"detail",lambda image,*a:image+.1)
    monkeypatch.setattr(p,"dlss",lambda image,*a:image+.1)
    s=disabled();s[stage]["enabled"]=True
    image=torch.zeros(1,8,8,3)
    outputs=run(s,image)
    index=["upscaler",*config.DETAILERS,"realism","dlss5"].index(stage)
    for n,out in enumerate(outputs):assert torch.allclose(out,image+(.1 if n>=index else 0))

def test_realism_against_original_functions():
    """Load only reference math definitions, never register external node packs."""
    import ast
    import cv2
    import numpy as np
    from PIL import Image
    layer=ROOT.parent/"ComfyUI_LayerStyle/py/imagefunc.py"
    was=ROOT.parent/"was-ns/WAS_Node_Suite.py"
    if not layer.exists() or not was.exists():pytest.skip("Local reference sources unavailable")
    names={"pil2tensor","tensor2pil","pil2cv2","cv22pil","RGB2YCbCr","YCbCr2RGB","cv_blur_tensor","image_add_grain","adjust_levels","image_hue_offset","image_gray_offset"}
    scope=dict(torch=torch,np=np,cv2=cv2,Image=Image)
    tree=ast.parse(layer.read_text("utf-8"))
    selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(layer),"exec"),scope)
    tree=ast.parse(was.read_text("utf-8"))
    selected=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="WAS_Lucy_Sharpen"]
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(was),"exec"),scope)
    image=torch.rand(1,32,40,3,generator=torch.Generator().manual_seed(57))
    rgb=p.pil(image[0]);reference={}
    reference["grain"]=scope["image_add_grain"](rgb,1,.08,1,seed=42)
    h,s,v=rgb.convert("HSV").split()
    reference["hsv"]=Image.merge("HSV",(h,scope["image_gray_offset"](s,-10),v)).convert("RGB")
    reference["levels"]=scope["adjust_levels"](rgb,0,249,1,0,253)
    reference["sharpen"]=scope["WAS_Lucy_Sharpen"]().lucy_sharpen(rgb,1,3)
    reference["brightness"]=rgb
    for name,expected in reference.items():
        settings=dict(config.DEFAULTS[name])
        if name=="grain":settings.update(seed_mode="fixed",seed=42)
        assert torch.equal(p.realism(image,name,settings)[0],p.tensor(expected)),name
