import test from "node:test";
import assert from "node:assert/strict";

import {
  buildUrlPatchFromUiArgsCookie,
  dedupeNavigationPages,
  normalizeUiPagePath,
  normalizeUiUrlArgsPatch,
  preserveUiNavSearchParams,
  readUiUrlArgsCookie,
  uiPageHref,
  UI_URL_ARGS_COOKIE_NAME,
} from "./ui-url-args-cookie.js";

test("normalizeUiUrlArgsPatch validates chrome keys and submenu", () => {
  assert.deepEqual(
    normalizeUiUrlArgsPatch({
      font: "large",
      theme: "dark",
      lang: "pl",
      sidebar: "open",
      submenu: "shared-bus",
      junk: "skip",
    }),
    {
      font: "large",
      theme: "dark",
      lang: "pl",
      sidebar: "on",
      submenu: "shared-bus",
    },
  );
});

test("buildUrlPatchFromUiArgsCookie fills only missing URL params", () => {
  const patch = buildUrlPatchFromUiArgsCookie(
    "?theme=dark&submenu=modbus-io",
    {
      font: "large",
      theme: "light",
      lang: "en",
      sidebar: "off",
      submenu: "shared-bus",
    },
  );
  assert.deepEqual(patch, {
    font: "large",
    lang: "en",
    sidebar: "off",
  });
});

test("readUiUrlArgsCookie parses encoded JSON cookie", () => {
  const raw = `${UI_URL_ARGS_COOKIE_NAME}=${encodeURIComponent(JSON.stringify({
    font: "default",
    sidebar: "collapsed",
    submenu: "shared-bus",
  }))}`;
  assert.deepEqual(readUiUrlArgsCookie(raw), {
    font: "default",
    sidebar: "off",
    submenu: "shared-bus",
  });
});

test("preserveUiNavSearchParams falls back to cookie for missing args", () => {
  const link = preserveUiNavSearchParams(
    "/hardware-modbus",
    "?theme=dark",
    { submenu: "shared-bus", sidebar: "on", lang: "pl" },
  );
  assert.equal(link, "/hardware-modbus?theme=dark&lang=pl&sidebar=on&submenu=shared-bus");
});

test("uiPageHref builds absolute /ui path with preserved args", () => {
  const href = uiPageHref("/ui/hardware-modbus", "?theme=dark", {
    submenu: "shared-bus",
    sidebar: "on",
  });
  assert.equal(href, "/ui/hardware-modbus?theme=dark&sidebar=on&submenu=shared-bus");
});

test("normalizeUiPagePath maps legacy navigation and hardware-status to /ui/status", () => {
  assert.equal(normalizeUiPagePath("/ui/navigation"), "/ui/status");
  assert.equal(normalizeUiPagePath("/ui/hardware-status"), "/ui/status");
  assert.equal(normalizeUiPagePath("/ui/panel"), "/ui/panel");
});

test("dedupeNavigationPages merges legacy status and navigation entries", () => {
  const pages = dedupeNavigationPages([
    { path: "/ui/navigation", label: "Navigation" },
    { path: "/ui/hardware-status", label: "Hardware status" },
    { path: "/ui/status", label: "Status" },
    { path: "/ui/panel", label: "Panel" },
  ]);
  assert.deepEqual(
    pages.map((p) => p.path),
    ["/ui/status", "/ui/panel"],
  );
});

test("uiPageHref canonicalizes legacy status paths", () => {
  assert.equal(uiPageHref("/ui/hardware-status"), "/ui/status");
  assert.equal(uiPageHref("/ui/navigation"), "/ui/status");
});
