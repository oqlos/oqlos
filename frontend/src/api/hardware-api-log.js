export const HARDWARE_API_LOG_TAG = "[HardwareApi]";

const WIZARD_PATH_FRAGMENTS = ["modbus/wizard", "modbus/waveshare-diagnose"];

export function isHardwareWizardPath(path) {
  const normalized = String(path || "");
  return WIZARD_PATH_FRAGMENTS.some((fragment) => normalized.includes(fragment));
}

export function summarizeHardwareApiBody(path, body) {
  if (body === undefined || body === null) {
    return undefined;
  }
  if (typeof body !== "object") {
    return String(body).slice(0, 80);
  }

  const normalized = String(path || "");
  if (normalized.includes("/mapping")) {
    return { keys: Object.keys(body).slice(0, 8) };
  }
  if (normalized.includes("probe-isolated")) {
    return {
      serial_port: body.serial_port,
      baudrates: Array.isArray(body.baudrates) ? body.baudrates.length : undefined,
      parities: body.parities,
      device_ids: Array.isArray(body.device_ids) ? body.device_ids.length : undefined,
    };
  }
  if (normalized.includes("program-isolated")) {
    return {
      serial_port: body.serial_port,
      current_device_id: body.current_device_id,
      new_device_id: body.new_device_id,
      new_baudrate: body.new_baudrate,
      new_parity: body.new_parity,
      confirm_isolated: body.confirm_isolated,
    };
  }

  const keys = Object.keys(body);
  if (keys.length <= 6) {
    return body;
  }
  return { keys: keys.slice(0, 8), more: keys.length - 8 };
}

export function summarizeHardwareApiResponse(path, payload) {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }

  const normalized = String(path || "");
  if (normalized.includes("probe-isolated")) {
    return {
      ok: payload.ok,
      candidates: Array.isArray(payload.candidates) ? payload.candidates.length : undefined,
    };
  }
  if (normalized.includes("program-isolated")) {
    return { ok: payload.ok, verified: payload.verified };
  }
  if (normalized.includes("wizard/plan")) {
    return {
      steps: Array.isArray(payload.steps) ? payload.steps.length : undefined,
      serial_port: payload.serial_port,
    };
  }
  if (normalized.includes("waveshare-diagnose")) {
    return { ok: payload.ok };
  }
  return undefined;
}

export function logHardwareApiEvent(event, path, meta = {}) {
  const record = { event, path, ...meta };
  const isFailure = event === "error" || (event === "response" && Number(meta.status) >= 400);

  if (isFailure) {
    console.error(HARDWARE_API_LOG_TAG, event, record);
    return;
  }

  if (import.meta.env.DEV || isHardwareWizardPath(path)) {
    console.debug(HARDWARE_API_LOG_TAG, event, record);
  }
}
