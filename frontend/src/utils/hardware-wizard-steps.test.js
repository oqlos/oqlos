import test from "node:test";
import assert from "node:assert/strict";

import { selectWizardProbeCandidate, wizardStepKind } from "./hardware-wizard-steps.js";

test("wizardStepKind classifies configure steps", () => {
  assert.equal(wizardStepKind({ step: "configure-modbus-io" }), "configure");
  assert.equal(wizardStepKind({ action: { type: "diagnostic" } }), "diagnostic");
});

test("selectWizardProbeCandidate returns sole candidate at target id", () => {
  const result = selectWizardProbeCandidate(
    [{ role: "modbus-io", device_id: 2, baudrate: 9600 }],
    { moduleRole: "modbus-io", newDeviceId: 2 },
  );
  assert.equal(result.candidate?.device_id, 2);
});

test("selectWizardProbeCandidate reports multiple modbus ids", () => {
  const result = selectWizardProbeCandidate(
    [
      { role: "modbus-io", device_id: 1 },
      { role: "modbus-io", device_id: 2 },
    ],
    { moduleRole: "modbus-io", newDeviceId: 2 },
  );
  assert.equal(result.error, "multiple_modbus_ids");
  assert.deepEqual(result.deviceIds, [1, 2]);
});
