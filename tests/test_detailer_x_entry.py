import asyncio
import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from detailer_x import entry, config, DetailerX, DetailerXReplay


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    entry.SESSIONS.clear()
    monkeypatch.setattr(entry,"ACTIVE_PROMPTS",lambda:set())
    monkeypatch.setattr(entry,"announce",lambda s:None)


def session(paused=True):
    settings=copy.deepcopy(config.DEFAULTS)
    settings['entry'].update(pause=paused,wait_indefinitely=True)
    return entry.new_session('owner','dx',settings)


@pytest.mark.parametrize('action,expected',[('resume',True),('skip',False),('cancel',False)])
def test_gate_actions_and_persistent_pause(action,expected):
    async def exercise():
        s=session()
        task=asyncio.create_task(entry.gate(s,lambda:None))
        await asyncio.sleep(0)
        assert s['state']=='paused'
        settings=copy.deepcopy(s['settings']);settings['face']['denoise']=.33
        entry.command(s,action,settings,1)
        assert await task is expected
        assert s['settings']['entry']['pause']
        if expected: assert s['settings']['face']['denoise']==.33
    asyncio.run(exercise())


def test_gate_internal_timeout_without_browser_or_commands():
    async def exercise():
        s=session();s['settings']['entry'].update(wait_indefinitely=False,pause_minutes=.001)
        assert await asyncio.wait_for(entry.gate(s,lambda:None),1) is True
        assert s['state']=='processing'
        assert 'wake' not in s and 'loop' not in s
    asyncio.run(exercise())


def test_gate_global_interrupt_while_waiting_cleans_up():
    async def exercise():
        interrupted=False
        def check():
            if interrupted:raise RuntimeError('global interrupt')
        s=session();task=asyncio.create_task(entry.gate(s,check))
        await asyncio.sleep(.01);interrupted=True
        with pytest.raises(RuntimeError,match='global interrupt'):
            await asyncio.wait_for(task,1)
        assert 'wake' not in s and 'loop' not in s
    asyncio.run(exercise())


def test_gate_invalid_update_disarms_timeout_until_valid_resume():
    async def exercise():
        s=session();s['settings']['entry'].update(wait_indefinitely=False,pause_minutes=.001)
        task=asyncio.create_task(entry.gate(s,lambda:None));await asyncio.sleep(0)
        bad=copy.deepcopy(s['settings']);bad['face']['denoise']=99
        with pytest.raises(ValueError):entry.command(s,'update',bad,1)
        await asyncio.sleep(.1);assert not task.done()
        valid=copy.deepcopy(config.DEFAULTS);valid['face']['denoise']=.27
        entry.command(s,'resume',valid,2)
        with pytest.raises(ValueError):entry.command(s,'resume',valid,3)
        assert await asyncio.wait_for(task,1) is True
        assert s['settings']['face']['denoise']==.27
    asyncio.run(exercise())


def test_timer_expiry_and_duration_recalculation(monkeypatch):
    clock=[10.0]
    monkeypatch.setattr(entry.time,'monotonic',lambda:clock[0])
    async def exercise():
        s=session();s['settings']['entry'].update(wait_indefinitely=False,pause_minutes=5)
        task=asyncio.create_task(entry.gate(s,lambda:None));await asyncio.sleep(0)
        clock[0]=190
        settings=copy.deepcopy(s['settings']);settings['entry']['pause_minutes']=2
        entry.command(s,'update',settings,1)
        assert entry.view(s)['remaining']==0
        assert await task is True
    asyncio.run(exercise())


def test_enabling_skip_releases_paused_gate_without_processing():
    async def exercise():
        s=session();task=asyncio.create_task(entry.gate(s,lambda:None));await asyncio.sleep(0)
        settings=copy.deepcopy(s['settings']);settings['entry']['skip']=True
        entry.command(s,'update',settings,1)
        assert await task is False
        assert s['state']=='passed' and s['settings']['entry']['pause']
    asyncio.run(exercise())


def test_invalid_update_blocks_expiry_and_stale_commands(monkeypatch):
    s=session();s['state']='paused';s['entered']=entry.time.monotonic()-1000
    invalid=copy.deepcopy(s['settings']);invalid['face']['denoise']=99
    with pytest.raises(ValueError):entry.command(s,'update',invalid,2)
    assert s['error']
    entry.command(s,'update',s['settings'],3)
    assert not s['error']
    with pytest.raises(ValueError,match='stale'):entry.command(s,'update',s['settings'],2)
    entry.command(s,'cancel')
    with pytest.raises(ValueError,match='released'):entry.command(s,'resume',s['settings'])


def test_skip_persists_takes_priority_over_pause_and_interrupt():
    s=session();s['settings']['entry']['skip']=True
    for _ in range(3):
        assert asyncio.run(entry.gate(s,lambda:None)) is False
        assert s['settings']['entry']['skip'] is True
    def interrupt():raise RuntimeError('interrupted')
    with pytest.raises(RuntimeError,match='interrupted'):
        asyncio.run(entry.gate(session(),interrupt))


def graph():
    return {
      'up':{'class_type':'Generator','inputs':{'seed':123}},
      'external':{'class_type':'Text','inputs':{'text':'retained'}},
      'dx':{'class_type':entry.TYPE,'inputs':{'image':['up',0],'settings':json.dumps(config.DEFAULTS)}},
      'join':{'class_type':'Join','inputs':{'image':['dx',8],'text':['external',0]}},
      'save':{'class_type':'Save','inputs':{'image':['join',0]}},
      'unrelated':{'class_type':'Save','inputs':{'image':['up',0]}},
    }


def test_capture_and_replay_graph_freezes_boundaries_excludes_upstream():
    original=graph();payload=entry.prepare_prompt({'prompt':copy.deepcopy(original)})
    token=json.loads(payload['prompt']['dx']['inputs']['settings'])['_run']
    s=entry.get_session(token)
    assert payload['prompt_id']
    taps=[v for v in payload['prompt'].values() if v['class_type']==entry.TAP]
    assert len(taps)==1
    tap=taps[0]['inputs']
    assert entry.Capture().capture(['retained'],[token],[tap['key']])==(['retained'],)
    rerun=entry.replay_graph(s,original,'dx',config.DEFAULTS,'job')
    assert {'up','external','unrelated'}.isdisjoint(rerun)
    assert {'dx','join','save'}<=rerun.keys()
    assert rerun['dx']['class_type']==entry.REPLAY
    source=rerun[rerun['join']['inputs']['text'][0]]['inputs']
    assert entry.Snapshot().read(**source)==(['retained'],)


def test_missing_boundary_rejected_and_resolved_subgraph_ids():
    s=session(False);p=graph()
    with pytest.raises(ValueError,match='No retained input'):entry.replay_graph(s,p,'dx',config.DEFAULTS,'job')
    p['container:dx']=p.pop('dx');p['join']['inputs']['image']=['container:dx',8]
    s['boundary'][json.dumps(['external',0])]=['retained']
    assert 'container:dx' in entry.replay_graph(s,p,'container:dx',config.DEFAULTS,'job')
    with pytest.raises(ValueError,match='mapping changed'):entry.replay_graph(s,p,'missing',config.DEFAULTS,'job')


def test_snapshot_cpu_immutable_and_eviction(monkeypatch):
    tensor=torch.ones(1,2,2,4)
    saved=entry.snapshot({'image':tensor});tensor.zero_()
    assert saved['image'].sum()==16
    a=session(False);a.update(inputs=saved,state='completed')
    b=entry.new_session('second','dx',config.DEFAULTS);b.update(inputs=entry.snapshot(saved),state='paused')
    monkeypatch.setattr(entry,'LIMIT',64)
    entry.prune()
    assert a['token'] not in entry.SESSIONS and b['token'] in entry.SESSIONS


def test_retention_limit_protects_active_sessions(monkeypatch):
    a=session();a['state']='paused'
    monkeypatch.setattr(entry,'LIMIT',64)
    entry.retain(a,'inputs',{'image':torch.ones(1,2,2,4)})
    b=entry.new_session('other','node',config.DEFAULTS);b['state']='processing'
    with pytest.raises(ValueError,match='shared 2 GiB'):
        entry.retain(b,'inputs',{'image':torch.ones(1,2,2,4)})
    assert a['token'] in entry.SESSIONS and b['inputs'] is None


@pytest.mark.parametrize('headers,host,allowed',[
    ({'Sec-Fetch-Site':'same-origin','Origin':'http://localhost:8188'},'127.0.0.1:8188',True),
    ({'Sec-Fetch-Site':'same-origin'},'127.0.0.1:8188',True),
    ({'Origin':'http://LOCALHOST:8188'},'localhost:8188',True),
    ({'Origin':'http://other.example'},'localhost:8188',False),
    ({'Sec-Fetch-Site':'cross-site','Origin':'http://localhost:8188'},'localhost:8188',False),
    ({'Sec-Fetch-Site':'same-site','Origin':'http://localhost:9999'},'localhost:8188',False),
    ({'Origin':'null'},'localhost:8188',False),
])
def test_entry_origin_security(headers,host,allowed):
    from aiohttp import web
    server=SimpleNamespace(routes=web.RouteTableDef(),add_on_prompt_handler=lambda fn:None,
        prompt_queue=SimpleNamespace(get_current_queue_volatile=lambda:([],[])))
    entry.register(server)
    handler=next(r.handler for r in server.routes if r.method=='GET' and r.path.endswith('/entry'))
    request=SimpleNamespace(headers=headers,host=host,query={'owner':'missing'})
    async def exercise():
        if allowed:assert (await handler(request)).status==200
        else:
            with pytest.raises(web.HTTPForbidden):await handler(request)
    asyncio.run(exercise())


def test_routes_isolate_owner_and_queue_rerun(monkeypatch):
    from aiohttp import web
    import execution
    queued=[]
    server=SimpleNamespace(routes=web.RouteTableDef(),number=0,add_on_prompt_handler=lambda fn:None,
        prompt_queue=SimpleNamespace(get_current_queue_volatile=lambda:([],queued),put=queued.append))
    entry.register(server)
    handlers={(route.method,route.path.rsplit('/',1)[-1]):route.handler for route in server.routes}
    async def validated(*args):return True,None,['dx'],{}
    monkeypatch.setattr(execution,'validate_prompt',validated)
    s=session(False);s.update(state='completed',inputs={'image':torch.ones(1,2,2,3)})
    p={'dx':{'class_type':entry.TYPE,'inputs':{}}}
    data=dict(owner='owner',token=s['token'],target='dx',prompt=p,settings=s['settings'])
    async def json_data():return data
    request=SimpleNamespace(headers={'Origin':'http://localhost:8188'},host='localhost:8188',json=json_data)
    async def exercise():
        data['owner']='wrong'
        assert (await handlers['POST','rerun'](request)).status==400
        data['owner']='owner'
        response=await handlers['POST','rerun'](request)
        assert response.status==200 and len(queued)==1
        assert queued[0][2]['dx']['class_type']==entry.REPLAY
        assert (await handlers['POST','rerun'](request)).status==400
        request.headers={'Origin':'http://other.example'}
        with pytest.raises(web.HTTPForbidden):await handlers['POST','rerun'](request)
    asyncio.run(exercise())


@pytest.mark.parametrize('channels',[3,4])
def test_async_entry_passes_all_nine_outputs_and_records_metadata(monkeypatch,channels):
    from detailer_x import processing
    monkeypatch.setattr(processing,'cancelled',lambda:None)
    s=session(False);s['settings']['entry']['skip']=True
    image=torch.rand(2,8,8,channels)
    settings={**s['settings'],'_run':s['token']}
    prompt={'dx':{'inputs':{}}};extra={}
    def forbidden(**kwargs):raise AssertionError('processing must not run')
    result=asyncio.run(entry.execute_entry(forbidden,{'image':image},settings,'dx',prompt,extra))
    assert len(result)==9 and all(torch.equal(image,v) for v in result)
    result[0].zero_();assert not torch.equal(result[0],result[1])
    assert extra['detailer_x_effective']['dx']['entry']['pause'] is False
    assert s['state']=='passed'


def test_replay_uses_retained_inputs_latest_settings_and_no_gate(monkeypatch):
    import detailer_x
    s=session();s.update(inputs={'image':torch.ones(1,2,2,3)},state='queued',prompt_id='job')
    seen=[]
    monkeypatch.setattr(DetailerX,'process',lambda self,**kwargs:seen.append(kwargs) or (kwargs['image'],)*9)
    settings=copy.deepcopy(config.DEFAULTS);settings['face']['denoise']=.27;settings['entry']['pause']=True
    out=DetailerXReplay().run(s['token'],json.dumps(settings),'job','dx')
    assert len(out)==9 and seen[0]['settings']['face']['denoise']==.27
    assert s['state']=='completed'
    with pytest.raises(ValueError,match='stale'):DetailerXReplay().run(s['token'],json.dumps(settings),'job','dx')


def test_rerun_honors_persistent_skip(monkeypatch):
    s=session();s.update(inputs={'image':torch.ones(1,2,2,4)},state='queued',prompt_id='job')
    def forbidden(*args,**kwargs):raise AssertionError('Skip must bypass processing')
    monkeypatch.setattr(DetailerX,'process',forbidden)
    settings=copy.deepcopy(config.DEFAULTS);settings['entry'].update(skip=True,pause=True)
    out=DetailerXReplay().run(s['token'],json.dumps(settings),'job','dx')
    assert len(out)==9 and all(torch.equal(v,s['inputs']['image']) for v in out)
    assert s['state']=='passed'


def test_real_comfy_executor_replays_downstream_without_generator(monkeypatch):
    """Exercise Comfy's real validation, async gate, list wiring and executor queue path."""
    import execution
    import nodes
    import detailer_x
    counts={'generate':0,'save':0}
    import comfy.model_management
    monkeypatch.setattr(nodes,'interrupt_processing',comfy.model_management.interrupt_current_processing,raising=False)
    monkeypatch.setattr(nodes,'before_node_execution',comfy.model_management.throw_exception_if_processing_interrupted,raising=False)
    class Generate:
        @classmethod
        def INPUT_TYPES(cls):return {'required':{}}
        RETURN_TYPES=('MODEL','VAE','CLIP','CONDITIONING','CONDITIONING','IMAGE','STRING')
        FUNCTION='run'
        def run(self):
            counts['generate']+=1
            return None,None,None,[],[],torch.ones(1,8,8,4),'external'
    class Save:
        @classmethod
        def INPUT_TYPES(cls):return {'required':{'image':('IMAGE',),'text':('STRING',)}}
        RETURN_TYPES=()
        OUTPUT_NODE=True
        FUNCTION='run'
        def run(self,image,text):
            assert text=='external'
            counts['save']+=1
            return ()
    for key,cls in {**detailer_x.NODE_CLASS_MAPPINGS,'DXTestGenerate':Generate,'DXTestSave':Save}.items():
        monkeypatch.setitem(nodes.NODE_CLASS_MAPPINGS,key,cls)
    monkeypatch.setattr(DetailerX,'process',lambda self,**kw:(kw['image'],)*9)
    s=copy.deepcopy(config.DEFAULTS)
    s['entry']['pause']=False
    p={'g':{'class_type':'DXTestGenerate','inputs':{}},
       'dx':{'class_type':entry.TYPE,'inputs':{**{k:['g',i] for i,k in enumerate(('model','vae','clip','positive','negative','image'))},'settings':json.dumps(s)}},
       'save':{'class_type':'DXTestSave','inputs':{'image':['dx',8],'text':['g',6]}}}
    payload=entry.prepare_prompt({'prompt':copy.deepcopy(p)})
    async def exercise():
        valid=await execution.validate_prompt(payload['prompt_id'],payload['prompt'],None)
        assert valid[0],valid
        server=SimpleNamespace(client_id=None,last_node_id=None,send_sync=lambda *args:None)
        executor=execution.PromptExecutor(server,cache_args={'ram':0,'ram_inactive':0,'lru':0})
        await executor.execute_async(payload['prompt'],payload['prompt_id'],{},valid[2])
        assert executor.success,executor.status_messages
        assert counts=={'generate':1,'save':1}
        retained=next(iter(entry.SESSIONS.values()))
        replay=entry.replay_graph(retained,p,'dx',s,'replay-job')
        retained.update(prompt_id='replay-job',state='queued')
        valid=await execution.validate_prompt('replay-job',replay,None)
        assert valid[0],valid
        await executor.execute_async(replay,'replay-job',{},valid[2])
        assert executor.success,executor.status_messages
        assert counts=={'generate':1,'save':2}
    asyncio.run(exercise())
