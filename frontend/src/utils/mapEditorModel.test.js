import test from "node:test";
import assert from "node:assert/strict";

import {
  ensureMapShape,
  ensureParamConversion,
  isMapEmpty,
} from "./mapEditorMapShape.js";

test("ensureMapShape fills missing groups with empty objects", () => {
  const shaped = ensureMapShape({ objectActionMap: { motor2: {} } });
  assert.deepEqual(shaped.objectActionMap, { motor2: {} });
  assert.deepEqual(shaped.paramSensorMap, {});
  assert.deepEqual(shaped.actions, {});
  assert.deepEqual(shaped.funcImplementations, {});
  assert.deepEqual(shaped.runtimeConfig, {});
});

test("isMapEmpty is true only when all groups are empty", () => {
  assert.equal(isMapEmpty(ensureMapShape({})), true);
  assert.equal(isMapEmpty(ensureMapShape({ actions: { ping: { url: "/x" } } })), false);
});

test("ensureParamConversion applies identity defaults", () => {
  const target = { sensor: "adc-1" };
  ensureParamConversion(target);
  assert.equal(target.conversionAlgorithm, "identity");
  assert.equal(target.conversionScale, 1);
  assert.equal(target.conversionOffset, 0);
  assert.equal(target.conversionExpression, "x");
  assert.equal(target.conversionInputUnit, "V");
});
