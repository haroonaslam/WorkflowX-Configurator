import copy
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from detailer_x import config,processing
import detailer_x as dx
from detailer_x import sam_backends


def _only_face(settings):
    for name in settings["order"]:
        target=settings["extra_detailers"].get(name) if name.startswith("detailer:") else settings[name]
        target["enabled"]=name=="face"
    settings["visible"]["face"]=True
    return settings


def test_v4_migrates_to_inherited_sam_and_bounding_constraint():
    value=config.normalize({"version":4})
    assert value["version"]==5
    for name in config.DETAILERS:
        assert value[name]["sam_strategy"]=="inherit"
        assert value[name]["sam3_constraint"]=="bounding_box"
        assert value[name]["sam_override"]["backend"]=="sam1"


def test_bbox_controlled_normalizes_and_validates_detector_and_concept():
    value=config.normalize({"version":5,"face":{"sam3_mode":"bbox_controlled"}})
    assert value["face"]["sam3_mode"]=="bbox_controlled"
    value=_only_face(value);value["sam"].update(enabled=True,backend="sam3.1",model="checkpoint:sam3.pt")
    value["face"].update(detector="",mask_concept="anus")
    try:dx.asset_signatures(value)
    except ValueError as exc:assert "requires a detector" in str(exc)
    else:raise AssertionError("BBox controlled accepted a missing detector")
    value["face"].update(detector="internal:ultralytics/bbox/face_yolov8m.pt",mask_concept="")
    try:dx.asset_signatures(value)
    except ValueError as exc:assert "requires a non-empty mask concept" in str(exc)
    else:raise AssertionError("BBox controlled accepted an empty mask concept")


def test_existing_sam3_modes_roundtrip_without_reinterpretation():
    for mode in ("refine_detector","concept_with_detector","concept_only"):
        value=config.normalize({"version":5,"face":{"sam3_mode":mode}})
        assert value["face"]["sam3_mode"]==mode


def test_detector_proposal_migrates_to_native_and_roundtrips_bbox():
    assert config.normalize({"version":4})["face"]["detector_proposal"]=="native"
    value=config.normalize({"version":5,"face":{"detector_proposal":"bbox"}})
    assert value["face"]["detector_proposal"]=="bbox"


def test_effective_sam_is_immutable_and_detailer_override_wins():
    value=copy.deepcopy(config.DEFAULTS);stage=value["face"]
    value["sam"].update(enabled=False,backend="sam1",device="CPU")
    inherited=config.effective_sam(value,stage)
    assert not inherited["enabled"] and inherited["source"]=="global"
    stage["sam_strategy"]="detector_only"
    assert config.effective_sam(value,stage)["source"]=="detector_only"
    stage["sam_strategy"]="override";stage["sam_override"].update(backend="sam3.1",model="checkpoint:sam3.pt",device="Prefer GPU")
    overridden=config.effective_sam(value,stage)
    assert overridden["enabled"] and overridden["backend"]=="sam3.1" and overridden["source"]=="override"
    overridden["backend"]="changed"
    assert stage["sam_override"]["backend"]=="sam3.1"


def test_repeatable_custom_detailers_allow_duplicate_names_and_concepts():
    value=copy.deepcopy(config.DEFAULTS);ids=["detailer:custom:11111111-1111-4111-8111-111111111111","detailer:custom:22222222-2222-4222-8222-222222222222"]
    for identifier in ids:
        item=copy.deepcopy(value["anything"]);item.update(label="Jewellery",mask_concept="necklace",enabled=False,catalog_id="custom")
        value["extra_detailers"][identifier]=item;value["visible"][identifier]=True
        value["order"].insert(value["order"].index("brightness"),identifier)
    result=config.normalize(value)
    assert [result["extra_detailers"][identifier]["label"] for identifier in ids]==["Jewellery","Jewellery"]
    assert all(identifier in result["order"] for identifier in ids)


def test_process_resolves_global_detector_only_and_override_per_detailer(monkeypatch):
    value=copy.deepcopy(config.DEFAULTS)
    for name in value["order"]:
        target=value["extra_detailers"].get(name) if name.startswith("detailer:") else value[name]
        target["enabled"]=False
    value["sam"].update(enabled=True,backend="sam1",model="internal:sams/global.pth")
    value["face"].update(enabled=True,sam_strategy="inherit")
    value["hand"].update(enabled=True,sam_strategy="detector_only")
    value["hair"].update(enabled=True,sam_strategy="override")
    value["hair"]["sam_override"].update(backend="sam3.1",model="checkpoint:local-sam3.safetensors")
    seen={}
    monkeypatch.setattr(dx,"asset_signatures",lambda settings:{})
    monkeypatch.setattr(dx,"model_signature",lambda *args:"model")
    monkeypatch.setattr(dx,"status",lambda *args:None)
    monkeypatch.setattr(processing,"cancelled",lambda:None)
    def detail(image,stage,shared,*args):
        seen[stage["catalog_id"]]=shared
        return image
    monkeypatch.setattr(processing,"detail",detail)
    dx.DetailerX().process(None,None,None,[],[],torch.zeros(1,8,8,3),value)
    assert seen["face"]["source"]=="global" and seen["face"]["backend"]=="sam1"
    assert seen["hand"]["source"]=="detector_only" and not seen["hand"]["enabled"]
    assert seen["hair"]["source"]=="override" and seen["hair"]["backend"]=="sam3.1"


def test_sam3_constraints_preserve_raw_expand_or_detector_shape():
    raw=np.zeros((8,8),np.float32);raw[1:7,1:7]=1
    proposal=np.zeros((8,8),np.float32);proposal[3:5,3:5]=1
    bbox=np.asarray([2,2,6,6])
    detector=processing.sam3_constraint(raw,proposal,bbox,"detector_mask",8,8)
    bounded=processing.sam3_constraint(raw,proposal,bbox,"bounding_box",8,8)
    free=processing.sam3_constraint(raw,proposal,bbox,"none",8,8)
    assert detector.sum()==4
    assert bounded.sum()==16 and not bounded[1,1]
    assert free.sum()==36 and free[1,1]


def test_sam3_detector_assisted_calls_each_box_independently(monkeypatch):
    calls=[]
    class Detect:
        FUNCTION="run"
        def run(self,**kwargs):
            calls.append(kwargs)
            box=kwargs["bboxes"][0];mask=torch.zeros(1,10,10)
            x=int(box["x"]);mask[:,x:x+2,x:x+2]=1
            return mask,[]
    monkeypatch.setitem(sys.modules,"nodes",SimpleNamespace(NODE_CLASS_MAPPINGS={"SAM3_Detect":Detect}))
    monkeypatch.setattr(sam_backends,"_sam3_load",lambda shared:(object(),object()))
    regions=[]
    for start in (1,5):
        proposal=np.zeros((10,10),np.float32);proposal[start:start+2,start:start+2]=1
        bbox=np.asarray([start,start,start+2,start+2]);regions.append((bbox,(0,0,10,10),proposal))
    settings=dict(sam3_mode="refine_detector",sam3_threshold=.5,sam3_refine_iterations=3,bbox_crop_factor=2)
    returned,masks=sam_backends.sam3(torch.zeros(10,10,3),regions,settings,{"model":"checkpoint:sam3.pt"})
    assert returned is regions and len(masks)==2 and len(calls)==2
    assert calls[0]["bboxes"][0]["x"]==1 and calls[1]["bboxes"][0]["x"]==5
    assert masks[0][1,1] and not masks[0][5,5] and masks[1][5,5]


def test_sam3_fully_text_guided_bypasses_detector_and_keeps_multiple_regions(monkeypatch):
    calls=[]
    class Detect:
        FUNCTION="run"
        def run(self,**kwargs):
            calls.append(kwargs);masks=torch.zeros(2,12,12);masks[0,1:3,2:5]=1;masks[1,7:10,8:11]=1
            return masks,[]
    monkeypatch.setitem(sys.modules,"nodes",SimpleNamespace(NODE_CLASS_MAPPINGS={"SAM3_Detect":Detect}))
    monkeypatch.setattr(sam_backends,"_sam3_load",lambda shared:(object(),object()))
    monkeypatch.setattr(sam_backends,"_encode",lambda clip,text:("concept",text))
    settings=dict(sam3_mode="concept_only",mask_concept="necklace",sam3_threshold=.5,sam3_refine_iterations=3,bbox_crop_factor=2)
    regions,masks=sam_backends.sam3(torch.zeros(12,12,3),[],settings,{"model":"checkpoint:sam3.pt"})
    assert len(calls)==1 and calls[0]["bboxes"] is None and calls[0]["conditioning"]==("concept","necklace")
    assert len(regions)==len(masks)==2
    assert regions[0][0].tolist()==[2,1,5,3] and regions[1][0].tolist()==[8,7,11,10]


def test_sam3_bbox_controlled_crops_translates_resizes_and_hard_clips(monkeypatch):
    calls=[]
    class Detect:
        FUNCTION="run"
        def run(self,**kwargs):
            calls.append(kwargs)
            return torch.ones(2,2,2),[]
    monkeypatch.setitem(sys.modules,"nodes",SimpleNamespace(NODE_CLASS_MAPPINGS={"SAM3_Detect":Detect}))
    monkeypatch.setattr(sam_backends,"_sam3_load",lambda shared:(object(),object()))
    monkeypatch.setattr(sam_backends,"_encode",lambda clip,text:("concept",text))
    image=torch.zeros(8,10,3);regions=[]
    for bbox in (np.asarray([-2,1,4,5]),np.asarray([7,6,12,10])):
        proposal=np.zeros((8,10),np.float32);regions.append((bbox,(0,0,10,8),proposal))
    settings=dict(sam3_mode="bbox_controlled",mask_concept="anus",sam3_threshold=.5,sam3_refine_iterations=3,bbox_crop_factor=2)
    returned,masks=sam_backends.sam3(image,regions,settings,{"model":"checkpoint:sam3.pt"})
    assert returned is regions and len(calls)==len(masks)==2
    assert tuple(calls[0]["image"].shape)==(1,4,4,3) and tuple(calls[1]["image"].shape)==(1,2,3,3)
    assert calls[0]["bboxes"]==[{"x":0.0,"y":0.0,"width":4.0,"height":4.0}]
    assert calls[1]["bboxes"]==[{"x":0.0,"y":0.0,"width":3.0,"height":2.0}]
    assert calls[0]["conditioning"]==("concept","anus")
    assert masks[0].shape==masks[1].shape==(8,10)
    assert masks[0][1:5,0:4].min()==1 and masks[0].sum()==16
    assert masks[1][6:8,7:10].min()==1 and masks[1].sum()==6


def test_sam3_bbox_controlled_empty_and_degenerate_results_are_safe(monkeypatch):
    calls=[]
    class Detect:
        FUNCTION="run"
        def run(self,**kwargs):
            calls.append(kwargs);return torch.zeros(0,2,2),[]
    monkeypatch.setitem(sys.modules,"nodes",SimpleNamespace(NODE_CLASS_MAPPINGS={"SAM3_Detect":Detect}))
    monkeypatch.setattr(sam_backends,"_sam3_load",lambda shared:(object(),object()))
    monkeypatch.setattr(sam_backends,"_encode",lambda clip,text:("concept",text))
    image=torch.zeros(8,10,3);zero=np.zeros((8,10),np.float32)
    regions=[(np.asarray([2,2,6,6]),(0,0,8,8),zero),(np.asarray([11,3,12,5]),(0,0,8,8),zero)]
    settings=dict(sam3_mode="bbox_controlled",mask_concept="small object",sam3_threshold=.5,sam3_refine_iterations=3,bbox_crop_factor=2)
    _,masks=sam_backends.sam3(image,regions,settings,{"model":"checkpoint:sam3.pt"})
    assert len(masks)==2 and len(calls)==1
    assert not masks[0].any() and not masks[1].any()


def test_two_model_lru_offloads_oldest():
    sam_backends._CACHE.clear();moves=[]
    class Model:
        def __init__(self,name):self.name=name
        def to(self,device):moves.append((self.name,str(device)))
    one,two,three=Model("one"),Model("two"),Model("three")
    sam_backends._remember("one",(object(),one));sam_backends._remember("two",(object(),two))
    assert sam_backends._cached("one")[1] is one
    sam_backends._remember("three",(object(),three))
    assert list(sam_backends._CACHE)==["one","three"]
    assert ("two","cpu") in moves
    sam_backends._CACHE.clear()
