"""NanoBanana Full API node bundled with WorkflowX Configurator."""

from .node import NanoBananaAPINode_V2

NODE_CLASS_MAPPINGS = {
    "NanoBanana_Gemini_2_5_Flash_V2": NanoBananaAPINode_V2,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NanoBanana_Gemini_2_5_Flash_V2": "NanoBanana Full API",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
