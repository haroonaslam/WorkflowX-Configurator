import { app } from "../../scripts/app.js";

const TARGET_NODE = "FluxVisualJsonBuilder";
const OPEN_BUTTON = "Open Visual Builder";
const VISUAL_STATE_VERSION = 1;
const VISUAL_STATE_KEY = "flux_visual_state";

let presets = null;
let templates = {};
let currentNode = null;
let treeState = null;
let selectedNodeId = null;
let dragNodeId = null;

let overlayEl = null;
let treePanelEl = null;
let inspectorEl = null;
let statusEl = null;
let templateNameEl = null;
let templateListEl = null;
let templateStateEl = null;
let diagnosticsEl = null;
let forceApplyEl = null;
let randomizerListEl = null;
let selectedTemplateName = "";
let loadedTemplateName = "";
let baselineTreeSignature = "";

function uid(prefix = "node") {
    if (window.crypto?.randomUUID) return `${prefix}_${window.crypto.randomUUID()}`;
    return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function clone(obj) {
    return JSON.parse(JSON.stringify(obj));
}

function stripOptionsFromTree(node) {
    if (!node || typeof node !== "object") return;
    if (Object.prototype.hasOwnProperty.call(node, "options")) delete node.options;
    for (const child of node.children || []) stripOptionsFromTree(child);
    for (const item of node.items || []) stripOptionsFromTree(item);
    if (node.item_template) stripOptionsFromTree(node.item_template);
}

function cloneTreeForTemplateSave(tree) {
    const out = clone(tree);
    stripOptionsFromTree(out);
    return out;
}

function normalizedTree(node) {
    if (!node || typeof node !== "object") return null;

    if (node.node_type === "field") {
        const out = {
            node_type: "field",
            key: node.key || "",
            label: node.label || "",
            value: node.value || "",
        };
        if (node.options && typeof node.options === "object") out.options = clone(node.options);
        return out;
    }

    if (node.node_type === "group") {
        return {
            node_type: "group",
            key: node.key || "",
            label: node.label || "",
            children: (node.children || []).map(normalizedTree),
        };
    }

    if (node.node_type === "array") {
        return {
            node_type: "array",
            key: node.key || "",
            label: node.label || "",
            item_template: node.item_template ? normalizedTree(node.item_template) : null,
            items: (node.items || []).map(normalizedTree),
        };
    }

    return null;
}

function treeSignature(tree) {
    return JSON.stringify(normalizedTree(tree));
}

function promptSignatureFromObject(obj) {
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) return "{}";
    return JSON.stringify(obj);
}

function normalizeRandomizerChecked(raw) {
    const out = {};
    if (Array.isArray(raw)) {
        for (const id of raw) {
            const k = String(id || "").trim();
            if (k) out[k] = true;
        }
        return out;
    }

    if (raw && typeof raw === "object") {
        for (const [k, v] of Object.entries(raw)) {
            if (v) out[k] = true;
        }
    }
    return out;
}

function stateSignature(state) {
    const checked = Object.keys(state?.randomizerChecked || {})
        .filter((k) => state.randomizerChecked[k])
        .sort();
    return JSON.stringify({
        tree: normalizedTree(state?.tree || null),
        randomizer_checked: checked,
    });
}

function currentPromptSignature(node) {
    const widget = findPromptWidget(node);
    if (!widget?.value || !String(widget.value).trim()) return "{}";
    try {
        const parsed = JSON.parse(widget.value);
        return promptSignatureFromObject(parsed);
    } catch {
        return "{}";
    }
}

function persistVisualState(signatureOverride = null) {
    if (!currentNode || !treeState?.tree) return;
    if (!currentNode.properties || typeof currentNode.properties !== "object") currentNode.properties = {};

    currentNode.properties[VISUAL_STATE_KEY] = {
        version: VISUAL_STATE_VERSION,
        prompt_signature: signatureOverride || currentPromptSignature(currentNode),
        tree: cloneTreeForTemplateSave(treeState.tree),
        randomizer_checked: Object.keys(treeState.randomizerChecked || {}).filter((k) => treeState.randomizerChecked[k]),
    };
}

function loadPersistedVisualState(node, promptSignature) {
    const raw = node?.properties?.[VISUAL_STATE_KEY];
    if (!raw || typeof raw !== "object") return null;
    if (!raw.tree || typeof raw.tree !== "object") return null;
    if (raw.prompt_signature !== promptSignature) return null;
    return raw;
}

function markTreeClean() {
    baselineTreeSignature = stateSignature(treeState);
}

function isTreeDirty() {
    return stateSignature(treeState) !== baselineTreeSignature;
}

function setStatus(msg) {
    if (statusEl) statusEl.textContent = msg;
}

function findPromptWidget(node) {
    return node.widgets?.find((w) => w.name === "prompt_json") || null;
}

function isLeafOptions(node) {
    if (!node || typeof node !== "object" || Array.isArray(node)) return false;
    const vals = Object.values(node);
    return vals.length > 0 && vals.every((v) => typeof v === "string");
}

function flattenPresetLibrary(node, prefix = "", out = []) {
    if (!node || typeof node !== "object" || Array.isArray(node)) return out;
    if (isLeafOptions(node)) {
        out.push({ path: prefix, options: node });
        return out;
    }
    for (const [k, v] of Object.entries(node)) {
        const next = prefix ? `${prefix}.${k}` : k;
        flattenPresetLibrary(v, next, out);
    }
    return out;
}

function fieldNode(key, label, options = null, value = "") {
    const n = {
        id: uid("field"),
        node_type: "field",
        key,
        label: label || key,
        value,
        expanded: false,
    };
    if (options && typeof options === "object") n.options = clone(options);
    return n;
}

function groupNode(key, label, children = [], expanded = false) {
    return {
        id: uid("group"),
        node_type: "group",
        key,
        label: label || key,
        expanded,
        children,
    };
}

function arrayNode(key, label, itemTemplate, items = [], expanded = false) {
    return {
        id: uid("array"),
        node_type: "array",
        key,
        label: label || key,
        expanded,
        item_template: itemTemplate,
        items,
    };
}

function buildNodesFromPresetObject(key, value, label = null, expanded = false, presetPath = "") {
    const fullPath = presetPath || key;
    if (isLeafOptions(value)) {
        const f = fieldNode(key, label || key, value, "");
        f.origin_preset_path = fullPath;
        f.preset_path = fullPath;
        return f;
    }
    if (value && typeof value === "object" && !Array.isArray(value)) {
        const children = Object.entries(value).map(([k, v]) => buildNodesFromPresetObject(k, v, k, false, `${fullPath}.${k}`));
        const g = groupNode(key, label || key, children, expanded);
        g.origin_preset_path = fullPath;
        return g;
    }
    return fieldNode(key, label || key, null, "");
}

function buildSubjectItemTemplate(subjectPreset) {
    const identity = buildNodesFromPresetObject("identity", subjectPreset.identity || {}, "identity", false, "subject.identity");
    const dress = buildNodesFromPresetObject("dress", subjectPreset.dress || {}, "dress", false, "subject.dress");
    const pose = buildNodesFromPresetObject("pose", subjectPreset.pose || {}, "pose", false, "subject.pose");
    const properties = buildNodesFromPresetObject("properties", subjectPreset.properties || {}, "properties", false, "subject.properties");

    const common = groupNode(
        "common",
        "common",
        [
            fieldNode("id", "id", null, ""),
            fieldNode("name", "name", null, ""),
        ],
        false,
    );

    return groupNode("subject", "subject", [common, identity, dress, pose, properties], false);
}

function buildStarterTree() {
    const subjectPreset = presets.subject || {};

    const rootChildren = [
        buildNodesFromPresetObject("scene", presets.scene || {}, "scene", false, "scene"),
        arrayNode(
            "subjects",
            "subjects",
            buildSubjectItemTemplate(subjectPreset),
            [cloneWithFreshIds(buildSubjectItemTemplate(subjectPreset))],
            false,
        ),
        // Interactions: blank group container by design in v4.
        groupNode("interactions", "interactions", [], false),
        buildNodesFromPresetObject("style", presets.style || {}, "style", false, "style"),
        buildNodesFromPresetObject("lighting", presets.lighting || {}, "lighting", false, "lighting"),
        buildNodesFromPresetObject("camera", presets.camera || {}, "camera", false, "camera"),
        buildNodesFromPresetObject("mood", presets.mood || {}, "mood", false, "mood"),
        buildNodesFromPresetObject("quality", presets.quality || {}, "quality", false, "quality"),
        groupNode("negative", "negative", [fieldNode("text", "text", null, "")], false),
    ];

    return groupNode("prompt", "prompt", rootChildren, true);
}

function cloneWithFreshIds(node) {
    const n = clone(node);
    (function walk(x) {
        x.id = uid(x.node_type || "node");
        if (Array.isArray(x.children)) x.children.forEach(walk);
        if (Array.isArray(x.items)) x.items.forEach(walk);
        if (x.item_template) walk(x.item_template);
    })(n);
    return n;
}

function reorderListByPreferredKeys(list, preferredKeys) {
    if (!Array.isArray(list) || !Array.isArray(preferredKeys) || !preferredKeys.length) return list || [];
    const remaining = [...list];
    const ordered = [];
    for (const key of preferredKeys) {
        for (let i = 0; i < remaining.length;) {
            if (remaining[i].key === key) {
                ordered.push(remaining[i]);
                remaining.splice(i, 1);
            } else {
                i += 1;
            }
        }
    }
    return ordered.concat(remaining);
}

function reorderNodeFromPrompt(node, value) {
    if (!node) return;

    if (node.node_type === "group") {
        if (!value || typeof value !== "object" || Array.isArray(value)) return;
        node.children = reorderListByPreferredKeys(node.children || [], Object.keys(value));
        for (const child of node.children || []) {
            if (Object.prototype.hasOwnProperty.call(value, child.key)) {
                reorderNodeFromPrompt(child, value[child.key]);
            }
        }
        return;
    }

    if (node.node_type === "array") {
        if (!Array.isArray(value)) return;
        const lim = Math.min((node.items || []).length, value.length);
        for (let i = 0; i < lim; i += 1) {
            reorderNodeFromPrompt(node.items[i], value[i]);
        }
    }
}

function findPathToNode(root, targetId, trail = []) {
    if (!root) return null;
    const nextTrail = [...trail, root];
    if (root.id === targetId) return nextTrail;

    for (const child of root.children || []) {
        const hit = findPathToNode(child, targetId, nextTrail);
        if (hit) return hit;
    }
    for (const item of root.items || []) {
        const hit = findPathToNode(item, targetId, nextTrail);
        if (hit) return hit;
    }
    return null;
}

function findCanonicalNodeByPath(root, keyPath) {
    let cur = root;
    for (const key of keyPath || []) {
        if (!cur) return null;
        if (cur.node_type === "group") {
            cur = (cur.children || []).find((c) => c.key === key) || null;
            continue;
        }
        if (cur.node_type === "array") {
            const tpl = cur.item_template || null;
            if (tpl?.key === key) {
                cur = tpl;
            } else {
                cur = (cur.items || []).find((c) => c.key === key) || null;
            }
            continue;
        }
        return null;
    }
    return cur;
}

function reorderNodeToCanonical(node, canonicalNode, recursive) {
    if (!node || !canonicalNode) return;

    if (node.node_type === "group" && canonicalNode.node_type === "group") {
        const canonicalKeys = (canonicalNode.children || []).map((c) => c.key);
        node.children = reorderListByPreferredKeys(node.children || [], canonicalKeys);
        if (!recursive) return;

        for (const child of node.children || []) {
            const canonicalChild = (canonicalNode.children || []).find((c) => c.key === child.key) || null;
            reorderNodeToCanonical(child, canonicalChild, true);
        }
        return;
    }

    if (node.node_type === "array" && canonicalNode.node_type === "array") {
        if (!recursive) return;
        for (const item of node.items || []) {
            reorderNodeToCanonical(item, canonicalNode.item_template || null, true);
        }
    }
}

function ensureModal() {
    if (overlayEl) return;

    const style = document.createElement("style");
    style.textContent = `
    .f4-overlay { position: fixed; inset: 0; z-index: 10000; display: none; background: rgba(8, 10, 14, 0.82); color: #e7eef7; font-family: "Segoe UI", sans-serif; padding: 12px; box-sizing: border-box; }
    .f4-modal { width: min(1480px, 100%); height: min(940px, 100%); margin: 0 auto; border: 1px solid #24405a; border-radius: 12px; overflow: hidden; background: linear-gradient(165deg, #0f151c, #101a25); display: grid; grid-template-rows: auto 1fr auto; }
    .f4-head, .f4-foot { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 14px; border-bottom: 1px solid #23384b; }
    .f4-foot { border-bottom: 0; border-top: 1px solid #23384b; }
    .f4-body { display: grid; grid-template-columns: 290px 1fr 420px; min-height: 0; }
    .f4-side { border-right: 1px solid #23384b; padding: 10px; display: flex; flex-direction: column; gap: 8px; min-height: 0; }
    .f4-tree { border-right: 1px solid #23384b; padding: 10px; overflow: auto; background: radial-gradient(circle at top right, rgba(10, 95, 158, 0.14), transparent 46%); }
    .f4-inspector { padding: 10px; overflow: auto; }
    .f4-title { font-size: 15px; font-weight: 700; }
    .f4-sub { font-size: 12px; color: #9fb3c7; }
    .f4-list { border: 1px solid #2a4358; border-radius: 8px; overflow: auto; min-height: 240px; flex: 1 1 auto; background: rgba(12, 19, 27, 0.8); }
    .f4-item { padding: 8px 10px; border-bottom: 1px solid #21374a; cursor: pointer; user-select: none; }
    .f4-item:last-child { border-bottom: 0; }
    .f4-item:hover { background: rgba(22, 35, 49, 0.8); }
    .f4-item.sel { background: rgba(28, 74, 110, 0.65); }
    .f4-item.loaded::after { content: " loaded"; color: #8fc3ea; font-size: 11px; margin-left: 6px; }
    .f4-btn { border: 1px solid #395a78; background: #1a2d3d; color: #fff; border-radius: 6px; padding: 7px 10px; cursor: pointer; }
    .f4-btn.primary { background: #0f6ca8; border-color: #0f6ca8; }
    .f4-btn.warn { background: #7d3240; border-color: #7d3240; }
    .f4-btns { display: flex; flex-wrap: wrap; gap: 6px; }
    .f4-input, .f4-select, .f4-text { width: 100%; box-sizing: border-box; border-radius: 6px; border: 1px solid #35506b; background: #0f161f; color: #edf4fc; padding: 7px; }
    .f4-text { min-height: 72px; resize: vertical; }
    .f4-block { border: 1px solid #28445b; border-radius: 8px; background: rgba(12, 20, 30, 0.72); margin-bottom: 8px; }
    .f4-block-h { padding: 6px 8px; display: flex; align-items: center; justify-content: space-between; gap: 8px; border-bottom: 1px solid #223d51; }
    .f4-block-h.sel { background: rgba(19, 53, 79, 0.62); }
    .f4-chip { background: #224663; border-radius: 999px; padding: 1px 8px; font-size: 11px; }
    .f4-h-left { display:flex; align-items:center; gap:8px; }
    .f4-toggle { border: 1px solid #3f6280; background:#1a2f41; color:#fff; border-radius:4px; padding:0 6px; height:22px; cursor:pointer; }
    .f4-row-drag { cursor: grab; }
    .f4-children { padding: 7px 8px 6px 14px; border-top: 1px dashed #2a4861; }
    .f4-drop { border: 1px dashed #3d6280; border-radius: 6px; padding: 6px 7px; font-size: 12px; color: #a9c1d7; margin: 6px 0; }
    .f4-drop.on { background: rgba(22, 63, 94, 0.4); }
    .f4-grid2 { display: grid; gap: 8px; grid-template-columns: 1fr 1fr; }
    .f4-field { border: 1px solid #29475e; border-radius: 8px; background: rgba(14, 21, 31, 0.72); padding: 8px; margin-bottom: 8px; display: grid; gap: 6px; }
    .f4-check { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #c7d7e8; }
    .f4-diagnostics { min-height: 56px; max-height: 74px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    .f4-mini-list { border: 1px solid #2a4358; border-radius: 8px; overflow: auto; max-height: 190px; background: rgba(12, 19, 27, 0.8); }
    .f4-mini-item { padding: 6px 8px; border-bottom: 1px solid #21374a; display: flex; align-items: center; gap: 6px; font-size: 12px; }
    .f4-mini-item:last-child { border-bottom: 0; }
    @media (max-width: 1240px) { .f4-body { grid-template-columns: 280px 1fr; } .f4-inspector { grid-column: 1 / -1; border-top: 1px solid #23384b; } }
    `;
    document.head.appendChild(style);

    overlayEl = document.createElement("div");
    overlayEl.className = "f4-overlay";
    overlayEl.innerHTML = `
      <div class="f4-modal">
        <div class="f4-head">
          <div>
            <div class="f4-title">AFJ Visual Builder v4</div>
            <div class="f4-sub">All tags optional. Interactions starts blank. Presets are direct JSON-editable.</div>
          </div>
          <div class="f4-chip">simple-presets mode</div>
        </div>
        <div class="f4-body">
          <aside class="f4-side">
            <div><strong>Templates</strong></div>
            <input id="f4-template-name" class="f4-input" placeholder="Template name" />
            <div class="f4-btns">
              <button id="f4-save-template" class="f4-btn">Save</button>
              <button id="f4-load-template" class="f4-btn">Load</button>
              <button id="f4-delete-template" class="f4-btn warn">Delete</button>
            </div>
            <div class="f4-btns">
              <button id="f4-expand-all" class="f4-btn">Expand All</button>
              <button id="f4-collapse-all" class="f4-btn">Collapse All</button>
              <button id="f4-reset-order" class="f4-btn">Reset Order</button>
              <button id="f4-global-reset" class="f4-btn warn">Global Reset</button>
            </div>
            <div id="f4-template-list" class="f4-list"></div>
            <div id="f4-template-state" class="f4-sub">Selected: (none) | Loaded: (none) | Unsaved: no</div>
            <div class="f4-field">
              <label>Validation (errors/warnings)</label>
              <textarea id="f4-diagnostics" class="f4-text f4-diagnostics" readonly>No validation run yet.</textarea>
              <label class="f4-check"><input id="f4-force-apply" type="checkbox" /> Force apply even when validation has errors</label>
            </div>

            <div class="f4-sub">Drag node headers to reorder or reparent. Drop over row to place before, or drop into container zone.</div>
          </aside>
          <section id="f4-tree-panel" class="f4-tree"></section>
          <section id="f4-inspector" class="f4-inspector"></section>
        </div>
        <div class="f4-foot">
          <div id="f4-status" class="f4-sub">Ready.</div>
          <div class="f4-btns">
            <button id="f4-close" class="f4-btn">Close</button>
            <button id="f4-apply" class="f4-btn primary">Validate & Apply</button>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(overlayEl);

    treePanelEl = overlayEl.querySelector("#f4-tree-panel");
    inspectorEl = overlayEl.querySelector("#f4-inspector");
    statusEl = overlayEl.querySelector("#f4-status");
    templateNameEl = overlayEl.querySelector("#f4-template-name");
    templateListEl = overlayEl.querySelector("#f4-template-list");
    templateStateEl = overlayEl.querySelector("#f4-template-state");
    diagnosticsEl = overlayEl.querySelector("#f4-diagnostics");
    forceApplyEl = overlayEl.querySelector("#f4-force-apply");
    randomizerListEl = null;

    overlayEl.querySelector("#f4-close").addEventListener("click", closeBuilder);
    overlayEl.querySelector("#f4-apply").addEventListener("click", validateAndApply);
    overlayEl.querySelector("#f4-save-template").addEventListener("click", saveTemplate);
    overlayEl.querySelector("#f4-load-template").addEventListener("click", loadSelectedTemplate);
    overlayEl.querySelector("#f4-delete-template").addEventListener("click", deleteTemplate);
    overlayEl.querySelector("#f4-expand-all").addEventListener("click", () => setCollapseState(true));
    overlayEl.querySelector("#f4-collapse-all").addEventListener("click", () => setCollapseState(false));
    overlayEl.querySelector("#f4-reset-order").addEventListener("click", resetOrderWithScopePrompt);
    overlayEl.querySelector("#f4-global-reset").addEventListener("click", globalResetWithConfirm);
    forceApplyEl.addEventListener("change", () => {
        if (!treeState) return;
        treeState.forceApply = !!forceApplyEl.checked;
        renderTemplateState();
    });
    templateNameEl.addEventListener("input", () => {
        const typed = (templateNameEl.value || "").trim();
        selectedTemplateName = typed && templates[typed] ? typed : "";
        renderTemplateList();
        renderTemplateState();
    });
}

async function loadPresets() {
    if (presets) return presets;
    const r = await fetch("/fluxvisual/presets");
    if (!r.ok) throw new Error(`/fluxvisual/presets returned ${r.status}`);
    presets = await r.json();
    return presets;
}

function renderTemplateState() {
    if (!templateStateEl) return;
    const selected = selectedTemplateName || "(none)";
    const loaded = loadedTemplateName || "(none)";
    const unsaved = treeState ? (isTreeDirty() ? "yes" : "no") : "no";
    templateStateEl.textContent = `Selected: ${selected} | Loaded: ${loaded} | Unsaved: ${unsaved}`;
}

async function loadTemplates() {
    try {
        const r = await fetch("/fluxvisual/templates");
        templates = r.ok ? await r.json() : {};
    } catch {
        templates = {};
    }

    if (selectedTemplateName && !templates[selectedTemplateName]) selectedTemplateName = "";
    if (loadedTemplateName && !templates[loadedTemplateName]) loadedTemplateName = "";

    renderTemplateList();
    renderTemplateState();
}

function renderTemplateList() {
    templateListEl.innerHTML = "";
    const names = Object.keys(templates || {}).sort((a, b) => a.localeCompare(b));
    if (!names.length) {
        const empty = document.createElement("div");
        empty.className = "f4-item";
        empty.textContent = "No templates saved.";
        templateListEl.appendChild(empty);
        return;
    }

    for (const name of names) {
        const row = document.createElement("div");
        const classes = ["f4-item"];
        if (name === selectedTemplateName) classes.push("sel");
        if (name === loadedTemplateName) classes.push("loaded");
        row.className = classes.join(" ");
        row.textContent = name;
        row.addEventListener("click", () => {
            selectedTemplateName = name;
            templateNameEl.value = name;
            renderTemplateList();
            renderTemplateState();
            setStatus(`Selected template '${name}'. Click Load to apply.`);
        });
        templateListEl.appendChild(row);
    }
}

function resolveTemplateNameForLoad() {
    const typed = (templateNameEl?.value || "").trim();
    if (typed && templates[typed]) return typed;
    if (selectedTemplateName && templates[selectedTemplateName]) return selectedTemplateName;
    return "";
}

function loadSelectedTemplate() {
    const name = resolveTemplateNameForLoad();
    if (!name) {
        setStatus("Select or type a saved template name first.");
        return;
    }

    if (isTreeDirty()) {
        const ok = window.confirm(`Loading template '${name}' will overwrite unsaved edits. Continue?`);
        if (!ok) {
            setStatus("Template load canceled.");
            return;
        }
    }

    treeState = hydrateStateFromTemplate(templates[name]);
    selectedNodeId = treeState.tree.id;
    selectedTemplateName = name;
    loadedTemplateName = name;
    markTreeClean();
    renderAll();
    renderTemplateList();
    setStatus(`Loaded template '${name}'.`);
}
function walkTree(node, fn, parent = null, listRef = null, index = -1) {
    fn({ node, parent, listRef, index });
    (node.children || []).forEach((c, i) => walkTree(c, fn, node, node.children, i));
    (node.items || []).forEach((c, i) => walkTree(c, fn, node, node.items, i));
}

function findCtxById(root, id) {
    let found = null;
    walkTree(root, (ctx) => {
        if (!found && ctx.node.id === id) found = ctx;
    });
    return found;
}

function setCollapseState(open) {
    if (!treeState?.tree) return;
    walkTree(treeState.tree, ({ node, parent }) => {
        if (node.node_type === "group" || node.node_type === "array") {
            if (!parent) node.expanded = true; // root always visible
            else node.expanded = open;
        }
    });
    renderAll();
}

function isDescendant(rootNode, id) {
    let hit = false;
    walkTree(rootNode, ({ node }) => {
        if (node.id === id) hit = true;
    });
    return hit;
}

function getContainerList(node) {
    if (!node) return null;
    if (node.node_type === "group") {
        if (!Array.isArray(node.children)) node.children = [];
        return node.children;
    }
    if (node.node_type === "array") {
        if (!Array.isArray(node.items)) node.items = [];
        return node.items;
    }
    return null;
}

function keyPathForNode(root, nodeId) {
    const path = findPathToNode(root, nodeId) || [];
    return path.map((n) => n.key).slice(1);
}

function findNodeByKeyPath(root, keyPath) {
    let cur = root;
    for (const key of keyPath || []) {
        if (!cur) return null;

        if (cur.node_type === "group") {
            cur = (cur.children || []).find((c) => c.key === key) || null;
            continue;
        }

        if (cur.node_type === "array") {
            const firstItem = (cur.items || [])[0] || null;
            if (!firstItem) return null;
            if (firstItem.key === key) {
                cur = firstItem;
            } else if (firstItem.node_type === "group") {
                cur = (firstItem.children || []).find((c) => c.key === key) || null;
            } else {
                cur = null;
            }
            continue;
        }

        return null;
    }
    return cur;
}

function buildCanonicalFieldParentMap(canonicalRoot) {
    const out = new Map();
    walkTree(canonicalRoot, ({ node, parent }) => {
        if (!parent || node.node_type !== "field") return;
        const presetPath = node.origin_preset_path || node.preset_path || "";
        if (!presetPath || out.has(presetPath)) return;
        out.set(presetPath, keyPathForNode(canonicalRoot, parent.id));
    });
    return out;
}

function reparentOriginalPresetFieldsToCanonical(canonicalRoot) {
    const parentMap = buildCanonicalFieldParentMap(canonicalRoot);
    const moves = [];

    walkTree(treeState.tree, ({ node, parent }) => {
        if (!parent || node.node_type !== "field") return;
        if (node.is_duplicate) return;

        const presetPath = node.origin_preset_path || "";
        if (!presetPath) return;

        const targetParentPath = parentMap.get(presetPath);
        if (!targetParentPath) return;

        const currentParentPath = keyPathForNode(treeState.tree, parent.id);
        if (JSON.stringify(currentParentPath) === JSON.stringify(targetParentPath)) return;

        moves.push({ nodeId: node.id, targetParentPath });
    });

    for (const m of moves) {
        const ctx = findCtxById(treeState.tree, m.nodeId);
        if (!ctx || !ctx.parent || !ctx.listRef) continue;

        const targetParent = findNodeByKeyPath(treeState.tree, m.targetParentPath);
        const targetList = getContainerList(targetParent);
        if (!targetList) continue;

        ctx.listRef.splice(ctx.index, 1);
        targetList.push(ctx.node);
    }
}

function markNodeAsDuplicate(node) {
    if (!node || typeof node !== "object") return;
    node.is_duplicate = true;
    for (const child of node.children || []) markNodeAsDuplicate(child);
    for (const item of node.items || []) markNodeAsDuplicate(item);
    if (node.item_template) markNodeAsDuplicate(node.item_template);
}

function walkTreeWithPath(node, fn, path = []) {
    if (!node) return;
    const next = [...path, node.key || ""];
    fn(node, next);
    for (const child of node.children || []) walkTreeWithPath(child, fn, next);
    for (const item of node.items || []) walkTreeWithPath(item, fn, next);
}

function getRandomizableFields() {
    const out = [];
    if (!treeState?.tree) return out;

    walkTreeWithPath(treeState.tree, (node, path) => {
        if (node.node_type !== "field") return;
        if (!node.options || typeof node.options !== "object") return;
        const optionCount = Object.keys(node.options).length;
        if (!optionCount) return;
        out.push({ node, pathLabel: path.slice(1).join(".") || node.key });
    });

    out.sort((a, b) => a.pathLabel.localeCompare(b.pathLabel));
    return out;
}

function renderRandomizerPanel() {
    if (!randomizerListEl || !treeState) return;
    if (!treeState.randomizerChecked || typeof treeState.randomizerChecked !== "object") {
        treeState.randomizerChecked = {};
    }

    randomizerListEl.innerHTML = "";
    const fields = getRandomizableFields();
    const validIds = new Set(fields.map((f) => f.node.id));
    for (const id of Object.keys(treeState.randomizerChecked)) {
        if (!validIds.has(id)) delete treeState.randomizerChecked[id];
    }

    if (!fields.length) {
        const empty = document.createElement("div");
        empty.className = "f4-mini-item";
        empty.textContent = "No preset-backed fields available.";
        randomizerListEl.appendChild(empty);
        return;
    }

    for (const f of fields) {
        const row = document.createElement("label");
        row.className = "f4-mini-item";
        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.checked = !!treeState.randomizerChecked[f.node.id];
        cb.addEventListener("change", () => {
            if (cb.checked) treeState.randomizerChecked[f.node.id] = true;
            else delete treeState.randomizerChecked[f.node.id];
            renderTemplateState();
        });

        const txt = document.createElement("span");
        txt.textContent = f.pathLabel;
        row.appendChild(cb);
        row.appendChild(txt);
        randomizerListEl.appendChild(row);
    }
}

function randomizeCheckedFields() {
    if (!treeState?.tree) return;
    const fields = getRandomizableFields();
    const byId = new Map(fields.map((f) => [f.node.id, f.node]));
    let changed = 0;

    for (const id of Object.keys(treeState.randomizerChecked || {})) {
        if (!treeState.randomizerChecked[id]) continue;
        const node = byId.get(id);
        if (!node) continue;

        const options = Object.values(node.options || {});
        if (!options.length) continue;

        const pick = options[Math.floor(Math.random() * options.length)];
        node.value = String(pick || "");
        changed += 1;
    }

    if (!changed) {
        setStatus("Randomize skipped: no checked preset-backed fields available.");
        return;
    }

    renderAll();
    setStatus(`Randomized ${changed} field${changed === 1 ? "" : "s"}.`);
}

function renderDiagnosticsPanel() {
    if (!diagnosticsEl || !forceApplyEl || !treeState) return;
    diagnosticsEl.value = treeState.lastDiagnostics || "No validation run yet.";
    forceApplyEl.checked = !!treeState.forceApply;
}

function enrichPresetBindingsFromTree(root) {
    const entries = getPresetLibraryEntries();
    const byPath = new Map(entries.map((e) => [e.path, e]));
    const byLeaf = new Map();

    for (const e of entries) {
        const leaf = (e.path.split(".").slice(-1)[0] || "").toLowerCase();
        if (!byLeaf.has(leaf)) byLeaf.set(leaf, []);
        byLeaf.get(leaf).push(e);
    }

    const baseKey = (key) => String(key || "").replace(/_\d+$/, "").toLowerCase();

    walkTree(root, ({ node }) => {
        if (node.node_type !== "field") return;
        let chosen = null;
        if (node.preset_path && byPath.has(node.preset_path)) chosen = byPath.get(node.preset_path);
        if (!chosen && node.origin_preset_path && byPath.has(node.origin_preset_path)) chosen = byPath.get(node.origin_preset_path);
        if (!chosen) {
            const cands = byLeaf.get(baseKey(node.key)) || [];
            if (cands.length === 1) chosen = cands[0];
        }

        if (!chosen) {
            if (Object.prototype.hasOwnProperty.call(node, "options")) delete node.options;
            return;
        }
        node.options = clone(chosen.options);
        if (!node.preset_path) node.preset_path = chosen.path;
        if (!node.origin_preset_path) node.origin_preset_path = chosen.path;
    });
}

function globalResetWithConfirm() {
    const ok = window.confirm("Global reset will clear current editor values and restore starter structure/order. Continue?");
    if (!ok) {
        setStatus("Global reset canceled.");
        return;
    }

    treeState = {
        tree: buildStarterTree(),
        lastDiagnostics: "No validation run yet.",
        forceApply: false,
        randomizerChecked: {},
    };
    selectedNodeId = treeState.tree.id;
    renderAll();
    setStatus("Global reset complete.");
}
function nextSiblingKey(baseKey, siblings) {
    const safeBase = String(baseKey || "node").trim() || "node";
    const keys = new Set((siblings || []).map((n) => String(n?.key || "")));
    let i = 2;
    let candidate = `${safeBase}_${i}`;
    while (keys.has(candidate)) {
        i += 1;
        candidate = `${safeBase}_${i}`;
    }
    return candidate;
}

function clearNodeValues(node) {
    if (!node) return;

    if (node.node_type === "field") {
        node.value = "";
        return;
    }

    if (node.node_type === "group") {
        for (const child of node.children || []) clearNodeValues(child);
        return;
    }

    if (node.node_type === "array") {
        for (const item of node.items || []) clearNodeValues(item);
    }
}

function clearSelectedNodeValues(nodeId) {
    const ctx = findCtxById(treeState.tree, nodeId);
    if (!ctx || !ctx.parent) return;
    clearNodeValues(ctx.node);
    renderAll();
    setStatus(`Cleared values for '${ctx.node.key}'.`);
}

function duplicateNode(nodeId, mode = "copy") {
    const ctx = findCtxById(treeState.tree, nodeId);
    if (!ctx || !ctx.parent || !ctx.listRef) return;

    const copy = cloneWithFreshIds(ctx.node);
    markNodeAsDuplicate(copy);
    copy.key = nextSiblingKey(ctx.node.key || copy.node_type || "node", ctx.listRef);
    if (mode === "clear") clearNodeValues(copy);

    ctx.listRef.splice(ctx.index + 1, 0, copy);
    selectedNodeId = copy.id;
    renderAll();
    setStatus(`Duplicated '${ctx.node.key}' as '${copy.key}' (${mode === "clear" ? "clear values" : "copy values"}).`);
}

function duplicateNodeWithPrompt(nodeId) {
    const answer = window.prompt(
        "Duplicate mode:\n1) Copy values\n2) Clear values\nEnter 1 or 2.",
        "1",
    );
    if (answer === null) {
        setStatus("Duplicate canceled.");
        return;
    }

    const v = String(answer).trim().toLowerCase();
    if (v === "1" || v === "copy" || v === "copy values") {
        duplicateNode(nodeId, "copy");
        return;
    }
    if (v === "2" || v === "clear" || v === "clear values") {
        duplicateNode(nodeId, "clear");
        return;
    }

    setStatus("Duplicate canceled: invalid choice.");
}

function nearestSelectedGroupLikeCtx() {
    const root = treeState?.tree;
    if (!root) return null;

    let ctx = findCtxById(root, selectedNodeId || root.id);
    while (ctx && ctx.node.node_type === "field") {
        if (!ctx.parent) break;
        ctx = findCtxById(root, ctx.parent.id);
    }
    return ctx;
}

function resetOrder(scope) {
    if (!treeState?.tree) return;
    const canonicalRoot = buildStarterTree();

    if (scope === "root") {
        reorderNodeToCanonical(treeState.tree, canonicalRoot, false);
        renderAll();
        setStatus("Reset order applied: root categories only.");
        return;
    }

    if (scope === "selected") {
        const targetCtx = nearestSelectedGroupLikeCtx();
        if (!targetCtx || (targetCtx.node.node_type !== "group" && targetCtx.node.node_type !== "array")) {
            setStatus("Select a group or array (or one of their fields) first.");
            return;
        }

        const path = findPathToNode(treeState.tree, targetCtx.node.id) || [];
        const keyPath = path.map((n) => n.key).slice(1);
        const canonicalTarget = findCanonicalNodeByPath(canonicalRoot, keyPath);
        if (!canonicalTarget) {
            setStatus("No canonical order found for selected group.");
            return;
        }

        reorderNodeToCanonical(targetCtx.node, canonicalTarget, true);
        renderAll();
        setStatus(`Reset order applied: selected group '${targetCtx.node.key}'.`);
        return;
    }

    reparentOriginalPresetFieldsToCanonical(canonicalRoot);
    reorderNodeToCanonical(treeState.tree, canonicalRoot, true);
    renderAll();
    setStatus("Reset order applied: all groups.");
}

function resetOrderWithScopePrompt() {
    const answer = window.prompt(
        "Reset order scope:\n1) Root categories only\n2) Selected group\n3) All\nEnter 1, 2, or 3.",
        "1",
    );

    if (answer === null) {
        setStatus("Reset order canceled.");
        return;
    }

    const v = String(answer).trim().toLowerCase();
    if (v === "1" || v === "root" || v === "root categories only") {
        resetOrder("root");
        return;
    }
    if (v === "2" || v === "selected" || v === "selected group") {
        resetOrder("selected");
        return;
    }
    if (v === "3" || v === "all") {
        resetOrder("all");
        return;
    }

    setStatus("Reset order canceled: invalid choice.");
}

function moveNodeBefore(targetId) {
    if (!dragNodeId || dragNodeId === targetId) return;
    const root = treeState.tree;
    const drag = findCtxById(root, dragNodeId);
    const target = findCtxById(root, targetId);
    if (!drag || !target || !drag.parent || !target.parent) return;
    if (drag.node.id === root.id) return;
    if (isDescendant(drag.node, target.node.id)) return;

    drag.listRef.splice(drag.index, 1);
    const refreshedTarget = findCtxById(root, targetId);
    if (!refreshedTarget?.listRef) return;
    refreshedTarget.listRef.splice(refreshedTarget.index, 0, drag.node);
    dragNodeId = null;
    renderAll();
}

function moveNodeInto(containerId) {
    if (!dragNodeId || dragNodeId === containerId) return;
    const root = treeState.tree;
    const drag = findCtxById(root, dragNodeId);
    const containerCtx = findCtxById(root, containerId);
    if (!drag || !containerCtx || !drag.parent) return;
    if (drag.node.id === root.id) return;
    if (isDescendant(drag.node, containerCtx.node.id)) return;

    const list = getContainerList(containerCtx.node);
    if (!list) return;

    drag.listRef.splice(drag.index, 1);
    list.push(drag.node);
    dragNodeId = null;
    renderAll();
}

function addChildNode(parentId, type) {
    const ctx = findCtxById(treeState.tree, parentId);
    if (!ctx) return;
    const list = getContainerList(ctx.node);
    if (!list) return;

    let child;
    if (type === "group") {
        child = groupNode("new_group", "new_group", [], false);
    } else if (type === "array") {
        child = arrayNode("new_array", "new_array", groupNode("item", "item", [], false), [], false);
    } else {
        child = fieldNode("new_field", "new_field", null, "");
    }

    list.push(child);
    selectedNodeId = child.id;
    renderAll();
}

function removeNode(nodeId) {
    const ctx = findCtxById(treeState.tree, nodeId);
    if (!ctx || !ctx.parent || !ctx.listRef) return;
    ctx.listRef.splice(ctx.index, 1);
    selectedNodeId = treeState.tree.id;
    renderAll();
}

function addArrayItem(arrayNodeId) {
    const ctx = findCtxById(treeState.tree, arrayNodeId);
    if (!ctx || ctx.node.node_type !== "array") return;
    const tpl = ctx.node.item_template ? cloneWithFreshIds(ctx.node.item_template) : groupNode("item", "item", [], false);
    if (!Array.isArray(ctx.node.items)) ctx.node.items = [];
    ctx.node.items.push(tpl);
    selectedNodeId = tpl.id;
    renderAll();
}

function renderTreeNode(node, container) {
    const block = document.createElement("div");
    block.className = "f4-block";

    const header = document.createElement("div");
    header.className = `f4-block-h ${selectedNodeId === node.id ? "sel" : ""}`;

    const left = document.createElement("div");
    left.className = "f4-h-left";

    const toggle = document.createElement("button");
    toggle.className = "f4-toggle";
    toggle.textContent = node.node_type === "field" ? "." : (node.expanded ? "-" : "+");
    toggle.disabled = node.node_type === "field";
    toggle.addEventListener("click", (e) => {
        e.stopPropagation();
        if (node.node_type === "group" || node.node_type === "array") {
            node.expanded = !node.expanded;
            renderAll();
        }
    });

    const title = document.createElement("div");
    title.innerHTML = `<strong>${node.key}</strong> <span class="f4-chip">${node.node_type}</span>`;

    left.appendChild(toggle);
    left.appendChild(title);

    const right = document.createElement("div");
    right.className = "f4-sub";
    right.textContent = node.label || node.key;

    header.appendChild(left);
    header.appendChild(right);

    header.classList.add("f4-row-drag");
    header.draggable = node.id !== treeState.tree.id;
    header.addEventListener("dragstart", () => {
        dragNodeId = node.id;
    });
    header.addEventListener("dragover", (e) => e.preventDefault());
    header.addEventListener("drop", (e) => {
        e.preventDefault();
        moveNodeBefore(node.id);
    });

    header.addEventListener("click", () => {
        selectedNodeId = node.id;
        renderAll();
    });

    block.appendChild(header);

    if (node.node_type === "group" || node.node_type === "array") {
        const drop = document.createElement("div");
        drop.className = "f4-drop";
        drop.textContent = `Drop into ${node.key}`;
        drop.addEventListener("dragover", (e) => {
            e.preventDefault();
            drop.classList.add("on");
        });
        drop.addEventListener("dragleave", () => drop.classList.remove("on"));
        drop.addEventListener("drop", (e) => {
            e.preventDefault();
            drop.classList.remove("on");
            moveNodeInto(node.id);
        });
        block.appendChild(drop);
    }

    if (node.expanded && (node.node_type === "group" || node.node_type === "array")) {
        const kidsWrap = document.createElement("div");
        kidsWrap.className = "f4-children";
        const kids = node.node_type === "group" ? (node.children || []) : (node.items || []);
        for (const child of kids) renderTreeNode(child, kidsWrap);
        block.appendChild(kidsWrap);
    }

    container.appendChild(block);
}

function renderTree() {
    treePanelEl.innerHTML = "";
    if (!treeState?.tree) return;
    renderTreeNode(treeState.tree, treePanelEl);
}

function getPresetLibraryEntries() {
    const libraryRoot = {
        scene: presets.scene || {},
        style: presets.style || {},
        lighting: presets.lighting || {},
        camera: presets.camera || {},
        mood: presets.mood || {},
        quality: presets.quality || {},
        subject: presets.subject || {},
        interaction_suggestions: presets.interaction_suggestions || {},
    };
    return flattenPresetLibrary(libraryRoot);
}
function renderInspector() {
    inspectorEl.innerHTML = "";
    if (!treeState?.tree) return;

    const ctx = findCtxById(treeState.tree, selectedNodeId || treeState.tree.id);
    const node = ctx?.node || treeState.tree;
    selectedNodeId = node.id;

    const summary = document.createElement("div");
    summary.className = "f4-field";
    summary.innerHTML = `<strong>Selected Node</strong><div class="f4-sub">id=${node.id} | type=${node.node_type}</div>`;
    inspectorEl.appendChild(summary);

    const randomizerField = document.createElement("div");
    randomizerField.className = "f4-field";
    randomizerField.innerHTML = `<label>Randomizer (preset-backed fields)</label>`;
    randomizerListEl = document.createElement("div");
    randomizerListEl.className = "f4-mini-list";
    const randomizeBtn = document.createElement("button");
    randomizeBtn.className = "f4-btn";
    randomizeBtn.textContent = "Randomize Checked";
    randomizeBtn.addEventListener("click", randomizeCheckedFields);
    randomizerField.appendChild(randomizerListEl);
    randomizerField.appendChild(randomizeBtn);
    inspectorEl.appendChild(randomizerField);

    const keyLabel = document.createElement("div");
    keyLabel.className = "f4-grid2";
    keyLabel.innerHTML = `
      <div class="f4-field"><label>Key</label><input class="f4-input" value="${node.key || ""}" /></div>
      <div class="f4-field"><label>Label</label><input class="f4-input" value="${node.label || ""}" /></div>
    `;
    const [keyInput, labelInput] = keyLabel.querySelectorAll("input");
    keyInput.addEventListener("input", (e) => {
        node.key = e.target.value;
        renderTree();
        renderTemplateState();
    });
    labelInput.addEventListener("input", (e) => {
        node.label = e.target.value;
        renderTemplateState();
    });
    inspectorEl.appendChild(keyLabel);

    const actions = document.createElement("div");
    actions.className = "f4-btns";
    if (node.node_type === "group" || node.node_type === "array") {
        const addFieldBtn = document.createElement("button");
        addFieldBtn.className = "f4-btn";
        addFieldBtn.textContent = "+ Field";
        addFieldBtn.addEventListener("click", () => addChildNode(node.id, "field"));
        actions.appendChild(addFieldBtn);

        const addGroupBtn = document.createElement("button");
        addGroupBtn.className = "f4-btn";
        addGroupBtn.textContent = "+ Group";
        addGroupBtn.addEventListener("click", () => addChildNode(node.id, "group"));
        actions.appendChild(addGroupBtn);

        const addArrayBtn = document.createElement("button");
        addArrayBtn.className = "f4-btn";
        addArrayBtn.textContent = "+ Array";
        addArrayBtn.addEventListener("click", () => addChildNode(node.id, "array"));
        actions.appendChild(addArrayBtn);

        if (node.node_type === "array") {
            const addItemBtn = document.createElement("button");
            addItemBtn.className = "f4-btn";
            addItemBtn.textContent = "+ Item";
            addItemBtn.addEventListener("click", () => addArrayItem(node.id));
            actions.appendChild(addItemBtn);
        }
    }

    if (node.id !== treeState.tree.id) {
        const clearBtn = document.createElement("button");
        clearBtn.className = "f4-btn";
        clearBtn.textContent = "Clear Values";
        clearBtn.addEventListener("click", () => clearSelectedNodeValues(node.id));
        actions.appendChild(clearBtn);

        const dupBtn = document.createElement("button");
        dupBtn.className = "f4-btn";
        dupBtn.textContent = "Duplicate Node";
        dupBtn.addEventListener("click", () => duplicateNodeWithPrompt(node.id));
        actions.appendChild(dupBtn);

        const delBtn = document.createElement("button");
        delBtn.className = "f4-btn warn";
        delBtn.textContent = "Delete Node";
        delBtn.addEventListener("click", () => removeNode(node.id));
        actions.appendChild(delBtn);
    }
    inspectorEl.appendChild(actions);

    if (node.node_type === "field") {
        const valueField = document.createElement("div");
        valueField.className = "f4-field";

        if (node.options && typeof node.options === "object") {
            valueField.innerHTML = `<label>Preset Value</label>`;
            const select = document.createElement("select");
            select.className = "f4-select";
            select.appendChild(new Option("-- none --", "-- none --"));
            for (const k of Object.keys(node.options)) select.appendChild(new Option(k, k));
            select.value = "-- none --";
            for (const [k, v] of Object.entries(node.options)) {
                if (String(v) === String(node.value || "")) {
                    select.value = k;
                    break;
                }
            }

            const text = document.createElement("textarea");
            text.className = "f4-text";
            text.value = node.value || "";

            select.addEventListener("change", () => {
                if (select.value === "-- none --") {
                    node.value = "";
                    text.value = "";
                } else {
                    node.value = node.options[select.value] || "";
                    text.value = node.value;
                }
                renderTree();
                renderTemplateState();
            });

            text.addEventListener("input", () => {
                node.value = text.value;
                renderTree();
                renderTemplateState();
            });

            valueField.appendChild(select);
            valueField.appendChild(text);
        } else {
            valueField.innerHTML = `<label>Value</label><textarea class="f4-text">${node.value || ""}</textarea>`;
            valueField.querySelector("textarea").addEventListener("input", (e) => {
                node.value = e.target.value;
                renderTree();
                renderTemplateState();
            });
        }

        inspectorEl.appendChild(valueField);

        const attachField = document.createElement("div");
        attachField.className = "f4-field";
        attachField.innerHTML = `<label>Attach Preset Options</label>`;

        const attachSearch = document.createElement("input");
        attachSearch.className = "f4-input";
        attachSearch.placeholder = "Search preset paths (substring match)";

        const attachSelect = document.createElement("select");
        attachSelect.className = "f4-select";
        const entries = getPresetLibraryEntries();

        const fillAttachOptions = () => {
            const q = String(attachSearch.value || "").trim().toLowerCase();
            const selected = node.preset_path || attachSelect.value || "";

            attachSelect.innerHTML = "";
            attachSelect.appendChild(new Option("-- custom/no preset --", ""));
            const filtered = entries.filter((e) => !q || e.path.toLowerCase().includes(q));
            for (const e of filtered) {
                attachSelect.appendChild(new Option(e.path, e.path));
            }

            if (selected && filtered.some((e) => e.path === selected)) {
                attachSelect.value = selected;
            }
        };

        attachSearch.addEventListener("input", fillAttachOptions);
        fillAttachOptions();

        attachSelect.addEventListener("change", () => {
            const chosen = entries.find((e) => e.path === attachSelect.value);
            if (!chosen) {
                delete node.options;
                delete node.preset_path;
                renderAll();
                return;
            }
            node.options = clone(chosen.options);
            node.preset_path = chosen.path;
            if (!node.origin_preset_path) node.origin_preset_path = chosen.path;
            node.key = chosen.path.split(".").slice(-1)[0] || node.key;
            node.label = chosen.path;
            node.value = "";
            renderAll();
        });

        attachField.appendChild(attachSearch);
        attachField.appendChild(attachSelect);
        inspectorEl.appendChild(attachField);
    }
}

function compileNode(node) {
    if (!node) return undefined;

    if (node.node_type === "field") {
        const v = String(node.value || "").trim();
        return v ? v : undefined;
    }

    if (node.node_type === "group") {
        const out = {};
        for (const child of node.children || []) {
            const val = compileNode(child);
            if (val === undefined) continue;
            out[child.key || "field"] = val;
        }
        return Object.keys(out).length ? out : undefined;
    }

    if (node.node_type === "array") {
        const arr = [];
        for (const item of node.items || []) {
            const val = compileNode(item);
            if (val !== undefined) arr.push(val);
        }
        return arr.length ? arr : undefined;
    }

    return undefined;
}

function applyPromptObjectToGroup(group, obj) {
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) return;

    for (const [k, v] of Object.entries(obj)) {
        let child = (group.children || []).find((c) => c.key === k);
        if (!child) {
            child = makeNodeFromValue(k, v);
            group.children.push(child);
        }
        applyValueToNode(child, v);
    }
}

function applyValueToNode(node, value) {
    if (node.node_type === "field") {
        if (value === null || value === undefined) {
            node.value = "";
        } else if (typeof value === "string") {
            node.value = value;
        } else {
            node.value = JSON.stringify(value);
        }
        return;
    }

    if (node.node_type === "group") {
        if (value && typeof value === "object" && !Array.isArray(value)) {
            applyPromptObjectToGroup(node, value);
        }
        return;
    }

    if (node.node_type === "array") {
        if (!Array.isArray(value)) return;
        node.items = [];
        for (const itemVal of value) {
            let itemNode;
            if (node.item_template) {
                itemNode = cloneWithFreshIds(node.item_template);
                applyValueToNode(itemNode, itemVal);
            } else {
                itemNode = makeNodeFromValue("item", itemVal);
            }
            node.items.push(itemNode);
        }
    }
}

function makeNodeFromValue(key, value) {
    if (Array.isArray(value)) {
        const arr = arrayNode(key, key, groupNode("item", "item", [], false), [], false);
        for (const item of value) arr.items.push(makeNodeFromValue("item", item));
        return arr;
    }
    if (value && typeof value === "object") {
        const g = groupNode(key, key, [], false);
        for (const [k, v] of Object.entries(value)) g.children.push(makeNodeFromValue(k, v));
        return g;
    }
    return fieldNode(key, key, null, value == null ? "" : String(value));
}

function hydrateStateFromTemplate(templateData) {
    if (templateData && typeof templateData === "object" && templateData.tree) {
        const tree = clone(templateData.tree);
        walkTree(tree, ({ node, parent }) => {
            if (!node.id) node.id = uid(node.node_type || "node");
            if ((node.node_type === "group" || node.node_type === "array") && node.expanded === undefined) {
                node.expanded = parent ? false : true;
            }
        });
        enrichPresetBindingsFromTree(tree);
        return {
            tree,
            lastDiagnostics: "No validation run yet.",
            forceApply: false,
            randomizerChecked: normalizeRandomizerChecked(templateData.randomizer_checked),
        };
    }
    return {
        tree: buildStarterTree(),
        lastDiagnostics: "No validation run yet.",
        forceApply: false,
        randomizerChecked: {},
    };
}

function hydrateStateFromPrompt(promptObj) {
    const state = {
        tree: buildStarterTree(),
        lastDiagnostics: "No validation run yet.",
        forceApply: false,
        randomizerChecked: {},
    };
    if (!promptObj || typeof promptObj !== "object" || Array.isArray(promptObj)) return state;
    if (!Object.keys(promptObj).length) return state;

    applyPromptObjectToGroup(state.tree, promptObj);
    reorderNodeFromPrompt(state.tree, promptObj);
    enrichPresetBindingsFromTree(state.tree);
    return state;
}

function renderAll() {
    renderTree();
    renderInspector();
    renderTemplateState();
    renderDiagnosticsPanel();
    renderRandomizerPanel();
}
async function saveTemplate() {
    const name = (templateNameEl.value || "").trim();
    if (!name) {
        setStatus("Enter a template name first.");
        return;
    }
    const payload = {
        tree: cloneTreeForTemplateSave(treeState.tree),
        randomizer_checked: Object.keys(treeState.randomizerChecked || {}).filter((k) => treeState.randomizerChecked[k]),
    };
    const r = await fetch("/fluxvisual/templates/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, data: payload }),
    });
    if (!r.ok) {
        setStatus("Failed to save template.");
        return;
    }
    templates[name] = payload;
    selectedTemplateName = name;
    loadedTemplateName = name;
    markTreeClean();
    renderTemplateList();
    renderTemplateState();
    setStatus(`Saved template '${name}'.`);
}

async function deleteTemplate() {
    const name = (templateNameEl.value || "").trim();
    if (!name) {
        setStatus("Enter a template name to delete.");
        return;
    }
    const r = await fetch("/fluxvisual/templates/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
    });
    if (!r.ok) {
        setStatus("Failed to delete template.");
        return;
    }
    delete templates[name];
    if (selectedTemplateName === name) selectedTemplateName = "";
    if (loadedTemplateName === name) loadedTemplateName = "";
    if ((templateNameEl.value || "").trim() === name) templateNameEl.value = "";
    renderTemplateList();
    renderTemplateState();
    setStatus(`Deleted template '${name}'.`);
}

function compiledPrompt() {
    const prompt = compileNode(treeState.tree);
    return prompt && typeof prompt === "object" ? prompt : {};
}

function formatDiagnostics(report) {
    const parts = [];
    const errors = report?.errors || [];
    const warnings = report?.warnings || [];

    parts.push(`errors: ${errors.length}`);
    for (const e of errors) {
        parts.push(`- [ERROR] ${e.code || "error"}${e.path ? ` @ ${e.path}` : ""}: ${e.message || ""}`);
    }

    parts.push(`warnings: ${warnings.length}`);
    for (const w of warnings) {
        parts.push(`- [WARN] ${w.code || "warning"}${w.path ? ` @ ${w.path}` : ""}: ${w.message || ""}`);
    }

    if (!errors.length && !warnings.length) {
        parts.push("Validation passed. No issues.");
    }

    return parts.join("\n");
}

async function validateAndApply() {
    const prompt = compiledPrompt();
    const v = await fetch("/fluxvisual/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(prompt),
    });

    if (!v.ok) {
        treeState.lastDiagnostics = "Validation API request failed.";
        renderDiagnosticsPanel();
        setStatus("Validation API failed.");
        return;
    }

    const report = await v.json();
    treeState.lastDiagnostics = formatDiagnostics(report);
    renderDiagnosticsPanel();

    const hasErrors = !report.ok;
    const force = !!treeState.forceApply;
    if (hasErrors && !force) {
        setStatus(`Validation failed (${(report.errors || []).length} errors). Enable Force Apply to write anyway.`);
        return;
    }

    const widget = findPromptWidget(currentNode);
    if (!widget) {
        setStatus("Node has no prompt_json widget.");
        return;
    }

    const text = JSON.stringify(prompt, null, 2);
    widget.value = text;
    if (typeof widget.callback === "function") widget.callback(text);
    app.graph.setDirtyCanvas(true);
    persistVisualState(promptSignatureFromObject(prompt));

    const warningCount = (report.warnings || []).length;
    if (hasErrors && force) {
        setStatus(`Force applied with ${(report.errors || []).length} errors and ${warningCount} warnings.`);
    } else {
        setStatus(warningCount ? `Applied with ${warningCount} warnings.` : "Applied successfully.");
    }

    closeBuilder();
}

function closeBuilder() {
    if (overlayEl) overlayEl.style.display = "none";
    currentNode = null;
    treeState = null;
    selectedNodeId = null;
    dragNodeId = null;
    selectedTemplateName = "";
    loadedTemplateName = "";
    baselineTreeSignature = "";
}

async function openBuilder(node) {
    ensureModal();
    currentNode = node;

    await loadPresets();
    await loadTemplates();

    selectedTemplateName = "";
    loadedTemplateName = "";
    templateNameEl.value = "";

    const widget = findPromptWidget(node);
    let parsed = null;
    if (widget?.value && String(widget.value).trim()) {
        try {
            parsed = JSON.parse(widget.value);
        } catch {
            parsed = null;
        }
    }

    const promptSig = promptSignatureFromObject(parsed);
    const saved = loadPersistedVisualState(node, promptSig);
    treeState = saved ? hydrateStateFromTemplate(saved) : hydrateStateFromPrompt(parsed);

    selectedNodeId = treeState.tree.id;
    markTreeClean();
    renderTemplateList();
    renderAll();

    overlayEl.style.display = "block";
    setStatus("Ready.");
}

function attachButton(node) {
    if (!node.widgets) return;
    if (node.widgets.some((w) => w.name === OPEN_BUTTON)) return;
    node.addWidget("button", OPEN_BUTTON, "", () => openBuilder(node));
}

app.registerExtension({
    name: "AFJ.VisualBuilder",

    async nodeCreated(node) {
        if (node.comfyClass !== TARGET_NODE) return;
        attachButton(node);
    },

    async loadedGraphNode(node) {
        if (node.comfyClass !== TARGET_NODE) return;
        attachButton(node);
    },
});
