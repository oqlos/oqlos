import assert from "node:assert/strict";
import test from "node:test";

import {
  buildCoilTestReport,
  nextUntestedCoil,
  pulseConfirmation,
} from "./hardware-coil-test.js";
import {
  canConnectRoleAccessPath,
  isAdminConnectRole,
  normalizeConnectRole,
} from "./rbac.policy.js";

test("nextUntestedCoil preserves physical DO order", () => {
  const coils = [{ address: 0 }, { address: 1 }, { address: 2 }];
  assert.deepEqual(nextUntestedCoil(coils, { "0": "correct" }), { address: 1 });
});

test("pulseConfirmation is tied to one-based DO label", () => {
  assert.equal(pulseConfirmation({ address: 7 }), "PULSE_DO8");
});

test("buildCoilTestReport joins operator and pulse results", () => {
  const report = buildCoilTestReport(
    { mode: "real", coils: [{ address: 0, id: "DO1" }] },
    { "0": "correct" },
    { "0": { ok: true } },
  );
  assert.equal(report.schema, "oqlos-boardnet-coil-test-v1");
  assert.equal(report.coils[0].operator_result, "correct");
  assert.equal(report.coils[0].pulse.ok, true);
});

test("system role remains system and can access the guarded test", () => {
  assert.equal(normalizeConnectRole("system"), "system");
  assert.equal(isAdminConnectRole("system"), true);
  assert.equal(canConnectRoleAccessPath("/hardware-coils", "system"), true);
});
