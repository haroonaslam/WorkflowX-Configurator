"""WorkflowX Kie and Atlas image API nodes and browser routes."""

from __future__ import annotations

from .catalogs import public_catalogs
from .nodes import AtlasImageAPINode, KieImageAPINode
from .runtime import CancellationRegistry, PendingStore


NODE_CLASS_MAPPINGS = {
    "WorkflowX_KieImageAPI": KieImageAPINode,
    "WorkflowX_AtlasImageAPI": AtlasImageAPINode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "WorkflowX_KieImageAPI": "Kie Image API X",
    "WorkflowX_AtlasImageAPI": "Atlas Image API X",
}


def register_routes(app) -> None:
    """Register capability and pending-record routes on the ComfyUI app."""
    router = getattr(app, "router", None)
    if router is None or getattr(app, "_workflowx_remote_image_routes", False):
        return
    try:
        from aiohttp import web
    except Exception:
        return

    async def catalogs(_request):
        return web.json_response({"providers": public_catalogs()})

    async def pending(request):
        provider = str(request.match_info.get("provider", "")).lower()
        node_id = str(request.match_info.get("node_id", ""))
        if provider not in ("kie", "atlas"):
            return web.json_response({"error": "unsupported provider"}, status=400)
        record = PendingStore().get(provider, node_id)
        return web.json_response({"pending": bool(record), "record": record})

    async def forget(request):
        provider = str(request.match_info.get("provider", "")).lower()
        node_id = str(request.match_info.get("node_id", ""))
        if provider not in ("kie", "atlas"):
            return web.json_response({"error": "unsupported provider"}, status=400)
        removed = PendingStore().delete(provider, node_id)
        return web.json_response({"ok": True, "removed": removed, "warning": "Local record removed; the provider-side task was not cancelled."})

    async def cancel(request):
        provider = str(request.match_info.get("provider", "")).lower()
        node_id = str(request.match_info.get("node_id", ""))
        if provider not in ("kie", "atlas"):
            return web.json_response({"error": "unsupported provider"}, status=400)
        try:
            body = await request.json()
        except Exception:
            body = {}
        mode = str(body.get("mode", "retrieve")).lower()
        try:
            accepted = CancellationRegistry.request(provider, node_id, mode)
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        return web.json_response({
            "ok": accepted,
            "mode": mode,
            "message": "Cancellation requested; an in-flight network call may finish first." if accepted else "This node is not currently running.",
            "warning": "Provider-side work is not cancelled.",
        }, status=200 if accepted else 409)

    router.add_get("/workflowx_configurator/remote_image/catalogs", catalogs)
    router.add_get("/workflowx_configurator/remote_image/pending/{provider}/{node_id}", pending)
    router.add_delete("/workflowx_configurator/remote_image/pending/{provider}/{node_id}", forget)
    router.add_post("/workflowx_configurator/remote_image/cancel/{provider}/{node_id}", cancel)
    app._workflowx_remote_image_routes = True


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "register_routes"]
