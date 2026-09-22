import { rememberDetails, rememberHeight } from './ui_state.js';
import { HELP, LABELS, OPTIONS, helpFor } from './help_text.js';
// Compact DOM controls retain the original widgets as the serialization source.
const css = `
.h3rc-character-header{display:flex;align-items:center;gap:12px;padding-bottom:10px;margin-bottom:6px;border-bottom:1px solid #39424b;}
.h3rc-identity{flex:1;min-width:0;line-height:1.5;overflow-wrap:anywhere;}
.h3rc-character-header button{margin:6px 0 0!important;}
.h3rc-file-row{display:grid;grid-template-columns:minmax(0,1fr) 28px auto;gap:5px;align-items:center;margin-bottom:8px;}
.h3rc-file-row button{margin:0!important;white-space:nowrap;}
.h3rc-association-row{display:grid;grid-template-columns:110px minmax(0,1fr);gap:8px;align-items:center;grid-column:1/-1;}
.h3rc-footer{border-top:1px solid #39424b;margin-top:10px;padding-top:5px;}
.h3rc-hint{grid-column:1/-1;color:#97a7b6;font-size:11px;line-height:1.4;}

.h3rc-panel{box-sizing:border-box;width:100%;height:auto;min-height:0;overflow:visible;padding:10px;background:rgba(18,29,36,.96);border-radius:6px;color:var(--input-text,#ddd);font:12px system-ui;}
.h3rc-panel *{box-sizing:border-box;}
.h3rc-panel [hidden]{display:none!important;}
.h3rc-fields{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:6px 0;}
.h3rc-field{display:flex;flex-direction:column;gap:4px;min-width:0;}
.h3rc-field:has(input[type=checkbox]){flex-direction:row;align-items:center;align-self:end;min-height:30px;}
.h3rc-field input[type=checkbox]{order:-1;}
.h3rc-field.wide{grid-column:1/-1;}
.h3rc-panel input,.h3rc-panel select,.h3rc-panel textarea{width:100%;min-width:0;border:1px solid #48515c;border-radius:4px;background:var(--comfy-input-bg,#171b20);color:inherit;padding:6px;font:12px system-ui;}
.h3rc-panel input[type=checkbox]{width:auto;align-self:flex-start;}
.h3rc-panel textarea{height:64px;min-height:42px;max-height:500px;resize:vertical;overflow:auto;}
.h3rc-panel button{font:12px system-ui!important;padding:5px 8px!important;margin:3px!important;}
.h3rc-panel details{margin:6px 0;} .h3rc-panel summary{cursor:pointer;color:#aab9c8;}
.h3rc-panel details p{line-height:1.4;}
.h3rc-media-frame{height:180px;min-height:80px;max-height:600px;resize:vertical;overflow:hidden;margin:8px 0;}
.h3rc-media-frame img,.h3rc-media-frame video{display:block;width:100%;height:100%;object-fit:contain;max-height:none!important;}
.h3rc-panel audio{width:100%;height:40px;}
`;
if(!document.getElementById('h3rc-layout')){const s=document.createElement('style');s.id='h3rc-layout';s.textContent=css;document.head.append(s);}
export function compactFields(node,box,names){
 box.classList.add('h3rc-panel');box.style.cssText='';
 const form=document.createElement('div');form.className='h3rc-fields';form.h3rcNode=node;box.prepend(form);const rows=[];
 const labels={reference_type:'Reference type',retain:'Retain',change:'Change',sample_frames:'Maximum sampled frames per video',preservation:'Preservation',preservation_text:'What to preserve and what may change',package_name:'Package name (blank = Display name)',folder:'Source folder',description:'Description (catalog notes)',source_ranges:'Source ranges',video_fps:'Frame-batch FPS',descriptor:'Descriptor',use_saved_voice:'Use saved voice',source:'Source',tag:'Prompt tag',role:'Use reference for',use_instructions:'Use instructions',fps:'Frames per second',start_seconds:'Start (seconds)',duration_seconds:'Duration (0 = remaining)',use_soundtrack:'Use video soundtrack',audio_tag:'Soundtrack tag',audio_role:'Soundtrack role',audio_mode:'Audio use',audio_instructions:'Soundtrack instructions',batch_selection:'Images from connected batch',};
 for(const w of [...node.widgets]){
  if(w.options?.serialize===false||w.name==='character_browser'||w.name==='named_media_controls')continue;
  w.h3rcReplaced=true;w.type='converted-widget';w.computeSize=()=>[0,-4];w.draw=()=>{};w.hidden=true;
  for(const e of [w.element,w.inputEl])if(e)e.style.display='none';
  w.getHeight=()=>0;if(w.options){w.options.getMinHeight=()=>0;w.options.getMaxHeight=()=>0;}
 }
 for(const name of names){const w=node.widgets.find(w=>w.name===name);if(!w)continue;
  const row=document.createElement('label');row.className='h3rc-field';row.dataset.field=name;const title=document.createElement('span');title.textContent=LABELS[name]||labels[name]||w.label||name;row.append(title);
  const multiline=['retain','change','preservation_text','use_descriptor','use_instructions','audio_instructions','description','source_ranges'].includes(name);const choices=w.options?.values;
  const input=document.createElement(multiline?'textarea':choices?'select':'input');row.append(input);form.append(row);
  if(multiline||name==='folder'||name==='descriptor'||name==='batch_selection')row.classList.add('wide');
  if(!multiline&&!choices)input.type=typeof w.value==='boolean'?'checkbox':typeof w.value==='number'?'number':'text';
  if(input.type==='number'){input.step='any';if(w.options?.min!=null)input.min=w.options.min;if(w.options?.max!=null)input.max=w.options.max;}
  row.title=helpFor(name,node.type)||w.tooltip||w.options?.tooltip||({batch_selection:'For a connected IMAGE batch only: all uses every image; 1,3 uses the first and third. Leave all for a single image.',use_instructions:'Optional instructions for this reference. Drag the lower-right corner to resize.'}[name]||title.textContent);
  input.title=row.title;
  const numericDefault=typeof w.value==='number'?w.value:null;
  input.oninput=()=>{if(input.type==='number'&&(input.value===''||!Number.isFinite(Number(input.value))))return;w.value=input.type==='checkbox'?input.checked:input.type==='number'?Number(input.value):input.value;w.callback?.(w.value);node.graph?.setDirtyCanvas(true,true);};
  if(multiline){
   rememberHeight(node,input,'text:'+name,64,42,500);
  }
  rows.push({w,row,input,choices,numericDefault});
 }
 const sync=()=>{for(const {w,row,input,choices,numericDefault} of rows){if(numericDefault!==null&&(w.value===''||w.value==null||!Number.isFinite(Number(w.value))))w.value=numericDefault;row.style.display=w.h3rcShow===false?'none':'';input.disabled=w.h3rcDisabled===true;
  if(choices){const list=typeof w.options.values==='function'?w.options.values():w.options.values;const signature=JSON.stringify(list);if(input.dataset.list!==signature){input.replaceChildren(...list.map(v=>{const o=document.createElement('option');o.value=v;o.textContent=(OPTIONS[v]||v);return o;}));input.dataset.list=signature;}}
  if(document.activeElement!==input){if(input.type==='checkbox')input.checked=!!w.value;else input.value=w.value??'';}
 }for(const group of form.querySelectorAll('details[data-fields]'))group.hidden=![...group.querySelectorAll('[data-field]')].some(r=>r.style.display!=='none');};node.h3rcSyncFields=sync;
 const configured=node.onConfigure;node.onConfigure=function(){configured?.apply(this,arguments);setTimeout(()=>{

  sync();},0);};
 const removed=node.onRemoved;node.onRemoved=function(){for(const observer of node.h3rcLayoutObservers||[])observer.disconnect();removed?.apply(this,arguments);};
 sync();return form;
}
export function panelOptions(box,node){
 if(!box||!node)return {serialize:false,hideOnZoom:false,getMinHeight:()=>260,getMaxHeight:()=>1600};
 let height=260,queued=false;
 const update=()=>{queued=false;const next=Math.ceil(box.scrollHeight)+12;if(next<40||next===height)return;height=next;const size=node.computeSize();node.setSize([node.size[0],size[1]]);node.graph?.setDirtyCanvas(true,true);};
 const observer=new ResizeObserver(()=>{if(!queued){queued=true;requestAnimationFrame(update);}});observer.observe(box);(node.h3rcLayoutObservers??=[]).push(observer);
 setTimeout(update,0);
 return {serialize:false,hideOnZoom:false,getMinHeight:()=>height,getMaxHeight:()=>height};
}

export function groupFields(form, title, names, open=false){
 const group=document.createElement('details');group.dataset.fields=names.join(',');group.style.cssText='grid-column:1/-1;border-top:1px solid #394b57;padding:8px 0';const node=form.h3rcNode;if(node)rememberDetails(node,group,'group:'+title,()=>node.properties?.h3rcGroups?.[title]??open);else group.open=open;
 const summary=document.createElement('summary');summary.textContent=title;summary.style.cssText='font-weight:600;padding:3px 0';group.append(summary);
 const fields=document.createElement('div');fields.className='h3rc-fields';group.append(fields);
 for(const name of names){const row=form.querySelector(`[data-field="${name}"]`);if(row)fields.append(row);}
 form.append(group);return group;
}
