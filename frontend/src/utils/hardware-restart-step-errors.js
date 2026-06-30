import { formatHardwareApiError } from "../api/hardwareApi.js";

export function buildStepError(err, currentStep) {
  const message = formatHardwareApiError(err, "Krok zakonczony bledem.");
  const commandResult = err?.commandResult ?? null;
  return {
    message,
    commandResult,
    payload: {
      step: currentStep,
      error: message,
      ...(commandResult ? { diagnostic: commandResult, commandResult } : {}),
    },
  };
}
