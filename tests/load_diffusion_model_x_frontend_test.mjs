import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  activateModelRow,
  defaultModelRow,
  modelFilenameStem,
  normalizeModelRow,
  removeModelRow,
  restoreModelRows,
} from "../web/js/load_diffusion_model_x_state.mjs";

const searchSource = readFileSync(new URL("../web/js/load_diffusion_model_x_search.js", import.meta.url), "utf8");
const searchUrl = `data:text/javascript;base64,${Buffer.from(searchSource).toString("base64")}`;
const { itemMatchesQuery } = await import(searchUrl);
const frontendSource = readFileSync(new URL("../web/js/load_diffusion_model_x.js", import.meta.url), "utf8");

const models = [
  {
    load_name: "Flux/flux-dev.safetensors",
    folder: "Flux",
    filename: "flux-dev.safetensors",
    display_name: "Flux Dev",
    base_model: "Flux.1 D",
    tags: ["image", "dev"],
  },
  {
    load_name: "Video/Wan_2.2.gguf",
    folder: "Video",
    filename: "Wan_2.2.gguf",
    display_name: "Wan 2.2",
    metadata: { model_name: "Wan Video", sub_type: "diffusion_model" },
  },
];

test("diffusion model search covers paths and optional manager metadata", () => {
  assert.equal(itemMatchesQuery(models[0], "flux dev"), true);
  assert.equal(itemMatchesQuery(models[0], "flux image"), true);
  assert.equal(itemMatchesQuery(models[1], "wan video"), true);
  assert.equal(itemMatchesQuery(models[1], "flux"), false);
});

test("restoration keeps exactly the first active model", () => {
  const rows = restoreModelRows([
    { on: false, load_name: "A.safetensors" },
    { on: true, load_name: "B.safetensors" },
    { on: true, load_name: "C.safetensors" },
  ]);
  assert.deepEqual(rows.map((row) => row.on), [false, true, false]);
});

test("restoration promotes the first model when legacy state has none active", () => {
  const rows = restoreModelRows([
    { on: false, load_name: "A.safetensors" },
    { on: false, load_name: "B.safetensors" },
  ]);
  assert.deepEqual(rows.map((row) => row.on), [true, false]);
});

test("activation and active-row removal preserve radio semantics", () => {
  const rows = [defaultModelRow({ load_name: "A.safetensors" }, true), defaultModelRow({ load_name: "B.safetensors" }, false)];
  const activated = activateModelRow(rows, 1);
  assert.deepEqual(activated.map((row) => row.on), [false, true]);
  const remaining = removeModelRow(activated, 1);
  assert.equal(remaining.length, 1);
  assert.equal(remaining[0].load_name, "A.safetensors");
  assert.equal(remaining[0].on, true);
});

test("node rows always display the real filename without its final extension", () => {
  assert.equal(modelFilenameStem("Minimax H3/minimax_h3_ref2va_pruned_bf16.safetensors"), "minimax_h3_ref2va_pruned_bf16");
  assert.equal(modelFilenameStem({ filename: "wan2.2.high.gguf" }), "wan2.2.high");
  assert.equal(
    defaultModelRow({
      load_name: "Minimax H3/minimax_h3_ref2va_pruned_bf16.safetensors",
      display_name: "Minimax",
      model_name: "H3 Eros Max",
    }).display_name,
    "minimax_h3_ref2va_pruned_bf16",
  );
  assert.equal(
    normalizeModelRow({
      load_name: "Minimax H3/minimax_h3_hybrid_fl2va_ref2va_b25-49-int8.safetensors",
      display_name: "Minimax",
    }).display_name,
    "minimax_h3_hybrid_fl2va_ref2va_b25-49-int8",
  );
});

test("frontend includes native-compatible rows, enrichment fallback, and dynamic sizing", () => {
  for (const token of [
    'import { app } from "../../scripts/app.js"',
    'const NODE_TYPE = "KVGC_LoadDiffusionModelX"',
    'const CATALOG_ROUTE = "/workflowx_configurator/load_diffusion_model_x/models"',
    'const MANAGER_LIST_ROUTE = "/api/lm/checkpoints/list"',
    'model_type: "diffusion_model"',
    'return `diffusion_model_${node.__dmxCounter}`',
    'node.serialize_widgets = true',
    'restoreNodeWidthSoon(node, targetWidth)',
    '"+ Add Diffusion Model"',
    'openDetails(selected, selectAndClose)',
    'renderRichTextContent(text, description)',
    'sanitizeRichTextNode(sourceNode)',
    'function rowFilenameStem(value)',
    'refresh.addEventListener("click", () => reload(true))',
  ]) assert.ok(frontendSource.includes(token), `missing ${token}`);
});

test("frontend remains loadable with the pre-filename-fix state module export surface", () => {
  const stateImport = frontendSource.match(/import\s*\{([^}]*)\}\s*from\s*"\.\/load_diffusion_model_x_state\.mjs"/u);
  assert.ok(stateImport, "missing state module import");
  const importedNames = stateImport[1]
    .split(",")
    .map((name) => name.trim())
    .filter(Boolean)
    .sort();
  assert.deepEqual(importedNames, [
    "activateModelRow",
    "defaultModelRow",
    "normalizeModelRow",
    "removeModelRow",
    "restoreModelRows",
  ]);
});
