import { HardwareApi } from "../api/hardwareApi.js";
import {
  isOptionalWizardStep,
  isPumpOffUnavailableError,
} from "./hardware-wizard-steps.js";
import {
  runConfigureProbePhase,
  runConfigureProgramPhase,
} from "./hardware-restart-configure.js";

export { buildWizardProbePayload, wizardStepSerialPort } from "./hardware-restart-wizard-helpers.js";

export async function executeConfigureStep(ctx) {
  const { confirmIsolated, confirmErrorKey, t } = ctx;
  if (!confirmIsolated) throw new Error(t(confirmErrorKey));
  const probePhase = await runConfigureProbePhase(ctx);
  return runConfigureProgramPhase({ ...ctx, ...probePhase });
}

export async function executeDiagnosticStep({ currentStep, t, runRetry, log, apiContext }) {
  const { peripheral_id: peripheralId, command, args = {} } = currentStep.action;
  log(`Diagnostic ${peripheralId}.${command}...`);
  const diagnostic = await runRetry("Diagnostic", () => HardwareApi.runDiagnosticCommand({ peripheral_id: peripheralId, command, args }, apiContext));
  log(`Diagnostic result ok=${String(Boolean(diagnostic?.ok))}`);
  const ok = Boolean(diagnostic?.ok);
  if (!ok && isOptionalWizardStep(currentStep)) log(`WARN: krok opcjonalny (${currentStep.step}) — RTC/piRTC tylko na RPi; kontynuuję mimo błędu.`);
  if (!ok && peripheralId === "motor-dri0050" && isPumpOffUnavailableError(diagnostic?.error)) log(t("hardwareRestart.pumpErrorRemedy"));
  return { ok, payload: { step: currentStep, diagnostic } };
}

export async function executePeripheralStatusStep({ currentStep, runRetry, log, apiContext }) {
  const { peripheral_id: peripheralId } = currentStep.action;
  log(`Peripheral status ${peripheralId}...`);
  const status = await runRetry("Status", () => HardwareApi.peripheralStatus(peripheralId, apiContext));
  log(`Status result ok=${String(Boolean(status?.ok))}`);
  return { ok: Boolean(status?.ok), payload: { step: currentStep, status } };
}

export async function executeFinalDiagnoseStep({ currentStep, t, runRetry, log, apiContext }) {
  log("Run final waveshare diagnose with all modules connected...");
  log(t("hardwareRestart.finalDiagnoseSlowHint"));
  const diagnose = await runRetry("Diagnose", () => HardwareApi.getModbusWaveshareDiagnose(apiContext), { retryDelaysMs: [3000, 15000, 45000] });
  if (diagnose?.runtime_control) log(`Diagnose runtime_control=${diagnose.runtime_control}`);
  log(`Final diagnose ok=${String(Boolean(diagnose?.ok))}`);
  return { ok: Boolean(diagnose?.ok), payload: { step: currentStep, diagnose } };
}
