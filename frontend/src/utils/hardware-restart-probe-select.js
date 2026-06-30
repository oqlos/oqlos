import { selectWizardProbeCandidate } from "./hardware-wizard-steps.js";

export function resolveWizardProbeCandidate(probe, role, target, isSeparateAdapters, t) {
  const candidates = Array.isArray(probe?.candidates) ? probe.candidates : [];
  const selection = selectWizardProbeCandidate(candidates, {
    moduleRole: role,
    newDeviceId: Number(target.new_device_id),
  });
  if (selection.error === "multiple_modbus_ids") {
    throw new Error(t("hardwareRestart.multipleModbusIdsError", { ids: selection.deviceIds.join(", ") }));
  }
  const candidate = selection.candidate || null;
  if (!candidate) {
    const hint = probe?.diagnostics?.failure_reason
      || (isSeparateAdapters ? t("hardwareRestart.probeFailSeparateAdapters") : "Sprawdz zasilanie, okablowanie A/B i izolacje magistrali.");
    throw new Error(`${t("hardwareRestart.probeNoCandidate")} ${hint}`);
  }
  return candidate;
}
