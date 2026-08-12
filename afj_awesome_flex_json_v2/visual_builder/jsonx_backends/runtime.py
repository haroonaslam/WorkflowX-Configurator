from __future__ import annotations


def refresh_comfy_vram() -> str:
    try:
        import comfy.model_management as model_management
    except Exception as exc:
        return f"refresh VRAM skipped: could not import ComfyUI model management ({exc})"

    messages: list[str] = []
    try:
        model_management.unload_all_models()
        messages.append("unloaded all models")
    except Exception as exc:
        messages.append(f"unload_all_models failed: {exc}")
    try:
        model_management.soft_empty_cache(force=True)
        messages.append("emptied cache")
    except TypeError:
        try:
            model_management.soft_empty_cache()
            messages.append("emptied cache")
        except Exception as exc:
            messages.append(f"soft_empty_cache failed: {exc}")
    except Exception as exc:
        messages.append(f"soft_empty_cache failed: {exc}")
    return "; ".join(messages)
