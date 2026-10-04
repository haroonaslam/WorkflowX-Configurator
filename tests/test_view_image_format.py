import copy
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import view_image_format as v


@pytest.fixture
def env(tmp_path, monkeypatch):
    output=tmp_path/'output';temp=tmp_path/'temp';output.mkdir();temp.mkdir()
    def path(prefix,root,w,h):
        p=Path(root)/prefix
        if not p.resolve().is_relative_to(Path(root).resolve()):raise ValueError('outside output')
        p.parent.mkdir(parents=True,exist_ok=True)
        return str(p.parent),p.name,1,p.parent.relative_to(root).as_posix(),prefix
    monkeypatch.setitem(sys.modules,'folder_paths',SimpleNamespace(get_output_directory=lambda:str(output),get_temp_directory=lambda:str(temp),get_save_image_path=path))
    monkeypatch.setattr(v,'STORE',v.PreviewStore())
    monkeypatch.setattr(v,'metadata_allowed',lambda:True)
    yield output,temp
    with v.STORE.lock:
        for token in list(v.STORE.entries):v.STORE.remove(token)


@pytest.mark.parametrize('format',['png','webp','jpg'])
@pytest.mark.parametrize('channels',[1,3,4])
def test_formats_preview_and_manual(env,format,channels):
    output,temp=env;images=torch.rand(2,12,16,channels)
    workflow={'id':'old','version':.4,'nodes':[],'links':[]}
    result=v.ViewImageFormat().view(images,format=format,prompt={'seed':42},extra_pnginfo={'workflow':workflow})
    assert result['result'][0] is images
    assert not list(output.iterdir())
    for record in result['ui']['images']:
        assert record['type']=='temp'
        with Image.open(temp/record['subfolder']/record['filename']) as im:
            assert im.size==(16,12)
            assert im.format=='PNG'
            assert im.mode==('RGBA' if channels==4 else 'RGB')
    workflow['id']='edited'
    token=result['ui']['workflowx_preview_token'][0]
    options=dict(filename_prefix='saved/test',format=format,quality=84,include_metadata=True)
    saved=v.STORE.export(token,options)
    for rec in saved:
        image=output/rec['subfolder']/rec['filename']
        if format=='png':
            with Image.open(image) as im:assert json.loads(im.info['workflow'])['id']=='old'
        else:
            doc=json.loads(image.with_suffix('.json').read_text())
            assert doc['id']=='old' and doc['nodes']==[]
            assert doc['extra']['workflowx_export']['quality']==84
    again=v.STORE.export(token,options)
    assert again[0]['filename']!=saved[0]['filename']


def test_latest_owner_eviction_and_current_format(env):
    a=torch.rand(1,8,8,3);node=v.ViewImageFormat()
    first=node.view(a,session_key='one')['ui']['workflowx_preview_token'][0]
    second=node.view(a,session_key='two')['ui']['workflowx_preview_token'][0]
    third=node.view(a,session_key='one')['ui']['workflowx_preview_token'][0]
    assert first not in v.STORE.entries and second in v.STORE.entries
    assert not list(Path(env[1]/'workflowx_view_sources').glob('batch-*/99.npy'))
    saved=v.STORE.export(third,dict(filename_prefix='fresh',format='jpg',quality=70,include_metadata=False))
    assert saved[0]['filename'].endswith('.jpg')
    assert not list(env[0].rglob('*.json'))
    v.STORE.limit=a.numel()*4
    node.view(a,session_key='three')
    assert len(v.STORE.entries)==1
    with pytest.raises(ValueError,match='unavailable'):v.STORE.export(second,{})


def test_automatic_metadata_disabled_and_alpha(env,monkeypatch):
    monkeypatch.setattr(v,'metadata_allowed',lambda:False)
    result=v.ViewImageFormat().view(torch.zeros(1,8,8,4),format='jpg',save_automatically=True,extra_pnginfo={'workflow':{'nodes':[]}})
    rec=result['ui']['images'][0]
    assert rec['type']=='output' and not list(env[0].rglob('*.json'))
    with Image.open(env[0]/rec['filename']) as im:assert im.getpixel((0,0))==(255,255,255)


def test_sidecar_write_failure_cleans_pair(env,monkeypatch):
    def fail(*a,**k):raise OSError('disk full')
    monkeypatch.setattr(v.json,'dump',fail)
    with pytest.raises(OSError):v.write_batch([np.zeros((8,8,3))],format='jpg')
    assert not list(env[0].iterdir())


def test_invalid_options_api_metadata_and_collision(env):
    with pytest.raises(ValueError):v.write_batch([np.zeros((8,8,3))],filename_prefix='../escape')
    with pytest.raises(ValueError):v.write_batch([],format='gif')
    with pytest.raises(ValueError):v.write_batch([],quality=101)
    (env[0]/'ComfyUI_00001_.json').write_text('existing')
    r=v.write_batch([np.zeros((8,8,3))],format='webp',metadata={'prompt':{'node':'api'}})
    assert r[0]['filename']=='ComfyUI_00002_.webp'
    doc=json.loads((env[0]/'ComfyUI_00002_.json').read_text())
    assert not doc['extra']['workflowx_export']['ui_workflow_available']
    assert (env[0]/'ComfyUI_00001_.json').read_text()=='existing'
