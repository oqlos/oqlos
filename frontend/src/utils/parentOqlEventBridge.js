const PROTOCOL_VERSION = "1.0";
const DEFAULT_TIMEOUT_MS = 10000;

export class ParentOqlEventError extends Error {
  constructor(details = {}) {
    const message = String(details.message || "Parent OQL event failed");
    super(message);
    this.name = "ParentOqlEventError";
    this.errorCode = details.error_code;
    this.statusCode = details.status_code;
    this.correlationId = details.correlation_id;
    this.processUri = details.process_uri;
    this.runId = details.run_id;
    this.stage = details.stage;
    this.component = details.component;
    this.failureCodes = Array.isArray(details.failure_codes) ? details.failure_codes : [];
    this.hint = details.hint;
    this.issues = Array.isArray(details.issues) ? details.issues : [];
  }
}

function parentOrigin() {
  try {
    const raw = new URLSearchParams(globalThis.location?.search || "").get("parent_origin");
    return raw ? new URL(raw).origin : "";
  } catch {
    return "";
  }
}

function requestId() {
  try {
    if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  } catch {
    // Stable fallback below.
  }
  return `oql_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * Ask the authenticated Connect host to execute one declared OQL event.
 * Returns null outside an iframe, allowing the standalone OqlOS UI to use its
 * local process endpoint without pretending that it has the host session.
 */
export function requestParentOqlEvent(name, payload, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const origin = parentOrigin();
  if (!origin || !globalThis.parent || globalThis.parent === globalThis) {
    return Promise.resolve(null);
  }
  const id = requestId();
  return new Promise((resolve, reject) => {
    const timer = globalThis.setTimeout(() => {
      globalThis.removeEventListener("message", onMessage);
      reject(new Error(`OQL event '${name}' timed out`));
    }, timeoutMs);
    const onMessage = (event) => {
      const envelope = event.data;
      if (
        event.origin !== origin
        || event.source !== globalThis.parent
        || !envelope
        || envelope.type !== "parent.oqlEvent.response"
        || envelope.version !== PROTOCOL_VERSION
        || envelope.requestId !== id
      ) return;
      globalThis.clearTimeout(timer);
      globalThis.removeEventListener("message", onMessage);
      if (envelope.payload?.ok === true) {
        resolve(envelope.payload.result);
      } else {
        const error = envelope.payload?.error;
        reject(new ParentOqlEventError(
          error && typeof error === "object"
            ? error
            : { message: String(error || `OQL event '${name}' failed`) },
        ));
      }
    };
    globalThis.addEventListener("message", onMessage);
    globalThis.parent.postMessage({
      type: "child.oqlEvent.request",
      version: PROTOCOL_VERSION,
      requestId: id,
      timestamp: new Date().toISOString(),
      payload: { name, payload },
    }, origin);
  });
}
