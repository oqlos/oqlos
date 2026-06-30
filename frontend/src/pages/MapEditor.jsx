import { useCallback, useEffect, useMemo, useState } from "react";
import SharedNav from "../components/SharedNav";
import { useSelectionCollapsePanel } from "../utils/useSelectionCollapsePanel.js";
import { CONNECT_HARDWARE_PATHS } from "@semcod/hardware-client/paths.js";
import { HardwareApi, formatHardwareApiError } from "../api/hardwareApi";
import { useAppConfig } from "../context/AppConfigProvider";
import { useI18n } from "../i18n/I18nProvider";
import { useWsStatus } from "../hooks/useWsStatus";
import {
  buildHardwareEventsWsUrl,
  matchesHardwareEventFilters,
  normalizeHardwareEvent,
} from "../utils/hardwareEventStream.js";
import { summarizeFuncToHardware } from "../utils/mapEditorFuncHardwareSummary.js";
import DEFAULT_MAP from "./mapEditorDefaultMap";

const TABS = ["funcs", "objects", "params", "actions", "json"];
const LIVE_EVENTS_LIMIT = 120;
const TIC249_TARGET_VELOCITY_SCALE = 10000;

const GROUP_FOR_TAB = Object.freeze({
  objects: "objectActionMap",
  params: "paramSensorMap",
  actions: "actions",
  funcs: "funcImplementations",
});

const SECTION_DESC_KEY = Object.freeze({
  objects: "objectsDesc",
  params: "paramsDesc",
  actions: "actionsDesc",
  funcs: "funcsDesc",
});

const EMPTY_KEY = Object.freeze({
  objects: "emptyObjects",
  params: "emptyParams",
  actions: "emptyActions",
  funcs: "emptyFuncs",
});

const META_FIELDS = Object.freeze([
  "environment",
  "usageMode",
  "apiService",
  "apiEndpoint",
  "hardwareAddress",
  "handlerRuntime",
  "handlerFunction",
]);

const PARAM_CONVERSION_ALGORITHMS = Object.freeze([
  "identity",
  "linear",
  "lookup",
  "custom",
]);

function cloneDefaultMap() {
  return JSON.parse(JSON.stringify(DEFAULT_MAP));
}

function cloneValue(value) {
  return JSON.parse(JSON.stringify(value));
}

function tic249RawTargetVelocity(stepsPerSecond) {
  const value = Number(stepsPerSecond);
  if (!Number.isFinite(value) || value <= 0) return "—";
  return Math.round(value * TIC249_TARGET_VELOCITY_SCALE).toLocaleString("en-US");
}

function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function fillMissingFields(target, defaults) {
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

function ensureRequiredDefaultMappings(mapData) {
  const shaped = ensureMapShape(mapData);
  shaped.runtimeConfig = fillMissingFields(
    isPlainObject(shaped.runtimeConfig) ? shaped.runtimeConfig : {},
    DEFAULT_MAP.runtimeConfig || {}
  );
  const defaultMotor2 = DEFAULT_MAP.objectActionMap?.motor2;
  if (defaultMotor2) {
    shaped.objectActionMap.motor2 = fillMissingFields(
      isPlainObject(shaped.objectActionMap.motor2) ? shaped.objectActionMap.motor2 : {},
      defaultMotor2
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
        defaultParam
      );
    }
  }
  return shaped;
}

function isMapEmpty(mapData) {
  return (
    Object.keys(mapData.objectActionMap || {}).length === 0 &&
    Object.keys(mapData.paramSensorMap || {}).length === 0 &&
    Object.keys(mapData.actions || {}).length === 0 &&
    Object.keys(mapData.funcImplementations || {}).length === 0 &&
    Object.keys(mapData.runtimeConfig || {}).length === 0
  );
}

function firstBindingFromObjectMapping(detailCfg) {
  if (!detailCfg || typeof detailCfg !== "object") return null;
  for (const value of Object.values(detailCfg)) {
    if (value && typeof value === "object") return value;
  }
  return null;
}

function readIntegrationMeta(activeTab, detailCfg) {
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

function setMetaField(target, field, value, { allowSensor = false } = {}) {
  if (!target || typeof target !== "object") return;
  const nextValue = value?.trim() || "";

  if (field === "apiService") {
    if (nextValue) target.service = nextValue;
    else delete target.service;
    return;
  }

  if (field === "environment" || field === "usageMode") {
    if (nextValue) target[field] = nextValue;
    else delete target[field];
    return;
  }

  if (field === "apiEndpoint") {
    if (nextValue) {
      target.endpoint = nextValue;
      target.url = nextValue;
    } else {
      delete target.endpoint;
      delete target.url;
    }
    return;
  }

  if (field === "hardwareAddress") {
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

function ensureMapShape(input) {
  const src = isPlainObject(input) ? input : {};
  return {
    runtimeConfig: isPlainObject(src.runtimeConfig) ? src.runtimeConfig : {},
    objectActionMap: isPlainObject(src.objectActionMap) ? src.objectActionMap : {},
    paramSensorMap: isPlainObject(src.paramSensorMap) ? src.paramSensorMap : {},
    actions: isPlainObject(src.actions) ? src.actions : {},
    funcImplementations: isPlainObject(src.funcImplementations) ? src.funcImplementations : {},
  };
}

function ensureParamConversion(target) {
  if (!target || typeof target !== "object") return;
  if (!target.conversionAlgorithm) target.conversionAlgorithm = "identity";
  if (target.conversionScale === undefined) target.conversionScale = 1;
  if (target.conversionOffset === undefined) target.conversionOffset = 0;
  if (!target.conversionExpression) target.conversionExpression = "x";
  if (!target.conversionInputUnit) target.conversionInputUnit = target.inputMode === "current" ? "mA" : "V";
  if (!target.conversionOutputUnit) target.conversionOutputUnit = target.unit || target.conversionInputUnit;
}

function toPrettyJson(mapData) {
  return JSON.stringify(ensureMapShape(mapData), null, 2);
}

function createInitialEditorState() {
  const seeded = ensureRequiredDefaultMappings(cloneDefaultMap());
  const pretty = toPrettyJson(seeded);
  return {
    mapData: seeded,
    jsonText: pretty,
    originalJson: pretty,
    jsonError: "",
  };
}

export default function MapEditor() {
  const { isReadOnly, isAdmin, isOperator } = useAppConfig();
  const { t } = useI18n();
  const wsOnline = useWsStatus(true);

  const initial = createInitialEditorState();

  const [activeTab, setActiveTab] = useState(() => {
    const tab = new URLSearchParams(globalThis.location.search).get("tab");
    return TABS.includes(tab) ? tab : "funcs";
  });

  const [mapData, setMapData] = useState(() => initial.mapData);
  const [jsonText, setJsonText] = useState(() => initial.jsonText);
  const [originalJson, setOriginalJson] = useState(() => initial.originalJson);
  const [jsonError, setJsonError] = useState(() => initial.jsonError);

  const [saveState, setSaveState] = useState("idle");
  const [saveError, setSaveError] = useState("");
  const [resolveState, setResolveState] = useState("idle");
  const [resolveResult, setResolveResult] = useState(null);
  const [resolveError, setResolveError] = useState("");
  const [mappingContract, setMappingContract] = useState("");

  const [selectedEntryKey, setSelectedEntryKey] = useState(null);
  const [definitionFilter, setDefinitionFilter] = useState("");
  const [hardwareEvents, setHardwareEvents] = useState([]);
  const [eventsPeripheralFilter, setEventsPeripheralFilter] = useState("");
  const [eventsCommandFilter, setEventsCommandFilter] = useState("");
  const [eventsWsState, setEventsWsState] = useState("idle");
  const [eventsWsError, setEventsWsError] = useState("");
  const [eventsClearState, setEventsClearState] = useState("idle");
  const [eventsStorePath, setEventsStorePath] = useState("");
  const canClearServerEvents = isOperator;
  const canClearPersistentEvents = isAdmin;

  const isDirty = jsonText !== originalJson && !jsonError;

  const setTabAndUrl = useCallback((tab) => {
    setActiveTab(tab);
    setDefinitionFilter("");
    const url = new URL(globalThis.location.href);
    url.searchParams.set("tab", tab);
    globalThis.history.replaceState(null, "", `${url.pathname}${url.search}`);
  }, []);

  const onJsonChange = useCallback((value) => {
    setJsonText(value);
    try {
      const parsed = JSON.parse(value);
      if (!isPlainObject(parsed)) {
        throw new Error(t("mapEditor.mapMustBeObject"));
      }
      setMapData(ensureMapShape(parsed));
      setJsonError("");
    } catch (err) {
      setJsonError(err?.message || "Invalid JSON");
    }
  }, [t]);

  const applyMapMutation = useCallback((mutator) => {
    if (isReadOnly) return;
    setMapData((prev) => {
      const next = ensureMapShape(structuredClone(prev));
      mutator(next);
      const pretty = toPrettyJson(next);
      setJsonText(pretty);
      setJsonError("");
      return next;
    });
  }, [isReadOnly]);

  const addObject = useCallback(() => {
    const name = prompt(t("mapEditor.prompts.objectName"));
    if (!name) return;
    applyMapMutation((next) => {
      const periId = name.replaceAll(" ", "-").toLowerCase();
      next.objectActionMap[name] = {
        Włącz: {
          kind: "api",
          service: "hardware-proxy",
          environment: "lab",
          usageMode: "control",
          endpoint: CONNECT_HARDWARE_PATHS.diagnosticCommand,
          url: CONNECT_HARDWARE_PATHS.diagnosticCommand,
          hardwareAddress: `modbus://rack-a/${periId}`,
          handlerRuntime: "python",
          handlerFunction: `handle_${periId}_on`,
          method: "POST",
          body: { peripheral_id: periId, command: "valve_on" },
        },
        Wyłącz: {
          kind: "api",
          service: "hardware-proxy",
          environment: "lab",
          usageMode: "control",
          endpoint: "/api/v3/hardware/diagnostic-command",
          url: "/api/v3/hardware/diagnostic-command",
          hardwareAddress: `modbus://rack-a/${periId}`,
          handlerRuntime: "python",
          handlerFunction: `handle_${periId}_off`,
          method: "POST",
          body: { peripheral_id: periId, command: "valve_off" },
        },
      };
    });
  }, [applyMapMutation, t]);

  const addParam = useCallback(() => {
    const name = prompt(t("mapEditor.prompts.paramName"));
    if (!name) return;
    applyMapMutation((next) => {
      next.paramSensorMap[name] = {
        sensor: "V1",
        service: "state-api",
        environment: "lab",
        usageMode: "measurement",
        endpoint: "/api/v1/state",
        url: "/api/v1/state",
        hardwareAddress: "modbus://rack-a/modbus-adc/V1",
        handlerRuntime: "nodejs",
        handlerFunction: "mapVoltageInput",
        unit: "V",
        inputMode: "voltage",
        physicalInput: "V1",
        conversionAlgorithm: "identity",
        conversionScale: 1,
        conversionOffset: 0,
        conversionExpression: "x",
        conversionInputUnit: "V",
        conversionOutputUnit: "V",
      };
    });
  }, [applyMapMutation, t]);

  const editParamConversionField = useCallback((field, type = "text") => {
    if (activeTab !== "params" || !selectedEntryKey) return;
    const current = mapData.paramSensorMap?.[selectedEntryKey] || {};
    const value = prompt(`${selectedEntryKey}.${field}:`, current[field] ?? "");
    if (value === null) return;
    applyMapMutation((next) => {
      const target = next.paramSensorMap?.[selectedEntryKey];
      if (!target || typeof target !== "object") return;
      ensureParamConversion(target);
      if (type === "number") {
        const parsed = Number(value);
        if (!Number.isFinite(parsed)) return;
        target[field] = parsed;
      } else {
        target[field] = value.trim();
      }
    });
  }, [activeTab, selectedEntryKey, mapData.paramSensorMap, applyMapMutation]);

  const editParamConversionAlgorithm = useCallback(() => {
    if (activeTab !== "params" || !selectedEntryKey) return;
    const current = mapData.paramSensorMap?.[selectedEntryKey] || {};
    const hint = `algorithm (${PARAM_CONVERSION_ALGORITHMS.join(", ")}):`;
    const value = prompt(hint, current.conversionAlgorithm || "identity");
    if (value === null) return;
    const normalized = value.trim().toLowerCase();
    if (!PARAM_CONVERSION_ALGORITHMS.includes(normalized)) return;
    applyMapMutation((next) => {
      const target = next.paramSensorMap?.[selectedEntryKey];
      if (!target || typeof target !== "object") return;
      ensureParamConversion(target);
      target.conversionAlgorithm = normalized;
    });
  }, [activeTab, selectedEntryKey, mapData.paramSensorMap, applyMapMutation]);

  const addAction = useCallback(() => {
    const name = prompt(t("mapEditor.prompts.actionName"));
    if (!name) return;
    applyMapMutation((next) => {
      const periId = name.replaceAll(" ", "-").toLowerCase();
      next.actions[name] = {
        kind: "api",
        service: "hardware-proxy",
        environment: "lab",
        usageMode: "control",
        endpoint: CONNECT_HARDWARE_PATHS.diagnosticCommand,
        url: CONNECT_HARDWARE_PATHS.diagnosticCommand,
        hardwareAddress: `modbus://rack-a/${periId}`,
        handlerRuntime: "python",
        handlerFunction: `handle_${periId}`,
        method: "POST",
        body: { peripheral_id: periId, command: "valve_on" },
      };
    });
  }, [applyMapMutation, t]);

  const addFunc = useCallback(() => {
    const name = prompt(t("mapEditor.prompts.funcName"));
    if (!name) return;
    applyMapMutation((next) => {
      next.funcImplementations[name] = {
        kind: "sequence",
        service: "connect-scenario-backend",
        environment: "lab",
        usageMode: "test-run",
        endpoint: CONNECT_HARDWARE_PATHS.runtimePython,
        hardwareAddress: `pipeline://func/${name.replaceAll(" ", "-").toLowerCase()}`,
        handlerRuntime: "python",
        handlerFunction: "run_func_handler",
        steps: [{ action: "Włącz", object: "pompa 1" }],
      };
    });
  }, [applyMapMutation, t]);

  const renameKey = useCallback((group, oldName) => {
    const nextName = prompt(t("mapEditor.prompts.rename"), oldName);
    if (!nextName || nextName === oldName) return;
    applyMapMutation((next) => {
      const item = next[group][oldName];
      delete next[group][oldName];
      next[group][nextName] = item;
    });
  }, [applyMapMutation, t]);

  const deleteKey = useCallback((group, name) => {
    if (!confirm(t("mapEditor.prompts.confirmDelete", { name }))) return;
    applyMapMutation((next) => {
      delete next[group][name];
    });
  }, [applyMapMutation, t]);

  const editJsonField = useCallback((group, name, field) => {
    const current = mapData[group]?.[name];
    if (!current) return;
    const value = prompt(`${field}:`, current[field] ?? "");
    if (value === null) return;
    applyMapMutation((next) => {
      next[group][name][field] = value;
    });
  }, [applyMapMutation, mapData]);

  const editObjectActionArg = useCallback((objectName, actionName, argName, type = "text") => {
    const current = mapData.objectActionMap?.[objectName]?.[actionName]?.args?.[argName];
    const value = prompt(`${actionName}.${argName}:`, current ?? "");
    if (value === null) return;
    applyMapMutation((next) => {
      const binding = next.objectActionMap?.[objectName]?.[actionName];
      if (!binding || typeof binding !== "object") return;
      if (!binding.args || typeof binding.args !== "object") binding.args = {};

      if (type === "number") {
        const parsed = Number(value);
        if (!Number.isFinite(parsed)) return;
        binding.args[argName] = parsed;
      } else {
        binding.args[argName] = value.trim();
      }

      if (binding.body?.command === "move_relative") {
        const direction = String(binding.args.direction || actionName || "").toLowerCase();
        const steps = Math.abs(Number(binding.args.steps ?? binding.args.offset ?? 0));
        if (Number.isFinite(steps) && steps > 0) {
          binding.args.steps = steps;
          binding.args.offset = direction === "left" ? -steps : steps;
        }
      }
    });
  }, [applyMapMutation, mapData]);

  const editObjectActionBodyField = useCallback((objectName, actionName, field) => {
    const current = mapData.objectActionMap?.[objectName]?.[actionName]?.body?.[field];
    const value = prompt(`${actionName}.body.${field}:`, current ?? "");
    if (value === null) return;
    applyMapMutation((next) => {
      const binding = next.objectActionMap?.[objectName]?.[actionName];
      if (!binding || typeof binding !== "object") return;
      if (!binding.body || typeof binding.body !== "object") binding.body = {};
      binding.body[field] = value.trim();
    });
  }, [applyMapMutation, mapData]);

  const editMotorRuntimeConfig = useCallback((field, type = "number") => {
    const current = mapData.runtimeConfig?.motor2?.[field];
    const value = prompt(`motor2.${field}:`, current ?? "");
    if (value === null) return;
    applyMapMutation((next) => {
      if (!next.runtimeConfig || typeof next.runtimeConfig !== "object") next.runtimeConfig = {};
      if (!next.runtimeConfig.motor2 || typeof next.runtimeConfig.motor2 !== "object") {
        next.runtimeConfig.motor2 = {};
      }
      if (type === "number") {
        const parsed = Number(value);
        if (!Number.isFinite(parsed)) return;
        next.runtimeConfig.motor2[field] = parsed;
      } else {
        next.runtimeConfig.motor2[field] = value.trim();
      }
    });
  }, [applyMapMutation, mapData]);

  const renderMotorRuntimeRow = useCallback((labelKey, field, suffix = "", type = "number") => {
    const cfg = mapData.runtimeConfig?.motor2 || {};
    const value = cfg[field];
    return (
      <div className="mapx-meta-row">
        <span className="mapx-meta-label">{t(labelKey)}</span>
        <span className="mapx-meta-value">{value ?? "—"}{suffix}</span>
        <button
          type="button"
          className="mapx-btn"
          onClick={() => editMotorRuntimeConfig(field, type)}
          disabled={isReadOnly}
        >
          {t("mapEditor.editMeta")}
        </button>
      </div>
    );
  }, [editMotorRuntimeConfig, isReadOnly, mapData.runtimeConfig, t]);

  const saveMap = useCallback(async () => {
    if (isReadOnly || jsonError) return;
    setSaveState("saving");
    setSaveError("");
    try {
      const parsedJson = JSON.parse(jsonText);
      if (!isPlainObject(parsedJson)) {
        throw new Error(t("mapEditor.mapMustBeObject"));
      }
      const mappingPayload = parsedJson;
      const response = await HardwareApi.replaceMapping({ mapping: mappingPayload, persist: true });
      const savedMap = ensureRequiredDefaultMappings(ensureMapShape(response?.mapping || mappingPayload));
      const pretty = toPrettyJson(savedMap);
      setOriginalJson(pretty);
      setMapData(savedMap);
      setJsonText(pretty);
      setSaveState("saved");
      setTimeout(() => setSaveState("idle"), 1200);
    } catch (err) {
      console.error("MapEditor: save failed", err);
      setSaveError(formatHardwareApiError(err, t("mapEditor.saveError")));
      setSaveState("error");
    }
  }, [isReadOnly, jsonError, jsonText, t]);

  const restoreDefaultMap = useCallback(async () => {
    if (isReadOnly) return;
    if (!confirm(t("mapEditor.restoreDefaultsConfirm"))) return;
    setSaveState("saving");
    setSaveError("");
    try {
      const seeded = ensureRequiredDefaultMappings(cloneDefaultMap());
      const response = await HardwareApi.replaceMapping({ mapping: seeded, persist: true });
      const restored = ensureRequiredDefaultMappings(ensureMapShape(response?.mapping || seeded));
      const pretty = toPrettyJson(restored);
      setMapData(restored);
      setJsonText(pretty);
      setOriginalJson(pretty);
      setSaveState("saved");
      setTimeout(() => setSaveState("idle"), 1200);
    } catch (err) {
      console.error("MapEditor: restore defaults failed", err);
      setSaveError(formatHardwareApiError(err, t("mapEditor.restoreDefaultsError")));
      setSaveState("error");
    }
  }, [isReadOnly, t]);

  const reloadCurrent = useCallback(async () => {
    try {
      const payload = await HardwareApi.getMapping();
      const parsed = ensureMapShape(payload?.mapping);
      const shouldSeedBackend = isMapEmpty(parsed);
      const shaped = ensureRequiredDefaultMappings(shouldSeedBackend ? cloneDefaultMap() : parsed);
      if (shouldSeedBackend && !isReadOnly) {
        await HardwareApi.replaceMapping({ mapping: shaped, persist: true });
      }
      const pretty = toPrettyJson(shaped);
      setMapData(shaped);
      setJsonText(pretty);
      setOriginalJson(pretty);
      setJsonError("");
      setSaveError("");
      setMappingContract(payload?.contract || "");
    } catch (err) {
      console.error("MapEditor: load failed", err);
      setSaveError(formatHardwareApiError(err, t("mapEditor.loadError")));
      setMappingContract("");
    }
  }, [isReadOnly, t]);

  const loadRecentHardwareEvents = useCallback(async () => {
    try {
      const payload = await HardwareApi.listHardwareCqrsEvents(LIVE_EVENTS_LIMIT);
      const normalized = (Array.isArray(payload?.events) ? payload.events : [])
        .map(normalizeHardwareEvent)
        .slice(-LIVE_EVENTS_LIMIT);
      setHardwareEvents(normalized);
      setEventsStorePath(typeof payload?.store_path === "string" ? payload.store_path : "");
      setEventsWsError("");
    } catch (err) {
      setEventsWsError(formatHardwareApiError(err, t("mapEditor.eventsLoadFailed")));
    }
  }, [t]);

  const clearServerHardwareEvents = useCallback(async (truncatePersistent = false) => {
    if (truncatePersistent && !isAdmin) {
      setEventsWsError(t("mapEditor.liveEventsAdminOnly"));
      return;
    }
    if (!truncatePersistent && !isOperator) {
      setEventsWsError(t("mapEditor.liveEventsOperatorOnly"));
      return;
    }
    if (truncatePersistent && !confirm(t("mapEditor.liveEventsConfirmClearPersistent"))) {
      return;
    }
    setEventsClearState("clearing");
    try {
      await HardwareApi.clearHardwareCqrsEvents({ truncate_persistent: Boolean(truncatePersistent) });
      await loadRecentHardwareEvents();
      setEventsClearState("idle");
      setEventsWsError("");
    } catch (err) {
      setEventsClearState("error");
      setEventsWsError(formatHardwareApiError(err, t("mapEditor.eventsClearFailed")));
    }
  }, [isAdmin, isOperator, loadRecentHardwareEvents, t]);

  useEffect(() => {
    loadRecentHardwareEvents();
  }, [loadRecentHardwareEvents]);

  useEffect(() => {
    reloadCurrent();
  }, [reloadCurrent]);

  useEffect(() => {
    let cancelled = false;
    HardwareApi.getMappingSchema()
      .then((payload) => {
        if (!cancelled) setMappingContract(payload?.contract || "");
      })
      .catch(() => {
        if (!cancelled) setMappingContract("");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const wsUrl = buildHardwareEventsWsUrl({ wsUrlEnv: import.meta.env.VITE_WS_URL });
    let closed = false;
    let socket = null;
    try {
      setEventsWsState("connecting");
      socket = new WebSocket(wsUrl);
    } catch {
      setEventsWsState("error");
      setEventsWsError(t("mapEditor.liveEventsWsError"));
      return undefined;
    }

    socket.onopen = () => {
      if (closed) return;
      setEventsWsState("live");
      setEventsWsError("");
    };
    socket.onmessage = (event) => {
      if (closed) return;
      try {
        const message = JSON.parse(event.data);
        if (message?.message_type !== "event" || !message?.data) return;
        const normalized = normalizeHardwareEvent(message.data);
        setHardwareEvents((prev) => [...prev, normalized].slice(-LIVE_EVENTS_LIMIT));
      } catch {
        // ignore non-json or heartbeat messages
      }
    };
    socket.onerror = () => {
      if (closed) return;
      setEventsWsState("error");
      setEventsWsError(t("mapEditor.liveEventsWsError"));
    };
    socket.onclose = () => {
      if (closed) return;
      setEventsWsState("closed");
    };

    return () => {
      closed = true;
      if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
        socket.close();
      }
    };
  }, [t]);

  const mappingGroup = activeTab !== "json" ? GROUP_FOR_TAB[activeTab] : null;

  const entryKeys = useMemo(() => {
    if (!mappingGroup) return [];
    return Object.keys(mapData[mappingGroup] || {}).sort((a, b) =>
      a.localeCompare(b, "pl", { sensitivity: "base" })
    );
  }, [mappingGroup, mapData]);

  const navContext = (
    <div className="section-label" style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: 0 }}>
      <span>{t("mapEditor.title")}</span>
      {mappingContract && (
        <span className="cql-status cql-status--online">
          {t("mapEditor.contract")}: {mappingContract}
        </span>
      )}
      <span className={`cql-status ${wsOnline ? "cql-status--online" : ""}`}>
        {wsOnline ? t("scenarios.connected") : t("scenarios.disconnected")}
      </span>
    </div>
  );

  const filteredEntryKeys = useMemo(() => {
    const q = definitionFilter.trim().toLowerCase();
    if (!q) return entryKeys;
    return entryKeys.filter((name) => name.toLowerCase().includes(q));
  }, [entryKeys, definitionFilter]);

  const {
    collapsed: sidebarCollapsed,
    userCollapsed: sidebarUserCollapsed,
    autoCollapsed: sidebarAutoCollapsed,
    inIframe: sidebarInIframe,
    scheduleCollapse: scheduleSidebarCollapse,
    cancelAutoCollapse: cancelSidebarCollapse,
    toggleCollapsed: toggleSidebarCollapsed,
    setAutoCollapsed: setSidebarAutoCollapsed,
    railEnter: sidebarRailEnter,
    railLeave: sidebarRailLeave,
    panelEnter: sidebarPanelEnter,
    panelLeave: sidebarPanelLeave,
  } = useSelectionCollapsePanel({
    toggleId: "map-editor-definitions",
    storageKey: "ui.map-editor-sidebar-collapsed",
    label: t("mapEditor.title"),
    icon: "☰",
    badge: filteredEntryKeys.length,
  });

  useEffect(() => {
    const applyAutoCollapse = () => {
      const root = document.documentElement;
      const font = String(root?.dataset?.font || "").trim().toLowerCase();
      const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 1280;
      const denseFont = font === "large" || font === "xlarge";
      if (!denseFont) {
        setSidebarAutoCollapsed(false);
        return;
      }
      const minWidth = font === "xlarge" ? 1700 : 1500;
      setSidebarAutoCollapsed(viewportWidth < minWidth);
    };

    applyAutoCollapse();
    window.addEventListener("resize", applyAutoCollapse);
    const root = document.documentElement;
    const observer = new MutationObserver(applyAutoCollapse);
    observer.observe(root, { attributes: true, attributeFilter: ["data-font"] });
    return () => {
      window.removeEventListener("resize", applyAutoCollapse);
      observer.disconnect();
    };
  }, [setSidebarAutoCollapsed]);

  useEffect(() => {
    if (definitionFilter) cancelSidebarCollapse();
  }, [definitionFilter, cancelSidebarCollapse]);

  const handleSelectEntry = useCallback((name) => {
    setSelectedEntryKey(name);
    if (activeTab !== "json") scheduleSidebarCollapse();
  }, [activeTab, scheduleSidebarCollapse]);

  useEffect(() => {
    if (activeTab === "json") return;
    if (filteredEntryKeys.length === 0) {
      setSelectedEntryKey(null);
      return;
    }
    setSelectedEntryKey((prev) => (prev && filteredEntryKeys.includes(prev) ? prev : filteredEntryKeys[0]));
  }, [activeTab, filteredEntryKeys]);

  const detailCfg =
    mappingGroup && selectedEntryKey ? mapData[mappingGroup]?.[selectedEntryKey] : undefined;

  const integrationMeta = useMemo(
    () => readIntegrationMeta(activeTab, detailCfg),
    [activeTab, detailCfg]
  );

  const updateIntegrationMeta = useCallback((field) => {
    if (!mappingGroup || !selectedEntryKey || !META_FIELDS.includes(field)) return;

    const value = prompt(t(`mapEditor.meta.${field}`), integrationMeta[field] || "");
    if (value === null) return;

    applyMapMutation((next) => {
      if (activeTab === "objects") {
        const objectCfg = next.objectActionMap[selectedEntryKey];
        const binding = firstBindingFromObjectMapping(objectCfg);
        if (!binding) return;
        setMetaField(binding, field, value);
        return;
      }

      if (activeTab === "params") {
        const target = next.paramSensorMap[selectedEntryKey];
        setMetaField(target, field, value, { allowSensor: true });
        return;
      }

      if (activeTab === "actions") {
        const target = next.actions[selectedEntryKey];
        setMetaField(target, field, value);
        return;
      }

      if (activeTab === "funcs") {
        const target = next.funcImplementations[selectedEntryKey];
        setMetaField(target, field, value);
      }
    });
  }, [mappingGroup, selectedEntryKey, activeTab, integrationMeta, applyMapMutation, t]);

  const resolveSelectedFuncMapping = useCallback(async () => {
    if (activeTab !== "funcs" || !selectedEntryKey) return;
    setResolveState("loading");
    setResolveError("");
    try {
      const result = await HardwareApi.resolveRuntimeFuncMapping({
        hardware_map: mapData,
        func_name: selectedEntryKey,
        environment: integrationMeta.environment || null,
        usage_mode: integrationMeta.usageMode || null,
      });
      setResolveResult(result);
      setResolveState("ready");
    } catch (err) {
      setResolveResult(null);
      setResolveError(formatHardwareApiError(err, t("mapEditor.resolveFailed")));
      setResolveState("error");
    }
  }, [activeTab, selectedEntryKey, mapData, integrationMeta, t]);

  useEffect(() => {
    setResolveState("idle");
    setResolveResult(null);
    setResolveError("");
  }, [activeTab, selectedEntryKey, integrationMeta.environment, integrationMeta.usageMode]);

  const filteredHardwareEvents = useMemo(() => {
    return [...hardwareEvents]
      .reverse()
      .filter((item) => matchesHardwareEventFilters(item, eventsPeripheralFilter, eventsCommandFilter))
      .slice(0, 30);
  }, [hardwareEvents, eventsPeripheralFilter, eventsCommandFilter]);

  const renderIntegrationMetaEditor = useCallback(() => {
    if (!detailCfg) return null;
    return (
      <div className="mapx-meta-box">
        <div className="mapx-meta-title">{t("mapEditor.integrationMeta")}</div>
        <div className="mapx-meta-grid">
          {META_FIELDS.map((field) => (
            <div key={field} className="mapx-meta-row">
              <span className="mapx-meta-label">{t(`mapEditor.meta.${field}`)}</span>
              <span className="mapx-meta-value">{integrationMeta[field] || "—"}</span>
              <button
                type="button"
                className="mapx-btn"
                onClick={() => updateIntegrationMeta(field)}
                disabled={isReadOnly}
              >
                {t("mapEditor.editMeta")}
              </button>
            </div>
          ))}
        </div>
      </div>
    );
  }, [detailCfg, integrationMeta, updateIntegrationMeta, isReadOnly, t]);

  const renderObjectActionEditor = useCallback((objectName, objectCfg) => {
    if (!objectCfg || typeof objectCfg !== "object") return null;
    return (
      <div className="mapx-meta-box">
        <div className="mapx-meta-title">Akcje i parametry</div>
        <div className="mapx-action-list">
          {Object.entries(objectCfg).map(([actionName, binding]) => {
            const args = binding?.args && typeof binding.args === "object" ? binding.args : {};
            const body = binding?.body && typeof binding.body === "object" ? binding.body : {};
            const isRelativeMotorMove =
              body.peripheral_id === "motor-tic249" && body.command === "move_relative";

            return (
              <div key={actionName} className="mapx-action-row">
                <div className="mapx-action-main">
                  <strong>{actionName}</strong>
                  <span>{body.peripheral_id || "—"} / {body.command || "—"}</span>
                </div>
                {isRelativeMotorMove ? (
                  <div className="mapx-action-params">
                    <button
                      type="button"
                      className="mapx-param-pill"
                      onClick={() => editObjectActionArg(objectName, actionName, "steps", "number")}
                      disabled={isReadOnly}
                    >
                      steps: {args.steps ?? "—"}
                    </button>
                    <button
                      type="button"
                      className="mapx-param-pill"
                      onClick={() => editObjectActionArg(objectName, actionName, "direction")}
                      disabled={isReadOnly}
                    >
                      direction: {args.direction ?? "—"}
                    </button>
                    <button
                      type="button"
                      className="mapx-param-pill"
                      onClick={() => editObjectActionArg(objectName, actionName, "offset", "number")}
                      disabled={isReadOnly}
                    >
                      offset: {args.offset ?? "—"}
                    </button>
                    <button
                      type="button"
                      className="mapx-param-pill"
                      onClick={() => editObjectActionArg(objectName, actionName, "speed", "number")}
                      disabled={isReadOnly}
                    >
                      speed: {args.speed ?? "—"}
                    </button>
                    <button
                      type="button"
                      className="mapx-param-pill"
                      onClick={() => editObjectActionArg(objectName, actionName, "max_steps_per_second", "number")}
                      disabled={isReadOnly}
                    >
                      limit: {args.max_steps_per_second ?? "—"} steps/s
                    </button>
                    <button
                      type="button"
                      className="mapx-param-pill"
                      onClick={() => editObjectActionArg(objectName, actionName, "acceleration", "number")}
                      disabled={isReadOnly}
                    >
                      accel: {args.acceleration ?? "—"}%/s
                    </button>
                  </div>
                ) : (
                  <div className="mapx-action-params">
                    <button
                      type="button"
                      className="mapx-param-pill"
                      onClick={() => editObjectActionBodyField(objectName, actionName, "peripheral_id")}
                      disabled={isReadOnly}
                    >
                      peripheral: {body.peripheral_id || "—"}
                    </button>
                    <button
                      type="button"
                      className="mapx-param-pill"
                      onClick={() => editObjectActionBodyField(objectName, actionName, "command")}
                      disabled={isReadOnly}
                    >
                      command: {body.command || "—"}
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  }, [editObjectActionArg, editObjectActionBodyField, isReadOnly]);

  const renderMotorRuntimeConfigEditor = useCallback(() => {
    if (activeTab !== "objects" || selectedEntryKey !== "motor2") return null;
    const cfg = mapData.runtimeConfig?.motor2 || {};
    return (
      <div className="mapx-meta-box">
        <div className="mapx-meta-title">{t("mapEditor.motorRuntimeTitle")}</div>
        <div className="mapx-meta-grid">
          {renderMotorRuntimeRow("mapEditor.motorStrokeSteps", "strokeSteps", " steps")}
          {renderMotorRuntimeRow("mapEditor.motorCycleVolume", "cycleVolumeLiters", " l")}
          {renderMotorRuntimeRow("mapEditor.motorMaxSpeed", "maxStepsPerSecond", " steps/s")}
          {renderMotorRuntimeRow("mapEditor.motorDefaultSpeed", "defaultSpeedStepsPerSecond", " steps/s")}
          {renderMotorRuntimeRow("mapEditor.motorAcceleration", "accelerationPercentPerSecond", " %/s")}
          {renderMotorRuntimeRow("mapEditor.motorSpeedUnit", "speedUnit", "", "text")}
          {renderMotorRuntimeRow("mapEditor.motorLimitMode", "limitMode", "", "text")}
          {renderMotorRuntimeRow("mapEditor.motorStartDirection", "startDirection", "", "text")}
          <div className="mapx-meta-row">
            <span className="mapx-meta-label">{t("mapEditor.motorRawTargetVelocity")}</span>
            <span className="mapx-meta-value">{tic249RawTargetVelocity(cfg.defaultSpeedStepsPerSecond)}</span>
          </div>
        </div>
      </div>
    );
  }, [activeTab, selectedEntryKey, mapData.runtimeConfig, renderMotorRuntimeRow, t]);

  const renderParamConversionEditor = useCallback(() => {
    if (activeTab !== "params" || !selectedEntryKey) return null;
    const target = mapData.paramSensorMap?.[selectedEntryKey];
    if (!target || typeof target !== "object") return null;

    const view = structuredClone(target);
    ensureParamConversion(view);

    return (
      <div className="mapx-meta-box">
        <div className="mapx-meta-title">Przeliczanie wartosci (mapowanie)</div>
        <div className="mapx-meta-grid">
          <div className="mapx-meta-row">
            <span className="mapx-meta-label">Algorytm</span>
            <span className="mapx-meta-value">{view.conversionAlgorithm}</span>
            <button type="button" className="mapx-btn" onClick={editParamConversionAlgorithm} disabled={isReadOnly}>
              {t("mapEditor.editMeta")}
            </button>
          </div>
          <div className="mapx-meta-row">
            <span className="mapx-meta-label">Skala</span>
            <span className="mapx-meta-value">{view.conversionScale}</span>
            <button type="button" className="mapx-btn" onClick={() => editParamConversionField("conversionScale", "number")} disabled={isReadOnly}>
              {t("mapEditor.editMeta")}
            </button>
          </div>
          <div className="mapx-meta-row">
            <span className="mapx-meta-label">Offset</span>
            <span className="mapx-meta-value">{view.conversionOffset}</span>
            <button type="button" className="mapx-btn" onClick={() => editParamConversionField("conversionOffset", "number")} disabled={isReadOnly}>
              {t("mapEditor.editMeta")}
            </button>
          </div>
          <div className="mapx-meta-row">
            <span className="mapx-meta-label">Wzor (x = napiecie)</span>
            <span className="mapx-meta-value">{view.conversionExpression || "x"}</span>
            <button type="button" className="mapx-btn" onClick={() => editParamConversionField("conversionExpression")} disabled={isReadOnly}>
              {t("mapEditor.editMeta")}
            </button>
          </div>
          <div className="mapx-meta-row">
            <span className="mapx-meta-label">Jednostka wejscia</span>
            <span className="mapx-meta-value">{view.conversionInputUnit}</span>
            <button type="button" className="mapx-btn" onClick={() => editParamConversionField("conversionInputUnit")} disabled={isReadOnly}>
              {t("mapEditor.editMeta")}
            </button>
          </div>
          <div className="mapx-meta-row">
            <span className="mapx-meta-label">Jednostka wyjscia</span>
            <span className="mapx-meta-value">{view.conversionOutputUnit}</span>
            <button type="button" className="mapx-btn" onClick={() => editParamConversionField("conversionOutputUnit")} disabled={isReadOnly}>
              {t("mapEditor.editMeta")}
            </button>
          </div>
        </div>
      </div>
    );
  }, [
    activeTab,
    selectedEntryKey,
    mapData.paramSensorMap,
    editParamConversionAlgorithm,
    editParamConversionField,
    isReadOnly,
    t,
  ]);

  const runAddForTab = useCallback(() => {
    if (activeTab === "objects") addObject();
    else if (activeTab === "params") addParam();
    else if (activeTab === "actions") addAction();
    else if (activeTab === "funcs") addFunc();
  }, [activeTab, addObject, addParam, addAction, addFunc]);

  const sidebarClass = [
    "mapx-def-sidebar",
    "mapx-left-rail",
    sidebarCollapsed ? "collapsed" : "",
    sidebarCollapsed && sidebarInIframe ? "collapsed--hosted" : "",
    !sidebarCollapsed && sidebarUserCollapsed ? "preview" : "",
  ].filter(Boolean).join(" ");

  const sidebarInPreview = !sidebarCollapsed && (sidebarUserCollapsed || sidebarAutoCollapsed);

  return (
    <div className="mapx-shell">
      <aside
        className={sidebarClass}
        data-collapsed={sidebarCollapsed ? "1" : "0"}
        data-auto-collapsed={sidebarAutoCollapsed ? "1" : "0"}
        data-toggle-hosted={sidebarCollapsed && sidebarInIframe ? "parent" : "self"}
        data-preview={sidebarInPreview ? "1" : "0"}
        onMouseEnter={sidebarInPreview ? sidebarPanelEnter : undefined}
        onMouseLeave={sidebarInPreview ? sidebarPanelLeave : undefined}
      >
        {sidebarCollapsed ? (
          <button
            type="button"
            className="mapx-sidebar-rail"
            onClick={toggleSidebarCollapsed}
            onMouseEnter={sidebarRailEnter}
            onMouseLeave={sidebarRailLeave}
            onFocus={sidebarRailEnter}
            onBlur={sidebarRailLeave}
            title={t("mapEditor.title")}
            aria-label={t("mapEditor.title")}
            aria-pressed="true"
          >
            <span aria-hidden="true" className="mapx-sidebar-rail-icon">☰</span>
          </button>
        ) : (
          <>
        <div className="mapx-left-rail-head" style={{ display: "flex", alignItems: "center", gap: "4px" }}>
          <button
            type="button"
            className="mapx-sidebar-collapse-btn"
            onClick={toggleSidebarCollapsed}
            title="Ukryj definicje"
            aria-label="Ukryj definicje"
            style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", padding: "0 4px" }}
          >
            «
          </button>
          <span style={{ flex: 1 }}>{t("mapEditor.title")}</span>
        </div>
        <nav className="mapx-def-tabs mapx-tabs mapx-tabs--toolbar" aria-label={t("mapEditor.title")}>
          {TABS.map((tab) => (
            <button
              key={tab}
              type="button"
              className={`mapx-tab ${activeTab === tab ? "active" : ""}`}
              onClick={() => setTabAndUrl(tab)}
            >
              {t(`mapEditor.tabs.${tab}`)}
            </button>
          ))}
        </nav>

        {activeTab === "json" && (
          <div className="mapx-def-sidebar-json-hint">{t("mapEditor.jsonSidebarHint")}</div>
        )}

        {activeTab !== "json" && (
          <>
            <div className="mapx-def-sidebar-head">
              {activeTab === "funcs" ? t("mapEditor.sidebarFuncsHardware") : t("mapEditor.mappingDefinitions")}
            </div>
            <div className="mapx-def-filter-wrap">
              <input
                type="search"
                className="mapx-def-filter"
                placeholder={t("mapEditor.filterMappings")}
                value={definitionFilter}
                onChange={(e) => setDefinitionFilter(e.target.value)}
                aria-label={t("mapEditor.filterMappings")}
              />
            </div>
            <div className="mapx-def-sidebar-body">
              {entryKeys.length === 0 ? (
                <div className="mapx-empty">{t(`mapEditor.${EMPTY_KEY[activeTab]}`)}</div>
              ) : filteredEntryKeys.length === 0 ? (
                <div className="mapx-empty">{t("mapEditor.noFilterResults")}</div>
              ) : (
                filteredEntryKeys.map((name) => {
                  const hwSummary =
                    activeTab === "funcs"
                      ? summarizeFuncToHardware(mapData.funcImplementations?.[name], mapData)
                      : "";
                  return (
                    <button
                      key={name}
                      type="button"
                      className={`mapx-list-item ${selectedEntryKey === name ? "active" : ""}`}
                      onClick={() => handleSelectEntry(name)}
                    >
                      <span className="mapx-list-item-lines">
                        <span className="mapx-list-item-title">{name}</span>
                        {activeTab === "funcs" && (
                          <span className="mapx-list-item-sub">{hwSummary || "—"}</span>
                        )}
                      </span>
                    </button>
                  );
                })
              )}
            </div>
          </>
        )}
          </>
        )}
      </aside>

      <div className="dashboard mapx-main-dashboard">
        <SharedNav navContext={navContext} />
        <div className="dash-content mapx-page">
          <div className="mapx-header">
            <div>
              <h2>{t("mapEditor.title")}</h2>
              <p className="section-desc">{t("mapEditor.subtitle")}</p>
            </div>
            <div className="mapx-header-actions">
              <button onClick={saveMap} disabled={!isDirty || isReadOnly || saveState === "saving"} className="mapx-btn mapx-btn-primary">
                {saveState === "saving" ? "…" : t("mapEditor.save")}
              </button>
              <button type="button" onClick={restoreDefaultMap} className="mapx-btn" disabled={isReadOnly || saveState === "saving"}>
                {t("mapEditor.restoreDefaults")}
              </button>
              <button type="button" onClick={reloadCurrent} className="mapx-btn">{t("mapEditor.reload")}</button>
            </div>
          </div>
          {saveError && <div className="mapx-error">{saveError}</div>}

          <main className="mapx-main mapx-main--editor mapx-main-panel">
            {activeTab === "json" && (
              <div className="mapx-json-wrap">
                <div className="mapx-section-head">
                  <span>{t("mapEditor.jsonDesc")}</span>
                  <button
                    type="button"
                    className="mapx-btn"
                    onClick={() => {
                      try {
                        const parsed = JSON.parse(jsonText);
                        if (!isPlainObject(parsed)) {
                          throw new Error(t("mapEditor.mapMustBeObject"));
                        }
                        const pretty = JSON.stringify(parsed, null, 2);
                        setJsonText(pretty);
                        setMapData(ensureMapShape(parsed));
                        setJsonError("");
                      } catch (err) {
                        setJsonError(err?.message || "Invalid JSON");
                      }
                    }}
                  >
                    {t("mapEditor.format")}
                  </button>
                </div>
                <textarea className="mapx-json" value={jsonText} onChange={(e) => onJsonChange(e.target.value)} spellCheck={false} />
                {jsonError && <div className="mapx-error">{jsonError}</div>}
              </div>
            )}

            {activeTab !== "json" && mappingGroup && (
              <>
                <div className="mapx-section-head">
                  <span>{t(`mapEditor.${SECTION_DESC_KEY[activeTab]}`)}</span>
                  <button type="button" className="mapx-btn" onClick={runAddForTab} disabled={isReadOnly}>
                    + {t("mapEditor.add")}
                  </button>
                </div>
                {entryKeys.length === 0 ? (
                  <div className="mapx-empty">{t(`mapEditor.${EMPTY_KEY[activeTab]}`)}</div>
                ) : filteredEntryKeys.length === 0 ? (
                  <div className="mapx-empty">{t("mapEditor.noFilterResults")}</div>
                ) : !detailCfg || !selectedEntryKey ? (
                  <div className="mapx-empty">{t("mapEditor.selectDefinition")}</div>
                ) : activeTab === "objects" ? (
                  <div className="mapx-card">
                    <div className="mapx-card-head">
                      <strong>{selectedEntryKey}</strong>
                      <span>
                        <button type="button" className="mapx-btn" onClick={() => renameKey("objectActionMap", selectedEntryKey)} disabled={isReadOnly}>✎</button>
                        <button type="button" className="mapx-btn" onClick={() => deleteKey("objectActionMap", selectedEntryKey)} disabled={isReadOnly}>🗑</button>
                      </span>
                    </div>
                    {renderObjectActionEditor(selectedEntryKey, detailCfg)}
                    {renderMotorRuntimeConfigEditor()}
                    <pre>{JSON.stringify(detailCfg, null, 2)}</pre>
                    {renderIntegrationMetaEditor()}
                  </div>
                ) : activeTab === "params" ? (
                  <div className="mapx-card">
                    <div className="mapx-card-head">
                      <strong>{selectedEntryKey}</strong>
                      <span>
                        <button type="button" className="mapx-btn" onClick={() => editJsonField("paramSensorMap", selectedEntryKey, "sensor")} disabled={isReadOnly}>sensor</button>
                        <button type="button" className="mapx-btn" onClick={() => renameKey("paramSensorMap", selectedEntryKey)} disabled={isReadOnly}>✎</button>
                        <button type="button" className="mapx-btn" onClick={() => deleteKey("paramSensorMap", selectedEntryKey)} disabled={isReadOnly}>🗑</button>
                      </span>
                    </div>
                    <pre>{JSON.stringify(detailCfg, null, 2)}</pre>
                    {renderParamConversionEditor()}
                    {renderIntegrationMetaEditor()}
                  </div>
                ) : activeTab === "actions" ? (
                  <div className="mapx-card">
                    <div className="mapx-card-head">
                      <strong>{selectedEntryKey}</strong>
                      <span>
                        <button type="button" className="mapx-btn" onClick={() => editJsonField("actions", selectedEntryKey, "url")} disabled={isReadOnly}>url</button>
                        <button type="button" className="mapx-btn" onClick={() => renameKey("actions", selectedEntryKey)} disabled={isReadOnly}>✎</button>
                        <button type="button" className="mapx-btn" onClick={() => deleteKey("actions", selectedEntryKey)} disabled={isReadOnly}>🗑</button>
                      </span>
                    </div>
                    <pre>{JSON.stringify(detailCfg, null, 2)}</pre>
                    {renderIntegrationMetaEditor()}
                  </div>
                ) : (
                  <div className="mapx-card">
                    <div className="mapx-card-head">
                      <strong>{selectedEntryKey}</strong>
                      <span>
                        <button type="button" className="mapx-btn" onClick={() => renameKey("funcImplementations", selectedEntryKey)} disabled={isReadOnly}>✎</button>
                        <button type="button" className="mapx-btn" onClick={() => deleteKey("funcImplementations", selectedEntryKey)} disabled={isReadOnly}>🗑</button>
                      </span>
                    </div>
                    <pre>{JSON.stringify(detailCfg, null, 2)}</pre>
                    {renderIntegrationMetaEditor()}
                    <div className="mapx-meta-box">
                      <div className="mapx-meta-title">{t("mapEditor.resolverTitle")}</div>
                      <div className="mapx-meta-row">
                        <span className="mapx-meta-label">{t("mapEditor.resolverContextLabel")}</span>
                        <span className="mapx-meta-value">
                          {t("mapEditor.resolveContext", {
                            environment: integrationMeta.environment || "*",
                            usageMode: integrationMeta.usageMode || "*",
                          })}
                        </span>
                        <button type="button" className="mapx-btn" onClick={resolveSelectedFuncMapping} disabled={resolveState === "loading"}>
                          {resolveState === "loading" ? "…" : t("mapEditor.resolveMapping")}
                        </button>
                      </div>
                      {resolveError && <div className="mapx-error">{resolveError}</div>}
                      {resolveResult && <pre>{JSON.stringify(resolveResult, null, 2)}</pre>}
                    </div>
                    <div className="mapx-meta-box">
                      <div className="mapx-meta-title">{t("mapEditor.liveEventsTitle")}</div>
                      <div className="mapx-live-toolbar">
                        <span className={`cql-status ${eventsWsState === "live" ? "cql-status--online" : ""}`}>
                          {eventsWsState === "live"
                            ? t("mapEditor.liveEventsConnected")
                            : eventsWsState === "connecting"
                              ? t("mapEditor.liveEventsConnecting")
                              : t("mapEditor.liveEventsDisconnected")}
                        </span>
                        <button type="button" className="mapx-btn" onClick={loadRecentHardwareEvents}>
                          {t("mapEditor.liveEventsRefresh")}
                        </button>
                        <button
                          type="button"
                          className="mapx-btn"
                          onClick={() => setHardwareEvents([])}
                        >
                          {t("mapEditor.liveEventsClear")}
                        </button>
                        <button
                          type="button"
                          className="mapx-btn"
                          onClick={() => clearServerHardwareEvents(false)}
                          disabled={eventsClearState === "clearing" || !canClearServerEvents}
                        >
                          {eventsClearState === "clearing"
                            ? t("mapEditor.liveEventsClearingServer")
                            : t("mapEditor.liveEventsClearServer")}
                        </button>
                        <button
                          type="button"
                          className="mapx-btn mapx-btn-danger"
                          onClick={() => clearServerHardwareEvents(true)}
                          disabled={eventsClearState === "clearing" || !canClearPersistentEvents}
                        >
                          {eventsClearState === "clearing"
                            ? t("mapEditor.liveEventsClearingPersistent")
                            : t("mapEditor.liveEventsClearPersistent")}
                        </button>
                      </div>
                      {!canClearServerEvents && (
                        <div className="mapx-meta-value">{t("mapEditor.liveEventsOperatorOnly")}</div>
                      )}
                      {canClearServerEvents && !canClearPersistentEvents && (
                        <div className="mapx-meta-value">{t("mapEditor.liveEventsAdminOnly")}</div>
                      )}
                      {eventsStorePath && (
                        <div className="mapx-meta-value">{t("mapEditor.liveEventsStorePath", { path: eventsStorePath })}</div>
                      )}
                      <div className="mapx-live-filters">
                        <input
                          type="search"
                          className="mapx-def-filter"
                          placeholder={t("mapEditor.liveFilterPeripheral")}
                          value={eventsPeripheralFilter}
                          onChange={(e) => setEventsPeripheralFilter(e.target.value)}
                        />
                        <input
                          type="search"
                          className="mapx-def-filter"
                          placeholder={t("mapEditor.liveFilterCommand")}
                          value={eventsCommandFilter}
                          onChange={(e) => setEventsCommandFilter(e.target.value)}
                        />
                      </div>
                      {eventsWsError && <div className="mapx-error">{eventsWsError}</div>}
                      {filteredHardwareEvents.length === 0 ? (
                        <div className="mapx-empty">{t("mapEditor.liveEventsEmpty")}</div>
                      ) : (
                        <div className="hw-log-list">
                          {filteredHardwareEvents.map((eventItem) => (
                            <div
                              key={eventItem.id}
                              className={`hw-log-row ${
                                eventItem.status === "error" ? "hw-log-error" : "hw-log-ok"
                              }`}
                            >
                              <span className="hw-log-time">
                                {new Date(eventItem.timestamp).toLocaleTimeString()}
                              </span>
                              <span className="hw-log-level">{eventItem.commandName || "command"}</span>
                              <span>
                                {eventItem.peripheralId || "—"}
                                <span className="hw-log-detail">{eventItem.status}</span>
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
