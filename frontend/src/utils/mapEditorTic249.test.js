import test from "node:test";
import assert from "node:assert/strict";

import { tic249RawTargetVelocity } from "./mapEditorTic249.js";

test("tic249RawTargetVelocity scales steps per second to raw velocity", () => {
  assert.equal(tic249RawTargetVelocity(1000), "10,000,000");
});

test("tic249RawTargetVelocity returns dash for invalid input", () => {
  assert.equal(tic249RawTargetVelocity(0), "—");
  assert.equal(tic249RawTargetVelocity("n/a"), "—");
});
