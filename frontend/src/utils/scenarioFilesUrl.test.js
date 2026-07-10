import test from "node:test";
import assert from "node:assert/strict";

import {
  buildScenarioFilesSearch,
  findFileByScenarioQuery,
  findSidebarItemByScenarioQuery,
  panelScenarioUrlPatch,
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

test("buildScenarioFilesSearch ignores chrome keys in patch", () => {
  assert.equal(
    buildScenarioFilesSearch("?theme=dark&mode=keyboard", {
      scenario: "demo.oql",
      mode: "real",
      theme: "light",
      sidebar: "off",
    }),
    "?theme=dark&mode=keyboard&scenario=demo.oql",
  );
});

test("findSidebarItemByScenarioQuery matches file path or title", () => {
  const items = [
    { id: "file:examples/demo.oql", title: "demo.oql", subtitle: "Pliki" },
    { id: "tpl:Health-check sensorów", title: "Health-check sensorów", subtitle: "Szablony" },
  ];
  assert.equal(findSidebarItemByScenarioQuery(items, "demo.oql")?.id, "file:examples/demo.oql");
  assert.equal(findSidebarItemByScenarioQuery(items, "examples/demo.oql")?.id, "file:examples/demo.oql");
  assert.equal(
    findSidebarItemByScenarioQuery(items, "Health-check sensorów")?.id,
    "tpl:Health-check sensorów",
  );
  assert.equal(findSidebarItemByScenarioQuery(items, "missing.oql"), null);
});

test("panelScenarioUrlPatch writes shareable panel edit state", () => {
  assert.deepEqual(panelScenarioUrlPatch({ id: "file:examples/demo.oql", title: "demo.oql" }), {
    view: "edit",
    scenario: "examples/demo.oql",
    test: "demo.oql",
    action: "edit",
  });
  assert.deepEqual(panelScenarioUrlPatch({ id: "tpl:Smoke test", title: "Smoke test" }), {
    view: "edit",
    scenario: "Smoke test",
    test: "Smoke test",
    action: "edit",
  });
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
