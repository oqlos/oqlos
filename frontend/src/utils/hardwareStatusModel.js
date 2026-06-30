/** Pure helpers for the hardware status page (HardwareStatus.jsx). */

export function adapterStatusBadgeClass(status) {
  const normalized = String(status || "unknown").toLowerCase();
  if (normalized === "ok") return "hw-badge hw-badge-ok";
  if (normalized === "error" || normalized === "fail" || normalized === "failed") {
    return "hw-badge hw-badge-err";
  }
  return "hw-badge hw-badge-warn";
}

export function extractHardwareDiagnostics(identify) {
  const diagnostics = identify?.diagnostics && typeof identify.diagnostics === "object"
    ? identify.diagnostics
    : {};
  return {
    serialPorts: diagnostics.serial_ports || diagnostics.modbus_preflight?.serial_ports || [],
    i2cBuses: diagnostics.i2c_buses || [],
    usbDevices: diagnostics.usb_devices || diagnostics.usb || [],
  };
}

export function listHardwareAdapters(identify) {
  return Array.isArray(identify?.adapters) ? identify.adapters : [];
}

export function formatHardwareJson(value) {
  return JSON.stringify(value ?? null, null, 2);
}

export function hardwareStatusSummary(health, identify) {
  return {
    mode: identify?.mode || health?.mode || "unknown",
    detected: identify?.detected ?? "—",
    total: identify?.total ?? "—",
    transport: health?.transport || "direct-oqlos",
  };
}
