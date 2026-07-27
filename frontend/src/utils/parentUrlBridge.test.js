import assert from "node:assert/strict";
import test from "node:test";

import {
  bridgeSearchToParent,
  OQLOS_PARENT_NAVIGATE_MESSAGE,
} from "./parentUrlBridge.js";

test("bridge sends command state through the OqlOS parent protocol", () => {
  const messages = [];
  const originalWindow = globalThis.window;
  const parent = { postMessage: (...args) => messages.push(args) };
  globalThis.window = { parent };
  try {
    bridgeSearchToParent({ COMMAND: "coil-test-pulse", ERRORS: "HTTP_403,ROLE_REQUIRED" });
  } finally {
    globalThis.window = originalWindow;
  }

  assert.equal(OQLOS_PARENT_NAVIGATE_MESSAGE, "oqlos-hardware:navigate");
  assert.deepEqual(messages, [[{
    type: "oqlos-hardware:navigate",
    search: "COMMAND=coil-test-pulse&ERRORS=HTTP_403%2CROLE_REQUIRED",
  }, "*"]]);
});
