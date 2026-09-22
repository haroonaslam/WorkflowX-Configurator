import { rememberDetails, readUI, writeUI } from './ui_state.js';
import { api } from '../../../scripts/api.js';
import { HELP } from './help_text.js';
import { readSourceSelection } from './source_state.js';

// Directory-only editor. Original files are never modified.
export function openSourceEditor(sources, saved, settings, onSave, node) {
 const make=(tag,parent,text='')=>{const e=document.createElement(tag);e.textContent=text;parent?.append(e);return e;};
 const available=new Map(sources.map(s=>[s.source,s]));
 const selection=readSourceSelection(saved);
 const entries=selection.entries.filter(e=>available.has(e.source)).map(e=>({...e,...available.get(e.source)}));
 for(const s of sources)if(!entries.some(e=>e.source===s.source))entries.push({...s,start:0,duration:0,enabled:true});
 const options={...settings};
 const overlay=make('div',document.body);overlay.className='h3rc-source-editor';
 const style=make('style',overlay);style.textContent=`
 .h3rc-source-editor{position:fixed;inset:0;z-index:10000;background:#080c12c9;display:grid;place-items:center;color:#e7edf4;font:13px system-ui}
 .h3rc-source-editor *{box-sizing:border-box}
 .h3rc-source-editor section{width:min(1060px,95vw);height:min(780px,92vh);max-width:95vw;max-height:92vh;min-width:min(360px,95vw);min-height:300px;resize:both;overflow:hidden;display:flex;flex-direction:column;background:#17232d;border:1px solid #40505e;border-radius:12px;box-shadow:0 18px 70px #0008}
 .h3rc-source-editor header,.h3rc-source-editor footer{padding:16px 20px;flex-shrink:0}
 .h3rc-source-editor h2{font-size:19px;margin:0 0 5px}
 .h3rc-source-editor p,.h3rc-source-editor small{color:#abbcca;line-height:1.5}
 .h3rc-source-editor .body{overflow:auto;min-height:0;flex:1;padding:0 20px}.h3rc-source-editor .sources{min-height:100px}
 .h3rc-source-editor .source{border:1px solid #344553;border-radius:8px;margin:8px 0;padding:12px;background:#1d2c38}
 .h3rc-source-editor .source[data-excluded=true]{opacity:.55}
 .h3rc-source-editor .source[data-drop=true]{border-top:3px solid #79c8f2}
 .h3rc-source-editor .line{display:grid;grid-template-columns:28px 180px minmax(180px,1fr) auto;align-items:center;gap:14px}
 .h3rc-source-editor .name{overflow-wrap:anywhere;min-width:0}
 .h3rc-source-editor .media{width:180px;height:110px;object-fit:contain;border-radius:5px;background:#101820;cursor:pointer}
 .h3rc-source-editor audio{width:100%;height:38px}
 .h3rc-source-editor .audio-preview{width:180px;display:grid;gap:10px}
 .h3rc-source-editor small{display:block;margin-top:4px}
 .h3rc-source-editor button,.h3rc-source-editor select,.h3rc-source-editor input[type=number]{background:#233744;border:1px solid #516675;border-radius:5px;padding:7px 10px;color:inherit;font:inherit}
 .h3rc-source-editor button{cursor:pointer;white-space:nowrap}
 .h3rc-source-editor button:focus-visible{outline:2px solid #79c8f2}
 .h3rc-source-editor .handle{cursor:grab;padding:4px;border:0;background:transparent;font-size:23px}
 .h3rc-source-editor .controls{display:flex;flex-wrap:wrap;gap:12px;align-items:end;margin:12px 0}
 .h3rc-source-editor .controls label{display:grid;gap:6px}
 .h3rc-source-editor input[type=number]{width:120px}
 .h3rc-source-editor footer{display:flex;align-items:center;gap:10px;border-top:1px solid #344553;margin-top:10px}
 .h3rc-source-editor footer span{flex:1;color:#b5c4ce}
 .h3rc-source-editor .primary{background:#315c70}
 .h3rc-source-editor details{border-top:1px solid #344553;padding-top:10px;margin-top:12px}
 .h3rc-source-editor summary{cursor:pointer;font-weight:600}
 .h3rc-source-editor .strip{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}
 .h3rc-source-editor .strip img{width:100px;height:68px;object-fit:contain;background:#101820}
 .h3rc-source-editor .preview-resize{height:300px;min-height:100px;max-height:65vh;resize:vertical;overflow:hidden;margin-top:12px}.h3rc-source-editor .large-preview{width:100%;height:100%;object-fit:contain;background:#101820}
 .h3rc-source-editor .actions{display:flex;flex-direction:column;gap:10px}
 @media(max-width:650px){.h3rc-source-editor .line{grid-template-columns:24px 110px 1fr}.h3rc-source-editor .media,.h3rc-source-editor .audio-preview{width:110px}.h3rc-source-editor .actions{grid-column:2/-1;flex-direction:row}}
 `;
 const panel=make('section',overlay);panel.setAttribute('role','dialog');panel.setAttribute('aria-modal','true');panel.setAttribute('aria-label','Edit source media');
 const savedSize=readUI(node,'source-editor:size',[1060,780]);panel.style.width=Math.min(savedSize[0],innerWidth*.95)+'px';panel.style.height=Math.min(savedSize[1],innerHeight*.92)+'px';
 const header=make('header',panel);make('h2',header,'Edit source media');
 if(selection.warning){const notice=make('p',header,selection.warning);notice.setAttribute('role','status');notice.style.color='#ffd49b';}
 const help=make('small',header,'Drag to reorder · Click a picture to enlarge · Preview and trim recordings');
 const body=make('div',panel);body.className='body';
 const controls=make('details',body);rememberDetails(node,controls,'source-controls',false,false);make('summary',controls,'Video frames and total recording time');
 const config=make('div',controls);config.className='controls';
 const action=(parent,title,fn)=>{const b=make('button',parent,title);b.type='button';b.onclick=fn;return b;};
 function select(parent,label,value,choices,change,title=''){
  const l=make('label',parent,label),input=make('select',l);l.title=title;
  for(const [v,t] of choices){const o=make('option',input,t);o.value=v;}input.value=value;input.onchange=()=>change(input.value);return input;
 }
 function number(parent,label,value,change,title='',min=0){
  const l=make('label',parent,label),input=make('input',l);input.type='number';input.min=min;input.step='any';input.value=value;l.title=title;
  input.onchange=()=>{if(input.reportValidity())change(Number(input.value));};return input;
 }
 function configDraw(){config.replaceChildren();
  number(config,'Maximum source frames per video (0 = all)',options.sample_frames??16,v=>{options.sample_frames=Math.floor(v);draw();},'16 evenly spaced source frames is a compact starting point. 0 keeps every frame in each selected range; this is not FPS.',0).step='1';
  for(const kind of ['video','voice']){
   const key=kind+'_duration_limit',amount='maximum_total_'+kind+'_duration';
   select(config,kind==='video'?'Total video duration':'Total voice duration',options[key]||'Unlimited',[['Unlimited','No duration limit'],['Limited','Limit total seconds']],v=>{options[key]=v;configDraw();draw();},HELP[key]);
   if(options[key]==='Limited')number(config,'Maximum total '+kind+' seconds',options[amount]??(kind==='video'?15:10),v=>{options[amount]=v;draw();},HELP[amount]);
  }
 }
 const rows=make('div',body);rows.className='sources';
 const footer=make('footer',panel),count=make('span',footer);let dragging=null,expanded=null;
 const url=(entry,extra='')=>api.apiURL('/h3refcharacters/source-preview?handle='+encodeURIComponent(entry.handle)+extra);
 const close=()=>{for(const frame of panel.querySelectorAll('.preview-resize'))writeUI(node,'source-preview:'+frame.dataset.source,parseFloat(frame.style.height)||300);writeUI(node,'source-editor:size',[panel.offsetWidth,panel.offsetHeight]);document.removeEventListener('keydown',escape);overlay.remove();};
 const escape=e=>{if(e.key==='Escape'){e.stopPropagation();close();}};document.addEventListener('keydown',escape);
 function move(from,to){const item=entries.splice(from,1)[0];entries.splice(to,0,item);draw();}
 function allocations(){
  const left={audio:options.voice_duration_limit==='Limited'?options.maximum_total_voice_duration:Infinity,video:options.video_duration_limit==='Limited'?options.maximum_total_video_duration:Infinity};
  return entries.map(e=>{if(e.kind==='image'||e.enabled===false)return null;const available=Math.max(0,(e.media_duration||0)-(e.start||0));const requested=Math.min(available,e.duration>0?e.duration:available);const duration=Math.max(0,Math.min(requested,left[e.kind]));left[e.kind]-=duration;return {duration,requested};});
 }
 function indices(e,duration){
  let ids=[];const first=Math.max(0,Math.ceil((e.start||0)*e.fps-1e-7)),stop=Math.min(e.frame_count,Math.ceil(((e.start||0)+duration)*e.fps-1e-7));
  for(let i=first;i<stop;i++)ids.push(i);
  const mode='Uniform frame sample';
  const n=options.sample_frames??16;
  // Match torch's round-to-even for sampling ties.
  const round=x=>Math.abs(x-Math.floor(x)-.5)<1e-9?(Math.floor(x)%2===0?Math.floor(x):Math.ceil(x)):Math.round(x);
  if(n>0&&ids.length>n)ids=Array.from({length:n},(_,i)=>ids[n===1?0:round(i*(ids.length-1)/(n-1))]);
  return ids;
 }
 function draw(){
  const ranges=allocations();rows.replaceChildren();count.textContent=`${entries.filter(e=>e.enabled!==false).length} of ${entries.length} sources included`;
  if(!entries.length)make('p',rows,'No supported media found in this directory.');
  entries.forEach((entry,i)=>{
   const row=make('div',rows);row.className='source';row.dataset.excluded=entry.enabled===false;
   const line=make('div',row);line.className='line';
   const handle=action(line,'⠿',()=>{});handle.className='handle';handle.draggable=true;handle.title='Drag to reorder, or press Alt + Up / Down.';handle.setAttribute('aria-label',`Reorder ${entry.source}`);
   handle.ondragstart=e=>{dragging=i;e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',entry.source);};handle.ondragend=()=>{dragging=null;draw();};
   handle.onkeydown=e=>{if(e.altKey&&['ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();const to=Math.max(0,Math.min(entries.length-1,i+(e.key==='ArrowUp'?-1:1)));move(i,to);rows.children[to].querySelector('button').focus();}};
   row.ondragover=e=>{if(dragging!==null){e.preventDefault();row.dataset.drop=true;}};row.ondragleave=()=>delete row.dataset.drop;
   row.ondrop=e=>{e.preventDefault();if(dragging!==null){const from=dragging;dragging=null;move(from,i);}};
   let player;
   if(entry.kind==='audio'){
    const wrap=make('div',line);wrap.className='audio-preview';make('span',wrap,'♫ Voice recording');player=make('audio',wrap);player.controls=true;player.preload='metadata';player.src=url(entry,'&playable=1');
   }else{
    const picture=make('img',line);picture.className='media';picture.loading='lazy';picture.alt=entry.source;picture.src=url(entry,'&thumbnail=1');picture.title=entry.kind==='image'?'Click to enlarge':'Click to play and trim';picture.onclick=()=>{expanded=expanded===entry.source?null:entry.source;draw();};
   }
   const name=make('div',line);name.className='name';make('strong',name,`${i+1} · ${entry.kind==='image'?'Picture':entry.kind==='video'?'Video':'Audio'}`);make('small',name,entry.source);
   if(entry.dimensions)make('small',name,'Source: '+entry.dimensions.join(' × '));
   if(entry.preview_error)make('small',name,entry.preview_error);
   const range=ranges[i];
   if(range){const text=`${Number(entry.start||0).toFixed(2)}–${((entry.start||0)+range.duration).toFixed(2)} s · ${range.duration.toFixed(2)} s selected`;
    make('small',name,range.duration===0?'Excluded by total duration limit':text+(range.duration<range.requested?' · Shortened by total duration limit':''));
    if(entry.kind==='video'&&entry.fps)make('small',name,`${indices(entry,range.duration).length} frames to encode · recording ${entry.fps.toFixed(2)} FPS`);
   }
   const actions=make('div',line);actions.className='actions';
   action(actions,expanded===entry.source?'Close preview':entry.kind==='image'?'View picture':entry.kind==='video'?'Play / trim video':'Trim audio',()=>{expanded=expanded===entry.source?null:entry.source;draw();});
   const include=make('label',actions),check=make('input',include);check.type='checkbox';check.checked=entry.enabled!==false;include.append(' Include');check.onchange=()=>{entry.enabled=check.checked;draw();};check.title='Exclude from this creation without deleting the original file.';
   if(expanded===entry.source){
    const previewBox=make('div',row);previewBox.className='preview-resize';previewBox.dataset.source=entry.source;previewBox.style.height=readUI(node,'source-preview:'+entry.source,300)+'px';previewBox.onpointerup=()=>writeUI(node,'source-preview:'+entry.source,parseFloat(previewBox.style.height)||300);
    if(entry.kind==='image'){const image=make('img',previewBox);image.className='large-preview';image.src=url(entry);image.alt=entry.source;return;}
    if(entry.kind==='video'){player=make('video',previewBox);player.className='large-preview';player.controls=true;player.preload='metadata';player.src=url(entry,'&playable=1');}
    if(entry.kind==='audio')previewBox.remove();
    const edit=make('div',row);edit.className='controls';
    const end=()=>entry.duration>0?(entry.start||0)+entry.duration:entry.media_duration;
    number(edit,'Start time (seconds)',entry.start||0,v=>{if(v>=end()){alert('Start must be before the end time.');return;}const oldEnd=end();entry.start=v;entry.duration=oldEnd-v;draw();},'Choose where the selected recording begins. The original file is unchanged.');
    number(edit,'End time (seconds)',end()||0,v=>{if(v<=(entry.start||0)||v>entry.media_duration){alert('End must be after Start and within the recording.');return;}entry.duration=v-(entry.start||0);draw();},'Choose where the selected recording ends.');
    action(edit,'Use whole recording',()=>{entry.start=0;entry.duration=0;draw();}).title='Reset this recording to its original full duration. A total duration limit can still shorten it.';
    if(player){player.onloadedmetadata=()=>{player.currentTime=entry.start||0;};player.ontimeupdate=()=>{if(range&&player.currentTime>=(entry.start||0)+range.duration&&!player.paused)player.pause();};}
    if(entry.kind==='video'){
     const ids=range&&entry.fps?indices(entry,range.duration):[];
     const details=make('details',row);rememberDetails(node,details,'source-frames:'+entry.source,false,false);make('summary',details,`Selected frames (${ids.length})`);
     details.ontoggle=()=>{if(!details.open||details.dataset.loaded)return;details.dataset.loaded='1';const strip=make('div',details);strip.className='strip';for(const f of ids.slice(0,24)){const img=make('img',strip);img.loading='lazy';img.alt=`Frame ${f+1}`;img.title=`Frame ${f+1} · ${(f/entry.fps).toFixed(2)} seconds`;img.src=url(entry,'&thumbnail=1&frame='+f);}if(ids.length>24)make('small',details,'Showing the first 24 selected frames. All '+ids.length+' will be used before optional budget fitting.');};
    }
   }
  });
 }
 action(footer,'Cancel',close);action(footer,'Save selection',()=>{if([...panel.querySelectorAll('input[type=number]')].some(e=>!e.reportValidity()))return;onSave(entries.map(({source,start=0,duration=0,enabled=true})=>({source,start,duration,enabled})),options);close();}).className='primary';
 configDraw();draw();
}
