"""WorkflowX Load VideoX Adv node and metadata route."""

from __future__ import annotations

from .runtime import (
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
    metadata_handler,
)


def register_routes(app) -> None:
    router = getattr(app, "router", None)
    if router is None or getattr(app, "_workflowx_load_video_x_routes", False):
        return
    router.add_get("/workflowx_configurator/load_video_x/metadata", metadata_handler)
    app._workflowx_load_video_x_routes = True


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "register_routes"]
