/**
 * Short label for FUNC sequence steps → resolved peripheral/command from MAP bindings.
 */
export function summarizeFuncToHardware(cfg, mapData) {
  const md = mapData && typeof mapData === "object" ? mapData : {};
  const objectActionMap =
    md.objectActionMap && typeof md.objectActionMap === "object" ? md.objectActionMap : {};
  const actions = md.actions && typeof md.actions === "object" ? md.actions : {};

  if (!cfg || typeof cfg !== "object") return "";
  if (cfg.kind === "sequence" && Array.isArray(cfg.steps)) {
    const hints = [];
    for (const step of cfg.steps) {
      if (!step || typeof step !== "object") continue;
      const objName = step.object;
      const actName = step.action;

      if (objName && objectActionMap[objName]) {
        const om = objectActionMap[objName];
        for (const label of Object.keys(om)) {
          const b = om[label];
          if (b && typeof b === "object" && b.kind === "api") {
            const cmd = b.body?.command ?? "";
            const peri = b.body?.peripheral_id ?? "";
            hints.push(peri && cmd ? `${peri}:${cmd}` : cmd || peri || label);
            break;
          }
        }
      } else if (actName && actions[actName]) {
        const b = actions[actName];
        if (b && typeof b === "object" && b.kind === "api") {
          const cmd = b.body?.command ?? "";
          const peri = b.body?.peripheral_id ?? "";
          hints.push(peri && cmd ? `${peri}:${cmd}` : cmd || peri || actName);
        } else if (b?.url) {
          hints.push(String(b.url).replace(/^.*\//, "").slice(0, 36));
        }
      }
    }
    const seen = new Set();
    const uniq = [];
    for (const h of hints) {
      if (!h || seen.has(h)) continue;
      seen.add(h);
      uniq.push(h);
    }
    return uniq.slice(0, 5).join(" · ");
  }
  return cfg.kind ? String(cfg.kind) : "";
}
