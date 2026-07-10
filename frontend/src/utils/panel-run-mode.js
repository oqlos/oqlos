export const PANEL_RUN_MODES = ["execute", "dry-run", "validate"];
export const PANEL_RUN_MODE_PARAM = "run_mode";

export function readPanelRunModeFromSearch(search = "") {
  const params = new URLSearchParams(String(search || "").replace(/^\?/, ""));
  const explicit = (params.get(PANEL_RUN_MODE_PARAM) || "").trim();
  if (PANEL_RUN_MODES.includes(explicit)) return explicit;
  const legacy = (params.get("mode") || "").trim();
  if (PANEL_RUN_MODES.includes(legacy)) return legacy;
  return "dry-run";
}
