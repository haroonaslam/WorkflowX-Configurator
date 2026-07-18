import asyncio
import importlib.util
import os
import pathlib
import sys
import types

import numpy as np
import pytest
from PIL import Image


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load_runtime_module():
    original = sys.modules.get("folder_paths")
    stub = types.ModuleType("folder_paths")
    stub.get_input_directory = lambda: str(ROOT)
    stub.get_user_directory = lambda: str(ROOT / ".test_user")
    stub.filter_files_content_types = lambda files, _types: list(files)
    sys.modules["folder_paths"] = stub
    try:
        spec = importlib.util.spec_from_file_location(
            "workflowx_load_image_x_runtime_test",
            ROOT / "load_image_x" / "runtime.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if original is None:
            sys.modules.pop("folder_paths", None)
        else:
            sys.modules["folder_paths"] = original


runtime = _load_runtime_module()


class FakeFolderPaths:
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

    def __init__(self, input_dir, user_dir=None):
        self.input_dir = pathlib.Path(input_dir)
        self.user_dir = pathlib.Path(user_dir or input_dir / "user")

    def get_input_directory(self):
        return str(self.input_dir)

    def get_user_directory(self):
        return str(self.user_dir)

    def filter_files_content_types(self, files, content_types):
        assert content_types == ["image"]
        return [path for path in files if pathlib.Path(path).suffix.lower() in self.IMAGE_EXTENSIONS]


def _save_rgb(path, size=(4, 3), color=(10, 20, 30)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)


def _install_fake_aiohttp(monkeypatch):
    class Response:
        def __init__(self, body=None, status=200, headers=None, content_type=None):
            self.body = body
            self.status = status
            self.headers = headers or {}
            self.content_type = content_type

    web = types.ModuleType("aiohttp.web")
    web.Response = Response
    web.json_response = lambda data, status=200, headers=None: Response(
        body=data, status=status, headers=headers
    )
    aiohttp = types.ModuleType("aiohttp")
    aiohttp.web = web
    monkeypatch.setitem(sys.modules, "aiohttp", aiohttp)
    monkeypatch.setitem(sys.modules, "aiohttp.web", web)
    return Response


def test_catalog_recurses_filters_sorts_and_versions(tmp_path):
    input_dir = tmp_path / "input"
    _save_rgb(input_dir / "root.png")
    _save_rgb(input_dir / "Studio 1" / "B.JPG")
    _save_rgb(input_dir / "Studio 1" / "éclair.png")
    (input_dir / "notes.txt").write_text("not an image", encoding="utf-8")
    fake = FakeFolderPaths(input_dir)

    items, etag = runtime.build_catalog(fake)

    assert [item["path"] for item in items] == [
        "root.png",
        "Studio 1/B.JPG",
        "Studio 1/éclair.png",
    ]
    assert items[0]["folder"] == ""
    assert items[1]["folder"] == "Studio 1"
    assert all(len(item["version"]) == 24 for item in items)
    assert len(etag) == 64


def test_catalog_rejects_traversal_and_symlink_escape(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    outside = tmp_path / "outside.png"
    _save_rgb(outside)
    fake = FakeFolderPaths(input_dir)

    for value in ("../outside.png", "/absolute.png", "folder/../../outside.png", "C:/outside.png", "image.png [output]"):
        with pytest.raises(ValueError):
            runtime.resolve_input_path(value, fake)

    link = input_dir / "linked.png"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Symlink creation is unavailable on this Windows configuration")
    items, _etag = runtime.build_catalog(fake)
    assert items == []
    with pytest.raises(ValueError):
        runtime.resolve_input_path("linked.png", fake)


def test_load_image_outputs_rgb_alpha_exif_and_multiframe(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    fake = FakeFolderPaths(input_dir)
    monkeypatch.setattr(runtime, "folder_paths", fake)

    rgba = np.zeros((2, 3, 4), dtype=np.uint8)
    rgba[..., :3] = (100, 150, 200)
    rgba[..., 3] = np.array([[255, 128, 0], [255, 255, 255]], dtype=np.uint8)
    Image.fromarray(rgba, "RGBA").save(input_dir / "alpha.png")
    image, mask = runtime.LoadImageX().load_image("alpha.png")
    assert tuple(image.shape) == (1, 2, 3, 3)
    assert tuple(mask.shape) == (1, 2, 3)
    assert mask[0, 0, 0].item() == pytest.approx(0.0)
    assert mask[0, 0, 2].item() == pytest.approx(1.0)

    oriented = Image.new("RGB", (2, 3), (20, 30, 40))
    exif = Image.Exif()
    exif[274] = 6
    oriented.save(input_dir / "oriented.jpg", exif=exif)
    image, mask = runtime.LoadImageX().load_image("oriented.jpg")
    assert tuple(image.shape) == (1, 2, 3, 3)
    assert tuple(mask.shape) == (1, 2, 3)
    assert float(mask.max()) == 0.0

    first = Image.new("RGB", (3, 2), (255, 0, 0))
    second = Image.new("RGB", (3, 2), (0, 255, 0))
    first.save(input_dir / "animated.gif", save_all=True, append_images=[second], duration=20, loop=0)
    image, mask = runtime.LoadImageX().load_image("animated.gif")
    assert tuple(image.shape) == (2, 2, 3, 3)
    assert tuple(mask.shape) == (2, 2, 3)


def test_thumbnail_cache_hits_and_invalidates_when_source_changes(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    user_dir = tmp_path / "user"
    source = input_dir / "nested" / "sample.png"
    _save_rgb(source, size=(400, 200))
    fake = FakeFolderPaths(input_dir, user_dir)
    monkeypatch.setattr(runtime, "folder_paths", fake)
    runtime._thumbnail_locks.clear()
    runtime._prune_started = True

    items, _etag = runtime.build_catalog(fake)
    version = items[0]["version"]
    calls = 0
    original_generate = runtime.generate_thumbnail

    def counted_generate(source_path, destination):
        nonlocal calls
        calls += 1
        return original_generate(source_path, destination)

    monkeypatch.setattr(runtime, "generate_thumbnail", counted_generate)

    _install_fake_aiohttp(monkeypatch)

    class Request:
        rel_url = types.SimpleNamespace(query={"path": "nested/sample.png", "v": version})

    async def request_twice():
        first = await runtime.thumbnail_handler(Request())
        second = await runtime.thumbnail_handler(Request())
        return first, second

    first_response, second_response = asyncio.run(request_twice())
    assert first_response.status == 200
    assert second_response.status == 200
    assert calls == 1
    assert first_response.headers["Cache-Control"].endswith("immutable")

    old_cache_path = runtime.thumbnail_cache_path("nested/sample.png", source.stat(), fake)
    _save_rgb(source, size=(401, 200), color=(40, 50, 60))
    os.utime(source, ns=(source.stat().st_atime_ns, source.stat().st_mtime_ns + 1_000_000))
    new_items, _etag = runtime.build_catalog(fake)
    new_cache_path = runtime.thumbnail_cache_path("nested/sample.png", source.stat(), fake)
    assert new_items[0]["version"] != version
    assert new_cache_path != old_cache_path


def test_batch_delete_removes_images_caches_and_invalidates_catalog(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    user_dir = tmp_path / "user"
    first = input_dir / "root.png"
    second = input_dir / "nested" / "second.jpg"
    _save_rgb(first)
    _save_rgb(second)
    fake = FakeFolderPaths(input_dir, user_dir)
    monkeypatch.setattr(runtime, "folder_paths", fake)
    runtime._thumbnail_locks.clear()
    runtime._catalog_expires_at = 123.0
    _install_fake_aiohttp(monkeypatch)

    first_cache = runtime.thumbnail_cache_path("root.png", first.stat(), fake)
    second_cache = runtime.thumbnail_cache_path("nested/second.jpg", second.stat(), fake)
    first_cache.parent.mkdir(parents=True, exist_ok=True)
    first_cache.write_bytes(b"cached")
    second_cache.write_bytes(b"cached")

    class Request:
        content_type = "application/json"

        async def json(self):
            return {"paths": ["root.png", "nested/second.jpg", "root.png"]}

    response = asyncio.run(runtime.delete_images_handler(Request()))

    assert response.status == 200
    assert response.body["deleted"] == ["root.png", "nested/second.jpg"]
    assert response.body["deleted_count"] == 2
    assert response.body["missing"] == []
    assert response.body["failed"] == []
    assert not first.exists()
    assert not second.exists()
    assert not first_cache.exists()
    assert not second_cache.exists()
    assert runtime._catalog_expires_at == 0.0
    assert response.headers["Cache-Control"] == "no-store"


def test_batch_delete_rejects_unsafe_or_non_image_batches_before_deleting(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    keep = input_dir / "keep.png"
    _save_rgb(keep)
    (input_dir / "notes.txt").write_text("keep", encoding="utf-8")
    fake = FakeFolderPaths(input_dir)
    monkeypatch.setattr(runtime, "folder_paths", fake)
    _install_fake_aiohttp(monkeypatch)

    class Request:
        content_type = "application/json"

        def __init__(self, paths):
            self.paths = paths

        async def json(self):
            return {"paths": self.paths}

    traversal = asyncio.run(runtime.delete_images_handler(Request(["keep.png", "../outside.png"])))
    unsupported = asyncio.run(runtime.delete_images_handler(Request(["keep.png", "notes.txt"])))

    class WrongContentType(Request):
        content_type = "text/plain"

    wrong_content_type = asyncio.run(runtime.delete_images_handler(WrongContentType(["keep.png"])))
    oversized = asyncio.run(
        runtime.delete_images_handler(Request(["keep.png"] * (runtime.MAX_BATCH_DELETE_FILES + 1)))
    )

    assert traversal.status == 400
    assert unsupported.status == 400
    assert wrong_content_type.status == 415
    assert oversized.status == 400
    assert keep.exists()
    assert (input_dir / "notes.txt").exists()


def test_batch_delete_rejects_linked_images(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    target = input_dir / "target.png"
    _save_rgb(target)
    link = input_dir / "linked.png"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Symlink creation is unavailable on this Windows configuration")

    fake = FakeFolderPaths(input_dir)
    monkeypatch.setattr(runtime, "folder_paths", fake)
    _install_fake_aiohttp(monkeypatch)

    class Request:
        content_type = "application/json"

        async def json(self):
            return {"paths": ["linked.png"]}

    response = asyncio.run(runtime.delete_images_handler(Request()))

    assert response.status == 400
    assert target.exists()
    assert link.exists()


def test_load_image_registration_and_validation(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    _save_rgb(input_dir / "valid.png")
    fake = FakeFolderPaths(input_dir)
    monkeypatch.setattr(runtime, "folder_paths", fake)
    monkeypatch.setattr(runtime, "get_catalog", lambda: (runtime.build_catalog(fake)[0], "etag"))

    inputs = runtime.LoadImageX.INPUT_TYPES()
    assert inputs["required"]["image"][0] == ["valid.png"]
    assert inputs["required"]["image"][1]["image_upload"] is True
    assert runtime.LoadImageX.VALIDATE_INPUTS("valid.png") is True
    assert runtime.LoadImageX.VALIDATE_INPUTS("../valid.png") != True
    assert runtime.NODE_DISPLAY_NAME_MAPPINGS["WorkflowX_LoadImageX"] == "Load ImageX"
    assert runtime.LoadImageX.CATEGORY == "WorkflowX_Configurator/Image"


def test_route_registration_includes_batch_delete():
    package_name = "workflowx_load_image_x_package_test"
    runtime_name = f"{package_name}.runtime"
    original_package = sys.modules.get(package_name)
    original_runtime = sys.modules.get(runtime_name)
    sys.modules[runtime_name] = runtime
    try:
        spec = importlib.util.spec_from_file_location(
            package_name,
            ROOT / "load_image_x" / "__init__.py",
            submodule_search_locations=[str(ROOT / "load_image_x")],
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[package_name] = module
        spec.loader.exec_module(module)

        class Router:
            def __init__(self):
                self.get_routes = []
                self.post_routes = []

            def add_get(self, path, handler):
                self.get_routes.append((path, handler))

            def add_post(self, path, handler):
                self.post_routes.append((path, handler))

        app = types.SimpleNamespace(router=Router())
        module.register_routes(app)

        assert [path for path, _handler in app.router.get_routes] == [
            "/workflowx_configurator/load_image_x/images",
            "/workflowx_configurator/load_image_x/thumbnail",
        ]
        assert app.router.post_routes == [
            ("/workflowx_configurator/load_image_x/delete", runtime.delete_images_handler)
        ]
    finally:
        if original_package is None:
            sys.modules.pop(package_name, None)
        else:
            sys.modules[package_name] = original_package
        if original_runtime is None:
            sys.modules.pop(runtime_name, None)
        else:
            sys.modules[runtime_name] = original_runtime
