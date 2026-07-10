/** Resolve scenario file name from URL query (basename or path match). */
import { UI_URL_ARGS_KEYS } from "./ui-url-args-cookie.js";

const SCENARIO_URL_BLOCKED_KEYS = new Set([...UI_URL_ARGS_KEYS, "mode"]);

export function readScenarioFromUrl(search = globalThis.location?.search ?? "") {
  const params = new URLSearchParams(search);
  const raw = params.get("scenario") || params.get("test") || params.get("file");
  return raw?.trim() || null;
}

export function findFileByScenarioQuery(files, scenarioQuery) {
  if (!scenarioQuery || !Array.isArray(files)) return null;
  const needle = scenarioQuery.toLowerCase();
  return (
    files.find((f) => f.name?.toLowerCase() === needle)
    || files.find((f) => f.path?.toLowerCase() === needle)
    || files.find((f) => f.name?.toLowerCase().endsWith(needle))
    || null
  );
}

export function readScenarioSpeedFromUrl(search = globalThis.location?.search ?? "") {
  const raw = new URLSearchParams(search).get("speed");
  const parsed = Number.parseFloat(raw ?? "");
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export function buildScenarioFilesSearch(search = "", patch = {}) {
  const params = new URLSearchParams(search);
  Object.entries(patch).forEach(([key, value]) => {
    if (SCENARIO_URL_BLOCKED_KEYS.has(key)) return;
    if (value === undefined || value === null || value === "") {
      params.delete(key);
    } else {
      params.set(key, String(value));
    }
  });
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function scenarioUrlPatchForFile(file, action = "edit") {
  if (!file) return {};
  const scenario = file.path || file.name || "";
  const basename = file.name || scenario.split("/").pop() || scenario;
  return {
    view: "edit",
    scenario,
    test: basename,
    action,
  };
}

/** Match panel sidebar item by ?scenario= / ?test= / ?file= query value. */
export function findSidebarItemByScenarioQuery(items, scenarioQuery) {
  if (!scenarioQuery || !Array.isArray(items) || items.length === 0) return null;
  const needle = scenarioQuery.toLowerCase();
  return (
    items.find((i) => i.id.startsWith("file:") && i.id.slice(5).toLowerCase() === needle)
    || items.find((i) => i.id.startsWith("file:") && i.id.slice(5).toLowerCase().endsWith(`/${needle}`))
    || items.find((i) => i.title?.toLowerCase() === needle)
    || items.find((i) => i.id.endsWith(`:${needle}`))
    || null
  );
}

export function panelScenarioUrlPatch(item, action = "edit") {
  if (!item) return {};
  if (item.id.startsWith("file:")) {
    return scenarioUrlPatchForFile({ name: item.title, path: item.id.slice(5) }, action);
  }
  return {
    view: "edit",
    scenario: item.title,
    test: item.title,
    action,
  };
}

function _resolveUrlParts(options) {
  const location = options.location ?? globalThis.location;
  return {
    history: options.history ?? globalThis.history,
    pathname: options.pathname ?? location?.pathname ?? "",
    search: options.search ?? location?.search ?? "",
    hash: options.hash ?? location?.hash ?? "",
  };
}

export function replaceScenarioFilesUrlState(patch, options = {}) {
  const { history, pathname, search, hash } = _resolveUrlParts(options);
  const nextSearch = buildScenarioFilesSearch(search, patch);
  if (history?.replaceState && pathname) {
    history.replaceState(null, "", `${pathname}${nextSearch}${hash}`);
  }
  return nextSearch;
}
