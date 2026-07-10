import assert from "node:assert/strict";
import test from "node:test";

import {
  buildStatusLogSidebarItems,
  patchStatusLogSearchParams,
  readStatusLogFromSearch,
} from "./status-logs-menu.js";

const t = (key) => key;

test("readStatusLogFromSearch accepts file and journal ids", () => {
  assert.equal(readStatusLogFromSearch("?log=file:oqlos-hardware-api.log"), "file:oqlos-hardware-api.log");
  assert.equal(readStatusLogFromSearch("?log=journal:oqlos-hardware-api.service"), "journal:oqlos-hardware-api.service");
  assert.equal(readStatusLogFromSearch("?log=../secrets.log"), "");
  assert.equal(readStatusLogFromSearch("?submenu=modbus-adc"), "");
});

test("patchStatusLogSearchParams stores log selection", () => {
  const next = patchStatusLogSearchParams(new URLSearchParams("theme=dark"), "file:service.log");
  assert.equal(next.get("log"), "file:service.log");
  assert.equal(next.get("theme"), "dark");

  const cleared = patchStatusLogSearchParams(next, "");
  assert.equal(cleared.get("log"), null);
});

test("buildStatusLogSidebarItems groups files by day", () => {
  const items = buildStatusLogSidebarItems(
    {
      groups: [{ day: "2026-07-10", files: [{ id: "file:a.log", name: "a.log", size_bytes: 2048 }] }],
      journal_units: [{ id: "journal:mosquitto.service", name: "mosquitto.service" }],
    },
    t,
  );
  assert.equal(items[0].id, "");
  assert.equal(items.some((item) => item.kind === "header" && item.title === "2026-07-10"), true);
  assert.equal(items.some((item) => item.id === "file:a.log"), true);
  assert.equal(items.some((item) => item.id === "journal:mosquitto.service"), true);
});
