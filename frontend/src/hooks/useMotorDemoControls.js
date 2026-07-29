import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { HardwareApi, formatHardwareApiError } from "../api/hardwareApi";
import {
  prependHardwareActivityLogEntry,
  usePageOpenedLog,
} from "../utils/hardware-activity-log.js";
import { probeDemoDevices } from "../utils/hardware-demo-identify.js";

export const NOTES = {
  C4: { name: "C", freq: 261.63, power: 26 },
  D4: { name: "D", freq: 293.66, power: 30 },
  E4: { name: "E", freq: 329.63, power: 33 },
  F4: { name: "F", freq: 349.23, power: 35 },
  G4: { name: "G", freq: 392.0, power: 39 },
  A4: { name: "A", freq: 440.0, power: 44 },
  B4: { name: "B", freq: 493.88, power: 49 },
  C5: { name: "C'", freq: 523.25, power: 52 },
};

export const NOTE_KEYS = ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"];

export const DEVICES = {
  "motor-dri0050": {
    label: "Pompa DRI0050 (PWM)",
    short: "Pump",
    description: "PWM motor driver — pitch sterowany duty-cycle (0-100%). Każda nuta = pump_set { power_pct }.",
    noteCommand: (note) => ({ command: "pump_set", args: { power_pct: note.power } }),
    stopCommand: () => ({ command: "pump_off", args: {} }),
  },
  "motor-tic249": {
    label: "Silnik krokowy Tic T249",
    short: "Stepper",
    description: "Pololu Tic T249 — pitch = step rate (każdy krok generuje słyszalne kliknięcie). Mapowanie: speed = freq steps/s, steps ≈ freq × duration_sec.",
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

const MELODY_DEFS = {
  twinkle: {
    titleKey: "hardwareDemo.melody.twinkle",
    bpm: 120,
    notes: [["C4", 500], ["C4", 500], ["G4", 500], ["G4", 500], ["A4", 500], ["A4", 500], ["G4", 1000], ["F4", 500], ["F4", 500], ["E4", 500], ["E4", 500], ["D4", 500], ["D4", 500], ["C4", 1000]],
  },
  "ode-to-joy": {
    titleKey: "hardwareDemo.melody.ode_to_joy",
    bpm: 120,
    notes: [["E4", 400], ["E4", 400], ["F4", 400], ["G4", 400], ["G4", 400], ["F4", 400], ["E4", 400], ["D4", 400], ["C4", 400], ["C4", 400], ["D4", 400], ["E4", 400], ["E4", 600], ["D4", 200], ["D4", 800]],
  },
  "wlazl-kotek": {
    titleKey: "hardwareDemo.melody.wlazl_kotek",
    bpm: 110,
    notes: [["E4", 400], ["C4", 400], ["E4", 400], ["C4", 400], ["G4", 400], ["F4", 400], ["E4", 800], ["D4", 400], ["F4", 400], ["E4", 400], ["D4", 400], ["C4", 800]],
  },
  scale: { titleKey: "hardwareDemo.melody.scale", bpm: 120, notes: NOTE_KEYS.map((note) => [note, 350]) },
};

function playToneOnSpeakers(ctx, freq, durationMs) {
  if (!ctx || !freq || durationMs <= 0) return;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = "square";
  osc.frequency.value = freq;
  osc.connect(gain);
  gain.connect(ctx.destination);
  const now = ctx.currentTime;
  const end = now + Math.max(0.05, durationMs / 1000);
  gain.gain.setValueAtTime(0, now);
  gain.gain.linearRampToValueAtTime(0.15, now + 0.02);
  gain.gain.linearRampToValueAtTime(0.15, Math.max(now + 0.03, end - 0.04));
  gain.gain.linearRampToValueAtTime(0, end);
  osc.start(now);
  osc.stop(end + 0.02);
}

const sleep = (durationMs) => new Promise((resolve) => setTimeout(resolve, durationMs));

async function resumeAudioContext(ctx) {
  if (!ctx || ctx.state !== "suspended") return;
  try {
    await ctx.resume();
  } catch {
    // A failed resume only disables speaker feedback; hardware playback still works.
  }
}

function useDemoDeviceProbe({ appendLog, setDeviceId, t }) {
  const [deviceStatus, setDeviceStatus] = useState({});

  useEffect(() => {
    const controller = new AbortController();
    const probe = async () => {
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
        if (result.fallbackDeviceId) setDeviceId(result.fallbackDeviceId);
      } catch (error) {
        if (controller.signal.aborted) return;
        setDeviceStatus({ "motor-dri0050": "error", "motor-tic249": "error" });
        appendLog("error", t("hardwareDemo.log.identifyFailed"), formatHardwareApiError(error));
      }
    };
    probe();
    return () => controller.abort();
  }, [appendLog, setDeviceId, t]);

  return deviceStatus;
}

async function sendCommand(peripheralId, command, args) {
  await HardwareApi.runDiagnosticCommand({ peripheral_id: peripheralId, command, args });
}

export function useMotorDemoControls(t) {
  const [deviceId, setDeviceId] = useState("motor-dri0050");
  const [activeNote, setActiveNote] = useState(null);
  const [playingMelody, setPlayingMelody] = useState(null);
  const [activityLog, setActivityLog] = useState([]);
  const [audioOn, setAudioOn] = useState(true);
  const [hwOn, setHwOn] = useState(true);
  const audioCtxRef = useRef(null);
  const stopRequestedRef = useRef(false);
  const lastCmdAtRef = useRef(0);
  const stepperDirectionRef = useRef("right");

  const appendLog = useCallback((level, message, detail = "") => {
    setActivityLog((previous) => prependHardwareActivityLogEntry(previous, level, message, detail));
  }, []);
  const deviceStatus = useDemoDeviceProbe({ appendLog, setDeviceId, t });
  const device = DEVICES[deviceId];
  const melodies = useMemo(
    () => Object.fromEntries(Object.entries(MELODY_DEFS).map(([key, definition]) => [key, { ...definition, title: t(definition.titleKey) }])),
    [t],
  );

  usePageOpenedLog(t, setActivityLog, "hardwareDemo.log.pageOpened", "hardwareDemo.log.pageOpenedDetail");

  const ensureAudioCtx = useCallback(() => {
    if (audioCtxRef.current) return audioCtxRef.current;
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
      appendLog("warn", t("hardwareDemo.log.webAudioUnavailable"), t("hardwareDemo.log.webAudioDetail"));
      return null;
    }
    audioCtxRef.current = new AudioContextClass();
    return audioCtxRef.current;
  }, [appendLog, t]);

  const sendFallbackNote = useCallback(async (note, durationMs, direction, command) => {
    if (deviceId !== "motor-dri0050" || deviceStatus["motor-tic249"] !== "ok") return;
    appendLog("warn", t("hardwareDemo.log.pumpAutoSwitch", { command }), command);
    setDeviceId("motor-tic249");
    const fallback = DEVICES["motor-tic249"].noteCommand(note, durationMs, direction);
    try {
      await sendCommand("motor-tic249", fallback.command, fallback.args);
      appendLog("ok", t("hardwareDemo.log.stepperFallbackOk"), `${fallback.command} ${JSON.stringify(fallback.args)}`);
    } catch (error) {
      appendLog("error", t("hardwareDemo.log.stepperFallbackFail"), formatHardwareApiError(error));
    }
  }, [appendLog, deviceId, deviceStatus, t]);

  const sendDeviceNote = useCallback(async (note, durationMs) => {
    if (!hwOn || performance.now() - lastCmdAtRef.current < 60) return;
    lastCmdAtRef.current = performance.now();
    const direction = stepperDirectionRef.current === "right" ? "left" : "right";
    stepperDirectionRef.current = direction;
    const { command, args } = device.noteCommand(note, durationMs, direction);
    try {
      await sendCommand(deviceId, command, args);
    } catch (error) {
      appendLog("error", t("hardwareDemo.log.commandFailed", { command }), formatHardwareApiError(error));
      await sendFallbackNote(note, durationMs, direction, command);
    }
  }, [appendLog, device, deviceId, hwOn, sendFallbackNote, t]);

  const sendDeviceStop = useCallback(async () => {
    if (!hwOn) return;
    const { command, args } = device.stopCommand();
    try {
      await sendCommand(deviceId, command, args);
    } catch {
      // Stopping is best effort and should not interrupt the demo UI.
    }
  }, [device, deviceId, hwOn]);

  const playNote = useCallback(async (key, durationMs) => {
    const note = NOTES[key];
    if (!note) return;
    setActiveNote(key);
    const audioContext = audioOn ? ensureAudioCtx() : null;
    if (audioContext) playToneOnSpeakers(audioContext, note.freq, durationMs);
    sendDeviceNote(note, durationMs);
    await sleep(durationMs);
    setActiveNote(null);
  }, [audioOn, ensureAudioCtx, sendDeviceNote]);

  const onNoteClick = useCallback(async (key) => {
    const audioContext = ensureAudioCtx();
    await resumeAudioContext(audioContext);
    const note = NOTES[key];
    const { command, args } = device.noteCommand(note, 500);
    appendLog("info", t("hardwareDemo.log.playNote", { name: note.name, short: device.short }), `${note.freq.toFixed(2)} Hz · ${command} ${JSON.stringify(args)}`);
    await playNote(key, 500);
    sendDeviceStop();
  }, [appendLog, device, ensureAudioCtx, playNote, sendDeviceStop, t]);

  const playMelody = useCallback(async (melodyKey) => {
    if (playingMelody) return;
    const melody = melodies[melodyKey];
    if (!melody) return;
    await resumeAudioContext(ensureAudioCtx());
    stopRequestedRef.current = false;
    setPlayingMelody(melodyKey);
    appendLog("info", t("hardwareDemo.log.playingMelody", { title: melody.title }), t("hardwareDemo.log.playingMelodyDetail", { count: String(melody.notes.length), short: device.short }));
    try {
      for (let index = 0; index < melody.notes.length; index += 1) {
        if (stopRequestedRef.current) {
          appendLog("warn", t("hardwareDemo.log.melodyStopped"), t("hardwareDemo.log.melodyStoppedDetail", { at: String(index + 1), total: String(melody.notes.length) }));
          break;
        }
        const [key, durationMs] = melody.notes[index];
        await playNote(key, Math.max(120, durationMs - 40));
        await sleep(40);
      }
      if (!stopRequestedRef.current) appendLog("ok", t("hardwareDemo.log.finishedMelody", { title: melody.title }));
    } finally {
      setPlayingMelody(null);
      sendDeviceStop();
    }
  }, [appendLog, device.short, ensureAudioCtx, melodies, playNote, playingMelody, sendDeviceStop, t]);

  const stopMelody = useCallback(() => { stopRequestedRef.current = true; }, []);

  return {
    activeNote, activityLog, audioOn, device, deviceId, deviceStatus, hwOn, melodies,
    onNoteClick, playMelody, playingMelody, setAudioOn, setDeviceId, setHwOn, stopMelody,
  };
}
