// Bridge connect-scenario iframe URL state into the embedding shell URL.
//
// When connect-scenario runs inside maskservice at /connect-scenario (port
// 8100 reverse-proxy → 8081 frontend → iframe → :8096), only the iframe URL
// changes when the user selects a device or a test. The parent shell URL
// remains at /connect-scenario?... and operators lose the context if they
// share or reload the URL.
//
// `frontend/src/pages/helpers/embedded-app-iframe.ts` already wires a
// `cql:navigate` postMessage listener that merges arbitrary search params
// from the iframe into the parent URL via `URLSearchParams.set`. This module
// is the sender side of that protocol.
//
// Behaviour:
//   - No-op when we are not embedded (window.parent === window or no window).
//   - Empty/null/undefined values are skipped (the parent handler can only
//     set, not delete — sending an empty value would clear the key).
//   - Best-effort: never throws.

export function bridgeSearchToParent(partial) {
  try {
    if (typeof window === "undefined") return;
    if (!window.parent || window.parent === window) return;

    const filtered = {};
    Object.entries(partial || {}).forEach(([key, value]) => {
      if (value === null || value === undefined) return;
      const text = String(value);
      if (text === "") return;
      filtered[key] = text;
    });
    if (Object.keys(filtered).length === 0) return;

    const search = new URLSearchParams(filtered).toString();
    window.parent.postMessage({ type: "cql:navigate", search }, "*");
  } catch {
    // Embedding shell unreachable — fall back to local URL only.
  }
}
