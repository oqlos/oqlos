export const MAP_EDITOR_TABS = ["funcs", "objects", "params", "actions", "json"];
export const LIVE_EVENTS_LIMIT = 120;
export const TIC249_TARGET_VELOCITY_SCALE = 10_000;

export const GROUP_FOR_TAB = Object.freeze({
  objects: "objectActionMap",
  params: "paramSensorMap",
  actions: "actions",
  funcs: "funcImplementations",
});

export const SECTION_DESC_KEY = Object.freeze({
  objects: "objectsDesc",
  params: "paramsDesc",
  actions: "actionsDesc",
  funcs: "funcsDesc",
});

export const EMPTY_KEY = Object.freeze({
  objects: "emptyObjects",
  params: "emptyParams",
  actions: "emptyActions",
  funcs: "emptyFuncs",
});

export const META_FIELDS = Object.freeze([
  "environment",
  "usageMode",
  "apiService",
  "apiEndpoint",
  "hardwareAddress",
  "handlerRuntime",
  "handlerFunction",
]);

export const PARAM_CONVERSION_ALGORITHMS = Object.freeze([
  "identity",
  "linear",
  "lookup",
  "custom",
]);
