import json

from comfy_api.latest import io


SEPARATORS = {
    "comma + space": ", ",
    "newline": "\n\n",
    "space": " ",
    "period + space": ". ",
}
PROMPT_SLOTS = [f"prompt_{index}" for index in range(1, 101)]


def disabled_prompt_names(raw):
    try:
        names = json.loads(raw)
    except (TypeError, ValueError):
        return set()
    return {name for name in names if isinstance(name, str)} if isinstance(names, list) else set()


class PromptAssemblerX(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        prompt = io.String.Input("prompt", optional=True, force_input=True, lazy=True)
        slots = io.Autogrow.TemplateNames(prompt, names=PROMPT_SLOTS, min=0)
        return io.Schema(
            node_id="WorkflowXPromptAssemblerX",
            display_name="Prompt AssemblerX",
            category="WorkflowX",
            description="Assemble enabled prompt fragments in input order.",
            inputs=[
                io.Combo.Input("separator", options=[*SEPARATORS, "custom"], default="comma + space"),
                io.String.Input("custom_separator", default=", ", optional=True),
                io.String.Input("disabled_slots", default="[]", optional=True, socketless=True),
                io.Autogrow.Input("prompts", slots),
            ],
            outputs=[
                io.String.Output(display_name="assembled_prompt"),
                io.String.Output(display_name="debug_info"),
            ],
        )

    @classmethod
    def check_lazy_status(cls, separator, prompts, custom_separator=", ", disabled_slots="[]"):
        if not isinstance(prompts, dict):
            return []
        disabled = disabled_prompt_names(disabled_slots)
        return [f"prompts.{name}" for name in prompts if name not in disabled]

    @classmethod
    def execute(cls, separator, prompts, custom_separator=", ", disabled_slots="[]"):
        joiner = custom_separator if separator == "custom" else SEPARATORS.get(separator, ", ")
        disabled = disabled_prompt_names(disabled_slots)
        parts, debug_lines = [], []
        for index, name in enumerate(PROMPT_SLOTS, 1):
            if name not in prompts:
                continue
            value = prompts[name] or ""
            enabled = name not in disabled
            fragment = value.strip()
            if enabled and fragment:
                parts.append(fragment)
            status = "ON" if enabled else "OFF"
            debug_lines.append(f"Slot {index}: [{status}] {value[:60]!r}")
        assembled = joiner.join(parts)
        debug = "\n".join([
            "--- Prompt AssemblerX Debug ---",
            f"Separator: {joiner!r}",
            f"Active slots: {len(parts)} / {len(debug_lines)}",
            *debug_lines,
            f"--- Output length: {len(assembled)} chars ---",
        ])
        return io.NodeOutput(assembled, debug)
