import { useCallback, useEffect, useMemo, useState } from "react";
import SharedNav from "../components/SharedNav";
import SidebarList from "../components/SidebarList";
import { useI18n } from "../i18n/I18nProvider";
import {
  executeOqlScript,
  fetchScenarioFileContent,
  fetchScenarioFilesList,
  saveScenarioFileContent,
} from "../api/scenarioFilesApi";
import { splitOqlIntoGoalScripts, timeoutMsForOqlScript } from "../utils/oqlGoals";
import {
  findFileByScenarioQuery,
  readScenarioFromUrl,
  readScenarioSpeedFromUrl,
  replaceScenarioFilesUrlState,
  scenarioUrlPatchForFile,
} from "../utils/scenarioFilesUrl";

function formatLogTime() {
  return new Date().toLocaleTimeString();
}

export default function ScenarioFiles() {
  const { t } = useI18n();

  const [files, setFiles] = useState([]);
  const [currentFile, setCurrentFile] = useState(null);
  const [content, setContent] = useState("");
  const [savedContent, setSavedContent] = useState("");
  const [status, setStatus] = useState({ message: "", type: "info" });
  const [logs, setLogs] = useState([]);
  const [loadingFile, setLoadingFile] = useState(false);
  const [saving, setSaving] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [speed, setSpeed] = useState(() => readScenarioSpeedFromUrl() ?? 1.0);

  const isDirty = currentFile && content !== savedContent;

  const appendLog = useCallback((type, message) => {
    setLogs((prev) => [...prev, { id: `${Date.now()}-${prev.length}`, type, message, at: formatLogTime() }]);
  }, []);

  const loadFiles = useCallback(async () => {
    try {
      const list = await fetchScenarioFilesList();
      setFiles(list);
      setStatus({ message: t("scenarioFiles.statusLoaded", { count: list.length }), type: "info" });
      return list;
    } catch (err) {
      setStatus({ message: t("scenarioFiles.statusLoadError", { error: err.message }), type: "error" });
      return [];
    }
  }, [t]);

  const selectFile = useCallback(async (file) => {
    if (!file) return;
    setCurrentFile(file);
    setLoadingFile(true);
    replaceScenarioFilesUrlState(scenarioUrlPatchForFile(file, "edit"));
    try {
      setStatus({ message: t("scenarioFiles.statusLoading"), type: "info" });
      const text = await fetchScenarioFileContent(file.path);
      setContent(text);
      setSavedContent(text);
      setStatus({ message: t("scenarioFiles.statusLoadedFile", { name: file.name }), type: "info" });
    } catch (err) {
      setContent("");
      setSavedContent("");
      setStatus({ message: t("scenarioFiles.statusFileError", { error: err.message }), type: "error" });
    } finally {
      setLoadingFile(false);
    }
  }, [t]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const list = await loadFiles();
      if (cancelled || list.length === 0) return;
      const scenarioQuery = readScenarioFromUrl();
      const match = findFileByScenarioQuery(list, scenarioQuery);
      if (match) await selectFile(match);
    })();
    return () => {
      cancelled = true;
    };
  }, [loadFiles, selectFile]);

  const saveFile = useCallback(async () => {
    if (!currentFile || saving) return;
    setSaving(true);
    replaceScenarioFilesUrlState(scenarioUrlPatchForFile(currentFile, "save"));
    try {
      setStatus({ message: t("scenarioFiles.statusSaving"), type: "info" });
      await saveScenarioFileContent(currentFile.path, content);
      setSavedContent(content);
      setStatus({ message: t("scenarioFiles.statusSaved", { name: currentFile.name }), type: "success" });
      appendLog("success", t("scenarioFiles.logSaved", { name: currentFile.name }));
    } catch (err) {
      setStatus({ message: t("scenarioFiles.statusSaveError", { error: err.message }), type: "error" });
      appendLog("error", t("scenarioFiles.logSaveFailed", { error: err.message }));
    } finally {
      setSaving(false);
    }
  }, [appendLog, content, currentFile, saving, t]);

  const runScenario = useCallback(async () => {
    if (!currentFile || executing) return;
    setExecuting(true);
    replaceScenarioFilesUrlState({
      ...scenarioUrlPatchForFile(currentFile, "execute"),
      speed,
    });
    try {
      const goalScripts = splitOqlIntoGoalScripts(content);
      if (goalScripts.length === 0) {
        throw new Error(t("scenarioFiles.errorEmptyScenario"));
      }
      setStatus({ message: t("scenarioFiles.statusExecutingGoals", { count: goalScripts.length }), type: "info" });
      appendLog(
        "info",
        t("scenarioFiles.logStarting", { name: currentFile.name, speed: String(speed) }),
      );
      appendLog("info", t("scenarioFiles.logGoalsDetected", { count: goalScripts.length }));
      let lastResponse = null;
      for (const goal of goalScripts) {
        setStatus({
          message: t("scenarioFiles.statusGoalExecuting", {
            index: goal.index,
            total: goal.total,
            name: goal.name,
          }),
          type: "info",
        });
        appendLog(
          "info",
          t("scenarioFiles.logGoalStarting", {
            index: goal.index,
            total: goal.total,
            name: goal.name,
          }),
        );
        try {
          lastResponse = await executeOqlScript({
            oql: goal.script,
            mode: "real",
            speed,
            timeoutMs: timeoutMsForOqlScript(goal.script, speed),
          });
        } catch (err) {
          appendLog(
            "error",
            t("scenarioFiles.logGoalFailed", {
              index: goal.index,
              total: goal.total,
              name: goal.name,
              error: err.message,
            }),
          );
          throw err;
        }
        appendLog(
          "success",
          t("scenarioFiles.logGoalCompleted", {
            index: goal.index,
            total: goal.total,
            name: goal.name,
          }),
        );
      }
      setStatus({
        message: t("scenarioFiles.statusGoalsComplete", { count: goalScripts.length }),
        type: "success",
      });
      if (lastResponse?.node_id) {
        appendLog("success", t("scenarioFiles.logNodeId", { node: lastResponse.node_id }));
      }
    } catch (err) {
      setStatus({ message: t("scenarioFiles.statusExecuteError", { error: err.message }), type: "error" });
      appendLog("error", t("scenarioFiles.logExecuteFailed", { error: err.message }));
    } finally {
      setExecuting(false);
    }
  }, [appendLog, content, currentFile, executing, speed, t]);

  const sidebarItems = useMemo(
    () =>
      files.map((file) => ({
        id: file.path,
        title: file.name,
        subtitle: file.path,
      })),
    [files],
  );

  const navContext = (
    <div className="section-label" style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: 0 }}>
      <span>{t("scenarioFiles.navTitle")}</span>
    </div>
  );

  const statusClass =
    status.type === "error"
      ? "scenario-files-status scenario-files-status--error"
      : status.type === "success"
        ? "scenario-files-status scenario-files-status--ok"
        : "scenario-files-status";

  return (
    <div className="mapx-shell">
      <SidebarList
        title={t("scenarioFiles.sidebarTitle")}
        items={sidebarItems}
        activeId={currentFile?.path ?? null}
        onSelect={(id) => {
          const file = files.find((f) => f.path === id);
          if (file) selectFile(file);
        }}
        onRefresh={loadFiles}
        collapseToggleId="scenario-files-list"
        collapseLabel={t("scenarioFiles.sidebarTitle")}
        collapseStorageKey="ui.scenario-files-sidebar-collapsed"
      />
      <div className="dashboard scenario-files-dashboard">
        <SharedNav navContext={navContext} />
        <div className="dash-content scenario-files-content">
          <h2>{t("scenarioFiles.pageTitle")}</h2>
          <p className="section-desc">{t("scenarioFiles.subtitle")}</p>

          <div className="scenario-files-workspace">
          <div className="hw-card scenario-files-editor-card">
            <div className="scenario-files-toolbar">
              <button
                type="button"
                className="run-btn role-force"
                onClick={saveFile}
                disabled={!currentFile || !isDirty || saving || loadingFile}
              >
                {saving ? "…" : t("scenarioFiles.save")}
              </button>
              <button
                type="button"
                className="run-btn role-force"
                onClick={runScenario}
                disabled={!currentFile || executing || loadingFile}
              >
                {executing ? "…" : t("scenarioFiles.execute")}
              </button>
              <span className="scenario-files-filename">
                {currentFile ? currentFile.name : t("scenarioFiles.noFileSelected")}
              </span>
            </div>
            <textarea
              className="scenario-files-textarea"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder={t("scenarioFiles.editorPlaceholder")}
              spellCheck={false}
              disabled={!currentFile || loadingFile}
            />
          </div>

          <div className="hw-card scenario-files-exec-card">
            <h3>{t("scenarioFiles.executionTitle")}</h3>
            <div className="scenario-files-exec-controls">
              <label className="scenario-files-speed">
                <span>{t("scenarioFiles.speedLabel")}</span>
                <input
                  type="number"
                  min="0.1"
                  max="10"
                  step="0.1"
                  value={speed}
                  onChange={(e) => {
                    const nextSpeed = Number.parseFloat(e.target.value) || 1;
                    setSpeed(nextSpeed);
                    if (currentFile) {
                      replaceScenarioFilesUrlState({
                        ...scenarioUrlPatchForFile(currentFile, "configure"),
                        speed: nextSpeed,
                      });
                    }
                  }}
                />
              </label>
            </div>
            <div className="hw-log-list scenario-files-log">
              {logs.length === 0 ? (
                <div className="mapx-empty">{t("scenarioFiles.logEmpty")}</div>
              ) : (
                logs.map((entry) => (
                  <div
                    key={entry.id}
                    className={`hw-log-row ${
                      entry.type === "error" ? "hw-log-error" : entry.type === "success" ? "hw-log-ok" : ""
                    }`}
                  >
                    <span className="hw-log-time">{entry.at}</span>
                    <span className="hw-log-detail">{entry.message}</span>
                  </div>
                ))
              )}
            </div>
          </div>
          </div>

          <div className={statusClass} role="status">
            {status.message || t("scenarioFiles.statusReady")}
          </div>
        </div>
      </div>
    </div>
  );
}
