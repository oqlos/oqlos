/** Plan load failures when connect-scenario-backend cannot reach OqlOS :8202. */
export function isOqlosUnreachableError(message) {
  const normalized = String(message || "").toLowerCase();
  return (
    normalized.includes("cannot reach oqlos")
    || normalized.includes("all connection attempts failed")
    || normalized.includes("oqlos unavailable")
    || normalized.includes("connection refused")
  );
}

/** Throw a descriptive error when the stack itself reports failure. */
function throwIfStackError(stack) {
  if (stack?.ok === false) {
    const hint = stack?.hint ? ` ${stack.hint}` : "";
    throw new Error(`${stack?.error || "OqlOS niedostepny (port 8202)"}${hint}`);
  }
}

/** Find the wizard plan object in any of the known stack locations. */
function findPlanData(stack) {
  return (
    stack?.wizard_plan_enriched
    || stack?.configuration_cycle?.wizard_plan
    || stack?.wizard_plan
  );
}

/** Validate that the extracted data is a non-null object. */
function assertPlanData(data) {
  if (!data || typeof data !== "object") {
    throw new Error("Brak planu kreatora w hardware stack snapshot");
  }
}

export function extractWizardPlan(stack) {
  throwIfStackError(stack);
  const data = findPlanData(stack);
  assertPlanData(data);
  return data;
}
