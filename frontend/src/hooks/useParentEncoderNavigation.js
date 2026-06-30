import { useEffect } from "react";

const INTERACTIVE_SELECTOR = [
  "button:not([disabled])",
  "a[href]",
  "input:not([type=\"hidden\"]):not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex=\"-1\"])",
  "[role=\"button\"]",
  ".demo-user-btn",
  "[data-action]",
].join(",");

function getInteractiveItems() {
  const all = Array.from(document.querySelectorAll(INTERACTIVE_SELECTOR));
  return all.filter((el) => {
    try {
      const style = window.getComputedStyle(el);
      if (style.display === "none" || style.visibility === "hidden") return false;
      return el.offsetParent !== null || style.position === "fixed" || style.position === "absolute";
    } catch {
      return false;
    }
  });
}

function removeHighlights() {
  document.querySelectorAll(".encoder-focus").forEach((el) => {
    el.classList.remove("encoder-focus");
    el.style.outline = "";
  });
}

function parseParentEncoderEnvelope(data) {
  if (!data || typeof data !== "object") return null;
  if (data.type !== "parent.encoderCommand") return null;
  if (!data.payload || typeof data.payload !== "object") return null;
  return data;
}

function _applyScrollToItems(items, activeIndex, delta) {
  if (activeIndex < 0 || activeIndex >= items.length) {
    return delta > 0 ? 0 : items.length - 1;
  }
  return (activeIndex + delta + items.length) % items.length;
}

function _focusEncoderItem(target) {
  target.classList.add("encoder-focus");
  target.style.outline = "3px solid #2563eb";
  target.style.outlineOffset = "2px";
  target.focus({ preventScroll: true });
  target.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function _tryCancelPostMessage() {
  try {
    window.parent.postMessage({ type: "child.encoderCommandResponse", payload: { command: "cancel" } }, "*");
  } catch {
    // ignore cross-origin postMessage failures
  }
}

function createEncoderController() {
  let activeIndex = -1;
  let parentEncoderActive = false;

  const handleEncoderCommand = (cmd, payload = {}) => {
    if (cmd === "setActive") {
      parentEncoderActive = !!payload.active;
      document.body.dataset.parentEncoderActive = parentEncoderActive ? "1" : "0";
      if (!parentEncoderActive) { removeHighlights(); activeIndex = -1; }
      return;
    }

    const items = getInteractiveItems();
    if (items.length === 0) return;

    if (cmd === "scroll") {
      removeHighlights();
      activeIndex = _applyScrollToItems(items, activeIndex, payload.delta ?? 1);
      const target = items[activeIndex];
      if (target) _focusEncoderItem(target);
      return;
    }

    if (cmd === "click") { items[activeIndex]?.click(); return; }

    if (cmd === "cancel") {
      removeHighlights();
      activeIndex = -1;
      _tryCancelPostMessage();
    }
  };

  const onKeyDown = (event) => {
    if (activeIndex < 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault(); event.stopPropagation();
      handleEncoderCommand("scroll", { delta: 1 });
    } else if (event.key === "ArrowUp") {
      event.preventDefault(); event.stopPropagation();
      handleEncoderCommand("scroll", { delta: -1 });
    } else if (event.key === "Enter") {
      event.preventDefault(); event.stopPropagation();
      handleEncoderCommand("click");
    } else if (event.key === "Backspace" || event.key === "Escape") {
      event.preventDefault(); event.stopPropagation();
      handleEncoderCommand("cancel");
    }
  };

  return { handleEncoderCommand, onKeyDown, isParentEncoderActive: () => parentEncoderActive };
}

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
