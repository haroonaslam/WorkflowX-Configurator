# WorkflowX documentation

Start with the self-contained [WorkflowX README](../README.md). It contains the package overview, every active node contract, screenshots, controls, and linked working examples in workflow order.

## Advanced guides

| Area | Guide |
|---|---|
| Configuration and canvas | [Config SelectorX](CONFIG_SELECTOR_X.md), [Quick MuteX and Quick BypassX](../README.md#quick-mutex-and-quick-bypassx), [Quick ToggleX and ToggleX Controller](../README.md#quick-togglex-and-togglex-controller) |
| Image and video | [Image loaders](IMAGE_LOADERS.md), [Load VideoX Adv](LOAD_VIDEO_X_ADV.md), [Preview Video X](../README.md#preview-video-x), [Save Video X](SAVE_VIDEO_X.md), [View Image (Format)](VIEW_IMAGE_FORMAT.md), [Image ProcessorX](IMAGE_PROCESSOR_X.md), [Image Compare Edit X](IMAGE_COMPARE_EDIT_X_EDITOR.md), [DetailerX](detailer_x.md), [H3 RefMod](../h3_refmod/README.md) |
| Audio | [Load AudioX](LOAD_AUDIO_X.md), [Voice ChangerX](VOICE_CHANGER_X.md), [AuK](../auk/README.md), [AuK Chained Clone](../auk/docs/CHAINED_CLONE.md) |
| Models and assets | [WorkflowX Downloader](../README.md#workflowx-downloader), [Load Diffusion Model X](LOAD_DIFFUSION_MODEL_X.md), [LoraX](LORAX.md), [Load Lora PickerX](LOAD_LORA_PICKER_X.md) |
| Swap and APIs | [Anything Swap bridge](ANYTHING_SWAP_BRIDGE.md), [NanoBanana API](NANOBANANA_FULL_API.md), [Kie and Atlas APIs](KIE_ATLAS_API_NODES.md) |
| Prompting | [Prompt AssemblerX](../README.md#prompt-assemblerx), [Unified Autoprompter X](UNIFIED_AUTOPROMPTER_X.md), [JsonX user guide](afj-awesome-flex-json/USER_GUIDE.md) |
| Libraries | [XFlows](XFLOWS.md), [XPrompts](XPROMPTS.md), [Image Prompt Library](image-prompt-library.md), [XNodes](XNODES.md) |
| Compatibility | [Legacy migration](LEGACY_MIGRATION.md) |

## Feature requirements

| Feature | Setup |
|---|---|
| Video and audio media | FFmpeg is used for media conversion, repair, or encoding where described in the node guide. The [WorkflowX Downloader](../README.md#workflowx-downloader) can provision WorkflowX's FFmpeg bundle on Windows. [Load AudioX](LOAD_AUDIO_X.md) · [Save Video X](SAVE_VIDEO_X.md) |
| Voice ChangerX | Install the declared PyWORLD, NumPy, and SciPy dependencies into ComfyUI's Python environment. [Installation](VOICE_CHANGER_X.md#installation) |
| DetailerX | Install the Python dependencies and provision the models and runtime assets for the stages you enable. DLSS5 has platform-specific requirements. [Assets and runtime](detailer_x.md#local-assets) |
| AuK and H3 RefMod | AuK uses optional Python dependencies and separate model files. H3 RefMod needs ComfyUI with native MiniMax H3 support and the appropriate H3 VAEs. [AuK setup](../auk/README.md) · [H3 RefMod setup](../h3_refmod/README.md) |
| Prompt AssemblerX and ToggleX Controller | Prompt AssemblerX requires ComfyUI Autogrow. ToggleX Controller requires Autogrow and MatchType. [Prompt AssemblerX](../README.md#prompt-assemblerx) · [ToggleX Controller](../README.md#quick-togglex-and-togglex-controller) |
| Image Prompt Library | The standalone app uses Python and Pillow. The XPrompts entry works with a local ComfyUI browser session. [Launch and storage](image-prompt-library.md) |

## Project artifacts

- [Example workflow index](../examples/README.md)
- [Screenshot manifest](images/README.md)
- [Node-reference compatibility pointer](NODE_REFERENCE.md)
