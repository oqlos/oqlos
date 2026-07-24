import assert from "node:assert/strict";
import test from "node:test";

import { ParentOqlEventError, requestParentOqlEvent } from "./parentOqlEventBridge.js";

test("returns null outside an authenticated parent iframe", async () => {
  const hadLocation = Object.hasOwn(globalThis, "location");
  const previousLocation = globalThis.location;
  const hadParent = Object.hasOwn(globalThis, "parent");
  const previousParent = globalThis.parent;
  Object.defineProperty(globalThis, "location", {
    configurable: true,
    value: { search: "" },
  });
  Object.defineProperty(globalThis, "parent", {
    configurable: true,
    value: globalThis,
  });

  try {
    assert.equal(
      await requestParentOqlEvent("system.hardware-map.validate.requested", { sections: {} }),
      null,
    );
  } finally {
    if (hadLocation) {
      Object.defineProperty(globalThis, "location", { configurable: true, value: previousLocation });
    } else {
      delete globalThis.location;
    }
    if (hadParent) {
      Object.defineProperty(globalThis, "parent", { configurable: true, value: previousParent });
    } else {
      delete globalThis.parent;
    }
  }
});

test("preserves structured parent diagnostics for the MAP editor", async () => {
  const previousLocation = globalThis.location;
  const previousParent = globalThis.parent;
  const previousAdd = globalThis.addEventListener;
  const previousRemove = globalThis.removeEventListener;
  let messageListener;
  const parent = {
    postMessage(envelope) {
      queueMicrotask(() => messageListener?.({
        origin: "http://localhost:8100",
        source: parent,
        data: {
          type: "parent.oqlEvent.response",
          version: "1.0",
          requestId: envelope.requestId,
          payload: {
            ok: false,
            error: {
              message: "C2004-HW-0012 · Required hardware unavailable: modbus-io",
              error_code: "C2004-HW-0012",
              status_code: 503,
              correlation_id: "corr-map-1",
              run_id: "run-map-1",
              stage: "adapter.execute",
              component: "modbus-io",
              failure_codes: ["modbus-io_not_found"],
              hint: "Sprawdź zasilanie oraz przewody A/B/GND.",
            },
          },
        },
      }));
    },
  };
  Object.defineProperty(globalThis, "location", {
    configurable: true,
    value: { search: "?parent_origin=http%3A%2F%2Flocalhost%3A8100" },
  });
  Object.defineProperty(globalThis, "parent", { configurable: true, value: parent });
  globalThis.addEventListener = (type, listener) => {
    if (type === "message") messageListener = listener;
  };
  globalThis.removeEventListener = () => {};

  try {
    const failure = await requestParentOqlEvent(
      "system.hardware-map.update.requested",
      { sections: {} },
    ).catch((error) => error);
    assert.ok(failure instanceof ParentOqlEventError);
    assert.equal(failure.errorCode, "C2004-HW-0012");
    assert.equal(failure.correlationId, "corr-map-1");
    assert.equal(failure.runId, "run-map-1");
    assert.deepEqual(failure.failureCodes, ["modbus-io_not_found"]);
    assert.equal(failure.hint, "Sprawdź zasilanie oraz przewody A/B/GND.");
  } finally {
    Object.defineProperty(globalThis, "location", { configurable: true, value: previousLocation });
    Object.defineProperty(globalThis, "parent", { configurable: true, value: previousParent });
    globalThis.addEventListener = previousAdd;
    globalThis.removeEventListener = previousRemove;
  }
});
