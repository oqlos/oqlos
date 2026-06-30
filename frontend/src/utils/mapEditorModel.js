import DEFAULT_MAP from "../pages/mapEditorDefaultMap.js";

export function cloneDefaultMap() {
  return JSON.parse(JSON.stringify(DEFAULT_MAP));
}

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

export function ensureRequiredDefaultMappings(mapData) {
  const shaped = ensureMapShape(mapData);
  shaped.runtimeConfig = fillMissingFields(
    isPlainObject(shaped.runtimeConfig) ? shaped.runtimeConfig : {},
    DEFAULT_MAP.runtimeConfig || {},
  );
  const defaultMotor2 = DEFAULT_MAP.objectActionMap?.motor2;
  if (defaultMotor2) {
    shaped.objectActionMap.motor2 = fillMissingFields(
      isPlainObject(shaped.objectActionMap.motor2) ? shaped.objectActionMap.motor2 : {},
      defaultMotor2,
    );
  }
  for (const key of [
    "V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8",
    "VI1", "VI2", "VI3", "VI4", "VI5", "VI6", "VI7", "VI8",
    "PI1",
  ]) {
    const defaultParam = DEFAULT_MAP.paramSensorMap?.[key];
    if (defaultParam) {
      shaped.paramSensorMap[key] = fillMissingFields(
        isPlainObject(shaped.paramSensorMap[key]) ? shaped.paramSensorMap[key] : {},
        defaultParam,
      );
    }
  }
  return shaped;
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
  if (!target.conversionInputUnit) {
    target.conversionInputUnit = target.inputMode === "current" ? "mA" : "V";
  }
  if (!target.conversionOutputUnit) target.conversionOutputUnit = target.unit || target.conversionInputUnit;
}

export function toPrettyJson(mapData) {
  return JSON.stringify(ensureMapShape(mapData), null, 2);
}

export function createInitialEditorState() {
  const seeded = ensureRequiredDefaultMappings(cloneDefaultMap());
  const pretty = toPrettyJson(seeded);
  return {
    mapData: seeded,
    jsonText: pretty,
    originalJson: pretty,
    jsonError: "",
  };
}
