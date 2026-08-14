import { app } from "../../scripts/app.js";

const TARGET_NODE = "LLMToJsonX";
const ROUTE = "/workflowx/jsonx";
const SETTINGS_KEY = "workflowx_jsonx_provider_settings";
const GEMINI_KEY = "workflowx_jsonx_gemini_api_key";
const OPENAI_KEY = "workflowx_jsonx_openai_api_key";
const DEFAULT_OPENAI_URL = "http://localhost:1234/v1";
const DEFAULT_OLLAMA_HOST = "http://localhost:11434";
const INSTRUCTION_OVERRIDE_KEYS = [
  "stage_one_instructions",
  "template_fill_instructions",
  "refinement_instructions",
  "natural_language_instructions",
];
const GEMINI_SAFETY_OPTIONS = [
  "BLOCK_DEFAULT",
  "BLOCK_NONE",
  "BLOCK_LOW_AND_ABOVE",
  "BLOCK_MEDIUM_AND_ABOVE",
  "BLOCK_ONLY_HIGH",
];
const GEMINI_SAFETY_FIELDS = [
  ["safety_harassment", "Harassment"],
  ["safety_hate_speech", "Hate speech"],
  ["safety_sexual", "Sexual"],
  ["safety_dangerous", "Dangerous"],
];

function chainCallback(object, name, callback) {
  const previous = object?.[name];
  object[name] = function chainedJsonXCallback(...args) {
    const result = typeof previous === "function" ? previous.apply(this, args) : undefined;
    callback.apply(this, args);
    return result;
  };
}

function widget(node, name) {
  return node.widgets?.find((item) => item.name === name) || null;
}

function widgetValue(node, name, fallback = "") {
  return widget(node, name)?.value ?? fallback;
}

function setWidgetValue(node, name, value) {
  const item = widget(node, name);
  if (!item) return;
  item.value = value;
  item.callback?.(value);
  app.graph?.setDirtyCanvas?.(true, true);
}

function hideWidget(node, name) {
  const item = widget(node, name);
  if (!item) return;
  item.hidden = true;
  item.computeSize = () => [0, -4];
  const index = node.inputs?.findIndex((input) => input.name === name);
  if (index >= 0) node.removeInput(index);
}

function loadSettings() {
  try {
    const parsed = JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function saveSettings(settings) {
  // These settings are serialized in hidden node widgets so copied workflows
  // retain their JsonX generation behavior. Provider/runtime settings and
  // instruction overrides remain browser-local.
  const browserSettings = { ...settings };
  delete browserSettings.generation_profile;
  delete browserSettings.template_use_presets;
  delete browserSettings.detail_level;
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(browserSettings));
}

function storedSecret(key) {
  return localStorage.getItem(key) || "";
}

function storeSecret(key, value) {
  const clean = String(value || "").trim();
  if (clean) localStorage.setItem(key, clean);
  else localStorage.removeItem(key);
}

function additionalModelPaths(value) {
  return String(value || "")
    .split(/[;\r\n]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeLocalReasoning(value) {
  const mode = String(value || "auto").toLowerCase();
  if (mode === "none") return "off";
  if (mode === "deepseek" || mode === "qwen3") return "auto";
  return ["auto", "on", "off"].includes(mode) ? mode : "auto";
}

function graphLink(graph, linkId) {
  if (linkId == null) return null;
  if (typeof graph?.links?.get === "function") return graph.links.get(linkId);
  return graph?.links?.[linkId] || null;
}

function resolveImageSource(node) {
  const input = node.inputs?.find((item) => item.name === "image");
  if (!input || input.link == null) return null;
  const link = graphLink(node.graph, input.link);
  const source = link ? node.graph?.getNodeById?.(link.origin_id) : null;
  if (!source) return null;
  if (source.imgs?.[0]?.src) return source.imgs[0].src;
  const imageWidget = source.widgets?.find((item) => item.name === "image");
  if (imageWidget?.value) {
    let filename = String(imageWidget.value);
    let subfolder = "";
    const slash = filename.lastIndexOf("/");
    if (slash >= 0) {
      subfolder = filename.slice(0, slash);
      filename = filename.slice(slash + 1);
    }
    return `/view?filename=${encodeURIComponent(filename)}&type=input&subfolder=${encodeURIComponent(subfolder)}`;
  }
  return null;
}

function imageSourceToDataUrl(source) {
  return new Promise((resolve) => {
    if (!source) return resolve("");
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => {
      try {
        const canvas = document.createElement("canvas");
        canvas.width = image.naturalWidth || image.width || 1;
        canvas.height = image.naturalHeight || image.height || 1;
        canvas.getContext("2d")?.drawImage(image, 0, 0);
        resolve(canvas.toDataURL("image/png"));
      } catch {
        resolve("");
      }
    };
    image.onerror = () => resolve("");
    image.src = source;
  });
}

function option(select, value, label = value) {
  const item = document.createElement("option");
  item.value = value;
  item.textContent = label;
  select.appendChild(item);
}

function normalizeModelOption(value) {
  const id = value?.value || value?.id || value?.name || value;
  return {
    value: String(id || ""),
    label: String(value?.label || value?.display_name || value?.name || id || ""),
  };
}

function makePicker(panel, labelText, storedValue, placeholder) {
  const label = document.createElement("label");
  label.textContent = labelText;
  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "jsonx-picker-trigger";
  trigger.setAttribute("aria-haspopup", "listbox");
  const menu = document.createElement("div");
  menu.className = "jsonx-picker-menu";
  menu.setAttribute("role", "listbox");
  document.body.appendChild(menu);
  label.appendChild(trigger);
  panel.appendChild(label);

  let current = String(storedValue || "");
  let emptyText = String(placeholder || "Choose a model");
  let options = [];
  let lastToggleAt = 0;
  const listeners = new Set();

  const updateTrigger = () => {
    const selected = options.find((item) => item.value === current);
    const display = selected?.label || current || emptyText;
    trigger.textContent = display;
    trigger.title = `Choose the ${labelText.toLowerCase()} used for generation${current ? `\nCurrent: ${display}` : ""}`;
    trigger.classList.toggle("placeholder", !current);
  };
  const close = () => {
    menu.classList.remove("jsonx-picker-open");
    trigger.setAttribute("aria-expanded", "false");
  };
  const position = () => {
    const rect = trigger.getBoundingClientRect();
    menu.style.left = `${Math.max(4, rect.left)}px`;
    menu.style.top = `${rect.bottom + 2}px`;
    menu.style.width = `${Math.max(180, rect.width)}px`;
  };
  const selectValue = (value) => {
    current = String(value || "");
    updateTrigger();
    close();
    for (const listener of listeners) listener({target: picker});
  };
  const renderMenu = () => {
    menu.replaceChildren();
    for (const item of options) {
      const choice = document.createElement("button");
      choice.type = "button";
      choice.className = "jsonx-picker-option";
      choice.textContent = item.label;
      choice.title = item.value;
      choice.setAttribute("role", "option");
      choice.setAttribute("aria-selected", String(item.value === current));
      choice.onclick = (event) => {
        event.stopPropagation();
        selectValue(item.value);
      };
      menu.appendChild(choice);
    }
    if (!options.length) {
      const empty = document.createElement("div");
      empty.className = "jsonx-picker-empty";
      empty.textContent = emptyText;
      menu.appendChild(empty);
    }
  };
  const open = () => {
    if (trigger.disabled) return;
    for (const other of document.querySelectorAll(".jsonx-picker-menu.jsonx-picker-open")) {
      if (other !== menu) other.classList.remove("jsonx-picker-open");
    }
    renderMenu();
    position();
    menu.classList.add("jsonx-picker-open");
    trigger.setAttribute("aria-expanded", "true");
  };

  const picker = {
    dataset: trigger.dataset,
    get value() { return current; },
    set value(value) { current = String(value || ""); updateTrigger(); },
    get disabled() { return trigger.disabled; },
    set disabled(value) { trigger.disabled = Boolean(value); },
    addEventListener(name, listener) { if (name === "change") listeners.add(listener); },
    setOptions(values, selected = current, nextPlaceholder = emptyText) {
      options = (values || []).map(normalizeModelOption).filter((item) => item.value);
      emptyText = String(nextPlaceholder || emptyText);
      const requested = String(selected || "");
      current = options.some((item) => item.value === requested)
        ? requested
        : options[0]?.value || "";
      trigger.disabled = !options.length;
      updateTrigger();
      renderMenu();
    },
    destroy() {
      close();
      menu.remove();
    },
  };

  trigger.onclick = (event) => {
    event.stopPropagation();
    const now = performance.now();
    if (now - lastToggleAt < 250) return;
    lastToggleAt = now;
    if (menu.classList.contains("jsonx-picker-open")) close();
    else open();
  };
  trigger.onkeydown = (event) => {
    if (event.key === "Escape") close();
  };
  updateTrigger();
  return picker;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(`Invalid JSON response (HTTP ${response.status})`);
  }
  if (!response.ok || data.error) {
    const error = new Error(data.error || `HTTP ${response.status}`);
    error.data = data;
    throw error;
  }
  return data;
}

function setupLLMToJsonX(node) {
  if (node.__jsonXLLMReady) return;
  node.__jsonXLLMReady = true;
  hideWidget(node, "generated_prompt_json");
  hideWidget(node, "ui_state");
  hideWidget(node, "enable_framing_and_placement");
  hideWidget(node, "output_format");
  hideWidget(node, "generation_profile");
  hideWidget(node, "template_use_presets");
  hideWidget(node, "detail_level");
  const instructionsWidget = widget(node, "user_instructions");
  if (instructionsWidget) instructionsWidget.computeSize = () => [0, 82];

  if (!document.getElementById("workflowx-jsonx-llm-style")) {
    const style = document.createElement("style");
    style.id = "workflowx-jsonx-llm-style";
    style.textContent = `
    .jsonx-llm{font:11px "Segoe UI",sans-serif;color:#e8eef7;background:#111923;border:1px solid #2b4258;border-radius:7px;padding:6px;display:grid;gap:5px;align-content:start;overflow:hidden}
    .jsonx-llm *{box-sizing:border-box}.jsonx-llm-row{display:grid;grid-template-columns:minmax(0,1fr) 96px;gap:5px}
    .jsonx-llm label{display:grid;gap:2px;color:#adc0d3;min-width:0}.jsonx-llm input,.jsonx-llm select{width:100%;height:26px;min-height:26px;background:#0b1219;color:#edf4fb;border:1px solid #35516b;border-radius:4px;padding:2px 7px;font:inherit;color-scheme:dark}
    .jsonx-llm select:disabled{opacity:.72}.jsonx-llm button{height:27px;min-height:27px;background:#1b3349;color:#edf6ff;border:1px solid #3b6485;border-radius:4px;padding:2px 9px;font:inherit;cursor:pointer;white-space:nowrap}.jsonx-llm button.primary{background:#176a86;border-color:#35a6c4;font-weight:700}
    .jsonx-llm button:disabled{opacity:.55;cursor:wait}.jsonx-llm-status{min-height:27px;max-height:48px;overflow:auto;padding:5px 7px;border-radius:4px;background:#0c141c;color:#9fc1d8;white-space:pre-wrap;line-height:16px}.jsonx-llm-status.error{color:#ffadad;border:1px solid #713b45}
    .jsonx-llm-panel{display:none;gap:5px}.jsonx-llm-panel.active{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.jsonx-llm-panel>button{grid-column:1/-1;width:max-content;max-width:100%}.jsonx-local-tools{grid-column:1/-1;display:flex;align-items:center;gap:9px;flex-wrap:wrap}
    .jsonx-llm-actions{display:grid;grid-template-columns:minmax(0,1fr) minmax(132px,auto);grid-template-rows:auto auto;gap:5px;align-items:stretch}.jsonx-llm-actions .jsonx-llm-status{grid-row:1/span 2}.jsonx-llm-actions .primary{min-width:132px;width:100%}.jsonx-llm-secondary{display:grid;grid-template-columns:1fr;gap:5px}.jsonx-llm-secondary.generating{grid-template-columns:1fr 1fr}.jsonx-llm-actions .cancel{display:none;background:#552630;border-color:#9a4b59}.jsonx-llm-actions .cancel.visible{display:block}
    .jsonx-check{display:flex!important;grid-auto-flow:column!important;grid-template-columns:auto 1fr!important;align-items:center;gap:5px!important;white-space:nowrap;color:#adc0d3}.jsonx-check input{width:14px!important;height:14px!important;min-height:14px!important;margin:0}
    .jsonx-output-preview{display:grid;gap:2px;color:#adc0d3}.jsonx-output-preview textarea{width:100%;height:88px;min-height:88px;resize:vertical;background:#091119;color:#d8e9f6;border:1px solid #35516b;border-radius:4px;padding:6px 7px;font:10px/14px Consolas,"Cascadia Mono",monospace;white-space:pre;overflow:auto;color-scheme:dark}.jsonx-output-preview textarea:placeholder-shown{color:#7890a3}
    .jsonx-diagnostics{display:none;border:1px solid #713b45;border-radius:4px;padding:4px 6px;background:#180f14}.jsonx-diagnostics.visible{display:block}.jsonx-diagnostics summary{cursor:pointer;color:#ffb9b9}.jsonx-diagnostics textarea{width:100%;height:120px;margin-top:5px;resize:vertical;background:#090d12;color:#ffd2d2;border:1px solid #713b45;border-radius:4px;padding:6px;font:10px/14px Consolas,"Cascadia Mono",monospace;white-space:pre;overflow:auto}
    .jsonx-local-settings{grid-column:1/-1;border:1px solid #2b4258;border-radius:4px;padding:4px 6px;background:#0d161f}.jsonx-local-settings summary{cursor:pointer;color:#adc0d3;user-select:none}.jsonx-local-settings[open] summary{margin-bottom:5px}.jsonx-local-settings-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}
    .jsonx-llm .jsonx-picker-trigger{width:100%;text-align:left;overflow:hidden;text-overflow:ellipsis;padding-right:22px;position:relative;background:#0b1219}.jsonx-llm .jsonx-picker-trigger:after{content:"▾";position:absolute;right:7px;color:#9fc1d8}.jsonx-llm .jsonx-picker-trigger.placeholder{color:#7890a3}
    .jsonx-picker-menu{display:none;position:fixed;z-index:100000;max-height:220px;overflow:auto;padding:4px;background:#0b1219;border:1px solid #3b6485;border-radius:5px;box-shadow:0 8px 24px #000a;font:11px "Segoe UI",sans-serif}.jsonx-picker-menu.jsonx-picker-open{display:grid;gap:2px}.jsonx-picker-option{min-height:27px;height:auto;padding:5px 7px;text-align:left;white-space:normal;overflow-wrap:anywhere;color:#edf4fb;background:#111d28;border:1px solid transparent;border-radius:3px;cursor:pointer}.jsonx-picker-option:hover,.jsonx-picker-option[aria-selected="true"]{background:#1b4058;border-color:#3b7192}.jsonx-picker-empty{padding:7px;color:#7890a3}
    .jsonx-instruction-overlay{display:none;position:fixed;inset:0;z-index:100200;background:#000b;align-items:center;justify-content:center;padding:24px}.jsonx-instruction-overlay.visible{display:flex}.jsonx-instruction-modal{width:min(1040px,96vw);max-height:92vh;overflow:auto;background:#101923;color:#e9f2fa;border:1px solid #426783;border-radius:8px;box-shadow:0 18px 60px #000;padding:12px;font:12px "Segoe UI",sans-serif}.jsonx-instruction-head,.jsonx-instruction-buttons{display:flex;align-items:center;gap:8px}.jsonx-instruction-head{justify-content:space-between;margin-bottom:9px}.jsonx-instruction-head h2{font-size:16px;margin:0}.jsonx-instruction-modal button{height:29px;background:#1b3349;color:#edf6ff;border:1px solid #3b6485;border-radius:4px;padding:3px 10px;cursor:pointer}.jsonx-instruction-modal button.primary{background:#176a86;border-color:#35a6c4;font-weight:700}.jsonx-instruction-modal label{display:grid;gap:4px;color:#b7cadb;margin:7px 0}.jsonx-instruction-modal select{height:29px;background:#091119;color:#edf4fb;border:1px solid #35516b;border-radius:4px;padding:3px 7px}.jsonx-instruction-modal textarea{width:100%;height:210px;resize:vertical;background:#081018;color:#dcebf7;border:1px solid #35516b;border-radius:4px;padding:8px;font:11px/15px Consolas,"Cascadia Mono",monospace;white-space:pre;overflow:auto}.jsonx-instruction-modal .jsonx-effective textarea{height:170px}.jsonx-instruction-note{color:#8fa9bc;line-height:17px}.jsonx-instruction-meta{color:#8fc6df;margin:7px 0}.jsonx-instruction-buttons{justify-content:flex-end;flex-wrap:wrap;margin-top:9px}.jsonx-instruction-modal details{border:1px solid #2b4258;border-radius:5px;padding:6px;margin-top:9px}.jsonx-instruction-modal summary{cursor:pointer;color:#acd1e5}
    `;
    document.head.appendChild(style);
  }

  const savedSettings = loadSettings();
  const settings = {
    backend: "gemini",
    gemini_model: "",
    gemini_timeout: Number(savedSettings.timeout || 120),
    safety_harassment: "BLOCK_NONE",
    safety_hate_speech: "BLOCK_NONE",
    safety_sexual: "BLOCK_NONE",
    safety_dangerous: "BLOCK_NONE",
    openai_base_url: DEFAULT_OPENAI_URL,
    openai_model: "",
    openai_timeout: Number(savedSettings.timeout || 120),
    ollama_host: DEFAULT_OLLAMA_HOST,
    ollama_model: "",
    ollama_timeout: Number(savedSettings.timeout || 600),
    ollama_think: false,
    local_model: "",
    local_mmproj: "none",
    local_additional_model_paths: "",
    local_timeout: Number(savedSettings.timeout || 180),
    local_max_tokens: 8192,
    local_temperature: 0.7,
    local_top_p: 0.9,
    local_top_k: 40,
    local_repeat_penalty: 1.05,
    local_ctx_size: 32768,
    local_memory_mode: "auto",
    local_n_gpu_layers: 99,
    local_n_cpu_moe_layers: 0,
    local_reasoning: "off",
    local_speculative_mode: "auto",
    local_mtp_draft_tokens: 2,
    local_seed: -1,
    timeout: 180,
    unload_after: true,
    refresh_vram: false,
    generation_profile: "adaptive",
    template_use_presets: false,
    detail_level: "deep",
    stage_one_instructions: "",
    template_fill_instructions: "",
    refinement_instructions: "",
    natural_language_instructions: "",
    ...savedSettings,
  };
  delete settings["output_format"];
  delete settings["enable_framing_and_placement"];
  settings.generation_profile = String(widgetValue(node, "generation_profile", "adaptive")) || "adaptive";
  settings.template_use_presets = Boolean(widgetValue(node, "template_use_presets", false));
  settings.detail_level = String(widgetValue(node, "detail_level", "deep")) || "deep";
  settings.local_reasoning = normalizeLocalReasoning(settings.local_reasoning);

  const root = document.createElement("div");
  root.className = "jsonx-llm";
  root.addEventListener("pointerdown", (event) => event.stopPropagation());
  root.addEventListener("wheel", (event) => event.stopPropagation());

  const backendRow = document.createElement("div");
  backendRow.className = "jsonx-llm-row";
  const backendLabel = document.createElement("label");
  backendLabel.textContent = "LLM backend";
  const backend = document.createElement("select");
  for (const value of ["gemini", "openai", "ollama", "local"]) option(backend, value, value === "openai" ? "OpenAI compatible" : value === "local" ? "Local GGUF" : value[0].toUpperCase() + value.slice(1));
  backend.value = settings.backend;
  backend.title = "Choose the provider used for JsonX generation";
  backendLabel.appendChild(backend);
  const timeoutLabel = document.createElement("label");
  timeoutLabel.textContent = "Timeout seconds";
  const timeout = document.createElement("input");
  timeout.type = "number";
  timeout.min = "5";
  timeout.max = "3600";
  timeout.title = "Maximum seconds to wait for the selected provider";
  let activeBackend = settings.backend;
  timeout.value = settings[`${activeBackend}_timeout`] || settings.timeout || 180;
  timeoutLabel.appendChild(timeout);
  backendRow.append(backendLabel, timeoutLabel);
  root.appendChild(backendRow);

  const makePanel = () => {
    const panel = document.createElement("div");
    panel.className = "jsonx-llm-panel";
    root.appendChild(panel);
    return panel;
  };
  const makeInput = (panel, labelText, type = "text") => {
    const label = document.createElement("label");
    label.textContent = labelText;
    const input = document.createElement("input");
    input.type = type;
    label.appendChild(input);
    panel.appendChild(label);
    return input;
  };
  const makeRefresh = (panel, text) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = text;
    button.title = `${text} from the configured provider or local model folders`;
    panel.appendChild(button);
    return button;
  };
  const makeNumberInput = (panel, labelText, value, min, max, step = "1") => {
    const input = makeInput(panel, labelText, "number");
    input.value = String(value);
    input.min = String(min);
    input.max = String(max);
    input.step = String(step);
    return input;
  };
  const makeSelect = (panel, labelText, values, selected) => {
    const label = document.createElement("label");
    label.textContent = labelText;
    const select = document.createElement("select");
    for (const value of values) {
      if (typeof value === "string") option(select, value, value);
      else option(select, value.value, value.label);
    }
    select.value = selected;
    label.appendChild(select);
    panel.appendChild(label);
    return select;
  };
  const makeCheckbox = (panel, labelText, checked) => {
    const label = document.createElement("label");
    label.className = "jsonx-check";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = Boolean(checked);
    label.append(input, document.createTextNode(labelText));
    panel.appendChild(label);
    return input;
  };
  const numericValue = (input, fallback) => {
    const value = Number(input.value);
    return Number.isFinite(value) ? value : fallback;
  };

  const geminiPanel = makePanel();
  const geminiKey = makeInput(geminiPanel, "Gemini API key", "password");
  geminiKey.value = storedSecret(GEMINI_KEY);
  geminiKey.title = "Stored in this browser only; never written into the workflow";
  const geminiModel = makePicker(geminiPanel, "Gemini model", settings.gemini_model, "Fetch Gemini models");
  const geminiRefresh = makeRefresh(geminiPanel, "Fetch Gemini models");
  const geminiSettings = document.createElement("details");
  geminiSettings.className = "jsonx-local-settings";
  const geminiSettingsSummary = document.createElement("summary");
  geminiSettingsSummary.textContent = "Gemini safety settings";
  geminiSettingsSummary.title = "Show or hide Gemini content-safety thresholds";
  const geminiSettingsGrid = document.createElement("div");
  geminiSettingsGrid.className = "jsonx-local-settings-grid";
  geminiSettings.append(geminiSettingsSummary, geminiSettingsGrid);
  geminiPanel.appendChild(geminiSettings);
  const geminiSafetySelects = {};
  for (const [key, label] of GEMINI_SAFETY_FIELDS) {
    geminiSafetySelects[key] = makeSelect(
      geminiSettingsGrid,
      `Safety: ${label}`,
      GEMINI_SAFETY_OPTIONS,
      settings[key] || "BLOCK_NONE",
    );
  }

  const openaiPanel = makePanel();
  const openaiUrl = makeInput(openaiPanel, "OpenAI-compatible base URL");
  openaiUrl.value = settings.openai_base_url;
  openaiUrl.title = "Server root exposing OpenAI-compatible model and chat-completions endpoints";
  const openaiKey = makeInput(openaiPanel, "API key (optional)", "password");
  openaiKey.value = storedSecret(OPENAI_KEY);
  openaiKey.title = "Optional for local servers; stored in this browser only";
  const openaiManualModel = makeInput(openaiPanel, "Manual model ID (optional)");
  openaiManualModel.title = "Overrides the fetched model selection when populated";
  const openaiModel = makePicker(openaiPanel, "Fetched model", settings.openai_model, "Fetch compatible models");
  const openaiRefresh = makeRefresh(openaiPanel, "Fetch compatible models");
  const openaiUnload = makeCheckbox(openaiPanel, "Unload after generation", settings.unload_after);
  openaiUnload.parentElement.title = "Best-effort unload after a successful OpenAI-compatible generation";

  const ollamaPanel = makePanel();
  const ollamaHost = makeInput(ollamaPanel, "Ollama host");
  ollamaHost.value = settings.ollama_host;
  ollamaHost.title = "Base URL of the Ollama server";
  const ollamaModel = makePicker(ollamaPanel, "Ollama model", settings.ollama_model, "Fetch Ollama models");
  const ollamaRefresh = makeRefresh(ollamaPanel, "Fetch Ollama models");
  const ollamaThink = makeCheckbox(ollamaPanel, "Enable think mode", settings.ollama_think);
  const ollamaUnload = makeCheckbox(ollamaPanel, "Unload after generation", settings.unload_after);
  ollamaThink.parentElement.title = "Ask compatible Ollama models to use their thinking mode";
  ollamaUnload.parentElement.title = "Send keep_alive: 0 so Ollama unloads the model after generation";

  const localPanel = makePanel();
  const localModel = makePicker(localPanel, "Local GGUF model", settings.local_model, "Refresh to load GGUF models");
  const mmproj = makePicker(localPanel, "Vision mmproj", settings.local_mmproj || "none", "No vision projector");
  const localSettings = document.createElement("details");
  localSettings.className = "jsonx-local-settings";
  const localSettingsSummary = document.createElement("summary");
  localSettingsSummary.textContent = "Local generation settings";
  localSettingsSummary.title = "Show or hide llama.cpp context, sampling, memory, and speculative-decoding options";
  const localSettingsGrid = document.createElement("div");
  localSettingsGrid.className = "jsonx-local-settings-grid";
  localSettings.append(localSettingsSummary, localSettingsGrid);
  localPanel.appendChild(localSettings);
  const localContext = makeNumberInput(localSettingsGrid, "Context tokens", settings.local_ctx_size, 512, 262144);
  const localAdditionalPaths = makeInput(localSettingsGrid, "Additional model folders (; separated)");
  localAdditionalPaths.value = settings.local_additional_model_paths || "";
  localAdditionalPaths.placeholder = "D:\\LM Studio\\models; E:\\Shared GGUF";
  localAdditionalPaths.title = "Optional folders scanned recursively in addition to ComfyUI/models/LLM";
  const localMaxTokens = makeNumberInput(localSettingsGrid, "Max output tokens", settings.local_max_tokens, 32, 8192);
  const localTemperature = makeNumberInput(localSettingsGrid, "Temperature", settings.local_temperature, 0, 2, "0.05");
  const localTopP = makeNumberInput(localSettingsGrid, "Top P", settings.local_top_p, 0, 1, "0.05");
  const localTopK = makeNumberInput(localSettingsGrid, "Top K", settings.local_top_k, 0, 10000);
  const localRepeatPenalty = makeNumberInput(localSettingsGrid, "Repeat penalty", settings.local_repeat_penalty, 0, 5, "0.05");
  const localMemoryMode = makeSelect(localSettingsGrid, "Memory mode", [
    {value:"auto", label:"Auto memory"},
    {value:"gpu_layers", label:"GPU layers"},
    {value:"cpu_moe_layers", label:"CPU MoE layers"},
    {value:"gpu_and_cpu_moe_layers", label:"GPU + CPU MoE"},
  ], settings.local_memory_mode);
  const localReasoning = makeSelect(localSettingsGrid, "Reasoning", [
    {value:"auto", label:"Auto (model template)"},
    {value:"on", label:"On"},
    {value:"off", label:"Off"},
  ], settings.local_reasoning);
  const localSpeculativeMode = makeSelect(localSettingsGrid, "Speculative decoding", [
    {value:"auto", label:"Auto (detect embedded MTP)"},
    {value:"off", label:"Off"},
    {value:"mtp", label:"MTP"},
  ], settings.local_speculative_mode);
  const localMtpDraftTokens = makeNumberInput(localSettingsGrid, "MTP draft tokens", settings.local_mtp_draft_tokens, 1, 8);
  const localGpuLayers = makeNumberInput(localSettingsGrid, "GPU layers", settings.local_n_gpu_layers, 0, 999);
  const localCpuMoeLayers = makeNumberInput(localSettingsGrid, "CPU MoE layers", settings.local_n_cpu_moe_layers, 0, 999);
  const localSeed = makeNumberInput(localSettingsGrid, "Seed (-1 random)", settings.local_seed, -1, 4294967295);
  const status = document.createElement("div");
  status.className = "jsonx-llm-status";
  status.textContent = "Ready — Generate saves the validated JSON to prompt_json.";
  const generate = document.createElement("button");
  generate.type = "button";
  generate.className = "primary";
  generate.textContent = "Generate";
  generate.title = "Generate and save validated JsonX or natural-language output";
  const cancelGenerate = document.createElement("button");
  cancelGenerate.type = "button";
  cancelGenerate.className = "cancel";
  cancelGenerate.textContent = "Cancel";
  cancelGenerate.title = "Stop the active JsonX generation and keep the previous output";
  const instructionSettings = document.createElement("button");
  instructionSettings.type = "button";
  instructionSettings.textContent = "Settings";
  instructionSettings.title = "Review and customize JsonX backend instructions";
  const refreshVramLabel = document.createElement("label");
  refreshVramLabel.className = "jsonx-check";
  const refreshVram = document.createElement("input");
  refreshVram.type = "checkbox";
  refreshVram.checked = Boolean(settings.refresh_vram);
  refreshVramLabel.append(refreshVram, document.createTextNode("Refresh VRAM"));
  refreshVramLabel.title = "Unload ComfyUI models and clear cache before local JsonX generation";
  const localTools = document.createElement("div");
  localTools.className = "jsonx-local-tools";
  const localRefresh = makeRefresh(localTools, "Refresh models");
  localTools.appendChild(refreshVramLabel);
  localPanel.appendChild(localTools);
  const secondaryActions = document.createElement("div");
  secondaryActions.className = "jsonx-llm-secondary";
  secondaryActions.append(instructionSettings, cancelGenerate);
  const actions = document.createElement("div");
  actions.className = "jsonx-llm-actions";
  actions.append(status, generate, secondaryActions);
  root.append(actions);

  const outputPreviewLabel = document.createElement("label");
  outputPreviewLabel.className = "jsonx-output-preview";
  const outputPreviewTitle = document.createElement("span");
  const outputPreview = document.createElement("textarea");
  outputPreview.readOnly = true;
  outputPreview.spellcheck = false;
  outputPreview.placeholder = "Generated JSON will appear here.";
  outputPreview.value = String(widgetValue(node, "generated_prompt_json", "") || "");
  outputPreviewLabel.append(outputPreviewTitle, outputPreview);
  root.appendChild(outputPreviewLabel);

  const diagnostics = document.createElement("details");
  diagnostics.className = "jsonx-diagnostics";
  const diagnosticsSummary = document.createElement("summary");
  diagnosticsSummary.textContent = "Generation diagnostics";
  diagnosticsSummary.title = "Show provider responses and validation or repair details from the last failure";
  const diagnosticsOutput = document.createElement("textarea");
  diagnosticsOutput.readOnly = true;
  diagnosticsOutput.spellcheck = false;
  diagnostics.append(diagnosticsSummary, diagnosticsOutput);
  root.appendChild(diagnostics);

  const instructionOverlay = document.createElement("div");
  instructionOverlay.className = "jsonx-instruction-overlay";
  const instructionModal = document.createElement("div");
  instructionModal.className = "jsonx-instruction-modal";
  instructionModal.addEventListener("pointerdown", (event) => event.stopPropagation());
  const instructionHead = document.createElement("div");
  instructionHead.className = "jsonx-instruction-head";
  const instructionTitle = document.createElement("h2");
  instructionTitle.textContent = "JsonX Backend Instructions";
  const instructionClose = document.createElement("button");
  instructionClose.type = "button";
  instructionClose.textContent = "Close";
  instructionClose.title = "Close without saving settings changes";
  instructionHead.append(instructionTitle, instructionClose);
  const instructionNote = document.createElement("div");
  instructionNote.className = "jsonx-instruction-note";
  instructionNote.textContent = "Adaptive keeps the current open-world generation behavior. Template Fill supplies the complete blank hierarchy; Use Presets additionally sends the full presets.json verbatim. Natural language always runs validated JSON Stage 1 followed by preset-agnostic prose refinement. Provider and instruction settings stay browser-local. Output format and framing & placement are saved on this node and travel with the workflow.";
  const generationProfileLabel = document.createElement("label");
  generationProfileLabel.textContent = "Generation profile";
  const generationProfile = document.createElement("select");
  option(generationProfile, "adaptive", "Adaptive (current behavior)");
  option(generationProfile, "template_fill", "Template Fill (maximum structure compliance)");
  generationProfile.value = settings.generation_profile || "adaptive";
  generationProfile.title = "Adaptive expands relevant branches; Template Fill starts from the complete blank hierarchy";
  generationProfileLabel.appendChild(generationProfile);
  const outputFormatLabel = document.createElement("label");
  outputFormatLabel.textContent = "Output format";
  const outputFormat = document.createElement("select");
  option(outputFormat, "json", "JsonX JSON");
  option(outputFormat, "natural", "Natural language (validated JSON → refined prose)");
  outputFormat.value = String(widgetValue(node, "output_format", "json"));
  outputFormat.title = "Choose validated JsonX JSON or the two-pass natural-language result saved by this node";
  outputFormatLabel.appendChild(outputFormat);
  const templateUsePresetsLabel = document.createElement("label");
  templateUsePresetsLabel.className = "jsonx-check";
  const templateUsePresets = document.createElement("input");
  templateUsePresets.type = "checkbox";
  templateUsePresets.checked = Boolean(settings.template_use_presets);
  templateUsePresetsLabel.append(templateUsePresets, document.createTextNode("Use Presets (send full presets.json in Template Fill)"));
  templateUsePresetsLabel.title = "Include the full preset catalog during Template Fill; this uses substantially more context";
  const framingPlacementLabel = document.createElement("label");
  framingPlacementLabel.className = "jsonx-check";
  const framingPlacement = document.createElement("input");
  framingPlacement.type = "checkbox";
  framingPlacement.checked = Boolean(widgetValue(node, "enable_framing_and_placement", false));
  framingPlacementLabel.append(
    framingPlacement,
    document.createTextNode("Framing & placement (3×3 rule-of-thirds map)"),
  );
  framingPlacementLabel.title = "Add named 3×3 framing regions to the generation contract";
  const detailLevelLabel = document.createElement("label");
  detailLevelLabel.textContent = "Hierarchy coverage";
  const detailLevel = document.createElement("select");
  option(detailLevel, "deep", "Deep (maximize relevant hierarchy)");
  option(detailLevel, "exhaustive", "Exhaustive (maximum relevant branch coverage)");
  detailLevel.value = settings.detail_level || "deep";
  detailLevel.title = "Control how broadly JsonX fills relevant hierarchy branches";
  detailLevelLabel.appendChild(detailLevel);
  const stageOneLabel = document.createElement("label");
  stageOneLabel.textContent = "Adaptive Stage 1 system instructions";
  const stageOneInstructions = document.createElement("textarea");
  stageOneInstructions.spellcheck = false;
  stageOneLabel.appendChild(stageOneInstructions);
  const templateFillLabel = document.createElement("label");
  templateFillLabel.textContent = "Template Fill Stage 1 system instructions";
  const templateFillInstructions = document.createElement("textarea");
  templateFillInstructions.spellcheck = false;
  templateFillLabel.appendChild(templateFillInstructions);
  const refinementLabel = document.createElement("label");
  refinementLabel.textContent = "Refined Stage 2 system instructions";
  const refinementInstructions = document.createElement("textarea");
  refinementInstructions.spellcheck = false;
  refinementLabel.appendChild(refinementInstructions);
  const naturalLanguageLabel = document.createElement("label");
  naturalLanguageLabel.textContent = "Natural Language Stage 2 system instructions";
  const naturalLanguageInstructions = document.createElement("textarea");
  naturalLanguageInstructions.spellcheck = false;
  naturalLanguageLabel.appendChild(naturalLanguageInstructions);
  const effectiveDetails = document.createElement("details");
  effectiveDetails.className = "jsonx-effective";
  const effectiveSummary = document.createElement("summary");
  effectiveSummary.textContent = "Effective instructions preview";
  effectiveSummary.title = "Inspect the exact Stage 1 and Stage 2 system prompts that will be sent";
  const instructionMeta = document.createElement("div");
  instructionMeta.className = "jsonx-instruction-meta";
  const effectiveStageLabel = document.createElement("label");
  effectiveStageLabel.textContent = "Exact Stage 1 system prompt";
  const effectiveStage = document.createElement("textarea");
  effectiveStage.readOnly = true;
  effectiveStageLabel.appendChild(effectiveStage);
  const effectiveRefinementLabel = document.createElement("label");
  effectiveRefinementLabel.textContent = "Exact Stage 2 system prompt";
  const effectiveRefinement = document.createElement("textarea");
  effectiveRefinement.readOnly = true;
  effectiveRefinementLabel.appendChild(effectiveRefinement);
  effectiveDetails.append(effectiveSummary, instructionMeta, effectiveStageLabel, effectiveRefinementLabel);
  const instructionButtons = document.createElement("div");
  instructionButtons.className = "jsonx-instruction-buttons";
  const resetInstructions = document.createElement("button");
  resetInstructions.type = "button";
  resetInstructions.textContent = "Reset defaults";
  resetInstructions.title = "Restore packaged defaults in this editor; click Save settings to persist them";
  const previewInstructions = document.createElement("button");
  previewInstructions.type = "button";
  previewInstructions.textContent = "Refresh effective preview";
  previewInstructions.title = "Rebuild the exact effective prompts from the current unsaved editor values";
  const saveInstructions = document.createElement("button");
  saveInstructions.type = "button";
  saveInstructions.className = "primary";
  saveInstructions.textContent = "Save settings";
  saveInstructions.title = "Save custom instructions to the ComfyUI user profile and per-node choices to this workflow";
  instructionButtons.append(resetInstructions, previewInstructions, saveInstructions);
  instructionModal.append(
    instructionHead,
    instructionNote,
    generationProfileLabel,
    outputFormatLabel,
    templateUsePresetsLabel,
    framingPlacementLabel,
    detailLevelLabel,
    stageOneLabel,
    templateFillLabel,
    refinementLabel,
    naturalLanguageLabel,
    effectiveDetails,
    instructionButtons,
  );
  instructionOverlay.appendChild(instructionModal);
  document.body.appendChild(instructionOverlay);
  let defaultInstructionTemplates = null;
  let userInstructionOverrides = null;
  let userInstructionOverridesPromise = null;

  const clearDiagnostics = () => {
    diagnostics.classList.remove("visible");
    diagnostics.open = false;
    diagnosticsOutput.value = "";
    requestAnimationFrame(() => resizeForSettings());
  };
  const showDiagnostics = (details) => {
    if (!details || typeof details !== "object") return;
    const providerDetails = details.provider_diagnostics && typeof details.provider_diagnostics === "object"
      ? details.provider_diagnostics
      : details;
    const formatted = (value) => {
      if (value == null || value === "") return "";
      return typeof value === "object" ? JSON.stringify(value, null, 2) : String(value);
    };
    const sections = [
      ["Stage", details.stage],
      ["Provider", providerDetails.provider],
      ["Provider event", providerDetails.event],
      ["HTTP status", providerDetails.http_status],
      ["Prompt feedback", formatted(providerDetails.prompt_feedback)],
      ["Candidate details", formatted(providerDetails.candidates)],
      ["Completion reason", providerDetails.done_reason],
      ["Initial validation error", details.initial_error],
      ["Raw provider response", details.raw_response],
      ["Repair error", details.repair_error],
      ["Raw repair response", details.repair_response],
    ].filter(([, value]) => String(value || "").trim());
    diagnosticsOutput.value = sections.map(([label, value]) => `${label}:\n${value}`).join("\n\n");
    diagnostics.classList.add("visible");
    diagnostics.open = true;
    requestAnimationFrame(() => resizeForSettings());
  };

  const setStatus = (text, error = false) => {
    status.textContent = text;
    status.classList.toggle("error", error);
  };
  const updateOutputPreviewPresentation = (format = String(widgetValue(node, "output_format", "json"))) => {
    const natural = format === "natural";
    outputPreviewTitle.textContent = natural ? "Generated natural-language prompt" : "Generated JsonX output";
    outputPreview.placeholder = natural
      ? "Generated natural-language prompt will appear here."
      : "Generated JSON will appear here.";
  };
  let activeGeneration = null;
  const generationId = () => globalThis.crypto?.randomUUID?.()
    || `jsonx-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const setGenerationActive = (active) => {
    cancelGenerate.classList.toggle("visible", Boolean(active));
    secondaryActions.classList.toggle("generating", Boolean(active));
    cancelGenerate.disabled = !active;
    cancelGenerate.textContent = "Cancel";
    resizeForSettings();
  };
  const cancelActiveGeneration = () => {
    const active = activeGeneration;
    if (!active || active.cancelRequested) return;
    active.cancelRequested = true;
    cancelGenerate.disabled = true;
    cancelGenerate.textContent = "Cancelling...";
    setStatus("Cancelling JsonX generation. Previous output will be kept.");
    void requestJson(`${ROUTE}/cancel`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({generation_id: active.id}),
    }).catch(() => {});
    active.controller.abort();
  };
  const syncOutputFormatEditor = () => {
    const natural = outputFormat.value === "natural";
    refinementInstructions.disabled = natural;
    naturalLanguageInstructions.disabled = !natural;
    if (natural) setWidgetValue(node, "generation_mode", "refined");
  };
  const syncTemplateProfile = () => {
    const isTemplateFill = generationProfile.value === "template_fill";
    templateUsePresets.disabled = !isTemplateFill;
    templateFillInstructions.disabled = !isTemplateFill;
    stageOneInstructions.disabled = isTemplateFill;
  };
  updateOutputPreviewPresentation();
  const persist = () => {
    settings.backend = backend.value;
    settings[`${activeBackend}_timeout`] = Number(timeout.value || 180);
    settings.timeout = settings[`${activeBackend}_timeout`];
    settings.gemini_model = String(geminiModel.value || "").trim();
    for (const [key] of GEMINI_SAFETY_FIELDS) {
      settings[key] = geminiSafetySelects[key].value || "BLOCK_NONE";
    }
    settings.openai_base_url = openaiUrl.value.trim() || DEFAULT_OPENAI_URL;
    settings.openai_model = openaiManualModel.value.trim() || String(openaiModel.value || "").trim();
    settings.ollama_host = ollamaHost.value.trim() || DEFAULT_OLLAMA_HOST;
    settings.ollama_model = String(ollamaModel.value || "").trim();
    settings.ollama_think = ollamaThink.checked;
    if (backend.value === "openai") settings.unload_after = openaiUnload.checked;
    if (backend.value === "ollama") settings.unload_after = ollamaUnload.checked;
    settings.refresh_vram = refreshVram.checked;
    settings.generation_profile = generationProfile.value || "adaptive";
    settings.template_use_presets = templateUsePresets.checked;
    settings.local_model = localModel.value || "";
    settings.local_mmproj = mmproj.value || "none";
    settings.local_additional_model_paths = localAdditionalPaths.value.trim();
    settings.local_max_tokens = numericValue(localMaxTokens, 8192);
    settings.local_temperature = numericValue(localTemperature, 0.7);
    settings.local_top_p = numericValue(localTopP, 0.9);
    settings.local_top_k = numericValue(localTopK, 40);
    settings.local_repeat_penalty = numericValue(localRepeatPenalty, 1.05);
    settings.local_ctx_size = numericValue(localContext, 32768);
    settings.local_memory_mode = localMemoryMode.value || "auto";
    settings.local_n_gpu_layers = numericValue(localGpuLayers, 99);
    settings.local_n_cpu_moe_layers = numericValue(localCpuMoeLayers, 0);
    settings.local_reasoning = localReasoning.value || "auto";
    settings.local_speculative_mode = localSpeculativeMode.value || "auto";
    settings.local_mtp_draft_tokens = numericValue(localMtpDraftTokens, 2);
    settings.local_seed = numericValue(localSeed, -1);
    saveSettings(settings);
    storeSecret(GEMINI_KEY, geminiKey.value);
    storeSecret(OPENAI_KEY, openaiKey.value);
  };
  const loadInstructionTemplates = async () => {
    if (!defaultInstructionTemplates) {
      defaultInstructionTemplates = await requestJson(`${ROUTE}/instructions`);
    }
    return defaultInstructionTemplates;
  };
  const normalizeInstructionOverrides = (value) => {
    const source = value && typeof value === "object" ? value : {};
    return Object.fromEntries(INSTRUCTION_OVERRIDE_KEYS.map((key) => [
      key,
      typeof source[key] === "string" ? source[key].trim() : "",
    ]));
  };
  const loadUserInstructionOverrides = async () => {
    if (!userInstructionOverridesPromise) {
      userInstructionOverridesPromise = requestJson(`${ROUTE}/user-settings`)
        .then((data) => {
          userInstructionOverrides = normalizeInstructionOverrides(data.instruction_overrides);
          return userInstructionOverrides;
        })
        .catch((error) => {
          userInstructionOverridesPromise = null;
          throw error;
        });
    }
    try {
      const saved = await userInstructionOverridesPromise;
      // Existing browser-local overrides remain a one-time migration source until
      // the user saves them into the ComfyUI profile.
      return Object.fromEntries(INSTRUCTION_OVERRIDE_KEYS.map((key) => [
        key,
        saved[key] || String(settings[key] || "").trim(),
      ]));
    } catch {
      return normalizeInstructionOverrides(settings);
    }
  };
  const refreshInstructionPreview = async () => {
    previewInstructions.disabled = true;
    instructionMeta.textContent = "Building effective prompts...";
    try {
      const data = await requestJson(`${ROUTE}/instructions/preview`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          user_instructions: String(widgetValue(node, "user_instructions", "")).trim(),
          preset_context_mode: String(widgetValue(node, "preset_context_mode", "optimized")),
          has_image: Boolean(resolveImageSource(node)),
          generation_profile: generationProfile.value,
          generation_mode: outputFormat.value === "natural"
            ? "refined"
            : String(widgetValue(node, "generation_mode", "fast")),
          output_format: outputFormat.value,
          template_use_presets: templateUsePresets.checked,
          enable_framing_and_placement: framingPlacement.checked,
          detail_level: detailLevel.value,
          stage_one_instructions: stageOneInstructions.value,
          template_fill_instructions: templateFillInstructions.value,
          refinement_instructions: refinementInstructions.value,
          natural_language_instructions: naturalLanguageInstructions.value,
        }),
      });
      effectiveStage.value = data.stage_one || "";
      effectiveRefinement.value = data.refinement || "";
      instructionMeta.textContent = `Stage 1: ${Number(data.stage_one_characters || 0).toLocaleString()} chars · Stage 2: ${Number(data.refinement_characters || 0).toLocaleString()} chars · ${data.generation_profile} · ${data.output_format === "natural" ? "natural two-pass" : `${data.generation_mode} JSON`} · presets ${data.preset_context_mode} · framing ${data.enable_framing_and_placement ? "on" : "off"} · ${data.detail_level} depth`;
      effectiveDetails.open = true;
    } catch (error) {
      instructionMeta.textContent = error.message;
      effectiveDetails.open = true;
    } finally {
      previewInstructions.disabled = false;
    }
  };
  const closeInstructionModal = () => instructionOverlay.classList.remove("visible");
  instructionSettings.onclick = async () => {
    instructionSettings.disabled = true;
    try {
      const [defaults, overrides] = await Promise.all([
        loadInstructionTemplates(),
        loadUserInstructionOverrides(),
      ]);
      stageOneInstructions.value = String(overrides.stage_one_instructions || defaults.stage_one || "");
      templateFillInstructions.value = String(overrides.template_fill_instructions || defaults.template_fill || "");
      refinementInstructions.value = String(overrides.refinement_instructions || defaults.refinement || "");
      naturalLanguageInstructions.value = String(overrides.natural_language_instructions || defaults.natural_language || "");
      generationProfile.value = settings.generation_profile || defaults.default_generation_profile || "adaptive";
      outputFormat.value = String(widgetValue(node, "output_format", defaults.default_output_format || "json"));
      templateUsePresets.checked = Boolean(settings.template_use_presets);
      framingPlacement.checked = Boolean(widgetValue(node, "enable_framing_and_placement", false));
      detailLevel.value = settings.detail_level || defaults.default_detail_level || "deep";
      syncTemplateProfile();
      syncOutputFormatEditor();
      effectiveStage.value = "";
      effectiveRefinement.value = "";
      instructionMeta.textContent = "Open the preview to inspect the exact prompt including live preset context.";
      effectiveDetails.open = false;
      instructionOverlay.classList.add("visible");
    } catch (error) {
      setStatus(`Could not load JsonX instructions: ${error.message}`, true);
    } finally {
      instructionSettings.disabled = false;
    }
  };
  instructionClose.onclick = closeInstructionModal;
  instructionOverlay.onclick = (event) => {
    if (event.target === instructionOverlay) closeInstructionModal();
  };
  resetInstructions.onclick = async () => {
    const defaults = await loadInstructionTemplates();
    stageOneInstructions.value = defaults.stage_one || "";
    templateFillInstructions.value = defaults.template_fill || "";
    refinementInstructions.value = defaults.refinement || "";
    naturalLanguageInstructions.value = defaults.natural_language || "";
    generationProfile.value = defaults.default_generation_profile || "adaptive";
    outputFormat.value = defaults.default_output_format || "json";
    setWidgetValue(node, "generation_mode", "fast");
    setWidgetValue(node, "generation_profile", defaults.default_generation_profile || "adaptive");
    setWidgetValue(node, "template_use_presets", false);
    setWidgetValue(node, "detail_level", defaults.default_detail_level || "deep");
    templateUsePresets.checked = false;
    framingPlacement.checked = Boolean(defaults.default_enable_framing_and_placement);
    detailLevel.value = defaults.default_detail_level || "deep";
    syncTemplateProfile();
    syncOutputFormatEditor();
    instructionMeta.textContent = "Defaults restored in the editor. Click Save settings to keep them.";
  };
  previewInstructions.onclick = refreshInstructionPreview;
  saveInstructions.onclick = async () => {
    const stageOneValue = stageOneInstructions.value.trim();
    const templateFillValue = templateFillInstructions.value.trim();
    const refinementValue = refinementInstructions.value.trim();
    const naturalLanguageValue = naturalLanguageInstructions.value.trim();
    const overrides = {
      stage_one_instructions: stageOneValue === String(defaultInstructionTemplates?.stage_one || "").trim()
        ? ""
        : stageOneValue,
      template_fill_instructions: templateFillValue === String(defaultInstructionTemplates?.template_fill || "").trim()
        ? ""
        : templateFillValue,
      refinement_instructions: refinementValue === String(defaultInstructionTemplates?.refinement || "").trim()
        ? ""
        : refinementValue,
      natural_language_instructions: naturalLanguageValue === String(defaultInstructionTemplates?.natural_language || "").trim()
        ? ""
        : naturalLanguageValue,
    };
    saveInstructions.disabled = true;
    try {
      const saved = await requestJson(`${ROUTE}/user-settings`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({instruction_overrides: overrides}),
      });
      userInstructionOverrides = normalizeInstructionOverrides(saved.instruction_overrides);
      userInstructionOverridesPromise = Promise.resolve(userInstructionOverrides);
      for (const key of INSTRUCTION_OVERRIDE_KEYS) delete settings[key];
    } catch (error) {
      setStatus(`Could not save JsonX user-profile instructions: ${error.message}`, true);
      return;
    } finally {
      saveInstructions.disabled = false;
    }
    settings.detail_level = detailLevel.value || "deep";
    settings.generation_profile = generationProfile.value || "adaptive";
    settings.template_use_presets = templateUsePresets.checked;
    setWidgetValue(node, "generation_profile", settings.generation_profile);
    setWidgetValue(node, "template_use_presets", settings.template_use_presets);
    setWidgetValue(node, "detail_level", settings.detail_level);
    setWidgetValue(node, "enable_framing_and_placement", framingPlacement.checked);
    setWidgetValue(node, "output_format", outputFormat.value || "json");
    if (outputFormat.value === "natural") setWidgetValue(node, "generation_mode", "refined");
    updateOutputPreviewPresentation(outputFormat.value);
    saveSettings(settings);
    closeInstructionModal();
    setStatus(`JsonX settings saved to the ComfyUI user profile · ${settings.generation_profile} · ${outputFormat.value === "natural" ? "natural two-pass" : "JSON output"} · framing ${framingPlacement.checked ? "on" : "off"} · ${settings.detail_level} hierarchy depth.`);
  };
  outputFormat.onchange = syncOutputFormatEditor;
  cancelGenerate.onclick = cancelActiveGeneration;
  const instructionEscapeHandler = (event) => {
    if (event.key === "Escape" && instructionOverlay.classList.contains("visible")) {
      closeInstructionModal();
    }
  };
  document.addEventListener("keydown", instructionEscapeHandler);
  const refreshPanels = () => {
    for (const [name, panel] of [["gemini", geminiPanel], ["openai", openaiPanel], ["ollama", ollamaPanel], ["local", localPanel]]) {
      panel.classList.toggle("active", backend.value === name);
    }
    persist();
  };

  geminiRefresh.onclick = async () => {
    try {
      setStatus("Fetching Gemini models...");
      const data = await requestJson(`${ROUTE}/gemini/models`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({api_key:geminiKey.value, timeout:Number(timeout.value || 180)})});
      geminiModel.setOptions(data.models, settings.gemini_model, "No Gemini models found");
      persist();
      setStatus(`${data.models.length} Gemini models loaded.`);
    } catch (error) { setStatus(error.message, true); }
  };
  openaiRefresh.onclick = async () => {
    try {
      setStatus("Fetching compatible models...");
      const data = await requestJson(`${ROUTE}/openai/models`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({base_url:openaiUrl.value, api_key:openaiKey.value, timeout:Number(timeout.value || 180)})});
      openaiModel.setOptions(data.models, settings.openai_model, "No compatible models found");
      persist();
      setStatus(`${data.models.length} compatible models loaded.`);
    } catch (error) { setStatus(error.message, true); }
  };
  ollamaRefresh.onclick = async () => {
    try {
      setStatus("Fetching Ollama models...");
      const data = await requestJson(`${ROUTE}/ollama/models`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({host:ollamaHost.value, timeout:Number(timeout.value || 180)})});
      ollamaModel.setOptions(data.models, settings.ollama_model, "No Ollama models found");
      persist();
      setStatus(`${data.models.length} Ollama models loaded.`);
    } catch (error) { setStatus(error.message, true); }
  };
  localRefresh.onclick = async () => {
    try {
      setStatus("Refreshing local models...");
      const data = await requestJson(`${ROUTE}/local/models`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({additional_model_paths: additionalModelPaths(localAdditionalPaths.value)}),
      });
      localModel.setOptions(data.models, settings.local_model, "No GGUF models found");
      mmproj.setOptions(data.mmproj, settings.local_mmproj || "none", "No vision projector");
      localModel.dataset.loaded = "true";
      persist();
      const skipped = Number(data.invalid_paths?.length || 0);
      setStatus(`Local model list refreshed${data.additional_roots ? ` · ${data.additional_roots} additional folder(s)` : ""}${skipped ? ` · ${skipped} missing/invalid path(s) skipped` : ""}.`, skipped > 0);
    } catch (error) { setStatus(error.message, true); }
  };

  generate.onclick = async () => {
    persist();
    clearDiagnostics();
    const instructions = String(widgetValue(node, "user_instructions", "")).trim();
    const outputFormatValue = String(widgetValue(node, "output_format", "json"));
    const generationMode = outputFormatValue === "natural"
      ? "refined"
      : String(widgetValue(node, "generation_mode", "fast"));
    if (outputFormatValue === "natural") setWidgetValue(node, "generation_mode", "refined");
    const presetMode = String(widgetValue(node, "preset_context_mode", "optimized"));
    const generationProfileValue = String(widgetValue(node, "generation_profile", "adaptive")) || "adaptive";
    const templateUsePresetsValue = Boolean(widgetValue(node, "template_use_presets", false));
    const framingPlacementValue = Boolean(widgetValue(node, "enable_framing_and_placement", false));
    const imageSource = resolveImageSource(node);
    const imageB64 = await imageSourceToDataUrl(imageSource);
    if (!instructions && !imageB64) {
      setStatus(imageSource ? "Connected image has no readable preview. Run the upstream node first." : "Enter instructions or connect an image.", true);
      return;
    }
    const sendsFullPresets = generationProfileValue === "template_fill"
      ? templateUsePresetsValue
      : presetMode === "full";
    if (sendsFullPresets) {
      try {
        const info = await requestJson(`${ROUTE}/presets/info`);
        setStatus(`Full preset mode: sending all ${info.characters.toLocaleString()} characters (~${info.estimated_tokens.toLocaleString()} tokens) without truncation.`);
      } catch {
        setStatus("Full preset mode: sending the complete presets.json without truncation.");
      }
      await new Promise((resolve) => requestAnimationFrame(resolve));
    } else if (generationProfileValue === "template_fill") {
      setStatus(`Generating ${generationMode} JsonX with the blank Template Fill hierarchy and no presets...`);
    } else {
      setStatus(`Generating ${generationMode} JsonX with optimized presets...`);
    }
    if (outputFormatValue === "natural") {
      setStatus("Generating validated JsonX, then refining it into natural language...");
    }

    const userInstructionOverrides = await loadUserInstructionOverrides();
    const payload = {
      backend: backend.value,
      generation_mode: generationMode,
      output_format: outputFormatValue,
      preset_context_mode: presetMode,
      generation_profile: generationProfileValue,
      template_use_presets: templateUsePresetsValue,
      enable_framing_and_placement: framingPlacementValue,
      detail_level: String(widgetValue(node, "detail_level", "deep")) || "deep",
      stage_one_instructions: userInstructionOverrides.stage_one_instructions,
      template_fill_instructions: userInstructionOverrides.template_fill_instructions,
      refinement_instructions: userInstructionOverrides.refinement_instructions,
      natural_language_instructions: userInstructionOverrides.natural_language_instructions,
      user_instructions: instructions,
      image_b64: imageB64,
      timeout: Number(timeout.value || 180),
      refresh_vram: refreshVram.checked,
      model: backend.value === "gemini"
        ? String(geminiModel.value || "").trim()
        : backend.value === "openai"
          ? openaiManualModel.value.trim() || String(openaiModel.value || "").trim()
          : backend.value === "ollama"
            ? String(ollamaModel.value || "").trim()
            : localModel.value,
    };
    if (backend.value === "gemini") {
      payload.api_key = geminiKey.value.trim();
      payload.gemini_safety = {};
      for (const [key] of GEMINI_SAFETY_FIELDS) {
        payload.gemini_safety[key] = geminiSafetySelects[key].value || "BLOCK_NONE";
      }
    } else if (backend.value === "openai") {
      payload.base_url = openaiUrl.value.trim() || DEFAULT_OPENAI_URL;
      payload.api_key = openaiKey.value.trim();
      payload.unload_after = openaiUnload.checked;
    } else if (backend.value === "ollama") {
      payload.host = ollamaHost.value.trim() || DEFAULT_OLLAMA_HOST;
      payload.think = ollamaThink.checked;
      payload.unload_after = ollamaUnload.checked;
    } else {
      payload.mmproj = mmproj.value || "none";
      payload.additional_model_paths = additionalModelPaths(localAdditionalPaths.value);
      payload.local_options = {
        max_tokens: settings.local_max_tokens,
        temperature: settings.local_temperature,
        top_p: settings.local_top_p,
        top_k: settings.local_top_k,
        repeat_penalty: settings.local_repeat_penalty,
        ctx_size: settings.local_ctx_size,
        memory_mode: settings.local_memory_mode,
        n_gpu_layers: settings.local_n_gpu_layers,
        n_cpu_moe_layers: settings.local_n_cpu_moe_layers,
        reasoning: settings.local_reasoning,
        speculative_mode: settings.local_speculative_mode,
        mtp_draft_tokens: settings.local_mtp_draft_tokens,
        seed: settings.local_seed,
        timeout: Number(timeout.value || 180),
      };
    }

    const active = {
      id: generationId(),
      controller: new AbortController(),
      cancelRequested: false,
    };
    activeGeneration = active;
    setGenerationActive(true);
    generate.disabled = true;
    generate.textContent = outputFormatValue === "natural"
      ? "Generating JSON + prose..."
      : generationMode === "refined" ? "Generating + refining..." : "Generating...";
    try {
      payload.generation_id = active.id;
      const data = await requestJson(`${ROUTE}/generate`, {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify(payload),
        signal: active.controller.signal,
      });
      if (active.cancelRequested) {
        setStatus("JsonX generation cancelled. Previous output kept.");
        return;
      }
      const finalPrompt = data.prompt || data.prompt_json || "";
      setWidgetValue(node, "generated_prompt_json", finalPrompt);
      outputPreview.value = finalPrompt;
      outputPreview.scrollTop = 0;
      updateOutputPreviewPresentation(data.output_format || outputFormatValue);
      clearDiagnostics();
      const metrics = data.hierarchy_metrics || {};
      const metricText = metrics.leaf_count != null
        ? ` · ${metrics.leaf_count} leaves · depth ${metrics.max_depth} · ${metrics.root_groups} roots`
        : "";
      setStatus(`Saved to prompt · ${data.output_format === "natural" ? "natural language" : `${data.generation_mode} JSON`} · ${data.generation_profile || "adaptive"} · presets ${data.preset_context_mode} · framing ${data.enable_framing_and_placement ? "on" : "off"} · ${data.detail_level || "deep"}${metricText}`);
    } catch (error) {
      if (active.cancelRequested || error?.name === "AbortError" || error?.data?.cancelled) {
        clearDiagnostics();
        setStatus("JsonX generation cancelled. Previous output kept.");
      } else {
        showDiagnostics(error.data?.diagnostics);
        setStatus(`${error.message}. Previous output kept.`, true);
      }
    } finally {
      if (activeGeneration === active) {
        activeGeneration = null;
        setGenerationActive(false);
      }
      generate.disabled = false;
      generate.textContent = "Generate";
    }
  };

  backend.onchange = () => {
    settings[`${activeBackend}_timeout`] = Number(timeout.value || 180);
    activeBackend = backend.value;
    timeout.value = settings[`${activeBackend}_timeout`] || 180;
    refreshPanels();
    resizeForSettings();
    if (backend.value === "local" && localModel.dataset.loaded !== "true") {
      setTimeout(() => localRefresh.click(), 0);
    }
  };
  const syncMemoryFields = () => {
    localGpuLayers.disabled = !["gpu_layers", "gpu_and_cpu_moe_layers"].includes(localMemoryMode.value);
    localCpuMoeLayers.disabled = !["cpu_moe_layers", "gpu_and_cpu_moe_layers"].includes(localMemoryMode.value);
  };
  localMemoryMode.addEventListener("change", syncMemoryFields);
  syncMemoryFields();
  openaiModel.addEventListener("change", () => { openaiManualModel.value = ""; persist(); });
  generationProfile.addEventListener("change", syncTemplateProfile);
  for (const control of [timeout, geminiKey, geminiModel, ...Object.values(geminiSafetySelects), openaiUrl, openaiKey, openaiManualModel, openaiModel, openaiUnload, ollamaHost, ollamaModel, ollamaThink, ollamaUnload, refreshVram, localModel, mmproj, localAdditionalPaths, localContext, localMaxTokens, localTemperature, localTopP, localTopK, localRepeatPenalty, localMemoryMode, localReasoning, localSpeculativeMode, localMtpDraftTokens, localGpuLayers, localCpuMoeLayers, localSeed]) control.addEventListener("change", persist);
  syncTemplateProfile();
  refreshPanels();
  if (backend.value === "local") setTimeout(() => localRefresh.click(), 0);

  // DOM widgets are laid out at the node's current height. Measuring root.scrollHeight
  // after opening a details element therefore captures that old allocation and prevents
  // the node from shrinking when the element closes. Measure a width-matched clone with
  // auto height instead, then let LiteGraph calculate the complete node height from it.
  let domMinHeight = 118;
  const measureDomContentHeight = (nodeWidth) => {
    const clone = root.cloneNode(true);
    clone.classList.add("jsonx-llm-measure");
    clone.style.position = "fixed";
    clone.style.left = "-100000px";
    clone.style.top = "0";
    clone.style.visibility = "hidden";
    clone.style.pointerEvents = "none";
    clone.style.width = `${Math.max(300, nodeWidth - 18)}px`;
    clone.style.height = "auto";
    clone.style.minHeight = "0";
    clone.style.maxHeight = "none";
    document.body.appendChild(clone);
    const height = Math.ceil(clone.getBoundingClientRect().height) + 2;
    clone.remove();
    return Math.max(118, height);
  };
  const resizeForSettings = () => {
    requestAnimationFrame(() => {
      const width = Math.max(380, Number(node.size?.[0]) || 380);
      domMinHeight = measureDomContentHeight(width);
      requestAnimationFrame(() => {
        const computedHeight = Number(node.computeSize?.()?.[1]) || (domMinHeight + 210);
        node.setSize?.([width, Math.max(260, Math.ceil(computedHeight))]);
      });
    });
  };
  localSettings.addEventListener("toggle", resizeForSettings);
  geminiSettings.addEventListener("toggle", resizeForSettings);

  chainCallback(node, "onRemoved", function jsonXPickerCleanup() {
    cancelActiveGeneration();
    geminiModel.destroy();
    openaiModel.destroy();
    ollamaModel.destroy();
    localModel.destroy();
    mmproj.destroy();
    document.removeEventListener("keydown", instructionEscapeHandler);
    instructionOverlay.remove();
  });

  node.addDOMWidget("llm_to_jsonx", "LLM to JsonX", root, {serialize:false, hideOnZoom:false, getMinHeight:() => domMinHeight});
  node.resizable = true;
  const size = node.size || [420, 600];
  node.setSize?.([Math.max(380, size[0]), 260]);
  resizeForSettings();
}

app.registerExtension({
  name: "WorkflowX.LLMToJsonX",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== TARGET_NODE) return;
    chainCallback(nodeType.prototype, "onNodeCreated", function jsonXCreated() { setupLLMToJsonX(this); });
    chainCallback(nodeType.prototype, "onConfigure", function jsonXConfigured() { setTimeout(() => setupLLMToJsonX(this), 0); });
  },
});
