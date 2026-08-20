import { parseConnectRole } from "./rbac.policy.js";

export const COIL_RESULT_OPTIONS = ["correct", "wrong", "no_response"];
export const COIL_PULSE_DURATION_MS = 300;

export function nextUntestedCoil(coils = [], results = {}) {
  return coils.find((coil) => !results[String(coil.address)]) || null;
}

export function buildCoilTestReport(plan, results, pulses) {
  return {
    schema: "oqlos-boardnet-valve-controller-test-v2",
    generated_at: new Date().toISOString(),
    boardnet: {
      mode: plan?.mode || "unknown",
      module: plan?.module || {},
      safety: plan?.safety || {},
    },
    coils: (plan?.coils || []).map((coil) => ({
      ...coil,
      operator_result: results[String(coil.address)] || "not_tested",
      pulse: pulses[String(coil.address)] || null,
    })),
  };
}

export function pulseConfirmation(coil) {
  return `PULSE_DO${Number(coil?.address) + 1}`;
}

/**
 * Pass the already-normalized Connect UI role to the guarded pulse endpoint.
 * This does not grant a role: the endpoint still rejects every value outside
 * system/admin and keeps confirmation, preflight, locking and automatic OFF.
 */
export function coilPulseRequestOptions(role, logContext) {
  const normalized = parseConnectRole(role);
  const privileged = normalized === "system" || normalized === "admin";
  return {
    ...(logContext ? { logContext } : {}),
    ...(privileged ? { headers: { "X-Connect-Role": normalized } } : {}),
  };
}

function urlToken(value, fallback = "UNKNOWN") {
  const token = String(value ?? "")
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9_-]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 96);
  return token || fallback;
}

export function coilPulseIntentUrlArgs(coil, role) {
  const address = Number(coil?.address);
  const id = coil?.id || (Number.isInteger(address) ? `DO${address + 1}` : "UNKNOWN");
  return {
    COMMAND: "coil-test-pulse",
    COIL: urlToken(id),
    ADDRESS: Number.isInteger(address) ? String(address) : "UNKNOWN",
    DURATION_MS: String(COIL_PULSE_DURATION_MS),
    CONFIRM: pulseConfirmation(coil),
    REQUEST_ROLE: parseConnectRole(role) || urlToken(role),
  };
}

export function coilStopIntentUrlArgs(role) {
  return {
    COMMAND: "coil-test-stop",
    COILS: "ACTIVE-CONTROLLER",
    REQUEST_ROLE: parseConnectRole(role) || urlToken(role),
  };
}

function errorPayloads(error) {
  return [error, error?.payload, error?.payload?.detail, error?.commandResult].filter(Boolean);
}

/** Return stable, comma-safe ERROR tokens suitable for the ERRORS URL arg. */
export function coilCommandErrorCodes(error, fallback = "COIL_COMMAND_FAILED") {
  const codes = [];
  const add = (value) => {
    if (value == null || value === "") return;
    const code = urlToken(value, "");
    if (code && !codes.includes(code)) codes.push(code);
  };

  errorPayloads(error).forEach((payload) => {
    add(payload?.error_code);
    add(payload?.code);
  });
  if (Number.isInteger(Number(error?.status))) add(`HTTP_${Number(error.status)}`);

  const message = errorPayloads(error)
    .map((payload) => typeof payload === "string" ? payload : payload?.message || payload?.error || payload?.detail || "")
    .join(" ")
    .toLowerCase();
  if (message.includes("coil pulse requires") || (Number(error?.status) === 403 && message.includes("role"))) {
    add("COIL_PULSE_ROLE_REQUIRED");
  }
  if (message.includes("modbus") && (message.includes("unavailable") || message.includes("inactive"))) {
    add("MODBUS_IO_UNAVAILABLE");
  }
  if (codes.length === 0) add(fallback);
  return codes;
}

export function coilCommandResultUrlArgs(intent, result, error = null) {
  const normalizedResult = String(result || "PENDING").toUpperCase();
  const errors = normalizedResult === "OK"
    ? ["NONE"]
    : normalizedResult === "PENDING"
      ? ["PENDING"]
      : coilCommandErrorCodes(error);
  return {
    ...(intent || {}),
    RESULT: normalizedResult,
    HTTP_STATUS: error?.status ? String(error.status) : normalizedResult === "OK" ? "200" : "PENDING",
    ERRORS: errors.join(","),
  };
}
