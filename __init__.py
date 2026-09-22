import asyncio
import base64
from collections import OrderedDict
import hashlib
import io
import json
import logging
import os
import re
import threading

from .voice_changer_x import (
    NODE_CLASS_MAPPINGS as VOICE_CHANGER_X_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as VOICE_CHANGER_X_NODE_DISPLAY_NAME_MAPPINGS,
)

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
from .anything_swap_bridge import (
    NODE_CLASS_MAPPINGS as ANYTHING_SWAP_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as ANYTHING_SWAP_NODE_DISPLAY_NAME_MAPPINGS,
)
from .nanobanana_full_api import (
    NODE_CLASS_MAPPINGS as NANOBANANA_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as NANOBANANA_NODE_DISPLAY_NAME_MAPPINGS,
)
from .remote_image_api import (
    NODE_CLASS_MAPPINGS as REMOTE_IMAGE_API_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as REMOTE_IMAGE_API_NODE_DISPLAY_NAME_MAPPINGS,
    register_routes as _register_remote_image_api_routes_on_app,
)
from .load_image_x import (
    NODE_CLASS_MAPPINGS as LOAD_IMAGE_X_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as LOAD_IMAGE_X_NODE_DISPLAY_NAME_MAPPINGS,
    register_routes as _register_load_image_x_routes_on_app,
)
from .load_video_x import (
    NODE_CLASS_MAPPINGS as LOAD_VIDEO_X_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as LOAD_VIDEO_X_NODE_DISPLAY_NAME_MAPPINGS,
    register_routes as _register_load_video_x_routes_on_app,
)
from .load_audio_x import (
    NODE_CLASS_MAPPINGS as LOAD_AUDIO_X_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as LOAD_AUDIO_X_NODE_DISPLAY_NAME_MAPPINGS,
    register_routes as _register_load_audio_x_routes_on_app,
)
from .preview_video_x import (
    NODE_CLASS_MAPPINGS as PREVIEW_VIDEO_X_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as PREVIEW_VIDEO_X_NODE_DISPLAY_NAME_MAPPINGS,
)
from .save_video_x import (
    NODE_CLASS_MAPPINGS as SAVE_VIDEO_X_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as SAVE_VIDEO_X_NODE_DISPLAY_NAME_MAPPINGS,
)
from .image_processor_x import (
    NODE_CLASS_MAPPINGS as IMAGE_PROCESSOR_X_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as IMAGE_PROCESSOR_X_NODE_DISPLAY_NAME_MAPPINGS,
    register_routes as _register_image_processor_x_routes_on_app,
)

WEB_DIRECTORY = "./web/js"
DEBUG_LOG_ROUTE = "/workflowx_configurator/debug_log"
IMAGE_COMPARE_EDIT_SAVE_ROUTE = "/workflowx_configurator/image_compare_edit_x/save"
IMAGE_COMPARE_EDIT_PREPARE_ROUTE = "/workflowx_configurator/image_compare_edit_x/prepare"
LORAX_LORAS_ROUTE = "/workflowx_configurator/lorax/loras"
LORAX_HASH_ROUTE = "/workflowx_configurator/lorax/hash"
LORAX_REMAP_ROUTE = "/workflowx_configurator/lorax/remap"
LOAD_DIFFUSION_MODEL_X_ROUTE = "/workflowx_configurator/load_diffusion_model_x/models"
LOAD_DIFFUSION_MODEL_X_HASH_ROUTE = "/workflowx_configurator/load_diffusion_model_x/hash"
LOAD_DIFFUSION_MODEL_X_REMAP_ROUTE = "/workflowx_configurator/load_diffusion_model_x/remap"
logger = logging.getLogger("WorkflowX_Configurator")

_WORKFLOWX_HASH_CACHE_MAX = 512
_WORKFLOWX_HASH_CACHE: OrderedDict[tuple[str, int, int], str] = OrderedDict()
_WORKFLOWX_HASH_CACHE_LOCK = threading.Lock()

NODE_CLASS_MAPPINGS = {
    **VOICE_CHANGER_X_NODE_CLASS_MAPPINGS,
    **WORKFLOWX_NODE_CLASS_MAPPINGS,
    **AFJ_NODE_CLASS_MAPPINGS,
    **XFLOWS_NODE_CLASS_MAPPINGS,
    **UNIFIED_AUTOPROMPTER_NODE_CLASS_MAPPINGS,
    **ANYTHING_SWAP_NODE_CLASS_MAPPINGS,
    **NANOBANANA_NODE_CLASS_MAPPINGS,
    **REMOTE_IMAGE_API_NODE_CLASS_MAPPINGS,
    **LOAD_IMAGE_X_NODE_CLASS_MAPPINGS,
    **LOAD_VIDEO_X_NODE_CLASS_MAPPINGS,
    **LOAD_AUDIO_X_NODE_CLASS_MAPPINGS,
    **PREVIEW_VIDEO_X_NODE_CLASS_MAPPINGS,
    **SAVE_VIDEO_X_NODE_CLASS_MAPPINGS,
    **IMAGE_PROCESSOR_X_NODE_CLASS_MAPPINGS,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    **VOICE_CHANGER_X_NODE_DISPLAY_NAME_MAPPINGS,
    **WORKFLOWX_NODE_DISPLAY_NAME_MAPPINGS,
    **AFJ_NODE_DISPLAY_NAME_MAPPINGS,
    **XFLOWS_NODE_DISPLAY_NAME_MAPPINGS,
    **UNIFIED_AUTOPROMPTER_NODE_DISPLAY_NAME_MAPPINGS,
    **ANYTHING_SWAP_NODE_DISPLAY_NAME_MAPPINGS,
    **NANOBANANA_NODE_DISPLAY_NAME_MAPPINGS,
    **REMOTE_IMAGE_API_NODE_DISPLAY_NAME_MAPPINGS,
    **LOAD_IMAGE_X_NODE_DISPLAY_NAME_MAPPINGS,
    **LOAD_VIDEO_X_NODE_DISPLAY_NAME_MAPPINGS,
    **LOAD_AUDIO_X_NODE_DISPLAY_NAME_MAPPINGS,
    **PREVIEW_VIDEO_X_NODE_DISPLAY_NAME_MAPPINGS,
    **SAVE_VIDEO_X_NODE_DISPLAY_NAME_MAPPINGS,
    **IMAGE_PROCESSOR_X_NODE_DISPLAY_NAME_MAPPINGS,
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


def _normalize_sha256(value: object) -> str:
    digest = str(value or "").strip().lower()
    return digest if re.fullmatch(r"[0-9a-f]{64}", digest) else ""


def _lorax_resolve_load_name(load_name: object, folder_paths_module) -> tuple[str, str]:
    normalized_name = _normalize_lorax_path(load_name).strip()
    parts = [part for part in normalized_name.split("/") if part not in ("", ".")]
    if (
        not normalized_name
        or normalized_name.startswith("/")
        or normalized_name.startswith("//")
        or re.match(r"^[A-Za-z]:/", normalized_name)
        or ".." in parts
    ):
        raise ValueError("A canonical ComfyUI LoRA load name is required.")

    try:
        resolved = folder_paths_module.get_full_path("loras", normalized_name)
    except Exception as exc:
        raise ValueError(f"Could not resolve LoRA '{normalized_name}'.") from exc
    if not resolved or not os.path.isfile(resolved):
        raise FileNotFoundError(f"LoRA '{normalized_name}' was not found.")
    return normalized_name, os.path.abspath(resolved)


def _workflowx_hash_file(path: str) -> tuple[str, int]:
    stat = os.stat(path)
    cache_key = (os.path.normcase(os.path.abspath(path)), int(stat.st_size), int(stat.st_mtime_ns))
    with _WORKFLOWX_HASH_CACHE_LOCK:
        cached = _WORKFLOWX_HASH_CACHE.get(cache_key)
        if cached:
            _WORKFLOWX_HASH_CACHE.move_to_end(cache_key)
            return cached, int(stat.st_size)

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    value = digest.hexdigest()
    with _WORKFLOWX_HASH_CACHE_LOCK:
        _WORKFLOWX_HASH_CACHE[cache_key] = value
        _WORKFLOWX_HASH_CACHE.move_to_end(cache_key)
        while len(_WORKFLOWX_HASH_CACHE) > _WORKFLOWX_HASH_CACHE_MAX:
            _WORKFLOWX_HASH_CACHE.popitem(last=False)
    return value, int(stat.st_size)


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
    file_size = 0
    if resolved:
        full_path = _normalize_lorax_path(resolved)
        try:
            file_size = int(os.path.getsize(resolved))
        except OSError:
            file_size = 0

    return {
        "load_name": normalized_name,
        "folder": folder,
        "filename": filename,
        "file_stem": file_stem,
        "extension": extension,
        "full_path": full_path,
        "file_size": file_size,
    }


def _lorax_hash_load_name(load_name: object, folder_paths_module) -> dict[str, object]:
    normalized_name, resolved = _lorax_resolve_load_name(load_name, folder_paths_module)
    digest, file_size = _workflowx_hash_file(resolved)
    entry = _lorax_lora_entry(normalized_name, folder_paths_module)
    entry.update({"sha256": digest, "file_size": file_size})
    return entry


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


def _remap_catalog_items(items: object, catalog: list[dict[str, object]]) -> dict[str, object]:
    requests = items if isinstance(items, list) else []
    by_name = {
        str(entry["load_name"]).lower(): entry
        for entry in catalog
        if entry.get("load_name") and entry.get("full_path")
    }
    identity_cache: dict[str, tuple[str, int]] = {}

    def identity(entry: dict[str, object]) -> tuple[str, int]:
        load_name = str(entry.get("load_name", ""))
        if load_name not in identity_cache:
            identity_cache[load_name] = _workflowx_hash_file(str(entry["full_path"]))
        return identity_cache[load_name]

    results: list[dict[str, object]] = []
    for index, raw in enumerate(requests):
        request = raw if isinstance(raw, dict) else {}
        row_id = str(request.get("row_id") or request.get("id") or index)
        load_name = _normalize_lorax_path(request.get("load_name")).strip()
        stored_hash = _normalize_sha256(request.get("sha256"))
        try:
            stored_size = max(0, int(request.get("file_size") or 0))
        except (TypeError, ValueError):
            stored_size = 0
        current = by_name.get(load_name.lower())

        if not stored_hash:
            if current is None:
                results.append({"row_id": row_id, "status": "unresolved", "reason": "missing_hash"})
                continue
            digest, file_size = identity(current)
            entry = dict(current)
            entry.update({"sha256": digest, "file_size": file_size})
            results.append({"row_id": row_id, "status": "unchanged", "entry": entry, "duplicate_count": 1})
            continue

        if current is not None:
            current_hash, current_size = identity(current)
            if current_hash == stored_hash:
                entry = dict(current)
                entry.update({"sha256": current_hash, "file_size": current_size})
                results.append({"row_id": row_id, "status": "unchanged", "entry": entry, "duplicate_count": 1})
                continue

        candidates = catalog
        if stored_size:
            candidates = [entry for entry in candidates if int(entry.get("file_size") or 0) == stored_size]
        matches: list[dict[str, object]] = []
        for candidate in candidates:
            try:
                digest, file_size = identity(candidate)
            except OSError:
                continue
            if digest != stored_hash:
                continue
            entry = dict(candidate)
            entry.update({"sha256": digest, "file_size": file_size})
            matches.append(entry)

        matches.sort(key=lambda entry: str(entry.get("load_name", "")).lower())
        if not matches:
            reason = "hash_mismatch" if current is not None else "no_hash_match"
            results.append({"row_id": row_id, "status": "unresolved", "reason": reason})
            continue

        chosen = matches[0]
        status = "unchanged" if chosen.get("load_name") == load_name else "remapped"
        results.append(
            {
                "row_id": row_id,
                "status": status,
                "entry": chosen,
                "duplicate_count": len(matches),
            }
        )

    summary = {
        status: sum(1 for result in results if result.get("status") == status)
        for status in ("remapped", "unchanged", "unresolved")
    }
    summary["duplicates"] = sum(max(0, int(result.get("duplicate_count") or 0) - 1) for result in results)
    return {"items": results, "summary": summary}


def _lorax_remap_items(items: object, folder_paths_module) -> dict[str, object]:
    return _remap_catalog_items(items, _build_lorax_lora_entries(folder_paths_module))


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

    @prompt_server.routes.post(LORAX_HASH_ROUTE)
    async def workflowx_lorax_hash(request):
        try:
            payload = await request.json()
            entry = await asyncio.to_thread(
                _lorax_hash_load_name,
                payload.get("load_name") if isinstance(payload, dict) else None,
                folder_paths,
            )
        except (FileNotFoundError, ValueError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except Exception as exc:
            logger.exception("LoraX could not hash a LoRA")
            return web.json_response({"error": f"Hashing failed: {exc}"}, status=500)
        return web.json_response(entry)

    @prompt_server.routes.post(LORAX_REMAP_ROUTE)
    async def workflowx_lorax_remap(request):
        try:
            payload = await request.json()
            result = await asyncio.to_thread(
                _lorax_remap_items,
                payload.get("items") if isinstance(payload, dict) else None,
                folder_paths,
            )
        except Exception as exc:
            logger.exception("LoraX remapping failed")
            return web.json_response({"error": f"Remapping failed: {exc}"}, status=500)
        return web.json_response(result)

    prompt_server._workflowx_lorax_routes = True


def _normalize_diffusion_model_path(path: object) -> str:
    return str(path or "").replace("\\", "/")


def _diffusion_model_entry(load_name: object, folder_paths_module) -> dict[str, object]:
    normalized_name = _normalize_diffusion_model_path(load_name).strip()
    folder = _normalize_diffusion_model_path(os.path.dirname(normalized_name)).strip("./")
    filename = os.path.basename(normalized_name)
    file_stem, extension = os.path.splitext(filename)

    full_path = ""
    try:
        resolved = folder_paths_module.get_full_path("diffusion_models", normalized_name)
    except Exception:
        resolved = None
    if resolved:
        full_path = _normalize_diffusion_model_path(resolved)

    file_size = 0
    if full_path:
        try:
            file_size = os.path.getsize(full_path)
        except (OSError, TypeError, ValueError):
            file_size = 0

    return {
        "load_name": normalized_name,
        "folder": folder,
        "filename": filename,
        "file_stem": file_stem,
        "extension": extension,
        "display_name": file_stem,
        "full_path": full_path,
        "file_size": file_size,
        "sub_type": "diffusion_model",
    }


def _diffusion_model_entry_matches_query(entry: dict[str, object], query: object) -> bool:
    terms = _lorax_search_terms(query)
    if not terms:
        return True

    haystack = " ".join(
        str(entry.get(key, "") or "").lower()
        for key in (
            "load_name",
            "folder",
            "filename",
            "file_stem",
            "display_name",
            "full_path",
            "extension",
        )
    )
    return all(term in haystack for term in terms)


def _build_diffusion_model_entries(folder_paths_module, query: object = "") -> list[dict[str, object]]:
    try:
        load_names = list(folder_paths_module.get_filename_list("diffusion_models"))
    except Exception:
        load_names = []

    entries = [
        _diffusion_model_entry(load_name, folder_paths_module)
        for load_name in load_names
        if str(load_name or "").strip()
    ]
    entries = [entry for entry in entries if _diffusion_model_entry_matches_query(entry, query)]
    return sorted(entries, key=lambda item: str(item.get("load_name", "")).lower())


def _resolve_diffusion_model_load_name(load_name: object, folder_paths_module) -> tuple[str, str]:
    normalized_name = _normalize_diffusion_model_path(load_name).strip()
    parts = [part for part in normalized_name.split("/") if part not in ("", ".")]
    if (
        not normalized_name
        or normalized_name.startswith("/")
        or normalized_name.startswith("//")
        or re.match(r"^[A-Za-z]:/", normalized_name)
        or ".." in parts
    ):
        raise ValueError("A canonical ComfyUI diffusion-model load name is required.")

    try:
        resolved = folder_paths_module.get_full_path("diffusion_models", normalized_name)
    except Exception as exc:
        raise ValueError(f"Could not resolve diffusion model '{normalized_name}'.") from exc
    if not resolved or not os.path.isfile(resolved):
        raise FileNotFoundError(f"Diffusion model '{normalized_name}' was not found.")
    return normalized_name, os.path.abspath(resolved)


def _hash_diffusion_model_load_name(load_name: object, folder_paths_module) -> dict[str, object]:
    normalized_name, resolved = _resolve_diffusion_model_load_name(load_name, folder_paths_module)
    digest, file_size = _workflowx_hash_file(resolved)
    entry = _diffusion_model_entry(normalized_name, folder_paths_module)
    entry.update({"sha256": digest, "file_size": file_size})
    return entry


def _remap_diffusion_model_items(items: object, folder_paths_module) -> dict[str, object]:
    return _remap_catalog_items(items, _build_diffusion_model_entries(folder_paths_module))


def _register_load_diffusion_model_x_route() -> None:
    try:
        from aiohttp import web
        import folder_paths
        from server import PromptServer
    except Exception:
        return

    prompt_server = getattr(PromptServer, "instance", None)
    if prompt_server is None or getattr(prompt_server, "_workflowx_load_diffusion_model_x_route", False):
        return

    @prompt_server.routes.get(LOAD_DIFFUSION_MODEL_X_ROUTE)
    async def workflowx_load_diffusion_model_x_models(request):
        query = ""
        try:
            query = request.query.get("search", "")
        except Exception:
            query = ""

        entries = _build_diffusion_model_entries(folder_paths, query)
        return web.json_response({"items": entries, "total": len(entries)})

    @prompt_server.routes.post(LOAD_DIFFUSION_MODEL_X_HASH_ROUTE)
    async def workflowx_load_diffusion_model_x_hash(request):
        try:
            payload = await request.json()
            entry = await asyncio.to_thread(
                _hash_diffusion_model_load_name,
                payload.get("load_name") if isinstance(payload, dict) else None,
                folder_paths,
            )
        except (FileNotFoundError, ValueError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except Exception as exc:
            logger.exception("Load Diffusion Model X could not hash a model")
            return web.json_response({"error": f"Hashing failed: {exc}"}, status=500)
        return web.json_response(entry)

    @prompt_server.routes.post(LOAD_DIFFUSION_MODEL_X_REMAP_ROUTE)
    async def workflowx_load_diffusion_model_x_remap(request):
        try:
            payload = await request.json()
            result = await asyncio.to_thread(
                _remap_diffusion_model_items,
                payload.get("items") if isinstance(payload, dict) else None,
                folder_paths,
            )
        except Exception as exc:
            logger.exception("Load Diffusion Model X remapping failed")
            return web.json_response({"error": f"Remapping failed: {exc}"}, status=500)
        return web.json_response(result)

    prompt_server._workflowx_load_diffusion_model_x_route = True


_register_debug_log_route()
_register_image_compare_edit_routes()
_register_lorax_routes()
_register_load_diffusion_model_x_route()


def _register_afj_routes() -> None:
    try:
        from server import PromptServer
    except Exception as exc:
        logger.warning("[JsonX] Could not import PromptServer for routes: %s", exc)
        return

    prompt_server = getattr(PromptServer, "instance", None)
    app = getattr(prompt_server, "app", None)
    if app is None:
        return

    try:
        register_visual_builder_routes(app)
    except Exception as exc:
        logger.warning("[JsonX] Could not register API routes: %s", exc)


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


def _register_remote_image_api_routes() -> None:
    try:
        from server import PromptServer
    except Exception as exc:
        logger.warning("[WorkflowX Remote Image API] Could not import PromptServer: %s", exc)
        return

    prompt_server = getattr(PromptServer, "instance", None)
    app = getattr(prompt_server, "app", None)
    if app is None:
        return
    try:
        _register_remote_image_api_routes_on_app(app)
    except Exception as exc:
        logger.warning("[WorkflowX Remote Image API] Could not register routes: %s", exc)


_register_remote_image_api_routes()


def _register_load_image_x_routes() -> None:
    try:
        from server import PromptServer
    except Exception as exc:
        logger.warning("[Load ImageX] Could not import PromptServer: %s", exc)
        return

    prompt_server = getattr(PromptServer, "instance", None)
    app = getattr(prompt_server, "app", None)
    if app is None:
        return
    try:
        _register_load_image_x_routes_on_app(app)
    except Exception as exc:
        logger.warning("[Load ImageX] Could not register routes: %s", exc)


_register_load_image_x_routes()


def _register_load_video_x_routes() -> None:
    try:
        from server import PromptServer
    except Exception as exc:
        logger.warning("[Load VideoX Adv] Could not import PromptServer: %s", exc)
        return

    prompt_server = getattr(PromptServer, "instance", None)
    app = getattr(prompt_server, "app", None)
    if app is None:
        return
    try:
        _register_load_video_x_routes_on_app(app)
    except Exception as exc:
        logger.warning("[Load VideoX Adv] Could not register routes: %s", exc)


_register_load_video_x_routes()


def _register_load_audio_x_routes() -> None:
    try:
        from server import PromptServer
    except Exception as exc:
        logger.warning("[Load AudioX] Could not import PromptServer: %s", exc)
        return

    prompt_server = getattr(PromptServer, "instance", None)
    app = getattr(prompt_server, "app", None)
    if app is None:
        return
    try:
        _register_load_audio_x_routes_on_app(app)
    except Exception as exc:
        logger.warning("[Load AudioX] Could not register routes: %s", exc)


_register_load_audio_x_routes()


def _register_image_processor_x_routes() -> None:
    try:
        from server import PromptServer
    except Exception as exc:
        logger.warning("[Image ProcessorX] Could not import PromptServer: %s", exc)
        return
    prompt_server = getattr(PromptServer, "instance", None)
    app = getattr(prompt_server, "app", None)
    if prompt_server is None:
        return
    try:
        _register_image_processor_x_routes_on_app(app)
    except Exception as exc:
        logger.warning("[Image ProcessorX] Could not register routes: %s", exc)


_register_image_processor_x_routes()

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]


# AuK is an isolated addition. Missing optional audio dependencies must not
# prevent the existing WorkflowX registry or routes from loading.
try:
    from .auk import (
        NODE_CLASS_MAPPINGS as AUK_NODE_CLASS_MAPPINGS,
        NODE_DISPLAY_NAME_MAPPINGS as AUK_NODE_DISPLAY_NAME_MAPPINGS,
        register_routes as register_auk_routes,
    )
    if NODE_CLASS_MAPPINGS.keys() & AUK_NODE_CLASS_MAPPINGS.keys():
        raise RuntimeError("WorkflowX AuK node ID collision")
    register_auk_routes()
    NODE_CLASS_MAPPINGS.update(AUK_NODE_CLASS_MAPPINGS)
    NODE_DISPLAY_NAME_MAPPINGS.update(AUK_NODE_DISPLAY_NAME_MAPPINGS)
except Exception:
    logger.exception("WorkflowX AuK could not load; existing WorkflowX nodes remain available")


# H3 RefMod retains its public node IDs, media types and HTTP routes so existing
# workflows and saved character packages continue to work after consolidation.
# H3 requires native MiniMax support; isolate its import on older ComfyUI builds.
try:
    from .h3_refmod import (
        NODE_CLASS_MAPPINGS as H3_REFMOD_NODE_CLASS_MAPPINGS,
        NODE_DISPLAY_NAME_MAPPINGS as H3_REFMOD_NODE_DISPLAY_NAME_MAPPINGS,
    )
    if NODE_CLASS_MAPPINGS.keys() & H3_REFMOD_NODE_CLASS_MAPPINGS.keys():
        raise RuntimeError("WorkflowX H3 RefMod node ID collision")
    NODE_CLASS_MAPPINGS.update(H3_REFMOD_NODE_CLASS_MAPPINGS)
    NODE_DISPLAY_NAME_MAPPINGS.update(H3_REFMOD_NODE_DISPLAY_NAME_MAPPINGS)
except Exception:
    logger.exception("WorkflowX H3 RefMod could not load; existing WorkflowX nodes remain available")
