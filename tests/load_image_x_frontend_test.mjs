import assert from "node:assert/strict";
import test from "node:test";

import {
  filterCatalog,
  groupCatalog,
  higherNodeClipRects,
  isSquareDimensions,
  reconcileBatchSelection,
  splitRelativePath,
  thumbnailURL,
  viewURL,
} from "../web/js/load_image_x_helpers.mjs";

const items = [
  { path: "root.png", name: "root.png", folder: "", version: "v1" },
  { path: "Studio 1/cat image.png", name: "cat image.png", folder: "Studio 1", version: "v2" },
  { path: "__all/special.jpg", name: "special.jpg", folder: "__all", version: "v3" },
];

test("splits root and nested relative paths", () => {
  assert.deepEqual(splitRelativePath("root.png"), { folder: "", name: "root.png" });
  assert.deepEqual(splitRelativePath("Studio 1\\cat image.png"), { folder: "Studio 1", name: "cat image.png" });
});

test("groups root and folders with root first", () => {
  const groups = groupCatalog(items);
  assert.deepEqual(groups.map((group) => group.folder), ["", "__all", "Studio 1"]);
  assert.equal(groups[2].items[0].name, "cat image.png");
});

test("filters globally during search and exactly by selected folder", () => {
  assert.deepEqual(filterCatalog(items, "studio").map((item) => item.path), ["Studio 1/cat image.png"]);
  assert.deepEqual(filterCatalog(items, "", "__all").map((item) => item.path), ["__all/special.jpg"]);
  assert.equal(filterCatalog(items, "", null).length, 3);
});

test("builds encoded stable thumbnail and view URLs", () => {
  assert.equal(
    thumbnailURL(items[1]),
    "/workflowx_configurator/load_image_x/thumbnail?path=Studio%201%2Fcat%20image.png&v=v2",
  );
  assert.equal(
    viewURL(items[1]),
    "/view?filename=cat%20image.png&type=input&subfolder=Studio%201&v=v2",
  );
});

test("identifies thumbnails that need non-square padding", () => {
  assert.equal(isSquareDimensions(128, 128), true);
  assert.equal(isSquareDimensions(128, 127), true);
  assert.equal(isSquareDimensions(128, 96), false);
  assert.equal(isSquareDimensions(0, 128), false);
});

test("retains batch selections that still exist in the refreshed catalog", () => {
  assert.deepEqual(
    [...reconcileBatchSelection(new Set(["root.png", "missing.png"]), items)],
    ["root.png"],
  );
});

test("clips a deferred preview beneath nodes that are later in graph order", () => {
  const earlier = { pos: [10, 10], size: [20, 20] };
  const current = { pos: [100, 100], size: [220, 400] };
  const higherWithBounds = {
    pos: [140, 150],
    size: [80, 100],
    boundingRect: new Float32Array([140, 120, 80, 130]),
  };
  const higherFallback = { pos: [210, 260], size: [90, 110] };

  assert.deepEqual(
    higherNodeClipRects(current, [earlier, current, higherWithBounds, higherFallback], 30),
    [
      { x: 39, y: 19, width: 82, height: 132 },
      { x: 109, y: 129, width: 92, height: 142 },
    ],
  );
  assert.deepEqual(higherNodeClipRects(current, [earlier]), []);
});
