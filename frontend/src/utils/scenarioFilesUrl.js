/** Resolve scenario file name from ?scenario= query (basename match). */
export function readScenarioFromUrl(search = globalThis.location?.search ?? "") {
  const raw = new URLSearchParams(search).get("scenario");
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
