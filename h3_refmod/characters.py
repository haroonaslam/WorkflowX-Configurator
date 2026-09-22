"""Portable character manifests; no model imports are needed for browsing."""
import json
import os
import re
import tempfile
import uuid
from pathlib import Path
from safetensors import safe_open

SUFFIX = '.character.json'
PREVIEWS = ('.png', '.jpg', '.jpeg', '.webp')

def roots():
    import folder_paths
    paths = folder_paths.get_folder_paths('refmods') if 'refmods' in folder_paths.folder_names_and_paths else []
    return list(dict.fromkeys(Path(p).resolve() for p in paths + [str(Path(folder_paths.models_dir) / 'refmods')]))

def safe_path(value, must_exist=True):
    from .bundles import split_entry
    p = Path(split_entry(value)[0]).resolve()
    if not any(p.is_relative_to(r) for r in roots()):
        raise ValueError('Select a file inside a registered refmods folder.')
    if must_exist and not p.exists():
        raise ValueError(f'File or folder not found: {p.name}')
    return p

def alias_value(value):
    value = value.strip().lstrip('@').lower()
    if not re.fullmatch(r'[a-z0-9_-]+', value):
        raise ValueError('Prompt alias must contain letters, digits, underscores or hyphens.')
    return value

def suggested_alias(name):
    return re.sub(r'[^a-z0-9_-]+', '_', name.lower()).strip('_') or 'character'

def metadata(path):
    from .bundles import split_entry, header
    path,index=split_entry(path); bundle=header(path)
    if bundle:
        return bundle['entries'][index or 0]['meta']
    with safe_open(str(path), framework='pt', device='cpu') as f:
        raw = (f.metadata() or {}).get('refmod_meta')
        if not raw:
            sidecar = Path(path).with_suffix('.json')
            if not sidecar.exists():
                raise ValueError(f'{Path(path).name} is not a RefMod.')
            return json.loads(sidecar.read_text(encoding='utf-8'))
        return json.loads(raw)

def preview_for(stem):
    return next((str(Path(str(stem) + ext)) for ext in PREVIEWS if Path(str(stem) + ext).is_file()), '')

def legacy(path):
    p = safe_path(path)
    if p.suffix != '.safetensors':
        raise ValueError('Select a character manifest or RefMod safetensors file.')
    from .bundles import header
    if header(p): raise ValueError('This earlier custom tensor bundle needs recreation from original media.')
    meta = metadata(p)
    stem = p.with_suffix('')
    visual, voice = [], None
    for vs, aus in (('_Video', '_Audio'), ('_visual', '_audio')):
        for suffix in (vs, aus):
            if stem.name.endswith(suffix):
                base = stem.with_name(stem.name[:-len(suffix)])
                vp, ap = Path(str(base)+vs+'.safetensors'), Path(str(base)+aus+'.safetensors')
                visual = [str(vp)] if vp.exists() else []
                voice = str(ap) if ap.exists() else None
                stem = base
                break
        else:
            continue
        break
    else:
        if meta.get('kind') == 'audio':
            voice = str(p)
        else:
            visual = [str(p)]
            # Legacy combined visual/audio files carry the voice in the same file.
            if meta.get('ref_audio_t', 0):
                voice = str(p)
    manifest = Path(str(stem) + SUFFIX)
    if manifest.exists():
        return load_character(manifest)
    return dict(version=4, external=True, character_id=str(uuid.uuid5(uuid.NAMESPACE_URL, str(stem))),
                display_name=stem.name, alias=suggested_alias(stem.name), description=meta.get('description', ''), descriptor=meta.get('descriptor', ''),
                visuals=visual, voice=voice, preview=preview_for(stem) or preview_for(p.with_suffix('')) or next((preview_for(Path(v).with_suffix('')) for v in visual if preview_for(Path(v).with_suffix(''))), ''), path=str(p), manifest_path=str(manifest))

def load_character(path):
    p = safe_path(path)
    if not str(p).endswith(SUFFIX):
        data=legacy(p)
        from .representations import catalog
        data['statistics']=statistics(data)
        data['reference_catalog']=catalog(data)
        return data
    data = json.loads(p.read_text(encoding='utf-8'))
    if data.get('version') != 4:
        # Older browser registrations wrap ordinary third-party tensors. They are
        # still External references, not old custom source/profile packages.
        from .bundles import header,split_entry
        assets=data.get('visuals',[])+data.get('voices', [data['voice']] if data.get('voice') else [])
        registration=data.get('version') in (1,2,3) and bool(assets) and not any(data.get(k) for k in ('visual_layout','profile_layout','source_ranges'))
        if registration:
            for asset in assets:
                raw,index=split_entry(asset)
                if index is not None or header(safe_path(p.parent/raw)) is not None:
                    registration=False;break
        if not registration:
            raise ValueError('Earlier custom package must be recreated from original media to use saved profiles.')
        data['version']=4;data['external']=True
    data['alias'] = alias_value(data['alias'])
    if not data.get('character_id'):
        raise ValueError('Character manifest has no character_id.')
    data['visuals'] = [str(safe_path(p.parent / x)) for x in data.get('visuals', [])]
    data['voices'] = [str(safe_path(p.parent / x)) for x in data.get('voices', [data['voice']] if data.get('voice') else [])]
    data['voice'] = data['voices'][0] if data['voices'] else None
    candidate=safe_path(p.parent/data['preview'],must_exist=False) if data.get('preview') else None
    data['preview']=str(candidate) if candidate and candidate.is_file() else preview_for(p.with_name(p.name[:-len(SUFFIX)]))
    data.update(path=str(p), manifest_path=str(p))
    validate_assets(data)
    data['statistics'] = statistics(data)
    from .representations import catalog
    data['reference_catalog']=catalog(data)
    return data

def validate_assets(data):
    if not data['visuals'] and not voice_paths(data):
        raise ValueError('A character needs an appearance or voice reference.')
    from .bundles import expand
    for p in expand(data['visuals']):
        safe_path(p)
        if metadata(p).get('kind') not in ('image', 'video'):
            raise ValueError(f'{Path(p).name} is not a visual RefMod.')
    for voice in expand(voice_paths(data)):
        safe_path(voice)
        m = metadata(voice)
        if m.get('kind') != 'audio' and not m.get('ref_audio_t', 0):
            raise ValueError('Voice reference must contain an audio latent.')

def save_details(data):
    data = dict(data)
    data['alias'] = alias_value(data['alias'])
    data['display_name'] = str(data.get('display_name', '')).strip() or data['alias']
    validate_assets(data)
    if data.get('profile_layout'):
        from .representations import catalog
        catalog(data)
    p = safe_path(data['manifest_path'], must_exist=False)
    if not str(p).endswith(SUFFIX):
        raise ValueError('Invalid manifest extension.')
    stored = {k: data.get(k, '') for k in ('character_id', 'display_name', 'alias', 'description', 'descriptor')}
    stored['version'] = 4
    stored['external']=data.get('external',False)
    if data.get('profile_layout'): stored['profile_layout']=data['profile_layout']
    stored['voices'] = [os.path.relpath(safe_path(x), p.parent).replace('\\', '/') for x in voice_paths(data)]
    stored['statistics'] = statistics(data)
    stored['source_ranges'] = data.get('source_ranges', [])
    selected_ranges=[r for r in stored['source_ranges'] if not r.get('status','').startswith('omitted')]
    for asset,source_range in zip([a for a in stored['statistics']['assets'] if a['kind']=='audio'],[r for r in selected_ranges if r['kind']=='audio']): asset['source_range']=source_range
    stored['visuals'] = [os.path.relpath(safe_path(x), p.parent).replace('\\', '/') for x in data['visuals']]
    for key in ('preview',):
        stored[key] = os.path.relpath(safe_path(data[key]), p.parent).replace('\\', '/') if data.get(key) else None
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(stored, f, indent=2, ensure_ascii=False)
            f.write('\n')
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return load_character(p)

def list_folder(path=''):
    available = [r for r in roots() if r.is_dir()]
    p = safe_path(path) if path else (available[0] if available else roots()[0])
    if not p.is_dir():
        return dict(current=str(p), roots=[str(r) for r in available], parent=None, dirs=[], entries=[], errors=[])
    entries, errors, claimed = [], [], set()
    files = sorted(p.iterdir(), key=lambda x: x.name.lower())
    for f in files:
        if f.is_file() and str(f).endswith(SUFFIX):
            try:
                c = load_character(f); entries.append(c)
                claimed.update(c['visuals']); claimed.update(voice_paths(c))
            except (ValueError, OSError, KeyError) as e:
                errors.append(f'{f.name}: {e}')
    for f in files:
        if f.is_file() and f.suffix == '.safetensors' and str(f) not in claimed:
            try:
                c = legacy(f)
                if c['manifest_path'] not in {e['manifest_path'] for e in entries}:
                    entries.append(c)
                claimed.update(c['visuals']); claimed.update(voice_paths(c))
            except (ValueError, OSError, KeyError) as e:
                errors.append(f'{f.name}: {e}')
    return dict(current=str(p), roots=[str(r) for r in available], parent=str(p.parent) if p not in roots() else None,
                dirs=[dict(name=f.name, path=str(f)) for f in files if f.is_dir() and not f.name.startswith('.') and f.name not in ('graph_presets', '__pycache__')],
                entries=entries, errors=errors)


def voice_paths(data):
    return list(data.get('voices', [data['voice']] if data.get('voice') else []))


def asset_stats(path, voice=False):
    from .bundles import split_entry, header
    p=safe_path(path); _,index=split_entry(path); bundle=header(p); meta=metadata(path)
    key='audio_latent' if voice and meta.get('kind')!='audio' else 'latent'
    if bundle: key=bundle['entries'][index or 0]['key']
    with safe_open(str(p),framework='pt',device='cpu') as f:
        if key not in f.keys(): raise ValueError(f'{p.name}: missing {key}.')
        shape=list(f.get_slice(key).get_shape())
    if voice:
        if len(shape)!=4 or shape[:3]!=[1,32,2] or shape[-1]<1: raise ValueError(f'{p.name}: invalid H3 audio shape.')
        visual,audio=0,2*shape[-1]
    else:
        if len(shape)!=5 or shape[:2]!=[1,24] or min(shape[2:])<1 or shape[3]%2 or shape[4]%2: raise ValueError(f'{p.name}: invalid H3 visual shape.')
        visual,audio=shape[2]*(shape[3]//2)*(shape[4]//2),0
    st=p.stat(); side=p.with_suffix('.json')
    return dict(file=p.name,kind='audio' if voice else meta['kind'],shape=shape,visual_tokens=visual,audio_tokens=audio,
        signature=dict(size=st.st_size,mtime_ns=st.st_mtime_ns,sidecar_mtime_ns=side.stat().st_mtime_ns if side.exists() else 0))


def statistics(data):
    from .optimization import COUNTING_VERSION
    from .bundles import expand
    assets=[asset_stats(p) for p in expand(data['visuals'])]+[asset_stats(p,True) for p in expand(voice_paths(data))]
    return dict(counting_version=COUNTING_VERSION,assets=assets,visual_tokens=sum(a['visual_tokens'] for a in assets),audio_tokens=sum(a['audio_tokens'] for a in assets),storage_only=True)


def configure_character(c,use_saved_voice=True,descriptor='',retain='',change='',visual_references='Saved combined video',reference_selection='{}'):
    from .representations import select,MODES
    from .bundles import expand
    from .optimization import visual_cost
    from .media import transfer_text
    c=dict(c);c['descriptor']=str(descriptor or c.get('descriptor','')).strip()
    selected,report=select(c,visual_references,reference_selection)
    c['selection_report']=report
    c['selected_references']=selected;c['visuals']=[e['path'] for e in selected];c['runtime_shapes']=[e['shape'] for e in selected]
    c['visual_references']=visual_references;c['reference_selection']=reference_selection
    c['voices']=expand(voice_paths(c)) if use_saved_voice else []
    use_descriptor=transfer_text(retain,change)
    c.update(use_voice=use_saved_voice,retain=retain,change=change,use_descriptor=use_descriptor,appearance_transfer='Flexible' if use_descriptor else 'Full',estimated_tokens=False)
    c['original_visual_tokens']=sum(e['tokens'] for e in selected);c['runtime_visual_tokens']=sum(e['runtime_tokens'] for e in selected)
    c.pop('runtime_combined',None)
    if selected and visual_references in (MODES[0],MODES[3]) and not c.get('external'):
        from .runtime_combined import plan
        c['runtime_combined']=plan(selected,{})
    return c
