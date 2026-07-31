export function runtimeControlTranslationKey(status) {
  if (status?.runtime_control_available) {
    return "hardwareRestart.runtimeAvailable";
  }
  if (status?.transport === "direct-oqlos") {
    return "hardwareRestart.runtimeDirect";
  }
  return "hardwareRestart.runtimeUnavailable";
}
