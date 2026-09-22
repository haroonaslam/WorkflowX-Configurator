import { scheduleSocketSync, refreshSocketLabels } from './socket_state.js';
import { profileControls } from './profiles_ui.js';
import { rememberDetails } from './ui_state.js';
import { chooseReferences } from './reference_editor.js';
import { HELP, LABELS, helpFor } from './help_text.js';
import { compactFields, panelOptions, groupFields } from './layout.js';
import { app } from '../../../scripts/app.js';
import { api } from '../../../scripts/api.js';

const css = `background:#18212b;color:#e8eef4;border:1px solid #496078;border-radius:8px;padding:10px;font:14px system-ui;`;
function el(tag,text,parent){const e=document.createElement(tag);if(text)e.textContent=text;if(parent)parent.append(e);return e;}
function button(text,parent,fn){const b=el('button',text,parent);b.style.cssText=css+'cursor:pointer;margin:4px;';b.onclick=fn;return b;}
async function request(path,body){const r=await api.fetchApi('/h3refcharacters/'+path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:undefined);const d=await r.json();if(!r.ok)throw Error(d.error||r.statusText);return d;}
async function copyAlias(alias){await navigator.clipboard.writeText('@'+alias);}

async function browser(node){
 const overlay=el('div');overlay.style.cssText='position:fixed;inset:0;background:#000a;z-index:10000;display:grid;place-items:center';document.body.append(overlay);
 const panel=el('section','',overlay);panel.style.cssText=css+'width:min(1000px,90vw);height:85vh;max-height:90vh;min-width:0;box-sizing:border-box;display:flex;flex-direction:column;overflow:hidden;';
 const toolbar=el('div','',panel);toolbar.style.cssText='display:flex;align-items:center;gap:8px;flex-wrap:wrap;flex-shrink:0';el('strong','Choose a character',toolbar);button('Close',toolbar,()=>overlay.remove());
 const address=el('div','',panel);address.style.cssText='overflow-wrap:anywhere;margin:8px';
 const status=el('div','',panel);status.setAttribute('role','status');
 const scroll=el('div','',panel);scroll.style.cssText='overflow:auto;min-height:0;flex:1;';
 const warnings=el('details','',scroll);warnings.hidden=true;const warningTitle=el('summary','',warnings);warningTitle.style.cssText='cursor:pointer;padding:8px;color:#edc58b';const warningList=el('ul','',warnings);warningList.style.cssText='overflow-wrap:anywhere;padding-right:12px;line-height:1.5';
 const content=el('div','',scroll);content.style.cssText='display:grid;grid-template-columns:repeat(auto-fill,minmax(min(190px,100%),1fr));gap:12px;padding:8px;';
 let current='';
 button('Generate missing thumbnails',toolbar,async()=>{try{
  status.textContent='Scanning all registered character folders…';const pending=[],seen=new Set(),files=new Set();
  const roots=await request('list?path=');const todo=[...roots.roots];
  while(todo.length){const path=todo.shift();if(seen.has(path))continue;seen.add(path);const d=await request('list?path='+encodeURIComponent(path));
   for(const c of d.entries){if(c.visuals.length&&!c.preview&&!files.has(c.path)){files.add(c.path);pending.push(c);}}
   todo.push(...d.dirs.map(d=>d.path));
  }
  if(!pending.length){status.textContent='All visual characters already have thumbnails.';return;}
  status.textContent=pending.length+' missing previews found; existing previews will be kept.';await thumbnail(pending);
 }catch(e){status.textContent=e.message;}}).title='Scan all registered folders and generate only missing previews. Existing thumbnails and tensors are preserved. Select the H3 visual VAE before queuing.';
 async function edit(c){
  content.replaceChildren();
  const form=el('div','',content);form.style.cssText='grid-column:1/-1;display:grid;gap:10px';
  el('h3','Character details',form);
  el('p','These are the saved character files. Normally leave them unchanged. One visual file can hold information from many pictures and videos. You can pair it with a saved voice file here. To use a new MP3 or WAV recording, use H3 Audio Reference instead.',form);
  if(c.visuals.length&&c.preview)button('Replace this character thumbnail…',form,()=>thumbnail(c));const fields={};
  for(const [key,label] of [['display_name','Display name'],['alias','Prompt alias (without @)'],['descriptor','Descriptor'],['description','Description (catalog notes)'],['voices','Saved audio .safetensors file (optional)'],['visuals','Saved visual .safetensors file']]){
   const lab=el('label',label,form);lab.title=key==='descriptor'?'What this subject is, for example: a South Asian woman. Used in H3 subject definitions; saved in the character metadata.':key==='voices'?'Select an encoded H3 voice .safetensors file, not WAV/MP3. Leave empty for visual-only characters.':key==='visuals'?'The visual .safetensors file contains the saved appearance references. Profile mappings refer to this file; recreate the package to change the visual sources.':label;const input=el(key==='description'||(['visuals','voices'].includes(key)&&(c[key]||[]).length>1)?'textarea':'input','',lab);input.value=['visuals','voices'].includes(key)?(c[key]||(key==='voices'&&c.voice?[c.voice]:[])).join('\n'):c[key]||'';input.style.cssText=css+'display:block;width:95%;';if(key==='visuals'&&c.profile_layout)input.readOnly=true;fields[key]=input;
  }
  button('Save Character Details',form,async()=>{try{const saved=await request('details',{path:c.path,...Object.fromEntries(Object.entries(fields).map(([k,v])=>[k,['visuals','voices'].includes(k)?v.value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean):v.value]))});status.textContent='Saved @'+saved.alias;window.dispatchEvent(new Event('h3rc-details-changed'));if(node.widgets.find(w=>w.name==='character_path').value===c.path){node.widgets.find(w=>w.name==='character_path').value=saved.path;await node.h3rcRefresh();}await load(current);}catch(e){status.textContent=e.message;}});
  button('Back',form,()=>load(current));
 }
 async function thumbnail(c){
  const entries=Array.isArray(c)?c:[c];const missingOnly=Array.isArray(c);
  content.replaceChildren();const form=el('div','',content);form.style.gridColumn='1/-1';
  el('h3',missingOnly?'Generate '+entries.length+' missing thumbnails':'Replace this thumbnail',form);el('p','Choose the H3 picture/video VAE from the example workflow to make a preview from each saved character. The saved characters are not changed. '+(missingOnly?'Existing thumbnails are skipped.':''),form);
  const select=el('select','',form);select.style.cssText=css;
  try{const r=await api.fetchApi('/object_info/VAELoader');const d=await r.json();
   for(const name of d.VAELoader.input.required.vae_name[0]){const o=el('option',name,select);o.value=name;if(/minimax.*video.*vae/i.test(name))o.selected=true;}
  }catch(e){status.textContent=e.message;return;}
  button('Queue thumbnail generation',form,async()=>{try{
   const prompt={'1':{class_type:'VAELoader',inputs:{vae_name:select.value}}};entries.forEach((entry,i)=>{prompt[String(i+2)]={class_type:'H3RCPrepareThumbnail',inputs:{character_path:entry.path,regenerate:!missingOnly,vae:['1',0]}};});
   const response=await api.fetchApi('/prompt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt})});const queued=await response.json();
   if(!response.ok)throw Error(JSON.stringify(queued));status.textContent='Thumbnail queued...';
   const timer=setInterval(async()=>{try{const r=await api.fetchApi('/history/'+queued.prompt_id);const h=(await r.json())[queued.prompt_id];if(!h)return;clearInterval(timer);
    if(h.status?.status_str==='error'){status.textContent='Thumbnail failed: '+JSON.stringify(h.status.messages);return;}
    status.textContent='Thumbnail saved';window.dispatchEvent(new Event('h3rc-details-changed'));await load(current);await node.h3rcRefresh();
   }catch(e){clearInterval(timer);status.textContent=e.message;}},2000);
  }catch(e){status.textContent=e.message;}});
  button('Back',form,()=>load(current));
 }
 async function load(path){try{
  const data=await request('list?path='+encodeURIComponent(path));current=data.current;address.textContent=current;content.replaceChildren();status.textContent='';
  const errors=[...new Set(data.errors||[])];warnings.hidden=!errors.length;warnings.open=false;warningTitle.textContent=errors.length+' files could not be loaded — show details';warningList.replaceChildren();for(const error of errors)el('li',error,warningList);
  const nav=el('div','',content);nav.style.gridColumn='1/-1';
  if(data.parent)button('Up one folder',nav,()=>load(data.parent));
  for(const root of data.roots)button('Root: '+root.split(/[\\/]/).pop(),nav,()=>load(root));
  button('Refresh',nav,()=>load(current));
  for(const dir of data.dirs)button('📁 '+dir.name,content,()=>load(dir.path));
  for(const c of data.entries){
   const card=el('article','',content);card.style.cssText=css+'padding:8px;min-width:0;overflow-wrap:anywhere;';
   if(c.preview){const img=el('img','',card);img.src=api.apiURL('/h3refcharacters/preview?path='+encodeURIComponent(c.preview)+'&v='+Date.now());img.style.cssText='width:100%;height:180px;object-fit:cover;border-radius:5px';img.loading='lazy';img.alt=c.display_name;}
   else {const placeholder=el('div',c.visuals.length?'No preview image':'Audio-only character',card);placeholder.style.cssText='height:110px;display:grid;place-items:center;background:#223342;border-radius:5px;color:#9aabb9;margin-bottom:8px';}
   el('strong',c.display_name,card);const tag=el('div','@'+c.alias,card);tag.style.cssText='color:#8fe5d1;font-size:17px;font-weight:bold;margin:5px 0;overflow-wrap:anywhere';
   el('div',`${c.visuals.length} visual reference(s) · ${c.voice?'voice available':'no saved voice'}`,card);
   button('Select',card,async()=>{node.widgets.find(w=>w.name==='character_path').value=c.path;await node.h3rcRefresh();app.graph.setDirtyCanvas(true,true);overlay.remove();});

   button(c.path.endsWith('.character.json')?'Edit character details':'Prepare for Character Use',card,()=>edit(c));

  }
 }catch(e){status.textContent=e.message;}}
 await load('');
}

app.registerExtension({name:'H3RefCharacters.Picker',async beforeRegisterNodeDef(NodeType,data){
 if(data.name.startsWith('H3RC')){
  for(const group of Object.values(data.input||{}))for(const [key,spec] of Object.entries(group||{}))if(HELP[key]&&Array.isArray(spec)){spec[1]??={};spec[1].tooltip=helpFor(key,data.name);}
  const original=NodeType.prototype.onNodeCreated;
  NodeType.prototype.onNodeCreated=function(){original?.apply(this,arguments);
   const labels={visual_references:'Visual references',saved_character_conditioning:'Saved character conditioning',allow_reference_overflow:'Allow counts beyond documented limits',budget_mode:'Budget mode',manual_reference_budget:'Manual reference budget',source:'Media source',file:'Selected file',tag:'Prompt tag',associated_character:'Associated character',use_instructions:'Use instructions',batch_selection:'Image batch positions (all or 1,3)',start_seconds:'Start time (seconds)',duration_seconds:'Duration (seconds; 0 = remaining)',fps:'Frame-batch FPS',use_soundtrack:'Use video soundtrack',audio_tag:'Soundtrack prompt tag',audio_role:'Soundtrack role',audio_mode:'Audio transfer / reuse mode',audio_character:'Soundtrack associated character',audio_instructions:'Soundtrack use instructions',maximum_total_voice_duration:'Maximum total voice duration (seconds)',maximum_total_video_duration:'Maximum total video duration (seconds)',voice_duration_limit:'Voice duration cap',video_duration_limit:'Video duration cap',source_ranges:'Ordered source ranges',character_path:'Selected character file',use_saved_voice:'Use saved voice',display_name:'Display name',prompt_alias:'Prompt alias',description:'Character description',ref_image_size:'Regular image sizing',character_alias:'Associate with @character',reference_type:'Reference type',role:'What to use this reference for',length:'Video length (frames)',prompt:'Your complete H3 prompt'};
   for(const w of this.widgets||[]){if(LABELS[w.name]||labels[w.name])w.label=LABELS[w.name]||labels[w.name];if(HELP[w.name]){w.tooltip=helpFor(w.name,data.name);if(w.options)w.options.tooltip=w.tooltip;}}
  };
 }
 if(data.name==='H3RCCreateFromFolder'){
  const created=NodeType.prototype.onNodeCreated;
  NodeType.prototype.onNodeCreated=function(){created?.apply(this,arguments);
   const node=this,box=el('div');
   const names=['folder','display_name','package_name','prompt_alias','descriptor','description'];
   const update=()=>node.h3rcSyncFields?.();
   const form=compactFields(node,box,names);node.h3rcCreationForm=form;
   profileControls(node,form);
   groupFields(form,'Catalog notes',['description']);
   const connections=node.onConnectionsChange;node.onConnectionsChange=function(){connections?.apply(this,arguments);setTimeout(update,0);};
   this.addDOMWidget('creation_controls','div',box,panelOptions(box,node));
   const configured=this.onConfigure;this.onConfigure=function(){configured?.apply(this,arguments);setTimeout(update,0);};
   update();this.setSize([460,760]);
  };
 }
 if(data.name==='H3RCModReferenceToVideo'){
  const created=NodeType.prototype.onNodeCreated;
  NodeType.prototype.onNodeCreated=function(){created?.apply(this,arguments);const renameOutputs=()=>{if(this.outputs?.[2])this.outputs[2].label='Prompt';if(this.outputs?.[3])this.outputs[3].label='assignments';};renameOutputs();const configuredOutputs=this.onConfigure;this.onConfigure=function(){configuredOutputs?.apply(this,arguments);renameOutputs();};const node=this,box=el('div');box.style.cssText=css+'box-sizing:border-box;width:100%';
   node.properties??={};
   const promptWidget=node.widgets.find(w=>w.name==='prompt');
   const promptEditor=promptWidget.inputEl||promptWidget.element;
   let promptHeight=node.properties.h3rcPromptHeight||120;
   if(promptEditor){
    promptEditor.setAttribute('aria-label','Your complete H3 prompt');
    promptEditor.style.cssText+=';box-sizing:border-box;resize:vertical;min-height:60px;max-height:1200px;overflow:auto;font:14px monospace;margin:0;';
    promptEditor.style.height=promptHeight+'px';
    promptWidget.options??={};promptWidget.options.hideOnZoom=false;
    const externalPrompt=()=>node.inputs?.some(input=>input.name==='prompt'&&input.link!=null)||promptWidget.type==='converted-widget';
    promptWidget.options.getMinHeight=()=>externalPrompt()?28:promptHeight+12;promptWidget.options.getMaxHeight=()=>externalPrompt()?28:promptHeight+12;
    node.h3rcSyncPromptSize=()=>{const hidden=externalPrompt();if(hidden){promptWidget.computeSize=()=>[0,24];const socket=node.inputs?.find(input=>input.name==='prompt');if(socket)socket.label='prompt';}else if(promptWidget.h3rcWasExternal){delete promptWidget.computeSize;}promptWidget.h3rcWasExternal=hidden;promptEditor.style.display=hidden?'none':'';promptEditor.style.minHeight=hidden?'0px':'60px';promptEditor.style.height=hidden?'0px':promptHeight+'px';node.setSize([node.size[0],node.computeSize()[1]]);node.graph?.setDirtyCanvas(true,true);};
    let resizing=false;
    promptEditor.addEventListener('pointerdown',e=>{const r=promptEditor.getBoundingClientRect();resizing=e.clientX>r.right-24&&e.clientY>r.bottom-24;});
    const finishResize=()=>{if(!resizing)return;resizing=false;promptHeight=Math.max(60,promptEditor.offsetHeight);node.properties.h3rcPromptHeight=promptHeight;node.setSize([node.size[0],node.computeSize()[1]]);node.graph?.setDirtyCanvas(true,true);};
    document.addEventListener('pointerup',finishResize);node.h3rcPromptObserver={disconnect(){document.removeEventListener('pointerup',finishResize);}};
    const restorePrompt=node.onConfigure;node.onConfigure=function(){restorePrompt?.apply(this,arguments);setTimeout(()=>{promptHeight=node.properties.h3rcPromptHeight||120;node.h3rcSyncPromptSize();},0);};
   }
   const details=el('details','',box);rememberDetails(node,details,'reference-details',()=>!!node.properties.h3rcReferenceDetailsOpen);el('summary','Reference details',details);
   const calculated=el('div','Calculated reference tokens: pending',box);node.h3rcCalculated=calculated;
   const output=el('pre','',box);output.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere;margin:12px 0;font:12px monospace;';Object.defineProperty(output,'value',{get(){return this.textContent;},set(v){this.textContent=v;}});
   const budgetNotice=el('div','',box);budgetNotice.style.cssText='white-space:pre-wrap;font-size:13px;margin:8px 0';
   const countNotice=el('div','',box);countNotice.style.cssText='white-space:pre-wrap;margin:8px 0;color:#ffd18a';const actions=el('div','',box);
   const conditioningLabel=el('label','Saved character conditioning',box);conditioningLabel.style.cssText='display:grid;gap:6px;margin:0 0 12px;font-size:13px';const conditioningInput=el('select','',conditioningLabel);conditioningInput.style.cssText=css+'width:100%;box-sizing:border-box';const conditioningWidget=node.widgets.find(w=>w.name==='saved_character_conditioning');if(conditioningWidget){conditioningLabel.title=conditioningWidget.options?.tooltip||'Choose whether saved visuals also inform the vision-language encoder. Both choices supply the selected references to the generator.';for(const value of ['Vision-language + direct references','Direct references only']){const option=el('option',value,conditioningInput);option.value=value;}conditioningInput.value=conditioningWidget.value;conditioningWidget.hidden=true;conditioningWidget.type='converted-widget';conditioningWidget.draw=()=>{};conditioningWidget.computeSize=()=>[0,-4];conditioningInput.onchange=()=>{conditioningWidget.value=conditioningInput.value;node.h3rcUpdate?.(true);};}
   const advanced=el('details','',box);rememberDetails(node,advanced,'reference-counts');el('summary','Advanced reference counts',advanced);const allowLabel=el('label',' Allow counts beyond documented limits',advanced),allowInput=el('input','',allowLabel);allowInput.type='checkbox';allowLabel.prepend(allowInput);allowLabel.title='Permit counts outside documented input allowances. Successful processing does not establish reliable output quality.';const allowWidget=node.widgets.find(w=>w.name==='allow_reference_overflow');if(allowWidget){allowWidget.hidden=true;allowWidget.type='converted-widget';allowWidget.draw=()=>{};allowWidget.computeSize=()=>[0,-4];allowInput.checked=!!allowWidget.value;allowInput.onchange=()=>{allowWidget.value=allowInput.checked;node.h3rcUpdate?.(true);};}
   const breakdown=el('div','',box);breakdown.style.cssText='white-space:pre-wrap;font-size:12px';
   const manualLabel=el('label','Manual reference budget ',box),manualInput=el('input','',manualLabel);manualInput.type='number';manualInput.min=1;manualInput.max=1048576;
   for(const [name,input] of [['manual_reference_budget',manualInput]]){const w=node.widgets.find(x=>x.name===name);w.hidden=true;w.type='converted-widget';w.draw=()=>{};w.computeSize=()=>[0,-4];input.value=w.value;input.oninput=()=>{const current=node.widgets.find(x=>x.name===name);current.value=Math.max(1,Math.min(1048576,Number(input.value)||1));input.value=current.value;node.h3rcUpdate?.(true);};}
   const widgets=n=>Object.fromEntries((n.widgets||[]).map(w=>[w.name,w.value]));
   let lastLabels={},revision=0,lastPreview='',lastSignatures='';
   const notice=el('div','',box);notice.style.color='#ffd18a';
   node.h3rcUpdate=async(force=false)=>{refreshSocketLabels(node);const requestId=++revision;try{
    if(conditioningWidget&&!['Vision-language + direct references','Direct references only'].includes(conditioningWidget.value))conditioningWidget.value='Vision-language + direct references';
    const settings=widgets(node);manualLabel.style.display=settings.budget_mode==='Manual'?'block':'none';if(document.activeElement!==manualInput)manualInput.value=settings.manual_reference_budget;
    if(allowWidget)allowInput.checked=!!allowWidget.value;if(conditioningWidget)conditioningInput.value=conditioningWidget.value;
    const previewValue=name=>{const input=node.inputs?.find(i=>i.widget?.name===name||i.name===name);if(input?.link==null)return settings[name];const link=node.graph?.links[input.link],source=node.graph?.getNodeById(link?.origin_id);const output=source?.outputs?.[link?.origin_slot];return source?.widgets?.find(w=>w.name===output?.name)?.value??source?.widgets?.find(w=>w.name==='value')?.value??null;};
    const body={width:previewValue('width'),height:previewValue('height'),length:previewValue('length'),saved_character_conditioning:settings.saved_character_conditioning,allow_reference_overflow:settings.allow_reference_overflow,budget_mode:settings.budget_mode,manual_reference_budget:settings.manual_reference_budget,prompt:settings.prompt||'',characters:[],named_references:{},ref_images:{},ref_videos:{},ref_video_audios:{},ref_audios:{}};
    for(const input of [...(node.inputs||[])].sort((a,b)=>Number(a.name.split('_').pop())-Number(b.name.split('_').pop()))){
     if(input.link==null||input.widget)continue;const name=input.name.split('.').pop();
     if(name.startsWith('character_')){
      const link=node.graph?.links[input.link];if(!link||link.target_id!==node.id)continue;const prev=node.graph.getNodeById(link.origin_id);if(!prev)continue;const w=widgets(prev);
      if(prev.mode===2||prev.mode===4)continue;
      if(prev.type!=='H3RCCharacterPicker')throw Error('Character preview requires a picker. Creation outputs resolve during execution.');
      body.characters.push({path:w.character_path,settings:w});
     }else if(name.startsWith('reference_')){
      const link=node.graph?.links[input.link];if(!link||link.target_id!==node.id)continue;const prev=node.graph.getNodeById(link.origin_id);if(!prev)continue;
      if(prev.mode===2||prev.mode===4)continue;
      if(!prev.h3rcDescriptor)throw Error('Named-reference preview requires an H3 Image, Audio, or Video Reference node.');
      body.named_references[name]=prev.h3rcDescriptor();
     }else{const group=name.startsWith('ref_video_audio_')?'ref_video_audios':name.startsWith('ref_image_')?'ref_images':name.startsWith('ref_video_')?'ref_videos':name.startsWith('ref_audio_')?'ref_audios':null;if(group)body[group][name]=true;}
    }
    const d=await request('resolve',body);if(requestId!==revision)return;
    countNotice.textContent=d.reference_counts?.over_limit?'Reference counts exceed documented allowances: '+d.reference_counts.message+'\n'+Object.entries(d.reference_counts.breakdown).map(([name,c])=>`${name}: ${c.image} images, ${c.video} videos, ${c.audio} audio`).join('\n')+(settings.allow_reference_overflow?'\nAdvanced override enabled.':'\nChoose fewer sources, or use Saved combined video.') : '';
    const actionKey=JSON.stringify([d.reference_counts,body.characters]);
    if(actions.dataset.key!==actionKey){actions.dataset.key=actionKey;actions.replaceChildren();
     if(d.reference_counts?.over_limit)for(const input of node.inputs||[]){if(!input.name.split('.').pop().startsWith('character_')||input.link==null)continue;const link=node.graph?.links[input.link],picker=link&&node.graph.getNodeById(link.origin_id);if(picker?.type!=='H3RCCharacterPicker')continue;
      button((picker.h3rcAlias?'@'+picker.h3rcAlias+': ':'')+'Choose references…',actions,()=>chooseReferences(picker).catch(e=>countNotice.textContent=e.message));
      const path=picker.widgets.find(w=>w.name==='character_path')?.value,index=body.characters.findIndex(c=>c.path===path);if(index<0||body.characters[index].settings.visual_references==='Saved combined video')continue;
      const candidate=structuredClone(body);candidate.characters[index].settings.visual_references='Saved combined video';
      request('resolve',candidate).then(result=>{if(actions.dataset.key!==actionKey||result.reference_counts?.over_limit||result.error)return;button('Use combined video for @'+(picker.h3rcAlias||'character'),actions,()=>{const widget=picker.widgets.find(w=>w.name==='visual_references');widget.value='Saved combined video';widget.callback?.(widget.value);picker.h3rcRefresh?.();node.h3rcUpdate(true);});}).catch(()=>{});
     }
    }
    const b=d.budget_status;if(b){const fmt=n=>Number(n).toLocaleString();const pending=b.pending_references?` + ${b.pending_references} media reference(s) pending preprocessing`:'';
     budgetNotice.textContent=b.over_limit?`Over limit: saved characters alone need ${fmt(b.saved_tokens)} tokens — ${fmt(b.saved_tokens-b.limit)} above ${fmt(b.limit)}.${pending? '\nOther media will add to this total.':''}\nChoose fewer references, reduce their size in Choose references, or increase the manual budget.`:`${b.mode==='Automatic'?'Automatic allocation':'Manual budget'}: ${fmt(b.saved_tokens)} ${b.estimated?'estimated ':''}saved-reference tokens${pending}.\n${b.mode==='Automatic'?'No imposed token limit.':'Manual limit: '+fmt(b.limit)+' tokens.'}`;
     budgetNotice.style.color=b.over_limit?'#ffb3a7':'#b9ceda';
     breakdown.textContent=Object.entries(b.characters).map(([tag,c])=>`${tag}: ${fmt(c.total)} (${fmt(c.visual)} visual + ${fmt(c.voice)} voice)`).join('\n');
    }

    if(Object.keys(lastLabels).some(k=>d.labels[k]&&d.labels[k]!==lastLabels[k]))notice.textContent='Reference numbering changed. Check numeric tags in your prompt.';
    lastLabels=d.labels;
    refreshSocketLabels(node,d.labels);
    const previewText=d.error||d.reference_map+'\n\n'+d.expanded_prompt;const signature=JSON.stringify([d.signatures||[],d.budget_status]);if(force||previewText!==lastPreview||signature!==lastSignatures){output.value=previewText;calculated.textContent='Calculated reference tokens: '+(d.calculated_tokens||'pending');}lastPreview=previewText;lastSignatures=signature;app.graph.setDirtyCanvas(true,true);
   }catch(e){if(requestId===revision){output.value=e.message;calculated.textContent='Reference estimate unavailable';budgetNotice.textContent=e.message;breakdown.textContent='';}}};
   node.h3rcInvalidate=()=>{refreshSocketLabels(node);++revision;lastPreview='';lastSignatures='';output.value='Connections changed. Refreshing reference assignments…';breakdown.textContent='';calculated.textContent='Reference estimate pending';
    for(const socket of node.outputs||[])for(const id of socket.links||[]){const link=node.graph?.links[id],dest=link&&node.graph.getNodeById(link.target_id);if(dest?.type==='H3RCInspectText'){for(const w of dest.widgets||[])if(w.type==='text'||w.inputEl?.tagName==='TEXTAREA')w.value='Connections changed — run again to refresh this output.';}}
   };
   const modeControl=node.widgets.find(w=>w.name==='budget_mode'),modeChanged=modeControl.callback;modeControl.callback=function(){modeChanged?.apply(this,arguments);node.h3rcUpdate(true);};
   button('Preview references and prompt',details,()=>node.h3rcUpdate(true));
   button('Dismiss numbering notice',details,()=>notice.textContent='');
   node.h3rcTimer=setInterval(()=>{if(node.graph)node.h3rcUpdate();},3000);
   scheduleSocketSync(node,()=>node.h3rcUpdate());
   box.prepend(conditioningLabel,manualLabel);details.prepend(calculated,countNotice,actions,budgetNotice,breakdown,notice,output);details.append(advanced);
   const panelHeight=()=>Math.ceil(details.scrollHeight+conditioningLabel.scrollHeight+12+(manualLabel.style.display==='none'?0:manualLabel.scrollHeight)+32);
   this.addDOMWidget('resolved_preview','div',box,{serialize:false,hideOnZoom:false,getMinHeight:panelHeight,getMaxHeight:panelHeight});box.style.overflow='visible';box.style.height='auto';this.h3rcOutput=output;
   const infoObserver=new ResizeObserver(()=>{node.setSize([node.size[0],node.computeSize()[1]]);node.graph?.setDirtyCanvas(true,true);});infoObserver.observe(details);node.h3rcInfoObserver=infoObserver;
   details.ontoggle=()=>{node.setSize([node.size[0],node.computeSize()[1]]);node.graph?.setDirtyCanvas(true,true);};

  };
  const configure=NodeType.prototype.onConfigure;NodeType.prototype.onConfigure=function(info){
   configure?.apply(this,arguments);
   const values=info?.widgets_values;
   if(Array.isArray(values)&&values.length>=8&&['Automatic','Manual'].includes(values[5])&&typeof values[6]==='number'&&typeof values[7]==='number'){
    const manual=this.widgets.find(w=>w.name==='manual_reference_budget');if(manual)manual.value=values[7];
   }
   scheduleSocketSync(this,()=>{this.h3rcSyncPromptSize?.();this.h3rcUpdate?.(true);});
  };
  const removed=NodeType.prototype.onRemoved;NodeType.prototype.onRemoved=function(){clearInterval(this.h3rcTimer);this.h3rcPromptObserver?.disconnect();this.h3rcInfoObserver?.disconnect();removed?.apply(this,arguments);};
  const changed=NodeType.prototype.onConnectionsChange;NodeType.prototype.onConnectionsChange=function(){changed?.apply(this,arguments);this.h3rcInvalidate?.();scheduleSocketSync(this,()=>{this.h3rcSyncPromptSize?.();this.h3rcUpdate?.(true);});};
  const executed=NodeType.prototype.onExecuted;NodeType.prototype.onExecuted=function(message){executed?.apply(this,arguments);if(this.h3rcOutput)this.h3rcOutput.value=(message.text||[]).join('\n\n');const exact=(message.text||[]).join(' ').match(/Exact reference tokens: (\d+)/);if(exact&&this.h3rcCalculated)this.h3rcCalculated.textContent='Calculated reference tokens: '+exact[1]+' (exact)';};return;
 }
 if(data.name!=='H3RCCharacterPicker')return;
 const original=NodeType.prototype.onNodeCreated;
 NodeType.prototype.onNodeCreated=function(){original?.apply(this,arguments);
  const node=this, box=el('div');box.style.cssText=css+'box-sizing:border-box;width:100%;overflow:hidden';
  const selected=el('div','Select a character to see its @tag.',box);
  const preview=el('img','',box);preview.style.cssText='display:none;width:72px;height:72px;object-fit:cover;border-radius:5px;margin:6px 0';
  const assetList=el('details','',box);rememberDetails(node,assetList,'character-files');el('summary','What is saved in this character?',assetList);const assetText=el('pre','',assetList);assetText.style.cssText='white-space:pre-wrap;font:12px system-ui';
  const help=el('div','',box);help.style.cssText='font:13px system-ui;color:#b9ccdc;white-space:pre-wrap;margin:8px 0';
  const more=el('details','',box);rememberDetails(node,more,'character-help');el('summary','Help: appearance, voices and visual processing',more);
  el('p','Leave Retain and Change empty to ask H3 to keep this character as shown. Use Retain for details that should stay and Change for a different outfit, hairstyle or other changes. These boxes guide generation; they do not edit the saved character.',more);
  el('p','Use Choose references to select pictures, clips and saved profiles for this generation. Saved files and voices remain unchanged.',more);
  el('p','A saved character contains a visual reference file and, optionally, a voice file. One visual file can represent many photos and video moments; it is not one photo per file. Use the file list only to inspect what is saved. To use a new MP3 or WAV recording, load it with H3 Audio Reference.',more);

  const find=name=>node.widgets.find(w=>w.name===name);
  const hide=(w,hidden)=>{if(!w)return;w.h3rcShow=!hidden;if(w.h3rcReplaced)return;if(!w.h3rcDisplay)w.h3rcDisplay={type:w.type,computeSize:w.computeSize};w.type=hidden?'converted-widget':w.h3rcDisplay.type;w.computeSize=hidden?()=>[0,-4]:w.h3rcDisplay.computeSize;};
  const updateControls=()=>{
   hide(find('reference_selection'),true);
   const c=node.h3rcCharacter;if(find('use_saved_voice'))find('use_saved_voice').h3rcDisabled=!c||!(c.voices?.length||c.voice);
   help.textContent='Choose saved profiles and references. Generation never resizes their encoded data.';
   node.h3rcSyncFields?.();app.graph.setDirtyCanvas(true,true);
  };
  for(const key of ['retain','change']){const w=find(key);if(w){const cb=w.callback;w.callback=function(){cb?.apply(this,arguments);updateControls();};}}
  node.h3rcChooseReferences=()=>chooseReferences(node);
  const representation=find('visual_references');const repCallback=representation?.callback;if(representation)representation.callback=function(){repCallback?.apply(this,arguments);node.h3rcRefresh?.();};
  node.h3rcUpdateControls=updateControls;updateControls();
  let alias='';
  const header=el('div','',box);header.className='h3rc-character-header';header.append(preview);const identity=el('div','',header);identity.className='h3rc-identity';identity.append(selected);button('Browse characters',identity,()=>browser(node));
  more.append(help);
  const form=compactFields(node,box,['use_saved_voice','descriptor','retain','change','visual_references']);
  groupFields(form,'Retain and change',['retain','change'],true);
  const choiceRow=el('div','',form);choiceRow.style.gridColumn='1/-1';button('Choose references…',choiceRow,()=>chooseReferences(node).catch(e=>selectionSummary.textContent=e.message));const selectionSummary=el('div','',choiceRow);selectionSummary.style.cssText='font-size:12px;margin:5px 4px;color:#b9ceda';form.querySelector('[data-field=visual_references]')?.after(choiceRow);
  box.prepend(header);identity.append(form.querySelector('[data-field=use_saved_voice]'));const footer=el('div','',box);footer.className='h3rc-footer';footer.append(assetList,more);
  this.addDOMWidget('character_browser','div',box,panelOptions(box,node));
  this.h3rcRefresh=async()=>{const path=node.widgets.find(w=>w.name==='character_path').value;if(!path){selected.textContent='No character selected';preview.style.display='none';alias='';return;}try{const c=await request('character?path='+encodeURIComponent(path));alias=c.alias;node.h3rcAlias=c.alias;node.h3rcCharacter=c;
    const dw=node.widgets.find(w=>w.name==='descriptor');node.properties??={};
    const previousPath=node.properties.h3rcDescriptorPath,previousDefault=node.properties.h3rcDescriptorDefault;
    if(dw&&(!dw.value||(previousPath&&previousPath!==path)||dw.value===previousDefault))dw.value=c.descriptor||'';
    node.properties.h3rcDescriptorPath=path;node.properties.h3rcDescriptorDefault=c.descriptor||'';
    const available=c.reference_catalog||[];const repInput=form.querySelector('[data-field=visual_references] select');if(repInput)for(const option of repInput.options){const combined=option.value==='Saved combined video'||option.value==='Build combined video from selected references';option.disabled=c.external?option.value==='Build combined video from selected references':!available.some(e=>combined?e.group==='combined':e.group!=='combined'&&(option.value!=='Pictures only'||e.kind==='image'));option.title=option.disabled?'No saved profiles for this reference mode.':'';}
    request('reference-selection',{path,settings:Object.fromEntries(node.widgets.map(w=>[w.name,w.value]))}).then(d=>{selectionSummary.textContent=d.selected.filter(e=>e.kind==='image').length+' images · '+d.selected.filter(e=>e.kind==='video').length+' videos · '+d.tokens.toLocaleString()+' visual tokens';}).catch(e=>selectionSummary.textContent=e.message);
    node.h3rcUpdateControls();assetText.textContent='SAVED VISUAL TENSOR FILES (not original source clips)\n'+c.visuals.map((p,i)=>(i+1)+'. '+p.split(/[\\/]/).pop()).join('\n')+'\n\nSAVED VOICE TENSOR FILES\n'+(c.voices||(c.voice?[c.voice]:[])).map((p,i)=>(i+1)+'. '+p.split(/[\\/]/).pop()).join('\n');selected.textContent=`${c.display_name} — @${c.alias} · ${c.voice?'voice available':'no saved voice'}`;preview.style.display=c.preview?'block':'none';if(c.preview)preview.src=api.apiURL('/h3refcharacters/preview?path='+encodeURIComponent(c.preview)+'&v='+Date.now());}catch(e){selected.textContent=e.message;}};
  node.h3rcDetailsListener=()=>node.h3rcRefresh();window.addEventListener('h3rc-details-changed',node.h3rcDetailsListener);
  const pathWidget=node.widgets.find(w=>w.name==='character_path');const prior=pathWidget.callback;pathWidget.callback=function(){prior?.apply(this,arguments);node.h3rcRefresh();};
  this.setSize([380,510]);setTimeout(()=>this.h3rcRefresh(),0);
 };
 const removedPicker=NodeType.prototype.onRemoved;NodeType.prototype.onRemoved=function(){window.removeEventListener('h3rc-details-changed',this.h3rcDetailsListener);removedPicker?.apply(this,arguments);};
 const configured=NodeType.prototype.onConfigure;NodeType.prototype.onConfigure=function(){configured?.apply(this,arguments);setTimeout(()=>{this.h3rcUpdateControls?.();this.h3rcRefresh?.();},0);};
}});
