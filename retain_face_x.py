"""Protect detected faces during image-to-image latent sampling."""

import logging
import math

import torch
import torch.nn.functional as F


LOGGER = logging.getLogger(__name__)
FACE_DETECTOR = "ultralytics/bbox/face_yolov8m.pt"


def detect_faces(image):
    from .detailer_x.assets import resolve
    from .detailer_x.processing import detections

    detector = f"internal:{FACE_DETECTOR}"
    try:
        resolve(detector, "ultralytics")
    except FileNotFoundError:
        detector = f"comfy:{FACE_DETECTOR}"
    settings = {
        "detector": detector,
        "bbox_threshold": .4,
        "drop_size": 4,
        "bbox_dilation": 0,
        "bbox_crop_factor": 1.0,
    }
    rgb = image[..., :3].to(device="cpu", dtype=torch.float32)
    return [box for box, _, _ in detections(rgb, settings)]


def paint_protection(mask, box, margin, feather):
    height, width = mask.shape
    x1, y1, x2, y2 = box
    left = max(0, math.floor(x1) - margin)
    top = max(0, math.floor(y1) - margin)
    right = min(width, math.ceil(x2) + margin)
    bottom = min(height, math.ceil(y2) + margin)
    if left >= right or top >= bottom:
        return
    if feather == 0:
        mask[top:bottom, left:right] = 1
        return

    x0, x_end = max(0, left - feather), min(width, right + feather)
    y0, y_end = max(0, top - feather), min(height, bottom + feather)
    x = torch.arange(x0, x_end, dtype=mask.dtype)
    y = torch.arange(y0, y_end, dtype=mask.dtype)
    dx = torch.maximum(left - x, x - (right - 1)).clamp_min(0)
    dy = torch.maximum(top - y, y - (bottom - 1)).clamp_min(0)
    distance = torch.hypot(dy[:, None], dx[None, :])
    weight = (1 - distance / feather).clamp_min(0)
    weight = weight.square() * (3 - 2 * weight)
    area = mask[y0:y_end, x0:x_end]
    torch.maximum(area, weight, out=area)


def latent_geometry(height, width, latent_height, latent_width):
    """Account for the centered crop used by VAE Encode on unaligned images."""
    stride = min(height // latent_height, width // latent_width)
    if stride and height // stride == latent_height and width // stride == latent_width:
        encoded_height, encoded_width = latent_height * stride, latent_width * stride
        return (height - encoded_height) // 2, (width - encoded_width) // 2, encoded_height, encoded_width
    if abs(height * latent_width - width * latent_height) > max(height, width):
        raise ValueError("Retain FaceX needs the same framing in Original Image and Latent.")
    return 0, 0, height, width


class RetainFaceX:
    CATEGORY = "WorkflowX/Image Editing"
    DESCRIPTION = "Protect faces in an encoded image during refinement with a latent noise mask."
    FUNCTION = "protect"
    RETURN_TYPES = ("LATENT", "MASK")
    RETURN_NAMES = ("latent", "face_protection_mask")
    OUTPUT_TOOLTIPS = ("Connect to the refiner's latent input.", "White marks protected areas.")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "original_image": ("IMAGE", {"tooltip": "Use the image that was sent to VAE Encode."}),
            "latent": ("LATENT", {"tooltip": "Use the existing latent that goes into the refiner."}),
            "protection_strength": ("INT", {
                "default": 100, "min": 0, "max": 100,
                "tooltip": "Face protection as a percentage. Zero passes the latent through.",
            }),
            "face_margin": ("INT", {"default": 16, "min": 0, "max": 256, "tooltip": "Extra pixels around each detected face."}),
            "feather": ("INT", {"default": 16, "min": 0, "max": 256, "tooltip": "Soft transition outside the protected area."}),
        }}

    def protect(self, original_image, latent, protection_strength=100, face_margin=16, feather=16):
        batch, height, width, _ = original_image.shape
        protection = torch.zeros((batch, height, width), dtype=torch.float32, device="cpu")
        if protection_strength == 0:
            return latent, protection

        samples = latent["samples"]
        has_time_axis = samples.ndim == 5 and samples.shape[2] == 1
        if (samples.ndim != 4 and not has_time_axis) or any(size == 0 for size in samples.shape):
            raise ValueError(
                "Retain FaceX needs an encoded still-image latent with shape "
                "[batch, channels, height, width] or [batch, channels, 1, height, width]."
            )
        latent_batch = samples.shape[0]
        latent_height, latent_width = samples.shape[-2:]
        if batch not in (1, latent_batch):
            raise ValueError("Retain FaceX needs one source image or one source image per latent batch item.")
        top, left, crop_height, crop_width = latent_geometry(height, width, latent_height, latent_width)

        missed = 0
        for frame, mask in zip(original_image, protection):
            boxes = detect_faces(frame)
            if not boxes:
                missed += 1
            for box in boxes:
                paint_protection(mask, box, face_margin, feather)
        if missed:
            LOGGER.warning("Retain FaceX found no face in %d of %d source images.", missed, batch)
        protection.mul_(protection_strength / 100)
        cropped = protection[:, top:top + crop_height, left:left + crop_width]
        if not cropped.any():
            return latent, protection

        # Preserve even a face smaller than one latent cell. A cell that
        # contains protected pixels inherits the highest protection in it.
        pooled = F.adaptive_max_pool2d(cropped.unsqueeze(1), (latent_height, latent_width))
        denoise = 1 - pooled.expand(latent_batch, -1, -1, -1)
        if has_time_axis:
            denoise = denoise.unsqueeze(2)
        existing = latent.get("noise_mask")
        if existing is not None:
            from comfy.utils import reshape_mask

            if has_time_axis and existing.ndim < 5:
                # A 2D image mask stores its leading entries as batch items.
                existing = existing.reshape(-1, 1, 1, *existing.shape[-2:])
            existing = reshape_mask(existing.float(), denoise.shape)
            denoise = existing * denoise.to(existing.device)
        return {**latent, "noise_mask": denoise}, protection
