"""AnythingStitch -- node 2."""

from __future__ import annotations

import logging

import torch

from ..utils import colormatch, masking, resize

log = logging.getLogger("anything_swap_bridge")

ASPECT_TOLERANCE = 0.01  # 1%


class AnythingStitch:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "stitch": ("SWAP_STITCH", {"tooltip":
                    "Payload from Anything Crop. Carries the clean original and exact geometry."}),
                "swapped": ("IMAGE", {"tooltip":
                    "The edited crop, straight back from your model or API."}),
                "size_mismatch": (["resize", "stretch", "error"], {"default": "resize",
                    "tooltip": "What to do when the swap model returns a different "
                    "resolution. resize: rescale, but reject a changed aspect ratio. "
                    "stretch: rescale regardless, distorting. error: demand an exact match."}),
                "mask_mode": (["payload_mask", "full_rect", "override"],),
                "feather": ("INT", {"default": 6, "min": 0, "max": 256}),
                "color_match": ("BOOLEAN", {"default": True}),
                "color_match_method": (list(colormatch.METHODS), {"default": "mkl"}),
                "color_match_strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
            "optional": {
                "mask_override": ("MASK",),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "changed_mask")
    OUTPUT_TOOLTIPS = (
        "The full source image with the swapped region composited back in.",
        "Which pixels changed, at source resolution. Feed a refiner pass.",
    )
    FUNCTION = "execute"
    CATEGORY = "WorkflowX_Configurator/Image/Anything Swap"
    DESCRIPTION = (
        "Composite an edited crop back into the original. Pixels outside the "
        "mask are returned bit-identical."
    )

    def execute(self, stitch=None, swapped=None, size_mismatch="resize",
                mask_mode="payload_mask", feather=6, color_match=True,
                color_match_method="mkl", color_match_strength=1.0,
                mask_override=None):

        if stitch is None:
            raise ValueError(
                "AnythingStitch: 'stitch' is not connected. Wire it from the "
                "'stitch' output of Anything Crop (for Swap)."
            )
        if swapped is None:
            raise ValueError(
                "AnythingStitch: 'swapped' is not connected. Wire in the image your "
                "swap model produced from the 'crop' output."
            )
        swapped_face = swapped
        original = stitch["original_image"]

        # 1. no detection upstream -> clean passthrough
        if not stitch.get("detected", False):
            return (original, masking.empty_like_mask(original))

        if swapped_face.shape[0] != 1:
            raise ValueError(
                f"AnythingStitch accepts a single image; got a batch of {swapped_face.shape[0]}."
            )

        pad = stitch["source_padding"]
        x, y, cw, ch = stitch["bbox"]
        pre_w, pre_h = stitch["size_pre_resize"]
        post_w, post_h = stitch["size_post_resize"]
        device = original.device

        # 2. channels. ComfyUI IMAGE is RGB. Some APIs hand back RGBA.
        ch_n = int(swapped_face.shape[-1])
        if ch_n == 4:
            log.warning(
                "[anything-swap-bridge] swapped has an alpha channel; dropping it. "
                "If the alpha describes what the model changed, wire it into "
                "mask_override with mask_mode='override' instead."
            )
            swapped_face = swapped_face[..., :3]
        elif ch_n != 3:
            raise ValueError(
                f"AnythingStitch: swapped has {ch_n} channels; expected 3 (RGB)."
            )

        # 3. value range. ComfyUI IMAGE is float 0-1. A 0-255 tensor would survive
        # every shape check and then composite to garbage, so catch it by value.
        hi = float(swapped_face.max())
        if hi > 1.5:
            raise ValueError(
                f"AnythingStitch: swapped has values up to {hi:.1f}. ComfyUI images are "
                "float 0-1. Your swap model or API returned 0-255 data -- divide by 255 "
                "before wiring it in."
            )

        # 4. size. The requirement is aspect, not resolution.
        got_h, got_w = int(swapped_face.shape[1]), int(swapped_face.shape[2])
        if (got_w, got_h) != (post_w, post_h):
            if size_mismatch == "error":
                raise ValueError(
                    f"AnythingStitch: swapped is {got_w}x{got_h} but the crop was "
                    f"{post_w}x{post_h}, and size_mismatch='error'. Set it to 'resize' "
                    "to accept a rescaled return."
                )
            want_ar = post_w / post_h
            got_ar = got_w / got_h
            drift = abs(got_ar - want_ar) / want_ar
            if size_mismatch == "resize" and drift > ASPECT_TOLERANCE:
                raise ValueError(
                    f"AnythingStitch: swapped is {got_w}x{got_h} (aspect {got_ar:.4f}) but "
                    f"the crop was {post_w}x{post_h} (aspect {want_ar:.4f}), a {drift:.1%} "
                    "drift. The swap model changed the aspect ratio; stitching would "
                    "distort it. Common cause: the model forces square output. Either set "
                    "force_square=true on Anything Crop so the crop is already square, or "
                    "set size_mismatch='stretch' to accept the distortion."
                )
            if drift > ASPECT_TOLERANCE:
                log.warning(
                    "[anything-swap-bridge] stretching %dx%d to the crop's %.4f aspect; "
                    "the result will be distorted", got_w, got_h, want_ar,
                )
            else:
                log.info(
                    "[anything-swap-bridge] swapped is %dx%d, crop was %dx%d; rescaling",
                    got_w, got_h, post_w, post_h,
                )

        swapped = swapped_face.to(device)

        # 3. inverse of node 1's resize
        method = stitch["downscale_method"] if (pre_w * pre_h) < (got_w * got_h) else stitch["upscale_method"]
        swapped = resize.resize_image(swapped, pre_w, pre_h, method)

        # 4. reference = the untouched original crop, sliced out of the payload
        padded = resize.pad_image(original, pad)
        reference = padded[:, y:y + ch, x:x + cw, :]

        # 5. build the composite mask
        payload_mask = stitch["mask_cropped"].to(device)
        if mask_mode == "full_rect":
            m = masking.rect_mask(pre_h, pre_w, device)
        elif mask_mode == "override":
            if mask_override is None:
                raise ValueError(
                    "AnythingStitch: mask_mode='override' but no mask_override is connected."
                )
            m = mask_override.to(device).float()
            if m.dim() == 2:
                m = m.unsqueeze(0)

            # mask_override lives in CROP space, not source space. A mask drawn on
            # the full source image would be silently squashed into the bbox and
            # land nowhere near right -- a plausible-looking wrong result rather
            # than an error. Aspect is the cheapest way to catch it.
            ov_h, ov_w = int(m.shape[1]), int(m.shape[2])
            want_ar = pre_w / pre_h
            got_ar = ov_w / ov_h
            if abs(got_ar - want_ar) / want_ar > ASPECT_TOLERANCE:
                src_h, src_w = int(original.shape[1]), int(original.shape[2])
                hint = ""
                if abs(got_ar - (src_w / src_h)) / (src_w / src_h) <= ASPECT_TOLERANCE:
                    hint = (
                        f" Its aspect matches the SOURCE image ({src_w}x{src_h}), which "
                        "suggests you wired a source-space mask. mask_override must be in "
                        "crop space -- build it from the 'crop' or 'crop_mask' output."
                    )
                raise ValueError(
                    f"AnythingStitch: mask_override is {ov_w}x{ov_h}, aspect {got_ar:.3f}, "
                    f"but the crop is {pre_w}x{pre_h}, aspect {want_ar:.3f}.{hint}"
                )
        else:
            m = payload_mask
        m = resize.resize_mask(m, pre_w, pre_h)

        # 6. colour match BEFORE compositing, weighted by the hard mask.
        #    Feathering first would let background pixels bleed into the stats.
        if color_match and color_match_strength > 0.0:
            hard = resize.resize_mask(payload_mask, pre_w, pre_h)
            swapped = colormatch.color_match(
                swapped, reference, hard, color_match_method, color_match_strength
            )

        # 7. feather, then alpha composite
        m = masking.feather_edges(m, feather)
        m3 = m.unsqueeze(-1)
        blended = reference * (1.0 - m3) + swapped * m3

        canvas = padded.clone()
        canvas[:, y:y + ch, x:x + cw, :] = blended
        canvas = resize.unpad(canvas, pad).clamp(0.0, 1.0)

        # 8. changed_mask, in original coords, for a downstream refiner
        full = torch.zeros(
            (1, padded.shape[1], padded.shape[2]), device=device, dtype=torch.float32
        )
        full[:, y:y + ch, x:x + cw] = m
        full = resize.unpad(full.unsqueeze(-1), pad).squeeze(-1)

        return (canvas, full)
