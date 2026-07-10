import assert from "node:assert/strict";
import test from "node:test";

import {
  patchRtcMenuSearchParams,
  readRtcMenuFromSearch,
  resolveRtcMenuId,
} from "./rtc-menu.js";

test("readRtcMenuFromSearch reads rtc submenu ids", () => {
  assert.equal(readRtcMenuFromSearch("?submenu=read_time"), "read_time");
  assert.equal(readRtcMenuFromSearch("?submenu=modbus-adc"), "");
  assert.equal(readRtcMenuFromSearch(""), "");
});

test("patchRtcMenuSearchParams stores rtc submenu", () => {
  const next = patchRtcMenuSearchParams(new URLSearchParams("theme=dark"), "read_watchdog");
  assert.equal(next.get("submenu"), "read_watchdog");
  assert.equal(next.get("theme"), "dark");

  const cleared = patchRtcMenuSearchParams(next, "overview");
  assert.equal(cleared.get("submenu"), null);
});

test("resolveRtcMenuId falls back to overview", () => {
  assert.equal(resolveRtcMenuId("sync_to_system"), "sync_to_system");
  assert.equal(resolveRtcMenuId("unknown"), "overview");
});
