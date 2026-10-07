"""Ultralytics sidecar parsing and concept-oriented DetailerX catalog."""
from __future__ import annotations

import re
from pathlib import Path

from . import assets

_ALIASES = {
    "eyes": "eye", "feet": "foot", "tits": "breast", "nipple": "nipple",
    "pussy": "pussy", "vagina": "pussy", "vulva": "pussy", "booty": "ass",
    "asshole": "anus", "bush": "pubic_hair", "female_pubic_hair": "pubic_hair",
    "tounge_out": "tongue", "tongue_out": "tongue", "make_love": "sex",
    "upper_clothes": "upper_clothing", "lower_clothes": "lower_clothing",
}
_LABELS = {
    "pubic_hair": "Pubic hair", "upper_clothing": "Upper clothing",
    "lower_clothing": "Lower clothing", "make_love": "Sex scene",
}
_GROUPS = {
    "face": "Anatomy & features", "eye": "Anatomy & features", "hair": "Anatomy & features",
    "lips": "Anatomy & features", "teeth": "Anatomy & features", "hand": "Anatomy & features",
    "foot": "Anatomy & features", "nail": "Anatomy & features", "belly": "Anatomy & features",
    "breast": "Anatomy & features", "nipple": "Anatomy & features", "pussy": "Anatomy & features",
    "penis": "Anatomy & features", "anus": "Anatomy & features", "ass": "Anatomy & features",
    "pubic_hair": "Anatomy & features", "skin": "Whole subject & skin", "person": "Whole subject & skin",
    "bikini": "Clothing & accessories", "dress": "Clothing & accessories",
    "footwear": "Clothing & accessories", "heels": "Clothing & accessories",
    "glasses": "Clothing & accessories", "lingerie": "Clothing & accessories",
    "underwear": "Clothing & accessories", "stockings": "Clothing & accessories",
    "upper_clothing": "Clothing & accessories", "lower_clothing": "Clothing & accessories",
}
_PROMPTS = {
    "face": "detailed realistic face, natural eyes, nose, lips, ears, eyebrows and eyelashes",
    "eye": "detailed realistic eyes, matching irises, natural eyelashes and catchlights",
    "hair": "detailed realistic hair strands, natural hair texture and clean hairline",
    "hand": "detailed realistic hands and fingers, defined natural fingernails",
    "foot": "detailed realistic feet, toes and toenails",
    "breast": "detailed realistic breast, areola and nipple texture",
    "nipple": "detailed realistic nipple and areola texture",
    "pussy": "detailed realistic vagina and labia, anatomically correct pussy",
    "penis": "detailed realistic penis, anatomically correct skin texture",
    "anus": "detailed realistic anus, anatomically correct skin texture",
    "ass": "detailed realistic buttocks, natural skin texture",
    "skin": "detailed realistic natural skin texture and pores",
    "lips": "detailed realistic lips, natural texture and clean contours", "teeth": "detailed natural teeth and gums, clean realistic enamel",
    "nail": "detailed natural fingernails, clean edges and realistic texture", "areola": "detailed realistic areola texture and natural skin transition",
    "belly_seg": "detailed realistic abdomen, natural skin folds and navel", "pubic_hair": "detailed natural pubic hair strands and skin transition",
    "person": "detailed coherent person, natural anatomy, clothing and skin texture",
    "bikini": "detailed realistic bikini fabric, seams and fit", "dress": "detailed realistic dress fabric, seams, folds and construction",
    "footwear": "detailed realistic footwear, materials, laces, soles and edges", "heels": "detailed realistic high heels, materials, straps and soles",
    "glasses": "detailed realistic glasses frames, lenses and reflections", "lingerie": "detailed realistic lingerie fabric, lace, seams and fit",
    "leather_lingerie": "detailed realistic leather lingerie, grain, stitching and reflections", "underwear": "detailed realistic underwear fabric, seams and fit",
    "stockings": "detailed realistic stockings, weave, edges and skin transition", "upper_clothing": "detailed realistic upper clothing fabric, seams and folds",
    "lower_clothing": "detailed realistic lower clothing fabric, seams and folds", "shorts": "detailed realistic shorts fabric, seams and folds",
    "skirt": "detailed realistic skirt fabric, pleats, seams and folds", "trousers": "detailed realistic trousers fabric, seams and folds",
    "vest": "detailed realistic vest fabric, seams and fit", "vest_dress": "detailed realistic vest dress fabric, seams and folds",
    "sling": "detailed realistic sling garment, straps, seams and fit", "sling_dress": "detailed realistic sling dress, straps, seams and folds",
    "long_sleeved_dress": "detailed realistic long-sleeved dress, fabric, seams and folds", "short_sleeved_dress": "detailed realistic short-sleeved dress, fabric, seams and folds",
    "long_sleeved_outwear": "detailed realistic long-sleeved outerwear, fabric, seams and folds", "short_sleeved_outwear": "detailed realistic short-sleeved outerwear, fabric, seams and folds",
    "long_sleeved_shirt": "detailed realistic long-sleeved shirt, fabric, seams and folds", "short_sleeved_shirt": "detailed realistic short-sleeved shirt, fabric, seams and folds",
    "chains": "detailed realistic chains, metal links and reflections", "chocker": "detailed realistic choker, material, fastener and fit",
    "rope": "detailed realistic rope fibres, knots and contact shadows", "dildo": "detailed realistic dildo material, shape and highlights",
    "watermark": "clean coherent image area without watermark artifacts", "tongue": "detailed realistic tongue, mouth texture and natural shading",
    "cum": "detailed realistic fluid texture, highlights and contact", "blowjob": "coherent realistic oral sex anatomy and contact",
    "flashing_tits": "coherent realistic exposed breasts, hands, clothing and anatomy", "from_behind": "coherent realistic rear-view anatomy, pose and contact",
    "lesbian": "coherent realistic female intimacy, anatomy, pose and contact", "sex": "coherent realistic sexual anatomy, pose and contact",
    "shower": "detailed realistic shower scene, water, wet surfaces and reflections", "clothed": "detailed coherent clothing, fabric, seams and fit",
    "item": "detailed realistic selected object, clean shape, texture and edges",
}
_BUILTIN = {"face", "breast", "pussy", "hand", "foot", "hair"}
_INSPECTED = {}


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_") or "item"
    return _ALIASES.get(value, value)


def parse_sidecar(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    fields = {}
    for line in text.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip().lower().replace(" ", "_").replace("-", "_")] = value.strip()
    classes = []
    for match in re.finditer(r"\[(\d+)\]\s*([^,]+)", fields.get("classes", "")):
        classes.append({"id": int(match.group(1)), "label": match.group(2).strip()})
    return {"text": text.strip(), "fields": fields, "classes": classes}


def model_metadata(identifier: str, inspect=False) -> dict:
    path = assets.resolve(identifier, "ultralytics")
    sidecar = path.with_suffix(".txt")
    meta = parse_sidecar(sidecar) if sidecar.is_file() else {"text": "", "fields": {}, "classes": []}
    task = meta["fields"].get("impact_category") or ("segm" if "segm" in path.parts else "bbox")
    if inspect and not meta["classes"]:
        signature=(str(path),path.stat().st_size,path.stat().st_mtime_ns)
        if signature not in _INSPECTED:
            from ultralytics import YOLO
            model=YOLO(str(path));names=getattr(model,"names",{}) or {};detected=getattr(model,"task",None)
            _INSPECTED.clear();_INSPECTED[signature]={"classes":[{"id":int(i),"label":str(label)} for i,label in names.items()],"task":detected or task}
            model.to("cpu")
        meta["classes"]=_INSPECTED[signature]["classes"];task=_INSPECTED[signature]["task"]
    return {"id": identifier, "task": task, "description": meta["text"], "classes": meta["classes"]}


def build_catalog() -> dict:
    models, concepts = {}, {}
    for item in assets.inventory("ultralytics", enrich=False):
        try:
            meta = model_metadata(item["id"])
        except (FileNotFoundError, ValueError, OSError):
            meta = {"id": item["id"], "task": "unknown", "description": "", "classes": []}
        models[item["id"]] = {**item, **meta}
        for cls in meta["classes"]:
            raw = cls["label"]
            concept = _slug(raw)
            # Dedicated one-class checkpoints sometimes publish the placeholder "item".
            if concept == "item":
                stem = Path(item["id"]).stem.lower()
                concept = next((name for name in ("pussy", "penis", "breast") if name in stem), "item")
            entry = concepts.setdefault(concept, {
                "id": concept, "label": _LABELS.get(concept, concept.replace("_", " ").title()),
                "group": _GROUPS.get(concept, "Scene & objects"),
                "prompt": _PROMPTS.get(concept, f"detailed realistic {concept.replace('_', ' ')} texture and structure"),
                "mask_concept": raw.replace("_", " "), "models": [], "builtin": concept in _BUILTIN,
                "broad": _GROUPS.get(concept, "Scene & objects") == "Scene & objects",
            })
            entry["models"].append({"id": item["id"], "class_id": cls["id"], "class_label": raw, "task": meta["task"]})
    groups = ["Anatomy & features", "Clothing & accessories", "Whole subject & skin", "Scene & objects"]
    return {"groups": groups, "models": list(models.values()),
            "concepts": sorted(concepts.values(), key=lambda x: (groups.index(x["group"]), x["label"].lower()))}
