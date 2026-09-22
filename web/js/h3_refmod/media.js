import { rememberDetails, rememberHeight, readUI, writeUI, restoreUI } from './ui_state.js';
import { HELP } from './help_text.js';
import { openSourceEditor } from './source_editor.js';
import { compactFields, panelOptions, groupFields } from './layout.js';
import { app } from '../../../scripts/app.js';
import { api } from '../../../scripts/api.js';
const style='background:#172932;color:#e7edf4;border:1px solid #496078;border-radius:6px;padding:7px;font:13px system-ui;';
const el=(t,p,text='')=>{const x=document.createElement(t);x.textContent=text;p?.append(x);return x;};
const values=n=>Object.fromEntries((n.widgets||[]).map(w=>[w.name,w.value]));
const set=(n,key,v)=>{const w=n.widgets.find(w=>w.name===key);if(w){w.value=v;w.callback?.(v);app.graph.setDirtyCanvas(true,true);}};
const button=(p,text,fn)=>{const b=el('button',p,text);b.style.cssText=style+'cursor:pointer;margin:3px';b.onclick=fn;return b;};
const normalize=s=>String(s||'').trim().replace(/^@+/,'').toLowerCase();
function visibility(widget,show){if(!widget)return;widget.h3rcShow=show;if(widget.h3rcReplaced)return;if(!widget.h3rcOriginal)widget.h3rcOriginal={type:widget.type,computeSize:widget.computeSize};widget.type=show?widget.h3rcOriginal.type:'converted-widget';widget.computeSize=show?widget.h3rcOriginal.computeSize:()=>[0,-4];}
function identity(node,w){return JSON.stringify({...w,links:w.source==='Load file'?[]:(node.inputs||[]).filter(i=>i.link!=null).map(i=>{const l=app.graph.links[i.link];return [i.name,l?.origin_id,l?.origin_slot];})});}
function charactersFor(node){
 const targets=new Set(), mains=[];
 for(const output of node.outputs||[])for(const id of output.links||[]){const link=app.graph.links[id];const n=app.graph.getNodeById(link?.target_id);if(n?.type==='H3RCModReferenceToVideo')mains.push(n);}
 for(const main of mains)for(const input of main.inputs||[]){const link=app.graph.links[input.link];const src=app.graph.getNodeById(link?.origin_id);if(!src||src.mode===2||src.mode===4)continue;
  if(src.type==='H3RCCharacterPicker'&&src.h3rcAlias)targets.add(src.h3rcAlias);
  const w=values(src);if(src.type==='H3RCImageReference'&&w.role==='character appearance'&&!normalize(w.associated_character))targets.add(normalize(w.tag));
 }
 return [...targets];
}
app.registerExtension({name:'H3RefCharacters.NamedMedia',beforeRegisterNodeDef(NodeType,data){
 const kind={H3RCImageReference:'image',H3RCAudioReference:'audio',H3RCVideoReference:'video'}[data.name];
 if(!kind)return;
 const created=NodeType.prototype.onNodeCreated;
 NodeType.prototype.onNodeCreated=function(){created?.apply(this,arguments);const node=this,box=el('div');box.style.cssText=style+'box-sizing:border-box;width:100%';
  const tag=el('strong',box),fileRow=el('div',box),select=el('select',fileRow);fileRow.className='h3rc-file-row';select.style.cssText=style+'max-width:100%';
  const browse=kind==='image'?button(fileRow,'Browse images…',async()=>{try{const picker=await import('../load_image_x.js');picker.installLoadImageXBrowserCSS();const w=node.widgets.find(w=>w.name==='file');picker.openLoadImageXPicker(node,w,{loadNativePreview:false,onSelect:item=>{set(node,'file',item.path);set(node,'source','Load file');update();},onEmpty:()=>{set(node,'file','');update();}});}catch(e){status.textContent='Image browser requires WorkflowX Load ImageX: '+e.message;}}):null;
  if(kind==='image')select.style.display='none';
  const audioHelp=el('div',box);audioHelp.className='h3rc-hint';
  const status=el('div',box);status.style.cssText='white-space:pre-wrap;font-size:11px;color:#aab9c8';
  const frame=el('div',box);frame.className=kind==='audio'?'':'h3rc-media-frame';frame.title='Drag the lower-right corner to resize the preview.';const preview=el(kind==='image'?'img':kind,frame);preview.style.cssText='display:none';if(kind!=='image')preview.controls=true;
  if(kind!=='audio')rememberHeight(node,frame,'media-preview-height',180,80,600);
  node.h3rcShowMedia=files=>{const f=files?.[0];if(!f)return;preview.onloadedmetadata=null;preview.ontimeupdate=null;preview.src=api.apiURL('/view?'+new URLSearchParams(f));preview.style.display='block';};
  const associations=[];
  for(const [field,label] of [['associated_character','Associated character'],...(kind==='video'?[['audio_character','Soundtrack character']]:[])]){
   const row=el('label',box,label+' '),pick=el('select',row);row.className='h3rc-association-row';pick.style.cssText=style;pick.title=HELP[field]||label;row.title=pick.title;
   pick.onchange=()=>set(node,field,pick.value);associations.push({field,pick,row});
  }

  async function files(){try{const r=await api.fetchApi('/h3refcharacters/media-files?kind='+kind);const d=await r.json();select.replaceChildren();el('option',select,'Select a file').value='';for(const name of d.files)el('option',select,name).value=name;select.value=values(node).file||'';}catch(e){status.textContent=e.message;}}
  select.onchange=()=>{set(node,'file',select.value);set(node,'source','Load file');update();};
  const refresh=button(fileRow,'↻',files);refresh.title='Refresh available files';if(kind==='image')refresh.style.display='none';
  const upload=el('input',fileRow);upload.type='file';upload.accept=kind+'/*';upload.style.display='none';
  button(fileRow,'Upload '+kind,()=>upload.click());
  upload.onchange=async()=>{if(!upload.files[0])return;try{const form=new FormData();form.append('image',upload.files[0]);form.append('overwrite','false');const r=await api.fetchApi('/upload/image',{method:'POST',body:form});const d=await r.json();if(!r.ok)throw Error(d.error||'Upload failed');const name=(d.subfolder?d.subfolder+'/':'')+d.name;set(node,'file',name);set(node,'source','Load file');await files();update();}catch(e){status.textContent=e.message;}};
  node.h3rcDescriptor=()=>{const w=values(node);if(node.h3rcRuntimeDescriptor&&node.h3rcRuntimeSignature===JSON.stringify(w)){return {...node.h3rcRuntimeDescriptor,source_identity:identity(node,w)};}const target=normalize(w.associated_character);const ref={kind,tag:normalize(w.tag),role:w.role,target,descriptor:w.descriptor||'',reference_type:w.reference_type,retain:w.retain||'',change:w.change||'',instructions:(kind==='audio'?[w.retain?'Retain: '+w.retain:'',w.change?'Change: '+w.change:'']:[]).filter(Boolean).join(' '),source:w.source==='Load file'?w.file:w.source,
    source_identity:identity(node,w),duration:w.duration_seconds||'remaining',batch_count:w.batch_selection&&w.batch_selection!=='all'?w.batch_selection.split(',').length:1};
   if(kind==='video'&&w.use_soundtrack)ref.soundtrack={kind:'audio',tag:normalize(w.audio_tag),role:w.audio_role,target:normalize(w.audio_character),instructions:w.audio_instructions||'',source:ref.source,source_identity:ref.source_identity};
   return ref;
  };
  const advancedLabel=el('label',box),advanced=el('input',advancedLabel);advanced.type='checkbox';advancedLabel.append(' Choose images from a connected batch');advancedLabel.title=HELP.batch_selection;advancedLabel.style.display=kind==='image'?'block':'none';restoreUI(node,()=>{advanced.checked=!!readUI(node,'batch-options',false);});advanced.onchange=()=>{writeUI(node,'batch-options',advanced.checked);update();};
  let last='';
  function update(){const w=values(node),endpoint=kind==='image'&&['First frame','Last frame'].includes(w.role);audioHelp.style.display='none';audioHelp.textContent='';advancedLabel.style.display=kind==='image'&&w.source==='Connected input'?'block':'none';tag.textContent='@'+normalize(w.tag);fileRow.style.display=w.source==='Load file'?'grid':'none';
   for(const {field,pick,row} of associations){row.style.display=endpoint||(field==='audio_character'&&!w.use_soundtrack)?'none':'grid';const tags=charactersFor(node),chosen=normalize(w[field]);if(chosen&&!tags.includes(chosen))tags.push(chosen);const signature=JSON.stringify(tags);if(pick.dataset.signature!==signature){pick.replaceChildren();el('option',pick,'No character association').value='';for(const a of tags)el('option',pick,'@'+a).value=a;pick.dataset.signature=signature;}pick.value=chosen;}
   for(const widget of node.widgets||[]){if(['associated_character','audio_character'].includes(widget.name)){visibility(widget,false);}}
   if(kind==='video')for(const key of ['audio_tag','audio_role','audio_instructions'])visibility(node.widgets.find(x=>x.name===key),!!w.use_soundtrack);
   visibility(node.widgets.find(x=>x.name==='batch_selection'),kind==='image'&&advanced.checked&&w.source==='Connected input');visibility(node.widgets.find(x=>x.name==='fps'),w.source==='Connected frames');for(const key of ['reference_type','retain','change'])visibility(node.widgets.find(x=>x.name===key),!endpoint);
   if(retainGroup)retainGroup.style.display=endpoint?'none':'';
   visibility(node.widgets.find(x=>x.name==='use_instructions'),false);
   if(kind==='audio')visibility(node.widgets.find(x=>x.name==='descriptor'),w.role==='custom');
   for(const input of node.inputs||[]){const active=kind==='video'?(input.name==='video'?w.source==='Connected video':input.name==='frames'?w.source==='Connected frames':input.name==='audio'?w.source==='Connected frames'&&w.use_soundtrack:true):w.source==='Connected input';input.label=active?input.name:input.name+' (inactive for selected source)';}
   node.h3rcSyncFields?.();
   if(browse){browse.textContent=w.file?'Browse images · '+String(w.file).split(/[\\/]/).pop():'Browse images…';browse.title=w.file||'Choose an image from the thumbnail browser';fileRow.style.gridTemplateColumns='minmax(0,1fr) auto';}
   const signature=JSON.stringify(w);if(signature===last)return;last=signature;
   if(w.source==='Load file'&&w.file){const path=String(w.file).replaceAll('\\','/');const parts=path.split('/');const filename=parts.pop();preview.src=api.apiURL('/view?type=input&filename='+encodeURIComponent(filename)+'&subfolder='+encodeURIComponent(parts.join('/')));preview.style.display='block';if(kind!=='image'){preview.onloadedmetadata=()=>preview.currentTime=Number(w.start_seconds)||0;preview.ontimeupdate=()=>{const end=Number(w.start_seconds)+Number(w.duration_seconds);if(w.duration_seconds>0&&preview.currentTime>end)preview.pause();};}status.textContent='Source preview';}
   else {preview.style.display='none';status.textContent='Preview available after running.';}
  }
  const form=compactFields(node,box,['source','tag','role','descriptor','reference_type','retain','change','batch_selection',...(kind!=='image'?['fps','start_seconds','duration_seconds']:[]),...(kind==='video'?['use_soundtrack','audio_tag','audio_role','audio_instructions']:[])]);
  const retainGroup=groupFields(form,'Retain and change',['reference_type','retain','change'],true);
  if(kind!=='image')groupFields(form,'Selected range',['fps','start_seconds','duration_seconds']);
  if(kind==='video')groupFields(form,'Video soundtrack',['use_soundtrack','audio_tag','audio_role','audio_instructions']);
  if(kind==='image'){const row=form.querySelector('[data-field=role]');if(row){row.title='First frame and Last frame establish the opening or ending image. Select exactly one image. It is resized proportionally and cropped at the centre to fill the output; edges may be removed. Other roles supply ordinary references.';for(const input of row.querySelectorAll('select'))input.title=row.title;}}
  box.insertBefore(fileRow,form);tag.remove();for(const {row} of associations)form.append(row);form.append(audioHelp);
  this.addDOMWidget('named_media_controls','div',box,panelOptions(box,node));this.h3rcMediaStatus=status;
  for(const key of ['source','preservation','use_soundtrack','audio_role','role']){const widget=node.widgets.find(w=>w.name===key);if(widget){const previous=widget.callback;widget.callback=function(){previous?.apply(this,arguments);update();};}}
  restoreUI(node,()=>{last='';setTimeout(update,0);});this.h3rcMediaTimer=setInterval(update,1500);this.setSize([400,kind==='video'?650:kind==='audio'?500:560]);files();setTimeout(update,0);
 };
 const removed=NodeType.prototype.onRemoved;NodeType.prototype.onRemoved=function(){clearInterval(this.h3rcMediaTimer);removed?.apply(this,arguments);};
 const executed=NodeType.prototype.onExecuted;NodeType.prototype.onExecuted=function(m){executed?.apply(this,arguments);if(this.h3rcMediaStatus&&m.text)this.h3rcMediaStatus.textContent=m.text.join('\n');if(m.h3rc_preview)this.h3rcShowMedia?.(m.h3rc_preview);if(m.h3rc_descriptor){this.h3rcRuntimeDescriptor=m.h3rc_descriptor[0];this.h3rcRuntimeSignature=JSON.stringify(values(this));}};
}});
app.registerExtension({name:'H3RefCharacters.SourceRanges',beforeRegisterNodeDef(NodeType,data){
 if(data.name!=='H3RCCreateFromFolder')return;
 const created=NodeType.prototype.onNodeCreated;
 NodeType.prototype.onNodeCreated=function(){created?.apply(this,arguments);const node=this,box=el('div');box.className='h3rc-panel';const status=el('div',box);
  const editButton=button(box,'Edit source media',async()=>{try{
   status.textContent='Loading media previews…';
   const r=await api.fetchApi('/h3refcharacters/folder-sources?path='+encodeURIComponent(values(node).folder));const d=await r.json();if(!r.ok)throw Error(d.error);
   const entries=values(node).source_ranges;
   openSourceEditor(d.sources,entries,values(node),(selection,settings)=>{
    set(node,'source_ranges',JSON.stringify(selection,null,2));
    for(const key of ['voice_duration_limit','maximum_total_voice_duration','video_duration_limit','maximum_total_video_duration','sample_frames'])set(node,key,settings[key]);
    node.h3rcSyncFields?.();status.textContent=selection.filter(x=>x.enabled!==false).length+' sources selected';
   },node);status.textContent='';
  }catch(e){status.textContent=e.message;}});
  if(node.h3rcCreationForm&&editButton){const holder=el('div');holder.style.gridColumn='1/-1';holder.append(editButton);node.h3rcCreationForm.insertBefore(holder,node.h3rcCreationForm.querySelector(':scope > details'));}
  const reportGroup=el('details',box);rememberDetails(node,reportGroup,'creation-result');el('summary',reportGroup,'Creation result and selected ranges');const report=el('textarea',reportGroup);report.readOnly=true;report.placeholder='Run creation to see selected ranges, omitted sources and totals.';report.style.cssText=style+'width:100%;height:120px;min-height:60px;resize:vertical;box-sizing:border-box';rememberHeight(node,report,'creation-report-height',120,60,800);this.h3rcCreationReport=report;
  this.addDOMWidget('source_range_editor','div',box,panelOptions(box,node));
 };
 const executed=NodeType.prototype.onExecuted;NodeType.prototype.onExecuted=function(m){executed?.apply(this,arguments);if(this.h3rcCreationReport)this.h3rcCreationReport.value=(m.text||[]).join('\n');};
}});

app.registerExtension({name:'H3RefCharacters.InspectText',beforeRegisterNodeDef(NodeType,data){
 if(data.name!=='H3RCInspectText')return;
 const created=NodeType.prototype.onNodeCreated;
 NodeType.prototype.onNodeCreated=function(){created?.apply(this,arguments);const text=document.createElement('textarea');text.readOnly=true;text.style.cssText=style+'width:100%;height:100%;box-sizing:border-box';this.addDOMWidget('text_preview','div',text,{serialize:false});this.h3rcText=text;this.h3rcSetText=value=>{this.properties??={};this.properties.h3rcLastText=String(value??'');text.value=this.properties.h3rcLastText;};text.value=this.properties?.h3rcLastText||'';this.setSize([600,500]);};
 const configured=NodeType.prototype.onConfigure;NodeType.prototype.onConfigure=function(){configured?.apply(this,arguments);if(this.h3rcText)this.h3rcText.value=this.properties?.h3rcLastText||'';};
 const serialized=NodeType.prototype.onSerialize;NodeType.prototype.onSerialize=function(info){serialized?.apply(this,arguments);info.properties??={};info.properties.h3rcLastText=this.h3rcText?.value??this.properties?.h3rcLastText??'';};
 const executed=NodeType.prototype.onExecuted;NodeType.prototype.onExecuted=function(m){executed?.apply(this,arguments);this.h3rcSetText?.((m.text||[]).join('\n'));};
}});
