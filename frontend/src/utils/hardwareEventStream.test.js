import test from "node:test";
import assert from "node:assert/strict";

import {
  buildHardwareEventsWsUrl,
  matchesHardwareEventFilters,
  normalizeHardwareEvent,
} from "./hardwareEventStream.js";

test("buildHardwareEventsWsUrl uses env override", () => {
  assert.equal(
    buildHardwareEventsWsUrl({ wsUrlEnv: "ws://example.test/ws" }),
    "ws://example.test/ws/events/hardware",
  );
});

test("normalizeHardwareEvent maps command and status", () => {
  const event = normalizeHardwareEvent({
    id: "evt-1",
    timestamp: "2026-01-01T00:00:00Z",
    data: {
      peripheral_id: "motor-tic249",
      command_name: "stop",
      result: { ok: true },
    },
  });
  assert.equal(event.peripheralId, "motor-tic249");
  assert.equal(event.commandName, "stop");
  assert.equal(event.status, "ok");
});

test("matchesHardwareEventFilters filters by peripheral and command", () => {
  const event = { peripheralId: "modbus-io", commandName: "valve_on" };
  assert.equal(matchesHardwareEventFilters(event, "modbus", "valve"), true);
  assert.equal(matchesHardwareEventFilters(event, "motor", ""), false);
});
