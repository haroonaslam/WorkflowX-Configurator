"""ComfyUI-H3RefCharacters. Derived from FranckyB and Luisacaotica (MIT)."""
from .generation import CharacterPicker, ModReferenceToVideo, InspectText
from .creation import CreateFolder
from .preparation import PrepareThumbnail
from .media import ImageReference, AudioReference, VideoReference
from . import routes

NODE_CLASS_MAPPINGS = {
    'H3RCInspectText': InspectText,
    'H3RCImageReference': ImageReference,
    'H3RCAudioReference': AudioReference,
    'H3RCVideoReference': VideoReference,
    'H3RCPrepareThumbnail': PrepareThumbnail,
    'H3RCCharacterPicker': CharacterPicker,
    'H3RCModReferenceToVideo': ModReferenceToVideo,
    'H3RCCreateFromFolder': CreateFolder,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'H3RCInspectText': 'Inspect H3 Prompt or Assignments',
    'H3RCImageReference': 'H3 Image Reference',
    'H3RCAudioReference': 'H3 Audio Reference',
    'H3RCVideoReference': 'H3 Video Reference',
    'H3RCPrepareThumbnail': 'Generate H3 Character Thumbnail',
    'H3RCCharacterPicker': 'H3 Ref Character Picker',
    'H3RCModReferenceToVideo': 'H3 Mod Reference to Video',
    'H3RCCreateFromFolder': 'Create H3 Ref Character From Folder',
}
# Frontend assets are served by WorkflowX's WEB_DIRECTORY.
__version__ = '0.4.0'
