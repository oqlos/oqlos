import { TIC249_TARGET_VELOCITY_SCALE } from "../pages/mapEditorConstants.js";

export function tic249RawTargetVelocity(stepsPerSecond) {
  const value = Number(stepsPerSecond);
  if (!Number.isFinite(value) || value <= 0) return "—";
  return Math.round(value * TIC249_TARGET_VELOCITY_SCALE).toLocaleString("en-US");
}
