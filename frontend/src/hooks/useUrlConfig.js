import { useCallback, useEffect, useMemo, useState } from "react";
import { bridgeSearchToParent } from "@semcod/frontend-services/parentUrlBridge.js";
import {
  applyUrlEmbedPatch,
  buildEmbedConfigUrlPatch,
  parseUrlEmbedConfig,
  resolveParentContextUpdate,
} from "../utils/url-embed-config.js";
import {
  hydrateUrlFromUiArgsCookie,
  persistUiUrlArgsToCookie,
} from "../utils/ui-url-args-cookie.js";

export {
  APP_CONFIG_DEFAULTS,
  applyParentContextPayload,
  mergeParentContext,
  mergeParentSearchIntoChildUrl,
  parseUrlEmbedConfig,
  resolveParentContextUpdate,
  resolveUserFromContextPayload,
  resolveUserIdFromSearchParams,
  resolveViewportWidthPx,
  SUPPORTED_FONTS,
  SUPPORTED_LANGS_ENUM,
  SUPPORTED_ROLES,
  SUPPORTED_THEMES,
} from "../utils/url-embed-config.js";

export { APP_CONFIG_DEFAULTS as DEFAULTS } from "../utils/url-embed-config.js";

function notifyParentChildReady() {
  try {
    if (window.parent && window.parent !== window) {
      window.parent.postMessage({
        type: "child.ready",
        version: "1.0",
        requestId: `req_init_${Date.now()}`,
        timestamp: new Date().toISOString(),
        payload: {},
      }, "*");
    }
  } catch (error) {
    console.warn("Failed to send child.ready", error);
  }
}

export function useUrlConfig() {
  const [config, setConfig] = useState(() => {
    hydrateUrlFromUiArgsCookie();
    return parseUrlEmbedConfig(window.location.search);
  });

  useEffect(() => {
    const onPop = () => setConfig(parseUrlEmbedConfig(window.location.search));
    window.addEventListener("popstate", onPop);

    const onMessage = (event) => {
      const envelope = event.data;
      if (!envelope || typeof envelope !== "object" || envelope.type !== "parent.context") return;
      if (!envelope.payload) return;

      setConfig((prev) => {
        const { config: nextConfig, nextHref, currentHref } = resolveParentContextUpdate(
          prev,
          envelope.payload,
          window.location,
        );
        if (nextHref && currentHref && nextHref !== currentHref) {
          window.history.replaceState({}, "", nextHref);
          window.dispatchEvent(new PopStateEvent("popstate"));
        }
        return nextConfig;
      });
    };
    window.addEventListener("message", onMessage);
    notifyParentChildReady();

    return () => {
      window.removeEventListener("popstate", onPop);
      window.removeEventListener("message", onMessage);
    };
  }, []);

  // Keep the address bar in sync with active chrome config (font/theme/lang/size…).
  useEffect(() => {
    const patch = buildEmbedConfigUrlPatch(config, window.location.search);
    if (Object.keys(patch).length === 0) return;
    const { nextPath } = applyUrlEmbedPatch(window.location.href, patch);
    const current = `${window.location.pathname}${window.location.search}`;
    if (nextPath !== current) {
      window.history.replaceState({}, "", nextPath);
      persistUiUrlArgsToCookie(patch);
    }
  }, [config.font, config.theme, config.lang, config.role, config.size, config.mode]);

  const patch = useCallback((partial) => {
    const { nextPath, config: nextConfig } = applyUrlEmbedPatch(window.location.href, partial);
    window.history.replaceState({}, "", nextPath);
    setConfig(nextConfig);
    persistUiUrlArgsToCookie(partial);
    bridgeSearchToParent(partial);
  }, []);

  return useMemo(() => ({ config, patch }), [config, patch]);
}
