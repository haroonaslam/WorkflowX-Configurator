"""ComfyUI Anything Swap Bridge -- split crop/stitch around any model or API.

Import shim
-----------
Some ComfyUI builds register a custom node package in ``sys.modules`` under its
absolute filesystem path (e.g. ``D:\\ComfyUI\\custom_nodes\\ComfyUI-anything-swap-bridge``).
That is not a valid dotted identifier, so ``from .src.crop import X`` can
fail with a ModuleNotFoundError naming the whole path.

When the plain relative import works, we use it. When it does not, we register a
synthetic parent package under a clean name pointing at this directory, and let
the normal machinery resolve the submodules from there. Relative imports inside
``src/`` and ``utils/`` then work unchanged.
"""

import os
import sys
import types

_HERE = os.path.dirname(os.path.realpath(__file__))
_ALIAS = "comfyui_anything_swap_bridge"


def _import_nodes():
    try:
        from .src.crop import AnythingCropForSwap
        from .src.stitch import AnythingStitch

        return AnythingCropForSwap, AnythingStitch
    except (ImportError, ValueError, SystemError):
        pass

    if _ALIAS not in sys.modules:
        pkg = types.ModuleType(_ALIAS)
        pkg.__path__ = [_HERE]  # makes submodule resolution work
        pkg.__package__ = _ALIAS
        sys.modules[_ALIAS] = pkg

    from importlib import import_module

    crop = import_module(f"{_ALIAS}.src.crop")
    stitch = import_module(f"{_ALIAS}.src.stitch")
    return crop.AnythingCropForSwap, stitch.AnythingStitch


AnythingCropForSwap, AnythingStitch = _import_nodes()

NODE_CLASS_MAPPINGS = {
    "AnythingCropForSwap": AnythingCropForSwap,
    "AnythingStitch": AnythingStitch,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AnythingCropForSwap": "Anything Crop (for Swap)",
    "AnythingStitch": "Anything Stitch",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
