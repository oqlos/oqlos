import test from "node:test";
import assert from "node:assert/strict";

import {
  MODBUS_BAUD_OPTIONS,
  MODBUS_DEFAULT_BAUD,
  MODBUS_PROFILE_IDS,
  MODBUS_PROFILE_URL_PARAM,
  buildModbusSidebarItems,
  filterWizardStepsByProfile,
  patchModbusProfileSearchParams,
  probeSequenceLabel,
  profileFromPlan,
  readModbusProfileFromSearch,
  resolveModbusProfileId,
  resolveProfile,
} from "./modbus-profiles.js";

test("MODBUS_BAUD_OPTIONS spans 4800 to 115200 with 4800 IO default", () => {
  assert.deepEqual(MODBUS_BAUD_OPTIONS, [4800, 9600, 19200, 38400, 57600, 115200]);
  assert.equal(MODBUS_DEFAULT_BAUD, 4800);
});

test("resolveModbusProfileId falls back for unknown ids", () => {
  assert.equal(resolveModbusProfileId("modbus-io"), "modbus-io");
  assert.equal(resolveModbusProfileId("unknown", "shared-bus"), "shared-bus");
});

test("buildModbusSidebarItems maps profiles with ports", () => {
  const items = buildModbusSidebarItems(
    {
      profiles: {
        "modbus-adc": { serial_port: "/dev/ttyUSB1" },
        "modbus-io": { serial_port: "/dev/ttyUSB0" },
        "shared-bus": { serial_port: "/dev/ttyUSB0" },
      },
    },
    (key) => key,
    { io_serial_port: "/dev/ttyACM1", adc_serial_port: "/dev/ttyUSB0" },
  );
  assert.equal(items.length, MODBUS_PROFILE_IDS.length);
  assert.equal(items[0].subtitle, "/dev/ttyUSB1");
});

test("resolveProfile falls back to wizard plan ports", () => {
  const profile = resolveProfile(null, "modbus-io", {
    io_serial_port: "/dev/ttyACM1",
    adc_serial_port: "/dev/ttyUSB0",
    target_baudrate: 115200,
    target_parity: "N",
    target_ids: [1, 2],
  });
  assert.equal(profile.serial_port, "/dev/ttyACM1");
  assert.equal(profile.target_baudrate, 115200);
});

test("filterWizardStepsByProfile keeps io-only steps", () => {
  const steps = [
    { step: "configure-modbus-io-1" },
    { step: "configure-modbus-adc-1" },
    { step: "final-check-all-connected" },
  ];
  assert.deepEqual(
    filterWizardStepsByProfile(steps, "modbus-io").map((s) => s.step),
    ["configure-modbus-io-1", "final-check-all-connected"],
  );
});

test("probeSequenceLabel joins baud steps", () => {
  assert.equal(probeSequenceLabel({ baud_probe_sequence: [9600, 115200] }), "9600 → 115200");
  assert.equal(probeSequenceLabel(profileFromPlan("modbus-adc", null)), "9600");
  assert.equal(probeSequenceLabel(profileFromPlan("modbus-io", null)), "4800");
});

test("readModbusProfileFromSearch reads submenu query param", () => {
  assert.equal(readModbusProfileFromSearch("?submenu=modbus-io"), "modbus-io");
  assert.equal(readModbusProfileFromSearch("?submenu=unknown"), "");
});

test("patchModbusProfileSearchParams updates submenu", () => {
  const next = patchModbusProfileSearchParams(new URLSearchParams("lang=pl"), "shared-bus");
  assert.equal(next.get(MODBUS_PROFILE_URL_PARAM), "shared-bus");
  assert.equal(next.get("lang"), "pl");
});
