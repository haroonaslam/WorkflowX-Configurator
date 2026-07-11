"""Coordinate math for the crop/stitch round trip.

Deliberately free of torch so it can be tested standalone. Everything here
operates on plain ints and tuples. Bboxes are ``(x, y, w, h)`` with the origin
at top-left. Padding is ``(top, left, bottom, right)``.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

BBox = Tuple[int, int, int, int]
Pad = Tuple[int, int, int, int]

EDGE_MODES = ("shift", "pad_replicate", "clamp")


def round_up(value: int, multiple: int) -> int:
    if multiple <= 1:
        return int(value)
    return int(math.ceil(value / multiple) * multiple)


def round_down(value: int, multiple: int) -> int:
    if multiple <= 1:
        return int(value)
    return max(multiple, int(value // multiple) * multiple)


def expand_bbox(
    bbox: BBox,
    factor: float = 1.0,
    pixels: int = 0,
    force_square: bool = True,
    multiple: int = 8,
) -> BBox:
    """Grow a bbox around its centre, optionally squaring and rounding.

    Order is load-bearing: scale, then square, then round. Rounding before
    squaring would let the two axes land on different multiples.
    """
    x, y, w, h = bbox
    cx = x + w / 2.0
    cy = y + h / 2.0

    w = w * factor + 2 * pixels
    h = h * factor + 2 * pixels

    if force_square:
        w = h = max(w, h)

    w = round_up(int(math.ceil(w)), multiple)
    h = round_up(int(math.ceil(h)), multiple)

    if force_square:  # belt and braces; equal inputs round identically
        w = h = max(w, h)

    return (int(round(cx - w / 2.0)), int(round(cy - h / 2.0)), w, h)


def fit_bbox(
    bbox: BBox,
    img_w: int,
    img_h: int,
    mode: str = "shift",
    multiple: int = 8,
) -> Tuple[BBox, Pad, bool]:
    """Resolve a bbox that may fall outside the image.

    Returns ``(bbox, source_padding, degraded)``. When ``source_padding`` is
    non-zero the caller must pad the source image before slicing, and the
    returned bbox is expressed in *padded* coordinates.

    ``degraded`` is True when the requested mode could not be honoured -- i.e.
    ``shift`` was asked for but the box is larger than the image, so we fell
    back to clamping and the crop is no longer square / round.
    """
    if mode not in EDGE_MODES:
        raise ValueError(f"unknown edge_handling {mode!r}, expected one of {EDGE_MODES}")

    x, y, w, h = bbox

    if mode == "pad_replicate":
        top = max(0, -y)
        left = max(0, -x)
        bottom = max(0, (y + h) - img_h)
        right = max(0, (x + w) - img_w)
        return (x + left, y + top, w, h), (top, left, bottom, right), False

    if mode == "shift" and w <= img_w and h <= img_h:
        x = min(max(x, 0), img_w - w)
        y = min(max(y, 0), img_h - h)
        return (x, y, w, h), (0, 0, 0, 0), False

    # clamp, or a shift that cannot fit
    degraded = mode == "shift"
    x1 = max(0, min(x, img_w - 1))
    y1 = max(0, min(y, img_h - 1))
    x2 = min(img_w, x + w)
    y2 = min(img_h, y + h)
    cw = round_down(max(1, x2 - x1), multiple)
    ch = round_down(max(1, y2 - y1), multiple)
    cw = min(cw, img_w - x1)
    ch = min(ch, img_h - y1)
    return (x1, y1, cw, ch), (0, 0, 0, 0), degraded


def target_dims(
    w: int,
    h: int,
    mode: str,
    target: int,
    multiple: int = 8,
) -> Tuple[int, int]:
    """Compute post-resize dimensions."""
    if mode == "none":
        return w, h
    if mode == "target_size":
        return target, target
    if mode == "max_dimension":
        scale = target / float(max(w, h))
        return (
            max(multiple, round_up(int(round(w * scale)), multiple)),
            max(multiple, round_up(int(round(h * scale)), multiple)),
        )
    raise ValueError(f"unknown resize_mode {mode!r}")


def validate_resize(force_square: bool, resize_mode: str) -> Optional[str]:
    """``target_size`` forces a square output. Warn rather than silently distort."""
    if resize_mode == "target_size" and not force_square:
        return (
            "resize_mode='target_size' produces a square crop but force_square is "
            "off; the crop will be distorted. Enable force_square or use "
            "resize_mode='max_dimension'."
        )
    return None
