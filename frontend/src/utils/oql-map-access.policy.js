/**
 * OQL hardware MAP edit scopes — mirrors @semcod/ts-utils oql-map-access.policy.
 * Keep in sync with packages/ts-utils/src/oql-map-access.policy.ts
 */

export const OQL_EDIT_PERSONAS = ["system", "administrator", "operator"];

export const OQL_MAP_BODY_SECTIONS = [
  "runtimeConfig",
  "objectActionMap",
  "paramSensorMap",
  "actions",
  "funcImplementations",
  "operatorVariables",
];

export const OQL_MAP_SECTION_OWNERS = {
  runtimeConfig: "system",
  actions: "system",
  objectActionMap: "administrator",
  funcImplementations: "administrator",
  paramSensorMap: "operator",
  operatorVariables: "operator",
};

const PERSONA_RANK = { system: 3, administrator: 2, operator: 1 };

const CONNECT_ROLE_TO_PERSONA = {
  system: "system",
  sys: "system",
  root: "system",
  admin: "administrator",
  administrator: "administrator",
  manager: "administrator",
  technician: "administrator",
  operator: "operator",
  viewer: "operator",
  guest: "operator",
};

export function normalizeOqlEditPersona(raw) {
  const value = String(raw || "").trim().toLowerCase();
  if (!value) return null;
  if (OQL_EDIT_PERSONAS.includes(value)) return value;
  return CONNECT_ROLE_TO_PERSONA[value] || null;
}

export function personaFromConnectRole(role) {
  return normalizeOqlEditPersona(role) || "operator";
}

export function isOqlMapWriteRole(role) {
  const r = String(role || "").trim().toLowerCase();
  if (r === "viewer" || r === "guest") return false;
  return true;
}

export function sectionsOwnedBy(persona) {
  return OQL_MAP_BODY_SECTIONS.filter((s) => OQL_MAP_SECTION_OWNERS[s] === persona);
}

export function sectionsWritableBy(persona) {
  const p = normalizeOqlEditPersona(persona) || "operator";
  const rank = PERSONA_RANK[p] || 0;
  return OQL_MAP_BODY_SECTIONS.filter((s) => (PERSONA_RANK[OQL_MAP_SECTION_OWNERS[s]] || 0) <= rank);
}

export function canEditOqlMapSection(roleOrPersona, section) {
  if (!isOqlMapWriteRole(roleOrPersona)) return false;
  const persona = normalizeOqlEditPersona(roleOrPersona) || personaFromConnectRole(roleOrPersona);
  return sectionsWritableBy(persona).includes(section);
}

export const OQL_MAP_TAB_SECTIONS = {
  funcs: ["funcImplementations"],
  objects: ["objectActionMap"],
  params: ["paramSensorMap", "operatorVariables"],
  actions: ["actions"],
  runtime: ["runtimeConfig"],
  json: [...OQL_MAP_BODY_SECTIONS],
};

export function canEditOqlMapTab(roleOrPersona, tab) {
  const sections = OQL_MAP_TAB_SECTIONS[tab];
  if (!sections) return isOqlMapWriteRole(roleOrPersona);
  if (tab === "json") {
    const p = normalizeOqlEditPersona(roleOrPersona) || personaFromConnectRole(roleOrPersona);
    return p === "system" || String(roleOrPersona || "").toLowerCase() === "admin"
      || String(roleOrPersona || "").toLowerCase() === "administrator";
  }
  return sections.every((s) => canEditOqlMapSection(roleOrPersona, s));
}

export function diffChangedMapSections(original, current) {
  const changed = {};
  for (const section of OQL_MAP_BODY_SECTIONS) {
    const a = original?.[section] ?? {};
    const b = current?.[section] ?? {};
    if (JSON.stringify(a) !== JSON.stringify(b)) {
      changed[section] = b;
    }
  }
  return changed;
}

export const OQL_MAP_ACCESS_HEADERS = {
  persona: "X-Oql-Edit-Persona",
  role: "X-Connect-Role",
};
