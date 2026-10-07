import sys
import types
from pathlib import Path

import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import detailer_x
from detailer_x.preview import DetailerXPreview, make_bundle, validate_bundle
from detailer_x.masks import DetailerXMasks, make_mask_bundle, validate_mask_bundle


def test_public_output_contract_and_preview_registration():
    assert detailer_x.DetailerX.RETURN_TYPES == ("IMAGE", "DETAILERX_PROCESSOR_IMAGES", "DETAILERX_MASKS")
    assert detailer_x.DetailerX.RETURN_NAMES == ("final_image", "processor_images", "detailer_masks")
    assert detailer_x.NODE_CLASS_MAPPINGS["WorkflowX_DetailerXPreview"] is DetailerXPreview
    assert DetailerXPreview.RETURN_TYPES == () and DetailerXPreview.OUTPUT_NODE is True
    assert detailer_x.NODE_CLASS_MAPPINGS["WorkflowX_DetailerXMasks"] is DetailerXMasks
    assert DetailerXMasks.RETURN_TYPES == () and DetailerXMasks.OUTPUT_NODE is True


def test_bundle_is_ordered_and_immutable():
    original = torch.zeros(2, 5, 7, 4)
    first = original + .1
    second = original + .2
    bundle = make_bundle(original, [
        {"id": "face", "name": "Face detailer", "state": "processed", "image": first},
        {"id": "lut", "name": "LUT", "state": "cached", "image": second},
    ])
    validate_bundle(bundle)
    assert [item["id"] for item in bundle["stages"]] == ["face", "lut"]
    original.fill_(1);first.fill_(1);second.fill_(1)
    assert torch.count_nonzero(bundle["original"]) == 0
    assert torch.allclose(bundle["stages"][0]["image"], torch.full_like(first, .1))


def test_preview_writes_named_batch_payload_and_previous_links(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "folder_paths", types.SimpleNamespace(get_temp_directory=lambda: str(tmp_path)))
    original = torch.zeros(2, 4, 6, 4)
    stage_a = torch.full((2, 8, 12, 4), .25)
    stage_b = torch.full((2, 8, 12, 4), .75)
    bundle = make_bundle(original, [
        {"id": "upscaler", "name": "Upscaler", "state": "processed", "image": stage_a},
        {"id": "face", "name": "Face detailer", "state": "cached", "image": stage_b},
    ])
    result = DetailerXPreview().preview(bundle, "node-7")
    payload = result["ui"]["workflowx_detailer_preview"][0]
    assert payload["batch_count"] == 2
    assert [stage["name"] for stage in payload["stages"]] == ["Upscaler", "Face detailer"]
    assert payload["stages"][0]["previous"] == payload["original"]
    assert payload["stages"][1]["previous"] == payload["stages"][0]["images"]
    paths = [*payload["original"], *(image for stage in payload["stages"] for image in stage["images"])]
    assert all((tmp_path / item["subfolder"] / item["filename"]).is_file() for item in paths)


def test_preview_accepts_bypass_bundle(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "folder_paths", types.SimpleNamespace(get_temp_directory=lambda: str(tmp_path)))
    bundle = make_bundle(torch.rand(1, 3, 4, 3), bypass_reason="Skipped")
    payload = DetailerXPreview().preview(bundle, "skip")["ui"]["workflowx_detailer_preview"][0]
    assert payload["stages"] == [] and payload["bypass_reason"] == "Skipped"


def test_mask_bundle_and_overlay_payload(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "folder_paths", types.SimpleNamespace(get_temp_directory=lambda: str(tmp_path)))
    image=torch.rand(2,6,8,4);detector=torch.zeros(2,6,8);refined=detector.clone();blend=detector.clone()
    detector[:,1:5,2:7]=1;refined[:,2:5,3:7]=1;blend[:,2:5,3:7]=.6
    bundle=make_mask_bundle([dict(id="face",name="Face detailer",state="processed",input=image,debug=dict(
        detector=detector,refined=refined,blend=blend,backend="sam2.1",detector_model="face.pt",classes=["face"],
        region_counts=[1,1],processed_counts=[1,1],messages=["1 region(s), 1 processed"]*2))])
    validate_mask_bundle(bundle)
    image.zero_();detector.zero_()
    assert torch.count_nonzero(bundle["stages"][0]["input"])>0
    assert torch.count_nonzero(bundle["stages"][0]["masks"]["detector"])>0
    payload=DetailerXMasks().preview(bundle,"mask-node")["ui"]["workflowx_detailer_masks"][0]
    assert payload["stages"][0]["backend"]=="sam2.1"
    assert len(payload["stages"][0]["inputs"])==2
    paths=[*payload["stages"][0]["inputs"],*(item for values in payload["stages"][0]["masks"].values() for item in values)]
    assert all((tmp_path/item["subfolder"]/item["filename"]).is_file() for item in paths)
    detector_item=payload["stages"][0]["masks"]["detector"][0]
    with Image.open(tmp_path/detector_item["subfolder"]/detector_item["filename"]) as saved_mask:
        assert saved_mask.mode=="RGBA"
        alpha=torch.frombuffer(bytearray(saved_mask.getchannel("A").tobytes()),dtype=torch.uint8).reshape(6,8)
    assert torch.all(alpha[1:5,2:7]==255)
    assert torch.count_nonzero(alpha)==20


def test_mask_preview_accepts_bypass_bundle(tmp_path,monkeypatch):
    monkeypatch.setitem(sys.modules,"folder_paths",types.SimpleNamespace(get_temp_directory=lambda:str(tmp_path)))
    payload=DetailerXMasks().preview(make_mask_bundle(bypass_reason="Skipped"),"skip")["ui"]["workflowx_detailer_masks"][0]
    assert payload["stages"]==[] and payload["bypass_reason"]=="Skipped"
