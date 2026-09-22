"""One modality file per character; entries retain independent native latent shapes."""
import json
from dataclasses import fields
from safetensors import safe_open
from safetensors.torch import save_file

KEY = 'h3rc_bundle_v1'
SEP = '::h3rc_entry='

def split_entry(value):
    value=str(value)
    if SEP not in value: return value,None
    path,index=value.rsplit(SEP,1)
    if not index.isdigit(): raise ValueError('Invalid internal character entry.')
    return path,int(index)

def header(path):
    with safe_open(str(path),framework='pt',device='cpu') as f:
        raw=(f.metadata() or {}).get(KEY)
    if not raw:return None
    data=json.loads(raw)
    if data.get('version')!=1 or not data.get('entries'):raise ValueError('Unsupported or empty character tensor bundle.')
    return data

def expand(paths):
    result=[]
    for value in paths:
        path,index=split_entry(value)
        if index is not None:result.append(value);continue
        data=header(path)
        result.extend([path+SEP+str(i) for i in range(len(data['entries']))] if data else [path])
    return result

def save_bundle(mods,path):
    if len(mods)==1:return mods[0].save(str(path))
    tensors={};entries=[]
    for i,mod in enumerate(mods):
        meta={f.name:getattr(mod,f.name) for f in fields(mod) if f.name not in ('latent','audio_latent')}
        key='entry_'+str(i);tensors[key]=mod.latent.detach().cpu().contiguous().clone()
        entries.append(dict(key=key,meta=meta))
    destination=str(path)+'.safetensors'
    save_file(tensors,destination,metadata={KEY:json.dumps(dict(version=1,entries=entries))})
    return destination

def load_entry(path,index=0):
    from .vendor.py.refmod_core import H3RefMod
    data=header(path)
    if data is None:return None
    if index>=len(data['entries']):raise ValueError('Character tensor entry no longer exists.')
    entry=data['entries'][index]
    with safe_open(str(path),framework='pt',device='cpu') as f:z=f.get_tensor(entry['key']).clone()
    names={f.name for f in fields(H3RefMod)}
    meta={k:v for k,v in entry['meta'].items() if k in names and k not in ('latent','audio_latent')}
    return H3RefMod(latent=z,**meta)
