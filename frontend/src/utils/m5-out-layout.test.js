import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const globalCss = readFileSync(join(__dirname, "../styles/global.css"), "utf8");
const pageSource = readFileSync(join(__dirname, "../pages/HardwareM5Out.jsx"), "utf8");

function ruleFor(selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return globalCss.match(new RegExp(`${escaped}\\s*\\{([^}]*)\\}`))?.[1] || "";
}

test("M5 output page uses its own styled layout instead of unscoped generic classes", () => {
  for (const className of [
    "m5-out-page",
    "m5-out-content",
    "m5-out-card",
    "m5-out-actions",
    "m5-out-io-grid",
    "m5-out-channel-grid",
    "m5-out-channel",
  ]) {
    assert.match(pageSource, new RegExp(`className=.*${className}`));
  }

  assert.match(ruleFor(".m5-out-content"), /display:\s*grid/);
  assert.match(ruleFor(".m5-out-card"), /border:\s*1px solid/);
  assert.match(ruleFor(".m5-out-actions"), /display:\s*flex/);
  assert.match(ruleFor(".m5-out-io-grid"), /grid-template-columns:/);
  assert.match(ruleFor(".m5-out-channel-grid"), /grid-template-columns:/);
  assert.match(ruleFor(".m5-out-channel"), /border-radius:/);
});

test("embedded M5 output page owns vertical scrolling inside the iframe", () => {
  const root = ruleFor(':root[data-iframe-child="1"] #root:has(.m5-out-page)');
  assert.match(root, /overflow-x:\s*hidden/);
  assert.match(root, /overflow-y:\s*auto/);
});

test("M5 output page keeps read-only StackNet observable without enabling control", () => {
  assert.match(pageSource, /executePluginCommand\(PLUGIN_ID, "read_io_snapshot"\)/);
  assert.doesNotMatch(pageSource, /peripheralStatus\(PLUGIN_ID\)/);
  assert.match(pageSource, /snapshot\?\.control_ready !== false/);
  assert.match(pageSource, /disabled=\{!controlReady \|\| !isAdmin/);
});
