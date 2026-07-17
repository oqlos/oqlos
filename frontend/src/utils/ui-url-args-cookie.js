import { normalizeConnectRole } from "@semcod/ts-utils/rbac.policy";
import { MODBUS_PROFILE_IDS } from "./modbus-profiles.js";
import { RTC_MENU_IDS } from "./rtc-menu.js";
import {
  applyUrlEmbedPatch,
  resolveViewportWidthPx,
  sidebarCollapsedFromUrlParam,
  sidebarUrlFromCollapsed,
  SUPPORTED_FONTS,
  SUPPORTED_LANGS_ENUM,
  SUPPORTED_THEMES,
} from "./url-embed-config.js";

export const UI_URL_ARGS_COOKIE_NAME = "oqlos_ui_args";

/** Query keys restored on every /ui/* route (chrome + shared page args). */
export const UI_URL_ARGS_KEYS = [
  "font",
  "theme",
  "role",
  "lang",
  "size",
  "mode",
  "user",
  "sidebar",
  "submenu",
  "log",
];

const UI_URL_ARGS_KEY_SET = new Set(UI_URL_ARGS_KEYS);

function normalizePersistedValue(key, value) {
  if (value == null || value === "") return null;
  const token = String(value).trim();
  if (!token) return null;
  switch (key) {
    case "font":
      return SUPPORTED_FONTS.includes(token) ? token : null;
    case "theme":
      return SUPPORTED_THEMES.includes(token) ? token : null;
    case "lang":
      return SUPPORTED_LANGS_ENUM.includes(token) ? token : null;
    case "role": {
      const role = normalizeConnectRole(token, "");
      return role || null;
    }
    case "mode":
      return ["keyboard", "encoder", "scanner"].includes(token) ? token : null;
    case "sidebar": {
      const collapsed = sidebarCollapsedFromUrlParam(token);
      return collapsed === null ? null : sidebarUrlFromCollapsed(collapsed);
    }
    case "submenu":
      return MODBUS_PROFILE_IDS.includes(token) || RTC_MENU_IDS.includes(token) ? token : null;
    case "log":
      return /^(file:[\w.-]+\.log(?:\.\d+)?|journal:[\w@.-]+\.service)$/.test(token) ? token : null;
    case "size": {
      const resolved = resolveViewportWidthPx(token);
      return resolved == null ? null : String(resolved);
    }
    case "user":
      return token;
    default:
      return UI_URL_ARGS_KEY_SET.has(key) ? token : null;
  }
}

export function normalizeUiUrlArgsPatch(patch) {
  if (!patch || typeof patch !== "object") return {};
  const out = {};
  Object.entries(patch).forEach(([key, value]) => {
    if (!UI_URL_ARGS_KEY_SET.has(key)) return;
    if (value === null || value === undefined || value === "") {
      out[key] = null;
      return;
    }
    const normalized = normalizePersistedValue(key, value);
    if (normalized != null) out[key] = normalized;
  });
  return out;
}

export function readUiUrlArgsCookie(rawCookie = typeof document !== "undefined" ? document.cookie : "") {
  try {
    const source = String(rawCookie || "");
    const escaped = UI_URL_ARGS_COOKIE_NAME.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const match = source.match(new RegExp(`(?:^|; )${escaped}=([^;]*)`));
    if (!match) return {};
    const parsed = JSON.parse(decodeURIComponent(match[1]));
    if (!parsed || typeof parsed !== "object") return {};
    const out = {};
    UI_URL_ARGS_KEYS.forEach((key) => {
      const normalized = normalizePersistedValue(key, parsed[key]);
      if (normalized != null) out[key] = normalized;
    });
    return out;
  } catch {
    return {};
  }
}

export function persistUiUrlArgsToCookie(patch) {
  if (typeof document === "undefined") return;
  const normalized = normalizeUiUrlArgsPatch(patch);
  if (Object.keys(normalized).length === 0) return;
  const current = readUiUrlArgsCookie();
  const merged = { ...current };
  Object.entries(normalized).forEach(([key, value]) => {
    if (value === null) delete merged[key];
    else merged[key] = value;
  });
  try {
    const payload = encodeURIComponent(JSON.stringify(merged));
    document.cookie = `${UI_URL_ARGS_COOKIE_NAME}=${payload}; path=/; max-age=31536000; SameSite=Lax`;
  } catch { /* silent */ }
}

export function buildUrlPatchFromUiArgsCookie(search = "", cookie = readUiUrlArgsCookie()) {
  const params = new URLSearchParams(String(search || "").replace(/^\?/, ""));
  const patch = {};
  UI_URL_ARGS_KEYS.forEach((key) => {
    if (params.has(key)) return;
    const value = cookie[key];
    if (value != null && value !== "") patch[key] = value;
  });
  return patch;
}

/** Fill missing /ui query args from cookie. Explicit URL params win. */
export function hydrateUrlFromUiArgsCookie(locationLike = globalThis.location) {
  if (!locationLike?.href) return false;
  const patch = buildUrlPatchFromUiArgsCookie(locationLike.search || "");
  if (Object.keys(patch).length === 0) return false;
  const { nextPath } = applyUrlEmbedPatch(locationLike.href, patch);
  const current = `${locationLike.pathname || ""}${locationLike.search || ""}`;
  if (nextPath === current) return false;
  try {
    globalThis.history?.replaceState(null, "", nextPath);
  } catch {
    return false;
  }
  return true;
}

export function applyUrlEmbedPatchAndPersist(currentHref, partial) {
  const result = applyUrlEmbedPatch(currentHref, partial);
  persistUiUrlArgsToCookie(partial);
  return result;
}

/** Nav links: keep chrome/page args from URL, then fall back to cookie. */
export function preserveUiNavSearchParams(pathname, search = "", cookie = readUiUrlArgsCookie()) {
  const params = new URLSearchParams(String(search || "").replace(/^\?/, ""));
  const kept = new URLSearchParams();
  UI_URL_ARGS_KEYS.forEach((key) => {
    const value = params.get(key) || cookie[key];
    if (value) kept.set(key, value);
  });
  const query = kept.toString();
  return query ? `${pathname}?${query}` : pathname;
}

const LEGACY_UI_PAGE_PATHS = {
  "/ui/navigation": "/ui/status",
  "/ui/hardware-status": "/ui/status",
};

/** Map legacy UI paths to canonical routes after navigation/status merge. */
export function normalizeUiPagePath(path) {
  const normalized = String(path || "/");
  return LEGACY_UI_PAGE_PATHS[normalized] || normalized;
}

/** Collapse legacy navigation entries that resolve to the same canonical page. */
export function dedupeNavigationPages(pages) {
  const seen = new Set();
  return (pages || []).reduce((acc, page) => {
    const path = normalizeUiPagePath(page.path);
    if (seen.has(path)) return acc;
    seen.add(path);
    acc.push({ ...page, path });
    return acc;
  }, []);
}

/** Absolute /ui/... href with chrome args preserved (for plain <a> tags). */
export function uiPageHref(path, search = globalThis.location?.search ?? "", cookie = readUiUrlArgsCookie()) {
  const canonical = normalizeUiPagePath(path);
  const route = String(canonical || "/").startsWith("/ui")
    ? String(canonical).slice(3) || "/"
    : String(canonical || "/");
  return `/ui${preserveUiNavSearchParams(route, search, cookie)}`;
}
