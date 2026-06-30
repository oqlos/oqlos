import test from "node:test";
import assert from "node:assert/strict";

import {
  resolveNamedActionHardwareHint,
  resolveObjectActionHardwareHint,
  summarizeFuncToHardware,
} from "./mapEditorFuncHardwareSummary.js";

const mapData = {
  objectActionMap: {
    Lung: {
      inhale: {
        kind: "api",
        body: { peripheral_id: "motor-tic249", command: "reciprocate" },
      },
    },
  },
  actions: {
    pump_on: {
      kind: "api",
      body: { peripheral_id: "motor-dri0050", command: "pump_set" },
    },
  },
};

test("resolveObjectActionHardwareHint returns peripheral:command", () => {
  assert.equal(
    resolveObjectActionHardwareHint("Lung", mapData.objectActionMap),
    "motor-tic249:reciprocate",
  );
});

test("resolveNamedActionHardwareHint returns peripheral:command", () => {
  assert.equal(
    resolveNamedActionHardwareHint("pump_on", mapData.actions),
    "motor-dri0050:pump_set",
  );
});

test("summarizeFuncToHardware joins unique sequence hints", () => {
  const summary = summarizeFuncToHardware(
    {
      kind: "sequence",
      steps: [
        { object: "Lung", action: "inhale" },
        { action: "pump_on" },
        { action: "pump_on" },
      ],
    },
    mapData,
  );
  assert.equal(summary, "motor-tic249:reciprocate · motor-dri0050:pump_set");
});
