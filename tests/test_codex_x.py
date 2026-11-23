import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


spec = importlib.util.spec_from_file_location(
    "workflowx_codex_test", Path(__file__).resolve().parents[1] / "codex_x.py",
)
codex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(codex)


class FakeServer:
    def __init__(self):
        self.process = SimpleNamespace(poll=lambda: None)
        self.created = []
        self.released = []
        self.closed = False

    def start_thread(self):
        thread_id = str(len(self.created) + 1)
        self.created.append(thread_id)
        return thread_id

    def run_turn(self, thread_id, instructions, check_interrupt, image_paths=(), **_settings):
        check_interrupt()
        if instructions == "crash":
            raise codex.CodexConnectionError("server exited")
        if instructions == "timeout":
            raise RuntimeError("turn expired")
        return thread_id

    def release(self, thread_id):
        self.released.append(thread_id)

    def close(self):
        self.closed = True


@pytest.fixture
def sessions(monkeypatch):
    monkeypatch.setattr(codex, "CodexAppServer", FakeServer)
    manager = codex.CodeXSessions()
    yield manager
    manager.close()


def run(sessions, key=("client", "workflow", "node"), discard=False, reset=False, text="test"):
    return sessions.run(text, key, discard, reset, lambda: None)


def test_continue_reset_discard_and_isolation(sessions):
    assert run(sessions) == "1"
    assert run(sessions) == "1"
    assert run(sessions, key=("client", "other-workflow", "node")) == "2"
    assert run(sessions, key=("client", "workflow", "other-node")) == "3"
    assert run(sessions, key=("other-client", "workflow", "node")) == "4"
    assert run(sessions, reset=True) == "5"
    assert run(sessions, discard=True) == "6"
    assert run(sessions) == "7"
    assert sessions.server.released == ["1", "5", "6"]


def test_stateless_api_and_idle_expiry(sessions, monkeypatch):
    with pytest.raises(RuntimeError, match="workflow ID"):
        run(sessions, key=None)
    assert run(sessions, key=None, discard=True) == "1"

    released = codex.Lock()
    released.acquire()
    original = sessions.server.release

    def release(thread_id):
        original(thread_id)
        released.release()

    monkeypatch.setattr(sessions.server, "release", release)
    monkeypatch.setattr(codex, "IDLE_TIMEOUT", 0.01)
    assert run(sessions) == "2"
    assert released.acquire(timeout=1)
    assert sessions.server.released == ["1", "2"]


def test_failed_turn_and_server_restart(sessions):
    assert run(sessions) == "1"
    server = sessions.server
    with pytest.raises(RuntimeError, match="turn expired"):
        run(sessions, text="timeout")
    assert server.released == ["1"]
    assert run(sessions) == "2"

    with pytest.raises(codex.CodexConnectionError, match="server exited"):
        run(sessions, text="crash")
    assert server.closed
    assert run(sessions) == "1"
    assert sessions.server is not server


def test_turn_routes_only_the_matching_final_text(monkeypatch):
    server = object.__new__(codex.CodexAppServer)
    server.thread_defaults = {}
    events = iter([
        {"method": "item/completed", "params": {
            "threadId": "thread", "turnId": "turn",
            "item": {"type": "agentMessage", "phase": "commentary", "text": "Searching…"},
        }},
        {"method": "item/completed", "params": {
            "threadId": "thread", "turnId": "old-turn",
            "item": {"type": "agentMessage", "text": "stale"},
        }},
        {"method": "item/completed", "params": {
            "threadId": "thread", "turnId": "turn",
            "item": {"type": "agentMessage", "phase": "final_answer", "text": "Done ✓"},
        }},
        {"method": "turn/completed", "params": {
            "threadId": "thread", "turn": {"id": "turn", "status": "completed"},
        }},
    ])
    monkeypatch.setattr(server, "request", lambda *args: {"turn": {"id": "turn"}})
    monkeypatch.setattr(server, "receive", lambda *args: next(events))
    assert server.run_turn("thread", "test", lambda: None) == "Done ✓"


def test_numbered_inputs_and_multimodal_turn(monkeypatch, tmp_path):
    inputs = codex.CodeX.INPUT_TYPES()["optional"]
    assert inputs["image_1"] == inputs["image_22"] == ("IMAGE",)
    assert "image_0" not in inputs and "invalid" not in inputs

    server = object.__new__(codex.CodexAppServer)
    server.thread_defaults = {}
    sent = []

    def request(method, params):
        assert method == "turn/start"
        sent.extend(params["input"])
        return {"turn": {"id": "turn"}}

    monkeypatch.setattr(server, "request", request)
    monkeypatch.setattr(server, "receive", lambda *args: {
        "method": "turn/completed",
        "params": {"threadId": "thread", "turn": {"id": "turn", "status": "completed"}},
    })
    first = tmp_path / "image_1.png"
    second = tmp_path / "image_3-1.png"
    with pytest.raises(RuntimeError, match="without a final text response"):
        server.run_turn("thread", "Compare both.", lambda: None, [first, second])
    assert sent == [
        {"type": "text", "text": "Compare both."},
        {"type": "text", "text": "Attached image: image_1"},
        {"type": "localImage", "path": str(first)},
        {"type": "text", "text": "Attached image: image_3-1"},
        {"type": "localImage", "path": str(second)},
    ]


@pytest.mark.parametrize("failure", [codex.CodexTimeout("expired"), KeyboardInterrupt()])
def test_active_turn_is_interrupted(monkeypatch, failure):
    server = object.__new__(codex.CodexAppServer)
    server.thread_defaults = {}
    interrupted = []

    def receive(*args):
        raise failure

    monkeypatch.setattr(server, "request", lambda *args: {"turn": {"id": "turn"}})
    monkeypatch.setattr(server, "receive", receive)
    monkeypatch.setattr(server, "interrupt", lambda *args: interrupted.append(args))
    expected = RuntimeError if isinstance(failure, codex.CodexTimeout) else KeyboardInterrupt
    with pytest.raises(expected):
        server.run_turn("thread", "test", lambda: None)
    assert interrupted == [("thread", "turn")]


def test_model_options_preserve_thread_defaults_and_validate_catalog(monkeypatch):
    server = object.__new__(codex.CodexAppServer)
    server.thread_defaults = {"thread": ("configured", "medium")}
    models = {
        "configured": {"efforts": ["low", "medium"], "defaultEffort": "low", "acceptsImages": True},
        "other": {"efforts": ["low", "high"], "defaultEffort": "low", "acceptsImages": False},
    }
    monkeypatch.setattr(server, "model_catalog", lambda: {"models": models})
    default = codex.CODEX_DEFAULT

    assert server.turn_options("thread", "other", "high", False) == {"model": "other", "effort": "high"}
    assert server.turn_options("thread", "other", default, False) == {"model": "other", "effort": "low"}
    assert server.turn_options("thread", default, "low", False) == {"model": "configured", "effort": "low"}
    assert server.turn_options("thread", default, default, False) == {"model": "configured", "effort": "medium"}
    with pytest.raises(ValueError, match="unavailable"):
        server.turn_options("thread", "removed", default, False)
    with pytest.raises(ValueError, match="does not support reasoning effort"):
        server.turn_options("thread", "other", "medium", False)
    with pytest.raises(ValueError, match="does not accept image inputs"):
        server.turn_options("thread", "other", "high", True)
