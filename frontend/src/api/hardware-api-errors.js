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

function isProcessDiagnostic(err) {
  return Boolean(err.errorCode || err.correlationId || err.hint || err.component);
}

function processDiagnosticContext(err) {
  return [
    err.component ? `komponent: ${err.component}` : "",
    err.stage ? `etap: ${err.stage}` : "",
    err.runId ? `run: ${err.runId}` : "",
    err.correlationId ? `korelacja: ${err.correlationId}` : "",
  ].filter(Boolean).join(" · ");
}

function processDiagnosticCauses(err) {
  return [
    ...(Array.isArray(err.failureCodes) ? err.failureCodes : []),
    ...(Array.isArray(err.issues) ? err.issues : []),
  ];
}

function formatProcessDiagnostic(err, fallback) {
  const message = String(err.message || fallback);
  const firstLine = err.errorCode && !message.includes(err.errorCode)
    ? `${err.errorCode} · ${message}`
    : message;
  const causes = processDiagnosticCauses(err);
  return [
    firstLine,
    processDiagnosticContext(err),
    causes.length ? `przyczyny: ${causes.join("; ")}` : "",
    err.hint ? `zalecenie: ${err.hint}` : "",
  ].filter(Boolean).join("\n");
}

function formatPayloadError(payload) {
  const oqlError = parseOqlError(payload);
  if (oqlError) return oqlError.message;
  return describeDetail(payload?.detail ?? payload?.error ?? payload);
}

/**
 * Parse the standard OqlIssue body (see oqlos/errors/catalog.py /
 * oqlos.errors.OqlosError) out of a backend response payload.
 * Returns null when the payload isn't in the OqlIssue shape — callers should
 * fall back to the older, defensive `describeDetail` cascade in that case.
 */
export function parseOqlError(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload) || !payload.code) {
    return null;
  }
  return {
    code: payload.code,
    domain: payload.domain || "unknown",
    severity: payload.severity || "error",
    message: payload.message || payload.code,
    detail: payload.detail ?? null,
    repair: payload.repair ?? null,
  };
}

export function formatHardwareApiError(err, fallback = "Hardware API request failed") {
  if (!err) return fallback;
  if (isProcessDiagnostic(err)) return formatProcessDiagnostic(err, fallback);
  const payload = extractErrorPayload(err);
  return formatPayloadError(payload) || err.message || fallback;
}

export { tryParseJson, describeDetail };
