/** Server-backed UI chrome prefs for OqlOS (sidebar collapse, pins). */

const PREFS_URL = "/api/v3/ui/prefs";
const LEGACY_PREFIXES = ["ui.", "oqlos_panel_"];

let serverPrefs = {};
let flushTimer = null;
let hydrated = false;

function readLegacyLocalPrefs() {
  const out = {};
  try {
    for (let i = 0; i < window.localStorage.length; i += 1) {
      const key = window.localStorage.key(i);
      if (!key) continue;
      if (!LEGACY_PREFIXES.some((prefix) => key.startsWith(prefix))) continue;
      const value = window.localStorage.getItem(key);
      if (value !== null) out[key] = value;
    }
  } catch { /* silent */ }
  return out;
}

function applyPrefsToLocalCache(prefs) {
  if (!prefs || typeof prefs !== "object") return;
  try {
    Object.entries(prefs).forEach(([key, value]) => {
      window.localStorage.setItem(key, String(value));
    });
  } catch { /* silent */ }
}

function scheduleServerPersist(patch) {
  serverPrefs = { ...serverPrefs, ...patch };
  if (flushTimer) clearTimeout(flushTimer);
  flushTimer = setTimeout(async () => {
    flushTimer = null;
    try {
      await fetch(PREFS_URL, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prefs: serverPrefs, merge: true, persist: true }),
      });
    } catch { /* silent */ }
  }, 200);
}

export async function hydrateUiPrefsFromServer() {
  if (hydrated) return serverPrefs;
  hydrated = true;
  const legacy = readLegacyLocalPrefs();
  try {
    const res = await fetch(PREFS_URL, { cache: "no-store" });
    if (res.ok) {
      const payload = await res.json();
      serverPrefs = payload?.prefs && typeof payload.prefs === "object" ? payload.prefs : {};
    }
  } catch { /* silent */ }

  const merged = { ...serverPrefs, ...legacy };
  if (Object.keys(legacy).length) {
    scheduleServerPersist(legacy);
    Object.keys(legacy).forEach((key) => {
      try { window.localStorage.removeItem(key); } catch { /* silent */ }
    });
  }
  applyPrefsToLocalCache(merged);
  serverPrefs = merged;
  return merged;
}

export function queueUiPrefPersist(storageKey, value) {
  if (!storageKey) return;
  scheduleServerPersist({ [storageKey]: String(value) });
}
