/** Hardware Demo mount-time identify + pump probe (extracted from HardwareDemo.jsx). */

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
  const next = {};
  for (const id of deviceIds) {
    const adapter = adapters.find((entry) => entry.id === id);
    next[id] = adapter?.status || "unknown";
  }

  let pumpOk = next["motor-dri0050"] === "ok";
  const stepperOk = next["motor-tic249"] === "ok";

  if (pumpOk) {
    try {
      await runDiagnosticCommand({
        peripheral_id: "motor-dri0050",
        command: "pump_off",
        args: {},
      });
    } catch (err) {
      pumpOk = false;
      next["motor-dri0050"] = "probe-failed";
      appendLog("warn", t("hardwareDemo.log.pumpProbeFailed"), formatError(err));
    }
  }

  if (signal?.aborted) return null;

  appendLog(
    pumpOk ? "ok" : "warn",
    t("hardwareDemo.log.pumpStatusLine", {
      pump: next["motor-dri0050"],
      stepper: next["motor-tic249"],
    }),
    pumpOk
      ? t("hardwareDemo.log.pumpConnectedDetail")
      : stepperOk
        ? t("hardwareDemo.log.pumpFallbackDetail")
        : t("hardwareDemo.log.neitherDeviceDetail"),
  );

  return {
    deviceStatus: { ...next },
    fallbackDeviceId: !pumpOk && stepperOk ? "motor-tic249" : null,
  };
}
