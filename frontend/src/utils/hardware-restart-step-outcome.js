import { isOptionalWizardStep } from "./hardware-wizard-steps.js";

export function resolveStepAdvance(ok, currentStep) {
  if (!ok && isOptionalWizardStep(currentStep)) return { advanceOk: true, optionalSkip: true };
  return { advanceOk: ok, optionalSkip: false };
}
