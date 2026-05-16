from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

import logging

WEB_DIRECTORY = "./web/js"
DEBUG_LOG_ROUTE = "/workflowx_configurator/debug_log"
logger = logging.getLogger("WorkflowX_Configurator")


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

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
