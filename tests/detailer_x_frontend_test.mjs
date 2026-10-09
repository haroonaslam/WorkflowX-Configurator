import test from "node:test";
import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import * as stateModule from "../web/js/detailer_x_state.mjs";
import {restore,serialize,rows,minimumSize,bodyHeight,MIN_WIDTH,reconcileOutputSlots} from "../web/js/detailer_x_state.mjs";
const defaults={version:1,cache_epoch:0,ui:{realism_collapsed:false},face:{denoise:.15,enabled:true},sam:{model:"internal:sams/model.pth",device:"Prefer GPU"}};
async function entryHarness(fetchApi){
  const source=await readFile(new URL("../web/js/detailer_x.js",import.meta.url),"utf8");
  const store=new Map(),storage={getItem:k=>store.get(k),setItem:(k,v)=>store.set(k,v),key:i=>[...store.keys()][i],get length(){return store.size;}};
  const app={graph:{id:"graph-A"}},api={clientId:"new-client",fetchApi};
  const body="function updateStatus(){};"+source.slice(source.indexOf("function entryOwner("),source.indexOf("async function entryRequest("));
  const helpers=new Function("app","api","sessionStorage","crypto","updateEntry","TYPE",body+";return {entryOwner,entryOwners,acceptEntry,acceptProgress,pollEntry};")(app,api,storage,{randomUUID:()=>"fresh-owner"},node=>{node.updated=true;},"WorkflowX_DetailerX");
  return {...helpers,store,app,api,node:{id:624,graph:app.graph,_dx:{}}};
}
test("entry status recovers tab-local owner after client reconnect",async()=>{
  const h=await entryHarness(async url=>({ok:true,json:async()=>url.includes("old-owner")?{owner:"old-owner",state:"paused",token:"run",revision:3}:{state:"ready"}}));
  h.store.set("workflowx.dx.entry:old-client::graph-A:624","old-owner");
  h.store.set("workflowx.dx.entry:old-client::graph-B:624","wrong-graph");
  await h.pollEntry(h.node);
  assert.equal(h.node._dx.entry.state,"paused");assert.equal(h.node._dx.owner,"old-owner");
  assert.equal(h.node._dx.entryRevision,3);assert.ok(!h.entryOwners(h.node).includes("wrong-graph"));
  h.acceptEntry(h.node,{owner:"wrong-graph",state:"completed"});assert.equal(h.node._dx.entry.state,"paused");
});
test("late Resume acknowledgement cannot restore countdown after processing",async()=>{
  const h=await entryHarness(async()=>{}),paused={owner:'fresh-owner',token:'run-1',state:'paused',remaining:120};
  h.acceptEntry(h.node,paused);
  h.acceptEntry(h.node,{...paused,state:'processing',remaining:null});
  h.acceptEntry(h.node,paused);
  assert.equal(h.node._dx.entry.state,'processing');assert.equal(h.node._dx.entryDeadline,null);
  h.acceptEntry(h.node,{...paused,token:'run-2'});
  assert.equal(h.node._dx.entry.state,'paused');
  h.acceptProgress(h.node,{stage:'face',state:'processing',message:'Face sampling'});
  h.acceptEntry(h.node,{...paused,token:'run-2'});
  assert.equal(h.node._dx.entry.state,'processing');assert.equal(h.node._dx.entryDeadline,null);
  assert.equal(h.node._dx.message,'Face sampling');
  h.acceptProgress(h.node,{stage:'complete',state:'complete',message:'Finished'});
  assert.equal(h.node._dx.entry.state,'completed');
});
test("countdown interval only renders; recovery is event driven",async()=>{
  const source=await readFile(new URL("../web/js/detailer_x.js",import.meta.url),"utf8");
  const timer=source.slice(source.indexOf('window.setInterval('),source.indexOf('function recoverEntries('));
  assert.match(timer,/updateEntry\(node\)/);
  assert.doesNotMatch(timer,/pollEntry|fetchApi|entryRequest/);
  assert.match(source,/addEventListener\("reconnected",recoverEntries\)/);
  const h=await entryHarness(async()=>{});
  h.acceptEntry(h.node,{owner:'fresh-owner',state:'paused',remaining:10});
  assert.ok(h.node._dx.entryDeadline>Date.now()+9000);
  h.acceptEntry(h.node,{owner:'fresh-owner',state:'processing',remaining:null});
  assert.equal(h.node._dx.entryDeadline,null);
});
test("entry polling shows failures and recovers instead of silently displaying Ready",async()=>{
  const h=await entryHarness(async()=>{throw new Error("offline");});
  await h.pollEntry(h.node);assert.match(h.node._dx.entryConnectionError,/offline/);assert.equal(h.node._dx.entryPolling,false);
  h.api.fetchApi=async()=>({ok:true,json:async()=>({owner:"fresh-owner",state:"paused",token:"run"})});
  await h.pollEntry(h.node);assert.equal(h.node._dx.entryConnectionError,null);assert.equal(h.node._dx.entry.state,"paused");
});
test("queue recovery requires matching client and workflow",async()=>{
  for(const same of [false,true]){
    const h=await entryHarness(async url=>({ok:true,json:async()=>url==="/queue"?{queue_running:[[0,"job",{"624":{class_type:"WorkflowX_DetailerX",inputs:{settings:JSON.stringify({_control:{owner:"queued-owner"},_run:"token"})}}},{client_id:same?"new-client":"other-client",extra_pnginfo:{workflow:{id:"graph-A"}}}]]}:url.includes("queued-owner")?{owner:"queued-owner",state:"paused",token:"token"}:{state:"ready"}}));
    await h.pollEntry(h.node);assert.equal(h.node._dx.entry.state,same?"paused":"ready");
  }
});
test("confirmed pause enables Resume and Cancel; processing and lost connection disable them",async()=>{
  const source=await readFile(new URL("../web/js/detailer_x.js",import.meta.url),"utf8");
  const body=source.slice(source.indexOf("function updateEntry("),source.indexOf("function renderEntry("));
  const update=new Function("updateStatus","updateRefineButtons",body+";return updateEntry;")(()=>{},()=>{});
  const entryButtons=Object.fromEntries(["pause","skip","resume","cancel","rerun"].map(k=>[k,{setAttribute(){}}]));
  const node={_dx:{entryPanel:{},entry:{state:"paused",remaining:45},state:{entry:{pause:true,skip:false}},entryButtons}};
  update(node);assert.equal(entryButtons.resume.disabled,false);assert.equal(entryButtons.cancel.disabled,false);
  assert.match(node._dx.entryText,/Paused/);
  node._dx.entryConnectionError="offline";update(node);assert.equal(entryButtons.resume.disabled,true);
  node._dx.entryConnectionError=null;node._dx.entry.state="processing";update(node);assert.equal(entryButtons.resume.disabled,true);
});
test("legacy Qwen display name migrates while preserving existing values",()=>{
  const preset={id:"qwen21",label:"Qwen 2.1 — Current workflow",values:{face:{denoise:.15}}};
  const state=restore({preset},defaults);
  assert.equal(state.preset.label,"Qwen 2.1");
  assert.deepEqual(state.preset.values.face,preset.values.face);
  assert.deepEqual(state.preset.values.hair,preset.values.face);
  assert.deepEqual(state.preset.values.anything,preset.values.face);
});
test("tooltips prefer panel sides and never clamp onto the active control",async()=>{
  const source=await readFile(new URL("../web/js/detailer_x.js",import.meta.url),"utf8");
  const body=source.slice(source.indexOf("function tooltipPosition("),source.indexOf("function help("));
  const place=new Function(body+";return tooltipPosition;")();
  const r={left:400,right:450,top:400,bottom:430},t={width:300,height:100};
  assert.equal(place(r,{left:200,right:500},t,1200,800).left,512);
  assert.equal(place(r,{left:400,right:1000},t,1100,800).left,88);
  const p=place(r,{left:0,right:800},t,800,480);
  assert.ok(p.top+t.height<r.top);
});
test("configuration roundtrip and copies are isolated",()=>{
  const a=restore("{}",defaults);a.face.denoise=.3;a.sam.device="CPU";
  const b=restore(serialize(a),defaults);assert.deepEqual(a,b);b.face.denoise=.8;assert.equal(a.face.denoise,.3);assert.equal(defaults.face.denoise,.15);
});
test("missing fields migrate and unsupported version rejects",()=>{
  assert.equal(restore('{"face":{"denoise":0.5}}',defaults).face.enabled,true);
  assert.throws(()=>restore('{"version":6}',defaults));
});
test("visibility transitions preserve settings and hidden order positions",()=>{
  const full={...defaults,...Object.fromEntries(stateModule.ORDER.map(n=>[n,{enabled:true,marker:n}]))};
  const s=restore('{}',full),original=[...s.order];
  stateModule.applyVisibility(s,{...s.visible});assert.equal(s.face.enabled,true);
  stateModule.applyVisibility(s,{...s.visible,face:false});assert.equal(s.face.enabled,false);
  stateModule.moveVisible(s,'upscaler','breast');assert.equal(s.order[1],'face');
  stateModule.applyVisibility(s,{...s.visible,face:true,gamma:true});
  assert.equal(s.face.enabled,false);assert.equal(s.gamma.enabled,false);assert.equal(s.face.marker,'face');
  assert.deepEqual(restore(serialize(s),full),s);
  const legacy=restore({version:2,realism:{enabled:false},ui:{realism_collapsed:true}},full);
  assert.ok(stateModule.LEGACY_REALISM.every(n=>!legacy[n].enabled&&legacy.visible[n]));
  assert.deepEqual(legacy.order,original);
});
test("v4 dynamic detailers serialize, hide, and reorder like processors",()=>{
  const full={...structuredClone(defaults),version:4,extra_detailers:{},...Object.fromEntries(stateModule.ORDER.map(n=>[n,{enabled:false}]))};
  const s=restore({},full),id="detailer:eye";s.extra_detailers[id]={...structuredClone(s.anything),label:"Eye detailer",enabled:true};
  s.order.splice(s.order.indexOf("brightness"),0,id);s.visible[id]=true;
  assert.equal(stateModule.labelFor(s,id),"Eye detailer");assert.ok(stateModule.rows(s).includes(id));
  stateModule.moveVisible(s,id,"face");assert.ok(s.order.indexOf(id)<s.order.indexOf("face"));
  stateModule.applyVisibility(s,{...s.visible,[id]:false});assert.equal(s.extra_detailers[id].enabled,false);
  const loaded=restore(serialize(s),full);assert.equal(loaded.extra_detailers[id].label,"Eye detailer");assert.ok(!stateModule.rows(loaded).includes(id));
});
test("global seed override survives frontend roundtrip",()=>{
  const full={...structuredClone(defaults),version:4,global_seed:{enabled:false,mode:"fixed",seed:1},extra_detailers:{}};
  const s=restore({},full);s.global_seed={enabled:true,mode:"random",seed:42};
  assert.deepEqual(restore(serialize(s),full).global_seed,s.global_seed);
});
test("v3 preset migration backfills new detailers without treating seeds or toggles as model edits",()=>{
  const sampling=Object.fromEntries(stateModule.PRESET_FIELDS.map((key,index)=>[key,key==="guidance_mode"?"incoming":key==="sampler_name"?"euler":key==="scheduler"?"simple":index+1]));
  const full={...structuredClone(defaults),version:4,global_seed:{enabled:false,mode:"fixed",seed:1},extra_detailers:{},preset:{id:"qwen21",label:"Qwen 2.1",family:"qwen",revision:1,values:{}}};
  for(const name of stateModule.DETAILERS)full[name]={...structuredClone(sampling),enabled:name==="face"};
  full.preset.values=Object.fromEntries(stateModule.DETAILERS.map(name=>[name,structuredClone(sampling)]));
  const legacyPreset={id:"qwen21",label:"Qwen 2.1",family:"qwen",revision:1,values:Object.fromEntries(stateModule.OUTPUT_DETAILERS.map(name=>[name,structuredClone(sampling)]))};
  const state=restore({version:3,preset:legacyPreset},full);
  assert.deepEqual(state.preset.values.hair,state.preset.values.hand);
  assert.deepEqual(state.preset.values.anything,state.preset.values.hand);
  assert.equal(stateModule.modified(state),false);
  state.global_seed.enabled=true;state.hair.enabled=true;state.anything.enabled=true;
  assert.equal(stateModule.modified(state),false);
});
test("global SAM is tabbed and detailer gears expose inherited or overridden masking",async()=>{
  const source=await readFile(new URL("../web/js/detailer_x.js",import.meta.url),"utf8");
  const settings=source.slice(source.indexOf("function nodeSettings("),source.indexOf("function additionalDetailers("));
  const gear=source.slice(source.indexOf("function gear("),source.indexOf("function classSelector("));
  for(const label of ["Flow","Seed","Detailers","SAM"])assert.match(settings,new RegExp(`\\[\\"[^\\]]*\\"${label}\\"`));
  assert.match(settings,/state\.sam=shared/);
  assert.match(settings,/role\",\"tablist/);
  assert.match(settings,/ArrowRight/);
  assert.doesNotMatch(gear,/state\.sam=/);
  for(const token of ["Masking strategy","sam_strategy","sam_override","sam3_constraint","Use selected class concept"])assert.match(gear,new RegExp(token));
  assert.match(source,/bbox_controlled:"BBox controlled"/);
  assert.match(gear,/!\["concept_only","bbox_controlled"\]\.includes\(draft\.sam3_mode\)/);
  assert.match(gear,/draft\.sam3_mode!=="refine_detector"/);
});
test("repeatable custom detailers and gear lifecycle controls are exposed",async()=>{
  const source=await readFile(new URL("../web/js/detailer_x.js",import.meta.url),"utf8");
  for(const token of ["Create Custom Detailer","detailer:custom:","crypto.randomUUID","Hide processor","Delete custom"])assert.match(source,new RegExp(token));
  assert.match(source,/structuredClone\(state\.anything\)/);
  assert.match(source,/cache_epoch=\(node\._dx\.state\.cache_epoch\|\|0\)\+1/);
});
test("SAM-only edits do not mark the model preset modified",()=>{
  const s=restore("{}",defaults);assert.equal(stateModule.modified(s),false);
  s.face.sam_strategy="override";s.face.sam_override.backend="sam3.1";s.face.mask_concept="hair";
  assert.equal(stateModule.modified(s),false);
});
test("expanded and collapsed layouts reserve slots and all rows",()=>{
  const a=restore("{}",defaults);assert.equal(rows(a).length,14);assert.equal(minimumSize(a)[0],MIN_WIDTH);
  assert.ok(minimumSize(a)[1]>bodyHeight(a)+6*20);
  a.ui.realism_collapsed=true;assert.equal(rows(a).length,14);assert.equal(bodyHeight(a),15*36+132);
});
test("entry toolbar has no inline image display or image fetch",async()=>{
  const source=await readFile(new URL("../web/js/detailer_x.js",import.meta.url),"utf8");
  assert.doesNotMatch(source,/dx-entry-preview|entryPreview|entry\/image|previewIndex/);
  assert.match(source,/x.entryPanel.append\(toolbar\)/);
  assert.doesNotMatch(source,/dx-entry-message|x.entryMessage/);
});
test("DetailerX Preview exposes named stage, batch, and comparison controls",async()=>{
  const source=await readFile(new URL("../web/js/detailer_x_preview.js",import.meta.url),"utf8");
  assert.match(source,/WorkflowX_DetailerXPreview/);
  assert.match(source,/Compare: Original/);
  assert.match(source,/Compare: Previous processor/);
  assert.match(source,/Side by side/);
  assert.match(source,/Previous processor stage/);
  assert.match(source,/Next image in batch/);
  assert.match(source,/Enlarge/);
  assert.match(source,/Move the mouse over the image to compare/);
  assert.match(source,/pointermove/);
  assert.match(source,/Zoom out/);
  assert.match(source,/Show one image pixel per screen pixel/);
  assert.match(source,/ResizeObserver/);
  assert.match(source,/Number\.isFinite\(state\.modalZoom\)\?state\.modalZoom:1/);
  assert.match(source,/state\.modalZoom=zoom/);
  assert.doesNotMatch(source,/function move(?:Stage|Batch)[^{]*\{[^}]*zoom=1/);
});
test("DetailerX Masks exposes detector, SAM-refined, and blend overlays",async()=>{
  const source=await readFile(new URL("../web/js/detailer_x_masks.js",import.meta.url),"utf8");
  for(const token of ["WorkflowX_DetailerXMasks","Detector proposal","SAM-refined mask","Final blend mask","Mask overlay opacity","workflowx_detailer_masks"])assert.match(source,new RegExp(token));
  assert.doesNotMatch(source,/Compare: Original|Compare: Previous/);
});
test("legacy cumulative sockets reconcile to the structured output contract",()=>{
  const old=["upscaler_image","face_detailer_image","breast_detailer_image","pussy_detailer_image","hand_detailer_image","foot_detailer_image","realism_detailer_image","dlss5_image","final_image"].map((name,index)=>({name,type:"IMAGE",links:[100+index]}));
  const migrated=reconcileOutputSlots(old);
  assert.deepEqual(migrated.outputs.map(item=>[item.name,item.type]),[["final_image","IMAGE"],["processor_images","DETAILERX_PROCESSOR_IMAGES"],["detailer_masks","DETAILERX_MASKS"]]);
  assert.deepEqual(migrated.outputs[0].links,[108]);
  assert.equal(migrated.outputs[1].links.length,0);
  assert.deepEqual(migrated.keptLinks,[{id:108,slot:0}]);
  assert.deepEqual(migrated.staleLinks,[100,101,102,103,104,105,106,107]);
});

test("rerenders fit height to current content instead of accumulating prior height",async()=>{
  const source=await readFile(new URL("../web/js/detailer_x.js",import.meta.url),"utf8");
  const fit=source.slice(source.indexOf("function fit(node)"),source.indexOf("function report(node,error)"));
  assert.match(fit,/node\.setSize\(\[Math\.max\([\s\S]*?size\[0\]\),size\[1\]\]\)/);
  assert.doesNotMatch(fit,/node\.size\[1\].*\+delta|bodyHeight==null/);
});
test("Pause and Skip persist through serialization and legacy defaults are off",()=>{
  const state=restore('{}',defaults);
  assert.equal(state.entry.pause,false);assert.equal(state.entry.skip,false);
  state.entry.pause=true;state.entry.skip=true;
  const saved=restore(serialize(state),defaults);
  assert.equal(saved.entry.pause,true);assert.equal(saved.entry.skip,true);
});
test("Rerun communicates its one-execution Skip override",async()=>{
  const source=await readFile(new URL("../web/js/detailer_x.js",import.meta.url),"utf8");
  assert.match(source,/state==="queued"&&x\.state\.entry\.skip\?" · Skip overridden"/);
  assert.match(source,/Pause and Skip are bypassed for this run/);
  assert.match(source,/Skip: persistent bypass for ordinary queues and Resume/);
});

test("Rerun detects an image link and supports connected-input fallback",async()=>{
  const source=await readFile(new URL("../web/js/detailer_x.js",import.meta.url),"utf8");
  const body=source.slice(source.indexOf("function inputConnected("),source.indexOf("async function connectedRerun("));
  const connected=new Function(body+";return inputConnected;")();
  assert.equal(connected({inputs:[{name:"image",link:7}]},"image"),true);
  assert.equal(connected({inputs:[{name:"image",link:null}]},"image"),false);
  assert.match(source,/Image input not detected/);
  assert.match(source,/connected_rerun/);
  assert.match(source,/connected_selective_rerun/);
  assert.match(source,/required upstream dependencies and downstream consumers/);
  assert.match(source,/x\.entry=\{\.\.\.x\.entry,\.\.\.queued,state:"queued"/);
});
test("processor rows expose selective original, mask-reuse, and remask actions",async()=>{
  const source=await readFile(new URL("../web/js/detailer_x.js",import.meta.url),"utf8");
  assert.match(source,/selective_rerun/);
  assert.match(source,/Refine Original/);
  assert.match(source,/Refine Output — Reuse Mask/);
  assert.match(source,/Refine Output — Remask/);
  assert.match(source,/Latest DetailerX output is unavailable/);
  assert.match(source,/className="dx-refine-menu"|"dx-refine-menu"/);
  assert.match(source,/setAttribute\("role","menuitem"\)/);
  assert.match(source,/button\("▶",\(\)=>selectiveMenu\(node,name,refine\)/);
  assert.doesNotMatch(source,/dialog\(`Refine \$\{label\}`/);
  assert.match(source,/Keep the menu discoverable even before a retained run exists/);
  assert.match(source,/setAttribute\("aria-disabled",String\(!available\)\)/);
  assert.doesNotMatch(source,/available=!!x\.entry\?\.can_refine_original&&!busy/);
  assert.match(source,/if\(activeRefineAnchor===anchor\)\{dismissRefineMenu\(\);return;\}/);
  assert.match(source,/connectedOriginal=source==="original"&&!x\.entry\?\.can_refine_original/);
  assert.match(source,/can_refine_original\|\|inputConnected\(node,"image"\)/);
});

test("preset application replaces only model fields, isolates copies and tracks local edits",()=>{
  const state={...structuredClone(defaults),preset:{id:"old"}};
  for(const n of stateModule.DETAILERS)state[n]={enabled:false,detector:"keep",seed:123,prompt:"keep",denoise:.15,steps:15,cfg:2};
  const before=structuredClone(state);
  const profile={id:"new",label:"Test",family:"sdxl",revision:2,values:stateModule.presetValues(state)};
  for(const n of stateModule.DETAILERS)profile.values[n].cfg=5;
  stateModule.applyPreset(state,profile);
  assert.equal(stateModule.modified(state),false);
  for(const n of stateModule.DETAILERS){assert.equal(state[n].cfg,5);assert.equal(state[n].enabled,false);assert.equal(state[n].detector,"keep");assert.equal(state[n].seed,123);assert.equal(state[n].prompt,"keep");}
  state.face.cfg=6;assert.equal(stateModule.modified(state),true);assert.equal(profile.values.face.cfg,5);
  const loaded=restore(serialize(state),state);assert.equal(loaded.face.cfg,6);assert.equal(loaded.preset.values.face.cfg,5);assert.equal(stateModule.modified(loaded),true);
  const custom=stateModule.customPreset(state);stateModule.applyPreset(state,custom);assert.equal(stateModule.modified(state),false);
  assert.deepEqual(state.sam,before.sam);
});

test("all preset controls have meaningful help",()=>{
  for(const key of stateModule.PRESET_FIELDS)assert.ok(stateModule.helpText("face",key).length>35,key);
  assert.match(stateModule.helpText("face","cfg"),/negative prompting has no effect/);
  assert.match(stateModule.helpText("face","guidance"),/not the CFG/);
});
test("DLSS controls distinguish NR preset, carrier model preset, and post-composite",async()=>{
  const source=await readFile(new URL("../web/js/detailer_x.js",import.meta.url),"utf8");
  for(const token of ['preset:{0:"Default",1:"Preset #1",2:"Preset #2",3:"Preset #3"}','model_preset:{Default:"Default — runtime choice"','Post-composite','not additional DLSS model parameters'])assert.match(source,new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")));
  assert.match(stateModule.helpText("dlss5","intensity"),/nr_intensity/);
  assert.match(stateModule.helpText("dlss5","model_preset"),/Super Resolution model/);
  assert.match(stateModule.helpText("dlss5","detail"),/after DLSS finishes/);
  assert.match(stateModule.helpText("dlss5","color"),/Post-composite chroma/);
});
test("SAM1 detection hints expose descriptive labels and contextual help",async()=>{
  const source=await readFile(new URL("../web/js/detailer_x.js",import.meta.url),"utf8");
  const help=await readFile(new URL("../web/js/detailer_x_help.mjs",import.meta.url),"utf8");
  for(const token of ["general default","wide target","tall target","use SEGM shape","small target","box only"])assert.match(source,new RegExp(token));
  for(const token of ["Center-1:","Horizontal-2:","Vertical-2:","Rect-4:","Diamond-4:","Mask-area:","Mask-points:","Mask-point-bbox:","None:"])assert.match(help,new RegExp(token));
  assert.match(source,/helpText\(section,key,object\[key\]\)/);
});
test("detailer proposal selector exposes native segmentation and forced bbox modes",async()=>{
  const source=await readFile(new URL("../web/js/detailer_x.js",import.meta.url),"utf8");
  const help=await readFile(new URL("../web/js/detailer_x_help.mjs",import.meta.url),"utf8");
  assert.match(source,/detector_proposal:\{native:"Native — use SEGM shape",bbox:"Bounding box — force rectangle"\}/);
  assert.match(help,/Bounding box replaces it with a solid rectangle before dilation/);
});

test("real extension hooks preserve inline values in API, save/load, and clone",async()=>{
  class Element {
    constructor(tag){this.tag=tag;this.children=[];this.listeners={};this.style={};this.classList={add(){}};this.attributes={};}
    append(...elements){this.children.push(...elements);}
    replaceChildren(...elements){this.children=elements;}
    addEventListener(name,fn){(this.listeners[name]??=[]).push(fn);}
    setAttribute(key,value){this.attributes[key]=value;}
    checkValidity(){return true;}
    remove(){}
  }
  const full={...structuredClone(defaults),upscaler:{enabled:true,model:"internal:upscale_models/model.pth"},realism:{enabled:true},dlss5:{enabled:true,upscaling_mode:"native"}};
  for(const name of stateModule.DETAILERS)full[name]={enabled:true,denoise:.15};
  for(const name of stateModule.REALISM)full[name]={enabled:true};
  let extension,progressHandler;
  const app={registerExtension(value){extension=value;},graph:{change(){}}};
  const api={addEventListener(name,fn){progressHandler=fn;},async fetchApi(){return {ok:true,json:async()=>({defaults:full,choices:{upscaling_mode:["native"]},ranges:{},assets:{}})};}};
  const document={createElement:tag=>new Element(tag),getElementById:()=>null,head:new Element("head")};
  const source=(await readFile(new URL("../web/js/detailer_x.js",import.meta.url),"utf8")).replace(/^import .*;\r?$/gm,"");
  new Function("app","api","document",...Object.keys(stateModule),source)(app,api,document,...Object.values(stateModule));
  class Node {
    constructor(){this.widgets=[{name:"settings",value:JSON.stringify(full),inputEl:{style:{}},serializeValue:()=>JSON.stringify(full)}];this.size=[300,200];this.inputs=Array(6);this.outputs=Array(2);this.properties={};this.onNodeCreated();}
    setSize(size){this.size=size;}
    setDirtyCanvas(){}
    addDOMWidget(name,type,element,options){const w={name,type,element,options};this.widgets.push(w);return w;}
    onConfigure(info){this.properties=structuredClone(info.properties||{});this.widgets[0].value=info.widgets_values[0];}
  }
  await extension.beforeRegisterNodeDef(Node,{name:"WorkflowX_DetailerX"});
  const original=new Node();
  original.id=42;
  progressHandler({detail:{node:"42",stage:"face",state:"processing",message:"Face detailer — Sampling step 3/15"}});
  assert.equal(original._dx.status.textContent,"Face detailer — Sampling step 3/15");
  assert.ok(!original.widgets[0].serializeValue().includes("Sampling step"));
  function find(element,label){if(element.attributes?.["aria-label"]===label)return element;for(const child of element.children||[]){const result=find(child,label);if(result)return result;}}
  const inline=find(original._dx.root,"Face detailer denoise");inline.value="0.37";
  for(const fn of inline.listeners.input)fn();
  assert.equal(original._dx.state.face.denoise,.37);
  assert.equal(JSON.parse(await original.widgets[0].serializeValue()).face.denoise,.37);
  const saved={};original.onSerialize(saved);
  const clone=new Node();clone.onConfigure(JSON.parse(JSON.stringify(saved)));
  assert.equal(clone._dx.state.face.denoise,.37);
  assert.equal(JSON.parse(await clone.widgets[0].serializeValue()).face.denoise,.37);
  clone._dx.state.face.denoise=.8;assert.equal(original._dx.state.face.denoise,.37);
  assert.ok(original.size.every(Number.isFinite));
});
