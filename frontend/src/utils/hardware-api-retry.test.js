import test from "node:test";
import assert from "node:assert/strict";

import { runApiWithRetry } from "@semcod/frontend-services/hardware-api-retry.js";

test("runApiWithRetry returns action result on first success", async () => {
  const result = await runApiWithRetry("Probe", async () => ({ ok: true }));
  assert.deepEqual(result, { ok: true });
});

test("runApiWithRetry retries 502 then succeeds", async () => {
  let calls = 0;
  const result = await runApiWithRetry(
    "Probe",
    async () => {
      calls += 1;
      if (calls === 1) {
        const err = new Error("bad gateway");
        err.status = 502;
        throw err;
      }
      return { ok: true };
    },
    { retryDelaysMs: [1] },
  );
  assert.equal(calls, 2);
  assert.deepEqual(result, { ok: true });
});

test("runApiWithRetry does not retry when allowRetry=false", async () => {
  let calls = 0;
  await assert.rejects(
    () => runApiWithRetry(
      "Probe",
      async () => {
        calls += 1;
        const err = new Error("bad gateway");
        err.status = 503;
        throw err;
      },
      { allowRetry: false, retryDelaysMs: [1] },
    ),
  );
  assert.equal(calls, 1);
});
