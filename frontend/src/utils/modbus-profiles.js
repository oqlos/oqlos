export const MODBUS_PROFILE_IDS = ["modbus-adc", "modbus-io", "shared-bus"];
export const MODBUS_PROFILE_URL_PARAM = "submenu";
export const MODBUS_BAUD_OPTIONS = [4800, 9600, 19200, 38400, 57600, 115200];
export const MODBUS_DEFAULT_BAUD = 4800;

function defaultBaudForProfile(profileId) {
  return profileId === "modbus-adc" ? 9600 : MODBUS_DEFAULT_BAUD;
}

function defaultProfile(profileId) {
  const baudrate = defaultBaudForProfile(profileId);
  return {
    profile_id: profileId,
    topology: profileTopology(profileId),
    serial_port: "",
    target_baudrate: baudrate,
    target_parity: "N",
    device_ids: [],
    baseline_baudrate: baudrate,
    baud_probe_sequence: [baudrate],
  };
}

function serialPortForProfile(profileId, plan) {
  const ioPort = plan.io_serial_port || plan.serial_port || "";
  const adcPort = plan.adc_serial_port || ioPort;
  if (profileId === "modbus-adc") return adcPort;
  if (profileId === "modbus-io") return ioPort;
  return ioPort || adcPort;
}

function deviceIdsForProfile(profileId, plan) {
  const deviceIds = Array.isArray(plan.target_ids) ? plan.target_ids : [];
  const selectedIds = profileId === "modbus-adc"
    ? deviceIds.filter((id) => id !== 1 || deviceIds.length === 1).slice(-1)
    : profileId === "modbus-io"
      ? deviceIds.filter((id) => id === 1 || deviceIds.length === 1)
      : deviceIds;
  return selectedIds.length ? selectedIds : deviceIds;
}

function baudProbeSequence(plan, fallbackBaud, targetBaud) {
  if (Array.isArray(plan.baud_probe_sequence)) return plan.baud_probe_sequence;
  return [fallbackBaud, targetBaud].filter((value, index, values) => values.indexOf(value) === index);
}

export const MODBUS_PROFILE_LABEL_KEYS = {
  "modbus-adc": "hardwareRestart.profileAdc",
  "modbus-io": "hardwareRestart.profileIo",
  "shared-bus": "hardwareRestart.profileShared",
};

export const MODBUS_PROFILE_DESC_KEYS = {
  "modbus-adc": "hardwareRestart.profileAdcDesc",
  "modbus-io": "hardwareRestart.profileIoDesc",
  "shared-bus": "hardwareRestart.profileSharedDesc",
};

export function resolveModbusProfileId(value, fallback = "modbus-adc") {
  return MODBUS_PROFILE_IDS.includes(value) ? value : fallback;
}

export function readModbusProfileFromSearch(search = "") {
  const raw = String(search || "").trim();
  const params = new URLSearchParams(raw.startsWith("?") ? raw.slice(1) : raw);
  const profileId = params.get(MODBUS_PROFILE_URL_PARAM);
  return profileId && MODBUS_PROFILE_IDS.includes(profileId) ? profileId : "";
}

export function patchModbusProfileSearchParams(searchParams, profileId) {
  const next = new URLSearchParams(searchParams);
  if (profileId && MODBUS_PROFILE_IDS.includes(profileId)) {
    next.set(MODBUS_PROFILE_URL_PARAM, profileId);
  } else {
    next.delete(MODBUS_PROFILE_URL_PARAM);
  }
  return next;
}

export function profileTopology(profileId) {
  return profileId === "shared-bus" ? "shared-bus" : "separate-adapters";
}

export function profileFromPlan(profileId, plan) {
  if (!plan) return defaultProfile(profileId);
  const fallbackBaud = defaultBaudForProfile(profileId);
  const targetBaud = Number(plan.target_baudrate) || fallbackBaud;
  return {
    profile_id: profileId,
    topology: profileTopology(profileId),
    serial_port: serialPortForProfile(profileId, plan),
    target_baudrate: targetBaud,
    target_parity: plan.target_parity || "N",
    device_ids: deviceIdsForProfile(profileId, plan),
    baseline_baudrate: plan.baseline_baudrate || fallbackBaud,
    baud_probe_sequence: baudProbeSequence(plan, fallbackBaud, targetBaud),
  };
}

export function resolveProfile(settings, profileId, plan) {
  const fromApi = settings?.profiles?.[profileId];
  if (fromApi) {
    return { ...profileFromPlan(profileId, plan), ...fromApi };
  }
  return profileFromPlan(profileId, plan);
}

export function profileFromSettings(settings, profileId) {
  return settings?.profiles?.[profileId] || null;
}

export function buildModbusSidebarItems(settings, t, plan) {
  return MODBUS_PROFILE_IDS.map((id) => {
    const profile = resolveProfile(settings, id, plan);
    const port = profile?.serial_port || "—";
    return {
      id,
      title: t(MODBUS_PROFILE_LABEL_KEYS[id]),
      subtitle: port,
    };
  });
}

export function probeSequenceLabel(profile) {
  const seq = profile?.baud_probe_sequence;
  if (Array.isArray(seq) && seq.length) {
    return seq.join(" → ");
  }
  const target = profile?.target_baudrate;
  const baseline = profile?.baseline_baudrate || MODBUS_DEFAULT_BAUD;
  if (target && target !== baseline) {
    return `${baseline} → ${target}`;
  }
  return String(baseline);
}

export function filterWizardStepsByProfile(steps, profileId) {
  if (!Array.isArray(steps)) return [];
  if (profileId === "modbus-io") {
    return steps.filter((step) => step.step?.includes("modbus-io") || step.step === "final-check-all-connected");
  }
  if (profileId === "modbus-adc") {
    return steps.filter((step) => step.step?.includes("modbus-adc") || step.step === "final-check-all-connected");
  }
  return steps;
}

export function profileUsesSeparateAdapter(profileId) {
  return profileId !== "shared-bus";
}
