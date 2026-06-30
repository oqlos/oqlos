import { useEffect, useRef } from "react";
import { hardwareNowText } from "./hardware-time.js";

export function createHardwareActivityLogEntry(level, message, detail = "", index = 0) {
  return {
    id: `${Date.now()}-${index}`,
    time: hardwareNowText(),
    level,
    message,
    detail,
  };
}

export function prependHardwareActivityLogEntry(prev, level, message, detail = "", limit = 80) {
  return [createHardwareActivityLogEntry(level, message, detail, prev.length), ...prev].slice(0, limit);
}

export function usePageOpenedLog(t, setActivityLog, pageOpenedKey, pageOpenedDetailKey) {
  const loggedRef = useRef(false);
  useEffect(() => {
    if (loggedRef.current) return;
    loggedRef.current = true;
    setActivityLog([
      {
        ...createHardwareActivityLogEntry(
          "info",
          t(pageOpenedKey),
          t(pageOpenedDetailKey),
        ),
        id: "page-opened",
      },
    ]);
  }, [t, setActivityLog, pageOpenedKey, pageOpenedDetailKey]);
}
