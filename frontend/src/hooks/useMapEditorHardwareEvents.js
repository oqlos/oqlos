import { useEffect, useState } from "react";
import {
  buildHardwareEventsWsUrl,
  normalizeHardwareEvent,
} from "../utils/hardwareEventStream.js";
import { LIVE_EVENTS_LIMIT } from "../pages/mapEditorConstants.js";

export function useMapEditorHardwareEvents(t, { limit = LIVE_EVENTS_LIMIT } = {}) {
  const [hardwareEvents, setHardwareEvents] = useState([]);
  const [eventsWsState, setEventsWsState] = useState("idle");
  const [eventsWsError, setEventsWsError] = useState("");

  useEffect(() => {
    const wsUrl = buildHardwareEventsWsUrl({ wsUrlEnv: import.meta.env.VITE_WS_URL });
    let closed = false;
    let socket = null;
    try {
      setEventsWsState("connecting");
      socket = new WebSocket(wsUrl);
    } catch {
      setEventsWsState("error");
      setEventsWsError(t("mapEditor.liveEventsWsError"));
      return undefined;
    }

    socket.onopen = () => {
      if (closed) return;
      setEventsWsState("live");
      setEventsWsError("");
    };
    socket.onmessage = (event) => {
      if (closed) return;
      try {
        const message = JSON.parse(event.data);
        if (message?.message_type !== "event" || !message?.data) return;
        const normalized = normalizeHardwareEvent(message.data);
        setHardwareEvents((prev) => [...prev, normalized].slice(-limit));
      } catch {
        // ignore non-json or heartbeat messages
      }
    };
    socket.onerror = () => {
      if (closed) return;
      setEventsWsState("error");
      setEventsWsError(t("mapEditor.liveEventsWsError"));
    };
    socket.onclose = () => {
      if (closed) return;
      setEventsWsState("closed");
    };

    return () => {
      closed = true;
      if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
        socket.close();
      }
    };
  }, [t, limit]);

  return { hardwareEvents, setHardwareEvents, eventsWsState, eventsWsError, setEventsWsError };
}
