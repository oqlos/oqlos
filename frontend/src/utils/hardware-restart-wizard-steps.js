import { HardwareApi } from "../api/hardwareApi.js";
import {
  isOptionalWizardStep,
  isPumpOffUnavailableError,
  selectWizardProbeCandidate,
} from "./hardware-wizard-steps.js";

export function wizardStepSerialPort(plan, step) {
  return (
    step?.serial_port
    || step?.program_target?.serial_port
    || (step?.program_target?.module_role === "modbus-adc" ? plan?.adc_serial_port : null)
    || plan?.io_serial_port
    || plan?.serial_port
    || ""
  );
}

export function buildWizardProbePayload(plan, serialPort, moduleRole) {
  const targetBaud = Number(plan?.target_baudrate || 9600);
  const targetParity = String(plan?.target_parity || "N");
  const targetIds = Array.isArray(plan?.target_ids) ? plan.target_ids.map(Number) : [1, 2];
  const baudrates = [targetBaud, 19200].filter((v, i, a) => a.indexOf(v) === i);
  const parities = [targetParity];
  const device_ids = [...new Set([...targetIds, 1, 2, 3])];
  return {
    serial_port: serialPort,
    baudrates,
    parities,
    device_ids,
    ...(moduleRole ? { module_role: moduleRole } : {}),
    ...(plan?.modbus_topology ? { modbus_topology: plan.modbus_topology } : {}),
  };
}

export async function executeConfigureStep({
  currentStep,
  plan,
  confirmIsolated,
  confirmErrorKey,
  isSeparateAdapters,
  serialPort,
  refreshRuntimeStatus,
  t,
  runRetry,
  log,
  apiContext,
}) {
  if (!confirmIsolated) throw new Error(t(confirmErrorKey));
  const target = currentStep.program_target || {};
  const stepPort = wizardStepSerialPort(plan, currentStep);
  const role = String(target.module_role || "");
  const probePayload = buildWizardProbePayload(plan, stepPort, role);
  log(`Probe isolated module on ${stepPort} (backend zwalnia port RS485 automatycznie)...`);
  const probe = await runRetry("Probe", () => HardwareApi.probeModbusWizardIsolated(probePayload, apiContext), { allowRetry: false });
  log(`Probe result ok=${String(Boolean(probe?.ok))}, candidates=${(probe?.candidates || []).length}, runtime=${probe?.runtime_control || probe?.diagnostics?.runtime_control || "-"}`);
  if (probe?.diagnostics?.runtime_control_warning) log(`WARN: ${probe.diagnostics.runtime_control_warning}`);
  const candidates = Array.isArray(probe?.candidates) ? probe.candidates : [];
  const selection = selectWizardProbeCandidate(candidates, { moduleRole: role, newDeviceId: Number(target.new_device_id) });
  if (selection.error === "multiple_modbus_ids") throw new Error(t("hardwareRestart.multipleModbusIdsError", { ids: selection.deviceIds.join(", ") }));
  const selectedCandidate = selection.candidate || null;
  if (!selectedCandidate) {
    const hint = probe?.diagnostics?.failure_reason || (isSeparateAdapters ? t("hardwareRestart.probeFailSeparateAdapters") : "Sprawdz zasilanie, okablowanie A/B i izolacje magistrali.");
    throw new Error(`${t("hardwareRestart.probeNoCandidate")} ${hint}`);
  }
  const currentDeviceId = Number(selectedCandidate.device_id || target.new_device_id || 1);
  const programPayload = {
    serial_port: stepPort,
    current_device_id: currentDeviceId,
    new_device_id: Number(target.new_device_id || currentDeviceId),
    new_baudrate: Number(target.new_baudrate || selectedCandidate.baudrate || plan?.target_baudrate || 9600),
    new_parity: String(target.new_parity || selectedCandidate.parity || plan?.target_parity || "N"),
    confirm_isolated: true,
  };
  log(`Program module role=${role} current_id=${programPayload.current_device_id} -> new_id=${programPayload.new_device_id}, uart=${programPayload.new_baudrate}/${programPayload.new_parity}`);
  const program = await runRetry("Program", () => HardwareApi.programModbusWizardIsolated(programPayload, apiContext), { allowRetry: false });
  log(`Program result ok=${String(Boolean(program?.ok))} verified=${String(Boolean(program?.verified))} runtime=${program?.runtime_control || "-"}`);
  if (program?.writes?.skipped) log(program?.note || "INFO: modul juz ma docelowe ID/UART — pominieto zapis provisioning.");
  await refreshRuntimeStatus(stepPort || serialPort);
  return { ok: Boolean(program?.ok) || Boolean(program?.verified), payload: { step: currentStep, probe, program } };
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
