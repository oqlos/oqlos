import test from "node:test";
import assert from "node:assert/strict";

import { estimateOqlWaitMs, splitOqlIntoGoalScripts, timeoutMsForOqlScript } from "./oqlGoals.js";

test("splitOqlIntoGoalScripts sends each top-level GOAL with scenario header", () => {
  const source = `VERSION: 4
SCENARIO: PSS

GOAL:
  SET NAME 'Test wizualny'
  LOG 'start'

GOAL:
  SET NAME "Test pompy"
  SET 'pump-main' '5.0 l/min'
  SET WAIT '1 s'
`;

  const goals = splitOqlIntoGoalScripts(source);

  assert.equal(goals.length, 2);
  assert.equal(goals[0].name, "Test wizualny");
  assert.equal(goals[1].name, "Test pompy");
  assert.match(goals[0].script, /^VERSION: 4\nSCENARIO: PSS\n\nGOAL:/);
  assert.match(goals[1].script, /^VERSION: 4\nSCENARIO: PSS\n\nGOAL:/);
  assert.doesNotMatch(goals[0].script, /Test pompy/);
  assert.match(goals[1].script, /SET WAIT '1 s'/);
});

test("splitOqlIntoGoalScripts falls back to one script when there are no goals", () => {
  const goals = splitOqlIntoGoalScripts("SET 'pump' 0\n");
  assert.equal(goals.length, 1);
  assert.equal(goals[0].name, "Cały scenariusz");
  assert.equal(goals[0].script, "SET 'pump' 0\n");
});

test("estimateOqlWaitMs supports SET WAIT and legacy WAIT syntax", () => {
  assert.equal(
    estimateOqlWaitMs(`
GOAL:
  SET WAIT '1 s'
  SET WAIT '500 ms'
  WAIT 2s
  SET WAIT '0.5 min'
`),
    33_500,
  );
});

test("timeoutMsForOqlScript gives long GOAL blocks enough time", () => {
  assert.equal(timeoutMsForOqlScript("SET WAIT '60 s'", 1), 90_000);
  assert.equal(timeoutMsForOqlScript("SET WAIT '60 s'", 3), 60_000);
  assert.equal(timeoutMsForOqlScript("SET 'pump' 0", 1), 60_000);
});
