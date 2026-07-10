import test from "node:test";
import assert from "node:assert/strict";

import {
  createScenarioFile,
  deleteScenarioFile,
  encodeEditorFilePath,
  filterListableFiles,
  saveScenarioFileContent,
} from "./scenarioFilesApi.js";

test("encodeEditorFilePath encodes each path segment", () => {
  assert.equal(encodeEditorFilePath("demo.oql"), "demo.oql");
  assert.equal(encodeEditorFilePath("examples/demo.oql"), "examples/demo.oql");
  assert.equal(encodeEditorFilePath("nested/my test.oql"), "nested/my%20test.oql");
});

test("filterListableFiles drops directories", () => {
  const files = [
    { name: "a.oql", is_directory: false },
    { name: "lib", is_directory: true },
    null,
  ];
  assert.equal(filterListableFiles(files).length, 1);
  assert.equal(filterListableFiles(files)[0].name, "a.oql");
});

test("saveScenarioFileContent posts encoded path and payload", async () => {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    return { ok: true };
  };
  await saveScenarioFileContent("nested/demo.oql", "VERSION: 4\n");
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "/api/v1/editor/file/nested/demo.oql");
  assert.equal(calls[0].init.method, "POST");
  assert.deepEqual(JSON.parse(calls[0].init.body), {
    path: "nested/demo.oql",
    content: "VERSION: 4\n",
  });
});

test("deleteScenarioFile issues DELETE on encoded path", async () => {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    return { ok: true };
  };
  await deleteScenarioFile("nested/demo.oql");
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "/api/v1/editor/file/nested/demo.oql");
  assert.equal(calls[0].init.method, "DELETE");
});

test("createScenarioFile delegates to saveScenarioFileContent", async () => {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    return { ok: true };
  };
  const path = await createScenarioFile("new.oql", "GOAL:\n");
  assert.equal(path, "new.oql");
  assert.equal(calls[0].init.method, "POST");
});
