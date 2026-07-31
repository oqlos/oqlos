import test from "node:test";
import assert from "node:assert/strict";

import { runtimeControlTranslationKey } from "./hardware-restart-runtime-status.js";

test("reports host stop-probe-start control when available", () => {
  assert.equal(
    runtimeControlTranslationKey({ runtime_control_available: true }),
    "hardwareRestart.runtimeAvailable",
  );
});

test("does not recommend restarting connect-scenario for direct OqlOS", () => {
  assert.equal(
    runtimeControlTranslationKey({
      runtime_control_available: false,
      transport: "direct-oqlos",
    }),
    "hardwareRestart.runtimeDirect",
  );
});

test("keeps the backend remediation for an unavailable proxy runtime", () => {
  assert.equal(
    runtimeControlTranslationKey({ runtime_control_available: false }),
    "hardwareRestart.runtimeUnavailable",
  );
});
