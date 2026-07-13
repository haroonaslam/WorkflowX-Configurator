"""WorkflowX Load ImageX node and browser routes."""

from __future__ import annotations

from .runtime import (
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
    catalog_handler,
    thumbnail_handler,
)


def register_routes(app) -> None:
    router = getattr(app, "router", None)
    if router is None or getattr(app, "_workflowx_load_image_x_routes", False):
        return
    router.add_get("/workflowx_configurator/load_image_x/images", catalog_handler)
    router.add_get("/workflowx_configurator/load_image_x/thumbnail", thumbnail_handler)
    app._workflowx_load_image_x_routes = True


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "register_routes"]
