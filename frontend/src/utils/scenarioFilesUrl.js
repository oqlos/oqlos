/** Resolve scenario file name from URL query (basename or path match). */
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

export function replaceScenarioFilesUrlState(patch, options = {}) {
  const location = options.location ?? globalThis.location;
  const history = options.history ?? globalThis.history;
  const pathname = options.pathname ?? location?.pathname ?? "";
  const search = options.search ?? location?.search ?? "";
  const hash = options.hash ?? location?.hash ?? "";
  const nextSearch = buildScenarioFilesSearch(search, patch);
  if (history?.replaceState && pathname) {
    history.replaceState(null, "", `${pathname}${nextSearch}${hash}`);
  }
  return nextSearch;
}
