"""BOUNDING_BOX interop.

SAM3_Detect emits boxes carrying x, y, width, height and score. The container is
not a stable contract, so we duck-type it. We only ever read *scores*: crop
geometry comes from the mask, which is exact, while the detector box is looser.
"""

from __future__ import annotations

from typing import List, Optional


def _score_of(box) -> Optional[float]:
    if isinstance(box, dict):
        for key in ("score", "confidence", "conf"):
            if key in box:
                return float(box[key])
        return None
    for key in ("score", "confidence", "conf"):
        if hasattr(box, key):
            return float(getattr(box, key))
    if isinstance(box, (list, tuple)) and len(box) >= 5:
        return float(box[4])  # x, y, w, h, score
    return None


def scores(bboxes, expected: int) -> Optional[List[float]]:
    """One score per detection, or None if we cannot line them up.

    None is the honest answer on a count mismatch: silently zipping mismatched
    lists would attach the wrong score to the wrong mask, and the caller would
    then confidently select the wrong object.
    """
    if bboxes is None:
        return None
    try:
        seq = list(bboxes)
    except TypeError:
        return None
    if len(seq) == 1 and isinstance(seq[0], (list, tuple)) and len(seq[0]) != 5:
        seq = list(seq[0])  # single-frame nesting
    if len(seq) != expected:
        return None
    out = [_score_of(b) for b in seq]
    return None if any(s is None for s in out) else out
