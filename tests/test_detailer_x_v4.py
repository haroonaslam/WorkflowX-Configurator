import copy
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import detailer_x as dx
from detailer_x import config, processing
from detailer_x.cache import CACHE
from detailer_x.sam_backends import _eager_sam2_transforms, _make_sam2_predictor


def disabled():
    value=copy.deepcopy(config.DEFAULTS)
    for name in value["order"]: value[name]["enabled"]=False
    value["sam"]["enabled"]=False
    return value


def test_sam2_eager_transform_matches_unscripted_torchvision_and_is_local(monkeypatch):
    import torch.nn as nn
    from torchvision.transforms import Normalize,Resize,ToTensor

    class BaseTransforms(nn.Module):
        def inherited_marker(self):return "sam2"
    eager_class=_eager_sam2_transforms(BaseTransforms)
    transform=eager_class(16,0.0)
    image=np.arange(9*11*3,dtype=np.uint8).reshape(9,11,3)
    expected=Normalize(transform.mean,transform.std)(Resize((16,16))(ToTensor()(image)))
    assert transform.inherited_marker()=="sam2"
    assert transform(image).shape==(3,16,16)
    assert torch.allclose(transform(image),expected,atol=1e-6)

    class GlobalPredictor:
        def __init__(self,*args,**kwargs):raise AssertionError("global SAM2 constructor must not run")
    model=SimpleNamespace(image_size=16)
    predictor=_make_sam2_predictor(GlobalPredictor,eager_class,model)
    assert predictor.model is model and predictor._transforms.inherited_marker()=="sam2"
    assert predictor._is_image_set is False and predictor._bb_feat_sizes[-1]==(64,64)


def test_v3_migration_adds_hair_and_anything_without_enabling_them():
    order=[name for name in config.ORDER if name not in ("hair","anything")]
    migrated=config.normalize({"version":3,"order":order})
    assert migrated["version"]==5
    assert migrated["face"]["sam_strategy"]=="inherit"
    assert migrated["face"]["sam3_constraint"]=="bounding_box"
    assert migrated["order"].index("hair")==migrated["order"].index("foot")+1
    assert migrated["order"].index("anything")==migrated["order"].index("hair")+1
    assert not migrated["hair"]["enabled"] and not migrated["anything"]["enabled"]


def test_dynamic_detailer_roundtrip_and_hidden_forces_disabled():
    value=copy.deepcopy(config.DEFAULTS);stage="detailer:eye"
    value["extra_detailers"][stage]={**copy.deepcopy(config.DEFAULTS["anything"]),"label":"Eye detailer","catalog_id":"eye","enabled":True}
    value["order"].insert(value["order"].index("brightness"),stage);value["visible"][stage]=False
    result=config.normalize(value)
    assert result["extra_detailers"][stage]["label"]=="Eye detailer"
    assert not result["extra_detailers"][stage]["enabled"]


def test_detection_filters_classes_and_keeps_matching_segmentation(monkeypatch):
    class Boxes:
        xyxy=torch.tensor([[0,0,5,5],[2,2,9,9]],dtype=torch.float32)
        cls=torch.tensor([0,1],dtype=torch.float32)
    masks=SimpleNamespace(data=torch.stack((torch.zeros(10,10),torch.ones(10,10))))
    prediction=SimpleNamespace(boxes=Boxes(),masks=masks,names={0:"other",1:"eye"})
    class FakeYOLO:
        names=prediction.names
        def __init__(self,*a): pass
        def __call__(self,*a,**k): return [prediction]
        def to(self,*a): pass
    monkeypatch.setitem(sys.modules,"ultralytics",SimpleNamespace(YOLO=FakeYOLO))
    monkeypatch.setattr(processing,"resolve",lambda *a:"model.pt")
    settings=copy.deepcopy(config.DEFAULTS["face"]);settings.update(class_ids=[1],class_labels=["eye"],drop_size=0,bbox_dilation=0)
    regions=processing.detections(torch.zeros(10,10,3),settings)
    assert len(regions)==1 and regions[0][0].tolist()==[2,2,9,9]
    assert np.all(regions[0][2]==1)


def test_segmentation_detector_can_force_rectangular_proposal(monkeypatch):
    class Boxes:
        xyxy=torch.tensor([[2,2,9,9]],dtype=torch.float32)
        cls=torch.tensor([0],dtype=torch.float32)
    shaped=torch.zeros(10,10);shaped[4:7,4:7]=1
    prediction=SimpleNamespace(boxes=Boxes(),masks=SimpleNamespace(data=shaped[None]),names={0:"small_item"})
    class FakeYOLO:
        names=prediction.names
        def __init__(self,*a):pass
        def __call__(self,*a,**k):return [prediction]
        def to(self,*a):pass
    monkeypatch.setitem(sys.modules,"ultralytics",SimpleNamespace(YOLO=FakeYOLO))
    monkeypatch.setattr(processing,"resolve",lambda *a:"model.pt")
    settings=copy.deepcopy(config.DEFAULTS["anything"]);settings.update(detector="model.pt",class_ids=[0],class_labels=["small_item"],drop_size=0,bbox_dilation=0)
    native=processing.detections(torch.zeros(10,10,3),settings)[0][2]
    settings["detector_proposal"]="bbox"
    rectangular=processing.detections(torch.zeros(10,10,3),settings)[0][2]
    assert native.sum()==9 and native[4:7,4:7].all()
    assert rectangular.sum()==64 and rectangular[2:10,2:10].all()
    assert not rectangular[:2].any() and not rectangular[:,:2].any()


def test_reused_blend_mask_recovers_separate_soft_regions():
    mask=np.zeros((20,24),np.float32)
    mask[2:7,3:9]=.4
    mask[12:18,15:22]=.8
    settings=copy.deepcopy(config.DEFAULTS['face']);settings['bbox_crop_factor']=2
    regions=processing.reused_mask_regions(mask,settings)
    assert len(regions)==2
    boxes=[tuple(region[0]) for region in regions]
    assert boxes==[(3,2,9,7),(15,12,22,18)]
    assert np.isclose(regions[0][2].max(),.4) and np.isclose(regions[1][2].max(),.8)


def test_global_fixed_seed_supersedes_detailer_seeds(monkeypatch):
    CACHE.clear();seen=[];value=disabled()
    for name in ("face","hand"):
        value[name]["enabled"]=True;value[name]["seed"]=1 if name=="face" else 2
    value["global_seed"]={"enabled":True,"mode":"fixed","seed":987654}
    monkeypatch.setattr(dx,"asset_signatures",lambda s:{})
    monkeypatch.setattr(dx,"model_signature",lambda *a:"model")
    monkeypatch.setattr(dx,"status",lambda *a:None)
    monkeypatch.setattr(processing,"cancelled",lambda:None)
    monkeypatch.setattr(processing,"detail",lambda image,s,*a:(seen.append(s["seed"]) or image))
    dx.DetailerX().process(None,None,None,[],[],torch.zeros(1,8,8,3),value,unique_id="seed-node")
    assert seen==[987654,987654]
    assert dx.consume_realized_seed("seed-node")==987654
    assert dx.consume_realized_seed("seed-node") is None


def test_global_random_seed_resolves_once_per_execution_and_changes_on_rerun(monkeypatch):
    CACHE.clear();seen=[];value=disabled()
    for name in ("face","hand"):
        value[name]["enabled"]=True;value[name]["seed"]=1 if name=="face" else 2
    value["global_seed"]={"enabled":True,"mode":"random","seed":703203187737355}
    generated=iter((111111,222222))
    monkeypatch.setattr(dx.secrets,"randbelow",lambda _limit:next(generated))
    monkeypatch.setattr(dx,"asset_signatures",lambda s:{})
    monkeypatch.setattr(dx,"model_signature",lambda *a:"model")
    monkeypatch.setattr(dx,"status",lambda *a:None)
    monkeypatch.setattr(processing,"cancelled",lambda:None)
    monkeypatch.setattr(processing,"detail",lambda image,s,*a:(seen.append(s["seed"]) or image))

    node=dx.DetailerX()
    image=torch.zeros(1,8,8,3)
    node.process(None,None,None,[],[],image,value,unique_id="random-seed-node")
    first=dx.consume_realized_seed("random-seed-node")
    node.process(None,None,None,[],[],image,value,unique_id="random-seed-node")
    second=dx.consume_realized_seed("random-seed-node")

    assert (first,second)==(111111,222222)
    assert seen==[111111,111111,222222,222222]
    assert value["global_seed"]["seed"]==703203187737355


def test_sam3_concept_only_does_not_require_detector_signature(monkeypatch):
    value=disabled();value["face"].update(enabled=True,sam3_mode="concept_only")
    value["sam"].update(enabled=False,backend="sam3.1")
    # With SAM disabled the ordinary detector is still required; enabling SAM3 concept-only bypasses it.
    value["sam"]["enabled"]=True
    monkeypatch.setitem(sys.modules,"folder_paths",SimpleNamespace(get_full_path=lambda *a:__file__))
    signatures=dx.asset_signatures(value)
    assert "face" not in signatures and "sam:face" in signatures
