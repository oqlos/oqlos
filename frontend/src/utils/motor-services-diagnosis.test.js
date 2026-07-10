import assert from "node:assert/strict";
import test from "node:test";

import { filterMotorDiagnosis, filterMotorRepairs } from "./motor-services-diagnosis.js";

test("filterMotorDiagnosis keeps only motor devices and drops modbus global actions", () => {
  const filtered = filterMotorDiagnosis({
    devices: {
      "modbus-adc": { device_id: "modbus-adc" },
      "motor-tic249": { device_id: "motor-tic249" },
    },
    global_actions: [
      { id: "global-modbus-recover", device_id: "*" },
      { id: "tic249-ensure-sidecar", device_id: "motor-tic249" },
    ],
  });
  assert.deepEqual(Object.keys(filtered.devices), ["motor-tic249"]);
  assert.equal(filtered.global_actions.length, 1);
  assert.equal(filtered.global_actions[0].id, "tic249-ensure-sidecar");
});

test("filterMotorRepairs keeps only motor repair steps", () => {
  const filtered = filterMotorRepairs([
    { step: "reconnect-modbus-adc", ok: true },
    { step: "reconnect-motor-tic249", ok: true },
  ]);
  assert.equal(filtered.length, 1);
  assert.equal(filtered[0].step, "reconnect-motor-tic249");
});
