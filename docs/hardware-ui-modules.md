# OqlOS hardware UI modules — status and operator guide

Last updated: 2026-07-10.

## Open issues (analysis)

| Issue | Severity | Status |
| --- | --- | --- |
| `/func-editor` redirect pointed to `/ui/scenario-files` instead of `/ui/func-editor` | Medium | **Fixed** in `main.py` + test |
| RBAC missing `/ui/hardware-rtc` and `/ui/hardware-modbus` | Low | **Fixed** in `rbac.policy.js` |
| `navigationIndex.*` i18n only English fallbacks on `/ui/status` | Low | **Fixed** — PL/EN/DE/RU/UA/CS in `dictionaries.js` |
| Stale `submenu=modbus-*` on RTC page | Low | **Fixed** — stripped on mount (same as motor-services) |
| `task install` did not install local `oqlos-models` / `oqlos-core` | Medium | **Fixed** in `Taskfile.yml` |
| Large uncommitted diff (oqlos + c2004 connect-scenario) | High | **Open** — needs review + commit + BoardNet deploy |
| Live TestQL against `:8202` | Medium | **Done** — `testql run …/oqlos-hardware-ui-modules.testql.toon.yaml --url http://127.0.0.1:8202` (14/14) |
| Koru MCP / ticket loop | Ops | **Open** — server error |

BoardNet serves the React SPA under **`/ui/*`** on port **8202**. Legacy paths without
`/ui` redirect to canonical URLs (query string preserved). See also
[boardnet-navigation.md](boardnet-navigation.md).

## Summary

| Module | URL | Status | Notes |
| --- | --- | --- | --- |
| **Status + navigation** | `/ui/status` | **Works** | Merged `/navigation` + `/hardware-status`; machine index at `/api/v1/navigation` |
| **Modbus wizard** | `/ui/hardware-modbus` | **Works** (RPi / with hardware) | Wizard, profile sidebar (`submenu=modbus-adc\|modbus-io\|shared-bus`), channel inspector |
| **RTC (piRTC)** | `/ui/hardware-rtc` | **Works** (RPi + `OQLOS_ENABLE_RTC=1`) | Sidebar menu, v3 API; desktop shows “RTC disabled” without env |
| **Motor services** | `/ui/motor-services` | **Works** (with sidecars) | Tic249 + DRI0050 only; Modbus removed from view; `?devices=motors` repair scope |
| **MAP / scenarios / panel** | various | **Unchanged** | Pre-existing OqlOS pages |
| **connect-scenario nginx** | `:8096` redirects | **Done** | Regex includes `hardware-modbus`, `hardware-rtc`, `motor-services`, `func-editor` (c2004) |

## What works today

### `/ui/status`

- Single entry: navigation index, node health, adapter list, USB/serial/I2C diagnostics.
- Legacy redirects: `/navigation`, `/nav`, `/hardware-status`, `/ui/navigation` → `/ui/status`.
- React: `HardwareStatus.jsx` + `NodeNavigationPanel.jsx`.
- Backend: `NAVIGATION_PAGES` in `oqlos/api/main.py`, `/api/v1/navigation`.

### `/ui/hardware-modbus`

- Kit restart wizard (step-by-step Modbus IO/ADC probe/program).
- **Profile sidebar** via URL `submenu`: `modbus-adc`, `modbus-io`, `shared-bus`.
- **Channel inspector** — live DO/DI/coils, ADC reads, config registers (0x1000–0x4000).
- API v3:
  - `GET /api/v3/hardware/modbus/profile-channels?profile=…`
  - `PUT /api/v3/hardware/modbus/channel-value`
  - `GET/PUT /api/v3/hardware/modbus/settings`
  - `GET /api/v3/hardware/stack/snapshot` (wizard plan)
- Legacy aliases: `/restart`, `/hardware-restart`, `/modbus` → `/ui/hardware-modbus`.
- **Desktop without HAT**: wizard plan may load; Modbus probe timeouts are expected (`ok: false` with message).

### `/ui/hardware-rtc`

- Waveshare DS3231 + watchdog via **piRTC sidecar** (`:8125`, `PIRTC_API_URL`).
- Sidebar operations: overview, time, date, temperature, watchdog, sync, feed, reinit.
- URL `submenu` values: `overview`, `read_time`, `read_date`, … (see `frontend/src/utils/rtc-menu.js`).
- API v3:
  - `GET /api/v3/hardware/rtc/status`
  - `POST /api/v3/hardware/rtc/command` — body `{ "command": "read_time", "args": {} }`
- v1 equivalents: `/api/v1/hardware/rtc/status`, `/api/v1/hardware/rtc/command`.
- Requires **`OQLOS_ENABLE_RTC=1`** (or `C2004_HARDWARE_ENABLE_RTC=1`) on RPi5 with HAT.
- Aliases: `/hardware-rtc`, `/rtc` → `/ui/hardware-rtc`.

### `/ui/motor-services`

- Motor diagnostics cards: **motor-tic249**, **motor-dri0050** only.
- **Napraw teraz** runs safe recover with `?devices=motors` (no Modbus reconnect).
- Manual test panel: note keyboard + melodies → PWM (DRI0050) or stepper (Tic249).
- Stale `submenu=modbus-*` is **stripped** from URL on entry.
- Aliases: `/demo`, `/hardware-demo` → `/ui/motor-services`.
- Sidecars: `hw-tic249.service` (:8205), `dri0050-motor-api.service` (:8203).

### Shared UI chrome

- Top nav (`SharedNav.jsx`): Status, Modbus, RTC, Silniki, scenariusze, MAP, panel, API docs.
- URL chrome preserved across routes: `font`, `theme`, `role`, `lang`, `size`, `mode`, `sidebar`, `submenu`.
- RBAC patterns in `frontend/src/utils/rbac.policy.js`.

## What still needs work

| Area | Priority | Description |
| --- | --- | --- |
| **connect-scenario nginx** | Done | Redirect regex updated; regression `connect-scenario/backend/tests/test_oqlos_nginx_redirects.py` |
| **connect-scenario README** | Done | Canonical URLs `/ui/hardware-modbus`, `/ui/hardware-rtc`, `/ui/motor-services` |
| **Pytest full suite** | Medium | Run `task install` (installs `oqlos-models` + `oqlos-core` locally); use `python3 -m pytest`, not bare `pytest` from another venv |
| **RTC on desktop** | Low | Expected: disabled until `OQLOS_ENABLE_RTC=1` + piRTC sidecar; UI shows hint |
| **Modbus without hardware** | Low | Channel inspector / probe fail gracefully; document in operator runbook |
| **E2E / TestQL** | Medium | `testql-testing/scenarios/oqlos-hardware-ui-modules.testql.toon.yaml` + static regression test |
| **Git commit / deploy** | High | Large uncommitted diff in `oqlos` repo; needs review, commit, BoardNet redeploy |
| **Koru MCP** | Ops | Server in error state — ticket loop unavailable from Cursor |

## Quick operator URLs (local dev)

```text
http://localhost:8202/ui/status
http://localhost:8202/ui/hardware-modbus?submenu=modbus-adc
http://localhost:8202/ui/hardware-rtc?submenu=read_time
http://localhost:8202/ui/motor-services
```

Recommended chrome (embedded / bench):

```text
?font=default&theme=dark&role=admin&lang=pl&size=1280&mode=keyboard&sidebar=on
```

## API cheat sheet (v3)

```bash
BASE=http://localhost:8202

# Navigation index
curl -s "$BASE/api/v1/navigation" | jq '.pages[].path'

# Modbus channels (profile: modbus-adc | modbus-io | shared-bus)
curl -s "$BASE/api/v3/hardware/modbus/profile-channels?profile=modbus-adc"

# RTC status / command
curl -s "$BASE/api/v3/hardware/rtc/status"
curl -s -X POST "$BASE/api/v3/hardware/rtc/command" \
  -H 'Content-Type: application/json' \
  -d '{"command":"read_time","args":{}}'

# Motor-only diagnosis / repair
curl -s "$BASE/api/v3/hardware/diagnosis?devices=motors"
curl -s -X POST "$BASE/api/v3/hardware/diagnosis/repair?devices=motors"
```

## Frontend tests (run locally)

```bash
cd frontend
node --test src/utils/rtc-menu.test.js
node --test src/utils/motor-services-diagnosis.test.js
node --test src/utils/modbus-profiles.test.js
npm run test:unit
```

TestQL (c2004 bench, API-only):

```bash
# Static regression (no live server)
pytest testql-testing/tests/test_oqlos_hardware_ui_modules_scenario.py

# Live smoke (OqlOS on :8202)
# testql-testing/scenarios/oqlos-hardware-ui-modules.testql.toon.yaml
```

## Backend smoke tests

After `task install`:

```bash
python3 -m pytest tests/firmware/test_hw3_system_routes.py \
  tests/firmware/test_diagnosis_motors_filter.py \
  tests/firmware/test_hardware_modbus_channels.py -q
```

## File map (this feature set)

| Area | Key files |
| --- | --- |
| Status | `frontend/src/pages/HardwareStatus.jsx`, `components/NodeNavigationPanel.jsx` |
| Modbus UI | `frontend/src/pages/HardwareRestart.jsx`, `components/ModbusChannelInspector.jsx` |
| RTC UI | `frontend/src/pages/HardwareRtc.jsx`, `utils/rtc-menu.js` |
| Motors UI | `frontend/src/pages/MotorServices.jsx`, `utils/motor-services-diagnosis.js` |
| Routes | `frontend/src/App.jsx`, `oqlos/api/main.py`, `oqlos/api/_hw3_system.py` |
| Modbus API | `oqlos/api/hardware_modbus_channels.py` |
| RTC API | `oqlos/api/hardware_peripherals_routes.py`, `oqlos/hardware/rtc_probe.py` |
| Diagnosis scope | `oqlos/hardware/diagnosis.py`, `oqlos/api/hardware_diagnosis_routes.py` |

## Related docs

- [BoardNet navigation](boardnet-navigation.md) — URLs and aliases
- [Hardware diagnostics](HARDWARE_DIAGNOSTICS.md) — `oqlctl doctor`, Modbus probe
- [HARDWARE_CONTROL_OQL_MQTT.md](HARDWARE_CONTROL_OQL_MQTT.md) — manage verbs, sidecars
- c2004: [docs/hardware-runtime.md](https://github.com/maskservice/c2004/blob/main/docs/hardware-runtime.md) — port 8202, `make hardware-oqlos-only`
