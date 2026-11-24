"""CPU integration checks against the installed ComfyUI execution engine.

Run with the ComfyUI Python: python tests/run_controls_executor.py
All images live in a disposable directory; no server/profile is touched.
"""
import asyncio
import importlib
import json
from pathlib import Path
import sys
import tempfile
import types
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[1]))
sys.argv = [sys.argv[0], "--cpu"]
import comfy.options
comfy.options.enable_args_parsing()
import execution
import folder_paths
import nodes
import torch
from PIL import Image

# Import our isolated modules without starting every custom-node package.
package = types.ModuleType("workflowx_control_fixture")
package.__path__ = [str(ROOT)]
sys.modules[package.__name__] = package
loaders = types.ModuleType(package.__name__ + ".load_image_x")
loaders.__path__ = [str(ROOT / "load_image_x")]
sys.modules[loaders.__name__] = loaders
controls = importlib.import_module(package.__name__ + ".workflowx_run_controls")
runtime = importlib.import_module(loaders.__name__ + ".runtime")
advanced = importlib.import_module(loaders.__name__ + ".advanced")
nodes.NODE_CLASS_MAPPINGS.update(controls.NODE_CLASS_MAPPINGS)
nodes.NODE_CLASS_MAPPINGS.update(runtime.NODE_CLASS_MAPPINGS)
nodes.NODE_CLASS_MAPPINGS.update(advanced.NODE_CLASS_MAPPINGS)
controls.install_execution_hooks()

TRACE = []


class Source:
    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "produce"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"value": ("INT", {"default": 42})}}

    def produce(self, value):
        TRACE.append("source")
        return torch.full((2, 9, 13, 3), value / 255), torch.full((2, 9, 13), 0.25)


class Trace:
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "record"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",), "label": ("STRING",)}}

    def record(self, image, label):
        TRACE.append(label)
        return (image,)


class Output(Trace):
    OUTPUT_NODE = True


class AsyncOutput:
    RETURN_TYPES = ()
    FUNCTION = "wait"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    async def wait(self):
        TRACE.append("async_started")
        try:
            await asyncio.sleep(2)
            TRACE.append("async_finished")
            return ()
        finally:
            TRACE.append("async_closed")


nodes.NODE_CLASS_MAPPINGS.update(FixtureSource=Source, FixtureTrace=Trace, FixtureOutput=Output, FixtureAsync=AsyncOutput)


class Server:
    client_id = "fixture"
    last_node_id = None

    def __init__(self):
        self.events = []

    def send_sync(self, event, data, *args):
        self.events.append((event, data))


def prompt(config=None, same=False, kind="LoadImage"):
    p = {"src": {"class_type": "FixtureSource", "inputs": {"value": 42}},
         "stop": {"class_type": "FixtureTrace", "inputs": {"image": ["src", 0], "label": "stop"}},
         "out": {"class_type": "FixtureOutput", "inputs": {"image": ["stop", 0], "label": "after"}}}
    if same:
        original = {"class_type": kind, "inputs": {"image": "original.png"}}
        if kind == "WorkflowX_LoadImageXAdv":
            original["inputs"]["workflowx_state"] = json.dumps({"load_mode": "from_node", "mode": "off"})
        p["target"] = {"class_type": controls.ADV_BRIDGE if kind.endswith("Adv") else controls.BRIDGE,
                       "inputs": {"transfer": "pair", "settings": json.dumps(original), "nonce": uuid.uuid4().hex}}
        p["targetout"] = {"class_type": "FixtureOutput", "inputs": {"image": ["target", 0], "label": "target_after"}}
    if config is not None:
        p["control"] = {"class_type": controls.CONTROL, "inputs": {"config": json.dumps(config)}}
    return p


def config(stop=True, same=False):
    return {"workflow": "disposable-fixture", "nonce": uuid.uuid4().hex,
            "stops": ["stop"] if stop else [], "transfers": [{
                "id": "pair", "source": "src", "source_type": "LoadImage", "target": "target",
                "target_type": "LoadImage", "same_run": same}]}


async def checks(directory):
    background_errors = []
    asyncio.get_running_loop().set_exception_handler(lambda _loop, context: background_errors.append(context))
    server = Server()
    executor = execution.PromptExecutor(server, cache_type=execution.CacheType.CLASSIC,
                                       cache_args={"ram": 1, "ram_inactive": 1, "lru": 0})

    async def run(p, expected_success=True):
        TRACE.clear(); server.events.clear()
        outputs = [id for id, n in p.items() if getattr(nodes.NODE_CLASS_MAPPINGS[n["class_type"]], "OUTPUT_NODE", False)]
        valid = await execution.validate_prompt("validate", p, outputs)
        assert valid[0], valid
        await executor.execute_async(p, uuid.uuid4().hex, {"client_id": "fixture"}, outputs)
        assert executor.success is expected_success, executor.status_messages
        return executor.history_result["outputs"]

    # Both absent destination modes use exactly this prompt: no destination API
    # entry is required. The loader's original file stays byte-for-byte intact.
    for muted_mode in (2, 4):
        history = await run(prompt(config()))
        assert "after" not in TRACE, TRACE
        assert any(name == "workflowx_stopped" for name, _ in server.events)
        transfer = history["control"]["workflowx_transfers"][0]
        image = Image.open(directory / "temp" / transfer["image"]["subfolder"] / "image.png")
        assert image.size == (13, 9) and image.mode == "RGBA"
        assert image.getpixel((0, 0)) == (42, 42, 42, 191)
    print("PASS muted/bypassed destination, cached source, copy before stop, dimensions and alpha")

    # No controls: no scheduler changes leak into another queued workflow.
    await run(prompt())
    assert "after" in TRACE
    # Stop on a cached ancestor still prevents a cached output being staged.
    await run(prompt(config()))
    assert "after" not in TRACE and any(name == "workflowx_stopped" for name, _ in server.events)
    print("PASS independent normal queue and cached StopX")

    for kind in ("LoadImage", "WorkflowX_LoadImageX", "WorkflowX_LoadImageXAdv"):
        await run(prompt(config(stop=False, same=True), same=True, kind=kind))
        cache = await executor.caches.outputs.get("target")
        result = cache.outputs[0][0]
        assert result.shape == (1, 9, 13, 3), (kind, result.shape)
        assert abs(float(result[0, 0, 0, 0]) - 42 / 255) < 1e-6
    print("PASS same-run transfer through native/basic/advanced loaders")

    for kind in ("LoadImage", "WorkflowX_LoadImageX", "WorkflowX_LoadImageXAdv"):
        conf = config(stop=False)
        conf["transfers"][0]["source"] = "loader_source"
        conf["transfers"][0]["source_type"] = kind
        p = prompt(conf)
        p["loader_source"] = {"class_type": kind, "inputs": {"image": "original.png"}}
        if kind.endswith("Adv"):
            p["loader_source"]["inputs"]["workflowx_state"] = json.dumps({"mode": "off"})
        history = await run(p)
        result = history["control"]["workflowx_transfers"][0]["image"]
        image = Image.open(directory / "temp" / result["subfolder"] / "image.png")
        assert image.size == (2, 2) and image.convert("RGB").getpixel((0, 0)) == (255, 0, 0)
    print("PASS native/basic/advanced loaders as disconnected sources")

    conf = config()
    conf["transfers"][0].update(source="preview", source_type="PreviewImage")
    p = prompt(conf)
    p["preview"] = {"class_type": "PreviewImage", "inputs": {"images": ["src", 0]}}
    history = await run(p)
    result = history["control"]["workflowx_transfers"][0]["image"]
    assert Image.open(directory / "temp" / result["subfolder"] / "image.png").size == (13, 9)
    assert "after" not in TRACE
    print("PASS real PreviewImage capture before StopX")

    p = prompt(config())
    p["async"] = {"class_type": "FixtureAsync", "inputs": {}}
    await run(p)
    assert "async_started" in TRACE and "async_closed" in TRACE and "async_finished" not in TRACE, TRACE
    print("PASS StopX cancels and awaits this job's pending async tasks")

    # SaveImage/PreviewImage cache UI descriptors use the first produced file.
    Image.new("RGBA", (7, 5), (10, 20, 30, 80)).save(directory / "temp" / "saved.png")
    cache = types.SimpleNamespace(ui={"output": {"images": [{"filename": "saved.png", "subfolder": "", "type": "temp"}]}}, outputs=[])
    saved = controls.copy_first_image(cache, "PreviewImage")
    assert Image.open(directory / "temp" / saved["subfolder"] / "image.png").getpixel((0, 0)) == (10, 20, 30, 80)
    print("PASS save/preview image source")

    broken = config(stop=False)
    broken["transfers"][0]["source"] = "stop"
    # Use a node that produced no IMAGE data to verify the failure path.
    p = prompt(broken)
    p["stop"] = {"class_type": "FixtureOutput", "inputs": {"image": ["src", 0], "label": "stop"}}
    original = controls.copy_first_image
    def fail(*args):
        raise OSError("fixture copy failure")
    controls.copy_first_image = fail
    try:
        await run(p, expected_success=False)
        assert not any(name == "workflowx_image_transfer" for name, _ in server.events)
    finally:
        controls.copy_first_image = original
    print("PASS failed copies publish no loader update")
    await asyncio.sleep(0)
    assert not background_errors, background_errors


with tempfile.TemporaryDirectory(prefix="workflowx-run-controls-") as temporary:
    directory = Path(temporary)
    for name in ("input", "output", "temp"):
        (directory / name).mkdir()
    folder_paths.set_input_directory(str(directory / "input"))
    folder_paths.set_output_directory(str(directory / "output"))
    folder_paths.set_temp_directory(str(directory / "temp"))
    Image.new("RGB", (2, 2), "red").save(directory / "input" / "original.png")
    before = (directory / "input" / "original.png").read_bytes()
    asyncio.run(checks(directory))
    assert (directory / "input" / "original.png").read_bytes() == before
