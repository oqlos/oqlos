import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import SharedNav from "../components/SharedNav";
import SidebarList from "../components/SidebarList";
import UiNavLink from "../components/UiNavLink.jsx";
import { HardwareApi, formatHardwareApiError } from "../api/hardwareApi";
import { useI18n } from "../i18n/I18nProvider";
import { persistUiUrlArgsToCookie } from "../utils/ui-url-args-cookie.js";
import { readModbusProfileFromSearch } from "../utils/modbus-profiles.js";
import { formatRtcSummaryValue } from "../utils/rtc-summary.js";
import {
  buildRtcSidebarItems,
  patchRtcMenuSearchParams,
  readRtcMenuFromSearch,
  resolveRtcMenuCommand,
  resolveRtcMenuId,
} from "../utils/rtc-menu.js";

function SummaryRow({ label, value }) {
  return (
    <div className="hw-kv-row">
      <span className="hw-kv-label">{label}</span>
      <strong>{value ?? "—"}</strong>
    </div>
  );
}

export default function HardwareRtc() {
  const { t } = useI18n();
  const [searchParams, setSearchParams] = useSearchParams();
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [busyCommand, setBusyCommand] = useState("");
  const [lastResult, setLastResult] = useState(null);

  const activeMenuId = resolveRtcMenuId(
    readRtcMenuFromSearch(searchParams.toString()),
    "overview",
  );
  const activeCommand = resolveRtcMenuCommand(activeMenuId);
  const sidebarItems = useMemo(() => buildRtcSidebarItems(t), [t]);

  const syncMenuUrl = useCallback((menuId) => {
    setSearchParams((prev) => patchRtcMenuSearchParams(prev, menuId), { replace: true });
    persistUiUrlArgsToCookie({ submenu: menuId === "overview" ? null : menuId });
  }, [setSearchParams]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const payload = await HardwareApi.getRtcStatus({ logContext: "rtc-status" });
      setStatus(payload);
    } catch (err) {
      setStatus(null);
      setError(formatHardwareApiError(err, t("hardwareRtc.loadFailed")));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (!readModbusProfileFromSearch(searchParams.toString())) return;
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("submenu");
      return next;
    }, { replace: true });
    persistUiUrlArgsToCookie({ submenu: null });
  }, [searchParams, setSearchParams]);

  const data = status?.result?.data || {};
  const connected = Boolean(data.connected);
  const optionalDisabled = status?.ok === false && String(status?.error || "").includes("RTC disabled");
  const mockMode = Boolean(data.mock);

  const summary = useMemo(() => ({
    connected: connected ? t("hardwareRtc.connectedYes") : t("hardwareRtc.connectedNo"),
    mock: data.mock ? t("hardwareRtc.mockYes") : t("hardwareRtc.mockNo"),
    time: formatRtcSummaryValue(data.time),
    temperature: formatRtcSummaryValue(data.temperature),
    watchdog: data.watchdog_available ? t("hardwareRtc.connectedYes") : t("hardwareRtc.connectedNo"),
    i2c: data.rtc_i2c_address ? `bus ${data.rtc_i2c_bus ?? "?"} @ ${data.rtc_i2c_address}` : "—",
  }), [connected, data, t]);

  const runCommand = useCallback(async (command) => {
    setBusyCommand(command);
    setError("");
    try {
      const result = await HardwareApi.runRtcCommand(command, {}, { logContext: `rtc-${command}` });
      setLastResult(result);
      if (command === "read_status" || command === "reinit") {
        await refresh();
      }
    } catch (err) {
      setLastResult(null);
      setError(formatHardwareApiError(err, t("hardwareRtc.commandFailed")));
    } finally {
      setBusyCommand("");
    }
  }, [refresh, t]);

  const selectMenu = useCallback((menuId) => {
    syncMenuUrl(menuId);
    const command = resolveRtcMenuCommand(menuId);
    if (menuId !== "overview") {
      runCommand(command);
    } else {
      setLastResult(null);
      refresh();
    }
  }, [refresh, runCommand, syncMenuUrl]);

  const navContext = (
    <div className="section-label" style={{ marginBottom: 0 }}>
      {t("hardwareRtc.navTitle")}
    </div>
  );

  return (
    <div className="mapx-shell">
      <SidebarList
        title={t("hardwareRtc.sidebarTitle")}
        items={sidebarItems}
        activeId={activeMenuId}
        onSelect={(id) => selectMenu(id)}
        collapseToggleId="hardware-rtc-menu"
        collapseLabel={t("hardwareRtc.sidebarTitle")}
        collapseStorageKey="ui.hardware-rtc-sidebar-collapsed"
        collapseIcon="🕒"
      />
      <div className="dashboard mapx-main-dashboard">
        <SharedNav navContext={navContext} />
        <div className="dash-content">
          <div className="mapx-header">
            <div>
              <h2>{t("hardwareRtc.pageTitle")}</h2>
              <p className="section-desc">{t("hardwareRtc.pageDesc")}</p>
            </div>
            <div className="mapx-header-actions">
              <button type="button" className="run-btn role-force" onClick={refresh} disabled={loading || busyCommand}>
                {loading ? t("hardwareRtc.refreshing") : t("hardwareRtc.refresh")}
              </button>
              {activeMenuId !== "overview" ? (
                <button
                  type="button"
                  className="run-btn role-force"
                  disabled={loading || Boolean(busyCommand)}
                  onClick={() => runCommand(activeCommand)}
                >
                  {busyCommand ? "…" : t("hardwareRtc.runSelected")}
                </button>
              ) : null}
              <UiNavLink className="run-btn role-force" to="/status" style={{ textDecoration: "none", display: "inline-flex", alignItems: "center" }}>
                {t("hardwareRtc.backToStatus")}
              </UiNavLink>
            </div>
          </div>

          {error ? <div className="mapx-error">{error}</div> : null}
          {optionalDisabled ? (
            <div className="section-desc">{t("hardwareRtc.disabledHint")}</div>
          ) : null}
          {mockMode ? (
            <div className="section-desc">{t("hardwareRtc.mockHint")}</div>
          ) : null}

          <div className="hw-grid">
            <div className="hw-card">
              <h3>{t("hardwareRtc.summary")}</h3>
              <SummaryRow label={t("hardwareRtc.fieldConnected")} value={summary.connected} />
              <SummaryRow label={t("hardwareRtc.fieldMock")} value={summary.mock} />
              <SummaryRow label={t("hardwareRtc.fieldTime")} value={summary.time} />
              <SummaryRow label={t("hardwareRtc.fieldTemperature")} value={summary.temperature} />
              <SummaryRow label={t("hardwareRtc.fieldWatchdog")} value={summary.watchdog} />
              <SummaryRow label={t("hardwareRtc.fieldI2c")} value={summary.i2c} />
            </div>
            <div className="hw-card">
              <h3>{t("hardwareRtc.activeSection")}</h3>
              <p className="section-desc">{sidebarItems.find((item) => item.id === activeMenuId)?.title || activeMenuId}</p>
              {activeMenuId === "overview" ? (
                <p className="section-desc">{t("hardwareRtc.overviewHint")}</p>
              ) : (
                <p className="section-desc">{t("hardwareRtc.commandHint", { command: activeCommand })}</p>
              )}
            </div>
          </div>

          <div className="hw-card" style={{ marginTop: 12 }}>
            <h3>{t("hardwareRtc.statusJson")}</h3>
            <pre className="hw-pre">{status ? JSON.stringify(status, null, 2) : t("hardwareRtc.loading")}</pre>
          </div>

          {lastResult ? (
            <div className="hw-card" style={{ marginTop: 12 }}>
              <h3>{t("hardwareRtc.lastResult")}</h3>
              <pre className="hw-pre">{JSON.stringify(lastResult, null, 2)}</pre>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
