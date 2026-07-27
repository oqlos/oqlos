export function formatRtcSummaryValue(value) {
  if (value == null || value === "") return "—";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (typeof value !== "object") return String(value);

  if (typeof value.time === "string" && value.time) return value.time;
  if (
    Number.isFinite(value.hour)
    && Number.isFinite(value.minute)
    && Number.isFinite(value.second)
  ) {
    return [value.hour, value.minute, value.second]
      .map((part) => String(part).padStart(2, "0"))
      .join(":");
  }
  if (typeof value.temperature === "number") return String(value.temperature);

  return JSON.stringify(value);
}
