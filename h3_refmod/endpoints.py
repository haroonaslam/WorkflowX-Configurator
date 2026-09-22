"""Endpoint planning, prompt assembly and native H3 tokenization adapter."""
import copy
import re
from .compiler import PARTS, MENTION, compile_prompt
ROLES=('First frame','Last frame')

def split(refs):
    return [r for r in refs if r.get('endpoint')], [r for r in refs if not r.get('endpoint')]

def context(endpoints,width,height,length):
    from comfy_extras import nodes_minimax_h3 as native
    if width<32 or height<32 or width%32 or height%32: raise ValueError('Endpoint generation needs Width and Height to be positive multiples of 32.')
    count=native.temporal_shape(length)[0]
    for r in endpoints:
        r['estimated_tokens']=(width//32)*(height//32)
        r['frame_index']=0 if r['role']==ROLES[0] else count-1
        r['label']='opening-frame image' if r['role']==ROLES[0] else 'ending-frame image'
    endpoints.sort(key=lambda r:r['frame_index'])
    return count

def prompt_for(prompt,active,refs,endpoints,width,height,length):
    if not endpoints: return compile_prompt(prompt,active,refs)
    count=context(endpoints,width,height,length);mixed=bool(active or refs)
    aliases={r['tag']:r['label'] if mixed else f'<Picture {i+1}>' for i,r in enumerate(endpoints)}
    expansions={r['tag']: (str(r.get('descriptor','')).strip()+' from '+aliases[r['tag']] if str(r.get('descriptor','')).strip() else aliases[r['tag']]) for r in endpoints}
    pieces=[]
    for part in PARTS.split(prompt):
        pieces.append(part if part.startswith('<d>') else MENTION.sub(lambda m: expansions.get(m[1].lower(),m[0]) if m[1] else m[0],part))
    expanded=''.join(pieces)
    fields=re.findall(r'(?im)^(summary|detailed_description|integrated_multimodal_description|overall_soundscape|non_diegetic_music)\s*:',PARTS.sub(lambda m:' '*len(m[0]),expanded))
    fields=[f.lower() for f in fields]
    if 'detailed_description' in fields and 'integrated_multimodal_description' in fields: raise ValueError('Use either detailed_description or integrated_multimodal_description, not both.')
    if mixed:
        expanded=''.join(p if p.startswith('<d>') else re.sub(r'(?im)^integrated_multimodal_description\s*:', 'detailed_description:',p) for p in PARTS.split(expanded))
        expanded,report=compile_prompt(expanded,active,refs)
    else:
        if prompt.count('<d>')!=prompt.count('</d>'):raise ValueError('Every dialogue span needs a closing </d>.')
        for m in MENTION.finditer(''.join(p for p in PARTS.split(expanded) if not p.startswith('<d>'))):
            if m[1]:raise ValueError(f'Unknown @{m[1]}. Connect its character or reference.')
        expanded=''.join(p if p.startswith('<d>') else p.replace('@@','@') for p in PARTS.split(expanded))
        masked=PARTS.sub(lambda m:' '*len(m[0]),expanded)
        matches=list(re.finditer(r'(?im)^(summary|detailed_description|integrated_multimodal_description|overall_soundscape|non_diegetic_music)\s*:',masked))
        values={k:[] for k in ('integrated_multimodal_description','overall_soundscape','non_diegetic_music')}
        prefix=expanded[:matches[0].start()].strip() if matches else expanded.strip()
        if prefix:values['integrated_multimodal_description'].append(prefix)
        for i,m in enumerate(matches):
            key=m[1].lower() if m[1].lower() in values else 'integrated_multimodal_description'
            values[key].append(expanded[m.end():matches[i+1].start() if i+1<len(matches) else len(expanded)].strip())
        expanded='\n\n'.join(k+':\n'+'\n'.join(v) for k,v in values.items());report=''
    shots=re.findall(r'\[Shot\s+(\d+)\]',PARTS.sub(lambda m:' '*len(m[0]),prompt),re.I);last=shots[-1] if shots else '1'
    duration=f'{count/24:.2f}'
    lines=[]
    for r in endpoints:
        label=aliases[r['tag']];start=r['role']==ROLES[0]
        lines.append(f'{label} (from [Shot {"1" if start else last}]) aligns with the {"0.00" if start else duration}-second mark of the target video.')
    instruction='How the reference pictures align with the target video — '+' '.join(lines)
    if len(endpoints)==1 and endpoints[0]['role']==ROLES[0] and not mixed:instruction='For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.'
    if len(endpoints)==2 and not mixed: instruction=f'How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot {last}) aligns with the {duration}-second mark of the target video.'
    mode=('Hybrid: ' if mixed else '')+('first and last frames' if len(endpoints)==2 else endpoints[0]['role'].lower())
    report+='\nConditioning: '+mode
    for r in endpoints:report+=f'\n@{r["tag"]} -> {aliases[r["tag"]]} | frame {r["frame_index"]} | output {width} × {height} | Crop to fill | '+(f'{r["tokens"]} endpoint tokens' if 'tokens' in r else f'{r["estimated_tokens"]} estimated endpoint tokens; exact after encoding')
    for r in endpoints:
        if r.get('source_dimensions'): report+='\n@'+r['tag']+' source: '+' × '.join(map(str,r['source_dimensions']))
    return instruction+'\n\n'+expanded,report

def require_vae(vae):
    from comfy.ldm.minimax.vae import MiniMaxH3VideoVAE
    if vae is None or not isinstance(getattr(vae,'first_stage_model',None),MiniMaxH3VideoVAE):raise ValueError('First/last frames require the full H3 visual VAE.')

def encode(endpoints,vae,width,height):
    from comfy.ldm.minimax.vae import MiniMaxH3VideoVAE
    from .profiles import prepare
    from .optimization import visual_cost
    if vae is None or not isinstance(getattr(vae,'first_stage_model',None),MiniMaxH3VideoVAE):raise ValueError('First/last frames require the full H3 visual VAE.')
    for r in endpoints:
        image=r['data'];r['source_dimensions']=[image.shape[2],image.shape[1]]
        pixels=prepare(image,dict(size=0,framing='Crop to fill',smaller='Enlarge with Lanczos',downsize='Lanczos'),(width,height))
        z=vae.encode(pixels);r['pixels']=pixels;r['keyframe']=dict(resolved_frame_index=r['frame_index'],latent=z);r['tokens']=visual_cost(z.shape)

def tokenize(clip,prompt,refs,endpoints):
    items=[r['item'] for r in refs if r.get('item') is not None]
    if not refs:return clip.tokenize(prompt,images=[r['pixels'] for r in endpoints])
    # Local shallow adapter: native vision handling, explicit prefix labels. Never patch the loaded tokenizer.
    base=getattr(clip,'tokenizer',None)
    from comfy.text_encoders.minimax import MiniMaxH3Tokenizer
    if not isinstance(base,MiniMaxH3Tokenizer):raise ValueError('Hybrid endpoints require the native MiniMax H3 tokenizer.')
    mapping={};counts=dict(image=0,video=0,audio=0)
    for r in refs:
        if r.get('item') is None:continue
        kind=r['item']['type'];counts[kind]+=1;mapping[f'<{dict(image="Picture",video="Video",audio="Audio")[kind]} {counts[kind]}>: ']=r['label']+': '
    for r in endpoints:
        counts['image']+=1;mapping[f'<Picture {counts["image"]}>: ']=r['label']+': ';items.append(dict(type='image',data=r['pixels']))
    class Prefixes:
        def __getattr__(self,name):return getattr(base.qwen3vl_32b,name)
        def tokenize_with_weights(self,text,*a,**kw):return base.qwen3vl_32b.tokenize_with_weights(mapping.get(text,text),*a,**kw)
    adapter=copy.copy(base);adapter.qwen3vl_32b=Prefixes()
    return adapter.tokenize_with_weights(prompt,minimax_ref_items=items,tokenizer_options=getattr(clip,'tokenizer_options',{}))
