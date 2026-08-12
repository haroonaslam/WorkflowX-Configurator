from .visual_builder import (
    AFJPromptTemplateImporterNode,
    FluxTemplateRandomizerNode,
    FluxVisualJsonBuilderNode,
    LLMToJsonXNode,
    register_visual_builder_routes,
)

NODE_CLASS_MAPPINGS = {
    "FluxVisualJsonBuilder": FluxVisualJsonBuilderNode,
    "FluxTemplateRandomizer": FluxTemplateRandomizerNode,
    "AFJPromptTemplateImporter": AFJPromptTemplateImporterNode,
    "LLMToJsonX": LLMToJsonXNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "FluxVisualJsonBuilder": "JsonX - Visual Builder",
    "FluxTemplateRandomizer": "JsonX - Template Randomizer",
    "AFJPromptTemplateImporter": "JsonX - Prompt Template Importer",
    "LLMToJsonX": "LLM to JsonX",
}

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "register_visual_builder_routes",
]
