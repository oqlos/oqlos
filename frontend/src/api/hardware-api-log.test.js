import assert from "node:assert/strict";
import test from "node:test";

import {
  formatHardwareApiDiagnostic,
  logHardwareApiEvent,
} from "./hardware-api-log.js";

test("formats successful hardware requests with SOA nomenclature", () => {
  assert.equal(
    formatHardwareApiDiagnostic("response", "/api/v3/hardware/health", {
      method: "GET",
      status: 200,
      duration_ms: 12,
    }),
    'HTTP_REQUEST "/api/v3/hardware/health" {"architecture":"SOA","transport":"http","method":"GET","status":200,"duration_ms":12} -> OK',
  );
});

test("formats network and HTTP failures with distinct results", () => {
  assert.equal(
    formatHardwareApiDiagnostic("error", "/api/v3/hardware/health", {
      method: "GET",
      error: "NetworkError",
    }),
    'NETWORK_ERROR "/api/v3/hardware/health" {"architecture":"SOA","transport":"http","method":"GET","error":"NetworkError"} -> UNAVAILABLE',
  );
  assert.equal(
    formatHardwareApiDiagnostic("error", "/api/v3/hardware/health", {
      method: "GET",
      status: 503,
      error_code: "C2004-HW-0012",
    }),
    'HTTP_ERROR "/api/v3/hardware/health" {"architecture":"SOA","transport":"http","method":"GET","status":503,"error_code":"C2004-HW-0012"} -> ERROR',
  );
});

test("emits wizard events as one structured console argument", () => {
  const original = console.debug;
  const calls = [];
  console.debug = (...args) => calls.push(args);
  try {
    logHardwareApiEvent("request", "/api/v3/hardware/modbus/wizard/plan", { method: "GET" });
  } finally {
    console.debug = original;
  }
  assert.deepEqual(calls, [[
    'HTTP_REQUEST_START "/api/v3/hardware/modbus/wizard/plan" {"architecture":"SOA","transport":"http","method":"GET"} -> PENDING',
  ]]);
});
