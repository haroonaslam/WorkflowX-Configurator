"""Shared provider runtime for WorkflowX remote image API nodes."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import torch
from PIL import Image

from .catalogs import PROFILE_MAPS


KIE_CREATE_URL = "https://api.kie.ai/api/v1/jobs/createTask"
KIE_STATUS_URL = "https://api.kie.ai/api/v1/jobs/recordInfo"
KIE_UPLOAD_BASE64_URL = "https://kieai.redpandaai.co/api/file-base64-upload"
KIE_UPLOAD_STREAM_URL = "https://kieai.redpandaai.co/api/file-stream-upload"
ATLAS_CREATE_URL = "https://api.atlascloud.ai/api/v1/model/generateImage"
ATLAS_STATUS_URL = "https://api.atlascloud.ai/api/v1/model/prediction"
ATLAS_UPLOAD_URL = "https://api.atlascloud.ai/api/v1/model/uploadMedia"
USER_AGENT = "WorkflowX-Configurator/2"


class ProviderTerminalError(RuntimeError):
    """A provider has definitively failed a submitted task."""


class LocalCancellation(RuntimeError):
    """WorkflowX was asked to stop local work for this node."""

    def __init__(self, mode: str):
        self.mode = mode
        super().__init__("Remote image processing was stopped locally.")


class CancellationRegistry:
    """Thread-safe node-local cancellation signals set by browser routes."""

    _lock = threading.RLock()
    _states: dict[str, dict[str, Any]] = {}

    @classmethod
    def _key(cls, provider: str, node_id: object) -> str:
        return f"{provider}:{node_id}"

    @classmethod
    def begin(cls, provider: str, node_id: object) -> threading.Event:
        with cls._lock:
            event = threading.Event()
            cls._states[cls._key(provider, node_id)] = {"event": event, "mode": "", "active": True}
            return event

    @classmethod
    def request(cls, provider: str, node_id: object, mode: str) -> bool:
        if mode not in ("continue", "retrieve"):
            raise ValueError("Cancellation mode must be continue or retrieve.")
        with cls._lock:
            state = cls._states.get(cls._key(provider, node_id))
            if not state or not state.get("active"):
                return False
            state["mode"] = mode
            state["event"].set()
            return True

    @classmethod
    def check(cls, provider: str, node_id: object) -> None:
        with cls._lock:
            state = cls._states.get(cls._key(provider, node_id))
            if state and state["event"].is_set():
                raise LocalCancellation(str(state.get("mode") or "retrieve"))

    @classmethod
    def event(cls, provider: str, node_id: object) -> threading.Event | None:
        with cls._lock:
            state = cls._states.get(cls._key(provider, node_id))
            return state.get("event") if state else None

    @classmethod
    def finish(cls, provider: str, node_id: object) -> None:
        with cls._lock:
            cls._states.pop(cls._key(provider, node_id), None)


def emit_status(provider: str, node_id: object, phase: str, message: str, *, level: str = "info", **extra: Any) -> None:
    """Send a bounded, secret-free status event to the matching browser node."""
    payload = {
        "provider": provider,
        "node_id": str(node_id),
        "phase": phase,
        "level": level,
        "message": str(message),
        "timestamp_epoch_ms": int(time.time() * 1000),
        **extra,
    }
    try:
        server_module = sys.modules.get("server")
        if server_module is None:
            return
        PromptServer = server_module.PromptServer
        PromptServer.instance.send_sync("workflowx.remote_image.status", payload)
    except Exception:
        # Tests and headless imports do not have a PromptServer.
        return


def redact(value: object, secret: str) -> str:
    text = str(value or "")
    if secret:
        text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"(?i)(authorization|x-api-key)\s*[:=]\s*[^,}\s]+", r"\1=[REDACTED]", text)
    return re.sub(r"(https?://[^\s?'\"]+)\?[^\s'\"]+", r"\1?[REDACTED_QUERY]", text)


def resolve_api_key(provider: str, widget_value: object) -> str:
    direct = str(widget_value or "").strip()
    if direct:
        return direct
    if provider == "kie":
        return os.getenv("KIE_API_KEY", "").strip()
    return os.getenv("ATLAS_API_KEY", "").strip() or os.getenv("ATLASCLOUD_API_KEY", "").strip()


def resolve_profile(provider: str, model_id: str) -> dict[str, Any]:
    profiles = PROFILE_MAPS[provider]
    if model_id not in profiles:
        raise ValueError(f"Unsupported {provider.title()} model: {model_id}")
    return profiles[model_id]


def selected_size_options(profile: dict[str, Any]) -> list[str]:
    return list(profile.get("sizes") or [])


def validate_generation(profile: dict[str, Any], aspect_ratio: str, image_size: str, reference_count: int, prompt: str | None = None, settings: dict[str, Any] | None = None) -> None:
    settings = settings or {}
    maximum = int(profile.get("max_references", 14))
    if reference_count > maximum:
        raise ValueError(f"{profile['label']} supports up to {maximum} reference image(s); received {reference_count}.")
    aspects = list(profile.get("aspect_ratios") or [])
    if aspects and aspect_ratio not in aspects:
        raise ValueError(f"{profile['label']} supports aspect ratios: {', '.join(aspects)}")
    sizes = selected_size_options(profile)
    custom = profile.get("custom_size") or {}
    if sizes and image_size not in sizes and not settings.get("custom_size_enabled"):
        raise ValueError(f"{profile['label']} supports size/quality values: {', '.join(sizes)}")
    qualities = list(profile.get("quality_options") or [])
    if qualities and str(settings.get("quality", profile.get("default_quality"))) not in qualities:
        raise ValueError(f"{profile['label']} supports output quality values: {', '.join(qualities)}")
    formats = list(profile.get("output_formats") or [])
    if formats and str(settings.get("output_format", profile.get("default_output_format"))).lower() not in formats:
        raise ValueError(f"{profile['label']} supports output types: {', '.join(formats)}")
    maximum_prompt = profile.get("prompt_max_length")
    if prompt is not None and not str(prompt or "").strip():
        raise ValueError("Prompt is required.")
    if prompt is not None and maximum_prompt and len(prompt) > int(maximum_prompt):
        raise ValueError(f"{profile['label']} accepts prompts up to {maximum_prompt} characters; received {len(prompt)}.")
    if settings.get("custom_size_enabled"):
        if not custom:
            raise ValueError(f"{profile['label']} does not support a custom output size.")
        if settings.get("custom_size_auto") and custom.get("supports_auto"):
            return
        width = int(settings.get("custom_width", 0))
        height = int(settings.get("custom_height", 0))
        minimum = int(custom.get("min_edge", custom.get("width_height_step", 64)))
        maximum = int(custom.get("max_edge", 4096))
        step = int(custom.get("width_height_step", 1))
        if width < minimum or height < minimum or width > maximum or height > maximum or width % step or height % step:
            raise ValueError(f"Custom size must use {step}px steps with each edge between {minimum} and {maximum}px.")
        ratio = max(width, height) / min(width, height)
        pixels = width * height
        if custom.get("max_aspect_ratio") and ratio > float(custom["max_aspect_ratio"]):
            raise ValueError(f"Custom size must not exceed a {custom['max_aspect_ratio']}:1 aspect ratio.")
        if custom.get("min_pixels") and pixels < int(custom["min_pixels"]):
            raise ValueError(f"Custom size must contain at least {custom['min_pixels']:,} pixels.")
        if custom.get("max_pixels") and pixels > int(custom["max_pixels"]):
            raise ValueError(f"Custom size must contain no more than {custom['max_pixels']:,} pixels.")
    elif profile.get("provider") == "kie" and profile.get("id") == "gpt2":
        if aspect_ratio == "auto" and image_size.upper() != "1K":
            raise ValueError("GPT Image 2 with aspect ratio auto supports only 1K.")
        if aspect_ratio == "1:1" and image_size.upper() == "4K":
            raise ValueError("GPT Image 2 does not support 4K at aspect ratio 1:1.")


def tensor_images(values: Iterable[Any]) -> list[torch.Tensor]:
    frames: list[torch.Tensor] = []
    for value in values:
        if value is None:
            continue
        if not isinstance(value, torch.Tensor):
            raise ValueError("Reference inputs must be ComfyUI IMAGE tensors.")
        tensor = value.detach().cpu()
        if tensor.ndim == 3:
            tensor = tensor.unsqueeze(0)
        if tensor.ndim != 4 or tensor.shape[-1] not in (3, 4):
            raise ValueError(f"Unsupported IMAGE tensor shape: {tuple(tensor.shape)}")
        frames.extend(tensor[index] for index in range(tensor.shape[0]))
    return frames


def tensor_to_png(frame: torch.Tensor, max_edge: int = 5120) -> bytes:
    array = (frame[..., :3].clamp(0.0, 1.0).numpy() * 255.0).round().astype(np.uint8)
    image = Image.fromarray(array, "RGB")
    maximum = max(512, min(8192, int(max_edge)))
    if max(image.size) > maximum:
        scale = maximum / max(image.size)
        image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def placeholder_tensor(profile: dict[str, Any], aspect: str, image_size: str, settings: dict[str, Any]) -> torch.Tensor:
    """Return a valid black IMAGE matching the requested canvas where possible."""
    if settings.get("custom_size_enabled") and settings.get("custom_size_auto"):
        width = height = 64
    elif settings.get("custom_size_enabled"):
        width, height = int(settings.get("custom_width", 64)), int(settings.get("custom_height", 64))
    else:
        text = str(image_size or "")
        separator = "*" if "*" in text else "x" if "x" in text.lower() else ""
        if separator:
            try:
                width, height = (int(part) for part in text.lower().replace("x", "*").split("*", 1))
            except ValueError:
                width = height = 64
        else:
            tier = {"1K": 1024, "2K": 2048, "4K": 4096}.get(text.upper(), 1024)
            try:
                left, right = (int(part) for part in str(aspect or "1:1").split(":", 1))
                if left >= right:
                    width, height = tier, max(1, round(tier * right / left))
                else:
                    width, height = max(1, round(tier * left / right)), tier
            except (ValueError, ZeroDivisionError):
                width = height = 64
    width = max(1, min(8192, width))
    height = max(1, min(8192, height))
    return torch.zeros((1, height, width, 3), dtype=torch.float32)


def image_bytes_to_tensor(data: bytes) -> torch.Tensor:
    try:
        image = Image.open(io.BytesIO(data)).convert("RGB")
        image.load()
    except Exception as exc:
        raise RuntimeError(f"Provider output was not a decodable image: {exc}") from exc
    array = np.asarray(image, dtype=np.float32) / 255.0
    return torch.from_numpy(array.copy()).unsqueeze(0)


def request_fingerprint(provider: str, model_id: str, prompt: str, route: str, reference_count: int, settings: dict[str, Any]) -> str:
    safe_settings = {key: value for key, value in settings.items() if key != "api_key"}
    encoded = json.dumps(
        {"provider": provider, "model": model_id, "prompt": prompt, "route": route, "references": reference_count, "settings": safe_settings},
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _first_http_url(value: Any) -> str:
    if isinstance(value, str):
        candidate = value.strip()
        return candidate if candidate.startswith(("http://", "https://")) else ""
    if isinstance(value, list):
        for item in value:
            found = _first_http_url(item)
            if found:
                return found
    if isinstance(value, dict):
        preferred = ("url", "output_url", "outputUrl", "image_url", "imageUrl", "result_url", "resultUrl", "download_url", "downloadUrl", "resultUrls", "outputs", "urls", "images", "image", "result", "data")
        for key in preferred:
            if key in value:
                found = _first_http_url(value[key])
                if found:
                    return found
        for item in value.values():
            found = _first_http_url(item)
            if found:
                return found
    return ""


def _custom_size(profile: dict[str, Any], image_size: str, settings: dict[str, Any]) -> str:
    if not settings.get("custom_size_enabled"):
        return image_size
    if settings.get("custom_size_auto") and (profile.get("custom_size") or {}).get("supports_auto"):
        return "auto"
    separator = "x" if "x" in str(profile.get("size_format") or "").lower() else "*"
    return f"{int(settings['custom_width'])}{separator}{int(settings['custom_height'])}"


def _field_value(field_id: str, field: dict[str, Any], prompt: str, aspect: str, image_size: str, settings: dict[str, Any], provider: str) -> Any:
    if field_id == "prompt":
        return prompt
    if field_id in ("aspect_ratio", "image_size"):
        return aspect
    if field_id in ("resolution", "size"):
        value = _custom_size(settings["profile"], image_size, settings)
    elif field_id == "optimize_prompt_options":
        return {"thinking": "enabled" if settings.get("thinking_mode", True) else "disabled"}
    elif field_id == "seed":
        if provider == "atlas":
            return int(settings.get("seed", -1)) if settings.get("seed_enabled") else -1
        return int(settings.get("seed", 0))
    elif field_id in ("n", "num_images"):
        return (field.get("default") or {}).get("value", 1)
    else:
        default = (field.get("default") or {}).get("value")
        value = settings.get(field_id, default)
    transform = (field.get("mapping") or {}).get("transform")
    if transform == "to_lowercase" and isinstance(value, str):
        return value.lower()
    return value


def _build_payload(provider: str, profile: dict[str, Any], prompt: str, aspect: str, image_size: str, reference_urls: list[str], settings: dict[str, Any]) -> dict[str, Any]:
    has_refs = bool(reference_urls)
    route = "i2i" if has_refs else "t2i"
    route_data = profile.get("routes", {}).get(route) or profile.get("routes", {}).get("t2i_or_i2i") or {}
    model = route_data.get("model_id") or profile.get("unified_model") or (profile.get("image_model") if has_refs else profile.get("text_model"))
    if not model:
        raise ValueError(f"{profile['label']} does not support {'I2I' if has_refs else 'T2I'}.")
    data: dict[str, Any] = {}
    local_settings = {**settings, "profile": profile}
    for field_id, field in profile.get("fields", {}).items():
        rules = set(field.get("send_rules") or [])
        if field_id == "model" or "never" in rules:
            continue
        if "t2i_only" in rules and has_refs:
            continue
        if "i2i_only" in rules and not has_refs:
            continue
        if field_id == profile.get("input_image_field"):
            if has_refs:
                data[field_id] = reference_urls[0] if profile.get("single_image") else reference_urls
            continue
        if field_id == "seed" and provider == "kie" and not settings.get("seed_enabled"):
            continue
        should_send = bool((field.get("default") or {}).get("send", False)) or field_id in settings
        if not should_send:
            continue
        data[field_id] = _field_value(field_id, field, prompt, aspect, image_size, local_settings, provider)
    if provider == "kie":
        return {"model": model, "input": data}
    return {"model": model, **data}


def build_kie_payload(profile: dict[str, Any], prompt: str, aspect: str, image_size: str, reference_urls: list[str], settings: dict[str, Any]) -> dict[str, Any]:
    return _build_payload("kie", profile, prompt, aspect, image_size, reference_urls, settings)


def build_atlas_payload(profile: dict[str, Any], prompt: str, aspect: str, image_size: str, reference_urls: list[str], settings: dict[str, Any]) -> dict[str, Any]:
    return _build_payload("atlas", profile, prompt, aspect, image_size, reference_urls, settings)


class PendingStore:
    _lock = threading.RLock()

    def __init__(self, path: Path | None = None):
        if path is None:
            try:
                import folder_paths
                root = Path(folder_paths.get_user_directory())
            except Exception:
                root = Path.cwd() / ".test_user"
            path = root / "workflowx_configurator" / "remote_image_pending.json"
        self.path = Path(path)

    @staticmethod
    def key(provider: str, node_id: object) -> str:
        return f"{provider}:{str(node_id)}"

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            parsed = json.loads(self.path.read_text(encoding="utf-8"))
            return parsed if isinstance(parsed, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def _save(self, records: dict[str, dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f".tmp-{uuid.uuid4().hex}")
        temporary.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temporary, self.path)

    def get(self, provider: str, node_id: object) -> dict[str, Any] | None:
        with self._lock:
            item = self._load().get(self.key(provider, node_id))
            return dict(item) if isinstance(item, dict) else None

    def put(self, provider: str, node_id: object, record: dict[str, Any]) -> None:
        with self._lock:
            records = self._load()
            records[self.key(provider, node_id)] = dict(record)
            self._save(records)

    def delete(self, provider: str, node_id: object) -> bool:
        with self._lock:
            records = self._load()
            removed = records.pop(self.key(provider, node_id), None) is not None
            if removed:
                self._save(records)
            return removed


class ProviderClient:
    provider = ""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _headers(self, content_type: str | None = "application/json") -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json, text/plain, */*", "User-Agent": USER_AGENT}
        if self.provider == "kie":
            headers["x-api-key"] = self.api_key
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def _json_request(self, method: str, url: str, payload: dict[str, Any] | None = None, timeout: int = 60) -> tuple[int, dict[str, Any], str]:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(url, data=data, method=method, headers=self._headers())
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = int(getattr(response, "status", 200))
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        except Exception as exc:
            raise RuntimeError(f"{self.provider.title()} request failed: {redact(exc, self.api_key)}") from exc
        try:
            body = json.loads(raw) if raw else {}
            if not isinstance(body, dict):
                body = {}
        except json.JSONDecodeError:
            body = {}
        return status, body, raw

    def _multipart_request(self, url: str, file_bytes: bytes, filename: str = "reference.png", fields: dict[str, str] | None = None) -> tuple[int, dict[str, Any], str]:
        boundary = f"----WorkflowX{uuid.uuid4().hex}"
        chunks: list[bytes] = []
        for key, value in (fields or {}).items():
            chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode())
        chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\nContent-Type: image/png\r\n\r\n".encode())
        chunks.extend((file_bytes, f"\r\n--{boundary}--\r\n".encode()))
        request = urllib.request.Request(url, data=b"".join(chunks), method="POST", headers=self._headers(f"multipart/form-data; boundary={boundary}"))
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                status = int(getattr(response, "status", 200))
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        except Exception as exc:
            raise RuntimeError(f"{self.provider.title()} upload failed: {redact(exc, self.api_key)}") from exc
        try:
            body = json.loads(raw) if raw else {}
            if not isinstance(body, dict): body = {}
        except json.JSONDecodeError:
            body = {}
        return status, body, raw

    def download(self, url: str) -> bytes:
        request = urllib.request.Request(url, method="GET", headers=self._headers(None))
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    return response.read()
            except Exception as exc:
                last_error = exc
                if attempt == 0:
                    time.sleep(0.5)
        raise RuntimeError(f"{self.provider.title()} image download failed after retrying the same result URL: {redact(last_error, self.api_key)}")

    def upload(self, png_bytes: bytes, index: int) -> str:
        raise NotImplementedError

    def create(self, payload: dict[str, Any]) -> str:
        raise NotImplementedError

    def status(self, task_id: str) -> dict[str, str]:
        raise NotImplementedError


class KieClient(ProviderClient):
    provider = "kie"

    def upload(self, png_bytes: bytes, index: int) -> str:
        payload = {"base64Data": "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii"), "uploadPath": "images/user-uploads", "fileName": f"workflowx-reference-{index}.png"}
        status, body, raw = self._json_request("POST", KIE_UPLOAD_BASE64_URL, payload, timeout=90)
        code = int(body.get("code", status) or status)
        success = bool(body.get("success", code == 200))
        if code != 200 or not success:
            if code == 403 and "1010" in f"{body} {raw}":
                status, body, raw = self._multipart_request(KIE_UPLOAD_STREAM_URL, png_bytes, f"workflowx-reference-{index}.png", {"uploadPath": "images/user-uploads", "fileName": f"workflowx-reference-{index}.png"})
                code = int(body.get("code", status) or status)
                success = bool(body.get("success", code == 200))
            if code != 200 or not success:
                raise RuntimeError(f"Kie upload failed ({code}): {redact(body.get('msg') or raw[:300], self.api_key)}")
        url = _first_http_url(body.get("data", body))
        if not url:
            raise RuntimeError("Kie upload returned no download URL.")
        return url

    def create(self, payload: dict[str, Any]) -> str:
        status, body, raw = self._json_request("POST", KIE_CREATE_URL, payload)
        code = int(body.get("code", status) or status)
        if code != 200:
            raise RuntimeError(f"Kie createTask failed ({code}): {redact(body.get('msg') or raw[:300], self.api_key)}")
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        task_id = str(data.get("taskId") or "").strip()
        if not task_id:
            raise RuntimeError("Kie createTask returned no taskId.")
        return task_id

    def status(self, task_id: str) -> dict[str, str]:
        url = f"{KIE_STATUS_URL}?taskId={urllib.parse.quote(task_id, safe='')}"
        status, body, raw = self._json_request("GET", url, timeout=45)
        code = int(body.get("code", status) or status)
        if code != 200:
            raise RuntimeError(f"Kie status query failed ({code}): {redact(body.get('msg') or raw[:300], self.api_key)}")
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        state = str(data.get("state", "pending") or "pending").lower()
        if state in ("success", "completed"):
            parsed: Any = data
            result_json = data.get("resultJson")
            if isinstance(result_json, str) and result_json.strip():
                try: parsed = {**data, "parsedResult": json.loads(result_json)}
                except json.JSONDecodeError: pass
            return {"state": "completed", "url": _first_http_url(parsed), "error": ""}
        if state in ("fail", "failed", "error"):
            return {"state": "failed", "url": "", "error": f"{data.get('failCode', '')} {data.get('failMsg') or body.get('msg') or 'Generation failed'}".strip()}
        return {"state": "pending", "url": "", "error": ""}


class AtlasClient(ProviderClient):
    provider = "atlas"

    def upload(self, png_bytes: bytes, index: int) -> str:
        status, body, raw = self._multipart_request(ATLAS_UPLOAD_URL, png_bytes, f"workflowx-reference-{index}.png")
        code = int(body.get("code", status) or status)
        if code >= 400:
            raise RuntimeError(f"Atlas upload failed ({code}): {redact(body.get('msg') or body.get('message') or raw[:300], self.api_key)}")
        url = _first_http_url(body.get("data", body))
        if not url:
            raise RuntimeError("Atlas upload returned no file URL.")
        return url

    def create(self, payload: dict[str, Any]) -> str:
        status, body, raw = self._json_request("POST", ATLAS_CREATE_URL, payload)
        code = int(body.get("code", status) or status)
        if code >= 400:
            raise RuntimeError(f"Atlas task create failed ({code}): {redact(body.get('msg') or body.get('message') or raw[:300], self.api_key)}")
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        for source in (data, body):
            for key in ("id", "request_id", "requestId", "prediction_id", "predictionId", "taskId"):
                task_id = str(source.get(key) or "").strip()
                if task_id:
                    return task_id
        raise RuntimeError("Atlas task create returned no task ID.")

    def status(self, task_id: str) -> dict[str, str]:
        url = f"{ATLAS_STATUS_URL}/{urllib.parse.quote(task_id, safe='')}"
        status, body, raw = self._json_request("GET", url, timeout=45)
        data = body.get("data") if isinstance(body.get("data"), dict) else body
        state = str(data.get("status") or "").lower()
        if not state:
            if status >= 400:
                raise RuntimeError(f"Atlas prediction status unavailable ({status}): {redact(body.get('msg') or raw[:300], self.api_key)}")
            return {"state": "pending", "url": "", "error": ""}
        if state in ("completed", "succeeded", "success"):
            return {"state": "completed", "url": _first_http_url(data), "error": ""}
        if state in ("failed", "fail", "error"):
            return {"state": "failed", "url": "", "error": str(data.get("error") or body.get("msg") or "Generation failed")}
        return {"state": "pending", "url": "", "error": ""}

    def download(self, url: str) -> bytes:
        try:
            return super().download(url)
        except Exception as authenticated_error:
            request = urllib.request.Request(url, method="GET", headers={"Accept": "*/*", "User-Agent": USER_AGENT})
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    return response.read()
            except Exception as public_error:
                raise RuntimeError(
                    "Atlas image download failed using authenticated and public requests: "
                    f"{redact(authenticated_error, self.api_key)} | {redact(public_error, self.api_key)}"
                ) from public_error


def check_interrupted() -> None:
    try:
        import comfy.model_management as model_management
        model_management.throw_exception_if_processing_interrupted()
    except ImportError:
        return


def wait_for_result(
    client: ProviderClient,
    task_id: str,
    timeout_seconds: int,
    poll_interval_seconds: int,
    *,
    provider: str | None = None,
    node_id: object | None = None,
    status_callback=None,
) -> str:
    started = time.monotonic()
    attempt = 0
    provider = provider or client.provider
    while True:
        check_interrupted()
        if node_id is not None:
            CancellationRegistry.check(provider, node_id)
        elapsed = time.monotonic() - started
        if elapsed > timeout_seconds:
            raise TimeoutError(f"{client.provider.title()} task {task_id} timed out after {timeout_seconds}s. Use Force Retrieve to continue the same paid task.")
        event = CancellationRegistry.event(provider, node_id) if node_id is not None else None
        if event:
            event.wait(min(poll_interval_seconds, max(0.0, timeout_seconds - elapsed)))
            CancellationRegistry.check(provider, node_id)
        else:
            time.sleep(poll_interval_seconds)
        attempt += 1
        if status_callback:
            status_callback("polling", f"Checking task status (attempt {attempt})", poll_attempt=attempt, elapsed_seconds=round(time.monotonic() - started, 1))
        try:
            outcome = client.status(task_id)
        except Exception as exc:
            if status_callback:
                status_callback("polling", f"Transient status error; will retry: {redact(exc, client.api_key)}", level="warning", poll_attempt=attempt, elapsed_seconds=round(time.monotonic() - started, 1))
            continue
        if status_callback:
            status_callback("polling", f"Provider status: {outcome['state']}", poll_attempt=attempt, elapsed_seconds=round(time.monotonic() - started, 1))
        if outcome["state"] == "completed":
            if not outcome.get("url"):
                raise ProviderTerminalError(f"{client.provider.title()} task completed without an image URL.")
            return outcome["url"]
        if outcome["state"] == "failed":
            raise ProviderTerminalError(f"{client.provider.title()} generation failed: {outcome.get('error', '')}".strip())
