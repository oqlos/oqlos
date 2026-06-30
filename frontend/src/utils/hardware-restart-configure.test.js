import test from "node:test";
import assert from "node:assert/strict";

import { resolveWizardProbeCandidate } from "./hardware-restart-probe-select.js";

const t = (key, vars) => `${key}:${vars?.ids || ""}`;

test("resolveWizardProbeCandidate returns sole candidate", () => {
  const candidate = resolveWizardProbeCandidate(
    { candidates: [{ role: "modbus-io", device_id: 2 }] },
    "modbus-io",
    { new_device_id: 2 },
    false,
    t,
  );
  assert.equal(candidate.device_id, 2);
});

test("resolveWizardProbeCandidate throws on multiple modbus ids", () => {
  assert.throws(
    () => resolveWizardProbeCandidate(
      { candidates: [{ device_id: 1 }, { device_id: 2 }] },
      "modbus-io",
      { new_device_id: 2 },
      false,
      t,
    ),
    /multipleModbusIdsError/,
  );
});
