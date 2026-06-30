# Plan refaktoryzacji OqlOS

Źródło metryk: `project/analysis.toon.yaml`, `project/project.toon.yaml`, `project/planfile-tickets.yaml` (2026-06-30).

## Cele

- Obniżyć CC krytycznych funkcji (limit 15) i fan-out modułów hubowych.
- Zachować publiczne API (`hardware.py`, `HardwareApi`, `hui_actions` facade).
- Każda faza: ekstrakcja modułu + test regresji.

## Faza 0 — Hardware Python (zrobione)

| Moduł | Wynik |
|-------|--------|
| `tic249_units.py` | wspólne konwersje steps/s ↔ raw |
| `hui_lung_recipe.py`, `hui_hold.py`, `hui_artificial_lung.py` | podział HUI |
| `tic249_motion_params.py`, `tic249_command_mapping.py`, `tic249_sidecar_client.py`, `tic249_error_messages.py` | podział `tic249_extended.py` |
| `tests/firmware/test_tic249_units.py` | regresja |

## Faza 1 — Frontend API diagnostyka (zrobione)

| Ticket / alert | Plik | Akcja |
|----------------|------|--------|
| `extractDiagnosticFailure` CC=69 | `hardwareApi.js` | → `hardware-diagnostic-failure.js` + `hardware-tic249-status.js` |
| — | `hardware-diagnostic-failure.test.js` | `npm run test:unit` (6 testów) |

## Faza 2 — Frontend wizard / restart (zrobione)

| Ticket / alert | Plik | Akcja |
|----------------|------|--------|
| `_executeConfigureStep` CC=48 | `HardwareRestart.jsx` | → `hardware-restart-wizard-steps.js` |
| `runApiWithRetry` CC=16 | `HardwareRestart.jsx` | → `hardware-api-retry.js` + testy |

## Faza 3 — Frontend map-editor / config (częściowo)

| Ticket / alert | Plik | Akcja |
|----------------|------|--------|
| `summarizeFuncToHardware` CC=47 | `mapEditorFuncHardwareSummary.js` | helpery + testy |
| `AppConfigProvider` CC=44 | `AppConfigProvider.jsx` | → `app-config-document.js`, `useParentEncoderNavigation.js` |
| `useUrlConfig` CC=18, fan=27 | `useUrlConfig.js` | → `url-embed-config.js` + testy |
| `useSelectionCollapsePanel` CC=33 | `useSelectionCollapsePanel.js` | → `useRailHoverPreview.js` |
| `MapEditor.jsx` CC=24, 1490L | god module | podkomponenty (następny) |
| `MapEditor.jsx` CC=24, 1490L | god module | podkomponenty edytora + i18n |

## Faza 4 — Backend Python (duże moduły)

| Moduł | CC | Akcja |
|-------|-----|--------|
| `oqlos/api/hardware.py` | 14, 2266L | route groups → `api/hardware_hui.py`, `hardware_runtime.py`, … |
| `diagnosis.py` `build_diagnosis_report` | fan=22 | per-device builders |
| `identify_enrich.py` | god function | per-adapter enrichers |
| `doctor.py` | 971L | etapy diagnostyki |

## Faza 5 — Duplikacja (`duplication.toon.yaml`)

| Hotspot | Akcja |
|---------|--------|
| `motor.py` stop/set_speed handlers | wspólny `_handle_motor_cli_http` |
| `modbus_plugins_need_repair` | jeden moduł, import w autorepair + diagnosis |
| `gateway.py` read_channel / stop | shared helpers |

## Kolejność wdrożenia

1. Faza 1 (niski risk, czyste pure functions)
2. Faza 2 (wizard — izolowany flow restart)
3. Faza 3 (UI — większy blast radius)
4. Faza 4–5 (backend, po stabilizacji frontend API)

## Definition of done (faza)

- `pytest tests/firmware/` — 0 failures
- `node --test frontend/src/api/*.test.js` — 0 failures (fazy 1–2)
- `ruff check` / build frontend bez regresji
- Brak zmiany kontraktu HTTP / exportów publicznych
