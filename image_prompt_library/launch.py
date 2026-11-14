"""Can be run by path without importing WorkflowX or ComfyUI."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser


ROOT = Path(__file__).resolve().parent.parent


def ensure_started(home=None):
    home = Path(home or Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share")) / "WorkflowX" / "ImagePromptLibrary").resolve()
    home.mkdir(parents=True, exist_ok=True)
    def running():
        try:
            info = json.loads((home / "session.json").read_text(encoding="utf-8"))
            port = int(info["port"])
            url = f"http://127.0.0.1:{port}"
            request = urllib.request.Request(url + "/api/health", headers={"X-Library-Token": info["token"]})
            with urllib.request.urlopen(request, timeout=1) as response:
                if json.load(response).get("app") == "workflowx-image-prompt-library":
                    return url + "/#" + info["token"]
        except (OSError, ValueError, KeyError, urllib.error.URLError):
            return None
    url = running()
    if url:
        return url
    # -c also works with Windows embedded Python, which may disable cwd imports.
    code = "import sys,runpy;sys.path.insert(0,sys.argv.pop(1));runpy.run_module('image_prompt_library.server',run_name='__main__')"
    with (home / "server.log").open("ab") as log:
        process = subprocess.Popen([sys.executable, "-c", code, str(ROOT), "--home", str(home)], cwd=ROOT,
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    for _ in range(100):
        url = running()
        if url:
            return url
        if process.poll() not in (None, 0):
            break
        time.sleep(0.1)
    raise RuntimeError(f"Library did not start. See {home / 'server.log'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", action="store_true", help="Print launch URL instead of opening browser")
    parser.add_argument("--home", type=Path)
    args = parser.parse_args()
    url = ensure_started(args.home)
    if args.url:
        print(url)
    else:
        webbrowser.open(url)
