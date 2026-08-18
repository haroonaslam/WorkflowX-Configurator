"""Build the sanitized WorkflowX documentation workflows.

The examples intentionally contain no user media, model names, credentials, prompts,
or filesystem paths.  They are layout-controlled teaching graphs whose resource
widgets are placeholders that users replace after loading the workflow in ComfyUI.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def socket(name: str, type_name: str, *, widget: bool = False) -> dict[str, Any]:
    value: dict[str, Any] = {"name": name, "type": type_name, "link": None}
    if widget:
        value["widget"] = {"name": name}
    return value


def port(name: str, type_name: str) -> dict[str, Any]:
    return {"name": name, "type": type_name, "links": []}


class Workflow:
    def __init__(self, slug: str, title: str, requirements: str, status: str):
        self.slug = slug
        self.title = title
        self.requirements = requirements
        self.status = status
        self.nodes: list[dict[str, Any]] = []
        self.links: list[list[Any]] = []
        self.groups: list[dict[str, Any]] = []
        self._next_node = 1
        self._next_link = 1

    def node(
        self,
        type_name: str,
        x: int,
        y: int,
        *,
        size: tuple[int, int] = (260, 120),
        inputs: list[dict[str, Any]] | None = None,
        outputs: list[dict[str, Any]] | None = None,
        widgets: list[Any] | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        node = {
            "id": self._next_node,
            "type": type_name,
            "pos": [x, y],
            "size": list(size),
            "flags": {},
            "order": len(self.nodes),
            "mode": 0,
            "inputs": inputs or [],
            "outputs": outputs or [],
            "properties": {"Node name for S&R": type_name},
            "widgets_values": widgets or [],
        }
        if title:
            node["title"] = title
        self._next_node += 1
        self.nodes.append(node)
        return node

    def group(self, title: str, x: int, y: int, width: int, height: int, color: str) -> None:
        self.groups.append(
            {
                "id": len(self.groups) + 1,
                "title": title,
                "bounding": [x, y, width, height],
                "color": color,
                "font_size": 24,
                "flags": {},
            }
        )

    def connect(self, source: dict[str, Any], output_index: int, target: dict[str, Any], input_index: int) -> None:
        link_id = self._next_link
        self._next_link += 1
        output = source["outputs"][output_index]
        target["inputs"][input_index]["link"] = link_id
        output.setdefault("links", []).append(link_id)
        self.links.append(
            [link_id, source["id"], output_index, target["id"], input_index, output["type"]]
        )

    def note(self, x: int, y: int, text: str, *, size: tuple[int, int] = (320, 110)) -> dict[str, Any]:
        return self.node("Note", x, y, size=size, widgets=[text])

    def document(self) -> dict[str, Any]:
        return {
            "id": f"workflowx-{self.slug}",
            "revision": 0,
            "last_node_id": max(node["id"] for node in self.nodes),
            "last_link_id": self._next_link - 1,
            "nodes": self.nodes,
            "links": self.links,
            "groups": self.groups,
            "config": {},
            "extra": {
                "frontendVersion": "1.43.17",
                "workflowx_example": {
                    "title": self.title,
                    "requirements": self.requirements,
                    "status": self.status,
                    "privacy": "No media, credentials, personal paths, model-library names, or prompts are bundled.",
                },
            },
            "version": 0.4,
        }


def config_selector(w: Workflow, x: int, y: int, group_names: list[str]) -> dict[str, Any]:
    configs = []
    for selected in ("Draft", "Final"):
        configs.append(
            {
                "name": selected,
                "modes": {
                    name: ("Active" if selected.lower() in name.lower() else "Mute")
                    for name in group_names
                },
            }
        )
    state = {
        "version": 1,
        "initialized": True,
        "configs": configs,
        "scopes": {name: "Group Configurator" for name in group_names},
        "advanced": {"mute": {}, "bypass": {}},
    }
    return w.node(
        "KVGC_ConfigSelectorX",
        x,
        y,
        size=(330, 150),
        inputs=[socket("selected_config", "STRING", widget=True), socket("console_output", "COMBO", widget=True), socket("selectorx_state", "STRING", widget=True)],
        widgets=["Draft", "no", json.dumps(state, separators=(",", ":"))],
    )


TYPED = [
    ("Int", "INT", 20, 32),
    ("Float", "FLOAT", 3.0, 4.0),
    ("String", "STRING", "draft", "final"),
    ("Text", "STRING", "A concise neutral scene description.", "A detailed neutral scene description."),
    ("Boolean", "BOOLEAN", False, True),
    ("Sampler", "COMBO", "euler", "dpmpp_2m"),
    ("Scheduler", "COMBO", "normal", "karras"),
]


def set_node(w: Workflow, suffix: str, type_name: str, x: int, y: int, key: str, value: Any) -> dict[str, Any]:
    return w.node(
        f"KVGC_Set{suffix}",
        x,
        y,
        size=(230, 82),
        inputs=[socket("key", "STRING", widget=True), socket("value", type_name, widget=True)],
        widgets=[key, value],
    )


def get_node(w: Workflow, suffix: str, type_name: str, output_name: str, x: int, y: int, key: str) -> dict[str, Any]:
    return w.node(
        f"KVGC_Get{suffix}",
        x,
        y,
        size=(230, 92),
        inputs=[
            socket("key", "STRING", widget=True),
            socket("resolved_value", "STRING", widget=True),
            socket("resolved_config", "STRING", widget=True),
            socket("resolved_digest", "STRING", widget=True),
        ],
        outputs=[port(output_name, type_name)],
        widgets=[key, "", "", ""],
    )


def checkpoint(w: Workflow, x: int, y: int, placeholder: str) -> dict[str, Any]:
    return w.node(
        "CheckpointLoaderSimple",
        x,
        y,
        size=(300, 100),
        inputs=[socket("ckpt_name", "COMBO", widget=True)],
        outputs=[port("MODEL", "MODEL"), port("CLIP", "CLIP"), port("VAE", "VAE")],
        widgets=[placeholder],
    )


def clip_encode(w: Workflow, x: int, y: int, text: str) -> dict[str, Any]:
    return w.node(
        "CLIPTextEncode",
        x,
        y,
        size=(310, 130),
        inputs=[socket("clip", "CLIP"), socket("text", "STRING", widget=True)],
        outputs=[port("CONDITIONING", "CONDITIONING")],
        widgets=[text],
    )


def ksampler(w: Workflow, x: int, y: int) -> dict[str, Any]:
    return w.node(
        "KSampler",
        x,
        y,
        size=(290, 300),
        inputs=[
            socket("model", "MODEL"), socket("seed", "INT", widget=True), socket("steps", "INT", widget=True),
            socket("cfg", "FLOAT", widget=True), socket("sampler_name", "COMBO", widget=True), socket("scheduler", "COMBO", widget=True),
            socket("positive", "CONDITIONING"), socket("negative", "CONDITIONING"), socket("latent_image", "LATENT"), socket("denoise", "FLOAT", widget=True),
        ],
        outputs=[port("LATENT", "LATENT")],
        widgets=[0, "randomize", 20, 3.0, "euler", "normal", 1.0],
    )


def empty_latent(w: Workflow, x: int, y: int) -> dict[str, Any]:
    return w.node(
        "EmptyLatentImage", x, y, size=(240, 110),
        inputs=[socket("width", "INT", widget=True), socket("height", "INT", widget=True), socket("batch_size", "INT", widget=True)],
        outputs=[port("LATENT", "LATENT")], widgets=[1024, 1024, 8],
    )


def vae_decode(w: Workflow, x: int, y: int) -> dict[str, Any]:
    return w.node("VAEDecode", x, y, size=(220, 90), inputs=[socket("samples", "LATENT"), socket("vae", "VAE")], outputs=[port("IMAGE", "IMAGE")])


def preview(w: Workflow, x: int, y: int, title: str = "Preview") -> dict[str, Any]:
    return w.node("PreviewImage", x, y, size=(280, 240), inputs=[socket("images", "IMAGE")], title=title)


def load_image_x(w: Workflow, type_name: str, x: int, y: int) -> dict[str, Any]:
    if type_name == "WorkflowX_LoadImageX":
        return w.node(
            type_name, x, y, size=(300, 250),
            inputs=[socket("image", "COMBO", widget=True), socket("upload", "IMAGEUPLOAD", widget=True)],
            outputs=[port("image", "IMAGE"), port("mask", "MASK")],
            widgets=["select-an-image.png", "image"],
        )
    return w.node(
        type_name, x, y, size=(340, 330),
        inputs=[socket("image", "COMBO", widget=True), socket("workflowx_state", "STRING", widget=True)],
        outputs=[port("image", "IMAGE"), port("mask", "MASK"), port("inverted_mask", "MASK"), port("width", "INT"), port("height", "INT")],
        widgets=["select-an-image.png", "{}"],
    )


def build_configuration() -> Workflow:
    w = Workflow("configuration-and-routing", "Configuration and routing", "Choose local checkpoints before execution.", "Model-dependent; configuration state is complete and serialized.")
    draft_group, final_group = "Draft settings", "Final settings"
    config_selector(w, 40, 40, [draft_group, final_group])
    w.note(400, 40, "Set nodes publish values inside scoped groups. Get nodes resolve the active group's value; no Set-to-Get wire is expected.", size=(620, 100))
    for index, (suffix, type_name, draft, final) in enumerate(TYPED):
        key = suffix.lower()
        set_node(w, suffix, type_name, 60, 250 + index * 115, key, draft)
        set_node(w, suffix, type_name, 370, 250 + index * 115, key, final)
    relay_a_source = checkpoint(w, 60, 1080, "select-draft-checkpoint.safetensors")
    relay_b_source = checkpoint(w, 370, 1080, "select-final-checkpoint.safetensors")
    relay_a = w.node("KVGC_SetRelay", 60, 1210, size=(230, 72), inputs=[socket("value", "*"), socket("key", "STRING", widget=True)], outputs=[port("value", "*")], widgets=["model"])
    relay_b = w.node("KVGC_SetRelay", 370, 1210, size=(230, 72), inputs=[socket("value", "*"), socket("key", "STRING", widget=True)], outputs=[port("value", "*")], widgets=["model"])
    w.connect(relay_a_source, 0, relay_a, 0)
    w.connect(relay_b_source, 0, relay_b, 0)
    getters: dict[str, dict[str, Any]] = {}
    output_names = {"Int": "int", "Float": "float", "String": "string", "Text": "text", "Boolean": "boolean", "Sampler": "sampler_name", "Scheduler": "scheduler"}
    for index, (suffix, type_name, _draft, _final) in enumerate(TYPED):
        getters[suffix] = get_node(w, suffix, type_name, output_names[suffix], 840, 250 + index * 115, suffix.lower())
    relay_get = w.node("KVGC_GetRelay", 840, 1080, size=(230, 72), inputs=[socket("value", "*"), socket("key", "STRING", widget=True)], outputs=[port("value", "*")], widgets=["model"])
    positive = clip_encode(w, 1180, 250, "Resolved multiline prompt")
    negative = clip_encode(w, 1180, 430, "Resolved short text")
    sampler = ksampler(w, 1550, 360)
    latent = empty_latent(w, 1210, 650)
    decoded = vae_decode(w, 1900, 360)
    save = w.node("SaveImage", 2220, 360, size=(300, 260), inputs=[socket("images", "IMAGE"), socket("filename_prefix", "STRING", widget=True)], widgets=["WorkflowX/example"])
    w.connect(relay_a_source, 1, positive, 0)
    w.connect(relay_a_source, 1, negative, 0)
    w.connect(getters["Text"], 0, positive, 1)
    w.connect(getters["String"], 0, negative, 1)
    w.connect(relay_get, 0, sampler, 0)
    w.connect(getters["Int"], 0, sampler, 2)
    w.connect(getters["Float"], 0, sampler, 3)
    w.connect(getters["Sampler"], 0, sampler, 4)
    w.connect(getters["Scheduler"], 0, sampler, 5)
    w.connect(positive, 0, sampler, 6)
    w.connect(negative, 0, sampler, 7)
    w.connect(latent, 0, sampler, 8)
    w.connect(sampler, 0, decoded, 0)
    w.connect(relay_a_source, 2, decoded, 1)
    w.connect(decoded, 0, save, 0)
    w.group(draft_group, 20, 200, 300, 1100, "#355c7d")
    w.group(final_group, 330, 200, 300, 1100, "#6c5b7b")
    w.group("Resolved values", 790, 200, 310, 1020, "#2f6f62")
    w.group("Consumer pipeline", 1140, 200, 1420, 700, "#8a6d3b")
    return w


def build_local_generation() -> Workflow:
    w = Workflow("local-generation-and-model-management", "Local generation and model management", "Select a diffusion model, checkpoint components, LoRA, image, and installed FFmpeg codec.", "Model-dependent; locally runnable after resources are selected.")
    source = load_image_x(w, "WorkflowX_LoadImageX", 40, 250)
    model = checkpoint(w, 40, 40, "select-a-checkpoint.safetensors")
    diffusion_model = w.node(
        "KVGC_LoadDiffusionModelX", 400, 40, size=(360, 130),
        inputs=[socket("weight_dtype", "COMBO", widget=True)],
        outputs=[port("MODEL", "MODEL")],
        widgets=[
            "default",
            {"type": "header"},
            {
                "on": True,
                "load_name": "select-a-diffusion-model.safetensors",
                "unet_name": "select-a-diffusion-model.safetensors",
                "display_name": "Select a diffusion model",
                "path": None,
                "metadata": {},
            },
        ],
    )
    prompt = w.node(
        "UnifiedAutoprompterX", 400, 330, size=(360, 360),
        inputs=[socket("image", "IMAGE"), socket("bbox_json", "STRING"), socket("raw_prompt_text", "STRING"), socket("ui_state", "STRING", widget=True)],
        outputs=[port("prompt", "STRING"), port("positive", "STRING"), port("negative", "STRING")],
        widgets=["flux1_dev", "natural", True, False, False, False, False, "", "", "A neutral documentation example.", "{}"],
    )
    lorax = w.node("KVGC_LoraX", 400, 190, size=(360, 110), inputs=[socket("model", "MODEL"), socket("clip", "CLIP")], outputs=[port("MODEL", "MODEL"), port("CLIP", "CLIP"), port("trigger_words", "STRING"), port("loaded_loras", "STRING")])
    positive = clip_encode(w, 830, 130, "Generated positive prompt")
    negative = clip_encode(w, 830, 330, "Generated negative prompt")
    sampler = ksampler(w, 1210, 180)
    latent = empty_latent(w, 850, 540)
    decoded = vae_decode(w, 1560, 220)
    repeat = w.node("RepeatImageBatch", 1840, 220, size=(240, 90), inputs=[socket("image", "IMAGE"), socket("amount", "INT", widget=True)], outputs=[port("IMAGE", "IMAGE")], widgets=[16])
    unload = w.node(
        "KVGC_UnloadModelsByType", 2140, 190, size=(300, 180),
        inputs=[socket("model_type", "COMBO", widget=True), socket("device_scope", "COMBO", widget=True), socket("empty_cache", "BOOLEAN", widget=True), socket("trigger", "*"), socket("model", "MODEL"), socket("clip", "CLIP"), socket("vae", "VAE"), socket("conditioning", "CONDITIONING")],
        outputs=[port("trigger", "*"), port("model", "MODEL"), port("clip", "CLIP"), port("vae", "VAE"), port("conditioning", "CONDITIONING"), port("status", "STRING")],
        widgets=["All Loaded Models", "Current Device", True],
    )
    save = w.node(
        "WorkflowX_SaveVideoX", 2500, 140, size=(380, 360),
        inputs=[socket("images", "IMAGE"), socket("audio", "AUDIO"), socket("vae", "VAE"), socket("frame_rate", "FLOAT", widget=True), socket("filename_prefix", "STRING", widget=True), socket("format", "COMBO", widget=True), socket("crf_quality", "COMBO", widget=True), socket("pixel_format", "COMBO", widget=True), socket("color_range", "COMBO", widget=True), socket("save_metadata_preview_image", "BOOLEAN", widget=True), socket("audio_bitrate", "COMBO", widget=True), socket("audio_filters", "STRING", widget=True), socket("save_output", "BOOLEAN", widget=True)],
        outputs=[port("Filenames", "VHS_FILENAMES")],
        widgets=[24.0, "WorkflowX/example-video", "video/h264-mp4", "Standard (CRF 23)", "yuv420p (8-bit)", "Auto (format default)", True, "Source/default", "", False],
    )
    w.connect(source, 0, prompt, 0)
    w.connect(diffusion_model, 0, lorax, 0)
    w.connect(model, 1, lorax, 1)
    w.connect(lorax, 1, positive, 0)
    w.connect(lorax, 1, negative, 0)
    w.connect(prompt, 1, positive, 1)
    w.connect(prompt, 2, negative, 1)
    w.connect(lorax, 0, sampler, 0)
    w.connect(positive, 0, sampler, 6)
    w.connect(negative, 0, sampler, 7)
    w.connect(latent, 0, sampler, 8)
    w.connect(sampler, 0, decoded, 0)
    w.connect(model, 2, decoded, 1)
    w.connect(decoded, 0, repeat, 0)
    w.connect(repeat, 0, unload, 3)
    w.connect(unload, 0, save, 0)
    w.group("References and model", 10, 10, 780, 720, "#355c7d")
    w.group("Prompt and sampling", 800, 90, 720, 620, "#2f6f62")
    w.group("Decode, unload, and save", 1530, 90, 1390, 460, "#8a6d3b")
    return w


def build_image_tools() -> Workflow:
    w = Workflow("image-loading-processing-and-comparison", "Image loading, processing, and comparison", "Select two local input images.", "Locally runnable; Image Compare Edit X is the terminal interactive output.")
    basic = load_image_x(w, "WorkflowX_LoadImageX", 40, 100)
    advanced = load_image_x(w, "WorkflowX_LoadImageXAdv", 40, 500)
    mask = w.node("MaskToImage", 450, 540, size=(220, 90), inputs=[socket("mask", "MASK")], outputs=[port("IMAGE", "IMAGE")])
    inverted = w.node("MaskToImage", 450, 680, size=(220, 90), inputs=[socket("mask", "MASK")], outputs=[port("IMAGE", "IMAGE")])
    mask_preview = preview(w, 730, 500, "Mask preview")
    inverse_preview = preview(w, 730, 780, "Inverted mask preview")
    processor = w.node(
        "WorkflowX_ImageProcessorX", 450, 120, size=(360, 270),
        inputs=[socket("image1", "IMAGE"), socket("operation_mode", "COMBO", widget=True), socket("output_image", "COMBO", widget=True), socket("processor_state", "STRING", widget=True), socket("image2", "IMAGE")],
        outputs=[port("image", "IMAGE")], widgets=["Continue", "O3", '{"schemaVersion":1}'],
    )
    processed_preview = preview(w, 900, 110, "Processed output")
    compare = w.node("KVGC_ImageCompareEditX", 1260, 160, size=(420, 360), inputs=[socket("image1", "IMAGE"), socket("image2", "IMAGE")])
    w.connect(basic, 0, processor, 0)
    w.connect(advanced, 0, processor, 4)
    w.connect(advanced, 1, mask, 0)
    w.connect(advanced, 2, inverted, 0)
    w.connect(mask, 0, mask_preview, 0)
    w.connect(inverted, 0, inverse_preview, 0)
    w.connect(processor, 0, processed_preview, 0)
    w.connect(basic, 0, compare, 0)
    w.connect(processor, 0, compare, 1)
    w.group("Image inputs", 10, 50, 380, 820, "#355c7d")
    w.group("Processor and mask outputs", 410, 60, 800, 1020, "#2f6f62")
    w.group("Interactive comparison", 1220, 100, 500, 500, "#8a6d3b")
    return w


def build_anything_swap() -> Workflow:
    w = Workflow("anything-swap-with-nanobanana", "Anything Swap with NanoBanana", "Select a source image and enter a Gemini API key before running.", "API-dependent; credentials are intentionally blank.")
    source = load_image_x(w, "WorkflowX_LoadImageXAdv", 40, 160)
    crop = w.node(
        "AnythingCropForSwap", 460, 100, size=(360, 520),
        inputs=[socket("image", "IMAGE"), socket("mask", "MASK"), socket("caption", "STRING"), socket("use_sam3", "BOOLEAN", widget=True), socket("sam3_prompt", "STRING", widget=True), socket("sam3_checkpoint", "COMBO", widget=True), socket("threshold", "FLOAT", widget=True), socket("refine_iterations", "INT", widget=True), socket("keep_model_loaded", "BOOLEAN", widget=True), socket("select_mode", "COMBO", widget=True), socket("object_index", "INT", widget=True), socket("expand_factor", "FLOAT", widget=True), socket("expand_pixels", "INT", widget=True), socket("force_square", "BOOLEAN", widget=True), socket("padding", "COMBO", widget=True), socket("edge_handling", "COMBO", widget=True), socket("resize_mode", "COMBO", widget=True), socket("target_size", "INT", widget=True), socket("upscale_method", "COMBO", widget=True), socket("downscale_method", "COMBO", widget=True), socket("mask_grow", "INT", widget=True), socket("mask_blur", "INT", widget=True), socket("swap_prompt", "STRING", widget=True)],
        outputs=[port("crop", "IMAGE"), port("crop_mask", "MASK"), port("swap_prompt", "STRING"), port("source_masked", "IMAGE"), port("stitch", "SWAP_STITCH"), port("detected", "BOOLEAN")],
        widgets=[False, "subject", "select-a-sam3-checkpoint.safetensors", 0.5, 1, False, "largest", 0, 1.1, 16, False, 16, "shift", "target_size", 1024, "lanczos", "area", 4, 2, "Edit the selected region while preserving lighting and perspective."],
    )
    api = w.node(
        "NanoBanana_Gemini_2_5_Flash_V2", 900, 100, size=(390, 600),
        inputs=[socket("api_key", "STRING", widget=True), socket("model_version", "COMBO", widget=True), socket("prompt", "STRING", widget=True), socket("system_prompt", "STRING", widget=True), socket("aspect_ratio", "COMBO", widget=True), socket("seed", "INT", widget=True), socket("temperature", "FLOAT", widget=True), socket("top_p", "FLOAT", widget=True), socket("candidate_count", "INT", widget=True), socket("safety_harassment", "COMBO", widget=True), socket("safety_hate_speech", "COMBO", widget=True), socket("safety_sexual", "COMBO", widget=True), socket("safety_dangerous", "COMBO", widget=True), socket("edit_mode_enabled", "COMBO", widget=True), socket("resolution", "COMBO", widget=True), socket("timeout_seconds", "INT", widget=True), socket("show_thoughts", "BOOLEAN", widget=True), socket("thinking_level", "COMBO", widget=True), socket("mask", "MASK"), socket("image_1", "IMAGE")],
        outputs=[port("image_batch", "IMAGE"), port("text_output", "STRING")],
        widgets=["", "gemini-3.1-flash-image", "", "", "1:1", 0, 1.0, 0.95, 1, "BLOCK_DEFAULT", "BLOCK_DEFAULT", "BLOCK_DEFAULT", "BLOCK_DEFAULT", "yes", "1K", 300, False, "minimal"],
    )
    stitch = w.node(
        "AnythingStitch", 1380, 170, size=(320, 250),
        inputs=[socket("stitch", "SWAP_STITCH"), socket("swapped", "IMAGE"), socket("mask_override", "MASK"), socket("size_mismatch", "COMBO", widget=True), socket("mask_mode", "COMBO", widget=True), socket("feather", "INT", widget=True), socket("color_match", "BOOLEAN", widget=True), socket("color_match_method", "COMBO", widget=True), socket("color_match_strength", "FLOAT", widget=True)],
        outputs=[port("image", "IMAGE"), port("changed_mask", "MASK")],
        widgets=["resize", "payload_mask", 12, True, "reinhard", 0.7],
    )
    final_preview = preview(w, 1800, 100, "Stitched result")
    mask_to_image = w.node("MaskToImage", 1800, 430, size=(220, 90), inputs=[socket("mask", "MASK")], outputs=[port("IMAGE", "IMAGE")])
    mask_preview = preview(w, 2100, 400, "Changed mask")
    w.connect(source, 0, crop, 0)
    w.connect(source, 1, crop, 1)
    w.connect(crop, 2, api, 2)
    w.connect(crop, 1, api, 18)
    w.connect(crop, 0, api, 19)
    w.connect(crop, 4, stitch, 0)
    w.connect(api, 0, stitch, 1)
    w.connect(stitch, 0, final_preview, 0)
    w.connect(stitch, 1, mask_to_image, 0)
    w.connect(mask_to_image, 0, mask_preview, 0)
    w.group("Source and crop", 10, 50, 840, 650, "#355c7d")
    w.group("Remote crop edit", 870, 50, 450, 700, "#6c5b7b")
    w.group("Stitch and inspect", 1340, 80, 1100, 650, "#2f6f62")
    return w


def remote_api_node(w: Workflow, type_name: str, x: int, y: int, provider: str) -> dict[str, Any]:
    widget_names = ["api_key", "model", "prompt", "aspect_ratio", "image_size", "timeout_seconds", "poll_interval_seconds", "quality", "nsfw_checker", "thinking_mode", "watermark", "seed_enabled", "seed", "enable_sequential", "output_format", "enable_pro", "input_fidelity", "enable_web_search", "enable_image_search", "media_resolution", "guidance_scale", "num_inference_steps", "enable_safety_checker", "custom_size_enabled", "custom_size_auto", "custom_width", "custom_height", "reference_max_edge", "show_payload", "retrieval_mode"]
    widget_types = ["STRING", "COMBO", "STRING", "COMBO", "COMBO", "INT", "INT", "COMBO", "BOOLEAN", "BOOLEAN", "BOOLEAN", "BOOLEAN", "INT", "BOOLEAN", "COMBO", "BOOLEAN", "COMBO", "BOOLEAN", "BOOLEAN", "COMBO", "FLOAT", "INT", "BOOLEAN", "BOOLEAN", "BOOLEAN", "INT", "INT", "INT", "BOOLEAN", "COMBO"]
    values = ["", "nano-banana-2", f"A neutral {provider} documentation example.", "1:1", "1K", 600, 5, "basic", True, False, False, False, 0, False, "png", False, "low", False, False, "default", 3.5, 28, True, False, True, 1024, 1024, 2048, False, "generate"]
    inputs = [socket(name, kind, widget=True) for name, kind in zip(widget_names, widget_types)] + [socket("image_1", "IMAGE")]
    return w.node(type_name, x, y, size=(430, 620), inputs=inputs, outputs=[port("image", "IMAGE")], widgets=values)


def build_remote_apis() -> Workflow:
    w = Workflow("kie-and-atlas-apis", "Kie and Atlas APIs", "Select an optional reference image and enter provider credentials before running.", "API-dependent; credentials are intentionally blank.")
    source = load_image_x(w, "WorkflowX_LoadImageX", 40, 250)
    kie = remote_api_node(w, "WorkflowX_KieImageAPI", 450, 80, "Kie")
    atlas = remote_api_node(w, "WorkflowX_AtlasImageAPI", 450, 780, "Atlas")
    kie_preview = preview(w, 980, 210, "Kie result")
    atlas_preview = preview(w, 980, 910, "Atlas result")
    w.connect(source, 0, kie, 30)
    w.connect(source, 0, atlas, 30)
    w.connect(kie, 0, kie_preview, 0)
    w.connect(atlas, 0, atlas_preview, 0)
    w.group("Optional reference", 10, 190, 360, 380, "#355c7d")
    w.group("Kie provider branch", 410, 40, 900, 650, "#6c5b7b")
    w.group("Atlas provider branch", 410, 740, 900, 650, "#2f6f62")
    return w


def build_jsonx() -> Workflow:
    w = Workflow("jsonx-prompt-toolchain", "JsonX prompt toolchain", "Configure an LLM profile only if you want to regenerate the first lane.", "Builder/importer/randomizer are local; LLM generation is profile-dependent.")
    llm = w.node(
        "LLMToJsonX", 40, 120, size=(380, 320),
        inputs=[socket("user_instructions", "STRING", widget=True), socket("generation_mode", "COMBO", widget=True), socket("preset_context_mode", "COMBO", widget=True), socket("generated_prompt_json", "STRING", widget=True), socket("image", "IMAGE"), socket("ui_state", "STRING", widget=True), socket("enable_framing_and_placement", "BOOLEAN", widget=True), socket("output_format", "COMBO", widget=True), socket("generation_profile", "COMBO", widget=True), socket("template_use_presets", "BOOLEAN", widget=True), socket("detail_level", "COMBO", widget=True)],
        outputs=[port("prompt", "STRING")], widgets=["Create a neutral structured scene.", "fast", "optimized", '{"scene":"neutral documentation example"}', "{}", True, "json", "adaptive", True, "deep"],
    )
    builder = w.node("FluxVisualJsonBuilder", 500, 150, size=(330, 180), inputs=[socket("prompt_json", "STRING")], outputs=[port("prompt_json", "STRING")])
    importer = w.node("AFJPromptTemplateImporter", 920, 120, size=(360, 260), inputs=[socket("template_name", "STRING", widget=True), socket("source_prompt_json", "STRING"), socket("import_report", "STRING", widget=True)], outputs=[port("template_payload_json", "STRING")], widgets=["documentation-template", ""])
    randomizer = w.node("FluxTemplateRandomizer", 40, 650, size=(380, 260), inputs=[socket("template_name", "STRING", widget=True), socket("randomize_rules", "STRING", widget=True), socket("randomize_rules_help", "STRING", widget=True), socket("seed", "INT", widget=True)], outputs=[port("prompt_json", "STRING"), port("run_log", "STRING")], widgets=["documentation-template", "style: choose", "Select fields reproducibly with the seed.", 42])
    randomized_builder = w.node("FluxVisualJsonBuilder", 520, 690, size=(330, 180), inputs=[socket("prompt_json", "STRING")], outputs=[port("prompt_json", "STRING")], title="Inspect randomized JsonX")
    w.connect(llm, 0, builder, 0)
    w.connect(builder, 0, importer, 1)
    w.connect(randomizer, 0, randomized_builder, 0)
    w.group("Generate, inspect, and import", 10, 60, 1320, 440, "#355c7d")
    w.group("Seeded template randomization", 10, 590, 900, 400, "#2f6f62")
    return w


def build_production() -> Workflow:
    w = Workflow("advanced-configured-production", "Advanced configured production workflow", "Select two checkpoints, one or more LoRAs, and local output settings.", "Model-dependent sanitized production pattern derived from read-only workflow structure.")
    draft_group, final_group = "Draft model route", "Final model route"
    config_selector(w, 40, 40, [draft_group, final_group])
    draft_model = checkpoint(w, 40, 280, "select-draft-checkpoint.safetensors")
    final_model = checkpoint(w, 40, 620, "select-final-checkpoint.safetensors")
    draft_set = w.node("KVGC_SetRelay", 390, 290, size=(240, 72), inputs=[socket("value", "*"), socket("key", "STRING", widget=True)], outputs=[port("value", "*")], widgets=["production_model"])
    final_set = w.node("KVGC_SetRelay", 390, 630, size=(240, 72), inputs=[socket("value", "*"), socket("key", "STRING", widget=True)], outputs=[port("value", "*")], widgets=["production_model"])
    routed = w.node("KVGC_GetRelay", 760, 410, size=(250, 72), inputs=[socket("value", "*"), socket("key", "STRING", widget=True)], outputs=[port("value", "*")], widgets=["production_model"])
    lorax = w.node("KVGC_LoraX", 1100, 380, size=(360, 120), inputs=[socket("model", "MODEL"), socket("clip", "CLIP")], outputs=[port("MODEL", "MODEL"), port("CLIP", "CLIP"), port("trigger_words", "STRING"), port("loaded_loras", "STRING")])
    positive = clip_encode(w, 1100, 560, "Production prompt placeholder")
    negative = clip_encode(w, 1100, 760, "Production negative placeholder")
    sampler = ksampler(w, 1540, 470)
    latent = empty_latent(w, 1540, 830)
    decode = vae_decode(w, 1920, 520)
    repeat = w.node("RepeatImageBatch", 2200, 520, size=(230, 90), inputs=[socket("image", "IMAGE"), socket("amount", "INT", widget=True)], outputs=[port("IMAGE", "IMAGE")], widgets=[16])
    unload = w.node("KVGC_UnloadModelsByType", 2520, 470, size=(300, 180), inputs=[socket("model_type", "COMBO", widget=True), socket("device_scope", "COMBO", widget=True), socket("empty_cache", "BOOLEAN", widget=True), socket("trigger", "*"), socket("model", "MODEL"), socket("clip", "CLIP"), socket("vae", "VAE"), socket("conditioning", "CONDITIONING")], outputs=[port("trigger", "*"), port("model", "MODEL"), port("clip", "CLIP"), port("vae", "VAE"), port("conditioning", "CONDITIONING"), port("status", "STRING")], widgets=["All Loaded Models", "Current Device", True])
    save = w.node("WorkflowX_SaveVideoX", 2900, 410, size=(380, 360), inputs=[socket("images", "IMAGE"), socket("audio", "AUDIO"), socket("vae", "VAE"), socket("frame_rate", "FLOAT", widget=True), socket("filename_prefix", "STRING", widget=True), socket("format", "COMBO", widget=True), socket("crf_quality", "COMBO", widget=True), socket("pixel_format", "COMBO", widget=True), socket("color_range", "COMBO", widget=True), socket("save_metadata_preview_image", "BOOLEAN", widget=True), socket("audio_bitrate", "COMBO", widget=True), socket("audio_filters", "STRING", widget=True), socket("save_output", "BOOLEAN", widget=True)], outputs=[port("Filenames", "VHS_FILENAMES")], widgets=[24.0, "WorkflowX/production-example", "video/h264-mp4", "High (CRF 18)", "yuv420p (8-bit)", "Auto (format default)", True, "Source/default", "", False])
    w.connect(draft_model, 0, draft_set, 0)
    w.connect(final_model, 0, final_set, 0)
    w.connect(routed, 0, lorax, 0)
    w.connect(draft_model, 1, lorax, 1)
    w.connect(lorax, 1, positive, 0)
    w.connect(lorax, 1, negative, 0)
    w.connect(lorax, 0, sampler, 0)
    w.connect(positive, 0, sampler, 6)
    w.connect(negative, 0, sampler, 7)
    w.connect(latent, 0, sampler, 8)
    w.connect(sampler, 0, decode, 0)
    w.connect(draft_model, 2, decode, 1)
    w.connect(decode, 0, repeat, 0)
    w.connect(repeat, 0, unload, 3)
    w.connect(unload, 0, save, 0)
    w.group(draft_group, 10, 220, 650, 230, "#355c7d")
    w.group(final_group, 10, 560, 650, 230, "#6c5b7b")
    w.group("Selected model and LoRAs", 720, 330, 780, 210, "#2f6f62")
    w.group("Prompt and sampling", 1060, 550, 820, 470, "#8a6d3b")
    w.group("Output and cleanup", 1880, 350, 1440, 480, "#7a4e48")
    return w


BUILDERS = [
    ("01-configuration-and-routing.json", build_configuration),
    ("02-local-generation-and-model-management.json", build_local_generation),
    ("03-image-loading-processing-and-comparison.json", build_image_tools),
    ("04-anything-swap-with-nanobanana.json", build_anything_swap),
    ("05-kie-and-atlas-apis.json", build_remote_apis),
    ("06-jsonx-prompt-toolchain.json", build_jsonx),
    ("07-advanced-configured-production.json", build_production),
]


def render() -> dict[Path, str]:
    return {
        EXAMPLES / filename: json.dumps(builder().document(), indent=2, ensure_ascii=False) + "\n"
        for filename, builder in BUILDERS
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if checked-in examples differ from generated output.")
    args = parser.parse_args()
    expected = render()
    if args.check:
        stale = [str(path.relative_to(ROOT)) for path, content in expected.items() if not path.exists() or path.read_text(encoding="utf-8") != content]
        if stale:
            print("Stale documentation examples: " + ", ".join(stale))
            return 1
        return 0
    EXAMPLES.mkdir(exist_ok=True)
    for existing in EXAMPLES.glob("*.json"):
        existing.unlink()
    for path, content in expected.items():
        path.write_text(content, encoding="utf-8")
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
