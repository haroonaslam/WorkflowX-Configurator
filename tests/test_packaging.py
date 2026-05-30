import importlib.util
import pathlib
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


def test_combined_package_exports_workflowx_and_afj_nodes():
    _install_comfy_stubs()
    package_name = "workflowx_configurator_test_package"
    spec = importlib.util.spec_from_file_location(
        package_name,
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    spec.loader.exec_module(module)

    assert len(module.NODE_CLASS_MAPPINGS) == 23
    assert "KVGC_GroupConfigurator" in module.NODE_CLASS_MAPPINGS
    assert "KVGC_ConfigSelectorAdvanced" in module.NODE_CLASS_MAPPINGS
    assert "FluxVisualJsonBuilder" in module.NODE_CLASS_MAPPINGS
    assert "FluxTemplateRandomizer" in module.NODE_CLASS_MAPPINGS
    assert "AFJPromptTemplateImporter" in module.NODE_CLASS_MAPPINGS
    assert module.WEB_DIRECTORY == "./web/js"


if __name__ == "__main__":
    test_combined_package_exports_workflowx_and_afj_nodes()
    print("PASS test_combined_package_exports_workflowx_and_afj_nodes")
