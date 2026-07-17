import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import SharedNav from "../components/SharedNav";
import SidebarList from "../components/SidebarList";
import { createScenarioFile, deleteScenarioFile, saveScenarioFileContent } from "../api/scenarioFilesApi";
import { useI18n } from "../i18n/I18nProvider";
import { readPanelRunModeFromSearch, PANEL_RUN_MODE_PARAM, PANEL_RUN_MODES } from "../utils/panel-run-mode.js";
import {
  buildScenarioFilesSearch,
  findSidebarItemByScenarioQuery,
  panelScenarioUrlPatch,
  readScenarioFromUrl,
} from "../utils/scenarioFilesUrl.js";
import {
  buildPanelSidebarItems,
  canDeletePanelScenario,
  isPanelEditorDirty,
  isPanelScenarioFileId,
  shouldProceedWithScenarioSwitch,
} from "../utils/panelSidebar.js";
import {
  defaultNewScenarioContent,
  normalizeScenarioFilePath,
} from "../utils/panelScenarioCreate.js";
import { rem } from "@semcod/frontend-services/designRem.js";

const VALVE_IDS = [
  "valve-1", "valve-2", "valve-3", "valve-4",
  "valve-5", "valve-6", "valve-7", "valve-8",
  "valve-nc", "valve-sc", "valve-wc",
];
const SENSOR_IDS = ["ai01", "ai02", "ai03", "ai04", "ai05", "ai06", "ai07", "ai08"];
const HUI_HOLD_KEYS = [
  ["head-inflate", "Głowa +"],
  ["head-deflate", "Głowa -"],
  ["lp-pwm-plus5", "LP +5"],
  ["lp-pwm-plus10", "LP +10"],
  ["lp-pwm-minus5", "LP -5"],
  ["lp-pwm-minus10", "LP -10"],
  ["lp-bleed", "LP bleed"],
];
const LUNG_PANEL_PRESETS = {
  "lung-pz-500x5": { steps: 1000000, speed: 100000000, cycles: 5, pause: 0.5 },
  "lung-pz-1000x3": { steps: 1000000, speed: 100000000, cycles: 3, pause: 0.5 },
};

function numericPresetField(value, fallback) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function normalizeLungPresetArgs(raw, fallback) {
  const src = raw && typeof raw === "object" ? raw : {};
  return {
    steps: Math.round(numericPresetField(src.steps ?? src.stroke_steps ?? src.strokeSteps, fallback.steps)),
    speed: Math.round(numericPresetField(src.speed ?? src.target_velocity ?? src.targetVelocity, fallback.speed)),
    cycles: Math.round(numericPresetField(src.cycles, fallback.cycles)),
    pause: numericPresetField(src.pause, fallback.pause),
  };
}

function actionBodyArgs(action) {
  if (!action || typeof action !== "object") return null;
  const body = action.body && typeof action.body === "object" ? action.body : action;
  const nested = body.args && typeof body.args === "object" ? body.args : null;
  return nested ? { ...body, ...nested } : body;
}

const BUILTIN_SCENARIOS = [
  { name: "— wybierz scenariusz —", oql: "" },
  {
    name: "Health-check sensorów",
    oql: "VERSION: 4\nSCENARIO: Health-check sensorow\nGOAL:\n  SET NAME 'Odczyt sensorow ADC'\n  GET 'ai01'\n  GET 'ai02'\n  GET 'ai03'",
  },
  {
    name: "Test zaworów (sekwencja)",
    oql: "VERSION: 4\nSCENARIO: Test zaworow\nGOAL:\n  SET NAME 'Sekwencja otwarcia/zamkniecia'\n  SET 'valve-1' 'open'\n  SET WAIT '1 s'\n  SET 'valve-1' 'closed'\n  SET 'valve-2' 'open'\n  SET WAIT '1 s'\n  SET 'valve-2' 'closed'",
  },
  {
    name: "Test pompy (rampa)",
    oql: "VERSION: 4\nSCENARIO: Rampa pompy\nGOAL:\n  SET NAME 'Rampa mocy pompy'\n  SET 'pump' 25\n  SET WAIT '1 s'\n  SET 'pump' 50\n  SET WAIT '1 s'\n  SET 'pump' 0",
  },
];

const OQL_SNIPPETS = [
  {
    title: "Struktura",
    color: "#64748b",
    items: [
      { label: "VERSION: 4", t: "VERSION: 4\n" },
      { label: "SCENARIO: …", t: "SCENARIO: Mój test\n" },
      { label: "GOAL:", t: "GOAL:\n" },
      { label: "SET NAME '…'", t: "  SET NAME 'Opis'\n" },
      { label: "SET WAIT '1 s'", t: "  SET WAIT '1 s'\n" },
      { label: "SET WAIT '500 ms'", t: "  SET WAIT '500 ms'\n" },
    ],
  },
  {
    title: "Zawory",
    color: "#10b981",
    items: VALVE_IDS.flatMap((id) => [
      { label: id + " open", t: `  SET '${id}' 'open'\n` },
      { label: id + " closed", t: `  SET '${id}' 'closed'\n` },
    ]),
  },
  {
    title: "Pompa",
    color: "#f59e0b",
    items: [
      { label: "pump 0%", t: "  SET 'pump' 0\n" },
      { label: "pump 25%", t: "  SET 'pump' 25\n" },
      { label: "pump 50%", t: "  SET 'pump' 50\n" },
      { label: "pump 100%", t: "  SET 'pump' 100\n" },
    ],
  },
  {
    title: "Płuco",
    color: "#a855f7",
    items: [
      { label: "lung start", t: "  SET 'lung' 5\n" },
      { label: "lung stop", t: "  SET 'lung' 0\n" },
      { label: "lung wait stop", t: "  SET 'lung' 5\n  SET WAIT '500 ms'\n  SET 'lung' 0\n" },
    ],
  },
  {
    title: "Sensory (ADC)",
    color: "#06b6d4",
    items: SENSOR_IDS.map((id) => ({ label: "GET " + id, t: `  GET '${id}'\n` })),
  },
];

const DEFAULT_EDITOR_OQL = `VERSION: 4
SCENARIO: Mój test
GOAL:
  SET NAME 'Opis'
  SET 'pump' 25
  SET WAIT '1 s'
  SET 'pump' 0`;

const GROUP_COLLAPSE_KEY = "oqlos_panel_collapsed_groups";
const SNIP_COLLAPSE_KEY = "oqlos_panel_collapsed_snippets";
const MY_SCENARIOS_KEY = "oqlos_panel_scenarios";

export default function Panel() {
  const { t } = useI18n();
  const [searchParams, setSearchParams] = useSearchParams();

  // Mode and Skip Waits state synchronized with URL search params
  const runMode = readPanelRunModeFromSearch(`?${searchParams.toString()}`);
  const skipWaits = searchParams.get("skip_waits") === "true";

  const [editorText, setEditorText] = useState(DEFAULT_EDITOR_OQL);
  const [nodeBadge, setNodeBadge] = useState({ text: "łączenie…", cls: "warn" });
  const [svcBadge, setSvcBadge] = useState("—");
  const [bannerMsg, setBannerMsg] = useState("");
  const [results, setResults] = useState([]);
  const [logFilter, setLogFilter] = useState("");

  const [collapsedGroups, setCollapsedGroups] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(GROUP_COLLAPSE_KEY)) || {};
    } catch {
      return {};
    }
  });

  const [collapsedSnippets, setCollapsedSnippets] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(SNIP_COLLAPSE_KEY)) || {};
    } catch {
      return {};
    }
  });

  const [myScenarios, setMyScenarios] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(MY_SCENARIOS_KEY)) || [];
    } catch {
      return [];
    }
  });

  const [serverScenarios, setServerScenarios] = useState([]);
  const [fileScenarios, setFileScenarios] = useState([]);
  const [scenarioListStatus, setScenarioListStatus] = useState("Ładowanie plików z /api/v1/editor/files…");
  const [selectedScenarioId, setSelectedScenarioId] = useState("");
  const [savedEditorText, setSavedEditorText] = useState("");
  const [savingScenario, setSavingScenario] = useState(false);
  const [deletingScenario, setDeletingScenario] = useState(false);
  const urlScenarioBootRef = useRef(false);

  // Live Monitor State
  const [monMetric, setMonMetric] = useState("cpu");
  const [monInterval, setMonInterval] = useState(3);
  const [monIsRunning, setMonIsRunning] = useState(false);
  const [monVal, setMonVal] = useState("—");
  const [monMeta, setMonMeta] = useState("");
  const monDataRef = useRef([]);
  const monTimerRef = useRef(null);
  const canvasRef = useRef(null);

  // Auto-refresh panel status
  const [autoRefresh, setAutoRefresh] = useState(false);
  const autoRefreshTimerRef = useRef(null);

  const editorRef = useRef(null);

  // API wrappers
  const callApi = async (path, body) => {
    try {
      const r = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      let data = null;
      try {
        data = await r.json();
      } catch {}
      return { status: r.status, data };
    } catch (e) {
      return { status: 500, data: null };
    }
  };

  const getStatus = useCallback(async () => {
    try {
      const r = await fetch("/health");
      const h = await r.json();
      setSvcBadge(`${h.service || "oqlos"} v${h.version || "?"}`);
    } catch {
      setSvcBadge("offline");
    }

    const { status, data } = await callApi("/api/v1/oql/manage", { verb: "health" });
    if (status === 503) {
      setNodeBadge({ text: "transport OFF (nie-controller)", cls: "warn" });
      setBannerMsg(
        "Ten panel działa najlepiej na instancji oqlos w roli controller — wtedy steruje zdalnym węzłem sprzętowym przez MQTT."
      );
    } else if (status >= 200 && status < 300 && data && data.ok) {
      setNodeBadge({
        text: `węzeł: ${data.node_id || "?"} · ${(data.result || {}).mode || "?"}`,
        cls: "ok",
      });
    } else {
      setNodeBadge({ text: "węzeł niedostępny", cls: "fail" });
    }
  }, []);

  // Set up auto-refresh
  useEffect(() => {
    if (autoRefresh) {
      getStatus();
      autoRefreshTimerRef.current = setInterval(getStatus, 10000);
    } else {
      if (autoRefreshTimerRef.current) {
        clearInterval(autoRefreshTimerRef.current);
        autoRefreshTimerRef.current = null;
      }
    }
    return () => {
      if (autoRefreshTimerRef.current) {
        clearInterval(autoRefreshTimerRef.current);
      }
    };
  }, [autoRefresh, getStatus]);

  useEffect(() => {
    getStatus();
  }, [getStatus]);

  // Load scenarios from DB and Files
  const loadScenarios = useCallback(async () => {
    // 1. Files from editor
    setScenarioListStatus("Ładowanie plików z /api/v1/editor/files…");
    try {
      const r = await fetch(`/api/v1/editor/files?ts=${Date.now()}`, { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const data = await r.json();
      const files = Array.isArray(data.files) ? data.files : [];
      const parsed = files
        .filter((f) => f && !f.is_directory && /\.oql$/i.test(String(f.name || "")))
        .sort((a, b) => String(a.name || "").localeCompare(String(b.name || ""), "pl", { sensitivity: "base" }))
        .map((f) => ({
          name: f.path && f.path !== f.name ? `${f.name} — ${f.path}` : f.name,
          oql: null,
          _file: true,
          _filePath: f.path,
          _group: "Pliki scenariuszy (/ui/scenario-files)",
        }));
      setFileScenarios(parsed);
      setScenarioListStatus(`Wczytano ${parsed.length} plików .oql z /api/v1/editor/files.`);
    } catch (e) {
      setFileScenarios([]);
      setScenarioListStatus("Nie udało się wczytać plików .oql: " + e.message);
      setBannerMsg("Nie udało się wczytać listy plików scenariuszy: " + e.message);
    }

    // 2. Database scenarios
    try {
      const r = await fetch("/api/v1/scenarios/fetch");
      if (r.ok) {
        const list = await r.json();
        if (Array.isArray(list)) {
          const parsed = list
            .map((s) => ({
              name: s.id || s.name || "?",
              oql: typeof s.source === "string" && s.source ? s.source : null,
              _srv: s,
              _group: "Serwer DB",
            }))
            .filter((s) => s.name && s.oql);
          setServerScenarios(parsed);
        }
      }
    } catch {}
  }, []);

  useEffect(() => {
    loadScenarios();
  }, [loadScenarios]);

  const sidebarItems = useMemo(
    () => buildPanelSidebarItems({
      fileScenarios,
      myScenarios,
      builtinTemplates: BUILTIN_SCENARIOS.slice(1),
      serverScenarios,
    }),
    [fileScenarios, myScenarios, serverScenarios],
  );

  const selectedScenarioTitle = sidebarItems.find((i) => i.id === selectedScenarioId)?.title || "";
  const selectedScenarioIsFile = isPanelScenarioFileId(selectedScenarioId);
  const editorIsDirty = isPanelEditorDirty({ selectedScenarioId, editorText, savedEditorText });

  const syncScenarioUrl = useCallback((item, action = "edit") => {
    if (!item) return;
    const patch = panelScenarioUrlPatch(item, action);
    const nextSearch = buildScenarioFilesSearch(`?${searchParams.toString()}`, patch);
    setSearchParams(new URLSearchParams(nextSearch.slice(1) || ""), { replace: true });
  }, [searchParams, setSearchParams]);

  const handleSelectScenario = useCallback(async (id) => {
    setSelectedScenarioId(id);
    const item = sidebarItems.find((i) => i.id === id);
    const s = item?._scenario;
    if (!s) return;

    if (s._file && s._filePath && !s.oql) {
      try {
        setBannerMsg("");
        const encodedPath = String(s._filePath).split("/").map(encodeURIComponent).join("/");
        const r = await fetch(`/api/v1/editor/file/${encodedPath}`, { cache: "no-store" });
        if (!r.ok) throw new Error("HTTP " + r.status);
        const data = await r.json();
        s.oql = typeof data.content === "string" ? data.content : "";
      } catch (e) {
        setBannerMsg("Nie udało się wczytać pliku scenariusza: " + e.message);
        return;
      }
    }

    if (s && s.oql) {
      setEditorText(s.oql);
      setSavedEditorText(s.oql);
      syncScenarioUrl(item);
    }
  }, [sidebarItems, syncScenarioUrl]);

  const requestSelectScenario = useCallback(async (id) => {
    if (!shouldProceedWithScenarioSwitch({
      selectedScenarioId,
      nextId: id,
      editorText,
      savedEditorText,
      confirmDiscard: () => window.confirm(
        "Masz niezapisane zmiany w edytorze. Przejść do innego scenariusza bez zapisu?",
      ),
    })) {
      return;
    }
    await handleSelectScenario(id);
  }, [selectedScenarioId, editorText, savedEditorText, handleSelectScenario]);

  useEffect(() => {
    if (urlScenarioBootRef.current || sidebarItems.length === 0) return;
    const query = readScenarioFromUrl(`?${searchParams.toString()}`);
    if (!query) return;
    const item = findSidebarItemByScenarioQuery(sidebarItems, query);
    if (!item) return;
    urlScenarioBootRef.current = true;
    handleSelectScenario(item.id);
  }, [sidebarItems, searchParams, handleSelectScenario]);

  const saveLocalScenario = () => {
    const oql = editorText.trim();
    if (!oql) {
      setBannerMsg("Edytor jest pusty — nie ma czego zapisać.");
      return;
    }
    const name = (prompt("Nazwa scenariusza:") || "").trim();
    if (!name) return;
    const filtered = myScenarios.filter((s) => s.name !== name);
    const updated = [...filtered, { name, oql }];
    setMyScenarios(updated);
    localStorage.setItem(MY_SCENARIOS_KEY, JSON.stringify(updated));
    setBannerMsg(`Zapisano scenariusz „${name}” (w przeglądarce).`);
  };

  const saveSelectedScenario = async () => {
    const oql = editorText.trim();
    if (!oql) {
      setBannerMsg("Edytor jest pusty — nie ma czego zapisać.");
      return;
    }
    if (selectedScenarioIsFile) {
      const path = selectedScenarioId.slice(5);
      setSavingScenario(true);
      try {
        await saveScenarioFileContent(path, editorText);
        setSavedEditorText(editorText);
        const item = sidebarItems.find((i) => i.id === selectedScenarioId);
        if (item) syncScenarioUrl(item, "save");
        setBannerMsg(`Zapisano plik „${path}”.`);
      } catch (e) {
        setBannerMsg("Nie udało się zapisać pliku: " + e.message);
      } finally {
        setSavingScenario(false);
      }
      return;
    }
    saveLocalScenario();
  };

  const createNewScenarioFile = async () => {
    if (creatingScenario) return;
    if (
      selectedScenarioId
      && editorText !== savedEditorText
      && !window.confirm("Masz niezapisane zmiany. Utworzyć nowy plik bez zapisu bieżącego scenariusza?")
    ) {
      return;
    }
    const raw = prompt("Nazwa nowego pliku (.oql):", "moj-scenariusz.oql");
    if (!raw) return;
    try {
      const path = normalizeScenarioFilePath(raw);
      const duplicate = fileScenarios.some(
        (f) => String(f._filePath || "").toLowerCase() === path.toLowerCase(),
      );
      if (duplicate) {
        setBannerMsg(`Plik „${path}” już istnieje — wybierz inną nazwę.`);
        return;
      }
      const content = defaultNewScenarioContent(path);
      setCreatingScenario(true);
      setBannerMsg("");
      await createScenarioFile(path, content);
      await loadScenarios();
      setSelectedScenarioId(`file:${path}`);
      setEditorText(content);
      setSavedEditorText(content);
      syncScenarioUrl({ id: `file:${path}`, title: path.replace(/\.oql$/i, "") }, "edit");
      setBannerMsg(`Utworzono i otwarto plik „${path}”.`);
    } catch (e) {
      setBannerMsg("Nie udało się utworzyć pliku: " + e.message);
    } finally {
      setCreatingScenario(false);
    }
  };

  const deleteSelectedScenario = async () => {
    if (!canDeletePanelScenario(selectedScenarioId)) {
      setBannerMsg("Usuń można tylko plik .oql lub własny scenariusz z localStorage.");
      return;
    }
    if (selectedScenarioIsFile) {
      const path = selectedScenarioId.slice(5);
      if (!window.confirm(`Usunąć plik scenariusza „${path}”? Tej operacji nie można cofnąć.`)) {
        return;
      }
      setDeletingScenario(true);
      try {
        await deleteScenarioFile(path);
        await loadScenarios();
        setSelectedScenarioId("");
        setEditorText(DEFAULT_EDITOR_OQL);
        setSavedEditorText("");
        setBannerMsg(`Usunięto plik „${path}”.`);
      } catch (e) {
        setBannerMsg("Nie udało się usunąć pliku: " + e.message);
      } finally {
        setDeletingScenario(false);
      }
      return;
    }
    const name = selectedScenarioId.slice(3);
    const updated = myScenarios.filter((x) => x.name !== name);
    setMyScenarios(updated);
    localStorage.setItem(MY_SCENARIOS_KEY, JSON.stringify(updated));
    setBannerMsg(`Usunięto „${name}”.`);
    setSelectedScenarioId("");
  };

  // Sparkline Chart draw helper
  const drawSpark = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);
    const data = monDataRef.current;
    if (data.length < 2) return;
    const min = Math.min(...data);
    const max = Math.max(...data);
    const rng = max - min || 1;
    ctx.strokeStyle = "#3b82f6";
    ctx.lineWidth = 2;
    ctx.beginPath();
    data.forEach((v, i) => {
      const x = (i / (data.length - 1)) * (W - 4) + 2;
      const y = H - 3 - ((v - min) / rng) * (H - 8);
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.stroke();
  }, []);

  // Poll live monitor
  const monPoll = useCallback(async () => {
    const metric = monMetric;
    let val = null;
    let unit = "";
    try {
      if (metric === "cpu") {
        const { data } = await callApi("/api/v1/oql/manage", { verb: "pi-diagnostics" });
        val = data && data.result ? data.result.cpu_temp_c : null;
        unit = " °C";
      } else {
        const { data } = await callApi("/api/v1/oql/manage", { verb: "sensor", args: { sensor_id: metric } });
        val = data && data.ok && data.result ? data.result.value : null;
      }
    } catch {
      val = null;
    }
    if (val != null && !isNaN(+val)) {
      monDataRef.current.push(+val);
      if (monDataRef.current.length > 120) {
        monDataRef.current.shift();
      }
    }
    setMonVal((val != null ? val : "N/A") + unit);
    setMonMeta(
      monDataRef.current.length
        ? `min ${Math.min(...monDataRef.current).toFixed(1)} / max ${Math.max(...monDataRef.current).toFixed(
            1
          )} / n=${monDataRef.current.length}`
        : "brak danych"
    );
    drawSpark();
  }, [monMetric, drawSpark]);

  // Toggle Live Monitor
  const toggleMonitor = () => {
    if (monIsRunning) {
      if (monTimerRef.current) {
        clearInterval(monTimerRef.current);
        monTimerRef.current = null;
      }
      setMonIsRunning(false);
    } else {
      monDataRef.current = [];
      setMonIsRunning(true);
      monPoll();
      const iv = Math.max(1, Math.min(60, Number(monInterval) || 3)) * 1000;
      monTimerRef.current = setInterval(monPoll, iv);
    }
  };

  // Clean up monitor on unmount
  useEffect(() => {
    return () => {
      if (monTimerRef.current) {
        clearInterval(monTimerRef.current);
      }
    };
  }, []);

  // Results logs management
  const appendLogEntry = useCallback((title, env, status, sent, req) => {
    const rawClass = () => {
      const r = env && typeof env.result === "object" && env.result ? env.result : null;
      const innerFail = !!(r && (r.success === false || r.ok === false));
      if (status >= 200 && status < 300 && env && env.ok && !innerFail) return "ok";
      const blob = JSON.stringify(env || {});
      const naPatterns =
        /not available|all connection attempts failed|no active instance|permission denied|failed to connect|is not available|de-energized|deenergized|energized|stopped|transport off|timed out|disabled/i;
      if (status === 503 || innerFail || naPatterns.test(blob)) return "na";
      return "fail";
    };

    const cClass = rawClass();
    const cLabel = cClass === "ok" ? "OK" : cClass === "na" ? "N/D" : "BŁĄD";
    const cHint =
      cClass === "ok"
        ? ""
        : cClass === "na"
        ? "sprzęt niedostępny / brak uprawnień — nie błąd panelu"
        : "realny błąd";

    const summarize = (val) => {
      if (!val) return "brak odpowiedzi";
      const res = val.result;
      if (res && typeof res === "object") {
        if ("devices" in res) {
          const list = (res.devices || []).map(
            (d) =>
              `${d.vendor_id}:${d.product_id} ${d.product || d.vendor || ""}${
                d.tty && d.tty.length ? " [" + d.tty.join(",") + "]" : ""
              } @${d.port_path}`
          );
          return `${res.count} urządzeń USB\n  · ` + list.join("\n  · ");
        }
        if ("cpu_temp_c" in res) {
          return `${res.model || "Pi"} · CPU ${res.cpu_temp_c}°C · USB×${res.usb_device_count} · porty: ${(
            res.serial_ports || []
          ).join(", ") || "—"}`;
        }
        if ("passed" in res) {
          return `kroki: ${res.passed} OK / ${res.failed} błąd (z ${res.total || "?"})${
            res.errors && res.errors.length ? " · " + res.errors.join("; ") : ""
          }`;
        }
        if ("mode" in res) {
          return `mode=${res.mode}${res.overall_ok !== undefined ? " · overall_ok=" + res.overall_ok : ""}`;
        }
        if ("value" in res) {
          return `${res.sensor_id || ""} = ${res.value}`;
        }
        if ("reset" in res) {
          return res.success ? `reset OK: ${res.reset || ""}` : `błąd: ${res.error || val.error || "?"}`;
        }
        if ("success" in res) {
          return res.success
            ? res.data !== undefined
              ? JSON.stringify(res.data)
              : "success"
            : `błąd: ${res.error || val.error || "?"}`;
        }
        return JSON.stringify(res).slice(0, 140);
      }
      return val.error || (val.ok ? "OK" : "błąd");
    };

    const recv = summarize(env);
    const timeStr = new Date().toLocaleTimeString("pl-PL");

    const newEntry = {
      id: `${Date.now()}-${Math.random()}`,
      ts: new Date().toISOString(),
      time: timeStr,
      title,
      status,
      cls: cClass,
      label: cLabel,
      hint: cHint,
      sent,
      recv,
      raw: env,
      req,
    };

    setResults((prev) => [newEntry, ...prev]);
  }, []);

  const runManage = async (verb, args, label) => {
    const payload = { verb, args: args || {} };
    const sent = `POST /api/v1/oql/manage  ${JSON.stringify(payload)}`;
    const { status, data } = await callApi("/api/v1/oql/manage", payload);
    if (status === 503) {
      setBannerMsg(
        "Transport OQL wyłączony (rola ≠ controller). Uruchom oqlos w roli controller, aby sterować węzłem sprzętowym."
      );
    }
    appendLogEntry(label || `manage: ${verb}`, data, status, sent, {
      ep: "/api/v1/oql/manage",
      body: payload,
      title: label || `manage: ${verb}`,
    });
  };

  const runOql = async (oql, kind, label) => {
    const k = kind || "command";
    const payload = { oql, kind: k, mode: runMode, skip_waits: skipWaits };
    const sent = `POST /api/v1/oql/execute  ${JSON.stringify({
      kind: k,
      mode: runMode,
      skip_waits: skipWaits,
      oql,
    })}`;
    const { status, data } = await callApi("/api/v1/oql/execute", payload);
    if (status === 503) {
      setBannerMsg("Transport OQL wyłączony (rola ≠ controller). Uruchom oqlos w roli controller.");
    }
    appendLogEntry(label || `OQL: ${oql.split("\n")[0]}`, data, status, sent, {
      ep: "/api/v1/oql/execute",
      body: payload,
      title: label || `OQL: ${oql.split("\n")[0]}`,
    });
  };

  const runItem = (it) => {
    if (it.kind === "manage") {
      const args = it.presetKey
        ? LUNG_PANEL_PRESETS[it.presetKey] || LUNG_PANEL_PRESETS["lung-pz-500x5"]
        : it.args;
      return runManage(it.verb, args, `${it.label}${it.verb ? " (" + it.verb + ")" : ""}`);
    }
    return runOql(it.oql, "command", `OQL · ${it.label}`);
  };

  const runGroup = async (group) => {
    if (group.runAll === false) return;
    if (
      group.items.some((it) => it.act) &&
      !confirm(`Grupa „${group.title}” zawiera akcje na realnym sprzęcie. Uruchomić wszystkie po kolei?`)
    ) {
      return;
    }
    for (const it of group.items) {
      await runItem(it);
      await new Promise((r) => setTimeout(r, 250));
    }
  };

  const runEditor = () => {
    let txt = editorText.trim();
    if (!txt) {
      setBannerMsg("Edytor jest pusty.");
      return;
    }
    setBannerMsg("");
    const item = sidebarItems.find((i) => i.id === selectedScenarioId);
    if (item) syncScenarioUrl(item, "execute");
    // Normalize script
    const hasVersion = /^\s*VERSION\s*:\s*\d+\s*$/im.test(txt);
    const isNamedV4Goal = /^\s*GOAL\s*:\s*$/im.test(txt) && /^[ \t]+SET\s+NAME\b/im.test(txt);
    if (!hasVersion && isNamedV4Goal) {
      txt = "VERSION: 4\n" + txt;
    }
    runOql(txt, "script", `Scenariusz (${runMode})`);
  };

  // Clipboard Helpers
  const copyText = (text, e) => {
    const btn = e.currentTarget;
    const orig = btn.textContent;
    const flash = (msg) => {
      btn.textContent = msg;
      btn.disabled = true;
      setTimeout(() => {
        btn.textContent = orig;
        btn.disabled = false;
      }, 1200);
    };

    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard
        .writeText(text)
        .then(() => flash("✓ ok"))
        .catch(() => {
          if (legacyCopy(text)) flash("✓ ok");
          else flash("✗ błąd");
        });
    } else {
      if (legacyCopy(text)) flash("✓ ok");
      else flash("✗ błąd");
    }
  };

  const legacyCopy = (text) => {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.top = "-1000px";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    ta.setSelectionRange(0, text.length);
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch {
      ok = false;
    }
    document.body.removeChild(ta);
    return ok;
  };

  // Import preset groups
  const loadHardwareMapLungPresets = useCallback(async () => {
    try {
      const r = await fetch("/api/v3/hardware/mapping?ts=" + Date.now(), { cache: "no-store" });
      if (!r.ok) return;
      const data = await r.json();
      const actions = data.mapping && data.mapping.actions && typeof data.mapping.actions === "object" ? data.mapping.actions : {};
      for (const key of Object.keys(LUNG_PANEL_PRESETS)) {
        if (actions[key]) {
          LUNG_PANEL_PRESETS[key] = normalizeLungPresetArgs(actionBodyArgs(actions[key]), LUNG_PANEL_PRESETS[key]);
        }
      }
    } catch {}
  }, []);

  useEffect(() => {
    loadHardwareMapLungPresets();
  }, [loadHardwareMapLungPresets]);

  // Insert Snippet at Editor Cursor
  const insertSnippet = (snippetText) => {
    const ta = editorRef.current;
    if (!ta) return;
    const start = ta.selectionStart ?? ta.value.length;
    const end = ta.selectionEnd ?? ta.value.length;
    const oldText = ta.value;
    const nextText = oldText.slice(0, start) + snippetText + oldText.slice(end);
    setEditorText(nextText);
    const newPos = start + snippetText.length;
    setTimeout(() => {
      ta.selectionStart = ta.selectionEnd = newPos;
      ta.focus();
    }, 0);
  };

  // Predefined Groups Configuration
  const groupsList = [
    {
      title: "Diagnostyka",
      color: "#3b82f6",
      items: [
        { label: "Health", kind: "manage", verb: "health" },
        { label: "Identify", kind: "manage", verb: "identify", args: { scan: "never" } },
        { label: "Diagnose", kind: "manage", verb: "diagnose" },
        { label: "Stack snapshot", kind: "manage", verb: "stack-snapshot" },
        { label: "Temperatura", kind: "manage", verb: "temperature" },
        { label: "Recover (safe)", kind: "manage", verb: "recover", args: { scope: "safe" }, act: true },
      ],
    },
    {
      title: "Zawory",
      color: "#10b981",
      items: VALVE_IDS.flatMap((id) => [
        { label: id + " OPEN", kind: "oql", oql: `SET '${id}' 'open'`, act: true },
        { label: id + " CLOSE", kind: "oql", oql: `SET '${id}' 'closed'`, act: true },
      ]),
    },
    {
      title: "Pompa",
      color: "#f59e0b",
      items: [
        { label: "0%", kind: "oql", oql: "SET 'pump' 0", act: true },
        { label: "25%", kind: "oql", oql: "SET 'pump' 25", act: true },
        { label: "50%", kind: "oql", oql: "SET 'pump' 50", act: true },
        { label: "100%", kind: "oql", oql: "SET 'pump' 100", act: true },
        { label: "STOP", kind: "manage", verb: "pump", args: { power_pct: 0 }, act: true },
      ],
    },
    {
      title: "Płuco (Tic T249)",
      color: "#a855f7",
      runAll: false,
      items: [
        {
          label: "Status",
          kind: "manage",
          verb: "diagnostic-command",
          args: { peripheral_id: "motor-tic249", command: "status" },
        },
        { label: "AL status", kind: "manage", verb: "artificial-lung-status" },
        { label: "P-Z fast x5", kind: "manage", verb: "lung", presetKey: "lung-pz-500x5", act: true },
        { label: "P-Z fast x3", kind: "manage", verb: "lung", presetKey: "lung-pz-1000x3", act: true },
        { label: "HUI AL START", kind: "manage", verb: "hui-al-start", act: true },
        { label: "HUI AL STOP", kind: "manage", verb: "hui-al-stop", act: true },
        { label: "Stop", kind: "manage", verb: "lung-stop", act: true },
        { label: "Disable", kind: "manage", verb: "lung-disable", act: true },
      ],
    },
    {
      title: "HUI maska",
      color: "#84cc16",
      runAll: false,
      items: [
        ...HUI_HOLD_KEYS.flatMap(([key, label]) => [
          { label: label + " START", kind: "manage", verb: "hui-hold-start", args: { key }, act: true },
          { label: label + " STOP", kind: "manage", verb: "hui-hold-stop", args: { key }, act: true },
        ]),
        { label: "Wszystko STOP", kind: "manage", verb: "hui-shutdown", act: true },
      ],
    },
    {
      title: "Sensory (ADC)",
      color: "#06b6d4",
      items: SENSOR_IDS.map((id) => ({
        label: id.toUpperCase(),
        kind: "manage",
        verb: "sensor",
        args: { sensor_id: id },
      })),
    },
    {
      title: "Diagnostyka RPi3 / USB",
      color: "#ec4899",
      items: [
        { label: "Lista urządzeń USB", kind: "manage", verb: "usb-list" },
        { label: "Diagnostyka Pi", kind: "manage", verb: "pi-diagnostics" },
        { label: "Reset USB Tic (1ffb)", kind: "manage", verb: "usb-reset", args: { vendor_id: "1ffb" }, act: true },
        { label: "Reset USB CH340 (1a86)", kind: "manage", verb: "usb-reset", args: { vendor_id: "1a86" }, act: true },
      ],
    },
  ];

  // Collapsing utilities
  const toggleGroupCollapse = (title) => {
    const next = { ...collapsedGroups, [title]: !collapsedGroups[title] };
    setCollapsedGroups(next);
    localStorage.setItem(GROUP_COLLAPSE_KEY, JSON.stringify(next));
  };

  const setAllGroupsCollapsedState = (collapsed) => {
    const next = {};
    if (collapsed) {
      groupsList.forEach((g) => {
        next[g.title] = true;
      });
    }
    setCollapsedGroups(next);
    localStorage.setItem(GROUP_COLLAPSE_KEY, JSON.stringify(next));
  };

  const toggleSnippetCollapse = (title) => {
    const next = { ...collapsedSnippets, [title]: !collapsedSnippets[title] };
    setCollapsedSnippets(next);
    localStorage.setItem(SNIP_COLLAPSE_KEY, JSON.stringify(next));
  };

  // Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      const tag = (document.activeElement && document.activeElement.tagName) || "";
      const inField = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        runEditor();
      } else if ((e.ctrlKey || e.metaKey) && (e.key === "s" || e.key === "S")) {
        e.preventDefault();
        saveLocalScenario();
      } else if (e.key === "/" && !inField) {
        e.preventDefault();
        const f = document.getElementById("logFilterInput");
        if (f) f.focus();
      } else if (e.key === "Escape" && document.activeElement?.id === "logFilterInput") {
        setLogFilter("");
        document.activeElement.blur();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  });

  // Export Results Actions
  const resultsDoc = () => ({
    exported_at: new Date().toISOString(),
    node: nodeBadge.text,
    count: results.length,
    results: results.map((r) => ({
      ts: r.ts,
      title: r.title,
      status: r.status,
      class: r.cls,
      sent: r.sent,
      ok: !!r.raw?.ok,
      node_id: r.raw?.node_id,
      received_summary: r.recv,
      response: r.raw,
    })),
  });

  const downloadResults = () => {
    if (!results.length) {
      setBannerMsg("Brak wyników do pobrania.");
      return;
    }
    const doc = resultsDoc();
    const blob = new Blob([JSON.stringify(doc, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    a.href = url;
    a.download = `oqlos-panel-results-${stamp}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  };

  const downloadCsv = () => {
    if (!results.length) {
      setBannerMsg("Brak wyników do pobrania.");
      return;
    }
    const cols = ["ts", "title", "status", "class", "ok", "node_id", "sent", "received_summary"];
    const q = (v) => '"' + String(v == null ? "" : v).replace(/"/g, '""').replace(/\r?\n/g, " ") + '"';
    const lines = [cols.join(",")].concat(
      results.map((r) =>
        [
          r.ts,
          r.title,
          r.status,
          r.cls,
          !!r.raw?.ok,
          r.raw?.node_id,
          r.sent,
          r.recv,
        ]
          .map(q)
          .join(",")
      )
    );
    const blob = new Blob(["\ufeff" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    a.href = url;
    a.download = `oqlos-panel-results-${stamp}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  };

  const copyAllResults = (e) => {
    if (!results.length) {
      setBannerMsg("Brak wyników do skopiowania.");
      return;
    }
    copyText(JSON.stringify(resultsDoc(), null, 2), e);
  };

  const filteredLogs = results.filter((r) => {
    if (!logFilter.trim()) return true;
    const q = logFilter.toLowerCase();
    return (
      r.title.toLowerCase().includes(q) ||
      (r.sent && r.sent.toLowerCase().includes(q)) ||
      r.recv.toLowerCase().includes(q)
    );
  });

  const editorToolbar = (placement) => (
    <div className={`panel-editor-toolbar panel-editor-toolbar--${placement}`}>
      <span className="panel-editor-toolbar-label">Tryb:</span>
      <span className="toggle-mode-group panel-editor-mode-group">
        {["execute", "dry-run", "validate"].map((m) => (
          <button
            key={m}
            type="button"
            className={`mode-btn ${runMode === m ? "active" : ""}`}
            onClick={() => {
              const newParams = new URLSearchParams(searchParams);
              newParams.set(PANEL_RUN_MODE_PARAM, m);
              if (PANEL_RUN_MODES.includes(newParams.get("mode") || "")) {
                newParams.delete("mode");
              }
              setSearchParams(newParams);
            }}
          >
            {m === "execute" ? "Wykonaj" : m === "dry-run" ? "Symulacja" : "Walidacja"}
          </button>
        ))}
      </span>

      <label className="wait-toggle panel-editor-wait-toggle">
        <input
          type="checkbox"
          checked={skipWaits}
          onChange={(e) => {
            const newParams = new URLSearchParams(searchParams);
            newParams.set("skip_waits", String(e.target.checked));
            setSearchParams(newParams);
          }}
        />
        pomiń WAIT
      </label>

      <div className="panel-editor-toolbar-spacer" />

      {selectedScenarioIsFile ? (
        <button
          type="button"
          className="run-btn role-force"
          onClick={saveSelectedScenario}
          disabled={!editorIsDirty || savingScenario}
        >
          {savingScenario ? "…" : "💾 Zapisz plik"}
        </button>
      ) : null}

      <button type="button" className="run-btn run-btn--primary role-force" onClick={runEditor}>
        ▶ Uruchom scenariusz
      </button>
      <button type="button" className="run-btn role-force" onClick={(e) => copyText(editorText, e)}>
        📋 Kopiuj
      </button>
      <button type="button" className="run-btn role-force" onClick={() => setEditorText("")}>
        Wyczyść
      </button>
    </div>
  );

  const scenarioSidebarFooter = (
    <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
      <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
        <button
          type="button"
          className="run-btn run-btn--primary role-force"
          onClick={createNewScenarioFile}
          disabled={creatingScenario}
        >
          {creatingScenario ? "…" : "+ Nowy .oql"}
        </button>
        <button
          type="button"
          className="run-btn role-force"
          onClick={saveSelectedScenario}
          disabled={selectedScenarioIsFile && (!editorIsDirty || savingScenario)}
        >
          {selectedScenarioIsFile ? "💾 Zapisz plik" : "💾 Zapisz lokalnie"}
        </button>
        <button
          type="button"
          className="run-btn role-force"
          onClick={deleteSelectedScenario}
          disabled={!canDeletePanelScenario(selectedScenarioId) || deletingScenario}
        >
          {deletingScenario ? "…" : selectedScenarioIsFile ? "🗑 Usuń plik" : "🗑 Usuń wybrany"}
        </button>
      </div>
      <div style={{ fontSize: rem.xs, color: "var(--text-muted)" }}>{scenarioListStatus}</div>
      <a
        href={`/ui/scenario-files${buildScenarioFilesSearch(`?${searchParams.toString()}`, {})}`}
        className="run-btn role-force"
        style={{ textAlign: "center", textDecoration: "none" }}
      >
        ↗ Pełny edytor plików
      </a>
    </div>
  );

  return (
    <div className="mapx-shell oql-panel-shell">
      <SidebarList
        title="Scenariusze"
        items={sidebarItems}
        activeId={selectedScenarioId || null}
        onSelect={(id) => requestSelectScenario(id)}
        onRefresh={loadScenarios}
        collapseToggleId="panel-scenarios-list"
        collapseLabel="Scenariusze"
        collapseStorageKey="ui.panel-scenarios-sidebar-collapsed"
        collapseIcon="📋"
        collapseOnSelect={false}
        footer={scenarioSidebarFooter}
      />
      <div className="dashboard mapx-main-dashboard oql-panel-page">
        <SharedNav navContext={(
          <div className="section-label" style={{ marginBottom: 0 }}>
            {t("nav.panel", "OQL")}
          </div>
        )} />
        <div className="dash-content oql-panel-content">
        <div className="mapx-header">
          <div className="mapx-header-actions" style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginLeft: "auto" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span className={`badge badge--${nodeBadge.cls}`} style={{ border: "1px solid var(--border)" }}>
                {nodeBadge.text}
              </span>
              <span className="badge" style={{ border: "1px solid var(--border)" }}>
                {svcBadge}
              </span>
            </div>
            <button type="button" className="run-btn role-force" onClick={getStatus}>
              ⟳ {t("oqlPanel.refresh", "Odśwież status")}
            </button>
            <label className="wait-toggle" style={{ display: "flex", alignItems: "center", gap: "4px" }}>
              <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} />
              auto 10s
            </label>
            <button type="button" className="run-btn role-force" onClick={copyAllResults}>
              📋 {t("oqlPanel.copyAll", "Kopiuj wszystko")}
            </button>
            <button type="button" className="run-btn role-force" onClick={downloadResults}>
              ⬇ JSON
            </button>
            <button type="button" className="run-btn role-force" onClick={downloadCsv}>
              ⬇ CSV
            </button>
            <button type="button" className="run-btn role-force" onClick={() => setResults([])}>
              {t("oqlPanel.clearLog", "Wyczyść log")}
            </button>
          </div>
        </div>

        {bannerMsg && (
          <div
            className="mapx-error"
            style={{
              backgroundColor: "rgba(245, 158, 11, 0.12)",
              color: "var(--warn)",
              border: "1px solid var(--warn)",
              marginBottom: "16px",
            }}
          >
            {bannerMsg}
          </div>
        )}

        <div className="panel-wrap">
          {/* LEFT: Predefined Actions */}
          <div className="panel-col">
            <div className="hw-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <h3 style={{ margin: 0 }}>Predefiniowane grupy</h3>
                <div style={{ display: "flex", gap: "6px" }}>
                  <button
                    type="button"
                    className="run-btn role-force"
                    style={{ fontSize: rem.xs, padding: "4px 8px" }}
                    onClick={() => setAllGroupsCollapsedState(false)}
                  >
                    Rozwiń
                  </button>
                  <button
                    type="button"
                    className="run-btn role-force"
                    style={{ fontSize: rem.xs, padding: "4px 8px" }}
                    onClick={() => setAllGroupsCollapsedState(true)}
                  >
                    Zwiń
                  </button>
                </div>
              </div>
              <div className="panel-groups-container">
                {groupsList.map((g) => {
                  const collapsed = !!collapsedGroups[g.title];
                  return (
                    <div key={g.title} className={`panel-group ${collapsed ? "is-collapsed" : ""}`}>
                      <div className="panel-group-header" onClick={() => toggleGroupCollapse(g.title)}>
                        <span className="panel-group-dot" style={{ backgroundColor: g.color }}></span>
                        <strong>{g.title}</strong>
                        <span className="panel-group-count">({g.items.length})</span>
                        <span style={{ flex: 1 }}></span>
                        {g.runAll !== false && (
                          <button
                            type="button"
                            className="run-btn role-force"
                            style={{ fontSize: rem.xs, padding: "2px 8px", marginRight: "6px" }}
                            onClick={(e) => {
                              e.stopPropagation();
                              runGroup(g);
                            }}
                          >
                            ▶ grupa
                          </button>
                        )}
                        <span className="panel-group-toggle">{collapsed ? "▸" : "▾"}</span>
                      </div>
                      {!collapsed && (
                        <div className="panel-group-buttons">
                          {g.items.map((it, idx) => (
                            <button
                              key={idx}
                              type="button"
                              className={`run-btn role-force ${it.act ? "act-btn" : ""}`}
                              style={{ fontSize: rem.sm, padding: "5px 9px", margin: "3px" }}
                              onClick={() => runItem(it)}
                              title={it.kind === "manage" ? `manage: ${it.verb}` : it.oql}
                            >
                              {it.label}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              <div style={{ marginTop: "12px", fontSize: rem.xs, color: "var(--text-muted)" }}>
                ● = akcja na realnym sprzęcie. Komendy OQL respektują przełącznik trybu w edytorze.
              </div>
            </div>

            {/* Live Monitor */}
            <div className="hw-card" style={{ marginTop: "14px" }}>
              <h3>Monitor na żywo</h3>
              <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                <select
                  className="nav-control-select"
                  style={{ flex: 1, padding: "7px" }}
                  value={monMetric}
                  onChange={(e) => setMonMetric(e.target.value)}
                >
                  <option value="cpu">CPU temp (°C)</option>
                  <option value="ai01">Sensor AI01</option>
                  <option value="ai02">Sensor AI02</option>
                  <option value="ai03">Sensor AI03</option>
                </select>
                <input
                  type="number"
                  min="1"
                  max="60"
                  style={{ width: "62px", padding: "7px" }}
                  value={monInterval}
                  onChange={(e) => setMonInterval(e.target.value)}
                  title="interwał (s)"
                />
                <button
                  type="button"
                  className="run-btn role-force"
                  style={{ backgroundColor: monIsRunning ? "var(--accent-red)" : "var(--accent-blue)" }}
                  onClick={toggleMonitor}
                >
                  {monIsRunning ? "⏸ stop" : "▶ start"}
                </button>
              </div>
              <canvas
                ref={canvasRef}
                width="320"
                height="80"
                style={{
                  width: "100%",
                  height: "80px",
                  marginTop: "8px",
                  backgroundColor: "rgba(0,0,0,0.2)",
                  border: "1px solid var(--border)",
                  borderRadius: "6px",
                }}
              />
              <div style={{ marginTop: "6px", fontSize: rem.xs, color: "var(--text-muted)" }}>
                <strong>{monVal}</strong> · {monMeta}
              </div>
            </div>
          </div>

          {/* RIGHT: Editor + Results */}
          <div className="panel-col panel-col-split">
            <div className="hw-card panel-card-fill panel-editor-card">
              <h3>
                Edytor scenariusza (OQL)
                {selectedScenarioTitle ? (
                  <span style={{ fontWeight: 400, fontSize: rem.sm, color: "var(--text-muted)", marginLeft: "8px" }}>
                    — {selectedScenarioTitle}
                    {editorIsDirty ? " *" : ""}
                  </span>
                ) : null}
              </h3>
              {editorToolbar("top")}
              <div className="panel-editor-wrap">
                <textarea
                  ref={editorRef}
                  className="panel-editor-textarea"
                  value={editorText}
                  onChange={(e) => setEditorText(e.target.value)}
                  spellCheck="false"
                  placeholder="VERSION: 4&#10;SCENARIO: Mój test&#10;GOAL:&#10;  SET NAME 'Opis'&#10;  SET 'valve-1' 'open'&#10;  SET WAIT '1 s'&#10;  GET 'ai01'"
                />

                <div className="panel-snippets">
                  {OQL_SNIPPETS.map((g) => {
                    const collapsed = !!collapsedSnippets[g.title];
                    return (
                      <div key={g.title} className={`panel-snippet-group ${collapsed ? "is-collapsed" : ""}`}>
                        <div className="panel-snippet-header" onClick={() => toggleSnippetCollapse(g.title)}>
                          <span className="panel-snippet-dot" style={{ backgroundColor: g.color }}></span>
                          <strong>{g.title}</strong>
                          <span style={{ flex: 1 }}></span>
                          <span>{collapsed ? "▸" : "▾"}</span>
                        </div>
                        {!collapsed && (
                          <div className="panel-snippet-list">
                            {g.items.map((it, idx) => (
                              <button
                                key={idx}
                                type="button"
                                className="panel-snippet-btn"
                                onClick={() => insertSnippet(it.t)}
                                title={`Wstaw: ${it.t.trim()}`}
                              >
                                {it.label}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {editorToolbar("bottom")}
            </div>

            <div className="hw-card panel-card-fill panel-results-card">
              <h3>Wyniki</h3>
              <input
                id="logFilterInput"
                className="panel-log-filter"
                placeholder="filtruj wyniki (tytuł / komenda / odpowiedź)…"
                value={logFilter}
                onChange={(e) => setLogFilter(e.target.value)}
              />
              <div className="panel-log-list">
                {filteredLogs.length === 0 ? (
                  <div className="panel-log-empty">
                    Brak wyników — uruchom komendę lub scenariusz.
                  </div>
                ) : (
                  filteredLogs.map((entry) => (
                    <div key={entry.id} className="panel-log-entry">
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: rem.sm }}>
                        <span className={`badge badge--${entry.cls}`}>{entry.label}</span>
                        <strong className="entry-title">{entry.title}</strong>
                        {entry.raw?.node_id && <span className="badge">{entry.raw.node_id}</span>}
                        <span style={{ flex: 1 }}></span>
                        {entry.req && (
                          <button
                            type="button"
                            className="run-btn role-force"
                            style={{ fontSize: rem.xs, padding: "2px 6px" }}
                            onClick={() => {
                              if (entry.req.ep.includes("execute")) {
                                runOql(entry.req.body.oql, entry.req.body.kind, entry.req.title);
                              } else {
                                runManage(entry.req.body.verb, entry.req.body.args, entry.req.title);
                              }
                            }}
                          >
                            ↻ powtórz
                          </button>
                        )}
                        <button
                          type="button"
                          className="run-btn role-force"
                          style={{ fontSize: rem.xs, padding: "2px 6px" }}
                          onClick={(e) => copyText(JSON.stringify(entry.raw, null, 2), e)}
                        >
                          📋 JSON
                        </button>
                        <span style={{ color: "var(--text-muted)" }}>{entry.time}</span>
                      </div>
                      {entry.sent && (
                        <div style={{ marginTop: "5px", fontSize: rem.xs, color: "var(--text-muted)", display: "flex", alignItems: "center", gap: "6px" }}>
                          <span style={{ color: "var(--accent-blue)" }}>→ wysłano:</span>
                          <code style={{ backgroundColor: "rgba(0,0,0,0.2)", padding: "2px 6px", borderRadius: "4px", flex: 1, wordBreak: "break-all" }}>
                            {entry.sent}
                          </code>
                          <button
                            type="button"
                            className="run-btn role-force"
                            style={{ fontSize: rem.xxs, padding: "1px 4px" }}
                            onClick={(e) => copyText(entry.sent, e)}
                          >
                            📋
                          </button>
                        </div>
                      )}
                      <div style={{ marginTop: "5px", fontSize: rem.md, display: "flex", gap: "6px", alignItems: "baseline" }}>
                        <span style={{ color: "var(--accent-green)", fontWeight: 600, fontSize: rem.xs }}>← odebrano:</span>
                        <pre style={{ margin: 0, padding: 0, background: "none", border: "none", fontFamily: "var(--font-mono)", fontSize: rem.md, whiteSpace: "pre-wrap", overflowX: "auto" }}>
                          {entry.recv}
                        </pre>
                      </div>
                      <details style={{ marginTop: "6px" }}>
                        <summary style={{ cursor: "pointer", fontSize: rem.xs, color: "var(--text-muted)" }}>
                          surowa odpowiedź (pełny JSON)
                        </summary>
                        <pre
                          style={{
                            marginTop: "4px",
                            padding: "8px",
                            backgroundColor: "rgba(0,0,0,0.2)",
                            border: "1px solid var(--border)",
                            borderRadius: "6px",
                            fontSize: rem.xs,
                            overflowX: "auto",
                            color: "var(--text-muted)",
                          }}
                        >
                          {JSON.stringify(entry.raw, null, 2)}
                        </pre>
                      </details>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
        </div>
      </div>
    </div>
  );
}
