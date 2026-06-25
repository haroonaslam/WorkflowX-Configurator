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
        generated_positive: str = "",
        generated_negative: str = "",
        final_prompt: str = "",
        image=None,
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
        )


NODE_CLASS_MAPPINGS = {
    "UnifiedAutoprompterX": UnifiedAutoprompterX,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "UnifiedAutoprompterX": "Unified Autoprompter X",
}
