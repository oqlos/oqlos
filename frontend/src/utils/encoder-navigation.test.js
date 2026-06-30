import test from "node:test";
import assert from "node:assert/strict";

import {
  applyScrollToItems,
  parseParentEncoderEnvelope,
} from "./encoder-navigation.js";

test("parseParentEncoderEnvelope accepts parent.encoderCommand", () => {
  const envelope = parseParentEncoderEnvelope({
    type: "parent.encoderCommand",
    payload: { command: "scroll", delta: 1 },
  });
  assert.equal(envelope?.payload?.command, "scroll");
});

test("applyScrollToItems wraps at list bounds", () => {
  assert.equal(applyScrollToItems(["a", "b"], 1, 1), 0);
  assert.equal(applyScrollToItems(["a", "b"], 0, -1), 1);
});
