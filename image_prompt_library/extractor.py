"""Read stored graphs, never import or execute their node implementations."""
import json
from dataclasses import dataclass, field

from PIL import Image


VERSION = 4
NO_METADATA = "No embedded ComfyUI prompt or workflow"
ENHANCERS = {"TextGenerate", "TextGenerateV2", "TextGenerateLTX2Prompt", "WorkflowXAuKPromptEnhance"}


def instruction_input(name):
    name = name.lower()
    return "instruction" in name or "system" in name or "template" in name


def prompt_enhancer(kind, inputs):
    name = kind.lower()
    return kind in ENHANCERS or "enhanc" in name or any(instruction_input(k) for k in inputs)


ENCODERS = {
    "MiniMaxH3ImageConditioning": ("prompt",),
    "CLIPTextEncode": ("text",),
    "CLIPTextEncodeSDXL": ("text_g", "text_l"),
    "CLIPTextEncodeSDXLRefiner": ("text",),
    "CLIPTextEncodeFlux": ("clip_l", "t5xxl"),
}
LITERALS = {"StringConstant": "string", "StringConstantMultiline": "string",
            "PrimitiveString": "value", "PrimitiveStringMultiline": "value"}
PASSTHROUGH = {"FluxGuidance": "conditioning", "ConditioningSetArea": "conditioning",
               "ConditioningSetAreaPercentage": "conditioning", "ConditioningSetMask": "conditioning",
               "ConditioningSetTimestepRange": "conditioning", "ConditioningMultiply": "conditioning"}
SAVERS = {"SaveImage", "SaveImageAdvanced", "SaveAnimatedWEBP", "SaveAnimatedPNG",
          "PreviewImage", "SaveImageWebsocket", "WorkflowX_SaveImageJpg",
          "WorkflowX_ViewImageFormat"}
# Widget layouts are explicit; unknown visual nodes are never guessed by position.
WIDGETS = {"CLIPTextEncode": ("text",), "CLIPTextEncodeFlux": ("clip_l", "t5xxl", "guidance"),
           "StringConstant": ("string",), "StringConstantMultiline": ("string",),
           "PrimitiveString": ("value",), "PrimitiveStringMultiline": ("value",),
           "JoinStrings": ("delimiter",), "JoinStringMulti": ("inputcount", "delimiter", "return_list"),
           "StringConcatenate": ("string_a", "string_b", "delimiter")}


def normalize(text):
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def link(value):
    return isinstance(value, list) and len(value) == 2 and isinstance(value[0], (str, int)) and type(value[1]) is int


def visual_graph(workflow):
    links = {str(v[0]): [str(v[1]), v[2]] for v in workflow.get("links", []) if isinstance(v, list) and len(v) >= 5}
    graph = {}
    for node in workflow.get("nodes", []):
        kind = node.get("type", "")
        inputs = {}
        widgets = node.get("widgets_values", [])
        if isinstance(widgets, dict):
            inputs.update(widgets)
        elif isinstance(widgets, list):
            inputs.update(zip(WIDGETS.get(kind, ()), widgets))
        for socket in node.get("inputs", []):
            if socket.get("link") is not None:
                inputs[socket["name"]] = links.get(str(socket["link"]), ["missing", 0])
        graph[str(node["id"])] = {"class_type": kind, "inputs": inputs, "visual_mode": node.get("mode", 0)}
    return graph


def read_metadata(path):
    with Image.open(path) as image:
        info = dict(image.info)
        exif = image.getexif()
        values = [*exif.values(), info.get("comment")]
        if 34665 in exif:
            values.append(exif.get_ifd(34665).get(37510))
        for value in values:
            if isinstance(value, bytes):
                value = value.removeprefix(b"ASCII\x00\x00\x00").decode("utf-8", errors="replace")
            if not isinstance(value, str):
                continue
            for prefix in ("prompt:", "workflow:"):
                if value.startswith(prefix):
                    info[prefix[:-1]] = value[len(prefix):].strip()
            if value.lstrip().startswith("{"):
                try:
                    data = json.loads(value)
                    if isinstance(data, dict):
                        info.update({k: v for k, v in data.items() if k in ("prompt", "workflow")})
                except ValueError:
                    pass
        result = {}
        for key in ("prompt", "workflow"):
            value = info.get(key)
            if isinstance(value, (str, bytes)):
                value = json.loads(value)
            if isinstance(value, dict):
                result[key] = value
        return result


@dataclass
class Value:
    parts: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    operations: list = field(default_factory=list)

    @property
    def text(self):
        return "\n".join(self.parts)


class Resolver:
    def __init__(self, graph):
        self.graph = graph

    def boolean(self, value, seen=()):
        if type(value) is bool:
            return value
        if not link(value) or value[1] != 0 or str(value[0]) in seen:
            return None
        node_id = str(value[0])
        node = self.graph.get(node_id, {})
        inputs = node.get('inputs', {})
        if node.get('class_type') == 'PrimitiveBoolean':
            return self.boolean(inputs.get('value'), (*seen, node_id))
        if node.get('class_type') == 'Reroute':
            return self.boolean(next(iter(inputs.values()), None), (*seen, node_id))
        return None

    def enhancer_source(self, value, stack):
        if link(value) and value[1] == 0:
            node_id = str(value[0])
            node = self.graph.get(node_id, {})
            inputs = node.get('inputs', {})
            # MiniMax's task template injects the user's text into this placeholder.
            # Only strip this wrapper inside an enhancer, never in an image prompt.
            if (node_id not in stack and node.get('class_type') == 'StringReplace'
                    and inputs.get('find') == '{input text}'):
                return self.resolve(inputs.get('replace'), (*stack, node_id))
        return self.resolve(value, stack)

    def resolve(self, value, stack=()):
        if isinstance(value, str):
            return Value([value])
        if not link(value):
            return Value(issues=["Missing or non-text input"])
        node_id, slot = str(value[0]), value[1]
        if node_id in stack or len(stack) > 150:
            return Value(issues=[f"Cycle or excessive depth at node {node_id}"])
        node = self.graph.get(node_id)
        if not isinstance(node, dict):
            return Value(issues=[f"Missing node {node_id}"])
        kind, inputs = node.get("class_type", ""), node.get("inputs", {})
        stack = (*stack, node_id)
        def get(key):
            return self.resolve(inputs.get(key), stack)
        def merge(keys):
            values = [get(k) for k in keys]
            return Value([p for v in values for p in v.parts], [e for v in values for e in v.issues],
                         [op for v in values for op in v.operations])
        if node.get("visual_mode", 0) != 0:
            return Value(issues=[f"Node {node_id} ({kind}): muted/bypassed visual node needs execution metadata"])
        if prompt_enhancer(kind, inputs) and kind not in ENCODERS:
            # Source text is review evidence, not the LLM's unavailable runtime output.
            values = [self.enhancer_source(inputs[k], stack) for k in
                      ("prompt", "text", "user_prompt", "raw_prompt_text") if k in inputs] if slot == 0 else []
            result = Value([p for v in values for p in v.parts], [e for v in values for e in v.issues],
                           [op for v in values for op in v.operations])
            result.issues.append(f"Node {node_id} ({kind}): enhanced/generated output is not stored; source text only, instruction inputs ignored")
            result.operations.append({"node": node_id, "type": kind, "output": slot,
                                      "source_text_only": True})
            return result
        if slot != 0 and kind not in ("CondPassThrough", "ControlNetApplyAdvanced"):
            result = merge([k for k in ("text", "prompt", "generated_positive", "final_prompt") if k in inputs])
            result.issues.append(f"Node {node_id} ({kind}): unsupported output {slot}")
            return result
        if kind in ENCODERS:
            result = merge(ENCODERS[kind])
            # Identical text supplied to separate encoder channels is one prompt.
            result.parts = ["\n".join(dict.fromkeys(result.parts))] if result.parts else []
        elif kind in LITERALS:
            result = get(LITERALS[kind])
        elif kind == "Reroute":
            result = get(next(iter(inputs), ""))
        elif kind == 'PreviewAny':
            result = get('source')
        elif kind in ("KVGC_SetRelay", "KVGC_GetRelay"):
            result = get("value")
        elif kind in ("LazySwitchKJ", "ComfySwitchNode"):
            selected = self.boolean(inputs.get("switch"))
            if type(selected) is not bool:
                result = merge(("on_false", "on_true"))
                result.issues.append(f"Node {node_id}: selector value is not stored as a boolean")
            else:
                result = get("on_true" if selected else "on_false")
        elif kind == "CondPassThrough":
            result = get("positive" if slot == 0 else "negative") if slot in (0, 1) else Value(issues=[f"Node {node_id}: invalid output {slot}"])
        elif kind == "ControlNetApplyAdvanced":
            result = get("positive" if slot == 0 else "negative") if slot in (0, 1) else Value(issues=[f"Node {node_id}: invalid output {slot}"])
        elif kind == "ControlNetApply":
            result = get("conditioning")
        elif kind in PASSTHROUGH:
            result = get(PASSTHROUGH[kind])
        elif kind == "ConditioningZeroOut":
            result = Value()
        elif kind == "ConditioningCombine":
            result = merge(("conditioning_1", "conditioning_2"))
        elif kind == "ConditioningConcat":
            left, right = get("conditioning_to"), get("conditioning_from")
            result = Value([p + "\n" + right.parts[0] for p in left.parts] if right.parts else left.parts,
                           left.issues + right.issues, left.operations + right.operations)
        elif kind == 'StringReplace':
            source, find, replacement = get('string'), get('find'), get('replace')
            result = Value([source.text.replace(find.text, replacement.text)],
                           source.issues + find.issues + replacement.issues,
                           source.operations + find.operations + replacement.operations)
        elif kind == 'PromptAssemblerCompact':
            values = []
            for i in range(1, 5):
                enabled = self.boolean(inputs.get(f'enable_{i}', True))
                if enabled is None:
                    return Value(issues=[f'Node {node_id}: unresolved prompt slot toggle'])
                if enabled:
                    values.append(self.resolve(inputs.get(f'prompt_{i}', ''), stack))
            separator = get('custom_separator') if inputs.get('separator') == 'custom' else Value([
                {'comma + space': ', ', 'newline': '\n\n', 'space': ' ', 'period + space': '. '}.get(inputs.get('separator'), ', ')])
            result = Value([separator.text.join(v.text.strip() for v in values if v.text.strip())],
                           separator.issues + [e for v in values for e in v.issues],
                           separator.operations + [op for v in values for op in v.operations])
        elif kind in ("JoinStrings", "JoinStringMulti", "StringConcatenate"):
            if kind in ("JoinStrings", "StringConcatenate"):
                keys = ("string1", "string2") if kind == "JoinStrings" else ("string_a", "string_b")
            else:
                count = inputs.get("inputcount")
                if type(count) is not int or not 1 <= count <= 1000 or inputs.get("return_list") is not False:
                    return Value(issues=[f"Node {node_id}: unresolved string-list mode or input count"])
                keys = [f"string_{i}" for i in range(1, count + 1)]
            values = [self.resolve(inputs.get(k, ""), stack) for k in keys]
            delimiter = self.resolve(inputs.get("delimiter", "" if kind == "StringConcatenate" else " "), stack)
            result = Value(issues=delimiter.issues + [e for v in values for e in v.issues],
                           operations=[op for v in values for op in v.operations])
            texts = [v.text for v in values]
            if kind == "JoinStringMulti":
                texts = texts[:1] + [t for t in texts[1:] if t]
            result.parts = [delimiter.text.join(texts)]
        else:
            # Fragments remain useful for review, but unknown operations are never complete.
            result = merge([k for k, v in inputs.items() if not instruction_input(k)
                            and k not in ("model", "clip", "vae", "image", "images", "audio", "video")
                            and (link(v) or k in ("text", "prompt", "string", "generated_positive", "final_prompt"))])
            result.issues.append(f"Node {node_id} ({kind}): unsupported transformation or runtime output")
        result.operations.append({"node": node_id, "type": kind, "output": slot,
                                  "inputs": {k: v for k, v in inputs.items() if not instruction_input(k)}})
        return result


def extract(metadata):
    graph = metadata.get("prompt")
    visual_only = not graph
    if not graph:
        graph = visual_graph(metadata.get("workflow", {}))
    if not graph:
        return {"positive": "", "stages": [], "issues": [NO_METADATA], "skip_reason": "no_metadata"}
    graph = {str(k): v for k, v in graph.items() if isinstance(v, dict)}
    resolver = Resolver(graph)
    outputs = [k for k, n in graph.items() if n.get("class_type") in SAVERS]
    issues, stages, visited = [], [], set()
    if not outputs:
        issues.append("No supported image output node; output attribution needs review")
        outputs = list(graph)
    if len(outputs) > 1:
        issues.append("Multiple image outputs in metadata; select/correct the prompt for this image")
    def walk(node_id, stack=()):
        if node_id in stack:
            issues.append(f"Cycle in image lineage at node {node_id}")
            return
        if node_id in visited:
            return
        visited.add(node_id)
        node = graph.get(node_id, {})
        inputs = node.get("inputs", {})
        kind = node.get("class_type", "")
        if prompt_enhancer(kind, inputs):
            return
        # Follow image/latent lineage first so stages are recorded upstream-first.
        for key, value in inputs.items():
            if link(value) and not instruction_input(key) and key not in ("positive", "negative", "conditioning", "clip", "model", "vae", "prompt", "text", "string", "user_prompt"):
                walk(str(value[0]), (*stack, node_id))
        kind = node.get("class_type")
        if kind in ("KSampler", "KSamplerAdvanced", "SamplerCustom", "CFGGuider", "BasicGuider"):
            pos = resolver.resolve(inputs.get("positive", inputs.get("conditioning")))
            neg = resolver.resolve(inputs["negative"]) if "negative" in inputs else Value()
            stages.append({"node": node_id, "type": node.get("class_type"), "positive": pos.text,
                           "negative": neg.text, "branches": pos.parts, "operations": pos.operations,
                           "negative_operations": neg.operations, "issues": pos.issues + neg.issues,
                           "settings": {k: v for k, v in inputs.items() if not link(v)}})
            issues.extend(pos.issues + neg.issues)
        elif ("positive" in inputs or "prompt" in inputs) and kind not in (*ENCODERS, "ControlNetApplyAdvanced", "CondPassThrough"):
            fragment = resolver.resolve(inputs.get("positive", inputs.get("prompt")))
            problem = f"Node {node_id} ({kind}): unsupported generation stage"
            stages.append({"node": node_id, "type": kind, "positive": fragment.text,
                           "negative": "", "branches": fragment.parts, "operations": fragment.operations,
                           "issues": [problem, *fragment.issues], "settings": {}})
            issues.extend([problem, *fragment.issues])
    for output in outputs:
        walk(output)
    if not stages:
        issues.append("No supported positive conditioning path found")
    positives = list(dict.fromkeys(normalize(s["positive"]) for s in stages if normalize(s["positive"])))
    if len(positives) > 1:
        issues.append("Multiple generation stages have different prompts; review the stage records")
    if visual_only:
        issues.append("Only visual workflow available; runtime values and branch selection need review")
    if not positives:
        issues.append("No positive text recovered")
    return {"positive": positives[0] if len(positives) == 1 else "\n\n".join(positives),
            "stages": stages, "issues": list(dict.fromkeys(issues))}
