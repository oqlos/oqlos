import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { HardwareApi, formatHardwareApiError } from "../api/hardwareApi";
import { useI18n } from "../i18n/I18nProvider";
import { adapterStatusBadgeClass } from "../utils/hardwareStatusModel.js";
import {
  filterMotorDiagnosis,
  filterMotorRepairs,
  MOTOR_DEVICE_IDS,
} from "../utils/motor-services-diagnosis.js";
import { readModbusProfileFromSearch } from "../utils/modbus-profiles.js";
import { persistUiUrlArgsToCookie } from "../utils/ui-url-args-cookie.js";
import { MotorHardwareDemoPanel } from "./HardwareDemo.jsx";

function DeviceCard({ device }) {
  const { t } = useI18n();
  if (!device) return null;
  return (
    <div className="hw-card">
      <h3>{device.display_name}</h3>
      <div className="hw-kv-row">
        <span className="hw-kv-label">{t("motorServices.status")}</span>
        <span className={adapterStatusBadgeClass(device.status)}>{device.status}</span>
      </div>
      <div className="hw-kv-row">
        <span className="hw-kv-label">{t("motorServices.message")}</span>
        <strong>{device.health_summary || "—"}</strong>
      </div>
      {device.issues?.length ? (
        <ul className="hw-issue-list">
          {device.issues.map((issue, idx) => (
            <li key={idx}>{issue}</li>
          ))}
        </ul>
      ) : null}
      {device.recommended_actions?.length ? (
        <div style={{ marginTop: 8 }}>
          <div className="hw-kv-label">{t("motorServices.recommendedActions")}</div>
          <ul className="hw-issue-list">
            {device.recommended_actions.map((action) => (
              <li key={action.id}>
                {action.label}
                {action.detail ? ` — ${action.detail}` : ""}
                {action.scope === "host" ? ` (${t("motorServices.hostScope")})` : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

export default function MotorServices() {
  const { t } = useI18n();
  const [searchParams, setSearchParams] = useSearchParams();
  const [diagnosis, setDiagnosis] = useState(null);
  const [repairResult, setRepairResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [repairing, setRepairing] = useState(false);

  useEffect(() => {
    if (!readModbusProfileFromSearch(searchParams.toString())) return;
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("submenu");
      return next;
    }, { replace: true });
    persistUiUrlArgsToCookie({ submenu: null });
  }, [searchParams, setSearchParams]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = filterMotorDiagnosis(await HardwareApi.getIntelligentDiagnosis({ devices: "motors" }));
      setDiagnosis(data);
    } catch (err) {
      setError(formatHardwareApiError(err, t("motorServices.loadFailed")));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const runRepair = useCallback(async () => {
    setRepairing(true);
    setError("");
    setRepairResult(null);
    try {
      const result = await HardwareApi.runDiagnosisRepair({ devices: "motors" });
      setRepairResult(result);
      setDiagnosis(filterMotorDiagnosis(result.device_diagnosis || null));
    } catch (err) {
      setError(formatHardwareApiError(err, t("motorServices.repairFailed")));
    } finally {
      setRepairing(false);
    }
  }, [t]);

  const devices = diagnosis?.devices || {};
  const motorRepairs = filterMotorRepairs(repairResult?.repairs);
  const mockHardware = String(diagnosis?.environment?.hardware_mode || "").toLowerCase() === "mock";

  const topActions = (
    <div className="mapx-header" style={{ marginBottom: 12 }}>
      <div>
        <h2 style={{ marginBottom: 4 }}>{t("motorServices.diagnosticsTitle")}</h2>
        <p className="section-desc" style={{ marginBottom: 0 }}>{t("motorServices.subtitle")}</p>
      </div>
      <div className="mapx-header-actions">
        <button type="button" className="run-btn role-force" onClick={refresh} disabled={loading}>
          {loading ? t("motorServices.refreshing") : t("motorServices.refresh")}
        </button>
        <button
          type="button"
          className="run-btn role-force"
          onClick={runRepair}
          disabled={repairing}
          style={{ marginLeft: 8 }}
        >
          {repairing ? t("motorServices.repairing") : t("motorServices.repairNow")}
        </button>
      </div>
    </div>
  );

  const beforeContent = (
    <>
      {error ? <div className="mapx-error">{error}</div> : null}
      {mockHardware ? (
        <div className="section-desc">{t("motorServices.mockHint")}</div>
      ) : null}
      <div className="hw-grid">
        {MOTOR_DEVICE_IDS.map((id) => (
          <DeviceCard key={id} device={devices[id]} />
        ))}
      </div>
      {repairResult ? (
        <div className="hw-card" style={{ marginTop: 12, marginBottom: 16 }}>
          <h3>{t("motorServices.lastRepairResult")}</h3>
          <ul className="hw-issue-list">
            {motorRepairs.length === 0 ? (
              <li>{t("motorServices.noRepairsNeeded")}</li>
            ) : (
              motorRepairs.map((r, idx) => (
                <li key={idx}>
                  <strong>{r.step}</strong>: {r.ok ? t("motorServices.ok") : t("motorServices.failed")}
                  {r.method ? ` (${r.method})` : ""}
                  {r.error ? ` — ${r.error}` : ""}
                  {r.hint ? ` — ${r.hint}` : ""}
                </li>
              ))
            )}
          </ul>
        </div>
      ) : null}
      <h3 style={{ marginTop: 8, marginBottom: 4 }}>{t("motorServices.manualTestTitle")}</h3>
      <p className="section-desc" style={{ marginTop: 0 }}>{t("motorServices.manualTestSubtitle")}</p>
    </>
  );

  return (
    <MotorHardwareDemoPanel
      navTitleKey="motorServices.title"
      hidePageHeader
      topActions={topActions}
      beforeContent={beforeContent}
      sidebarCollapseToggleId="motor-services-devices"
      sidebarCollapseStorageKey="ui.motor-services-sidebar-collapsed"
    />
  );
}
