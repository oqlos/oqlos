// Bridge OqlOS iframe URL state into the embedding shell URL.
//
// When OqlOS runs inside the Connect shell (port 8100 shell → iframe →
// BoardNet :8202), only the iframe URL changes by default. The parent shell
// would otherwise lose command/debug context when operators share the URL.
//
// `frontend/src/pages/helpers/oqlos-hardware-iframe.ts` wires an
// `oqlos-hardware:navigate` postMessage listener that merges arbitrary search
// params from the iframe into the parent URL via `URLSearchParams.set`. This
// module is the sender side of that protocol.
//
// Behaviour:
//   - No-op when we are not embedded (window.parent === window or no window).
//   - Empty/null/undefined values are skipped (the parent handler can only
//     set, not delete — sending an empty value would clear the key).
//   - Best-effort: never throws.

export const OQLOS_PARENT_NAVIGATE_MESSAGE = "oqlos-hardware:navigate";

export function bridgeSearchToParent(partial, messageType = OQLOS_PARENT_NAVIGATE_MESSAGE) {
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
    window.parent.postMessage({ type: messageType, search }, "*");
  } catch {
    // Embedding shell unreachable — fall back to local URL only.
  }
}
