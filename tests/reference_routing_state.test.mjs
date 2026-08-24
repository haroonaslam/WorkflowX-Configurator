import assert from "node:assert/strict";
import test from "node:test";

import { referenceIsMuted } from "../web/js/reference_routing_state.mjs";

test("reference get remains active when both mute controls are false", () => {
  assert.equal(referenceIsMuted(false, false), false);
});

test("each reference get can mute independently", () => {
  assert.equal(referenceIsMuted(true, false), true);
  assert.equal(referenceIsMuted(false, false), false);
});

test("set reference mute globally overrides every matching get", () => {
  assert.equal(referenceIsMuted(false, true), true);
  assert.equal(referenceIsMuted(true, true), true);
});
