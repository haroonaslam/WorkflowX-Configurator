"""Portable, versioned DetailerX configuration and editor metadata."""
import copy
import json
import math
from .advanced_config import ADVANCED, CHOICES as ADV_CHOICES, RANGES as ADV_RANGES

DETAILERS = ("face", "breast", "pussy", "hand", "foot")
LEGACY_REALISM = ("brightness", "grain", "hsv", "levels", "sharpen")
REALISM = (*LEGACY_REALISM, *ADVANCED)
ORDER = ("upscaler", *DETAILERS, *REALISM, "dlss5")
DLSS_MODES = ["1x (DLAA / native)", "1.5x (Quality)", "1.724x (Balanced)", "2x (Performance)", "3x (Ultra Performance)", "1K", "2K", "4K", "8K"]

BASE_DETAILER = dict(enabled=True, guide_size=1024, guide_size_for=False, max_size=1024,
    seed=703203187737355, seed_mode="fixed", steps=15, cfg=2.5,
    sampler_name="dpmpp_2m", scheduler="beta", guidance_mode="incoming", guidance=3.5, denoise=0.5, feather=10,
    noise_mask=True, force_inpaint=True, bbox_threshold=0.4, bbox_dilation=10,
    bbox_crop_factor=3.0, sam_detection_hint="center-1", sam_dilation=10,
    sam_threshold=0.85, sam_bbox_expansion=0, sam_mask_hint_threshold=0.7,
    sam_mask_hint_use_negative="False", drop_size=10, prompt="", prompt_mode="replace",
    cycle=1, inpaint_model=False, noise_mask_feather=20, tiled_encode=False, tiled_decode=False)

DEFAULTS = {
    "version": 3, "cache_epoch": 0, "ui": {},
    "order": list(ORDER), "visible": {name: name not in ADVANCED for name in ORDER},
    "entry": {"pause": False, "skip": False, "pause_minutes": 5.0, "wait_indefinitely": False},
    "sam": {"model": "internal:sams/sam_vit_b_01ec64.pth", "device": "Prefer GPU", "enabled": True},
    "upscaler": dict(enabled=True, model="internal:upscale_models/1x-ITF-SkinDiffDetail-Lite-v1.pth",
        mode="rescale", rescale_factor=1.5, resize_width=1024, resampling_method="bilinear", supersample=False, rounding_modulus=8),
    "brightness": dict(enabled=True, brightness=1.0, contrast=1.0, saturation=1.0),
    "grain": dict(enabled=True, grain_power=0.08, grain_scale=1.0, grain_sat=1.0, seed=0, seed_mode="time"),
    "hsv": dict(enabled=True, H=0, S=-10, V=0),
    "levels": dict(enabled=True, channel="RGB", black_point=0, white_point=249, gray_point=1.0, output_black_point=0, output_white_point=253),
    "sharpen": dict(enabled=True, iterations=1, kernel_size=3),
    "dlss5": dict(enabled=True, upscaling_mode=DLSS_MODES[0], style="default", preset=0,
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
    DEFAULTS[name] = dict(BASE_DETAILER, detector="internal:ultralytics/bbox/" + detector, prompt=prompt)
for name, seed, denoise in (("face", 674025021604975, 0.15), ("breast", 1077858824591479, 0.45)):
    DEFAULTS[name].update(seed=seed, denoise=denoise, cfg=2.0, feather=15,
        bbox_threshold=0.5, bbox_dilation=15, bbox_crop_factor=2.5, sam_threshold=0.93)

CHOICES = {
    "guidance_mode": ["incoming", "set", "disabled"],
    "prompt_mode": ["replace", "incoming", "concat"], "seed_mode": ["fixed", "random"],
    "mode": ["rescale", "resize"], "resampling_method": ["nearest", "bilinear", "bicubic", "lanczos"],
    "sam_detection_hint": ["center-1", "horizontal-2", "vertical-2", "rect-4", "diamond-4", "mask-area", "mask-points", "mask-point-bbox", "none"],
    "sam_mask_hint_use_negative": ["False", "Small", "Outter"],
    "device": ["Prefer GPU", "CPU", "AUTO"], "channel": ["RGB", "red", "green", "blue"],
    "upscaling_mode": DLSS_MODES, "style": ["default", "natural", "cinematic", "off (bypass NR)"],
    "auto_mask": ["on", "off"], "motion": ["auto", "nvof", "optical_flow", "none"],
    "batch_mode": ["temporal sequence", "still images"], "backend": ["auto", "windows-bridge", "linux-wine"],
    "channel_order": ["auto", "RGBA", "BGRA"], "hdr": ["off", "on"],
}
RANGES = {
    "guidance": (0, 100, 0.1),
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
    "preset": (0, 9, 1), "intensity": (0, 2, 0.05), "tone": (0, 2, 0.05), "structure": (0, 2, 0.05),
    "skin": (-1, 2, 0.05), "global_tone": (-1, 2, 0.05), "detail": (0, 2, 0.05), "color": (0, 1, 0.05),
    "scene_change_threshold": (0.01, 1, 0.01), "warmup_frames": (0, 120, 1), "cache_epoch": (0, 9007199254740991, 1),
}

CHOICES.update(ADV_CHOICES)
RANGES.update(ADV_RANGES)

def choices_for(section, key):
    if section == "grain" and key == "seed_mode":
        return ["time", "fixed"]
    return CHOICES.get(key)

from .presets import builtins, values, validate_profile
BUILTINS = builtins(DEFAULTS)
DEFAULTS["preset"] = copy.deepcopy(BUILTINS["qwen21"])


def normalize(value, _preset=True):
    if isinstance(value, str):
        value = json.loads(value or "{}")
    if not isinstance(value, dict):
        raise ValueError("DetailerX settings must be a JSON object")
    if value.get("version", 1) not in (1, 2, 3):
        raise ValueError("Unsupported DetailerX settings version; update WorkflowX")
    result = copy.deepcopy(DEFAULTS)
    for section, default in DEFAULTS.items():
        if section in ("version", "preset", "order", "visible"):
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
            else:
                valid = isinstance(v, str)
            if not valid:
                raise ValueError(f"Invalid DetailerX {section}.{key}")
            result[section][key] = int(v) if type(fallback) is int else v
    order = value.get('order', list(ORDER))
    if not isinstance(order, list) or len(order)!=len(ORDER) or any(not isinstance(n,str) for n in order) or set(order)!=set(ORDER):
        raise ValueError('DetailerX order must contain every processor exactly once')
    result['order'] = list(order)
    visible = value.get('visible', DEFAULTS['visible'])
    if not isinstance(visible, dict) or any(k not in ORDER or type(v) is not bool for k,v in visible.items()):
        raise ValueError('Invalid DetailerX processor visibility')
    result['visible'].update(visible)
    if value.get('version',1)<3 and not value.get('realism',{}).get('enabled',True):
        for name in LEGACY_REALISM: result[name]['enabled']=False
    for name in ORDER:
        if not result['visible'][name]: result[name]['enabled']=False
    if result['lens']['blur_intensity'] % 2:
        raise ValueError('Lens blur intensity must be even')
    if _preset:
        supplied = value.get("preset")
        if supplied is not None:
            result["preset"] = validate_profile(supplied)
        elif values(result) != BUILTINS["qwen21"]["values"]:
            result["preset"] = dict(id="legacy", label="Legacy — Modified settings", family="custom", revision=1, values=values(result))
    return result
