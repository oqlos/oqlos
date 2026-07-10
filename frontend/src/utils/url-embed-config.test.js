import test from "node:test";
import assert from "node:assert/strict";

import {
  APP_CONFIG_DEFAULTS,
  applyParentContextPayload,
  applyUrlEmbedPatch,
  buildEmbedConfigUrlPatch,
  mergeParentContext,
  preserveEmbedSearchParams,
  mergeParentSearchIntoChildUrl,
  parseUrlEmbedConfig,
  resolveParentContextUpdate,
  resolveViewportWidthPx,
  sidebarCollapsedFromUrlParam,
  sidebarUrlFromCollapsed,
  SIDEBAR_URL_OFF,
  SIDEBAR_URL_ON,
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

test("buildEmbedConfigUrlPatch backfills missing embed params from config", () => {
  const patch = buildEmbedConfigUrlPatch(
    { font: "large", theme: "dark", lang: "en", role: "operator", size: 1280, mode: "keyboard" },
    "",
  );
  assert.equal(patch.font, "large");
  assert.equal(patch.theme, "dark");
  assert.equal(patch.lang, "en");
  assert.equal(patch.role, "operator");
  assert.equal(patch.size, 1280);
  assert.equal(patch.mode, "keyboard");
});

test("buildEmbedConfigUrlPatch skips keys already matching URL", () => {
  const patch = buildEmbedConfigUrlPatch(
    { font: "large", theme: "dark", lang: "en", role: "operator", size: 1280, mode: "keyboard" },
    "?font=large&theme=dark&lang=en&role=operator&size=1280&mode=keyboard",
  );
  assert.deepEqual(patch, {});
});

test("preserveEmbedSearchParams keeps shell chrome when changing routes", () => {
  assert.equal(
    preserveEmbedSearchParams(
      "/func-editor",
      "?font=large&theme=dark&lang=en&size=1280&sidebar=off&scenario=demo.oql",
    ),
    "/func-editor?font=large&theme=dark&lang=en&size=1280&sidebar=off",
  );
});

test("sidebarCollapsedFromUrlParam accepts on/off and legacy open/collapsed", () => {
  assert.equal(sidebarCollapsedFromUrlParam("on"), false);
  assert.equal(sidebarCollapsedFromUrlParam("off"), true);
  assert.equal(sidebarCollapsedFromUrlParam("open"), false);
  assert.equal(sidebarCollapsedFromUrlParam("collapsed"), true);
  assert.equal(sidebarCollapsedFromUrlParam("nope"), null);
});

test("sidebarUrlFromCollapsed writes on/off tokens", () => {
  assert.equal(sidebarUrlFromCollapsed(false), SIDEBAR_URL_ON);
  assert.equal(sidebarUrlFromCollapsed(true), SIDEBAR_URL_OFF);
});

test("parseUrlEmbedConfig normalizes sidebar query to on/off", () => {
  assert.equal(parseUrlEmbedConfig("?sidebar=off").sidebar, SIDEBAR_URL_OFF);
  assert.equal(parseUrlEmbedConfig("?sidebar=on").sidebar, SIDEBAR_URL_ON);
  assert.equal(parseUrlEmbedConfig("?sidebar=collapsed").sidebar, SIDEBAR_URL_OFF);
  assert.equal(parseUrlEmbedConfig("").sidebar, SIDEBAR_URL_ON);
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
