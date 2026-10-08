import importlib
import os
from pathlib import Path

from test_packaging import _load_package


def _module():
    package = _load_package()
    return importlib.import_module(f"{package.__name__}.workflowx_downloader")


def test_downloader_is_registered_with_category_controls():
    package = _load_package()
    cls = package.NODE_CLASS_MAPPINGS["WorkflowX_Downloader"]
    assert package.NODE_DISPLAY_NAME_MAPPINGS["WorkflowX_Downloader"] == "WorkflowX Downloader"
    assert cls.CATEGORY == "WorkflowX/Utilities"
    assert cls.OUTPUT_NODE is True
    required = cls.INPUT_TYPES()["required"]
    assert required["download_all"][0] == "BOOLEAN"
    assert required["force_download"][0] == "BOOLEAN"
    assert set(_module().CATEGORY_PATTERNS) <= set(required)


def test_download_all_selects_every_category_and_exact_payload_paths():
    module = _module()
    assert module.selected_categories(True, {}) == tuple(module.CATEGORY_PATTERNS)
    patterns = module.patterns_for(("ffmpeg", "sam3", "auk"))
    files = module.matching_repo_files(
        [
            ".gitattributes",
            "custom_nodes/WorkflowX-Configurator/vendor/ffmpeg/ffmpeg.exe",
            "models/checkpoints/sam3.1_multiplex_fp16.safetensors",
            "models/diffusion_models/auk_base_bf16.safetensors",
            "models/text_encoders/qwen_omni_bf16.safetensors",
            "models/vae/auk_vae.safetensors",
            "models/whisper/auto-download.bin",
        ],
        patterns,
    )
    assert len(files) == 5
    assert ".gitattributes" not in files
    assert all("models/whisper" not in filename for filename in files)


def test_download_categories_targets_comfyui_root_and_activates_ffmpeg(tmp_path, monkeypatch):
    module = _module()
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("WORKFLOWX_FORCE_FFMPEG_PATH", raising=False)
    calls = {}
    repo_files = [
        "custom_nodes/WorkflowX-Configurator/vendor/ffmpeg/ffmpeg.exe",
        "models/checkpoints/sam3.1_multiplex_fp16.safetensors",
    ]

    def list_repo_files(**kwargs):
        calls["list"] = kwargs
        return repo_files

    def snapshot_download(**kwargs):
        calls["download"] = kwargs
        root = Path(kwargs["local_dir"])
        for filename in kwargs["allow_patterns"]:
            target = root / Path(filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"test")
        return str(root)

    status = module.download_categories(
        tmp_path,
        ("ffmpeg", "sam3"),
        force_download=True,
        max_workers=99,
        list_repo_files_fn=list_repo_files,
        snapshot_download_fn=snapshot_download,
    )

    expected_ffmpeg = (
        tmp_path
        / "custom_nodes"
        / "WorkflowX-Configurator"
        / "vendor"
        / "ffmpeg"
        / "ffmpeg.exe"
    ).resolve()
    assert calls["list"]["repo_id"] == "haslam/WorkflowX-DL"
    assert calls["download"]["local_dir"] == str(tmp_path.resolve())
    assert calls["download"]["force_download"] is True
    assert calls["download"]["max_workers"] == 16
    assert set(calls["download"]["allow_patterns"]) == set(repo_files)
    assert os.environ["WORKFLOWX_FORCE_FFMPEG_PATH"] == str(expected_ffmpeg)
    assert str(expected_ffmpeg) in status
    assert "2 files verified" in status


def test_empty_selection_is_rejected(tmp_path):
    module = _module()
    try:
        module.download_categories(tmp_path, ())
    except ValueError as exc:
        assert "Select at least one category" in str(exc)
    else:
        raise AssertionError("empty downloader selection should fail")
