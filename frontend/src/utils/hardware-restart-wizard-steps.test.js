import test from "node:test";
import assert from "node:assert/strict";

import {
  buildWizardProbePayload,
  wizardStepSerialPort,
} from "./hardware-restart-wizard-helpers.js";

test("wizardStepSerialPort prefers step serial_port", () => {
  const plan = { io_serial_port: "/dev/ttyUSB0", serial_port: "/dev/ttyUSB1" };
  const step = { serial_port: "/dev/ttyAMA0" };
  assert.equal(wizardStepSerialPort(plan, step), "/dev/ttyAMA0");
});

test("wizardStepSerialPort uses adc_serial_port for modbus-adc role", () => {
  const plan = { adc_serial_port: "/dev/ttyUSB-adc", io_serial_port: "/dev/ttyUSB-io" };
  const step = { program_target: { module_role: "modbus-adc" } };
  assert.equal(wizardStepSerialPort(plan, step), "/dev/ttyUSB-adc");
});

test("buildWizardProbePayload dedupes baudrates and device ids", () => {
  const payload = buildWizardProbePayload(
    { target_baudrate: 4800, target_parity: "N", target_ids: [2] },
    "/dev/ttyUSB0",
    "modbus-io",
  );
  assert.equal(payload.serial_port, "/dev/ttyUSB0");
  assert.equal(payload.module_role, "modbus-io");
  assert.deepEqual(payload.baudrates, [4800]);
  assert.deepEqual(payload.device_ids, [2, 1, 3]);
});

test("buildWizardProbePayload uses baseline then target baud sequence", () => {
  const payload = buildWizardProbePayload(
    { target_baudrate: 115200, target_parity: "N", target_ids: [2], baud_probe_sequence: [9600, 115200] },
    "/dev/ttyUSB0",
    "modbus-adc",
  );
  assert.deepEqual(payload.baudrates, [9600, 115200]);
});

test("buildWizardProbePayload keeps IO baseline at 4800 before higher target", () => {
  const payload = buildWizardProbePayload(
    { target_baudrate: 115200, target_parity: "N", target_ids: [2] },
    "/dev/ttyUSB0",
    "modbus-io",
  );
  assert.deepEqual(payload.baudrates, [4800, 115200]);
});

test("buildWizardProgramPayload opens at candidate baud then targets higher baud", async () => {
  const { buildWizardProgramPayload } = await import("./hardware-restart-wizard-helpers.js");
  const payload = buildWizardProgramPayload(
    "/dev/ttyUSB0",
    { new_device_id: 1, new_baudrate: 115200, new_parity: "N" },
    { device_id: 1, baudrate: 4800, parity: "N" },
    { baseline_baudrate: 4800, target_baudrate: 115200, module_role: "modbus-io" },
  );
  assert.equal(payload.current_baudrate, 4800);
  assert.equal(payload.new_baudrate, 115200);
  assert.equal(payload.current_device_id, 1);
});
