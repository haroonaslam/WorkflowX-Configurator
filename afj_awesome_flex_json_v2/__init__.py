from .visual_builder import (
    AFJPromptTemplateImporterNode,
    FluxTemplateRandomizerNode,
    FluxVisualJsonBuilderNode,
    register_visual_builder_routes,
)

NODE_CLASS_MAPPINGS = {
    "FluxVisualJsonBuilder": FluxVisualJsonBuilderNode,
    "FluxTemplateRandomizer": FluxTemplateRandomizerNode,
    "AFJPromptTemplateImporter": AFJPromptTemplateImporterNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "FluxVisualJsonBuilder": "AFJ - Visual Builder",
    "FluxTemplateRandomizer": "AFJ - Template Randomizer",
    "AFJPromptTemplateImporter": "AFJ - Prompt Template Importer",
}

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "register_visual_builder_routes",
]
