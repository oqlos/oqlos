/** Wizard step classification for /hardware-modbus kit + Modbus flow. */

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
function _filterCandidatesByRole(candidates, role) {
  const all = Array.isArray(candidates) ? candidates : [];
  if (!role) return all;
  const matching = all.filter((entry) => String(entry?.role || "") === role);
  return matching.length ? matching : all;
}

function _findBestCandidate(list, targetId) {
  if (!Number.isFinite(targetId)) return { candidate: list[0] };
  const atTarget = list.find((entry) => Number(entry?.device_id) === targetId);
  if (atTarget) return { candidate: atTarget };
  const needsProgramming = list.find((entry) => Number(entry?.device_id) !== targetId);
  if (needsProgramming) return { candidate: needsProgramming };
  return { candidate: list[0] };
}

export function selectWizardProbeCandidate(candidates, { moduleRole = "", newDeviceId } = {}) {
  const list = _filterCandidatesByRole(candidates, String(moduleRole || ""));
  if (!list.length) return { error: "no_candidate" };

  const targetId = Number(newDeviceId);
  const deviceIds = [...new Set(list.map((e) => Number(e?.device_id)).filter((v) => Number.isFinite(v) && v > 0))];
  if (deviceIds.length > 1 && Number.isFinite(targetId)) {
    const atTarget = list.some((e) => Number(e?.device_id) === targetId);
    const notAtTarget = list.some((e) => Number(e?.device_id) !== targetId);
    if (atTarget && notAtTarget) return { error: "multiple_modbus_ids", deviceIds };
  }

  return _findBestCandidate(list, targetId);
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
