import test from "node:test";
import assert from "node:assert/strict";

import {
  ADC_PREVIEW_SAMPLE,
  buildLinearZeroPatch,
  formatConversionPreview,
  isAdcParamEntry,
  previewParamConversion,
} from "./mapEditorParamConversion.js";

test("isAdcParamEntry detects modbus-adc hardware mapping", () => {
  assert.equal(
    isAdcParamEntry({ hardwareAddress: "modbus://rack-a/modbus-adc/V1" }),
    true,
  );
  assert.equal(isAdcParamEntry({ hardwareAddress: "usb://rack-a/motor-tic249" }), false);
});

test("previewParamConversion applies signed linear calibration around 2V", () => {
  const spec = buildLinearZeroPatch({
    zeroPoint: 2,
    scale: 34,
    outputUnit: "mbar",
    inputUnit: "V",
    adcPerVolt: 3950,
  });
  assert.equal(previewParamConversion(ADC_PREVIEW_SAMPLE, spec), 0);
  assert.equal(previewParamConversion(3950, spec), -34);
  assert.equal(previewParamConversion(11850, spec), 34);
  assert.match(formatConversionPreview(ADC_PREVIEW_SAMPLE, spec), /0\.0000 mbar/);
});

test("previewParamConversion keeps raw ADC for identity", () => {
  const spec = {
    conversionAlgorithm: "identity",
    conversionInputUnit: "ADC",
    conversionScale: 1,
    conversionOffset: 0,
  };
  assert.equal(previewParamConversion(123, spec), 123);
  assert.match(formatConversionPreview(123, spec), /bez przeliczenia/);
});

test("each band can use different output unit and zero point", () => {
  const low = buildLinearZeroPatch({ zeroPoint: 2, scale: 34, outputUnit: "mbar", inputUnit: "V" });
  const medium = buildLinearZeroPatch({ zeroPoint: 1, scale: 12.5, outputUnit: "bar", inputUnit: "V" });
  const high = buildLinearZeroPatch({ zeroPoint: 0.5, scale: 200, outputUnit: "bar", inputUnit: "V" });

  assert.equal(low.conversionOutputUnit, "mbar");
  assert.equal(medium.conversionOutputUnit, "bar");
  assert.equal(high.conversionZeroPoint, 0.5);
});
