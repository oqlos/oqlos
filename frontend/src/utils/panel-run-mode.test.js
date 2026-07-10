import test from "node:test";
import assert from "node:assert/strict";

import { readPanelRunModeFromSearch, PANEL_RUN_MODE_PARAM } from "./panel-run-mode.js";

test("readPanelRunModeFromSearch prefers run_mode over chrome mode", () => {
  assert.equal(readPanelRunModeFromSearch("?run_mode=validate&mode=keyboard"), "validate");
});

test("readPanelRunModeFromSearch reads legacy panel mode param", () => {
  assert.equal(readPanelRunModeFromSearch("?mode=execute"), "execute");
});

test("readPanelRunModeFromSearch ignores chrome input mode", () => {
  assert.equal(readPanelRunModeFromSearch("?mode=keyboard"), "dry-run");
});

test("PANEL_RUN_MODE_PARAM is run_mode", () => {
  assert.equal(PANEL_RUN_MODE_PARAM, "run_mode");
});
