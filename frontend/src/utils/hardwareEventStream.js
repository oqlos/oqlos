function normalizeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

export function buildHardwareEventsWsUrl({ wsUrlEnv = "", locationLike = globalThis.location } = {}) {
  const envValue = normalizeText(wsUrlEnv);
  if (envValue) {
    const clean = envValue.replace(/\/+$/, "");
    if (clean.endsWith("/ws/events/hardware")) return clean;
    if (clean.endsWith("/ws")) return `${clean}/events/hardware`;
    return `${clean}/ws/events/hardware`;
  }

  const location = locationLike && typeof locationLike === "object" ? locationLike : null;
  const host = normalizeText(location?.host);
  const protocol = normalizeText(location?.protocol);
  const wsProtocol = protocol === "https:" ? "wss" : "ws";
  return `${wsProtocol}://${host || "localhost"}/ws/events/hardware`;
}

export function normalizeHardwareEvent(rawEvent) {
  const source = rawEvent && typeof rawEvent === "object" ? rawEvent : {};
  const data = source.data && typeof source.data === "object" ? source.data : {};
  const command = data.command && typeof data.command === "object" ? data.command : {};
  const payload = command.payload && typeof command.payload === "object" ? command.payload : {};
  const result = data.result && typeof data.result === "object" ? data.result : null;
  const peripheralId = normalizeText(data.peripheral_id) || normalizeText(payload.peripheral_id);
  const commandName = normalizeText(data.command_name) || normalizeText(payload.command);
  const timestamp = normalizeText(source.timestamp) || new Date().toISOString();
  const id = normalizeText(source.id) || normalizeText(source.event_id) || `${timestamp}:${peripheralId}:${commandName}`;
  let status = "unknown";
  if (result) {
    if (result.ok === false || result.success === false) status = "error";
    else if (result.ok === true || result.success === true) status = "ok";
  }
  return { id, timestamp, peripheralId, commandName, status, raw: source };
}

export function matchesHardwareEventFilters(eventItem, peripheralFilter, commandFilter) {
  const peripheralQuery = normalizeText(peripheralFilter).toLowerCase();
  const commandQuery = normalizeText(commandFilter).toLowerCase();
  if (!eventItem || typeof eventItem !== "object") return false;
  if (peripheralQuery && !String(eventItem.peripheralId || "").toLowerCase().includes(peripheralQuery)) return false;
  if (commandQuery && !String(eventItem.commandName || "").toLowerCase().includes(commandQuery)) return false;
  return true;
}

