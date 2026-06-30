import { useState, useEffect, useCallback, useRef } from "react";
import {
  COLLAPSE_DELAY_MS,
  isInIframe,
  postToParent,
  readStoredCollapsed,
  persistStoredCollapsed,
} from "./collapse-toggle-bridge.js";

/** Hover-intent before the thin rail flips into preview mode. */
export const RAIL_HOVER_OPEN_MS = 150;
/** Grace period after the cursor leaves the expanded preview panel. */
export const RAIL_HOVER_CLOSE_MS = 600;

/**
 * Selection-driven panel collapse with optional parent top-bar reveal toggle.
 * `userCollapsed` is the persisted stowed state; `collapsed` is what we render
 * (false briefly during hover-preview while the top-bar button stays visible).
 */
export function useSelectionCollapsePanel({
  toggleId,
  storageKey,
  label,
  icon = "☰",
  badge,
}) {
  const [userCollapsed, setUserCollapsed] = useState(() => readStoredCollapsed(storageKey));
  const [autoCollapsed, setAutoCollapsed] = useState(false);
  const [hoverPreview, setHoverPreview] = useState(false);
  const timerRef = useRef(null);
  const railOpenTimerRef = useRef(null);
  const panelCloseTimerRef = useRef(null);

  const collapsed = (userCollapsed || autoCollapsed) && !hoverPreview;

  const cancelAutoCollapse = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const cancelRailOpen = useCallback(() => {
    if (railOpenTimerRef.current) {
      clearTimeout(railOpenTimerRef.current);
      railOpenTimerRef.current = null;
    }
  }, []);

  const cancelPanelClose = useCallback(() => {
    if (panelCloseTimerRef.current) {
      clearTimeout(panelCloseTimerRef.current);
      panelCloseTimerRef.current = null;
    }
  }, []);

  const scheduleCollapse = useCallback(() => {
    cancelAutoCollapse();
    setHoverPreview(false);
    if (userCollapsed) return;
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      setUserCollapsed(true);
      persistStoredCollapsed(storageKey, true);
    }, COLLAPSE_DELAY_MS);
  }, [userCollapsed, cancelAutoCollapse, storageKey]);

  const expand = useCallback(() => {
    cancelAutoCollapse();
    setHoverPreview(false);
    setUserCollapsed(false);
    persistStoredCollapsed(storageKey, false);
  }, [cancelAutoCollapse, storageKey]);

  const previewExpand = useCallback(() => {
    if (!userCollapsed && !autoCollapsed) return;
    cancelAutoCollapse();
    setHoverPreview(true);
  }, [userCollapsed, autoCollapsed, cancelAutoCollapse]);

  const previewCollapse = useCallback(() => {
    setHoverPreview(false);
  }, []);

  const railEnter = useCallback(() => {
    if (!userCollapsed && !autoCollapsed) return;
    cancelPanelClose();
    if (railOpenTimerRef.current) return;
    railOpenTimerRef.current = setTimeout(() => {
      railOpenTimerRef.current = null;
      cancelAutoCollapse();
      setHoverPreview(true);
    }, RAIL_HOVER_OPEN_MS);
  }, [userCollapsed, autoCollapsed, cancelAutoCollapse, cancelPanelClose]);

  const railLeave = useCallback(() => {
    cancelRailOpen();
  }, [cancelRailOpen]);

  const panelEnter = useCallback(() => {
    cancelPanelClose();
  }, [cancelPanelClose]);

  const panelLeave = useCallback(() => {
    cancelRailOpen();
    if (!userCollapsed && !autoCollapsed) return;
    if (panelCloseTimerRef.current) clearTimeout(panelCloseTimerRef.current);
    panelCloseTimerRef.current = setTimeout(() => {
      panelCloseTimerRef.current = null;
      setHoverPreview(false);
    }, RAIL_HOVER_CLOSE_MS);
  }, [userCollapsed, autoCollapsed, cancelRailOpen]);

  const toggleCollapsed = useCallback(() => {
    if (autoCollapsed) {
      setHoverPreview((prev) => !prev);
      return;
    }
    cancelAutoCollapse();
    setHoverPreview(false);
    setUserCollapsed((prev) => {
      const next = !prev;
      persistStoredCollapsed(storageKey, next);
      return next;
    });
  }, [autoCollapsed, cancelAutoCollapse, storageKey]);

  useEffect(() => cancelAutoCollapse, [cancelAutoCollapse]);
  useEffect(() => cancelRailOpen, [cancelRailOpen]);
  useEffect(() => cancelPanelClose, [cancelPanelClose]);

  // Keep the top-bar button registered while `userCollapsed` — including
  // during hover-preview when the panel is temporarily visible.
  useEffect(() => {
    if (!toggleId || !isInIframe()) return undefined;
    if (userCollapsed || autoCollapsed) {
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
  }, [userCollapsed, autoCollapsed, toggleId, label, icon, badge]);

  useEffect(() => {
    if (!toggleId || !isInIframe()) return undefined;
    const onMessage = (event) => {
      const envelope = event.data;
      if (!envelope || typeof envelope !== "object") return;
      const payload = envelope.payload || {};
      if (payload.id !== toggleId) return;

      if (envelope.type === "parent.collapse-toggle.clicked") {
        expand();
        return;
      }
      if (envelope.type === "parent.collapse-toggle.hover-open") {
        previewExpand();
        return;
      }
      if (envelope.type === "parent.collapse-toggle.hover-close") {
        previewCollapse();
      }
    };
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
  };
}
