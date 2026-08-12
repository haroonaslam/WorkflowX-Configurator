from __future__ import annotations

import fnmatch
import json
import platform
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory


# b10252 matches LM Studio's llama.cpp engine 2.28.2 and includes the Qwen3.6
# embedded-MTP/NVFP4 loader required by current Blackwell GGUF releases.
LLAMA_CPP_RELEASE_TAG = "b10252"
RELEASE_API_URL = f"https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/{LLAMA_CPP_RELEASE_TAG}"
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
VENDOR_ROOT = PACKAGE_ROOT / "vendor" / "jsonx-llama.cpp"
USER_AGENT = "WorkflowX-JsonX"


@dataclass(frozen=True)
class PlatformSpec:
    key: str
    cli_executable: str
    asset_patterns: tuple[str, ...]
    required_files: tuple[str, ...]


@dataclass(frozen=True)
class LlamaCliPaths:
    cli: Path


WINDOWS_CUDA_13 = PlatformSpec(
    key="win-x64-cuda13",
    cli_executable="llama-cli.exe",
    asset_patterns=(
        "llama-*-bin-win-cuda-13*-x64.zip",
        "cudart-llama-bin-win-cuda-13*-x64.zip",
    ),
    required_files=("llama-cli.exe", "ggml-cuda.dll", "cudart64_13.dll"),
)


def _platform_spec() -> PlatformSpec:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows" and machine in {"amd64", "x86_64"}:
        return WINDOWS_CUDA_13
    raise RuntimeError("JsonX automatic llama.cpp download supports Windows x64 CUDA 13 only.")


def _json_get(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _format_size(num_bytes: float) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def _download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        total = response.headers.get("Content-Length")
        total_size = int(total) if total is not None else None
        downloaded = 0
        started = time.monotonic()
        last_report = started
        with destination.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                handle.write(chunk)
                downloaded += len(chunk)
                now = time.monotonic()
                if now - last_report < 1.0:
                    continue
                elapsed = max(now - started, 0.001)
                progress = f" / {_format_size(total_size)}" if total_size else ""
                print(
                    "[JsonX] Downloaded "
                    f"{_format_size(downloaded)}{progress} at {_format_size(downloaded / elapsed)}/s"
                )
                last_report = now


def _select_assets(release: dict, spec: PlatformSpec) -> list[dict]:
    assets = release.get("assets", [])
    selected = []
    for pattern in spec.asset_patterns:
        matches = [
            asset
            for asset in assets
            if fnmatch.fnmatch(str(asset.get("name") or "").lower(), pattern.lower())
        ]
        if not matches:
            raise RuntimeError(f"Could not find JsonX llama.cpp release asset matching: {pattern}")
        selected.append(sorted(matches, key=lambda item: item.get("name", ""))[0])
    return list({item["name"]: item for item in selected}.values())


def _find_file(root: Path, name: str) -> Path | None:
    return next((path for path in root.rglob(name) if path.is_file()), None)


def _is_complete(root: Path, spec: PlatformSpec) -> bool:
    return root.exists() and all(_find_file(root, name) is not None for name in spec.required_files)


def _paths(root: Path, spec: PlatformSpec) -> LlamaCliPaths:
    cli = _find_file(root, spec.cli_executable)
    if cli is None:
        raise RuntimeError(f"JsonX llama.cpp installation is missing {spec.cli_executable}: {root}")
    return LlamaCliPaths(cli=cli)


def _extract_assets(assets: list[dict], install_dir: Path) -> None:
    with TemporaryDirectory(prefix="workflowx-jsonx-llama-download-") as temp:
        temp_dir = Path(temp)
        for asset in assets:
            archive_path = temp_dir / asset["name"]
            print(f"[JsonX] Downloading {asset['name']}...")
            _download(asset["browser_download_url"], archive_path)
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(install_dir)


def ensure_llama_cli_paths() -> LlamaCliPaths:
    spec = _platform_spec()
    install_dir = VENDOR_ROOT / LLAMA_CPP_RELEASE_TAG / spec.key
    if _is_complete(install_dir, spec):
        return _paths(install_dir, spec)

    release = _json_get(RELEASE_API_URL)
    tag = str(release.get("tag_name") or LLAMA_CPP_RELEASE_TAG)
    install_dir = VENDOR_ROOT / tag / spec.key
    if _is_complete(install_dir, spec):
        return _paths(install_dir, spec)

    install_dir.mkdir(parents=True, exist_ok=True)
    _extract_assets(_select_assets(release, spec), install_dir)
    if not _is_complete(install_dir, spec):
        missing = [name for name in spec.required_files if _find_file(install_dir, name) is None]
        raise RuntimeError(f"JsonX llama.cpp download is incomplete; missing: {', '.join(missing)}")
    return _paths(install_dir, spec)
