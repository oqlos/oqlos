/**
 * Inline-style helpers: 1rem tracks html { font-size: var(--font-base-size) } (14px default).
 * Values are design px ÷ 14, shared by connect-scenario and OqlOS UI.
 *
 * SSOT — import from `@semcod/frontend-services/designRem.js`.
 */
export const rem = Object.freeze({
  /** 10px */
  xxs: "0.7143rem",
  /** 11px */
  xs: "0.7857rem",
  /** 12px */
  sm: "0.8571rem",
  /** 13px */
  md: "0.9286rem",
  /** 14px */
  base: "1rem",
  /** 15px */
  lg: "1.0714rem",
  /** 16px */
  xl: "1.1429rem",
  /** 22px */
  display: "1.5714rem",
  /** Collapsed left-rail ☰ glyph (same as xxs). */
  railIcon: "0.7143rem",
  /** Badge on collapsed rail (same as xs). */
  railBadge: "0.7857rem",
  /** Section headings (21px @ 14px base). */
  title: "1.5rem",
});

/** CSS custom property names matching `rem` (use in stylesheets). */
export const remVar = Object.freeze({
  xxs: "--font-rem-xxs",
  xs: "--font-rem-xs",
  sm: "--font-rem-sm",
  md: "--font-rem-md",
  base: "--font-rem-base",
  lg: "--font-rem-lg",
  xl: "--font-rem-xl",
  display: "--font-rem-display",
  title: "--font-rem-title",
  railIcon: "--font-rem-xxs",
  railBadge: "--font-rem-xs",
});
