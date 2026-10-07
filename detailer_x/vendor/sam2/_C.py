"""Compatibility shim for the Python-ABI-free SAM 2 CUDA operator."""

from pathlib import Path

import torch


def _load_native_library() -> None:
    torch_version = torch.__version__.split("+", 1)[0].split(".")
    if torch_version[:2] != ["2", "13"] or torch.version.cuda != "13.0":
        raise ImportError(
            "This SAM 2 CUDA extension requires Torch 2.13 with CUDA 13.0; "
            f"found Torch {torch.__version__} with CUDA {torch.version.cuda}."
        )
    package_dir = Path(__file__).resolve().parent
    candidates = [
        path
        for path in package_dir.glob("_C_ops*")
        if path.suffix.lower() in {".dll", ".dylib", ".pyd", ".so"}
    ]
    if len(candidates) != 1:
        raise ImportError(
            f"Expected one SAM 2 native library in {package_dir}, found {candidates}"
        )
    torch.ops.load_library(str(candidates[0]))


_load_native_library()


def get_connected_componnets(mask: torch.Tensor):
    """Call the upstream misspelled connected-components CUDA entry point."""

    return torch.ops.sam2.get_connected_componnets(mask)


__all__ = ["get_connected_componnets"]
