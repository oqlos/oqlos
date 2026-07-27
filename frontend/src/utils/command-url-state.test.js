import assert from "node:assert/strict";
import test from "node:test";

import { recordCommandUrlState } from "./command-url-state.js";

test("command state replaces local URL without triggering execution", () => {
  const calls = [];
  const browser = {
    location: {
      href: "http://boardnet/ui/hardware-coils?role=system",
      pathname: "/ui/hardware-coils",
      search: "?role=system",
    },
    history: { replaceState: (...args) => calls.push(args) },
  };
  assert.equal(recordCommandUrlState({ COMMAND: "coil-test-pulse", ERRORS: "PENDING" }, browser), true);
  assert.deepEqual(calls, [[
    null,
    "",
    "/ui/hardware-coils?role=system&COMMAND=coil-test-pulse&ERRORS=PENDING",
  ]]);
});
