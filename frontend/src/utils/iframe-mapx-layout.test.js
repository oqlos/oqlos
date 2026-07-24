import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const globalCss = readFileSync(join(__dirname, "../styles/global.css"), "utf8");

function ruleFor(selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return globalCss.match(new RegExp(`${escaped}\\s*\\{([^}]*)\\}`))?.[1] || "";
}

test("embedded mapx pages keep the dashboard beside the viewport-height sidebar", () => {
  const shell = ruleFor(':root[data-iframe-child="1"] .mapx-shell');
  assert.match(shell, /flex-direction:\s*row/);
  assert.match(shell, /height:\s*100%/);
  assert.match(shell, /min-height:\s*0/);
  assert.match(shell, /overflow:\s*hidden/);

  const dashboard = ruleFor(':root[data-iframe-child="1"] .mapx-main-dashboard');
  assert.match(dashboard, /height:\s*100%/);
  assert.match(dashboard, /min-height:\s*0/);
  assert.match(dashboard, /overflow:\s*auto/);
});

test("embedded hardware coil page scrolls inside the clipped iframe root", () => {
  const root = ruleFor(':root[data-iframe-child="1"] #root:has(.coil-test-page)');
  assert.match(root, /overflow-x:\s*hidden/);
  assert.match(root, /overflow-y:\s*auto/);
});
