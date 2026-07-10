export const MOTOR_DEVICE_IDS = ["motor-tic249", "motor-dri0050"];

export function filterMotorDiagnosis(data) {
  if (!data || typeof data !== "object") return data;
  const devices = data.devices || {};
  const motorDevices = {};
  for (const id of MOTOR_DEVICE_IDS) {
    if (devices[id]) motorDevices[id] = devices[id];
  }
  const globalActions = (data.global_actions || []).filter((action) => {
    const deviceId = String(action?.device_id || "");
    const actionId = String(action?.id || "");
    if (actionId.startsWith("global-modbus")) return false;
    if (deviceId.startsWith("modbus")) return false;
    return deviceId === "*" || MOTOR_DEVICE_IDS.includes(deviceId);
  });
  return {
    ...data,
    devices: motorDevices,
    global_actions: globalActions,
  };
}

export function filterMotorRepairs(repairs) {
  return (repairs || []).filter((entry) => {
    const step = String(entry?.step || "");
    return step.includes("tic249") || step.includes("dri0050");
  });
}
