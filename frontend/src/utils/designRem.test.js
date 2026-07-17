import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { rem, remVar } from "@semcod/frontend-services/designRem.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const globalCss = readFileSync(join(__dirname, "../styles/global.css"), "utf8");

test("rem ladder matches CSS custom properties", () => {
  assert.equal(rem.xxs, "0.7143rem");
  assert.equal(rem.xs, "0.7857rem");
  assert.equal(rem.sm, "0.8571rem");
  assert.equal(rem.md, "0.9286rem");
  assert.equal(rem.base, "1rem");
  assert.equal(remVar.sm, "--font-rem-sm");
});

test("global.css defines matching --font-rem-* tokens", () => {
  for (const [key, varName] of Object.entries(remVar)) {
    if (key === "railIcon" || key === "railBadge") continue;
    assert.match(globalCss, new RegExp(`${varName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}:\\s*${rem[key].replace(".", "\\.")}`));
  }
});

test("navigation panel avoids hardcoded px font sizes", () => {
  const navPanel = readFileSync(join(__dirname, "../components/NodeNavigationPanel.jsx"), "utf8");
  assert.doesNotMatch(navPanel, /fontSize:\s*"[0-9]+px"/);
});

test("global.css typography utilities use rem tokens", () => {
  assert.match(globalCss, /\.text-sm\s*\{\s*font-size:\s*var\(--font-rem-sm\)/);
  assert.match(globalCss, /\.badge\s*\{[^}]*font-size:\s*var\(--font-rem-xs\)/s);
});
