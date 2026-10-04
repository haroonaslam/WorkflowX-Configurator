import { app } from '../../scripts/app.js';
import { api } from '../../scripts/api.js';

const MIME={png:'image/png',jpg:'image/jpeg',webp:'image/webp'};
const saveCounters=new Map();
function reserveNumbers(prefix,count){
  const key='workflowx.view_image_format.counter:'+prefix;
  let next=saveCounters.get(key)||1;
  try{const stored=Number(window.localStorage?.getItem(key));if(Number.isSafeInteger(stored)&&stored>0)next=Math.max(next,stored);}catch{}
  saveCounters.set(key,next+count);
  try{window.localStorage?.setItem(key,String(next+count));}catch{}
  return next;
}
function update(node,text){
  for(const button of node._viewButtons||[])button.disabled=!node._viewToken||Boolean(node._viewSaving);
  if(text&&node._viewStatus){node._viewStatus.textContent=text;node._viewStatus.title=text;}
  node.setDirtyCanvas(true,true);
}
async function save(node,format){
  if(!node._viewToken||node._viewSaving)return;
  const find=name=>node.widgets.find(w=>w.name===name);
  const options={token:node._viewToken,format,...Object.fromEntries(['filename_prefix','quality','include_metadata'].map(k=>[k,find(k).value]))};
  const count=node._viewCount||1;
  node._viewSaving=true;update(node,'Choose save location…');
  try{
    if(!window.showSaveFilePicker)throw new Error('Save As requires Chrome/Edge on localhost or HTTPS. No image was saved.');
    // Select destinations before network work, preserving click activation for Save As.
    const handles=[];
    // Reserve synchronously before Save As to preserve browser click activation.
    // Cancelled attempts intentionally leave gaps, rather than reusing names.
    const first=reserveNumbers(options.filename_prefix,count);
    for(let i=0;i<count;i++){
      const base=options.filename_prefix.replaceAll('\\','/').split('/').pop().replaceAll('%batch_num%',String(i)).replace(/[<>:"|?*]/g,'_')||'ComfyUI';
      handles.push(await window.showSaveFilePicker({suggestedName:base+'_'+String(first+i).padStart(5,'0')+'_.'+format,types:[{description:format.toUpperCase()+' image',accept:{[MIME[format]]:['.'+format]}}]}));
    }
    for(let i=0;i<count;i++){
      update(node,'Saving '+format.toUpperCase()+' '+(i+1)+'/'+count+'…');
      const response=await api.fetchApi('/workflowx/view_image_format/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...options,index:i})});
      if(!response.ok){const error=await response.json();throw new Error(error.error||'Image export failed');}
      const blob=await response.blob(),writer=await handles[i].createWritable();
      try{await writer.write(blob);await writer.close();}catch(error){await writer.abort().catch(()=>{});throw error;}
    }
    let sidecar=null;
    if(format!=='png'&&options.include_metadata){
      const response=await api.fetchApi('/workflowx/view_image_format/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...options,action:'sidecar'})});
      const result=await response.json();if(!response.ok)throw new Error('Image saved, but sidecar failed: '+result.error);sidecar=result.sidecar;
    }
    update(node,'Saved '+count+' '+format.toUpperCase()+' image(s)'+(sidecar?' · Sidecar: output/'+sidecar:''));
  }catch(error){
    const message=error.name==='AbortError'?'Save cancelled':error.message;update(node,message);
    if(error.name!=='AbortError')app.extensionManager?.toast?.add({severity:'error',summary:'View Image (Format)',detail:message,life:8000});
  }finally{node._viewSaving=false;update(node);}
}

app.registerExtension({
  name:'workflowx.view_image_format',
  async beforeRegisterNodeDef(type,data){
    if(data.name!=='WorkflowX_ViewImageFormat')return;
    const created=type.prototype.onNodeCreated;
    type.prototype.onNodeCreated=function(){
      created?.apply(this,arguments);
      const node=this,find=name=>node.widgets.find(w=>w.name===name),session=find('session_key');
      Object.assign(session,{type:'converted-widget',hidden:true,draw:()=>{},computeSize:()=>[0,-4],computeLayoutSize:()=>({minHeight:0,maxHeight:0,minWidth:0})});
      session.options={...session.options,hidden:true};if(session.inputEl)session.inputEl.style.display='none';
      const owner=crypto.randomUUID();session.serializeValue=()=>owner;
      const metadata=find('include_metadata');metadata.label='Include metadata/workflow';metadata.options={...metadata.options,on:'',off:''};
      // Always available because manual JPG/WebP export is independent of auto format.
      find('quality').label='JPG / WebP quality';find('format').label='Automatic save format';
      const root=document.createElement('div');root.style.cssText='display:flex;flex-direction:column;gap:4px;padding:4px;width:100%;box-sizing:border-box;';
      const row=document.createElement('div');row.style.cssText='display:flex;gap:6px;width:100%;';
      node._viewButtons=['png','jpg','webp'].map(format=>{
        const b=document.createElement('button');b.textContent=format.toUpperCase();b.type='button';b.disabled=true;
        b.style.cssText='flex:1;min-width:0;height:28px;border:1px solid var(--border-color,#666);border-radius:5px;background:var(--comfy-input-bg,#222);color:var(--input-text,#ddd);cursor:pointer;';
        b.title='Save full-resolution '+format.toUpperCase()+' to a chosen location.'+(format==='png'?' Metadata is embedded.':' Workflow sidecar is saved once per generation in ComfyUI output.');
        b.addEventListener('click',()=>save(node,format));row.append(b);return b;
      });
      const status=document.createElement('div');status.style.cssText='font:11px system-ui;color:var(--input-text,#bbb);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;';status.textContent='Run the node to preview and save';
      root.append(row,status);for(const name of ['pointerdown','keydown'])root.addEventListener(name,e=>e.stopPropagation());
      node._viewStatus=status;node._viewRoot=root;
      const widget=node.addDOMWidget('format_save_buttons','ViewImageFormat',root,{serialize:false,hideOnZoom:false,getMinHeight:()=>54,getMaxHeight:()=>54});widget.computeSize=()=>[200,54];
    };
    const executed=type.prototype.onExecuted;
    type.prototype.onExecuted=function(message){executed?.apply(this,arguments);this._viewToken=message.workflowx_preview_token?.[0]||null;this._viewCount=message.workflowx_preview_count?.[0]||message.images?.length||1;update(this,message.workflowx_preview_message?.[0]||'Ready');};
    const configured=type.prototype.onConfigure;
    type.prototype.onConfigure=function(){configured?.apply(this,arguments);this._viewToken=null;update(this,'Run the node to preview and save');};
    const serialized=type.prototype.onSerialize;
    type.prototype.onSerialize=function(info){serialized?.apply(this,arguments);const i=this.widgets.findIndex(w=>w.name==='session_key');if(info.widgets_values&&i>=0)info.widgets_values[i]='';};
    const removed=type.prototype.onRemoved;
    type.prototype.onRemoved=function(){this._viewRoot?.remove();removed?.apply(this,arguments);};
  }
});
