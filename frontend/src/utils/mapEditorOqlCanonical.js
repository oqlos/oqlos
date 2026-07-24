/**
 * Slice 3 — MAP sections that now live in OQL (connect-oql-system / oql-store).
 * Map-editor stays as a read-only browser of residual MAP + migration guide.
 *
 * Unlock emergency legacy writes: ?legacy_edit=1 with system/admin role.
 */

import { normalizeOqlEditPersona, personaFromConnectRole } from "./oql-map-access.policy.js";

/** @type {Record<string, { fileId: string, slice: string, section: string }>} */
export const OQL_CANONICAL_TABS = Object.freeze({
  funcs: {
    section: "funcImplementations",
    fileId: "layers/system/map-func-catalog",
    slice: "2a",
  },
  objects: {
    section: "objectActionMap",
    fileId: "layers/system/map-object-actions",
    slice: "2b",
  },
  params: {
    section: "paramSensorMap",
    fileId: "layers/system/map-param-sensors",
    slice: "2c",
  },
  actions: {
    section: "actions",
    fileId: "layers/hardware/hui-profiles",
    slice: "1",
  },
});

export const OQL_CANONICAL_SECTIONS = Object.freeze(
  Object.values(OQL_CANONICAL_TABS).map((entry) => entry.section).concat(["runtimeConfig"])
);

export const OQL_CANONICAL_MOTOR2 = Object.freeze({
  section: "runtimeConfig",
  fileId: "layers/hardware/motor2-runtime",
  slice: "2d",
});

const CONNECT_OQL_BASE =
  typeof globalThis !== "undefined" && globalThis.location?.hostname
    ? `${globalThis.location.protocol}//${globalThis.location.hostname}:8100`
    : "http://localhost:8100";

const OQL_STORE_BASE =
  typeof globalThis !== "undefined" && globalThis.location?.hostname
    ? `${globalThis.location.protocol}//${globalThis.location.hostname}:8123`
    : "http://127.0.0.1:8123";

export function isMapEditorLegacyEditEnabled() {
  try {
    return new URLSearchParams(globalThis.location?.search || "").get("legacy_edit") === "1";
  } catch {
    return false;
  }
}

export function isOqlCanonicalTab(tab) {
  return Object.prototype.hasOwnProperty.call(OQL_CANONICAL_TABS, tab);
}

/**
 * Whether the map-editor may mutate a tab after OQL migration (slice 3).
 * @param {string} tab
 * @param {string} roleOrPersona
 * @param {boolean} baseCanEdit — role policy result before canonical lock
 */
export function canMutateMapEditorTab(tab, roleOrPersona, baseCanEdit) {
  if (!baseCanEdit) return false;
  if (!isOqlCanonicalTab(tab)) return true;
  if (!isMapEditorLegacyEditEnabled()) return false;
  const persona = normalizeOqlEditPersona(roleOrPersona) || personaFromConnectRole(roleOrPersona);
  return persona === "system" || persona === "administrator";
}

export function connectOqlSystemUrl(fileId) {
  const encoded = String(fileId || "")
    .split("/")
    .map(encodeURIComponent)
    .join("%2F");
  return `${CONNECT_OQL_BASE}/connect-oql-system?role=system&file=${encoded}`;
}

export function oqlStoreFileUrl(fileId) {
  const path = String(fileId || "")
    .split("/")
    .map(encodeURIComponent)
    .join("/");
  return `${OQL_STORE_BASE}/api/v1/files/${path}`;
}

export function canonicalInfoForTab(tab) {
  return OQL_CANONICAL_TABS[tab] || null;
}

/**
 * Sections that must not be persisted from map-editor without legacy_edit.
 * @param {string[]} sectionNames
 */
export function filterForbiddenCanonicalSections(sectionNames, roleOrPersona) {
  if (isMapEditorLegacyEditEnabled()) {
    const persona = normalizeOqlEditPersona(roleOrPersona) || personaFromConnectRole(roleOrPersona);
    if (persona === "system" || persona === "administrator") return [];
  }
  return (sectionNames || []).filter((s) => OQL_CANONICAL_SECTIONS.includes(s));
}
