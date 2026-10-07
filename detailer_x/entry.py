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
SELECTIVE = "WorkflowX_DetailerXSelective"
CONNECTED_SELECTIVE = "WorkflowX_DetailerXConnectedSelective"
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


def ancestors(prompt, seeds):
    """Return seeds plus every node needed to evaluate their linked inputs."""
    found = set(seeds)
    pending = list(seeds)
    while pending:
        key = pending.pop()
        for value in prompt.get(key, {}).get("inputs", {}).values():
            if link(value) and value[0] in prompt and value[0] not in found:
                found.add(value[0])
                pending.append(value[0])
    return found


def image_source_changed(previous, current, target):
    """Detect rewiring and changed leaf image loaders without treating a
    generation node's post-queue seed update as a request to regenerate it."""
    old_link = previous.get(target, {}).get("inputs", {}).get("image")
    new_link = current.get(target, {}).get("inputs", {}).get("image")
    if old_link != new_link:
        return True
    if not link(new_link):
        # Validation handles genuinely missing required inputs. Keeping two
        # absent synthetic/test links equivalent also preserves replay helpers.
        return False
    old_source = previous.get(new_link[0], {})
    new_source = current.get(new_link[0], {})
    # A leaf image provider (Load Image and equivalents) has no linked input.
    # Its filename/content selector must be current for iterative workflows.
    if not any(link(value) for value in new_source.get("inputs", {}).values()):
        return old_source != new_source
    return False


def connected_graph(prompt, target, settings, owner=None):
    """Keep DetailerX descendants and only the ancestors they actually require."""
    if target not in prompt or prompt[target].get("class_type") != TYPE:
        raise ValueError("DetailerX cannot be resolved in the current graph.")
    if not link(prompt[target].get("inputs", {}).get("image")):
        raise ValueError("Image input not detected — connect an IMAGE output to DetailerX.")
    downstream = descendants(prompt, target)
    keep = ancestors(prompt, downstream)
    result = {key: copy.deepcopy(prompt[key]) for key in keep}
    raw=json.loads(settings) if isinstance(settings,str) else settings
    owner=owner or (raw.get("_control",{}).get("owner") if isinstance(raw,dict) else None)
    effective = normalize(settings)
    effective["entry"]["pause"] = False
    effective["entry"]["skip"] = False
    # prepare_prompt uses this browser/workflow/node identity to create the
    # retained session. normalize intentionally strips runtime controls, so
    # restore only the validated owner needed for this queued execution.
    if owner:
        effective["_control"]={"owner":owner}
    result[target].setdefault("inputs", {})["settings"] = json.dumps(effective)
    return result


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
        total=sum(size_of((v.get('inputs'),v['boundary'],v.get('latest'))) for v in SESSIONS.values())
        for token,other in list(SESSIONS.items()):
            if total+additional<=LIMIT:
                break
            if other is s or other['state'] in ('paused','processing','queued') or other.get('prompt_id') in active:
                continue
            total-=size_of((other.get('inputs'),other['boundary'],other.get('latest')))
            del SESSIONS[token]
        if total+additional>LIMIT:
            raise ValueError('DetailerX retained inputs exceed the shared 2 GiB limit. Reduce the batch or finish other paused jobs.')
        target[key]=snapshot(value)


def prune():
    active = ACTIVE_PROMPTS()
    for s in SESSIONS.values():
        if s["state"] in ("queued", "waiting") and s.get("prompt_id") not in active and time.monotonic()-s["created"]>10:
            s["state"],s["error"]="failed","Queued job was removed or rejected; queue again."
    total = sum(size_of((s.get("inputs"), s["boundary"], s.get("latest"))) for s in SESSIONS.values())
    for token, s in list(SESSIONS.items()):
        if s["state"] in ("paused", "processing", "queued") or s.get("prompt_id") in active:
            continue
        if total <= LIMIT and len(SESSIONS) <= 32:
            continue
        total -= size_of((s.get("inputs"), s["boundary"], s.get("latest")))
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
                 created=time.monotonic(), entered=None, prompt_id=None, inputs=None, latest=None,
                 queue_mode=None, error="", revision=0)
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
    available=not busy and s["state"] in ("completed", "passed", "failed")
    latest=s.get("latest") or {}
    return dict(token=s["token"], owner=s["owner"], node=s["node"], state=s["state"], remaining=remaining,
                skip=s["settings"]["entry"]["skip"],
                queue_mode=s.get("queue_mode"),
                revision=s["revision"], error=s["error"], can_rerun=bool(s["inputs"]) and available,
                can_refine_original=bool(s["inputs"]) and available,
                can_refine_output=bool(latest.get("final") is not None) and available,
                mask_stages=sorted(latest.get("masks",{})),
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


def selective_graph(s, prompt, target, settings, job, stage, source, mask_mode):
    """Replay only one DetailerX processor while preserving downstream consumers."""
    result = replay_graph(s, prompt, target, settings, job)
    result[target] = dict(class_type=SELECTIVE, inputs=dict(
        token=s["token"], settings=json.dumps(normalize(settings)), job=job,
        stage=stage, source=source, mask_mode=mask_mode,
    ))
    return result


def compact_latest(result, previous=None, source="original"):
    """Retain the latest final image and mask tensors without duplicating stage images."""
    final, _processor_bundle, mask_bundle = result
    masks = {} if source == "original" else dict((previous or {}).get("masks", {}))
    for item in mask_bundle.get("stages", []):
        masks[str(item["id"])] = dict(
            masks=dict(item.get("masks",{})),
            backend=str(item.get("backend","")), detector=str(item.get("detector","")),
            classes=list(item.get("classes",[])), region_counts=list(item.get("region_counts",[])),
            processed_counts=list(item.get("processed_counts",[])), messages=list(item.get("messages",[])),
        )
    return dict(final=final, masks=masks)


def retain_result(s, result, source="original"):
    latest=compact_latest(result,s.get("latest"),source)
    retain(s,"latest",latest)


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
            from . import consume_realized_seed
            realized=consume_realized_seed(node)
            if realized is not None:
                actual=normalize(s["settings"]);actual["global_seed"]["realized_seed"]=realized
                effective_metadata(prompt,extra,node,actual)
            s["state"] = "completed"
        else:
            from .preview import make_bundle
            from .masks import make_mask_bundle
            image=inputs["image"].clone()
            reason="Skipped or cancelled before processing"
            result = (image,make_bundle(image,bypass_reason=reason),make_mask_bundle(bypass_reason=reason))
            s["state"] = "passed"
        retain_result(s,result,"original")
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
                if image_source_changed(s["prompt"], data["prompt"], str(data["target"])):
                    return web.json_response(dict(error="Connected upstream inputs changed; evaluating the current branch.", code="upstream_changed"), status=409)
                previous = s["state"]
                job = str(uuid.uuid4())
                graph = replay_graph(s, data["prompt"], str(data["target"]), data["settings"], job)
                s["state"] = "queued"
                s["queue_mode"] = "retained"
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

    @server.routes.post("/workflowx_configurator/detailer_x/selective_rerun")
    async def selective_rerun(request):
        """Queue one processor against the retained node input or latest output."""
        safe(request)
        s = None
        previous = None
        try:
            data = await request.json()
            source=str(data.get("source",""));mask_mode=str(data.get("mask_mode","remask"));stage=str(data.get("stage",""))
            if source not in ("original","output"):
                raise ValueError("Selective refinement source must be original or output")
            if mask_mode not in ("reuse","remask"):
                raise ValueError("Selective refinement mask mode must be reuse or remask")
            effective=normalize(data["settings"])
            if stage not in effective["order"]:
                raise ValueError(f"Processor is no longer available: {stage}")
            with LOCK:
                s = get_session(data["token"], data["owner"])
                availability=view(s)
                allowed=availability["can_refine_original"] if source=="original" else availability["can_refine_output"]
                if not allowed:
                    raise ValueError("Retained source unavailable or DetailerX is busy. Complete an ordinary run first.")
                previous = s["state"]
                job = str(uuid.uuid4())
                graph = selective_graph(s,data["prompt"],str(data["target"]),effective,job,stage,source,mask_mode)
                s["state"] = "queued"
                s["queue_mode"] = "selective"
                s["created"] = time.monotonic()
                s["error"] = ""
            import execution
            valid = await execution.validate_prompt(job, graph, None)
            if not valid[0]:
                raise ValueError(f"Selective refinement graph is not supported: {valid[1]}")
            extra = copy.deepcopy(data.get("extra_data", {}))
            extra["client_id"] = data.get("client_id")
            extra["detailer_x_effective"] = {str(data["target"]): effective}
            extra["detailer_x_selective"] = dict(stage=stage,source=source,mask_mode=mask_mode)
            with LOCK:
                s["prompt_id"] = job
                number = server.number
                server.number += 1
                server.prompt_queue.put((number, job, graph, extra, valid[2], {}))
            announce(s)
            return web.json_response(dict(prompt_id=job,stage=stage,source=source,mask_mode=mask_mode))
        except (ValueError, TypeError, KeyError) as exc:
            if s is not None and previous is not None:
                s["state"] = previous
            return web.json_response(dict(error=str(exc)), status=400)

    @server.routes.post("/workflowx_configurator/detailer_x/connected_selective_rerun")
    async def connected_selective_rerun(request):
        """Evaluate the current input branch, then run only one processor."""
        safe(request)
        s=None
        try:
            data=await request.json()
            target=str(data["target"]);stage=str(data.get("stage",""));owner=str(data.get("owner",""))
            if not 1 <= len(owner) <= 200:
                raise ValueError("Invalid owner")
            effective=normalize(data["settings"])
            if stage not in effective["order"]:
                raise ValueError(f"Processor is no longer available: {stage}")
            job=str(uuid.uuid4())
            graph=connected_graph(data["prompt"],target,effective,owner)
            payload=dict(prompt=graph,prompt_id=job)
            prepare_prompt(payload)
            graph=payload["prompt"]
            run_settings=json.loads(graph[target]["inputs"]["settings"])
            graph[target]["class_type"]=CONNECTED_SELECTIVE
            graph[target]["inputs"]["stage"]=stage
            with LOCK:
                s=get_session(run_settings["_run"],owner)
                s["state"]="queued"
                s["queue_mode"]="connected_selective"
            import execution
            valid=await execution.validate_prompt(job,graph,None)
            if not valid[0]:
                raise ValueError(f"Connected selective refinement is not supported: {valid[1]}")
            extra=copy.deepcopy(data.get("extra_data",{}))
            extra["client_id"]=data.get("client_id")
            extra["detailer_x_effective"]={target:effective}
            extra["detailer_x_selective"]=dict(stage=stage,source="original",mask_mode="remask",connected=True)
            number=server.number;server.number+=1
            server.prompt_queue.put((number,job,graph,extra,valid[2],{}))
            announce(s)
            LOG.info("[DetailerX #%s] queued connected selective refinement · %s — %d nodes",target,stage,len(graph))
            return web.json_response({**view(s),"prompt_id":job,"stage":stage,"source":"original","mask_mode":"remask"})
        except (ValueError,TypeError,KeyError) as exc:
            if s is not None:
                s["state"],s["error"]="failed",str(exc)
                announce(s)
            return web.json_response(dict(error=str(exc)),status=400)

    @server.routes.post("/workflowx_configurator/detailer_x/connected_rerun")
    async def connected_rerun(request):
        """Queue the target branch from current connections, excluding unrelated outputs."""
        safe(request)
        s=None
        try:
            data = await request.json()
            target = str(data["target"])
            owner=str(data.get("owner", ""))
            if not 1 <= len(owner) <= 200:
                raise ValueError("Invalid owner")
            job = str(uuid.uuid4())
            graph = connected_graph(data["prompt"], target, data["settings"], owner)
            payload = dict(prompt=graph, prompt_id=job)
            prepare_prompt(payload)
            graph = payload["prompt"]
            run_settings=json.loads(graph[target]["inputs"]["settings"])
            with LOCK:
                s=get_session(run_settings["_run"],owner)
                s["state"]="queued"
                s["queue_mode"]="connected"
            import execution
            valid = await execution.validate_prompt(job, graph, None)
            if not valid[0]:
                raise ValueError(f"Connected DetailerX branch is not supported: {valid[1]}")
            extra = copy.deepcopy(data.get("extra_data", {}))
            extra["client_id"] = data.get("client_id")
            effective = normalize(data["settings"])
            effective["entry"]["pause"] = False
            effective["entry"]["skip"] = False
            extra["detailer_x_effective"] = {target: effective}
            number = server.number
            server.number += 1
            server.prompt_queue.put((number, job, graph, extra, valid[2], {}))
            announce(s)
            LOG.info("[DetailerX #%s] queued connected branch — %d nodes", target, len(graph))
            return web.json_response({**view(s),"prompt_id":job})
        except (ValueError, TypeError, KeyError) as exc:
            if s is not None:
                s["state"],s["error"]="failed",str(exc)
                announce(s)
            return web.json_response(dict(error=str(exc)), status=400)
