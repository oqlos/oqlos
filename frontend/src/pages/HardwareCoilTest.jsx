import { useCallback, useEffect, useMemo, useState } from "react";

import { HardwareApi, formatHardwareApiError } from "../api/hardwareApi";
import SharedNav from "../components/SharedNav";
import { useAppConfig } from "../context/AppConfigProvider";
import { useI18n } from "../i18n/I18nProvider";
import {
  buildCoilTestReport,
  nextUntestedCoil,
  pulseConfirmation,
} from "../utils/hardware-coil-test.js";

const COPY = {
  pl: {
    title: "TEST — kolejność cewek BoardNet",
    subtitle: "Kontrolowany test DO1–DO8: jedna cewka, krótki impuls, automatyczne OFF i ocena operatora.",
    refresh: "Odśwież preflight",
    stop: "STOP — wyłącz wszystkie",
    ready: "GOTOWY",
    blocked: "ZABLOKOWANY",
    confirm: "Potwierdzam, że stanowisko jest zabezpieczone i obserwuję właściwy moduł wykonawczy.",
    next: "Impuls następnej cewki",
    copy: "Kopiuj raport JSON",
    configuration: "Szczegółowa konfiguracja modułu",
    sequence: "Test połączeń DO1–DO8",
    result: "Ocena",
    correct: "poprawnie",
    wrong: "inna cewka",
    no_response: "brak reakcji",
    notTested: "nie testowano",
    pulse: "Impuls",
    uses: "Użycie w HUI / konfiguracji",
    aliases: "Aliasy",
    state: "Stan",
    roleBlocked: "Impulsy są dostępne wyłącznie dla roli system/admin.",
    awaiting: "Po impulsie zaznacz zaobserwowany wynik.",
  },
  en: {
    title: "TEST — BoardNet coil order",
    subtitle: "Controlled DO1–DO8 test: one coil, short pulse, automatic OFF and operator assessment.",
    refresh: "Refresh preflight",
    stop: "STOP — de-energize all",
    ready: "READY",
    blocked: "BLOCKED",
    confirm: "I confirm the bench is safe and I am observing the correct actuator module.",
    next: "Pulse next coil",
    copy: "Copy JSON report",
    configuration: "Detailed module configuration",
    sequence: "DO1–DO8 wiring test",
    result: "Assessment",
    correct: "correct",
    wrong: "different coil",
    no_response: "no response",
    notTested: "not tested",
    pulse: "Pulse",
    uses: "HUI / configuration use",
    aliases: "Aliases",
    state: "State",
    roleBlocked: "Pulses are available only to system/admin.",
    awaiting: "After the pulse, record the observed result.",
  },
};

function valueText(value) {
  if (value == null) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export default function HardwareCoilTest() {
  const { isAdmin } = useAppConfig();
  const { lang } = useI18n();
  const text = COPY[lang] || COPY.en;
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [results, setResults] = useState({});
  const [pulses, setPulses] = useState({});

  const refresh = useCallback(async () => {
    setBusy("refresh");
    setError("");
    try {
      setPlan(await HardwareApi.getCoilTestPlan({ logContext: "coil-test-plan" }));
    } catch (err) {
      setError(formatHardwareApiError(err, "Coil test preflight failed"));
    } finally {
      setBusy("");
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const next = useMemo(
    () => nextUntestedCoil(plan?.coils || [], results),
    [plan, results],
  );
  const canPulse = Boolean(plan?.ready && confirmed && isAdmin && !busy);

  const pulse = useCallback(async (coil) => {
    if (!coil || !canPulse) return;
    setBusy(`pulse-${coil.address}`);
    setError("");
    try {
      const response = await HardwareApi.pulseCoil({
        address: coil.address,
        duration_ms: 300,
        confirm: pulseConfirmation(coil),
      }, { logContext: `coil-test-${coil.id}` });
      setPulses((current) => ({ ...current, [String(coil.address)]: response }));
      if (response.after) setPlan(response.after);
      if (!response.ok) {
        throw new Error(response.error || (response.blocked_reasons || []).join("; ") || "Pulse failed");
      }
    } catch (err) {
      setError(formatHardwareApiError(err, "Coil pulse failed"));
    } finally {
      setBusy("");
    }
  }, [canPulse]);

  const stop = useCallback(async () => {
    setBusy("stop");
    setError("");
    try {
      const response = await HardwareApi.stopAllCoils({ logContext: "coil-test-stop" });
      if (!response.ok) throw new Error(response.error || "Not every coil could be switched OFF");
      await refresh();
    } catch (err) {
      setError(formatHardwareApiError(err, "Emergency OFF failed"));
      setBusy("");
    }
  }, [refresh]);

  const copyReport = useCallback(async () => {
    const report = buildCoilTestReport(plan, results, pulses);
    await navigator.clipboard.writeText(JSON.stringify(report, null, 2));
  }, [plan, results, pulses]);

  const configRows = plan?.module?.config_registers || [];
  const blockedReasons = plan?.safety?.blocked_reasons || [];

  return (
    <>
      <SharedNav />
      <main className="coil-test-page">
        <header className="coil-test-header">
          <div>
            <h1>{text.title}</h1>
            <p>{text.subtitle}</p>
          </div>
          <div className="coil-test-actions">
            <button type="button" onClick={refresh} disabled={Boolean(busy)}>{text.refresh}</button>
            <button type="button" className="danger" onClick={stop} disabled={Boolean(busy)}>{text.stop}</button>
          </div>
        </header>

        {error ? <div className="coil-test-alert danger">{error}</div> : null}
        <section className={`coil-test-alert ${plan?.ready ? "ok" : "warn"}`}>
          <strong>{plan?.ready ? text.ready : text.blocked}</strong>
          <span>mode={plan?.mode || "—"} · {plan?.module?.role || "modbus-io"} · ID={valueText(plan?.module?.device_id)}</span>
          <span>{plan?.module?.serial_port || "serial: —"}</span>
          {blockedReasons.map((reason) => <span key={reason}>{reason}</span>)}
        </section>

        <section className="coil-test-card">
          <h2>{text.configuration}</h2>
          <div className="coil-test-config-grid">
            <div><small>serial_port</small><code>{plan?.module?.serial_port || "—"}</code></div>
            <div><small>device_id</small><code>{valueText(plan?.module?.device_id)}</code></div>
            <div><small>automatic_off</small><code>{valueText(plan?.safety?.automatic_off)}</code></div>
            <div><small>max_pulse_ms</small><code>{valueText(plan?.safety?.max_pulse_ms)}</code></div>
            {configRows.map((row) => (
              <div key={row.id}>
                <small>{row.id} · {row.address_hex}</small>
                <code>{valueText(row.value_decoded || row.value)}</code>
              </div>
            ))}
          </div>
        </section>

        <section className="coil-test-card">
          <div className="coil-test-sequence-head">
            <div>
              <h2>{text.sequence}</h2>
              <p>{text.awaiting}</p>
            </div>
            <div className="coil-test-actions">
              <button type="button" onClick={() => pulse(next)} disabled={!canPulse || !next}>
                {text.next}{next ? `: ${next.id}` : ""}
              </button>
              <button type="button" onClick={copyReport} disabled={!plan}>{text.copy}</button>
            </div>
          </div>
          <label className="coil-test-confirm">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
              disabled={!plan?.ready || !isAdmin}
            />
            <span>{text.confirm}</span>
          </label>
          {!isAdmin ? <div className="coil-test-alert warn">{text.roleBlocked}</div> : null}

          <div className="coil-test-table-wrap">
            <table className="coil-test-table">
              <thead>
                <tr>
                  <th># / coil</th><th>{text.state}</th><th>{text.aliases}</th>
                  <th>{text.uses}</th><th>{text.pulse}</th><th>{text.result}</th>
                </tr>
              </thead>
              <tbody>
                {(plan?.coils || []).map((coil) => {
                  const key = String(coil.address);
                  const result = results[key];
                  return (
                    <tr key={coil.id} className={next?.address === coil.address ? "is-next" : ""}>
                      <td><strong>{coil.sequence}. {coil.id}</strong><br /><code>{coil.address_hex}</code></td>
                      <td>{coil.state == null ? "—" : coil.state ? "ON" : "OFF"}</td>
                      <td>{(coil.aliases || []).join(", ") || "—"}</td>
                      <td>
                        {(coil.uses || []).length
                          ? coil.uses.map((use) => `${use.control}: ${use.action}`).join("; ")
                          : "—"}
                      </td>
                      <td>
                        <button
                          type="button"
                          onClick={() => pulse(coil)}
                          disabled={!canPulse}
                        >
                          {busy === `pulse-${coil.address}` ? "…" : text.pulse}
                        </button>
                      </td>
                      <td>
                        <div className="coil-test-result-buttons">
                          {["correct", "wrong", "no_response"].map((option) => (
                            <button
                              key={option}
                              type="button"
                              className={result === option ? "active" : ""}
                              onClick={() => setResults((current) => ({ ...current, [key]: option }))}
                              disabled={!pulses[key]?.ok}
                            >
                              {text[option]}
                            </button>
                          ))}
                        </div>
                        {!result ? <small>{text.notTested}</small> : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </>
  );
}
