"""Mask-weighted colour transfer.

Why weighted: at expand_factor=1.4 the crop is mostly hair, neck and
background. Computing statistics over the whole rectangle lets those pixels
dominate the distribution and drags the correction away from skin. Every
estimator here weights by the face mask instead.

Reference is always the *original* crop, pre-swap. Running the match after
compositing would fit the swapped face against pixels we already replaced.
"""

from __future__ import annotations

import torch

METHODS = ("reinhard", "mkl", "hm")
_EPS = 1e-6


def _flat(img: torch.Tensor, mask: torch.Tensor):
    """``[1,H,W,3]``, ``[1,H,W]`` -> ``[N,3]``, ``[N,1]``."""
    x = img.reshape(-1, img.shape[-1]).float()
    w = mask.reshape(-1, 1).float().clamp(0.0, 1.0)
    return x, w


def _weighted_mean_cov(x: torch.Tensor, w: torch.Tensor):
    total = w.sum().clamp(min=_EPS)
    mu = (x * w).sum(0) / total
    xc = x - mu
    cov = (xc * w).T @ xc / total
    return mu, cov


def _sqrt_psd(m: torch.Tensor, inverse: bool = False) -> torch.Tensor:
    vals, vecs = torch.linalg.eigh(m.double())
    vals = vals.clamp(min=_EPS)
    vals = vals.rsqrt() if inverse else vals.sqrt()
    return (vecs @ torch.diag(vals) @ vecs.T).to(m.dtype)


def _reinhard(src, ref, sw, rw):
    smu, scov = _weighted_mean_cov(src, sw)
    rmu, rcov = _weighted_mean_cov(ref, rw)
    sstd = torch.diagonal(scov).clamp(min=_EPS).sqrt()
    rstd = torch.diagonal(rcov).clamp(min=_EPS).sqrt()
    return (src - smu) * (rstd / sstd) + rmu


def _mkl(src, ref, sw, rw):
    """Monge-Kantorovich linear transport. Closed form for gaussians.

    T = A^-1/2 (A^1/2 B A^1/2)^1/2 A^-1/2   with A = cov(src), B = cov(ref)
    """
    smu, a = _weighted_mean_cov(src, sw)
    rmu, b = _weighted_mean_cov(ref, rw)
    eye = torch.eye(3, device=src.device, dtype=src.dtype) * _EPS
    a, b = a + eye, b + eye
    a_half = _sqrt_psd(a)
    a_inv_half = _sqrt_psd(a, inverse=True)
    middle = _sqrt_psd(a_half @ b @ a_half)
    t = a_inv_half @ middle @ a_inv_half
    return (src - smu) @ t.T + rmu


def _weighted_cdf(values: torch.Tensor, weights: torch.Tensor, bins: int = 256):
    idx = (values.clamp(0, 1) * (bins - 1)).long()
    hist = torch.zeros(bins, device=values.device, dtype=torch.float32)
    hist.scatter_add_(0, idx, weights.float())
    cdf = torch.cumsum(hist, 0)
    return cdf / cdf[-1].clamp(min=_EPS)


def _hm(src, ref, sw, rw, bins: int = 256):
    """Per-channel weighted histogram matching."""
    out = torch.empty_like(src)
    grid = torch.linspace(0, 1, bins, device=src.device)
    for c in range(src.shape[1]):
        scdf = _weighted_cdf(src[:, c], sw[:, 0], bins)
        rcdf = _weighted_cdf(ref[:, c], rw[:, 0], bins)
        # invert rcdf by searching for each scdf value
        pos = torch.searchsorted(rcdf.contiguous(), scdf.contiguous()).clamp(0, bins - 1)
        lut = grid[pos]
        sidx = (src[:, c].clamp(0, 1) * (bins - 1)).long()
        out[:, c] = lut[sidx]
    return out


def color_match(
    source: torch.Tensor,
    reference: torch.Tensor,
    mask: torch.Tensor,
    method: str = "mkl",
    strength: float = 1.0,
) -> torch.Tensor:
    """Match ``source`` to ``reference`` over ``mask``.

    All three tensors must share H and W. Returns ``[1,H,W,3]`` in 0-1.
    """
    if method not in METHODS:
        raise ValueError(f"unknown color_match_method {method!r}, expected {METHODS}")
    if strength <= 0.0:
        return source

    if float(mask.sum()) < 1.0:  # nothing to match against
        return source

    src, sw = _flat(source, mask)
    ref, rw = _flat(reference, mask)

    fn = {"reinhard": _reinhard, "mkl": _mkl, "hm": _hm}[method]
    matched = fn(src, ref, sw, rw).clamp(0.0, 1.0)
    matched = matched.reshape(source.shape)

    if strength >= 1.0:
        return matched
    return torch.lerp(source, matched, float(strength))
