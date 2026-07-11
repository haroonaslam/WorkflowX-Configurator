"""Internal SAM3 segmentation.

How SAM3 works in ComfyUI core (PR Comfy-Org/ComfyUI#13408):

  1. The sam3.1 checkpoint is loaded with ``CheckpointLoaderSimple``. It supplies
     BOTH the MODEL and a CLIP -- a dedicated ``sam3_clip`` text encoder living in
     ``comfy/text_encoders/sam3_clip.py``.
  2. Text prompts go through ``CLIPTextEncode(clip, text) -> CONDITIONING``.
  3. ``SAM3_Detect(model, image, conditioning, ...) -> (MASK, BOUNDING_BOX)``

This module does all three in-process, so the node shows one textbox instead of
making you wire three nodes.

Two robustness decisions:

* We fetch ``SAM3_Detect`` from ``nodes.NODE_CLASS_MAPPINGS`` rather than
  importing ``comfy_extras.nodes_sam3``. The registry is the stable surface; the
  module path is not.
* We introspect ``SAM3_Detect.INPUT_TYPES()`` and pass only the arguments it
  actually declares. When core adds or renames a parameter, we adapt instead of
  raising TypeError, and if a *required* argument appears that we cannot supply,
  we say exactly which one.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import torch

log = logging.getLogger("anything_swap_bridge")

SELECT_MODES = ("largest", "highest_confidence", "index")

# checkpoint name -> (model, clip). Size-1: SAM3 is the only thing we load.
_CACHE: Dict[str, Tuple[Any, Any]] = {}


# -- discovery ---------------------------------------------------------------

def checkpoint_list() -> List[str]:
    """All checkpoints, SAM3-looking ones first.

    We cannot reliably identify a SAM3 checkpoint from its filename, so we sort
    rather than filter. Filtering would hide a correctly-named-but-unusual file.
    """
    try:
        import folder_paths

        names = folder_paths.get_filename_list("checkpoints")
    except Exception:  # noqa: BLE001
        return ["<no checkpoints found>"]
    if not names:
        return ["<no checkpoints found>"]
    return sorted(names, key=lambda n: (0 if "sam3" in n.lower() else 1, n.lower()))


# -- loading -----------------------------------------------------------------

def load(ckpt_name: str, keep_loaded: bool = True):
    """Return ``(model, clip)`` for a SAM3 checkpoint.

    ``model`` is a ComfyUI ModelPatcher, so ``comfy.model_management`` handles its
    VRAM residency exactly as it does for a diffusion model. That is why this
    package carries no memory policy of its own: we hand core a normal model and
    let it evict under pressure like anything else. Nothing here is tuned to a
    particular GPU.
    """
    if ckpt_name in _CACHE:
        return _CACHE[ckpt_name]

    import comfy.sd
    import folder_paths

    try:
        path = folder_paths.get_full_path_or_raise("checkpoints", ckpt_name)
    except AttributeError:  # older cores
        path = folder_paths.get_full_path("checkpoints", ckpt_name)
    if not path:
        raise FileNotFoundError(f"checkpoint {ckpt_name!r} not found in models/checkpoints")

    out = comfy.sd.load_checkpoint_guess_config(
        path,
        output_vae=False,
        output_clip=True,
        embedding_directory=folder_paths.get_folder_paths("embeddings"),
    )
    model, clip = out[0], out[1]

    if clip is None:
        raise RuntimeError(
            f"{ckpt_name!r} loaded, but it has no text encoder.\n"
            "SAM3 text prompting needs the sam3_clip encoder that ships inside the "
            "SAM3 checkpoint. Download sam3.1_multiplex_fp16.safetensors from "
            "huggingface.co/Comfy-Org/sam3.1 into ComfyUI/models/checkpoints/."
        )

    if keep_loaded:
        _CACHE.clear()  # only ever hold one
        _CACHE[ckpt_name] = (model, clip)
    return model, clip


def release(ckpt_name: str) -> None:
    """Drop our reference. Core's model management reclaims the VRAM."""
    _CACHE.pop(ckpt_name, None)
    try:
        import comfy.model_management as mm

        mm.soft_empty_cache()
    except Exception:  # noqa: BLE001
        pass


# -- text encoding -----------------------------------------------------------

def encode(clip, text: str):
    """``CLIPTextEncode`` without the node."""
    tokens = clip.tokenize(text)
    if hasattr(clip, "encode_from_tokens_scheduled"):
        return clip.encode_from_tokens_scheduled(tokens)
    cond, pooled = clip.encode_from_tokens(tokens, return_pooled=True)
    return [[cond, {"pooled_output": pooled}]]


# -- detection ---------------------------------------------------------------

def _detect_cls():
    from nodes import NODE_CLASS_MAPPINGS

    cls = NODE_CLASS_MAPPINGS.get("SAM3_Detect")
    if cls is None:
        raise RuntimeError(
            "SAM3_Detect not found in this ComfyUI. Native SAM3.1 support landed in "
            "Comfy-Org/ComfyUI#13408 -- update ComfyUI, or turn use_sam3 off and wire "
            "a MASK into the mask input instead."
        )
    return cls


def _schema(cls) -> Tuple[set, set]:
    it = cls.INPUT_TYPES()
    return set(it.get("required", {})), set(it.get("optional", {}))


def _unwrap(result):
    """V1 nodes return a tuple; V3 nodes return io.NodeOutput."""
    inner = getattr(result, "result", result)
    return tuple(inner)


def _invoke(cls, supplied: Dict[str, Any]):
    required, optional = _schema(cls)
    accepted = required | optional

    kwargs = {k: v for k, v in supplied.items() if k in accepted}

    # SAM3_Detect names its image input "image"; some forks use "images".
    if "image" in accepted:
        kwargs["image"] = supplied["image"]
    elif "images" in accepted:
        kwargs["images"] = supplied["image"]

    missing = required - set(kwargs)
    if missing:
        raise RuntimeError(
            f"SAM3_Detect requires arguments this node does not supply: {sorted(missing)}.\n"
            "Core's signature has changed. Report this, or turn use_sam3 off and feed "
            "a MASK from a SAM3_Detect node you wire yourself."
        )

    obj = cls()
    fn = getattr(obj, getattr(cls, "FUNCTION", "execute"))
    return _unwrap(fn(**kwargs))


def detect(
    image: torch.Tensor,
    text: str,
    ckpt_name: str,
    threshold: float = 0.5,
    refine_iterations: int = 2,
    individual_masks: bool = True,
    keep_model_loaded: bool = True,
):
    """Run the full chain. Returns ``(masks [N,H,W], boxes | None)``."""
    if not text.strip():
        raise ValueError("sam3_prompt is empty. Describe what to segment, e.g. 'face'.")

    model, clip = load(ckpt_name, keep_model_loaded)
    try:
        conditioning = encode(clip, text)
        cls = _detect_cls()
        out = _invoke(cls, {
            "model": model,
            "image": image,
            "conditioning": conditioning,
            "threshold": threshold,
            "refine_iterations": refine_iterations,
            "individual_masks": individual_masks,
        })
    finally:
        if not keep_model_loaded:
            release(ckpt_name)

    masks = out[0]
    boxes = out[1] if len(out) > 1 else None

    if masks is None:
        return torch.zeros((0,) + tuple(image.shape[1:3])), None
    if masks.dim() == 2:
        masks = masks.unsqueeze(0)
    return masks.float().clamp(0.0, 1.0), boxes
