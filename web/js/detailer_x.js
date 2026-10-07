import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { DETAILERS, REALISM, ORDER, applyVisibility, moveVisible, LABELS, MIN_WIDTH, PRESET_FIELDS, presetValues, modified, applyPreset, customPreset, helpText, restore, serialize, rows, bodyHeight, minimumSize,detailerNames,isDetailer,stage,labelFor,reconcileOutputSlots } from "./detailer_x_state.mjs?v=19";

const TYPE="WorkflowX_DetailerX";
let metadata;
const instances=new Set();
const STYLE=`
.dx-root,.dx-dialog{font:13px/1.4 system-ui,sans-serif;color:var(--input-text,#e9edf5);box-sizing:border-box}
.dx-root *,.dx-dialog *{box-sizing:border-box;min-width:0}
.dx-root{padding:8px;width:100%;height:100%;overflow:auto;background:var(--comfy-menu-bg,#252932);border:1px solid #59616e;border-radius:10px}
.dx-row{display:grid;grid-template-columns:22px 28px minmax(110px,1fr) minmax(110px,1.25fr) 26px 28px;align-items:center;gap:7px;min-height:36px;border-bottom:1px solid #ffffff12}
.dx-row .dx-drag{cursor:grab;padding:0;min-width:22px}.dx-row[data-drop=true]{border-top:3px solid #a9bdff}.dx-citation{flex-basis:100%;font-size:11px}.dx-citation a{color:#b5caff}
.dx-row.dx-sub{padding-left:12px}.dx-row.dx-off .dx-label{opacity:.6}
.dx-root button,.dx-root input,.dx-dialog button,.dx-dialog input,.dx-dialog select,.dx-dialog textarea{font:inherit;color:inherit;background:var(--comfy-input-bg,#191e26);border:1px solid #626c7d;border-radius:6px;min-height:30px;padding:5px 8px}
.dx-root button,.dx-dialog button{cursor:pointer}.dx-root button:hover,.dx-dialog button:hover{border-color:#9aaef4;background:#394255}
.dx-root :focus-visible,.dx-dialog :focus-visible{outline:2px solid #a9bdff;outline-offset:2px}
.dx-toggle{width:28px;height:28px;padding:0!important;border-radius:50%!important;justify-self:center}
.dx-toggle[aria-checked=true]{background:#8fa8e8!important;border-color:#b8c8fc!important;color:#111827}
.dx-label{overflow-wrap:anywhere}.dx-model{overflow:hidden;white-space:nowrap;text-overflow:ellipsis;text-align:left;width:100%}
.dx-number{display:flex;align-items:center;gap:6px;justify-content:flex-end}.dx-number span{font-size:11px;color:#b9c2d1}.dx-number input{width:78px}
.dx-root .dx-gear{padding:2px;font-size:18px;width:30px}.dx-footer{display:flex;gap:8px;align-items:center;padding-top:10px}.dx-status{flex:1;overflow-wrap:anywhere;color:#b8c6e2;font-size:12px}
.dx-root .dx-row button,.dx-root .dx-row input{min-height:26px;height:26px;padding:2px 7px}
.dx-root .dx-row .dx-toggle{width:24px;height:24px;min-height:24px}
.dx-root .dx-row .dx-drag{padding:0;width:22px}
.dx-root .dx-row .dx-gear{padding:0;width:26px;font-size:16px}
.dx-root .dx-row .dx-refine{padding:0;width:26px;font-size:13px}
.dx-refine-menu{position:fixed;inset:auto;margin:0;z-index:2147483646;width:max-content;min-width:210px;max-width:min(320px,calc(100vw - 16px));padding:5px;border:1px solid #69768d;border-radius:8px;background:var(--comfy-menu-bg,#242932);box-shadow:0 8px 24px #000a;font:13px/1.35 system-ui,sans-serif;color:var(--input-text,#e9edf5)}
.dx-refine-menu button{display:block;width:100%;min-height:30px;padding:5px 9px;border:0;border-radius:5px;background:transparent;color:inherit;text-align:left;white-space:nowrap;cursor:pointer}
.dx-refine-menu button:hover,.dx-refine-menu button:focus-visible{background:#405783;outline:1px solid #95acf3}.dx-refine-menu button[aria-disabled=true]{opacity:.45}
.dx-dialog{padding:0;border:1px solid #69768d;border-radius:12px;background:var(--comfy-menu-bg,#242932);width:min(680px,calc(100vw - 24px));max-height:calc(100dvh - 24px);overflow:hidden}
.dx-dialog::backdrop{background:#080b12aa}.dx-dialog form{display:flex;flex-direction:column;max-height:calc(100dvh - 26px)}
.dx-dialog header{padding:18px 20px 12px;border-bottom:1px solid #ffffff20}.dx-dialog h2{margin:0;font-size:18px}.dx-dialog p{margin:8px 0 0;color:#b9c5da;font-size:12px}
.dx-body{padding:16px 20px;overflow:auto;overscroll-behavior:contain}.dx-field{display:grid;grid-template-columns:minmax(130px,1fr) minmax(160px,1.4fr);gap:12px;align-items:center;margin:0 0 12px}.dx-field>span{overflow-wrap:anywhere}.dx-field textarea{min-height:100px;resize:vertical;width:100%}
.dx-field input:not([type=checkbox]),.dx-field select{width:100%}.dx-field input[type=checkbox]{width:18px;height:18px;justify-self:start}
.dx-dialog footer{display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap;padding:12px 20px;border-top:1px solid #ffffff20}.dx-dialog footer button:first-child{margin-right:auto}
.dx-dialog .dx-primary{background:#405783;border-color:#95acf3}.dx-dialog fieldset{border:1px solid #68768a;border-radius:8px;margin:20px 0 0;padding:12px}.dx-dialog legend{padding:0 8px;font-weight:600}.dx-error{color:#ffb0b0;white-space:pre-wrap}
.dx-tabs{position:sticky;top:-16px;z-index:2;display:flex;gap:4px;margin:-16px -20px 16px;padding:12px 20px 0;background:var(--comfy-menu-bg,#242932);border-bottom:1px solid #ffffff20;overflow-x:auto}.dx-tabs button{border-radius:7px 7px 0 0;border-bottom-color:transparent;white-space:nowrap}.dx-tabs button[aria-selected=true]{background:#405783;border-color:#95acf3;border-bottom-color:#405783}.dx-tab-panel{min-height:290px}.dx-section-note{margin:0 0 16px;color:#b9c5da;font-size:12px}
.dx-options{display:flex;flex-direction:column;gap:5px;margin-top:12px;max-height:50vh;overflow:auto}.dx-options button{text-align:left;overflow-wrap:anywhere;white-space:normal}.dx-search{width:100%}
.dx-preset{grid-template-columns:minmax(120px,1fr) minmax(200px,2fr) 28px;border-bottom:1px solid #9aaef477;margin-bottom:4px}.dx-help{margin:0 0 12px;color:#b9c5da;font-size:12px;overflow-wrap:anywhere}
.dx-row[data-run-state=processing]{background:#6d91e324;box-shadow:inset 3px 0 #9ab8ff}.dx-row[data-run-state=failed]{background:#d7454526;box-shadow:inset 3px 0 #ff9999}.dx-status{max-height:64px;overflow:auto;white-space:normal}.dx-footer{align-items:flex-start}
.dx-tooltip{position:fixed;inset:auto;margin:0;z-index:2147483647;width:max-content;max-width:min(340px,calc(100vw - 16px));padding:9px 12px;border:1px solid #8599b9;border-radius:7px;background:#171e2b;color:#eef3ff;font:12px/1.5 system-ui;pointer-events:none;box-shadow:0 4px 18px #0008;overflow:hidden}
@media(max-width:500px){.dx-field{grid-template-columns:1fr;gap:4px}.dx-body{padding:12px}.dx-dialog header{padding:12px}.dx-tabs{top:-12px;margin:-12px -12px 12px;padding:10px 12px 0}}
.dx-entry{min-height:36px;margin-bottom:8px;border-bottom:1px solid #ffffff25;padding-bottom:5px}
.dx-toolbar{display:flex;gap:6px;flex-wrap:wrap}.dx-toolbar button{min-width:38px}.dx-toolbar button:disabled{opacity:.35;cursor:default}
.dx-toolbar [aria-pressed=true]{background:#405783;border-color:#b4c6ff}
`;
function el(tag, className, text) { const e=document.createElement(tag); if(className)e.className=className; if(text!==undefined)e.textContent=text; return e; }
let dismissTooltip=()=>{};
let dismissRefineMenu=()=>{};
let activeRefineAnchor=null;
function tooltipPosition(r,p,t,w,h){
  const gap=12,edge=8,clamp=(v,max)=>Math.max(edge,Math.min(v,max));
  if(p.right+gap+t.width<=w-edge)return {left:p.right+gap,top:clamp(r.top,h-t.height-edge)};
  if(p.left-gap-t.width>=edge)return {left:p.left-gap-t.width,top:clamp(r.top,h-t.height-edge)};
  const above=r.top-gap-edge,below=h-r.bottom-gap-edge;
  const height=Math.max(0,Math.min(t.height,Math.max(above,below)));
  return {left:clamp(r.left,w-t.width-edge),top:above>=below?r.top-gap-height:r.bottom+gap,maxHeight:height};
}
function help(control,text){
  control.title="";control.setAttribute("aria-description",text);
  if(control._dxHelp)return control;
  control._dxHelp=true;
  let tip,timer;
  const hide=()=>{clearTimeout(timer);tip?.remove();tip=null;window.removeEventListener("scroll",hide,true);window.removeEventListener("resize",hide);};
  const show=()=>{hide();dismissTooltip();dismissTooltip=hide;if(!control.isConnected)return;
    control.title="";tip=el("div","dx-tooltip",control.getAttribute?.("aria-description")||text);tip.setAttribute("role","tooltip");
    const owner=control.closest?.("dialog")||document.body;if(!owner)return;owner.append(tip);
    // A manual popover escapes dialog clipping and transformed canvas coordinates.
    if(tip.showPopover){tip.setAttribute("popover","manual");tip.showPopover();}
    const r=control.getBoundingClientRect(),panel=control.closest?.(".dx-dialog,.dx-root")||control;
    const pos=tooltipPosition(r,panel.getBoundingClientRect(),tip.getBoundingClientRect(),window.innerWidth,window.innerHeight);
    tip.style.left=`${pos.left}px`;tip.style.top=`${pos.top}px`;
    if(pos.maxHeight!==undefined)tip.style.maxHeight=`${pos.maxHeight}px`;
    window.addEventListener("scroll",hide,true);window.addEventListener("resize",hide);
  };
  control.addEventListener("pointerenter",()=>{control.title="";timer=setTimeout(show,400);});
  control.addEventListener("focus",()=>{if(control.matches?.(":focus-visible"))show();});
  control.addEventListener("pointerleave",hide);control.addEventListener("blur",hide);control.addEventListener("pointerdown",hide);control.addEventListener("click",hide);control.addEventListener("keydown",e=>{if(e.key==="Escape")hide();});return control;
}
function button(text, action, cls="") {
  const b=el("button",cls,text); b.type="button"; b.addEventListener("click",action);
  const descriptions={"Cancel":"Close without applying unsaved changes.","Apply":"Apply these settings to this node only; reusable preset defaults are unchanged.","Save and Apply":"Save this preset to the local reusable library and apply it to this node. Other nodes retain their own snapshots.","Save As":"Create a separate reusable preset using this draft and apply it to this node.","Restore Built-in Defaults":"Reset this preset draft to its original shipped values. Save and Apply persists the restoration.","Reset to Saved Baseline":"Discard draft and node-local overrides, restoring the selected preset's saved snapshot.","Restore workflow defaults":"Reset this stage draft to the original Qwen workflow settings, not the selected model preset. Apply commits the change to this node.","Show adjustments ▾":"Expand individual realism controls without changing their enabled states.","Hide adjustments ▴":"Collapse individual realism controls without disabling their processing."};
  help(b,descriptions[text]||`Select ${text}.`);return b;
}
function title(key){return key.replaceAll("_"," ").replace(/\b\w/g,c=>c.toUpperCase());}
function dirty(node){node.setDirtyCanvas?.(true,true);app.graph?.change?.();}
function persist(node){const value=serialize(node._dx.state);node._dx.widget.value=value;if(node._dx.widget.inputEl)node._dx.widget.inputEl.value=value;node.properties??={};node.properties.detailer_x=JSON.parse(value);if(node._dx.presetButton)node._dx.presetButton.textContent=presetLabel(node._dx.state);dirty(node);syncEntry(node);}

function entryOwner(node){
  const x=node._dx;
  if(x.owner)return x.owner;
  const workflow=app.extensionManager?.workflow?.activeWorkflow?.path||app.workflowManager?.activeWorkflow?.path||"";
  const key=`workflowx.dx.entry:${api.clientId||"local"}:${workflow}:${node.graph?.id||app.graph?.id||"graph"}:${node.id}`;
  let owner;
  try{owner=sessionStorage.getItem(key);}catch{}
  owner ||= crypto.randomUUID();
  try{sessionStorage.setItem(key,owner);}catch{}
  return x.owner=owner;
}
function entryOwners(node){
  const owners=new Set([entryOwner(node)]);
  // Client IDs can change on reconnect. Recover only identities previously
  // issued in this browser tab for this exact graph and node (never by node ID alone).
  const suffix=`:${node.graph?.id||app.graph?.id||"graph"}:${node.id}`;
  if(suffix.startsWith(":graph:"))return [...owners];
  try{for(let i=0;i<sessionStorage.length;i++){
    const key=sessionStorage.key(i);
    if(key?.startsWith("workflowx.dx.entry:")&&key.endsWith(suffix)){
      const owner=sessionStorage.getItem(key);if(owner)owners.add(owner);
    }
  }}catch{}
  return [...owners].slice(0,16);
}
function acceptEntry(node,data){
  const x=node._dx;
  if(data.owner&&!entryOwners(node).includes(data.owner))return;
  // HTTP command acknowledgements can arrive after the processing WebSocket
  // event. A released execution cannot go back through its entry gate.
  if(data.token&&data.token===x.entry?.token&&
    ["processing","completed","passed","failed"].includes(x.entry.state)&&
    ["waiting","paused"].includes(data.state))return;
  if(data.owner)x.owner=data.owner;
  x.entry=data;x.entryRevision=Math.max(x.entryRevision||0,data.revision||0);
  x.entryDeadline=data.state==="paused"&&data.remaining!=null?Date.now()+data.remaining*1000:null;
  x.entryConnectionError=null;updateEntry(node);
}
function acceptProgress(node,data){
  const x=node._dx;
  x.progress=data;
  x.message=data.message||`${LABELS[data.stage]||title(data.stage)} · ${data.state}`;
  // Actual stage execution is proof that the entry wait has ended, even if
  // its status event was missed. Invalidate any in-flight recovery response.
  x.entryEventVersion=(x.entryEventVersion||0)+1;
  x.entry={...x.entry,state:data.state==="failed"||data.state==="cancelled"?"failed":data.stage==="complete"?"completed":"processing",remaining:null,can_rerun:false};
  x.entryDeadline=null;x.entryConnectionError=null;x.localError=null;
  updateEntry(node);
  updateStatus(node); // Also support servers without the entry toolbar capability.
}
async function recoverEntryOwner(node){
  const x=node._dx,graphId=app.graph?.id;
  if(!api.clientId||!graphId||Date.now()-(x.entryRecoveryAt||0)<5000)return null;
  x.entryRecoveryAt=Date.now();
  const response=await api.fetchApi("/queue",{cache:"no-store",signal:AbortSignal.timeout(5000)});
  if(!response.ok)return null;
  const queue=await response.json();
  // Require browser AND workflow identity, not a coincidentally equal node ID.
  for(const run of queue.queue_running||[]){
    const extra=run[3];
    if(extra?.client_id!==api.clientId||extra?.extra_pnginfo?.workflow?.id!==graphId)continue;
    const definition=run[2]?.[String(node.id)];
    if(definition?.class_type!==TYPE)continue;
    try{
      const raw=JSON.parse(definition.inputs.settings),owner=raw._control?.owner;
      if(owner&&raw._run){x.owner=owner;return owner;}
    }catch{}
  }
  return null;
}
async function pollEntry(node){
  const x=node._dx;if(x.entryPolling)return;x.entryPolling=true;
  const eventVersion=x.entryEventVersion||0;
  try{
    let data;
    for(const owner of entryOwners(node)){
      const response=await api.fetchApi(`/workflowx_configurator/detailer_x/entry?owner=${encodeURIComponent(owner)}`,{cache:"no-store",signal:AbortSignal.timeout(5000)});
      if(!response.ok)throw new Error(`Status request failed (${response.status})`);
      data=await response.json();
      if(data.state!=="ready")break;
    }
    if(data.state==="ready"){
      const recovered=await recoverEntryOwner(node);
      if(recovered){
        const response=await api.fetchApi(`/workflowx_configurator/detailer_x/entry?owner=${encodeURIComponent(recovered)}`,{cache:"no-store",signal:AbortSignal.timeout(5000)});
        if(!response.ok)throw new Error(`Status request failed (${response.status})`);
        data=await response.json();
      }
    }
    if(eventVersion===(x.entryEventVersion||0))acceptEntry(node,data);
  }catch(e){if(eventVersion===(x.entryEventVersion||0)){x.entryConnectionError=`Status unavailable — reconnecting: ${e.message}`;updateEntry(node);}}
  finally{x.entryPolling=false;}
}
async function entryRequest(node,action,extra={}){
  const x=node._dx;
  const response=await api.fetchApi("/workflowx_configurator/detailer_x/entry",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({owner:entryOwner(node),token:x.entry?.token,action,...extra})});
  const data=await response.json();if(!response.ok)throw new Error(data.error||"Entry command failed");return data;
}
function syncEntry(node){
  const x=node._dx;if(!metadata.entry_controls||x.entry?.state!=="paused")return;
  const revision=x.entryRevision=(x.entryRevision||x.entry.revision||0)+1;
  const settings=serialize(x.state);x.entrySync="Saving changes…";updateEntry(node);
  x.entryQueue=(x.entryQueue||Promise.resolve()).catch(()=>{}).then(async()=>{
    acceptEntry(node,await entryRequest(node,"update",{settings,revision}));
    if(revision===x.entryRevision)x.entrySync="Changes saved";
  }).catch(e=>{x.entrySync=e.message;}).finally(()=>updateEntry(node));
}
function updateStatus(node){
  const x=node._dx;if(!x?.status)return;
  const state=x.entry?.state;
  let text=x.entryText||"Ready";
  if(!state||state==="ready"||state==="processing")text=x.message||text;
  if(state==="completed"&&x.progress?.state==="complete")text=x.message||text;
  if(x.localError)text=x.localError;
  x.status.textContent=text;x.status.title=text;
  x.status.classList.toggle?.("dx-error",!!x.localError||state==="failed"||x.progress?.state==="failed");
}
function inputConnected(node,name){
  const input=node.inputs?.find?.(item=>item.name===name);
  return !!input&&(input.link!==null&&input.link!==undefined||Array.isArray(input.links)&&input.links.length>0);
}
async function connectedRerun(node,graph,target){
  const response=await api.fetchApi("/workflowx_configurator/detailer_x/connected_rerun",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({owner:entryOwner(node),target,prompt:graph.output,settings:serialize(node._dx.state),client_id:api.clientId,extra_data:{extra_pnginfo:{workflow:graph.workflow}}})});
  const data=await response.json();if(!response.ok)throw new Error(data.error||"Unable to queue the connected DetailerX branch");return data;
}
async function connectedSelectiveRun(node,graph,target,stageName){
  const response=await api.fetchApi("/workflowx_configurator/detailer_x/connected_selective_rerun",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({owner:entryOwner(node),target,prompt:graph.output,settings:serialize(node._dx.state),stage:stageName,client_id:api.clientId,extra_data:{extra_pnginfo:{workflow:graph.workflow}}})});
  const data=await response.json();if(!response.ok)throw new Error(data.error||"Unable to queue connected selective refinement");return data;
}
function updateRefineButtons(node){
  const x=node._dx;if(!x?.refineButtons)return;
  // Keep the menu discoverable even before a retained run exists. The dialog
  // explains which individual sources are unavailable instead of presenting
  // an apparently inert row control.
  const busy=["paused","processing","queued","waiting"].includes(x.entry?.state)||!!x.entryPending;
  for(const control of x.refineButtons)control.disabled=busy;
}
async function selectiveRun(node,stageName,source,maskMode){
  const x=node._dx;if(x.entryPending)return;
  const connectedOriginal=source==="original"&&!x.entry?.can_refine_original;
  if(connectedOriginal&&!inputConnected(node,"image"))throw new Error("Image input not detected — connect an IMAGE output to DetailerX.");
  if(source==="output"&&!x.entry?.can_refine_output)throw new Error("Latest DetailerX output is unavailable. Complete an ordinary run first.");
  const graph=await app.graphToPrompt();
  const target=Object.keys(graph.output).find(id=>{try{return JSON.parse(graph.output[id].inputs?.settings||"{}")._control?.owner===entryOwner(node);}catch{return false;}});
  if(!target)throw new Error("Cannot resolve this node in the current graph. Queue the ordinary workflow first.");
  x.localError=null;x.entryPending=true;updateEntry(node);
  try{
    if(connectedOriginal){
      const queued=await connectedSelectiveRun(node,graph,target,stageName);
      x.entry={...x.entry,...queued,state:"queued",can_rerun:false,can_refine_original:false,can_refine_output:false,queue_mode:"connected_selective"};
      x.message=`Queued selective refinement · ${labelFor(x.state,stageName)} · connected original input`;
      return;
    }
    const response=await api.fetchApi("/workflowx_configurator/detailer_x/selective_rerun",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({owner:entryOwner(node),token:x.entry.token,target,prompt:graph.output,settings:serialize(x.state),stage:stageName,source,mask_mode:maskMode,client_id:api.clientId,extra_data:{extra_pnginfo:{workflow:graph.workflow}}})});
    const data=await response.json();if(!response.ok)throw new Error(data.error||"Unable to queue selective refinement");
    x.entry={...x.entry,state:"queued",can_rerun:false,can_refine_original:false,can_refine_output:false,queue_mode:"selective"};
    x.message=`Queued selective refinement · ${labelFor(x.state,stageName)} · ${source==="original"?"original input":maskMode==="reuse"?"latest output · reuse mask":"latest output · remask"}`;
  }finally{x.entryPending=false;updateEntry(node);}
}
function selectiveMenu(node,stageName,anchor){
  const x=node._dx,detailer=isDetailer(x.state,stageName),label=labelFor(x.state,stageName);
  if(activeRefineAnchor===anchor){dismissRefineMenu();return;}
  dismissRefineMenu();dismissTooltip();
  const menu=el("div","dx-refine-menu");menu.setAttribute("role","menu");menu.setAttribute("aria-label",`Refine ${label}`);menu.tabIndex=-1;
  const choices=detailer?[
    ["Refine Original","original","remask","Run this detailer alone against the original DetailerX input and detect its regions normally."],
    ["Refine Output — Reuse Mask","output","reuse","Run against the latest output using this detailer's previous final blend mask. If unavailable, DetailerX remasks automatically."],
    ["Refine Output — Remask","output","remask","Run detection and SAM again against the latest output, then apply only this detailer."],
  ]:[
    ["Refine Original","original","remask","Run only this processor against the original DetailerX input."],
    ["Refine Output","output","remask","Run only this processor against the latest completed or selectively refined DetailerX output."],
  ];
  for(const [text,source,maskMode,description] of choices){
    const available=source==="original"?(!!x.entry?.can_refine_original||inputConnected(node,"image")):!!x.entry?.can_refine_output;
    const unavailable=source==="original"?"Connect an IMAGE output to DetailerX.":"Complete DetailerX once to create a latest output.";
    const explanation=available?description:`${description} Unavailable: ${unavailable}`;
    const action=button(text,()=>{close();if(available)selectiveRun(node,stageName,source,maskMode).catch(error=>report(node,error));else report(node,new Error(unavailable));});
    action.setAttribute("role","menuitem");action.setAttribute("aria-disabled",String(!available));help(action,explanation);menu.append(action);
  }
  document.body.append(menu);if(menu.showPopover){menu.setAttribute("popover","manual");menu.showPopover();}
  const edge=8,gap=4,a=anchor.getBoundingClientRect(),r=menu.getBoundingClientRect();
  const left=Math.max(edge,Math.min(a.right-r.width,window.innerWidth-r.width-edge));
  const top=a.bottom+gap+r.height<=window.innerHeight-edge?a.bottom+gap:Math.max(edge,a.top-gap-r.height);
  menu.style.left=`${left}px`;menu.style.top=`${top}px`;
  const outside=event=>{if(!menu.contains(event.target)&&event.target!==anchor)close();},key=event=>{
    if(event.key==="Escape"){event.preventDefault();close();anchor.focus();return;}
    if(!["ArrowDown","ArrowUp","Home","End"].includes(event.key))return;
    const items=[...menu.querySelectorAll("button")],current=items.indexOf(document.activeElement);if(!items.length)return;
    const index=event.key==="Home"?0:event.key==="End"?items.length-1:event.key==="ArrowDown"?(current+1)%items.length:(current<1?items.length-1:current-1);
    event.preventDefault();items[index].focus();
  };
  function close(){document.removeEventListener("pointerdown",outside,true);document.removeEventListener("keydown",key,true);window.removeEventListener("resize",close);window.removeEventListener("scroll",close,true);if(menu.matches?.(":popover-open"))menu.hidePopover();menu.remove();if(activeRefineAnchor===anchor)activeRefineAnchor=null;if(dismissRefineMenu===close)dismissRefineMenu=()=>{};}
  activeRefineAnchor=anchor;dismissRefineMenu=close;document.addEventListener("pointerdown",outside,true);document.addEventListener("keydown",key,true);window.addEventListener("resize",close);window.addEventListener("scroll",close,true);
  menu.focus({preventScroll:true});
}
function updateEntry(node){
  const x=node._dx;if(!x.entryPanel)return;
  const state=x.entry?.state||"ready",paused=state==="paused",busy=["processing","queued","waiting"].includes(state);
  const names={ready:"Ready",waiting:"Waiting for input",paused:"Paused",queued:x.entry?.queue_mode==="connected"?"Queued connected branch":["selective","connected_selective"].includes(x.entry?.queue_mode)?"Queued selective refinement":"Queued rerun",processing:"Processing",passed:"Passed through",completed:"Completed",failed:"Failed"};
  let text=(names[state]||state)+(state==="queued"&&x.state.entry.skip?" · Skip overridden":x.state.entry.skip?" · Skip enabled":"");
  if(paused){
    const remaining=x.entryDeadline==null?x.entry.remaining:Math.max(0,(x.entryDeadline-Date.now())/1000);
    text+=x.entry.error?" · Waiting for valid settings":remaining==null?" · Waiting indefinitely":remaining>0?` · Processing resumes in ${Math.ceil(remaining)}s`:" · Waiting for server to resume";
  }
  if(x.entrySync&&paused)text+=` · ${x.entrySync}`;
  if(x.entry?.error)text+=` · ${x.entry.error}`;
  if(x.entryConnectionError)text=x.entryConnectionError;
  x.entryText=text;updateStatus(node);
  x.entryButtons.pause.setAttribute("aria-pressed",String(x.state.entry.pause));
  x.entryButtons.skip.setAttribute("aria-pressed",String(x.state.entry.skip));
  x.entryButtons.skip.disabled=["processing","queued"].includes(state)||!!x.entryPending;
  for(const key of ["resume","cancel"])x.entryButtons[key].disabled=!paused||!!x.entryPending||!!x.entryConnectionError;
  x.entryButtons.rerun.disabled=busy||!!x.entryPending;
  updateRefineButtons(node);
}
function renderEntry(node){
  const x=node._dx;if(!metadata.entry_controls)return;
  x.entryPanel=el("section","dx-entry");const toolbar=el("div","dx-toolbar");x.entryButtons={};
  const run=async action=>{if(x.entryPending)return;x.localError=null;x.entryPending=true;updateEntry(node);try{
    if(action==="pause"){x.state.entry.pause=!x.state.entry.pause;persist(node);}
    else if(action==="skip"){x.state.entry.skip=!x.state.entry.skip;persist(node);await x.entryQueue;}
    else if(action==="rerun"){
      if(!inputConnected(node,"image")){
        x.localError="Image input not detected — connect an IMAGE output to DetailerX.";
        return;
      }
      const graph=await app.graphToPrompt();
      const target=Object.keys(graph.output).find(id=>{try{return JSON.parse(graph.output[id].inputs?.settings||"{}")._control?.owner===entryOwner(node);}catch{return false;}});
      if(!target)throw new Error("Cannot resolve this node in the current graph. Queue the ordinary workflow.");
      if(!x.entry?.can_rerun){
        const queued=await connectedRerun(node,graph,target);
        x.entry={...x.entry,...queued,state:"queued",can_rerun:false,can_refine_original:false,can_refine_output:false,queue_mode:"connected"};x.message="Connected image queued — running only required upstream dependencies and downstream consumers.";
        return;
      }
      const response=await api.fetchApi("/workflowx_configurator/detailer_x/rerun",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({owner:entryOwner(node),token:x.entry.token,target,prompt:graph.output,settings:serialize(x.state),client_id:api.clientId,extra_data:{extra_pnginfo:{workflow:graph.workflow}}})});
      const data=await response.json();
      if(response.status===409&&data.code==="upstream_changed"){
        const queued=await connectedRerun(node,graph,target);x.entry={...x.entry,...queued};x.message="Upstream input changed — running the current DetailerX branch.";
      }else if(!response.ok)throw new Error(data.error);
      x.entry={...x.entry,state:"queued",can_rerun:false,queue_mode:data.code==="upstream_changed"?"connected":"retained"};
    }else{await x.entryQueue;const data=await entryRequest(node,action,{settings:serialize(x.state),revision:(x.entryRevision||0)+1});acceptEntry(node,data);}
  }catch(e){report(node,e);}finally{x.entryPending=false;updateEntry(node);}};
  for(const [key,icon,description] of [
    ["pause","⏸","Pause on entry: persistent toggle. Does not stop stages already running."],
    ["skip","⏭","Skip: persistent bypass for ordinary queues and Resume until disabled. Passes the input unchanged through all outputs and takes priority over Pause. Rerun explicitly overrides Skip for that rerun only."],
    ["cancel","✕","Cancel paused detailing and pass the original input downstream."],
    ["resume","▶","Use this node's toggles and applied settings at the time you click Resume—not when the workflow was queued. Apply open gear dialogs first. Skip, if enabled, passes the input through unchanged."],
    ["rerun","↻","Run with current applied settings. A retained image is reused without upstream generation. Otherwise, only this node's required upstream branch and its downstream consumers are queued; unrelated generation branches are excluded. Pause and Skip are bypassed for this run."],
  ]){const b=button(icon,()=>run(key));help(b,description);b.setAttribute("aria-label",title(key));x.entryButtons[key]=b;toolbar.append(b);}
  const gearButton=button("⚙",()=>nodeSettings(node));
  help(gearButton,"Node settings: Flow, Seed, Detailers, and shared SAM configuration.");gearButton.setAttribute("aria-label","Node settings");toolbar.append(gearButton);
  x.entryPanel.append(toolbar);x.root.append(x.entryPanel);updateEntry(node);
}
function presetLabel(state){return `${state.preset?.label||"Custom"}${modified(state)?" · Modified":""}`;}
function fit(node){
  const size=minimumSize(node._dx.state,Math.max(node.inputs?.length||0,node.outputs?.length||0));
  node.setSize([Math.max(Number.isFinite(node.size[0])?node.size[0]:0,size[0]),size[1]]);
}
function report(node,error){node._dx.localError=error.message||String(error);updateStatus(node);}
function dialog(heading,description){
  const d=el("dialog","dx-dialog"),form=el("form"),header=el("header"),body=el("div","dx-body"),footer=el("footer");
  header.append(el("h2","",heading));if(description)header.append(el("p","",description));
  form.append(header,body,footer);d.append(form);document.body.append(d);
  const previous=document.activeElement;
  d.addEventListener("close",()=>{d.remove();previous?.focus?.();});
  d.addEventListener("click",e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close();}});
  form.addEventListener("submit",e=>e.preventDefault());
  d.showModal();return {d,form,body,footer};
}
function searchable(heading,options,current,onPick,description="Internal assets and registered ComfyUI model folders"){
  const {d,body,footer}=dialog(heading,description);
  const search=el("input","dx-search");search.placeholder="Search…";search.setAttribute("aria-label","Search choices");help(search,"Filter the available choices by name.");
  const list=el("div","dx-options");body.append(search,list);
  function populate(){list.replaceChildren();const query=search.value.toLowerCase();for(const item of options.filter(i=>(i.label+" "+(i.description||"")).toLowerCase().includes(query))){const b=button(`${item.id===current?"✓ ":""}${item.label}`,()=>{Promise.resolve(onPick(item.id)).catch(console.error);d.close();});help(b,item.description||item.id);list.append(b);}if(!list.children.length)list.append(el("p","","No matching models. Restore internal assets or add a model to ComfyUI."));}
  search.addEventListener("input",populate);populate();footer.append(button("Cancel",()=>d.close()));search.focus();
}
function assetKind(section,key){if(key==="lut")return "luts";if(key==="detector")return "ultralytics";if(key==="model")return section==="sam"?"sams":"upscale_models";return null;}
async function detectorInfo(id){let model=metadata.detector_catalog?.models?.find(m=>m.id===id);if(model?.classes?.length)return model;const response=await api.fetchApi(`/workflowx_configurator/detailer_x/detector_info?id=${encodeURIComponent(id)}`);const data=await response.json();if(!response.ok)throw new Error(data.error||"Unable to inspect detector");metadata.detector_catalog.models=[...(metadata.detector_catalog.models||[]).filter(m=>m.id!==id),data];return data;}
function samModelFor(backend,current){
  const choices=backend==="sam3.1"?(metadata.sam3_checkpoints||[]):metadata.assets.sams||[],match=backend==="sam1"?/sam_vit_/i:/sam2\.1/i;
  return choices.some(item=>item.id===current&&(backend==="sam3.1"||match.test(item.id)))?current:(choices.find(item=>backend==="sam3.1"||match.test(item.id))?.id||current);
}
function nodeSettings(node){
  const state=node._dx.state,entry=structuredClone(state.entry),globalSeed=structuredClone(state.global_seed),shared=structuredClone(state.sam),visible={...state.visible};let resetOrder=false;
  const {d,form,body,footer}=dialog("Node Settings","Node-wide controls are grouped here. Global SAM is the inherited default; each detailer may use its detector directly or define a complete override.");
  const tabs=el("div","dx-tabs"),panel=el("section","dx-tab-panel"),names=[["flow","Flow"],["seed","Seed"],["detailers","Detailers"],["sam","SAM"]],buttons={};
  tabs.setAttribute("role","tablist");panel.setAttribute("role","tabpanel");panel.id=`dx-settings-panel-${node.id}`;body.append(tabs,panel);
  function show(name,focus=false){
    node._dx.settingsTab=name;panel.replaceChildren();panel.setAttribute("aria-labelledby",`dx-settings-${name}-${node.id}`);
    for(const [key,b] of Object.entries(buttons)){const selected=key===name;b.setAttribute("aria-selected",String(selected));b.tabIndex=selected?0:-1;}
    if(name==="flow")panel.append(el("p","dx-section-note","Controls what happens when execution reaches DetailerX. Pause and Skip remain persistent toolbar toggles."),field("entry","pause_minutes",entry),field("entry","wait_indefinitely",entry));
    else if(name==="seed")panel.append(el("p","dx-section-note","A global seed overrides local seeds for every seeded processor while retaining each processor's offsets."),field("global_seed","enabled",globalSeed),field("global_seed","mode",globalSeed),field("global_seed","seed",globalSeed));
    else if(name==="sam"){
      panel.append(el("p","dx-section-note","This is the default inherited by detailers. A detailer gear may choose detector-only masking or override the backend, checkpoint, device and loading preference."));
      for(const key of Object.keys(shared))panel.append(field("sam",key,shared,(changed)=>{if(changed==="backend"){shared.model=samModelFor(shared.backend,shared.model);show("sam");}}));
      const restoreSam=button("Restore SAM Defaults",()=>{Object.assign(shared,structuredClone(metadata.defaults.sam));show("sam");});help(restoreSam,"Restore the shipped shared SAM backend, checkpoint, enabled state, and device preference in this draft. Apply commits the change.");panel.append(restoreSam);
    }else{
      panel.append(el("p","dx-section-note","Visible does not mean enabled. Newly shown processors start off. Hiding a processor disables it while retaining advanced settings and its position."));
      const more=button("Additional Detailers",()=>additionalDetailers(node,visible,()=>show("detailers")));help(more,"Choose additional concept-based detailers. Newly added rows appear disabled and retain their place when hidden.");panel.append(more,el("h3","","Visible processors"));
      for(const processor of state.order){const row=el("label","dx-field"),input=el("input");input.type="checkbox";input.checked=visible[processor];const label=labelFor(state,processor);input.setAttribute("aria-label",`Show ${label}`);help(input,`Show ${label}. Newly shown processors start off; hiding disables execution.`);input.addEventListener("change",()=>visible[processor]=input.checked);row.append(el("span","",label),input);panel.append(row);}
      const reset=button(resetOrder?"Default order will apply":"Restore Default Order",()=>{resetOrder=true;reset.textContent="Default order will apply";});help(reset,"Restore the default processing order when Apply is clicked. Does not change visibility or execution toggles.");panel.append(reset);
    }
    if(focus)buttons[name]?.focus();
  }
  for(const [name,label] of names){const tab=button(label,()=>show(name));tab.id=`dx-settings-${name}-${node.id}`;tab.setAttribute("role","tab");tab.setAttribute("aria-controls",panel.id);help(tab,`Open ${label} node-wide settings.`);buttons[name]=tab;tabs.append(tab);}
  tabs.addEventListener("keydown",event=>{const index=names.findIndex(([name])=>name===node._dx.settingsTab);let next;if(event.key==="ArrowRight")next=(index+1)%names.length;else if(event.key==="ArrowLeft")next=(index-1+names.length)%names.length;else if(event.key==="Home")next=0;else if(event.key==="End")next=names.length-1;else return;event.preventDefault();show(names[next][0],true);});
  show(names.some(([name])=>name===node._dx.settingsTab)?node._dx.settingsTab:"flow");
  footer.append(button("Cancel",()=>d.close()),button("Apply",()=>{if(!form.reportValidity())return;applyVisibility(state,visible);state.entry=entry;state.global_seed=globalSeed;state.sam=shared;if(resetOrder)state.order=["upscaler",...DETAILERS,...Object.keys(state.extra_detailers||{}),...REALISM,"dlss5"];persist(node);render(node);d.close();},"dx-primary"));
}
function additionalDetailers(node,visible,onApply){
  const state=node._dx.state,catalog=metadata.detector_catalog?.concepts||[],selected=new Set(Object.keys(state.extra_detailers||{}).filter(id=>state.visible?.[id])),created={};
  const {d,body,footer}=dialog("Additional Detailers","Select catalogued concepts or create repeatable custom detailers. Newly shown rows start disabled.");
  const customName=el("input");customName.placeholder="Custom detailer name";customName.maxLength=120;customName.setAttribute("aria-label","Custom detailer name");
  const add=button("Create Custom Detailer",()=>{const label=customName.value.trim();if(!label){customName.setCustomValidity("Enter a display name");customName.reportValidity();return;}customName.setCustomValidity("");const id=`detailer:custom:${crypto.randomUUID()}`,copy=structuredClone(state.anything);copy.label=label;copy.catalog_id="custom";copy.enabled=false;created[id]=copy;selected.add(id);customName.value="";draw();});
  help(add,"Create an independent detailer by copying this node's current Anything detailer settings. The new row starts disabled.");
  function choice(id,label,description){const row=el("label","dx-field"),input=el("input");input.type="checkbox";input.checked=selected.has(id);help(input,description);input.addEventListener("change",()=>input.checked?selected.add(id):selected.delete(id));row.append(el("span","",label),input);return row;}
  function draw(){body.replaceChildren(el("h3","","Create custom detailer"),customName,add);const customs=[...Object.entries(state.extra_detailers||{}),...Object.entries(created)].filter(([id])=>id.startsWith("detailer:custom:"));if(customs.length){body.append(el("h3","","Custom detailers"));for(const [id,item] of customs)body.append(choice(id,item.label,"Show this saved custom detailer. Hiding retains its configuration and order."));}for(const group of metadata.detector_catalog?.groups||[]){body.append(el("h3","",group));for(const concept of catalog.filter(c=>c.group===group&&!c.builtin)){const id=`detailer:${concept.id}`;body.append(choice(id,concept.label,`${concept.prompt}${concept.broad?" Broad detections may create large crops.":""}`));}}}
  draw();
  footer.append(button("Cancel",()=>d.close()),button("Apply",()=>{state.extra_detailers??={};Object.assign(state.extra_detailers,created);for(const id of selected){if(!state.extra_detailers[id]){const concept=catalog.find(c=>`detailer:${c.id}`===id),choice=concept?.models?.[0];state.extra_detailers[id]={...structuredClone(metadata.defaults.anything),...structuredClone(state.preset?.values?.hand||{}),label:`${concept.label} detailer`,catalog_id:concept.id,detector:choice?.id||"",class_ids:choice?[choice.class_id]:[],class_labels:choice?[choice.class_label]:[],prompt:concept.prompt,mask_concept:concept.mask_concept,enabled:false};}if(!state.order.includes(id))state.order.splice(Math.max(0,state.order.findIndex(n=>REALISM.includes(n))),0,id);visible[id]=true;}for(const id of Object.keys(state.extra_detailers))if(!selected.has(id))visible[id]=false;persist(node);render(node);d.close();onApply?.();},"dx-primary"));
}
function dragHandle(node,name,row){
  const x=node._dx,label=labelFor(x.state,name),handle=button("⠿",()=>{},"dx-drag");handle.draggable=true;handle.setAttribute("aria-label",`Move ${label}`);
  help(handle,"Drag to reorder processing. Keyboard: Arrow Up / Arrow Down moves this processor. Hidden positions are retained.");
  const move=target=>{moveVisible(x.state,name,target);persist(node);render(node);x.root.querySelector(`[data-stage="${name}"] .dx-drag`)?.focus();};
  handle.addEventListener("keydown",e=>{if(!["ArrowUp","ArrowDown"].includes(e.key))return;e.preventDefault();e.stopPropagation();const list=rows(x.state),i=list.indexOf(name)+(e.key==="ArrowUp"?-1:1);if(list[i])move(list[i]);});
  handle.addEventListener("dragstart",e=>{x.dragStage=name;e.dataTransfer.setData("text/plain",name);e.dataTransfer.effectAllowed="move";e.stopPropagation();});
  handle.addEventListener("dragend",()=>{x.dragStage=null;for(const r of x.root.querySelectorAll('[data-drop]'))r.removeAttribute('data-drop');});
  row.addEventListener("dragover",e=>{if(!x.dragStage)return;e.preventDefault();e.stopPropagation();row.setAttribute('data-drop','true');});
  row.addEventListener("dragleave",()=>row.removeAttribute('data-drop'));
  row.addEventListener("drop",e=>{if(!x.dragStage)return;e.preventDefault();e.stopPropagation();const source=x.dragStage;x.dragStage=null;moveVisible(x.state,source,name);persist(node);render(node);});
  return handle;
}
function optionsFor(section,key){if(key==="sampler_name")return metadata.samplers;if(key==="scheduler")return metadata.schedulers;if(section==="grain"&&key==="seed_mode")return ["time","fixed"];if(section==="global_seed"&&key==="mode")return ["fixed","random"];if(section==="sam"&&key==="backend")return ["sam1","sam2.1","sam3.1"];return metadata.choices[key];}
function optionLabel(key,value){
  const labels={
    sam_strategy:{inherit:"Inherit global SAM",detector_only:"Detector only",override:"Override SAM"},
    sam3_mode:{refine_detector:"Refine detector",concept_with_detector:"Hybrid — detector + concept",bbox_controlled:"BBox controlled",concept_only:"Fully text-guided"},
    sam3_constraint:{bounding_box:"Bounding box",detector_mask:"Detector mask",none:"No post-constraint"},
    detector_proposal:{native:"Native — use SEGM shape",bbox:"Bounding box — force rectangle"},
    sam_detection_hint:{"center-1":"center-1 — general default","horizontal-2":"horizontal-2 — wide target","vertical-2":"vertical-2 — tall target","rect-4":"rect-4 — broad coverage","diamond-4":"diamond-4 — interior coverage","mask-area":"mask-area — use SEGM shape","mask-points":"mask-points — combine detections","mask-point-bbox":"mask-point-bbox — small target","none":"none — box only"},
  };
  return labels[key]?.[value]||value;
}
function field(section,key,object,onEdit){
  const row=el("label","dx-field"),caption=el("span","",title(key));row.append(caption);
  const kind=assetKind(section,key);let control;
  if(kind){let choices=section==="sam"&&key==="model"&&object.backend==="sam3.1"?(metadata.sam3_checkpoints||[]):metadata.assets[kind];const concept=key==="detector"&&object.catalog_id&&object.catalog_id!=="anything"?metadata.detector_catalog?.concepts?.find(c=>c.id===object.catalog_id):null;if(concept){const ids=new Set(concept.models.map(m=>m.id));choices=choices.filter(item=>ids.has(item.id)||item.id===object.detector);}control=button(object[key],()=>searchable(title(key),choices,object[key],async v=>{object[key]=v;control.textContent=v;if(key==="detector"){if(concept){const match=concept.models.find(m=>m.id===v);if(match){object.class_ids=[match.class_id];object.class_labels=[match.class_label];}}else{const model=await detectorInfo(v);object.class_ids=model?.classes?.map(c=>c.id)||[];object.class_labels=model?.classes?.map(c=>c.label)||[];}}onEdit?.(key,object[key]);}),"dx-model");}
  else if(optionsFor(section,key)){control=el("select");for(const v of optionsFor(section,key)){const o=el("option","",optionLabel(key,v));o.value=v;control.append(o);}control.value=object[key];control.addEventListener("change",()=>{object[key]=control.value;control.setAttribute("aria-description",helpText(section,key,object[key]));});}
  else if(typeof object[key]==="boolean"){control=el("input");control.type="checkbox";control.checked=object[key];control.addEventListener("change",()=>object[key]=control.checked);}
  else if(typeof object[key]==="number"){control=el("input");control.type="number";const [min,max,step]=metadata.ranges[key]||[0,Number.MAX_SAFE_INTEGER,1];Object.assign(control,{min,max,step,value:object[key],required:true});control.addEventListener("input",()=>{if(control.value!==""&&control.checkValidity())object[key]=Number(control.value);});}
  else {control=el(key==="prompt"?"textarea":"input");control.value=object[key];control.addEventListener("input",()=>object[key]=control.value);}
  help(control,helpText(section,key,object[key])+(kind?` Current asset: ${object[key]}`:""));help(caption,helpText(section,key));
  if(onEdit)for(const event of ["input","change"])control.addEventListener(event,()=>{if(control.checkValidity?.()!==false)onEdit(key,object[key]);});
  control.setAttribute("aria-label",title(key));row.append(control);return row;
}
function presetGear(node){
  const state=node._dx.state,draft={...structuredClone(state.preset),values:presetValues(state)};
  const baseline=structuredClone(state.preset);
  const {d,form,body,footer}=dialog("Model preset defaults","Save and Apply updates this node and the reusable local library. Other nodes keep their own saved snapshots. Only model-related detailer settings are changed.");
  const name=el("input");name.value=draft.label;name.required=true;name.maxLength=120;name.setAttribute("aria-label","Preset name");help(name,"Name used in the model preset selector. Save As creates an independent preset.");
  const family=el("select");for(const v of ["sdxl","qwen","flux","klein","zimage","krea2","custom"]){const o=el("option","",v);o.value=v;family.append(o);}family.value=draft.family;family.setAttribute("aria-label","Preset family");help(family,"Family used for mismatch warnings. Does not load or modify the connected model.");
  const scope=el("select");for(const v of ["all",...DETAILERS]){const o=el("option","",v==="all"?"All detailers — edit shared values":LABELS[v]);o.value=v;scope.append(o);}scope.value="all";scope.setAttribute("aria-label","Edit detailer defaults");help(scope,"All detailers changes only fields you edit. Choose a detailer to view or edit its individual preset values.");
  const fields=el("div"),error=el("p","dx-error");error.setAttribute("role","alert");
  body.append(el("p","dx-help","Preset name"),name,el("p","dx-help","Family"),family,el("p","dx-help","Values to edit"),scope,fields,error);
  function populate(){fields.replaceChildren();const selected=scope.value;const object=selected==="all"?structuredClone(draft.values.face):draft.values[selected];for(const key of PRESET_FIELDS){const row=field("face",key,object,(k,v)=>{if(selected==="all")for(const n of DETAILERS)draft.values[n][k]=v;});if(selected==="all"&&DETAILERS.some(n=>draft.values[n][key]!==object[key]))row.append(el("small","dx-help","Mixed values — editing applies to all"));fields.append(row);}}
  scope.addEventListener("change",populate);populate();
  async function save(asNew){
    if(!form.reportValidity())return;
    const next={...draft,label:name.value.trim(),family:family.value};
    const newItem=asNew||["custom","legacy"].includes(next.id);
    if(newItem)next.id=`user-${crypto.randomUUID()}`;
    const revision=newItem?0:baseline.revision;
    for(const b of footer.children)b.disabled=true;
    try{const response=await api.fetchApi("/workflowx_configurator/detailer_x/presets",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({preset:next,expected_revision:revision})});const saved=await response.json();if(!response.ok)throw new Error(saved.error||"Unable to save preset");metadata.presets=[...(metadata.presets||[]).filter(p=>p.id!==saved.id),saved];applyPreset(state,saved);persist(node);render(node);d.close();}
    catch(e){error.textContent=e.message;}finally{for(const b of footer.children)b.disabled=false;}
  }
  const builtin=(metadata.builtins||[]).find(p=>p.id===draft.id);
  footer.append(button(builtin?"Restore Built-in Defaults":"Reset to Saved Baseline",()=>{draft.values=structuredClone((builtin||baseline).values);draft.family=(builtin||baseline).family;family.value=draft.family;populate();}),button("Cancel",()=>d.close()),button("Save As",()=>save(true)),button("Save and Apply",()=>save(false),"dx-primary"));
}
function gear(node,section){
  const source=stage(node._dx.state,section),draft=structuredClone(source),detailer=isDetailer(node._dx.state,section);
  const label=labelFor(node._dx.state,section),{d,form,body,footer}=dialog(`${label} settings`,detailer?"Configure detection, masking and enhancement. Global SAM is the inherited default; this detailer may use detector-only masking or a complete override.":"Changes apply to this processor when you choose Apply.");
  const effectiveBackend=()=>draft.sam_strategy==="detector_only"||draft.sam_strategy==="inherit"&&!node._dx.state.sam.enabled?null:draft.sam_strategy==="override"?draft.sam_override.backend:node._dx.state.sam.backend;
  function samPanel(){
    const box=el("fieldset"),legend=el("legend","","Masking strategy");box.append(legend,field(section,"sam_strategy",draft,()=>populate()));
    if(draft.sam_strategy==="inherit")box.append(el("p","dx-help",node._dx.state.sam.enabled?`Using global ${node._dx.state.sam.backend} · ${node._dx.state.sam.model}`:"Global SAM is disabled; this detailer will use its detector mask."));
    else if(draft.sam_strategy==="detector_only")box.append(el("p","dx-help","Use the selected Ultralytics BBOX or SEGM proposal directly; no SAM checkpoint is loaded."));
    else{
      draft.sam_override??=structuredClone(metadata.defaults.anything.sam_override);
      for(const key of Object.keys(draft.sam_override))box.append(field("sam",key,draft.sam_override,(changed)=>{if(changed==="backend"){draft.sam_override.model=samModelFor(draft.sam_override.backend,draft.sam_override.model);populate();}}));
    }
    const backend=effectiveBackend();
    if(backend==="sam3.1"){
      box.append(field(section,"sam3_mode",draft,()=>populate()));
      if(!["concept_only","bbox_controlled"].includes(draft.sam3_mode))box.append(field(section,"sam3_constraint",draft));
      if(draft.sam3_mode!=="refine_detector"){
        box.append(field(section,"mask_concept",draft));
        const useClass=button("Use selected class concept",()=>{const concept=metadata.detector_catalog?.concepts?.find(c=>c.id===draft.catalog_id)?.mask_concept,labels=[...new Set(draft.class_labels||[])].filter(Boolean);draft.mask_concept=concept||labels.join(" or ");populate();});
        useClass.disabled=!(metadata.detector_catalog?.concepts?.find(c=>c.id===draft.catalog_id)?.mask_concept||(draft.class_labels||[]).length);help(useClass,"Replace the draft mask concept with the catalog's canonical concept, or the currently selected detector class label when no catalog mapping exists.");box.append(useClass);
      }
      box.append(field(section,"sam3_threshold",draft),field(section,"sam3_refine_iterations",draft));
    }
    body.append(box);
  }
  function populate(){body.replaceChildren();if(node._dx.state.global_seed?.enabled&&Object.hasOwn(draft,"seed"))body.append(el("p","dx-help",`Global seed override is active (${node._dx.state.global_seed.mode}). Local seed values are retained but are not currently used.`));for(const key of Object.keys(draft)){if(key==="enabled"||key==="label"||key==="catalog_id"||key==="class_labels"||key==="sam_strategy"||key==="sam_override"||key.startsWith("sam3_")||key==="mask_concept")continue;if(key==="class_ids"){body.append(classSelector(draft));continue;}body.append(field(section,key,draft,key==="detector"?()=>populate():undefined));}if(detailer)samPanel();
    if(section==="temperature"){
      const presets=[[2000,"Candlelight"],[2700,"Warm Bulb"],[3200,"Tungsten"],[4000,"Warm White"],[5000,"Daylight"],[5500,"Flash"],[6500,"Neutral"],[7500,"Cloudy"],[9000,"Shade"]];
      const selector=el("select");selector.setAttribute("aria-label","Source temperature preset");
      for(const [v,label] of [...presets,["custom","Custom"]]){const o=el("option","",v==="custom"?label:`${v} K — ${label}`);o.value=v;selector.append(o);}
      selector.value=presets.some(([v])=>v===draft.kelvin)?String(draft.kelvin):"custom";
      help(selector,"Correct the source lighting toward neutral daylight. Lower source Kelvin cools the image. Custom allows 2000–12000 K; 6500 K is neutral. Not automatic white balance or tint correction.");
      const numeric=body.querySelector('input');selector.addEventListener('change',()=>{if(selector.value!=="custom"){draft.kelvin=Number(selector.value);numeric.value=draft.kelvin;}numeric.focus();});
      numeric.addEventListener('input',()=>selector.value='custom');body.prepend(selector);
    }
  }
  populate();
  if(section==="neural_grain"){
    const note=el("div","dx-citation","Neural Film Grain Rendering — Gwilherm Lesné, Yann Gousseau, Saïd Ladjal, Alasdair Newson. ");
    for(const [label,url] of [["Paper","https://doi.org/10.1111/cgf.70076"],["Project repository","https://github.com/Gwilherm-LESNE/Neural_Film_Grain_Rendering"]]){const a=el("a","",label);a.href=url;a.target="_blank";a.rel="noopener noreferrer";note.append(a,document.createTextNode(" · "));}footer.append(note);
  }
  const hide=button("Hide processor",()=>{const saved=stage(node._dx.state,section);saved.enabled=false;node._dx.state.visible[section]=false;persist(node);render(node);d.close();});help(hide,"Disable and hide this processor without applying dialog drafts. Its saved settings and processing-order position are retained.");footer.append(hide);
  if(section.startsWith("detailer:custom:")){
    const remove=button("Delete custom",()=>{if(!confirm(`Delete ${label}? Its saved settings will be permanently removed.`))return;delete node._dx.state.extra_detailers[section];delete node._dx.state.visible[section];node._dx.state.order=node._dx.state.order.filter(name=>name!==section);node._dx.state.cache_epoch=(node._dx.state.cache_epoch||0)+1;persist(node);render(node);d.close();});help(remove,"Permanently delete this custom detailer after confirmation. Other processors are unaffected.");footer.append(remove);
  }
  footer.append(button("Restore workflow defaults",()=>{const enabled=draft.enabled,identity=section.startsWith("detailer:")?Object.fromEntries(["label","catalog_id","detector","class_ids","class_labels","prompt","mask_concept"].map(key=>[key,structuredClone(draft[key])])):{};Object.assign(draft,structuredClone(metadata.defaults[DETAILERS.includes(section)?section:"anything"]),identity,{enabled});populate();}),button("Cancel",()=>d.close()),button("Apply",()=>{if(!form.reportValidity())return;if(section.startsWith("detailer:"))node._dx.state.extra_detailers[section]=draft;else node._dx.state[section]=draft;persist(node);render(node);d.close();},"dx-primary"));
}
function classSelector(draft){const row=el("div","dx-field"),wrap=el("div"),model=metadata.detector_catalog?.models?.find(m=>m.id===draft.detector),classes=model?.classes||[];row.append(el("span","","Detector classes"));for(const item of classes){const label=el("label",""),input=el("input");input.type="checkbox";input.checked=(draft.class_ids||[]).includes(item.id);input.addEventListener("change",()=>{const chosen=new Set(draft.class_ids||[]);input.checked?chosen.add(item.id):chosen.delete(item.id);draft.class_ids=[...chosen];draft.class_labels=draft.class_ids.map(id=>classes.find(c=>c.id===id)?.label||String(id));});label.append(input,document.createTextNode(` ${item.id}: ${item.label}`));wrap.append(label,el("br"));}if(!classes.length)wrap.append(el("small","dx-help","No class metadata is available. The detector will use all returned classes."));row.append(wrap);return row;}
function toggle(state,key,callback,label){const b=button(state[key]?"✓":"",()=>{state[key]=!state[key];callback();},"dx-toggle");help(b,`${label}. ${helpText("stage","enabled")}`);b.setAttribute("role","switch");b.setAttribute("aria-checked",String(state[key]));b.setAttribute("aria-label",label);return b;}
function render(node){
  const x=node._dx;if(!x)return;const {root,state}=x;root.replaceChildren();x.refineButtons=[];
  renderEntry(node);
  const presetRow=el("div","dx-row dx-preset");presetRow.append(el("span","dx-label","Model preset"));
  x.presetButton=button(presetLabel(state),async()=>{
    try{const response=await api.fetchApi("/workflowx_configurator/detailer_x/config");if(!response.ok)throw new Error("Unable to refresh preset library");const latest=await response.json();metadata.presets=latest.presets||metadata.presets;metadata.preset_error=latest.preset_error;
      if(metadata.preset_error)throw new Error(metadata.preset_error);
      const options=[...(metadata.presets||[]),{id:"custom",label:"Custom — copy current settings"}];
      searchable("Model preset",options,state.preset.id,id=>{const selected=id==="custom"?customPreset(state):options.find(p=>p.id===id);applyPreset(state,selected);persist(node);render(node);},helpText("node","preset"));
    }catch(e){report(node,e);}
  },"dx-model");help(x.presetButton,`${helpText("node","preset")} Selected: ${presetLabel(state)}`);x.presetButton.setAttribute("aria-label","Model preset");
  const pg=button("⚙",()=>presetGear(node),"dx-gear");help(pg,"Edit model preset defaults, save a new preset, or restore its original defaults.");pg.setAttribute("aria-label","Model preset settings");presetRow.append(x.presetButton,pg);root.append(presetRow);
  for(const name of rows(state)){
    const s=stage(state,name),label=labelFor(state,name),row=el("div",`dx-row${!s.enabled?" dx-off":""}`);
    row.setAttribute("data-stage",name);if(x.progress?.stage===name)row.setAttribute("data-run-state",x.progress.state);
    row.append(dragHandle(node,name,row),toggle(s,"enabled",()=>{persist(node);render(node);},`${label} enabled`));
    row.append(el("span","dx-label",label));
    if(name==="upscaler"){
      const b=button(s.model.split("/").at(-1),()=>searchable("Upscale model",metadata.assets.upscale_models,s.model,v=>{s.model=v;persist(node);render(node);}),"dx-model");help(b,`${helpText(name,"model")} Current: ${s.model}`);row.append(b);
    }else if(isDetailer(state,name)){
      const wrap=el("label","dx-number"),input=el("input");input.type="number";Object.assign(input,{min:0,max:1,step:0.01,value:s.denoise});help(input,helpText(name,"denoise"));input.setAttribute("aria-label",`${label} denoise`);input.addEventListener("input",()=>{if(input.checkValidity()&&input.value!==""){s.denoise=Number(input.value);persist(node);}});input.addEventListener("change",()=>{if(!input.checkValidity()||input.value==="")input.value=s.denoise;});wrap.append(el("span","","Denoise"),input);row.append(wrap);
    }else if(name==="dlss5"){
      const b=button(s.upscaling_mode,()=>searchable("DLSS5 upscaling mode",metadata.choices.upscaling_mode.map(v=>({id:v,label:v})),s.upscaling_mode,v=>{s.upscaling_mode=v;persist(node);render(node);}),"dx-model");help(b,helpText(name,"upscaling_mode"));row.append(b);
    }else row.append(el("span"));
    const refine=button("▶",()=>selectiveMenu(node,name,refine),"dx-refine");help(refine,`Choose how to run only ${label}: use the original input, reuse its previous output mask when available, or remask the latest output. Other DetailerX processors do not run. If no input is retained, Original evaluates only the connected ancestors required to supply the image.`);refine.setAttribute("aria-label",`Selectively refine with ${label}`);x.refineButtons.push(refine);row.append(refine);
    if(name!=="realism"){const b=button("⚙",()=>gear(node,name),"dx-gear");help(b,`${label} advanced settings. Changes apply to this node only.`);b.setAttribute("aria-label",`${label} advanced settings`);row.append(b);}else row.append(el("span"));
    root.append(row);
  }
  const footer=el("div","dx-footer");x.status=el("span","dx-status",x.message||"Ready · final image + processor preview bundle");x.status.setAttribute("role","status");footer.append(x.status,help(button("Clear cache",()=>{state.cache_epoch=(state.cache_epoch||0)+1;persist(node);x.message="Fresh processing on next queue";render(node);}),"Invalidate this node's cached stages on the next queue, including realized time-based grain. Does not affect other nodes."));root.append(footer);
  updateStatus(node);updateRefineButtons(node);fit(node);
}
function setup(node){
  const widget=node.widgets?.find(w=>w.name==="settings");if(!widget)return;
  widget.type="converted-widget";widget.computeSize=()=>[0,-4];if(widget.inputEl)widget.inputEl.style.display="none";
  const root=el("div","dx-root");
  for(const event of ["pointerdown","keydown","wheel"])root.addEventListener(event,e=>e.stopPropagation());
  node._dx={root,widget,state:restore(node.properties?.detailer_x??widget.value,metadata.defaults)};
  // The native STRING widget may serialize its original textarea, not .value.
  // Both workflow serialization and API submission must use our single state.
  widget.serializeValue=()=>metadata.entry_controls?JSON.stringify({...node._dx.state,_control:{owner:entryOwner(node)}}):serialize(node._dx.state);
  const dom=node.addDOMWidget("detailer_x_controls","DetailerX",root,{serialize:false,hideOnZoom:false,margin:0,getMinHeight:()=>bodyHeight(node._dx.state),getMaxHeight:()=>bodyHeight(node._dx.state)});
  dom.computeSize=()=>[MIN_WIDTH,bodyHeight(node._dx.state)];dom.options.serialize=false;
  node.resizable=true;
  node.serialize_widgets=true;instances.add(node);render(node);
  if(typeof window!=="undefined")setTimeout(()=>{if(instances.has(node))void pollEntry(node);},0);
}
function reconcileNodeOutputs(node){
  const migration=reconcileOutputSlots(node.outputs);
  node.outputs=migration.outputs;
  // Old workflows serialized links for the removed cumulative sockets. They
  // cannot be remapped to the new structured history, so remove them after
  // graph configuration has finished and leave final_image ready to rewire.
  if(migration.staleLinks.length||migration.keptLinks.length)setTimeout(()=>{
    for(const {id,slot} of migration.keptLinks){const links=node.graph?.links,link=links?.get?.(id)??links?.[id];if(link){link.origin_id=node.id;link.origin_slot=slot;}}
    for(const id of migration.staleLinks)node.graph?.removeLink?.(id);
    node.setDirtyCanvas?.(true,true);
  },0);
}

app.registerExtension({
  name:"workflowx.detailer_x",
  async beforeRegisterNodeDef(nodeType,nodeData){
    if(nodeData.name!==TYPE)return;
    if(!document.getElementById("workflowx-detailer-style")){const style=el("style");style.id="workflowx-detailer-style";style.textContent=STYLE;document.head.append(style);}
    const response=await api.fetchApi("/workflowx_configurator/detailer_x/config");if(!response.ok)throw new Error("DetailerX configuration could not be loaded");metadata=await response.json();
    const created=nodeType.prototype.onNodeCreated;nodeType.prototype.onNodeCreated=function(){created?.apply(this,arguments);reconcileNodeOutputs(this);setup(this);};
    const configured=nodeType.prototype.onConfigure;nodeType.prototype.onConfigure=function(info){const result=configured?.apply(this,arguments);reconcileNodeOutputs(this);if(this._dx){try{const index=this.widgets.indexOf(this._dx.widget);this._dx.state=restore(info?.properties?.detailer_x??info?.widgets_values?.[index]??this._dx.widget.value,metadata.defaults);this._dx.widget.value=serialize(this._dx.state);render(this);}catch(e){report(this,e);}}return result;};
    const restoreCompact=nodeType.prototype.onConfigure;nodeType.prototype.onConfigure=function(info){const result=restoreCompact?.apply(this,arguments);const layout=info?.properties?.detailer_x_compact_entry;if(this._dx&&layout!==3&&Array.isArray(info?.size)){const min=minimumSize(this._dx.state,Math.max(this.inputs?.length||0,this.outputs?.length||0));const reduction=(layout===2?0:layout?36:186)+6*(rows(this._dx.state).length+1);this.setSize([Math.max(min[0],this.size[0]),Math.max(min[1],info.size[1]-reduction)]);}return result;};
    const serialized=nodeType.prototype.onSerialize;nodeType.prototype.onSerialize=function(info){serialized?.apply(this,arguments);if(this._dx){info.widgets_values??=[];info.widgets_values[this.widgets.indexOf(this._dx.widget)]=serialize(this._dx.state);info.properties??={};info.properties.detailer_x_compact_entry=3;info.properties.detailer_x=JSON.parse(serialize(this._dx.state));}};
    const resized=nodeType.prototype.onResize;nodeType.prototype.onResize=function(size){resized?.apply(this,arguments);if(this._dx){const min=minimumSize(this._dx.state,Math.max(this.inputs?.length||0,this.outputs?.length||0));size[0]=Math.max(min[0],size[0]);size[1]=Math.max(min[1],size[1]);}};
    const removed=nodeType.prototype.onRemoved;nodeType.prototype.onRemoved=function(){instances.delete(this);this._dx?.root.remove();removed?.apply(this,arguments);};
  },
});
// Countdown is display-only. Only backend events/commands can release the gate.
if(typeof window!=="undefined")window.setInterval(()=>{
  if(!metadata?.entry_controls)return;
  for(const node of instances)if(node._dx.entry?.state==="paused")updateEntry(node);
},1000);
function recoverEntries(){for(const node of instances)void pollEntry(node);}
api.addEventListener("reconnected",recoverEntries);
api.addEventListener("execution_start",recoverEntries);
// Completion is announced before the queue releases the job. Recover availability
// once afterward so retained-input Rerun becomes available without continuous polling.
api.addEventListener("execution_success",()=>setTimeout(recoverEntries,300));
api.addEventListener("reconnecting",()=>{
  for(const node of instances){node._dx.entryConnectionError="Connection lost — reconnecting";updateEntry(node);}
});
api.addEventListener("workflowx.detailer_x.entry",event=>{
  for(const node of instances){
    if(event.detail?.owner&&entryOwners(node).includes(event.detail.owner)){
      node._dx.entryEventVersion=(node._dx.entryEventVersion||0)+1;
      acceptEntry(node,event.detail);
    }
  }
});
api.addEventListener("workflowx.detailer_x.progress",event=>{
  for(const node of instances){
    if(String(node.id)!==event.detail.node||!node._dx)continue;
    const x=node._dx,data=event.detail;
    acceptProgress(node,data);
    for(const row of x.root.querySelectorAll?.("[data-stage]")||[]){
      const stage=row.getAttribute("data-stage");
      const active=stage===data.stage;
      row.setAttribute("data-run-state",active?data.state:"");
    }
  }
});
