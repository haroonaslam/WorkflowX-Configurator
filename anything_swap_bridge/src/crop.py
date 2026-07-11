"""AnythingCropForSwap -- node 1."""

from __future__ import annotations

import logging

import torch

from ..utils import bboxes as bbox_utils
from ..utils import geometry, masking, prompting, resize, sam3

log = logging.getLogger("anything_swap_bridge")

PAYLOAD_VERSION = 3


class AnythingCropForSwap:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {"tooltip": "Source image. Single image only, not a batch."}),
                "use_sam3": ("BOOLEAN", {"default": True, "tooltip":
                    "On: segment internally from sam3_prompt. Off: use the mask input."}),
                "sam3_prompt": ("STRING", {"default": "face", "tooltip":
                    "What to segment. Short, concrete nouns work best: 'face', "
                    "'left hand', 'shoe', 'sunglasses'."}),
                "sam3_checkpoint": (sam3.checkpoint_list(), {"tooltip":
                    "SAM3 checkpoint in models/checkpoints. It carries its own text encoder."}),
                "threshold": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": "Detection confidence floor. Lower finds more, and more junk."}),
                "refine_iterations": ("INT", {"default": 2, "min": 0, "max": 5,
                    "tooltip": "SAM3 mask refinement passes. 0 is fastest, 2 is the core default."}),
                "keep_model_loaded": ("BOOLEAN", {"default": True, "tooltip":
                    "Keep SAM3 in memory between runs. Off reloads from disk each time."}),
                "select_mode": (list(sam3.SELECT_MODES), {"tooltip":
                    "Which object to crop when the prompt matches several."}),
                "object_index": ("INT", {"default": 0, "min": 0, "max": 63,
                    "tooltip": "Used only when select_mode is 'index'."}),
                "expand_factor": ("FLOAT", {"default": 1.4, "min": 1.0, "max": 4.0, "step": 0.01,
                    "tooltip": "Grow the bounding box around its centre. 1.0 is a tight crop."}),
                "expand_pixels": ("INT", {"default": 0, "min": 0, "max": 512,
                    "tooltip": "Extra pixels added per side after expand_factor."}),
                "force_square": ("BOOLEAN", {"default": False, "tooltip":
                    "Square the crop. Right for faces, wasteful for hands, shoes, bottles. "
                    "Required if resize_mode is 'target_size'."}),
                "padding": ([0, 8, 16, 32, 64], {"default": 16, "tooltip":
                    "Round crop dimensions up to this multiple."}),
                "edge_handling": (list(geometry.EDGE_MODES), {"tooltip":
                    "shift: slide the box inside. pad_replicate: edge-pad the source. "
                    "clamp: truncate."}),
                "resize_mode": (["none", "target_size", "max_dimension"], {"tooltip":
                    "none preserves native resolution and is lossless."}),
                "target_size": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 8}),
                "upscale_method": (list(resize.UPSCALE_METHODS),),
                "downscale_method": (list(resize.DOWNSCALE_METHODS),),
                "mask_grow": ("INT", {"default": 0, "min": -256, "max": 256, "tooltip":
                    "Dilate (+) or erode (-) before the bbox is measured."}),
                "mask_blur": ("INT", {"default": 3, "min": 0, "max": 256, "tooltip":
                    "Softens only the mask handed downstream. Does not affect stitching."}),
                "swap_prompt": ("STRING", {"multiline": True, "default": prompting.DEFAULT_PROMPT,
                    "tooltip": "Passed to the output. Tokens: {target} {width} {height} {caption}"}),
            },
            "optional": {
                "mask": ("MASK", {"tooltip": "Used when use_sam3 is off."}),
                "caption": ("STRING", {"forceInput": True, "tooltip":
                    "Optional VLM caption, substituted into {caption}."}),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK", "STRING", "IMAGE", "SWAP_STITCH", "BOOLEAN")
    RETURN_NAMES = ("crop", "crop_mask", "swap_prompt", "source_masked", "stitch", "detected")
    OUTPUT_TOOLTIPS = (
        "The cropped region, ready for your swap model or API.",
        "The object's mask inside the crop, blurred by mask_blur.",
        "swap_prompt with tokens substituted.",
        "Source with the object blanked. Preview, or feed an inpaint model.",
        "Opaque payload for Anything Stitch. Carries the clean original and exact geometry.",
        "False when nothing was segmented. Branch on this to skip work.",
    )
    FUNCTION = "execute"
    CATEGORY = "WorkflowX_Configurator/Image/Anything Swap"
    DESCRIPTION = (
        "Segment an object, crop tightly around it, and emit a payload that "
        "Anything Stitch uses to put the result back exactly."
    )

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _payload(image, detected, bbox=None, pad=(0, 0, 0, 0), pre=None, post=None,
                 mask_cropped=None, up="lanczos", down="area"):
        return {
            "version": PAYLOAD_VERSION,
            "detected": bool(detected),
            "original_image": image,
            "source_padding": tuple(pad),
            "bbox": bbox,
            "size_pre_resize": pre,
            "size_post_resize": post,
            "mask_cropped": mask_cropped,
            "upscale_method": up,
            "downscale_method": down,
        }

    def _nothing_found(self, image, prompt_text, target_size, resize_mode, why):
        side = target_size if resize_mode != "none" else 64
        blank = torch.zeros((1, side, side, 3), device=image.device, dtype=image.dtype)
        blank_mask = torch.zeros((1, side, side), device=image.device, dtype=torch.float32)
        log.warning("[anything-swap-bridge] %s; passing the image through untouched", why)
        return (blank, blank_mask, prompt_text, image, self._payload(image, False), False)

    @staticmethod
    def _select(mask, boxes, mode, index):
        """``[N,H,W]`` -> ``[1,H,W]``. N is a batch of objects, not of images."""
        n = int(mask.shape[0])
        if n == 0:
            return None
        if n == 1:
            return mask

        if mode == "index":
            if not 0 <= index < n:
                raise ValueError(f"object_index {index} out of range for {n} detections")
            return mask[index : index + 1]

        if mode == "highest_confidence":
            scores = bbox_utils.scores(boxes, n)
            if scores is None:
                log.warning(
                    "[anything-swap-bridge] select_mode='highest_confidence' but scores are "
                    "absent or do not line up with %d masks; falling back to 'largest'", n
                )
            else:
                return mask[max(range(n), key=lambda i: scores[i])][None]

        areas = [masking.mask_area(mask[i : i + 1]) for i in range(n)]
        return mask[max(range(n), key=lambda i: areas[i])][None]

    # -- main ---------------------------------------------------------------

    def execute(self, image=None, use_sam3=True, sam3_prompt="face", sam3_checkpoint="",
                threshold=0.5, refine_iterations=2, keep_model_loaded=True,
                select_mode="largest", object_index=0, expand_factor=1.4, expand_pixels=0,
                force_square=False, padding=16, edge_handling="shift", resize_mode="none",
                target_size=1024, upscale_method="lanczos", downscale_method="area",
                mask_grow=0, mask_blur=3, swap_prompt=prompting.DEFAULT_PROMPT,
                mask=None, caption=None):

        if image is None:
            raise ValueError("AnythingCropForSwap: 'image' is not connected.")
        if image.shape[0] != 1:
            raise ValueError(
                f"AnythingCropForSwap takes a single image; got a batch of {image.shape[0]}. "
                "Split the batch upstream."
            )

        if warn := geometry.validate_resize(force_square, resize_mode):
            log.warning("[anything-swap-bridge] %s", warn)

        h, w = int(image.shape[1]), int(image.shape[2])
        prompt_text = prompting.render(swap_prompt, {
            "target": sam3_prompt if use_sam3 else "masked region",
            "width": target_size if resize_mode != "none" else "",
            "height": target_size if resize_mode != "none" else "",
            "caption": caption or "",
        })

        # 1. resolve the mask. The toggle is authoritative.
        boxes = None
        if use_sam3:
            masks, boxes = sam3.detect(
                image, sam3_prompt, sam3_checkpoint, threshold,
                refine_iterations, True, keep_model_loaded,
            )
            obj = self._select(masks.to(image.device), boxes, select_mode, object_index)
            if obj is None:
                return self._nothing_found(
                    image, prompt_text, target_size, resize_mode,
                    f"SAM3 found nothing matching {sam3_prompt!r}",
                )
            target_mask = obj
        elif mask is not None:
            target_mask = mask.to(image.device).float()
            if target_mask.dim() == 2:
                target_mask = target_mask.unsqueeze(0)
            target_mask = self._select(target_mask, None, select_mode, object_index)
        else:
            raise ValueError(
                "AnythingCropForSwap: use_sam3 is off and no mask is connected.\n"
                "Either turn use_sam3 on, or wire a MASK into the mask input."
            )

        if target_mask.shape[1:] != (h, w):
            target_mask = resize.resize_mask(target_mask, w, h)

        # 2. grow before the bbox, so growth is reflected in the crop bounds
        target_mask = masking.grow_mask(target_mask, mask_grow)

        base = masking.mask_to_bbox(target_mask)
        if base is None:
            return self._nothing_found(
                image, prompt_text, target_size, resize_mode, "the mask is empty"
            )

        # 3-8. expand, square, round, place, resolve edges
        box = geometry.expand_bbox(base, expand_factor, expand_pixels, force_square, padding)
        box, pad, degraded = geometry.fit_bbox(box, w, h, edge_handling, padding)
        if degraded:
            log.warning("[anything-swap-bridge] crop is larger than the image; fell back to clamp")

        src_img = resize.pad_image(image, pad)
        src_mask = resize.pad_mask(target_mask, pad)

        x, y, cw, ch = box
        crop = src_img[:, y : y + ch, x : x + cw, :]
        crop_mask_raw = src_mask[:, y : y + ch, x : x + cw]  # PRE-blur; goes in the payload

        # 9-10. blur only the copy handed downstream
        crop_mask_out = masking.gaussian_blur(crop_mask_raw, mask_blur)

        # 11. resize
        tw, th = geometry.target_dims(cw, ch, resize_mode, target_size, padding)
        method = upscale_method if (tw * th) > (cw * ch) else downscale_method
        crop_out = resize.resize_image(crop, tw, th, method)
        crop_mask_out = resize.resize_mask(crop_mask_out, tw, th)

        source_masked = image * (1.0 - target_mask.unsqueeze(-1))

        payload = self._payload(
            image, True, bbox=box, pad=pad, pre=(cw, ch), post=(tw, th),
            mask_cropped=crop_mask_raw.cpu(), up=upscale_method, down=downscale_method,
        )
        return (crop_out, crop_mask_out, prompt_text, source_masked, payload, True)
