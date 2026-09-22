"""WorkflowX-owned AuK nodes, isolated from standalone AuK registrations."""
from .nodes.nodes import (
    WorkflowXAuKModelLoader, WorkflowXAuKEncoderLoader, WorkflowXAuKVAELoader, WorkflowXAuKInstructionEncode, WorkflowXAuKGenerateEdit, WorkflowXAuKInstructionBuilder, WorkflowXAuKWhisperTranscribe, WorkflowXAuKPromptEnhance, WorkflowXAuKChainedClone, WorkflowXAuKChainedCloneReviewStep, WorkflowXAuKSegmentFinalize
)

NODE_CLASSES = [WorkflowXAuKModelLoader, WorkflowXAuKEncoderLoader, WorkflowXAuKVAELoader, WorkflowXAuKInstructionEncode, WorkflowXAuKGenerateEdit, WorkflowXAuKInstructionBuilder, WorkflowXAuKWhisperTranscribe, WorkflowXAuKPromptEnhance, WorkflowXAuKChainedClone, WorkflowXAuKChainedCloneReviewStep, WorkflowXAuKSegmentFinalize]
NODE_CLASS_MAPPINGS = {cls.define_schema().node_id: cls for cls in NODE_CLASSES}
NODE_DISPLAY_NAME_MAPPINGS = {cls.define_schema().node_id: cls.define_schema().display_name for cls in NODE_CLASSES}

def register_routes():
    from .nodes.chain_review import register_routes as register_review_routes
    register_review_routes()
