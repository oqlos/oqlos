import test from "node:test";
import assert from "node:assert/strict";
import {
  OQL_CANONICAL_SECTIONS,
  canMutateMapEditorTab,
  filterForbiddenCanonicalSections,
  isOqlCanonicalTab,
} from "./mapEditorOqlCanonical.js";

test("canonical tabs cover migrated MAP sections", () => {
  assert.equal(isOqlCanonicalTab("funcs"), true);
  assert.equal(isOqlCanonicalTab("objects"), true);
  assert.equal(isOqlCanonicalTab("params"), true);
  assert.equal(isOqlCanonicalTab("actions"), true);
  assert.equal(isOqlCanonicalTab("json"), false);
  assert.ok(OQL_CANONICAL_SECTIONS.includes("runtimeConfig"));
});

test("mutate locked without legacy_edit", () => {
  assert.equal(canMutateMapEditorTab("funcs", "system", true), false);
  assert.equal(canMutateMapEditorTab("json", "system", true), true);
});

test("filterForbiddenCanonicalSections blocks OQL sections", () => {
  const forbidden = filterForbiddenCanonicalSections(
    ["funcImplementations", "operatorVariables", "runtimeConfig"],
    "system"
  );
  assert.deepEqual(forbidden.sort(), ["funcImplementations", "runtimeConfig"].sort());
});
