import base64
import io
import json
import logging
import os
import re

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
IMAGE_COMPARE_EDIT_SAVE_ROUTE = "/workflowx_configurator/image_compare_edit_x/save"
IMAGE_COMPARE_EDIT_PREPARE_ROUTE = "/workflowx_configurator/image_compare_edit_x/prepare"
LORAX_LORAS_ROUTE = "/workflowx_configurator/lorax/loras"
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


def _safe_filename_prefix(prefix: object, fallback: str = "ImageCompareEditX") -> str:
    value = str(prefix or fallback).replace("\\", "/").split("/")[-1]
    value = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("._-")
    return value[:64] or fallback


def _decode_png_data_url(image_b64: object):
    if not isinstance(image_b64, str):
        return None

    payload = image_b64.strip()
    if "," in payload:
        header, payload = payload.split(",", 1)
        if "base64" not in header.lower():
            return None

    try:
        raw = base64.b64decode(payload, validate=True)
        from PIL import Image

        image = Image.open(io.BytesIO(raw))
        image.load()
        return image
    except Exception:
        return None


def _build_pnginfo(prompt: object = None, workflow: object = None):
    try:
        from PIL.PngImagePlugin import PngInfo
    except Exception:
        return None

    pnginfo = PngInfo()
    if prompt is not None:
        try:
            pnginfo.add_text("prompt", json.dumps(prompt))
        except (TypeError, ValueError):
            pass
    if workflow is not None:
        try:
            pnginfo.add_text("workflow", json.dumps(workflow))
        except (TypeError, ValueError):
            pass
    return pnginfo


def _image_to_data_url(image, pnginfo=None) -> str:
    buffer = io.BytesIO()
    image.save(buffer, "PNG", pnginfo=pnginfo)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return "data:image/png;base64," + encoded


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


def _register_image_compare_edit_routes() -> None:
    try:
        from aiohttp import web
        import folder_paths
        from server import PromptServer
    except Exception:
        return

    prompt_server = getattr(PromptServer, "instance", None)
    if prompt_server is None or getattr(prompt_server, "_workflowx_image_compare_edit_routes", False):
        return

    @prompt_server.routes.post(IMAGE_COMPARE_EDIT_SAVE_ROUTE)
    async def workflowx_image_compare_edit_save(request):
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)

        image = _decode_png_data_url(data.get("image_b64"))
        if image is None:
            return web.json_response({"error": "invalid image data"}, status=400)

        prefix = _safe_filename_prefix(data.get("filename_prefix"), "ImageCompareEditX")
        workflow = data.get("workflow")
        prompt = data.get("prompt")

        try:
            output_dir = folder_paths.get_output_directory()
            full_folder, name, counter, subfolder, _ = folder_paths.get_save_image_path(
                prefix,
                output_dir,
                image.width,
                image.height,
            )
            os.makedirs(full_folder, exist_ok=True)
            filename = f"{name}_{counter:05}_.png"
            image.save(
                os.path.join(full_folder, filename),
                "PNG",
                pnginfo=_build_pnginfo(prompt=prompt, workflow=workflow),
            )
        except Exception as exc:
            return web.json_response({"error": f"save failed: {exc}"}, status=500)

        return web.json_response(
            {"status": "success", "filename": filename, "subfolder": subfolder}
        )

    @prompt_server.routes.post(IMAGE_COMPARE_EDIT_PREPARE_ROUTE)
    async def workflowx_image_compare_edit_prepare(request):
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)

        image = _decode_png_data_url(data.get("image_b64"))
        if image is None:
            return web.json_response({"error": "invalid image data"}, status=400)

        prefix = _safe_filename_prefix(data.get("filename_prefix"), "ImageCompareEditX")
        workflow = data.get("workflow")
        prompt = data.get("prompt")

        try:
            pnginfo = _build_pnginfo(prompt=prompt, workflow=workflow)
            output_dir = folder_paths.get_output_directory()
            _, name, counter, _, _ = folder_paths.get_save_image_path(
                prefix,
                output_dir,
                image.width,
                image.height,
            )
            image_b64 = _image_to_data_url(image, pnginfo=pnginfo)
            suggested_filename = f"{name}_{counter:05}_.png"
        except Exception as exc:
            return web.json_response({"error": f"prepare failed: {exc}"}, status=500)

        return web.json_response(
            {
                "image_b64": image_b64,
                "suggested_filename": suggested_filename,
            }
        )

    prompt_server._workflowx_image_compare_edit_routes = True


def _normalize_lorax_path(path: object) -> str:
    return str(path or "").replace("\\", "/")


def _lorax_lora_entry(load_name: object, folder_paths_module) -> dict[str, object]:
    normalized_name = _normalize_lorax_path(load_name).strip()
    folder = _normalize_lorax_path(os.path.dirname(normalized_name)).strip("./")
    filename = os.path.basename(normalized_name)
    file_stem, extension = os.path.splitext(filename)

    full_path = ""
    try:
        resolved = folder_paths_module.get_full_path("loras", normalized_name)
    except Exception:
        resolved = None
    if resolved:
        full_path = _normalize_lorax_path(resolved)

    return {
        "load_name": normalized_name,
        "folder": folder,
        "filename": filename,
        "file_stem": file_stem,
        "extension": extension,
        "full_path": full_path,
    }


def _lorax_search_terms(query: object) -> list[str]:
    return [
        term.strip().lower()
        for term in str(query or "").replace("\\", " ").replace("/", " ").split()
        if term.strip()
    ]


def _lorax_entry_matches_query(entry: dict[str, object], query: object) -> bool:
    terms = _lorax_search_terms(query)
    if not terms:
        return True

    haystack = " ".join(
        str(entry.get(key, "") or "").lower()
        for key in ("load_name", "folder", "filename", "file_stem", "full_path")
    )
    return all(term in haystack for term in terms)


def _build_lorax_lora_entries(folder_paths_module, query: object = "") -> list[dict[str, object]]:
    try:
        load_names = list(folder_paths_module.get_filename_list("loras"))
    except Exception:
        load_names = []

    entries = [
        _lorax_lora_entry(load_name, folder_paths_module)
        for load_name in load_names
        if str(load_name or "").strip()
    ]
    entries = [entry for entry in entries if _lorax_entry_matches_query(entry, query)]
    return sorted(entries, key=lambda item: str(item.get("load_name", "")).lower())


def _register_lorax_routes() -> None:
    try:
        from aiohttp import web
        import folder_paths
        from server import PromptServer
    except Exception:
        return

    prompt_server = getattr(PromptServer, "instance", None)
    if prompt_server is None or getattr(prompt_server, "_workflowx_lorax_routes", False):
        return

    @prompt_server.routes.get(LORAX_LORAS_ROUTE)
    async def workflowx_lorax_loras(request):
        query = ""
        try:
            query = request.query.get("search", "")
        except Exception:
            query = ""

        entries = _build_lorax_lora_entries(folder_paths, query)
        return web.json_response({"items": entries, "total": len(entries)})

    prompt_server._workflowx_lorax_routes = True


_register_debug_log_route()
_register_image_compare_edit_routes()
_register_lorax_routes()


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
