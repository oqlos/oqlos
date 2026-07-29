import assert from "node:assert/strict";
import test from "node:test";
import {
  createPanelResultLogEntry,
  panelResultClass,
  summarizePanelResult,
} from "./panelResultLog.js";

test("panel result class distinguishes successful, unavailable and failed calls", () => {
  assert.equal(panelResultClass({ ok: true }, 200), "ok");
  assert.equal(panelResultClass({ result: { success: false } }, 200), "na");
  assert.equal(panelResultClass({ error: "unexpected" }, 500), "fail");
});

test("panel result log entry keeps the USB summary and deterministic timestamp", () => {
  const now = new Date("2026-07-29T10:15:30.000Z");
  const entry = createPanelResultLogEntry({
    title: "USB",
    envelope: { ok: true, result: { count: 1, devices: [{ vendor_id: "1", product_id: "2", product: "Device", tty: ["ttyUSB0"], port_path: "1-1" }] } },
    status: 200,
    sent: "GET /usb",
    request: { ep: "/usb" },
    now,
  });

  assert.equal(summarizePanelResult(entry.raw), "1 urządzeń USB\n  · 1:2 Device [ttyUSB0] @1-1");
  assert.equal(entry.cls, "ok");
  assert.equal(entry.ts, "2026-07-29T10:15:30.000Z");
  assert.ok(entry.id.startsWith(`${now.getTime()}-`));
});
