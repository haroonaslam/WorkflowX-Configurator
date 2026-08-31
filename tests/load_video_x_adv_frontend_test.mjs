import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

import {
  DEFAULT_VIDEO_STATE,
  clearForVideoChange,
  computeOutputDimensions,
  isNativeVideoPreviewWidgetName,
  normalizeTrimRange,
  normalizeVideoState,
  requestedOutputsFromPrompt,
  videoViewURL,
  withRequestedOutputsState,
} from "../web/js/load_video_x_adv_helpers.mjs";
import { graphDockScreenRect } from "../web/js/workflowx_graph_dock.mjs";


test("migrates malformed and partial state", () => {
  const malformed = normalizeVideoState("not-json");
  assert.deepEqual(malformed, DEFAULT_VIDEO_STATE);
  const migrated = normalizeVideoState(JSON.stringify({ mode: "fit_inside", fit_w: 768, short_mode: "legacy-value", trim_start: 1.25 }));
  assert.equal(migrated.mode, "fit_inside");
  assert.equal(migrated.fit_w, 768);
  assert.equal("short_mode" in migrated, false);
  assert.equal(migrated.trim_start, 1.25);
});

test("changing video resets trim and crop but retains geometry", () => {
  const state = clearForVideoChange({
    ...DEFAULT_VIDEO_STATE, mode: "pad", pad_left: 12, output_snap: 16,
    trim_start: 2, trim_end: 4,
    crop_enabled: true, crop_rect: { x: .1, y: .1, w: .5, h: .5 },
  });
  assert.equal(state.trim_start, 0); assert.equal(state.trim_end, null); assert.equal(state.crop_rect, null);
  assert.equal(state.mode, "pad"); assert.equal(state.pad_left, 12); assert.equal(state.output_snap, 16);
});

test("unwired trim handles resize independently and snap to average-fps frames", () => {
  const metadata = { duration: 10, fps: 24 };
  const range = normalizeTrimRange(metadata, { ...DEFAULT_VIDEO_STATE, trim_start: 1.011, trim_end: 3.03 });
  assert.deepEqual(range, { start: 1, end: 3.041667, fixed: false });
});

test("wired seconds locks range length and slides it inside the source", () => {
  const metadata = { duration: 10, fps: 10 };
  const startMoved = normalizeTrimRange(metadata, { ...DEFAULT_VIDEO_STATE, trim_start: 8, trim_end: 9 }, 3, "start");
  assert.deepEqual(startMoved, { start: 7, end: 10, fixed: true });
  const endMoved = normalizeTrimRange(metadata, { ...DEFAULT_VIDEO_STATE, trim_start: 2, trim_end: 4 }, 3, "end");
  assert.deepEqual(endMoved, { start: 1, end: 4, fixed: true });
  const shortSource = normalizeTrimRange({ duration: 2, fps: 10 }, DEFAULT_VIDEO_STATE, 3);
  assert.deepEqual(shortSource, { start: 0, end: 2, fixed: true });
});

test("crop, geometry, and output snapping use ImageX Adv parity helpers", () => {
  const result = computeOutputDimensions(200, 100, {
    ...DEFAULT_VIDEO_STATE, crop_enabled: true, crop_snap: 16,
    crop_rect: { x: .11, y: .1, w: .51, h: .72 }, mode: "scale_factor", scale_factor: .5, output_snap: 8,
  });
  assert.deepEqual(result, { width: 48, height: 40, crop: { x: 22, y: 10, w: 96, h: 80 } });
});

test("prompt links generate an ordered transient media-output mask", () => {
  const output = {
    1: { class_type: "WorkflowX_LoadVideoXAdv", inputs: { workflowx_state: "{}" } },
    2: { inputs: { frames: ["1", 1] } },
    3: { inputs: { nested: { audio: [1, 2] } } },
    4: { inputs: { width: ["1", 3] } },
  };
  assert.deepEqual(requestedOutputsFromPrompt(output, "1"), ["video_frames", "audio"]);
  const serialized = JSON.parse(withRequestedOutputsState("{}", ["audio", "video_frames"]));
  assert.deepEqual(serialized.requested_outputs, ["video_frames", "audio"]);
});

test("video paths produce native ComfyUI input URLs", () => {
  assert.equal(videoViewURL("phone/clips/take 1.mov", "abc"), "/view?filename=take+1.mov&type=input&subfolder=phone%2Fclips&v=abc");
});

test("recognizes both legacy and Vue native video preview widget names", () => {
  for (const name of ["videopreview", "video_preview", "video-preview", "VIDEO-PREVIEW"]) {
    assert.equal(isNativeVideoPreviewWidgetName(name), true);
  }
  assert.equal(isNativeVideoPreviewWidgetName("image-preview"), false);
});

test("frontend uses the native player crop overlay, accessible trim controls, and prompt-time injection", () => {
  const source = fs.readFileSync(new URL("../web/js/load_video_x_adv.js", import.meta.url), "utf8");
  assert.match(source, /Math\.min\(14,/);
  assert.match(source, /player\.currentTime >= Math\.min\(ui\.metadata\.duration, range\.end\)/);
  assert.match(source, /snapCropRect\(rect/);
  assert.match(source, /root\?\.closest\?\.\("\[data-node-id\]"\)/);
  assert.match(source, /\.video-preview video/);
  assert.match(source, /isNativeVideoPreviewWidgetName\(name\)/);
  assert.match(source, /findNativeVideoPreview\(node, root\)/);
  assert.match(source, /host\.append\(canvas, cropSurface, help\)/);
  assert.match(source, /cropSurface\.style\.pointerEvents = "auto"/);
  assert.match(source, /event\.clientY >= rect\.bottom - 44/);
  assert.match(source, /cropSurface\.addEventListener\("click"/);
  assert.match(source, /beginRangeDrag\(event, "start"\)/);
  assert.match(source, /workflowx-lvxa-trim-selection/);
  assert.match(source, /scrubber\.addEventListener\("input"/);
  assert.match(source, /Selection seconds/);
  assert.match(source, /durationInput\.disabled = wired/);
  assert.match(source, /ui\.reflow\(\)/);
  assert.match(source, /visible\.reduce\(\(sum, child\) => sum \+ child\.offsetHeight/);
  assert.match(source, /getMinHeight: \(\) => ui\.layoutHeight/);
  assert.match(source, /getMaxHeight: \(\) => ui\.layoutHeight/);
  assert.match(source, /maxHeight: ui\.layoutHeight/);
  assert.match(source, /\.workflowx-lvxa-help\{position:absolute;left:50%;top:8px/);
  assert.match(source, /transform:translateX\(-50%\)/);
  assert.doesNotMatch(source, /Short source:|Pad last frame/);
  assert.doesNotMatch(source, /stage\.append\(preview/);
  assert.doesNotMatch(source, /ctx\.drawImage\(ui\.preview/);
  assert.match(source, /app\.graphToPrompt = async function/);
  assert.match(source, /entry\.inputs\.workflowx_state = withRequestedOutputsState/);
  assert.match(source, /loadVideo\("restore"\)/);
  const restoreBody = source.match(/ui\.restore = \(\) => \{([\s\S]*?)\n  \};/)?.[1] || "";
  assert.doesNotMatch(restoreBody, /markChanged|graph\?\.change|stateWidget\.callback/);
});

test("shared graph dock persists independent geometry and supports all window modes", () => {
  const source = fs.readFileSync(new URL("../web/js/workflowx_graph_dock.mjs", import.meta.url), "utf8");
  assert.match(source, /node\.properties\[dock\.propertyKey\]/);
  assert.match(source, /dock\.locked/); assert.match(source, /dock\.minimized/); assert.match(source, /dock\.fullscreen/);
  assert.match(source, /setPointerCapture\?\.\(pointerId\)/);
  assert.match(source, /\(next\.buttons & 1\) === 0/);
  assert.doesNotMatch(source, /window\.addEventListener\("pointermove", move\)/);
  assert.match(source, /resolveCanvasLayer\(dock\)/);
  assert.match(source, /layerHost\.appendChild\(dock\.element\)/);
  assert.match(source, /ownerElement/);
  for (const edge of ["n", "e", "s", "w", "ne", "se", "sw", "nw"]) assert.match(source, new RegExp(`"${edge}"`));
  const videoSource = fs.readFileSync(new URL("../web/js/load_video_x_adv.js", import.meta.url), "utf8");
  assert.match(videoSource, /propertyKey: "workflowx_video_timeline_dock"/);
  assert.match(videoSource, /ownerElement: ui\.root/);
  const unifiedSource = fs.readFileSync(new URL("../web/js/unified_autoprompter.js", import.meta.url), "utf8");
  assert.match(unifiedSource, /graphDockScreenRect\(app, node, graph\)/);
});

test("shared dock transform retains Unified's graph-relative geometry", () => {
  const app = { canvas: { ds: { scale: 2, offset: [10, 20] }, canvas: { getBoundingClientRect: () => ({ left: 5, top: 7 }) } } };
  assert.deepEqual(graphDockScreenRect(app, { pos: [100, 200] }, { x: 30, y: 40 }), { left: 285, top: 527, scale: 2 });
});
