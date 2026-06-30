import { useCallback, useEffect, useMemo, useState } from "react";
import { bridgeSearchToParent } from "../utils/parentUrlBridge.js";
import {
  applyUrlEmbedPatch,
  parseUrlEmbedConfig,
  resolveParentContextUpdate,
} from "../utils/url-embed-config.js";

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
  const [config, setConfig] = useState(() => parseUrlEmbedConfig(window.location.search));

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

  const patch = useCallback((partial) => {
    const { nextPath, config: nextConfig } = applyUrlEmbedPatch(window.location.href, partial);
    window.history.replaceState({}, "", nextPath);
    setConfig(nextConfig);
    bridgeSearchToParent(partial);
  }, []);

  return useMemo(() => ({ config, patch }), [config, patch]);
}
