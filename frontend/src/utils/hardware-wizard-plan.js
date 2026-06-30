/** Plan load failures when connect-scenario-backend cannot reach OqlOS :8202. */
export function isOqlosUnreachableError(message) {
  const normalized = String(message || "").toLowerCase();
  return (
    normalized.includes("cannot reach oqlos")
    || normalized.includes("all connection attempts failed")
    || normalized.includes("oqlos unavailable")
    || normalized.includes("connection refused")
  );
}
