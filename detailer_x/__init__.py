"""DetailerX public node. Heavy dependencies are imported only during execution."""
import json
import logging
import secrets
import threading
import time
from .config import DEFAULTS, DETAILERS, LEGACY_REALISM, RANGES, CHOICES, normalize, effective_sam
from .advanced_config import ADVANCED
from . import assets
from . import presets
from .progress import stage_updates, message
from .cache import CACHE, digest, fingerprint, model_signature

log=logging.getLogger("WorkflowX.DetailerX")
NODE_ID="WorkflowX_DetailerX"
OUTPUTS=("final_image","processor_images","detailer_masks")
_REALIZED_SEEDS={}
_REALIZED_LOCK=threading.RLock()

class DetailerX:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required":{"model":("MODEL",{"tooltip":"Authoritative sampling model; connect matching CLIP and VAE. Presets do not load or replace it or its attention patches."}),"vae":("VAE",{"tooltip":"VAE matching the supplied model. RGB/RGBA decoded images are supported; input alpha is preserved."}),"clip":("CLIP",{"tooltip":"Text encoder matching the model; used for local detailer prompts."}),
            "positive":("CONDITIONING",{"tooltip":"Incoming positive conditioning. Per-detailer prompt mode controls replacement or concatenation."}),"negative":("CONDITIONING",{"tooltip":"Incoming negative conditioning; preserved by detailers, but inactive at CFG 1."}),"image":("IMAGE",{"tooltip":"RGB or RGBA image batch to process. final_image is completed; processor_images feeds DetailerX Preview; detailer_masks feeds DetailerX Masks."}),
            "settings":("STRING",{"default":json.dumps(DEFAULTS),"multiline":True})},
            "hidden":{"unique_id":"UNIQUE_ID", "prompt":"PROMPT", "extra_pnginfo":"EXTRA_PNGINFO"}}

    RETURN_TYPES=("IMAGE","DETAILERX_PROCESSOR_IMAGES","DETAILERX_MASKS")
    RETURN_NAMES=OUTPUTS
    FUNCTION="run"
    CATEGORY="WorkflowX/Image"
    DESCRIPTION="Ordered upscale, class-aware detailers, realism controls and DLSS5. Outputs the final image, named processor snapshots, and detailer mask diagnostics."

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
        if s["global_seed"]["enabled"] and s["global_seed"]["mode"]=="random": return float("nan")
        if any(stage_settings(s,k)["enabled"] and stage_settings(s,k).get("seed_mode")=="random" for k in s['order']):
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
        original=image.clone()
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
        global_seed=None
        if s["global_seed"]["enabled"]:
            global_seed=s["global_seed"]["seed"] if s["global_seed"]["mode"]=="fixed" else secrets.randbelow(2**53)
            if unique_id is not None:
                with _REALIZED_LOCK:_REALIZED_SEEDS[str(unique_id)]=global_seed
            status(unique_id,"seed","processing",0,0,f"Global {s['global_seed']['mode']} seed · {global_seed}")
        for k in s['order']:
            stage=stage_settings(s,k)
            if not stage.get('enabled'): continue
            if global_seed is not None and 'seed' in stage: stage['seed']=global_seed;stage['seed_mode']='fixed'
            elif stage.get("seed_mode")=="random": stage["seed"]=secrets.randbelow(2**53)
        details=all_detailers(s)
        needs_detail=any(stage_settings(s,k)["enabled"] and stage_settings(s,k)["denoise"]>0 for k in details)
        sampling=(model_signature(model,clip,vae),fingerprint(positive),fingerprint(negative)) if needs_detail else None
        previous=digest((fingerprint(image),s["cache_epoch"]))
        stages=s['order']
        processor_images=[]
        mask_items=[]
        for index,name in enumerate(stages):
            try:
                p.cancelled()
            except Exception:
                status(unique_id,name,"cancelled",index+1,len(stages))
                raise
            stage=stage_settings(s,name);enabled=stage["enabled"]
            if enabled:
                stage_input=image
                resolved_sam=effective_sam(s,stage) if name in details else None
                dependency=(sampling,resolved_sam,signatures.get(f"sam:{name}")) if name in details else None
                key=digest((previous,name,stage,signatures.get(name),dependency,"mask-debug-v1" if name in details else None))
                cached=CACHE.get(key)
                stage_started=time.monotonic()
                status(unique_id,name,"cached" if cached is not None else "processing",index+1,len(stages))
                if cached is not None:
                    if name in details and isinstance(cached,dict):image,mask_debug=cached["image"],cached["debug"]
                    else:
                        image=cached
                        if name in details:mask_debug=empty_mask_debug(stage_input,stage,resolved_sam,"Mask diagnostics unavailable from legacy cache")
                    reused+=1
                    stage_state="cached"
                else:
                    try:
                        with stage_updates(lambda detail:status(unique_id,name,"processing",index+1,len(stages),detail)), torch.inference_mode():
                            if name=="upscaler":
                                result=p.upscale(image,stage)
                            elif name in details:
                                detailed=p.detail(image,stage,resolved_sam,model,clip,vae,positive,negative,True)
                                if isinstance(detailed,tuple) and len(detailed)==2:result,mask_debug=detailed
                                else:result=detailed;mask_debug=empty_mask_debug(stage_input,stage,resolved_sam,"Mask diagnostics unavailable")
                                mask_debug=compact_mask_debug(mask_debug)
                            elif name in ADVANCED:
                                from .advanced_processing import process
                                result=process(image,name,stage)
                            elif name in LEGACY_REALISM:
                                result=p.realism(image,name,stage)
                            else:
                                result=p.dlss(image,stage)
                        image=result.detach().cpu()
                        CACHE.put(key,{"image":image,"debug":mask_debug} if name in details else image)
                        stage_state="processed"
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
                from .preview import stage_label
                processor_images.append(dict(id=name,name=stage_label(name,stage),state=stage_state,image=image))
                if name in details:
                    mask_items.append(dict(id=name,name=stage_label(name,stage),state=stage_state,input=stage_input,debug=mask_debug))
            else:
                status(unique_id,name,"bypassed",index+1,len(stages))
        final=image.clone()
        status(unique_id,"complete","complete",len(stages),len(stages),f"{time.monotonic()-started:.1f}s total · {reused} cached stage(s) reused")
        from .preview import make_bundle
        from .masks import make_mask_bundle
        return final,make_bundle(original,processor_images),make_mask_bundle(mask_items)

    def process_selective(self,inputs,settings,stage_name,source,mask_mode,latest,unique_id=None):
        """Run exactly one processor against the retained node input or latest output."""
        import torch
        from . import processing as p
        s=normalize(settings)
        details=all_detailers(s)
        if stage_name not in s["order"]:
            raise ValueError(f"Processor is no longer available: {stage_name}")
        if source not in ("original","output"):
            raise ValueError("Selective refinement source must be original or output")
        if source=="output" and not isinstance((latest or {}).get("final"),torch.Tensor):
            raise ValueError("Latest DetailerX output is unavailable. Complete an ordinary run first.")
        base=snapshot(inputs["image"] if source=="original" else latest["final"])
        stage=stage_settings(s,stage_name)
        stage["enabled"]=True
        global_seed=None
        if s["global_seed"]["enabled"]:
            global_seed=s["global_seed"]["seed"] if s["global_seed"]["mode"]=="fixed" else secrets.randbelow(2**53)
            if unique_id is not None:
                with _REALIZED_LOCK:_REALIZED_SEEDS[str(unique_id)]=global_seed
            status(unique_id,"seed","processing",0,0,f"Global {s['global_seed']['mode']} seed · {global_seed}")
        if global_seed is not None and "seed" in stage:
            stage["seed"]=global_seed;stage["seed_mode"]="fixed"
        elif stage.get("seed_mode")=="random":
            stage["seed"]=secrets.randbelow(2**53)

        reuse=None;fallback=False
        if stage_name in details and source=="output" and mask_mode=="reuse":
            reuse=(latest or {}).get("masks",{}).get(stage_name,{}).get("masks",{}).get("blend")
            fallback=reuse is None
        isolated=normalize(s)
        for name in isolated["order"]:stage_settings(isolated,name)["enabled"]=name==stage_name
        if not (stage_name in details and reuse is not None):
            asset_signatures(isolated)
        action=("original input" if source=="original" else
                ("latest output · reused mask" if reuse is not None else "latest output · remasked")
                if stage_name in details else "latest output")
        if fallback:action+=" (previous mask unavailable)"
        status(unique_id,stage_name,"processing",1,1,f"Selective refinement · {action}")
        try:
            with stage_updates(lambda detail:status(unique_id,stage_name,"processing",1,1,detail)),torch.inference_mode():
                if stage_name=="upscaler":result=p.upscale(base,stage)
                elif stage_name in details:
                    shared=effective_sam(s,stage)
                    result,debug=p.detail(base,stage,shared,inputs["model"],inputs["clip"],inputs["vae"],inputs["positive"],inputs["negative"],True,reuse)
                    debug=compact_mask_debug(debug)
                elif stage_name in ADVANCED:
                    from .advanced_processing import process
                    result=process(base,stage_name,stage)
                elif stage_name in LEGACY_REALISM:result=p.realism(base,stage_name,stage)
                else:result=p.dlss(base,stage)
            result=result.detach().cpu()
        except Exception as exc:
            status(unique_id,stage_name,"failed",1,1,str(exc))
            raise RuntimeError(f"DetailerX {stage_name} selective refinement: {exc}") from exc
        from .preview import make_bundle,stage_label
        from .masks import make_mask_bundle
        label=stage_label(stage_name,stage)
        processor=make_bundle(base,[dict(id=stage_name,name=label,state=f"selective · {action}",image=result)])
        masks=make_mask_bundle([dict(id=stage_name,name=label,state=f"selective · {action}",input=base,debug=debug)]) if stage_name in details else make_mask_bundle()
        status(unique_id,"complete","complete",1,1,f"Selective refinement finished · {label} · {result.shape[2]}×{result.shape[1]}")
        return result.clone(),processor,masks

def empty_mask_debug(image,stage,shared,reason):
    import torch
    zero=torch.zeros(tuple(image.shape[:3]),dtype=torch.float32)
    return dict(detector=zero.clone(),refined=zero.clone(),blend=zero.clone(),
                region_counts=[0]*image.shape[0],processed_counts=[0]*image.shape[0],messages=[reason]*image.shape[0],
                backend=shared.get("backend","disabled") if shared.get("enabled") else "detector-only",
                detector_model=stage.get("detector",""),classes=list(stage.get("class_labels") or stage.get("class_ids") or []))

def compact_mask_debug(debug):
    import torch
    result=dict(debug)
    for key in ("detector","refined","blend"):
        value=result[key]
        if value.dtype!=torch.uint8:result[key]=(value.detach().cpu().clamp(0,1)*255).round().to(torch.uint8)
    return result

def all_detailers(s):
    return tuple(DETAILERS)+tuple(s.get('extra_detailers',{}))

def stage_settings(s,name):
    return s['extra_detailers'][name] if name.startswith('detailer:') else s[name]

def sam3_inventory():
    try:
        import folder_paths
        names=folder_paths.get_filename_list('checkpoints')
        return [{"id":f"checkpoint:{name}","label":f"ComfyUI checkpoint / {name}"} for name in names if 'sam3' in name.lower()]
    except Exception:
        return []

def consume_realized_seed(node):
    with _REALIZED_LOCK:return _REALIZED_SEEDS.pop(str(node),None)

def asset_signatures(s):
    signatures={}
    for stage, kind, identifier in [('lut','luts',s['lut']['lut']),('neural_grain','neural_grain','internal:neural_grain/grainnet.pt')]:
        if s[stage]['enabled']:
            try:
                signatures[stage]=assets.signature(assets.resolve(identifier,kind))
            except (FileNotFoundError,ValueError) as exc:
                raise ValueError(f'DetailerX {stage}: {exc}') from exc
    details=all_detailers(s)
    for stage in ("upscaler",*details):
        cfg=stage_settings(s,stage)
        if not cfg["enabled"] or (stage in details and cfg["denoise"]==0):
            continue
        shared=effective_sam(s,cfg) if stage in details else None
        text_only=stage in details and shared.get('enabled') and shared.get('backend')=='sam3.1' and cfg.get('sam3_mode')=='concept_only'
        bbox_controlled=stage in details and shared.get('enabled') and shared.get('backend')=='sam3.1' and cfg.get('sam3_mode')=='bbox_controlled'
        if bbox_controlled and not cfg.get('mask_concept','').strip():
            raise ValueError(f"DetailerX {stage}: BBox controlled SAM3 requires a non-empty mask concept")
        if text_only:
            if not cfg.get('mask_concept','').strip(): raise ValueError(f"DetailerX {stage}: fully text-guided SAM3 requires a mask concept")
        else:
            kind,key=("upscale_models","model") if stage=="upscaler" else ("ultralytics","detector")
            if stage in details and not cfg.get(key):
                raise ValueError(f"DetailerX {stage}: {shared.get('backend','SAM')} {cfg.get('sam3_mode','')} requires a detector; choose one or use fully text-guided SAM3")
            try:
                signatures[stage]=assets.signature(assets.resolve(cfg[key],kind))
            except (FileNotFoundError,ValueError) as exc:
                raise ValueError(f"DetailerX {stage}: {exc}") from exc
    for stage in details:
        cfg=stage_settings(s,stage)
        if not cfg['enabled'] or cfg['denoise']==0: continue
        shared=effective_sam(s,cfg)
        if not shared.get('enabled'): continue
        if shared.get('backend')=='sam3.1':
            import folder_paths
            name=shared['model'].split(':',1)[-1];path=folder_paths.get_full_path('checkpoints',name)
            if not path: raise ValueError(f'DetailerX {stage}: SAM3 checkpoint missing: {name}')
            from pathlib import Path
            signatures[f'sam:{stage}']=assets.signature(Path(path))
        else:
            try: signatures[f'sam:{stage}']=assets.signature(assets.resolve(shared['model'],'sams'))
            except (FileNotFoundError,ValueError) as exc: raise ValueError(f'DetailerX {stage}: {exc}') from exc
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
        from .catalog import build_catalog
        return web.json_response(dict(defaults=DEFAULTS,ranges=RANGES,choices=CHOICES,entry_controls=True,
            presets=profiles,builtins=list(BUILTINS.values()),preset_fields=presets.FIELDS,preset_error=error,
            samplers=comfy.samplers.KSampler.SAMPLERS,schedulers=[*comfy.samplers.KSampler.SCHEDULERS,"flux2","krea2"],
            assets={k:assets.inventory(k) for k in assets.KINDS},detector_catalog=build_catalog(),
            sam3_checkpoints=sam3_inventory()))

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

    @server.routes.get("/workflowx_configurator/detailer_x/detector_info")
    async def detector_info(request):
        try:
            from .catalog import model_metadata
            return web.json_response(model_metadata(request.query.get('id',''),inspect=True))
        except (ValueError,FileNotFoundError,OSError,RuntimeError) as exc:
            return web.json_response({"error":str(exc)},status=400)

from .entry import Capture, Snapshot, get_session, snapshot, announce, LOCK, effective_metadata, retain, retain_result
from .preview import DetailerXPreview
from .masks import DetailerXMasks

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
            # Rerun is an explicit request to process retained inputs. Keep the
            # saved Skip toggle intact, but never turn this replay into another
            # pass-through execution.
            effective["entry"]["skip"]=False
            effective_metadata(prompt,extra_pnginfo,unique_id,effective)
            result=DetailerX().process(**snapshot(s["inputs"]),settings=effective,unique_id=unique_id)
            retain_result(s,result,"original")
            realized=consume_realized_seed(unique_id)
            if realized is not None:
                actual=normalize(effective);actual['global_seed']['realized_seed']=realized
                effective_metadata(prompt,extra_pnginfo,unique_id,actual)
            s["state"]="completed"
            return result
        except BaseException as exc:
            s["state"],s["error"]="failed",str(exc)
            raise
        finally:
            announce(s)


class DetailerXSelective:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required":{"token":("STRING",),"settings":("STRING",),"job":("STRING",),
                            "stage":("STRING",),"source":(["original","output"],),"mask_mode":(["reuse","remask"],)},
                "hidden":{"unique_id":"UNIQUE_ID","prompt":"PROMPT","extra_pnginfo":"EXTRA_PNGINFO"}}
    RETURN_TYPES=DetailerX.RETURN_TYPES
    RETURN_NAMES=DetailerX.RETURN_NAMES
    FUNCTION="run"
    CATEGORY="WorkflowX/Internal"
    OUTPUT_NODE=True
    def run(self,token,settings,job,stage,source,mask_mode,unique_id=None,prompt=None,extra_pnginfo=None):
        s=get_session(token)
        if s["prompt_id"]!=job or s["state"]!="queued":
            raise ValueError("Selective refinement session is stale; choose the processor play action again.")
        try:
            s["state"]="processing";announce(s)
            effective=normalize(settings);effective["entry"]["pause"]=False;effective["entry"]["skip"]=False
            effective_metadata(prompt,extra_pnginfo,unique_id,effective)
            result=DetailerX().process_selective(snapshot(s["inputs"]),effective,stage,source,mask_mode,snapshot(s.get("latest")),unique_id)
            retain_result(s,result,source)
            realized=consume_realized_seed(unique_id)
            if realized is not None:
                actual=normalize(effective);actual["global_seed"]["realized_seed"]=realized
                effective_metadata(prompt,extra_pnginfo,unique_id,actual)
            s["state"]="completed"
            return result
        except BaseException as exc:
            s["state"],s["error"]="failed",str(exc)
            raise
        finally:
            announce(s)


class DetailerXConnectedSelective:
    """Normal connected inputs, but exactly one selected processor."""
    @classmethod
    def INPUT_TYPES(cls):
        base=DetailerX.INPUT_TYPES()["required"]
        return {"required":{**base,"stage":("STRING",)},
                "hidden":{"unique_id":"UNIQUE_ID","prompt":"PROMPT","extra_pnginfo":"EXTRA_PNGINFO"}}
    RETURN_TYPES=DetailerX.RETURN_TYPES
    RETURN_NAMES=DetailerX.RETURN_NAMES
    FUNCTION="run"
    CATEGORY="WorkflowX/Internal"
    OUTPUT_NODE=True
    def run(self,model,vae,clip,positive,negative,image,settings,stage,unique_id=None,prompt=None,extra_pnginfo=None):
        raw=json.loads(settings) if isinstance(settings,str) else settings
        token=raw.get("_run") if isinstance(raw,dict) else None
        s=get_session(token)
        inputs=dict(model=model,vae=vae,clip=clip,positive=positive,negative=negative,image=image)
        try:
            retain(s,"inputs",inputs)
            s["state"]="processing";announce(s)
            effective=normalize(settings);effective["entry"]["pause"]=False;effective["entry"]["skip"]=False
            effective_metadata(prompt,extra_pnginfo,unique_id,effective)
            result=DetailerX().process_selective(inputs,effective,stage,"original","remask",None,unique_id)
            retain_result(s,result,"original")
            realized=consume_realized_seed(unique_id)
            if realized is not None:
                actual=normalize(effective);actual["global_seed"]["realized_seed"]=realized
                effective_metadata(prompt,extra_pnginfo,unique_id,actual)
            s["state"]="completed"
            return result
        except BaseException as exc:
            s["state"],s["error"]="failed",str(exc)
            raise
        finally:
            announce(s)

NODE_CLASS_MAPPINGS={NODE_ID:DetailerX,"WorkflowX_DetailerXCapture":Capture,
                     "WorkflowX_DetailerXSnapshot":Snapshot,"WorkflowX_DetailerXReplay":DetailerXReplay,
                     "WorkflowX_DetailerXSelective":DetailerXSelective,
                     "WorkflowX_DetailerXConnectedSelective":DetailerXConnectedSelective,
                     "WorkflowX_DetailerXPreview":DetailerXPreview,"WorkflowX_DetailerXMasks":DetailerXMasks}
NODE_DISPLAY_NAME_MAPPINGS={NODE_ID:"DetailerX","WorkflowX_DetailerXPreview":"DetailerX Preview","WorkflowX_DetailerXMasks":"DetailerX Masks"}
