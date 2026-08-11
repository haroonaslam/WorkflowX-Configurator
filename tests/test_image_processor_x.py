import asyncio
import base64
import importlib.util
import io
import json
import pathlib
import sys
import types

import numpy as np
import pytest
import torch
from PIL import Image


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load_module():
    name = "workflowx_image_processor_x_tests"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "image_processor_x.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ipx = _load_module()


def _image(value, batch=1, height=4, width=5):
    return torch.full((batch, height, width, 3), float(value), dtype=torch.float32)


def _mask_data(alpha, width=5, height=4):
    image = Image.new("RGBA", (width, height), (255, 255, 255, alpha))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def test_node_contract_defaults_and_independent_names():
    inputs = ipx.ImageProcessorX.INPUT_TYPES()
    assert tuple(inputs["required"]) == ("image1", "operation_mode", "output_image", "processor_state")
    assert inputs["required"]["operation_mode"][1]["default"] == "Continue"
    assert inputs["required"]["output_image"][1]["default"] == "O1"
    assert inputs["optional"]["image2"][0] == "IMAGE"
    assert inputs["hidden"]["unique_id"] == "UNIQUE_ID"
    assert ipx.ImageProcessorX.RETURN_TYPES == ("IMAGE",)
    assert ipx.NODE_CLASS_MAPPINGS["WorkflowX_ImageProcessorX"] is ipx.ImageProcessorX
    assert ipx.ROUTE_ROOT.endswith("/image_processor_x")


def test_independent_routes_register_under_processor_namespace(monkeypatch):
    registered = []

    class Routes:
        def post(self, path):
            def decorate(function):
                registered.append(("POST", path, function))
                return function
            return decorate

        def get(self, path):
            def decorate(function):
                registered.append(("GET", path, function))
                return function
            return decorate

    instance = types.SimpleNamespace(routes=Routes())
    server_module = types.ModuleType("server")
    server_module.PromptServer = types.SimpleNamespace(instance=instance)
    monkeypatch.setitem(sys.modules, "server", server_module)
    ipx.register_routes()
    paths = {(method, path) for method, path, _ in registered}
    assert paths == {
        ("POST", f"{ipx.ROUTE_ROOT}/save"),
        ("POST", f"{ipx.ROUTE_ROOT}/prepare"),
        ("POST", f"{ipx.ROUTE_ROOT}/continue"),
        ("POST", f"{ipx.ROUTE_ROOT}/cancel"),
        ("GET", f"{ipx.ROUTE_ROOT}/status"),
    }


def test_pending_routes_validate_resume_cancel_status_and_tokens(monkeypatch):
    handlers = {}

    class Routes:
        def post(self, path):
            return lambda function: handlers.setdefault(("POST", path), function)

        def get(self, path):
            return lambda function: handlers.setdefault(("GET", path), function)

    instance = types.SimpleNamespace(routes=Routes())
    server_module = types.ModuleType("server")
    server_module.PromptServer = types.SimpleNamespace(instance=instance)
    monkeypatch.setitem(sys.modules, "server", server_module)
    ipx.register_routes()

    class Request:
        def __init__(self, data=None, query=None):
            self.data = data or {}
            self.query = query or {}

        async def json(self):
            return self.data

    async def run():
        loop = asyncio.get_running_loop()
        first = ipx.PendingSession("token-a", "11", loop.create_future(), [], False, None)
        second = ipx.PendingSession("token-b", "12", loop.create_future(), [], True, None)
        ipx.PENDING_SESSIONS.update({first.request_id: first, second.request_id: second})
        try:
            status_handler = handlers[("GET", f"{ipx.ROUTE_ROOT}/status")]
            status = await status_handler(Request(query={"node_id": "11"}))
            status_data = json.loads(status.text)
            assert status.status == 200
            assert [item["request_id"] for item in status_data["pending"]] == ["token-a"]

            continue_handler = handlers[("POST", f"{ipx.ROUTE_ROOT}/continue")]
            missing = await continue_handler(Request({"request_id": "stale", "node_id": "11"}))
            assert missing.status == 404
            unavailable = await continue_handler(Request({"request_id": "token-a", "node_id": "11", "output_image": "O2", "processor_state": '{}'}))
            assert unavailable.status == 400
            malformed = await continue_handler(Request({"request_id": "token-a", "node_id": "11", "output_image": "O3", "processor_state": '{'}))
            assert malformed.status == 400
            continued = await continue_handler(Request({"request_id": "token-a", "node_id": "11", "output_image": "O3", "processor_state": '{"schemaVersion":1}'}))
            assert continued.status == 200
            await asyncio.sleep(0)
            assert first.future.result()["output_image"] == "O3"

            cancel_handler = handlers[("POST", f"{ipx.ROUTE_ROOT}/cancel")]
            wrong_node = await cancel_handler(Request({"request_id": "token-b", "node_id": "11"}))
            assert wrong_node.status == 404
            cancelled = await cancel_handler(Request({"request_id": "token-b", "node_id": "12"}))
            assert cancelled.status == 200
            await asyncio.sleep(0)
            assert second.future.result() == {"cancel": True}
        finally:
            ipx.PENDING_SESSIONS.clear()

    asyncio.run(run())


def test_state_validation_normalizes_ranges_and_rejects_invalid_json():
    state = ipx.parse_processor_state(json.dumps({
        "schemaVersion": 1,
        "topOpacity": 9,
        "layerOrder": "1over2",
        "adjustmentLayers": [{
            "amount": -2,
            "adjustments": {"hue": 999, "sharpness": -50},
            "curve": {"strength": 999},
        }],
        "futureField": "ignored",
    }))
    assert state["topOpacity"] == 1
    assert state["layerOrder"] == "1over2"
    assert state["adjustmentLayers"][0]["amount"] == 0
    assert state["adjustmentLayers"][0]["adjustments"]["hue"] == 180
    assert state["adjustmentLayers"][0]["adjustments"]["sharpness"] == 0
    assert state["adjustmentLayers"][0]["curve"]["strength"] == 200
    with pytest.raises(ValueError, match="invalid JSON"):
        ipx.parse_processor_state("{")
    with pytest.raises(ValueError, match="schemaVersion"):
        ipx.parse_processor_state('{"schemaVersion":2}')


def test_single_identity_is_exact_and_adjustments_produce_a_new_image():
    source = torch.linspace(0, 1, 60, dtype=torch.float32).reshape(1, 4, 5, 3)
    assert ipx.render_o3(source, None, '{}') is source
    state = {
        "schemaVersion": 1,
        "adjustmentLayers": [{
            "visible": True,
            "mode": "global",
            "amount": 1,
            "adjustments": {"brightness": 20, "contrast": 15, "saturation": 10},
            "curve": {"channels": {"RGB": [[0, 0], [128, 150], [255, 255]]}},
        }],
    }
    result = ipx.render_o3(source, None, json.dumps(state))
    assert result.shape == source.shape
    assert not torch.equal(result, source)
    assert 0 <= float(result.min()) <= float(result.max()) <= 1


@pytest.mark.parametrize("adjustment", tuple(ipx.NEUTRAL))
def test_every_supported_adjustment_is_rendered(adjustment):
    source = torch.tensor(
        [[[[0.08, 0.28, 0.72], [0.82, 0.42, 0.14], [0.30, 0.65, 0.45]],
          [[0.91, 0.78, 0.36], [0.16, 0.50, 0.84], [0.62, 0.22, 0.56]],
          [[0.42, 0.12, 0.23], [0.69, 0.88, 0.58], [0.24, 0.38, 0.95]]]],
        dtype=torch.float32,
    )
    value = 35 if adjustment == "hue" else 55
    state = {"schemaVersion": 1, "adjustmentLayers": [{"adjustments": {adjustment: value}}]}
    result = ipx.render_o3(source, None, json.dumps(state))
    assert result.shape == source.shape
    assert not torch.allclose(result, source, atol=1 / 510), adjustment


@pytest.mark.parametrize("interpolation", ("linear", "cubic"))
def test_rgb_and_channel_curves_are_rendered(interpolation):
    source = torch.tensor([[[[0.2, 0.4, 0.6], [0.8, 0.3, 0.1]]]], dtype=torch.float32)
    state = {
        "schemaVersion": 1,
        "adjustmentLayers": [{
            "curve": {
                "interpolation": interpolation,
                "channels": {
                    "RGB": [[0, 8], [96, 122], [192, 205], [255, 248]],
                    "R": [[0, 0], [128, 155], [255, 255]],
                    "G": [[0, 0], [128, 105], [255, 255]],
                    "B": [[0, 4], [255, 242]],
                },
            },
        }],
    }
    result = ipx.render_o3(source, None, json.dumps(state))
    assert result.shape == source.shape
    assert not torch.equal(result, source)


def test_adjustment_layers_follow_editor_stack_order():
    source = _image(0.2, height=2, width=2)
    brighten = {"name": "top", "adjustments": {"brightness": 70}}
    dark_curve = {"name": "bottom", "curve": {"channels": {"RGB": [[0, 0], [255, 80]]}}}
    top_first = ipx.render_o3(source, None, json.dumps({"schemaVersion": 1, "adjustmentLayers": [brighten, dark_curve]}))
    bottom_first = ipx.render_o3(source, None, json.dumps({"schemaVersion": 1, "adjustmentLayers": [dark_curve, brighten]}))
    assert not torch.equal(top_first, bottom_first)
    manual = ipx._compose_pair(source[0], None, ipx.parse_processor_state({"schemaVersion": 1, "adjustmentLayers": [brighten, dark_curve]}))
    assert torch.equal(top_first, torch.from_numpy(manual).unsqueeze(0).float() / 255)


def test_grain_is_deterministic_and_different_dimensions_aspect_fit():
    source = torch.linspace(0.05, 0.95, 90, dtype=torch.float32).reshape(1, 5, 6, 3)
    grain = json.dumps({"schemaVersion": 1, "adjustmentLayers": [{"adjustments": {"grain": 80}}]})
    assert torch.equal(ipx.render_o3(source, None, grain), ipx.render_o3(source, None, grain))

    under = _image(0.1, height=6, width=8)
    top = _image(0.9, height=2, width=2)
    result = ipx.render_o3(under, top, json.dumps({"schemaVersion": 1, "layerOrder": "2over1", "topOpacity": 1}))
    assert result.shape == under.shape
    assert float(result[0, 0, 0].mean()) == pytest.approx(0.1, abs=1 / 255)
    assert float(result[0, 3, 3].mean()) == pytest.approx(0.9, abs=1 / 255)


def test_python_renderer_matches_cross_engine_fixture():
    fixture = json.loads((ROOT / "tests" / "fixtures" / "image_processor_x_cross_engine.json").read_text(encoding="utf-8"))
    rgba = np.asarray(fixture["rgba"], dtype=np.uint8).reshape(fixture["height"], fixture["width"], 4)
    ipx._apply_fx(rgba, ipx._merge_adjustments(fixture["adjustments"]), fixture["amount"], fixture["seed"])
    ipx._apply_curves(rgba, ipx._normalize_curve(fixture["curve"]), fixture["amount"])
    expected = np.asarray(fixture["expectedRgba"], dtype=np.int16)
    difference = np.abs(rgba.reshape(-1).astype(np.int16) - expected)
    assert int(difference.max(initial=0)) <= fixture["pixelTolerance"]


def test_brush_mask_limits_adjustment_area():
    source = _image(0.25)
    state = {
        "schemaVersion": 1,
        "adjustmentLayers": [{
            "visible": True,
            "mode": "brush",
            "amount": 1,
            "maskData": _mask_data(0),
            "adjustments": {"brightness": 100},
        }],
    }
    no_mask = ipx.render_o3(source, None, json.dumps(state))
    assert torch.allclose(no_mask, source, atol=1 / 255)
    state["adjustmentLayers"][0]["maskData"] = _mask_data(255)
    full_mask = ipx.render_o3(source, None, json.dumps(state))
    assert float(full_mask.mean()) > float(source.mean())


def test_two_image_composite_order_opacity_and_blend_mask():
    black = _image(0)
    white = _image(1)
    opaque = {"schemaVersion": 1, "layerOrder": "2over1", "topOpacity": 1}
    result = ipx.render_o3(black, white, json.dumps(opaque))
    assert float(result.mean()) == pytest.approx(1, abs=1 / 255)
    opaque["maskData"] = _mask_data(255)
    revealed = ipx.render_o3(black, white, json.dumps(opaque))
    assert float(revealed.mean()) == pytest.approx(0, abs=1 / 255)
    opaque.update({"layerOrder": "1over2", "maskData": ""})
    reversed_result = ipx.render_o3(black, white, json.dumps(opaque))
    assert float(reversed_result.mean()) == pytest.approx(0, abs=1 / 255)


def test_batch_pairing_equal_and_singleton_broadcast_and_mismatch():
    one = _image(0.2, batch=1)
    three = torch.stack((_image(0.3)[0], _image(0.5)[0], _image(0.7)[0]))
    broadcast = ipx.render_o3(one, three, '{}')
    assert broadcast.shape[0] == 3
    equal = ipx.render_o3(three, three, '{}')
    assert equal.shape[0] == 3
    with pytest.raises(ValueError, match="cannot pair"):
        ipx.render_o3(_image(0, batch=2), _image(1, batch=3), '{}')


def test_o1_o2_are_exact_pass_through_and_missing_o2_is_an_error(monkeypatch):
    monkeypatch.setattr(ipx, "_save_temp_refs", lambda images: [{"filename": f"{index}.png", "type": "temp", "subfolder": ""} for index, _ in enumerate(images)])
    first = _image(0.2, batch=2)
    second = _image(0.8, batch=3)

    async def run():
        node = ipx.ImageProcessorX()
        out1 = await node.process(first, output_image="O1")
        out2 = await node.process(first, output_image="O2", image2=second)
        assert out1["result"][0] is first
        assert out2["result"][0] is second
        with pytest.raises(ValueError, match="requires image2"):
            await node.process(first, output_image="O2")

    asyncio.run(run())


def test_pause_continue_uses_latest_state_and_cleans_registry(monkeypatch):
    monkeypatch.setattr(ipx, "_save_temp_refs", lambda images: [{"filename": "preview.png", "type": "temp", "subfolder": ""}])
    source = _image(0.2)
    latest = json.dumps({"schemaVersion": 1, "adjustmentLayers": [{"adjustments": {"brightness": 50}}]})

    async def run():
        task = asyncio.create_task(ipx.ImageProcessorX().process(source, operation_mode="Pause", output_image="O1", unique_id="7"))
        while not ipx.PENDING_SESSIONS:
            await asyncio.sleep(0)
        request_id, session = next(iter(ipx.PENDING_SESSIONS.items()))
        assert session.node_id == "7"
        session.future.set_result({"output_image": "O3", "processor_state": latest})
        result = await task
        assert request_id not in ipx.PENDING_SESSIONS
        assert result["ui"]["image_processor_x"][0]["selected_output"] == "O3"
        assert float(result["result"][0].mean()) > float(source.mean())

    asyncio.run(run())


def test_pause_emits_node_specific_event(monkeypatch):
    monkeypatch.setattr(ipx, "_save_temp_refs", lambda images: [{"filename": "fresh.png", "type": "temp", "subfolder": ""}])
    events = []
    instance = types.SimpleNamespace(client_id="client-1", send_sync=lambda *args: events.append(args))
    server_module = types.ModuleType("server")
    server_module.PromptServer = types.SimpleNamespace(instance=instance)
    monkeypatch.setitem(sys.modules, "server", server_module)

    async def run():
        task = asyncio.create_task(ipx.ImageProcessorX().process(_image(0.4), operation_mode="Pause", unique_id="42"))
        while not ipx.PENDING_SESSIONS:
            await asyncio.sleep(0)
        session = next(iter(ipx.PENDING_SESSIONS.values()))
        assert events[0][0] == ipx.EVENT_NAME
        assert events[0][1]["request_id"] == session.request_id
        assert events[0][1]["node_id"] == "42"
        assert events[0][1]["images"][0]["filename"] == "fresh.png"
        session.future.set_result({"output_image": "O1", "processor_state": '{}'})
        await task

    asyncio.run(run())


def test_pause_cancel_raises_and_cleans_registry(monkeypatch):
    monkeypatch.setattr(ipx, "_save_temp_refs", lambda images: [{"filename": "preview.png", "type": "temp", "subfolder": ""}])

    async def run():
        task = asyncio.create_task(ipx.ImageProcessorX().process(_image(0), operation_mode="Pause", unique_id="8"))
        while not ipx.PENDING_SESSIONS:
            await asyncio.sleep(0)
        session = next(iter(ipx.PENDING_SESSIONS.values()))
        session.future.set_result({"cancel": True})
        with pytest.raises(ipx.ImageProcessorXCancelled):
            await task
        assert not ipx.PENDING_SESSIONS

    asyncio.run(run())
