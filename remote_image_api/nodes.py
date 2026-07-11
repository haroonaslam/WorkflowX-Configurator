"""ComfyUI node definitions for Kie and Atlas image generation."""

from __future__ import annotations

import time
from typing import Any

from .catalogs import PROFILES
from .runtime import (
    AtlasClient,
    CancellationRegistry,
    KieClient,
    LocalCancellation,
    PendingStore,
    ProviderTerminalError,
    build_atlas_payload,
    build_kie_payload,
    emit_status,
    image_bytes_to_tensor,
    placeholder_tensor,
    redact,
    request_fingerprint,
    resolve_api_key,
    resolve_profile,
    selected_size_options,
    tensor_images,
    tensor_to_png,
    validate_generation,
    wait_for_result,
)


class _FlexibleImageInputs(dict):
    """Accept browser-created image_N sockets while typing all of them as IMAGE."""

    def __init__(self) -> None:
        super().__init__({"image_1": ("IMAGE",)})

    def __getitem__(self, key: str):
        return super().get(key, ("IMAGE",))

    def __contains__(self, _key: object) -> bool:
        return True


def _union(provider: str, key: str, fallback: str) -> list[str]:
    values: list[str] = []
    for profile in PROFILES[provider]:
        source = selected_size_options(profile) if key == "sizes" else list(profile.get(key) or [])
        for value in source:
            if value not in values:
                values.append(value)
    return values or [fallback]


class RemoteImageAPINode:
    provider = ""
    client_class = KieClient
    CATEGORY = "WorkflowX_Configurator/Image/API"
    FUNCTION = "generate_image"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        profiles = PROFILES[cls.provider]
        default = profiles[0]
        return {
            "required": {
                "api_key": ("STRING", {"default": "", "password": True, "tooltip": f"Optional override; otherwise use {'KIE_API_KEY' if cls.provider == 'kie' else 'ATLAS_API_KEY or ATLASCLOUD_API_KEY'}."}),
                "model": ([p["id"] for p in profiles], {"default": default["id"]}),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "aspect_ratio": (_union(cls.provider, "aspect_ratios", "1:1"), {"default": default.get("default_aspect") or (default.get("aspect_ratios") or ["1:1"])[0]}),
                "image_size": (_union(cls.provider, "sizes", "1K"), {"default": default.get("default_size") or selected_size_options(default)[0]}),
                "timeout_seconds": ("INT", {"default": 600, "min": 30, "max": 3600, "step": 1}),
                "poll_interval_seconds": ("INT", {"default": 3, "min": 2, "max": 60, "step": 1}),
                "quality": (["basic", "low", "medium", "high"], {"default": default.get("default_quality", "medium")}),
                "nsfw_checker": ("BOOLEAN", {"default": default.get("default_nsfw", True)}),
                "thinking_mode": ("BOOLEAN", {"default": bool(default.get("default_thinking", cls.provider == "atlas"))}),
                "watermark": ("BOOLEAN", {"default": False}),
                "seed_enabled": ("BOOLEAN", {"default": False}),
                "seed": ("INT", {"default": 0, "min": -1, "max": 2147483647}),
                "enable_sequential": ("BOOLEAN", {"default": False}),
                "output_format": (["default", "png", "jpg", "jpeg"], {"default": default.get("default_output_format", "default")}),
                "enable_pro": ("BOOLEAN", {"default": False}),
                "input_fidelity": (["low", "high"], {"default": "high"}),
                "enable_web_search": ("BOOLEAN", {"default": False}),
                "enable_image_search": ("BOOLEAN", {"default": False}),
                "media_resolution": (["default", "low", "medium", "high"], {"default": "default"}),
                "guidance_scale": ("FLOAT", {"default": 3.5, "min": 0.0, "max": 20.0, "step": 0.1}),
                "num_inference_steps": ("INT", {"default": 28, "min": 1, "max": 100}),
                "enable_safety_checker": ("BOOLEAN", {"default": True}),
                "custom_size_enabled": ("BOOLEAN", {"default": False}),
                "custom_size_auto": ("BOOLEAN", {"default": False}),
                "custom_width": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 64}),
                "custom_height": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 64}),
                "reference_max_edge": ("INT", {"default": 5120, "min": 512, "max": 8192, "step": 64}),
                "show_payload": ("BOOLEAN", {"default": False}),
                "retrieval_mode": (["generate", "force_retrieve"], {"default": "generate"}),
            },
            "optional": _FlexibleImageInputs(),
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    @classmethod
    def IS_CHANGED(cls, **_kwargs):
        # A remote generation is deliberately a side effect and should run on every queue.
        return float("nan")

    @staticmethod
    def _settings(**values: Any) -> dict[str, Any]:
        return dict(values)

    @staticmethod
    def _ordered_image_values(kwargs: dict[str, Any]) -> list[Any]:
        def index(item: tuple[str, Any]) -> int:
            try:
                return int(item[0].rsplit("_", 1)[1])
            except (IndexError, ValueError):
                return 10_000
        return [value for key, value in sorted(((k, v) for k, v in kwargs.items() if k.startswith("image_")), key=index)]

    def _build_payload(self, profile: dict[str, Any], prompt: str, aspect: str, image_size: str, urls: list[str], settings: dict[str, Any]) -> dict[str, Any]:
        if self.provider == "kie":
            return build_kie_payload(profile, prompt, aspect, image_size, urls, settings)
        return build_atlas_payload(profile, prompt, aspect, image_size, urls, settings)

    def generate_image(
        self,
        api_key: str,
        model: str,
        prompt: str,
        aspect_ratio: str,
        image_size: str,
        timeout_seconds: int,
        poll_interval_seconds: int,
        quality: str,
        nsfw_checker: bool,
        thinking_mode: bool,
        watermark: bool,
        seed_enabled: bool,
        seed: int,
        enable_sequential: bool,
        output_format: str,
        enable_pro: bool,
        input_fidelity: str,
        enable_web_search: bool,
        enable_image_search: bool,
        media_resolution: str,
        guidance_scale: float,
        num_inference_steps: int,
        enable_safety_checker: bool,
        custom_size_enabled: bool = False,
        custom_size_auto: bool = False,
        custom_width: int = 1024,
        custom_height: int = 1024,
        reference_max_edge: int = 5120,
        show_payload: bool = False,
        retrieval_mode: str = "generate",
        unique_id: object = None,
        **kwargs: Any,
    ):
        key = resolve_api_key(self.provider, api_key)
        if not key:
            env_hint = "KIE_API_KEY" if self.provider == "kie" else "ATLAS_API_KEY or ATLASCLOUD_API_KEY"
            raise RuntimeError(f"{self.provider.title()} API key is required. Enter it in the node or set {env_hint}.")

        node_id = str(unique_id if unique_id is not None else "unknown")
        CancellationRegistry.begin(self.provider, node_id)
        store = PendingStore()
        pending = store.get(self.provider, node_id)
        client = self.client_class(key)
        settings = self._settings(
            quality=quality, nsfw_checker=nsfw_checker, thinking_mode=thinking_mode,
            watermark=watermark, seed_enabled=seed_enabled, seed=seed,
            enable_sequential=enable_sequential, output_format=output_format,
            enable_pro=enable_pro, input_fidelity=input_fidelity,
            enable_web_search=enable_web_search, enable_image_search=enable_image_search,
            media_resolution=media_resolution, guidance_scale=guidance_scale,
            num_inference_steps=num_inference_steps, enable_safety_checker=enable_safety_checker,
            custom_size_enabled=custom_size_enabled, custom_size_auto=custom_size_auto, custom_width=custom_width,
            custom_height=custom_height, reference_max_edge=reference_max_edge,
        )

        def status(phase: str, message: str, **extra: Any) -> None:
            emit_status(self.provider, node_id, phase, message, **extra)

        try:
            status("starting", f"Preparing {self.provider.title()} request")
            if retrieval_mode == "force_retrieve":
                if not pending:
                    raise RuntimeError("No pending task is stored for this node. Run Generate first.")
                task_id = str(pending.get("task_id") or "")
                if not task_id:
                    raise RuntimeError("The stored pending record has no task ID; use Forget Pending.")
                status("retrieving", f"Retrieving pending task {task_id}", task_id=task_id)
                image_url = str(pending.get("result_url") or "")
                if not image_url:
                    image_url = wait_for_result(
                        client, task_id, int(timeout_seconds), int(poll_interval_seconds),
                        provider=self.provider, node_id=node_id, status_callback=status,
                    )
                    pending["result_url"] = image_url
                    pending["status"] = "completed_pending_download"
                    pending["updated_at_epoch_ms"] = int(time.time() * 1000)
                    store.put(self.provider, node_id, pending)
            else:
                if pending:
                    task_id = str(pending.get("task_id") or "unknown")
                    raise RuntimeError(f"This node already has pending {self.provider.title()} task {task_id}. Use Force Retrieve or Forget Pending; a replacement paid task was not submitted.")
                profile = resolve_profile(self.provider, model)
                frames = tensor_images(self._ordered_image_values(kwargs))
                status("validating", f"Validating {profile['label']} with {len(frames)} reference image(s)")
                validate_generation(profile, str(aspect_ratio), str(image_size), len(frames), str(prompt or ""), settings)
                urls: list[str] = []
                for index, frame in enumerate(frames, start=1):
                    CancellationRegistry.check(self.provider, node_id)
                    status("uploading", f"Uploading reference {index} of {len(frames)}", upload_index=index, upload_count=len(frames))
                    urls.append(client.upload(tensor_to_png(frame, int(reference_max_edge)), index))
                    CancellationRegistry.check(self.provider, node_id)
                route = "i2i" if urls else "t2i"
                payload = self._build_payload(profile, str(prompt or ""), str(aspect_ratio), str(image_size), urls, settings)
                if show_payload:
                    visible = str(payload)
                    for url in urls:
                        visible = visible.replace(url, "[REFERENCE_URL]")
                    status("payload", visible)
                CancellationRegistry.check(self.provider, node_id)
                status("submitting", f"Submitting one {route.upper()} generation; this call is never retried")
                task_id = client.create(payload)
                pending = {
                    "provider": self.provider,
                    "node_id": node_id,
                    "task_id": task_id,
                    "model_id": model,
                    "route": route,
                    "reference_count": len(urls),
                    "request_fingerprint": request_fingerprint(self.provider, model, str(prompt or ""), route, len(urls), settings),
                    "status": "pending",
                    "created_at_epoch_ms": int(time.time() * 1000),
                    "updated_at_epoch_ms": int(time.time() * 1000),
                }
                store.put(self.provider, node_id, pending)
                status("submitted", f"Task accepted: {task_id}", task_id=task_id)
                image_url = wait_for_result(
                    client, task_id, int(timeout_seconds), int(poll_interval_seconds),
                    provider=self.provider, node_id=node_id, status_callback=status,
                )
                pending["result_url"] = image_url
                pending["status"] = "completed_pending_download"
                pending["updated_at_epoch_ms"] = int(time.time() * 1000)
                store.put(self.provider, node_id, pending)

            CancellationRegistry.check(self.provider, node_id)
            status("downloading", "Downloading provider result")
            output = image_bytes_to_tensor(client.download(image_url))
            CancellationRegistry.check(self.provider, node_id)
            store.delete(self.provider, node_id)
            status("completed", "Image generation completed")
            return {"ui": {"provider": [self.provider], "task_id": [task_id], "pending": [False]}, "result": (output,)}
        except LocalCancellation as exc:
            if exc.mode == "continue":
                store.delete(self.provider, node_id)
                profile = resolve_profile(self.provider, model)
                status("cancelled", "Stopped locally; continuing with a black placeholder. Provider-side work was not cancelled.", level="warning")
                output = placeholder_tensor(profile, str(aspect_ratio), str(image_size), settings)
                return {"ui": {"provider": [self.provider], "pending": [False], "cancelled": ["continue"]}, "result": (output,)}
            status("parked", "Stopped locally; pending task retained for Force Retrieve.", level="warning")
            raise RuntimeError("Stopped locally. Any submitted provider task remains pending; use Force Retrieve to continue it.") from exc
        except TimeoutError as exc:
            status("timeout", str(exc), level="warning")
            raise RuntimeError(redact(exc, key)) from exc
        except ProviderTerminalError:
            store.delete(self.provider, node_id)
            status("failed", "Provider reported a terminal generation failure.", level="error")
            raise
        except Exception as exc:
            status("failed", redact(exc, key), level="error")
            raise RuntimeError(redact(exc, key)) from exc
        finally:
            CancellationRegistry.finish(self.provider, node_id)


class KieImageAPINode(RemoteImageAPINode):
    provider = "kie"
    client_class = KieClient
    DESCRIPTION = "Generate or edit one image through Kie, with model-aware controls and resumable task retrieval."


class AtlasImageAPINode(RemoteImageAPINode):
    provider = "atlas"
    client_class = AtlasClient
    DESCRIPTION = "Generate or edit one image through Atlas, with model-aware controls and resumable task retrieval."
