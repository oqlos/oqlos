export function firstBindingFromObjectMapping(detailCfg) {
  if (!detailCfg || typeof detailCfg !== "object") return null;
  for (const value of Object.values(detailCfg)) {
    if (value && typeof value === "object") return value;
  }
  return null;
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

  const source =
    activeTab === "objects" ? firstBindingFromObjectMapping(detailCfg) || {} : detailCfg;

  meta.environment = source.environment || "";
  meta.usageMode = source.usageMode || "";
  meta.apiService = source.service || "";
  meta.apiEndpoint = source.endpoint || source.url || "";
  meta.hardwareAddress =
    source.hardwareAddress ||
    source.body?.peripheral_id ||
    source.sensor ||
    "";
  meta.handlerRuntime = source.handlerRuntime || "";
  meta.handlerFunction = source.handlerFunction || "";
  return meta;
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

  if (field === "apiService") {
    setApiServiceField(target, nextValue);
    return;
  }
  if (field === "environment" || field === "usageMode") {
    if (nextValue) target[field] = nextValue;
    else delete target[field];
    return;
  }
  if (field === "apiEndpoint") {
    setApiEndpointField(target, nextValue);
    return;
  }
  if (field === "hardwareAddress") {
    setHardwareAddressField(target, nextValue, allowSensor);
    return;
  }
  if (field === "handlerRuntime") {
    if (nextValue) target.handlerRuntime = nextValue;
    else delete target.handlerRuntime;
    return;
  }
  if (field === "handlerFunction") {
    if (nextValue) target.handlerFunction = nextValue;
    else delete target.handlerFunction;
  }
}
