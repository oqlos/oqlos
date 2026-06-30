export function firstBindingFromObjectMapping(detailCfg) {
  if (!detailCfg || typeof detailCfg !== "object") return null;
  for (const value of Object.values(detailCfg)) {
    if (value && typeof value === "object") return value;
  }
  return null;
}

function _resolveHardwareAddress(source) {
  return source.hardwareAddress || source.body?.peripheral_id || source.sensor || "";
}

export function readIntegrationMeta(activeTab, detailCfg) {
  const meta = {
    environment: "",
    usageMode: "",
    apiService: "",
    apiEndpoint: "",
    hardwareAddress: "",
    handlerRuntime: "",
    handlerFunction: "",
  };
  if (!detailCfg || typeof detailCfg !== "object") return meta;
  const source = activeTab === "objects" ? firstBindingFromObjectMapping(detailCfg) || {} : detailCfg;
  meta.environment = source.environment || "";
  meta.usageMode = source.usageMode || "";
  meta.apiService = source.service || "";
  meta.apiEndpoint = source.endpoint || source.url || "";
  meta.hardwareAddress = _resolveHardwareAddress(source);
  meta.handlerRuntime = source.handlerRuntime || "";
  meta.handlerFunction = source.handlerFunction || "";
  return meta;
}

const _SIMPLE_FIELDS = new Set(["environment", "usageMode", "handlerRuntime", "handlerFunction"]);

function _setOrDelete(target, key, value) {
  if (value) target[key] = value;
  else delete target[key];
}

function setApiServiceField(target, nextValue) {
  if (nextValue) target.service = nextValue;
  else delete target.service;
}

function setApiEndpointField(target, nextValue) {
  if (nextValue) {
    target.endpoint = nextValue;
    target.url = nextValue;
  } else {
    delete target.endpoint;
    delete target.url;
  }
}

function setHardwareAddressField(target, nextValue, allowSensor) {
  if (nextValue) {
    target.hardwareAddress = nextValue;
    if (allowSensor) target.sensor = nextValue;
    if (target.body && typeof target.body === "object") {
      target.body.peripheral_id = nextValue;
    }
  } else {
    delete target.hardwareAddress;
    if (allowSensor) delete target.sensor;
    if (target.body && typeof target.body === "object") {
      delete target.body.peripheral_id;
    }
  }
}

export function setMetaField(target, field, value, { allowSensor = false } = {}) {
  if (!target || typeof target !== "object") return;
  const nextValue = value?.trim() || "";
  if (_SIMPLE_FIELDS.has(field)) { _setOrDelete(target, field, nextValue); return; }
  if (field === "apiService") { setApiServiceField(target, nextValue); return; }
  if (field === "apiEndpoint") { setApiEndpointField(target, nextValue); return; }
  if (field === "hardwareAddress") { setHardwareAddressField(target, nextValue, allowSensor); }
}
