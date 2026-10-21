import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from detailer_x import config, presets, processing as p


@pytest.mark.parametrize("id", config.BUILTINS)
def test_builtin_validation_and_portability(id):
    profile = config.BUILTINS[id]
    assert presets.validate_profile(profile) == profile
    s = copy.deepcopy(config.DEFAULTS)
    for stage, values in profile["values"].items():
        s[stage].update(values)
    s["preset"] = profile
    assert config.normalize(json.dumps(s)) == s


def test_exact_qwen_defaults_and_legacy_migration():
    assert config.BUILTINS["qwen21"]["values"] == presets.values(config.DEFAULTS)
    legacy = copy.deepcopy(config.DEFAULTS)
    legacy.pop("preset"); legacy["version"] = 1
    for name in config.DETAILERS:
        legacy[name].pop("guidance"); legacy[name].pop("guidance_mode")
    assert config.normalize(legacy) == config.DEFAULTS
    legacy["face"]["cfg"] = 3.5
    migrated = config.normalize(legacy)
    assert migrated["face"]["cfg"] == 3.5
    assert migrated["preset"]["id"] == "legacy"


def test_atomic_library_conflict_restore_and_isolation(tmp_path):
    path = tmp_path / "local" / "presets.json"
    profile = copy.deepcopy(config.BUILTINS["sdxl"])
    profile["values"]["face"]["cfg"] = 6
    saved = presets.save(profile, 1, path)
    assert saved["revision"] == 2
    assert presets.library(path)["sdxl"]["values"]["face"]["cfg"] == 6
    assert config.BUILTINS["sdxl"]["values"]["face"]["cfg"] == 5
    with pytest.raises(ValueError, match="another editor"):
        presets.save(profile, 1, path)
    restored = presets.save(config.BUILTINS["sdxl"], 2, path)
    assert restored["values"] == config.BUILTINS["sdxl"]["values"]
    assert not list(path.parent.glob("*.tmp"))
    custom = dict(saved, id="user-example", label="My custom settings")
    assert presets.save(custom, 0, path)["revision"] == 1
    custom["id"] = "../bad"
    with pytest.raises(ValueError): presets.save(custom, 0, path)
    custom["id"] = "valid"
    custom["values"]["face"]["cfg"] = float("nan")
    with pytest.raises(ValueError): presets.save(custom, 0, path)


@pytest.mark.parametrize("source_channels", [3,4])
@pytest.mark.parametrize("decoded_channels", [3,4])
@pytest.mark.parametrize("decode_mode", ["normal","tiled","oom"])
def test_detail_rgb_rgba_composite(monkeypatch, source_channels, decoded_channels, decode_mode):
    import nodes
    import comfy.model_management as mm
    s = dict(config.DEFAULTS["face"], prompt="", noise_mask=False, guide_size=64, max_size=64, tiled_decode=decode_mode=="tiled")
    image = torch.rand(2,16,24,source_channels)
    monkeypatch.setattr(p, "cancelled", lambda:None)
    monkeypatch.setattr(p, "detections", lambda *a:[((0,0,24,16),(0,0,24,16),np.ones((16,24),np.float32))])
    monkeypatch.setattr(p, "sample_crop", lambda *a:a[-1])
    monkeypatch.setattr(nodes, "VAEEncode", lambda:SimpleNamespace(encode=lambda *a:({"samples":torch.ones(1,4,8,8)},)), raising=False)
    decoded = torch.full((1,32,48,decoded_channels),.75)
    monkeypatch.setattr(nodes, "VAEDecodeTiled", lambda:SimpleNamespace(decode=lambda *a:(decoded,)), raising=False)
    class VAE:
        def decode(self, *args):
            if decode_mode=="oom": raise mm.OOM_EXCEPTION("test")
            return decoded
        def decode_tiled(self, *args, **kwargs): return decoded
    out,debug = p.detail(image,s,dict(config.DEFAULTS["sam"],enabled=False),None,None,VAE(),[],[],True)
    assert out.shape == image.shape
    assert torch.isfinite(out).all()
    assert torch.allclose(out[...,:3],torch.full_like(out[...,:3],191/255))
    if source_channels==4: assert torch.equal(out[...,3],image[...,3])
    assert debug["detector"].shape==debug["refined"].shape==debug["blend"].shape==(2,16,24)
    assert torch.all(debug["detector"]==1) and torch.all(debug["refined"]==1)
    assert torch.any(debug["blend"]>0) and debug["processed_counts"]==[1,1]


@pytest.mark.parametrize("shape", [(1,8,8,1),(1,8,8,8),(8,8,3),(0,8,8,3)])
def test_bad_decode_fails_helpfully(shape):
    with pytest.raises(ValueError, match="BHWC RGB or RGBA"):
        p.decoded_rgb(torch.zeros(shape))


@pytest.mark.parametrize("channels", [3, 4])
def test_single_frame_video_vae_decode_is_normalized_to_bhwc(channels):
    decoded = torch.rand(2, 1, 8, 12, channels)
    result = p.decoded_rgb(decoded)
    assert result.shape == (2, 8, 12, 3)
    assert torch.equal(result, decoded[:, 0, ..., :3])


def test_multi_frame_video_vae_decode_fails_with_shape():
    with pytest.raises(ValueError, match=r"single-frame BTHWC image; got \(1, 2, 8, 12, 3\)"):
        p.decoded_rgb(torch.zeros(1, 2, 8, 12, 3))


def test_guidance_is_separate_and_nonmutating():
    original = [[torch.ones(1), {"guidance":8, "pooled_output":torch.ones(2)}]]
    s = dict(config.DEFAULTS["face"], guidance_mode="set", guidance=3.5)
    result = p.guided_conditioning(original,s)
    assert result[0][1]["guidance"]==3.5 and original[0][1]["guidance"]==8
    assert result[0][1]["pooled_output"] is original[0][1]["pooled_output"]
    assert p.guided_conditioning(original,dict(s,guidance_mode="disabled"))[0][1]["guidance"] is None
    assert p.guided_conditioning(original,dict(s,guidance_mode="incoming")) is original


def test_local_prompt_conditioning_modes_are_symmetric(monkeypatch):
    import nodes
    encoded=[]
    class Encoder:
        def encode(self, clip, text):
            encoded.append((clip,text))
            return ([[f"encoded:{text}",{}]],)
    class Concatenator:
        def concat(self, incoming, local):
            return (["concat",incoming,local],)
    monkeypatch.setattr(nodes,"CLIPTextEncode",Encoder,raising=False)
    monkeypatch.setattr(nodes,"ConditioningConcat",Concatenator,raising=False)
    incoming=[["incoming",{"guidance":3.5}]]
    assert p.prompt_conditioning(incoming,"ignored","incoming","clip") is incoming
    assert p.prompt_conditioning(incoming,"","concat","clip") is incoming
    assert p.prompt_conditioning(incoming,"","replace","clip") is incoming
    replaced=p.prompt_conditioning(incoming,"","replace","clip",encode_blank=True)
    assert encoded[-1]==("clip","") and replaced==[["encoded:",{"guidance":3.5}]]
    concatenated=p.prompt_conditioning(incoming,"avoid artifact","concat","clip",label="negative detail")
    assert concatenated[0]=="concat" and concatenated[1] is incoming
    assert concatenated[2]==[["encoded:avoid artifact",{"guidance":3.5}]]


def test_global_prompt_conditioning_order_blank_rules_and_encoding_cache(monkeypatch):
    import nodes
    encoded=[]
    class Encoder:
        def encode(self, clip, text):
            encoded.append((clip,text))
            return ([[f"encoded:{text}",{}]],)
    class Concatenator:
        def concat(self, left, right):
            return (left+right,)
    monkeypatch.setattr(nodes,"CLIPTextEncode",Encoder,raising=False)
    monkeypatch.setattr(nodes,"ConditioningConcat",Concatenator,raising=False)
    incoming=[["incoming",{"guidance":3.5,"stable":"yes"}]]
    snapshot=copy.deepcopy(incoming)
    cache={}

    def compose(mode,local="local",global_text="global",negative=False):
        return p.prompt_conditioning(incoming,local,mode,"clip","incoming","negative detail" if negative else "detail",
                                     negative,global_text,cache,"negative" if negative else "positive")

    assert [item[0] for item in compose("incoming")]==["incoming","encoded:global"]
    assert [item[0] for item in compose("concat")]==["incoming","encoded:global","encoded:local"]
    assert [item[0] for item in compose("replace")]==["encoded:global","encoded:local"]
    assert [item[0] for item in compose("replace",local="")]==["incoming","encoded:global"]
    assert [item[0] for item in compose("replace",local="",negative=True)]==["encoded:global","encoded:"]
    assert [item[0] for item in compose("concat",local="",global_text="   ")]==["incoming"]
    assert incoming==snapshot
    assert encoded.count(("clip","global"))==2  # once for each polarity
    assert all(item[1].get("guidance")==3.5 for item in compose("concat"))


def test_global_prompt_enable_control_retains_but_excludes_saved_text():
    saved={"enabled":False,"positive":"saved detail","negative":"saved artifact"}
    assert p._global_prompt_text(saved,"positive")==""
    assert p._global_prompt_text(saved,"negative")==""
    saved["enabled"]=True
    assert p._global_prompt_text(saved,"positive")=="saved detail"
    assert p._global_prompt_text(saved,"negative")=="saved artifact"
    assert p._global_prompt_text({"positive":"legacy"},"positive")=="legacy"


def test_global_prompts_are_not_model_preset_fields():
    assert "global_prompts" not in presets.FIELDS
    state=copy.deepcopy(config.DEFAULTS)
    before=presets.values(state)
    state["global_prompts"]={"enabled":False,"positive":"shared detail","negative":"shared artifact"}
    assert presets.values(state)==before


def test_v8_prompt_defaults_and_v5_migration():
    assert config.DEFAULTS["version"]==8
    assert config.DEFAULTS["global_prompts"]=={"enabled":True,"positive":"","negative":""}
    assert config.DEFAULTS["face"]["negative_prompt"]==""
    assert config.DEFAULTS["face"]["negative_prompt_mode"]=="incoming"
    legacy=copy.deepcopy(config.DEFAULTS);legacy["version"]=5
    for name in config.DETAILERS:
        legacy[name].pop("negative_prompt");legacy[name].pop("negative_prompt_mode")
    migrated=config.normalize(legacy)
    assert all(migrated[name]["negative_prompt"]=="" and migrated[name]["negative_prompt_mode"]=="incoming" for name in config.DETAILERS)
    configured=copy.deepcopy(config.DEFAULTS);configured["face"].update(negative_prompt="duplicate anatomy",negative_prompt_mode="concat")
    assert config.normalize(configured)["face"]["negative_prompt"]=="duplicate anatomy"
    configured["face"]["negative_prompt_mode"]="invalid"
    with pytest.raises(ValueError,match="negative_prompt_mode"):
        config.normalize(configured)


def test_anus_catalog_uses_targeted_detector_mask_and_prompt_defaults(monkeypatch):
    from detailer_x import catalog
    detector="internal:ultralytics/bbox/sexual_elements_yolo11m.pt"
    monkeypatch.setattr(catalog.assets,"inventory",lambda *args,**kwargs:[{"id":detector,"label":"Sexual elements"}])
    monkeypatch.setattr(catalog,"model_metadata",lambda identifier:{"id":identifier,"task":"bbox","description":"","classes":[{"id":1,"label":"Asshole"}]})
    concept=next(item for item in catalog.build_catalog()["concepts"] if item["id"]=="anus")
    defaults=concept["detailer_defaults"]
    assert defaults["detector"]==detector and defaults["class_ids"]==[1] and defaults["class_labels"]==["Asshole"]
    assert defaults["denoise"]==.25 and concept["detailer_revision"]==1
    assert defaults["feather"]==18 and defaults["noise_mask_feather"]==5
    assert defaults["bbox_threshold"]==.7 and defaults["bbox_dilation"]==1 and defaults["bbox_crop_factor"]==1.5
    assert defaults["detector_proposal"]=="native" and defaults["sam_dilation"]==1
    assert defaults["noise_mask"] is True and defaults["force_inpaint"] is True
    assert concept["prompt"].startswith("subtle natural detail") and concept["prompt"].endswith("natural perianal skin")
    assert set(presets.FIELDS)&set(defaults)==set()


def test_existing_anus_catalog_detailer_migrates_once():
    stage="detailer:anus"
    value=copy.deepcopy(config.DEFAULTS)
    value["extra_detailers"]={stage:{**copy.deepcopy(config.DEFAULTS["anything"]),"label":"Anus detailer","catalog_id":"anus","catalog_revision":0,"detector":"old.pt","prompt":"old prompt","denoise":.5,"steps":8,"enabled":True}}
    value["order"]=[*config.ORDER,stage];value["visible"][stage]=True
    migrated=config.normalize(value)["extra_detailers"][stage]
    assert migrated["detector"]=="internal:ultralytics/bbox/sexual_elements_yolo11m.pt"
    assert migrated["prompt"].startswith("subtle natural detail") and migrated["denoise"]==.25
    assert migrated["feather"]==18 and migrated["sam_dilation"]==1 and migrated["steps"]==8
    assert migrated["enabled"] is True and migrated["catalog_revision"]==1
    migrated["prompt"]="user prompt";value["extra_detailers"][stage]=migrated
    assert config.normalize(value)["extra_detailers"][stage]["prompt"]=="user prompt"


def test_denoise_is_detailer_local_and_legacy_profiles_are_accepted():
    assert "denoise" not in presets.FIELDS
    state=copy.deepcopy(config.DEFAULTS);profile=copy.deepcopy(config.BUILTINS["qwen21"])
    for values in profile["values"].values(): values["denoise"]=.99
    validated=presets.validate_profile(profile)
    assert all("denoise" not in values for values in validated["values"].values())
    assert state["face"]["denoise"]==.15 and state["breast"]["denoise"]==.45 and state["pussy"]["denoise"]==.5


@pytest.mark.parametrize("schedule", ["flux2","krea2"])
@pytest.mark.parametrize("denoise", [.15,.5,1])
def test_resolution_schedule_reference(schedule, denoise):
    from comfy_extras.nodes_flux import Flux2Scheduler
    s = dict(config.DEFAULTS["face"], steps=4, denoise=denoise, scheduler=schedule, sampler_name="euler")
    latent={"samples":torch.zeros(1,128 if schedule=="flux2" else 16,64,96)}
    total, tail=p.crop_sigmas(None,s,latent)
    n=int(4/denoise)
    if schedule=="flux2": reference=Flux2Scheduler.execute(n,96*16,64*16)[0]
    else:
        mu=.5+(64*96/4-256)*.65/6144
        t=torch.linspace(1,1/n,n)
        reference=torch.cat((np.exp(mu)/(np.exp(mu)+(1/t-1)),torch.zeros(1)))
    assert torch.allclose(total,reference,atol=1e-6)
    assert len(tail)==5 and tail[-1]==0 and torch.isfinite(tail).all()
    assert torch.all(tail[:-1]>tail[1:])
    other,_=p.crop_sigmas(None,s,{"samples":torch.zeros(1,16,32,32)})
    assert not torch.equal(other,total)


def test_mismatch_does_not_change_model():
    inner=type("SDXL",(),{})()
    model=SimpleNamespace(model=inner)
    assert presets.mismatch(model,"flux")
    assert presets.mismatch(model,"sdxl") is None
    assert presets.mismatch(model,"custom") is None
    assert model.model is inner


def test_routes_validate_origin_and_library_requests(monkeypatch,tmp_path):
    import asyncio
    import detailer_x
    from aiohttp import web
    instance=SimpleNamespace(routes=web.RouteTableDef(),add_on_prompt_handler=lambda handler:None)
    monkeypatch.setitem(sys.modules,"server",SimpleNamespace(PromptServer=SimpleNamespace(instance=instance)))
    monkeypatch.setattr(presets,"LIBRARY",tmp_path/"presets.json")
    monkeypatch.setattr(detailer_x.assets,"inventory",lambda kind,**kwargs:[])
    detailer_x.register_routes()
    post=next(route.handler for route in instance.routes if route.path.endswith('/presets') and route.method=="POST")
    get=next(route.handler for route in instance.routes if route.path.endswith('/config') and route.method=="GET")
    async def exercise():
        payload={"preset":config.BUILTINS["sdxl"],"expected_revision":1}
        async def read():return json.dumps(payload).encode()
        request=SimpleNamespace(headers={"Origin":"http://localhost:8188"},host="localhost:8188",read=read)
        result=await post(request)
        assert result.status==200 and json.loads(result.body)["revision"]==2
        result=await post(request)
        assert result.status==400 and "another editor" in json.loads(result.body)["error"]
        request.headers={"Origin":"https://other.example"}
        with pytest.raises(web.HTTPForbidden):await post(request)
        metadata=json.loads((await get(None)).body)
        assert metadata["defaults"]["version"]==8
        assert {"flux2","krea2"} <= set(metadata["schedulers"])
        assert len(metadata["presets"])==12
    asyncio.run(exercise())


def test_profile_metadata_not_processing_cache_key():
    from detailer_x.cache import digest
    a=copy.deepcopy(config.DEFAULTS);b=copy.deepcopy(a)
    b["preset"]["label"]="Renamed";b["preset"]["revision"]+=1
    assert all(digest(a[n])==digest(b[n]) for n in config.DETAILERS)
    b["face"]["cfg"]+=1
    assert digest(a["face"])!=digest(b["face"])
    c=copy.deepcopy(a);c["face"]["negative_prompt"]="local negative"
    assert digest(a["face"])!=digest(c["face"])
