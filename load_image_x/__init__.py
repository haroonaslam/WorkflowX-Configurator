"""WorkflowX Load ImageX node and browser routes."""

from __future__ import annotations

from .runtime import (
    NODE_CLASS_MAPPINGS as LOAD_IMAGE_X_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as LOAD_IMAGE_X_NODE_DISPLAY_NAME_MAPPINGS,
    catalog_handler,
    delete_images_handler,
    thumbnail_handler,
)
from .advanced import (
    NODE_CLASS_MAPPINGS as LOAD_IMAGE_X_ADV_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as LOAD_IMAGE_X_ADV_NODE_DISPLAY_NAME_MAPPINGS,
)
from .direct import direct_upload_handler
from .source import SOURCE_NODE_ID, ImageXSource, register_source_routes


NODE_CLASS_MAPPINGS = {
    **LOAD_IMAGE_X_NODE_CLASS_MAPPINGS,
    **LOAD_IMAGE_X_ADV_NODE_CLASS_MAPPINGS,
    SOURCE_NODE_ID: ImageXSource,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    **LOAD_IMAGE_X_NODE_DISPLAY_NAME_MAPPINGS,
    **LOAD_IMAGE_X_ADV_NODE_DISPLAY_NAME_MAPPINGS,
    SOURCE_NODE_ID: "ImageX Source",
}


def register_routes(app) -> None:
    router = getattr(app, "router", None)
    if router is None or getattr(app, "_workflowx_load_image_x_routes", False):
        return
    router.add_get("/workflowx_configurator/load_image_x/images", catalog_handler)
    router.add_get("/workflowx_configurator/load_image_x/thumbnail", thumbnail_handler)
    router.add_post("/workflowx_configurator/load_image_x/delete", delete_images_handler)
    router.add_post("/workflowx_configurator/load_image_x/direct", direct_upload_handler)
    register_source_routes(router)
    app._workflowx_load_image_x_routes = True


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "register_routes"]
