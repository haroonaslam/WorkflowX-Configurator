"""Native previews and explicit, queue-free exports of retained image batches."""
import asyncio
import copy
import json
import io
import os
import secrets
import tempfile
import threading
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo


class PreviewStore:
    def __init__(self, limit=2 * 1024**3):
        self.limit = limit
        self.entries = OrderedDict()
        self.lock = threading.RLock()

    def remove(self, token):
        entry = self.entries.pop(token)
        entry['directory'].cleanup()
        import folder_paths
        root = Path(folder_paths.get_temp_directory()).resolve()
        for record in entry.get('previews', []):
            if record['type'] != 'temp': continue
            path = (root / record['subfolder'] / record['filename']).resolve()
            if path.is_relative_to(root / 'workflowx_view'):
                path.unlink(missing_ok=True)
                path.with_suffix('.json').unlink(missing_ok=True)

    def retain(self, images, owner, metadata):
        import folder_paths
        with self.lock:
            for token, entry in list(self.entries.items()):
                if entry['owner'] == owner:
                    self.remove(token)
            size = images.numel() * 4
            if size > self.limit:
                return None
            while self.entries and sum(e['size'] for e in self.entries.values()) + size > self.limit:
                self.remove(next(iter(self.entries)))
            root = Path(folder_paths.get_temp_directory()) / 'workflowx_view_sources'
            root.mkdir(parents=True, exist_ok=True)
            directory = tempfile.TemporaryDirectory(prefix='batch-', dir=root)
            try:
                for i, frame in enumerate(images):
                    np.save(Path(directory.name) / f'{i}.npy', frame.detach().float().cpu().numpy(), allow_pickle=False)
            except BaseException:
                directory.cleanup()
                raise
            token = secrets.token_urlsafe(32)
            self.entries[token] = dict(directory=directory, owner=owner, metadata=copy.deepcopy(metadata), size=size, count=len(images),width=images.shape[2],height=images.shape[1])
            return token

    def export(self, token, options):
        # Pin entries by holding the lock during export; double-clicks cannot overlap.
        with self.lock:
            if token not in self.entries:
                raise ValueError('Preview source unavailable—run the node again.')
            entry = self.entries[token]
            self.entries.move_to_end(token)
            frames = (np.load(Path(entry['directory'].name) / f'{i}.npy', allow_pickle=False) for i in range(entry['count']))
            return write_batch(frames, metadata=entry['metadata'], **options)


STORE = PreviewStore()


def download_image(token, index, options):
    with STORE.lock:
        if token not in STORE.entries: raise ValueError('Preview source unavailable—run the node again.')
        entry = STORE.entries[token]
        validate(**options)
        if type(index) is not int or not 0 <= index < entry['count']: raise ValueError('Invalid batch image index')
        STORE.entries.move_to_end(token)
        a = np.clip(np.load(Path(entry['directory'].name)/f'{index}.npy',allow_pickle=False),0,1)
        format = options['format']
        if a.shape[-1] == 1: a = np.repeat(a,3,axis=-1)
        if format == 'jpg' and a.shape[-1] == 4: a = a[...,:3]*a[...,3:4]+1-a[...,3:4]
        image = Image.fromarray((a*255).astype(np.uint8));stream=io.BytesIO();kwargs={}
        if format=='png' and options['include_metadata'] and metadata_allowed():
            info=PngInfo()
            for key,value in entry['metadata'].items():info.add_text(key,json.dumps(value))
            kwargs['pnginfo']=info
        elif format=='jpg':kwargs.update(quality=options['quality'],subsampling=0,optimize=True)
        elif format=='webp':kwargs.update(quality=options['quality'],lossless=False,method=4)
        image.save(stream,format={'jpg':'JPEG','png':'PNG','webp':'WEBP'}[format],**kwargs)
        return stream.getvalue()


def generation_sidecar(entry, options):
    import folder_paths
    if options['format']=='png' or not options['include_metadata'] or not metadata_allowed():return None
    root=Path(folder_paths.get_output_directory()).resolve()
    if 'sidecar' not in entry:
        folder,stem,_,_,_=folder_paths.get_save_image_path(options['filename_prefix'],str(root),entry.get('width',0),entry.get('height',0))
        entry['sidecar']=Path(folder)/f'{stem.replace("%batch_num%","batch")}_{secrets.token_hex(12)}.json'
    path=entry['sidecar'].resolve()
    if not path.is_relative_to(root):raise ValueError('Sidecar must remain within ComfyUI output')
    metadata=entry['metadata'];workflow=metadata.get('workflow')
    doc=copy.deepcopy(workflow) if isinstance(workflow,dict) else {}
    if not isinstance(doc.get('extra'),dict):doc['extra']={}
    doc['extra']['workflowx_export']=dict(metadata=metadata,format=options['format'],quality=options['quality'],batch_count=entry['count'],ui_workflow_available=isinstance(workflow,dict))
    pending=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,prefix='.view-',delete=False) as f:
            pending=Path(f.name);json.dump(doc,f,ensure_ascii=False,indent=2)
        os.replace(pending,path)
    finally:
        if pending:pending.unlink(missing_ok=True)
    return path.relative_to(root).as_posix()


def save_sidecar(token, options):
    with STORE.lock:
        validate(**options)
        if token not in STORE.entries:raise ValueError('Preview source unavailable—run the node again.')
        return generation_sidecar(STORE.entries[token],options)


def validate(format, quality, filename_prefix, include_metadata):
    if format not in ('png', 'webp', 'jpg'):
        raise ValueError('Choose png, webp or jpg')
    if type(quality) is not int or not 1 <= quality <= 100:
        raise ValueError('Quality must be an integer between 1 and 100')
    if not isinstance(filename_prefix, str) or not filename_prefix.strip() or len(filename_prefix) > 512:
        raise ValueError('Provide a filename prefix of 1–512 characters')
    if type(include_metadata) is not bool:
        raise ValueError('Include metadata must be a boolean')


def metadata_allowed():
    from comfy.cli_args import args
    return not args.disable_metadata


def write_batch(frames, filename_prefix='ComfyUI', format='png', quality=95, include_metadata=True, metadata=None, temporary=False):
    import folder_paths
    validate(format, quality, filename_prefix, include_metadata)
    metadata = metadata or {}
    include_metadata = include_metadata and metadata_allowed()
    root = Path(folder_paths.get_temp_directory() if temporary else folder_paths.get_output_directory()).resolve()
    results = []
    for index, frame in enumerate(frames):
        a = np.clip(frame, 0, 1)
        if a.shape[-1] == 1:
            a = np.repeat(a, 3, axis=-1)
        if format == 'jpg' and a.shape[-1] == 4:
            a = a[..., :3] * a[..., 3:4] + 1 - a[..., 3:4]
        image = Image.fromarray((a * 255).astype(np.uint8))
        folder, stem, counter, subfolder, _ = folder_paths.get_save_image_path(filename_prefix, str(root), image.width, image.height)
        folder = Path(folder).resolve()
        if not folder.is_relative_to(root):
            raise ValueError('Save destination must remain within the ComfyUI output directory')
        stem = stem.replace('%batch_num%', str(index))
        created = []
        while True:
            target = folder / f'{stem}_{counter:05}_.{format}'
            sidecar = target.with_suffix('.json')
            if not target.resolve().is_relative_to(root):
                raise ValueError('Invalid save destination')
            try:
                handle = target.open('xb')
            except FileExistsError:
                counter += 1
                continue
            created.append(target)
            side_handle = None
            if include_metadata and format != 'png':
                try:
                    side_handle = sidecar.open('x', encoding='utf-8')
                    created.append(sidecar)
                except FileExistsError:
                    handle.close(); target.unlink(); created.clear(); counter += 1
                    continue
                except BaseException:
                    handle.close(); target.unlink()
                    raise
            break
        try:
            kwargs = {}
            if format == 'png' and include_metadata:
                info = PngInfo()
                for key, value in metadata.items():
                    info.add_text(key, json.dumps(value))
                kwargs['pnginfo'] = info
            elif format == 'jpg':
                kwargs.update(quality=quality, subsampling=0, optimize=True)
            elif format == 'webp':
                kwargs.update(quality=quality, lossless=False, method=4)
            with handle:
                image.save(handle, format={'jpg':'JPEG','png':'PNG','webp':'WEBP'}[format], **kwargs)
            if side_handle:
                workflow = metadata.get('workflow')
                document = copy.deepcopy(workflow) if isinstance(workflow, dict) else {}
                if not isinstance(document.get('extra'), dict): document['extra'] = {}
                extra = document['extra']
                extra['workflowx_export'] = dict(metadata=metadata, format=format, quality=quality, batch_index=index,
                    ui_workflow_available=isinstance(workflow, dict))
                with side_handle:
                    json.dump(document, side_handle, ensure_ascii=False, indent=2)
        except BaseException:
            handle.close()
            if side_handle: side_handle.close()
            for path in created: path.unlink(missing_ok=True)
            raise
        results.append(dict(filename=target.name, subfolder=subfolder, type='temp' if temporary else 'output'))
    return results


class ViewImageFormat:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'images': ('IMAGE',),
            'filename_prefix': ('STRING', {'default':'ComfyUI'}),
            'format': (['png','webp','jpg'], {'default':'png'}),
            'quality': ('INT', {'default':95,'min':1,'max':100,'tooltip':'JPG/WebP quality. PNG is lossless. JPG flattens transparency onto white.'}),
            'save_automatically': ('BOOLEAN', {'default':False}),
            'include_metadata': ('BOOLEAN', {'default':True,'label_on':'','label_off':''}),
        }, 'optional': {'session_key':('STRING', {'default':''})},
            'hidden': {'prompt':'PROMPT','extra_pnginfo':'EXTRA_PNGINFO','unique_id':'UNIQUE_ID'}}

    RETURN_TYPES = ('IMAGE',)
    RETURN_NAMES = ('images',)
    FUNCTION = 'view'
    OUTPUT_NODE = True
    CATEGORY = 'WorkflowX/Image'
    DESCRIPTION = 'Preview the input losslessly. Automatic saving uses the selected format; PNG/JPG/WebP buttons open Save As without rerunning. JPG/WebP share one workflow sidecar in ComfyUI output. IMAGE output is the original input.'

    def view(self, images, filename_prefix='ComfyUI', format='png', quality=95, save_automatically=False,
             include_metadata=True, session_key='', prompt=None, extra_pnginfo=None, unique_id=None):
        validate(format, quality, filename_prefix, include_metadata)
        if type(save_automatically) is not bool:
            raise ValueError('Save automatically must be a boolean')
        if images.ndim != 4 or images.shape[-1] not in (1,3,4) or min(images.shape[:3]) < 1:
            raise ValueError('View Image (Format) expects a nonempty BHWC grayscale, RGB or RGBA batch')
        metadata = copy.deepcopy(extra_pnginfo or {})
        if prompt is not None: metadata['prompt'] = copy.deepcopy(prompt)
        if not metadata_allowed(): metadata = {}
        owner = session_key or f'api:{unique_id}:{metadata.get("workflow",{}).get("id", "")}'
        token = STORE.retain(images, owner, metadata)
        prefix = filename_prefix if save_automatically else f'workflowx_view/{secrets.token_hex(12)}'
        previews = write_batch((f.detach().float().cpu().numpy() for f in images), prefix,
                               format if save_automatically else 'png', quality,
                               include_metadata if save_automatically and format=='png' else False,
                               metadata, temporary=not save_automatically)
        with STORE.lock:
            entry=STORE.entries.get(token,dict(metadata=metadata,count=len(images),width=images.shape[2],height=images.shape[1]))
            entry['previews']=copy.deepcopy(previews)
            if save_automatically:generation_sidecar(entry,dict(format=format,quality=quality,filename_prefix=filename_prefix,include_metadata=include_metadata))
        return {'ui': {'images':previews, 'workflowx_preview_token':[token or ''],
                       'workflowx_preview_count':[len(images)],
                       'workflowx_preview_message':['Ready to save' if token else 'Batch exceeds temporary-source limit; manual Save unavailable']}, 'result':(images,)}


def export_origin_allowed(request):
    # Browser-controlled Fetch Metadata survives reverse proxies rewriting Host.
    site = request.headers.get('Sec-Fetch-Site', '').lower()
    if site == 'same-origin':
        return True
    if site == 'cross-site':
        return False
    origin = request.headers.get('Origin')
    if not origin:
        return True  # Non-browser API clients still require an opaque source token.
    try:
        parsed = urlsplit(origin)
        host = urlsplit(f'{parsed.scheme}://{request.host}')
        port = lambda value: value.port or {'http':80, 'https':443}.get(value.scheme)
        return (parsed.scheme in ('http', 'https') and not parsed.username
                and parsed.hostname == host.hostname and port(parsed) == port(host))
    except ValueError:
        return False


def register_routes():
    from aiohttp import web
    from server import PromptServer
    server = PromptServer.instance
    if server is None or getattr(server, '_workflowx_view_format', False): return
    server._workflowx_view_format = True

    @server.routes.post('/workflowx/view_image_format/save')
    async def save(request):
        if not export_origin_allowed(request):
            return web.json_response({'error':'Cross-origin export rejected'}, status=403)
        try:
            data = await request.json()
            options = {key:data[key] for key in ('filename_prefix','format','quality','include_metadata')}
            if data.get('action')=='sidecar':
                path=await asyncio.to_thread(save_sidecar,data['token'],options)
                return web.json_response({'sidecar':path})
            content=await asyncio.to_thread(download_image,data['token'],data.get('index',0),options)
            return web.Response(body=content,content_type={'png':'image/png','jpg':'image/jpeg','webp':'image/webp'}[options['format']])
        except (ValueError, KeyError, TypeError, OSError) as exc:
            return web.json_response({'error':str(exc)}, status=400)


NODE_CLASS_MAPPINGS = {'WorkflowX_ViewImageFormat':ViewImageFormat}
NODE_DISPLAY_NAME_MAPPINGS = {'WorkflowX_ViewImageFormat':'View Image (Format)'}
