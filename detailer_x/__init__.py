"""DetailerX public node. Heavy dependencies are imported only during execution."""
import json
import logging
import secrets
import time
from .config import DEFAULTS, DETAILERS, REALISM, LEGACY_REALISM, RANGES, CHOICES, normalize
from .advanced_config import ADVANCED
from . import assets
from . import presets
from .progress import stage_updates, message
from .cache import CACHE, digest, fingerprint, model_signature

log=logging.getLogger("WorkflowX.DetailerX")
NODE_ID="WorkflowX_DetailerX"
OUTPUTS=("upscaler_image","face_detailer_image","breast_detailer_image","pussy_detailer_image",
         "hand_detailer_image","foot_detailer_image","realism_detailer_image","dlss5_image","final_image")

class DetailerX:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required":{"model":("MODEL",{"tooltip":"Authoritative sampling model; connect matching CLIP and VAE. Presets do not load or replace it or its attention patches."}),"vae":("VAE",{"tooltip":"VAE matching the supplied model. RGB/RGBA decoded images are supported; input alpha is preserved."}),"clip":("CLIP",{"tooltip":"Text encoder matching the model; used for local detailer prompts."}),
            "positive":("CONDITIONING",{"tooltip":"Incoming positive conditioning. Per-detailer prompt mode controls replacement or concatenation."}),"negative":("CONDITIONING",{"tooltip":"Incoming negative conditioning; preserved by detailers, but inactive at CFG 1."}),"image":("IMAGE",{"tooltip":"RGB or RGBA image batch to process. Outputs are cumulative stage results."}),
            "settings":("STRING",{"default":json.dumps(DEFAULTS),"multiline":True})},
            "hidden":{"unique_id":"UNIQUE_ID", "prompt":"PROMPT", "extra_pnginfo":"EXTRA_PNGINFO"}}

    RETURN_TYPES=("IMAGE",)*9
    RETURN_NAMES=OUTPUTS
    FUNCTION="run"
    CATEGORY="WorkflowX/Image"
    DESCRIPTION="Cumulative upscale, five SAM detailers, realism controls and DLSS5 with reusable intermediate results. Shared SAM settings are in the face detailer gear."

    @classmethod
    def VALIDATE_INPUTS(cls,settings,**kwargs):
        try:
            normalize(settings)
            return True
        except (ValueError,TypeError) as exc:
            return str(exc)

    @classmethod
    def IS_CHANGED(cls,settings,**kwargs):
        # Check asset mtimes on every queue and allow intentional random seeds.
        raw=json.loads(settings) if isinstance(settings,str) else settings
        if raw.get("_run"):
            return raw["_run"]  # Entry must be reachable even with missing stage assets.
        s=normalize(settings)
        if s["entry"]["pause"] or s["entry"]["skip"]:
            return float("nan")
        if any(s[k]["enabled"] and s[k].get("seed_mode")=="random" for k in s['order']):
            return float("nan")
        return digest(asset_signatures(s))

    async def run(self,model,vae,clip,positive,negative,image,settings,unique_id=None,prompt=None,extra_pnginfo=None):
        from .entry import execute_entry
        return await execute_entry(self.process, dict(model=model,vae=vae,clip=clip,positive=positive,negative=negative,image=image),
                                   settings,unique_id,prompt,extra_pnginfo)

    def process(self,model,vae,clip,positive,negative,image,settings,unique_id=None):
        import torch
        from . import processing as p
        s=normalize(settings)
        if not isinstance(image,torch.Tensor) or image.ndim!=4 or image.shape[-1] not in (3,4) or min(image.shape[:3])<1:
            raise ValueError("DetailerX expects a nonempty BHWC RGB or RGBA IMAGE batch")
        image=image.detach().cpu()
        started=time.monotonic()
        reused=0
        status(unique_id,"prepare","processing",0,0,"Checking assets and input fingerprints")
        warning=presets.mismatch(model,s["preset"]["family"])
        if warning:
            log.warning(warning)
            status(unique_id,"preset",warning,0,1)
        try:
            signatures=asset_signatures(s)
        except Exception as exc:
            status(unique_id,"prepare","failed",0,0,str(exc))
            raise
        for k in s['order']:
            if s[k]['enabled'] and s[k].get("seed_mode")=="random":
                s[k]["seed"]=secrets.randbelow(2**53)
        needs_detail=any(s[k]["enabled"] and s[k]["denoise"]>0 for k in DETAILERS)
        sampling=(model_signature(model,clip,vae),fingerprint(positive),fingerprint(negative)) if needs_detail else None
        previous=digest((fingerprint(image),s["cache_epoch"]))
        stages=s['order']
        outputs={}
        realism_output=next((n for n in reversed(stages) if n in REALISM and s[n]['enabled']),next(n for n in reversed(stages) if n in REALISM))
        for index,name in enumerate(stages):
            try:
                p.cancelled()
            except Exception:
                status(unique_id,name,"cancelled",index+1,len(stages))
                raise
            enabled=s[name]["enabled"]
            if enabled:
                dependency=(sampling,s["sam"],signatures.get("sam")) if name in DETAILERS else None
                key=digest((previous,name,s[name],signatures.get(name),dependency))
                cached=CACHE.get(key)
                stage_started=time.monotonic()
                status(unique_id,name,"cached" if cached is not None else "processing",index+1,len(stages))
                if cached is not None:
                    image=cached
                    reused+=1
                else:
                    try:
                        with stage_updates(lambda detail:status(unique_id,name,"processing",index+1,len(stages),detail)), torch.inference_mode():
                            if name=="upscaler":
                                result=p.upscale(image,s[name])
                            elif name in DETAILERS:
                                result=p.detail(image,s[name],s["sam"],model,clip,vae,positive,negative)
                            elif name in ADVANCED:
                                from .advanced_processing import process
                                result=process(image,name,s[name])
                            elif name in LEGACY_REALISM:
                                result=p.realism(image,name,s[name])
                            else:
                                result=p.dlss(image,s[name])
                        image=result.detach().cpu()
                        CACHE.put(key,image)
                        status(unique_id,name,"done",index+1,len(stages),f"{time.monotonic()-stage_started:.1f}s · {image.shape[2]}×{image.shape[1]} · {image.shape[0]} image(s)")
                    except Exception as exc:
                        try:
                            p.cancelled()
                        except Exception:
                            status(unique_id,name,"cancelled",index+1,len(stages))
                            raise
                        status(unique_id,name,"failed",index+1,len(stages),str(exc))
                        raise RuntimeError(f"DetailerX {name}: {exc}") from exc
                previous=key
            else:
                status(unique_id,name,"bypassed",index+1,len(stages))
            if name in ("upscaler",*DETAILERS,"dlss5"):
                # Downstream processors must never modify published images in place.
                outputs[name]=image.clone()
            if name==realism_output: outputs['realism']=image.clone()
        outputs['final']=image.clone()
        status(unique_id,"complete","complete",len(stages),len(stages),f"{time.monotonic()-started:.1f}s total · {reused} cached stage(s) reused")
        return tuple(outputs[n] for n in ('upscaler',*DETAILERS,'realism','dlss5','final'))

def asset_signatures(s):
    signatures={}
    for stage, kind, identifier in [('lut','luts',s['lut']['lut']),('neural_grain','neural_grain','internal:neural_grain/grainnet.pt')]:
        if s[stage]['enabled']:
            try:
                signatures[stage]=assets.signature(assets.resolve(identifier,kind))
            except (FileNotFoundError,ValueError) as exc:
                raise ValueError(f'DetailerX {stage}: {exc}') from exc
    for stage in ("upscaler",*DETAILERS):
        if not s[stage]["enabled"] or (stage in DETAILERS and s[stage]["denoise"]==0):
            continue
        kind,key=("upscale_models","model") if stage=="upscaler" else ("ultralytics","detector")
        try:
            signatures[stage]=assets.signature(assets.resolve(s[stage][key],kind))
        except (FileNotFoundError,ValueError) as exc:
            raise ValueError(f"DetailerX {stage}: {exc}") from exc
    if s["sam"]["enabled"] and any(s[k]["enabled"] and s[k]["denoise"]>0 for k in DETAILERS):
        signatures["sam"]=assets.signature(assets.resolve(s["sam"]["model"],"sams"))
    if s["dlss5"]["enabled"]:
        runtime=list((assets.ASSETS/"dlss5").rglob("*.dll"))
        native=assets.ROOT/"vendor/dlss/native/bin"
        runtime.extend(p for p in native.rglob("*") if p.suffix.lower() in (".dll",".exe"))
        signatures["dlss5"]=[assets.signature(p) for p in sorted(runtime)]
    return signatures

def status(node,stage,state,current,total,detail=""):
    text=message(stage,state,current,total,detail)
    writer=log.error if state=="failed" else log.info
    writer("[DetailerX #%s] %s",node,text)
    from comfy.utils import ProgressBar
    if total and stage!="preset" and (state!="processing" or not detail):
        completed=current-1 if state in ("processing","failed","cancelled") else current
        ProgressBar(total).update_absolute(max(0,completed),total)
    try:
        from server import PromptServer
        if PromptServer.instance is not None:
            PromptServer.instance.send_sync("workflowx.detailer_x.progress",dict(node=str(node),stage=stage,state=state,message=text,current=current,total=total))
    except (ImportError,AttributeError):
        pass

def register_routes():
    from aiohttp import web
    from server import PromptServer
    server=PromptServer.instance
    if server is None or getattr(server,"_workflowx_detailer_routes",False):
        return
    server._workflowx_detailer_routes=True
    from .entry import register
    register(server)

    @server.routes.get("/workflowx_configurator/detailer_x/config")
    async def config(request):
        import comfy.samplers
        from .config import BUILTINS
        try:
            profiles=list(presets.library().values())
            error=None
        except (ValueError,OSError) as exc:
            profiles=list(BUILTINS.values())
            error=str(exc)
        return web.json_response(dict(defaults=DEFAULTS,ranges=RANGES,choices=CHOICES,entry_controls=True,
            presets=profiles,builtins=list(BUILTINS.values()),preset_fields=presets.FIELDS,preset_error=error,
            samplers=comfy.samplers.KSampler.SAMPLERS,schedulers=[*comfy.samplers.KSampler.SCHEDULERS,"flux2","krea2"],
            assets={k:assets.inventory(k) for k in assets.KINDS}))

    @server.routes.post("/workflowx_configurator/detailer_x/presets")
    async def save_preset(request):
        from urllib.parse import urlsplit
        origin=request.headers.get("Origin")
        if request.headers.get("Sec-Fetch-Site")=="cross-site" or (origin and urlsplit(origin).netloc != request.host):
            raise web.HTTPForbidden(text="Cross-origin preset writes are not allowed")
        try:
            data=await request.read()
            if len(data)>262144:
                raise ValueError("Preset request is too large")
            payload=json.loads(data)
            if not isinstance(payload,dict):
                raise ValueError("Expected a preset object")
            item=presets.save(payload.get("preset"),payload.get("expected_revision"))
            return web.json_response(item)
        except (ValueError,TypeError,OSError) as exc:
            return web.json_response({"error":str(exc)},status=400)

from .entry import Capture, Snapshot, get_session, snapshot, announce, LOCK, effective_metadata

class DetailerXReplay:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required":{"token":("STRING",),"settings":("STRING",),"job":("STRING",)},
                "hidden":{"unique_id":"UNIQUE_ID","prompt":"PROMPT","extra_pnginfo":"EXTRA_PNGINFO"}}
    RETURN_TYPES=DetailerX.RETURN_TYPES
    RETURN_NAMES=DetailerX.RETURN_NAMES
    FUNCTION="run"
    CATEGORY="WorkflowX/Internal"
    OUTPUT_NODE=True
    def run(self,token,settings,job,unique_id=None,prompt=None,extra_pnginfo=None):
        s=get_session(token)
        if s["prompt_id"]!=job or s["state"]!="queued":
            raise ValueError("Rerun session is stale; queue from the DetailerX toolbar again.")
        try:
            s["state"]="processing"
            announce(s)
            effective=normalize(settings)
            effective_metadata(prompt,extra_pnginfo,unique_id,effective)
            if effective["entry"]["skip"]:
                result=tuple(s["inputs"]["image"].clone() for _ in range(9))
                s["state"]="passed"
            else:
                result=DetailerX().process(**snapshot(s["inputs"]),settings=effective,unique_id=unique_id)
                s["state"]="completed"
            return result
        except BaseException as exc:
            s["state"],s["error"]="failed",str(exc)
            raise
        finally:
            announce(s)

NODE_CLASS_MAPPINGS={NODE_ID:DetailerX,"WorkflowX_DetailerXCapture":Capture,
                     "WorkflowX_DetailerXSnapshot":Snapshot,"WorkflowX_DetailerXReplay":DetailerXReplay}
NODE_DISPLAY_NAME_MAPPINGS={NODE_ID:"DetailerX"}
