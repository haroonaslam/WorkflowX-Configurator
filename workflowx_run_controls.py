"""Per-prompt execution boundaries and image mailboxes for free-floating controls.

The canvas is never mutated by execution. Scheduler hooks are inert unless the
submitted prompt contains our private control node, and state is task-local.
"""
from __future__ import annotations

import asyncio
from contextvars import ContextVar
from functools import wraps
import json
from pathlib import Path
import time
import uuid

CONTROL = "WorkflowX_RunControls"
BRIDGE = "WorkflowX_ImageTransferLoader"
ADV_BRIDGE = "WorkflowX_ImageTransferLoaderAdv"
_job = ContextVar("workflowx_run_controls", default=None)


class RunControls:
    CATEGORY = "WorkflowX/internal"
    RETURN_TYPES = ()
    FUNCTION = "finish"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"config": ("STRING", {"default": "{}"})}}

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def finish(self, config):
        return ()


class ImageTransferLoader:
    CATEGORY = "WorkflowX/internal"
    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "load"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {name: ("STRING",) for name in ("transfer", "settings", "nonce")}}

    def load(self, transfer, settings, nonce):
        import nodes
        job = _job.get()
        if job is None or transfer not in job["copies"]:
            raise ValueError("Image TargetX has not received its source image")
        options = json.loads(settings)
        payload = job["copies"][transfer]
        image = f'{payload["subfolder"]}/{payload["name"]} [temp]'
        cls = nodes.NODE_CLASS_MAPPINGS[options["class_type"]]
        inputs = dict(options["inputs"], image=image)
        if options["class_type"] == "WorkflowX_LoadImageXAdv":
            state = json.loads(inputs.get("workflowx_state") or "{}")
            state["load_mode"] = "direct"
            inputs["workflowx_state"] = json.dumps(state)
        return getattr(cls(), cls.FUNCTION)(**inputs)


class ImageTransferLoaderAdv(ImageTransferLoader):
    RETURN_TYPES = ("IMAGE", "MASK", "MASK", "INT", "INT")


def copy_first_image(cache, source_kind):
    """Write a new, owned PNG slot; never overwrite a loader's existing file."""
    import folder_paths
    import numpy as np
    from PIL import Image
    from .load_image_x.runtime import resolve_annotated_image_path

    if cache is None:
        raise ValueError("Image SourceX produced no image")
    images = (cache.ui or {}).get("output", {}).get("images", [])
    if images:
        item = images[0]
        path = "/".join(filter(None, [item.get("subfolder"), item["filename"]]))
        _, source = resolve_annotated_image_path(f'{path} [{item.get("type", "output")}]')
        with Image.open(source) as opened:
            opened.seek(0)
            image = opened.copy()
    else:
        # Comfy's cache outputs are lists (one entry per mapped invocation).
        tensor = cache.outputs[0][0][0].detach().cpu().float().clamp(0, 1)
        array = (tensor.numpy() * 255).round().astype(np.uint8)
        if array.shape[-1] == 1:
            array = array[..., 0]
        image = Image.fromarray(array)
        if len(cache.outputs) > 1 and cache.outputs[1]:
            mask = cache.outputs[1][0][0].detach().cpu().float().clamp(0, 1)
            if tuple(mask.shape) == tuple(tensor.shape[:2]) and image.mode != "RGBA":
                image = image.convert("RGBA")
                image.putalpha(Image.fromarray(((1 - mask.numpy()) * 255).round().astype(np.uint8)))
    directory = Path(folder_paths.get_temp_directory()) / "workflowx_transfers" / uuid.uuid4().hex
    directory.mkdir(parents=True)
    image.save(directory / "image.png", format="PNG")
    return {"name": "image.png", "subfolder": f"workflowx_transfers/{directory.name}", "type": "temp"}


def _error(node_id, exc):
    return {"node_id": node_id, "exception_message": f"WorkflowX: {exc}",
            "exception_type": "WorkflowX.RunControlError", "traceback": [], "current_inputs": {}}


def install_execution_hooks():
    import execution
    from comfy_execution.graph import ExecutionList

    if getattr(execution.execute, "_workflowx_run_controls", False):
        return
    original_prompt = execution.PromptExecutor.execute_async
    original_stage = ExecutionList.stage_node_execution
    original_execute = execution.execute

    @wraps(original_prompt)
    async def execute_prompt(self, prompt, prompt_id, extra_data=None, execute_outputs=None):
        controls = [(key, value) for key, value in prompt.items() if value["class_type"] == CONTROL]
        job = None
        if controls:
            if len(controls) != 1:
                raise ValueError("A prompt can contain only one WorkflowX control record")
            key, control = controls[0]
            config = json.loads(control["inputs"]["config"])
            job = dict(config, control=key, copies={}, initialized=False, stopped=None)
        token = _job.set(job)
        try:
            return await original_prompt(self, prompt, prompt_id, extra_data or {}, execute_outputs or [])
        finally:
            _job.reset(token)

    @wraps(original_stage)
    async def stage(self):
        job = _job.get()
        if job and not job["initialized"]:
            job["initialized"] = True
            try:
                def order(source, target):
                    # Cached sources still have a copy operation to perform.
                    # Native add_strong_link deliberately skips cached nodes.
                    self.add_strong_link(source, None, target)
                    if source in self.pendingNodes and target not in self.blocking[source]:
                        self.blocking[source][target] = {None: True}
                        self.blockCount[target] += 1

                # Schedule sources even when their destinations have no API node
                # (muted/bypassed), or their results are already cached.
                for transfer in job.get("transfers", []):
                    source = transfer["source"]
                    self.add_node(source)
                for stop in job.get("stops", []):
                    self.add_node(stop)
                for transfer in job.get("transfers", []):
                    source = transfer["source"]
                    order(source, job["control"])
                    if transfer.get("same_run"):
                        order(source, transfer["target"])
                for stop in job.get("stops", []):
                    for transfer in job.get("transfers", []):
                        if transfer["source"] != stop:
                            order(transfer["source"], stop)
                    # A cached downstream output otherwise skips its cached
                    # ancestors completely, including the selected stop point.
                    def depends(node, ancestor, seen):
                        if node in seen:
                            return False
                        seen.add(node)
                        for value in self.dynprompt.get_node(node)["inputs"].values():
                            if isinstance(value, list) and len(value) == 2 and isinstance(value[1], int):
                                parent = str(value[0])
                                if parent == ancestor or depends(parent, ancestor, seen):
                                    return True
                        return False
                    for pending in list(self.pendingNodes):
                        if pending != stop and depends(pending, stop, set()):
                            order(stop, pending)
            except Exception as exc:
                return None, _error(job["control"], exc), exc
        return await original_stage(self)

    @wraps(original_execute)
    async def execute_node(server, dynprompt, caches, current_item, extra_data, executed,
                           prompt_id, execution_list, pending_subgraph_results,
                           pending_async_nodes, ui_outputs, asset_manager):
        result = await original_execute(server, dynprompt, caches, current_item, extra_data,
                                        executed, prompt_id, execution_list, pending_subgraph_results,
                                        pending_async_nodes, ui_outputs, asset_manager)
        job = _job.get()
        if not job or result[0] != execution.ExecutionResult.SUCCESS:
            return result
        try:
            for transfer in job.get("transfers", []):
                if transfer["source"] != current_item or transfer["id"] in job["copies"]:
                    continue
                cache = execution_list.get_cache(current_item, job["control"])
                if cache is None:
                    cache = await caches.outputs.get(current_item)
                payload = await asyncio.to_thread(copy_first_image, cache, transfer["source_type"])
                job["copies"][transfer["id"]] = payload
                record = dict(transfer, image=payload, workflow=job.get("workflow"), prompt_id=prompt_id,
                              completed_at=time.time_ns())
                job.setdefault("results", []).append(record)
                server.send_sync("workflowx_image_transfer", record, server.client_id)
            # History is durable even if StopX suppresses the private output node.
            ui_outputs[job["control"]] = {"meta": {}, "output": {
                "workflowx_transfers": job.get("results", []), "workflowx_stopped": job["stopped"]}}
            if current_item in job.get("stops", []):
                job["stopped"] = current_item
                tasks = [task for values in pending_async_nodes.values() for task in values
                         if isinstance(task, asyncio.Future)]
                for task in tasks:
                    task.cancel()
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                    # Let Comfy's completion callbacks release their external
                    # scheduler blocks before removing the pending nodes.
                    await asyncio.sleep(0)
                execution_list.inhibit_nodes(set(execution_list.pendingNodes) - {current_item})
                ui_outputs[job["control"]]["output"]["workflowx_stopped"] = current_item
                server.send_sync("workflowx_stopped", {"prompt_id": prompt_id, "node": current_item,
                                                       "workflow": job.get("workflow")}, server.client_id)
        except Exception as exc:
            return execution.ExecutionResult.FAILURE, _error(current_item, exc), exc
        return result

    execute_node._workflowx_run_controls = True
    execution.PromptExecutor.execute_async = execute_prompt
    execution.execute = execute_node
    ExecutionList.stage_node_execution = stage


NODE_CLASS_MAPPINGS = {CONTROL: RunControls, BRIDGE: ImageTransferLoader, ADV_BRIDGE: ImageTransferLoaderAdv}
