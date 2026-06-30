/** Pure mutations for objectActionMap editor prompts (MapEditor). */

export function parsePromptedFieldValue(value, type = "text") {
  if (value === null || value === undefined) return null;
  if (type === "number") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return String(value).trim();
}

export function syncMoveRelativeArgs(binding, actionName) {
  if (!binding?.body || binding.body.command !== "move_relative") return;
  if (!binding.args || typeof binding.args !== "object") binding.args = {};
  const direction = String(binding.args.direction || actionName || "").toLowerCase();
  const steps = Math.abs(Number(binding.args.steps ?? binding.args.offset ?? 0));
  if (!Number.isFinite(steps) || steps <= 0) return;
  binding.args.steps = steps;
  binding.args.offset = direction === "left" ? -steps : steps;
}

export function applyObjectActionArgMutation(
  next,
  { objectName, actionName, argName, value, type = "text" },
) {
  const parsed = parsePromptedFieldValue(value, type);
  if (parsed === null) return false;
  const binding = next.objectActionMap?.[objectName]?.[actionName];
  if (!binding || typeof binding !== "object") return false;
  if (!binding.args || typeof binding.args !== "object") binding.args = {};
  binding.args[argName] = parsed;
  syncMoveRelativeArgs(binding, actionName);
  return true;
}

export function applyObjectActionBodyFieldMutation(next, { objectName, actionName, field, value }) {
  const parsed = parsePromptedFieldValue(value, "text");
  if (parsed === null) return false;
  const binding = next.objectActionMap?.[objectName]?.[actionName];
  if (!binding || typeof binding !== "object") return false;
  if (!binding.body || typeof binding.body !== "object") binding.body = {};
  binding.body[field] = parsed;
  return true;
}
