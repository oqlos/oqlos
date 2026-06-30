import { useEffect } from "react";

import { createEncoderController, parseParentEncoderEnvelope } from "../utils/encoder-navigation.js";

/** Parent iframe encoder navigation (scroll wheel + postMessage). */
export function useParentEncoderNavigation(iframeChild) {
  useEffect(() => {
    if (typeof window === "undefined") return undefined;

    const controller = createEncoderController();

    const onMessage = (event) => {
      const envelope = parseParentEncoderEnvelope(event.data);
      if (!envelope) return;
      const detail = envelope.payload || {};
      controller.handleEncoderCommand(detail.command, detail);
    };

    const onWheel = (event) => {
      if (!iframeChild || !controller.isParentEncoderActive()) return;
      event.preventDefault();
      event.stopPropagation();
      const raw = Math.abs(event.deltaY) >= Math.abs(event.deltaX) ? event.deltaY : event.deltaX;
      if (raw === 0) return;
      controller.handleEncoderCommand("scroll", { delta: raw > 0 ? 1 : -1 });
    };

    window.addEventListener("message", onMessage);
    window.addEventListener("wheel", onWheel, { capture: true, passive: false });
    window.addEventListener("keydown", controller.onKeyDown, { capture: true });

    return () => {
      window.removeEventListener("message", onMessage);
      window.removeEventListener("wheel", onWheel, { capture: true });
      window.removeEventListener("keydown", controller.onKeyDown, { capture: true });
      delete document.body.dataset.parentEncoderActive;
    };
  }, [iframeChild]);
}
