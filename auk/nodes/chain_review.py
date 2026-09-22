"""Temporary segment editor; one retained take per line, no intermediate cache."""
import math
import json
import os
from dataclasses import replace
from pathlib import Path
import secrets
import shutil
import tempfile
import threading
import time
import torch
import soundfile as sf
from aiohttp import web
from comfy_api.latest import io
from comfy_execution.graph_utils import ExecutionBlocker
import comfy.model_management as mm
from server import PromptServer
from .chain_script import parse_script, SPEAKER

SESSIONS = {}
REGISTRY_LOCK = threading.RLock()
TTL = 24 * 60 * 60
STORAGE = Path(tempfile.gettempdir()) / 'workflowx-auk-segment-editor'

def lines(text):
    return [line for line in text.splitlines() if line.strip()]

class Session:
    def __init__(self, token, owner):
        STORAGE.mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(prefix='batch-', dir=STORAGE)
        self.root = Path(self.directory.name)
        (self.root / 'editor-owned').write_text(json.dumps({'pid':os.getpid()}), encoding='utf-8')
        self.token, self.owner = token, owner
        self.batch = secrets.token_hex(16)
        self.revision = 0
        self.lock = threading.Lock()
        self.segments = []
        self.source_count = 0
        self.updated = time.time()
        self.cancelled = False
        self.nonces = set()
        self.state = {}
        self.publish('generating', 'Generating all lines...')

    def publish(self, status, message, selected=None):
        self.state = dict(status=status, message=message, batch=self.batch, revision=self.revision,
            selected=selected, total=len(self.segments), source_count=self.source_count,
            segments=[{k:v for k,v in segment.items() if k not in ('file', 'preview')} |
                {'audio': f'/workflowx/auk/chain-review/{self.token}/audio/{segment["id"]}?v={segment.get("version", "")}' if segment.get('file') else None}
                for segment in self.segments])

    def close(self):
        self.directory.cleanup()

def process_running(pid):
    """Read process liveness; ambiguous/access-denied results keep its files safe."""
    if pid == os.getpid():
        return True
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.GetExitCodeProcess.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() != 87  # ERROR_INVALID_PARAMETER: PID no longer exists.
        try:
            code = wintypes.DWORD()
            return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def orphan_ready(path):
    try:
        marker = json.loads((path / 'editor-owned').read_text(encoding='utf-8'))
        pid = marker.get('pid') if isinstance(marker,dict) else None
        if isinstance(pid,int) and 0 < pid < 2**32:
            if pid != os.getpid():
                return not process_running(pid)
        return time.time() - path.stat().st_mtime > TTL
    except (OSError,ValueError):
        return False


def expire():
    with REGISTRY_LOCK:
        for token, session in list(SESSIONS.items()):
            if time.time() - session.updated > TTL and session.lock.acquire(blocking=False):
                try:
                    session.close()
                    del SESSIONS[token]
                finally:
                    session.lock.release()
        active = {s.root for s in SESSIONS.values()}
        if STORAGE.exists():
            for path in STORAGE.glob('batch-*'):
                if path not in active and not path.is_symlink() and path.resolve().parent == STORAGE.resolve() and (path / 'editor-owned').is_file() and orphan_ready(path):
                    shutil.rmtree(path)

def maintenance():
    expire()
    timer = threading.Timer(600, maintenance)
    timer.daemon = True
    timer.start()

class CancellationCheck:
    """Use the generation hook for cancellation without storing intermediate audio."""
    def __init__(self, session):
        self.session = session
    def key(self, *args):
        if self.session.cancelled:
            raise mm.InterruptProcessingException('Segment editor cleared.')
    def get(self, key):
        return None
    def put(self, key, audio):
        self.key()

def metadata(hidden):
    extra = hidden.extra_pnginfo or {}
    node_id = str(hidden.unique_id)
    request = extra.get('workflowx_auk_review', {}).get(node_id, {})
    node = next((n for n in extra.get('workflow', {}).get('nodes', []) if str(n.get('id')) == node_id), {})
    token = request.get('token') or node.get('properties', {}).get('workflowx_auk_review_id')
    if not isinstance(token, str) or len(token) != 32 or any(c not in '0123456789abcdef' for c in token):
        raise ValueError('Open this workflow in ComfyUI to use the Segment editor.')
    return token, request, node_id

def blocked(state):
    return io.NodeOutput(ExecutionBlocker(None), ExecutionBlocker(None), ui={'workflowx_auk_review': [state]})

def check_session(session, request):
    if session.cancelled:
        raise ValueError('This editor was cleared. Run the workflow again.')
    if request.get('batch') != session.batch or request.get('revision') != session.revision:
        raise ValueError('The editor changed. Refresh its state and try again.')

def assemble(session, gap):
    if not math.isfinite(gap) or gap < 0:
        raise ValueError('Gap must be finite and nonnegative.')
    if not session.segments or any(not s.get('file') for s in session.segments):
        raise ValueError('Generate every segment before finalizing.')
    clips, reports, cursor = [], [], 0
    gap_samples = round(gap * 24000)
    for index, segment in enumerate(session.segments):
        mm.throw_exception_if_processing_interrupted()
        CancellationCheck(session).key()
        clip = torch.load(session.root / segment['file'], map_location='cpu', weights_only=True)['waveform']
        if index and gap_samples:
            clips.append(clip.new_zeros((1,1,gap_samples)))
            cursor += gap_samples
        start = cursor / 24000
        clips.append(clip)
        cursor += clip.shape[-1]
        # Aggregate numbering/timings are current; retain only the take's stage details here.
        stages = '\n'.join(segment['report'].splitlines()[4:])
        reports.append(f'Segment {index+1} | voice {segment["voice"]} | seed {segment["seed"]} | output {start:.3f}-{cursor/24000:.3f}s\nRetained text: {segment["raw"]}\n{stages}')
    return {'waveform':torch.cat(clips,dim=-1),'sample_rate':24000}, f'{len(session.segments)} segments | total: {cursor/24000:.3f}s | gap: {gap_samples/24000:.3f}s\n\n' + '\n\n'.join(reports)

def validate_references(inputs, segments):
    from .chained_clone import validate_timing
    validate_timing(segments, inputs['gap_seconds'], inputs['sound_extra_seconds'], inputs.get('speed_timing_multiplier', 1.0))
    for segment in segments:
        ref = inputs.get('reference_audio' if segment.voice == 1 else 'reference_audio_2')
        if ref is None or ref['waveform'].ndim != 3 or ref['waveform'].shape[0] != 1 or min(ref['waveform'].shape[1:]) < 1 or ref['sample_rate'] <= 0:
            raise ValueError(f'Line {segment.line}: Voice {segment.voice} requires one nonempty recording.')

def generate_take(session, index, segment, raw, inputs):
    from .chained_clone import generate_chain
    slot = session.segments[index]
    attempt = slot.get('attempt', -1) + 1
    slot['attempt'] = attempt
    seed = (inputs['seed'] + index + attempt * 104729) % (2**64)
    session.publish('generating', f'Generating segment {index+1}...', slot['id'])
    audio, report = generate_chain(**{**inputs, 'seed':(seed-index) % (2**64), 'gap_seconds':0}, _segments=[segment], _index=index, _cache=CancellationCheck(session))
    CancellationCheck(session).key()
    version = secrets.token_hex(8)
    stem = slot['id'] + '-' + version
    file, preview = stem+'.pt', stem+'.wav'
    try:
        torch.save(audio, session.root / file)
        sf.write(session.root / preview, audio['waveform'][0].T.numpy(), 24000, subtype='FLOAT')
        CancellationCheck(session).key()
    except BaseException:
        (session.root / file).unlink(missing_ok=True)
        (session.root / preview).unlink(missing_ok=True)
        raise
    old = [slot.get('file'), slot.get('preview')]
    slot.update(file=file, preview=preview, version=version, raw=raw, text=segment.text, voice=segment.voice,
        seed=seed, duration=audio['waveform'].shape[-1]/24000, report=report,
        settings={k:v for k,v in inputs.items() if isinstance(v,(str,int,float,bool)) and k != 'script'})
    for name in old:
        if name:
            (session.root / name).unlink(missing_ok=True)
    session.revision += 1
    session.publish('generating', f'Segment {index+1} ready.', slot['id'])

def selected_segment(effective, index, inputs):
    # Other retained lines are not regenerated or revalidated. Only their speaker
    # prefixes participate in inheritance for the selected take.
    previous_voice = 1
    for raw in effective[:index]:
        prefix = SPEAKER.match(raw.strip())
        if prefix:
            previous_voice = int(prefix[1])
    segment = parse_script('\n' * index + effective[index], inputs['words_per_second'], inputs['multi_speaker'], inputs['inline_edits'])[0]
    if inputs['multi_speaker'] and not segment.voice_explicit:
        segment = replace(segment, voice=previous_voice)
    return segment


def execute_review(inputs, hidden):
    token, request, owner = metadata(hidden)
    action = request.get('action', 'run')
    if action not in ('run', 'regenerate', 'add'):
        raise ValueError('Unknown editor action.')
    expire()
    with REGISTRY_LOCK:
        session = SESSIONS.get(token)
        if session and session.owner != owner:
            raise ValueError('Editor belongs to another node.')
        if action == 'run':
            if session:
                if not session.lock.acquire(blocking=False):
                    raise ValueError('Wait for the active editor operation.')
                session.close()
                session.lock.release()
            session = Session(token, owner)
            SESSIONS[token] = session
        if not session:
            raise ValueError('Editor expired. Run the workflow again.')
        if not session.lock.acquire(blocking=False):
            raise ValueError('Wait for the active editor operation.')
    try:
        session.updated = time.time()
        source = lines(inputs['script'])
        if action == 'run':
            parsed = parse_script(inputs['script'], inputs['words_per_second'], inputs['multi_speaker'], inputs['inline_edits'])
            validate_references(inputs, parsed)
            session.source_count = len(source)
            session.segments = [dict(id=secrets.token_hex(12), source=i, editor_only=False, draft=raw) for i,raw in enumerate(source)]
            for index, segment in enumerate(parsed):
                generate_take(session,index,segment,source[index],inputs)
            audio, report = assemble(session, inputs['gap_seconds'])
            session.publish('ready','All segments generated and sent to the outputs.')
            return io.NodeOutput(audio, report, ui={'workflowx_auk_review':[session.state]})
        check_session(session, request)
        nonce = request.get('nonce')
        if not nonce or nonce in session.nonces:
            return blocked(session.state)
        if len(session.nonces) >= 256:
            session.nonces.clear()
        session.nonces.add(nonce)
        index = next((i for i,s in enumerate(session.segments) if s['id'] == request.get('segment')), None)
        if index is None:
            raise ValueError('Select a segment.')
        local_add = action == 'add' and not request.get('connected')
        expected = session.source_count + (1 if local_add else 0)
        if len(source) != expected:
            raise ValueError('The script line count changed. Start a full Run before editing segments; retained audio can still be finalized.')
        new_raw = request.get('text', '')
        if action == 'add':
            if len(lines(new_raw)) != 1 or '\n' in new_raw or '\r' in new_raw:
                raise ValueError('Enter exactly one nonblank script line.')
            if local_add:
                if session.segments[index]['source'] is None:
                    raise ValueError('This editor-only line needs a connected script, or start a new Run.')
                position = session.segments[index]['source'] + 1
                if source[position] != new_raw:
                    raise ValueError('Inserted text does not match the script. Start a new Run.')
                source.pop(position)
            else:
                position = None
        effective = [source[s['source']] if s['source'] is not None else s['draft'] for s in session.segments]
        if action == 'add':
            index += 1
            effective.insert(index,new_raw)
        selected = selected_segment(effective,index,inputs)
        validate_references(inputs,[selected])
        if action == 'add':
            if local_add:
                for slot in session.segments:
                    if slot['source'] is not None and slot['source'] >= position:
                        slot['source'] += 1
                session.source_count += 1
            session.segments.insert(index,dict(id=secrets.token_hex(12),source=position,editor_only=not local_add,draft=new_raw))
            session.revision += 1
        generate_take(session,index,selected,effective[index],inputs)
        session.publish('ready','Segment updated. Finalize to send the revised recording.',session.segments[index]['id'])
        return blocked(session.state)
    except BaseException as error:
        session.publish('error', str(error), session.segments[index]['id'] if 'index' in locals() and index is not None and index < len(session.segments) else None)
        raise
    finally:
        if session.cancelled:
            with REGISTRY_LOCK:
                SESSIONS.pop(token,None)
            session.close()
        session.lock.release()

def finalize_editor(gap_seconds, hidden):
    token, request, owner = metadata(hidden)
    session = SESSIONS.get(token)
    if not session or session.owner != owner:
        raise ValueError('Editor expired. Run the workflow again.')
    if not session.lock.acquire(blocking=False):
        raise ValueError('Wait for generation to finish.')
    try:
        check_session(session,request)
        nonce = request.get('nonce')
        if not nonce or nonce in session.nonces:
            return blocked(session.state)
        if len(session.nonces) >= 256:
            session.nonces.clear()
        session.nonces.add(nonce)
        session.updated = time.time()
        audio,report = assemble(session,gap_seconds)
        session.publish('ready','Finalized recording sent to the outputs.')
        return io.NodeOutput(audio,report,ui={'workflowx_auk_review':[session.state]})
    finally:
        if session.cancelled:
            SESSIONS.pop(token,None)
            session.close()
        session.lock.release()

def register_routes():
    routes = PromptServer.instance.routes
    @routes.post('/workflowx/auk/chain-review/validate-line')
    async def validate_line(request):
        data = await request.json()
        try:
            raw = data.get('text', '')
            if len(lines(raw)) != 1 or '\n' in raw or '\r' in raw:
                raise ValueError('Enter exactly one nonblank line.')
            parse_script(raw, 2, True, bool(data.get('inline_edits')))
            return web.json_response({'valid': True})
        except ValueError as error:
            return web.json_response({'error': str(error)}, status=400)

    @routes.get('/workflowx/auk/chain-review/{token}')
    async def state(request):
        expire()
        session = SESSIONS.get(request.match_info['token'])
        return web.json_response(session.state if session else {'status':'empty','message':'Run the workflow to generate segments.','segments':[]})
    @routes.get('/workflowx/auk/chain-review/{token}/audio/{segment}')
    async def audio(request):
        session = SESSIONS.get(request.match_info['token'])
        slot = next((s for s in session.segments if s['id'] == request.match_info['segment']),None) if session else None
        if not slot or not slot.get('preview'):
            raise web.HTTPNotFound()
        session.updated = time.time()
        return web.FileResponse(session.root / slot['preview'],headers={'Cache-Control':'no-store'})
    @routes.post('/workflowx/auk/chain-review/{token}/touch')
    async def touch(request):
        session = SESSIONS.get(request.match_info['token'])
        if session:
            session.updated = time.time()
        return web.json_response({'active': bool(session)})
    @routes.post('/workflowx/auk/chain-review/{token}/cancel')
    async def cancel(request):
        token = request.match_info['token']
        session = SESSIONS.get(token)
        if session:
            session.cancelled = True
            if session.lock.acquire(blocking=False):
                try:
                    SESSIONS.pop(token,None)
                    session.close()
                finally:
                    session.lock.release()
        return web.json_response({'status':'empty','segments':[]})
    maintenance()
