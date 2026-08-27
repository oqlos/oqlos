import assert from "node:assert/strict";
import test from "node:test";

import {
  M5_POLL_OFFLINE_INITIAL_MS,
  M5_POLL_OFFLINE_MAX_MS,
  M5_POLL_ONLINE_MS,
  nextM5OfflinePollDelay,
} from "./m5-out-polling.js";

test("M5 polling backs off quickly when the physical module is unavailable", () => {
  assert.equal(nextM5OfflinePollDelay(M5_POLL_ONLINE_MS), M5_POLL_OFFLINE_INITIAL_MS);
  assert.equal(nextM5OfflinePollDelay(M5_POLL_OFFLINE_INITIAL_MS), 20000);
  assert.equal(nextM5OfflinePollDelay(20000), M5_POLL_OFFLINE_MAX_MS);
  assert.equal(nextM5OfflinePollDelay(M5_POLL_OFFLINE_MAX_MS), M5_POLL_OFFLINE_MAX_MS);
});

test("M5 polling handles an invalid previous delay conservatively", () => {
  assert.equal(nextM5OfflinePollDelay(Number.NaN), M5_POLL_OFFLINE_INITIAL_MS);
});
