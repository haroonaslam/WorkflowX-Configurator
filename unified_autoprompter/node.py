from __future__ import annotations

from .profiles import FORMAT_JSON, format_options, normalize_format, profile_options
from .prompt_io import build_outputs


class UnifiedAutoprompterX:
    CATEGORY = "WorkflowX_Configurator/Prompting"
    FUNCTION = "build"
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("prompt", "positive", "negative")
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "target_model": (profile_options(), {"default": "ideogram4"}),
                "prompt_format": (format_options(), {"default": FORMAT_JSON}),
                "negative_enabled": ("BOOLEAN", {"default": False}),
                "enable_bbox_json_input": (
                    "BOOLEAN",
                    {"default": False, "tooltip": "UI-managed toggle for syncing a connected bbox_json STRING into BBox Layout."},
                ),
                "enable_text_input": (
                    "BOOLEAN",
                    {"default": False, "tooltip": "UI-managed toggle for using raw_prompt_text as the prompt source during generation."},
                ),
                "refresh_vram": (
                    "BOOLEAN",
                    {"default": False, "tooltip": "UI-managed toggle to unload ComfyUI models and clear cache before prompt generation."},
                ),
                "disable_color_palette": (
                    "BOOLEAN",
                    {"default": False, "tooltip": "UI-managed toggle to strip color_palette blocks from JSON outputs without changing the stored model response."},
                ),
                "generated_positive": (
                    "STRING",
                    {"default": "", "multiline": True, "tooltip": "Managed by the WorkflowX UI."},
                ),
                "generated_negative": (
                    "STRING",
                    {"default": "", "multiline": True, "tooltip": "Managed by the WorkflowX UI."},
                ),
                "final_prompt": (
                    "STRING",
                    {"default": "", "multiline": True, "tooltip": "Managed by the WorkflowX UI."},
                ),
            },
            "optional": {
                "image": ("IMAGE",),
                "bbox_json": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "forceInput": True,
                        "tooltip": "Optional connected raw bbox layout JSON for the frontend BBox Layout Sync action.",
                    },
                ),
                "raw_prompt_text": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "forceInput": True,
                        "tooltip": "Optional connected raw prompt text used during generation when enabled in the UI.",
                    },
                ),
                "ui_state": (
                    "STRING",
                    {"default": "{}", "multiline": True, "tooltip": "Managed by the WorkflowX UI."},
                ),
            },
        }

    def build(
        self,
        target_model: str = "ideogram4",
        prompt_format: str = FORMAT_JSON,
        negative_enabled: bool = False,
        enable_bbox_json_input: bool = False,
        enable_text_input: bool = False,
        refresh_vram: bool = False,
        disable_color_palette: bool = False,
        generated_positive: str = "",
        generated_negative: str = "",
        final_prompt: str = "",
        image=None,
        bbox_json: str = "",
        raw_prompt_text: str = "",
        ui_state: str = "{}",
    ) -> tuple[str, str, str]:
        prompt_format = normalize_format(target_model, prompt_format)
        return build_outputs(
            target_model=target_model,
            prompt_format=prompt_format,
            positive=generated_positive,
            negative=generated_negative,
            final_prompt=final_prompt,
            negative_enabled=negative_enabled,
            disable_color_palette=disable_color_palette,
        )


NODE_CLASS_MAPPINGS = {
    "UnifiedAutoprompterX": UnifiedAutoprompterX,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "UnifiedAutoprompterX": "Unified Autoprompter X",
}
