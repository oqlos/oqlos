import { createContext, useContext, useEffect, useMemo } from "react";
import { useUrlConfig } from "../hooks/useUrlConfig";
import {
  isAdminConnectRole,
  isOperatorConnectRole,
  isReadOnlyConnectRole,
  normalizeConnectRole,
} from "../utils/rbac.policy.js";

/** Mirrors maskservice `ConnectFont` / `SIZE_TO_SCALE` (mono & dyslexic = base scale). */
const FONT_USER_SCALE = Object.freeze({
  default: "1.00",
  large: "1.20",
  xlarge: "1.518",
  mono: "1.00",
  dyslexic: "1.00",
});

const AppConfigContext = createContext(null);

export function AppConfigProvider({ children }) {
  const { config, patch } = useUrlConfig();

  // Apply theme/font/size to the document root so CSS vars react instantly.
  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-theme", config.theme);
    root.setAttribute("data-font", config.font);
    root.setAttribute("data-role", config.role);
    root.setAttribute("data-user", config.user || "");
    root.setAttribute("data-lang", config.lang);
    root.setAttribute("data-iframe-child", config.iframeChild ? "1" : "0");
    root.style.setProperty("--viewport-size", `${config.size}px`);
    const scale = FONT_USER_SCALE[config.font] ?? FONT_USER_SCALE.default;
    root.style.setProperty("--font-user-scale", scale);
    document.body.dataset.font = config.font;
    document.body.dataset.iframeChild = config.iframeChild ? "1" : "0";
  }, [config.theme, config.font, config.role, config.user, config.lang, config.size, config.iframeChild]);

  // Integrated Encoder Mode support for cross-origin iframe navigation.
  useEffect(() => {
    if (typeof window === "undefined") return;

    let activeIndex = -1;
    let parentEncoderActive = false;

    const getInteractiveItems = () => {
      const selectors = [
        "button:not([disabled])",
        "a[href]",
        "input:not([type=\"hidden\"]):not([disabled])",
        "select:not([disabled])",
        "textarea:not([disabled])",
        "[tabindex]:not([tabindex=\"-1\"])",
        "[role=\"button\"]",
        ".demo-user-btn",
        "[data-action]"
      ].join(",");

      const all = Array.from(document.querySelectorAll(selectors));
      return all.filter((el) => {
        try {
          const style = window.getComputedStyle(el);
          if (style.display === "none" || style.visibility === "hidden") return false;
          return el.offsetParent !== null || style.position === "fixed" || style.position === "absolute";
        } catch {
          return false;
        }
      });
    };

    const removeHighlights = () => {
      document.querySelectorAll(".encoder-focus").forEach((el) => {
        el.classList.remove("encoder-focus");
        el.style.outline = "";
      });
    };

    const handleEncoderCommand = (cmd, payload = {}) => {
      if (cmd === "setActive") {
        parentEncoderActive = !!payload.active;
        document.body.dataset.parentEncoderActive = parentEncoderActive ? "1" : "0";
        if (!parentEncoderActive) {
          removeHighlights();
          activeIndex = -1;
        }
        return;
      }

      const items = getInteractiveItems();
      if (items.length === 0) return;

      if (cmd === "scroll") {
        removeHighlights();
        const delta = payload.delta ?? 1;

        if (activeIndex < 0 || activeIndex >= items.length) {
          activeIndex = delta > 0 ? 0 : items.length - 1;
        } else {
          activeIndex = (activeIndex + delta + items.length) % items.length;
        }

        const target = items[activeIndex];
        if (target) {
          target.classList.add("encoder-focus");
          target.style.outline = "3px solid #2563eb";
          target.style.outlineOffset = "2px";
          target.focus({ preventScroll: true });
          target.scrollIntoView({ block: "nearest", behavior: "smooth" });
        }
      } else if (cmd === "click") {
        const target = items[activeIndex];
        if (target) {
          target.click();
        }
      } else if (cmd === "cancel") {
        removeHighlights();
        activeIndex = -1;
        try {
          window.parent.postMessage({
            type: "child.encoderCommandResponse",
            payload: { command: "cancel" }
          }, "*");
        } catch {}
      }
    };

    const parseParentEnvelope = (data) => {
      if (!data || typeof data !== "object") return null;
      if (data.type !== "parent.encoderCommand") return null;
      if (!data.payload || typeof data.payload !== "object") return null;
      return data;
    };

    const onMessage = (event) => {
      const envelope = parseParentEnvelope(event.data);
      if (!envelope) return;

      const detail = envelope.payload || {};
      handleEncoderCommand(detail.command, detail);
    };

    const onWheel = (event) => {
      if (!config.iframeChild || !parentEncoderActive) return;
      event.preventDefault();
      event.stopPropagation();
      const raw = Math.abs(event.deltaY) >= Math.abs(event.deltaX) ? event.deltaY : event.deltaX;
      if (raw === 0) return;
      handleEncoderCommand("scroll", { delta: raw > 0 ? 1 : -1 });
    };

    const onKeyDown = (e) => {
      // If we have an active focused element in our encoder sequence, intercept standard controls
      if (activeIndex >= 0) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          e.stopPropagation();
          handleEncoderCommand("scroll", { delta: 1 });
        } else if (e.key === "ArrowUp") {
          e.preventDefault();
          e.stopPropagation();
          handleEncoderCommand("scroll", { delta: -1 });
        } else if (e.key === "Enter") {
          e.preventDefault();
          e.stopPropagation();
          handleEncoderCommand("click");
        } else if (e.key === "Backspace" || e.key === "Escape") {
          e.preventDefault();
          e.stopPropagation();
          handleEncoderCommand("cancel");
        }
      }
    };

    window.addEventListener("message", onMessage);
    window.addEventListener("wheel", onWheel, { capture: true, passive: false });
    window.addEventListener("keydown", onKeyDown, { capture: true });

    return () => {
      window.removeEventListener("message", onMessage);
      window.removeEventListener("wheel", onWheel, { capture: true });
      window.removeEventListener("keydown", onKeyDown, { capture: true });
      delete document.body.dataset.parentEncoderActive;
    };
  }, [config.iframeChild]);

  const value = useMemo(
    () => ({
      ...config,
      role: normalizeConnectRole(config.role),
      isAdmin: isAdminConnectRole(config.role),
      isOperator: isOperatorConnectRole(config.role),
      isReadOnly: isReadOnlyConnectRole(config.role),
      patch,
    }),
    [config, patch]
  );

  return <AppConfigContext.Provider value={value}>{children}</AppConfigContext.Provider>;
}

export function useAppConfig() {
  const ctx = useContext(AppConfigContext);
  if (!ctx) throw new Error("useAppConfig must be used within AppConfigProvider");
  return ctx;
}
