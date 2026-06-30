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

export { tryParseJson, describeDetail };
