import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../web/js/lorax_identity.js", import.meta.url), "utf8");
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const { applyIdentity, itemFileSize, itemSha256, normalizeSha256, sortedHashMatches } = await import(moduleUrl);

const hash = "a".repeat(64);
assert.equal(normalizeSha256(hash.toUpperCase()), hash);
assert.equal(normalizeSha256("not-a-hash"), "");
assert.equal(itemSha256({ metadata: { sha256: hash } }), hash);
assert.equal(itemFileSize({ metadata: { file_size: "123" } }), 123);

const matches = sortedHashMatches(
  [
    { load_name: "Z/moved.safetensors", sha256: hash },
    { load_name: "A/moved.safetensors", metadata: { sha256: hash } },
    { load_name: "Other.safetensors", sha256: "b".repeat(64) },
  ],
  hash,
);
assert.deepEqual(matches.map((item) => item.load_name), ["A/moved.safetensors", "Z/moved.safetensors"]);

const original = {
  on: false,
  load_name: "Old/name.safetensors",
  lora: "Old/name.safetensors",
  strength: 0.65,
  trigger_words: ["keep me"],
};
const updated = applyIdentity(original, {
  load_name: "New/name.safetensors",
  folder: "New",
  file_stem: "name",
  sha256: hash,
  file_size: 456,
});
assert.equal(updated.load_name, "New/name.safetensors");
assert.equal(updated.lora, "New/name.safetensors");
assert.equal(updated.sha256, hash);
assert.equal(updated.file_size, 456);
assert.equal(updated.on, false);
assert.equal(updated.strength, 0.65);
assert.deepEqual(updated.trigger_words, ["keep me"]);

console.log("PASS LoraX identity helper tests");
