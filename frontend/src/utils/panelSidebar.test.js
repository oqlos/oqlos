import test from "node:test";
import assert from "node:assert/strict";

import {
  buildPanelSidebarItems,
  canDeletePanelScenario,
  isPanelEditorDirty,
  isPanelScenarioFileId,
  isPanelScenarioHeaderId,
  panelScenarioFilePath,
  shouldProceedWithScenarioSwitch,
} from "./panelSidebar.js";

test("buildPanelSidebarItems groups files, local, templates and server entries", () => {
  const items = buildPanelSidebarItems({
    fileScenarios: [{ _filePath: "demo.oql", name: "demo.oql", _file: true }],
    myScenarios: [{ name: "Mój", oql: "VERSION: 4\n" }],
    builtinTemplates: [{ name: "Tpl", oql: "GOAL:\n" }],
    serverScenarios: [{ name: "srv-1", _group: "Serwer DB", oql: "VERSION: 4\n" }],
  });
  assert.equal(items.filter((i) => i.kind === "header").length, 4);
  assert.equal(items.some((i) => i.id === "file:demo.oql"), true);
  assert.equal(items.some((i) => i.id === "my:Mój"), true);
  assert.equal(items.some((i) => i.id === "tpl:Tpl"), true);
  assert.equal(items.some((i) => i.id === "srv:srv-1"), true);
});

test("buildPanelSidebarItems skips empty sections", () => {
  const items = buildPanelSidebarItems({
    fileScenarios: [{ _filePath: "only.oql", name: "only.oql" }],
  });
  assert.equal(items.length, 2);
  assert.equal(items[0].kind, "header");
  assert.equal(items[1].id, "file:only.oql");
});

test("isPanelEditorDirty detects unsaved editor state", () => {
  assert.equal(
    isPanelEditorDirty({ selectedScenarioId: "file:a.oql", editorText: "a", savedEditorText: "b" }),
    true,
  );
  assert.equal(
    isPanelEditorDirty({ selectedScenarioId: "", editorText: "a", savedEditorText: "b" }),
    false,
  );
});

test("shouldProceedWithScenarioSwitch respects dirty guard", () => {
  let confirmed = false;
  assert.equal(
    shouldProceedWithScenarioSwitch({
      selectedScenarioId: "file:a.oql",
      nextId: "file:b.oql",
      editorText: "changed",
      savedEditorText: "saved",
      confirmDiscard: () => {
        confirmed = true;
        return false;
      },
    }),
    false,
  );
  assert.equal(confirmed, true);

  assert.equal(
    shouldProceedWithScenarioSwitch({
      selectedScenarioId: "file:a.oql",
      nextId: "__header__files",
      editorText: "changed",
      savedEditorText: "saved",
      confirmDiscard: () => true,
    }),
    false,
  );
});

test("panel scenario id helpers", () => {
  assert.equal(isPanelScenarioHeaderId("__header__files"), true);
  assert.equal(isPanelScenarioFileId("file:demo.oql"), true);
  assert.equal(panelScenarioFilePath("file:examples/demo.oql"), "examples/demo.oql");
});

test("canDeletePanelScenario allows files and local scenarios only", () => {
  assert.equal(canDeletePanelScenario("file:demo.oql"), true);
  assert.equal(canDeletePanelScenario("my:local"), true);
  assert.equal(canDeletePanelScenario("tpl:Smoke"), false);
  assert.equal(canDeletePanelScenario("srv:db"), false);
});
