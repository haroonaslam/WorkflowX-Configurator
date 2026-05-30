import { app } from "../../scripts/app.js";

const TARGET_NODE = "AFJPromptTemplateImporter";
const OPEN_BUTTON = "Open Prompt Template Importer UI";

let overlayEl = null;
let templateNameEl = null;
let sourceJsonEl = null;
let reportEl = null;
let previewEl = null;
let statusEl = null;

let currentNode = null;
let currentPreviewPayload = null;

function isTargetNode(node) {
    if (!node) return false;
    if (node.comfyClass === TARGET_NODE) return true;
    if (node.type === TARGET_NODE) return true;
    const title = String(node.title || "").toLowerCase();
    return title.includes("prompt template importer");
}

function findWidget(node, name) {
    return node?.widgets?.find((w) => w.name === name) || null;
}

function readWidgetText(node, name) {
    return String(findWidget(node, name)?.value || "");
}

function setWidgetValue(node, name, value) {
    const w = findWidget(node, name);
    if (!w) return false;
    w.value = value;
    if (typeof w.callback === "function") w.callback(value);
    app.graph.setDirtyCanvas(true);
    return true;
}

function setStatus(msg) {
    if (statusEl) statusEl.textContent = msg;
}

async function fetchTemplates() {
    const r = await fetch("/fluxvisual/templates");
    if (!r.ok) throw new Error(`/fluxvisual/templates returned ${r.status}`);
    const data = await r.json();
    return data && typeof data === "object" ? data : {};
}

async function convertPromptToTemplate(sourcePromptJson) {
    const r = await fetch("/fluxvisual/import/convert", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_prompt_json: sourcePromptJson }),
    });
    if (!r.ok) throw new Error(`/fluxvisual/import/convert returned ${r.status}`);
    return r.json();
}

async function saveTemplate(templateName, payload) {
    const r = await fetch("/fluxvisual/templates/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: templateName, data: payload }),
    });
    const data = await r.json();
    if (!r.ok || !data?.ok) {
        throw new Error(data?.error || "Template save failed.");
    }
    return data;
}

function persistNodeWidgets() {
    if (!currentNode) return;
    setWidgetValue(currentNode, "template_name", String(templateNameEl.value || ""));
    setWidgetValue(currentNode, "source_prompt_json", String(sourceJsonEl.value || ""));
    setWidgetValue(currentNode, "import_report", String(reportEl.value || ""));
}

async function onConvertPreview() {
    if (!currentNode) return;

    const sourceText = String(sourceJsonEl.value || "").trim();
    if (!sourceText) {
        setStatus("Paste prompt JSON first.");
        return;
    }

    persistNodeWidgets();

    let result;
    try {
        result = await convertPromptToTemplate(sourceText);
    } catch (err) {
        currentPreviewPayload = null;
        setStatus(`Convert failed: ${err.message || err}`);
        return;
    }

    if (!result?.ok) {
        currentPreviewPayload = null;
        const failReport = String(result?.report || result?.error || "Conversion failed.");
        reportEl.value = failReport;
        previewEl.value = JSON.stringify(
            {
                error: String(result?.error || "Conversion failed."),
                warnings: result?.warnings || [],
            },
            null,
            2,
        );
        persistNodeWidgets();
        setStatus("Conversion failed. Check report.");
        return;
    }

    currentPreviewPayload = result.data || null;
    previewEl.value = JSON.stringify(currentPreviewPayload || {}, null, 2);

    const warnings = Array.isArray(result.warnings) ? result.warnings : [];
    const reportParts = [String(result.report || "Conversion completed.")];
    if (warnings.length) {
        reportParts.push("Warnings:");
        for (const w of warnings) reportParts.push(`- ${String(w)}`);
    }
    reportEl.value = reportParts.join("\n");
    persistNodeWidgets();
    setStatus("Converted and previewed successfully.");
}

async function onSaveTemplate() {
    if (!currentNode) return;

    const templateName = String(templateNameEl.value || "");
    if (!templateName.trim()) {
        setStatus("Template name is required.");
        return;
    }

    if (!currentPreviewPayload) {
        await onConvertPreview();
        if (!currentPreviewPayload) return;
    }

    let templates = {};
    try {
        templates = await fetchTemplates();
    } catch (err) {
        setStatus(`Could not check existing templates: ${err.message || err}`);
        return;
    }

    if (templates[templateName]) {
        const ok = window.confirm(`Template '${templateName}' already exists. Overwrite?`);
        if (!ok) {
            setStatus("Save canceled.");
            return;
        }
    }

    try {
        await saveTemplate(templateName, currentPreviewPayload);
    } catch (err) {
        setStatus(`Save failed: ${err.message || err}`);
        return;
    }

    persistNodeWidgets();
    setStatus(`Saved template '${templateName}'.`);
}

function closeModal() {
    if (overlayEl) overlayEl.style.display = "none";
    currentNode = null;
    currentPreviewPayload = null;
}

function ensureModal() {
    if (overlayEl) return;

    const style = document.createElement("style");
    style.textContent = `
    .afjimp-overlay { position: fixed; inset: 0; z-index: 10020; display: none; background: rgba(8, 10, 14, 0.82); color: #e7eef7; font-family: "Segoe UI", sans-serif; padding: 14px; box-sizing: border-box; }
    .afjimp-modal { width: min(1420px, 100%); height: min(900px, 100%); margin: 0 auto; border: 1px solid #24405a; border-radius: 12px; overflow: hidden; background: linear-gradient(165deg, #0f151c, #101a25); display: grid; grid-template-rows: auto auto 1fr auto; }
    .afjimp-head, .afjimp-foot { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 14px; border-bottom: 1px solid #23384b; }
    .afjimp-foot { border-bottom: 0; border-top: 1px solid #23384b; }
    .afjimp-tools { padding: 10px 14px; display: grid; grid-template-columns: minmax(260px, 420px) auto; gap: 10px; align-items: center; border-bottom: 1px solid #23384b; }
    .afjimp-body { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; padding: 10px; min-height: 0; }
    .afjimp-panel { border: 1px solid #2a4358; border-radius: 8px; background: rgba(12, 19, 27, 0.8); display: grid; grid-template-rows: auto 1fr; min-height: 0; }
    .afjimp-ph { padding: 8px 10px; border-bottom: 1px solid #21374a; font-weight: 600; }
    .afjimp-title { font-size: 15px; font-weight: 700; }
    .afjimp-sub { font-size: 12px; color: #9fb3c7; }
    .afjimp-input, .afjimp-text { width: 100%; box-sizing: border-box; border-radius: 6px; border: 1px solid #35506b; background: #0f161f; color: #edf4fc; padding: 7px; }
    .afjimp-text { resize: none; min-height: 0; }
    .afjimp-row { display: flex; gap: 6px; flex-wrap: wrap; }
    .afjimp-btn { border: 1px solid #395a78; background: #1a2d3d; color: #fff; border-radius: 6px; padding: 7px 10px; cursor: pointer; }
    .afjimp-btn.primary { background: #0f6ca8; border-color: #0f6ca8; }
    @media (max-width: 1180px) { .afjimp-body { grid-template-columns: 1fr; } .afjimp-tools { grid-template-columns: 1fr; } }
    `;
    document.head.appendChild(style);

    overlayEl = document.createElement("div");
    overlayEl.className = "afjimp-overlay";
    overlayEl.innerHTML = `
      <div class="afjimp-modal">
        <div class="afjimp-head">
          <div>
            <div class="afjimp-title">AFJ Prompt Template Importer</div>
            <div class="afjimp-sub">Paste final prompt JSON, convert to AFJ template, then save.</div>
          </div>
        </div>
        <div class="afjimp-tools">
          <input id="afjimp-template" class="afjimp-input" placeholder="template_name" />
          <div class="afjimp-row">
            <button id="afjimp-convert" class="afjimp-btn">Convert/Preview</button>
            <button id="afjimp-save" class="afjimp-btn primary">Save Template</button>
          </div>
        </div>
        <div class="afjimp-body">
          <section class="afjimp-panel">
            <div class="afjimp-ph">Source Prompt JSON (final prompt object only)</div>
            <textarea id="afjimp-source" class="afjimp-text"></textarea>
          </section>
          <section class="afjimp-panel">
            <div class="afjimp-ph">Converted Template Payload Preview</div>
            <textarea id="afjimp-preview" class="afjimp-text" readonly></textarea>
          </section>
          <section class="afjimp-panel" style="grid-column: 1 / -1;">
            <div class="afjimp-ph">Import Report</div>
            <textarea id="afjimp-report" class="afjimp-text"></textarea>
          </section>
        </div>
        <div class="afjimp-foot">
          <div id="afjimp-status" class="afjimp-sub">Ready.</div>
          <div class="afjimp-row">
            <button id="afjimp-close" class="afjimp-btn">Close</button>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(overlayEl);

    templateNameEl = overlayEl.querySelector("#afjimp-template");
    sourceJsonEl = overlayEl.querySelector("#afjimp-source");
    reportEl = overlayEl.querySelector("#afjimp-report");
    previewEl = overlayEl.querySelector("#afjimp-preview");
    statusEl = overlayEl.querySelector("#afjimp-status");

    overlayEl.querySelector("#afjimp-close").addEventListener("click", closeModal);
    overlayEl.querySelector("#afjimp-convert").addEventListener("click", onConvertPreview);
    overlayEl.querySelector("#afjimp-save").addEventListener("click", onSaveTemplate);
}

function openModal(node) {
    ensureModal();
    currentNode = node;
    currentPreviewPayload = null;

    templateNameEl.value = readWidgetText(node, "template_name");
    sourceJsonEl.value = readWidgetText(node, "source_prompt_json") || "{}";
    reportEl.value = readWidgetText(node, "import_report") || "";
    previewEl.value = "";

    overlayEl.style.display = "block";
    setStatus("Ready.");
}

function attachButton(node) {
    if (!node.widgets) return;
    if (node.widgets.some((w) => w.name === OPEN_BUTTON)) return;

    const widget = node.addWidget("button", OPEN_BUTTON, "", () => openModal(node));

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
            // Non-fatal across ComfyUI builds.
        }
    }
}

app.registerExtension({
    name: "AFJ.PromptTemplateImporterUI",

    async nodeCreated(node) {
        if (!isTargetNode(node)) return;
        attachButton(node);
    },

    async loadedGraphNode(node) {
        if (!isTargetNode(node)) return;
        attachButton(node);
    },
});
