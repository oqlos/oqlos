import test from "node:test";
import assert from "node:assert/strict";

import {
  describeDetail,
  formatHardwareApiError,
  parseOqlError,
} from "@semcod/frontend-services/hardware-api-errors.js";

test("parseOqlError recognizes the standard OqlIssue shape", () => {
  const payload = {
    code: "api_invalid_recover_scope",
    domain: "api",
    severity: "warning",
    message: "POST /api/v1/hardware/recover was called with an unsupported `scope` query param.",
    detail: { scope: "full" },
  };

  const parsed = parseOqlError(payload);

  assert.equal(parsed.code, "api_invalid_recover_scope");
  assert.equal(parsed.domain, "api");
  assert.equal(parsed.severity, "warning");
  assert.equal(parsed.detail.scope, "full");
  assert.equal(parsed.repair, null);
});

test("parseOqlError returns null for payloads without a code field", () => {
  assert.equal(parseOqlError(null), null);
  assert.equal(parseOqlError("plain string"), null);
  assert.equal(parseOqlError({ detail: "legacy shape" }), null);
  assert.equal(parseOqlError([1, 2, 3]), null);
});

test("parseOqlError carries the repair template through untouched", () => {
  const payload = {
    code: "hw_tic249_sidecar_unreachable",
    domain: "hardware",
    severity: "error",
    message: "hw-tic249 sidecar is unreachable.",
    repair: {
      id: "tic249-ensure-sidecar",
      scope: "oqlos",
      auto_executable: true,
      actuation_risk: "config",
      hint: "systemctl --user restart hw-tic249.service",
    },
  };

  const parsed = parseOqlError(payload);
  assert.equal(parsed.repair.id, "tic249-ensure-sidecar");
  assert.equal(parsed.repair.actuation_risk, "config");
});

test("formatHardwareApiError prefers the OqlIssue message when payload.code is present", () => {
  const err = new Error("HTTP 503");
  err.payload = {
    code: "api_oql_transport_disabled",
    domain: "api",
    severity: "error",
    message: "OQL-over-MQTT transport is disabled.",
  };

  assert.equal(formatHardwareApiError(err), "OQL-over-MQTT transport is disabled.");
});

test("formatHardwareApiError still falls back to describeDetail for legacy shapes", () => {
  const err = new Error("HTTP 400");
  err.payload = { detail: { error: "Invalid hardware MAP", issues: ["missing peripherals"] } };

  assert.equal(formatHardwareApiError(err), "Invalid hardware MAP: missing peripherals");
});

test("formatHardwareApiError falls back to err.message when nothing else matches", () => {
  const err = new Error("network down");
  assert.equal(formatHardwareApiError(err), "network down");
});

test("describeDetail still works standalone for plain strings and objects", () => {
  assert.equal(describeDetail("plain"), "plain");
  assert.equal(describeDetail({ message: "boom" }), "boom");
  assert.equal(describeDetail(null), "");
});
