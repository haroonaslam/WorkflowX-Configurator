import logging

from .nodes import (
    NODE_CLASS_MAPPINGS as WORKFLOWX_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as WORKFLOWX_NODE_DISPLAY_NAME_MAPPINGS,
)
from .afj_awesome_flex_json_v2 import (
    NODE_CLASS_MAPPINGS as AFJ_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as AFJ_NODE_DISPLAY_NAME_MAPPINGS,
    register_visual_builder_routes,
)
from .xflows_manager import (
    NODE_CLASS_MAPPINGS as XFLOWS_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as XFLOWS_NODE_DISPLAY_NAME_MAPPINGS,
)
from .unified_autoprompter import (
    NODE_CLASS_MAPPINGS as UNIFIED_AUTOPROMPTER_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as UNIFIED_AUTOPROMPTER_NODE_DISPLAY_NAME_MAPPINGS,
    register_routes as register_unified_autoprompter_routes,
)

WEB_DIRECTORY = "./web/js"
DEBUG_LOG_ROUTE = "/workflowx_configurator/debug_log"
logger = logging.getLogger("WorkflowX_Configurator")

NODE_CLASS_MAPPINGS = {
    **WORKFLOWX_NODE_CLASS_MAPPINGS,
    **AFJ_NODE_CLASS_MAPPINGS,
    **XFLOWS_NODE_CLASS_MAPPINGS,
    **UNIFIED_AUTOPROMPTER_NODE_CLASS_MAPPINGS,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    **WORKFLOWX_NODE_DISPLAY_NAME_MAPPINGS,
    **AFJ_NODE_DISPLAY_NAME_MAPPINGS,
    **XFLOWS_NODE_DISPLAY_NAME_MAPPINGS,
    **UNIFIED_AUTOPROMPTER_NODE_DISPLAY_NAME_MAPPINGS,
}


def _register_debug_log_route() -> None:
    try:
        from aiohttp import web
        from server import PromptServer
    except Exception:
        return

    prompt_server = getattr(PromptServer, "instance", None)
    if prompt_server is None or getattr(prompt_server, "_workflowx_debug_log_route", False):
        return

    @prompt_server.routes.post(DEBUG_LOG_ROUTE)
    async def workflowx_debug_log(request):
        try:
            payload = await request.json()
        except Exception:
            payload = {}

        message = str(payload.get("message", "")).strip()
        if message:
            logger.info("[WorkflowX_Configurator] %s", message)

        return web.json_response({"ok": True})

    prompt_server._workflowx_debug_log_route = True


_register_debug_log_route()


def _register_afj_routes() -> None:
    try:
        from server import PromptServer
    except Exception as exc:
        logger.warning("[AFJ] Could not import PromptServer for routes: %s", exc)
        return

    prompt_server = getattr(PromptServer, "instance", None)
    app = getattr(prompt_server, "app", None)
    if app is None:
        return

    try:
        register_visual_builder_routes(app)
    except Exception as exc:
        logger.warning("[AFJ] Could not register API routes: %s", exc)


_register_afj_routes()


def _register_unified_autoprompter_routes() -> None:
    try:
        from server import PromptServer
    except Exception as exc:
        logger.warning("[Unified Autoprompter X] Could not import PromptServer for routes: %s", exc)
        return

    prompt_server = getattr(PromptServer, "instance", None)
    app = getattr(prompt_server, "app", None)
    if app is None:
        return

    try:
        register_unified_autoprompter_routes(app)
    except Exception as exc:
        logger.warning("[Unified Autoprompter X] Could not register API routes: %s", exc)


_register_unified_autoprompter_routes()

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
