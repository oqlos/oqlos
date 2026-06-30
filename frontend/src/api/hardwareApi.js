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

const API_BASE = (import.meta.env?.VITE_API_BASE || "").replace(/\/$/, "");

function tryParseJson(text) {
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function describeDetail(detail) {
  if (!detail) {
    return "";
  }

  if (typeof detail === "string") {
    return detail;
  }

  if (typeof detail !== "object") {
    return String(detail);
  }

  const message = detail.error || detail.message || detail.detail;
  const issues = Array.isArray(detail.issues) ? detail.issues.filter(Boolean).map(String) : [];
  const lastError = detail.last_error || detail.lastError;
  if (message && issues.length > 0) {
    return `${message}: ${issues.join("; ")}`;
  }
  if (message && lastError) {
    return `${message} (${lastError})`;
  }
  if (message) {
    return String(message);
  }

  return JSON.stringify(detail);
}

function extractErrorPayload(err) {
  if (!err) {
    return null;
  }

  if (err.commandResult) {
    return err.commandResult;
  }

  if (err.payload) {
    return err.payload;
  }

  return tryParseJson(err.body);
}

const TIC249_DEENERGIZE_COMMANDS = new Set(["motor_disable", "deenergize", "disable", "standby"]);

function tic249ResultStatus(result) {
  if (!result || typeof result !== "object") {
    return "";
  }
  const data = result.data && typeof result.data === "object" ? result.data : null;
  return String(result.status || data?.status || "").toLowerCase();
}

function isIdempotentTic249Deenergized(command, result) {
  if (!TIC249_DEENERGIZE_COMMANDS.has(command)) {
    return false;
  }
  if (result?.idempotent_success) {
    return true;
  }
  const status = tic249ResultStatus(result);
  if (status === "de-energized" || status === "disabled") {
    return !result?.error;
  }
  const data = result?.data;
  if (data && typeof data === "object" && data.energized === false && !data.error) {
    return true;
  }
  return false;
}

export function formatHardwareApiError(err, fallback = "Hardware API request failed") {
  if (!err) {
    return fallback;
  }

  const payload = extractErrorPayload(err);
  const detail = payload?.detail ?? payload?.error ?? payload;
  const detailMessage = describeDetail(detail);
  if (detailMessage) {
    return detailMessage;
  }

  return err.message || fallback;
}

export function extractDiagnosticFailure(payload) {
  const command = String(payload?.command || "").toLowerCase();
  const result = payload?.result;
  const status = tic249ResultStatus(result);
  const isIdempotentLungState =
    isIdempotentTic249Deenergized(command, result) ||
    (command === "lung_stop" && status === "stopped");
  if (isIdempotentLungState && !payload?.result?.error) {
    return "";
  }

  if (payload?.ok === false) {
    const result = payload?.result;
    const data = result?.data && typeof result.data === "object" ? result.data : null;
    const nested =
      result?.error ||
      data?.error ||
      data?.message ||
      (data?.connected === false ? data?.error || "Tic249 motor is not connected" : "");
    const genericErrors = new Set([
      "Command failed",
      "Command failed (ok=false)",
      "Diagnostic command failed",
    ]);
    const nestedOkMsg =
      result?.ok && typeof result.ok === "object"
        ? String(result.ok.message || result.ok.error || "").trim()
        : "";
    const candidates = [nested, nestedOkMsg, payload?.error].filter(Boolean);
    const detail = candidates.find((value) => !genericErrors.has(String(value))) || candidates[0];
    if (detail) {
      return String(detail);
    }
    if (result?.base_url && result?.path) {
      return `Tic249 command failed (${result.base_url}${result.path})`;
    }
    return "Diagnostic command failed";
  }

  if (!result || typeof result !== "object") {
    return "";
  }

  if (result.success === false) {
    const data = result?.data && typeof result.data === "object" ? result.data : null;
    const nested = result.error || data?.error || data?.message || payload?.error;
    const genericErrors = new Set(["Command failed", "Command failed (ok=false)"]);
    if (nested && !genericErrors.has(String(nested))) {
      return String(nested);
    }
    if (data?.connected === false) {
      return String(data?.error || "Tic249 motor is not connected");
    }
    return String(nested || "Diagnostic command failed");
  }

  const nestedOk = result.ok;
  if (nestedOk === false) {
    if (isIdempotentTic249Deenergized(command, result)) {
      return "";
    }
    return String(payload?.error || result.error || "Command failed (ok=false)");
  }
  if (nestedOk && typeof nestedOk === "object" && nestedOk.success === false) {
    const fromNested = String(nestedOk.error || nestedOk.message || "").trim();
    const fromPayload = String(payload?.error || "").trim();
    const genericErrors = new Set([
      "Command failed",
      "Command failed (ok=false)",
      "Diagnostic command failed",
    ]);
    if (fromPayload && !genericErrors.has(fromPayload)) {
      return fromPayload;
    }
    if (fromNested) {
      return fromNested;
    }
    return fromPayload || "DRI0050 pump command failed (no detail from driver)";
  }

  return "";
}

async function request(path, { method = "GET", body, logContext } = {}) {
  const startedAt = performance.now();
  const bodySummary = summarizeHardwareApiBody(path, body);
  logHardwareApiEvent("request", path, {
    method,
    ...(logContext ? { context: logContext } : {}),
    ...(bodySummary !== undefined ? { body: bodySummary } : {}),
  });

  const init = {
    method,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
  };
  if (body !== undefined) {
    init.body = JSON.stringify(body ?? {});
  }

  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
    });
  } catch (err) {
    const durationMs = Math.round(performance.now() - startedAt);
    logHardwareApiEvent("error", path, {
      method,
      duration_ms: durationMs,
      error: err instanceof Error ? err.message : String(err),
      ...(logContext ? { context: logContext } : {}),
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
      ...(logContext ? { context: logContext } : {}),
    });
    const err = new Error(message);
    err.status = res.status;
    err.path = path;
    err.body = text;
    err.payload = payload;
    throw err;
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
  async getIntelligentDiagnosis(options) {
    return get("/api/v3/hardware/diagnosis", options);
  },

  /** Diagnose + run targeted auto-repair (motors / Modbus), return before/after. */
  async runDiagnosisRepair(options) {
    return post("/api/v3/hardware/diagnosis/repair", {}, options);
  },

  async getModbusWaveshareDiagnose(options) {
    return get("/api/v3/hardware/modbus/waveshare-diagnose", options);
  },

  async getModbusWizardPlan(options) {
    return get("/api/v3/hardware/modbus/wizard/plan", options);
  },

  /** Central autodetect + wizard plan (starts OqlOS if down). Prefer over raw plan on /hardware-restart. */
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

  async probeModbusWizardIsolated(payload, options) {
    return post("/api/v3/hardware/modbus/wizard/probe-isolated", payload || {}, options);
  },

  async programModbusWizardIsolated(payload, options) {
    return post("/api/v3/hardware/modbus/wizard/program-isolated", payload || {}, options);
  },

  async executeRuntimePython(payload) {
    return post(CONNECT_HARDWARE_PATHS.runtimePython, payload);
  },

  async resolveRuntimeFuncMapping(payload) {
    return post(CONNECT_HARDWARE_PATHS.runtimePythonResolveFunc, payload);
  },

  async getMapping() {
    return get(CONNECT_HARDWARE_PATHS.mapping);
  },

  async getMappingSchema() {
    return get(CONNECT_HARDWARE_PATHS.mappingSchema);
  },

  async replaceMapping(payload) {
    return put(CONNECT_HARDWARE_PATHS.mapping, payload);
  },

  async importMapping(payload) {
    return post(CONNECT_HARDWARE_PATHS.mappingImport, payload);
  },

  async exportMapping(payload) {
    return post(CONNECT_HARDWARE_PATHS.mappingExport, payload);
  },

  async resetMapping(payload = { persist: true }) {
    return post(CONNECT_HARDWARE_PATHS.mappingReset, payload);
  },

  async executeOqlMapped(payload) {
    return post(CONNECT_HARDWARE_PATHS.oqlMappedExec, payload);
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
