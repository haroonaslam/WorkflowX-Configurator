import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  activateModelRow,
  applyModelIdentity,
  defaultModelRow,
  modelItemFileSize,
  modelItemSha256,
  modelFilenameStem,
  normalizeModelRow,
  normalizeSha256,
  removeModelRow,
  restoreModelRows,
  sortedModelHashMatches,
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

test("model identities serialize and remap without changing active state", () => {
  const hash = "a".repeat(64);
  assert.equal(normalizeSha256(hash.toUpperCase()), hash);
  assert.equal(modelItemSha256({ metadata: { sha256: hash } }), hash);
  assert.equal(modelItemFileSize({ metadata: { file_size: "123" } }), 123);

  const row = defaultModelRow({ load_name: "Old/model.safetensors", sha256: hash, file_size: 123 }, true);
  assert.equal(row.sha256, hash);
  assert.equal(row.file_size, 123);
  const restored = restoreModelRows([row]);
  assert.equal(restored[0].sha256, hash);
  assert.equal(restored[0].file_size, 123);
  assert.equal(restored[0].on, true);
  const remapped = applyModelIdentity(row, {
    load_name: "New/model.safetensors",
    folder: "New",
    sha256: hash,
    file_size: 123,
  });
  assert.equal(remapped.load_name, "New/model.safetensors");
  assert.equal(remapped.unet_name, "New/model.safetensors");
  assert.equal(remapped.on, true);

  const matches = sortedModelHashMatches([
    { load_name: "Z/model.safetensors", sha256: hash },
    { load_name: "A/model.safetensors", metadata: { sha256: hash } },
  ], hash);
  assert.deepEqual(matches.map((item) => item.load_name), ["A/model.safetensors", "Z/model.safetensors"]);
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
    'const HASH_ROUTE = "/workflowx_configurator/load_diffusion_model_x/hash"',
    'const REMAP_ROUTE = "/workflowx_configurator/load_diffusion_model_x/remap"',
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
    'const tooltip = "Remap moved diffusion models"',
    'async function remapModelRows(node)',
  ]) assert.ok(frontendSource.includes(token), `missing ${token}`);

  const remapSource = frontendSource.slice(frontendSource.indexOf("async function remapModelRows"), frontendSource.indexOf("function activateRow"));
  assert.doesNotMatch(remapSource, /resizeNode\(|setupNode\(/);
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
    "applyModelIdentity",
    "defaultModelRow",
    "modelItemFileSize",
    "modelItemSha256",
    "normalizeModelRow",
    "normalizeSha256",
    "removeModelRow",
    "restoreModelRows",
    "sortedModelHashMatches",
  ]);
});

test("picker cards prioritize a fully wrapping filename in the taller layout", () => {
  assert.match(frontendSource, /workflowx-dmx-card\{[^}]*min-height:156px/);
  assert.match(frontendSource, /workflowx-dmx-filename\{[^}]*overflow-wrap:anywhere/);
  assert.match(frontendSource, /body\.append\(filename, name, path, meta\)/);
});

test("picker cards omit the redundant diffusion model type chip", () => {
  assert.match(frontendSource, /replace\(\/\[\^a-z0-9\]\+\/g, ""\) !== "diffusionmodel"/);
  assert.doesNotMatch(frontendSource, /\[item\.base_model, item\.sub_type, formatFileSize/);
});
