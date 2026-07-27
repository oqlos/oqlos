/** Pure helpers for hardware restart wizard (no HardwareApi dependency). */

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
  const role = String(moduleRole || "").toLowerCase();
  const baselineBaud = role.includes("adc") ? 9600 : 4800;
  // ADC may have a different target baud than IO; probe the role baseline first.
  const targetBaud = Number(
    role.includes("adc")
      ? (plan?.target_adc_baudrate || plan?.target_baudrate || baselineBaud)
      : (plan?.target_baudrate || baselineBaud),
  );
  const targetParity = String(plan?.target_parity || "N");
  const targetIds = Array.isArray(plan?.target_ids) ? plan.target_ids.map(Number) : [1, 2];
  // Commissioning order: lowest/baseline first, then target (build_init_baud_sequence).
  const baudrates = Array.isArray(plan?.baud_probe_sequence) && plan.baud_probe_sequence.length
    ? plan.baud_probe_sequence.map(Number)
    : (targetBaud === baselineBaud ? [baselineBaud] : [baselineBaud, targetBaud]);
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

export function buildWizardProgramPayload(stepPort, target, candidate, plan) {
  const currentDeviceId = Number(candidate.device_id || target.new_device_id || 1);
  const role = String(target?.module_role || plan?.module_role || "").toLowerCase();
  const baselineBaud = role.includes("adc") ? 9600 : 4800;
  // Open bus at the baud probe found (usually the role baseline), then write target UART.
  const currentBaud = Number(
    candidate.baudrate
    || plan?.baseline_baudrate
    || baselineBaud,
  );
  return {
    serial_port: stepPort,
    current_device_id: currentDeviceId,
    current_baudrate: currentBaud,
    new_device_id: Number(target.new_device_id || currentDeviceId),
    new_baudrate: Number(target.new_baudrate || candidate.baudrate || plan?.target_baudrate || baselineBaud),
    new_parity: String(target.new_parity || candidate.parity || plan?.target_parity || "N"),
    confirm_isolated: true,
  };
}
