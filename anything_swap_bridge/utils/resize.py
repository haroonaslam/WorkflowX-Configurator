"""Resizing, isolated so the NHWC <-> NCHW permute happens in exactly one place.

ComfyUI IMAGE is ``[B, H, W, C]`` float32 0-1 RGB. MASK is ``[B, H, W]``.
Neither is NCHW. Every torch spatial op wants NCHW. This is the single most
common source of bugs in custom nodes, so it lives behind these two functions
and nowhere else.
"""

from __future__ import annotations

import torch
import torch.nn.functional as F

try:  # pragma: no cover
    import comfy.utils

    HAS_COMFY = True
except Exception:  # noqa: BLE001
    comfy = None
    HAS_COMFY = False

UPSCALE_METHODS = ("lanczos", "bicubic", "bilinear", "area", "nearest-exact")
DOWNSCALE_METHODS = ("area", "lanczos", "bicubic", "bilinear")


def _common_upscale(nchw: torch.Tensor, w: int, h: int, method: str) -> torch.Tensor:
    if HAS_COMFY:
        return comfy.utils.common_upscale(nchw, w, h, method, "disabled")
    # Fallback for standalone tests. lanczos has no torch equivalent.
    mode = {"nearest-exact": "nearest-exact", "area": "area"}.get(method, method)
    if mode == "lanczos":
        mode = "bicubic"
    kwargs = {} if mode in ("area", "nearest-exact") else {"align_corners": False}
    return F.interpolate(nchw, size=(h, w), mode=mode, **kwargs)


def resize_image(img: torch.Tensor, w: int, h: int, method: str) -> torch.Tensor:
    """``[B,H,W,C]`` -> ``[B,H,W,C]``. Identity when dims already match."""
    if img.shape[2] == w and img.shape[1] == h:
        return img  # exact no-op; preserves the identity invariant
    x = img.movedim(-1, 1).float()
    x = _common_upscale(x, w, h, method)
    # lanczos/bicubic ring outside [0,1]
    return x.movedim(1, -1).clamp(0.0, 1.0)


def resize_mask(mask: torch.Tensor, w: int, h: int, method: str = "bilinear") -> torch.Tensor:
    """``[B,H,W]`` -> ``[B,H,W]``. Identity when dims already match."""
    if mask.shape[2] == w and mask.shape[1] == h:
        return mask
    x = mask.unsqueeze(1).float()
    x = _common_upscale(x, w, h, method)
    return x.squeeze(1).clamp(0.0, 1.0)


def pad_image(img: torch.Tensor, pad) -> torch.Tensor:
    """Replicate-pad ``[B,H,W,C]`` by ``(top, left, bottom, right)``."""
    top, left, bottom, right = pad
    if not any(pad):
        return img
    x = img.movedim(-1, 1).float()
    x = F.pad(x, (left, right, top, bottom), mode="replicate")
    return x.movedim(1, -1)


def pad_mask(mask: torch.Tensor, pad) -> torch.Tensor:
    """Zero-pad ``[B,H,W]``. Outside the source there is no face, so 0, not replicate."""
    top, left, bottom, right = pad
    if not any(pad):
        return mask
    x = mask.unsqueeze(1).float()
    x = F.pad(x, (left, right, top, bottom), mode="constant", value=0.0)
    return x.squeeze(1)


def unpad(t: torch.Tensor, pad) -> torch.Tensor:
    """Inverse of pad_image/pad_mask. Works for ``[B,H,W,...]``."""
    top, left, bottom, right = pad
    if not any(pad):
        return t
    h, w = t.shape[1], t.shape[2]
    return t[:, top : h - bottom, left : w - right, ...]
