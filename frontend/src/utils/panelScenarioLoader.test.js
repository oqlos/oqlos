import assert from "node:assert/strict";
import test from "node:test";
import { loadFileScenarios, loadServerScenarios } from "./panelScenarioLoader.js";

test("loadFileScenarios keeps only sorted OQL files", async () => {
  let request;
  const scenarios = await loadFileScenarios(async (url, options) => {
    request = { url, options };
    return {
      ok: true,
      json: async () => ({
        files: [
          { name: "zeta.oql", path: "zeta.oql" },
          { name: "folder.oql", is_directory: true },
          { name: "alpha.OQL", path: "plans/alpha.OQL" },
          { name: "notes.txt" },
        ],
      }),
    };
  });

  assert.match(request.url, /^\/api\/v1\/editor\/files\?ts=\d+$/);
  assert.deepEqual(request.options, { cache: "no-store" });
  assert.deepEqual(scenarios.map((scenario) => scenario.name), ["alpha.OQL — plans/alpha.OQL", "zeta.oql"]);
});

test("loadServerScenarios omits records without source and keeps failed response unchanged", async () => {
  const scenarios = await loadServerScenarios(async () => ({
    ok: true,
    json: async () => [{ id: "ready", source: "VERSION: 4" }, { name: "empty", source: "" }],
  }));
  assert.deepEqual(scenarios.map((scenario) => scenario.name), ["ready"]);
  assert.equal(await loadServerScenarios(async () => ({ ok: false })), undefined);
});
