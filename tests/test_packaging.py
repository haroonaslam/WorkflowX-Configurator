import importlib.util
import asyncio
import base64
import json
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

    def add_delete(self, *_args, **_kwargs):
        return None


def _install_comfy_stubs():
    aiohttp = types.ModuleType("aiohttp")
    web = types.ModuleType("aiohttp.web")

    def json_response(data, status=200, **_kwargs):
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
    folder_paths.get_filename_list = lambda folder_name: []
    folder_paths.get_full_path = lambda folder_name, filename: str(ROOT / ".test_models" / folder_name / filename)
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
    assert len(module.NODE_CLASS_MAPPINGS) == 33
    assert "KVGC_GroupConfigurator" in module.NODE_CLASS_MAPPINGS
    assert "KVGC_ConfigSelectorAdvanced" in module.NODE_CLASS_MAPPINGS
    assert "KVGC_UnloadModelsByType" in module.NODE_CLASS_MAPPINGS
    assert "KVGC_LoraX" in module.NODE_CLASS_MAPPINGS
    assert "FluxVisualJsonBuilder" in module.NODE_CLASS_MAPPINGS
    assert "FluxTemplateRandomizer" in module.NODE_CLASS_MAPPINGS
    assert "AFJPromptTemplateImporter" in module.NODE_CLASS_MAPPINGS
    assert "UnifiedAutoprompterX" in module.NODE_CLASS_MAPPINGS
    assert module.NODE_DISPLAY_NAME_MAPPINGS["UnifiedAutoprompterX"] == "Unified Autoprompter X"
    assert "AnythingCropForSwap" in module.NODE_CLASS_MAPPINGS
    assert "AnythingStitch" in module.NODE_CLASS_MAPPINGS
    assert "NanoBanana_Gemini_2_5_Flash_V2" in module.NODE_CLASS_MAPPINGS
    assert module.NODE_DISPLAY_NAME_MAPPINGS["AnythingCropForSwap"] == "Anything Crop (for Swap)"
    assert module.NODE_DISPLAY_NAME_MAPPINGS["AnythingStitch"] == "Anything Stitch"
    assert module.NODE_DISPLAY_NAME_MAPPINGS["NanoBanana_Gemini_2_5_Flash_V2"] == "NanoBanana Full API"
    assert module.NODE_CLASS_MAPPINGS["AnythingCropForSwap"].CATEGORY == "WorkflowX_Configurator/Image/Anything Swap"
    assert module.NODE_CLASS_MAPPINGS["AnythingStitch"].CATEGORY == "WorkflowX_Configurator/Image/Anything Swap"
    assert module.NODE_CLASS_MAPPINGS["NanoBanana_Gemini_2_5_Flash_V2"].CATEGORY == "WorkflowX_Configurator/Image/NanoBanana"
    assert "WorkflowX_KieImageAPI" in module.NODE_CLASS_MAPPINGS
    assert "WorkflowX_AtlasImageAPI" in module.NODE_CLASS_MAPPINGS
    assert module.NODE_DISPLAY_NAME_MAPPINGS["WorkflowX_KieImageAPI"] == "Kie Image API X"
    assert module.NODE_DISPLAY_NAME_MAPPINGS["WorkflowX_AtlasImageAPI"] == "Atlas Image API X"
    assert module.NODE_CLASS_MAPPINGS["WorkflowX_KieImageAPI"].CATEGORY == "WorkflowX_Configurator/Image/API"
    assert module.NODE_CLASS_MAPPINGS["WorkflowX_AtlasImageAPI"].CATEGORY == "WorkflowX_Configurator/Image/API"
    assert "WorkflowX_LoadImageX" in module.NODE_CLASS_MAPPINGS
    assert module.NODE_DISPLAY_NAME_MAPPINGS["WorkflowX_LoadImageX"] == "Load ImageX"
    assert module.NODE_CLASS_MAPPINGS["WorkflowX_LoadImageX"].CATEGORY == "WorkflowX_Configurator/Image"
    assert module.WEB_DIRECTORY == "./web/js"


def test_lorax_route_helpers_build_canonical_entries_and_token_search():
    module = _load_package()

    class FolderPaths:
        @staticmethod
        def get_filename_list(folder_name):
            assert folder_name == "loras"
            return [
                "SDXL 1.0/concept/Pussy_Lily_v5_XL.safetensors",
                "Flux.2 Klein 9B/style/Example.safetensors",
                "ZImageTurbo/concept/pussy_floss.safetensors",
            ]

        @staticmethod
        def get_full_path(folder_name, filename):
            return f"D:/ComfyUI/models/{folder_name}/{filename}"

    entries = module._build_lorax_lora_entries(FolderPaths)
    assert entries[1]["load_name"] == "SDXL 1.0/concept/Pussy_Lily_v5_XL.safetensors"
    assert entries[1]["folder"] == "SDXL 1.0/concept"
    assert entries[1]["file_stem"] == "Pussy_Lily_v5_XL"
    assert entries[1]["full_path"].endswith("/SDXL 1.0/concept/Pussy_Lily_v5_XL.safetensors")

    first_query = module._build_lorax_lora_entries(FolderPaths, "pussy sdxl")
    second_query = module._build_lorax_lora_entries(FolderPaths, "sdxl pussy")
    assert [entry["load_name"] for entry in first_query] == [
        "SDXL 1.0/concept/Pussy_Lily_v5_XL.safetensors"
    ]
    assert first_query == second_query
    assert module._build_lorax_lora_entries(FolderPaths, "pussy flux") == []
    assert module._build_lorax_lora_entries(FolderPaths, "pussy sdxl zimage") == []


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


def test_xflows_move_preserves_metadata_and_returns_workflow():
    module = _load_package()
    xflows = sys.modules[f"{module.__name__}.xflows_manager"]
    shutil.rmtree(ROOT / ".test_user", ignore_errors=True)
    try:
        workflow_root = xflows._workflow_root()
        (workflow_root / "folder").mkdir(parents=True, exist_ok=True)
        (workflow_root / "target").mkdir(parents=True, exist_ok=True)
        (workflow_root / "folder" / "sample.json").write_text(
            '{"nodes":[{"id":1,"type":"KSampler"}],"links":[]}',
            encoding="utf-8",
        )
        xflows._save_metadata({
            "workflows": {
                "folder/sample.json": {
                    "favorite": True,
                    "manual_tags": ["keep"],
                    "run_count": 7,
                    "last_run_at": 123,
                }
            }
        })

        result = xflows._move_workflow_file("folder/sample.json", "target")
        metadata = xflows._load_metadata()["workflows"]

        assert result["ok"] is True
        assert result["old_path"] == "folder/sample.json"
        assert result["path"] == "target/sample.json"
        assert result["workflow"]["path"] == "target/sample.json"
        assert not (workflow_root / "folder" / "sample.json").exists()
        assert (workflow_root / "target" / "sample.json").exists()
        assert "folder/sample.json" not in metadata
        assert metadata["target/sample.json"]["favorite"] is True
        assert metadata["target/sample.json"]["manual_tags"] == ["keep"]
        assert metadata["target/sample.json"]["run_count"] == 7
    finally:
        shutil.rmtree(ROOT / ".test_user", ignore_errors=True)


def test_xflows_move_routes_return_paths_folders_and_batch_results():
    module = _load_package()
    xflows = sys.modules[f"{module.__name__}.xflows_manager"]

    class Request:
        def __init__(self, body):
            self._body = body

        async def json(self):
            return self._body

    shutil.rmtree(ROOT / ".test_user", ignore_errors=True)
    try:
        workflow_root = xflows._workflow_root()
        (workflow_root / "source").mkdir(parents=True, exist_ok=True)
        (workflow_root / "target").mkdir(parents=True, exist_ok=True)
        (workflow_root / "source" / "single.json").write_text(
            '{"nodes":[{"id":1,"type":"KSampler"}],"links":[]}',
            encoding="utf-8",
        )
        (workflow_root / "a.json").write_text('{"nodes":[],"links":[]}', encoding="utf-8")
        (workflow_root / "source" / "b.json").write_text('{"nodes":[],"links":[]}', encoding="utf-8")

        single = asyncio.run(xflows.move_workflow(Request({"path": "source/single.json", "folder": "target"})))
        assert single["status"] == 200
        assert single["data"]["old_path"] == "source/single.json"
        assert single["data"]["path"] == "target/single.json"
        assert "target" in single["data"]["folders"]
        assert single["data"]["workflow"]["path"] == "target/single.json"

        batch = asyncio.run(xflows.move_workflows_batch(Request({
            "paths": ["a.json", "source/b.json", "missing.json"],
            "folder": "target",
        })))
        assert batch["status"] == 200
        assert batch["data"]["ok"] is False
        assert batch["data"]["moved_count"] == 2
        assert batch["data"]["failed_count"] == 1
        assert [result["ok"] for result in batch["data"]["results"]] == [True, True, False]
        assert "target" in batch["data"]["folders"]
    finally:
        shutil.rmtree(ROOT / ".test_user", ignore_errors=True)


def test_xflows_batch_move_preserves_metadata_collisions_and_failures():
    module = _load_package()
    xflows = sys.modules[f"{module.__name__}.xflows_manager"]
    shutil.rmtree(ROOT / ".test_user", ignore_errors=True)
    try:
        workflow_root = xflows._workflow_root()
        workflow_root.mkdir(parents=True, exist_ok=True)
        (workflow_root / "folder").mkdir(parents=True, exist_ok=True)
        (workflow_root / "target").mkdir(parents=True, exist_ok=True)
        workflow_bytes = b'{"nodes":[{"id":1,"type":"KSampler"}],"links":[]}'
        (workflow_root / "a.json").write_bytes(workflow_bytes)
        (workflow_root / "folder" / "b.json").write_bytes(workflow_bytes)
        (workflow_root / "target" / "a.json").write_bytes(workflow_bytes)
        xflows._save_metadata({
            "workflows": {
                "a.json": {"run_count": 2, "manual_tags": ["root"]},
                "folder/b.json": {"run_count": 5, "favorite": True},
            }
        })

        metadata = xflows._load_metadata()
        model_index = xflows._build_model_index()
        results = []
        for raw_path in ["a.json", "folder/b.json", "missing.json"]:
            try:
                result = xflows._move_workflow_file(
                    raw_path,
                    "target",
                    metadata=metadata,
                    model_index=model_index,
                    save_metadata=False,
                )
            except ValueError as exc:
                result = {"ok": False, "path": raw_path, "error": str(exc)}
            results.append(result)
        xflows._save_metadata(metadata)

        assert [result["ok"] for result in results] == [True, True, False]
        assert results[0]["path"] == "target/a (2).json"
        assert results[1]["path"] == "target/b.json"
        assert results[2]["error"] == "workflow not found"
        saved = xflows._load_metadata()["workflows"]
        assert "a.json" not in saved
        assert "folder/b.json" not in saved
        assert saved["target/a (2).json"]["run_count"] == 2
        assert saved["target/a (2).json"]["manual_tags"] == ["root"]
        assert saved["target/b.json"]["run_count"] == 5
        assert saved["target/b.json"]["favorite"] is True
        assert (workflow_root / "target" / "a.json").exists()
        assert (workflow_root / "target" / "a (2).json").exists()
        assert (workflow_root / "target" / "b.json").exists()
    finally:
        shutil.rmtree(ROOT / ".test_user", ignore_errors=True)


def test_xflows_deeper_duplicate_groups_compare_names_nodes_and_values():
    module = _load_package()
    xflows = sys.modules[f"{module.__name__}.xflows_manager"]
    shutil.rmtree(ROOT / ".test_user", ignore_errors=True)

    def workflow(seed, prompt, node_ids, layout):
        link_id = node_ids[0] + node_ids[1]
        return {
            "nodes": [
                {
                    "id": node_ids[0],
                    "type": "KSampler",
                    "pos": [layout, layout + 1],
                    "size": [300 + layout, 200 + layout],
                    "flags": {"collapsed": bool(layout % 2)},
                    "widgets_values": [seed, prompt],
                    "inputs": [
                        {"name": "model", "type": "MODEL", "link": link_id},
                        {"name": "positive", "type": "STRING", "value": prompt},
                    ],
                    "outputs": [{"name": "LATENT", "type": "LATENT", "links": [link_id]}],
                },
                {
                    "id": node_ids[1],
                    "type": "SaveImage",
                    "pos": [layout + 2, layout + 3],
                    "widgets_values": ["out"],
                    "inputs": [{"name": "images", "type": "IMAGE", "link": link_id}],
                },
            ],
            "links": [[link_id, node_ids[0], 0, node_ids[1], 0, "LATENT"]],
        }

    try:
        workflow_root = xflows._workflow_root()
        (workflow_root / "one").mkdir(parents=True, exist_ok=True)
        (workflow_root / "two").mkdir(parents=True, exist_ok=True)
        files = {
            "one/Flow.json": workflow(1, "cat", (10, 20), 1),
            "two/flow.json": workflow(2, "dog", (101, 201), 8),
            "one/alpha.json": workflow(7, "same", (30, 40), 3),
            "two/beta.json": workflow(7, "same", (301, 401), 9),
        }
        for rel, data in files.items():
            path = workflow_root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data), encoding="utf-8")

        model_index = xflows._build_model_index()
        entries = [
            xflows._entry_from_file(workflow_root / rel, model_index)
            for rel in sorted(files)
        ]
        by_path = {entry["path"]: entry for entry in entries}

        assert len({entry["node_signature"] for entry in entries}) == 1
        assert by_path["one/alpha.json"]["value_signature"] == by_path["two/beta.json"]["value_signature"]
        assert by_path["one/Flow.json"]["value_signature"] != by_path["two/flow.json"]["value_signature"]

        name_groups = xflows._same_name_node_groups(entries)
        assert len(name_groups) == 1
        assert name_groups[0]["name_key"] == "flow"
        assert {workflow["path"] for workflow in name_groups[0]["workflows"]} == {"one/Flow.json", "two/flow.json"}

        same_value_groups = xflows._same_node_value_groups(entries)
        assert any(
            {workflow["path"] for workflow in group["workflows"]} == {"one/alpha.json", "two/beta.json"}
            for group in same_value_groups
        )

        changed_value_groups = xflows._same_node_changed_value_groups(entries)
        assert len(changed_value_groups) == 1
        assert changed_value_groups[0]["count"] == 4
        assert changed_value_groups[0]["value_variant_count"] == 3

        response = asyncio.run(xflows.duplicates(None))
        assert response["status"] == 200
        assert set(response["data"]) >= {
            "same_name_nodes",
            "same_nodes_values",
            "same_nodes_changed_values",
            "generated_at",
        }
        assert response["data"]["same_name_nodes"][0]["name_key"] == "flow"
    finally:
        shutil.rmtree(ROOT / ".test_user", ignore_errors=True)


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
