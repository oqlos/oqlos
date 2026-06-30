import { useCallback, useEffect, useMemo, useState } from "react";
import SharedNav from "../components/SharedNav";
import HardwareActivityLog from "../components/HardwareActivityLog";
import { HardwareApi, formatHardwareApiError } from "../api/hardwareApi";
import { useI18n } from "../i18n/I18nProvider";
import {
  prependHardwareActivityLogEntry,
  usePageOpenedLog,
} from "../utils/hardware-activity-log.js";
import {
  adapterStatusBadgeClass,
  extractHardwareDiagnostics,
  formatHardwareJson,
  hardwareStatusSummary,
  listHardwareAdapters,
} from "../utils/hardwareStatusModel.js";

function SummaryRow({ label, value }) {
  return (
    <div className="hw-kv-row">
      <span className="hw-kv-label">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default function HardwareStatus() {
  const { t } = useI18n();
  const [health, setHealth] = useState(null);
  const [identify, setIdentify] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [activityLog, setActivityLog] = useState([]);

  usePageOpenedLog(
    t,
    setActivityLog,
    "hardware.log.pageOpened",
    "hardware.log.pageOpenedDetail",
  );

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    setActivityLog((prev) =>
      prependHardwareActivityLogEntry(
        prev,
        "info",
        t("hardware.log.refreshStarted"),
        t("hardware.log.refreshStartedDetail"),
      ),
    );
    const startedAt = performance.now();
    try {
      const [healthPayload, identifyPayload] = await Promise.all([
        HardwareApi.health(),
        HardwareApi.identify(),
      ]);
      setHealth(healthPayload);
      setIdentify(identifyPayload);
      const durationMs = Math.round(performance.now() - startedAt);
      setActivityLog((prev) =>
        prependHardwareActivityLogEntry(
          prev,
          "ok",
          t("hardware.log.refreshFinished"),
          t("hardware.log.requestCompleted", { label: "health+identify", ms: String(durationMs) }),
        ),
      );
    } catch (err) {
      const durationMs = Math.round(performance.now() - startedAt);
      const message = formatHardwareApiError(err, t("hardware.runtimeStatusFailed"));
      setError(message);
      setActivityLog((prev) =>
        prependHardwareActivityLogEntry(
          prev,
          "error",
          t("hardware.log.refreshFinishedWarn"),
          t("hardware.log.requestFailed", { label: "health+identify", ms: String(durationMs) }),
        ),
      );
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const summary = useMemo(() => hardwareStatusSummary(health, identify), [health, identify]);
  const adapters = useMemo(() => listHardwareAdapters(identify), [identify]);
  const diagnostics = useMemo(() => extractHardwareDiagnostics(identify), [identify]);

  const navContext = (
    <div className="section-label" style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: 0 }}>
      <span>{t("hardware.title")}</span>
    </div>
  );

  return (
    <div className="dashboard">
      <SharedNav navContext={navContext} />
      <div className="dash-content">
        <div className="mapx-header">
          <div>
            <h2>{t("hardware.title")}</h2>
            <p className="section-desc">{t("hardware.subtitle")}</p>
          </div>
          <div className="mapx-header-actions">
            <button
              type="button"
              className="run-btn role-force"
              onClick={refresh}
              disabled={loading}
            >
              {loading ? t("hardware.refreshing") : t("hardware.refresh")}
            </button>
          </div>
        </div>

        {error ? <div className="mapx-error">{error}</div> : null}

        <div className="hw-grid">
          <div className="hw-card">
            <h3>{t("hardware.summary")}</h3>
            <SummaryRow label={t("hardware.mode")} value={summary.mode} />
            <SummaryRow label={t("hardware.detected")} value={String(summary.detected)} />
            <SummaryRow label={t("hardware.total")} value={String(summary.total)} />
            <SummaryRow label={t("hardware.transport")} value={summary.transport} />
          </div>
          <div className="hw-card">
            <h3>{t("hardware.healthJson")}</h3>
            <pre className="hw-pre">{health ? formatHardwareJson(health) : t("hardware.loading")}</pre>
          </div>
        </div>

        <div className="hw-card" style={{ marginTop: 12 }}>
          <h3>{t("hardware.adapters")}</h3>
          <div className="hw-table-wrap">
            <table className="hw-table">
              <thead>
                <tr>
                  <th>{t("hardware.tableId")}</th>
                  <th>{t("hardware.tableName")}</th>
                  <th>{t("hardware.tableProtocol")}</th>
                  <th>{t("hardware.tableStatus")}</th>
                </tr>
              </thead>
              <tbody>
                {adapters.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="hw-muted-cell">
                      {loading ? t("hardware.loading") : t("hardware.noAdapterData")}
                    </td>
                  </tr>
                ) : (
                  adapters.map((adapter) => (
                    <tr key={adapter.id || adapter.name}>
                      <td>{adapter.id || "—"}</td>
                      <td>{adapter.name || "—"}</td>
                      <td>{adapter.protocol || "—"}</td>
                      <td>
                        <span className={adapterStatusBadgeClass(adapter.status)}>
                          {adapter.status || "unknown"}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="hw-grid" style={{ marginTop: 12 }}>
          <div className="hw-card">
            <h3>{t("hardware.serialPorts")}</h3>
            <pre className="hw-pre">{formatHardwareJson(diagnostics.serialPorts)}</pre>
          </div>
          <div className="hw-card">
            <h3>{t("hardware.i2cBuses")}</h3>
            <pre className="hw-pre">{formatHardwareJson(diagnostics.i2cBuses)}</pre>
          </div>
        </div>

        <div className="hw-card" style={{ marginTop: 12 }}>
          <h3>{t("hardware.usbDevices")}</h3>
          <pre className="hw-pre">{formatHardwareJson(diagnostics.usbDevices)}</pre>
        </div>

        <HardwareActivityLog entries={activityLog} />
      </div>
    </div>
  );
}
