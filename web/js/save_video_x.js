import { app } from "/scripts/app.js";
import { setWidgetConfig } from "/extensions/core/widgetInputs.js";
import { applyTextReplacements } from "/scripts/utils.js";

const NODE_NAME = "WorkflowX_SaveVideoX";
const AUDIO_FILTERS = [
  "Denoise light",
  "De-click",
  "High-pass rumble cut",
  "Low-pass hiss cut",
  "De-esser light",
  "Presence boost",
  "Warmth",
  "Brightness",
  "Speech clarity",
  "Stereo widen",
];

function chainCallback(object, property, callback) {
  if (!object) return;
  if (property in object && object[property]) {
    const original = object[property];
    object[property] = function () {
      const result = original.apply(this, arguments);
      return callback.apply(this, arguments) ?? result;
    };
  } else {
    object[property] = callback;
  }
}

function fitHeight(node) {
  node.setSize([node.size[0], node.computeSize([node.size[0], node.size[1]])[1]]);
  node?.graph?.setDirtyCanvas(true);
}

function addDateFormatting(nodeType, field) {
  chainCallback(nodeType.prototype, "onNodeCreated", function () {
    const widget = this.widgets?.find((w) => w.name === field);
    if (!widget) return;
    widget.serializeValue = () => applyTextReplacements(app, widget.value);
  });
}

function addWidgetMapState(nodeType) {
  chainCallback(nodeType.prototype, "onNodeCreated", function () {
    chainCallback(this, "onConfigure", function (info) {
      if (!this.widgets || typeof info?.widgets_values !== "object") return;
      if (Array.isArray(info.widgets_values)) return;

      for (const widget of this.widgets) {
        if (widget.type === "button") continue;
        if (widget.name in info.widgets_values) {
          widget.value = info.widgets_values[widget.name];
          widget.callback?.(widget.value);
        }
      }
    });

    chainCallback(this, "onSerialize", function (info) {
      info.widgets_values = {};
      for (const widget of this.widgets ?? []) {
        if (widget.type === "button") continue;
        info.widgets_values[widget.name] = widget.value;
      }
    });
  });
}

function addConvertedWidgetInputSupport(nodeType) {
  chainCallback(nodeType.prototype, "onNodeCreated", function () {
    const originalAddInput = this.addInput;
    this.addInput = function (name, type, options) {
      if (options?.widget) {
        const widget = this.widgets?.find((w) => w.name === name);
        if (widget?.config) {
          type = widget.config[0] === "FLOAT" ? "FLOAT,INT" : widget.config[0];
          setWidgetConfig(options, widget.config);
        }
      }
      return originalAddInput.apply(this, [name, type, options]);
    };
  });
}

function parseAudioFilters(value) {
  if (Array.isArray(value)) return value.filter((item) => AUDIO_FILTERS.includes(item));
  if (!value || typeof value !== "string") return [];
  try {
    const parsed = JSON.parse(value);
    if (Array.isArray(parsed)) return parsed.filter((item) => AUDIO_FILTERS.includes(item));
  } catch {
    return value
      .split(",")
      .map((item) => item.trim())
      .filter((item) => AUDIO_FILTERS.includes(item));
  }
  return [];
}

function selectedAudioFilterText(value) {
  const selected = parseAudioFilters(value);
  if (!selected.length) return "Off";
  if (selected.length <= 2) return selected.join(", ");
  return `${selected.length} filters selected`;
}

function showAudioFilterDialog(widget, node) {
  const selected = new Set(parseAudioFilters(widget.value));
  const backdrop = document.createElement("div");
  backdrop.style.cssText = [
    "position:fixed",
    "inset:0",
    "z-index:100000",
    "display:flex",
    "align-items:center",
    "justify-content:center",
    "background:rgba(0,0,0,.62)",
    "font-family:ui-sans-serif,system-ui,sans-serif",
  ].join(";");

  const panel = document.createElement("div");
  panel.style.cssText = [
    "width:min(420px,92vw)",
    "max-height:80vh",
    "overflow:auto",
    "box-sizing:border-box",
    "padding:14px",
    "border:1px solid #555",
    "border-radius:8px",
    "background:#262626",
    "color:#eee",
    "box-shadow:0 18px 60px rgba(0,0,0,.55)",
  ].join(";");

  const title = document.createElement("div");
  title.textContent = "Audio improvement filters";
  title.style.cssText = "font-weight:700;font-size:14px;margin-bottom:10px";
  panel.appendChild(title);

  for (const label of AUDIO_FILTERS) {
    const row = document.createElement("label");
    row.style.cssText = "display:flex;align-items:center;gap:8px;padding:6px 2px;cursor:pointer";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = selected.has(label);
    checkbox.onchange = () => {
      if (checkbox.checked) selected.add(label);
      else selected.delete(label);
    };
    row.append(checkbox, document.createTextNode(label));
    panel.appendChild(row);
  }

  const actions = document.createElement("div");
  actions.style.cssText = "display:flex;justify-content:flex-end;gap:8px;margin-top:12px";

  const clear = document.createElement("button");
  clear.textContent = "Clear";
  clear.onclick = () => {
    selected.clear();
    for (const input of panel.querySelectorAll("input")) input.checked = false;
  };

  const cancel = document.createElement("button");
  cancel.textContent = "Cancel";
  cancel.onclick = () => backdrop.remove();

  const apply = document.createElement("button");
  apply.textContent = "Apply";
  apply.onclick = () => {
    widget.value = JSON.stringify(AUDIO_FILTERS.filter((label) => selected.has(label)));
    widget.callback?.(widget.value);
    backdrop.remove();
    node?.graph?.setDirtyCanvas(true, true);
  };

  actions.append(clear, cancel, apply);
  panel.appendChild(actions);
  backdrop.appendChild(panel);
  backdrop.addEventListener("mousedown", (event) => {
    if (event.target === backdrop) backdrop.remove();
  });
  document.body.appendChild(backdrop);
}

function createAudioFilterWidget(originalWidget, node) {
  return {
    name: "audio_filters",
    type: "WORKFLOWX_AUDIO_FILTERS",
    value: originalWidget?.value || "[]",
    options: originalWidget?.options || {},
    callback: originalWidget?.callback,
    serializeValue() {
      return this.value || "[]";
    },
    computeSize(width) {
      return [width || 220, 28];
    },
    draw(ctx, _node, width, y, height) {
      const margin = 10;
      ctx.save();
      ctx.fillStyle = "#1f1f1f";
      ctx.strokeStyle = "#666";
      ctx.beginPath();
      ctx.roundRect?.(margin, y + 3, width - margin * 2, height - 6, 4);
      if (ctx.roundRect) {
        ctx.fill();
        ctx.stroke();
      } else {
        ctx.fillRect(margin, y + 3, width - margin * 2, height - 6);
        ctx.strokeRect(margin, y + 3, width - margin * 2, height - 6);
      }
      ctx.fillStyle = "#ddd";
      ctx.font = "12px sans-serif";
      ctx.textBaseline = "middle";
      ctx.fillText(`audio_filters: ${selectedAudioFilterText(this.value)}`, margin + 8, y + height / 2);
      ctx.restore();
    },
    mouse(event, _pos, widgetNode) {
      if (event.type !== "pointerdown" && event.type !== "mousedown") return false;
      showAudioFilterDialog(this, widgetNode);
      return true;
    },
  };
}

function installAudioFilterWidget(nodeType) {
  chainCallback(nodeType.prototype, "onNodeCreated", function () {
    const index = this.widgets?.findIndex((widget) => widget.name === "audio_filters") ?? -1;
    if (index < 0) return;
    this.widgets[index] = createAudioFilterWidget(this.widgets[index], this);
    fitHeight(this);
  });
}

app.registerExtension({
  name: "WorkflowX.SaveVideoX",
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== NODE_NAME) return;
    addWidgetMapState(nodeType);
    addDateFormatting(nodeType, "filename_prefix");
    addConvertedWidgetInputSupport(nodeType);
    installAudioFilterWidget(nodeType);
  },
});
