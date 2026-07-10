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
  const targetBaud = Number(plan?.target_baudrate || 9600);
  const targetParity = String(plan?.target_parity || "N");
  const targetIds = Array.isArray(plan?.target_ids) ? plan.target_ids.map(Number) : [1, 2];
  const baudrates = Array.isArray(plan?.baud_probe_sequence) && plan.baud_probe_sequence.length
    ? plan.baud_probe_sequence.map(Number)
    : (targetBaud === 9600 ? [9600] : [9600, targetBaud]);
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
  return {
    serial_port: stepPort,
    current_device_id: currentDeviceId,
    new_device_id: Number(target.new_device_id || currentDeviceId),
    new_baudrate: Number(target.new_baudrate || candidate.baudrate || plan?.target_baudrate || 9600),
    new_parity: String(target.new_parity || candidate.parity || plan?.target_parity || "N"),
    confirm_isolated: true,
  };
}
