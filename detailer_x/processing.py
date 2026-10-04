"""Internal image processors. No imports from other ComfyUI custom-node packs.

Compatibility algorithms adapted from LayerStyle (MIT), WAS Suite (MIT),
Comfyroll and Impact Pack (GPL-3.0); see THIRD_PARTY.md and licenses/.
"""
import math
import time
import numpy as np
import torch
from PIL import Image, ImageEnhance
from .assets import resolve
from .progress import report, prefix

def pil(tensor):
    return Image.fromarray(np.clip(tensor.detach().cpu().numpy() * 255, 0, 255).astype(np.uint8))

def tensor(image):
    return torch.from_numpy(np.array(image).astype(np.float32) / 255)

def resize(images, width, height, method="lanczos"):
    return torch.stack([tensor(pil(i).resize((width, height), getattr(Image.Resampling, method.upper()))) for i in images])

def with_alpha(source, result):
    if source.shape[-1] == 4:
        alpha = torch.nn.functional.interpolate(source[..., 3:4].movedim(-1, 1), size=result.shape[1:3], mode="bilinear", align_corners=False).movedim(1, -1)
        result = torch.cat((result[..., :3], alpha.to(result)), -1)
    return result

def cancelled():
    import comfy.model_management as mm
    mm.throw_exception_if_processing_interrupted()

def upscale(image, settings):
    import comfy.utils
    import comfy.model_patcher
    import comfy.model_management as mm
    from spandrel import ModelLoader
    from comfy_extras.nodes_upscale_model import ImageUpscaleWithModel
    path = resolve(settings["model"], "upscale_models")
    report("Loading upscale model")
    state = comfy.utils.load_torch_file(str(path), safe_load=True)
    if "module.layers.0.residual_group.blocks.0.norm1.weight" in state:
        state = comfy.utils.state_dict_prefix_replace(state, {"module.": ""})
    model = ModelLoader().load_from_state_dict(state).eval()
    if hasattr(comfy.model_patcher, "CoreModelPatcher"):
        model.patcher = comfy.model_patcher.CoreModelPatcher(model.model, load_device=mm.get_torch_device(), offload_device=mm.unet_offload_device())
    try:
        report(f"Upscaling {image.shape[0]} image(s)")
        result = ImageUpscaleWithModel().upscale(model, image[..., :3])[0].cpu()
    finally:
        if hasattr(model,"patcher"):
            mm.unload_model_and_clones(model.patcher)
        model.to("cpu")
    h, w = image.shape[1:3]
    if result.shape[2] == w and settings["rescale_factor"] == 1:
        return with_alpha(image, result)
    if settings["mode"] == "rescale":
        width, height = max(1, int(w * settings["rescale_factor"])), max(1, int(h * settings["rescale_factor"]))
    else:
        m = settings["rounding_modulus"]
        width = math.ceil(settings["resize_width"] / m) * m
        height = math.ceil(int(settings["resize_width"] * h / w) / m) * m
    if settings["supersample"]:
        result = resize(result, width * 8, height * 8, settings["resampling_method"])
    return with_alpha(image, resize(result, width, height, settings["resampling_method"]))

def grain(image, s, seed):
    import cv2
    h, w = image.shape[:2]
    rng = torch.Generator(device="cpu").manual_seed(seed)
    t = torch.rand((max(1, int(h // s["grain_scale"])), max(1, int(w // s["grain_scale"])), 3), generator=rng)
    y = t.clone()
    y[..., 0] = .2123*t[..., 0] + .7152*t[..., 1] + .0722*t[..., 2]
    y[..., 1] = -.1146*t[..., 0] - .3854*t[..., 1] + .5*t[..., 2]
    y[..., 2] = .5*t[..., 0] - .4542*t[..., 1] - .0458*t[..., 2]
    for c, k in enumerate((3, 15, 11)):
        y[..., c] = torch.from_numpy(cv2.GaussianBlur(y[..., c].numpy(), (k, k), 0))
    t[..., 0] = y[..., 0] + 1.5748*y[..., 2]
    t[..., 1] = y[..., 0] - .1873*y[..., 1] - .4681*y[..., 2]
    t[..., 2] = y[..., 0] + 1.8556*y[..., 1]
    t = (t - .5) * s["grain_power"]
    t[..., 0] *= 2
    t[..., 2] *= 3
    t += 1
    t = t*s["grain_sat"] + t[..., 1:2]*(1-s["grain_sat"])
    t = torch.nn.functional.interpolate(t[None].movedim(-1, 1), size=(h, w), mode="bilinear").movedim(1, -1)[0]
    return pil((1 - (1-image)*t).clamp(0, 1))

def realism(image, name, s):
    results = []
    base_seed = int(time.time()) if s.get("seed_mode") == "time" else s.get("seed", 0)
    for index, frame in enumerate(image[..., :3]):
        cancelled()
        out = pil(frame)
        if name == "brightness":
            for key, cls in (("brightness", ImageEnhance.Brightness), ("contrast", ImageEnhance.Contrast), ("saturation", ImageEnhance.Color)):
                if s[key] != 1:
                    out = cls(out).enhance(s[key])
        elif name == "grain":
            out = grain(tensor(out), s, base_seed + index)
        elif name == "hsv":
            channels = list(out.convert("HSV").split())
            for c, key in enumerate(("H", "S", "V")):
                a = np.array(channels[c]).astype(np.int32) + s[key]
                channels[c] = Image.fromarray((a % 256 if c == 0 else a.clip(0, 255)).astype(np.uint8))
            out = Image.merge("HSV", channels).convert("RGB")
        elif name == "levels":
            a = np.array(out).astype(np.float64)
            ib, iw = sorted((s["black_point"], s["white_point"]))
            ob, ow = sorted((s["output_black_point"], s["output_white_point"]))
            if ib == iw or ob == ow:
                adjusted = np.full_like(a, 128)
            else:
                adjusted = np.clip(255*(a-ib)/(iw-ib), 0, 255)
                adjusted = 255 * (adjusted/255)**(1/s["gray_point"])
                adjusted = np.clip(adjusted/255*(ow-ob)+ob, 0, 255)
            if s["channel"] != "RGB":
                c = {"red": 0, "green": 1, "blue": 2}[s["channel"]]
                a[..., c] = adjusted[..., c]
            else:
                a = adjusted
            out = Image.fromarray(a.astype(np.uint8))
        elif name == "sharpen":
            from scipy.signal import convolve2d
            a = np.array(out).astype(np.float32)/255
            k = s["kernel_size"]
            a = np.pad(a, ((k, k), (k, k), (0, 0)), mode="edge")
            kernel = np.ones((k, k), np.float32)/(k*k)
            for c in range(3):
                for _ in range(s["iterations"]):
                    cancelled()
                    a[..., c] *= convolve2d(a[..., c]/(convolve2d(a[..., c], kernel, mode="same")+1e-6), kernel, mode="same")
            out = Image.fromarray((a[k:-k, k:-k].clip(0, 1)*255).astype(np.uint8))
        results.append(tensor(out))
    return with_alpha(image, torch.stack(results))

def dilate(mask, amount):
    import cv2
    if not amount:
        return mask
    kernel = np.ones((abs(amount), abs(amount)), np.uint8)
    return (cv2.dilate if amount > 0 else cv2.erode)(mask, kernel, iterations=1)

def blur(mask, radius):
    from torchvision.transforms.functional import gaussian_blur
    k = radius*2+1
    shortest = min(mask.shape[-2:])
    if shortest <= k:
        k = int(shortest/2)
        if k % 2 == 0:
            k += 1
    return gaussian_blur(mask[None], k, 10)[0] if radius > 0 and k >= 3 else mask

def crop_region(width, height, box, factor):
    def axis(limit, start, end):
        size = (end-start)*factor
        left = int((start+end-size)/2)
        left = max(0, min(left, limit-size))
        return int(left), int(min(limit, left+size))
    x1, x2 = axis(width, box[0], box[2])
    y1, y2 = axis(height, box[1], box[3])
    return x1, y1, x2, y2

def detections(image, settings):
    from ultralytics import YOLO
    model = YOLO(str(resolve(settings["detector"], "ultralytics")))
    try:
        prediction = model(pil(image), conf=settings["bbox_threshold"], device="cpu", verbose=False)[0]
        h, w = image.shape[:2]
        regions = []
        for idx, bbox in enumerate(prediction.boxes.xyxy.cpu().numpy()):
            x1, y1, x2, y2 = map(int, bbox)
            if x2-x1 <= settings["drop_size"] or y2-y1 <= settings["drop_size"]:
                continue
            mask = np.zeros((h, w), np.float32)
            if prediction.masks is not None:
                raw = prediction.masks.data[idx].cpu()[None, None].float()
                mask = torch.nn.functional.interpolate(raw, size=(h, w), mode="nearest")[0, 0].numpy()
            else:
                mask[max(0,y1):min(h,y2+1), max(0,x1):min(w,x2+1)] = 1
            mask = dilate(mask, settings["bbox_dilation"])
            regions.append((bbox, crop_region(w, h, bbox, settings["bbox_crop_factor"]), mask))
        return regions
    finally:
        model.to("cpu")

def sam_masks(image, regions, settings, shared):
    from segment_anything import sam_model_registry, SamPredictor
    import comfy.model_management as mm
    path = resolve(shared["model"], "sams")
    kind = "vit_h" if "vit_h" in path.name else "vit_l" if "vit_l" in path.name else "vit_b"
    model = sam_model_registry[kind](checkpoint=str(path))
    device = "cpu" if shared["device"] == "CPU" else mm.get_torch_device()
    try:
        model.to(device)
        predictor = SamPredictor(model)
        predictor.set_image(np.array(pil(image)))
        combined = np.zeros(tuple(image.shape[:2]), np.float32)
        h, w = combined.shape
        hint = settings["sam_detection_hint"]
        for bbox, crop, mask in regions:
            cancelled()
            e = settings["sam_bbox_expansion"]
            x1, y1, x2, y2 = max(0,bbox[0]-e), max(0,bbox[1]-e), min(w,bbox[2]+e), min(h,bbox[3]+e)
            cx, cy = (bbox[0]+bbox[2])/2, (bbox[1]+bbox[3])/2
            dx, dy = (x2-x1)/3, (y2-y1)/3
            choices = {"center-1": [(cx,cy)], "mask-point-bbox": [(cx,cy)],
                "horizontal-2": [(x1+dx,cy),(x1+2*dx,cy)], "vertical-2": [(cx,y1+dy),(cx,y1+2*dy)],
                "rect-4": [(x1+dx,cy),(x1+2*dx,cy),(cx,y1+dy),(cx,y1+2*dy)],
                "diamond-4": [(x1+dx,y1+dy),(x1+2*dx,y1+dy),(x1+dx,y1+2*dy),(x1+2*dx,y1+2*dy)]}
            points = choices.get(hint, [])
            labels = [1]*len(points)
            if hint == "mask-points":
                points = [((b[0]+b[2])/2,(b[1]+b[3])/2) for b, _, _ in regions]
                labels = [0 if settings["sam_mask_hint_use_negative"] == "Small" and b[2]-b[0] < 10 else 1 for b,_,_ in regions]
            elif hint == "mask-area":
                a,b,c,d = crop
                for py in range(b,d,max(3,(d-b)//20)):
                    for px in range(a,c,max(3,(c-a)//20)):
                        foreground = mask[py,px] > settings["sam_mask_hint_threshold"]
                        if foreground or settings["sam_mask_hint_use_negative"] == "Small":
                            points.append((px,py)); labels.append(int(foreground))
            if settings["sam_mask_hint_use_negative"] == "Outter":
                a,b,c,d = crop
                for py in range(10,h-10,max(1,h//20)):
                    for px in range(10,w-10,max(1,w//20)):
                        if not (a <= px <= c and b <= py <= d):
                            points.append((px,py)); labels.append(0)
            masks, scores, _ = predictor.predict(point_coords=np.asarray(points) if points else None,
                point_labels=np.asarray(labels) if labels else None,
                box=None if hint == "mask-points" else np.asarray([x1,y1,x2,y2]), multimask_output=True)
            selected = masks[scores >= settings["sam_threshold"]]
            if not len(selected):
                selected = masks[[int(np.argmax(scores))]]
            combined = np.maximum(combined, np.any(selected,axis=0).astype(np.float32))
            if hint == "mask-points":
                break
        return dilate(combined, settings["sam_dilation"])
    finally:
        model.to("cpu")

def decoded_rgb(decoded):
    """Normalize image channels, never latent channels or model-name heuristics."""
    if not isinstance(decoded, torch.Tensor) or decoded.ndim != 4 or decoded.shape[-1] not in (3, 4) or min(decoded.shape[:3]) < 1:
        raise ValueError("VAE must decode a nonempty BHWC RGB or RGBA image; check the connected VAE and model")
    return decoded[..., :3]


def guided_conditioning(positive, s):
    mode = s.get("guidance_mode", "incoming")
    if mode == "incoming":
        return positive
    value = s["guidance"] if mode == "set" else None
    return [[embedding, {**metadata, "guidance": value}] for embedding, metadata in positive]


def crop_sigmas(model, s, latent):
    import comfy.samplers
    steps = math.floor(s["steps"] / s["denoise"])
    discard = s["sampler_name"] in ("dpm_2", "dpm_2_ancestral", "uni_pc", "uni_pc_bh2")
    count = steps + int(discard)
    scheduler = s["scheduler"]
    if scheduler == "flux2":
        # Flux2's f16 VAE has one image token per encoded spatial position.
        from comfy_extras.nodes_flux import get_schedule
        total = get_schedule(count, math.prod(latent["samples"].shape[-2:]))
    elif scheduler == "krea2":
        # Krea uses f8 latents packed into 2x2 patches; no second model shift.
        tokens = math.prod(latent["samples"].shape[-2:]) / 4
        mu = 0.5 + (tokens - 256) * (1.15 - 0.5) / (6400 - 256)
        t = torch.linspace(1, 0, count + 1)
        exponent = math.exp(mu)
        total = exponent * t / (1 + (exponent - 1) * t)
    else:
        total = comfy.samplers.calculate_sigmas(model.get_model_object("model_sampling"), scheduler, count)
    if discard:
        total = torch.cat((total[:-2], total[-1:]))
    return total, total[steps-s["steps"]:]


def sample_crop(model, seed, s, positive, negative, latent):
    """Impact-compatible truncated schedule and final denoised prediction."""
    import comfy.sample
    import comfy.samplers
    import comfy.model_management as mm
    import comfy.utils
    import latent_preview
    sampler_name=s["sampler_name"]
    total,sigmas=crop_sigmas(model,s,latent)
    positive=guided_conditioning(positive,s)
    negative=guided_conditioning(negative,s)
    sampler=comfy.samplers.sampler_object(sampler_name)
    if sampler_name in ("dpmpp_sde","dpmpp_sde_gpu","dpmpp_2m_sde","dpmpp_2m_sde_gpu","dpmpp_2m_sde_heun","dpmpp_2m_sde_heun_gpu","dpmpp_3m_sde","dpmpp_3m_sde_gpu"):
        from comfy.k_diffusion import sampling
        function=sampler.sampler_function
        def wrapped(model_,x,sigmas_,**kwargs):
            kwargs.setdefault("noise_sampler",sampling.BrownianTreeNoiseSampler(x,total[total>0].min(),total.max(),seed=seed,cpu="gpu" not in sampler_name))
            return function(model_,x,sigmas_,**kwargs)
        sampler=comfy.samplers.KSAMPLER(wrapped,extra_options=dict(sampler.extra_options),inpaint_options=dict(sampler.inpaint_options))
    samples=comfy.sample.fix_empty_latent_channels(model,latent["samples"])
    noise=comfy.sample.prepare_noise(samples,seed,latent.get("batch_index"))
    x0={}
    preview_callback=latent_preview.prepare_callback(model,len(sigmas)-1,x0)
    def callback(step, denoised, x, total_steps):
        preview_callback(step,denoised,x,total_steps)
        # Five checkpoints per crop/cycle, not a terminal line for every step.
        if step==0 or (step+1)%max(1,total_steps//5)==0 or step+1==total_steps:
            report(f"Sampling step {step+1}/{total_steps}")
    device=mm.get_torch_device()
    mask=latent.get("noise_mask")
    result=comfy.sample.sample_custom(model,noise.to(device),s["cfg"],sampler,sigmas,positive,negative,samples.to(device),
        noise_mask=mask.to(device) if mask is not None else None,callback=callback,
        disable_pbar=not comfy.utils.PROGRESS_BAR_ENABLED,seed=seed)
    output=dict(latent)
    output["samples"]=model.model.process_latent_out(x0["x0"].cpu()) if "x0" in x0 else result.to(mm.intermediate_device())
    return output

def crop_conditioning(conditioning, height, width, crop):
    result=[]
    x1,y1,x2,y2=crop
    for embedding,metadata in conditioning:
        values=dict(metadata)
        if "mask" in values:
            mask=values["mask"]
            if mask.ndim==2:mask=mask[None]
            mask=torch.nn.functional.interpolate(mask[:,None],size=(height,width),mode="bilinear",align_corners=False)[:,0]
            values["mask"]=mask[:,y1:y2,x1:x2]
        result.append([embedding,values])
    return result

def detail(image, s, shared, model, clip, vae, positive, negative):
    import nodes
    import comfy.model_management as mm
    if s["denoise"] == 0:
        report("Denoise is zero — passing through input")
        return image
    if s["prompt"] and s["prompt_mode"] != "incoming":
        report("Encoding detail prompt")
        local = nodes.CLIPTextEncode().encode(clip, s["prompt"])[0]
        if s.get("guidance_mode", "incoming") == "incoming":
            guidance_values = {metadata.get("guidance") for _,metadata in positive if "guidance" in metadata}
            if len(guidance_values) == 1:
                value = next(iter(guidance_values))
                local = [[embedding, {**metadata, "guidance": value}] for embedding,metadata in local]
        positive = nodes.ConditioningConcat().concat(positive, local)[0] if s["prompt_mode"] == "concat" else local
    if s["noise_mask"] and s["noise_mask_feather"] and "denoise_mask_function" not in model.model_options:
        from comfy_extras.nodes_differential_diffusion import DifferentialDiffusion
        model = DifferentialDiffusion.execute(model)[0]
    outputs = []
    for batch_index, frame in enumerate(image[..., :3]):
        cancelled()
        prefix(f"Image {batch_index+1}/{image.shape[0]}")
        report("Detecting regions")
        regions = detections(frame, s)
        if not regions:
            report("No detections — passing through input")
            outputs.append(frame.clone()); continue
        report(f"Found {len(regions)} region(s) · " + ("Building SAM masks" if shared["enabled"] else "Using detector masks"))
        segmentation = sam_masks(frame, regions, s, shared) if shared["enabled"] else None
        output = frame.clone()
        for region_index, (bbox, (x1,y1,x2,y2), mask) in enumerate(regions):
            cancelled()
            prefix(f"Image {batch_index+1}/{image.shape[0]} · region {region_index+1}/{len(regions)}")
            mask = mask if segmentation is None else mask * segmentation
            mask = torch.from_numpy(mask[y1:y2,x1:x2].copy())
            if not torch.any(mask):
                report("Empty mask — skipped")
                continue
            bh, bw = bbox[3]-bbox[1], bbox[2]-bbox[0]
            if not s["force_inpaint"] and bh >= s["guide_size"] and bw >= s["guide_size"]:
                report("Region already meets guide size — skipped")
                continue
            crop = output[None,y1:y2,x1:x2].clone()
            h,w = crop.shape[1:3]
            scale = s["guide_size"]/min(bw,bh) if s["guide_size_for"] else s["guide_size"]/min(w,h)
            nw,nh = int(w*scale),int(h*scale)
            if max(nw,nh)>s["max_size"]:
                scale *= s["max_size"]/max(nw,nh)
                nw,nh = int(w*scale),int(h*scale)
            if scale <= 1 or min(nw,nh) == 0:
                if not s["force_inpaint"]:
                    continue
                nw,nh=w,h
            pixels = resize(crop,nw,nh)
            report(f"VAE encoding crop {nw}×{nh}" + (" (tiled)" if s["tiled_encode"] else ""))
            noise_mask = blur(mask,s["noise_mask_feather"])[None] if s["noise_mask"] else None
            pos=crop_conditioning(positive,*frame.shape[:2],(x1,y1,x2,y2))
            neg=crop_conditioning(negative,*frame.shape[:2],(x1,y1,x2,y2))
            if s["inpaint_model"] and noise_mask is not None:
                pos,neg,latent = nodes.InpaintModelConditioning().encode(pos,neg,pixels,vae,noise_mask,noise_mask=True)
            else:
                latent = (nodes.VAEEncodeTiled().encode(vae,pixels,512)[0] if s["tiled_encode"] else nodes.VAEEncode().encode(vae,pixels)[0])
                if noise_mask is not None:
                    latent["noise_mask"] = noise_mask
            for cycle in range(s["cycle"]):
                cancelled()
                prefix(f"Image {batch_index+1}/{image.shape[0]} · region {region_index+1}/{len(regions)} · pass {cycle+1}/{s['cycle']}")
                report(f"Sampling · {s['steps']} steps · CFG {s['cfg']:g} · denoise {s['denoise']:g}")
                latent = sample_crop(model,s["seed"]+batch_index+region_index+cycle,s,pos,neg,latent)
            report("VAE decoding" + (" (tiled)" if s["tiled_decode"] else ""))
            if s["tiled_decode"]:
                decoded=nodes.VAEDecodeTiled().decode(vae,latent,512)[0]
            else:
                try:
                    decoded=vae.decode(latent["samples"])
                except mm.OOM_EXCEPTION:
                    report("VAE memory limit — retrying tiled decode")
                    decoded=vae.decode_tiled(latent["samples"],tile_x=64,tile_y=64)
            rgb=decoded_rgb(decoded)
            if rgb.shape[0] != 1:
                raise ValueError("VAE decoded an unexpected batch size for a single detail crop")
            refined=resize(rgb.cpu(),w,h)[0]
            report("Blending refined region into image")
            blend=blur(mask,s["feather"])[...,None]
            output[y1:y2,x1:x2] = output[y1:y2,x1:x2]*(1-blend)+refined*blend
        outputs.append(output)
    return with_alpha(image,torch.stack(outputs))

def dlss(image, settings):
    report(f"Preparing DLSS5 runtime · {settings['upscaling_mode']} · {image.shape[0]} image(s)")
    from .vendor.dlss import nodes as engine
    from .assets import ASSETS
    if settings["style"].startswith("off"):
        return image
    params=engine._build_params(dict(settings,runtime_dir=str(ASSETS/"dlss5")))
    params,_=engine._resolve_auto_scale(params,image.shape[2],image.shape[1])
    backend=engine._pick_backend(settings["backend"])
    module=engine._load_backend(backend)
    try:
        report(f"Rendering with DLSS5 · {settings['upscaling_mode']} · {backend}")
        result=engine._run_frames(image[...,:3],params,backend)[0]
        cancelled()
        return with_alpha(image,result)
    finally:
        if hasattr(module,"shutdown"):
            module.shutdown()
