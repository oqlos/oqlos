/** Mirrors maskservice `ConnectFont` / `SIZE_TO_SCALE` (mono & dyslexic = base scale). */
export const FONT_USER_SCALE = Object.freeze({
  default: "1.00",
  large: "1.20",
  xlarge: "1.518",
  mono: "1.00",
  dyslexic: "1.00",
});

export function applyDocumentAppConfig(config) {
  if (typeof document === "undefined") {
    return;
  }
  const root = document.documentElement;
  root.setAttribute("data-theme", config.theme);
  root.setAttribute("data-font", config.font);
  root.setAttribute("data-role", config.role);
  root.setAttribute("data-user", config.user || "");
  root.setAttribute("data-lang", config.lang);
  root.setAttribute("data-iframe-child", config.iframeChild ? "1" : "0");
  root.setAttribute("data-input-mode", config.mode || "keyboard");
  root.style.setProperty("--viewport-size", `${config.size}px`);
  const scale = FONT_USER_SCALE[config.font] ?? FONT_USER_SCALE.default;
  root.style.setProperty("--font-user-scale", scale);
  document.body.dataset.font = config.font;
  document.body.dataset.iframeChild = config.iframeChild ? "1" : "0";
  document.body.dataset.inputMode = config.mode || "keyboard";
}
