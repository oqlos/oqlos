import { useCallback, useEffect, useMemo, useState } from "react";
import { HardwareApi, formatHardwareApiError } from "../api/hardwareApi";
import { useI18n } from "../i18n/I18nProvider";
import { rem } from "../utils/designRem.js";
const MODULE_LABEL_KEYS = {
  "modbus-io": "hardwareRestart.profileIo",
  "modbus-adc": "hardwareRestart.profileAdc",
};

function formatValue(row) {
  if (row.kind === "digital_output" || row.kind === "digital_input") {
    return row.value ? "1 / ON" : "0 / OFF";
  }
  if (row.value_scaled != null && row.unit) {
    return `${row.value} (${row.value_scaled} ${row.unit})`;
  }
  if (row.value_decoded && typeof row.value_decoded === "object") {
    const decoded = row.value_decoded;
    return `${row.value} → ${decoded.baudrate || "?"} baud ${decoded.parity || "?"}`;
  }
  return row.value == null ? "—" : String(row.value);
}

function ChannelTable({ title, rows, moduleRole, busy, onWrite, t }) {
  const [drafts, setDrafts] = useState({});

  useEffect(() => {
    setDrafts({});
  }, [rows]);

  if (!rows?.length) {
    return null;
  }

  return (
    <div style={{ marginTop: "12px" }}>
      <h4 style={{ margin: "0 0 8px", fontSize: rem.base }}>{title}</h4>
      <div className="hw-table-wrap">
        <table className="hw-table">
          <thead>
            <tr>
              <th>{t("hardwareRestart.channelLabel", "Kanał")}</th>
              <th>{t("hardwareRestart.channelType", "Typ")}</th>
              <th>{t("hardwareRestart.channelAddress", "Adres")}</th>
              <th>{t("hardwareRestart.channelValue", "Wartość")}</th>
              <th>{t("hardwareRestart.channelWrite", "Zapis")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const draftKey = `${row.id}:${row.address_hex}`;
              const draft = drafts[draftKey] ?? (row.kind === "digital_output" ? (row.value ? "1" : "0") : String(row.value ?? ""));
              return (
                <tr key={draftKey}>
                  <td>{row.label}</td>
                  <td>{row.register_type}</td>
                  <td><code>{row.address_hex}</code></td>
                  <td>{formatValue(row)}</td>
                  <td>
                    {row.writable && row.write ? (
                      <div style={{ display: "flex", gap: "6px", alignItems: "center", flexWrap: "wrap" }}>
                        <input
                          type="text"
                          value={draft}
                          disabled={busy}
                          onChange={(e) => setDrafts((prev) => ({ ...prev, [draftKey]: e.target.value }))}
                          style={{ width: "88px", fontFamily: "var(--font-mono)", fontSize: rem.sm }}
                        />
                        <button
                          type="button"
                          className="run-btn role-force"
                          disabled={busy}
                          onClick={() => onWrite(moduleRole, row.write, draft)}
                        >
                          {t("hardwareRestart.channelApply", "Zapisz")}
                        </button>
                      </div>
                    ) : (
                      <span className="hw-muted-cell">{t("hardwareRestart.channelReadOnly", "tylko odczyt")}</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function ModbusChannelInspector({ profileId, refreshToken = 0, busy = false }) {
  const { t } = useI18n();
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  const loadChannels = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const payload = await HardwareApi.getModbusProfileChannels(profileId, { logContext: `profile-channels:${profileId}` });
      setReport(payload);
    } catch (err) {
      setReport(null);
      setError(formatHardwareApiError(err, t("hardwareRestart.channelsLoadFailed", "Nie udało się odczytać kanałów Modbus.")));
    } finally {
      setLoading(false);
    }
  }, [profileId, t]);

  useEffect(() => {
    loadChannels();
  }, [loadChannels, refreshToken]);

  const handleWrite = useCallback(async (moduleRole, writeMeta, rawValue) => {
    setStatus("");
    setError("");
    try {
      const payload = {
        module_role: moduleRole,
        write_type: writeMeta.type,
        address: writeMeta.address,
        value: writeMeta.type === "coil" ? rawValue : Number(rawValue),
      };
      await HardwareApi.writeModbusChannelValue(payload, { logContext: `channel-write:${moduleRole}` });
      setStatus(t("hardwareRestart.channelWriteOk", "Zapisano wartość rejestru."));
      await loadChannels();
    } catch (err) {
      setError(formatHardwareApiError(err, t("hardwareRestart.channelWriteFailed", "Zapis rejestru nie powiódł się.")));
    }
  }, [loadChannels, t]);

  const modules = useMemo(() => report?.modules || [], [report]);

  return (
    <div className="hw-card" style={{ marginBottom: "12px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
        <h3 style={{ margin: 0 }}>{t("hardwareRestart.channelsTitle", "Kanały i rejestry")}</h3>
        <button type="button" className="run-btn role-force" onClick={loadChannels} disabled={busy || loading}>
          {loading ? t("hardwareRestart.channelsRefreshing", "Odświeżanie…") : t("hardwareRestart.channelsRefresh", "Odśwież kanały")}
        </button>
      </div>
      <p style={{ margin: "8px 0 0", color: "var(--text-secondary)", fontSize: rem.sm }}>
        {t("hardwareRestart.channelsDesc", "Wejścia/wyjścia i rejestry konfiguracyjne dla wybranego profilu. Zmiana rejestru wysyła zapis bezpośrednio do modułu.")}
      </p>
      {error ? <div className="mapx-error" style={{ marginTop: "8px" }}>{error}</div> : null}
      {status ? <div className="section-desc">{status}</div> : null}
      {modules.map((module) => (
        <div key={module.module_role} style={{ marginTop: "14px", borderTop: "1px solid var(--border-subtle, #2e3a48)", paddingTop: "12px" }}>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "baseline" }}>
            <strong>{t(MODULE_LABEL_KEYS[module.module_role] || module.module_role, module.module_role)}</strong>
            <span style={{ color: "var(--text-muted)", fontSize: rem.sm }}>{module.module_role}</span>
            <span style={{ color: "var(--text-muted)", fontSize: rem.sm }}>ID={module.device_id}</span>
            {module.serial_port ? <span style={{ color: "var(--text-muted)", fontSize: rem.sm }}>{module.serial_port}</span> : null}
            {!module.ok ? <span className="hw-badge hw-badge-err">{module.message || t("hardwareRestart.channelsUnavailable", "niedostępny")}</span> : null}
          </div>
          <ChannelTable
            title={t("hardwareRestart.configRegisters", "Rejestry konfiguracyjne")}
            rows={module.config_registers}
            moduleRole={module.module_role}
            busy={busy || loading}
            onWrite={handleWrite}
            t={t}
          />
          <ChannelTable
            title={t("hardwareRestart.ioChannels", "Wejścia / wyjścia")}
            rows={module.channels}
            moduleRole={module.module_role}
            busy={busy || loading}
            onWrite={handleWrite}
            t={t}
          />
        </div>
      ))}
    </div>
  );
}
