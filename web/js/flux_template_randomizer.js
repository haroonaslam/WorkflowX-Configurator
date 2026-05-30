import { app } from "../../scripts/app.js";

const TARGET_NODE = "FluxTemplateRandomizer";
const OPEN_BUTTON = "Open Template Randomizer UI";

const RULES_HELP_TEXT = `AFJ Randomize Rules (one line per field):
path | mode | value

Examples:
scene.environment | preset | indoor photography studio, seamless backdrop
subjects[0].dress.top.color | preset | black; white; red
subjects[0].custom_tag | custom | alpha; beta; gamma

Notes:
- mode is visual only.
- if value equals template current value:
  - preset-backed fields randomize from preset options
  - custom-only fields remain unchanged
- if value differs, semicolon values are override candidates.
`;

let overlayEl = null;
let templateSelectEl = null;
let fieldListEl = null;
let staleListEl = null;
let summaryEl = null;
let statusEl = null;

let currentNode = null;
let templates = {};
let fieldItems = [];
let fieldByPath = new Map();
let staleRows = [];
let checkedPaths = new Set();
let rulesByPath = new Map();

function findWidget(node, name) {
    return node?.widgets?.find((w) => w.name === name) || null;
}

function readWidgetText(node, name) {
    const w = findWidget(node, name);
    return String(w?.value || "");
}

function setWidgetValue(node, name, value) {
    const w = findWidget(node, name);
    if (!w) return false;
    w.value = value;
    if (typeof w.callback === "function") w.callback(value);
    app.graph.setDirtyCanvas(true);
    return true;
}

function parseRulesLines(text) {
    const entries = [];
    const byPath = new Map();

    for (const raw of String(text || "").split(/\r?\n/)) {
        const line = raw.trim();
        if (!line) continue;

        const parts = line.split("|", 3);
        if (parts.length < 3) {
            entries.push({ raw: line, valid: false, path: "" });
            continue;
        }

        const path = String(parts[0] || "").trim();
        const mode = String(parts[1] || "").trim();
        const value = String(parts[2] || "").trim();

        if (!path) {
            entries.push({ raw: line, valid: false, path: "" });
            continue;
        }

        entries.push({ raw: line, valid: true, path, mode, value });
        byPath.set(path, line);
    }

    return { entries, byPath };
}

function collectNonEmptyFields(tree) {
    const out = [];

    function walk(node, path) {
        if (!node || typeof node !== "object") return;
        const t = node.node_type;

        if (t === "field") {
            const value = String(node.value || "");
            if (!value.trim()) return;
            const hasOptions = !!(
                (node.options && typeof node.options === "object" && Object.keys(node.options).length)
                || String(node.preset_path || "").trim()
                || String(node.origin_preset_path || "").trim()
            );
            out.push({ path, value, hasOptions });
            return;
        }

        if (t === "group") {
            for (const child of node.children || []) {
                const key = String(child?.key || "").trim();
                if (!key) continue;
                const next = path ? `${path}.${key}` : key;
                walk(child, next);
            }
            return;
        }

        if (t === "array") {
            const items = Array.isArray(node.items) ? node.items : [];
            for (let i = 0; i < items.length; i += 1) {
                const next = `${path}[${i}]`;
                walk(items[i], next);
            }
        }
    }

    if (tree?.node_type === "group") {
        for (const child of tree.children || []) {
            const key = String(child?.key || "").trim();
            if (!key) continue;
            walk(child, key);
        }
    }

    out.sort((a, b) => a.path.localeCompare(b.path));
    return out;
}

function setStatus(msg) {
    if (statusEl) statusEl.textContent = msg;
}

function rebuildStaleRows() {
    const valid = new Set(fieldItems.map((f) => f.path));
    const rows = [];

    for (const path of rulesByPath.keys()) {
        if (valid.has(path)) continue;
        rows.push({ path });
    }

    rows.sort((a, b) => a.path.localeCompare(b.path));
    staleRows = rows;
}

function renderSummary() {
    if (!summaryEl) return;
    const total = checkedPaths.size;
    const presetEligible = fieldItems.filter((f) => checkedPaths.has(f.path) && f.hasOptions).length;
    const staleCount = staleRows.filter((r) => checkedPaths.has(r.path)).length;
    summaryEl.textContent = `Selected: ${total} | Preset-eligible: ${presetEligible} | Stale selected: ${staleCount}`;
}

function renderFieldLists() {
    fieldListEl.innerHTML = "";
    staleListEl.innerHTML = "";

    if (!fieldItems.length) {
        const empty = document.createElement("div");
        empty.className = "ftr-empty";
        empty.textContent = "No non-empty fields found in this template.";
        fieldListEl.appendChild(empty);
    } else {
        for (const item of fieldItems) {
            const row = document.createElement("label");
            row.className = "ftr-row";

            const cb = document.createElement("input");
            cb.type = "checkbox";
            cb.checked = checkedPaths.has(item.path);
            cb.addEventListener("change", () => {
                if (cb.checked) checkedPaths.add(item.path);
                else checkedPaths.delete(item.path);
                renderSummary();
            });

            const body = document.createElement("div");
            body.className = "ftr-row-body";

            const top = document.createElement("div");
            top.className = "ftr-row-top";
            const pathEl = document.createElement("code");
            pathEl.textContent = item.path;
            const chip = document.createElement("span");
            chip.className = `ftr-chip ${item.hasOptions ? "" : "alt"}`;
            chip.textContent = item.hasOptions ? "preset-backed" : "custom-only";
            top.appendChild(pathEl);
            top.appendChild(chip);

            const val = document.createElement("div");
            val.className = "ftr-val";
            const compact = item.value.length > 140 ? `${item.value.slice(0, 140)}...` : item.value;
            val.textContent = compact;

            body.appendChild(top);
            body.appendChild(val);
            row.appendChild(cb);
            row.appendChild(body);
            fieldListEl.appendChild(row);
        }
    }

    if (!staleRows.length) {
        const ok = document.createElement("div");
        ok.className = "ftr-empty";
        ok.textContent = "No stale paths.";
        staleListEl.appendChild(ok);
    } else {
        for (const rowData of staleRows) {
            const row = document.createElement("label");
            row.className = "ftr-row stale";

            const cb = document.createElement("input");
            cb.type = "checkbox";
            cb.checked = checkedPaths.has(rowData.path);
            cb.addEventListener("change", () => {
                if (cb.checked) checkedPaths.add(rowData.path);
                else checkedPaths.delete(rowData.path);
                renderSummary();
            });

            const body = document.createElement("div");
            body.className = "ftr-row-body";

            const top = document.createElement("div");
            top.className = "ftr-row-top";
            const pathEl = document.createElement("code");
            pathEl.textContent = rowData.path;
            top.appendChild(pathEl);

            const note = document.createElement("div");
            note.className = "ftr-val";
            note.textContent = "Path not found in selected template. Kept and skipped at runtime if unresolved.";

            body.appendChild(top);
            body.appendChild(note);
            row.appendChild(cb);
            row.appendChild(body);
            staleListEl.appendChild(row);
        }
    }

    renderSummary();
}

function refreshTemplateSelect(selectedName = "") {
    templateSelectEl.innerHTML = "";

    const names = Object.keys(templates || {}).sort((a, b) => a.localeCompare(b));
    templateSelectEl.appendChild(new Option("-- select template --", ""));
    for (const name of names) templateSelectEl.appendChild(new Option(name, name));

    if (selectedName && templates[selectedName]) templateSelectEl.value = selectedName;
    else templateSelectEl.value = "";
}

async function fetchTemplates() {
    const r = await fetch("/fluxvisual/templates");
    if (!r.ok) throw new Error(`/fluxvisual/templates returned ${r.status}`);
    const data = await r.json();
    return data && typeof data === "object" ? data : {};
}

function loadTemplateFields(templateName) {
    const data = templates[templateName];
    const tree = data?.tree;

    fieldItems = collectNonEmptyFields(tree);
    fieldByPath = new Map(fieldItems.map((f) => [f.path, f]));

    rebuildStaleRows();
    renderFieldLists();

    if (!templateName) {
        setStatus("Select a template to load fields.");
        return;
    }

    if (!data || !tree) {
        setStatus(`Template '${templateName}' has no valid tree payload.`);
        return;
    }

    setStatus(`Loaded template '${templateName}'.`);
}

async function reloadTemplates(preserveSelection = true) {
    const currentSelection = preserveSelection ? String(templateSelectEl?.value || "") : "";
    const nodeTemplate = String(readWidgetText(currentNode, "template_name") || "").trim();

    templates = await fetchTemplates();
    const preferred = currentSelection && templates[currentSelection] ? currentSelection : nodeTemplate;
    refreshTemplateSelect(preferred);
}

function ensureModal() {
    if (overlayEl) return;

    const style = document.createElement("style");
    style.textContent = `
    .ftr-overlay { position: fixed; inset: 0; z-index: 10010; display: none; background: rgba(8, 10, 14, 0.82); color: #e7eef7; font-family: "Segoe UI", sans-serif; padding: 14px; box-sizing: border-box; }
    .ftr-modal { width: min(1320px, 100%); height: min(880px, 100%); margin: 0 auto; border: 1px solid #24405a; border-radius: 12px; overflow: hidden; background: linear-gradient(165deg, #0f151c, #101a25); display: grid; grid-template-rows: auto 1fr auto; }
    .ftr-head, .ftr-foot { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 14px; border-bottom: 1px solid #23384b; }
    .ftr-foot { border-bottom: 0; border-top: 1px solid #23384b; }
    .ftr-body { display: grid; grid-template-columns: 320px 1fr; min-height: 0; }
    .ftr-side { border-right: 1px solid #23384b; padding: 10px; display: grid; gap: 8px; align-content: start; }
    .ftr-main { padding: 10px; display: grid; grid-template-rows: 1fr 0.8fr; gap: 10px; min-height: 0; }
    .ftr-panel { border: 1px solid #2a4358; border-radius: 8px; background: rgba(12, 19, 27, 0.8); display: grid; grid-template-rows: auto 1fr; min-height: 0; }
    .ftr-panel-h { padding: 8px 10px; border-bottom: 1px solid #21374a; font-weight: 600; }
    .ftr-list { overflow: auto; padding: 8px; min-height: 0; }
    .ftr-row { border: 1px solid #29475e; border-radius: 8px; padding: 7px; margin-bottom: 6px; display: grid; grid-template-columns: auto 1fr; gap: 8px; align-items: start; background: rgba(14, 21, 31, 0.72); }
    .ftr-row.stale { border-color: #6c5734; background: rgba(54, 42, 26, 0.45); }
    .ftr-row-body { min-width: 0; display: grid; gap: 4px; }
    .ftr-row-top { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; min-width: 0; }
    .ftr-row-top code { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; display: inline-block; }
    .ftr-val { font-size: 12px; color: #b8cadb; line-height: 1.3; }
    .ftr-chip { background: #224663; border-radius: 999px; padding: 1px 8px; font-size: 11px; }
    .ftr-chip.alt { background: #5a3f28; }
    .ftr-empty { padding: 8px; font-size: 12px; color: #a7bbcf; }
    .ftr-title { font-size: 15px; font-weight: 700; }
    .ftr-sub { font-size: 12px; color: #9fb3c7; }
    .ftr-select { width: 100%; box-sizing: border-box; border-radius: 6px; border: 1px solid #35506b; background: #0f161f; color: #edf4fc; padding: 7px; }
    .ftr-btn { border: 1px solid #395a78; background: #1a2d3d; color: #fff; border-radius: 6px; padding: 7px 10px; cursor: pointer; }
    .ftr-btn.primary { background: #0f6ca8; border-color: #0f6ca8; }
    .ftr-btns { display: flex; flex-wrap: wrap; gap: 6px; }
    @media (max-width: 1180px) { .ftr-body { grid-template-columns: 1fr; } .ftr-side { border-right: 0; border-bottom: 1px solid #23384b; } }
    `;
    document.head.appendChild(style);

    overlayEl = document.createElement("div");
    overlayEl.className = "ftr-overlay";
    overlayEl.innerHTML = `
      <div class="ftr-modal">
        <div class="ftr-head">
          <div>
            <div class="ftr-title">Template Randomizer Config</div>
            <div class="ftr-sub">Select template and randomizable fields. Apply updates randomize_rules.</div>
          </div>
          <div class="ftr-chip">single rules mode</div>
        </div>
        <div class="ftr-body">
          <aside class="ftr-side">
            <label>Template</label>
            <select id="ftr-template" class="ftr-select"></select>
            <div class="ftr-btns">
              <button id="ftr-refresh" class="ftr-btn">Refresh Templates</button>
              <button id="ftr-load" class="ftr-btn">Load Fields</button>
            </div>
            <div id="ftr-summary" class="ftr-sub">Selected: 0 | Preset-eligible: 0 | Stale selected: 0</div>
            <div id="ftr-status" class="ftr-sub">Ready.</div>
            <div class="ftr-sub">Line format: path | mode | value (mode is visual cue only).</div>
          </aside>
          <section class="ftr-main">
            <div class="ftr-panel">
              <div class="ftr-panel-h">Available Non-Empty Fields</div>
              <div id="ftr-field-list" class="ftr-list"></div>
            </div>
            <div class="ftr-panel">
              <div class="ftr-panel-h">Missing Paths From Saved Rules</div>
              <div id="ftr-stale-list" class="ftr-list"></div>
            </div>
          </section>
        </div>
        <div class="ftr-foot">
          <div class="ftr-sub">Apply removes deselected lines, appends new lines, and preserves unchanged existing lines.</div>
          <div class="ftr-btns">
            <button id="ftr-close" class="ftr-btn">Close</button>
            <button id="ftr-apply" class="ftr-btn primary">Apply</button>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(overlayEl);

    templateSelectEl = overlayEl.querySelector("#ftr-template");
    fieldListEl = overlayEl.querySelector("#ftr-field-list");
    staleListEl = overlayEl.querySelector("#ftr-stale-list");
    summaryEl = overlayEl.querySelector("#ftr-summary");
    statusEl = overlayEl.querySelector("#ftr-status");

    overlayEl.querySelector("#ftr-close").addEventListener("click", closeModal);
    overlayEl.querySelector("#ftr-refresh").addEventListener("click", async () => {
        try {
            await reloadTemplates(true);
            setStatus("Templates refreshed.");
        } catch (err) {
            setStatus(`Failed to refresh templates: ${err.message || err}`);
        }
    });
    overlayEl.querySelector("#ftr-load").addEventListener("click", () => {
        loadTemplateFields(String(templateSelectEl.value || "").trim());
    });
    templateSelectEl.addEventListener("change", () => {
        loadTemplateFields(String(templateSelectEl.value || "").trim());
    });
    overlayEl.querySelector("#ftr-apply").addEventListener("click", applySelectionToNode);
}

function closeModal() {
    if (overlayEl) overlayEl.style.display = "none";
    currentNode = null;
    fieldItems = [];
    fieldByPath = new Map();
    staleRows = [];
    checkedPaths = new Set();
    rulesByPath = new Map();
}

function hydrateStateFromNode() {
    const parsed = parseRulesLines(readWidgetText(currentNode, "randomize_rules"));
    rulesByPath = parsed.byPath;
    checkedPaths = new Set([...rulesByPath.keys()]);
}

function orderedCheckedPaths() {
    const ordered = [];
    for (const f of fieldItems) {
        if (checkedPaths.has(f.path)) ordered.push(f.path);
    }
    for (const s of staleRows) {
        if (checkedPaths.has(s.path)) ordered.push(s.path);
    }
    return ordered;
}

function applySelectionToNode() {
    if (!currentNode) return;

    const templateName = String(templateSelectEl.value || "").trim();
    if (!templateName) {
        setStatus("Select a template first.");
        return;
    }

    const existing = parseRulesLines(readWidgetText(currentNode, "randomize_rules"));
    const outLines = [];
    const keptPaths = new Set();

    // Preserve all invalid lines untouched.
    for (const entry of existing.entries) {
        if (!entry.valid) {
            outLines.push(entry.raw);
            continue;
        }

        if (!checkedPaths.has(entry.path)) continue;
        if (keptPaths.has(entry.path)) continue;

        outLines.push(entry.raw);
        keptPaths.add(entry.path);
    }

    // Append newly selected paths not already represented.
    for (const path of orderedCheckedPaths()) {
        if (keptPaths.has(path)) continue;
        const field = fieldByPath.get(path);
        if (!field) continue;

        const mode = field.hasOptions ? "preset" : "custom";
        outLines.push(`${path} | ${mode} | ${field.value}`);
        keptPaths.add(path);
    }

    const rulesText = outLines.join("\n");

    const okTemplate = setWidgetValue(currentNode, "template_name", templateName);
    const okRules = setWidgetValue(currentNode, "randomize_rules", rulesText);

    if (!okTemplate || !okRules) {
        setStatus("Failed to write one or more node widgets.");
        return;
    }

    const parsed = parseRulesLines(rulesText);
    rulesByPath = parsed.byPath;
    checkedPaths = new Set([...rulesByPath.keys()]);
    rebuildStaleRows();
    renderFieldLists();

    setStatus(`Applied ${checkedPaths.size} rule path(s) to node widgets.`);
}

async function openModal(node) {
    ensureModal();
    currentNode = node;

    hydrateStateFromNode();

    try {
        await reloadTemplates(true);
    } catch (err) {
        setStatus(`Failed to load templates: ${err.message || err}`);
        overlayEl.style.display = "block";
        return;
    }

    const nodeTemplate = String(readWidgetText(node, "template_name") || "").trim();
    if (nodeTemplate && templates[nodeTemplate]) {
        templateSelectEl.value = nodeTemplate;
    }

    loadTemplateFields(String(templateSelectEl.value || "").trim());

    overlayEl.style.display = "block";
    setStatus("Ready.");
}

function isTargetNode(node) {
    if (!node) return false;
    if (node.comfyClass === TARGET_NODE) return true;
    if (node.type === TARGET_NODE) return true;
    const title = String(node.title || "");
    return title.toLowerCase().includes("template randomizer");
}

function attachButton(node) {
    if (!node.widgets) return;

    if (node.widgets.some((w) => w.name === OPEN_BUTTON)) return;

    const widget = node.addWidget("button", OPEN_BUTTON, "", () => openModal(node));

    // Keep button visible even on tall nodes by moving it to the top.
    if (widget && Array.isArray(node.widgets)) {
        const idx = node.widgets.indexOf(widget);
        if (idx > 0) {
            node.widgets.splice(idx, 1);
            node.widgets.unshift(widget);
        }
    }

    if (typeof node.computeSize === "function" && typeof node.setSize === "function") {
        try {
            const want = node.computeSize();
            if (Array.isArray(want) && want.length >= 2) {
                const cur = Array.isArray(node.size) ? node.size : [0, 0];
                node.setSize([Math.max(cur[0] || 0, want[0] || 0), Math.max(cur[1] || 0, want[1] || 0)]);
            }
        } catch {
            // Non-fatal: layout helpers differ across ComfyUI builds.
        }
    }
}

app.registerExtension({
    name: "AFJ.TemplateRandomizerUI",

    async nodeCreated(node) {
        if (!isTargetNode(node)) return;
        attachButton(node);
    },

    async loadedGraphNode(node) {
        if (!isTargetNode(node)) return;
        attachButton(node);
    },
});
