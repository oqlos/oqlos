import { useCallback, useEffect, useMemo, useState } from "react";

import { HardwareApi, formatHardwareApiError } from "../api/hardwareApi";
import SharedNav from "../components/SharedNav";
import { useAppConfig } from "../context/AppConfigProvider";
import { useI18n } from "../i18n/I18nProvider";

const PLUGIN_ID = "io-m5-4in8out";
const OUTPUT_COUNT = 8;
const INPUT_COUNT = 4;

const COPY = {
  pl: {
    title: "M5Stack 4In8Out — wyjścia",
    subtitle:
      "Bezpośrednie sterowanie 8 wyjściami MOSFET modułu I2C (0x45). Wejścia IN1–IN4 tylko do odczytu.",
    refresh: "Odśwież stan",
    stop: "STOP — wyłącz wszystkie",
    allOn: "Załącz wszystkie",
    confirm:
      "Potwierdzam, że stanowisko jest zabezpieczone i obserwuję właściwy moduł wykonawczy.",
    roleBlocked: "Sterowanie wyjściami jest dostępne wyłącznie dla roli system/admin.",
    outputs: "Wyjścia OUT1–OUT8",
    inputs: "Wejścia IN1–IN4",
    module: "Moduł",
    state: "Stan",
    on: "ZAŁ",
    off: "WYŁ",
    closed: "zwarte",
    open: "rozwarte",
    unavailable: "Moduł nie odpowiada",
    unavailableHint:
      "Brak potwierdzenia adresu 0x45 na magistrali. Sprawdź przełącznik BOOT0 (pozycja 0), zasilanie DC IN 9–24 V oraz SDA/SCL i wspólną masę. Po zmianie odłącz i podaj zasilanie modułu.",
    firmware: "Firmware",
    address: "Adres",
    transport: "Transport",
    valveHint:
      "Wyjścia są typu low-side ze wspólną anodą: obciążenie łączy się między zacisk V+ modułu a OUTn.",
  },
  en: {
    title: "M5Stack 4In8Out — outputs",
    subtitle:
      "Direct control of the 8 MOSFET outputs on the I2C module (0x45). IN1–IN4 are read-only.",
    refresh: "Refresh state",
    stop: "STOP — de-energize all",
    allOn: "Energize all",
    confirm: "I confirm the bench is safe and I am observing the correct actuator module.",
    roleBlocked: "Output control is available only to system/admin.",
    outputs: "Outputs OUT1–OUT8",
    inputs: "Inputs IN1–IN4",
    module: "Module",
    state: "State",
    on: "ON",
    off: "OFF",
    closed: "closed",
    open: "open",
    unavailable: "Module does not answer",
    unavailableHint:
      "No acknowledgement at address 0x45. Check the BOOT0 switch (position 0), the 9–24 V DC IN supply, SDA/SCL and the common ground. Power-cycle the module after any change.",
    firmware: "Firmware",
    address: "Address",
    transport: "Transport",
    valveHint:
      "Outputs are low-side with a common anode: wire the load between the module V+ terminal and OUTn.",
  },
};

/** Direct manual control of the alternative M5 valve output stage. */
export default function HardwareM5Out() {
  const { isAdmin } = useAppConfig();
  const { lang } = useI18n();
  const text = COPY[lang] || COPY.en;

  const [health, setHealth] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setBusy("refresh");
    setError("");
    try {
      const status = await HardwareApi.peripheralStatus(PLUGIN_ID);
      setHealth(status);
      const result = await HardwareApi.executePluginCommand(PLUGIN_ID, "read_io_snapshot");
      setSnapshot(result?.data || result?.result?.data || null);
    } catch (err) {
      setSnapshot(null);
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

  const online = Boolean(snapshot);
  const canDrive = Boolean(online && confirmed && isAdmin && !busy);

  const runCommand = useCallback(async (command, params, tag) => {
    setBusy(tag);
    setError("");
    try {
      await HardwareApi.executePluginCommand(PLUGIN_ID, command, params);
      const result = await HardwareApi.executePluginCommand(PLUGIN_ID, "read_io_snapshot");
      setSnapshot(result?.data || result?.result?.data || null);
    } catch (err) {
      setError(formatHardwareApiError(err, `M5 4In8Out ${command} failed`));
    } finally {
      setBusy("");
    }
  }, []);

  const toggle = useCallback((output) => {
    if (!canDrive) return;
    // Coils keep the zero-based wire contract; OUTn is what the case is labelled.
    void runCommand("set_coil", { coil: output.coil, value: !output.on }, `out-${output.channel}`);
  }, [canDrive, runCommand]);

  // Safe-off stays reachable without the confirmation checkbox: de-energizing
  // is the recovery action, never the risky one.
  const stopAll = useCallback(() => {
    if (!online || !isAdmin || busy) return;
    void runCommand("all_outputs_off", {}, "stop");
  }, [online, isAdmin, busy, runCommand]);

  const allOn = useCallback(() => {
    if (!canDrive) return;
    void runCommand("set_coil", { coil: 0x00ff, value: true }, "all-on");
  }, [canDrive, runCommand]);

  const details = health?.details || health?.result?.details || {};

  return (
    <div className="page">
      <SharedNav />
      <header className="page-header">
        <h1>{text.title}</h1>
        <p>{text.subtitle}</p>
      </header>

      <section className="panel">
        <div className="panel-row">
          <strong>{text.module}</strong>
          <span>
            {text.address}: {details.address || "0x45"} · {text.transport}: {details.backend || "i2c"}
            {details.firmware_version ? ` · ${text.firmware}: ${details.firmware_version}` : ""}
          </span>
          <span className={online ? "status-ok" : "status-error"}>
            {online ? "online" : "offline"}
          </span>
        </div>
        <div className="panel-actions">
          <button type="button" onClick={() => void refresh()} disabled={Boolean(busy)}>
            {text.refresh}
          </button>
          <button
            type="button"
            className="danger"
            onClick={stopAll}
            disabled={!online || !isAdmin || Boolean(busy)}
          >
            {text.stop}
          </button>
          <button type="button" onClick={allOn} disabled={!canDrive}>
            {text.allOn}
          </button>
        </div>
        {!isAdmin && <p className="hint">{text.roleBlocked}</p>}
        {!online && (
          <div className="empty-state">
            <strong>{text.unavailable}</strong>
            <p>{text.unavailableHint}</p>
          </div>
        )}
        {error && <p className="status-error">{error}</p>}
      </section>

      <section className="panel">
        <label className="confirm-line">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(event) => setConfirmed(event.target.checked)}
            disabled={!online || !isAdmin}
          />
          <span>{text.confirm}</span>
        </label>
        <p className="hint">{text.valveHint}</p>
      </section>

      <section className="panel">
        <h2>{text.outputs}</h2>
        <div className="coil-grid">
          {outputs.map((output) => (
            <button
              key={output.channel}
              type="button"
              className={output.on ? "coil coil-on" : "coil"}
              onClick={() => toggle(output)}
              disabled={!canDrive}
            >
              <strong>OUT{output.channel}</strong>
              <span>{output.on ? text.on : text.off}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>{text.inputs}</h2>
        <div className="coil-grid">
          {inputs.map((input) => (
            <div key={input.channel} className={input.closed ? "coil coil-on" : "coil"}>
              <strong>IN{input.channel}</strong>
              <span>{input.closed ? text.closed : text.open}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
