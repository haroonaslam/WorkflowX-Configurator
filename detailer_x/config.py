"""Portable, versioned DetailerX configuration and editor metadata."""
import copy
import json
import math
import re
from .advanced_config import ADVANCED, CHOICES as ADV_CHOICES, RANGES as ADV_RANGES

OUTPUT_DETAILERS = ("face", "breast", "pussy", "hand", "foot")
DETAILERS = (*OUTPUT_DETAILERS, "hair", "anything")
LEGACY_REALISM = ("brightness", "grain", "hsv", "levels", "sharpen")
REALISM = (*LEGACY_REALISM, *ADVANCED)
ORDER = ("upscaler", *DETAILERS, *REALISM, "dlss5")
DLSS_MODES = ["1x (DLAA / native)", "1.5x (Quality)", "1.724x (Balanced)", "2x (Performance)", "3x (Ultra Performance)", "1K", "2K", "4K", "8K"]

BASE_DETAILER = dict(enabled=True, guide_size=1024, guide_size_for=False, max_size=1024,
    seed=703203187737355, seed_mode="fixed", steps=15, cfg=2.5,
    sampler_name="dpmpp_2m", scheduler="beta", guidance_mode="incoming", guidance=3.5, denoise=0.5, feather=10,
    noise_mask=True, force_inpaint=True, bbox_threshold=0.4, bbox_dilation=10,
    bbox_crop_factor=3.0, detector_proposal="native", sam_detection_hint="center-1", sam_dilation=10,
    sam_threshold=0.85, sam_bbox_expansion=0, sam_mask_hint_threshold=0.7,
    sam_mask_hint_use_negative="False", drop_size=10, prompt="", prompt_mode="replace",
    cycle=1, inpaint_model=False, noise_mask_feather=20, tiled_encode=False, tiled_decode=False,
    sam_strategy="inherit", sam_override=dict(backend="sam1",model="internal:sams/sam_vit_b_01ec64.pth",
        device="Prefer GPU",keep_model_loaded=True), sam3_constraint="bounding_box")

DEFAULTS = {
    "version": 5, "cache_epoch": 0, "ui": {}, "extra_detailers": {},
    "order": list(ORDER), "visible": {name: name not in ADVANCED for name in ORDER},
    "entry": {"pause": False, "skip": False, "pause_minutes": 5.0, "wait_indefinitely": False},
    "global_seed": {"enabled": False, "mode": "fixed", "seed": 703203187737355},
    "sam": {"backend": "sam1", "model": "internal:sams/sam_vit_b_01ec64.pth", "device": "Prefer GPU", "enabled": True,
            "keep_model_loaded": True},
    "upscaler": dict(enabled=True, model="internal:upscale_models/1x-ITF-SkinDiffDetail-Lite-v1.pth",
        mode="rescale", rescale_factor=1.5, resize_width=1024, resampling_method="bilinear", supersample=False, rounding_modulus=8),
    "brightness": dict(enabled=True, brightness=1.0, contrast=1.0, saturation=1.0),
    "grain": dict(enabled=True, grain_power=0.08, grain_scale=1.0, grain_sat=1.0, seed=0, seed_mode="time"),
    "hsv": dict(enabled=True, H=0, S=-10, V=0),
    "levels": dict(enabled=True, channel="RGB", black_point=0, white_point=249, gray_point=1.0, output_black_point=0, output_white_point=253),
    "sharpen": dict(enabled=True, iterations=1, kernel_size=3),
    "dlss5": dict(enabled=True, upscaling_mode=DLSS_MODES[0], style="default", preset=0, model_preset="Default",
        intensity=1.0, tone=1.0, structure=1.25, skin=-1.0, auto_mask="on", motion="auto",
        scene_change_threshold=0.24, batch_mode="temporal sequence", warmup_frames=0,
        backend="auto", channel_order="auto", hdr="off", global_tone=-1.0, detail=0.3, color=0.3),
}
DEFAULTS.update(copy.deepcopy(ADVANCED))
for name, detector, prompt in (
    ("face", "face_yolov8m.pt", "detailed realistic eyes, nose, lips and ears texture, detailed eyebrows and eyelashes"),
    ("breast", "female-breast-v4.7.pt", "detailed areola and nipple texture"),
    ("pussy", "pussyV2.pt", "detailed realistic vagina and labia, anatomically correct pussy"),
    ("hand", "Hands.pt", "detailed hands and fingers, defined natural fingernails"),
    ("foot", "Foot.pt", "detailed realistic feet, toes and toenails"),
):
    DEFAULTS[name] = dict(BASE_DETAILER, detector="internal:ultralytics/bbox/" + detector, prompt=prompt,label=f"{name.title()} detailer",catalog_id=name,
        class_ids=[0], class_labels=[name if name!="pussy" else "pussy"], mask_concept=name, sam3_mode="refine_detector", sam3_threshold=0.5, sam3_refine_iterations=3)
DEFAULTS["hair"] = dict(BASE_DETAILER, enabled=False, detector="internal:ultralytics/segm/hair_yolov8n-seg_60.pt",
    prompt="detailed realistic hair strands, natural hair texture and clean hairline",label="Hair detailer",catalog_id="hair",class_ids=[0], class_labels=["hair"],
    mask_concept="hair", sam3_mode="refine_detector", sam3_threshold=0.5, sam3_refine_iterations=3)
DEFAULTS["anything"] = dict(BASE_DETAILER, enabled=False, detector="", prompt="", prompt_mode="incoming",label="Anything detailer",catalog_id="anything",
    class_ids=[], class_labels=[], mask_concept="", sam3_mode="refine_detector", sam3_threshold=0.5, sam3_refine_iterations=3)
for name, seed, denoise in (("face", 674025021604975, 0.15), ("breast", 1077858824591479, 0.45)):
    DEFAULTS[name].update(seed=seed, denoise=denoise, cfg=2.0, feather=15,
        bbox_threshold=0.5, bbox_dilation=15, bbox_crop_factor=2.5, sam_threshold=0.93)
DEFAULTS["breast"].update(class_ids=[0,1],class_labels=["breast_pair","breast_single"])

CHOICES = {
    "guidance_mode": ["incoming", "set", "disabled"],
    "prompt_mode": ["replace", "incoming", "concat"], "seed_mode": ["fixed", "random"],
    "mode_seed": ["fixed", "random"], "backend_sam": ["sam1", "sam2.1", "sam3.1"],
    "sam3_mode": ["refine_detector", "concept_with_detector", "bbox_controlled", "concept_only"],
    "sam_strategy": ["inherit", "detector_only", "override"],
    "sam3_constraint": ["bounding_box", "detector_mask", "none"],
    "detector_proposal": ["native", "bbox"],
    "mode": ["rescale", "resize"], "resampling_method": ["nearest", "bilinear", "bicubic", "lanczos"],
    "sam_detection_hint": ["center-1", "horizontal-2", "vertical-2", "rect-4", "diamond-4", "mask-area", "mask-points", "mask-point-bbox", "none"],
    "sam_mask_hint_use_negative": ["False", "Small", "Outter"],
    "device": ["Prefer GPU", "CPU", "AUTO"], "channel": ["RGB", "red", "green", "blue"],
    "upscaling_mode": DLSS_MODES, "style": ["default", "natural", "cinematic", "off (bypass NR)"],
    "preset": [0, 1, 2, 3], "model_preset": ["Default", "J", "K", "L", "M"],
    "auto_mask": ["on", "off"], "motion": ["auto", "nvof", "optical_flow", "none"],
    "batch_mode": ["temporal sequence", "still images"], "backend": ["auto", "windows-bridge", "linux-wine"],
    "channel_order": ["auto", "RGBA", "BGRA"], "hdr": ["off", "on"],
}
RANGES = {
    "guidance": (0, 100, 0.1),
    "sam3_threshold": (0, 1, 0.01), "sam3_refine_iterations": (0, 10, 1),
    "pause_minutes": (0.05, 1440, 0.05),
    "guide_size": (64, 16384, 8), "max_size": (64, 16384, 8), "seed": (0, 9007199254740991, 1),
    "steps": (1, 10000, 1), "cfg": (0, 100, 0.1), "denoise": (0, 1, 0.01), "feather": (0, 100, 1),
    "bbox_threshold": (0, 1, 0.01), "bbox_dilation": (-512, 512, 1), "bbox_crop_factor": (1, 10, 0.1),
    "sam_dilation": (-512, 512, 1), "sam_threshold": (0, 1, 0.01), "sam_bbox_expansion": (0, 1000, 1),
    "sam_mask_hint_threshold": (0, 1, 0.01), "drop_size": (1, 16384, 1), "cycle": (1, 10, 1), "noise_mask_feather": (0, 100, 1),
    "rescale_factor": (0.01, 16, 0.01), "resize_width": (1, 48000, 1), "rounding_modulus": (8, 1024, 8),
    "brightness": (0, 3, 0.01), "contrast": (0, 3, 0.01), "saturation": (0, 3, 0.01),
    "grain_power": (0, 1, 0.01), "grain_scale": (0.1, 10, 0.1), "grain_sat": (0, 1, 0.01),
    "H": (-255, 255, 1), "S": (-255, 255, 1), "V": (-255, 255, 1),
    "black_point": (0, 255, 1), "white_point": (0, 255, 1), "gray_point": (0.01, 9.99, 0.01),
    "output_black_point": (0, 255, 1), "output_white_point": (0, 255, 1), "iterations": (1, 12, 1), "kernel_size": (1, 16, 1),
    "intensity": (0, 2, 0.05), "tone": (0, 2, 0.05), "structure": (0, 2, 0.05),
    "skin": (-1, 2, 0.05), "global_tone": (-1, 2, 0.05), "detail": (0, 2, 0.05), "color": (0, 1, 0.05),
    "scene_change_threshold": (0.01, 1, 0.01), "warmup_frames": (0, 120, 1), "cache_epoch": (0, 9007199254740991, 1),
}

CHOICES.update(ADV_CHOICES)
RANGES.update(ADV_RANGES)

def choices_for(section, key):
    if section == "grain" and key == "seed_mode":
        return ["time", "fixed"]
    if section == "sam" and key == "backend": return CHOICES["backend_sam"]
    if section == "global_seed" and key == "mode": return CHOICES["mode_seed"]
    return CHOICES.get(key)

from .presets import builtins, values, validate_profile
BUILTINS = builtins(DEFAULTS)
DEFAULTS["preset"] = copy.deepcopy(BUILTINS["qwen21"])


def normalize(value, _preset=True):
    if isinstance(value, str):
        value = json.loads(value or "{}")
    if not isinstance(value, dict):
        raise ValueError("DetailerX settings must be a JSON object")
    source_version=value.get("version", 1)
    if source_version not in (1, 2, 3, 4, 5):
        raise ValueError("Unsupported DetailerX settings version; update WorkflowX")
    result = copy.deepcopy(DEFAULTS)
    for section, default in DEFAULTS.items():
        if section in ("version", "preset", "order", "visible", "extra_detailers"):
            continue
        supplied = value.get(section, default)
        if not isinstance(default, dict):
            if type(supplied) is not int or supplied < 0:
                raise ValueError(f"Invalid {section}")
            result[section] = supplied
            continue
        if not isinstance(supplied, dict):
            raise ValueError(f"Invalid {section} settings")
        for key, fallback in default.items():
            v = supplied.get(key, fallback)
            # Early DetailerX builds exposed undocumented numeric NR preset
            # values 4-9. Current runtimes document only Default/#1/#2/#3;
            # migrate those old selections to the safe runtime default.
            if section == "dlss5" and key == "preset" and type(v) is int and 4 <= v <= 9:
                v = 0
            if key == "sam_override":
                if not isinstance(v,dict): raise ValueError(f"Invalid DetailerX {section}.sam_override")
                override=copy.deepcopy(fallback)
                for override_key,override_fallback in fallback.items():
                    candidate=v.get(override_key,override_fallback)
                    options=choices_for("sam",override_key)
                    valid=(candidate in options) if options else (type(candidate) is bool if isinstance(override_fallback,bool) else isinstance(candidate,str))
                    if not valid: raise ValueError(f"Invalid DetailerX {section}.sam_override.{override_key}")
                    override[override_key]=candidate
                result[section][key]=override
                continue
            options = choices_for(section, key)
            if options and v not in options:
                raise ValueError(f"{section}.{key}: choose one of {options}")
            if isinstance(fallback, bool):
                valid = type(v) is bool
            elif isinstance(fallback, (int, float)):
                valid = type(v) in (int, float) and math.isfinite(v)
                if isinstance(fallback, int):
                    valid = valid and int(v) == v
                if key in RANGES:
                    lo, hi, _ = RANGES[key]
                    valid = valid and lo <= v <= hi
            elif isinstance(fallback, list):
                valid = isinstance(v, list) and all(isinstance(x, (str, int)) and not isinstance(x, bool) for x in v)
            else:
                valid = isinstance(v, str)
            if not valid:
                raise ValueError(f"Invalid DetailerX {section}.{key}")
            result[section][key] = int(v) if type(fallback) is int else v
    extras=value.get('extra_detailers',{})
    custom_id=r'detailer:custom:[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89aAbB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}'
    catalog_id=r'detailer:[a-z0-9][a-z0-9_]{0,79}'
    if not isinstance(extras,dict) or any(not isinstance(k,str) or not re.fullmatch(f'(?:{custom_id}|{catalog_id})',k) or not isinstance(v,dict) for k,v in extras.items()):
        raise ValueError('Invalid DetailerX additional detailers')
    result['extra_detailers']={}
    for stage,supplied in extras.items():
        template=copy.deepcopy(DEFAULTS['anything']);merged=copy.deepcopy(template)
        merged.update(mask_concept=stage.split(':',1)[1].replace('_',' '),label=stage.split(':',1)[1].replace('_',' ').title(),catalog_id=stage.split(':',1)[1])
        for key,fallback in template.items():
            v=supplied.get(key,merged[key]);options=choices_for(stage,key)
            if key=='sam_override':
                if not isinstance(v,dict): raise ValueError(f'Invalid DetailerX {stage}.sam_override')
                override=copy.deepcopy(fallback)
                for override_key,override_fallback in fallback.items():
                    candidate=v.get(override_key,override_fallback);override_options=choices_for('sam',override_key)
                    valid=(candidate in override_options) if override_options else (type(candidate) is bool if isinstance(override_fallback,bool) else isinstance(candidate,str))
                    if not valid: raise ValueError(f'Invalid DetailerX {stage}.sam_override.{override_key}')
                    override[override_key]=candidate
                merged[key]=override
                continue
            if options and v not in options: raise ValueError(f'{stage}.{key}: choose one of {options}')
            if isinstance(fallback,bool): valid=type(v) is bool
            elif isinstance(fallback,(int,float)):
                valid=type(v) in (int,float) and math.isfinite(v) and (not isinstance(fallback,int) or int(v)==v)
                if key in RANGES: valid=valid and RANGES[key][0]<=v<=RANGES[key][1]
            elif isinstance(fallback,list): valid=isinstance(v,list) and all(isinstance(x,(str,int)) and not isinstance(x,bool) for x in v)
            else: valid=isinstance(v,str)
            if not valid: raise ValueError(f'Invalid DetailerX {stage}.{key}')
            merged[key]=int(v) if type(fallback) is int else v
        if any(type(x) is not int or x<0 for x in merged['class_ids']): raise ValueError(f'{stage}: invalid class IDs')
        if any(not isinstance(x,str) for x in merged['class_labels']) or (merged['class_labels'] and len(merged['class_labels'])!=len(merged['class_ids'])): raise ValueError(f'{stage}: invalid class labels')
        if not merged['label'].strip() or len(merged['label'])>120: raise ValueError(f'{stage}: label must contain 1–120 characters')
        result['extra_detailers'][stage]=merged
    order=value.get('order', list(ORDER))
    if source_version<4:
        order=[n for n in order if n in ORDER]
        insert=order.index('foot')+1 if 'foot' in order else len(order)
        for name in reversed(('hair','anything')):
            if name not in order: order.insert(insert,name)
    expected=set(ORDER)|set(result['extra_detailers'])
    if not isinstance(order,list) or len(order)!=len(expected) or any(not isinstance(n,str) for n in order) or set(order)!=expected:
        raise ValueError('DetailerX order must contain every processor exactly once')
    result['order'] = list(order)
    visible = value.get('visible', DEFAULTS['visible'])
    if not isinstance(visible, dict) or any(k not in expected or type(v) is not bool for k,v in visible.items()):
        raise ValueError('Invalid DetailerX processor visibility')
    result['visible'].update(visible)
    if value.get('version',1)<3 and not value.get('realism',{}).get('enabled',True):
        for name in LEGACY_REALISM: result[name]['enabled']=False
    result['visible'].update({name:False for name in result['extra_detailers'] if name not in result['visible']})
    for name in DETAILERS:
        if any(type(x) is not int or x<0 for x in result[name]['class_ids']): raise ValueError(f'{name}: invalid class IDs')
        if any(not isinstance(x,str) for x in result[name]['class_labels']) or (result[name]['class_labels'] and len(result[name]['class_labels'])!=len(result[name]['class_ids'])): raise ValueError(f'{name}: invalid class labels')
    for name in expected:
        target=result['extra_detailers'][name] if name.startswith('detailer:') else result[name]
        if not result['visible'].get(name,False): target['enabled']=False
    if result['lens']['blur_intensity'] % 2:
        raise ValueError('Lens blur intensity must be even')
    if _preset:
        supplied = value.get("preset")
        if supplied is not None:
            result["preset"] = validate_profile(supplied)
        elif values(result) != BUILTINS["qwen21"]["values"]:
            result["preset"] = dict(id="legacy", label="Legacy — Modified settings", family="custom", revision=1, values=values(result))
    return result


def effective_sam(settings,stage):
    """Resolve an immutable SAM snapshot for one detailer."""
    strategy=stage.get("sam_strategy","inherit")
    if strategy=="detector_only":
        value=copy.deepcopy(settings["sam"]);value["enabled"]=False;value["source"]="detector_only"
    elif strategy=="override":
        value=copy.deepcopy(stage["sam_override"]);value["enabled"]=True;value["source"]="override"
    else:
        value=copy.deepcopy(settings["sam"]);value["source"]="global"
    return value
