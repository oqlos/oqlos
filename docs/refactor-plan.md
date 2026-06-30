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

## Faza 3 — Frontend map-editor / config (zrobione)

| Ticket / alert | Plik | Akcja |
|----------------|------|--------|
| `summarizeFuncToHardware` CC=47 | `mapEditorFuncHardwareSummary.js` | helpery + testy |
| `AppConfigProvider` CC=44 | `AppConfigProvider.jsx` | → `app-config-document.js`, `useParentEncoderNavigation.js` |
| `useUrlConfig` CC=18, fan=27 | `useUrlConfig.js` | → `url-embed-config.js` + testy |
| `useSelectionCollapsePanel` CC=33 | `useSelectionCollapsePanel.js` | → `useRailHoverPreview.js` |
| `MapEditor.jsx` CC=24, 1490L | god module | → `mapEditorModel.js`, `mapEditorIntegrationMeta.js`, panele + hooki |
| — | `mapEditorModel.test.js`, `mapEditorIntegrationMeta.test.js`, `mapEditorTic249.test.js` | `npm run test:unit` |

## Faza 4 — Backend Python (zrobione)

| Moduł | CC | Akcja |
|-------|-----|--------|
| `oqlos/api/hardware_modbus_topology.py` | — | porty RS485, device IDs |
| `oqlos/api/hardware_modbus_waveshare.py` | — | scan matrix + diagnose report |
| `oqlos/api/hardware_modbus_wizard.py` | — | wizard program/probe/plan |
| `oqlos/api/hardware_modbus_routes.py` | — | HTTP `/modbus/*` |
| `oqlos/api/hardware_registry.py` | — | statyczny rejestr adapterów |
| `oqlos/api/hardware_platform.py` | — | detekcja platformy / RPi |
| `oqlos/api/hardware_probe.py` | — | orchestrator (~130L) |
| `oqlos/api/hardware_probe_devices.py` | — | USB/I2C/Modbus RTU probe helpers |
| `oqlos/api/hardware_identify.py` | — | `/health`, `/identify` |
| `oqlos/api/hardware_diagnosis_routes.py` | — | snapshot, `/diagnosis`, `/recover` |
| `oqlos/api/hardware_peripherals_routes.py` | — | `/modbus-adc/raw`, `/rtc/*` |
| `oqlos/api/hardware.py` | — | facade (~75L): router composition + legacy re-exports |
| `oqlos/hardware/diagnosis_types.py` | — | dataclasses + `report_to_dict` |
| `oqlos/hardware/diagnosis_plugin_health.py` | — | plugin health / stale detection |
| `oqlos/hardware/diagnosis_device_actions.py` | — | per-device diagnosis builders |
| `diagnosis.py` `build_diagnosis_report` | fan=22 | orchestrator (~230L) |
| `identify_enrich.py` | orchestrator (~75L) | payload normalization + counts |
| `identify_enrich_adapters.py` | — | per-adapter enrichers + `adapter_status_from_health` |
| `identify_enrich_modbus_io.py` | — | multi-slave modbus-io expansion |
| `doctor.py` | facade (~95L) | orchestrator + test monkeypatch surface |
| `doctor_detection.py` / `doctor_modbus_analysis.py` / … | — | etapy diagnostyki |

## Faza 5 — Duplikacja (zrobione)

| Hotspot | Akcja |
|---------|--------|
| `motor.py` stop/set_speed handlers | `motor_http_handlers.py` — wspólny HTTP/CLI |
| `modbus_plugins_need_repair` | jeden moduł (`diagnosis_plugin_health`), import w autorepair + diagnosis — done |
| `gateway.py` read_channel / stop | `gateway_http.py` — `get_json` / `post_json` |
| `lung.py` stop/status HTTP | `plugin_http_handlers.py` — `http_get_command` / `http_post_command` |
| `piadc.py` read_channel HTTP | `plugin_http_handlers.py` |
| `hardware_probe_devices.py` | — | USB/I2C/Modbus RTU probe helpers |

## Faza 6 — Frontend / transport cleanup (zrobione)

| Ticket / alert | Plik | Akcja |
|----------------|------|--------|
| `editObjectActionArg` CC=24 | `MapEditor.jsx` | → `mapEditorObjectActionEdits.js` + testy |
| `manage_ops._run_diagnostic_command` CC=19 | `manage_ops.py` | → `manage_ops_diagnostic.py`, `manage_ops_usb.py` |
| `motor.py` modbus handlers | `motor_modbus_handlers.py` | connect, health, set_speed, stop, status + testy |
| `hardware-restart-wizard-steps.js` | pure helpers | → `hardware-restart-wizard-helpers.js` + testy |

## Faza 7 — analysis.toon.yaml HEALTH[6] (zrobione)

| CC | Funkcja | Akcja |
|----|---------|--------|
| 17 | `createEncoderController` | → `encoder-navigation.js` + testy |
| 16 | `cancelled` (HardwareDemo mount) | → `hardware-demo-identify.js` + testy |
| 19 | `_validate_motor2` | → `hardware_mapping_motor2.py` + testy |
| 15 | `_extractWizardPlan` | → `hardware-wizard-plan.js` `extractWizardPlan` + testy |
| 15 | `runCurrentStep` | → `hardware-restart-step-runner.js` `runWizardStep` + testy |
| 28 | `executeConfigureStep` | → `hardware-restart-configure.js` (probe/program) |

Po regeneracji `project/analysis.toon.yaml` oczekiwane: **HEALTH critical = 0**.

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
