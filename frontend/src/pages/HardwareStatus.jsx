import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import SharedNav from "../components/SharedNav";
import SidebarList from "../components/SidebarList";
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
import { copyTextToClipboard } from "../utils/clipboard.js";
import { persistUiUrlArgsToCookie } from "../utils/ui-url-args-cookie.js";
import { readModbusProfileFromSearch } from "../utils/modbus-profiles.js";
import {
  buildStatusLogSidebarItems,
  patchStatusLogSearchParams,
  readStatusLogFromSearch,
  resolveStatusLogTitle,
} from "../utils/status-logs-menu.js";
import NodeNavigationPanel from "../components/NodeNavigationPanel.jsx";

function SummaryRow({ label, value }) {
  return (
    <div className="hw-kv-row">
      <span className="hw-kv-label">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function downloadJson(name, text) {
  const blob = new Blob([text], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export default function HardwareStatus() {
  const { t } = useI18n();
  const [searchParams, setSearchParams] = useSearchParams();
  const [health, setHealth] = useState(null);
  const [identify, setIdentify] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [activityLog, setActivityLog] = useState([]);
  const [copyStatus, setCopyStatus] = useState("");
  const [rebootArmed, setRebootArmed] = useState(false);
  const [rebooting, setRebooting] = useState(false);
  const [rebootStatus, setRebootStatus] = useState("");
  const [navRefreshToken, setNavRefreshToken] = useState(0);
  const [logIndex, setLogIndex] = useState(null);
  const [logIndexLoading, setLogIndexLoading] = useState(false);
  const [logIndexError, setLogIndexError] = useState("");
  const [logPayload, setLogPayload] = useState(null);
  const [logLoading, setLogLoading] = useState(false);
  const [logError, setLogError] = useState("");

  const activeLogId = readStatusLogFromSearch(searchParams.toString());
  const sidebarItems = useMemo(
    () => buildStatusLogSidebarItems(logIndex, t),
    [logIndex, t],
  );
  const activeLogTitle = useMemo(
    () => resolveStatusLogTitle(sidebarItems, activeLogId, t),
    [activeLogId, sidebarItems, t],
  );

  usePageOpenedLog(
    t,
    setActivityLog,
    "hardware.log.pageOpened",
    "hardware.log.pageOpenedDetail",
  );

  const syncLogUrl = useCallback((logId) => {
    setSearchParams((prev) => patchStatusLogSearchParams(prev, logId), { replace: true });
    persistUiUrlArgsToCookie({ log: logId || null });
  }, [setSearchParams]);

  const refreshLogIndex = useCallback(async () => {
    setLogIndexLoading(true);
    setLogIndexError("");
    try {
      const payload = await HardwareApi.listHardwareLogs({ logContext: "status-log-index" });
      setLogIndex(payload);
    } catch (err) {
      setLogIndex(null);
      setLogIndexError(formatHardwareApiError(err, t("hardware.statusLogs.loadFailed")));
    } finally {
      setLogIndexLoading(false);
    }
  }, [t]);

  const refreshActiveLog = useCallback(async (logId = activeLogId) => {
    if (!logId) {
      setLogPayload(null);
      setLogError("");
      return;
    }
    setLogLoading(true);
    setLogError("");
    try {
      const payload = await HardwareApi.readHardwareLog(logId, {
        lines: 300,
        logContext: `status-log:${logId}`,
      });
      if (!payload?.ok) {
        throw new Error(payload?.error || t("hardware.statusLogs.readFailed"));
      }
      setLogPayload(payload);
    } catch (err) {
      setLogPayload(null);
      setLogError(formatHardwareApiError(err, t("hardware.statusLogs.readFailed")));
    } finally {
      setLogLoading(false);
    }
  }, [activeLogId, t]);

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
      setNavRefreshToken((token) => token + 1);
    }
  }, [t]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    refreshLogIndex();
  }, [refreshLogIndex]);

  useEffect(() => {
    refreshActiveLog(activeLogId);
  }, [activeLogId, refreshActiveLog]);

  useEffect(() => {
    if (!readModbusProfileFromSearch(searchParams.toString())) return;
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("submenu");
      return next;
    }, { replace: true });
    persistUiUrlArgsToCookie({ submenu: null });
  }, [searchParams, setSearchParams]);

  const summary = useMemo(() => hardwareStatusSummary(health, identify), [health, identify]);
  const adapters = useMemo(() => listHardwareAdapters(identify), [identify]);
  const diagnostics = useMemo(() => extractHardwareDiagnostics(identify), [identify]);

  const copyAllJson = useCallback(async () => {
    const payload = JSON.stringify(
      {
        health,
        adapters,
        serial_ports: diagnostics.serialPorts,
        i2c_buses: diagnostics.i2cBuses,
        usb_devices: diagnostics.usbDevices,
      },
      null,
      2,
    );
    if (await copyTextToClipboard(payload)) {
      setCopyStatus(t("hardware.copyAllOk"));
    } else {
      downloadJson(`oqlos-hardware-status-${Date.now()}.json`, payload);
      setCopyStatus(t("hardware.copyAllDownload"));
    }
    setTimeout(() => setCopyStatus(""), 2500);
  }, [health, adapters, diagnostics, t]);

  const rebootHost = useCallback(async () => {
    if (!rebootArmed) {
      setRebootArmed(true);
      setTimeout(() => setRebootArmed(false), 5000);
      return;
    }
    setRebootArmed(false);
    setRebooting(true);
    setError("");
    try {
      const res = await HardwareApi.rebootHost();
      if (!res || res.ok === false) {
        setRebooting(false);
        setError(`${t("hardware.rebootHostFailed")}: ${(res && res.error) || ""}`);
        return;
      }
    } catch (err) {
      setRebooting(false);
      setError(formatHardwareApiError(err, t("hardware.rebootHostFailed")));
      return;
    }
    setRebootStatus(t("hardware.rebootHostScheduled"));
    const deadline = Date.now() + 240_000;
    await new Promise((resolve) => setTimeout(resolve, 15_000));
    while (Date.now() < deadline) {
      try {
        await HardwareApi.health();
        setRebootStatus(t("hardware.rebootHostBackOnline"));
        setRebooting(false);
        refresh();
        setTimeout(() => setRebootStatus(""), 5000);
        return;
      } catch {
        await new Promise((resolve) => setTimeout(resolve, 5000));
      }
    }
    setRebooting(false);
    setRebootStatus("");
    setError(t("hardware.rebootHostFailed"));
  }, [rebootArmed, refresh, t]);

  const selectLog = useCallback((logId) => {
    syncLogUrl(logId || "");
  }, [syncLogUrl]);

  const navContext = (
    <div className="section-label" style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: 0 }}>
      <span>{t("hardware.title")}</span>
    </div>
  );

  const statusDashboard = (
    <>
      <NodeNavigationPanel embedded refreshToken={navRefreshToken} />

      <div className="hw-section-divider" aria-hidden="true" />

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
    </>
  );

  const logViewer = (
    <div className="hw-card">
      <div className="mapx-header" style={{ marginBottom: 12 }}>
        <div>
          <h3 style={{ margin: 0 }}>{activeLogTitle}</h3>
          <p className="section-desc">
            {logPayload?.lines ? `${logPayload.lines} ${t("hardware.statusLogs.lines")}` : ""}
          </p>
        </div>
        <div className="mapx-header-actions">
          <button
            type="button"
            className="run-btn role-force"
            onClick={() => refreshActiveLog(activeLogId)}
            disabled={logLoading}
          >
            {logLoading ? t("hardware.refreshing") : t("hardware.statusLogs.refreshLog")}
          </button>
        </div>
      </div>
      {logError ? <div className="mapx-error">{logError}</div> : null}
      <pre className="hw-pre hw-log-view">
        {logLoading
          ? t("hardware.statusLogs.loading")
          : (logPayload?.text || t("hardware.statusLogs.empty"))}
      </pre>
    </div>
  );

  return (
    <div className="mapx-shell">
      <SidebarList
        title={t("hardware.statusLogs.sidebarTitle")}
        items={sidebarItems}
        activeId={activeLogId}
        onSelect={(id) => selectLog(id)}
        onRefresh={refreshLogIndex}
        collapseToggleId="hardware-status-logs"
        collapseLabel={t("hardware.statusLogs.sidebarTitle")}
        collapseStorageKey="ui.hardware-status-sidebar-collapsed"
        collapseIcon="📋"
      />
      <div className="dashboard mapx-main-dashboard">
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
              {!activeLogId ? (
                <>
                  <button
                    type="button"
                    className="run-btn role-force"
                    onClick={copyAllJson}
                    disabled={!health}
                    style={{ marginLeft: 8 }}
                  >
                    {t("hardware.copyJson")}
                  </button>
                  <button
                    type="button"
                    className="mapx-btn mapx-btn-danger"
                    onClick={rebootHost}
                    disabled={rebooting}
                    style={{ marginLeft: 8 }}
                  >
                    {rebootArmed ? t("hardware.rebootHostConfirm") : t("hardware.rebootHost")}
                  </button>
                </>
              ) : null}
            </div>
          </div>

          {error ? <div className="mapx-error">{error}</div> : null}
          {copyStatus ? <div className="section-desc">{copyStatus}</div> : null}
          {rebootStatus ? <div className="section-desc">{rebootStatus}</div> : null}
          {logIndexError ? <div className="mapx-error">{logIndexError}</div> : null}
          {logIndex?.dir && !activeLogId ? (
            <div className="section-desc">
              {logIndex.groups?.length
                ? t("hardware.statusLogs.dirHint", { dir: logIndex.dir })
                : t("hardware.statusLogs.dirMissing", { dir: logIndex.dir })}
            </div>
          ) : null}
          {logIndexLoading && !logIndex ? (
            <div className="section-desc">{t("hardware.statusLogs.loading")}</div>
          ) : null}

          {activeLogId ? logViewer : statusDashboard}
        </div>
      </div>
    </div>
  );
}
