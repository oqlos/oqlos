import test from "node:test";
import assert from "node:assert/strict";

import {
  evaluateConfigureSkip,
  isPluginHealthOk,
  pluginHealthEntry,
  portsLooselyMatch,
} from "./hardware-restart-configure-skip.js";

test("portsLooselyMatch accepts equal and basename-equal paths", () => {
  assert.equal(portsLooselyMatch("/dev/ttyUSB1", "/dev/ttyUSB1"), true);
  assert.equal(
    portsLooselyMatch(
      "/dev/serial/by-path/platform-3f980000.usb-usb-0:1.3:1.0-port0",
      "/dev/serial/by-path/platform-3f980000.usb-usb-0:1.3:1.0-port0",
    ),
    true,
  );
  assert.equal(portsLooselyMatch("", "/dev/ttyUSB1"), true);
  assert.equal(portsLooselyMatch("/dev/ttyUSB1", "/dev/ttyUSB2"), false);
});

test("isPluginHealthOk accepts connected/compatible", () => {
  assert.equal(isPluginHealthOk({ status: "connected" }), true);
  assert.equal(isPluginHealthOk({ compatible: true, status: "degraded" }), true);
  assert.equal(isPluginHealthOk({ status: "error" }), false);
});

test("evaluateConfigureSkip does NOT skip healthy baseline when plan wants higher baud", () => {
  // Commissioning: module answers at 9600, plan wants 115200 → must continue (ramp baud).
  const health = {
    "modbus-adc": {
      status: "connected",
      compatible: true,
      details: {
        serial_port: "/dev/serial/by-path/platform-3f980000.usb-usb-0:1.3:1.0-port0",
        baudrate: 9600,
        parity: "N",
        device_id: 1,
      },
    },
  };
  const decision = evaluateConfigureSkip({
    programTarget: {
      module_role: "modbus-adc",
      serial_port: "/dev/serial/by-path/platform-3f980000.usb-usb-0:1.3:1.0-port0",
      new_device_id: 1,
      new_baudrate: 115200,
      new_parity: "N",
    },
    healthPayload: health,
  });
  assert.equal(decision.skip, false);
  assert.equal(decision.reason, "baud-ramp-pending");
  assert.equal(decision.details.live_baudrate, 9600);
  assert.equal(decision.details.target_baudrate, 115200);
});

test("evaluateConfigureSkip skips only when live UART already equals target", () => {
  const health = {
    "modbus-adc": {
      status: "connected",
      compatible: true,
      details: {
        serial_port: "/dev/serial/by-path/platform-3f980000.usb-usb-0:1.3:1.0-port0",
        baudrate: 115200,
        parity: "N",
        device_id: 1,
      },
    },
  };
  const decision = evaluateConfigureSkip({
    programTarget: {
      module_role: "modbus-adc",
      serial_port: "/dev/serial/by-path/platform-3f980000.usb-usb-0:1.3:1.0-port0",
      new_device_id: 1,
      new_baudrate: 115200,
      new_parity: "N",
    },
    healthPayload: health,
  });
  assert.equal(decision.skip, true);
  assert.equal(decision.reason, "already_at_target");
});

test("evaluateConfigureSkip refuses device-id mismatch", () => {
  const health = {
    "modbus-adc": {
      status: "connected",
      compatible: true,
      details: { device_id: 2, baudrate: 9600, serial_port: "/dev/ttyUSB1" },
    },
  };
  const decision = evaluateConfigureSkip({
    programTarget: { module_role: "modbus-adc", new_device_id: 1, serial_port: "/dev/ttyUSB1" },
    healthPayload: health,
  });
  assert.equal(decision.skip, false);
  assert.equal(decision.reason, "device-id-mismatch");
});

test("pluginHealthEntry reads nested plugins map", () => {
  const entry = pluginHealthEntry(
    { plugins: { "modbus-io": { status: "connected" } } },
    "modbus-io",
  );
  assert.equal(entry.status, "connected");
});
