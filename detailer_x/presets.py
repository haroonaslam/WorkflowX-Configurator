"""Portable sampling presets. Local library files are never required for execution."""
import copy
import json
import os
from pathlib import Path
import re
import tempfile
import threading

FIELDS = ("steps", "cfg", "guidance_mode", "guidance", "sampler_name", "scheduler",
          "denoise", "guide_size", "guide_size_for", "max_size", "cycle")
FAMILIES = ("sdxl", "qwen", "flux", "klein", "zimage", "krea2", "custom")
LIBRARY = Path(__file__).parent / "local" / "presets.json"
LOCK = threading.RLock()


def values(settings):
    from .config import DETAILERS
    return {name: {key: copy.deepcopy(settings[name][key]) for key in FIELDS} for name in DETAILERS}


def builtins(defaults):
    profiles = {}
    def add(id, label, family, **changes):
        data = values(defaults)
        for stage in data.values():
            stage.update(changes)
        profiles[id] = dict(id=id, label=label, family=family, revision=1, values=data)
    add("qwen21", "Qwen 2.1", "qwen")
    add("sdxl", "SDXL — Standard", "sdxl", steps=20, cfg=5.0, scheduler="karras")
    add("flux-dev", "FLUX.1 — Dev", "flux", steps=20, cfg=1.0, sampler_name="euler", scheduler="simple", guidance_mode="set", guidance=3.5)
    add("flux-schnell", "FLUX.1 — Schnell", "flux", steps=4, cfg=1.0, sampler_name="euler", scheduler="simple", guidance_mode="disabled")
    for size in ("4B", "9B"):
        for variant, steps, cfg in (("Base", 20, 5.0), ("Distilled", 4, 1.0)):
            add(f"klein-{size.lower()}-{variant.lower()}", f"FLUX.2 Klein — {size} {variant}", "klein", steps=steps, cfg=cfg, sampler_name="euler", scheduler="flux2", guidance_mode="disabled")
    for variant, steps, cfg in (("Base",25,4.0), ("Turbo",8,1.0)):
        add(f"zimage-{variant.lower()}", f"Z-Image — {variant}", "zimage", steps=steps, cfg=cfg, sampler_name="res_multistep", scheduler="simple")
    add("krea2-raw", "Krea 2 — Raw", "krea2", steps=52, cfg=4.5, sampler_name="euler", scheduler="krea2")
    add("krea2-turbo", "Krea 2 — Turbo", "krea2", steps=8, cfg=1.0, sampler_name="euler", scheduler="simple")
    return profiles


def snapshot(profile):
    return copy.deepcopy(profile)


def validate_profile(profile):
    from .config import DETAILERS, normalize
    if not isinstance(profile, dict):
        raise ValueError("Preset must be an object")
    id = profile.get("id", "")
    label = profile.get("label", "")
    if id == "qwen21" and label == "Qwen 2.1 — Current workflow":
        label = "Qwen 2.1"
    revision = profile.get("revision", 1)
    if not isinstance(id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", id):
        raise ValueError("Invalid preset identifier")
    if not isinstance(label, str) or not label.strip() or len(label) > 120:
        raise ValueError("Preset name must contain 1–120 characters")
    if profile.get("family") not in FAMILIES:
        raise ValueError("Invalid preset family")
    if type(revision) is not int or revision < 1:
        raise ValueError("Invalid preset revision")
    data = profile.get("values")
    if not isinstance(data, dict) or set(data) != set(DETAILERS):
        raise ValueError("Preset must contain all five detailers")
    for name in DETAILERS:
        if not isinstance(data[name], dict) or set(data[name]) != set(FIELDS):
            raise ValueError(f"Preset {name}: incomplete sampling settings")
    # Reuse backend processing validation without recursively validating a preset.
    normalized = normalize({**data, "version": 2}, _preset=False)
    for name in DETAILERS:
        if not re.fullmatch(r"[a-zA-Z0-9_]+", normalized[name]["sampler_name"]) or not re.fullmatch(r"[a-zA-Z0-9_]+", normalized[name]["scheduler"]):
            raise ValueError("Invalid sampler or schedule identifier")
    return dict(id=id, label=label.strip(), family=profile["family"], revision=revision, values=values(normalized))


def library(path=None):
    from .config import BUILTINS
    result = copy.deepcopy(BUILTINS)
    path = Path(path or LIBRARY)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("version") != 1 or not isinstance(data.get("presets"), list):
            raise ValueError("Invalid DetailerX preset library; restore its backup or repair the JSON")
        for profile in data["presets"]:
            item = validate_profile(profile)
            result[item["id"]] = item
    return result


def save(profile, expected_revision=None, path=None):
    path = Path(path or LIBRARY)
    item = validate_profile(profile)
    with LOCK:
        all_profiles = library(path)
        existing = all_profiles.get(item["id"])
        if expected_revision is not None and expected_revision != (existing["revision"] if existing else 0):
            raise ValueError("Preset changed in another editor. Reopen the preset selector before saving.")
        item["revision"] = (existing["revision"] if existing else 0) + 1
        all_profiles[item["id"]] = item
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix="presets-", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(dict(version=1, presets=list(all_profiles.values())), stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return item


def mismatch(model, family):
    """Warn only when architecture is identifiable; never replace the model."""
    inner = getattr(model, "model", None)
    name = type(inner).__name__.lower()
    detected = next((value for token, value in (("flux2", "klein"), ("qwenimage", "qwen"), ("flux", "flux"), ("krea2", "krea2"), ("sdxl", "sdxl")) if token in name), None)
    config = getattr(getattr(inner, "model_config", None), "unet_config", {})
    if name == "lumina2" and config.get("dim") == 3840:
        detected = "zimage"
    return f"Preset family {family} does not match detected model family {detected}; connect a matching MODEL/CLIP/VAE or select another preset." if detected and family not in (detected, "custom") else None
