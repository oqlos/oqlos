/** Shared activity log panel for hardware demo/status pages. */
import { useI18n } from "../i18n/I18nProvider";

export default function HardwareActivityLog({ entries }) {
  const { t } = useI18n();

  return (
    <div className="hw-card" style={{ marginTop: 16 }}>
      <h3>{t("hardware.activityLog")}</h3>
      <div className="hw-log-list">
        {entries.map((entry) => (
          <div className={`hw-log-row hw-log-${entry.level}`} key={entry.id}>
            <span className="hw-log-time">{entry.time}</span>
            <span className="hw-log-level">{entry.level}</span>
            <span>
              <span>{entry.message}</span>
              {entry.detail ? <span className="hw-log-detail">{entry.detail}</span> : null}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
