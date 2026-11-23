import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {webcrypto} from 'node:crypto';

// Execute the production ingestion closure with transport/widget doubles.
const source = fs.readFileSync(new URL('../web/js/load_image_x_adv.js', import.meta.url), 'utf8');
const code = source.slice(source.indexOf('  const slot = crypto.randomUUID()'), source.indexOf('  const fileInput ='));
function harness(transport) {
  const ui = {state:{load_mode:'direct'}};
  const changes = [], statuses = [];
  const widget = {options:{values:[]},callback:value=>changes.push(value)};
  const create = new Function('crypto','ui','node','imageWidget','setStatus','markChanged','fetch','FormData','console', code+'\nreturn ingestImage;');
  const ingest = create(webcrypto, ui, {}, widget, (...s)=>statuses.push(s), ()=>{}, transport, FormData, {error(){}});
  return {ui,widget,changes,statuses,ingest};
}
const file = new File(['original bytes'], 'test.png', {type:'image/png'});
test('loaded image does not lock mode; next upload uses the changed mode', async () => {
  const calls=[];
  const h=harness(async(url)=>{calls.push(url);return {ok:true,json:async()=>({name:'image',type:'temp'})};});
  h.ui.state.load_mode='normal';
  h.widget.value='existing.png';
  h.ui.source={naturalWidth:832,naturalHeight:1216};
  const original=h.ui.source;
  let change;
  const loadMode={value:'direct',addEventListener:(_,handler)=>{change=handler;}};
  const start=source.indexOf('    loadMode.addEventListener("change"');
  const end=source.indexOf('\n    mainControls.append',start);
  new Function('loadMode','ui','commitState','syncSourceControls',source.slice(start,end))(
    loadMode,h.ui,(state,options)=>{assert.equal(options.render,false);h.ui.state=state;},()=>{});
  change();
  assert.equal(h.widget.value,'existing.png');assert.equal(h.ui.source,original);
  assert.equal(h.ui.state.load_mode,'direct');
  await h.ingest(file);assert.ok(calls[0].endsWith('/direct'));
});
test('uploads serialize, capture mode, reuse one slot and refresh same paths', async () => {
  const calls = [];
  let release;
  const blocked = new Promise(resolve=>release=resolve);
  const h = harness(async (url,{body}) => {
    calls.push({url,slot:body.get('slot'),file:body.get('image')});
    if (calls.length===1) await blocked;
    return {ok:true,json:async()=>({name:'image',subfolder:'private',type:url.endsWith('/direct')?'temp':'input'})};
  });
  const first=h.ingest(file), second=h.ingest(file);
  h.ui.state.load_mode='normal';
  const third=h.ingest(file);
  await Promise.resolve();
  assert.equal(calls.length,1);
  release();
  await Promise.all([first,second,third]);
  assert.equal(calls.length,3);
  assert.equal(new Set(calls.map(x=>x.slot)).size,1);
  assert.ok(calls[0].url.endsWith('/direct'));
  assert.ok(calls[1].url.endsWith('/direct'));
  assert.equal(calls[2].url,'/upload/image');
  assert.equal(await calls[0].file.text(),'original bytes');
  assert.deepEqual(h.changes,['private/image [temp]','private/image [temp]','private/image']);
});
test('upload errors retain source and next upload recovers; instances isolate slots', async () => {
  let fail=true;
  const slots=[];
  const transport=async (_url,{body})=>{
    slots.push(body.get('slot'));
    return {ok:!fail,json:async()=>fail?{error:'bad image'}:{name:'image',type:'temp'}};
  };
  const a=harness(transport), b=harness(transport);
  a.widget.value='previous.png';
  await a.ingest(file);
  assert.equal(a.widget.value,'previous.png');
  assert.deepEqual(a.statuses.at(-1),['bad image',true]);
  fail=false;
  await a.ingest(file); await b.ingest(file);
  assert.equal(slots[0],slots[1]);
  assert.notEqual(slots[1],slots[2]);
  assert.equal(a.widget.value,'image [temp]');
});

test('a changed capture reopens the picker and cancelling preserves the held image', async () => {
  const start = source.indexOf('  async function refreshSource()');
  const end = source.indexOf('  function ingestImage', start);
  const refresh = new Function(
    'ui','app','sourceNodes','fetch','chooseFrame','selectTemporaryResult',
    `let sourceBusy = false;
     const SOURCE_ROUTE = '/source', sourceSlot = 'slot';
     function syncSourceControls() {}
     function setStatus() {}
     ${source.slice(start, end)}
     return refreshSource;`,
  );
  const selected = [], frames = [], posts = [];
  const response = (status, body) => ({status, ok:status === 200, json:async () => body});
  let count = 0;
  const run = refresh(
    {state:{source_node:'5'}}, {graph:{id:'workflow'}}, () => [{id:5}],
    async (_url, opts) => {
      if (opts.method !== 'POST') return response(200,{version:`version-${++count}`,count:2});
      posts.push(JSON.parse(opts.body));
      return response(409,{error:'A newer batch is ready'});
    },
    async (_params, capture) => {
      frames.push(capture.version);
      return frames.length === 1 ? 1 : null;
    },
    (payload) => selected.push(payload),
  );
  await run();
  assert.deepEqual(frames, ['version-1', 'version-2']);
  assert.deepEqual(posts.map((post) => post.frame), [1]);
  assert.deepEqual(selected, []);
});
