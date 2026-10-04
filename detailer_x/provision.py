"""Copy existing local weights/runtime into DetailerX; never download binaries.

Run: python -m detailer_x.provision --comfy-root /path/to/ComfyUI
Existing different files are rejected, not overwritten. Manifest is local cache.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from .assets import ROOT, ASSETS

def sha256(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(8*1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def provision(comfy):
    models=comfy/"models"
    dlss=comfy/"custom_nodes"/"ComfyUI-RH-DLSS5"
    pairs=[]
    pairs.append((comfy/'custom_nodes/ComfyUI_INSTARAW/pretrained/neural_grain/grainnet.pt',ASSETS/'neural_grain/grainnet.pt'))
    pairs.append((comfy/'custom_nodes/ComfyUI_LayerStyle/lut/BlueArchitecture.cube',ASSETS/'luts/BlueArchitecture.cube'))
    for name in ("face_yolov8m.pt","female-breast-v4.7.pt","pussyV2.pt","Hands.pt","Foot.pt"):
        pairs.append((models/"ultralytics"/"bbox"/name,ASSETS/"ultralytics"/"bbox"/name))
    for relative in ("sams/sam_vit_b_01ec64.pth","upscale_models/1x-ITF-SkinDiffDetail-Lite-v1.pth",
                     "dlss5/_nvngx.dll","dlss5/nvngx_dlss.dll","dlss5/nvngx_dlssnr.dll"):
        pairs.append((models/relative,ASSETS/relative))
    for name in ("dlss5nr_bridge.dll","dlss5nr_host.exe"):
        pairs.append((dlss/"native"/"bin"/name,ROOT/"vendor"/"dlss"/"native"/"bin"/name))
    pairs.append((dlss/"runtime"/"caller"/"nvngx.dll_comfy.dll",ASSETS/"dlss5"/"caller"/"nvngx.dll_comfy.dll"))
    manifest=[]
    for source,target in pairs:
        if not source.is_file():
            raise FileNotFoundError(f"Local source missing: {source}")
        expected=sha256(source)
        if target.exists() and sha256(target)!=expected:
            raise FileExistsError(f"Different internal asset already exists: {target}")
        if not target.exists():
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
        if sha256(target)!=expected:
            raise IOError(f"Copy verification failed: {target}")
        manifest.append(dict(source=str(source.resolve()),file=target.relative_to(ROOT).as_posix(),bytes=target.stat().st_size,sha256=expected))
    ASSETS.mkdir(parents=True,exist_ok=True)
    (ASSETS/"manifest.json").write_text(json.dumps({"version":1,"files":manifest},indent=2),encoding="utf-8")
    return manifest

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfy-root",type=Path,required=True)
    args=parser.parse_args()
    result=provision(args.comfy_root.resolve())
    print(f"Verified {len(result)} internal DetailerX assets ({sum(x['bytes'] for x in result)/1024**2:.1f} MiB)")
