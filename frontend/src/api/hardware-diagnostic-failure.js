import {
  isIdempotentDiagnosticSuccess,
  isIdempotentTic249Deenergized,
  tic249ResultStatus,
} from "./hardware-tic249-status.js";

const GENERIC_DIAGNOSTIC_ERRORS = new Set([
  "Command failed",
  "Command failed (ok=false)",
  "Diagnostic command failed",
]);

function resultData(result) {
  return result?.data && typeof result.data === "object" ? result.data : null;
}

function firstActionableError(candidates, genericErrors = GENERIC_DIAGNOSTIC_ERRORS) {
  const values = candidates.filter(Boolean);
  return values.find((value) => !genericErrors.has(String(value))) || values[0] || "";
}

function failureFromOkFalsePayload(payload) {
  const result = payload?.result;
  const data = resultData(result);
  const nested =
    result?.error ||
    data?.error ||
    data?.message ||
    (data?.connected === false ? data?.error || "Tic249 motor is not connected" : "");
  const nestedOkMsg =
    result?.ok && typeof result.ok === "object"
      ? String(result.ok.message || result.ok.error || "").trim()
      : "";
  const detail = firstActionableError([nested, nestedOkMsg, payload?.error]);
  if (detail) {
    return String(detail);
  }
  if (result?.base_url && result?.path) {
    return `Tic249 command failed (${result.base_url}${result.path})`;
  }
  return "Diagnostic command failed";
}

function failureFromSuccessFalse(payload, result) {
  const data = resultData(result);
  const nested = result.error || data?.error || data?.message || payload?.error;
  if (nested && !GENERIC_DIAGNOSTIC_ERRORS.has(String(nested))) {
    return String(nested);
  }
  if (data?.connected === false) {
    return String(data?.error || "Tic249 motor is not connected");
  }
  return String(nested || "Diagnostic command failed");
}

function failureFromNestedOk(command, payload, result) {
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
    if (fromPayload && !GENERIC_DIAGNOSTIC_ERRORS.has(fromPayload)) {
      return fromPayload;
    }
    if (fromNested) {
      return fromNested;
    }
    return fromPayload || "DRI0050 pump command failed (no detail from driver)";
  }
  return "";
}

export function extractDiagnosticFailure(payload) {
  const command = String(payload?.command || "").toLowerCase();
  const result = payload?.result;

  if (isIdempotentDiagnosticSuccess(command, result) && !payload?.result?.error) {
    return "";
  }

  if (payload?.ok === false) {
    return failureFromOkFalsePayload(payload);
  }

  if (!result || typeof result !== "object") {
    return "";
  }

  if (result.success === false) {
    return failureFromSuccessFalse(payload, result);
  }

  return failureFromNestedOk(command, payload, result);
}

// Exported for tests and callers that need status without full failure extraction.
export { tic249ResultStatus };
