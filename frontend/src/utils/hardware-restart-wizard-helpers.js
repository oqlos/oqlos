/** Pure helpers for hardware restart wizard (no HardwareApi dependency). */

function moduleRole(target, plan) {
  return String(target?.module_role || plan?.module_role || "").toLowerCase();
}

function baselineBaudrate(role) {
  return role.includes("adc") ? 9600 : 4800;
}

function targetBaudrate(plan, role, baselineBaud) {
  const target = role.includes("adc")
    ? plan?.target_adc_baudrate || plan?.target_baudrate
    : plan?.target_baudrate;
  return Number(target || baselineBaud);
}

function probeBaudrates(plan, targetBaud, baselineBaud) {
  if (Array.isArray(plan?.baud_probe_sequence) && plan.baud_probe_sequence.length) {
    return plan.baud_probe_sequence.map(Number);
  }
  return targetBaud === baselineBaud ? [baselineBaud] : [baselineBaud, targetBaud];
}

function currentDeviceId(candidate, target) {
  return Number(candidate.device_id || target.new_device_id || 1);
}

function currentBaudrate(candidate, plan, baselineBaud) {
  return Number(candidate.baudrate || plan?.baseline_baudrate || baselineBaud);
}

function targetUart(candidate, target, plan, baselineBaud, deviceId) {
  return {
    new_device_id: Number(target.new_device_id || deviceId),
    new_baudrate: Number(target.new_baudrate || candidate.baudrate || plan?.target_baudrate || baselineBaud),
    new_parity: String(target.new_parity || candidate.parity || plan?.target_parity || "N"),
  };
}

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
  const baselineBaud = baselineBaudrate(role);
  // ADC may have a different target baud than IO; probe the role baseline first.
  const targetBaud = targetBaudrate(plan, role, baselineBaud);
  const targetParity = String(plan?.target_parity || "N");
  const targetIds = Array.isArray(plan?.target_ids) ? plan.target_ids.map(Number) : [1, 2];
  // Commissioning order: lowest/baseline first, then target (build_init_baud_sequence).
  const baudrates = probeBaudrates(plan, targetBaud, baselineBaud);
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
  const role = moduleRole(target, plan);
  const baselineBaud = baselineBaudrate(role);
  const deviceId = currentDeviceId(candidate, target);
  // Open bus at the baud probe found (usually the role baseline), then write target UART.
  const currentBaud = currentBaudrate(candidate, plan, baselineBaud);
  return {
    serial_port: stepPort,
    current_device_id: deviceId,
    current_baudrate: currentBaud,
    ...targetUart(candidate, target, plan, baselineBaud, deviceId),
    confirm_isolated: true,
  };
}
