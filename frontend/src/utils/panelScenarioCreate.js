/** Normalize user input into a safe root-level .oql file path. */
export function normalizeScenarioFilePath(raw) {
  const trimmed = String(raw || "").trim();
  if (!trimmed) {
    throw new Error("Podaj nazwę pliku.");
  }
  const normalized = trimmed.replace(/\\/g, "/");
  if (normalized.includes("/") || normalized.includes("..")) {
    throw new Error("Nowy scenariusz musi być plikiem w katalogu głównym (bez podkatalogów).");
  }
  const withExt = /\.oql$/i.test(normalized) ? normalized : `${normalized}.oql`;
  if (!/^[\w.\-()]+\.oql$/i.test(withExt)) {
    throw new Error("Nazwa może zawierać litery, cyfry, -, _, ., ( ).");
  }
  return withExt;
}

export function defaultNewScenarioContent(filePath) {
  const base = String(filePath || "scenariusz").replace(/\.oql$/i, "");
  return `VERSION: 4
SCENARIO: ${base}
GOAL:
  SET NAME '${base}'
  SET WAIT '1 s'
`;
}
