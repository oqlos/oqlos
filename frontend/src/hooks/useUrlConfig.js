import { useEffect, useMemo, useState, useCallback } from "react";
import { CONNECT_SUPPORTED_ROLES, normalizeConnectRole } from "../utils/rbac.policy.js";
import { bridgeSearchToParent } from "../utils/parentUrlBridge.js";
import { isValidShellHuiKey, SHELL_HUI_KEY_PARAM } from "../utils/hui-shell-key.js";

// Canonical set of iframe-embed params read from the URL when cql is hosted
// inside maskservice at /connect-scenario/scenarios.
// Example:
//   ?font=default&theme=dark&role=operator&lang=pl&user=operator@fleet.local&size=1280&scenario=ts-c20
//
// `size` controls CSS `--viewport-size` (max content width in px). The host
// shell often passes `size=100` meaning **100% width / responsive**, not 100px —
// see `resolveViewportWidthPx`.
export const SUPPORTED_THEMES = ["dark", "light", "high-contrast"];
// `font` values mirror maskservice shell (ConnectFont): default | large | xlarge,
// plus connect-scenario-specific faces mono | dyslexic.
export const SUPPORTED_FONTS = ["default", "mono", "dyslexic", "large", "xlarge"];
export const SUPPORTED_ROLES = [...CONNECT_SUPPORTED_ROLES];
export const SUPPORTED_LANGS_ENUM = ["pl", "en", "de", "ru", "ua", "cs"];

const DEFAULTS = Object.freeze({
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

/**
 * @param {string|{username?: string, user_id?: string, id?: string, role?: string}|null|undefined} raw
 * @returns {{ userId: string, role: string }}
 */
export function resolveUserFromContextPayload(raw) {
  if (typeof raw === "string") {
    const userId = raw.trim();
    return { userId, role: "" };
  }
  if (!raw || typeof raw !== "object") return { userId: "", role: "" };
  const userId = String(raw.username || raw.user_id || raw.id || "").trim();
  const role = typeof raw.role === "string" ? raw.role.trim() : "";
  return { userId, role };
}

/**
 * Map URL / parent.context `size` to pixels for `--viewport-size`.
 * @param {string|number|null|undefined} raw
 * @returns {number|null}
 */
export function resolveViewportWidthPx(raw) {
  if (raw == null || raw === "") return null;
  const n = typeof raw === "number" ? raw : Number(String(raw).trim());
  if (!Number.isFinite(n)) return null;
  // Host / maskservice convention: 100 = full width (responsive), not 100px.
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
    (params.get("iframe_child") || "").trim().toLowerCase()
  );
}

function parseNavigationParams(params, out) {
  const scenario = params.get("scenario") || params.get("scenario_id");
  if (scenario) out.scenario = scenario.trim();
  const scenarioByFilename = params.get("scenario-by-filename");
  if (scenarioByFilename) out.scenarioByFilename = scenarioByFilename.trim();
  // Operator workflow context (PLF / hostorca request 2026-05-26):
  // /connect-scenario shell URL must reflect the active device + test so
  // share / reload preserves the selection. `device` is the device id
  // (DEV-001…) and `test` is the scenario file name (mask-tightness-test.oql).
  const device = params.get("device");
  if (device) out.device = device.trim();
  const deviceName = params.get("device_name");
  if (deviceName) out.deviceName = deviceName.trim();
  const test = params.get("test");
  if (test) out.test = test.trim();
  const key = (params.get(SHELL_HUI_KEY_PARAM) || "").trim();
  if (key && isValidShellHuiKey(key)) out.key = key;
}

function parseParams(search) {
  const params = new URLSearchParams(search);
  const out = { ...DEFAULTS };
  parseAppearanceParams(params, out);
  parseIdentityParams(params, out);
  parseNavigationParams(params, out);
  return out;
}

/** @param {string} search `location.search` or `?a=b` — for tests and tooling */
export function parseUrlEmbedConfig(search) {
  return parseParams(search);
}

/**
 * Merge an incoming `parent.context` envelope payload into the previous embed
 * config. Pure function — exported for tests so the iframe lang/theme/font
 * propagation path is regression-proof without a DOM.
 *
 * @param {object} prev   Previous config snapshot from {@link parseParams}.
 * @param {object} ctx    Payload from a `parent.context` envelope.
 * @returns {object}      Merged config (same shape as {@link parseParams}).
 */
export function mergeParentContext(prev, ctx) {
  if (!ctx || typeof ctx !== "object") return prev;
  const incomingFont = typeof ctx.font === "string" ? ctx.font.trim() : "";
  const nextFont =
    incomingFont && SUPPORTED_FONTS.includes(incomingFont) ? incomingFont : prev.font;
  const incomingLang = typeof ctx.locale === "string"
    ? ctx.locale.trim()
    : typeof ctx.lang === "string"
      ? ctx.lang.trim()
      : "";
  const nextLang =
    incomingLang && SUPPORTED_LANGS_ENUM.includes(incomingLang) ? incomingLang : prev.lang;
  const incomingTheme = typeof ctx.theme === "string" ? ctx.theme.trim() : "";
  const nextTheme =
    incomingTheme && SUPPORTED_THEMES.includes(incomingTheme) ? incomingTheme : prev.theme;
  const fromUser = resolveUserFromContextPayload(ctx.user);
  const nextUser = fromUser.userId || prev.user;
  const roleCandidate = typeof ctx.role === "string" ? ctx.role : fromUser.role;
  return {
    ...prev,
    theme: nextTheme,
    font: nextFont,
    role: normalizeConnectRole(roleCandidate, prev.role),
    user: nextUser,
    lang: nextLang,
    size: resolveViewportWidthPx(ctx.size) ?? prev.size,
  };
}

const IFRAME_ONLY_SEARCH_PARAMS = new Set(["iframe_child", "parent_origin"]);

/**
 * Apply the parent shell query string to the iframe URL (scanner deep-links:
 * scenario, test, run=true, device, …). Keeps iframe-only params from the child.
 */
export function mergeParentSearchIntoChildUrl(currentHref, parentSearch) {
  const url = new URL(currentHref);
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

/** Pure merge used by tests and {@link useUrlConfig} parent.context handler. */
export function applyParentContextPayload(prev, ctx, currentHref) {
  const search = typeof ctx?.search === "string" ? ctx.search.trim() : "";
  let base = prev;
  if (search && currentHref) {
    const href = mergeParentSearchIntoChildUrl(currentHref, search);
    base = parseParams(new URL(href, "http://localhost").search);
  }
  return mergeParentContext(base, ctx);
}

/**
 * Reads font/theme/role/lang/size/scenario from the current URL and keeps
 * state in sync when the history changes (e.g. parent frame postMessage or
 * browser navigation).
 */
export function useUrlConfig() {
  const [config, setConfig] = useState(() => parseParams(window.location.search));

  useEffect(() => {
    const onPop = () => setConfig(parseParams(window.location.search));
    window.addEventListener("popstate", onPop);

    const onMessage = (event) => {
      const envelope = event.data;
      if (envelope && typeof envelope === "object" && envelope.type === "parent.context" && envelope.payload) {
        const ctx = envelope.payload;
        setConfig((prev) => {
          const search = typeof ctx.search === "string" ? ctx.search.trim() : "";
          if (search) {
            try {
              const nextHref = mergeParentSearchIntoChildUrl(window.location.href, search);
              const currentHref = `${window.location.pathname}${window.location.search}`;
              if (nextHref !== currentHref) {
                window.history.replaceState({}, "", nextHref);
                window.dispatchEvent(new PopStateEvent("popstate"));
              }
              return applyParentContextPayload(prev, ctx, nextHref);
            } catch {
              // fall through to theme/locale-only merge
            }
          }
          return mergeParentContext(prev, ctx);
        });
      }
    };
    window.addEventListener("message", onMessage);

    // Notify parent that child is ready
    try {
      if (window.parent && window.parent !== window) {
        window.parent.postMessage({
          type: "child.ready",
          version: "1.0",
          requestId: `req_init_${Date.now()}`,
          timestamp: new Date().toISOString(),
          payload: {}
        }, "*");
      }
    } catch (e) {
      console.warn("Failed to send child.ready", e);
    }

    return () => {
      window.removeEventListener("popstate", onPop);
      window.removeEventListener("message", onMessage);
    };
  }, []);

  const patch = useCallback((partial) => {
    const url = new URL(window.location.href);
    Object.entries(partial).forEach(([k, v]) => {
      const param = k === "key" ? SHELL_HUI_KEY_PARAM : k;
      if (v === null || v === undefined || v === "") {
        url.searchParams.delete(param);
      } else if (k === "key" && !isValidShellHuiKey(String(v))) {
        url.searchParams.delete(param);
      } else {
        url.searchParams.set(param, String(v));
      }
    });
    window.history.replaceState({}, "", `${url.pathname}${url.search}`);
    setConfig(parseParams(url.search));
    // Mirror the patched keys into the embedding shell URL (maskservice
    // /connect-scenario at :8100) so the operator's address bar reflects
    // device/test/scenario selection in real time.
    bridgeSearchToParent(partial);
  }, []);

  return useMemo(() => ({ config, patch }), [config, patch]);
}

export { DEFAULTS as APP_CONFIG_DEFAULTS };
