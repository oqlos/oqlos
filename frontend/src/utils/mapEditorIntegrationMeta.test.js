import test from "node:test";
import assert from "node:assert/strict";

import { readIntegrationMeta, setMetaField } from "./mapEditorIntegrationMeta.js";

test("readIntegrationMeta reads object binding fields from first action", () => {
  const meta = readIntegrationMeta("objects", {
    left: {
      environment: "lab",
      usageMode: "test",
      body: { peripheral_id: "motor-tic249", command: "move_relative" },
    },
  });
  assert.equal(meta.environment, "lab");
  assert.equal(meta.usageMode, "test");
  assert.equal(meta.hardwareAddress, "motor-tic249");
});

test("readIntegrationMeta reads func endpoint from detail config", () => {
  const meta = readIntegrationMeta("funcs", {
    environment: "prod",
    service: "hardware",
    endpoint: "/api/hui/run",
    handlerRuntime: "python",
    handlerFunction: "run",
  });
  assert.equal(meta.environment, "prod");
  assert.equal(meta.apiService, "hardware");
  assert.equal(meta.apiEndpoint, "/api/hui/run");
  assert.equal(meta.handlerRuntime, "python");
  assert.equal(meta.handlerFunction, "run");
});

test("setMetaField updates api endpoint and clears empty values", () => {
  const target = { url: "/old", endpoint: "/old" };
  setMetaField(target, "apiEndpoint", "  /new  ");
  assert.equal(target.endpoint, "/new");
  assert.equal(target.url, "/new");

  setMetaField(target, "apiEndpoint", "");
  assert.equal(target.endpoint, undefined);
  assert.equal(target.url, undefined);
});
