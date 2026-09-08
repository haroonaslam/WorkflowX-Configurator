import asyncio
import base64
import io
import json
import sys
import types
from pathlib import Path

import pytest
from PIL import Image

from test_unified_autoprompter import _load_routes_module, _load_package_modules


@pytest.fixture(autouse=True)
def restore_host_modules():
    saved = {name: sys.modules.get(name) for name in ("folder_paths", "server")}
    yield
    for name, module in saved.items():
        if module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module


class Request:
    def __init__(self, data):
        self.data = data

    async def json(self):
        return self.data


@pytest.mark.parametrize("status,detail,expected", [
    (403, "Content policy violation SECRET prompt", "content or safety"),
    (403, "Usage guidelines rejected the request", "content or safety"),
    (403, "Your team has used all available credits", "billing or credit"),
    (403, "Forbidden", "denied access"),
    (401, "Unauthorized", "Authentication failed"),
    (400, "Invalid temperature; contact API key owner", "request parameters"),
    (429, "Rate limit", "usage limit"),
])
def test_http_errors_preserve_safe_category(status, detail, expected):
    from importlib import import_module
    routes = _load_routes_module()
    errors = import_module(routes.__package__ + ".generation_errors")
    error = errors.ProviderHTTPError(status, detail, "grok")
    assert expected in str(error)
    assert f"HTTP {status}" in str(error)
    assert "SECRET" not in str(error)
    assert errors.friendly_error(error, "grok") == str(error)


def test_grok_successful_refusal_is_text():
    routes = _load_routes_module()
    assert routes.grok_backend._extract_text({"output": [{"type": "message", "content": [{"type": "refusal", "refusal": "I cannot generate that."}]}]}) == "I cannot generate that."


@pytest.fixture
def general_routes(monkeypatch, tmp_path):
    routes = _load_routes_module()
    handlers = {}

    class Router:
        def get(self, path):
            return lambda function: handlers.setdefault(("GET", path), function)

        def post(self, path):
            return lambda function: handlers.setdefault(("POST", path), function)

    server = types.ModuleType("server")
    server.PromptServer = types.SimpleNamespace(instance=types.SimpleNamespace(routes=Router()))
    monkeypatch.setitem(sys.modules, "server", server)
    monkeypatch.setattr(routes.general, "prompt_root", lambda: tmp_path)
    routes.register_routes()

    def call(endpoint, data=None, method="POST"):
        response = asyncio.run(handlers[(method, routes.ROUTE_PREFIX + endpoint)](Request(data)))
        return response.status, json.loads(response.text)

    return routes, call, tmp_path


def payload(**overrides):
    return {"schema_version": 7, "general_schema_version": 1, "backend": "openai", "model": "test-model", "fields": {"prompt_text": "  user\r\ntext  ", "detail": "high"}, **overrides}


@pytest.mark.parametrize("answer", ['  prose\n\n', '```json\n{"x":1}\n```', '{"positive":"p","negative":"n"}', '{"anything":[1,2]}'])
def test_general_preview_dispatch_and_output_are_exact(general_routes, monkeypatch, answer):
    routes, call, root = general_routes
    preset = "# system\r\n\r\n<exact>  \r\n"
    (root / "nested").mkdir()
    (root / "nested" / "preset.txt").write_bytes(preset.encode())
    received = []

    async def dispatch(data, system, user, images, format_, cancel):
        received.append((system, user))
        assert data["system_prompt_preset"] == "none"
        assert format_ == "natural"
        return answer

    def forbidden(*args, **kwargs):
        raise AssertionError("General invoked a profile builder or parser")

    monkeypatch.setattr(routes, "dispatch_provider", dispatch)
    for name in ("get_profile", "build_system_prompt", "build_user_prompt", "parse_generation_response", "normalize_generation_type"):
        monkeypatch.setattr(routes, name, forbidden)
    request = payload(preset="nested/preset.txt", system_prompt_preset="old.txt", nsfw_enabled=True, negative_enabled=True)
    status, preview = call("/general/preview", request)
    assert status == 200
    status, result = call("/general/generate", request)
    assert status == 200
    assert received == [(preset, "  user\r\ntext  ")]
    assert received[0] == (preview["system_prompt"], preview["user_prompt"])
    assert result["prompt"] == result["positive"] == answer
    assert result["negative"] == ""
    (root / "nested" / "preset.txt").write_bytes(b"manual edit")
    assert call("/general/preview", request)[1]["system_prompt"] == "manual edit"


def test_general_presets_validation_and_connected_text(general_routes):
    routes, call, root = general_routes
    (root / "valid.txt").write_text("system")
    (root / "not-preset.md").write_text("ignore")
    assert call("/general/presets", method="GET")[1]["presets"] == ["valid.txt"]
    for bad in ("../escape.txt", "not-preset.md", "missing.txt", "C:/secret.txt"):
        assert call("/general/preview", payload(preset=bad))[0] == 400
    assert call("/general/preview", payload(general_schema_version=0))[0] == 400
    status, preview = call("/general/preview", payload(fields={"prompt_text":"manual", "raw_prompt_text":" connected\n", "detail":"high"}))
    assert status == 200
    assert preview["system_prompt"] == ""
    assert preview["user_prompt"] == " connected\n"
    assert call("/general/preview", payload(images_b64=["bad"] * 10))[0] == 400
    assert call("/general/preview", payload(images_b64=["bad"]))[0] == 400


@pytest.mark.parametrize("backend", ["gemini", "openai", "lm_studio", "unsloth", "grok", "deepseek", "ollama", "local"])
@pytest.mark.parametrize("with_image", [False, True])
def test_general_reuses_each_provider_dispatch(general_routes, monkeypatch, backend, with_image):
    routes, call, root = general_routes
    images = []
    if with_image:
        stream = io.BytesIO()
        Image.new("RGB", (2, 2), "blue").save(stream, format="PNG")
        images = [base64.b64encode(stream.getvalue()).decode()]
    module = {"gemini": routes.gemini_backend,"openai":routes.openai_backend,"lm_studio":routes.openai_backend,"unsloth":routes.openai_backend,"grok":routes.grok_backend,"deepseek":routes.deepseek_backend,"ollama":routes.ollama_backend,"local":routes.local_llama_backend}[backend]
    calls = []

    def fake(*args, **kwargs):
        system, user = (kwargs["system_prompt"], kwargs["user_prompt"]) if backend == "local" else (args[3:5] if backend in {"openai","lm_studio","unsloth"} else args[2:4])
        assert system == ""
        assert user == "  user\r\ntext  "
        assert len(kwargs.get("pil_images") or []) == int(with_image)
        calls.append(True)
        return "raw output"

    monkeypatch.setattr(module, "generate", fake)
    monkeypatch.setattr(routes.deepseek_backend, "is_vision_model", lambda model: True)
    status, result = call("/general/generate", payload(backend=backend, images_b64=images, mmproj="vision.gguf"))
    assert status == 200, result
    assert calls == [True]


def test_general_node_output_ignores_profile_transformations():
    _, _, _, node, _ = _load_package_modules()
    text = '  ```json\n{"color_palette":["red"],"negative":"keep"}\n```  '
    assert "general" in node.UnifiedAutoprompterX.INPUT_TYPES()["required"]["target_model"][0]
    assert node.UnifiedAutoprompterX().build(target_model="general", final_prompt=text, negative_enabled=True, disable_color_palette=True) == (text, text, "")


def test_local_budget_flags_are_independent_and_validated():
    routes = _load_routes_module()
    from importlib import import_module
    private = import_module(routes.__package__ + ".jsonx_profile.backends.local_llama")
    for module in (routes.local_llama_backend, private):
        assert module.reasoning_budget_args({}) == []
        assert module.reasoning_budget_args({"reasoning":"off","reasoning_budget":512}) == []
        for value in (512, 2048, 4096, 1234):
            assert module.reasoning_budget_args({"reasoning":"on","reasoning_budget":value}) == ["--reasoning-budget",str(value)]
        for value in (0,-1,1.2,True,"bad"):
            with pytest.raises(ValueError):
                module.reasoning_budget_args({"reasoning":"on","reasoning_budget":value})


def test_general_logs_no_secrets_and_preserves_failure(general_routes, monkeypatch, caplog):
    routes, call, _ = general_routes

    async def fail(*args):
        raise RuntimeError("401 SECRET-KEY private user text base64-image")

    monkeypatch.setattr(routes, "dispatch_provider", fail)
    status, response = call("/general/generate", payload())
    assert status == 400
    assert "Authentication" in response["error"]
    assert "Previous output kept" in response["error"]
    assert "SECRET" not in caplog.text + response["error"]


def test_general_preview_rejects_nonvision_and_cancel_is_not_failure(general_routes, monkeypatch, caplog):
    routes, call, _ = general_routes
    stream = io.BytesIO()
    Image.new("RGB", (2, 2)).save(stream, format="PNG")
    images = [base64.b64encode(stream.getvalue()).decode()]
    status, result = call("/general/preview", payload(images_b64=images, model_capabilities={"vision": False}))
    assert status == 400
    assert "vision-capable" in result["error"]

    async def cancelled(data, system, user, images, format_, event):
        event.set()
        raise RuntimeError("interrupted runtime")

    monkeypatch.setattr(routes, "dispatch_provider", cancelled)
    status, result = call("/general/generate", payload(generation_id="test-cancel"))
    assert status == 409
    assert "cancelled" in result["error"]
    assert "interrupted runtime" not in caplog.text
