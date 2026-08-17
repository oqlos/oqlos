import {
  CONNECT_HARDWARE_PATHS,
  connectCqrsEventsPath,
  connectDiagnosticCommandPath,
  connectPeripheralStatusPath,
} from "@semcod/hardware-client/paths.js";
import {
  logHardwareApiEvent,
  summarizeHardwareApiBody,
  summarizeHardwareApiResponse,
} from "./hardware-api-log.js";
import { extractDiagnosticFailure } from "./hardware-diagnostic-failure.js";
import { describeDetail, formatHardwareApiError, tryParseJson } from "./hardware-api-errors.js";

export { extractDiagnosticFailure } from "./hardware-diagnostic-failure.js";
export { formatHardwareApiError, parseOqlError } from "./hardware-api-errors.js";

const API_BASE = (import.meta.env?.VITE_API_BASE || "").replace(/\/$/, "");

function _withCtx(logContext) {
  return logContext ? { context: logContext } : {};
}

function _throwHttpError(res, text, path, message, detailMessage) {
  const err = new Error(message);
  err.status = res.status;
  err.path = path;
  err.body = text;
  err.payload = tryParseJson(text);
  throw err;
}

async function request(path, { method = "GET", body, logContext, headers: extraHeaders } = {}) {
  const startedAt = performance.now();
  const bodySummary = summarizeHardwareApiBody(path, body);
  logHardwareApiEvent("request", path, {
    method,
    ..._withCtx(logContext),
    ...(bodySummary !== undefined ? { body: bodySummary } : {}),
  });

  const init = {
    method,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(extraHeaders || {}),
    },
  };
  if (body !== undefined) init.body = JSON.stringify(body ?? {});

  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init });
  } catch (err) {
    const durationMs = Math.round(performance.now() - startedAt);
    logHardwareApiEvent("error", path, {
      method,
      duration_ms: durationMs,
      error: err instanceof Error ? err.message : String(err),
      ..._withCtx(logContext),
    });
    throw err;
  }

  const durationMs = Math.round(performance.now() - startedAt);

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    const payload = tryParseJson(text);
    const detailMessage = describeDetail(payload?.detail ?? payload);
    const message = detailMessage || `HTTP ${res.status} ${res.statusText} - ${path}`;
    logHardwareApiEvent("error", path, {
      method,
      status: res.status,
      duration_ms: durationMs,
      error: message,
      ...(detailMessage ? { detail: detailMessage } : {}),
      ..._withCtx(logContext),
    });
    _throwHttpError(res, text, path, message, detailMessage);
  }

  const data = await res.json();
  const summary = summarizeHardwareApiResponse(path, data);
  logHardwareApiEvent("response", path, {
    method,
    status: res.status,
    duration_ms: durationMs,
    ...(summary ? { summary } : {}),
    ...(logContext ? { context: logContext } : {}),
  });
  return data;
}

async function get(path, options) {
  return request(path, { method: "GET", ...options });
}

async function post(path, body, options) {
  return request(path, { method: "POST", body, ...options });
}

async function put(path, body, options) {
  return request(path, { method: "PUT", body, ...options });
}

export const HardwareApi = {
  async health() {
    return get("/api/v3/hardware/health");
  },

  async identify(options) {
    return get("/api/v3/hardware/identify", options);
  },

  async proxyInfo(options) {
    return get("/api/v3/hardware/proxy-info", options);
  },

  async executePluginCommand(pluginId, command, params = {}, options) {
    // Direct plugin channel: the M5 valve stage is addressed by its own id even
    // while the gateway still routes logical valves to another output module.
    // Send both params and args — older firmware only read one of the keys.
    const kwargs = params && typeof params === "object" ? params : {};
    return post(
      `/api/v1/plugins/${encodeURIComponent(pluginId)}/execute`,
      { command, params: kwargs, args: kwargs },
      options,
    );
  },

  async peripheralStatus(peripheralId, options) {
    return get(`/api/v3/hardware/peripheral-status/${encodeURIComponent(peripheralId)}`, options);
  },

  async runDiagnosticCommand(payload, options) {
    const data = await post("/api/v3/hardware/diagnostic-command", payload, options);
    const failure = extractDiagnosticFailure(data);
    const peripheralId = String(payload?.peripheral_id || "").trim().toLowerCase();
    if (failure && peripheralId === "rtc") {
      return {
        ...data,
        ok: false,
        optional: true,
        error: failure,
      };
    }
    if (failure) {
      const err = new Error(failure);
      err.status = 200;
      err.commandResult = data;
      err.body = JSON.stringify(data);
      throw err;
    }
    return data;
  },

  async runModbusAutoconfigure(options) {
    return post("/api/v3/hardware/modbus/autoconfigure", {}, options);
  },

  /** Per-device diagnosis plan (environment + recommended actions, no repairs). */
  async getIntelligentDiagnosis(options = {}) {
    const devices = options.devices ? `?devices=${encodeURIComponent(options.devices)}` : "";
    return get(`/api/v3/hardware/diagnosis${devices}`, options);
  },

  /** Diagnose + run targeted auto-repair (motors / Modbus), return before/after. */
  async runDiagnosisRepair(options = {}) {
    const devices = options.devices ? `?devices=${encodeURIComponent(options.devices)}` : "";
    return post(`/api/v3/hardware/diagnosis/repair${devices}`, {}, options);
  },

  async getModbusWaveshareDiagnose(options) {
    return get("/api/v3/hardware/modbus/waveshare-diagnose", options);
  },

  async getModbusWizardPlan(options) {
    return get("/api/v3/hardware/modbus/wizard/plan", options);
  },

  async getModbusSettings(options) {
    return get("/api/v3/hardware/modbus/settings", options);
  },

  async updateModbusSettings(payload, options) {
    return put("/api/v3/hardware/modbus/settings", payload || {}, options);
  },

  async getModbusProfileChannels(profileId, options = {}) {
    const query = profileId ? `?profile=${encodeURIComponent(profileId)}` : "";
    return get(`/api/v3/hardware/modbus/profile-channels${query}`, options);
  },

  async writeModbusChannelValue(payload, options) {
    return put("/api/v3/hardware/modbus/channel-value", payload || {}, options);
  },

  async getCoilTestPlan(options) {
    return get("/api/v3/hardware/modbus/coil-test/plan", options);
  },

  async pulseCoil(payload, options) {
    return post("/api/v3/hardware/modbus/coil-test/pulse", payload || {}, options);
  },

  async stopAllCoils(options) {
    return post("/api/v3/hardware/modbus/coil-test/stop", {}, options);
  },

  async getRtcStatus(options) {
    return get("/api/v3/hardware/rtc/status", options);
  },

  async runRtcCommand(command, args = {}, options) {
    return post("/api/v3/hardware/rtc/command", { command, args: args || {} }, options);
  },

  /** Central autodetect + wizard plan (starts OqlOS if down). Prefer over raw plan on /hardware-modbus. */
  async getHardwareStackSnapshot(options) {
    return get("/api/v3/hardware/stack/snapshot", options);
  },

  async stopOqlosRuntime(options = {}) {
    const serialPort = options.serialPort || options.serial_port || "";
    return post("/api/v3/hardware/runtime/stop", serialPort ? { serial_port: serialPort } : {}, options);
  },

  async getOqlosRuntimeStatus(serialPort, options) {
    const query = serialPort ? `?serial_port=${encodeURIComponent(serialPort)}` : "";
    return get(`/api/v3/hardware/runtime/status${query}`, options);
  },

  async startOqlosRuntime(options = {}) {
    const mode = options.mode === "full" ? "full" : "light";
    return post("/api/v3/hardware/runtime/start", { mode }, options);
  },

  async runC2004Make(target, options = {}) {
    const normalized = String(target || "").trim();
    return post("/api/v3/hardware/runtime/make", { target: normalized }, options);
  },

  /** Whole-board system reboot (sudo systemctl reboot on the hardware host). */
  async rebootHost(options = {}) {
    return post("/api/v3/hardware/host/reboot", { confirm: true }, options);
  },

  async listHardwareLogs(options) {
    return get("/api/v3/hardware/logs", options);
  },

  async readHardwareLog(logId, options = {}) {
    const lines = options.lines ? `?lines=${encodeURIComponent(String(options.lines))}` : "";
    return get(`/api/v3/hardware/logs/${encodeURIComponent(logId)}${lines}`, options);
  },

  async probeModbusWizardIsolated(payload, options) {
    return post("/api/v3/hardware/modbus/wizard/probe-isolated", payload || {}, options);
  },

  async programModbusWizardIsolated(payload, options) {
    return post("/api/v3/hardware/modbus/wizard/program-isolated", payload || {}, options);
  },

  async executeHardwareCqrsCommand(payload) {
    return post(CONNECT_HARDWARE_PATHS.cqrsCommand, payload);
  },

  async listHardwareCqrsEvents(limit = 50) {
    return get(connectCqrsEventsPath(limit));
  },

  async clearHardwareCqrsEvents(payload = { truncate_persistent: false }) {
    return post(CONNECT_HARDWARE_PATHS.cqrsEventsClear, payload);
  },

  async getScannerStatus(options) {
    return get(CONNECT_HARDWARE_PATHS.scannerStatus, options);
  },

  async getScannerLast(options) {
    return get(CONNECT_HARDWARE_PATHS.scannerLast, options);
  },

  async ingestScannerCode(payload, options) {
    return post(CONNECT_HARDWARE_PATHS.scannerIngest, payload, options);
  },
};
