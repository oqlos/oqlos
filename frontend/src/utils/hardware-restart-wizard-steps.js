import { HardwareApi } from "../api/hardwareApi.js";
import {
  isOptionalWizardStep,
  isPumpOffUnavailableError,
} from "./hardware-wizard-steps.js";
import {
  runConfigureProbePhase,
  runConfigureProgramPhase,
} from "./hardware-restart-configure.js";
import { evaluateConfigureSkip } from "./hardware-restart-configure-skip.js";
import { wizardStepSerialPort } from "./hardware-restart-wizard-helpers.js";

export { buildWizardProbePayload, wizardStepSerialPort } from "./hardware-restart-wizard-helpers.js";

function configureSkipResult(currentStep, decision) {
  return {
    ok: true,
    skipped: true,
    payload: {
      step: currentStep,
      skipped: true,
      reason: decision.reason,
      health: decision.details || {},
    },
  };
}

function logConfigureSkip(log, role, details) {
  log?.(
    `SKIP: ${role} already at target UART `
    + `(status=${details.status}, compatible=${details.compatible}, `
    + `${details.live_baudrate || "?"}/${details.live_parity || "?"} id=${details.live_device_id ?? "?"}`
    + `${details.live_serial_port ? ` @ ${details.live_serial_port}` : ""}) — skip isolated probe/program.`,
  );
  if (details.note) log?.(`INFO: ${details.note}`);
}

/**
 * If OqlOS already has a healthy modbus-io / modbus-adc plugin on the planned
 * port, skip isolated probe+program (avoids RS485 port-busy failures).
 */
export async function trySkipConfigureIfAlreadyHealthy(ctx) {
  const { currentStep, plan, log, apiContext } = ctx;
  const target = currentStep?.program_target || {};
  const role = String(target.module_role || "");
  if (!role.startsWith("modbus-")) return null;

  let healthPayload;
  try {
    healthPayload = await HardwareApi.health(apiContext);
  } catch (err) {
    log?.(`WARN: health preflight failed — continue configure (${err?.message || err})`);
    return null;
  }

  const stepPort = wizardStepSerialPort(plan, currentStep);
  const decision = evaluateConfigureSkip({
    programTarget: target,
    stepSerialPort: stepPort,
    healthPayload,
  });
  if (!decision.skip) return null;

  logConfigureSkip(log, role, decision.details || {});
  return configureSkipResult(currentStep, decision);
}

export async function executeConfigureStep(ctx) {
  const { confirmIsolated, confirmErrorKey, t } = ctx;
  const skipped = await trySkipConfigureIfAlreadyHealthy(ctx);
  if (skipped) return skipped;
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
