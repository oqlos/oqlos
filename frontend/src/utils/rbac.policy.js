export const CONNECT_CONTEXT_QUERY_KEYS = ["font", "theme", "role", "lang", "size", "sidebar"];

export const CONNECT_SUPPORTED_ROLES = [
  "admin",
  "manager",
  "technician",
  "operator",
  "viewer",
  "guest",
];

const ROLE_ALIASES = {
  admin: "admin",
  administrator: "admin",
  manager: "manager",
  technician: "technician",
  technik: "technician",
  operator: "operator",
  viewer: "viewer",
  przegladajacy: "viewer",
  "przeglądający": "viewer",
  guest: "guest",
};

export function parseConnectRole(raw) {
  const key = String(raw || "").trim().toLowerCase();
  return ROLE_ALIASES[key] || null;
}

export function normalizeConnectRole(raw, fallback = "operator") {
  return parseConnectRole(raw) || fallback;
}

export function normalizeHostRole(raw, fallback = "operator") {
  const normalized = normalizeConnectRole(raw, fallback);
  return normalized === "guest" ? "viewer" : normalized;
}

export function isReadOnlyConnectRole(raw) {
  const role = normalizeConnectRole(raw, "viewer");
  return role === "viewer" || role === "guest";
}

export function isOperatorConnectRole(raw) {
  const role = normalizeConnectRole(raw, "viewer");
  return role === "admin" || role === "manager" || role === "technician" || role === "operator";
}

export function isAdminConnectRole(raw) {
  return normalizeConnectRole(raw, "viewer") === "admin";
}

const VIEW_ROLE_BINDINGS = [
  { pattern: "/connect-config*", roles: ["admin", "manager"] },
  { pattern: "/connect-menu-editor*", roles: ["admin", "manager"] },
  { pattern: "/connect-menu-tree*", roles: ["admin", "manager"] },
  { pattern: "/connect-devtools*", roles: ["admin", "manager"] },
  { pattern: "/connect-router*", roles: ["admin", "manager"] },
  { pattern: "/connect-manager*", roles: ["admin", "manager", "technician"] },
  { pattern: "/connect-reports*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/connect-workshop*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/connect-data*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/connect-id*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/connect-test*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/connect-live-protocol*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/connect-scenario*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/scenario-files*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/status*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/hardware-status*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/hardware-modbus*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/hardware-rtc*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/ui/hardware-modbus*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/ui/hardware-rtc*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/hardware-restart*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/hardware-demo*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/map-editor*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/func-editor*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/motor-services*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/panel*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/ui/panel*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/navigation*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/ui/status*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/docs*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/api-docs*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/templates*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
  { pattern: "/operator-parameters*", roles: ["admin", "manager", "technician", "operator", "viewer"] },
];

function normalizePath(path) {
  const raw = String(path || "").trim();
  if (!raw) return "/";
  try {
    const url = new URL(raw, "http://localhost");
    return url.pathname || "/";
  } catch {
    return raw.startsWith("/") ? raw : `/${raw}`;
  }
}

function matchesPattern(path, pattern) {
  if (pattern.endsWith("*")) {
    const prefix = pattern.slice(0, -1);
    return path === prefix || path.startsWith(prefix);
  }
  return path === pattern;
}

export function resolveAllowedRolesForPath(path) {
  const normalizedPath = normalizePath(path);
  let matched = null;
  for (const binding of VIEW_ROLE_BINDINGS) {
    if (!matchesPattern(normalizedPath, binding.pattern)) continue;
    if (!matched || binding.pattern.length > matched.pattern.length) {
      matched = binding;
    }
  }
  return matched ? matched.roles : null;
}

export function canConnectRoleAccessPath(path, role) {
  const allowed = resolveAllowedRolesForPath(path);
  if (!allowed) return true;
  return allowed.includes(normalizeConnectRole(role));
}

export function canHostRoleAccessPath(path, role) {
  const allowed = resolveAllowedRolesForPath(path);
  if (!allowed) return true;
  return allowed.includes(normalizeHostRole(role));
}
