import importlib.util
import base64
import pathlib
import shutil
import sys
import types
import zipfile
import io


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
    folder_paths.folder_names_and_paths = {}
    folder_paths.map_legacy = lambda folder_name: folder_name
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
    assert len(module.NODE_CLASS_MAPPINGS) == 24
    assert "KVGC_GroupConfigurator" in module.NODE_CLASS_MAPPINGS
    assert "KVGC_ConfigSelectorAdvanced" in module.NODE_CLASS_MAPPINGS
    assert "FluxVisualJsonBuilder" in module.NODE_CLASS_MAPPINGS
    assert "FluxTemplateRandomizer" in module.NODE_CLASS_MAPPINGS
    assert "AFJPromptTemplateImporter" in module.NODE_CLASS_MAPPINGS
    assert "UnifiedAutoprompterX" in module.NODE_CLASS_MAPPINGS
    assert module.NODE_DISPLAY_NAME_MAPPINGS["UnifiedAutoprompterX"] == "Unified Autoprompter X"
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


def test_xflows_export_import_roundtrip_with_backup_and_safe_zip():
    module = _load_package()
    xflows = sys.modules[f"{module.__name__}.xflows_manager"]
    shutil.rmtree(ROOT / ".test_user", ignore_errors=True)
    try:
        workflow_root = xflows._workflow_root()
        workflow_root.mkdir(parents=True, exist_ok=True)
        (workflow_root / "folder").mkdir(parents=True, exist_ok=True)
        original_workflow = b'{"nodes":[{"id":1,"type":"KSampler","pos":[1,2],"size":[3,4]}],"links":[]}'
        (workflow_root / "folder" / "sample.json").write_bytes(original_workflow)
        (workflow_root / ".index.json").write_text("{}", encoding="utf-8")
        xflows._save_metadata({"workflows": {"folder/sample.json": {"run_count": 7, "manual_tags": ["keep"]}}})
        xflows._save_library("prompts", {"prompts": [{"id": "prompt_1", "title": "A", "text": "B"}]})
        xflows._save_library("presets", {"categories": [{"id": "cat_1", "name": "quality", "snippets": []}]})
        xflows._save_library("node_snips", {"snips": [{"id": "snip_1", "title": "Node", "payload": {}}]})

        files = xflows._export_files({"workflows", "metadata", "prompts", "presets", "node_snips"})
        file_names = {file["name"] for file in files}
        assert "workflowx_workflows.zip" in file_names
        assert "workflowx_manifest.json" in file_names

        workflow_zip = next(file for file in files if file["name"] == "workflowx_workflows.zip")
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(workflow_zip["content"])), "r") as archive:
            assert "folder/sample.json" in archive.namelist()
            assert ".index.json" not in archive.namelist()

        (workflow_root / "folder" / "sample.json").write_bytes(b'{"changed": true}')
        xflows._save_library("prompts", {"prompts": []})
        decoded = xflows._decode_import_files(files)
        bundle = xflows._validate_import_bundle(decoded, {"workflows", "metadata", "prompts", "presets", "node_snips"})
        result = xflows._apply_import_bundle({"workflows", "metadata", "prompts", "presets", "node_snips"}, bundle)

        assert (workflow_root / "folder" / "sample.json").read_bytes() == original_workflow
        assert xflows._load_library("prompts")["prompts"][0]["id"] == "prompt_1"
        assert pathlib.Path(result["backup_path"]).exists()
        assert (pathlib.Path(result["backup_path"]) / "workflows" / "folder" / "sample.json").exists()
    finally:
        shutil.rmtree(ROOT / ".test_user", ignore_errors=True)


def test_xflows_import_rejects_zip_path_traversal():
    module = _load_package()
    xflows = sys.modules[f"{module.__name__}.xflows_manager"]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../escape.json", "{}")

    try:
        xflows._validate_workflow_zip(buffer.getvalue())
    except ValueError as exc:
        assert "unsafe workflow path" in str(exc)
    else:
        raise AssertionError("unsafe zip path was accepted")


if __name__ == "__main__":
    tests = [
        (name, value)
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for name, test in tests:
        test()
        print(f"PASS {name}")
