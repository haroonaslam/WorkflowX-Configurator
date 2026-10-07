"""Provision verified local weights/runtime into DetailerX.

Run: python -m detailer_x.provision --comfy-root /path/to/ComfyUI
Existing different files are rejected, not overwritten. Official SAM downloads are
opt-in. The manifest is a local cache and records provenance plus verified hashes.
"""
import argparse
import hashlib
import json
import os
import shutil
import urllib.request
from pathlib import Path
from .assets import ROOT, ASSETS

OFFICIAL_SAMS = {
    "sam_vit_b_01ec64.pth": ("https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth", "ec2df62732614e57411cdcf32a23ffdf28910380d03139ee0f4fcbe91eb8c912"),
    "sam_vit_l_0b3195.pth": ("https://dl.fbaipublicfiles.com/segment_anything/sam_vit_l_0b3195.pth", "3adcc4315b642a4d2101128f611684e8734c41232a17c648ed1693702a49a622"),
    "sam_vit_h_4b8939.pth": ("https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth", "a7bf3b02f3ebf1267aba913ff637d9a2d5c33d3173bb679e46d9f338c26f262e"),
    "sam2.1_hiera_tiny.pt": ("https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt", "7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69"),
    "sam2.1_hiera_small.pt": ("https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt", "6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38"),
    "sam2.1_hiera_base_plus.pt": ("https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_base_plus.pt", "a2345aede8715ab1d5d31b4a509fb160c5a4af1970f199d9054ccfb746c004c5"),
    "sam2.1_hiera_large.pt": ("https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt", "2647878d5dfa5098f2f8649825738a9345572bae2d4350a2468587ece47dd318"),
}

def sha256(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(8*1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def _download_official_sams():
    records=[]
    for name,(url,expected) in OFFICIAL_SAMS.items():
        target=ASSETS/"sams"/name
        if target.exists():
            actual=sha256(target)
            if actual!=expected:
                raise FileExistsError(f"Existing SAM asset has the wrong SHA-256: {target}")
        else:
            target.parent.mkdir(parents=True,exist_ok=True)
            temporary=target.with_name(f".{target.name}.{os.getpid()}.part")
            try:
                with urllib.request.urlopen(url,timeout=60) as response, temporary.open("wb") as output:
                    shutil.copyfileobj(response,output,8*1024*1024)
                if sha256(temporary)!=expected:
                    raise IOError(f"Official SAM download failed SHA-256 verification: {name}")
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
        records.append(dict(source=url,file=target.relative_to(ROOT).as_posix(),bytes=target.stat().st_size,sha256=expected))
    return records


def provision(comfy, ultralytics_source=None, download_official_sams=False):
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
    if ultralytics_source:
        for kind in ("bbox","segm"):
            for source in sorted((ultralytics_source/kind).glob("*")):
                if source.suffix.lower() in (".pt",".txt"):
                    pairs.append((source,ASSETS/"ultralytics"/kind/source.name))
    manifest_path=ASSETS/"manifest.json"
    try:
        previous=json.loads(manifest_path.read_text(encoding="utf-8")).get("files",[])
    except (FileNotFoundError,json.JSONDecodeError,TypeError):
        previous=[]
    records={item.get("file"):item for item in previous if isinstance(item,dict) and item.get("file")}
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
        record=dict(source=str(source.resolve()),file=target.relative_to(ROOT).as_posix(),bytes=target.stat().st_size,sha256=expected)
        records[record["file"]]=record
    if download_official_sams:
        for record in _download_official_sams(): records[record["file"]]=record
    manifest=sorted(records.values(),key=lambda item:item["file"])
    ASSETS.mkdir(parents=True,exist_ok=True)
    temporary=manifest_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({"version":1,"files":manifest},indent=2),encoding="utf-8")
    temporary.replace(manifest_path)
    return manifest

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfy-root",type=Path,required=True)
    parser.add_argument("--ultralytics-source",type=Path,help="Optional PT/TXT catalog directory containing bbox and segm folders")
    parser.add_argument("--download-official-sams",action="store_true",help="Download and SHA-256 verify official SAM1/SAM2.1 checkpoints")
    args=parser.parse_args()
    result=provision(args.comfy_root.resolve(),args.ultralytics_source.resolve() if args.ultralytics_source else None,args.download_official_sams)
    print(f"Verified {len(result)} internal DetailerX assets ({sum(x['bytes'] for x in result)/1024**2:.1f} MiB)")
