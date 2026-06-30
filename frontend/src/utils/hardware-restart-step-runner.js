import {
  executeConfigureStep,
  executeDiagnosticStep,
  executeFinalDiagnoseStep,
  executePeripheralStatusStep,
} from "./hardware-restart-wizard-steps.js";

export { buildStepError } from "./hardware-restart-step-errors.js";
export { resolveStepAdvance } from "./hardware-restart-step-outcome.js";

export async function runWizardStep(ctx) {
  const { currentStep } = ctx;
  if (currentStep.step.startsWith("configure-")) {
    return executeConfigureStep(ctx);
  }
  if (currentStep.action?.type === "diagnostic") {
    return executeDiagnosticStep(ctx);
  }
  if (currentStep.action?.type === "peripheral-status") {
    return executePeripheralStatusStep(ctx);
  }
  return executeFinalDiagnoseStep(ctx);
}
