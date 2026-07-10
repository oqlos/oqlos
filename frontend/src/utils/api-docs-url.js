/** FastAPI Swagger UI served by OqlOS at the site root. */
export const API_DOCS_IFRAME_SRC = "/docs";

const SUPPORTED_THEMES = new Set(["light", "dark", "high-contrast"]);

/** Build iframe src for Swagger UI, preserving theme from the UI chrome URL. */
export function buildApiDocsIframeSrc(search = "") {
  const params = new URLSearchParams(String(search || "").replace(/^\?/, ""));
  const theme = String(params.get("theme") || "dark").trim().toLowerCase();
  const out = new URLSearchParams();
  if (SUPPORTED_THEMES.has(theme)) {
    out.set("theme", theme);
  } else {
    out.set("theme", "dark");
  }
  const query = out.toString();
  return query ? `${API_DOCS_IFRAME_SRC}?${query}` : API_DOCS_IFRAME_SRC;
}
