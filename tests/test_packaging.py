import importlib.util
import pathlib
import shutil
import sys
import types


ROOT = pathlib.Path(__file__).resolve().parents[1]


class _Routes:
    def get(self, _path):
        def decorator(func):
            return func

        return decorator

    def post(self, _path):
        def decorator(func):
            return func

        return decorator


class _Router:
    def routes(self):
        return []

    def add_get(self, *_args, **_kwargs):
        return None

    def add_post(self, *_args, **_kwargs):
        return None


def _install_comfy_stubs():
    aiohttp = types.ModuleType("aiohttp")
    web = types.ModuleType("aiohttp.web")

    def json_response(data, status=200):
        return {"data": data, "status": status}

    web.json_response = json_response
    aiohttp.web = web
    sys.modules.setdefault("aiohttp", aiohttp)
    sys.modules.setdefault("aiohttp.web", web)

    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_user_directory = lambda: str(ROOT / ".test_user")
    folder_paths.models_dir = str(ROOT / ".test_models")
    sys.modules.setdefault("folder_paths", folder_paths)

    server = types.ModuleType("server")
    server.PromptServer = types.SimpleNamespace(
        instance=types.SimpleNamespace(routes=_Routes(), app=types.SimpleNamespace(router=_Router()))
    )
    sys.modules.setdefault("server", server)


def _load_package():
    _install_comfy_stubs()
    package_name = "workflowx_configurator_test_package"
    if package_name in sys.modules:
        return sys.modules[package_name]
    spec = importlib.util.spec_from_file_location(
        package_name,
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    spec.loader.exec_module(module)
    return module


def test_combined_package_exports_workflowx_and_afj_nodes():
    module = _load_package()
    assert len(module.NODE_CLASS_MAPPINGS) == 23
    assert "KVGC_GroupConfigurator" in module.NODE_CLASS_MAPPINGS
    assert "KVGC_ConfigSelectorAdvanced" in module.NODE_CLASS_MAPPINGS
    assert "FluxVisualJsonBuilder" in module.NODE_CLASS_MAPPINGS
    assert "FluxTemplateRandomizer" in module.NODE_CLASS_MAPPINGS
    assert "AFJPromptTemplateImporter" in module.NODE_CLASS_MAPPINGS
    assert module.WEB_DIRECTORY == "./web/js"


def test_xflows_hidden_auto_tags_survive_metadata_merge():
    module = _load_package()
    xflows = sys.modules[f"{module.__name__}.xflows_manager"]
    merged = xflows._merge_entry_with_record(
        {"path": "example.json", "auto_tags": ["controlnet", "lora", "Flux"]},
        {
            "manual_tags": ["custom", "Flux"],
            "hidden_auto_tags": ["controlnet", "missing"],
            "favorite": True,
            "run_count": 4,
        },
    )

    assert merged["manual_tags"] == ["custom", "Flux"]
    assert merged["hidden_auto_tags"] == ["controlnet"]
    assert "controlnet" not in merged["all_tags"]
    assert "lora" in merged["all_tags"]
    assert "Flux" in merged["all_tags"]
    assert merged["favorite"] is True
    assert merged["run_count"] == 4


def test_xflows_library_storage_helpers_roundtrip():
    module = _load_package()
    xflows = sys.modules[f"{module.__name__}.xflows_manager"]
    shutil.rmtree(ROOT / ".test_user", ignore_errors=True)
    try:
        prompt = xflows._upsert_prompt({
            "title": "Portrait prompt",
            "text": "cinematic portrait",
            "tags": ["portrait", "quality"],
        })
        assert prompt["id"].startswith("prompt_")
        assert prompt["title"] == "Portrait prompt"
        assert prompt["tags"] == ["portrait", "quality"]
        assert xflows._touch_prompt(prompt["id"])["use_count"] == 1

        category = xflows._upsert_preset_category({"name": "lighting"})
        snippet = xflows._upsert_preset_snippet(category["id"], {"text": "soft rim light"})
        assert snippet["id"].startswith("snippet_")
        assert xflows._touch_preset_snippet(category["id"], snippet["id"])["use_count"] == 1

        snip = xflows._upsert_node_snip({
            "title": "Sampler chain",
            "type": "group",
            "tags": ["sampler"],
            "payload": {
                "type": "group",
                "nodes": [{"id": 1, "type": "KSampler", "widgets_values": [20]}],
                "links": [],
            },
        })
        assert snip["id"].startswith("snip_")
        assert snip["type"] == "group"
        assert xflows._touch_node_snip(snip["id"])["use_count"] == 1

        assert xflows._delete_prompt(prompt["id"]) is True
        assert xflows._delete_preset_snippet(category["id"], snippet["id"]) is True
        assert xflows._delete_preset_category(category["id"]) is True
        assert xflows._delete_node_snip(snip["id"]) is True
    finally:
        shutil.rmtree(ROOT / ".test_user", ignore_errors=True)


if __name__ == "__main__":
    tests = [
        (name, value)
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for name, test in tests:
        test()
        print(f"PASS {name}")
