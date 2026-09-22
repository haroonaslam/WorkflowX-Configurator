from aiohttp import web
import server
from .characters import list_folder, load_character, save_details, safe_path, PREVIEWS
from .compiler import resolve, compile_prompt
from .characters import metadata

def register():
    routes=server.PromptServer.instance.routes
    def character_settings(values):
        return {k:v for k,v in values.items() if k in ('use_saved_voice','descriptor','retain','change','visual_references','reference_selection')}
    @routes.get('/h3refcharacters/upscale-models')
    async def upscale_models(request):
        import folder_paths
        return web.json_response({'models':folder_paths.get_filename_list('upscale_models')})
    @routes.get('/h3refcharacters/list')
    async def listing(request):
        try: return web.json_response(list_folder(request.query.get('path','')))
        except (ValueError,OSError) as e: return web.json_response({'error':str(e)},status=400)
    @routes.get('/h3refcharacters/character')
    async def character(request):
        try: return web.json_response(load_character(request.query.get('path','')))
        except (ValueError,OSError,KeyError) as e: return web.json_response({'error':str(e)},status=400)
    @routes.get('/h3refcharacters/preview')
    async def preview(request):
        try:
            p=safe_path(request.query.get('path',''))
            if p.suffix.lower() not in (*PREVIEWS,'.mp4'): raise ValueError('Preview must be an image.')
            return web.FileResponse(p)
        except (ValueError,OSError) as e: return web.json_response({'error':str(e)},status=400)
    @routes.post('/h3refcharacters/reference-selection')
    async def reference_selection(request):
        try:
            from .characters import configure_character
            from .representations import catalog
            body=await request.json();c=load_character(body['path'])
            entries=catalog(c)
            for e in entries:
                preview=e.get('preview') or (c.get('preview') if e['representation']=='combined' or c.get('external') else '')
                if preview:
                    from pathlib import Path
                    preview=str(safe_path(Path(c['manifest_path']).parent/preview,must_exist=False))
                e['preview']=preview
                if e.get('preview_video'): e['preview_video']=str(safe_path(__import__('pathlib').Path(c['manifest_path']).parent/e['preview_video']))
            if body.get('catalog_only'): return web.json_response(dict(character_id=c['character_id'],entries=entries,profiles=(c.get('profile_layout') or {}).get('profiles',{}),external=c.get('external',False)))
            selected=configure_character(c,**character_settings(body.get('settings',{})))
            return web.json_response(dict(character_id=c['character_id'],entries=entries,profiles=(c.get('profile_layout') or {}).get('profiles',{}),external=c.get('external',False),selected=selected['selected_references'],report=selected['selection_report'],combined=selected.get('runtime_combined'),tokens=selected['runtime_visual_tokens'],estimated=False,original_tokens=selected['original_visual_tokens']))
        except (ValueError,OSError,KeyError,TypeError) as e: return web.json_response({'error':str(e)},status=400)
    @routes.get('/h3refcharacters/media-files')
    async def media_files(request):
        import folder_paths
        from pathlib import Path
        root=Path(folder_paths.get_input_directory())
        kind=request.query.get('kind','image')
        extensions={'image':{'.png','.jpg','.jpeg','.webp','.bmp'},'audio':{'.wav','.mp3','.flac','.ogg','.m4a'},'video':{'.mp4','.webm','.mov','.mkv'}}
        return web.json_response({'files':[p.relative_to(root).as_posix() for p in sorted(root.rglob('*')) if p.is_file() and p.suffix.lower() in extensions.get(kind,set())]})
    @routes.get('/h3refcharacters/folder-sources')
    async def folder_sources(request):
        import asyncio
        from .source_catalog import describe_folder
        try: return web.json_response({'sources':await asyncio.to_thread(describe_folder,request.query.get('path',''))})
        except (ValueError,OSError) as e: return web.json_response({'error':str(e)},status=400)
    @routes.get('/h3refcharacters/source-preview')
    async def source_preview(request):
        import asyncio
        from .source_catalog import media_path
        try:
            p=await asyncio.to_thread(media_path,request.query.get('handle',''),request.query.get('thumbnail')=='1',int(request.query.get('frame','0')),request.query.get('playable')=='1')
            return web.FileResponse(p)
        except Exception as e: return web.json_response({'error':str(e)},status=400)
    @routes.post('/h3refcharacters/details')
    async def details(request):
        try:
            body=await request.json()
            c=load_character(body['path'])
            for key in ('display_name','alias','description','descriptor','voices','visuals'):
                if key in body: c[key]=body[key]
            from .generation import load_mod, audio_valid
            from .bundles import expand
            for path in expand(c['visuals']): load_mod(path)
            from .characters import voice_paths
            for voice in expand(voice_paths(c)):
                m=load_mod(voice)
                audio_valid(m.latent if m.kind=='audio' else m.audio_latent)
                if m.sample_rate!=32000: raise ValueError('Saved voice must use the H3 32 kHz audio VAE.')
            return web.json_response(save_details(c))
        except (ValueError,OSError,KeyError) as e: return web.json_response({'error':str(e)},status=400)
    @routes.post('/h3refcharacters/resolve')
    async def resolve_preview(request):
        try:
            body=await request.json()
            chars=[]
            for selection in body.get('characters',[]):
                if not selection.get('path'): continue
                from .characters import configure_character
                c=configure_character(load_character(selection['path']),**character_settings(selection.get('settings',{'use_saved_voice':selection.get('use_voice',True)})));chars.append(c)
            for ref in body.get('named_references',{}).values():
                if ref.get('role') in ('First frame','Last frame'):
                    try:
                        from .media import file_path
                        from PIL import Image
                        with Image.open(file_path(ref.get('source',''))) as image:
                            ref['source_dimensions']=list(image.size);ref['batch_count']=getattr(image,'n_frames',1)
                    except (ValueError,OSError): pass
            from .reference_plan import build_plan
            active,refs=build_plan('', {f'character_{i}':c for i,c in enumerate(chars)},
                named_references=body.get('named_references',{}),**{k:body.get(k,{}) for k in ('ref_images','ref_videos','ref_video_audios','ref_audios')})
            from . import endpoints as ep
            endpoints,refs=ep.split(refs)
            if endpoints and any(body.get(k,default) is None for k,default in [('width',512),('height',512),('length',121)]): raise ValueError('Endpoint timing and sizing preview require resolved output dimensions and length. Connected computed values will resolve during execution.')
            width,height,length=(int(body.get(k,default) if body.get(k,default) is not None else default) for k,default in [('width',512),('height',512),('length',121)])
            compile_prompt('',active,refs)
            error=None
            try:
                expanded,report=ep.prompt_for(body.get('prompt',''),active,refs,endpoints,width,height,length)
            except ValueError as e:
                error=str(e);expanded='';report=''
            labels={r['socket']: ['@'+r['tag']+' / '+r['role'].lower()] for r in endpoints}
            for r in refs:
                if 'socket' in r: labels.setdefault(r['socket'],[]).append(('@'+r['tag']+' / ' if r.get('tag') else '')+r['label'])
            labels={k:', '.join(v) for k,v in labels.items()}
            saved=sum(r.get('tokens',0) for r in refs if r['category']=='saved')
            from .representations import count_status
            reference_counts=count_status(refs)
            mode=body.get('budget_mode','Automatic')
            limit=int(body.get('manual_reference_budget',20480)) if mode=='Manual' else None
            pending=sum(r['category']!='saved' for r in refs)+len(endpoints)
            parts={}
            for r in refs:
                if r['category']=='saved':
                    key='@'+r['owner'];part=parts.setdefault(key,dict(visual=0,voice=0,total=0))
                    part['voice' if r['kind']=='audio' else 'visual']+=r.get('tokens',0);part['total']+=r.get('tokens',0)
            estimated=any(c.get('estimated_tokens') for c in chars)
            endpoint_estimate=sum(r.get('estimated_tokens',0) for r in endpoints)
            report+=('\nEstimated endpoint tokens: '+str(endpoint_estimate)) if endpoints else ''
            budget_status=dict(endpoint_tokens_estimate=endpoint_estimate,estimated=estimated,saved_tokens=saved,pending_references=pending,limit=limit,mode=mode,over_limit=limit is not None and saved+endpoint_estimate>limit,characters=parts)

            from .characters import asset_stats
            signatures=[asset_stats(r['path'],r['is_voice'])['signature'] for r in refs if 'path' in r]
            from .media import file_path
            for r in refs:
                if r['category']=='named':
                    try:
                        st=file_path(r.get('source','')).stat();signatures.append([st.st_size,st.st_mtime_ns])
                    except (ValueError,OSError): signatures.append(None)
            return web.json_response(dict(expanded_prompt=expanded,reference_map=report+'\nPreview only: token totals are calculated during encoding.',labels=labels,error=error,budget_status=budget_status,calculated_tokens=str(saved)+(' (estimated; exact after VAE processing)' if estimated else '')+(' + media preprocessing pending' if pending else ' (saved references)'),signatures=signatures,reference_counts=reference_counts))
        except (ValueError,OSError,KeyError) as e: return web.json_response({'error':str(e)},status=400)

if getattr(server.PromptServer,'instance',None) is not None:
    register()
