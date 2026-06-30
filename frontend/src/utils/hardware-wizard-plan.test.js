import test from "node:test";
import assert from "node:assert/strict";

import { extractWizardPlan } from "./hardware-wizard-plan.js";

test("extractWizardPlan reads enriched wizard plan", () => {
  const plan = extractWizardPlan({ wizard_plan_enriched: { steps: [{ step: "a" }] } });
  assert.equal(plan.steps[0].step, "a");
});

test("extractWizardPlan throws when stack reports failure", () => {
  assert.throws(
    () => extractWizardPlan({ ok: false, error: "down" }),
    /down/,
  );
});
