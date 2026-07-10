import test from "node:test";
import assert from "node:assert/strict";

import { API_DOCS_IFRAME_SRC, buildApiDocsIframeSrc } from "./api-docs-url.js";

test("API_DOCS_IFRAME_SRC points at FastAPI Swagger", () => {
  assert.equal(API_DOCS_IFRAME_SRC, "/docs");
});

test("buildApiDocsIframeSrc forwards theme=dark", () => {
  assert.equal(
    buildApiDocsIframeSrc("?font=default&theme=dark&role=admin&lang=pl"),
    "/docs?theme=dark",
  );
});

test("buildApiDocsIframeSrc defaults to dark theme", () => {
  assert.equal(buildApiDocsIframeSrc(""), "/docs?theme=dark");
});

test("buildApiDocsIframeSrc supports high-contrast theme", () => {
  assert.equal(buildApiDocsIframeSrc("?theme=high-contrast"), "/docs?theme=high-contrast");
});
