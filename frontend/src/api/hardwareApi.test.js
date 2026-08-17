import test from "node:test";
import assert from "node:assert/strict";

import { HardwareApi } from "./hardwareApi.js";

test("executePluginCommand posts the plugin id, command and params", async () => {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    return {
      ok: true,
      status: 200,
      json: async () => ({ success: true }),
    };
  };

  const result = await HardwareApi.executePluginCommand(
    "io-m5-4in8out",
    "set_coil",
    { coil: 2, value: true },
  );

  assert.deepEqual(result, { success: true });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "/api/v1/plugins/io-m5-4in8out/execute");
  assert.equal(calls[0].init.method, "POST");
  assert.deepEqual(JSON.parse(calls[0].init.body), {
    command: "set_coil",
    params: { coil: 2, value: true },
    args: { coil: 2, value: true },
  });
});
