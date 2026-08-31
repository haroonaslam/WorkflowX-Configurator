"""Compact native VIDEO preview with optional persistent saving."""

from __future__ import annotations

import os

import folder_paths


def _browser_safe_video(video):
    """Materialize an 8-bit, even-sized copy suitable for browser H.264 preview."""
    import torch.nn.functional as functional
    from comfy_api.latest import InputImpl, Types

    width, height = video.get_dimensions()
    components = video.get_components()
    pad_right = width % 2
    pad_bottom = height % 2
    images = components.images
    if pad_right or pad_bottom:
        images = functional.pad(images, (0, 0, 0, pad_right, 0, pad_bottom))
    return InputImpl.VideoFromComponents(
        Types.VideoComponents(
            images=images,
            audio=components.audio,
            frame_rate=components.frame_rate,
        ),
        bit_depth=8,
        color_space=video.get_color_space(),
    )


class PreviewVideoX:
    DESCRIPTION = (
        "Preview a native ComfyUI VIDEO in the node. The preview is temporary unless "
        "Save output is enabled. The VIDEO value passes through unchanged."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video": ("VIDEO", {"tooltip": "Native ComfyUI video to preview."}),
                "save_output": ("BOOLEAN", {"default": False}),
                "filename_prefix": ("STRING", {"default": "WorkflowX/preview-video"}),
            },
        }

    RETURN_TYPES = ("VIDEO", "VHS_FILENAMES")
    RETURN_NAMES = ("video", "filenames")
    OUTPUT_NODE = True
    CATEGORY = "WorkflowX/Video"
    FUNCTION = "preview_video"

    def preview_video(self, video, save_output=False, filename_prefix="WorkflowX/preview-video"):
        from comfy_api.latest import Types

        output_dir = (
            folder_paths.get_output_directory()
            if save_output
            else folder_paths.get_temp_directory()
        )
        width, height = video.get_dimensions()
        full_folder, filename, counter, subfolder, _prefix = folder_paths.get_save_image_path(
            filename_prefix,
            output_dir,
            width,
            height,
        )
        os.makedirs(full_folder, exist_ok=True)
        output_name = f"{filename}_{counter:05}_.mp4"
        output_path = os.path.join(full_folder, output_name)
        width, height = video.get_dimensions()
        preview_video = _browser_safe_video(video) if width % 2 or height % 2 else video
        try:
            preview_video.save_to(
                output_path,
                format=Types.VideoContainer.MP4,
                codec=Types.VideoCodec.H264,
            )
        except Exception as exc:
            # Compatible file-backed H.264 inputs normally stream-copy. If their
            # codec/pixel format cannot open in this PyAV build, retry as a
            # conservative 8-bit browser preview without changing the output VIDEO.
            if preview_video is not video or "avcodec_open2" not in str(exc):
                raise
            preview_video = _browser_safe_video(video)
            preview_video.save_to(
                output_path,
                format=Types.VideoContainer.MP4,
                codec=Types.VideoCodec.H264,
            )
        preview = {
            "filename": output_name,
            "subfolder": subfolder,
            "type": "output" if save_output else "temp",
        }
        return {
            "ui": {"images": [preview], "animated": (True,)},
            "result": (video, (bool(save_output), [output_path])),
        }


NODE_CLASS_MAPPINGS = {"WorkflowX_PreviewVideoX": PreviewVideoX}
NODE_DISPLAY_NAME_MAPPINGS = {"WorkflowX_PreviewVideoX": "Preview Video X"}


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "PreviewVideoX",
]
