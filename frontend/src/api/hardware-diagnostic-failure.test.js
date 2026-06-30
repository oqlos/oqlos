import test from "node:test";
import assert from "node:assert/strict";

import { extractDiagnosticFailure } from "./hardware-diagnostic-failure.js";
import {
  isIdempotentTic249Deenergized,
  isIdempotentDiagnosticSuccess,
} from "./hardware-tic249-status.js";

test("idempotent tic249 deenergize yields no failure", () => {
  const payload = {
    ok: false,
    command: "motor_disable",
    result: { status: "de-energized", idempotent_success: true },
  };
  assert.equal(extractDiagnosticFailure(payload), "");
});

test("lung_stop stopped is idempotent success", () => {
  assert.equal(
    isIdempotentDiagnosticSuccess("lung_stop", { status: "stopped" }),
    true,
  );
});

test("ok=false surfaces nested tic249 connection error", () => {
  const payload = {
    ok: false,
    command: "status",
    result: { data: { connected: false } },
  };
  assert.equal(extractDiagnosticFailure(payload), "Tic249 motor is not connected");
});

test("success=false prefers specific nested error", () => {
  const payload = {
    ok: true,
    command: "reciprocate",
    result: { success: false, error: "USB timeout" },
  };
  assert.equal(extractDiagnosticFailure(payload), "USB timeout");
});

test("nested ok object failure for dri0050", () => {
  const payload = {
    ok: true,
    command: "pump_set",
    result: { ok: { success: false, error: "power_pct invalid" } },
  };
  assert.equal(extractDiagnosticFailure(payload), "power_pct invalid");
});

test("isIdempotentTic249Deenergized honors energized=false", () => {
  assert.equal(
    isIdempotentTic249Deenergized("disable", { data: { energized: false } }),
    true,
  );
});
