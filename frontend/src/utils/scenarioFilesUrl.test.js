import test from "node:test";
import assert from "node:assert/strict";

import {
  buildScenarioFilesSearch,
  findFileByScenarioQuery,
  readScenarioFromUrl,
  readScenarioSpeedFromUrl,
  replaceScenarioFilesUrlState,
  scenarioUrlPatchForFile,
} from "./scenarioFilesUrl.js";

test("readScenarioFromUrl reads scenario query param", () => {
  assert.equal(readScenarioFromUrl("?scenario=demo.oql&lang=pl"), "demo.oql");
  assert.equal(readScenarioFromUrl("?test=demo.oql&lang=pl"), "demo.oql");
  assert.equal(readScenarioFromUrl("?file=examples/demo.oql&lang=pl"), "examples/demo.oql");
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

test("readScenarioSpeedFromUrl reads positive speed", () => {
  assert.equal(readScenarioSpeedFromUrl("?speed=2.5"), 2.5);
  assert.equal(readScenarioSpeedFromUrl("?speed=0"), null);
  assert.equal(readScenarioSpeedFromUrl("?speed=bad"), null);
});

test("scenarioUrlPatchForFile writes shareable edit state", () => {
  assert.deepEqual(
    scenarioUrlPatchForFile({ name: "demo.oql", path: "examples/demo.oql" }, "execute"),
    {
      view: "edit",
      scenario: "examples/demo.oql",
      test: "demo.oql",
      action: "execute",
    },
  );
});

test("buildScenarioFilesSearch merges and removes query params", () => {
  assert.equal(
    buildScenarioFilesSearch("?theme=dark&action=edit", {
      scenario: "examples/demo.oql",
      test: "demo.oql",
      action: "save",
      speed: null,
    }),
    "?theme=dark&action=save&scenario=examples%2Fdemo.oql&test=demo.oql",
  );
});

test("replaceScenarioFilesUrlState updates browser history", () => {
  const calls = [];
  const search = replaceScenarioFilesUrlState(
    { scenario: "demo.oql", action: "edit" },
    {
      location: { pathname: "/ui/scenario-files", search: "?theme=dark", hash: "#top" },
      history: { replaceState: (...args) => calls.push(args) },
    },
  );
  assert.equal(search, "?theme=dark&scenario=demo.oql&action=edit");
  assert.equal(calls[0][2], "/ui/scenario-files?theme=dark&scenario=demo.oql&action=edit#top");
});
