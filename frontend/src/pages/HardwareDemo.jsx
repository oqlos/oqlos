import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useI18n } from "../i18n/I18nProvider";
import SharedNav from "../components/SharedNav";
import { HardwareApi, formatHardwareApiError } from "../api/hardwareApi";
import SidebarList from "../components/SidebarList";
import HardwareActivityLog from "../components/HardwareActivityLog";
import { rem } from "../utils/designRem.js";
import { createHardwareActivityLogEntry, prependHardwareActivityLogEntry, usePageOpenedLog } from "../utils/hardware-activity-log.js";
import { probeDemoDevices } from "../utils/hardware-demo-identify.js";

// ── Notes (C major) ──────────────────────────────────────────────────────────
// freq:  Hz — used by Web Audio oscillator (audible feedback on speakers)
// power: % — sent as power_pct to DRI0050 PWM driver. Higher pitch ≈ higher PWM
//             frequency, but current backend exposes only duty-cycle (0-100%).
//             We linearly map freq→duty so the motor whine pitch tracks notes.
const NOTES = {
  C4: { name: "C",  freq: 261.63, power: 26 },
  D4: { name: "D",  freq: 293.66, power: 30 },
  E4: { name: "E",  freq: 329.63, power: 33 },
  F4: { name: "F",  freq: 349.23, power: 35 },
  G4: { name: "G",  freq: 392.00, power: 39 },
  A4: { name: "A",  freq: 440.00, power: 44 },
  B4: { name: "B",  freq: 493.88, power: 49 },
  C5: { name: "C'", freq: 523.25, power: 52 },
};
const NOTE_KEYS = ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"];

// ── Devices ──────────────────────────────────────────────────────────────────
//  motor-dri0050  — pump, PWM, default device
//  motor-tic249   — Pololu Tic T249 stepper, fallback when pump is unreachable
const DEVICES = {
  "motor-dri0050": {
    label: "Pompa DRI0050 (PWM)",
    short: "Pump",
    description:
      "PWM motor driver — pitch sterowany duty-cycle (0-100%). Każda nuta = pump_set { power_pct }.",
    // Build args per note for this device. Returns { command, args }.
    noteCommand: (note /*, durationMs */) => ({
      command: "pump_set",
      args: { power_pct: note.power },
    }),
    stopCommand: () => ({ command: "pump_off", args: {} }),
  },
  "motor-tic249": {
    label: "Silnik krokowy Tic T249",
    short: "Stepper",
    description:
      "Pololu Tic T249 — pitch = step rate (każdy krok generuje słyszalne kliknięcie). " +
      "Mapowanie: speed = freq steps/s, steps ≈ freq × duration_sec.",
    noteCommand: (note, durationMs, direction = "right") => ({
      command: "move_relative",
      args: {
        direction,
        steps: Math.max(20, Math.round(note.freq * (durationMs / 1000))),
        speed: Math.max(1, Math.round(note.freq)),
        speed_unit: "steps/s",
        acceleration: 100,
        acceleration_unit: "%/s",
      },
    }),
    stopCommand: () => ({ command: "stop", args: {} }),
  },
};

// ── Preset melodies (note + duration_ms) ─────────────────────────────────────
const MELODY_DEFS = {
  twinkle: {
    titleKey: "hardwareDemo.melody.twinkle",
    bpm: 120,
    notes: [
      ["C4", 500], ["C4", 500], ["G4", 500], ["G4", 500],
      ["A4", 500], ["A4", 500], ["G4", 1000],
      ["F4", 500], ["F4", 500], ["E4", 500], ["E4", 500],
      ["D4", 500], ["D4", 500], ["C4", 1000],
    ],
  },
  "ode-to-joy": {
    titleKey: "hardwareDemo.melody.ode_to_joy",
    bpm: 120,
    notes: [
      ["E4", 400], ["E4", 400], ["F4", 400], ["G4", 400],
      ["G4", 400], ["F4", 400], ["E4", 400], ["D4", 400],
      ["C4", 400], ["C4", 400], ["D4", 400], ["E4", 400],
      ["E4", 600], ["D4", 200], ["D4", 800],
    ],
  },
  "wlazl-kotek": {
    titleKey: "hardwareDemo.melody.wlazl_kotek",
    bpm: 110,
    notes: [
      ["E4", 400], ["C4", 400], ["E4", 400], ["C4", 400],
      ["G4", 400], ["F4", 400], ["E4", 800],
      ["D4", 400], ["F4", 400], ["E4", 400], ["D4", 400],
      ["C4", 800],
    ],
  },
  scale: {
    titleKey: "hardwareDemo.melody.scale",
    bpm: 120,
    notes: NOTE_KEYS.map((n) => [n, 350]),
  },
};

// ── Web Audio helper ─────────────────────────────────────────────────────────
function playToneOnSpeakers(ctx, freq, durationMs) {
  if (!ctx || !freq || durationMs <= 0) return;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = "square"; // similar timbre to PWM motor whine
  osc.frequency.value = freq;
  osc.connect(gain);
  gain.connect(ctx.destination);

  const now = ctx.currentTime;
  const end = now + Math.max(0.05, durationMs / 1000);
  // ADSR-like envelope (short attack/release to avoid clicks)
  gain.gain.setValueAtTime(0, now);
  gain.gain.linearRampToValueAtTime(0.15, now + 0.02);
  gain.gain.linearRampToValueAtTime(0.15, Math.max(now + 0.03, end - 0.04));
  gain.gain.linearRampToValueAtTime(0, end);

  osc.start(now);
  osc.stop(end + 0.02);
}

// ── Page ─────────────────────────────────────────────────────────────────────
export default function HardwareDemo() {
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
  // Device selection + status (per-device map)
  const [deviceId, setDeviceId] = useState("motor-dri0050"); // pump default
  const [deviceStatus, setDeviceStatus] = useState({}); // { "motor-dri0050": "ok"|"no-access"|... }

  const [activeNote, setActiveNote] = useState(null);
  const [playingMelody, setPlayingMelody] = useState(null);
  const [activityLog, setActivityLog] = useState([]);
  const [audioOn, setAudioOn] = useState(true); // play tone on speakers
  const [hwOn, setHwOn] = useState(true);       // send command to selected device

  const audioCtxRef = useRef(null);
  const stopRequestedRef = useRef(false);
  const lastCmdAtRef = useRef(0);
  const stepperDirectionRef = useRef("right");

  const device = DEVICES[deviceId];
  const deviceLabel = deviceMeta[deviceId]?.label || device.label;
  const deviceDescription = deviceMeta[deviceId]?.description || device.description;

  const melodies = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(MELODY_DEFS).map(([key, def]) => [
          key,
          { ...def, title: t(def.titleKey) },
        ]),
      ),
    [t],
  );

  const appendLog = useCallback((level, message, detail = "") => {
    setActivityLog((prev) => prependHardwareActivityLogEntry(prev, level, message, detail));
  }, []);

  usePageOpenedLog(t, setActivityLog, "hardwareDemo.log.pageOpened", "hardwareDemo.log.pageOpenedDetail");

  // Lazily create AudioContext on first user gesture (browser autoplay policy)
  const ensureAudioCtx = useCallback(() => {
    if (audioCtxRef.current) return audioCtxRef.current;
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) {
      appendLog("warn", t("hardwareDemo.log.webAudioUnavailable"), t("hardwareDemo.log.webAudioDetail"));
      return null;
    }
    audioCtxRef.current = new Ctx();
    return audioCtxRef.current;
  }, [appendLog, t]);

  // Probe both devices on mount, suggest fallback if pump is unavailable
  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const result = await probeDemoDevices({
          identify: () => HardwareApi.identify(),
          runDiagnosticCommand: (body) => HardwareApi.runDiagnosticCommand(body),
          deviceIds: Object.keys(DEVICES),
          formatError: formatHardwareApiError,
          appendLog,
          t,
          signal: controller.signal,
        });
        if (!result) return;
        setDeviceStatus(result.deviceStatus);
        if (result.fallbackDeviceId) {
          setDeviceId(result.fallbackDeviceId);
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        setDeviceStatus({ "motor-dri0050": "error", "motor-tic249": "error" });
        appendLog("error", t("hardwareDemo.log.identifyFailed"), formatHardwareApiError(err));
      }
    })();
    return () => controller.abort();
  }, [appendLog, t]);

  // ── Send a single hardware command for current device (throttled) ────────
  const sendDeviceNote = useCallback(
    async (note, durationMs) => {
      if (!hwOn) return;
      // Throttle to avoid command spam (browser → backend latency ~100-200 ms)
      const now = performance.now();
      if (now - lastCmdAtRef.current < 60) return;
      lastCmdAtRef.current = now;
      const direction = stepperDirectionRef.current === "right" ? "left" : "right";
      stepperDirectionRef.current = direction;
      const { command, args } = device.noteCommand(note, durationMs, direction);
      try {
        await HardwareApi.runDiagnosticCommand({
          peripheral_id: deviceId,
          command,
          args,
        });
      } catch (err) {
        appendLog("error", t("hardwareDemo.log.commandFailed", { command }), formatHardwareApiError(err));
        // Auto-fallback: if pump fails and stepper is ok, switch and retry
        if (deviceId === "motor-dri0050" && deviceStatus["motor-tic249"] === "ok") {
          appendLog("warn", t("hardwareDemo.log.pumpAutoSwitch", { command }), command);
          setDeviceId("motor-tic249");
          const fallbackDevice = DEVICES["motor-tic249"];
          const fb = fallbackDevice.noteCommand(note, durationMs, direction);
          try {
            await HardwareApi.runDiagnosticCommand({
              peripheral_id: "motor-tic249",
              command: fb.command,
              args: fb.args,
            });
            appendLog("ok", t("hardwareDemo.log.stepperFallbackOk"), `${fb.command} ${JSON.stringify(fb.args)}`);
          } catch (error_) {
            appendLog("error", t("hardwareDemo.log.stepperFallbackFail"), formatHardwareApiError(error_));
          }
        }
      }
    },
    [appendLog, device, deviceId, hwOn, deviceStatus, setDeviceId, t]
  );

  const sendDeviceStop = useCallback(async () => {
    if (!hwOn) return;
    const { command, args } = device.stopCommand();
    try {
      await HardwareApi.runDiagnosticCommand({
        peripheral_id: deviceId,
        command,
        args,
      });
    } catch {
      /* silent */
    }
  }, [device, deviceId, hwOn]);

  // ── Play a single note (used by keyboard click + melody iterator) ────────
  const playNote = useCallback(
    async (key, durationMs) => {
      const note = NOTES[key];
      if (!note) return;
      setActiveNote(key);
      const ctx = audioOn ? ensureAudioCtx() : null;
      if (ctx) playToneOnSpeakers(ctx, note.freq, durationMs);
      // Hardware command (parallel, fire-and-forget)
      sendDeviceNote(note, durationMs);
      // Hold for note duration
      await new Promise((r) => setTimeout(r, durationMs));
      setActiveNote(null);
    },
    [audioOn, ensureAudioCtx, sendDeviceNote]
  );

  // ── Manual keyboard click (single note) ───────────────────────────────────
  const onNoteClick = useCallback(
    async (key) => {
      ensureAudioCtx(); // unlock AudioContext on first user gesture
      const ctx = audioCtxRef.current;
      if (ctx && ctx.state === "suspended") {
        try {
          await ctx.resume();
        } catch {
          /* ignore */
        }
      }
      const note = NOTES[key];
      const { command, args } = device.noteCommand(note, 500);
      appendLog(
        "info",
        t("hardwareDemo.log.playNote", { name: note.name, short: device.short }),
        `${note.freq.toFixed(2)} Hz · ${command} ${JSON.stringify(args)}`,
      );
      await playNote(key, 500);
      sendDeviceStop();
    },
    [appendLog, device, ensureAudioCtx, playNote, sendDeviceStop, t]
  );

  // ── Play preset melody ────────────────────────────────────────────────────
  const playMelody = useCallback(
    async (melodyKey) => {
      if (playingMelody) return; // ignore concurrent press
      const melody = melodies[melodyKey];
      if (!melody) return;

      ensureAudioCtx();
      const ctx = audioCtxRef.current;
      if (ctx && ctx.state === "suspended") {
        try {
          await ctx.resume();
        } catch {
          /* ignore */
        }
      }

      stopRequestedRef.current = false;
      setPlayingMelody(melodyKey);
      appendLog(
        "info",
        t("hardwareDemo.log.playingMelody", { title: melody.title }),
        t("hardwareDemo.log.playingMelodyDetail", {
          count: String(melody.notes.length),
          short: device.short,
        }),
      );

      try {
        for (let i = 0; i < melody.notes.length; i += 1) {
          if (stopRequestedRef.current) {
            appendLog(
              "warn",
              t("hardwareDemo.log.melodyStopped"),
              t("hardwareDemo.log.melodyStoppedDetail", {
                at: String(i + 1),
                total: String(melody.notes.length),
              }),
            );
            break;
          }
          const [key, dur] = melody.notes[i];
          // eslint-disable-next-line no-await-in-loop
          await playNote(key, Math.max(120, dur - 40));
          // small gap between notes
          // eslint-disable-next-line no-await-in-loop
          await new Promise((r) => setTimeout(r, 40));
        }
        if (!stopRequestedRef.current) {
          appendLog("ok", t("hardwareDemo.log.finishedMelody", { title: melody.title }));
        }
      } finally {
        setPlayingMelody(null);
        sendDeviceStop();
      }
    },
    [appendLog, device, ensureAudioCtx, melodies, playNote, playingMelody, sendDeviceStop, t]
  );

  const stopMelody = useCallback(() => {
    stopRequestedRef.current = true;
  }, []);

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
      <span>{t("hardwareDemo.title")}</span>
    </div>
  );

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      <SidebarList
        title={t("hardwareDemo.sidebarTitle")}
        items={sidebarItems}
        activeId={deviceId}
        onSelect={(id) => {
          if (!playingMelody) setDeviceId(id);
        }}
        collapseToggleId="hardware-demo-devices"
        collapseLabel={t("hardwareDemo.sidebarTitle")}
        collapseStorageKey="ui.hardware-demo-sidebar-collapsed"
      />
      <div className="dashboard" style={{ flex: 1, overflow: "auto" }}>
        <SharedNav navContext={navContext} />
        <div className="dash-content">
          <h2>{t("hardwareDemo.pageTitle")}</h2>
          <p className="section-desc">
            {t("hardwareDemo.subtitle")}
          </p>

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
