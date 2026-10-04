export const DETAILERS = ["face", "breast", "pussy", "hand", "foot"];
export {helpText} from "./detailer_x_help.mjs?v=3";
export const LEGACY_REALISM = ["brightness", "grain", "hsv", "levels", "sharpen"];
export const ADVANCED = ["rgb","gamma","color_balance","temperature","lens","pixel_perturb","neural_grain","lut","camera","compression"];
export const REALISM = [...LEGACY_REALISM,...ADVANCED];
export const ORDER = ["upscaler",...DETAILERS,...REALISM,"dlss5"];
export const MIN_WIDTH = 520;
export const PRESET_FIELDS = ["steps","cfg","guidance_mode","guidance","sampler_name","scheduler","denoise","guide_size","guide_size_for","max_size","cycle"];
export function presetValues(state) { return Object.fromEntries(DETAILERS.map(name=>[name,Object.fromEntries(PRESET_FIELDS.filter(key=>state[name]?.[key]!==undefined).map(key=>[key,structuredClone(state[name][key])]))])); }
export function modified(state) { return DETAILERS.some(name=>PRESET_FIELDS.some(key=>state[name]?.[key]!==state.preset?.values?.[name]?.[key])); }
export function applyPreset(state,preset) { state.preset=structuredClone(preset);for(const name of DETAILERS)Object.assign(state[name],structuredClone(preset.values[name]));return state; }
export function customPreset(state) { return {id:"custom",label:"Custom",family:"custom",revision:1,values:presetValues(state)}; }
export const LABELS = {upscaler:"Upscaler", face:"Face detailer", breast:"Breast detailer", pussy:"Pussy detailer", hand:"Hand detailer", foot:"Foot detailer", realism:"Realism helpers", brightness:"Brightness / Contrast", grain:"Grain", hsv:"HSV", levels:"Levels", sharpen:"Lucy Sharpen", dlss5:"DLSS5"};
Object.assign(LABELS,{rgb:"RGB",gamma:"Gamma",color_balance:"Color Balance",temperature:"Kelvin White Balance",lens:"Lens Optic Axis",pixel_perturb:"Pixel Perturb",neural_grain:"Neural Grain",lut:"LUT",camera:"Camera Simulator",compression:"Multi-Compression"});
export function applyVisibility(state,visible){
  for(const name of ORDER){
    if(!visible[name]||!state.visible[name])if(state[name])state[name].enabled=false;
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
  if (input.version != null && ![1,2,3].includes(input.version)) throw new Error("Unsupported DetailerX configuration version");
  const result = structuredClone(defaults);
  for (const [key, fallback] of Object.entries(defaults)) {
    if (fallback && typeof fallback === "object") result[key] = {...fallback, ...(input[key] || {})};
    else if (input[key] !== undefined) result[key] = input[key];
  }
  result.version=3;
  result.order=[...(input.order||ORDER)];
  if(result.order.length!==ORDER.length||new Set(result.order).size!==ORDER.length||result.order.some(n=>!ORDER.includes(n)))throw new Error("Invalid processor order");
  result.visible={...Object.fromEntries(ORDER.map(n=>[n,!ADVANCED.includes(n)])),...input.visible};
  if((input.version||1)<3&&input.realism?.enabled===false)for(const n of LEGACY_REALISM)if(result[n])result[n].enabled=false;
  for(const n of ORDER)if(!result.visible[n]&&result[n])result[n].enabled=false;
  delete result.realism;
  result.entry={pause:false,skip:false,pause_minutes:5,wait_indefinitely:false,...(input.entry||result.entry||{})};
  if(input.preset)result.preset=structuredClone(input.preset);
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
export function minimumSize(state, slots=9) { return [MIN_WIDTH, slots*20 + bodyHeight(state) + 48]; }
