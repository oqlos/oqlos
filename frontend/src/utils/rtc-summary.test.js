import test from "node:test";
import assert from "node:assert/strict";

import { formatRtcSummaryValue } from "./rtc-summary.js";

test("formats RTC time objects as HH:MM:SS", () => {
  assert.equal(
    formatRtcSummaryValue({ hour: 7, minute: 5, second: 9, mock: true }),
    "07:05:09",
  );
});

test("uses explicit time strings when present", () => {
  assert.equal(
    formatRtcSummaryValue({ time: "2026-07-27 11:59:00" }),
    "2026-07-27 11:59:00",
  );
});

test("returns em dash for empty values", () => {
  assert.equal(formatRtcSummaryValue(null), "—");
});
