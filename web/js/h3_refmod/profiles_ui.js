import { rememberDetails } from './ui_state.js';
import { api } from '../../../scripts/api.js';
import { readProfileSettings } from './profile_state.js';
const make=(tag,text,parent)=>{const e=document.createElement(tag);if(text)e.textContent=text;parent?.append(e);return e;};
const defaults=()=>Object.fromEntries(['picture','video','combined'].map(g=>[g,[{id:'1024',name:'1024 short edge',size:1024,enabled:true,downsize:'Lanczos',smaller:g==='combined'?'Pad to target':'Keep size',model:'',framing:'Fit whole image',budget:0}]]));
export function profileControls(node,form){
 const widget=node.widgets.find(w=>w.name==='profiles');let models=[];
 const initialValues=new Map(node.widgets.filter(w=>w.options?.serialize!==false).map(w=>[w.name,structuredClone(w.value)]));
 const holder=make('div','',form);holder.style.cssText='grid-column:1/-1;min-width:0';
 const save=data=>{widget.value=JSON.stringify(data);widget.callback?.(widget.value);node.graph?.setDirtyCanvas(true,true);};
 function render(){holder.replaceChildren();const data=readProfileSettings(widget?.value);
  for(const w of node.widgets)if(initialValues.has(w.name)&&w.name!=='folder')w.h3rcDisabled=!data;
  node.h3rcSyncFields?.();
  if(!data){
   const notice=make('div','',holder);notice.setAttribute('role','alert');notice.style.cssText='border:1px solid #c39759;border-radius:6px;padding:10px;line-height:1.5';
   make('strong','Creation settings need resetting',notice);
   make('p',widget?'This node has incompatible or damaged saved settings. Values may appear under the wrong labels. Reset before editing or creating a RefMod.':'ComfyUI is serving an older creation node definition. Restart ComfyUI, refresh the browser, and add a new creation node.',notice);
   if(widget){const reset=make('button','Reset creation settings',notice);reset.type='button';reset.title='Restores current defaults for identity fields, profiles and source selection. Keeps the source folder, connections and saved RefMod files unchanged.';reset.onclick=()=>{
    for(const w of node.widgets)if(initialValues.has(w.name)&&w.name!=='folder')w.value=structuredClone(initialValues.get(w.name));
    widget.value=JSON.stringify(defaults());node.h3rcSyncFields?.();node.graph?.setDirtyCanvas(true,true);render();
   };}
   return;
  }
  for(const group of ['picture','video','combined']){
   const section=make('details','',holder);rememberDetails(node,section,'profiles:'+group,false,false);section.style.cssText='border-top:1px solid #394b57;padding:8px 0';
   make('summary',({picture:'Picture profiles',video:'Video profiles',combined:'Combined video profiles'})[group]+` · ${data[group].filter(p=>p.enabled).length} enabled`,section);
   const list=make('div','',section);
   data[group].forEach((p,index)=>{
    const row=make('details','',list);rememberDetails(node,row,'profile:'+group+':'+p.id,false,false);row.style.cssText='padding:6px;border:1px solid #394b57;border-radius:5px;margin-top:6px;min-width:0';
    const summary=make('summary','',row);summary.style.cssText='display:flex;align-items:center;gap:8px;min-width:0';
    const enabled=make('input','',summary);enabled.type='checkbox';enabled.checked=p.enabled;enabled.style.width='auto';enabled.setAttribute('aria-label','Enable '+group+' '+p.name);enabled.onclick=e=>e.stopPropagation();enabled.onchange=()=>{p.enabled=enabled.checked;save(data);render();};
    const name=make('span',p.name,summary);name.style.cssText='flex:1;overflow-wrap:anywhere';const sizeLabel=make('small','',summary);const summarize=()=>{name.textContent=p.name;const text=p.size?p.size+' short edge':'Original size';sizeLabel.textContent=p.name===text?'':text;};summarize();make('small','Edit',summary);
    row.addEventListener('toggle',()=>{if(row.open)for(const other of list.children)if(other!==row)other.open=false;});
    const fields=make('fieldset','',row);fields.disabled=!p.enabled;fields.style.cssText='border:0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(160px,100%),1fr));gap:8px;margin-top:10px;min-width:0';
    const controls={};
    function field(key,label,choices,help){
     const l=make('label',label,fields);l.style.cssText='display:flex;flex-direction:column;gap:4px;min-width:0';l.title=help;
     const input=make(choices?'select':'input','',l);input.title=help;input.setAttribute('aria-label',group+' '+label);input.style.cssText='width:100%;min-width:0';
     if(choices){for(const value of choices){const o=make('option',value,input);o.value=value;}}
     else{input.type=typeof p[key]==='number'?'number':'text';if(input.type==='number'){input.min=key==='size'?32:0;input.step=1;}}
     input.value=p[key]??'';input.onchange=()=>{if(!input.reportValidity())return;p[key]=input.type==='number'?Number(input.value):input.value;if(key==='size'&&(/^[0-9]+ short edge$/.test(p.name)||p.name==='Original size')){p.name=p.size+' short edge';controls.name.input.value=p.name;}save(data);visibility();summarize();};controls[key]={l,input};return input;
    }
    field('name','Profile name',null,'Name shown in the generation chooser. Use a name that describes the saved size.');
    const presetLabel=make('label','Saved size',fields);presetLabel.style.cssText='display:grid;gap:4px;min-width:0';const preset=make('select','',presetLabel);preset.setAttribute('aria-label',group+' Saved size');
    for(const [value,text] of [['1024','1024 short edge'],['2048','2048 short edge'],['custom','Custom'],['0','Original size']]){const o=make('option',text,preset);o.value=value;}
    preset.value=p.size_choice??([0,1024,2048].includes(p.size)?String(p.size):'custom');preset.title='The shorter side sets the requested size; the other side follows the source proportions. Original size keeps the source dimensions, with H3 alignment padding.';
    field('size','Shorter side (pixels)',null,preset.title);
    field('downsize','Downsize method',['Lanczos','Bicubic','Area','Nearest exact'],'Lanczos is the default for photographic detail. Bicubic is smoother, Area averages detail, and Nearest exact keeps hard pixel edges. Reducing size saves tokens but removes detail.');
    field('smaller','When the source is smaller',['Keep size','Pad to target','Enlarge with Lanczos','Enlarge with Nearest exact','Enlarge with an upscale model'],'Keep size avoids enlargement. Padding adds borders. Enlargement fills more of the frame but cannot guarantee recovered detail. Models may invent texture; use the original or padded version when fidelity matters.');
    field('model','Upscale model',['',...models],'Uses the standard ComfyUI upscale-model implementation. Select an installed model; missing models stop creation before encoding.');
    if(group==='combined')field('framing','Framing',['Fit whole image','Crop to fill'],'Fit whole image keeps all content and adds borders. Crop to fill can remove edges. The first selected visual sets the shared proportions; the smaller-source setting determines padding or enlargement.');
    if(group!=='picture')field('budget','Maximum reference tokens (0 = no limit)',null,'Leave 0 to keep the full encoded profile. A limit removes similar video samples first, then evenly selects survivors. Combined profiles protect every picture and stop if those alone exceed the allowance. This is not a file-size limit.');
    function visibility(){controls.size.l.hidden=preset.value!=='custom';controls.size.input.disabled=preset.value!=='custom';controls.model.l.hidden=p.smaller!=='Enlarge with an upscale model';controls.model.input.disabled=controls.model.l.hidden;controls.downsize.l.hidden=p.size===0&&group!=='combined';controls.downsize.input.disabled=controls.downsize.l.hidden;}
    preset.onchange=()=>{p.size_choice=preset.value;if(preset.value!=='custom')p.size=Number(preset.value);else if(!p.size)p.size=1024;controls.size.input.value=p.size;if(/^[0-9]+ short edge$/.test(p.name)||p.name==='Original size'){p.name=p.size?p.size+' short edge':'Original size';controls.name.input.value=p.name;}save(data);visibility();summarize();};visibility();
    const remove=make('button','Remove profile',row);remove.type='button';remove.onclick=()=>{data[group].splice(index,1);save(data);render();};
   });
   const add=make('button','Add profile',section);add.type='button';add.onclick=()=>{data[group].push({...defaults()[group][0],id:crypto.randomUUID(),name:'2048 short edge',size:2048});save(data);render();};
  }
 }
 render();node.h3rcRenderProfiles=render;
 const configured=node.onConfigure;node.onConfigure=function(){configured?.apply(this,arguments);setTimeout(render,0);};
 api.fetchApi('/h3refcharacters/upscale-models').then(r=>r.json()).then(d=>{models=d.models||[];render();}).catch(()=>{});
}
