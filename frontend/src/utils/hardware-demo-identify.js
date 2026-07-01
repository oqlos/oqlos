/** Hardware Demo mount-time identify + pump probe (extracted from HardwareDemo.jsx). */

const PUMP_DEVICE_ID = "motor-dri0050";
const STEPPER_DEVICE_ID = "motor-tic249";

/** Build a status map for each requested device id from the adapter list. */
function buildDeviceStatus(adapters, deviceIds) {
  const next = {};
  for (const id of deviceIds) {
    const adapter = adapters.find((entry) => entry.id === id);
    next[id] = adapter?.status || "unknown";
  }
  return next;
}

/** Send a pump_off command to verify the pump is actually reachable. */
async function probePump({ runDiagnosticCommand, formatError, appendLog, t }) {
  try {
    await runDiagnosticCommand({
      peripheral_id: PUMP_DEVICE_ID,
      command: "pump_off",
      args: {},
    });
    return true;
  } catch (err) {
    appendLog("warn", t("hardwareDemo.log.pumpProbeFailed"), formatError(err));
    return false;
  }
}

/** Resolve the human-readable detail line based on device availability. */
function buildStatusDetail(pumpOk, stepperOk, t) {
  if (pumpOk) return t("hardwareDemo.log.pumpConnectedDetail");
  if (stepperOk) return t("hardwareDemo.log.pumpFallbackDetail");
  return t("hardwareDemo.log.neitherDeviceDetail");
}

/** Determine which device (if any) should be used as fallback. */
function resolveFallbackDeviceId(pumpOk, stepperOk) {
  if (!pumpOk && stepperOk) return STEPPER_DEVICE_ID;
  return null;
}

export async function probeDemoDevices({
  identify,
  runDiagnosticCommand,
  deviceIds,
  formatError,
  appendLog,
  t,
  signal,
}) {
  const res = await identify();
  if (signal?.aborted) return null;

  const adapters = res?.adapters || [];
  const next = buildDeviceStatus(adapters, deviceIds);

  let pumpOk = next[PUMP_DEVICE_ID] === "ok";
  const stepperOk = next[STEPPER_DEVICE_ID] === "ok";

  if (pumpOk) {
    const probeOk = await probePump({ runDiagnosticCommand, formatError, appendLog, t });
    if (!probeOk) {
      pumpOk = false;
      next[PUMP_DEVICE_ID] = "probe-failed";
    }
  }

  if (signal?.aborted) return null;

  appendLog(
    pumpOk ? "ok" : "warn",
    t("hardwareDemo.log.pumpStatusLine", {
      pump: next[PUMP_DEVICE_ID],
      stepper: next[STEPPER_DEVICE_ID],
    }),
    buildStatusDetail(pumpOk, stepperOk, t),
  );

  return {
    deviceStatus: { ...next },
    fallbackDeviceId: resolveFallbackDeviceId(pumpOk, stepperOk),
  };
}
