"""Execution-local progress; never stored in workflow settings or caches."""
from contextlib import contextmanager
from contextvars import ContextVar

_active = ContextVar("detailer_x_progress", default=None)


@contextmanager
def stage_updates(callback):
    token = _active.set({"callback": callback, "prefix": ""})
    try:
        yield
    finally:
        _active.reset(token)


def prefix(value):
    active = _active.get()
    if active is not None:
        active["prefix"] = value


def report(message):
    active = _active.get()
    if active is not None:
        active["callback"](" · ".join(part for part in (active["prefix"], message) if part))


LABELS = dict(upscaler="Upscaler", face="Face detailer", breast="Breast detailer",
              pussy="Pussy detailer", hand="Hand detailer", foot="Foot detailer",
              brightness="Realism: brightness / contrast / saturation", grain="Realism: grain",
              hsv="Realism: HSV", levels="Realism: levels", sharpen="Realism: Lucy sharpen",
              dlss5="DLSS5", prepare="Preparing", complete="Complete", preset="Preset warning")
LABELS.update(rgb="RGB", gamma="Gamma", color_balance="Color Balance", temperature="Kelvin White Balance",
              lens="Lens Optic Axis", pixel_perturb="Pixel Perturb", neural_grain="Neural Grain",
              lut="LUT", camera="Camera Simulator", compression="Multi-Compression")


def message(stage, state, current, total, detail=""):
    label = LABELS.get(stage, stage)
    action = {"processing": "Running", "cached": "Reused cached result", "bypassed": "Skipped (disabled)",
              "done": "Finished", "failed": "Failed", "cancelled": "Cancelled", "complete": "Finished"}.get(state, state)
    position = f"[{current}/{total}] " if total and stage not in ("prepare", "complete", "preset") else ""
    return f"{position}{label} — {action}" + (f" · {detail}" if detail else "")
