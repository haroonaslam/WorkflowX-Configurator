"""JPEG output node using ComfyUI's native saved-image preview contract."""
import os

import numpy as np
from PIL import Image


class SaveImageJpg:
    DEPRECATED = True
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "images": ("IMAGE", {"tooltip": "Images to save and preview. Transparency is composited over white because JPEG has no alpha channel."}),
            "filename_prefix": ("STRING", {"default": "ComfyUI", "tooltip": "Output filename prefix; subfolders and ComfyUI filename substitutions are supported."}),
            "quality": ("INT", {"default": 95, "min": 1, "max": 100, "tooltip": "JPEG quality. Higher values give larger files. Uses 4:4:4 color sampling. JPEG files do not embed a reloadable ComfyUI workflow."}),
        }}

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "save_images"
    OUTPUT_NODE = True
    CATEGORY = "WorkflowX/Image"
    DESCRIPTION = "Save JPG files in the ComfyUI output directory with the standard in-node image preview. The IMAGE output passes through the original input, not the compressed JPEG."
    SEARCH_ALIASES = ["save jpeg", "save jpg", "export image"]

    def save_images(self, images, filename_prefix="ComfyUI", quality=95):
        import folder_paths
        import comfy.model_management as mm

        if images.ndim != 4 or images.shape[-1] not in (1, 3, 4) or min(images.shape[:3]) < 1:
            raise ValueError("Save Image Jpg expects a nonempty BHWC grayscale, RGB or RGBA image batch")
        if type(quality) is not int or not 1 <= quality <= 100:
            raise ValueError("JPEG quality must be an integer between 1 and 100")
        folder, filename, counter, subfolder, _ = folder_paths.get_save_image_path(
            filename_prefix, folder_paths.get_output_directory(), images.shape[2], images.shape[1])
        results = []
        for batch_number, tensor in enumerate(images):
            mm.throw_exception_if_processing_interrupted()
            array = np.clip(tensor.detach().cpu().numpy(), 0, 1)
            if array.shape[-1] == 4:
                array = array[..., :3] * array[..., 3:4] + (1 - array[..., 3:4])
            elif array.shape[-1] == 1:
                array = np.repeat(array, 3, axis=-1)
            image = Image.fromarray((array * 255).astype(np.uint8))
            stem = filename.replace("%batch_num%", str(batch_number))
            # Exclusive creation also protects files written by another saver.
            while True:
                name = f"{stem}_{counter:05}_.jpg"
                path = os.path.join(folder, name)
                try:
                    output = open(path, "xb")
                    break
                except FileExistsError:
                    counter += 1
            try:
                with output:
                    image.save(output, format="JPEG", quality=quality, subsampling=0, optimize=True)
            except BaseException:
                os.unlink(path)  # Only this invocation's incomplete new file.
                raise
            results.append({"filename": name, "subfolder": subfolder, "type": "output"})
            counter += 1
        return {"ui": {"images": results}, "result": (images,)}


NODE_CLASS_MAPPINGS = {"WorkflowX_SaveImageJpg": SaveImageJpg}
NODE_DISPLAY_NAME_MAPPINGS = {"WorkflowX_SaveImageJpg": "View Image (Format) — Legacy JPG"}
