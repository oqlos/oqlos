import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { HardwareApi, formatHardwareApiError } from "../api/hardwareApi";
import SharedNav from "../components/SharedNav";
import { useAppConfig } from "../context/AppConfigProvider";
import { useI18n } from "../i18n/I18nProvider";
import {
  M5_POLL_OFFLINE_INITIAL_MS,
  M5_POLL_ONLINE_MS,
  nextM5OfflinePollDelay,
} from "../utils/m5-out-polling.js";

const PLUGIN_ID = "io-m5-4in8out";
const OUTPUT_COUNT = 16;
const INPUT_COUNT = 8;

const COPY = {
  pl: {
    title: "M5Stack 4In8Out — wyjścia",
    subtitle:
      "Sterowanie przez LAN lub Wi-Fi 16 wyjściami MOSFET dwóch modułów I2C (0x45 i 0x66). Wejścia IN1–IN8 są tylko do odczytu.",
    refresh: "Odśwież stan",
    stop: "STOP — wyłącz wszystkie",
    allOn: "Załącz wszystkie",
    confirm:
      "Potwierdzam, że stanowisko jest zabezpieczone i obserwuję właściwy moduł wykonawczy.",
    roleBlocked: "Sterowanie wyjściami jest dostępne wyłącznie dla roli system/admin.",
    outputs: "Wyjścia OUT1–OUT16",
    inputs: "Wejścia IN1–IN8",
    module: "Moduł",
    controller: "Sterownik I/O",
    outputsSummary: "16 kanałów MOSFET",
    inputsSummary: "8 wejść stykowych",
    state: "Stan",
    online: "online",
    offline: "offline",
    readOnly: "tylko odczyt",
    controlUnavailable: "StackNet działa, ale sterowanie jest zablokowane do czasu uzyskania autoryzacji, dzierżawy i zgodnej konfiguracji OQL.",
    on: "ZAŁ",
    off: "WYŁ",
    closed: "zwarte",
    open: "rozwarte",
    unavailable: "Moduł nieaktywny lub niedostępny",
    unavailableHint:
      "StackNet lub moduł 0x45/0x66 nie odpowiada. Sprawdź profil HTTP, LAN/Wi-Fi, nazwę stacknet.local, unikalne adresy I2C, zasilanie DC IN 9–24 V, SDA/SCL i wspólną masę.",
    firmware: "Firmware",
    address: "Adres",
    transport: "Transport",
    latency: "Ostatnia komenda",
    valveHint:
      "Wyjścia są typu low-side ze wspólną anodą: obciążenie łączy się między zacisk V+ modułu a OUTn.",
  },
  en: {
    title: "M5Stack 4In8Out — outputs",
    subtitle:
      "LAN or Wi-Fi control of 16 MOSFET outputs on two I2C modules (0x45 and 0x66). IN1–IN8 are read-only.",
    refresh: "Refresh state",
    stop: "STOP — de-energize all",
    allOn: "Energize all",
    confirm: "I confirm the bench is safe and I am observing the correct actuator module.",
    roleBlocked: "Output control is available only to system/admin.",
    outputs: "Outputs OUT1–OUT16",
    inputs: "Inputs IN1–IN8",
    module: "Module",
    controller: "I/O controller",
    outputsSummary: "16 MOSFET channels",
    inputsSummary: "8 contact inputs",
    state: "State",
    online: "online",
    offline: "offline",
    readOnly: "read-only",
    controlUnavailable: "StackNet is online, but control stays blocked until authorization, a lease and a compatible OQL configuration are available.",
    on: "ON",
    off: "OFF",
    closed: "closed",
    open: "open",
    unavailable: "Module inactive or unavailable",
    unavailableHint:
      "StackNet or module 0x45/0x66 is unavailable. Check the HTTP profile, LAN/Wi-Fi, stacknet.local name, unique I2C addresses, 9–24 V DC IN, SDA/SCL and common ground.",
    firmware: "Firmware",
    address: "Address",
    transport: "Transport",
    latency: "Last command",
    valveHint:
      "Outputs are low-side with a common anode: wire the load between the module V+ terminal and OUTn.",
  },
};

/** Direct manual control of the alternative M5 valve output stage. */
export default function HardwareM5Out() {
  const { isAdmin } = useAppConfig();
  const { lang } = useI18n();
  const text = COPY[lang] || COPY.en;

  const [snapshot, setSnapshot] = useState(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [lastCommandMs, setLastCommandMs] = useState(null);
  const [pollDelayMs, setPollDelayMs] = useState(M5_POLL_ONLINE_MS);
  const pollInFlight = useRef(false);

  const refresh = useCallback(async () => {
    setBusy("refresh");
    setError("");
    try {
      const result = await HardwareApi.executePluginCommand(PLUGIN_ID, "read_io_snapshot");
      setSnapshot(result?.data || result?.result?.data || null);
    } catch (err) {
      setSnapshot(null);
      setPollDelayMs(M5_POLL_OFFLINE_INITIAL_MS);
      setError(formatHardwareApiError(err, "M5 4In8Out snapshot failed"));
    } finally {
      setBusy("");
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const outputs = useMemo(() => {
    const coils = Array.isArray(snapshot?.coils) ? snapshot.coils : [];
    return Array.from({ length: OUTPUT_COUNT }, (_, index) => ({
      channel: index + 1,
      coil: index,
      on: Boolean(coils[index]),
    }));
  }, [snapshot]);

  const inputs = useMemo(() => {
    const contacts = Array.isArray(snapshot?.discrete_inputs) ? snapshot.discrete_inputs : [];
    return Array.from({ length: INPUT_COUNT }, (_, index) => ({
      channel: index + 1,
      closed: Boolean(contacts[index]),
    }));
  }, [snapshot]);

  const online = Boolean(snapshot && snapshot.physical_healthy !== false);
  const controlReady = Boolean(online && snapshot?.control_ready !== false);
  const canDrive = Boolean(controlReady && confirmed && isAdmin && !busy);

  const reconcileSnapshot = useCallback(async () => {
    try {
      const result = await HardwareApi.executePluginCommand(PLUGIN_ID, "read_io_snapshot");
      setSnapshot(result?.data || result?.result?.data || null);
      setError("");
      setPollDelayMs(M5_POLL_ONLINE_MS);
    } catch {
      // Preserve the command error; manual refresh exposes transport diagnostics.
      // Back off an offline module so a diagnostic page does not continuously
      // create expensive HTTP/plugin reconnect attempts.
      setPollDelayMs(nextM5OfflinePollDelay);
    }
  }, []);

  const runCommand = useCallback(async (command, params, tag, optimisticUpdate) => {
    setBusy(tag);
    setError("");
    if (optimisticUpdate) setSnapshot((current) => optimisticUpdate(current));
    const startedAt = performance.now();
    try {
      await HardwareApi.executePluginCommand(PLUGIN_ID, command, params);
    } catch (err) {
      setError(formatHardwareApiError(err, `M5 4In8Out ${command} failed`));
      void reconcileSnapshot();
    } finally {
      setLastCommandMs(Math.round(performance.now() - startedAt));
      setBusy("");
    }
  }, [reconcileSnapshot]);

  useEffect(() => {
    const interval = window.setInterval(async () => {
      if (document.hidden || busy || pollInFlight.current) return;
      pollInFlight.current = true;
      try {
        await reconcileSnapshot();
      } finally {
        pollInFlight.current = false;
      }
    }, pollDelayMs);
    return () => window.clearInterval(interval);
  }, [busy, pollDelayMs, reconcileSnapshot]);

  const toggle = useCallback((output) => {
    if (!canDrive) return;
    // Coils keep the zero-based wire contract; OUTn is what the case is labelled.
    const nextValue = !output.on;
    void runCommand(
      "set_coil",
      { coil: output.coil, value: nextValue },
      `out-${output.channel}`,
      (current) => {
        const coils = Array.isArray(current?.coils)
          ? [...current.coils]
          : Array(OUTPUT_COUNT).fill(false);
        coils[output.coil] = nextValue;
        return { ...(current || {}), coils, outputs: coils };
      },
    );
  }, [canDrive, runCommand]);

  // Safe-off stays reachable without the confirmation checkbox: de-energizing
  // is the recovery action, never the risky one.
  const stopAll = useCallback(() => {
    if (!controlReady || !isAdmin || busy) return;
    void runCommand(
      "all_outputs_off",
      {},
      "stop",
      (current) => {
        const coils = Array(OUTPUT_COUNT).fill(false);
        return { ...(current || {}), coils, outputs: coils };
      },
    );
  }, [controlReady, isAdmin, busy, runCommand]);

  const allOn = useCallback(() => {
    if (!canDrive) return;
    void runCommand(
      "set_coil",
      { coil: 0x00ff, value: true },
      "all-on",
      (current) => {
        const coils = Array(OUTPUT_COUNT).fill(true);
        return { ...(current || {}), coils, outputs: coils };
      },
    );
  }, [canDrive, runCommand]);

  const details = snapshot || {};

  return (
    <div className="m5-out-page">
      <SharedNav navContext={<div className="section-label">M5 4In8Out</div>} />
      <main className="m5-out-content">
        <header className="m5-out-header">
          <div>
            <span className="m5-out-eyebrow">LAN / Wi-Fi · Core2 / CoreS3 · 0x45 + 0x66 · 16 OUT / 8 IN</span>
            <h1>{text.title}</h1>
            <p>{text.subtitle}</p>
          </div>
          <span className={`m5-out-status m5-out-status--${online ? "online" : "offline"}`}>
            <span className="m5-out-status-dot" aria-hidden="true" />
            {online ? `${text.online}${controlReady ? "" : ` · ${text.readOnly}`}` : text.offline}
          </span>
        </header>

        <section className="m5-out-card m5-out-overview">
          <div className="m5-out-card-heading">
            <div className="m5-out-device">
              <span>{text.controller}</span>
              <strong>{PLUGIN_ID}</strong>
            </div>
            <div className="m5-out-meta">
              <div>
                <span>{text.address}</span>
                <strong>{details.address || "0x45, 0x66"}</strong>
              </div>
              <div>
                <span>{text.transport}</span>
                <strong>{details.backend || "http"}</strong>
              </div>
              <div>
                <span>{text.latency}</span>
                <strong>{lastCommandMs == null ? "—" : `${lastCommandMs} ms`}</strong>
              </div>
              <div>
                <span>{text.firmware}</span>
                <strong>{details.firmware_version || "—"}</strong>
              </div>
            </div>
          </div>

          <div className="m5-out-actions">
            <button
              className="m5-out-button"
              type="button"
              onClick={() => void refresh()}
              disabled={Boolean(busy)}
            >
              {text.refresh}
            </button>
            <button
              className="m5-out-button m5-out-button--danger"
              type="button"
              onClick={stopAll}
              disabled={!controlReady || !isAdmin || Boolean(busy)}
            >
              {text.stop}
            </button>
            <button
              className="m5-out-button m5-out-button--energize"
              type="button"
              onClick={allOn}
              disabled={!canDrive}
            >
              {text.allOn}
            </button>
          </div>

          {!isAdmin && <p className="m5-out-role-hint">{text.roleBlocked}</p>}
          {online && !controlReady && (
            <p className="m5-out-role-hint">
              {text.controlUnavailable}
              {snapshot?.control_message ? ` ${snapshot.control_message}` : ""}
            </p>
          )}
          {!online && (
            <div className="m5-out-alert" role="status">
              <span className="m5-out-alert-icon" aria-hidden="true">!</span>
              <div>
                <strong>{text.unavailable}</strong>
                <p>{text.unavailableHint}</p>
                {error && <code>{error}</code>}
              </div>
            </div>
          )}
          {online && error && <p className="m5-out-command-error">{error}</p>}
        </section>

        <section className="m5-out-card m5-out-safety">
          <label className="m5-out-confirm">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
              disabled={!controlReady || !isAdmin}
            />
            <span>{text.confirm}</span>
          </label>
          <p>{text.valveHint}</p>
        </section>

        <div className="m5-out-io-grid">
          <section className="m5-out-card m5-out-io-card">
            <div className="m5-out-section-heading">
              <h2>{text.outputs}</h2>
              <span>{text.outputsSummary}</span>
            </div>
            <div className="m5-out-channel-grid m5-out-channel-grid--outputs">
              {outputs.map((output) => (
                <button
                  key={output.channel}
                  type="button"
                  className={`m5-out-channel m5-out-channel--output${output.on ? " is-active" : ""}`}
                  aria-pressed={output.on}
                  onClick={() => toggle(output)}
                  disabled={!canDrive}
                >
                  <span className="m5-out-channel-index">{String(output.channel).padStart(2, "0")}</span>
                  <strong>OUT{output.channel}</strong>
                  <span className="m5-out-channel-state">{output.on ? text.on : text.off}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="m5-out-card m5-out-io-card">
            <div className="m5-out-section-heading">
              <h2>{text.inputs}</h2>
              <span>{text.inputsSummary}</span>
            </div>
            <div className="m5-out-channel-grid m5-out-channel-grid--inputs">
              {inputs.map((input) => (
                <div
                  key={input.channel}
                  className={`m5-out-channel m5-out-channel--input${input.closed ? " is-active" : ""}`}
                >
                  <span className="m5-out-channel-index">{String(input.channel).padStart(2, "0")}</span>
                  <strong>IN{input.channel}</strong>
                  <span className="m5-out-channel-state">
                    {input.closed ? text.closed : text.open}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
