import test from "node:test";
import assert from "node:assert/strict";

import {
  defaultNewScenarioContent,
  normalizeScenarioFilePath,
} from "./panelScenarioCreate.js";

test("normalizeScenarioFilePath adds .oql extension", () => {
  assert.equal(normalizeScenarioFilePath("moj-test"), "moj-test.oql");
  assert.equal(normalizeScenarioFilePath("demo.oql"), "demo.oql");
});

test("normalizeScenarioFilePath rejects path traversal", () => {
  assert.throws(() => normalizeScenarioFilePath("../evil.oql"), /podkatalogów/);
  assert.throws(() => normalizeScenarioFilePath("foo/bar.oql"), /podkatalogów/);
});

test("defaultNewScenarioContent builds VERSION 4 skeleton", () => {
  const content = defaultNewScenarioContent("moj-test.oql");
  assert.match(content, /^VERSION: 4/m);
  assert.match(content, /SCENARIO: moj-test/m);
  assert.match(content, /GOAL:/m);
});
