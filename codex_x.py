"""Run ephemeral turns through the locally installed Codex App Server."""

import atexit
import asyncio
import json
import os
from pathlib import Path
from queue import Empty, Queue
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
from threading import Lock, Thread, Timer, current_thread
import time


TURN_TIMEOUT = 180
RPC_TIMEOUT = 10
STOP_TIMEOUT = 5
IDLE_TIMEOUT = 30 * 60
MODEL_CACHE_TIMEOUT = 60
CODEX_DEFAULT = "Use Codex setting"
WORKDIR = Path(__file__).resolve().parent
IMAGE_SOCKET = re.compile(r"image_([1-9][0-9]*)")
DESKTOP_SESSION_ENV = {
    "CODEX_APP_RUNTIME_CLI_PATH",
    "CODEX_APP_TOOLS_PIPE_PATH",
    "CODEX_INTERNAL_ORIGINATOR_OVERRIDE",
    "CODEX_PERMISSION_PROFILE",
    "CODEX_SESSION_ID",
    "CODEX_TASK_WORKSPACE_VERIFYING_IDENTITY",
    "CODEX_THREAD_ID",
    "CODEX_TOOL_CALL_ID",
    "CODEX_WINDOWS_REGISTERED_CORE",
    "CODEX_WINDOWS_SANDBOX_PACKAGE_FAMILY",
}


class CodexConnectionError(RuntimeError):
    pass


class CodexTimeout(CodexConnectionError):
    pass


class ImageInputs(dict):
    """Expose the first image slot and accept numbered sockets added by the editor."""

    def __contains__(self, key):
        return super().__contains__(key) or isinstance(key, str) and IMAGE_SOCKET.fullmatch(key) is not None

    def __missing__(self, key):
        if key in self:
            return ("IMAGE",)
        raise KeyError(key)


def save_images(directory, inputs):
    from .remote_image_api.runtime import tensor_images, tensor_to_png

    ordered = sorted(inputs, key=lambda name: int(IMAGE_SOCKET.fullmatch(name)[1]))
    paths = []
    for name in ordered:
        frames = tensor_images([inputs[name]])
        for index, frame in enumerate(frames, start=1):
            label = name if len(frames) == 1 else f"{name}-{index}"
            path = Path(directory) / f"{label}.png"
            path.write_bytes(tensor_to_png(frame.float()))
            paths.append(path)
    return paths


def find_codex():
    executable = shutil.which("codex.exe" if os.name == "nt" else "codex")
    if executable or os.name != "nt":
        return executable

    # The desktop app can expose codex.exe inside its Windows app package
    # without putting that directory on ComfyUI's PATH.
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    try:
        result = subprocess.run(
            [str(powershell), "-NoProfile", "-NonInteractive", "-Command",
             "[Console]::OutputEncoding = [Text.Encoding]::UTF8;"
             " (Get-AppxPackage -Name OpenAI.Codex | Select-Object -First 1).InstallLocation"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=RPC_TIMEOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    location = result.stdout.strip()
    if result.returncode == 0 and location:
        candidate = Path(location) / "app/resources/codex.exe"
        if candidate.is_file():
            return str(candidate)
    return None


class CodexAppServer:
    def __init__(self):
        executable = find_codex()
        if not executable:
            raise RuntimeError(
                "CodeX could not find Codex. Add the installed Codex executable to "
                "the PATH used by ComfyUI, then restart ComfyUI."
            )
        try:
            # A ComfyUI process launched from Codex can inherit desktop-only
            # runtime handles which cannot provision shells in this app server.
            # Keep the user's Codex home and provider settings.
            environment = {key: value for key, value in os.environ.items() if key.upper() not in DESKTOP_SESSION_ENV}
            self.process = subprocess.Popen(
                [executable, "app-server", "--listen", "stdio://"],
                cwd=WORKDIR,
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                encoding="utf-8",
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except OSError as exc:
            raise CodexConnectionError("CodeX could not start the installed Codex executable.") from exc

        self.events = Queue()
        self.request_id = 0
        self.thread_defaults = {}
        self.catalog = None
        self.catalog_expires = 0
        self.reader = Thread(target=self._read, name="CodeX stdout", daemon=True)
        self.reader.start()
        try:
            self.request("initialize", {"clientInfo": {"name": "workflowx_codex", "version": "1.0.0"}})
            self.send({"method": "initialized"})
        except BaseException:
            self.close()
            raise

    def _read(self):
        try:
            for line in self.process.stdout:
                message = json.loads(line)
                if not isinstance(message, dict):
                    break
                self.events.put(message)
        except (OSError, UnicodeError, ValueError):
            pass
        finally:
            self.events.put(None)

    def send(self, message):
        try:
            self.process.stdin.write(json.dumps(message) + "\n")
            self.process.stdin.flush()
        except OSError as exc:
            raise CodexConnectionError("CodeX lost its connection to the local Codex server.") from exc

    def receive(self, deadline, check_interrupt):
        while True:
            check_interrupt()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise CodexTimeout("CodeX timed out waiting for the local Codex server.")
            try:
                message = self.events.get(timeout=min(remaining, 0.2))
            except Empty:
                continue
            if message is None:
                raise CodexConnectionError("The local Codex server exited or returned invalid protocol data.")
            if "method" in message and "id" in message:
                self.send({
                    "id": message["id"],
                    "error": {"code": -32601, "message": "CodeX does not support interactive approvals."},
                })
                continue
            return message

    def request(self, method, params, *, timeout=RPC_TIMEOUT):
        self.request_id += 1
        request_id = self.request_id
        self.send({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while True:
            message = self.receive(deadline, lambda: None)
            if message.get("id") == request_id:
                if "error" in message:
                    error = message["error"].get("message", "Unknown error")
                    raise RuntimeError(f"CodeX request failed ({method}). {error}")
                return message["result"]

    def start_thread(self):
        result = self.request("thread/start", {
            "cwd": str(WORKDIR),
            "ephemeral": True,
            "sandbox": "read-only",
            "approvalPolicy": "never",
        })
        thread = result["thread"]
        if thread.get("ephemeral") is not True:
            raise CodexConnectionError("CodeX could not establish an ephemeral Codex session.")
        thread_id = thread["id"]
        self.thread_defaults[thread_id] = (result.get("model"), result.get("reasoningEffort"))
        return thread_id

    def model_catalog(self):
        if self.catalog is not None and time.monotonic() < self.catalog_expires:
            return self.catalog
        config = self.request("config/read", {"cwd": str(WORKDIR)})["config"]
        models = {}
        params = {}
        while True:
            page = self.request("model/list", params)
            for model in page["data"]:
                models[model["model"]] = {
                    "efforts": [item["reasoningEffort"] for item in model.get("supportedReasoningEfforts", [])],
                    "defaultEffort": model.get("defaultReasoningEffort"),
                    "acceptsImages": "image" in model.get("inputModalities", ["text", "image"]),
                }
                if model.get("isDefault") and not config.get("model"):
                    config["model"] = model["model"]
            cursor = page.get("nextCursor")
            if not cursor:
                break
            params = {"cursor": cursor}
        self.catalog = {"models": models, "defaultModel": config.get("model")}
        self.catalog_expires = time.monotonic() + MODEL_CACHE_TIMEOUT
        return self.catalog

    def turn_options(self, thread_id, model, effort, has_images):
        default_model, default_effort = self.thread_defaults.get(thread_id, (None, None))
        if model == effort == CODEX_DEFAULT:
            # Turn overrides persist on the Codex thread. Send the original
            # defaults so the inherited choices are restored on a follow-up.
            return {key: value for key, value in (("model", default_model), ("effort", default_effort)) if value}

        catalog = self.model_catalog()
        model_id = (default_model or catalog["defaultModel"]) if model == CODEX_DEFAULT else model
        entry = catalog["models"].get(model_id)
        if entry is None:
            raise ValueError(f"CodeX model {model_id!r} is unavailable. Select a model from the local Codex catalog.")
        if has_images and not entry["acceptsImages"]:
            raise ValueError(f"CodeX model {model_id!r} does not accept image inputs.")
        if effort == CODEX_DEFAULT:
            effort = default_effort if model_id == default_model else entry["defaultEffort"]
        elif effort not in entry["efforts"]:
            raise ValueError(f"CodeX model {model_id!r} does not support reasoning effort {effort!r}.")
        return {"model": model_id, **({"effort": effort} if effort else {})}

    def release(self, thread_id):
        self.thread_defaults.pop(thread_id, None)
        self.request("thread/unsubscribe", {"threadId": thread_id})

    def interrupt(self, thread_id, turn_id):
        try:
            self.request("turn/interrupt", {"threadId": thread_id, "turnId": turn_id}, timeout=STOP_TIMEOUT)
        except CodexConnectionError:
            # The server could not acknowledge cancellation. Stop it so the
            # turn cannot keep running after ComfyUI reports cancellation.
            if self.process.poll() is None:
                self.process.terminate()
        except RuntimeError:
            # A turn can finish between the local cancellation and the RPC.
            pass

    def run_turn(self, thread_id, instructions, check_interrupt, image_paths=(), *,
                 model=CODEX_DEFAULT, effort=CODEX_DEFAULT):
        check_interrupt()
        inputs = [{"type": "text", "text": instructions}]
        for path in image_paths:
            inputs.append({"type": "text", "text": f"Attached image: {path.stem}"})
            inputs.append({"type": "localImage", "path": str(path)})
        result = self.request("turn/start", {
            "threadId": thread_id,
            "input": inputs,
            **self.turn_options(thread_id, model, effort, bool(image_paths)),
        })
        turn_id = result["turn"]["id"]
        deadline = time.monotonic() + TURN_TIMEOUT
        response = None
        try:
            while True:
                message = self.receive(deadline, check_interrupt)
                params = message.get("params", {})
                if params.get("threadId") != thread_id:
                    continue
                if message.get("method") == "item/completed" and params.get("turnId") == turn_id:
                    item = params["item"]
                    if item.get("type") == "agentMessage" and item.get("phase") in (None, "final_answer", "finalAnswer"):
                        response = item["text"]
                if message.get("method") != "turn/completed" or params["turn"]["id"] != turn_id:
                    continue
                turn = params["turn"]
                break
        except CodexTimeout as exc:
            self.interrupt(thread_id, turn_id)
            raise RuntimeError(f"CodeX reached its {TURN_TIMEOUT}-second turn timeout.") from exc
        except BaseException:
            self.interrupt(thread_id, turn_id)
            raise

        if turn["status"] != "completed":
            error = (turn.get("error") or {}).get("message") or turn["status"]
            raise RuntimeError(f"CodeX turn failed. {error} Check `codex login status` if authentication failed.")
        if response is None:
            raise RuntimeError("Codex completed the turn without a final text response.")
        return response

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=STOP_TIMEOUT)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.reader.join(timeout=STOP_TIMEOUT)
        self.process.stdin.close()
        self.process.stdout.close()


class CodeXSessions:
    def __init__(self):
        self.lock = Lock()
        self.server = None
        self.sessions = {}

    def _close(self):
        for _, timer, _ in self.sessions.values():
            timer.cancel()
        self.sessions.clear()
        if self.server is not None:
            server, self.server = self.server, None
            server.close()

    def close(self):
        with self.lock:
            self._close()

    def _take(self, key):
        entry = self.sessions.pop(key, None)
        if entry is not None:
            thread_id, timer, expires_at = entry
            timer.cancel()
            if time.monotonic() < expires_at:
                return thread_id
            self._release(thread_id)
        return None

    def _release(self, thread_id):
        try:
            self.server.release(thread_id)
        except RuntimeError:
            self._close()

    def _expire(self, key, thread_id):
        with self.lock:
            entry = self.sessions.get(key)
            if entry is not None and entry[0] == thread_id and entry[1] is current_thread():
                self.sessions.pop(key)
                self._release(thread_id)

    def _retain(self, key, thread_id):
        timer = Timer(IDLE_TIMEOUT, self._expire, args=(key, thread_id))
        timer.daemon = True
        self.sessions[key] = (thread_id, timer, time.monotonic() + IDLE_TIMEOUT)
        timer.start()

    def _app_server(self):
        if self.server is not None and self.server.process.poll() is not None:
            self._close()
        if self.server is None:
            self.server = CodexAppServer()
        return self.server

    def model_catalog(self):
        with self.lock:
            try:
                return self._app_server().model_catalog()
            except CodexConnectionError:
                self._close()
                raise

    def run(self, instructions, key, discard, reset, check_interrupt, image_paths=(), *,
            model=CODEX_DEFAULT, effort=CODEX_DEFAULT):
        if not discard and key is None:
            raise RuntimeError(
                "CodeX continuation needs a ComfyUI client and workflow ID. "
                "Queue from the workflow editor or enable Discard session after response."
            )
        while not self.lock.acquire(timeout=0.2):
            check_interrupt()
        try:
            check_interrupt()
            return self._run(instructions, key, discard, reset, check_interrupt, image_paths, model, effort)
        finally:
            self.lock.release()

    def _run(self, instructions, key, discard, reset, check_interrupt, image_paths, model, effort):
        if self.server is not None and self.server.process.poll() is not None:
            self._close()
        thread_id = self._take(key)
        if thread_id is not None and (discard or reset):
            self._release(thread_id)
            thread_id = None
        server = self._app_server()
        try:
            if thread_id is None:
                thread_id = server.start_thread()
            response = server.run_turn(thread_id, instructions, check_interrupt, image_paths, model=model, effort=effort)
        except CodexConnectionError:
            self._close()
            raise
        except BaseException:
            if thread_id is not None:
                self._release(thread_id)
            raise
        if discard:
            self._release(thread_id)
        else:
            self._retain(key, thread_id)
        return response


_sessions = CodeXSessions()
atexit.register(_sessions.close)


def _is_loopback_server():
    from comfy.cli_args import args
    from server import is_loopback

    return all(is_loopback(host.strip()) for host in args.listen.split(","))


def register_routes():
    try:
        from aiohttp import web
        from server import PromptServer
    except ImportError:
        return
    instance = getattr(PromptServer, "instance", None)
    if instance is None:
        return

    @instance.routes.get("/workflowx_configurator/codex/models")
    async def models(_request):
        if not _is_loopback_server():
            return web.json_response({"error": "CodeX requires a loopback server."}, status=403)
        try:
            return web.json_response(await asyncio.to_thread(_sessions.model_catalog))
        except RuntimeError as exc:
            return web.json_response({"error": str(exc)}, status=503)


class CodeX:
    CATEGORY = "WorkflowX/Prompting"
    FUNCTION = "ask"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("response",)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "instructions": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": ImageInputs({
                "text": ("STRING", {"forceInput": True, "tooltip": "Additional text to send with the instructions."}),
                "discard_session_after_response": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Release the temporary session after each response. Turn off to continue it on the next run.",
                }),
                "reset_session_on_next_run": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Start with fresh context on this run. Turn this off again to continue the new session.",
                }),
                "image_1": ("IMAGE",),
                "model": ([CODEX_DEFAULT], {"tooltip": "Select a model available in the local Codex catalog."}),
                "reasoning_effort": ([CODEX_DEFAULT], {
                    "tooltip": "Use the configured effort for the Codex model, or the selected model's default.",
                }),
            }),
            "hidden": {"unique_id": "UNIQUE_ID", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    @classmethod
    def IS_CHANGED(cls, **_kwargs):
        return float("nan")

    @classmethod
    def VALIDATE_INPUTS(cls, model=CODEX_DEFAULT, reasoning_effort=CODEX_DEFAULT):
        # ComfyUI's static schema has only the default choice. Runtime
        # validation uses the selected account's model catalog.
        return True

    def ask(self, instructions, discard_session_after_response=True, reset_session_on_next_run=False,
            unique_id=None, extra_pnginfo=None, text="", model=CODEX_DEFAULT,
            reasoning_effort=CODEX_DEFAULT, **images):
        from comfy.model_management import throw_exception_if_processing_interrupted
        from server import PromptServer

        if not _is_loopback_server():
            raise RuntimeError("CodeX requires ComfyUI to listen on loopback only. Use --listen 127.0.0.1.")
        prompt = "\n\n".join(piece for piece in (instructions, text) if piece.strip())
        if not prompt:
            raise ValueError("Enter instructions or connect a text input to CodeX before queueing.")

        workflow = (extra_pnginfo or {}).get("workflow") or {}
        workflow_id = workflow.get("id") if isinstance(workflow, dict) else None
        client_id = getattr(PromptServer.instance, "client_id", None)
        key = None
        if client_id and isinstance(workflow_id, str) and workflow_id and unique_id is not None:
            key = (client_id, workflow_id, unique_id)
        run_args = (
            prompt, key, discard_session_after_response, reset_session_on_next_run,
            throw_exception_if_processing_interrupted,
        )
        if images:
            with TemporaryDirectory(prefix="workflowx-codex-images-") as directory:
                response = _sessions.run(
                    *run_args, image_paths=save_images(directory, images), model=model, effort=reasoning_effort,
                )
        else:
            response = _sessions.run(*run_args, model=model, effort=reasoning_effort)
        return (response,)
