"""Mask grow/shrink and gaussian feathering. All ops take/return ``[B,H,W]``."""

from __future__ import annotations

import math
from typing import Optional, Tuple

import torch
import torch.nn.functional as F


def mask_to_bbox(mask: torch.Tensor, threshold: float = 0.5) -> Optional[Tuple[int, int, int, int]]:
    """First mask in the batch -> ``(x, y, w, h)``, or None if empty."""
    m = mask[0] if mask.dim() == 3 else mask
    ys, xs = torch.nonzero(m > threshold, as_tuple=True)
    if ys.numel() == 0:
        return None
    x1, x2 = int(xs.min()), int(xs.max()) + 1
    y1, y2 = int(ys.min()), int(ys.max()) + 1
    return (x1, y1, x2 - x1, y2 - y1)


def grow_mask(mask: torch.Tensor, px: int) -> torch.Tensor:
    """Dilate (px > 0) or erode (px < 0) by a square structuring element.

    Padding is constant 0 in both directions, so background is background: an
    erode eats the image border rather than treating it as solid.
    """
    if px == 0:
        return mask
    r = abs(int(px))
    k = 2 * r + 1
    x = mask.unsqueeze(1).float()
    x = F.pad(x, (r, r, r, r), mode="constant", value=0.0)
    if px > 0:
        x = F.max_pool2d(x, k, stride=1)
    else:
        x = -F.max_pool2d(-x, k, stride=1)
    return x.squeeze(1).clamp(0.0, 1.0)


def gaussian_blur(mask: torch.Tensor, radius: int) -> torch.Tensor:
    """Separable gaussian. ``radius`` is in pixels; sigma is radius/2."""
    if radius <= 0:
        return mask
    r = int(radius)
    k = 2 * r + 1
    sigma = max(r / 2.0, 1e-3)

    coords = torch.arange(k, dtype=torch.float32, device=mask.device) - r
    g = torch.exp(-(coords**2) / (2 * sigma**2))
    g = g / g.sum()

    x = mask.unsqueeze(1).float()
    x = F.pad(x, (r, r, r, r), mode="replicate")
    x = F.conv2d(x, g.view(1, 1, 1, k))
    x = F.conv2d(x, g.view(1, 1, k, 1))
    return x.squeeze(1).clamp(0.0, 1.0)


def feather_edges(mask: torch.Tensor, px: int) -> torch.Tensor:
    """Blur inward only, so a solid mask does not lose coverage at its core."""
    if px <= 0:
        return mask
    eroded = grow_mask(mask, -max(1, px // 2))
    return gaussian_blur(eroded, px)


def rect_mask(h: int, w: int, device, dtype=torch.float32) -> torch.Tensor:
    return torch.ones((1, h, w), device=device, dtype=dtype)


def mask_area(mask: torch.Tensor, threshold: float = 0.5) -> int:
    return int((mask > threshold).sum())


def empty_like_mask(image: torch.Tensor) -> torch.Tensor:
    """``[B,H,W,C]`` -> zero ``[B,H,W]``."""
    return torch.zeros(image.shape[:3], device=image.device, dtype=torch.float32)


def _gaussian_note() -> str:
    return f"sigma = radius/2, kernel = 2*radius+1 (~{2 * math.pi:.2f} rad coverage)"
