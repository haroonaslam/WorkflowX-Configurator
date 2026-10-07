import { app } from '../../scripts/app.js';
import { api } from '../../scripts/api.js';

const NODE='WorkflowX_DetailerXPreview';

function css(){
  if(document.getElementById('workflowx-detailer-preview-css'))return;
  const style=document.createElement('style');style.id='workflowx-detailer-preview-css';style.textContent=`
  .dxp{width:100%;height:100%;box-sizing:border-box;display:flex;flex-direction:column;gap:7px;padding:8px;color:var(--input-text,#ddd);font:12px system-ui;overflow:hidden}
  .dxp-bar{display:grid;grid-template-columns:34px minmax(0,1fr) 34px;align-items:center;gap:6px}
  .dxp-bar.batch{grid-template-columns:34px minmax(0,1fr) 34px;max-width:210px;align-self:center}
  .dxp button,.dxp select{height:28px;border:1px solid var(--border-color,#687487);border-radius:6px;background:var(--comfy-input-bg,#222);color:inherit;min-width:0}
  .dxp button{cursor:pointer}.dxp button:disabled{opacity:.35;cursor:default}.dxp-title{text-align:center;font-weight:650;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .dxp-sub{display:flex;gap:6px;align-items:center}.dxp-sub select{flex:1;padding:0 7px}.dxp-state{font-size:11px;opacity:.72;white-space:nowrap}
  .dxp-view{position:relative;flex:1;min-height:250px;background:#0b0b0b;border:1px solid #3c424b;border-radius:7px;overflow:hidden;display:flex;align-items:center;justify-content:center}
  .dxp-view img{display:block;max-width:100%;max-height:100%;object-fit:contain;user-select:none;-webkit-user-drag:none}.dxp-view.zoom{display:block;overflow:auto}.dxp-view.zoom img{max-width:none;max-height:none;margin:auto}
  .dxp-wipe{position:absolute;inset:0;overflow:hidden}.dxp-wipe img{width:100%;height:100%;object-fit:contain}.dxp-current{position:absolute;inset:0;clip-path:inset(0 0 0 var(--wipe,50%))}.dxp-divider{position:absolute;top:0;bottom:0;left:var(--wipe,50%);width:2px;background:#fff;box-shadow:0 0 0 1px #0008;pointer-events:none}
  .dxp-side{display:grid;grid-template-columns:1fr 1fr;gap:4px;width:100%;height:100%}.dxp-pane{position:relative;display:flex;align-items:center;justify-content:center;min-width:0;overflow:hidden}.dxp-pane span{position:absolute;top:5px;left:5px;background:#000a;padding:2px 5px;border-radius:4px;z-index:2}.dxp-pane img{width:100%;height:100%;object-fit:contain}
  .dxp-range{width:100%;accent-color:#8eb0ff}.dxp-empty{padding:20px;text-align:center;color:#aaa}.dxp-footer{display:flex;justify-content:space-between;align-items:center;gap:6px}.dxp-footer button{padding:0 10px}
  .dxp-modal{position:fixed;inset:0;z-index:100000;background:#05070af2;color:#eef2fa;display:grid;grid-template-rows:auto minmax(0,1fr) auto;gap:10px;padding:14px;font:13px system-ui}
  .dxp-modal-toolbar{display:grid;grid-template-columns:auto minmax(120px,1fr) auto minmax(180px,260px) auto;gap:8px;align-items:center;max-width:1200px;width:100%;margin:auto}.dxp-modal-toolbar button,.dxp-modal-toolbar select,.dxp-modal-footer button{height:34px;border:1px solid #687487;border-radius:7px;background:#1d222b;color:inherit;padding:0 11px}.dxp-modal-toolbar button{min-width:38px;font-size:18px;cursor:pointer}.dxp-modal-toolbar button:disabled,.dxp-modal-footer button:disabled{opacity:.35}.dxp-modal-heading{text-align:center;font-size:15px;font-weight:650;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.dxp-modal-toolbar select{min-width:0}
  .dxp-modal-view{position:relative;min-width:0;min-height:0;overflow:auto;background:#020303;border:1px solid #343b46;border-radius:9px}.dxp-modal-stage{position:relative;overflow:hidden;box-shadow:0 0 0 1px #ffffff18}.dxp-modal-stage img{position:absolute;inset:0;width:100%;height:100%;object-fit:fill;user-select:none;-webkit-user-drag:none}.dxp-modal-stage .dxp-current{position:absolute;inset:0;clip-path:inset(0 0 0 var(--wipe,50%));overflow:hidden}.dxp-modal-stage .dxp-divider{z-index:3}.dxp-modal-tag{position:absolute;top:8px;z-index:4;background:#000b;border:1px solid #ffffff30;border-radius:5px;padding:3px 7px;pointer-events:none}.dxp-modal-tag.left{left:8px}.dxp-modal-tag.right{right:8px}
  .dxp-modal-footer{display:flex;align-items:center;justify-content:center;gap:8px;flex-wrap:wrap}.dxp-modal-footer button{cursor:pointer}.dxp-modal-zoom{min-width:56px;text-align:center;color:#bcc9dd}.dxp-modal-help{position:absolute;left:50%;bottom:12px;transform:translateX(-50%);z-index:5;background:#000b;border-radius:5px;padding:4px 8px;pointer-events:none;opacity:.8;white-space:nowrap}.dxp-modal-close{font-size:20px!important}
  @media(max-width:720px){.dxp-modal{padding:8px}.dxp-modal-toolbar{grid-template-columns:auto minmax(80px,1fr) auto auto}.dxp-modal-toolbar select{grid-column:1/-1}.dxp-modal-help{font-size:11px}}
  `;document.head.append(style);
}
function viewUrl(item){if(!item)return'';return api.apiURL('/view?'+new URLSearchParams({filename:item.filename,subfolder:item.subfolder||'',type:item.type||'temp'}));}
function payload(message){let value=message?.workflowx_detailer_preview;if(Array.isArray(value))value=value[0];return value&&typeof value==='object'?value:null;}
function button(text,title,fn){const b=document.createElement('button');b.type='button';b.textContent=text;b.title=title;b.addEventListener('click',fn);return b;}
function select(options,value,title,onchange){const s=document.createElement('select');s.title=title;for(const [v,label] of options){const o=document.createElement('option');o.value=v;o.textContent=label;s.append(o);}s.value=value;s.addEventListener('change',()=>onchange(s.value));return s;}
function persist(node){node.properties??={};node.properties.detailer_x_preview={stage:node._dxp.stage,batch:node._dxp.batch,compare:node._dxp.compare,layout:node._dxp.layout,zoom:node._dxp.zoom,wipe:node._dxp.wipe};}
function restore(node){const p=node.properties?.detailer_x_preview||{};return{stage:Number(p.stage)||0,batch:Number(p.batch)||0,compare:['off','original','previous'].includes(p.compare)?p.compare:'off',layout:p.layout==='side'?'side':'wipe',zoom:Boolean(p.zoom),wipe:Math.max(5,Math.min(95,Number(p.wipe)||50)),data:null};}
function current(node){const d=node._dxp.data;if(!d)return null;if(!d.stages?.length)return{name:'Original',state:d.bypass_reason||'No processors executed',images:d.original,previous:d.original};return d.stages[Math.max(0,Math.min(node._dxp.stage,d.stages.length-1))];}
function showModal(node){
  const state=node._dxp,d=state.data;if(!d)return;let zoom=Number.isFinite(state.modalZoom)?state.modalZoom:1,natural=[1,1],wipe=state.wipe;
  const modal=document.createElement('div');modal.className='dxp-modal';modal.tabIndex=0;
  const toolbar=document.createElement('div');toolbar.className='dxp-modal-toolbar';const heading=document.createElement('div');heading.className='dxp-modal-heading';
  const previous=button('‹','Previous processor stage',()=>moveStage(-1)),next=button('›','Next processor stage',()=>moveStage(1));
  const comparison=select([['off','Compare: Off'],['original','Compare: Original'],['previous','Compare: Previous processor']],state.compare,'Choose comparison source',value=>{state.compare=value;persist(node);render(node);draw();});
  const close=button('×','Close enlarged preview',()=>dispose());close.className='dxp-modal-close';toolbar.append(previous,heading,next,comparison,close);
  const viewport=document.createElement('div');viewport.className='dxp-modal-view';const stage=document.createElement('div');stage.className='dxp-modal-stage';viewport.append(stage);
  const footer=document.createElement('div');footer.className='dxp-modal-footer';const batchPrevious=button('‹','Previous image in batch',()=>moveBatch(-1)),batchTitle=document.createElement('span'),batchNext=button('›','Next image in batch',()=>moveBatch(1));
  const minus=button('−','Zoom out',()=>setZoom(zoom/1.25)),fit=button('Fit','Fit image to window',()=>setZoom(1)),actual=button('100%','Show one image pixel per screen pixel',()=>setZoom(nativeZoom())),plus=button('+','Zoom in',()=>setZoom(zoom*1.25)),zoomLabel=document.createElement('span');zoomLabel.className='dxp-modal-zoom';footer.append(batchPrevious,batchTitle,batchNext,minus,fit,actual,plus,zoomLabel);
  modal.append(toolbar,viewport,footer);document.body.append(modal);
  const observer=new ResizeObserver(()=>layout());observer.observe(viewport);
  function dispose(){observer.disconnect();modal.remove();}
  function item(){return current(node);}
  function counts(){return{stage:Math.max(1,d.stages?.length||1),batch:Math.max(1,Number(d.batch_count)||d.original?.length||1)};}
  function moveStage(delta){const count=counts().stage;state.stage=(state.stage+delta+count)%count;persist(node);render(node);draw();}
  function moveBatch(delta){const count=counts().batch;state.batch=(state.batch+delta+count)%count;persist(node);render(node);draw();}
  function fitScale(){const box=viewport.getBoundingClientRect(),padding=8;return Math.max(.0001,Math.min((box.width-padding)/natural[0],(box.height-padding)/natural[1]));}
  function nativeZoom(){return 1/fitScale();}
  function setZoom(value){zoom=Math.max(.1,Math.min(16,value));state.modalZoom=zoom;layout();}
  function layout(){const scale=fitScale()*zoom,width=Math.max(1,Math.round(natural[0]*scale)),height=Math.max(1,Math.round(natural[1]*scale)),box=viewport.getBoundingClientRect();stage.style.width=width+'px';stage.style.height=height+'px';stage.style.marginLeft=Math.max(0,Math.floor((box.width-width)/2))+'px';stage.style.marginTop=Math.max(0,Math.floor((box.height-height)/2))+'px';zoomLabel.textContent=Math.round(scale*100)+'%';}
  function draw(){
    const selected=item(),count=counts();if(!selected)return;state.stage=Math.max(0,Math.min(state.stage,count.stage-1));state.batch=Math.max(0,Math.min(state.batch,count.batch-1));
    previous.disabled=next.disabled=count.stage<2;batchPrevious.disabled=batchNext.disabled=count.batch<2;heading.textContent=selected.name;heading.title=`${selected.name}${selected.state?' · '+selected.state:''}`;batchTitle.textContent=`Image ${state.batch+1} / ${count.batch}`;comparison.value=state.compare;
    const currentUrl=viewUrl(selected.images?.[state.batch]||d.original?.[state.batch]),compareItems=state.compare==='original'?d.original:selected.previous,compareUrl=viewUrl(compareItems?.[state.batch]||d.original?.[state.batch]);stage.replaceChildren();stage.style.setProperty('--wipe',wipe+'%');
    const top=document.createElement('img');top.src=currentUrl;top.alt=selected.name;top.addEventListener('load',()=>{natural=[top.naturalWidth||1,top.naturalHeight||1];layout();},{once:true});
    if(state.compare==='off'){stage.append(top);}
    else{
      const base=document.createElement('img');base.src=compareUrl;base.alt=state.compare;const overlay=document.createElement('div');overlay.className='dxp-current';overlay.append(top);const divider=document.createElement('div');divider.className='dxp-divider';const left=document.createElement('span');left.className='dxp-modal-tag left';left.textContent=state.compare==='original'?'Original':'Previous';const right=document.createElement('span');right.className='dxp-modal-tag right';right.textContent=selected.name;const hint=document.createElement('span');hint.className='dxp-modal-help';hint.textContent='Move the mouse over the image to compare';stage.append(base,overlay,divider,left,right,hint);
    }
  }
  stage.addEventListener('pointermove',event=>{if(state.compare==='off')return;const rect=stage.getBoundingClientRect();wipe=Math.max(0,Math.min(100,(event.clientX-rect.left)/Math.max(1,rect.width)*100));stage.style.setProperty('--wipe',wipe+'%');});
  viewport.addEventListener('wheel',event=>{if(!event.ctrlKey)return;event.preventDefault();setZoom(event.deltaY>0?zoom/1.15:zoom*1.15);},{passive:false});
  modal.addEventListener('keydown',event=>{if(event.key==='Escape'){dispose();return;}if(event.target.closest?.('select,button'))return;if(event.key==='ArrowLeft')moveStage(-1);else if(event.key==='ArrowRight')moveStage(1);else if(event.key==='+'||event.key==='=')setZoom(zoom*1.25);else if(event.key==='-')setZoom(zoom/1.25);});
  draw();modal.focus();
}
function render(node){
  const state=node._dxp,root=node._dxpRoot;root.replaceChildren();const d=state.data,item=current(node);
  if(!d||!item){const empty=document.createElement('div');empty.className='dxp-empty';empty.textContent='Run DetailerX to browse processor stages.';root.append(empty);return;}
  const count=d.stages?.length||1;state.stage=Math.max(0,Math.min(state.stage,count-1));const batchCount=Math.max(1,Number(d.batch_count)||d.original?.length||1);state.batch=Math.max(0,Math.min(state.batch,batchCount-1));
  const stageBar=document.createElement('div');stageBar.className='dxp-bar';const prev=button('‹','Previous processor stage',()=>{state.stage=(state.stage-1+count)%count;persist(node);render(node);});const title=document.createElement('div');title.className='dxp-title';title.textContent=item.name;title.title=item.name;const next=button('›','Next processor stage',()=>{state.stage=(state.stage+1)%count;persist(node);render(node);});prev.disabled=next.disabled=count<2;stageBar.append(prev,title,next);
  const controls=document.createElement('div');controls.className='dxp-sub';controls.append(select([['off','Compare: Off'],['original','Compare: Original'],['previous','Compare: Previous processor']],state.compare,'Choose comparison source',v=>{state.compare=v;persist(node);render(node);}));if(state.compare!=='off')controls.append(select([['wipe','Wipe'],['side','Side by side']],state.layout,'Choose comparison layout',v=>{state.layout=v;persist(node);render(node);}));const stageState=document.createElement('span');stageState.className='dxp-state';stageState.textContent=item.state||'';controls.append(stageState);
  const view=document.createElement('div');view.className='dxp-view'+(state.zoom?' zoom':'');const currentUrl=viewUrl(item.images?.[state.batch]||d.original?.[state.batch]);let compareItems=state.compare==='original'?d.original:item.previous;const compareUrl=viewUrl(compareItems?.[state.batch]||d.original?.[state.batch]);
  if(state.compare==='off'){
    const img=document.createElement('img');img.src=currentUrl;img.alt=item.name;img.addEventListener('dblclick',()=>showModal(node));view.append(img);
  }else if(state.layout==='side'){
    const side=document.createElement('div');side.className='dxp-side';for(const [label,url] of [[state.compare==='original'?'Original':'Previous',compareUrl],[item.name,currentUrl]]){const pane=document.createElement('div');pane.className='dxp-pane';const tag=document.createElement('span');tag.textContent=label;const img=document.createElement('img');img.src=url;img.alt=label;img.addEventListener('dblclick',()=>showModal(node));pane.append(tag,img);side.append(pane);}view.append(side);
  }else{
    const wipe=document.createElement('div');wipe.className='dxp-wipe';wipe.style.setProperty('--wipe',state.wipe+'%');const base=document.createElement('img');base.src=compareUrl;base.alt=state.compare;const overlay=document.createElement('div');overlay.className='dxp-current';const top=document.createElement('img');top.src=currentUrl;top.alt=item.name;overlay.append(top);const divider=document.createElement('div');divider.className='dxp-divider';wipe.append(base,overlay,divider);view.append(wipe);
  }
  root.append(stageBar,controls,view);
  if(state.compare!=='off'&&state.layout==='wipe'){const range=document.createElement('input');range.type='range';range.className='dxp-range';range.min=5;range.max=95;range.value=state.wipe;range.title='Move comparison divider';range.addEventListener('input',()=>{state.wipe=Number(range.value);view.querySelector('.dxp-wipe')?.style.setProperty('--wipe',state.wipe+'%');});range.addEventListener('change',()=>persist(node));root.append(range);}
  const footer=document.createElement('div');footer.className='dxp-footer';const batch=document.createElement('div');batch.className='dxp-bar batch';const bp=button('‹','Previous image in batch',()=>{state.batch=(state.batch-1+batchCount)%batchCount;persist(node);render(node);});const bt=document.createElement('div');bt.className='dxp-title';bt.textContent='Image '+(state.batch+1)+' / '+batchCount;const bn=button('›','Next image in batch',()=>{state.batch=(state.batch+1)%batchCount;persist(node);render(node);});bp.disabled=bn.disabled=batchCount<2;batch.append(bp,bt,bn);const actions=document.createElement('div');actions.style.cssText='display:flex;gap:6px';actions.append(button(state.zoom?'Fit':'100%','Toggle fit or pixel-size preview',()=>{state.zoom=!state.zoom;persist(node);render(node);}),button('Enlarge','Open fullscreen preview with stage navigation, mouse split comparison, and zoom controls',()=>showModal(node)));footer.append(batch,actions);root.append(footer);
  node.setDirtyCanvas(true,true);
}

app.registerExtension({
  name:'workflowx.detailer_x_preview',
  async beforeRegisterNodeDef(type,data){
    if(data.name!==NODE)return;
    const created=type.prototype.onNodeCreated;
    type.prototype.onNodeCreated=function(){created?.apply(this,arguments);css();this._dxp=restore(this);const root=document.createElement('div');root.className='dxp';for(const event of ['pointerdown','pointerup','wheel','keydown'])root.addEventListener(event,e=>e.stopPropagation());this._dxpRoot=root;const widget=this.addDOMWidget('detailer_x_preview','DetailerXPreview',root,{serialize:false,hideOnZoom:false,getMinHeight:()=>420,getMaxHeight:()=>1200});widget.computeSize=()=>[500,460];const width=Math.max(520,this.size?.[0]||0),height=Math.max(540,this.size?.[1]||0);this.setSize([width,height]);render(this);};
    const executed=type.prototype.onExecuted;type.prototype.onExecuted=function(message){executed?.apply(this,arguments);this._dxp.data=payload(message);this._dxp.stage=Math.min(this._dxp.stage,Math.max(0,(this._dxp.data?.stages?.length||1)-1));render(this);};
    const configured=type.prototype.onConfigure;type.prototype.onConfigure=function(info){configured?.apply(this,arguments);this._dxp={...restore(this),data:null};render(this);};
  }
});
