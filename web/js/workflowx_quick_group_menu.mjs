const menuBindings = new WeakMap();

function vueMenuAt(event) {
  for (const trigger of document.querySelectorAll('button[data-menu-owner][aria-expanded="true"]')) {
    if (Math.abs(parseFloat(trigger.style.left) - event.clientX) > 1
      || Math.abs(parseFloat(trigger.style.top) - event.clientY) > 1) continue;
    if (!trigger.style.left || !trigger.style.top) continue;
    const owner = CSS.escape(trigger.dataset.menuOwner);
    const menu = document.querySelector(`[role="menu"][data-menu-owner="${owner}"][data-state="open"]`);
    if (menu) return menu;
  }
}

function appendVueGroupActions(menu, actions) {
  menuBindings.get(menu)?.abort();
  menu.querySelector(".workflowx-quick-group-actions")?.remove();
  const nativeItems = [...menu.querySelectorAll(':scope > [role="menuitem"]:not([data-disabled])')];
  const lastNative = nativeItems.at(-1);
  const section = document.createElement("div");
  section.className = "workflowx-quick-group-actions";
  section.setAttribute("role", "group");
  section.setAttribute("aria-label", "WorkflowX");
  section.style.cssText = "border-top:1px solid var(--border-color,#555);margin-top:3px;padding-top:3px";
  const buttons = actions.map(({ content, callback }) => {
    const button = document.createElement("button");
    button.type = "button";
    button.tabIndex = -1;
    button.setAttribute("role", "menuitem");
    button.className = "flex w-full rounded-sm px-2 py-1.5 text-left text-sm focus:bg-accent hover:bg-accent";
    button.textContent = content;
    button.addEventListener("click", () => {
      menu.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      callback();
    });
    return button;
  });
  section.append(...buttons);
  menu.append(section);

  const binding = new AbortController();
  menuBindings.set(menu, binding);
  menu.addEventListener("keydown", (event) => {
    const index = buttons.indexOf(event.target);
    let next;
    if (event.key === "ArrowDown" && event.target === lastNative) next = buttons[0];
    else if (event.key === "ArrowDown" && index >= 0) next = buttons[index + 1] ?? nativeItems[0];
    else if (event.key === "ArrowUp" && index >= 0) next = buttons[index - 1] ?? lastNative;
    if (!next) return;
    event.preventDefault();
    event.stopPropagation();
    next.focus();
  }, { capture: true, signal: binding.signal });
}

export function installQuickGroupMenu(makeActions) {
  const { LGraphCanvas, LiteGraph } = globalThis;
  const canvasProto = LGraphCanvas?.prototype;
  if (!canvasProto?.processContextMenu || canvasProto.__workflowxQuickGroupMenu) return;
  const classicTargets = new WeakMap();
  const getCanvasMenuOptions = canvasProto.getCanvasMenuOptions;
  if (getCanvasMenuOptions) {
    canvasProto.getCanvasMenuOptions = function () {
      const options = getCanvasMenuOptions.apply(this, arguments);
      const group = classicTargets.get(this);
      return group && Array.isArray(options) ? [...options, null, ...makeActions(group)] : options;
    };
  }

  const original = canvasProto.processContextMenu;
  canvasProto.processContextMenu = function (node, event) {
    const graph = this.graph;
    const group = !node && graph?.getGroupOnPos?.(event.canvasX, event.canvasY);
    if (!group) return original.apply(this, arguments);
    if (!LiteGraph?.vueNodesMode) {
      classicTargets.set(this, group);
      try {
        return original.apply(this, arguments);
      } finally {
        classicTargets.delete(this);
      }
    }

    const result = original.apply(this, arguments);
    if (this.selectedItems?.size === 1 && this.selectedItems.has(group)) {
      requestAnimationFrame(() => {
        // Nodes 2.0 opens a Vue menu without calling LGraphGroup.getMenuOptions.
        // Match the native popover to this click so node and link menus are untouched.
        const menu = this.graph === graph && vueMenuAt(event);
        if (menu && this.selectedItems.size === 1 && this.selectedItems.has(group)) {
          appendVueGroupActions(menu, makeActions(group));
        }
      });
    }
    return result;
  };
  canvasProto.__workflowxQuickGroupMenu = true;
}
