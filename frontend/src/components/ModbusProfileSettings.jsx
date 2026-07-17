import { useI18n } from "../i18n/I18nProvider";
import { rem } from "@semcod/frontend-services/designRem.js";
import { MODBUS_PROFILE_DESC_KEYS, probeSequenceLabel } from "../utils/modbus-profiles.js";

export default function ModbusProfileSettings({
  profileId,
  profile,
  baudOptions,
  targetBaudDraft,
  serialPortDraft,
  onTargetBaudChange,
  onSerialPortChange,
  onSave,
  busy,
  settingsStatus,
  baselineBaud = 9600,
}) {
  const { t } = useI18n();
  const deviceIds = Array.isArray(profile?.device_ids) ? profile.device_ids.join(", ") : "—";

  return (
    <div className="hw-card" style={{ marginBottom: "12px" }}>
      <h3>{t("hardwareRestart.profileSettingsTitle")}</h3>
      <p style={{ margin: "0 0 10px", color: "var(--text-secondary)", fontSize: rem.sm }}>
        {t(MODBUS_PROFILE_DESC_KEYS[profileId] || "hardwareRestart.profileAdcDesc")}
      </p>
      <div className="hw-kv">
        <span>{t("hardwareRestart.profileTopology")}</span>
        <strong>{profile?.topology || "—"}</strong>
      </div>
      <label className="hw-kv" style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
        <span>{t("hardwareRestart.serialPort")}</span>
        <input
          type="text"
          value={serialPortDraft}
          onChange={(e) => onSerialPortChange(e.target.value)}
          disabled={busy}
          placeholder="/dev/ttyUSB0"
          style={{
            flex: 1,
            minWidth: "180px",
            fontFamily: "var(--font-mono)",
            fontSize: rem.sm,
          }}
        />
      </label>
      <div className="hw-kv">
        <span>{t("hardwareRestart.targetIds")}</span>
        <strong>{deviceIds}</strong>
      </div>
      <div className="hw-kv">
        <span>{t("hardwareRestart.baselineBaud")}</span>
        <strong>{profile?.baseline_baudrate || baselineBaud}</strong>
      </div>
      <div className="hw-kv">
        <span>{t("hardwareRestart.probeSequence")}</span>
        <strong>{probeSequenceLabel(profile)}</strong>
      </div>
      <div className="hw-kv" style={{ display: "flex", gap: "12px", marginTop: "8px", flexWrap: "wrap", alignItems: "flex-start" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "6px", minWidth: "140px" }}>
          <span>{t("hardwareRestart.targetBaudSelect")}</span>
          <select
            value={targetBaudDraft}
            onChange={(e) => onTargetBaudChange(e.target.value)}
            disabled={busy}
            size={Math.max(3, baudOptions.length)}
            style={{
              minWidth: "140px",
              fontFamily: "var(--font-mono)",
              fontSize: rem.sm,
              padding: "4px",
            }}
            aria-label={t("hardwareRestart.targetBaudSelect")}
          >
            {baudOptions.map((baud) => (
              <option key={baud} value={String(baud)}>
                {baud}{baud === 9600 ? ` (${t("hardwareRestart.baudDefault")})` : ""}
              </option>
            ))}
          </select>
        </div>
        <button className="run-btn role-force" type="button" onClick={onSave} disabled={busy} style={{ marginTop: "22px" }}>
          {t("hardwareRestart.saveProfile")}
        </button>
      </div>
      <p style={{ margin: "8px 0 0", color: "var(--text-secondary)", fontSize: rem.sm }}>
        {t("hardwareRestart.baudInitHint")}
      </p>
      {settingsStatus ? (
        <p style={{ margin: "8px 0 0", color: "var(--text-muted)", fontSize: rem.sm }}>{settingsStatus}</p>
      ) : null}
    </div>
  );
}
