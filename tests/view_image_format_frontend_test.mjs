import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

async function harness(cancel=false,storage=new Map()){
  const source=await readFile(new URL('../web/js/view_image_format.js',import.meta.url),'utf8');
  let extension;const requests=[],pickers=[],writes=[];
  const app={registerExtension:e=>extension=e};
  const api={fetchApi:async(url,options)=>{const data=JSON.parse(options.body);requests.push(data);return {ok:true,json:async()=>({sidecar:'generation.json'}),blob:async()=>new Blob(['image'])};}};
  const window={showSaveFilePicker:async options=>{pickers.push(options);if(cancel)throw Object.assign(new Error('cancelled'),{name:'AbortError'});return {createWritable:async()=>({write:async b=>writes.push(b),close:async()=>{},abort:async()=>{}})};}};
  const document={createElement:()=>({style:{},children:[],events:{},append(...a){this.children.push(...a);},addEventListener(n,f){this.events[n]=f;}})};
  window.localStorage={getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)};
  new Function('app','api','crypto','document','window',source.replace(/^import .*;\r?\n/gm,''))(app,api,{randomUUID:()=>String(Math.random())},document,window);
  class Node{
    constructor(){this.widgets=[['format','png'],['quality',95],['filename_prefix','ComfyUI'],['include_metadata',true],['session_key','']].map(([name,value])=>({name,value,type:'number'}));this.onNodeCreated();}
    setDirtyCanvas(){}
    addDOMWidget(name,type,element,options){const w={name,type,element,options};this.widgets.push(w);return w;}
  }
  await extension.beforeRegisterNodeDef(Node,{name:'WorkflowX_ViewImageFormat'});
  return {node:new Node(),Node,requests,pickers,writes};
}
test('three inline buttons and internal field hidden',async()=>{
  const {node}=await harness();
  assert.deepEqual(node._viewButtons.map(b=>b.textContent),['PNG','JPG','WEBP']);
  assert.ok(node._viewButtons.every(b=>b.disabled));
  const session=node.widgets.find(w=>w.name==='session_key');assert.equal(session.hidden,true);assert.deepEqual(session.computeSize(),[0,-4]);
  assert.equal(node.widgets.find(w=>w.name==='quality').type,'number');
  assert.equal(node.widgets.find(w=>w.name==='include_metadata').options.on,'');
});
test('format button overrides auto format and reuses generation token',async()=>{
  const {node,Node,requests,pickers,writes}=await harness();
  node.onExecuted({workflowx_preview_token:['secret'],workflowx_preview_count:[1]});
  await node._viewButtons[1].events.click();
  await node._viewButtons[2].events.click();
  assert.deepEqual(requests.map(r=>[r.format,r.action||'image']),[['jpg','image'],['jpg','sidecar'],['webp','image'],['webp','sidecar']]);
  assert.ok(requests.every(r=>r.token==='secret'));assert.equal(writes.length,2);
  assert.equal(pickers[0].suggestedName,'ComfyUI_00001_.jpg');
  assert.equal(pickers[1].suggestedName,'ComfyUI_00002_.webp');
  const info={widgets_values:node.widgets.map(w=>w.value)};node.onSerialize(info);assert.equal(info.widgets_values[4],'');
  const copy=new Node();copy.onConfigure(info);assert.ok(copy._viewButtons.every(b=>b.disabled));
});
test('PNG embeds metadata without separate sidecar and batch writes all images',async()=>{
  const {node,requests,writes}=await harness();node.onExecuted({workflowx_preview_token:['secret'],workflowx_preview_count:[2]});
  await node._viewButtons[0].events.click();
  assert.deepEqual(requests.map(r=>r.index),[0,1]);assert.equal(writes.length,2);
});
test('cancelled picker makes no image or sidecar requests',async()=>{
  const {node,requests}=await harness(true);node.onExecuted({workflowx_preview_token:['secret']});
  await node._viewButtons[1].events.click();assert.equal(requests.length,0);assert.equal(node._viewStatus.textContent,'Save cancelled');
});

test('numbering persists across reloads, batches and formats',async()=>{
  const storage=new Map();
  const first=await harness(false,storage);
  first.node.onExecuted({workflowx_preview_token:['one'],workflowx_preview_count:[2]});
  await first.node._viewButtons[0].events.click();
  assert.deepEqual(first.pickers.map(p=>p.suggestedName),['ComfyUI_00001_.png','ComfyUI_00002_.png']);
  const next=await harness(false,storage);
  next.node.onExecuted({workflowx_preview_token:['two']});
  await next.node._viewButtons[1].events.click();
  assert.equal(next.pickers[0].suggestedName,'ComfyUI_00003_.jpg');
});
