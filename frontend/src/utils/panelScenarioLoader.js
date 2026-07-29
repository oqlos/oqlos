function fileScenarioFromEditorFile(file) {
  return {
    name: file.path && file.path !== file.name ? `${file.name} — ${file.path}` : file.name,
    oql: null,
    _file: true,
    _filePath: file.path,
    _group: "Pliki scenariuszy (/ui/scenario-files)",
  };
}

export async function loadFileScenarios(fetchImpl = fetch) {
  const response = await fetchImpl(`/api/v1/editor/files?ts=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const { files } = await response.json();
  return (Array.isArray(files) ? files : [])
    .filter((file) => file && !file.is_directory && /\.oql$/i.test(String(file.name || "")))
    .sort((left, right) => String(left.name || "").localeCompare(String(right.name || ""), "pl", { sensitivity: "base" }))
    .map(fileScenarioFromEditorFile);
}

export async function loadServerScenarios(fetchImpl = fetch) {
  const response = await fetchImpl("/api/v1/scenarios/fetch");
  if (!response.ok) return undefined;
  const scenarios = await response.json();
  if (!Array.isArray(scenarios)) return undefined;
  return scenarios
    .map((scenario) => ({
      name: scenario.id || scenario.name || "?",
      oql: typeof scenario.source === "string" && scenario.source ? scenario.source : null,
      _srv: scenario,
      _group: "Serwer DB",
    }))
    .filter((scenario) => scenario.name && scenario.oql);
}
