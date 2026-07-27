import { bridgeSearchToParent } from "./parentUrlBridge.js";
import { applyUrlEmbedPatch } from "./url-embed-config.js";

/**
 * Persist command intent/result in both the OqlOS iframe URL and its parent.
 * These arguments are an audit trail only; they must never execute a command
 * when a page is loaded or refreshed.
 */
export function recordCommandUrlState(partial, browser = globalThis) {
  const location = browser?.location;
  const history = browser?.history;
  if (!location?.href || !history?.replaceState) return false;

  const { nextPath } = applyUrlEmbedPatch(location.href, partial || {});
  const currentPath = `${location.pathname || ""}${location.search || ""}`;
  if (nextPath !== currentPath) history.replaceState(null, "", nextPath);
  bridgeSearchToParent(partial);
  return true;
}
