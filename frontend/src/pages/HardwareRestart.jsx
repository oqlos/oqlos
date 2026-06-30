import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import SharedNav from "../components/SharedNav";
import { HardwareApi, formatHardwareApiError } from "../api/hardwareApi";
import { useI18n } from "../i18n/I18nProvider";
import { rem } from "../utils/designRem.js";
import { isOptionalWizardStep, isSkippablePumpOffWizardStep } from "../utils/hardware-wizard-steps.js";
import {
  executeConfigureStep,
  executeDiagnosticStep,
  executeFinalDiagnoseStep,
  executePeripheralStatusStep,
} from "../utils/hardware-restart-wizard-steps.js";
import { hardwareRestartDocsUrl } from "../utils/hardware-restart-docs.js";
import { isOqlosUnreachableError } from "../utils/hardware-wizard-plan.js";
import { runApiWithRetry } from "../utils/hardware-api-retry.js";

function timestamp() {
  return new Date().toISOString();
}

function _extractWizardPlan(stack) {
  if (stack?.ok === false) {
    const hint = stack?.hint ? ` ${stack.hint}` : "";
    throw new Error(`${stack?.error || "OqlOS niedostepny (port 8202)"}${hint}`);
  }
  const data = stack?.wizard_plan_enriched || stack?.configuration_cycle?.wizard_plan || stack?.wizard_plan;
  if (!data || typeof data !== "object") throw new Error("Brak planu kreatora w hardware stack snapshot");
  return data;
}

function _resolveStepAdvance(ok, currentStep) {
  if (!ok && isOptionalWizardStep(currentStep)) return { advanceOk: true, optionalSkip: true };
  return { advanceOk: ok, optionalSkip: false };
}

function _buildStepError(err, currentStep) {
  const message = formatHardwareApiError(err, "Krok zakonczony bledem.");
  const commandResult = err?.commandResult ?? null;
  return {
    message,
    commandResult,
    payload: {
      step: currentStep,
      error: message,
      ...(commandResult ? { diagnostic: commandResult, commandResult } : {}),
    },
  };
}

function txtDownload(name, text) {
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export default function HardwareRestart() {
  const { t } = useI18n();
  const [plan, setPlan] = useState(null);
  const [planError, setPlanError] = useState("");
  const [busy, setBusy] = useState(false);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [stepResults, setStepResults] = useState({});
  const [confirmIsolated, setConfirmIsolated] = useState(false);
  const [stepLog, setStepLog] = useState({
    step: "",
    ok: null,
    lines: [],
    payload: null,
  });
  const [copyStatus, setCopyStatus] = useState("");
  const logPanelRef = useRef(null);
  const [runtimeStatus, setRuntimeStatus] = useState(null);

  const refreshRuntimeStatus = useCallback(async (port) => {
    try {
      const status = await HardwareApi.getOqlosRuntimeStatus(port || undefined, { logContext: "runtime-status" });
      setRuntimeStatus(status);
      return status;
    } catch {
      setRuntimeStatus(null);
      return null;
    }
  }, []);

  const loadPlan = useCallback(async () => {
    setBusy(true);
    setPlanError("");
    try {
      const stack = await HardwareApi.getHardwareStackSnapshot({ logContext: "load-stack" });
      const data = _extractWizardPlan(stack);
      setPlan(data);
      setCurrentStepIndex(0);
      setStepResults({});
      await refreshRuntimeStatus(data?.serial_port || "");
    } catch (err) {
      setPlanError(formatHardwareApiError(err, "Nie udalo sie pobrac planu konfiguracji Modbus."));
      await refreshRuntimeStatus("");
    } finally {
      setBusy(false);
    }
  }, [refreshRuntimeStatus]);

  const serialPort = plan?.serial_port || "";

  const startOqlosAndRefreshPlan = useCallback(async () => {
    const port = plan?.serial_port || "";
    setBusy(true);
    setPlanError("");
    try {
      const start = await HardwareApi.startOqlosRuntime({ mode: "light", logContext: "quick-start" });
      if (start?.ok === false) {
        throw new Error(String(start.error || start.stderr || "OqlOS start failed"));
      }
      await refreshRuntimeStatus(port);
      await loadPlan();
    } catch (err) {
      setPlanError(formatHardwareApiError(err, t("hardwareRestart.startOqlosFailed")));
      await refreshRuntimeStatus(port);
    } finally {
      setBusy(false);
    }
  }, [loadPlan, plan?.serial_port, refreshRuntimeStatus, t]);

  useEffect(() => {
    loadPlan();
  }, [loadPlan]);

  const steps = useMemo(() => (Array.isArray(plan?.steps) ? plan.steps : []), [plan]);
  const currentStep = steps[currentStepIndex] || null;
  const isSeparateAdapters = plan?.modbus_topology === "separate-adapters";
  const isConfigureStep = Boolean(currentStep?.step?.startsWith("configure-"));
  const requiresStepConfirm = isConfigureStep;
  const confirmLabelKey = isSeparateAdapters
    ? "hardwareRestart.confirmSeparateAdapter"
    : "hardwareRestart.confirmIsolated";
  const confirmErrorKey = isSeparateAdapters
    ? "hardwareRestart.confirmSeparateAdapterError"
    : "hardwareRestart.confirmIsolatedError";
  const canRunCurrentStep = Boolean(currentStep) && (!requiresStepConfirm || confirmIsolated);

  const releaseRs485Port = useCallback(async () => {
    setBusy(true);
    try {
      const stop = await HardwareApi.stopOqlosRuntime({ logContext: "release-port", serialPort });
      await refreshRuntimeStatus(serialPort);
      return stop;
    } finally {
      setBusy(false);
    }
  }, [refreshRuntimeStatus, serialPort]);

  useEffect(() => {
    if (serialPort) {
      void refreshRuntimeStatus(serialPort);
    }
  }, [serialPort, refreshRuntimeStatus]);

  const runCurrentStep = useCallback(async () => {
    if (!currentStep || busy) return;
    const lines = [];
    setStepLog({ step: currentStep.step, ok: null, lines: [], payload: null });
    const log = (line) => {
      const entry = `[${timestamp()}] ${line}`;
      lines.push(entry);
      setStepLog((prev) => ({ ...prev, lines: [...prev.lines, entry] }));
    };
    setBusy(true);
    let payload = null;
    let ok = false;
    const apiContext = { logContext: currentStep.step };
    const runRetry = (label, action, opts) => runApiWithRetry(label, action, { log, t, ...opts });
    const ctx = { currentStep, plan, confirmIsolated, confirmErrorKey, isSeparateAdapters, serialPort, refreshRuntimeStatus, t, runRetry, log, apiContext };
    try {
      log(`START ${currentStep.step}`);
      log(currentStep.instruction || "Brak instrukcji.");
      if (currentStep.step.startsWith("configure-")) {
        ({ ok, payload } = await executeConfigureStep(ctx));
      } else if (currentStep.action?.type === "diagnostic") {
        ({ ok, payload } = await executeDiagnosticStep(ctx));
      } else if (currentStep.action?.type === "peripheral-status") {
        ({ ok, payload } = await executePeripheralStatusStep(ctx));
      } else {
        ({ ok, payload } = await executeFinalDiagnoseStep(ctx));
      }
    } catch (err) {
      const stepErr = _buildStepError(err, currentStep);
      log(`ERROR: ${stepErr.message}`);
      if (stepErr.commandResult) log(`Diagnostic payload: ${JSON.stringify(stepErr.commandResult)}`);
      payload = stepErr.payload;
      ok = false;
    } finally {
      const { advanceOk, optionalSkip } = _resolveStepAdvance(ok, currentStep);
      if (optionalSkip) log(`WARN: krok opcjonalny (${currentStep.step}) — RTC/piRTC tylko na RPi; kontynuuję mimo błędu.`);
      setStepResults((prev) => ({
        ...prev,
        [currentStep.step]: {
          ok: advanceOk,
          finished_at: timestamp(),
          payload,
          ...(optionalSkip ? { optional_skip: true, attempted_ok: ok } : {}),
        },
      }));
      if (advanceOk && currentStepIndex < steps.length - 1) setCurrentStepIndex((prev) => prev + 1);
      setStepLog((prev) => ({ ...prev, ok: advanceOk, payload }));
      setBusy(false);
    }
  }, [
    busy,
    confirmErrorKey,
    confirmIsolated,
    currentStep,
    currentStepIndex,
    isSeparateAdapters,
    plan,
    refreshRuntimeStatus,
    serialPort,
    steps.length,
    t,
  ]);

  const skipPumpOffStep = useCallback(() => {
    if (!currentStep || busy || !isSkippablePumpOffWizardStep(currentStep)) return;
    const entry = `[${timestamp()}] SKIP ${currentStep.step} (pompa — pominięty ręcznie; upewnij się, że DRI0050 jest wyłączona)`;
    setStepResults((prev) => ({
      ...prev,
      [currentStep.step]: {
        ok: true,
        optional_skip: true,
        pump_skip: true,
        finished_at: timestamp(),
        payload: { step: currentStep, skipped: true },
      },
    }));
    setStepLog((prev) => ({
      ...prev,
      step: currentStep.step,
      ok: true,
      lines: [...prev.lines, entry],
      payload: { step: currentStep, skipped: true },
    }));
    if (currentStepIndex < steps.length - 1) {
      setCurrentStepIndex((prev) => prev + 1);
    }
  }, [busy, currentStep, currentStepIndex, steps.length]);

  const skipOptionalStep = useCallback(() => {
    if (!currentStep || busy || !isOptionalWizardStep(currentStep)) return;
    const entry = `[${timestamp()}] SKIP ${currentStep.step} (opcjonalny RTC — pominięty ręcznie)`;
    setStepResults((prev) => ({
      ...prev,
      [currentStep.step]: {
        ok: true,
        optional_skip: true,
        finished_at: timestamp(),
        payload: { step: currentStep, skipped: true },
      },
    }));
    setStepLog((prev) => ({
      ...prev,
      step: currentStep.step,
      ok: true,
      lines: [...prev.lines, entry],
      payload: { step: currentStep, skipped: true },
    }));
    if (currentStepIndex < steps.length - 1) {
      setCurrentStepIndex((prev) => prev + 1);
    }
  }, [busy, currentStep, currentStepIndex, steps.length]);

  const logText = useMemo(() => stepLog.lines.join("\n"), [stepLog.lines]);

  const exportText = useMemo(() => {
    const payload = stepLog.payload ? `\n\n--- payload ---\n${JSON.stringify(stepLog.payload, null, 2)}` : "";
    return `${logText}${payload}`;
  }, [logText, stepLog.payload]);

  const stepRunning = stepLog.ok === null && Boolean(stepLog.step) && busy;

  const copyLogsToClipboard = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(exportText);
      setCopyStatus(t("hardwareRestart.logsCopied"));
    } catch {
      setCopyStatus(t("hardwareRestart.logsCopyFailed"));
    }
  }, [exportText]);

  useEffect(() => {
    const el = logPanelRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [stepLog.lines.length]);

  useEffect(() => {
    if (!copyStatus) return undefined;
    const timer = setTimeout(() => setCopyStatus(""), 2500);
    return () => clearTimeout(timer);
  }, [copyStatus]);

  return (
    <div className="dashboard" style={{ minHeight: "100vh", overflow: "auto" }}>
      <SharedNav navContext={<div className="section-label">{t("hardwareRestart.navTitle")}</div>} />
      <div className="dash-content">
        <h2>{t("hardwareRestart.pageTitle")}</h2>
        <p className="section-desc">{t("hardwareRestart.pageDesc")}</p>
        <p className="section-desc" style={{ marginTop: "-8px" }}>
          {t("hardwareRestart.docsHint")}{" "}
          <a
            href={hardwareRestartDocsUrl(globalThis.location?.origin || "")}
            target="_blank"
            rel="noopener noreferrer"
          >
            {t("hardwareRestart.openDocumentation")}
          </a>
        </p>

        <div style={{ display: "flex", gap: "8px", marginBottom: "12px", alignItems: "center", flexWrap: "wrap" }}>
          <button className="run-btn role-force" onClick={loadPlan} disabled={busy}>
            {busy ? t("hardwareRestart.loadingPlan") : t("hardwareRestart.refreshPlan")}
          </button>
          <Link className="run-btn role-force" to="/hardware-status" style={{ textDecoration: "none", display: "inline-flex", alignItems: "center" }}>
            {t("hardwareRestart.backToStatus")}
          </Link>
          <a
            className="run-btn role-force"
            href={hardwareRestartDocsUrl(globalThis.location?.origin || "")}
            target="_blank"
            rel="noopener noreferrer"
            style={{ textDecoration: "none", display: "inline-flex", alignItems: "center" }}
          >
            {t("hardwareRestart.openDocumentation")}
          </a>
          <span style={{ color: "var(--text-muted)", fontSize: rem.sm }}>{t("hardwareRestart.targetIds")}: {Array.isArray(plan?.target_ids) ? plan.target_ids.join(", ") : "-"}</span>
        </div>
        {planError ? (
          <div className="hw-error" style={{ marginBottom: "8px" }}>
            <div>{planError}</div>
            {isOqlosUnreachableError(planError) || runtimeStatus?.oqlos_up === false ? (
              <p style={{ margin: "8px 0 0", fontSize: rem.sm, fontWeight: 400, color: "var(--text-secondary)" }}>
                {t("hardwareRestart.planErrorOqlosHint")}
              </p>
            ) : null}
          </div>
        ) : null}
        {planError && (isOqlosUnreachableError(planError) || !runtimeStatus?.oqlos_up) ? (
          <div style={{ display: "flex", gap: "8px", marginBottom: "12px", flexWrap: "wrap" }}>
            <button className="run-btn role-force" type="button" onClick={startOqlosAndRefreshPlan} disabled={busy}>
              {t("hardwareRestart.startOqlosRefreshPlan")}
            </button>
          </div>
        ) : null}

        <div className="hw-card" style={{ marginBottom: "12px" }}>
          <h3>{t("hardwareRestart.portCard")}</h3>
          <div className="hw-kv"><span>{t("hardwareRestart.runtimeControl")}</span><strong>{runtimeStatus?.runtime_control_available ? t("hardwareRestart.runtimeAvailable") : t("hardwareRestart.runtimeUnavailable")}</strong></div>
          <div className="hw-kv"><span>{t("hardwareRestart.oqlosPort")}</span><strong>{runtimeStatus?.oqlos_up ? t("hardwareRestart.oqlosUp") : t("hardwareRestart.oqlosStopped")}</strong></div>
          <div className="hw-kv"><span>{t("hardwareRestart.serialPort")}</span><strong>{runtimeStatus?.serial_state || "-"}</strong></div>
          <div style={{ display: "flex", gap: "8px", marginTop: "10px", flexWrap: "wrap" }}>
            <button className="run-btn role-force" type="button" onClick={releaseRs485Port} disabled={busy}>
              {t("hardwareRestart.releasePort")}
            </button>
            <button className="run-btn role-force" type="button" onClick={startOqlosAndRefreshPlan} disabled={busy}>
              {t("hardwareRestart.quickStart")}
            </button>
            <button className="run-btn role-force" type="button" onClick={() => refreshRuntimeStatus(serialPort)} disabled={busy}>
              {t("hardwareRestart.refreshStatus")}
            </button>
          </div>
        </div>

        <div className="hw-card">
          <h3>{t("hardwareRestart.wizardSteps")}</h3>
          <div className="hw-kv"><span>{t("hardwareRestart.serialPort")}</span><strong>{serialPort || "-"}</strong></div>
          <div className="hw-kv"><span>{t("hardwareRestart.targetUart")}</span><strong>{plan ? `${plan.target_baudrate} / ${plan.target_parity}` : "-"}</strong></div>
          <ol style={{ margin: "12px 0 0 18px", fontSize: rem.md }}>
            {steps.map((step, idx) => {
              const result = stepResults[step.step];
              const skippedOptional = Boolean(result?.optional_skip);
              const done = Boolean(result?.ok);
              const failed = result && !result.ok;
              const isCurrent = idx === currentStepIndex;
              return (
                <li key={step.step} style={{ marginBottom: "10px" }}>
                  <div>
                    <strong>{step.step}</strong>{" "}
                    {skippedOptional ? (
                      <span className="hw-badge" style={{ marginLeft: "6px" }}>{t("hardwareRestart.stepSkipped")}</span>
                    ) : done ? (
                      <span className="hw-badge hw-badge-ok" style={{ marginLeft: "6px" }}>{t("hardwareRestart.stepOk")}</span>
                    ) : failed ? (
                      <span className="hw-badge hw-badge-err" style={{ marginLeft: "6px" }}>{t("hardwareRestart.stepFail")}</span>
                    ) : null}
                    {isOptionalWizardStep(step) ? (
                      <span style={{ color: "var(--text-muted)", marginLeft: "6px", fontSize: rem.sm }}>{t("hardwareRestart.stepOptional")}</span>
                    ) : null}
                    {isCurrent ? <span style={{ color: "#74b9ff", marginLeft: "8px" }}>{t("hardwareRestart.stepActive")}</span> : null}
                  </div>
                  <div style={{ color: "var(--text-secondary)" }}>{step.instruction}</div>
                </li>
              );
            })}
          </ol>
          <label
            style={{
              display: "inline-flex",
              gap: "8px",
              alignItems: "center",
              marginTop: "8px",
              padding: requiresStepConfirm && !confirmIsolated ? "8px 10px" : undefined,
              borderRadius: requiresStepConfirm && !confirmIsolated ? "6px" : undefined,
              border: requiresStepConfirm && !confirmIsolated ? "1px solid #e17055" : undefined,
            }}
          >
            <input type="checkbox" checked={confirmIsolated} onChange={(e) => setConfirmIsolated(e.target.checked)} />
            {t(confirmLabelKey)}
          </label>
          {requiresStepConfirm && !confirmIsolated ? (
            <p style={{ margin: "8px 0 0", color: "#e17055", fontSize: rem.sm }}>
              {t(confirmErrorKey)}
            </p>
          ) : null}
          <div style={{ marginTop: "12px", display: "flex", gap: "8px", flexWrap: "wrap" }}>
            <button className="run-btn role-force" onClick={runCurrentStep} disabled={busy || !canRunCurrentStep}>
              {busy ? t("hardwareRestart.executing") : currentStep ? t("hardwareRestart.runStep", { step: currentStep.step }) : t("hardwareRestart.noSteps")}
            </button>
            {currentStep && isOptionalWizardStep(currentStep) ? (
              <button className="run-btn role-force" type="button" onClick={skipOptionalStep} disabled={busy}>
                {t("hardwareRestart.skipOptionalStep")}
              </button>
            ) : null}
            {currentStep && isSkippablePumpOffWizardStep(currentStep) ? (
              <button className="run-btn role-force" type="button" onClick={skipPumpOffStep} disabled={busy}>
                {t("hardwareRestart.skipPumpOffStep")}
              </button>
            ) : null}
          </div>
        </div>

        <div className="hw-card" style={{ marginTop: "12px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px", flexWrap: "wrap", marginBottom: "8px" }}>
            <h3 style={{ margin: 0 }}>
              {t("hardwareRestart.stepTerminal")}
              {stepLog.step ? `: ${stepLog.step}` : ""}{" "}
              {stepRunning ? (
                <span className="hw-badge hw-badge-warn" style={{ marginLeft: "6px" }}>{t("hardwareRestart.stepRunning")}</span>
              ) : stepLog.ok === true ? (
                <span className="hw-badge hw-badge-ok" style={{ marginLeft: "6px" }}>{t("hardwareRestart.stepOk")}</span>
              ) : stepLog.ok === false ? (
                <span className="hw-badge hw-badge-err" style={{ marginLeft: "6px" }}>{t("hardwareRestart.stepFail")}</span>
              ) : null}
            </h3>
            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
              <button className="run-btn role-force" type="button" onClick={copyLogsToClipboard} disabled={!stepLog.lines.length}>
                {t("hardwareRestart.copyLogs")}
              </button>
              <button
                className="run-btn role-force"
                type="button"
                onClick={() => txtDownload(`modbus-wizard-${stepLog.step || "step"}.log.txt`, exportText)}
                disabled={!stepLog.lines.length}
              >
                {t("hardwareRestart.downloadLogs")}
              </button>
            </div>
          </div>
          {copyStatus ? (
            <div style={{ marginBottom: "8px", color: "var(--text-muted)", fontSize: rem.sm }}>
              {copyStatus}
            </div>
          ) : null}
          <pre
            ref={logPanelRef}
            style={{
              background: "#0d1117",
              color: "#58a6ff",
              fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
              fontSize: rem.sm,
              padding: "12px",
              borderRadius: "6px",
              border: "1px solid #30363d",
              whiteSpace: "pre-wrap",
              maxHeight: "320px",
              overflow: "auto",
              margin: 0,
            }}
          >
            {stepLog.lines.length
              ? logText
              : t("hardwareRestart.noLogs")}
          </pre>
          {stepLog.payload ? (
            <details style={{ marginTop: "10px" }}>
              <summary style={{ cursor: "pointer", color: "var(--text-secondary)", fontSize: rem.sm }}>
                {t("hardwareRestart.payloadJson")}
              </summary>
              <pre className="hw-pre" style={{ marginTop: "8px" }}>
                {JSON.stringify(stepLog.payload, null, 2)}
              </pre>
            </details>
          ) : null}
        </div>
      </div>
    </div>
  );
}

