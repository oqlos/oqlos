import test from "node:test";
import assert from "node:assert/strict";

import {
  adapterStatusBadgeClass,
  extractHardwareDiagnostics,
  hardwareStatusSummary,
  listHardwareAdapters,
} from "./hardwareStatusModel.js";

test("adapterStatusBadgeClass maps status to badge classes", () => {
  assert.match(adapterStatusBadgeClass("ok"), /hw-badge-ok/);
  assert.match(adapterStatusBadgeClass("error"), /hw-badge-err/);
  assert.match(adapterStatusBadgeClass("adapter-only"), /hw-badge-warn/);
});

test("extractHardwareDiagnostics reads nested probe data", () => {
  const diagnostics = extractHardwareDiagnostics({
    diagnostics: {
      serial_ports: ["/dev/ttyUSB0"],
      i2c_buses: [1],
      usb_devices: [{ id: "1a86" }],
    },
  });
  assert.deepEqual(diagnostics.serialPorts, ["/dev/ttyUSB0"]);
  assert.deepEqual(diagnostics.i2cBuses, [1]);
  assert.deepEqual(diagnostics.usbDevices, [{ id: "1a86" }]);
});

test("hardwareStatusSummary prefers identify mode over health", () => {
  const summary = hardwareStatusSummary(
    { mode: "health-mode", transport: "mqtt" },
    { mode: "identify-mode", detected: 2, total: 3 },
  );
  assert.equal(summary.mode, "identify-mode");
  assert.equal(summary.detected, 2);
  assert.equal(summary.transport, "mqtt");
});

test("listHardwareAdapters returns array or empty list", () => {
  assert.equal(listHardwareAdapters({ adapters: [{ id: "adc" }] }).length, 1);
  assert.deepEqual(listHardwareAdapters(null), []);
});
