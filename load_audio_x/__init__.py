"""WorkflowX Load AudioX node and browser routes."""

from __future__ import annotations

from .runtime import (
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
    analyze_handler,
    clean_stale_cache,
    files_handler,
    repair_handler,
)


def register_routes(app) -> None:
    router = getattr(app, "router", None)
    if router is None or getattr(app, "_workflowx_load_audio_x_routes", False):
        return
    router.add_get("/workflowx_configurator/load_audio_x/files", files_handler)
    router.add_post("/workflowx_configurator/load_audio_x/analyze", analyze_handler)
    router.add_post("/workflowx_configurator/load_audio_x/repair", repair_handler)
    app._workflowx_load_audio_x_routes = True
    if not getattr(app, "_workflowx_load_audio_x_cache_cleaned", False):
        clean_stale_cache()
        app._workflowx_load_audio_x_cache_cleaned = True


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "register_routes"]
