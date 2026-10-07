import copy
import sys
from pathlib import Path
import numpy as np
import pytest
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import detailer_x as dx
from detailer_x import config, advanced_processing as ap, processing
from detailer_x.cache import CACHE

def settings():
    s=copy.deepcopy(config.DEFAULTS)
    for n in config.ORDER:s[n]['enabled']=False
    return s

def test_migration_hidden_and_validation():
    old={'version':2,'realism':{'enabled':False},'ui':{'realism_collapsed':True}}
    s=config.normalize(old)
    assert s['version']==5
    assert all(not s[n]['enabled'] and s['visible'][n] for n in config.LEGACY_REALISM)
    assert all(not s['visible'][n] for n in config.ADVANCED)
    s['gamma']['enabled']=True
    assert not config.normalize(s)['gamma']['enabled']
    s['order'][0]=s['order'][1]
    with pytest.raises(ValueError,match='order'):config.normalize(s)

def test_order_outputs_cache_and_visibility(monkeypatch):
    CACHE.clear();calls=[]
    monkeypatch.setattr(dx,'status',lambda *a:None)
    monkeypatch.setattr(dx,'asset_signatures',lambda s:{})
    monkeypatch.setattr(processing,'cancelled',lambda:None)
    monkeypatch.setattr(processing,'upscale',lambda im,s:im+1)
    monkeypatch.setattr(processing,'dlss',lambda im,s:im+10)
    def fake(im,n,s):calls.append(n);return im+100
    monkeypatch.setattr(ap,'process',fake)
    s=settings()
    for n in ['upscaler','dlss5','gamma']:s[n]['enabled']=True;s['visible'][n]=True
    s['order'].remove('gamma');s['order'].append('gamma')
    image=torch.zeros(2,3,5,4)
    run=lambda:dx.DetailerX().process(None,None,None,[],[],image,s)
    final,bundle,masks=run()
    assert torch.equal(final,image+111)
    assert [item['id'] for item in bundle['stages']]==['upscaler','dlss5','gamma']
    assert torch.equal(bundle['stages'][0]['image'],image+1)
    assert torch.equal(bundle['stages'][1]['image'],image+11)
    assert torch.equal(bundle['stages'][2]['image'],image+111)
    calls.clear();s['visible']['face']=False;run();assert calls==[]
    s['order'].remove('gamma');s['order'].insert(0,'gamma')
    final,bundle,masks=run();assert calls==['gamma']
    assert torch.equal(final,image+111)
    assert [item['id'] for item in bundle['stages']]==['gamma','upscaler','dlss5']
    assert torch.equal(bundle['stages'][0]['image'],image+100)
    assert torch.equal(bundle['stages'][1]['image'],image+101)

@pytest.mark.parametrize('name',list(config.ADVANCED))
def test_advanced_batch_alpha_fixed_seed(name,monkeypatch):
    monkeypatch.setattr(processing,'cancelled',lambda:None)
    s=copy.deepcopy(config.DEFAULTS[name]);s['seed']=42
    if name=='neural_grain':
        # Exercise the real network with bundled weights, on CPU.
        import comfy.model_management as mm
        monkeypatch.setattr(mm,'get_torch_device',lambda:torch.device('cpu'))
    image=torch.rand(2,16,20,4)
    a=ap.process(image,name,s);b=ap.process(image,name,s)
    assert a.shape==image.shape and torch.equal(a[...,3],image[...,3])
    assert torch.equal(a,b) and torch.isfinite(a).all()
    assert a.min()>=0 and a.max()<=1

def test_kelvin_neutral_and_direction():
    rgb=np.full((4,5,3),.5,np.float32)
    assert np.array_equal(ap.kelvin(rgb,6500),rgb)
    cool=ap.kelvin(rgb,2700);warm=ap.kelvin(rgb,9000)
    assert cool[0,0,2]>cool[0,0,0]
    assert warm[0,0,0]>warm[0,0,2]

def test_missing_new_asset_is_stage_specific():
    s=settings();s['lut'].update(enabled=True,lut='internal:luts/missing.cube');s['visible']['lut']=True
    with pytest.raises(ValueError,match='DetailerX lut'):dx.asset_signatures(s)

def load_reference(relative):
    import importlib.util
    path=Path(__file__).resolve().parents[2]/relative
    if not path.exists():pytest.skip('Installed comparison reference unavailable')
    spec=importlib.util.spec_from_file_location('dx_reference',path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

def test_camera_matches_installed_reference():
    reference=load_reference('ComfyUI_INSTARAW/modules/detection_bypass/camera_pipeline.py')
    a=np.random.default_rng(12).integers(0,256,(64,72,3),dtype=np.uint8)
    s=config.DEFAULTS['camera']
    expected=reference.simulate_camera_pipeline(a,bayer=True,jpeg_quality_range=(98,98),vignette_strength=.1,chroma_aberr_strength=1,iso_scale=1,read_noise_std=2,hot_pixel_prob=.000001,banding_strength=0,motion_blur_kernel=3,seed=42)
    assert np.array_equal(ap.camera(a,s,42),expected)

@pytest.mark.parametrize('zone',['shadows','midtones','highlights'])
def test_balance_matches_installed_reference(zone):
    ref=load_reference('ComfyUI-Image-Effects/core/color_balance_node.py')
    a=torch.rand(1,32,40,3)
    s=dict(config.DEFAULTS['color_balance'],adjust_type=zone,cyan_red=12,magenta_green=-8,yellow_blue=7)
    expected=ref.ColorBalanceNode().apply_color_balance(a,zone,12,-8,7,True)[0].numpy()[0]
    assert np.allclose(ap.balance(a.numpy()[0],s),expected,atol=1e-6)
