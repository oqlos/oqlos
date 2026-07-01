import DEFAULT_MAP from "../pages/mapEditorDefaultMap.js";
import {
  ensureMapShape,
  fillMissingFields,
  isPlainObject,
  toPrettyJson,
} from "./mapEditorMapShape.js";

export {
  cloneValue,
  ensureMapShape,
  ensureParamConversion,
  fillMissingFields,
  isMapEmpty,
  isPlainObject,
  toPrettyJson,
} from "./mapEditorMapShape.js";

export function cloneDefaultMap() {
  return JSON.parse(JSON.stringify(DEFAULT_MAP));
}

const REQUIRED_ACTION_KEYS = [
  "hui-al-start",
  "lung-pz-500x5",
  "lung-pz-1000x3",
  "head-inflate",
  "head-deflate",
  "lp-pwm-plus5",
  "lp-pwm-plus10",
  "lp-pwm-minus5",
  "lp-pwm-minus10",
  "lp-bleed",
];

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
  for (const key of REQUIRED_ACTION_KEYS) {
    const defaultAction = DEFAULT_MAP.actions?.[key];
    if (defaultAction) {
      shaped.actions[key] = fillMissingFields(
        isPlainObject(shaped.actions[key]) ? shaped.actions[key] : {},
        defaultAction,
      );
    }
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
