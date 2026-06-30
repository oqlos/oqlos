/** Static wizard troubleshooting doc (served from connect-scenario frontend `public/docs/`). */
export const HARDWARE_RESTART_DOCS_PATH = "/docs/hardware-restart.md";

/**
 * @param {string} [origin] — e.g. `window.location.origin`; empty uses site-relative path.
 * @returns {string}
 */
export function hardwareRestartDocsUrl(origin = "") {
  const base = String(origin || "").replace(/\/$/, "");
  return `${base}${HARDWARE_RESTART_DOCS_PATH}`;
}
