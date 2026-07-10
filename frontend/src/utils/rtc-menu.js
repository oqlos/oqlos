export const RTC_MENU_URL_PARAM = "submenu";

export const RTC_MENU_IDS = [
  "overview",
  "read_status",
  "read_time",
  "read_date",
  "read_temperature",
  "read_watchdog",
  "sync_from_system",
  "sync_to_system",
  "feed_watchdog",
  "reinit",
];

export const RTC_MENU_ITEMS = [
  { id: "overview", labelKey: "hardwareRtc.menuOverview", command: "read_status" },
  { id: "read_time", labelKey: "hardwareRtc.cmdTime", command: "read_time" },
  { id: "read_date", labelKey: "hardwareRtc.cmdDate", command: "read_date" },
  { id: "read_temperature", labelKey: "hardwareRtc.cmdTemperature", command: "read_temperature" },
  { id: "read_watchdog", labelKey: "hardwareRtc.cmdWatchdog", command: "read_watchdog" },
  { id: "sync_from_system", labelKey: "hardwareRtc.cmdSyncFromSystem", command: "sync_from_system" },
  { id: "sync_to_system", labelKey: "hardwareRtc.cmdSyncToSystem", command: "sync_to_system" },
  { id: "feed_watchdog", labelKey: "hardwareRtc.cmdFeedWatchdog", command: "feed_watchdog" },
  { id: "reinit", labelKey: "hardwareRtc.cmdReinit", command: "reinit" },
];

export function readRtcMenuFromSearch(search) {
  const params = new URLSearchParams(String(search || "").replace(/^\?/, ""));
  const token = String(params.get(RTC_MENU_URL_PARAM) || "").trim();
  if (!RTC_MENU_IDS.includes(token)) return "";
  return token;
}

export function resolveRtcMenuId(raw, fallback = "overview") {
  const token = String(raw || "").trim();
  return RTC_MENU_IDS.includes(token) ? token : fallback;
}

export function patchRtcMenuSearchParams(params, menuId) {
  const next = new URLSearchParams(params);
  const resolved = resolveRtcMenuId(menuId);
  if (resolved === "overview") {
    next.delete(RTC_MENU_URL_PARAM);
  } else {
    next.set(RTC_MENU_URL_PARAM, resolved);
  }
  return next;
}

export function buildRtcSidebarItems(t) {
  return RTC_MENU_ITEMS.map((item) => ({
    id: item.id,
    title: t(item.labelKey),
    subtitle: item.command,
  }));
}

export function resolveRtcMenuCommand(menuId) {
  const item = RTC_MENU_ITEMS.find((entry) => entry.id === menuId);
  return item?.command || "read_status";
}
