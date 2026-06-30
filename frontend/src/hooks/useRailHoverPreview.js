import { useCallback, useEffect, useRef, useState } from "react";

/** Hover-intent before the thin rail flips into preview mode. */
export const RAIL_HOVER_OPEN_MS = 150;
/** Grace period after the cursor leaves the expanded preview panel. */
export const RAIL_HOVER_CLOSE_MS = 600;

/**
 * Deferred rail/panel hover preview while the sidebar is stowed.
 * @param {{ stowed: boolean, onBeforeOpen?: () => void }} options
 */
export function useRailHoverPreview({ stowed, onBeforeOpen }) {
  const [hoverPreview, setHoverPreview] = useState(false);
  const railOpenTimerRef = useRef(null);
  const panelCloseTimerRef = useRef(null);

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

  const previewCollapse = useCallback(() => {
    setHoverPreview(false);
  }, []);

  const previewExpand = useCallback(() => {
    if (!stowed) return;
    onBeforeOpen?.();
    setHoverPreview(true);
  }, [stowed, onBeforeOpen]);

  const railEnter = useCallback(() => {
    if (!stowed) return;
    cancelPanelClose();
    if (railOpenTimerRef.current) return;
    railOpenTimerRef.current = setTimeout(() => {
      railOpenTimerRef.current = null;
      previewExpand();
    }, RAIL_HOVER_OPEN_MS);
  }, [stowed, cancelPanelClose, previewExpand]);

  const railLeave = useCallback(() => {
    cancelRailOpen();
  }, [cancelRailOpen]);

  const panelEnter = useCallback(() => {
    cancelPanelClose();
  }, [cancelPanelClose]);

  const panelLeave = useCallback(() => {
    cancelRailOpen();
    if (!stowed) return;
    if (panelCloseTimerRef.current) clearTimeout(panelCloseTimerRef.current);
    panelCloseTimerRef.current = setTimeout(() => {
      panelCloseTimerRef.current = null;
      setHoverPreview(false);
    }, RAIL_HOVER_CLOSE_MS);
  }, [stowed, cancelRailOpen]);

  useEffect(() => cancelRailOpen, [cancelRailOpen]);
  useEffect(() => cancelPanelClose, [cancelPanelClose]);

  return {
    hoverPreview,
    setHoverPreview,
    previewCollapse,
    previewExpand,
    railEnter,
    railLeave,
    panelEnter,
    panelLeave,
    cancelRailOpen,
    cancelPanelClose,
  };
}
