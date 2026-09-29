// Presentation state belongs to the workflow, never to a character package.
export function readUI(node, key, fallback) {
 return node?.properties?.h3rcUI?.[key] ?? fallback;
}
export function writeUI(node, key, value) {
 if (!node) return;
 node.properties ??= {}; node.properties.h3rcUI ??= {};
 if (node.properties.h3rcUI[key] === value) return;
 node.properties.h3rcUI[key] = value;
 node.graph?.setDirtyCanvas(true, true);
}
export function restoreUI(node, restore) {
 const previous = node.onConfigure;
 node.onConfigure = function () { previous?.apply(this, arguments); restore(); };
 restore();
}
function serializeUI(node, capture) {
 const previous=node.onSerialize;
 node.onSerialize=function(info){
  previous?.apply(this,arguments);capture();
  info.properties??={};info.properties.h3rcUI=JSON.parse(JSON.stringify(node.properties?.h3rcUI||{}));
 };
}
export function rememberDetails(node, element, key, fallback = false, lifecycle = true) {
 let restored;
 const restore = () => { restored = !!readUI(node, key, typeof fallback === 'function' ? fallback() : fallback); element.open = restored; };
 if(lifecycle){restoreUI(node, restore);serializeUI(node,()=>writeUI(node,key,element.open));}else restore();
 // Ignore delayed initial/restoration toggle events, including events after removal.
 element.addEventListener('toggle', () => {
  if (!element.isConnected || element.open === restored) return;
  restored = element.open; writeUI(node, key, restored);
 });
}
export function rememberHeight(node, element, key, fallback, min, max) {
 restoreUI(node, () => { const h = Number(readUI(node,key,fallback)); element.style.height = Math.max(min,Math.min(max,Number.isFinite(h)?h:fallback))+'px'; });
 const capture=()=>{const h=parseFloat(element.style.height);if(Number.isFinite(h))writeUI(node,key,Math.max(min,Math.min(max,h)));};
 serializeUI(node,capture);
 const observer = new ResizeObserver(() => {
  if (!element.isConnected || element.offsetHeight < min) return;
  // Only explicit CSS resizing; hidden groups and zoom must not overwrite the size.
  const h = parseFloat(element.style.height);
  if (Number.isFinite(h)) writeUI(node,key,Math.max(min,Math.min(max,h)));
 });
 observer.observe(element); (node.h3rcLayoutObservers ??= []).push(observer);
}
