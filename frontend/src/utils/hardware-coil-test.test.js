import assert from "node:assert/strict";
import test from "node:test";

import {
  buildCoilTestReport,
  coilCommandErrorCodes,
  coilCommandResultUrlArgs,
  coilPulseIntentUrlArgs,
  coilPulseRequestOptions,
  coilStopIntentUrlArgs,
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
  assert.equal(report.schema, "oqlos-boardnet-valve-controller-test-v2");
  assert.equal(report.coils[0].operator_result, "correct");
  assert.equal(report.coils[0].pulse.ok, true);
});

test("system role remains system and can access the guarded test", () => {
  assert.equal(normalizeConnectRole("system"), "system");
  assert.equal(isAdminConnectRole("system"), true);
  assert.equal(canConnectRoleAccessPath("/hardware-coils", "system"), true);
});

test("coil pulse request forwards only an accepted privileged role", () => {
  assert.deepEqual(coilPulseRequestOptions("admin", "coil-test-DO1"), {
    logContext: "coil-test-DO1",
    headers: { "X-Connect-Role": "admin" },
  });
  assert.deepEqual(coilPulseRequestOptions("administrator", "coil-test-DO1"), {
    logContext: "coil-test-DO1",
    headers: { "X-Connect-Role": "admin" },
  });
  assert.deepEqual(coilPulseRequestOptions("operator", "coil-test-DO1"), {
    logContext: "coil-test-DO1",
  });
});

test("coil command URL args preserve request intent and successful response", () => {
  const intent = coilPulseIntentUrlArgs({ id: "DO1", address: 0 }, "system");
  assert.deepEqual(intent, {
    COMMAND: "coil-test-pulse",
    COIL: "DO1",
    ADDRESS: "0",
    DURATION_MS: "300",
    CONFIRM: "PULSE_DO1",
    REQUEST_ROLE: "system",
  });
  assert.deepEqual(coilCommandResultUrlArgs(intent, "OK"), {
    ...intent,
    RESULT: "OK",
    HTTP_STATUS: "200",
    ERRORS: "NONE",
  });
  assert.deepEqual(coilStopIntentUrlArgs("administrator"), {
    COMMAND: "coil-test-stop",
    COILS: "ACTIVE-CONTROLLER",
    REQUEST_ROLE: "admin",
  });
});

test("coil command URL args expose normalized backend failures", () => {
  const error = Object.assign(new Error("Coil pulse requires the system or administrator role"), {
    status: 403,
    payload: { detail: { error_code: "C2004-AUTH-0002" } },
  });
  assert.deepEqual(coilCommandErrorCodes(error), [
    "C2004-AUTH-0002",
    "HTTP_403",
    "COIL_PULSE_ROLE_REQUIRED",
  ]);
  assert.equal(
    coilCommandResultUrlArgs({ COMMAND: "coil-test-pulse" }, "ERROR", error).ERRORS,
    "C2004-AUTH-0002,HTTP_403,COIL_PULSE_ROLE_REQUIRED",
  );
});
