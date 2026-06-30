import test from "node:test";
import assert from "node:assert/strict";

import { resolveStepAdvance } from "./hardware-restart-step-outcome.js";

test("resolveStepAdvance advances optional rtc steps on failure", () => {
  const step = { step: "reconfigure-rtc", action: { peripheral_id: "rtc" } };
  const result = resolveStepAdvance(false, step);
  assert.equal(result.advanceOk, true);
  assert.equal(result.optionalSkip, true);
});

test("resolveStepAdvance blocks required step failures", () => {
  const step = { step: "configure-modbus-io" };
  const result = resolveStepAdvance(false, step);
  assert.equal(result.advanceOk, false);
});
