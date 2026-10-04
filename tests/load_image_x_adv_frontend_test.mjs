import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_ADV_STATE,
  clearCropForImageChange,
  computeOutputDimensions,
  cropSnapVisible,
  normalizeAdvState,
  normalizedRect,
  pixelRectFromState,
  snapCropRect,
} from "../web/js/load_image_x_adv_helpers.mjs";
import { splitAnnotatedPath, viewURL } from "../web/js/load_image_x_helpers.mjs";
import fs from "node:fs";

test("Direct mode survives image-change normalization and uses a versioned state helper", () => {
  const state=normalizeAdvState({load_mode:"direct",crop_rect:{x:0,y:0,w:.5,h:.5}});
  const changed=clearCropForImageChange(state);
  assert.equal(changed.load_mode,"direct");
  assert.equal(changed.crop_rect,null);
  assert.equal(normalizeAdvState(JSON.stringify(changed)).load_mode,"direct");
  const source=fs.readFileSync(new URL('../web/js/load_image_x_adv.js',import.meta.url),'utf8');
  assert.match(source,/load_image_x_adv_helpers\.mjs\?v=direct-mode-2/);
  assert.match(source,/stateWidget\.serializeValue = \(\) => JSON\.stringify\(ui\.state\)/);
});

test("normalizes malformed state to independent defaults", () => {
  const state = normalizeAdvState("not json");
  assert.deepEqual(state, DEFAULT_ADV_STATE);
  assert.equal(state.crop_enabled, false);
  assert.equal(state.allow_upscale, false);
});

test("crop snap changes size while preserving free pixel position", () => {
  const state = {
    ...DEFAULT_ADV_STATE,
    crop_enabled: true,
    crop_snap: 16,
    crop_rect: { x: 0.13, y: 0.07, w: 0.27, h: 0.34 },
  };
  assert.deepEqual(pixelRectFromState(100, 100, state), { x: 13, y: 7, w: 32, h: 32 });
});

test("resizing a crop can preserve the opposite corner", () => {
  assert.deepEqual(
    snapCropRect({ x: 13, y: 7, w: 27, h: 34 }, 100, 100, 16, "bottom-right"),
    { x: 8, y: 9, w: 32, h: 32 },
  );
  assert.deepEqual(normalizedRect({ x: 8, y: 9, w: 32, h: 32 }, 100, 100), {
    x: 0.08, y: 0.09, w: 0.32, h: 0.32,
  });
});

test("crop is applied before resize and output snap", () => {
  const result = computeOutputDimensions(200, 100, {
    ...DEFAULT_ADV_STATE,
    crop_enabled: true,
    crop_snap: 16,
    crop_rect: { x: 0.11, y: 0.1, w: 0.51, h: 0.72 },
    mode: "scale_factor",
    scale_factor: 0.5,
    output_snap: 8,
  });
  assert.deepEqual(result, { width: 48, height: 40, crop: { x: 22, y: 10, w: 96, h: 80 } });
});

test("crop snap visibility follows the crop toggle", () => {
  assert.equal(cropSnapVisible(DEFAULT_ADV_STATE), false);
  assert.equal(cropSnapVisible({ ...DEFAULT_ADV_STATE, crop_enabled: true }), true);
});

test("changing images clears only the crop rectangle", () => {
  const state = clearCropForImageChange({
    ...DEFAULT_ADV_STATE,
    crop_enabled: true,
    crop_snap: 32,
    mode: "fit_inside",
    fit_w: 768,
    crop_rect: { x: 0.1, y: 0.2, w: 0.3, h: 0.4 },
  });
  assert.equal(state.crop_rect, null);
  assert.equal(state.crop_enabled, true);
  assert.equal(state.crop_snap, 32);
  assert.equal(state.mode, "fit_inside");
  assert.equal(state.fit_w, 768);
});

test("dimension preview covers all resize modes", () => {
  const cases = [
    [{ mode: "off" }, [320, 240]],
    [{ mode: "max_mp", max_mp: 0.01 }, [118, 89]],
    [{ mode: "longest_side", longest_side: 160 }, [160, 120]],
    [{ mode: "scale_factor", scale_factor: 0.5 }, [160, 120]],
    [{ mode: "fit_inside", fit_w: 100, fit_h: 100 }, [100, 75]],
    [{ mode: "cover", cover_w: 100, cover_h: 100, cover_action: "fill" }, [100, 100]],
    [{ mode: "cover", cover_w: 100, cover_h: 80, cover_action: "crop" }, [100, 80]],
    [{ mode: "match_ratio", ratio_w: 1, ratio_h: 1 }, [240, 240]],
    [{ mode: "pad", pad_left: 10, pad_right: 20, pad_top: 5, pad_bottom: 15 }, [350, 260]],
  ];
  for (const [updates, expected] of cases) {
    const result = computeOutputDimensions(320, 240, { ...DEFAULT_ADV_STATE, ...updates });
    assert.deepEqual([result.width, result.height], expected);
  }
});

test("dimension preview preserves tiny sources when output snapping is off", () => {
  assert.deepEqual(computeOutputDimensions(4, 2, DEFAULT_ADV_STATE), { width: 4, height: 2, crop: null });
});

test("annotated image paths produce the correct native ComfyUI view URL", () => {
  assert.deepEqual(splitAnnotatedPath("folder/frame.png [output]"), { path: "folder/frame.png", type: "output" });
  assert.deepEqual(splitAnnotatedPath("frame.png"), { path: "frame.png", type: "input" });
  assert.equal(
    viewURL({ path: "renders/final.png [temp]", version: "7" }),
    "/view?filename=final.png&type=temp&subfolder=renders&v=7",
  );
});

test("advanced UI uses dynamic mode and crop rows without fixed placeholder height", () => {
  const source = fs.readFileSync(new URL("../web/js/load_image_x_adv.js", import.meta.url), "utf8");
  assert.doesNotMatch(source, /UI_HEIGHT|825px|height:\s*165px|crop-hidden|visibility:\s*hidden/);
  assert.match(source, /if \(ui\.state\.mode === "off"\) return;/);
  assert.match(source, /else cropSnap\.remove\(\)/);
  assert.match(source, /getMaxHeight: \(\) => Infinity/);
});

test("crop pointer handling is primary-button only and native state remains populated", () => {
  const source = fs.readFileSync(new URL("../web/js/load_image_x_adv.js", import.meta.url), "utf8");
  assert.match(source, /event\.button !== 0 \|\| !event\.isPrimary/);
  assert.match(source, /node\.imgs = \[image\]/);
  assert.match(source, /node\.imageIndex = 0/);
});

test("custom preview opens ComfyUI's native node menu", () => {
  const source = fs.readFileSync(new URL("../web/js/load_image_x_adv.js", import.meta.url), "utf8");
  assert.match(source, /root\.addEventListener\("contextmenu"/);
  assert.match(source, /app\.canvas\?\.getNodeMenuOptions\?\.\(node\)/);
  assert.match(source, /new ContextMenu\(options, \{ event, title: node\.type, extra: node \}\)/);
});

test("advanced image source row exposes thumbnail browsing and owned upload", () => {
  const source = fs.readFileSync(new URL("../web/js/load_image_x_adv.js", import.meta.url), "utf8");
  assert.match(source, /workflowx-lixa-source-actions/);
  assert.match(source, /grid-template-columns:repeat\(2,minmax\(0,1fr\)\)/);
  assert.match(source, /button\("Browse Thumbnails"/);
  assert.match(source, /button\("Upload Photo"/);
  assert.match(source, /upload.addEventListener\("click", \(\) => fileInput.click\(\)\)/);
  assert.match(source, /root\.append\(sourceActions, modes, outputSnap, resample, toggles, preview\)/);
});

test("advanced image UI accepts dropped image files through ComfyUI's upload endpoint", () => {
  const source = fs.readFileSync(new URL("../web/js/load_image_x_adv.js", import.meta.url), "utf8");
  assert.match(source, /root\.addEventListener\("dragenter"/);
  assert.match(source, /root\.addEventListener\("dragover"/);
  assert.match(source, /root\.addEventListener\("dragleave"/);
  assert.match(source, /root\.addEventListener\("drop", async/);
  assert.match(source, /fetch\(endpoint, \{ method: "POST", body: form \}\)/);
  assert.match(source, /form\.append\("type", "input"\)/);
  assert.match(source, /ui\.pendingBrowserSelection = true/);
  assert.match(source, /imageWidget\.callback\?\.\(selected\)/);
  assert.match(source, /Drop image to load/);
});

test("load mode defaults, validation and serialized snapshots", () => {
  assert.equal(normalizeAdvState('{}').load_mode, 'normal');
  assert.equal(normalizeAdvState({load_mode: 'invalid'}).load_mode, 'normal');
  const state = normalizeAdvState({load_mode: 'direct', mode: 'pad', resample: 'lanczos'});
  assert.deepEqual(normalizeAdvState(JSON.stringify(state)), state);
  assert.equal(state.mode, 'pad');
  assert.equal(state.load_mode, 'direct');
});

test("compact controls and all image ingestion paths share the mode-aware queue", () => {
  const source = fs.readFileSync(new URL("../web/js/load_image_x_adv.js", import.meta.url), "utf8");
  assert.doesNotMatch(source, /shiftResample|Previous resampling filter|Next resampling filter/);
  assert.match(source, /resample.append\(select, loadMode\)/);
  assert.match(source, /uploadQueue = uploadQueue.then/);
  assert.match(source, /crypto.randomUUID/);
  assert.match(source, /window.addEventListener\("paste", pasteImage, true\)/);
  assert.match(source, /window.removeEventListener\("paste", pasteImage, true\)/);
  assert.match(source, /event.stopImmediatePropagation\(\)/);
  assert.match(source, /selectedNodes.length === 1/);
  assert.equal((source.match(/ingestImage\(file\)/g) || []).length, 4);
});

test("advanced UI is user-resizable and reflows narrow control grids", () => {
  const source = fs.readFileSync(new URL("../web/js/load_image_x_adv.js", import.meta.url), "utf8");
  assert.match(source, /const MIN_WIDTH = 300/);
  assert.match(source, /container-type:inline-size/);
  assert.match(source, /@container \(max-width:430px\)/);
  assert.match(source, /workflowx-lixa-modes \{ grid-template-columns:repeat\(2,minmax\(0,1fr\)\)/);
  assert.match(source, /workflowx-lixa-quick, \.workflowx-lixa-ratios \{ grid-template-columns:repeat\(3,minmax\(0,1fr\)\)/);
  assert.match(source, /ui\.resizeObserver\.observe\(root\)/);
  assert.match(source, /node\.resizable = true/);
  assert.match(source, /workflowx-lixa-resize-handle/);
  assert.match(source, /resizeHandle\.addEventListener\("pointerdown"/);
  assert.match(source, /bounds\.width \/ Math\.max\(1, root\.offsetWidth\)/);
  assert.match(source, /node\.setSize\?\.\(\[width, height\]\)/);
});

test("advanced extension is auto-discovered without a duplicate side-effect import", () => {
  const browserSource = fs.readFileSync(new URL("../web/js/load_image_x.js", import.meta.url), "utf8");
  assert.doesNotMatch(browserSource, /import\s+["']\.\/load_image_x_adv\.js/);
});
