"""Asset enumeration without depending on another custom node's registration."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
KINDS = {"ultralytics": {".pt"}, "sams": {".pth", ".pt", ".safetensors"}, "upscale_models": {".pth", ".pt", ".safetensors"}, 'luts':{'.cube'}, 'neural_grain':{'.pt'}}

def roots(kind):
    import folder_paths
    values = [Path(folder_paths.models_dir) / kind]
    if kind=='luts':
        for base in folder_paths.get_folder_paths('custom_nodes'):
            for directory in Path(base).glob('*'):
                if directory.name.lower()=='comfyui_layerstyle': values.append(directory/'lut')
    for key in ([kind, "ultralytics_bbox", "ultralytics_segm"] if kind == "ultralytics" else [kind]):
        for path in folder_paths.folder_names_and_paths.get(key, ([], set()))[0]:
            path = Path(path)
            if key in ("ultralytics_bbox", "ultralytics_segm"):
                path = path.parent
            if path not in values:
                values.append(path)
    return values

def inventory(kind, enrich=True):
    found = {}
    for origin, root in [("internal", ASSETS / kind)] + [("comfy", p) for p in roots(kind)]:
        if root.is_dir():
            for path in sorted(root.rglob("*")):
                if path.is_file() and path.suffix.lower() in KINDS[kind]:
                    relative = path.relative_to(root).as_posix()
                    identifier = f"{origin}:{kind}/{relative}"
                    item={"id": identifier, "label": f"{'Internal' if origin == 'internal' else 'ComfyUI'} / {relative}"}
                    if enrich and kind=="ultralytics":
                        sidecar=path.with_suffix('.txt')
                        if sidecar.is_file(): item['description']=sidecar.read_text(encoding='utf-8',errors='replace').strip()
                    found.setdefault(identifier, item)
    return list(found.values())

def resolve(identifier, kind):
    prefix, sep, relative = identifier.partition(":")
    relative = relative.replace("\\", "/")
    if not sep or prefix not in ("internal", "comfy") or not relative.startswith(kind + "/"):
        raise ValueError(f"Invalid {kind} asset identifier: {identifier}")
    relative = Path(relative[len(kind) + 1:])
    if relative.is_absolute() or ".." in relative.parts or ":" in str(relative):
        raise ValueError("Asset path must remain inside its model folder")
    candidates = [ASSETS / kind] if prefix == "internal" else roots(kind)
    for root in candidates:
        path = (root / relative).resolve()
        if path.is_relative_to(root.resolve()) and path.is_file() and path.suffix.lower() in KINDS[kind]:
            return path
    raise FileNotFoundError(f"DetailerX asset missing: {identifier}. Restore the internal asset or choose a model in the gear panel.")

def signature(path):
    stat = path.stat()
    return str(path), stat.st_size, stat.st_mtime_ns
