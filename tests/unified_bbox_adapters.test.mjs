import assert from "node:assert/strict";
import test from "node:test";

import {
  bboxModeConfig,
  parseBBoxDocument,
  serializeBBoxDocument,
} from "../web/js/unified_bbox_adapters.mjs";

const neutral = {
  highLevelDescription: "poster",
  backgroundDescription: "plain background",
  summaryMeta: ["poster", "layout"],
  stylePalette: ["#112233"],
  detail: "deep",
  boxes: [{ type: "text", text: "EXACT", desc: "headline", palette: ["#ffffff"], x: 0.25, y: 0.125, w: 0.5, h: 0.25 }],
};

test("Ideogram and Krea adapters preserve their native coordinate order", () => {
  const ideogram = serializeBBoxDocument("ideogram4", neutral, 1024, 1024);
  const krea = serializeBBoxDocument("krea2", neutral, 1024, 1024);
  assert.deepEqual(ideogram.compositional_deconstruction.elements[0].bbox, [125, 250, 375, 750]);
  assert.deepEqual(krea.compositional_deconstruction.elements[0].bbox, [250, 125, 750, 375]);
  const normalized = { ...neutral.boxes[0], palette: ["#FFFFFF"] };
  assert.deepEqual(parseBBoxDocument("ideogram4", ideogram, 1024, 1024).boxes[0], normalized);
  assert.deepEqual(parseBBoxDocument("krea2", krea, 1024, 1024).boxes[0], normalized);
});

test("MOSS adapter emits and imports centered pixel yxyx on square and rectangular canvases", () => {
  for (const [width, height, expected] of [
    [1024, 1024, [-384, -256, -128, 256]],
    [1280, 768, [-288, -320, -96, 320]],
  ]) {
    const native = serializeBBoxDocument("moss_image", neutral, width, height);
    assert.equal(native.bbox_coord_space, "abs_centralized");
    assert.equal(native.bbox_format, "yxyx");
    assert.deepEqual(native.items[0].bbox, expected);
    const restored = parseBBoxDocument("moss_image", native, width, height);
    assert.deepEqual(restored.boxes[0], { ...neutral.boxes[0], palette: [] });
    assert.deepEqual(restored.summaryMeta, neutral.summaryMeta);
  }
  assert.equal(bboxModeConfig("moss_image").palette, false);
});
