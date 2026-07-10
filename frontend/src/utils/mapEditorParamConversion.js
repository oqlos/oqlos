/** Helpers for paramSensorMap ADC → physical-unit conversion in map-editor. */

export const PARAM_OUTPUT_UNITS = Object.freeze([
  "mbar",
  "bar",
  "Pa",
  "kPa",
  "V",
  "L/min",
]);

export const PARAM_INPUT_UNITS = Object.freeze(["ADC", "V"]);

export const ADC_PREVIEW_SAMPLE = 7900;
export const DEFAULT_ADC_PER_VOLT = 3950;

export function isAdcParamEntry(target) {
  if (!target || typeof target !== "object") return false;
  const addr = String(target.hardwareAddress || "");
  if (addr.includes("modbus-adc")) return true;
  if (String(target.conversionInputUnit || "").toUpperCase() === "ADC") return true;
  if (target.inputMode === "adc") return true;
  return false;
}

export function conversionInputUnit(spec) {
  const unit = String(spec?.conversionInputUnit || "ADC").trim().toUpperCase();
  return unit === "V" ? "V" : "ADC";
}

export function conversionAdcPerVolt(spec) {
  const parsed = Number(spec?.conversionAdcPerVolt);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_ADC_PER_VOLT;
}

/** Normalize batch reading to the unit used by zero-point calibration. */
export function normalizeConversionInput(rawValue, spec) {
  const x = Number(rawValue);
  if (!Number.isFinite(x)) return null;
  if (conversionInputUnit(spec) === "V") {
    return x / conversionAdcPerVolt(spec);
  }
  return x;
}

export function previewParamConversion(rawValue, spec) {
  if (!spec || typeof spec !== "object") return null;

  const algo = String(spec.conversionAlgorithm || "identity").trim().toLowerCase();
  if (algo === "identity") {
    const x = Number(rawValue);
    return Number.isFinite(x) ? x : null;
  }

  const x = normalizeConversionInput(rawValue, spec);
  if (x === null) return null;

  const scale = Number(spec.conversionScale);
  const offset = Number(spec.conversionOffset);
  const zeroPoint = Number(spec.conversionZeroPoint);

  if (algo === "linear") {
    const zero = Number.isFinite(zeroPoint) ? zeroPoint : 0;
    return (x - zero) * (Number.isFinite(scale) ? scale : 1) + (Number.isFinite(offset) ? offset : 0);
  }

  if (algo === "custom") {
    try {
      const formula = String(spec.conversionExpression || "x").trim() || "x";
      const fn = new Function("x", "Math", `return (${formula});`);
      const out = Number(fn(x, Math));
      return Number.isFinite(out) ? out : null;
    } catch {
      return null;
    }
  }

  return x;
}

export function formatConversionPreview(rawValue, spec) {
  const inputUnit = conversionInputUnit(spec);
  const outputUnit = String(spec?.conversionOutputUnit || spec?.unit || "").trim();
  const algo = String(spec?.conversionAlgorithm || "identity").trim().toLowerCase();

  if (algo === "identity") {
    const label = inputUnit === "V" ? "wejście" : "ADC";
    return `${rawValue} ${label} (bez przeliczenia)`;
  }

  const converted = previewParamConversion(rawValue, spec);
  if (converted === null) {
    return `${rawValue} ${inputUnit} → błąd wzoru`;
  }

  const suffix = outputUnit ? ` ${outputUnit}` : "";
  const normalized = normalizeConversionInput(rawValue, spec);
  const inputLabel = inputUnit === "V"
    ? `${normalized?.toFixed(4)} V`
    : `${rawValue} ADC`;
  const sign = converted > 0 ? "+" : "";
  return `${inputLabel} → ${sign}${converted.toFixed(4)}${suffix}`;
}

export function formatSignedConversionPreview(rawValue, spec) {
  const below = previewParamConversion(rawValue - 100, spec);
  const at = previewParamConversion(rawValue, spec);
  const above = previewParamConversion(rawValue + 100, spec);
  const outputUnit = String(spec?.conversionOutputUnit || spec?.unit || "").trim() || "—";
  const fmt = (value) => (value === null ? "—" : `${value > 0 ? "+" : ""}${value.toFixed(2)} ${outputUnit}`);
  return `poniżej zera: ${fmt(below)} · na zerze: ${fmt(at)} · powyżej: ${fmt(above)}`;
}

export function buildLinearZeroPatch({
  zeroPoint,
  scale,
  offset = 0,
  outputUnit,
  inputUnit = "V",
  adcPerVolt = DEFAULT_ADC_PER_VOLT,
}) {
  const unit = String(outputUnit || "mbar").trim() || "mbar";
  return {
    conversionAlgorithm: "linear",
    conversionZeroPoint: zeroPoint,
    conversionScale: scale,
    conversionOffset: offset,
    conversionInputUnit: inputUnit,
    conversionAdcPerVolt: adcPerVolt,
    conversionOutputUnit: unit,
    unit,
    conversionExpression: "x",
  };
}

/** @deprecated use buildLinearZeroPatch */
export function buildLinearAdcPatch(scale, offset, outputUnit) {
  return buildLinearZeroPatch({
    zeroPoint: 0,
    scale,
    offset,
    outputUnit,
    inputUnit: "ADC",
  });
}

export function normalizeParamConversionPatch(patch, target) {
  const next = { ...patch };
  const merged = { ...target, ...next };

  if (next.conversionAlgorithm === "linear" && isAdcParamEntry(merged)) {
    if (!next.conversionInputUnit && !target?.conversionInputUnit) {
      next.conversionInputUnit = "ADC";
    }
    if (conversionInputUnit(merged) === "V" && next.conversionAdcPerVolt === undefined && target?.conversionAdcPerVolt === undefined) {
      next.conversionAdcPerVolt = DEFAULT_ADC_PER_VOLT;
    }
  }

  if (next.conversionOutputUnit) {
    next.unit = next.conversionOutputUnit;
  }

  if (next.conversionAlgorithm === "identity") {
    next.conversionScale = 1;
    next.conversionOffset = 0;
    next.conversionZeroPoint = 0;
    next.conversionExpression = "x";
  }

  return next;
}

export function linearConversionHint(spec) {
  const inputUnit = conversionInputUnit(spec);
  const outputUnit = String(spec?.conversionOutputUnit || spec?.unit || "—");
  const zero = Number(spec?.conversionZeroPoint ?? 0);
  const scale = Number(spec?.conversionScale ?? 1);
  const offset = Number(spec?.conversionOffset ?? 0);
  const adcPerVolt = conversionAdcPerVolt(spec);
  const inputLabel = inputUnit === "V"
    ? `V = ADC / ${adcPerVolt}`
    : "ADC";
  return `(${inputLabel} − ${zero} ${inputUnit}) × ${scale} + ${offset} → ${outputUnit}`;
}
