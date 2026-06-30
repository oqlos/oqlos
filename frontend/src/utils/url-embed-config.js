import { CONNECT_SUPPORTED_ROLES, normalizeConnectRole } from "./rbac.policy.js";
import { isValidShellHuiKey, SHELL_HUI_KEY_PARAM } from "./hui-shell-key.js";

// Canonical iframe-embed params when hosted inside maskservice /connect-scenario.
export const SUPPORTED_THEMES = ["dark", "light", "high-contrast"];
export const SUPPORTED_FONTS = ["default", "mono", "dyslexic", "large", "xlarge"];
export const SUPPORTED_ROLES = [...CONNECT_SUPPORTED_ROLES];
export const SUPPORTED_LANGS_ENUM = ["pl", "en", "de", "ru", "ua", "cs"];

export const APP_CONFIG_DEFAULTS = Object.freeze({
  font: "default",
  theme: "dark",
  role: "admin",
  user: "",
  lang: "pl",
  size: 1280,
  scenario: "",
  scenarioByFilename: "",
  device: "",
  deviceName: "",
  test: "",
  key: "",
  iframeChild: false,
});

/** @param {URLSearchParams} params */
export function resolveUserIdFromSearchParams(params) {
  for (const key of ["user", "user_id", "userId", "operator_id"]) {
    const value = (params.get(key) || "").trim();
    if (value) return value;
  }
  return "";
}

/** @param {string|{username?: string, user_id?: string, id?: string, role?: string}|null|undefined} raw */
export function resolveUserFromContextPayload(raw) {
  if (typeof raw === "string") {
    return { userId: raw.trim(), role: "" };
  }
  if (!raw || typeof raw !== "object") return { userId: "", role: "" };
  const userId = String(raw.username || raw.user_id || raw.id || "").trim();
  const role = typeof raw.role === "string" ? raw.role.trim() : "";
  return { userId, role };
}

/** Map URL / parent.context `size` to pixels for `--viewport-size`. */
export function resolveViewportWidthPx(raw) {
  if (raw == null || raw === "") return null;
  const n = typeof raw === "number" ? raw : Number(String(raw).trim());
  if (!Number.isFinite(n)) return null;
  if (n === 100) {
    const w =
      typeof globalThis !== "undefined" && globalThis.window
        ? Number(globalThis.window.innerWidth || 0)
        : 0;
    if (w >= 320) return Math.min(4096, Math.max(960, w));
    return 1920;
  }
  if (n >= 320 && n <= 4096) return n;
  return null;
}

function parseAppearanceParams(params, out) {
  const font = (params.get("font") || "").trim();
  if (font && SUPPORTED_FONTS.includes(font)) out.font = font;
  const theme = params.get("theme");
  if (theme && SUPPORTED_THEMES.includes(theme)) out.theme = theme;
  const lang = params.get("lang");
  if (lang && SUPPORTED_LANGS_ENUM.includes(lang)) out.lang = lang;
  const resolved = resolveViewportWidthPx(params.get("size"));
  if (resolved != null) out.size = resolved;
}

function parseIdentityParams(params, out) {
  const role = params.get("role");
  if (role) out.role = normalizeConnectRole(role, out.role);
  const userId = resolveUserIdFromSearchParams(params);
  if (userId) out.user = userId;
  out.iframeChild = ["1", "true", "yes", "on"].includes(
    (params.get("iframe_child") || "").trim().toLowerCase(),
  );
}

function parseNavigationParams(params, out) {
  const scenario = params.get("scenario") || params.get("scenario_id");
  if (scenario) out.scenario = scenario.trim();
  const scenarioByFilename = params.get("scenario-by-filename");
  if (scenarioByFilename) out.scenarioByFilename = scenarioByFilename.trim();
  const device = params.get("device");
  if (device) out.device = device.trim();
  const deviceName = params.get("device_name");
  if (deviceName) out.deviceName = deviceName.trim();
  const test = params.get("test");
  if (test) out.test = test.trim();
  const key = (params.get(SHELL_HUI_KEY_PARAM) || "").trim();
  if (key && isValidShellHuiKey(key)) out.key = key;
}

export function parseUrlEmbedConfig(search) {
  const params = new URLSearchParams(search);
  const out = { ...APP_CONFIG_DEFAULTS };
  parseAppearanceParams(params, out);
  parseIdentityParams(params, out);
  parseNavigationParams(params, out);
  return out;
}

function pickSupportedString(incoming, supported, fallback) {
  const value = typeof incoming === "string" ? incoming.trim() : "";
  return value && supported.includes(value) ? value : fallback;
}

export function mergeParentContext(prev, ctx) {
  if (!ctx || typeof ctx !== "object") return prev;
  const fromUser = resolveUserFromContextPayload(ctx.user);
  const roleCandidate = typeof ctx.role === "string" ? ctx.role : fromUser.role;
  return {
    ...prev,
    theme: pickSupportedString(ctx.theme, SUPPORTED_THEMES, prev.theme),
    font: pickSupportedString(ctx.font, SUPPORTED_FONTS, prev.font),
    lang: pickSupportedString(ctx.locale ?? ctx.lang, SUPPORTED_LANGS_ENUM, prev.lang),
    role: normalizeConnectRole(roleCandidate, prev.role),
    user: fromUser.userId || prev.user,
    size: resolveViewportWidthPx(ctx.size) ?? prev.size,
  };
}

const IFRAME_ONLY_SEARCH_PARAMS = new Set(["iframe_child", "parent_origin"]);

export function mergeParentSearchIntoChildUrl(currentHref, parentSearch, baseOrigin = "http://localhost") {
  const url = /^https?:\/\//i.test(String(currentHref || ""))
    ? new URL(currentHref)
    : new URL(currentHref, baseOrigin);
  const raw = String(parentSearch || "").trim();
  const incoming = new URLSearchParams(raw.startsWith("?") ? raw.slice(1) : raw);
  for (const key of IFRAME_ONLY_SEARCH_PARAMS) {
    const kept = url.searchParams.get(key);
    if (kept && !incoming.has(key)) incoming.set(key, kept);
  }
  url.search = "";
  incoming.forEach((value, key) => url.searchParams.set(key, value));
  return `${url.pathname}${url.search}`;
}

export function applyParentContextPayload(prev, ctx, currentHref) {
  const search = typeof ctx?.search === "string" ? ctx.search.trim() : "";
  let base = prev;
  if (search && currentHref) {
    const href = mergeParentSearchIntoChildUrl(currentHref, search);
    base = parseUrlEmbedConfig(new URL(href, "http://localhost").search);
  }
  return mergeParentContext(base, ctx);
}

/**
 * Apply parent.context envelope to current location.
 * @returns {{ config: object, nextHref?: string, currentHref?: string }}
 */
export function resolveParentContextUpdate(prev, ctx, locationLike) {
  const href = locationLike?.href || "";
  const pathname = locationLike?.pathname || "";
  const search = locationLike?.search || "";
  const parentSearch = typeof ctx?.search === "string" ? ctx.search.trim() : "";
  if (parentSearch && href) {
    try {
      const nextHref = mergeParentSearchIntoChildUrl(href, parentSearch);
      return {
        nextHref,
        currentHref: `${pathname}${search}`,
        config: applyParentContextPayload(prev, ctx, nextHref),
      };
    } catch {
      return { config: mergeParentContext(prev, ctx) };
    }
  }
  return { config: mergeParentContext(prev, ctx) };
}

export function applyUrlEmbedPatch(currentHref, partial) {
  const url = new URL(currentHref);
  Object.entries(partial).forEach(([key, value]) => {
    const param = key === "key" ? SHELL_HUI_KEY_PARAM : key;
    if (value === null || value === undefined || value === "") {
      url.searchParams.delete(param);
    } else if (key === "key" && !isValidShellHuiKey(String(value))) {
      url.searchParams.delete(param);
    } else {
      url.searchParams.set(param, String(value));
    }
  });
  const nextPath = `${url.pathname}${url.search}`;
  return { nextPath, config: parseUrlEmbedConfig(url.search) };
}
