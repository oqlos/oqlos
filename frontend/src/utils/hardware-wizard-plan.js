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

export function extractWizardPlan(stack) {
  if (stack?.ok === false) {
    const hint = stack?.hint ? ` ${stack.hint}` : "";
    throw new Error(`${stack?.error || "OqlOS niedostepny (port 8202)"}${hint}`);
  }
  const data = stack?.wizard_plan_enriched || stack?.configuration_cycle?.wizard_plan || stack?.wizard_plan;
  if (!data || typeof data !== "object") {
    throw new Error("Brak planu kreatora w hardware stack snapshot");
  }
  return data;
}
