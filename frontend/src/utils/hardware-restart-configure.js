import { HardwareApi } from "../api/hardwareApi.js";
import { resolveWizardProbeCandidate } from "./hardware-restart-probe-select.js";
import {
  buildWizardProbePayload,
  buildWizardProgramPayload,
  wizardStepSerialPort,
} from "./hardware-restart-wizard-helpers.js";

export { resolveWizardProbeCandidate } from "./hardware-restart-probe-select.js";

export async function runConfigureProbePhase({
  currentStep,
  plan,
  isSeparateAdapters,
  t,
  runRetry,
  log,
  apiContext,
}) {
  const target = currentStep.program_target || {};
  const stepPort = wizardStepSerialPort(plan, currentStep);
  const role = String(target.module_role || "");
  const probePayload = buildWizardProbePayload(plan, stepPort, role);
  log(`Probe isolated module on ${stepPort} (backend zwalnia port RS485 automatycznie)...`);
  const probe = await runRetry(
    "Probe",
    () => HardwareApi.probeModbusWizardIsolated(probePayload, apiContext),
    { allowRetry: false },
  );
  log(`Probe result ok=${String(Boolean(probe?.ok))}, candidates=${(probe?.candidates || []).length}, runtime=${probe?.runtime_control || probe?.diagnostics?.runtime_control || "-"}`);
  if (probe?.diagnostics?.runtime_control_warning) {
    log(`WARN: ${probe.diagnostics.runtime_control_warning}`);
  }
  const candidate = resolveWizardProbeCandidate(probe, role, target, isSeparateAdapters, t);
  return { stepPort, target, role, probe, candidate };
}

export async function runConfigureProgramPhase({
  stepPort,
  target,
  role,
  probe,
  candidate,
  plan,
  serialPort,
  refreshRuntimeStatus,
  runRetry,
  log,
  apiContext,
  currentStep,
}) {
  const programPayload = buildWizardProgramPayload(stepPort, target, candidate, plan);
  log(
    `Program module role=${role} `
    + `open@${programPayload.current_baudrate || "?"} id=${programPayload.current_device_id} `
    + `-> target id=${programPayload.new_device_id} uart=${programPayload.new_baudrate}/${programPayload.new_parity} `
    + `(commission: baseline then raise baud)`,
  );
  const program = await runRetry(
    "Program",
    () => HardwareApi.programModbusWizardIsolated(programPayload, apiContext),
    { allowRetry: false },
  );
  log(`Program result ok=${String(Boolean(program?.ok))} verified=${String(Boolean(program?.verified))} runtime=${program?.runtime_control || "-"}`);
  if (program?.writes?.skipped) {
    log(program?.note || "INFO: modul juz ma docelowe ID/UART — pominieto zapis provisioning.");
  }
  await refreshRuntimeStatus(stepPort || serialPort);
  return {
    ok: Boolean(program?.ok) || Boolean(program?.verified),
    payload: { step: currentStep, probe, program },
  };
}
