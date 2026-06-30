# Deduplikacja: migracja elementów sprzętowych z connect-scenario → oqlos

Status na podstawie analizy `oqlos` vs `maskservice/c2004/connect-scenario` (CS).
**Nic nie zostało usunięte z CS** — to plan odcięcia. Usuwanie wymaga osobnej, świadomej
decyzji i przejścia kroków w podanej kolejności.

## TL;DR — co usunąć z connect-scenario

| Warstwa | Stan | Co usunąć z CS |
|---|---|---|
| **Backend (sprzęt)** | ✅ już odcięte przez fasady | nic — pliki CS to celowe fasady do `oqlos.hardware.client` |
| **Frontend [B] współdzielone** | używane przez inne funkcje CS | **nie usuwać** (ew. → wspólna paczka) |
| **Frontend [A] sprzętowe — czyste** | tylko trasy `/hardware-*` | usunąć **po** zdjęciu 3 tras z `App.jsx` |
| **Frontend [A] sprzętowe — lepkie** | używane poza sprzętem | **najpierw refaktor**, dopiero potem usuwać |

## 1. Backend — odcięcie już trwa (nic nie kasować)

CS importuje implementację z OqlOS przez fasadę `hardware_client._compat`:

- `backend/.../api/hardware_tic249_extended.py` → `from oqlos.hardware.client import tic249_extended`
- `backend/.../api/hardware_autorepair.py` → `from oqlos.hardware.client import autorepair`
- `backend/.../api/tic249_rig_direction.py` → `from hardware_client._compat import ensure_oqlos_client_available`

Te pliki CS to **cienkie fasady** — źródłem prawdy jest `oqlos/hardware/client/` (11/15 plików
unikalnych dla oqlos, reszta zrefaktorowana). **Nie usuwać** — usunięcie zerwie API CS.
`oqlos/hardware/client/` zostaje właścicielem.

## 2. Frontend — 34 bajtowo-identyczne duplikaty

`App.jsx` i `main.jsx` są w obu repo, ale **rozjechane** (powłoka oqlos ≠ powłoka CS) — zostają
osobno w każdym repo.

### [B] Współdzielone / generyczne — NIE usuwać (16)
Używane przez nie-sprzętowe funkcje CS:
```
src/api/wsClient.js                  src/i18n/I18nProvider.jsx
src/components/SharedNav.jsx         src/i18n/dictionaries.js
src/components/SidebarList.jsx       src/pages/MapEditor.jsx
src/context/AppConfigProvider.jsx    src/pages/mapEditorDefaultMap.js
src/hooks/useUrlConfig.js            src/styles/global.css
src/hooks/useWsStatus.js             src/utils/collapse-toggle-bridge.js
src/utils/designRem.js               src/utils/parentUrlBridge.js
src/utils/rbac.policy.js             src/utils/useSelectionCollapsePanel.js
```
Jeśli mają być wspólne → wydzielić do osobnej paczki npm, a nie kasować w CS.

### [A] Sprzętowe — kandydaci do usunięcia (18), w dwóch podgrupach

**A1 — lepkie (3): NAJPIERW refaktor, potem usuwanie.** Używane poza trasami sprzętowymi:
```
src/api/hardwareApi.js          <- hooks/useTerminalRun.js (terminal) + testy
src/api/hardware-api-log.js     <- hardwareApi.js
src/utils/hui-shell-key.js      <- components/VirtualHuiKeyPanel.jsx, hooks/useUrlConfig.js,
                                   utils/iframeChildProtocol.js
```
Te zostają w CS dopóki terminal / panel HUI / useUrlConfig nie dostaną własnego źródła
(lokalna kopia lub wspólna paczka).

**A2 — sprzętowe pod trasami `/hardware-*` (15): usuwalne PO kroku 3.**
```
src/pages/HardwareDemo.jsx               src/pages/HardwareStatus.jsx
src/pages/HardwareRestart.jsx            src/components/HardwareActivityLog.jsx
src/i18n/hardware-demo-extra-translations.js
src/i18n/hardware-status-log-translations.js
src/i18n/hardware-status-panel-translations.js
src/i18n/hardware-status-presets-translations.js
src/utils/hardware-activity-log.js       src/utils/hardware-restart-docs.js
src/utils/hardware-time.js               src/utils/hardware-wizard-plan.js
src/utils/hardware-wizard-steps.js       src/utils/hardwareEventStream.js
src/utils/mapEditorFuncHardwareSummary.js
```

## 3. Bezpieczna kolejność odcięcia (frontend)

1. **Decyzja:** OqlOS jest właścicielem UI sprzętowego; CS przestaje renderować własne strony
   sprzętowe (osadza panel/strony oqlos przez iframe lub redirect na `:8202`).
2. **Edycja `connect-scenario/frontend/src/App.jsx`** — zdejmij importy i trasy sprzętowe:
   ```diff
   - import HardwareStatus from "./pages/HardwareStatus";
   - import HardwareDemo from "./pages/HardwareDemo";
   - import HardwareRestart from "./pages/HardwareRestart";
   ...
   - <Route path="/hardware-status"  element={<GuardedRoute .../>} />
   - <Route path="/hardware-restart" element={<GuardedRoute .../>} />
   - <Route path="/hardware-demo"    element={<GuardedRoute .../>} />
   - <Route path="/connect-scenario/hardware-status"  element={<Navigate .../>} />
   - <Route path="/connect-scenario/hardware-restart" element={<Navigate .../>} />
   - <Route path="/connect-scenario/hardware-demo"    element={<Navigate .../>} />
   ```
   (lub zamień element trasy na osadzenie panelu oqlos).
3. **Refaktor A1** — `hardwareApi`/`hardware-api-log` używane przez `useTerminalRun.js`
   oraz `hui-shell-key` przez `VirtualHuiKeyPanel`/`useUrlConfig`/`iframeChildProtocol`:
   wydziel do wspólnej paczki albo zostaw lokalną kopię w CS.
4. **Usuń A2 (15 plików)** z CS i potwierdź budowę:
   ```bash
   cd connect-scenario/frontend && npm run build   # musi przejść (brak martwych importów)
   ```
5. **[B] zostaje** w CS (lub → wspólna paczka). A1 dopiero po kroku 3.

## 4. Weryfikacja przed kasowaniem (zalecane)

Przed `git rm` sprawdź, że plik jest naprawdę osierocony (poza zbiorem [A]):
```bash
cd connect-scenario/frontend
grep -rl "NAZWA_MODULU" src --include=*.jsx --include=*.js | grep -v "/NAZWA_MODULU\."
# pusto (lub tylko pliki sprzętowe) ⇒ bezpieczne po kroku 2/3
npm run build   # ostateczny dowód: brak martwych importów
```
