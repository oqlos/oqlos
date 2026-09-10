/** Database-backed preferences. No persistent client-side copy. */
const PREFS_URL = '/api/v3/ui/prefs';
let serverPrefs = {};
let writes = Promise.resolve();

export async function hydrateUiPrefsFromServer() {
  const res = await fetch(PREFS_URL, { cache: 'no-store', signal: AbortSignal.timeout(8000) });
  if (!res.ok) throw new Error(`Preferences HTTP ${res.status}`);
  serverPrefs = (await res.json()).prefs || {};
  return serverPrefs;
}

export function queueUiPrefPersist(key, value) {
  if (!key) return;
  serverPrefs[key] = String(value);
  writes = writes.catch(() => {}).then(async () => {
    const res = await fetch(PREFS_URL, {
      method: 'PUT', keepalive: true, headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prefs: { [key]: String(value) }, merge: true, persist: true }),
    });
    if (!res.ok) throw new Error(`Preferences HTTP ${res.status}`);
  });
  void writes.catch(error => console.error('Nie zapisano ustawień w bazie danych.', error));
  return writes;
}

export const databasePreferences = {
  getItem(key) { return serverPrefs[key] ?? null; },
  setItem: queueUiPrefPersist,
};
