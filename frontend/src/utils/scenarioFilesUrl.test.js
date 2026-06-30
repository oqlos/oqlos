import test from "node:test";
import assert from "node:assert/strict";

import { findFileByScenarioQuery, readScenarioFromUrl } from "./scenarioFilesUrl.js";

test("readScenarioFromUrl reads scenario query param", () => {
  assert.equal(readScenarioFromUrl("?scenario=demo.oql&lang=pl"), "demo.oql");
  assert.equal(readScenarioFromUrl(""), null);
});

test("findFileByScenarioQuery matches basename or path", () => {
  const files = [
    { name: "demo.oql", path: "examples/demo.oql", is_directory: false },
    { name: "test.oql", path: "test.oql", is_directory: false },
  ];
  assert.equal(findFileByScenarioQuery(files, "demo.oql")?.path, "examples/demo.oql");
  assert.equal(findFileByScenarioQuery(files, "examples/demo.oql")?.name, "demo.oql");
  assert.equal(findFileByScenarioQuery(files, "missing.oql"), null);
});
