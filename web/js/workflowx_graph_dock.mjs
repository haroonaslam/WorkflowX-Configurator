const activeDocks = new Set();
let animationFrame = 0;

function stopEvent(event) {
  event.stopPropagation();
}

function save(dock) {
  const node = dock.node;
  node.properties ||= {};
  node.properties[dock.propertyKey] = {
    x: dock.graph.x, y: dock.graph.y, w: dock.graph.w, h: dock.graph.h,
    locked: dock.locked, minimized: dock.minimized,
  };
  node.graph?.change?.();
}

function canvasToGraphDelta(app, dx, dy) {
  const scale = app.canvas?.ds?.scale || 1;
  return [dx / scale, dy / scale];
}

function resolveCanvasLayer(dock) {
  const root = dock.ownerElement;
  const widgetHost = root?.closest?.(".dom-widget");
  const layerHost = widgetHost?.parentElement;
  if (!widgetHost || !layerHost?.classList?.contains("isolate")) return null;
  return { widgetHost, layerHost };
}

function syncCanvasLayer(dock) {
  const layer = resolveCanvasLayer(dock);
  if (!layer) return null;
  if (dock.element.parentElement !== layer.layerHost) layer.layerHost.appendChild(dock.element);
  const ownerZ = window.getComputedStyle(layer.widgetHost).zIndex;
  dock.element.style.zIndex = ownerZ && ownerZ !== "auto" ? ownerZ : String(Number(layer.widgetHost.style.zIndex) || 1);
  return layer;
}

export function graphDockScreenRect(app, node, graph) {
  const canvas = app?.canvas;
  const rect = canvas?.canvas?.getBoundingClientRect?.();
  if (!rect || !node?.pos || !graph) return null;
  const scale = canvas.ds?.scale || 1;
  const offset = canvas.ds?.offset || [0, 0];
  return {
    left: rect.left + (node.pos[0] + graph.x + offset[0]) * scale,
    top: rect.top + (node.pos[1] + graph.y + offset[1]) * scale,
    scale,
  };
}

function applyTransform(dock) {
  if (!dock.element.isConnected) return;
  const { app, node, graph, element } = dock;
  if (dock.fullscreen) {
    if (element.parentElement !== document.body) document.body.appendChild(element);
    return;
  }
  const canvasLayer = syncCanvasLayer(dock);
  let nodeElement = null;
  if (!canvasLayer && window.LiteGraph?.vueNodesMode && node.id != null) {
    nodeElement = dock.vueNodeElement;
    if (!nodeElement?.isConnected) nodeElement = dock.vueNodeElement = document.querySelector(`[data-node-id="${node.id}"]`);
  }
  if (nodeElement) {
    if (element.parentElement !== nodeElement) nodeElement.appendChild(element);
    const titleHeight = window.LiteGraph?.NODE_TITLE_HEIGHT ?? 30;
    const signature = `vue|${graph.x}|${graph.y}|${graph.w}|${graph.h}|${dock.minimized}`;
    if (element.__workflowxDockSignature === signature) return;
    element.__workflowxDockSignature = signature;
    Object.assign(element.style, {
      position: "absolute", left: `${graph.x}px`, top: `${titleHeight + graph.y}px`, width: `${graph.w}px`,
      height: `${dock.minimized ? 38 : graph.h}px`, transform: "", transformOrigin: "",
    });
    return;
  }
  if (!canvasLayer && element.parentElement !== document.body) document.body.appendChild(element);
  const screen = graphDockScreenRect(app, node, graph);
  if (!screen) return;
  const { left, top, scale } = screen;
  const signature = `${left}|${top}|${scale}|${graph.w}|${graph.h}|${dock.minimized}`;
  if (element.__workflowxDockSignature === signature) return;
  element.__workflowxDockSignature = signature;
  Object.assign(element.style, {
    position: "fixed", left: "0", top: "0", width: `${graph.w}px`,
    height: `${dock.minimized ? 38 : graph.h}px`, transformOrigin: "top left",
    transform: `translate(${left}px, ${top}px) scale(${scale})`,
  });
}

function tick() {
  animationFrame = 0;
  for (const dock of activeDocks) applyTransform(dock);
  if (activeDocks.size) animationFrame = requestAnimationFrame(tick);
}

function startTicking() {
  if (!animationFrame) animationFrame = requestAnimationFrame(tick);
}

function makeButton(label, title) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.title = title;
  return button;
}

function installDockCSS() {
  if (document.getElementById("workflowx-graph-dock-css")) return;
  const style = document.createElement("style");
  style.id = "workflowx-graph-dock-css";
  style.textContent = `
    .workflowx-graph-dock{z-index:1100;display:flex;flex-direction:column;min-width:320px;min-height:38px;
      color:#dfe4ec;background:#202226;border:1px solid #555c66;border-radius:7px;box-shadow:0 12px 34px #0009;
      overflow:hidden;font:12px ui-sans-serif,system-ui,sans-serif;box-sizing:border-box}
    .workflowx-graph-dock *{box-sizing:border-box}.workflowx-graph-dock-head{height:38px;flex:none;display:flex;
      align-items:center;gap:7px;padding:0 7px 0 11px;background:#303238;border-bottom:1px solid #454951;cursor:move;user-select:none}
    .workflowx-graph-dock.locked .workflowx-graph-dock-head{cursor:default}.workflowx-graph-dock-title{font-weight:700;flex:1}
    .workflowx-graph-dock-head button{width:27px;height:25px;padding:0;border:1px solid #50555e;border-radius:4px;
      background:#24262a;color:#d5d9e0;cursor:pointer}.workflowx-graph-dock-head button:hover{border-color:#7aa2f7;color:#fff}
    .workflowx-graph-dock-body{min-height:0;flex:1;overflow:hidden}.workflowx-graph-dock.minimized .workflowx-graph-dock-body,
      .workflowx-graph-dock.minimized .workflowx-graph-dock-resize{display:none}
    .workflowx-graph-dock.fullscreen{position:fixed!important;inset:12px!important;width:auto!important;height:auto!important;
      transform:none!important;z-index:20000}.workflowx-graph-dock-resize{position:absolute;z-index:3}
    .workflowx-graph-dock-resize[data-edge=e],.workflowx-graph-dock-resize[data-edge=w]{top:38px;bottom:7px;width:8px;cursor:ew-resize}
    .workflowx-graph-dock-resize[data-edge=e]{right:0}.workflowx-graph-dock-resize[data-edge=w]{left:0}
    .workflowx-graph-dock-resize[data-edge=s],.workflowx-graph-dock-resize[data-edge=n]{left:7px;right:7px;height:8px;cursor:ns-resize}
    .workflowx-graph-dock-resize[data-edge=s]{bottom:0}.workflowx-graph-dock-resize[data-edge=n]{top:0}
    .workflowx-graph-dock-resize[data-edge=se],.workflowx-graph-dock-resize[data-edge=sw],
      .workflowx-graph-dock-resize[data-edge=ne],.workflowx-graph-dock-resize[data-edge=nw]{width:12px;height:12px}
    .workflowx-graph-dock-resize[data-edge=se]{right:0;bottom:0;cursor:nwse-resize}
    .workflowx-graph-dock-resize[data-edge=sw]{left:0;bottom:0;cursor:nesw-resize}
    .workflowx-graph-dock-resize[data-edge=ne]{right:0;top:0;cursor:nesw-resize}
    .workflowx-graph-dock-resize[data-edge=nw]{left:0;top:0;cursor:nwse-resize}
  `;
  document.head.appendChild(style);
}

export function createGraphDock({ app, node, ownerElement, propertyKey, title, content, onClose }) {
  installDockCSS();
  const saved = node.properties?.[propertyKey] || {};
  const dock = {
    app, node, ownerElement, propertyKey, graph: {
      x: Number(saved.x) || 30, y: Number(saved.y) || 40,
      w: Math.max(320, Number(saved.w) || 720), h: Math.max(220, Number(saved.h) || 520),
    },
    locked: Boolean(saved.locked), minimized: Boolean(saved.minimized), fullscreen: false,
  };
  const element = document.createElement("section");
  element.className = "workflowx-graph-dock";
  const head = document.createElement("header");
  head.className = "workflowx-graph-dock-head";
  const heading = document.createElement("div");
  heading.className = "workflowx-graph-dock-title";
  heading.textContent = title;
  const lock = makeButton(dock.locked ? "🔒" : "🔓", "Lock position and size");
  const minimize = makeButton(dock.minimized ? "▢" : "—", "Minimize");
  const fullscreen = makeButton("□", "Fullscreen");
  const close = makeButton("×", "Close");
  head.append(heading, lock, minimize, fullscreen, close);
  const body = document.createElement("div");
  body.className = "workflowx-graph-dock-body";
  body.append(content);
  element.append(head, body);
  dock.element = element;
  dock.body = body;
  document.body.appendChild(element);
  activeDocks.add(dock);

  const refreshClasses = () => {
    element.classList.toggle("locked", dock.locked);
    element.classList.toggle("minimized", dock.minimized);
    element.classList.toggle("fullscreen", dock.fullscreen);
    applyTransform(dock);
  };
  const begin = (event, edge = "move") => {
    if (dock.locked || dock.fullscreen || event.button !== 0) return;
    event.preventDefault(); stopEvent(event);
    const captureTarget = event.currentTarget; const pointerId = event.pointerId;
    const initial = {
      pointerX: event.clientX, pointerY: event.clientY,
      graphX: dock.graph.x, graphY: dock.graph.y, w: dock.graph.w, h: dock.graph.h,
    };
    let finished = false;
    const finish = () => {
      if (finished) return; finished = true;
      captureTarget.removeEventListener("pointermove", move);
      captureTarget.removeEventListener("pointerup", finish);
      captureTarget.removeEventListener("pointercancel", finish);
      captureTarget.removeEventListener("lostpointercapture", finish);
      if (captureTarget.hasPointerCapture?.(pointerId)) captureTarget.releasePointerCapture(pointerId);
      save(dock); node.graph?.setDirtyCanvas?.(true, true);
    };
    const move = (next) => {
      if ((next.buttons & 1) === 0) { finish(); return; }
      const [dx, dy] = canvasToGraphDelta(app, next.clientX - initial.pointerX, next.clientY - initial.pointerY);
      if (edge === "move") { dock.graph.x = initial.graphX + dx; dock.graph.y = initial.graphY + dy; }
      else {
        if (edge.includes("e")) dock.graph.w = Math.max(320, initial.w + dx);
        if (edge.includes("s")) dock.graph.h = Math.max(220, initial.h + dy);
        if (edge.includes("w")) { const w = Math.max(320, initial.w - dx); dock.graph.x = initial.graphX + initial.w - w; dock.graph.w = w; }
        if (edge.includes("n")) { const h = Math.max(220, initial.h - dy); dock.graph.y = initial.graphY + initial.h - h; dock.graph.h = h; }
      }
      element.__workflowxDockSignature = "";
      applyTransform(dock);
    };
    captureTarget.addEventListener("pointermove", move);
    captureTarget.addEventListener("pointerup", finish);
    captureTarget.addEventListener("pointercancel", finish);
    captureTarget.addEventListener("lostpointercapture", finish);
    captureTarget.setPointerCapture?.(pointerId);
  };
  head.addEventListener("pointerdown", (event) => {
    if (event.target.closest("button")) return;
    begin(event);
  });
  for (const edge of ["n", "e", "s", "w", "ne", "se", "sw", "nw"]) {
    const grip = document.createElement("div");
    grip.className = "workflowx-graph-dock-resize"; grip.dataset.edge = edge;
    grip.addEventListener("pointerdown", (event) => begin(event, edge)); element.appendChild(grip);
  }
  lock.onclick = () => { dock.locked = !dock.locked; lock.textContent = dock.locked ? "🔒" : "🔓"; save(dock); refreshClasses(); };
  minimize.onclick = () => { dock.minimized = !dock.minimized; minimize.textContent = dock.minimized ? "▢" : "—"; save(dock); refreshClasses(); };
  fullscreen.onclick = () => { dock.fullscreen = !dock.fullscreen; fullscreen.textContent = dock.fullscreen ? "◲" : "□"; refreshClasses(); };
  dock.close = () => {
    activeDocks.delete(dock); element.remove(); onClose?.();
    if (!activeDocks.size && animationFrame) { cancelAnimationFrame(animationFrame); animationFrame = 0; }
  };
  close.onclick = dock.close;
  for (const name of ["pointerdown", "pointerup", "pointermove", "wheel", "contextmenu"]) element.addEventListener(name, stopEvent);
  refreshClasses(); startTicking();
  return dock;
}
