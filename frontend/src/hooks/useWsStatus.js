import { useEffect, useState } from "react";
import { getWsClient } from "../api/wsClient";

/**
 * Returns the current WebSocket connection status and triggers initial connect.
 * @param {boolean} enabled When false, does not attempt to connect.
 */
export function useWsStatus(enabled = true) {
  const [online, setOnline] = useState(false);

  useEffect(() => {
    if (!enabled) return undefined;
    const client = getWsClient();
    const onOpen = () => setOnline(true);
    const onClose = () => setOnline(false);
    client.addEventListener("open", onOpen);
    client.addEventListener("close", onClose);
    client.connect().then(() => setOnline(client.connected)).catch(() => setOnline(false));
    return () => {
      client.removeEventListener("open", onOpen);
      client.removeEventListener("close", onClose);
    };
  }, [enabled]);

  return online;
}
