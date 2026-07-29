const NOT_AVAILABLE_PATTERNS = /not available|all connection attempts failed|no active instance|permission denied|failed to connect|is not available|de-energized|deenergized|energized|stopped|transport off|timed out|disabled/i;

export function panelResultClass(envelope, status) {
  const result = envelope && typeof envelope.result === "object" && envelope.result ? envelope.result : null;
  const innerFailure = Boolean(result && (result.success === false || result.ok === false));
  if (status >= 200 && status < 300 && envelope && envelope.ok && !innerFailure) return "ok";
  if (status === 503 || innerFailure || NOT_AVAILABLE_PATTERNS.test(JSON.stringify(envelope || {}))) return "na";
  return "fail";
}

export function summarizePanelResult(envelope) {
  if (!envelope) return "brak odpowiedzi";
  const result = envelope.result;
  if (!result || typeof result !== "object") return envelope.error || (envelope.ok ? "OK" : "błąd");
  if ("devices" in result) {
    const devices = (result.devices || []).map((device) => `${device.vendor_id}:${device.product_id} ${device.product || device.vendor || ""}${device.tty && device.tty.length ? ` [${device.tty.join(",")}]` : ""} @${device.port_path}`);
    return `${result.count} urządzeń USB\n  · ${devices.join("\n  · ")}`;
  }
  if ("cpu_temp_c" in result) return `${result.model || "Pi"} · CPU ${result.cpu_temp_c}°C · USB×${result.usb_device_count} · porty: ${(result.serial_ports || []).join(", ") || "—"}`;
  if ("passed" in result) return `kroki: ${result.passed} OK / ${result.failed} błąd (z ${result.total || "?"})${result.errors && result.errors.length ? ` · ${result.errors.join("; ")}` : ""}`;
  if ("mode" in result) return `mode=${result.mode}${result.overall_ok !== undefined ? ` · overall_ok=${result.overall_ok}` : ""}`;
  if ("value" in result) return `${result.sensor_id || ""} = ${result.value}`;
  if ("reset" in result) return result.success ? `reset OK: ${result.reset || ""}` : `błąd: ${result.error || envelope.error || "?"}`;
  if ("success" in result) return result.success ? (result.data !== undefined ? JSON.stringify(result.data) : "success") : `błąd: ${result.error || envelope.error || "?"}`;
  return JSON.stringify(result).slice(0, 140);
}

export function createPanelResultLogEntry({ title, envelope, status, sent, request, now = new Date() }) {
  const cls = panelResultClass(envelope, status);
  const label = cls === "ok" ? "OK" : cls === "na" ? "N/D" : "BŁĄD";
  const hint = cls === "ok" ? "" : cls === "na" ? "sprzęt niedostępny / brak uprawnień — nie błąd panelu" : "realny błąd";
  return {
    id: `${now.getTime()}-${Math.random()}`,
    ts: now.toISOString(),
    time: now.toLocaleTimeString("pl-PL"),
    title,
    status,
    cls,
    label,
    hint,
    sent,
    recv: summarizePanelResult(envelope),
    raw: envelope,
    req: request,
  };
}
