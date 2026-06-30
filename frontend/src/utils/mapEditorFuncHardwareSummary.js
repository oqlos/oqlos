/**
 * Short label for FUNC sequence steps → resolved peripheral/command from MAP bindings.
 */

function apiBindingHint(binding, fallbackLabel) {
  if (!binding || typeof binding !== "object" || binding.kind !== "api") {
    return "";
  }
  const cmd = binding.body?.command ?? "";
  const peri = binding.body?.peripheral_id ?? "";
  return peri && cmd ? `${peri}:${cmd}` : cmd || peri || fallbackLabel;
}

export function resolveObjectActionHardwareHint(objName, objectActionMap) {
  if (!objName || !objectActionMap?.[objName]) {
    return "";
  }
  const objectMap = objectActionMap[objName];
  for (const label of Object.keys(objectMap)) {
    const hint = apiBindingHint(objectMap[label], label);
    if (hint) {
      return hint;
    }
  }
  return "";
}

export function resolveNamedActionHardwareHint(actName, actions) {
  if (!actName || !actions?.[actName]) {
    return "";
  }
  const binding = actions[actName];
  const apiHint = apiBindingHint(binding, actName);
  if (apiHint) {
    return apiHint;
  }
  if (binding?.url) {
    return String(binding.url).replace(/^.*\//, "").slice(0, 36);
  }
  return "";
}

function uniqueHints(hints, limit = 5) {
  const seen = new Set();
  const uniq = [];
  for (const hint of hints) {
    if (!hint || seen.has(hint)) continue;
    seen.add(hint);
    uniq.push(hint);
    if (uniq.length >= limit) break;
  }
  return uniq.join(" · ");
}

export function summarizeFuncToHardware(cfg, mapData) {
  const md = mapData && typeof mapData === "object" ? mapData : {};
  const objectActionMap =
    md.objectActionMap && typeof md.objectActionMap === "object" ? md.objectActionMap : {};
  const actions = md.actions && typeof md.actions === "object" ? md.actions : {};

  if (!cfg || typeof cfg !== "object") return "";
  if (cfg.kind !== "sequence" || !Array.isArray(cfg.steps)) {
    return cfg.kind ? String(cfg.kind) : "";
  }

  const hints = [];
  for (const step of cfg.steps) {
    if (!step || typeof step !== "object") continue;
    const fromObject = resolveObjectActionHardwareHint(step.object, objectActionMap);
    if (fromObject) {
      hints.push(fromObject);
      continue;
    }
    const fromAction = resolveNamedActionHardwareHint(step.action, actions);
    if (fromAction) {
      hints.push(fromAction);
    }
  }
  return uniqueHints(hints);
}
