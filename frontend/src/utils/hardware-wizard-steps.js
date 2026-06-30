/** Wizard step classification for /hardware-restart kit + Modbus flow. */

/**
 * @param {{ step?: string; action?: { type?: string }; verify_endpoint?: string } | null | undefined} step
 * @returns {"configure" | "diagnostic" | "peripheral-status" | "final-check" | "unknown"}
 */
export function wizardStepKind(step) {
  if (!step || typeof step !== "object") {
    return "unknown";
  }
  const stepId = String(step.step || "");
  if (stepId.startsWith("configure-")) {
    return "configure";
  }
  if (step.action?.type === "diagnostic") {
    return "diagnostic";
  }
  if (step.action?.type === "peripheral-status") {
    return "peripheral-status";
  }
  if (stepId === "final-check-all-connected" || step.verify_endpoint) {
    return "final-check";
  }
  return "unknown";
}

/**
 * RTC / piRTC is RPi-only; optional steps may fail without blocking the wizard.
 *
 * @param {{ step?: string; optional?: boolean } | null | undefined} step
 * @returns {boolean}
 */
/** pump_off when DRI0050 sidecar or OqlOS motor plugin is down (manual skip only). */
export function isSkippablePumpOffWizardStep(step) {
  return String(step?.step || "") === "reconfigure-motor-dri0050";
}

export function isPumpOffUnavailableError(message) {
  const normalized = String(message || "").toLowerCase();
  return (
    normalized.includes("motor plugin not available")
    || normalized.includes("dri0050 pump command failed")
    || normalized.includes("input/output error")
    || normalized.includes("write timeout")
  );
}

/**
 * Pick the probe candidate for an isolated configure step.
 *
 * @param {Array<{ role?: string; device_id?: number }>} candidates
 * @param {{ moduleRole?: string; newDeviceId?: number }} target
 * @returns {{ candidate: object } | { error: string; deviceIds: number[] }}
 */
export function selectWizardProbeCandidate(candidates, { moduleRole = "", newDeviceId } = {}) {
  const role = String(moduleRole || "");
  const pool = (Array.isArray(candidates) ? candidates : []).filter(
    (entry) => !role || String(entry?.role || "") === role,
  );
  const list = pool.length ? pool : (Array.isArray(candidates) ? candidates : []);
  if (!list.length) {
    return { error: "no_candidate" };
  }

  const deviceIds = [
    ...new Set(
      list
        .map((entry) => Number(entry?.device_id))
        .filter((value) => Number.isFinite(value) && value > 0),
    ),
  ];
  const targetId = Number(newDeviceId);

  if (deviceIds.length > 1 && Number.isFinite(targetId)) {
    const atTarget = list.some((entry) => Number(entry?.device_id) === targetId);
    const notAtTarget = list.some((entry) => Number(entry?.device_id) !== targetId);
    if (atTarget && notAtTarget) {
      return { error: "multiple_modbus_ids", deviceIds };
    }
  }

  if (Number.isFinite(targetId)) {
    const alreadyAtTarget = list.find((entry) => Number(entry?.device_id) === targetId);
    if (alreadyAtTarget) {
      return { candidate: alreadyAtTarget };
    }
    const needsProgramming = list.find((entry) => Number(entry?.device_id) !== targetId);
    if (needsProgramming) {
      return { candidate: needsProgramming };
    }
  }

  return { candidate: list[0] };
}

export function isOptionalWizardStep(step) {
  if (!step || typeof step !== "object") {
    return false;
  }
  if (step.optional === true) {
    return true;
  }
  if (String(step.step || "") === "reconfigure-rtc") {
    return true;
  }
  const action = step.action;
  if (action && typeof action === "object") {
    return String(action.peripheral_id || "").trim().toLowerCase() === "rtc";
  }
  return false;
}
