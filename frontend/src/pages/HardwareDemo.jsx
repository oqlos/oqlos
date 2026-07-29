import { useMemo } from "react";
import { useI18n } from "../i18n/I18nProvider";
import SharedNav from "../components/SharedNav";
import SidebarList from "../components/SidebarList";
import HardwareActivityLog from "../components/HardwareActivityLog";
import { rem } from "../utils/designRem.js";
import { DEVICES, NOTE_KEYS, NOTES, useMotorDemoControls } from "../hooks/useMotorDemoControls.js";

// ── Motor test panel (keyboard, melodies, activity log) ────────────────────
export function MotorHardwareDemoPanel({
  navTitleKey = "hardwareDemo.title",
  pageTitleKey = "hardwareDemo.pageTitle",
  subtitleKey = "hardwareDemo.subtitle",
  beforeContent = null,
  topActions = null,
  hidePageHeader = false,
  sidebarCollapseToggleId = "hardware-demo-devices",
  sidebarCollapseStorageKey = "ui.hardware-demo-sidebar-collapsed",
}) {
  const { t } = useI18n();
  const deviceMeta = useMemo(
    () => ({
      "motor-dri0050": {
        label: t("hardwareDemo.pumpLabel"),
        short: "Pump",
        description: t("hardwareDemo.pumpDesc"),
      },
      "motor-tic249": {
        label: t("hardwareDemo.stepperLabel"),
        short: "Stepper",
        description: t("hardwareDemo.stepperDesc"),
      },
    }),
    [t],
  );
  const {
    activeNote, activityLog, audioOn, device, deviceId, deviceStatus, hwOn, melodies,
    onNoteClick, playMelody, playingMelody, setAudioOn, setDeviceId, setHwOn, stopMelody,
  } = useMotorDemoControls(t);
  const deviceLabel = deviceMeta[deviceId]?.label || device.label;
  const deviceDescription = deviceMeta[deviceId]?.description || device.description;


  const currentBadge = useMemo(() => {
    const s = deviceStatus[deviceId];
    if (s === "ok") return "hw-badge hw-badge-ok";
    if (s === "no-access" || s === "error") return "hw-badge hw-badge-err";
    return "hw-badge hw-badge-warn";
  }, [deviceStatus, deviceId]);

  const sidebarItems = Object.keys(DEVICES).map((id) => ({
    id,
    title: deviceMeta[id]?.label || DEVICES[id].label,
    subtitle: deviceStatus[id] || "unknown",
  }));

  const navContext = (
    <div className="section-label" style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: 0 }}>
      <span>{t(navTitleKey)}</span>
    </div>
  );

  return (
    <div className="mapx-shell">
      <SidebarList
        title={t("hardwareDemo.sidebarTitle")}
        items={sidebarItems}
        activeId={deviceId}
        onSelect={(id) => {
          if (!playingMelody) setDeviceId(id);
        }}
        collapseToggleId={sidebarCollapseToggleId}
        collapseLabel={t("hardwareDemo.sidebarTitle")}
        collapseStorageKey={sidebarCollapseStorageKey}
      />
      <div className="dashboard mapx-main-dashboard">
        <SharedNav navContext={navContext} />
        <div className="dash-content">
          {topActions}
          {beforeContent}
          {!hidePageHeader ? (
            <>
              <h2>{t(pageTitleKey)}</h2>
              <p className="section-desc">
                {t(subtitleKey)}
              </p>
            </>
          ) : null}

          {/* ── Device selector + status row ───────────────────────────── */}
          <div
            className="hw-card"
            style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 12 }}
          >
            <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
              <span><strong>{t("hardwareDemo.deviceLabel")}:</strong> {deviceLabel}</span>
              <span className={currentBadge}>{deviceStatus[deviceId] || "loading"}</span>

              <label
                style={{ display: "flex", gap: 6, alignItems: "center", marginLeft: 16 }}
              >
                <input
                  type="checkbox"
                  checked={audioOn}
                  onChange={(e) => setAudioOn(e.target.checked)}
                />
                {t("hardwareDemo.audioLabel")}
              </label>
              <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={hwOn}
                  onChange={(e) => setHwOn(e.target.checked)}
                />
                {t("hardwareDemo.hardwareLabel", { short: device.short })}
              </label>
            </div>
            <div className="hw-runtime-note">{deviceDescription}</div>
            {deviceStatus["motor-dri0050"] &&
              deviceStatus["motor-dri0050"] !== "ok" &&
              deviceId === "motor-dri0050" && (
                <div className="hw-runtime-note" style={{ color: "var(--text-warn, #ffa726)" }}>
                  {t("hardwareDemo.pumpWarn", { status: deviceStatus["motor-dri0050"] })}
                  {deviceStatus["motor-tic249"] === "ok" ? t("hardwareDemo.stepperHint") : ""}
                </div>
              )}
          </div>

          {/* ── Keyboard ───────────────────────────────────────────────── */}
          <div className="hw-card" style={{ marginTop: 12 }}>
            <h3>{t("hardwareDemo.keyboardTitle")}</h3>
            <div
              style={{
                display: "flex",
                gap: 8,
                marginTop: 12,
                flexWrap: "wrap",
              }}
            >
              {NOTE_KEYS.map((key) => {
                const note = NOTES[key];
                const isActive = activeNote === key;
                const { args } = device.noteCommand(note, 500);
                const subline =
                  deviceId === "motor-dri0050"
                    ? `${note.freq.toFixed(0)} Hz · ${args.power_pct}%`
                    : `${note.freq.toFixed(0)} Hz · ${args.steps}st @ ${args.speed}`;
                return (
                  <button
                    key={key}
                    onClick={() => onNoteClick(key)}
                    disabled={Boolean(playingMelody)}
                    className="run-btn role-force"
                    style={{
                      minWidth: 78,
                      height: 96,
                      flexDirection: "column",
                      display: "flex",
                      justifyContent: "space-between",
                      padding: "10px 8px",
                      fontSize: rem.xl,
                      transform: isActive ? "translateY(2px) scale(0.98)" : "none",
                      boxShadow: isActive
                        ? "inset 0 0 0 3px var(--accent, #ff5722)"
                        : undefined,
                      transition: "transform 80ms, box-shadow 80ms",
                    }}
                  >
                    <strong style={{ fontSize: rem.display }}>{note.name}</strong>
                    <span style={{ fontSize: rem.xxs, opacity: 0.75, lineHeight: 1.2 }}>{subline}</span>
                  </button>
                );
              })}
            </div>
            <div className="hw-runtime-note" style={{ marginTop: 10 }}>
              {deviceId === "motor-dri0050"
                ? t("hardwareDemo.mappingPump")
                : t("hardwareDemo.mappingStepper")}
            </div>
          </div>

          {/* ── Preset melodies ────────────────────────────────────────── */}
          <div className="hw-card" style={{ marginTop: 16 }}>
            <h3>{t("hardwareDemo.melodiesTitle")}</h3>
            <div
              style={{
                display: "flex",
                gap: 8,
                marginTop: 12,
                flexWrap: "wrap",
              }}
            >
              {Object.entries(melodies).map(([k, m]) => {
                const isPlaying = playingMelody === k;
                return (
                  <button
                    key={k}
                    onClick={() => playMelody(k)}
                    disabled={Boolean(playingMelody) && !isPlaying}
                    className="run-btn role-force"
                    style={{
                      minWidth: 200,
                      transform: isPlaying ? "scale(0.98)" : "none",
                      boxShadow: isPlaying
                        ? "inset 0 0 0 3px var(--accent, #ff5722)"
                        : undefined,
                    }}
                  >
                    {isPlaying ? t("hardwareDemo.playing") : `🎼 ${m.title}`}
                  </button>
                );
              })}
              {playingMelody && (
                <button onClick={stopMelody} className="run-btn role-force" style={{ minWidth: 120 }}>
                  {t("hardwareDemo.stop")}
                </button>
              )}
            </div>
          </div>

          <HardwareActivityLog entries={activityLog} />
        </div>
      </div>
    </div>
  );
}
