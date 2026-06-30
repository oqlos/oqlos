import test from "node:test";
import assert from "node:assert/strict";

import { applyObjectActionArgMutation, syncMoveRelativeArgs } from "./mapEditorObjectActionEdits.js";

test("syncMoveRelativeArgs mirrors steps to signed offset", () => {
  const binding = {
    body: { command: "move_relative" },
    args: { direction: "left", steps: 120 },
  };
  syncMoveRelativeArgs(binding, "move-left");
  assert.equal(binding.args.offset, -120);
});

test("applyObjectActionArgMutation writes numeric args", () => {
  const next = {
    objectActionMap: {
      head: {
        move: { body: { command: "move_relative" }, args: { direction: "right" } },
      },
    },
  };
  const ok = applyObjectActionArgMutation(next, {
    objectName: "head",
    actionName: "move",
    argName: "steps",
    value: "80",
    type: "number",
  });
  assert.equal(ok, true);
  assert.equal(next.objectActionMap.head.move.args.steps, 80);
  assert.equal(next.objectActionMap.head.move.args.offset, 80);
});
