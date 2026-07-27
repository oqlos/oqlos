import { parseConnectRole } from "./rbac.policy.js";

export const COIL_RESULT_OPTIONS = ["correct", "wrong", "no_response"];

export function nextUntestedCoil(coils = [], results = {}) {
  return coils.find((coil) => !results[String(coil.address)]) || null;
}

export function buildCoilTestReport(plan, results, pulses) {
  return {
    schema: "oqlos-boardnet-coil-test-v1",
    generated_at: new Date().toISOString(),
    boardnet: {
      mode: plan?.mode || "unknown",
      module: plan?.module || {},
      safety: plan?.safety || {},
    },
    coils: (plan?.coils || []).map((coil) => ({
      ...coil,
      operator_result: results[String(coil.address)] || "not_tested",
      pulse: pulses[String(coil.address)] || null,
    })),
  };
}

export function pulseConfirmation(coil) {
  return `PULSE_DO${Number(coil?.address) + 1}`;
}

/**
 * Pass the already-normalized Connect UI role to the guarded pulse endpoint.
 * This does not grant a role: the endpoint still rejects every value outside
 * system/admin and keeps confirmation, preflight, locking and automatic OFF.
 */
export function coilPulseRequestOptions(role, logContext) {
  const normalized = parseConnectRole(role);
  const privileged = normalized === "system" || normalized === "admin";
  return {
    ...(logContext ? { logContext } : {}),
    ...(privileged ? { headers: { "X-Connect-Role": normalized } } : {}),
  };
}
