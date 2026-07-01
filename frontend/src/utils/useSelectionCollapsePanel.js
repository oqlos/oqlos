import { useState, useEffect, useCallback, useRef } from "react";
import {
  COLLAPSE_DELAY_MS,
  isInIframe,
  postToParent,
  readStoredCollapsed,
  persistStoredCollapsed,
} from "./collapse-toggle-bridge.js";
import { useRailHoverPreview } from "../hooks/useRailHoverPreview.js";

export { RAIL_HOVER_OPEN_MS, RAIL_HOVER_CLOSE_MS } from "../hooks/useRailHoverPreview.js";

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
  const [pinned, setPinned] = useState(() => {
    try {
      return localStorage.getItem(storageKey + "-pinned") === "true";
    } catch (_) {
      return false;
    }
  });
  const [userCollapsed, setUserCollapsed] = useState(() => {
    try {
      if (localStorage.getItem(storageKey + "-pinned") === "true") return false;
    } catch (_) {}
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
    if (pinned) return;
    if (userCollapsed) return;
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      setUserCollapsed(true);
      persistStoredCollapsed(storageKey, true);
    }, COLLAPSE_DELAY_MS);
  }, [userCollapsed, cancelAutoCollapse, storageKey, setHoverPreview, pinned]);

  const expand = useCallback(() => {
    cancelAutoCollapse();
    setHoverPreview(false);
    setUserCollapsed(false);
    persistStoredCollapsed(storageKey, false);
  }, [cancelAutoCollapse, storageKey, setHoverPreview]);

  const togglePinned = useCallback(() => {
    setPinned((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(storageKey + "-pinned", String(next));
      } catch (_) {}
      if (next) {
        setUserCollapsed(false);
        persistStoredCollapsed(storageKey, false);
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
        try {
          localStorage.setItem(storageKey + "-pinned", "false");
        } catch (_) {}
      }
      persistStoredCollapsed(storageKey, next);
      return next;
    });
  }, [autoCollapsed, cancelAutoCollapse, storageKey, setHoverPreview]);

  useEffect(() => cancelAutoCollapse, [cancelAutoCollapse]);

  useEffect(() => {
    if (!toggleId || !isInIframe()) return undefined;
    if (stowed) {
      postToParent("child.collapse-toggle.register", {
        id: toggleId,
        label,
        icon,
        badge: badge !== undefined && badge !== null && String(badge).length ? String(badge) : "",
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
