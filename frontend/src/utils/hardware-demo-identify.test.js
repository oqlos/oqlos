import test from "node:test";
import assert from "node:assert/strict";

import { probeDemoDevices } from "./hardware-demo-identify.js";

const t = (_key, vars) => JSON.stringify(vars || {});

test("probeDemoDevices falls back to tic249 when pump probe fails", async () => {
  const result = await probeDemoDevices({
    identify: async () => ({
      adapters: [
        { id: "motor-dri0050", status: "ok" },
        { id: "motor-tic249", status: "ok" },
      ],
    }),
    runDiagnosticCommand: async () => {
      throw new Error("timeout");
    },
    deviceIds: ["motor-dri0050", "motor-tic249"],
    formatError: (err) => String(err.message || err),
    appendLog: () => {},
    t,
  });

  assert.equal(result?.deviceStatus["motor-dri0050"], "probe-failed");
  assert.equal(result?.fallbackDeviceId, "motor-tic249");
});
