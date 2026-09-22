import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";
import { editorQueue, insertSourceLine } from "./segment_editor.mjs";

const owners = new Map();
const freshToken = () => crypto.randomUUID().replaceAll("-", "");
export function attachReview(node, {button, help, watch}) {
  const toggle = node.widgets.find(w => w.name === "review_each_line");
  if (!toggle) return;
  let token, state = {segments:[]}, selected = null, busy = false, disposed = false, checking = false;
  let pending = false, queuedId = null, insertion = null, submissionError = null;
  function identify() {
    node.properties ??= {};
    let next = node.properties.workflowx_auk_review_id;
    if (!next || (owners.has(next) && owners.get(next) !== node)) next = freshToken();
    if (token && token !== next) owners.delete(token);
    token = node.properties.workflowx_auk_review_id = next; owners.set(token,node);
  }
  identify();
  const root = document.createElement('div'); root.className = 'workflowx-auk-chain-controls workflowx-auk-chain-review';
  const heading = document.createElement('strong');
  const text = document.createElement('div'); text.className = 'workflowx-auk-review-text';
  const details = document.createElement('div'); details.tabIndex=0; help(details,'Settings used for this retained take.');
  const message = document.createElement('div'); message.setAttribute('aria-live','polite');
  const player = document.createElement('audio'); player.controls = true; player.preload = 'none';
  help(player,'Listen to this retained segment. Browsing does not regenerate audio.');
  function touch() {api.fetchApi(`/workflowx/auk/chain-review/${token}/touch`,{method:'POST'}).catch(()=>{});}
  player.addEventListener('play',touch);
  const actions = document.createElement('div'); actions.className = 'workflowx-auk-chain-actions';
  const list = () => state.segments ?? [];
  const current = () => list().find(s => s.id === selected);
  function navigate(offset) {
    const index = Math.max(0,list().findIndex(s => s.id === selected));
    selected = list()[Math.max(0,Math.min(list().length-1,index+offset))]?.id; touch(); render();
  }
  const previous = button('Previous','Listen to the preceding segment.',()=>navigate(-1));
  const next = button('Next','Listen to the following segment.',()=>navigate(1));
  const retry = button('Regenerate','Make a fresh take of this line using its current words and settings. Other takes stay unchanged.',()=>submit('regenerate'));
  const add = button('Add line…','Insert and generate a new line immediately after this segment.',()=>addLine());
  const finalize = button('Finalize','Assemble the retained takes with the current gap and send the revised recording onward. No speech is regenerated.',()=>submit('finalize'));
  const clear = button('Clear editor','Remove this editor’s temporary takes. Saved output recordings are not deleted.',async()=>{
    await api.fetchApi(`/workflowx/auk/chain-review/${token}/cancel`,{method:'POST'});
    node.properties.workflowx_auk_review_id=freshToken(); identify();
    state={segments:[]}; selected=null; submissionError=null;pending=busy=false; render();
  });
  actions.append(previous,next,retry,add,finalize,clear);
  root.append(heading,text,details,player,message,actions);
  root.addEventListener('pointerdown',e=>e.stopPropagation());
  root.addEventListener('keydown',e=>{if(e.key!=='Escape')e.stopPropagation();});
  const widget = node.addDOMWidget('auk_line_review','auk_line_review',root,{
    getMinHeight:()=>toggle.value?240:0,getMaxHeight:()=>toggle.value?240:0,serialize:false,hideOnZoom:false,
  });
  widget.serializeValue=()=>undefined;
  const connected=()=>node.inputs?.some(input=>input.name==='script' && input.link!=null);
  function render() {
    root.hidden=!toggle.value;
    if (!current()) selected=list()[0]?.id ?? null;
    const segment=current(), index=list().findIndex(s=>s.id===selected);
    heading.textContent=segment?`Segment editor · ${index+1} of ${list().length}${segment.voice?` · Voice ${segment.voice}`:''}`:'Segment editor';
    text.textContent=segment?.raw ?? segment?.draft ?? '';
    details.textContent=segment?.audio?`${segment.duration.toFixed(2)}s · Seed ${segment.seed}${segment.editor_only?' · Editor-only':''}`:segment?'Not generated yet':'';
    const labels={steps:'Steps',guidance:'Guidance',words_per_second:'Words per second',sound_extra_seconds:'Extra sound time',speed_timing_multiplier:'Speed timing multiplier'};
    details.dataset.help=segment?.settings?Object.entries(labels).filter(([key])=>key in segment.settings).map(([key,label])=>`${label}: ${segment.settings[key]}`).join('. ')+'. These settings describe the retained take.':'This line still needs to be generated.';
    details.setAttribute('aria-description',details.dataset.help);
    message.textContent=submissionError ?? state.message ?? 'Run the workflow to generate all segments.';
    if (segment?.audio && player.getAttribute('data-source')!==segment.audio) {
      player.src=api.apiURL(segment.audio); player.setAttribute('data-source',segment.audio);
    }
    player.hidden=!segment?.audio;
    if (!segment?.audio) {player.removeAttribute('src');player.removeAttribute('data-source');}
    previous.disabled=index<=0; next.disabled=index<0 || index>=list().length-1;
    retry.disabled=add.disabled=busy || !segment;
    finalize.disabled=busy || !list().length || list().some(s=>!s.audio);
    clear.disabled=busy || !list().length;
    node.graph?.setDirtyCanvas(true,true);
  }
  function receive(nextState) {
    if (insertion && (nextState.status === 'error' || submissionError)) {
      if (nextState.source_count === insertion.count && insertion.script.value === insertion.after) writeScript(insertion.script, insertion.before);
      insertion = null;
    } else if (insertion && nextState.source_count > insertion.count) insertion = null;
    const changed=nextState.batch!==state.batch || nextState.revision!==state.revision;
    if (nextState.batch!==state.batch) {selected=null;submissionError=null;}
    if (pending && changed && nextState.selected) selected=nextState.selected;
    if (nextState.status==='generating') {busy=true;pending=false;}
    else if (changed || !pending || nextState.status==='error') {busy=false;pending=false;}
    state=nextState; render();
  }
  async function submit(action, extra={}) {
    if (busy) return false;
    identify(); submissionError=null; busy=pending=true; render();
    try {
      const graph=await app.graphToPrompt();
      const id=String(node.id);
      const request={token,action,batch:state.batch,revision:state.revision,segment:selected,nonce:freshToken(),...extra};
      const gap=node.widgets.find(w=>w.name==='gap_seconds')?.value ?? 0;
      const queued=editorQueue(graph.output,id,action,gap);
      const body={prompt:queued.prompt,client_id:api.clientId,partial_execution_targets:queued.targets,extra_data:{extra_pnginfo:{workflow:graph.workflow,workflowx_auk_review:{[id]:request}}}};
      const response=await api.fetchApi('/prompt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      const result=await response.json();
      if(!response.ok) throw Error(result.error?.message ?? JSON.stringify(result.node_errors ?? result));
      queuedId=result.prompt_id;
      state={...state,message:action==='finalize'?'Queued assembly…':'Queued segment generation…'}; render(); return true;
    } catch(error) {busy=pending=false;submissionError=error.message;render();return false;}
  }
  let popup=null;
  function closePopup() {popup?.remove();popup=null;}
  function addLine() {
    closePopup();
    const segment=current(); if(!segment)return;
    popup=document.createElement('section');popup.className='workflowx-auk-chain-popover';popup.setAttribute('role','dialog');popup.setAttribute('aria-label','Add line');
    const title=document.createElement('strong');title.textContent=`Add after segment ${list().findIndex(s=>s.id===selected)+1}`;
    const input=document.createElement('textarea');input.rows=3;input.setAttribute('aria-label','New script line');
    help(input,'Enter one line with optional speaker, tags, and duration. It will be generated after the selected segment.');
    const note=document.createElement('p');note.textContent=connected()?'This line stays in the editor only; the connected text node is not changed.':'The new line will also be inserted into the script.';
    const error=document.createElement('div');error.setAttribute('role','alert');
    const save=button('Add & generate','Insert this line and generate only its audio.',async()=>{
      const raw=input.value.trim();
      if(!raw || /[\r\n]/.test(raw)) {error.textContent='Enter exactly one nonblank line.';return;}
      save.disabled=true;
      try {
      const response=await api.fetchApi('/workflowx/auk/chain-review/validate-line',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:raw,inline_edits:!!node.widgets.find(w=>w.name==='inline_edits')?.value})});
      const result=await response.json();
      if(!response.ok) {error.textContent=result.error ?? 'Check the line.';save.disabled=false;return;}
      let before=null,after=null;
      const script=node.widgets.find(w=>w.name==='script');
      if(!connected()) {
        before=String(script.value??'');
        after=insertSourceLine(before,segment.source,raw,state.source_count);
        insertion={script,before,after,count:state.source_count};
        writeScript(script,after);
      }
      closePopup();
      const queued=await submit('add',{text:raw,connected:connected(),segment:segment.id});
      if(!queued && before!==null && script.value===after) {writeScript(script,before);insertion=null;}
      } catch(failure) {error.textContent=failure.message;save.disabled=false;}
    });
    popup.append(title,input,note,error,save,button('Cancel','Close without adding a line.',closePopup));
    popup.addEventListener('keydown',e=>{
      e.stopPropagation();
      if(e.key==='Escape'){e.preventDefault();closePopup();add.focus();}
      if(e.key==='Tab') {
        const controls=[...popup.querySelectorAll('textarea,button:not(:disabled)')];
        if(e.shiftKey && document.activeElement===controls[0]) {e.preventDefault();controls.at(-1).focus();}
        else if(!e.shiftKey && document.activeElement===controls.at(-1)) {e.preventDefault();controls[0].focus();}
      }
    });
    popup.addEventListener('pointerdown',e=>e.stopPropagation());
    document.body.append(popup);
    const rect=add.getBoundingClientRect();popup.style.left=`${Math.max(8,Math.min(rect.left,innerWidth-popup.offsetWidth-8))}px`;popup.style.top=`${Math.max(8,Math.min(rect.bottom+6,innerHeight-popup.offsetHeight-8))}px`;
    input.style.width='100%'; input.style.boxSizing='border-box';
    input.focus();
  }
  function writeScript(script,value) {
    const box=script.element??script.inputEl;
    const textarea=box instanceof HTMLTextAreaElement?box:box?.querySelector?.('textarea');
    node.graph?.beforeChange();
    if(textarea) {
      textarea.focus();textarea.setSelectionRange(0,textarea.value.length);
      if(!document.execCommand('insertText',false,value)) textarea.setRangeText(value,0,textarea.value.length,'end');
      textarea.dispatchEvent(new Event('input',{bubbles:true}));
    }
    script.value=value;script.callback?.(value);node.graph?.afterChange();
  }
  const executed=node.onExecuted;
  node.onExecuted=function(output) {executed?.apply(this,arguments);if(output?.workflowx_auk_review?.[0]){busy=pending=false;receive(output.workflowx_auk_review[0]);}};
  async function poll() {
    if(disposed||checking||!toggle.value)return;
    checking=true;
    try {const response=await api.fetchApi(`/workflowx/auk/chain-review/${token}`);if(response.ok)receive(await response.json());}
    catch { /* Keep retained information visible during reconnect. */ }
    finally {checking=false;}
  }
  const interval=setInterval(poll,1500);
  const configured=node.onConfigure;
  node.onConfigure=function(){const result=configured?.apply(this,arguments);identify();render();poll();return result;};
  const removed=node.onRemoved;
  node.onRemoved=function(){disposed=true;closePopup();clearInterval(interval);owners.delete(token);return removed?.apply(this,arguments);};
  const callback=toggle.callback;
  toggle.callback=function(){const result=callback?.apply(this,arguments);if(!toggle.value){closePopup();api.fetchApi(`/workflowx/auk/chain-review/${token}/cancel`,{method:'POST'}).catch(()=>{});node.properties.workflowx_auk_review_id=freshToken();identify();state={segments:[]};busy=pending=false;}render();return result;};
  for(const event of ['execution_error','execution_interrupted'])watch(api,event,e=>{if(!queuedId||e.detail?.prompt_id===queuedId){busy=pending=false;submissionError=e.detail?.exception_message??'Generation did not finish.';poll();render();}});
  render();poll();
}
