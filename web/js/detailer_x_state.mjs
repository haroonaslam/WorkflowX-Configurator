export const OUTPUT_DETAILERS = ["face", "breast", "pussy", "hand", "foot"];
export const DETAILERS = [...OUTPUT_DETAILERS,"hair","anything"];
export {helpText} from "./detailer_x_help.mjs?v=7";
export const LEGACY_REALISM = ["brightness", "grain", "hsv", "levels", "sharpen"];
export const ADVANCED = ["rgb","gamma","color_balance","temperature","lens","pixel_perturb","neural_grain","lut","camera","compression"];
export const REALISM = [...LEGACY_REALISM,...ADVANCED];
export const ORDER = ["upscaler",...DETAILERS,...REALISM,"dlss5"];
export const MIN_WIDTH = 520;
export const DETAILERX_OUTPUTS = [
  {name:"final_image",type:"IMAGE"},
  {name:"processor_images",type:"DETAILERX_PROCESSOR_IMAGES"},
  {name:"detailer_masks",type:"DETAILERX_MASKS"},
];
export function reconcileOutputSlots(outputs=[]){
  const source=Array.isArray(outputs)?outputs:[];
  const keep=new Set(DETAILERX_OUTPUTS.map(item=>item.name));
  const staleLinks=source.filter(item=>!keep.has(item?.name)).flatMap(item=>Array.isArray(item?.links)?item.links:[]);
  const canonical=DETAILERX_OUTPUTS.map(definition=>{
    const existing=source.find(item=>item?.name===definition.name);
    return {...(existing||{}),...definition,links:Array.isArray(existing?.links)?[...existing.links]:[]};
  });
  const keptLinks=canonical.flatMap((item,slot)=>(item.links||[]).map(id=>({id,slot})));
  return {outputs:canonical,staleLinks,keptLinks};
}
export const PRESET_FIELDS = ["steps","cfg","guidance_mode","guidance","sampler_name","scheduler","denoise","guide_size","guide_size_for","max_size","cycle"];
export function detailerNames(state) { return [...DETAILERS,...Object.keys(state?.extra_detailers||{})]; }
export function isDetailer(state,name) { return DETAILERS.includes(name)||name.startsWith("detailer:"); }
export function stage(state,name) { return name.startsWith("detailer:")?state.extra_detailers?.[name]:state[name]; }
export function labelFor(state,name) { return stage(state,name)?.label||LABELS[name]||name.replace(/^detailer:/,"").replaceAll("_"," ").replace(/\b\w/g,c=>c.toUpperCase())+" detailer"; }
export function presetValues(state) { return Object.fromEntries(DETAILERS.map(name=>[name,Object.fromEntries(PRESET_FIELDS.filter(key=>state[name]?.[key]!==undefined).map(key=>[key,structuredClone(state[name][key])]))])); }
export function modified(state) { return DETAILERS.some(name=>PRESET_FIELDS.some(key=>state[name]?.[key]!==state.preset?.values?.[name]?.[key])); }
export function applyPreset(state,preset) { state.preset=structuredClone(preset);for(const name of detailerNames(state)){const target=stage(state,name),values=preset.values[name]||preset.values.anything||preset.values.hand||preset.values.face;if(target&&values)Object.assign(target,structuredClone(values));}return state; }
export function customPreset(state) { return {id:"custom",label:"Custom",family:"custom",revision:1,values:presetValues(state)}; }
export const LABELS = {upscaler:"Upscaler", face:"Face detailer", breast:"Breast detailer", pussy:"Pussy detailer", hand:"Hand detailer", foot:"Foot detailer",hair:"Hair detailer",anything:"Anything detailer", realism:"Realism helpers", brightness:"Brightness / Contrast", grain:"Grain", hsv:"HSV", levels:"Levels", sharpen:"Lucy Sharpen", dlss5:"DLSS5"};
Object.assign(LABELS,{rgb:"RGB",gamma:"Gamma",color_balance:"Color Balance",temperature:"Kelvin White Balance",lens:"Lens Optic Axis",pixel_perturb:"Pixel Perturb",neural_grain:"Neural Grain",lut:"LUT",camera:"Camera Simulator",compression:"Multi-Compression"});
export function applyVisibility(state,visible){
  for(const name of state.order){
    if(!visible[name]||!state.visible[name]){const target=stage(state,name);if(target)target.enabled=false;}
  }
  state.visible={...visible};
}
export function moveVisible(state,name,target){
  const visible=rows(state),from=visible.indexOf(name),to=visible.indexOf(target);
  if(from<0||to<0||from===to)return;
  visible.splice(from,1);visible.splice(to,0,name);
  let i=0;state.order=state.order.map(n=>state.visible[n]?visible[i++]:n);
}
export function restore(value, defaults) {
  const input = typeof value === "string" ? JSON.parse(value || "{}") : value || {};
  if (input.version != null && ![1,2,3,4,5].includes(input.version)) throw new Error("Unsupported DetailerX configuration version");
  const result = structuredClone(defaults);
  for (const [key, fallback] of Object.entries(defaults)) {
    if (fallback && typeof fallback === "object") result[key] = {...fallback, ...(input[key] || {})};
    else if (input[key] !== undefined) result[key] = input[key];
  }
  result.version=5;result.extra_detailers=structuredClone(input.extra_detailers||{});
  result.order=[...(input.order||ORDER)];
  if((input.version||1)<4){result.order=result.order.filter(n=>ORDER.includes(n));const at=Math.max(0,result.order.indexOf("foot")+1);for(const n of ["anything","hair"])if(!result.order.includes(n))result.order.splice(at,0,n);}
  const expected=[...ORDER,...Object.keys(result.extra_detailers)];
  if(result.order.length!==expected.length||new Set(result.order).size!==expected.length||result.order.some(n=>!expected.includes(n)))throw new Error("Invalid processor order");
  result.visible={...Object.fromEntries(ORDER.map(n=>[n,!ADVANCED.includes(n)])),...Object.fromEntries(Object.keys(result.extra_detailers).map(n=>[n,false])),...input.visible};
  if((input.version||1)<3&&input.realism?.enabled===false)for(const n of LEGACY_REALISM)if(result[n])result[n].enabled=false;
  for(const n of expected){const target=stage(result,n);if(!result.visible[n]&&target)target.enabled=false;}
  for(const n of detailerNames(result)){
    const target=stage(result,n);if(!target)continue;
    const fallback=defaults[n]?.sam_override||defaults.anything?.sam_override||{};
    target.sam_strategy=target.sam_strategy||"inherit";
    target.sam3_constraint=target.sam3_constraint||"bounding_box";
    target.sam_override={...structuredClone(fallback),...(target.sam_override||{})};
  }
  delete result.realism;
  result.entry={pause:false,skip:false,pause_minutes:5,wait_indefinitely:false,...(input.entry||result.entry||{})};
  if(input.preset){
    result.preset=structuredClone(input.preset);
    result.preset.values??={};
    // v1-v3 preset snapshots contain only the original five detailers. Seed
    // new v4 detailers from the closest existing sampling profile without
    // copying execution toggles, detectors, prompts, masks, or seeds.
    for(const name of DETAILERS)if(!result.preset.values[name])result.preset.values[name]=structuredClone(result.preset.values.hand||result.preset.values.face||{});
    if((input.version||1)<4)for(const name of ["hair","anything"])if(result[name]&&!input[name])Object.assign(result[name],structuredClone(result.preset.values[name]||{}));
  }
  else if(!result.preset || JSON.stringify(presetValues(result))!==JSON.stringify(result.preset.values))result.preset={...customPreset(result),id:"legacy",label:"Legacy — Modified settings"};
  if(result.preset?.id==="qwen21" && result.preset.label==="Qwen 2.1 — Current workflow")result.preset.label="Qwen 2.1";
  return result;
}
export function serialize(state) { return JSON.stringify(state); }
export function rows(state) {
  return (state.order||ORDER).filter(n=>state.visible?.[n]??!ADVANCED.includes(n));
}
// ComfyUI reserves widget padding inside the requested height.
export function bodyHeight(state) { return 36 * (rows(state).length + 1) + 132; }
export function minimumSize(state, slots=6) { return [MIN_WIDTH, slots*20 + bodyHeight(state) + 48]; }
