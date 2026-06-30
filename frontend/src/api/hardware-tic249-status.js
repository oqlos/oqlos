const TIC249_DEENERGIZE_COMMANDS = new Set(["motor_disable", "deenergize", "disable", "standby"]);

export function tic249ResultStatus(result) {
  if (!result || typeof result !== "object") {
    return "";
  }
  const data = result.data && typeof result.data === "object" ? result.data : null;
  return String(result.status || data?.status || "").toLowerCase();
}

export function isIdempotentTic249Deenergized(command, result) {
  if (!TIC249_DEENERGIZE_COMMANDS.has(command)) {
    return false;
  }
  if (result?.idempotent_success) {
    return true;
  }
  const status = tic249ResultStatus(result);
  if (status === "de-energized" || status === "disabled") {
    return !result?.error;
  }
  const data = result?.data;
  if (data && typeof data === "object" && data.energized === false && !data.error) {
    return true;
  }
  return false;
}

export function isIdempotentDiagnosticSuccess(command, result) {
  const status = tic249ResultStatus(result);
  return (
    isIdempotentTic249Deenergized(command, result) ||
    (command === "lung_stop" && status === "stopped")
  );
}
