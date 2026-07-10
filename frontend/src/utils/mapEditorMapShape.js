export function cloneValue(value) {
  return JSON.parse(JSON.stringify(value));
}

export function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function fillMissingFields(target, defaults) {
  if (!isPlainObject(target) || !isPlainObject(defaults)) return target;
  Object.entries(defaults).forEach(([key, value]) => {
    if (!(key in target)) {
      target[key] = cloneValue(value);
      return;
    }
    if (isPlainObject(target[key]) && isPlainObject(value)) {
      fillMissingFields(target[key], value);
    }
  });
  return target;
}

export function ensureMapShape(input) {
  const src = isPlainObject(input) ? input : {};
  return {
    runtimeConfig: isPlainObject(src.runtimeConfig) ? src.runtimeConfig : {},
    objectActionMap: isPlainObject(src.objectActionMap) ? src.objectActionMap : {},
    paramSensorMap: isPlainObject(src.paramSensorMap) ? src.paramSensorMap : {},
    actions: isPlainObject(src.actions) ? src.actions : {},
    funcImplementations: isPlainObject(src.funcImplementations) ? src.funcImplementations : {},
  };
}

export function isMapEmpty(mapData) {
  return (
    Object.keys(mapData.objectActionMap || {}).length === 0 &&
    Object.keys(mapData.paramSensorMap || {}).length === 0 &&
    Object.keys(mapData.actions || {}).length === 0 &&
    Object.keys(mapData.funcImplementations || {}).length === 0 &&
    Object.keys(mapData.runtimeConfig || {}).length === 0
  );
}

export function ensureParamConversion(target) {
  if (!target || typeof target !== "object") return;
  if (!target.conversionAlgorithm) target.conversionAlgorithm = "identity";
  if (target.conversionScale === undefined) target.conversionScale = 1;
  if (target.conversionOffset === undefined) target.conversionOffset = 0;
  if (!target.conversionExpression) target.conversionExpression = "x";
  if (target.conversionZeroPoint === undefined) target.conversionZeroPoint = 0;
  if (target.conversionAdcPerVolt === undefined) target.conversionAdcPerVolt = 3950;
  if (!target.conversionInputUnit) {
    const addr = String(target.hardwareAddress || "");
    if (addr.includes("modbus-adc") || target.inputMode === "adc") {
      target.conversionInputUnit = "ADC";
    } else {
      target.conversionInputUnit = target.inputMode === "current" ? "mA" : "V";
    }
  }
  if (!target.conversionOutputUnit) target.conversionOutputUnit = target.unit || target.conversionInputUnit;
}

export function toPrettyJson(mapData) {
  return JSON.stringify(ensureMapShape(mapData), null, 2);
}
