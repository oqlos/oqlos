/**
 * Visual grid (5×3) + Ctrl+Alt indices from `HUI_TEST_BUTTON_ORDER`.
 * Col 2: LP +5 / −5; col 4: LP +10 / −10; col 3 empty (SC removed).
 */
export const SHELL_HUI_KEY_ENTRIES = [
  { index: 1, key: "head-deflate", label: "Głowa −", tone: "green", gridRow: 3, gridCol: 1 },
  { index: 2, key: "lp-pwm-plus5", label: "LP +5", tone: "green", gridRow: 1, gridCol: 2 },
  { index: 3, key: "lp-pwm-plus10", label: "LP +10", tone: "green", gridRow: 1, gridCol: 4 },
  { index: 4, key: "al-start", label: "AL START", tone: "green", gridRow: 1, gridCol: 5 },
  { index: 5, key: "lp-bleed", label: "LP Upust", tone: "green", gridRow: 2, gridCol: 3 },
  { index: 6, key: "head-inflate", label: "Głowa ＋", tone: "green", gridRow: 1, gridCol: 1 },
  { index: 7, key: "lp-pwm-minus5", label: "LP −5", tone: "green", gridRow: 3, gridCol: 2 },
  { index: 8, key: "lp-pwm-minus10", label: "LP −10", tone: "green", gridRow: 3, gridCol: 4 },
  { index: 9, key: "al-stop", label: "AL STOP", tone: "green", gridRow: 3, gridCol: 5 },
];

export const SHELL_HUI_KEY_PARAM = "key";

export function isValidShellHuiKey(key) {
  return SHELL_HUI_KEY_ENTRIES.some((entry) => entry.key === key)
    || key === "mp-plus"
    || key === "mp-minus"
    || key === "lp-plus"
    || key === "lp-minus";
}

export function huiKeyForDigit(index) {
  const entry = SHELL_HUI_KEY_ENTRIES.find((item) => item.index === index);
  return entry?.key || null;
}

export function huiShortcutClass(index) {
  return `virtual-hui-key-btn--shortcut-${index}`;
}

export function huiShortcutLabelClass(index) {
  return `virtual-hui-key-btn__label--shortcut-${index}`;
}
