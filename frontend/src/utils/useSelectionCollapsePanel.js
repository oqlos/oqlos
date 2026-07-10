import { useState, useEffect, useCallback, useRef } from "react";
import {
  COLLAPSE_DELAY_MS,
  isInIframe,
  postToParent,
  readStoredCollapsed,
  persistStoredCollapsed,
  readPinned,
  writePinned,
  formatBadge,
} from "./collapse-toggle-bridge.js";
import {
  sidebarCollapsedFromUrlParam,
  sidebarUrlFromCollapsed,
} from "./url-embed-config.js";
import { applyUrlEmbedPatchAndPersist } from "./ui-url-args-cookie.js";
import { useRailHoverPreview } from "../hooks/useRailHoverPreview.js";

export { RAIL_HOVER_OPEN_MS, RAIL_HOVER_CLOSE_MS } from "../hooks/useRailHoverPreview.js";

function readSidebarCollapsedFromUrl() {
  try {
    return sidebarCollapsedFromUrlParam(new URL(window.location.href).searchParams.get("sidebar"));
  } catch { /* silent */ }
  return null;
}

function syncSidebarUrl(stowed) {
  try {
    const nextSidebar = sidebarUrlFromCollapsed(stowed);
    const params = new URL(window.location.href).searchParams;
    if (params.get("sidebar") === nextSidebar) return;
    const { nextPath } = applyUrlEmbedPatchAndPersist(window.location.href, { sidebar: nextSidebar });
    window.history.replaceState(null, "", nextPath);
  } catch { /* silent */ }
}

function _makeCollapseToggleHandler(toggleId, { expand, previewExpand, previewCollapse }) {
  return (event) => {
    const envelope = event.data;
    if (!envelope || typeof envelope !== "object") return;
    if ((envelope.payload || {}).id !== toggleId) return;
    if (envelope.type === "parent.collapse-toggle.clicked") { expand(); return; }
    if (envelope.type === "parent.collapse-toggle.hover-open") { previewExpand(); return; }
    if (envelope.type === "parent.collapse-toggle.hover-close") { previewCollapse(); }
  };
}

function _useIframeCollapseToggle(toggleId, stowed, { expand, previewExpand, previewCollapse, label, icon, badge }) {
  useEffect(() => {
    if (!toggleId || !isInIframe()) return undefined;
    if (stowed) {
      postToParent("child.collapse-toggle.register", {
        id: toggleId, label, icon, badge: formatBadge(badge),
      });
      return () => postToParent("child.collapse-toggle.unregister", { id: toggleId });
    }
    postToParent("child.collapse-toggle.unregister", { id: toggleId });
    return undefined;
  }, [stowed, toggleId, label, icon, badge]);

  useEffect(() => {
    if (!toggleId || !isInIframe()) return undefined;
    const onMessage = _makeCollapseToggleHandler(toggleId, { expand, previewExpand, previewCollapse });
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [toggleId, expand, previewExpand, previewCollapse]);
}

/**
 * Selection-driven panel collapse with optional parent top-bar reveal toggle.
 */
export function useSelectionCollapsePanel({
  toggleId,
  storageKey,
  label,
  icon = "☰",
  badge,
}) {
  const [pinned, setPinned] = useState(() => readPinned(storageKey));
  const [userCollapsed, setUserCollapsed] = useState(() => {
    if (readPinned(storageKey)) return false;
    const fromUrl = readSidebarCollapsedFromUrl();
    if (fromUrl !== null) return fromUrl;
    return readStoredCollapsed(storageKey);
  });
  const [autoCollapsed, setAutoCollapsed] = useState(false);
  const timerRef = useRef(null);
  const stowed = (userCollapsed || autoCollapsed) && !pinned;

  const cancelAutoCollapse = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const {
    hoverPreview,
    setHoverPreview,
    previewCollapse,
    previewExpand,
    railEnter,
    railLeave,
    panelEnter,
    panelLeave,
  } = useRailHoverPreview({ stowed, onBeforeOpen: cancelAutoCollapse });

  const collapsed = stowed && !hoverPreview;

  const scheduleCollapse = useCallback(() => {
    cancelAutoCollapse();
    setHoverPreview(false);
    if (pinned || userCollapsed) return;
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      setUserCollapsed(true);
      persistStoredCollapsed(storageKey, true);
      syncSidebarUrl(true);
    }, COLLAPSE_DELAY_MS);
  }, [userCollapsed, cancelAutoCollapse, storageKey, setHoverPreview, pinned]);

  const expand = useCallback(() => {
    cancelAutoCollapse();
    setHoverPreview(false);
    setUserCollapsed(false);
    persistStoredCollapsed(storageKey, false);
    syncSidebarUrl(false);
  }, [cancelAutoCollapse, storageKey, setHoverPreview]);

  const togglePinned = useCallback(() => {
    setPinned((prev) => {
      const next = !prev;
      writePinned(storageKey, next);
      if (next) {
        setUserCollapsed(false);
        persistStoredCollapsed(storageKey, false);
        syncSidebarUrl(false);
      }
      return next;
    });
  }, [storageKey]);

  const toggleCollapsed = useCallback(() => {
    if (autoCollapsed) {
      setHoverPreview((prev) => !prev);
      return;
    }
    cancelAutoCollapse();
    setHoverPreview(false);
    setUserCollapsed((prev) => {
      const next = !prev;
      if (next) {
        setPinned(false);
        writePinned(storageKey, false);
      }
      persistStoredCollapsed(storageKey, next);
      syncSidebarUrl(next);
      return next;
    });
  }, [autoCollapsed, cancelAutoCollapse, storageKey, setHoverPreview]);

  useEffect(() => cancelAutoCollapse, [cancelAutoCollapse]);

  useEffect(() => {
    syncSidebarUrl(stowed);
  }, [stowed]);

  useEffect(() => {
    window.__activeSidebar = {
      toggleCollapsed,
      collapsed,
    };
    window.dispatchEvent(new CustomEvent("oqlos-sidebar-registered"));
    return () => {
      if (window.__activeSidebar && window.__activeSidebar.toggleCollapsed === toggleCollapsed) {
        window.__activeSidebar = null;
        window.dispatchEvent(new CustomEvent("oqlos-sidebar-registered"));
      }
    };
  }, [toggleCollapsed, collapsed]);

  _useIframeCollapseToggle(toggleId, stowed, { expand, previewExpand, previewCollapse, label, icon, badge });

  return {
    collapsed,
    userCollapsed,
    autoCollapsed,
    hoverPreview,
    inIframe: isInIframe(),
    scheduleCollapse,
    cancelAutoCollapse,
    toggleCollapsed,
    setAutoCollapsed,
    expand,
    previewExpand,
    previewCollapse,
    railEnter,
    railLeave,
    panelEnter,
    panelLeave,
    pinned,
    togglePinned,
  };
}
