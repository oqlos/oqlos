/** Parent iframe encoder navigation — pure DOM helpers (no React). */

export const INTERACTIVE_SELECTOR = [
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

export function getInteractiveItems() {
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

export function removeEncoderHighlights() {
  document.querySelectorAll(".encoder-focus").forEach((el) => {
    el.classList.remove("encoder-focus");
    el.style.outline = "";
  });
}

export function parseParentEncoderEnvelope(data) {
  if (!data || typeof data !== "object") return null;
  if (data.type !== "parent.encoderCommand") return null;
  if (!data.payload || typeof data.payload !== "object") return null;
  return data;
}

export function applyScrollToItems(items, activeIndex, delta) {
  if (activeIndex < 0 || activeIndex >= items.length) {
    return delta > 0 ? 0 : items.length - 1;
  }
  return (activeIndex + delta + items.length) % items.length;
}

export function focusEncoderItem(target) {
  target.classList.add("encoder-focus");
  target.style.outline = "3px solid #2563eb";
  target.style.outlineOffset = "2px";
  target.focus({ preventScroll: true });
  target.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

export function tryCancelPostMessage() {
  try {
    window.parent.postMessage({ type: "child.encoderCommandResponse", payload: { command: "cancel" } }, "*");
  } catch {
    // ignore cross-origin postMessage failures
  }
}

function handleSetActive(state, payload) {
  state.parentEncoderActive = !!payload.active;
  document.body.dataset.parentEncoderActive = state.parentEncoderActive ? "1" : "0";
  if (!state.parentEncoderActive) {
    removeEncoderHighlights();
    state.activeIndex = -1;
  }
}

function handleScroll(state, payload) {
  const items = getInteractiveItems();
  if (items.length === 0) return;
  removeEncoderHighlights();
  state.activeIndex = applyScrollToItems(items, state.activeIndex, payload.delta ?? 1);
  const target = items[state.activeIndex];
  if (target) focusEncoderItem(target);
}

function handleClick(state) {
  const items = getInteractiveItems();
  if (items.length === 0) return;
  items[state.activeIndex]?.click();
}

function handleCancel(state) {
  removeEncoderHighlights();
  state.activeIndex = -1;
  tryCancelPostMessage();
}

export function createEncoderController() {
  const state = { activeIndex: -1, parentEncoderActive: false };

  const handleEncoderCommand = (cmd, payload = {}) => {
    if (cmd === "setActive") {
      handleSetActive(state, payload);
      return;
    }
    if (cmd === "scroll") {
      handleScroll(state, payload);
      return;
    }
    if (cmd === "click") {
      handleClick(state);
      return;
    }
    if (cmd === "cancel") {
      handleCancel(state);
    }
  };

  const onKeyDown = (event) => {
    if (state.activeIndex < 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      event.stopPropagation();
      handleEncoderCommand("scroll", { delta: 1 });
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      event.stopPropagation();
      handleEncoderCommand("scroll", { delta: -1 });
    } else if (event.key === "Enter") {
      event.preventDefault();
      event.stopPropagation();
      handleEncoderCommand("click");
    } else if (event.key === "Backspace" || event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      handleEncoderCommand("cancel");
    }
  };

  return {
    handleEncoderCommand,
    onKeyDown,
    isParentEncoderActive: () => state.parentEncoderActive,
  };
}
