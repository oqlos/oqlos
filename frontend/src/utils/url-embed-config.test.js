import test from "node:test";
import assert from "node:assert/strict";

import {
  APP_CONFIG_DEFAULTS,
  applyParentContextPayload,
  applyUrlEmbedPatch,
  mergeParentContext,
  mergeParentSearchIntoChildUrl,
  parseUrlEmbedConfig,
  resolveParentContextUpdate,
  resolveViewportWidthPx,
  SUPPORTED_LANGS_ENUM,
} from "./url-embed-config.js";

test("parseUrlEmbedConfig uses defaults for empty search", () => {
  assert.deepEqual(parseUrlEmbedConfig(""), { ...APP_CONFIG_DEFAULTS });
});

test("parseUrlEmbedConfig accepts font theme lang role iframe_child", () => {
  const cfg = parseUrlEmbedConfig("?lang=de&theme=light&role=operator&iframe_child=1&font=xlarge");
  assert.equal(cfg.lang, "de");
  assert.equal(cfg.theme, "light");
  assert.equal(cfg.role, "operator");
  assert.equal(cfg.iframeChild, true);
  assert.equal(cfg.font, "xlarge");
});

test("parseUrlEmbedConfig rejects unknown lang", () => {
  assert.equal(parseUrlEmbedConfig("?lang=zz").lang, APP_CONFIG_DEFAULTS.lang);
});

test("parseUrlEmbedConfig accepts every supported lang", () => {
  for (const code of SUPPORTED_LANGS_ENUM) {
    assert.equal(parseUrlEmbedConfig(`?lang=${code}`).lang, code);
  }
});

test("resolveViewportWidthPx maps 100 to responsive width band", () => {
  const px = resolveViewportWidthPx(100);
  assert.ok(px === null || (px >= 960 && px <= 4096));
  assert.equal(resolveViewportWidthPx(1280), 1280);
});

test("mergeParentContext applies parent locale theme font", () => {
  const prev = parseUrlEmbedConfig("?theme=dark&lang=pl");
  const next = mergeParentContext(prev, { theme: "light", locale: "en", font: "mono", size: 1024 });
  assert.equal(next.theme, "light");
  assert.equal(next.lang, "en");
  assert.equal(next.font, "mono");
  assert.equal(next.size, 1024);
});

test("mergeParentSearchIntoChildUrl preserves iframe_child", () => {
  const merged = mergeParentSearchIntoChildUrl(
    "http://localhost/connect?iframe_child=1",
    "?scenario=ts-1&test=mask.oql",
  );
  assert.match(merged, /scenario=ts-1/);
  assert.match(merged, /iframe_child=1/);
});

test("applyParentContextPayload merges search from parent", () => {
  const prev = parseUrlEmbedConfig("");
  const next = applyParentContextPayload(
    prev,
    { search: "?scenario=dev-test", theme: "light" },
    "http://localhost/connect?iframe_child=1",
  );
  assert.equal(next.scenario, "dev-test");
  assert.equal(next.theme, "light");
});

test("applyUrlEmbedPatch updates device and test query params", () => {
  const { nextPath, config } = applyUrlEmbedPatch(
    "http://localhost/hardware-status",
    { device: "DEV-001", test: "mask-tightness-test.oql" },
  );
  assert.match(nextPath, /device=DEV-001/);
  assert.equal(config.device, "DEV-001");
  assert.equal(config.test, "mask-tightness-test.oql");
});

test("resolveParentContextUpdate returns nextHref when search changes", () => {
  const update = resolveParentContextUpdate(
    parseUrlEmbedConfig(""),
    { search: "?scenario=abc", theme: "dark" },
    { href: "http://localhost/app?iframe_child=1", pathname: "/app", search: "?iframe_child=1" },
  );
  assert.ok(update.nextHref);
  assert.equal(update.config.scenario, "abc");
});
