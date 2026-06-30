const API_BASE = "/api/v1/editor";

export function filterListableFiles(files) {
  if (!Array.isArray(files)) return [];
  return files.filter((file) => file && !file.is_directory);
}

export async function fetchScenarioFilesList() {
  const response = await fetch(`${API_BASE}/files`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const data = await response.json();
  return filterListableFiles(data.files);
}

export async function fetchScenarioFileContent(filePath) {
  const response = await fetch(`${API_BASE}/file/${filePath}`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const data = await response.json();
  return data.content ?? "";
}

export async function saveScenarioFileContent(filePath, content) {
  const response = await fetch(`${API_BASE}/file/${filePath}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: filePath, content }),
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return true;
}

export async function executeScenarioFile({ scenarioFile, mode = "real", speed = 1.0 }) {
  const response = await fetch(`${API_BASE}/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scenario_file: scenarioFile,
      mode,
      speed,
    }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || `HTTP ${response.status}`);
  }
  return data;
}
