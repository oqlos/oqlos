/** Cross-frame + localStorage helpers for auto-collapsing side panels. */

export const COLLAPSE_DELAY_MS = 3000;

/** Stable ids for `child.collapse-toggle.register` (scoped as `cql:<id>` in parent iframe). */
export const COLLAPSE_TOGGLE_IDS = Object.freeze({
  scenariosList: "scenarios-list",
  funcEditorList: "func-editor-list",
  mapEditorDefinitions: "map-editor-definitions",
  oqlProtocolNav: "oql-protocol-nav",
  scenarioTerminal: "scenario-terminal",
  scenarioExecutionStatus: "scenario-execution-status",
  scenarioReportJson: "scenario-report-json",
  hardwareDemoDevices: "hardware-demo-devices",
  hardwareStatusPeripherals: "hardware-status-peripherals",
});

export function isInIframe() {
  try { return typeof window !== "undefined" && window.parent && window.parent !== window; }
  catch { return false; }
}

export function postToParent(type, payload) {
  if (!isInIframe()) return;
  try {
    window.parent.postMessage({
      type,
      version: "1.0",
      requestId: `req_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      timestamp: new Date().toISOString(),
      payload: payload || {},
    }, "*");
  } catch { /* silent */ }
}

export function readStoredCollapsed(storageKey) {
  if (!storageKey) return false;
  try { return window.localStorage.getItem(storageKey) === "1"; }
  catch { return false; }
}

export function persistStoredCollapsed(storageKey, collapsed) {
  if (!storageKey) return;
  try { window.localStorage.setItem(storageKey, collapsed ? "1" : "0"); }
  catch { /* silent */ }
}
