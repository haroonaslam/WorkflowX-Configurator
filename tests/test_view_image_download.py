import io
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import view_image_format as v
# Reuse filesystem isolation without importing the custom-node package root.
from test_view_image_format import env


@pytest.mark.parametrize('headers,host,allowed', [
    ({'Origin':'https://comfy.example','Sec-Fetch-Site':'same-origin'}, '127.0.0.1:8188', True),
    ({'Origin':'https://evil.example','Sec-Fetch-Site':'cross-site'}, 'localhost:8188', False),
    ({'Origin':'http://LOCALHOST:8188'}, 'localhost:8188', True),
    ({'Origin':'http://localhost:80'}, 'localhost', True),
    ({'Origin':'http://localhost:8189'}, 'localhost:8188', False),
    ({'Origin':'null'}, 'localhost:8188', False),
    ({'Origin':'http://localhost:bad'}, 'localhost:8188', False),
    ({'Origin':'https://evil.example','Sec-Fetch-Site':'same-site'}, 'comfy.example', False),
    ({}, 'localhost:8188', True),
])
def test_export_origin(headers, host, allowed):
    from types import SimpleNamespace
    assert v.export_origin_allowed(SimpleNamespace(headers=headers, host=host)) is allowed

def options(format,**kw):
    return dict(filename_prefix='manual',format=format,quality=91,include_metadata=True,**kw)

def test_manual_bytes_and_single_sidecar(env):
    workflow={'id':'producing-run','version':.4,'nodes':[],'links':[]}
    image=torch.rand(2,18,22,4)
    result=v.ViewImageFormat().view(image,format='jpg',extra_pnginfo={'workflow':workflow})
    token=result['ui']['workflowx_preview_token'][0]
    workflow['id']='edited'
    for format in ['jpg','webp','png']:
        content=v.download_image(token,0,options(format))
        with Image.open(io.BytesIO(content)) as im:
            assert im.format=={'jpg':'JPEG','webp':'WEBP','png':'PNG'}[format]
            assert im.size==(22,18)
            if format=='png':assert json.loads(im.info['workflow'])['id']=='producing-run'
        # Manual encoding never saves image files in ComfyUI output.
        assert not list(env[0].glob('*.jpg')) and not list(env[0].glob('*.webp'))
        sidecar=v.save_sidecar(token,options(format))
        if format!='png':
            assert len(list(env[0].glob('*.json')))==1
            if format=='jpg':first=sidecar
            else:assert first==sidecar
        else:assert sidecar is None
    doc=json.loads((env[0]/first).read_text())
    assert doc['id']=='producing-run' and doc['extra']['workflowx_export']['format']=='webp'

def test_preview_is_independent_of_format_and_quality(env):
    image=torch.rand(1,11,13,4)
    expected=(image[0].numpy()*255).astype(np.uint8)
    for format in ['png','jpg','webp']:
        result=v.ViewImageFormat().view(image,format=format,quality=1)
        rec=result['ui']['images'][0]
        with Image.open(env[1]/rec['subfolder']/rec['filename']) as im:
            assert im.format=='PNG' and np.array_equal(np.array(im),expected)
    assert not list(env[0].iterdir())

def test_auto_manual_share_generation_sidecar(env):
    result=v.ViewImageFormat().view(torch.rand(2,8,8,3),format='jpg',save_automatically=True)
    assert len(list(env[0].glob('*.jpg')))==2 and len(list(env[0].glob('*.json')))==1
    token=result['ui']['workflowx_preview_token'][0]
    old=next(env[0].glob('*.json'))
    assert v.save_sidecar(token,options('webp'))==old.name
    assert len(list(env[0].glob('*.json')))==1

def test_failed_sidecar_update_keeps_previous(env,monkeypatch):
    result=v.ViewImageFormat().view(torch.rand(1,8,8,3))
    token=result['ui']['workflowx_preview_token'][0]
    path=env[0]/v.save_sidecar(token,options('jpg'));original=path.read_bytes()
    def fail(*a,**k):raise OSError('full')
    monkeypatch.setattr(v.json,'dump',fail)
    with pytest.raises(OSError):v.save_sidecar(token,options('webp'))
    assert path.read_bytes()==original
    assert not list(env[0].glob('.view-*'))
