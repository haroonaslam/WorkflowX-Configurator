import { attachReview } from "./chain_review.js";
import { app } from "../../../scripts/app.js";
import { activeLine, editLine, isConversion, parameterValue, conversionSummary, inlineAt, editInline, editPresets, customPreset } from "./chain_editor.mjs";

const catalog = await fetch(new URL("./tags.json", import.meta.url)).then((r) => {
  if (!r.ok) throw Error("AuK choices could not be loaded.");
  return r.json();
});
const css = document.createElement("link");
css.rel = "stylesheet";
css.href = new URL("./chained_clone.css", import.meta.url).href;
document.head.append(css);

function element(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text) el.textContent = text;
  return el;
}

function attachPicker(node) {
  const script = node.widgets?.find((w) => w.name === "script");
  if (!script) return;
  const box = script.element ?? script.inputEl;
  const textarea = box instanceof HTMLTextAreaElement ? box : box?.querySelector?.("textarea");
  const root = element("div", "workflowx-auk-chain-controls");
  const actions = element("div", "workflowx-auk-chain-actions");
  const summary = element("div", "workflowx-auk-chain-summary");
  const status = element("div", "workflowx-auk-chain-status");
  status.setAttribute("aria-live", "polite");
  let selectionEnd = 0;
  let caret = 0, popover = null, opener = null, tooltip = null, tipTimer = null, tipsDismissed = false;
  const abort = new AbortController();
  const on = (el, event, fn) => el.addEventListener(event, fn);
  const watch = (el, event, fn) => el.addEventListener(event, fn, { signal: abort.signal });
  const connected = () => node.inputs?.some((input) => input.name === "script" && input.link != null);
  const value = () => String(script.value ?? "");
  const hideTip = () => { clearTimeout(tipTimer); tooltip?.remove(); tooltip = null; };
  function help(el, text) {
    el.dataset.help = text;
    el.setAttribute("aria-description", text);
    const show = () => {
      hideTip();
      if (tipsDismissed) return;
      tipTimer = setTimeout(() => {
        tooltip = element("div", "workflowx-auk-chain-tooltip", el.dataset.help);
        tooltip.setAttribute("role", "tooltip");
        document.body.append(tooltip);
        place(tooltip, el, true);
      }, 350);
    };
    on(el, "pointerenter", show); on(el, "focus", show);
    on(el, "pointerleave", hideTip); on(el, "blur", hideTip);
    return el;
  }
  function button(label, description, callback, className = "") {
    const el = help(element("button", className, label), description);
    el.type = "button"; on(el, "click", callback); return el;
  }
  function place(panel, anchor, above = false) {
    const rect = anchor.getBoundingClientRect();
    panel.style.left = `${Math.max(8, Math.min(rect.left, window.innerWidth - panel.offsetWidth - 8))}px`;
    const top = above && rect.top > panel.offsetHeight + 14 ? rect.top - panel.offsetHeight - 6 : rect.bottom + 6;
    panel.style.top = `${Math.max(8, Math.min(top, window.innerHeight - panel.offsetHeight - 8))}px`;
  }
  function close(restoreFocus = false) {
    if (restoreFocus) tipsDismissed = true;
    hideTip(); popover?.remove(); popover = null;
    if (restoreFocus && opener?.isConnected) opener.focus();
    hideTip();
  }
  function open(anchor, title) {
    close(); opener = anchor;
    popover = element("section", "workflowx-auk-chain-popover");
    popover.setAttribute("role", "dialog"); popover.setAttribute("aria-label", title);
    const heading = element("div", "workflowx-auk-chain-popover-heading");
    heading.append(element("strong", "", title), button("×", "Close this menu.", () => close(true), "workflowx-auk-chain-close"));
    popover.append(heading); document.body.append(popover);
    on(popover, "pointerdown", (e) => e.stopPropagation());
    on(popover, "keydown", (e) => {
      e.stopPropagation();
      tipsDismissed = e.key === "Escape";
      if (e.key === "Escape") { e.preventDefault(); close(true); return; }
      const controls = [...popover.querySelectorAll("button:not(:disabled),input,select,[tabindex='0']")];
      const index = controls.indexOf(document.activeElement);
      if (e.key === "Tab" && controls.length) {
        if (e.shiftKey && index <= 0) { e.preventDefault(); controls.at(-1).focus(); }
        else if (!e.shiftKey && index === controls.length - 1) { e.preventDefault(); controls[0].focus(); }
      }
      if (["ArrowDown", "ArrowUp"].includes(e.key) && document.activeElement?.type !== "number" && document.activeElement?.tagName !== "SELECT") {
        e.preventDefault(); controls[(index + (e.key === "ArrowDown" ? 1 : -1) + controls.length) % controls.length]?.focus();
      }
    });
    return popover;
  }
  function finishOpen(anchor, focus) { place(popover, anchor); focus?.focus(); }
  function apply(action) {
    if (connected()) return;
    let result;
    try { result = action.type === "inline" ? editInline(value(), caret, selectionEnd, action.tag) : editLine(value(), caret, action); }
    catch (error) { status.textContent = error.message; return; }
    close(); node.graph?.beforeChange();
    if (textarea) {
      textarea.focus(); textarea.setSelectionRange(result.start, result.end);
      // Native insertion preserves the textarea's undo history.
      if (!document.execCommand("insertText", false, result.replacement)) textarea.setRangeText(result.replacement, result.start, result.end, "end");
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
      textarea.setSelectionRange(result.caret, result.caret);
    }
    script.value = result.value; caret = selectionEnd = result.caret;
    script.callback?.(result.value); node.graph?.afterChange();
    update(); app.graph.setDirtyCanvas(true, true);
  }
  function settings(anchor, item, index = null, raw = null, inline = false) {
    const panel = open(anchor, index === null ? item.label : `Change ${index + 1} · ${item.label}`);
    panel.append(element("p", "workflowx-auk-chain-description", item.help));
    let field = null;
    const error = element("div", "workflowx-auk-chain-error"); error.setAttribute("role", "alert");
    if (item.parameter) {
      const label = element("label", "workflowx-auk-chain-field"); label.append(element("span", "", item.field));
      const row = element("div", "workflowx-auk-chain-parameter");
      field = help(element("input"), item.help);
      field.type = item.parameter === "number" ? "number" : "text";
      if (item.parameter === "number") field.step = "any";
      field.value = raw === null ? (item.tag === "c-speed" ? "1.0" : String(item.default)) : raw.replace(item.tag === "c-volume" ? /db$/i : /$^/, "").trim();
      field.setAttribute("aria-label", item.field); row.append(field);
      if (item.unit) row.append(element("span", "workflowx-auk-chain-unit", item.unit));
      if (item.step) {
        const increment = (direction) => {
          const current = Number(field.value);
          if (Number.isFinite(current)) field.value = String(Number((current + direction * item.step).toFixed(10)));
        };
        on(field, "keydown", (e) => {
          if (e.key === "ArrowUp" || e.key === "ArrowDown") {
            e.preventDefault(); increment(e.key === "ArrowUp" ? 1 : -1);
          }
        });
        row.append(button("−", `Decrease by ${item.step} ${item.unit}.`, () => increment(-1)), button("+", `Increase by ${item.step} ${item.unit}.`, () => increment(1)));
      }
      label.append(row); panel.append(label);
    }
    const save = () => {
      try {
        const tag = item.tag + (field ? `:${parameterValue(item, field.value)}${item.suffix ?? ""}` : "");
        apply(inline ? {type: "inline", tag} : { type: index === null ? "add" : "edit", index, tag });
      } catch (e) { error.textContent = e.message; field?.focus(); }
    };
    const footer = element("div", "workflowx-auk-chain-footer");
    if (index !== null) {
      const count = activeLine(value(), caret).tags.filter(isConversion).length;
      const earlier = button("← Earlier", "Apply this change before the previous one.", () => apply({ type: "move", index, offset: -1 }));
      const later = button("Later →", "Apply this change after the next one.", () => apply({ type: "move", index, offset: 1 }));
      earlier.disabled = index === 0; later.disabled = index === count - 1;
      footer.append(earlier, later, button("Remove", "Remove this change from the line.", () => apply({ type: "remove", index })));
    }
    const saveButton = button(index === null ? "Add change" : "Save change", "Keep this choice on the current line.", save, "workflowx-auk-chain-primary");
    footer.append(saveButton); panel.append(error, footer);
    if (field) on(field, "keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); save(); } });
    finishOpen(anchor, field ?? saveButton);
  }
  const savedChoices = () => Array.isArray(node.properties?.workflowx_auk_presets) ? node.properties.workflowx_auk_presets : [];
  function storeChoices(choices) {
    node.graph?.beforeChange();
    node.properties ??= {};
    node.properties.workflowx_auk_presets = choices;
    node.graph?.afterChange();
    app.graph.setDirtyCanvas(true, true);
  }
  function customChoices(anchor, kind, index = null) {
    const style = kind === "style", existing = index === null ? null : savedChoices()[index];
    const panel = open(anchor, existing ? "Edit saved choice" : "Save custom choice");
    const field = (label, control, description) => {
      const row = element("label", "workflowx-auk-chain-field");
      row.append(element("span", "", label), help(control, description)); panel.append(row);
      control.setAttribute("aria-label", label); return control;
    };
    const category = field("Category", element("select"), "Choose where this choice appears in the menu.");
    const groups = style ? ["Emotion", "Delivery", "Expressive delivery"] : Object.keys(catalog.categories);
    for (const group of groups) { const option = element("option", "", group); option.value = group; category.append(option); }
    category.value = existing?.group ?? "Emotion";
    const effect = field("Effect", element("select"), "Choose what this saved choice does to the voice.");
    effect.parentElement.hidden = style;
    const name = field("Name", element("input"), "The name shown in the picker."); name.value = existing?.label ?? "";
    const input = field("Value", element("input"), "Enter your tone, description, or numeric value.");
    const error = element("div", "workflowx-auk-chain-error"); error.setAttribute("role", "alert");
    function effects() {
      effect.replaceChildren();
      const group = category.value;
      const items = catalog.conversions.filter(item => item.group === group || (['Delivery', 'Expressive delivery'].includes(group) && ['c-delivery','c-whisper','c-normal'].includes(item.tag)));
      for (const item of items) { const option = element("option", "", item.label); option.value = item.tag; effect.append(option); }
    }
    function parameter() {
      const item = catalog.conversions.find(item => item.tag === effect.value);
      input.parentElement.hidden = !style && !item?.parameter;
      input.type = item?.parameter === "number" && !style ? "number" : "text"; input.step = "any";
      input.value = style ? "" : String(item?.default ?? "");
      input.parentElement.firstChild.textContent = style ? "Starting tone" : (item?.field ?? "Value") + (item?.unit ? ` (${item.unit})` : "");
    }
    effects();
    if (existing && !style) effect.value = existing.tag.split(':')[0];
    parameter();
    if (existing) input.value = style ? existing.tag : existing.tag.slice(existing.tag.indexOf(':') + 1).replace(/db$/i,'');
    on(category, "change", () => { effects(); parameter(); place(panel, anchor); });
    on(effect, "change", () => { parameter(); place(panel, anchor); });
    const save = () => {
      try {
        const choice = customPreset(catalog, {label:name.value, group:category.value, operation:effect.value, value:input.value}, style);
        const choices = [...savedChoices()];
        if (choices.some((item, i) => i !== index && item.style === style && item.group === choice.group && item.label.toLowerCase() === choice.label.toLowerCase())) throw Error('A choice with this name already exists in this category.');
        if (index === null) choices.push(choice); else choices[index] = choice;
        storeChoices(choices); menu(anchor, kind);
      } catch (e) { error.textContent = e.message; }
    };
    const footer = element("div", "workflowx-auk-chain-footer");
    footer.append(button("Save choice", "Save in this node's workflow, ready to select from the menu.", save, "workflowx-auk-chain-primary"));
    if (existing) footer.append(button("Delete", "Remove this saved choice. Tags already in the script remain unchanged.", () => { storeChoices(savedChoices().filter((_, i) => i !== index)); menu(anchor, kind); }));
    panel.append(error, footer); finishOpen(anchor, name);
  }
  function manageChoices(anchor, kind) {
    const panel = open(anchor, "Manage saved choices");
    savedChoices().forEach((item, index) => {
      if (Boolean(item.style) === (kind === "style")) panel.append(button(`${item.group} · ${item.label}`, "Edit or delete this saved choice.", () => customChoices(anchor, kind, index), "workflowx-auk-chain-choice"));
    });
    finishOpen(anchor, panel.querySelector(".workflowx-auk-chain-choice"));
  }
  function menu(anchor, kind) {
    if (connected()) return;
    const styles = kind === "style", inline = kind === "inline";
    const panel = open(anchor, inline ? "Inline edit" : styles ? "Voice style" : "Add conversion");
    const search = help(element("input", "workflowx-auk-chain-search"), "Type to find a choice. Use the arrow keys to browse and Enter to choose.");
    search.type = "search"; search.placeholder = styles ? "Search styles…" : "Search changes…";
    search.setAttribute("aria-label", search.placeholder);
    const list = element("div", "workflowx-auk-chain-choices"); panel.append(search, list);
    const customActions = element("div", "workflowx-auk-chain-footer");
    customActions.append(button("Save custom choice…", "Choose a category and save your own choice for one-click use.", () => customChoices(anchor, kind)));
    if (savedChoices().some(item => Boolean(item.style) === styles)) customActions.append(button("Manage saved…", "Edit or delete choices saved in this node.", () => manageChoices(anchor, kind)));
    panel.append(customActions);
    const render = () => {
      list.replaceChildren();
      const items = [...(styles ? catalog.styles : [...editPresets(catalog), ...catalog.conversions]), ...savedChoices().filter(item => Boolean(item.style) === styles)].filter((i) => `${i.tag} ${i.label ?? ""} ${i.group}`.toLowerCase().includes(search.value.trim().toLowerCase()));
      if (inline && inlineAt(value(), caret) && !search.value) {
        const span = inlineAt(value(), caret);
        const entry = catalog.conversions.find(x => x.tag === (catalog.inline_aliases[span[1].toLowerCase()] ?? span[1].toLowerCase()));
        if (entry?.parameter) list.append(button("Edit current value", "Adjust the change around these words.", () => settings(anchor, entry, null, span[2] ?? "", true), "workflowx-auk-chain-choice"));
        list.append(button("Remove inline edit", "Keep these words without their inline change.", () => apply({type:"inline", tag:null}), "workflowx-auk-chain-choice"));
      }
      if (styles && !search.value) list.append(button("No voice style", "Use the reference voice without asking for a particular feeling.", () => apply({ type: "style", tag: null }), "workflowx-auk-chain-choice"));
      for (const group of [...new Set(items.map((i) => i.group))]) {
        const heading = help(element("div", "workflowx-auk-chain-category", group), catalog.categories[group]); heading.tabIndex = 0; list.append(heading);
        for (const item of items.filter((i) => i.group === group)) list.append(button(item.label ?? item.tag, inline ? (item.inline_help ?? item.help.replaceAll("line", "selected words")) : item.help, () => {
          if (inline) { if (item.parameter) settings(anchor, item, null, null, true); else apply({type:"inline", tag:item.tag}); }
          else if (styles) apply({ type: "style", tag: item.tag });
          else if (item.parameter) settings(anchor, item);
          else apply({ type: "add", tag: item.tag });
        }, "workflowx-auk-chain-choice"));
      }
      if (!items.length) list.append(element("p", "workflowx-auk-chain-description", "No matching choices."));
      place(panel, anchor);
    };
    on(search, "input", render); render(); finishOpen(anchor, search);
  }
  const styleButton = button("Voice style ▾", catalog.help.style, () => menu(styleButton, "style"));
  const conversionButton = button("Add conversion +", catalog.help.conversion, () => menu(conversionButton, "conversion"));
  const multiSpeaker = node.widgets?.find((w) => w.name === "multi_speaker");
  const speakerHelp = "Choose who speaks this line. Continue previous uses the last selected speaker, starting with Voice 1.";
  function speakerMenu(anchor) {
    if (connected()) return;
    const panel = open(anchor, "Speaker");
    for (const [label, voice] of [["Voice 1", 1], ["Voice 2", 2], ["Continue previous", null]]) {
      panel.append(button(label, voice ? `Use the Voice ${voice} recording for this line.` : speakerHelp, () => apply({ type: "speaker", voice }), "workflowx-auk-chain-choice"));
    }
    finishOpen(anchor, panel.querySelector(".workflowx-auk-chain-choice"));
  }
  const inlineToggle = node.widgets?.find(w => w.name === "inline_edits");
  const inlineButton = button("Inline edit ▾", catalog.help.inline, () => menu(inlineButton, "inline"));
  const speakerButton = button("Speaker ▾", speakerHelp, () => speakerMenu(speakerButton));
  const durationHelp = help(element("span", "workflowx-auk-chain-duration", "Duration: (3s)"), catalog.help.duration); durationHelp.tabIndex = 0;
  actions.append(speakerButton, styleButton, conversionButton, inlineButton, durationHelp); root.append(actions, summary, status);
  help(status, catalog.help.connected);
  function update() {
    inlineButton.hidden = !inlineToggle?.value;
    inlineButton.disabled = connected();
    const linked = connected(); styleButton.disabled = conversionButton.disabled = linked;
    speakerButton.hidden = !multiSpeaker?.value;
    speakerButton.disabled = linked;
    summary.replaceChildren(); status.textContent = linked ? catalog.help.connected : "";
    status.tabIndex = linked ? 0 : -1;
    if (linked) { close(); return; }
    const line = activeLine(value(), caret), styles = line.tags.filter((tag) => !isConversion(tag));
    summary.append(element("span", "workflowx-auk-chain-line", `Line ${line.number}`));
    if (multiSpeaker?.value) summary.append(button(`Voice ${line.voice}${line.prefix ? "" : " · inherited"}`, speakerHelp, (e) => speakerMenu(e.currentTarget), "workflowx-auk-chain-chip"));
    summary.append(button(styles.join(" + ") || "Reference voice", catalog.help.style, (e) => menu(e.currentTarget, "style"), "workflowx-auk-chain-chip workflowx-auk-chain-style-chip"));
    line.tags.filter(isConversion).forEach((tag, index) => {
      const entry = conversionSummary(tag, catalog.conversions);
      summary.append(button(`${index + 1} · ${entry.label}${entry.effect ? ` · ${entry.effect}` : ""}`, `${entry.help} Click to edit, move, or remove.`, (e) => {
        if (entry.item) settings(e.currentTarget, entry.item, index, entry.raw);
        else {
          const panel = open(e.currentTarget, "Unknown change");
          const remove = button("Remove", "Remove this unknown change.", () => apply({ type: "remove", index }));
          panel.append(remove); finishOpen(e.currentTarget, remove);
        }
      }, "workflowx-auk-chain-chip"));
    });
    if (styles.length > 1) status.textContent = `Line ${line.number}: choose one voice style. Use Add conversion for additional changes.`;
  }
  if (textarea) {
    help(textarea, catalog.help.script);
    for (const event of ["input", "keyup", "click", "select", "blur"]) watch(textarea, event, () => {
      caret = textarea.selectionStart ?? 0; selectionEnd = textarea.selectionEnd ?? caret; if (event !== "blur") update();
    });
  }
  on(root, "pointerdown", (e) => e.stopPropagation());
  on(root, "keydown", (e) => { e.stopPropagation(); tipsDismissed = e.key === "Escape"; if (tipsDismissed) { hideTip(); close(true); } });
  watch(document, "keydown", (e) => { tipsDismissed = e.key === "Escape"; if (tipsDismissed) hideTip(); });
  watch(document, "pointermove", () => { tipsDismissed = false; });
  watch(document, "pointerdown", (e) => { if (popover && !popover.contains(e.target) && !root.contains(e.target)) close(); });
  watch(window, "resize", () => { if (popover && opener?.isConnected) place(popover, opener); hideTip(); });
  const toolbar = node.addDOMWidget("auk_tag_picker", "auk_tag_picker", root, {
    getMinHeight: () => 108, getMaxHeight: () => 108, serialize: false, hideOnZoom: false,
  });
  toolbar.serializeValue = () => undefined;
  node.widgets.splice(node.widgets.indexOf(toolbar), 1);
  node.widgets.splice(node.widgets.indexOf(script), 0, toolbar);
  const connectionChanged = node.onConnectionsChange;
  node.onConnectionsChange = function () { const result = connectionChanged?.apply(this, arguments); update(); return result; };
  const configured = node.onConfigure;
  node.onConfigure = function () { const result = configured?.apply(this, arguments); queueMicrotask(update); return result; };
  for (const toggle of [multiSpeaker, inlineToggle].filter(Boolean)) {
    const callback = toggle.callback;
    toggle.callback = function () { const result = callback?.apply(this, arguments); close(); update(); return result; };
  }
  const removed = node.onRemoved;
  node.onRemoved = function () { close(); abort.abort(); return removed?.apply(this, arguments); };
  attachReview(node, {button, help, watch});
  update(); node.setSize([Math.max(node.size[0], 560), Math.max(node.size[1], 600)]);
}

app.registerExtension({
  name: "WorkflowX.AuK.ChainedClone",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "WorkflowXAuKChainedClone") return;
    const created = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () { created?.apply(this, arguments); attachPicker(this); };
  },
});
