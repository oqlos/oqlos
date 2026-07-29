/**
 * Auto-skip configure-modbus-* only when the plugin is already at the *target*
 * UART (device_id + baud + parity). Healthy-at-baseline alone is NOT enough:
 * commissioning intentionally starts at lowest baud (9600), then raises speed.
 */

const HEALTHY_STATUSES = new Set(["connected", "ok", "healthy"]);
const BASELINE_BAUD = 9600;

function skipDecision(reason, details) {
  return details ? { skip: false, reason, details } : { skip: false, reason };
}

function uartDetails(entry) {
  const details = entry.details && typeof entry.details === "object" ? entry.details : {};
  return {
    details,
    livePort: String(details.serial_port || details.port || "").trim(),
    liveId: details.device_id,
    liveBaud: details.baudrate != null ? Number(details.baudrate) : null,
    liveParity: String(details.parity || "N").toUpperCase(),
  };
}

function baudRampDecision(role, liveBaud, targetBaud) {
  const canCompare = targetBaud != null
    && liveBaud != null
    && Number.isFinite(targetBaud)
    && Number.isFinite(liveBaud);
  if (!canCompare || liveBaud === targetBaud) return null;
  const note = liveBaud === BASELINE_BAUD && targetBaud > BASELINE_BAUD
    ? `Module healthy at baseline ${BASELINE_BAUD}; still need raise to ${targetBaud}`
    : `Live baud ${liveBaud} ≠ target ${targetBaud} — continue configure`;
  return skipDecision("baud-ramp-pending", {
    role,
    live_baudrate: liveBaud,
    target_baudrate: targetBaud,
    baseline_baudrate: BASELINE_BAUD,
    note,
  });
}

function alreadyConfiguredDecision(role, entry, live) {
  return {
    skip: true,
    reason: "already_at_target",
    details: {
      role,
      status: entry.status,
      compatible: entry.compatible,
      live_baudrate: live.liveBaud,
      live_parity: live.liveParity,
      live_device_id: live.liveId,
      live_serial_port: live.livePort,
      note: `Plugin ${role} already at target UART ${live.liveBaud}/${live.liveParity} id=${live.liveId}`,
    },
  };
}

/**
 * @param {Record<string, unknown>|null|undefined} healthPayload /api/v3/hardware/health
 * @param {string} moduleRole e.g. modbus-adc | modbus-io
 */
export function pluginHealthEntry(healthPayload, moduleRole) {
  const role = String(moduleRole || "").trim().toLowerCase();
  if (!role || !healthPayload || typeof healthPayload !== "object") return null;
  const direct = healthPayload[role];
  if (direct && typeof direct === "object") return direct;
  const plugins = healthPayload.plugins;
  if (plugins && typeof plugins === "object" && plugins[role]) {
    return plugins[role];
  }
  return null;
}

export function isPluginHealthOk(entry) {
  if (!entry || typeof entry !== "object") return false;
  if (entry.compatible === true) return true;
  const status = String(entry.status || "").toLowerCase();
  return HEALTHY_STATUSES.has(status);
}

/**
 * Loose port compare: by-path / by-id / ttyUSB* may all be the same device.
 * Empty live port does not block skip when health is otherwise OK.
 */
export function portsLooselyMatch(expected, live) {
  const a = String(expected || "").trim();
  const b = String(live || "").trim();
  if (!a || !b) return true;
  if (a === b) return true;
  const base = (p) => p.split("/").pop() || p;
  return base(a) === base(b);
}

/**
 * Fully commissioned = healthy AND live UART matches program_target
 * (id + baud + parity). If live is baseline 9600 and target is higher,
 * do NOT skip — wizard must raise baud.
 *
 * @returns {{ skip: boolean, reason?: string, details?: Record<string, unknown> }}
 */
export function evaluateConfigureSkip({
  programTarget = {},
  stepSerialPort = "",
  healthPayload = null,
} = {}) {
  const role = String(programTarget.module_role || "").trim().toLowerCase();
  if (!role.startsWith("modbus-")) return skipDecision("not-modbus-configure");
  const entry = pluginHealthEntry(healthPayload, role);
  if (!isPluginHealthOk(entry)) return skipDecision("plugin-not-healthy");
  const live = uartDetails(entry);
  const stepPort = String(stepSerialPort || programTarget.serial_port || "").trim();
  const { liveBaud, liveId, liveParity, livePort } = live;
  if (stepPort && livePort && !portsLooselyMatch(stepPort, livePort)) {
    return skipDecision("port-mismatch", { stepPort, livePort });
  }
  const targetId = programTarget.new_device_id;
  if (targetId != null && liveId != null && Number(targetId) !== Number(liveId)) {
    return skipDecision("device-id-mismatch", { targetId, liveId });
  }

  const targetBaud = programTarget.new_baudrate != null
    ? Number(programTarget.new_baudrate)
    : null;
  const targetParity = String(programTarget.new_parity || "N").toUpperCase();
  // Commissioning incomplete: healthy at baseline but plan wants higher speed.
  const baudDecision = baudRampDecision(role, liveBaud, targetBaud);
  if (baudDecision) return baudDecision;

  if (liveParity && targetParity && liveParity !== targetParity) {
    return skipDecision("parity-mismatch", { liveParity, targetParity });
  }
  return alreadyConfiguredDecision(role, entry, live);
}
