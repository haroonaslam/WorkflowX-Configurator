"""Entry gates and bounded, process-local replay snapshots. No executor cache mutation."""
import asyncio
import copy
import io
import json
import logging
import threading
import time
import uuid
from collections import OrderedDict

from .config import normalize

LOG = logging.getLogger("WorkflowX.DetailerX")
TYPE = "WorkflowX_DetailerX"
TAP = "WorkflowX_DetailerXCapture"
SOURCE = "WorkflowX_DetailerXSnapshot"
REPLAY = "WorkflowX_DetailerXReplay"
LIMIT = 2 * 1024**3
LOCK = threading.RLock()
SESSIONS = OrderedDict()
ACTIVE_PROMPTS = lambda: set()


def link(value):
    return isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and type(value[1]) is int


def descendants(prompt, target):
    found = {target}
    while True:
        added = {key for key, node in prompt.items() if any(link(v) and v[0] in found for v in node.get("inputs", {}).values())}
        if added <= found:
            return found
        found |= added


def snapshot(value):
    import torch
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().clone()
    if isinstance(value, dict):
        return {k: snapshot(v) for k, v in value.items()}
    if isinstance(value, list):
        return [snapshot(v) for v in value]
    if isinstance(value, tuple):
        return tuple(snapshot(v) for v in value)
    # Model patchers/encoders/VAEs are authoritative references, never copied weights.
    return value


def size_of(value, seen=None):
    import torch
    seen = set() if seen is None else seen
    if id(value) in seen:
        return 0
    seen.add(id(value))
    if isinstance(value, torch.Tensor):
        return value.numel() * value.element_size()
    if isinstance(value, dict):
        return sum(size_of(v, seen) for v in value.values())
    if isinstance(value, (list, tuple)):
        return sum(size_of(v, seen) for v in value)
    return 0


def retain(s, key, value, boundary=False):
    """Reserve bounded tensor storage before cloning; active jobs are never evicted."""
    with LOCK:
        target=s['boundary'] if boundary else s
        additional=size_of(value)-size_of(target.get(key))
        active=ACTIVE_PROMPTS()
        total=sum(size_of((v.get('inputs'),v['boundary'])) for v in SESSIONS.values())
        for token,other in list(SESSIONS.items()):
            if total+additional<=LIMIT:
                break
            if other is s or other['state'] in ('paused','processing','queued') or other.get('prompt_id') in active:
                continue
            total-=size_of((other.get('inputs'),other['boundary']))
            del SESSIONS[token]
        if total+additional>LIMIT:
            raise ValueError('DetailerX retained inputs exceed the shared 2 GiB limit. Reduce the batch or finish other paused jobs.')
        target[key]=snapshot(value)


def prune():
    active = ACTIVE_PROMPTS()
    for s in SESSIONS.values():
        if s["state"] in ("queued", "waiting") and s.get("prompt_id") not in active and time.monotonic()-s["created"]>10:
            s["state"],s["error"]="failed","Queued job was removed or rejected; queue again."
    total = sum(size_of((s.get("inputs"), s["boundary"])) for s in SESSIONS.values())
    for token, s in list(SESSIONS.items()):
        if s["state"] in ("paused", "processing", "queued") or s.get("prompt_id") in active:
            continue
        if total <= LIMIT and len(SESSIONS) <= 32:
            continue
        total -= size_of((s.get("inputs"), s["boundary"]))
        del SESSIONS[token]


def new_session(owner, node, settings, prompt=None, token=None):
    with LOCK:
        # Keep older active jobs isolated, discard previous idle retained inputs.
        for key, value in list(SESSIONS.items()):
            if value["owner"] == owner and value["state"] not in ("paused", "processing", "queued", "waiting") and value.get("prompt_id") not in ACTIVE_PROMPTS():
                del SESSIONS[key]
        token = token or uuid.uuid4().hex
        s = dict(token=token, owner=owner, node=str(node), settings=normalize(settings),
                 prompt=copy.deepcopy(prompt or {}), boundary={}, state="waiting", action=None,
                 created=time.monotonic(), entered=None, prompt_id=None, inputs=None, error="", revision=0)
        SESSIONS[token] = s
        prune()
        return s


def get_session(token, owner=None):
    with LOCK:
        s = SESSIONS.get(token)
        if s is None or (owner is not None and s["owner"] != owner):
            raise ValueError("Retained inputs unavailable. Run the ordinary workflow again.")
        SESSIONS.move_to_end(token)
        return s


def view(s):
    entry = s["settings"]["entry"]
    remaining = None
    if s["state"] == "paused" and not entry["wait_indefinitely"]:
        remaining = max(0, entry["pause_minutes"] * 60 - (time.monotonic() - s["entered"]))
    busy = s.get("prompt_id") in ACTIVE_PROMPTS()
    return dict(token=s["token"], owner=s["owner"], node=s["node"], state=s["state"], remaining=remaining,
                skip=s["settings"]["entry"]["skip"],
                revision=s["revision"], error=s["error"], can_rerun=bool(s["inputs"]) and not busy and s["state"] in ("completed", "passed", "failed"),
                batch=int(s["inputs"]["image"].shape[0]) if s["inputs"] else 0)


def announce(s):
    LOG.info("[DetailerX #%s] %s%s", s["node"], s["state"], f' — {s["error"]}' if s["error"] else "")
    try:
        from server import PromptServer
        PromptServer.instance.send_sync("workflowx.detailer_x.entry", view(s))
    except (ImportError, AttributeError):
        pass


def command(s, action, settings=None, revision=None):
    with LOCK:
        if s["state"] != "paused":
            raise ValueError("This run is no longer paused; refresh its status.")
        if s["action"] is not None:
            raise ValueError("This paused run has already been released.")
        if action not in ("update", "resume", "skip", "cancel"):
            raise ValueError("Unknown entry action")
        if action in ("update", "resume"):
            try:
                validated = normalize(settings)
            except (ValueError, TypeError) as exc:
                s["error"] = str(exc)
                if s.get("wake"):
                    s["loop"].call_soon_threadsafe(s["wake"].set)
                raise
            if revision is not None and revision < s["revision"]:
                raise ValueError("Settings update is stale")
            s["settings"] = validated
            s["revision"] = revision if revision is not None else s["revision"] + 1
            s["error"] = ""
        if action != "update":
            s["action"] = "pass" if action in ("skip", "cancel") else "resume"
        if s.get("wake"):
            s["loop"].call_soon_threadsafe(s["wake"].set)


async def gate(s, cancelled):
    wake = asyncio.Event()
    with LOCK:
        s["loop"], s["wake"] = asyncio.get_running_loop(), wake
        s["entered"] = time.monotonic()
        skip = s["settings"]["entry"]["skip"]
        s["state"] = "paused" if s["settings"]["entry"]["pause"] and not skip else "processing"
    announce(s)
    async def watch_interrupt():
        # ComfyUI exposes global interruption as a flag, not an awaitable.
        # This local watchdog never polls status or drives normal resumption.
        while True:
            cancelled()
            await asyncio.sleep(.1)
    watchdog = asyncio.create_task(watch_interrupt())
    waiter = None
    try:
        if skip:
            return False
        while s["state"] == "paused":
            cancelled()
            with LOCK:
                wake.clear()
                if s["settings"]["entry"]["skip"]:
                    s["state"] = "passed"
                    return False
                action = s["action"]
                if action:
                    s["state"] = "processing" if action == "resume" else "passed"
                    return action == "resume"
                entry = s["settings"]["entry"]
                timeout = None if s["error"] or entry["wait_indefinitely"] else max(0, s["entered"] + entry["pause_minutes"] * 60 - time.monotonic())
                if timeout == 0:
                    s["state"] = "processing"
                    return True
            waiter = asyncio.create_task(wake.wait())
            done, _ = await asyncio.wait((waiter, watchdog), timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
            waiter.cancel()
            await asyncio.gather(waiter, return_exceptions=True)
            if watchdog in done:
                await watchdog
        return True
    finally:
        with LOCK:
            s.pop("wake", None)
            s.pop("loop", None)
        watchdog.cancel()
        if waiter: waiter.cancel()
        await asyncio.gather(watchdog, *([waiter] if waiter else []), return_exceptions=True)


def prepare_prompt(payload):
    """Inject typed-transparent capture nodes only at downstream branch boundaries."""
    prompt = payload.get("prompt", {})
    if any(n.get("class_type")==TYPE for n in prompt.values()):
        payload.setdefault("prompt_id", str(uuid.uuid4()))
    original = copy.deepcopy(prompt)
    for node, definition in original.items():
        if definition.get("class_type") != TYPE:
            continue
        raw = json.loads(definition["inputs"].get("settings") or "{}")
        owner = raw.get("_control", {}).get("owner") or uuid.uuid4().hex
        s = new_session(owner, node, raw, original)
        s["prompt_id"] = payload.get("prompt_id")
        raw["_run"] = s["token"]
        prompt[node]["inputs"]["settings"] = json.dumps(raw)
        inside = descendants(original, node)
        captured = {}
        for consumer in inside - {node}:
            for name, value in original[consumer].get("inputs", {}).items():
                if not link(value) or value[0] in inside:
                    continue
                key = json.dumps(value)
                if key not in captured:
                    tap_id = f"dx_capture_{s['token']}_{len(captured)}"
                    # Use an existing tap link when several DetailerX branches share a boundary.
                    prompt[tap_id] = dict(class_type=TAP, inputs=dict(value=prompt[consumer]["inputs"][name], token=s["token"], key=key))
                    captured[key] = tap_id
                prompt[consumer]["inputs"][name] = [captured[key], 0]
    return payload


def replay_graph(s, prompt, target, settings, job):
    if target not in prompt or prompt[target].get("class_type") != TYPE:
        raise ValueError("DetailerX mapping changed or is dynamically expanded. Queue the ordinary workflow.")
    inside = descendants(prompt, target)
    result = {key: copy.deepcopy(prompt[key]) for key in inside}
    result[target] = dict(class_type=REPLAY, inputs=dict(token=s["token"], settings=json.dumps(normalize(settings)), job=job))
    for consumer in inside - {target}:
        for name, value in list(result[consumer].get("inputs", {}).items()):
            if not link(value) or value[0] in inside:
                continue
            key = json.dumps(value)
            old_source=s["prompt"].get(value[0],{})
            if old_source and old_source.get("class_type")!=prompt.get(value[0],{}).get("class_type"):
                raise ValueError(f"Boundary source {value[0]} changed type. Queue the ordinary workflow.")
            if key not in s["boundary"]:
                raise ValueError(f"No retained input for {consumer}.{name}. Queue the ordinary workflow to capture this connection.")
            source = f"dx_snapshot_{len(result)}_{job}"
            result[source] = dict(class_type=SOURCE, inputs=dict(token=s["token"], key=key, job=job))
            result[consumer]["inputs"][name] = [source, 0]
    return result


class AnyType(str):
    def __ne__(self, other):
        return False


ANY = AnyType("*")


class Capture:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"value": (ANY,), "token": ("STRING",), "key": ("STRING",)}}
    RETURN_TYPES = (ANY,)
    OUTPUT_IS_LIST = (True,)
    INPUT_IS_LIST = True
    FUNCTION = "capture"
    CATEGORY = "WorkflowX/Internal"
    def capture(self, value, token, key):
        with LOCK:
            s = get_session(token[0])
            try:
                retain(s,key[0],value,boundary=True)
            except ValueError as exc:
                s["error"] = str(exc)
            prune()
        return (value,)


class Snapshot:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"token": ("STRING",), "key": ("STRING",), "job": ("STRING",)}}
    RETURN_TYPES = (ANY,)
    OUTPUT_IS_LIST = (True,)
    FUNCTION = "read"
    CATEGORY = "WorkflowX/Internal"
    def read(self, token, key, job):
        return (snapshot(get_session(token)["boundary"][key]),)


def effective_metadata(prompt, extra, node, settings):
    # Prompt/history and image metadata must identify the settings actually applied.
    if prompt and node in prompt:
        prompt[node].setdefault("inputs", {})["settings"] = json.dumps(settings)
    if isinstance(extra, dict):
        extra.setdefault("detailer_x_effective", {})[str(node)] = copy.deepcopy(settings)


async def execute_entry(processor, inputs, settings, node=None, prompt=None, extra=None):
    from .processing import cancelled
    from comfy_execution.utils import get_executing_context
    raw = json.loads(settings) if isinstance(settings, str) else settings
    token = raw.get("_run")
    s = get_session(token) if token else new_session(raw.get("_control", {}).get("owner", uuid.uuid4().hex), node, raw, prompt)
    context = get_executing_context()
    s["prompt_id"] = context.prompt_id if context else None
    if context and context.list_index not in (None, 0):
        raise ValueError("DetailerX entry controls require a tensor batch, not list-mapped inputs. Combine the image list into a batch first.")
    try:
        if size_of(inputs) > LIMIT:
            raise ValueError("DetailerX retained inputs exceed 2 GiB. Reduce image batch size.")
        retain(s,"inputs",inputs)
        run = await gate(s, cancelled)
        effective_metadata(prompt, extra, node, s["settings"])
        if run:
            s["state"] = "processing"
            announce(s)
            result = processor(**inputs, settings=s["settings"], unique_id=node)
            s["state"] = "completed"
        else:
            result = tuple(inputs["image"].clone() for _ in range(9))
            s["state"] = "passed"
        return result
    except BaseException as exc:
        s["state"], s["error"] = "failed", str(exc)
        raise
    finally:
        announce(s)
        with LOCK:
            prune()


def register(server):
    from aiohttp import web
    from urllib.parse import urlsplit
    global ACTIVE_PROMPTS
    def active():
        running, pending = server.prompt_queue.get_current_queue_volatile()
        return {row[1] for row in (*running, *pending)}
    ACTIVE_PROMPTS = active
    server.add_on_prompt_handler(prepare_prompt)

    def safe(request):
        # Fetch Metadata is set by the browser, not page JavaScript. A proven
        # same-origin request must not be rejected by a proxy-rewritten Host.
        site = request.headers.get("Sec-Fetch-Site", "").lower()
        if site == "same-origin":
            return
        origin = request.headers.get("Origin")
        if site == "cross-site" or (origin and urlsplit(origin).netloc.lower() != request.host.lower()):
            LOG.warning("DetailerX entry request rejected: origin=%r host=%r fetch_site=%r", origin, request.host, site)
            raise web.HTTPForbidden(text="DetailerX blocked a non-matching request origin. Open ComfyUI directly at its server address and refresh.")

    @server.routes.get("/workflowx_configurator/detailer_x/entry")
    async def state(request):
        safe(request)
        owner = request.query.get("owner", "")
        with LOCK:
            prune()
            s = next((s for s in reversed(list(SESSIONS.values())) if s["owner"] == owner), None)
            return web.json_response(view(s) if s else dict(state="ready", can_rerun=False))

    @server.routes.get("/workflowx_configurator/detailer_x/entry/image")
    async def image(request):
        safe(request)
        try:
            s = get_session(request.query["token"], request.query["owner"])
            from PIL import Image
            import numpy as np
            index = int(request.query.get("index", 0))
            tensor = s["inputs"]["image"][index]
            img = Image.fromarray((tensor.clamp(0, 1).cpu().numpy() * 255).astype(np.uint8))
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            return web.Response(body=buffer.getvalue(), content_type="image/png", headers={"Cache-Control": "no-store"})
        except (ValueError, KeyError, IndexError, TypeError):
            raise web.HTTPNotFound()

    @server.routes.post("/workflowx_configurator/detailer_x/entry")
    async def control(request):
        safe(request)
        try:
            data = await request.json()
            owner, action = data["owner"], data["action"]
            if not isinstance(owner, str) or not 1 <= len(owner) <= 200:
                raise ValueError("Invalid owner")
            with LOCK:
                s = get_session(data["token"], owner)
                command(s, action, data.get("settings"), data.get("revision"))
                announce(s)
                return web.json_response(view(s))
        except (ValueError, TypeError, KeyError) as exc:
            return web.json_response(dict(error=str(exc)), status=400)

    @server.routes.post("/workflowx_configurator/detailer_x/rerun")
    async def rerun(request):
        safe(request)
        s = None
        previous = None
        try:
            data = await request.json()
            with LOCK:
                s = get_session(data["token"], data["owner"])
                if not view(s)["can_rerun"]:
                    raise ValueError("Wait for the current workflow to finish before rerunning.")
                previous = s["state"]
                job = str(uuid.uuid4())
                graph = replay_graph(s, data["prompt"], str(data["target"]), data["settings"], job)
                s["state"] = "queued"
                s["created"] = time.monotonic()
            import execution
            valid = await execution.validate_prompt(job, graph, None)
            if not valid[0]:
                raise ValueError(f"Rerun graph is not supported: {valid[1]}")
            extra = copy.deepcopy(data.get("extra_data", {}))
            extra["client_id"] = data.get("client_id")
            extra["detailer_x_effective"] = {str(data["target"]): normalize(data["settings"])}
            with LOCK:
                s["prompt_id"] = job
                number = server.number
                server.number += 1
                server.prompt_queue.put((number, job, graph, extra, valid[2], {}))
            announce(s)
            return web.json_response(dict(prompt_id=job))
        except (ValueError, TypeError, KeyError) as exc:
            if s is not None and previous is not None:
                s["state"] = previous
            return web.json_response(dict(error=str(exc)), status=400)
