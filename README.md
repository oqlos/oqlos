# OqlOS — Operation Query Language Runtime


## AI Cost Tracking

![PyPI](https://img.shields.io/badge/pypi-costs-blue) ![Version](https://img.shields.io/badge/version-0.1.27-blue) ![Python](https://img.shields.io/badge/python-3.9+-blue) ![License](https://img.shields.io/badge/license-Apache--2.0-green)
![AI Cost](https://img.shields.io/badge/AI%20Cost-$7.50-orange) ![Human Time](https://img.shields.io/badge/Human%20Time-35.2h-blue) ![Model](https://img.shields.io/badge/Model-openrouter%2Fqwen%2Fqwen3--coder--next-lightgrey)

- 🤖 **LLM usage:** $7.5000 (51 commits)
- 👤 **Human dev:** ~$3518 (35.2h @ $100/h, 30min dedup)

Generated on 2026-05-30 using [openrouter/qwen/qwen3-coder-next](https://openrouter.ai/qwen/qwen3-coder-next)

---

![Version](https://img.shields.io/badge/version-0.1.27-blue) ![Python](https://img.shields.io/badge/python-3.10+-blue) ![License](https://img.shields.io/badge/license-Apache--2.0-green)


OqlOS is the core runtime for executing OQL (Operation Query Language) hardware testing scenarios. It provides the execution engine, hardware abstraction layer, and API server for running automated hardware tests.

## Installation

```bash
# Install from source with development dependencies
pip install -e ".[dev]"

# Basic installation
pip install -e .
```

### Hardware Client Contract

The shared hardware REST contract lives in `oqlos.hardware.client`. Legacy
c2004 imports from `hardware_client.*` are compatibility facades over this
OqlOS-owned module, so OqlOS no longer depends on c2004 for hardware API
resolvers or proxy helpers.

### CLI Quick Check (step by step)

If you see:

```bash
oqlos: command not found
```

that is expected — `oqlos` is the package name, not the CLI command.

Use this sequence:

```bash
# 1) Activate your virtualenv
source .venv/bin/activate

# 2) Install the project in editable mode (creates console scripts)
python -m pip install -e .

# 3) Check available CLI help
oqlctl --help

# 4) If PATH still does not see scripts, use module form directly
python -m oqlos.tools.cql_cli.main --help
```

Main commands provided by this project:

- `oqlctl` — scenario CLI (validate / dry-run / execute)
- `oqlctl detect` — smart local hardware detection (USB/serial/I2C/Modbus + config)
- `oqlctl doctor` — operator-facing hardware/config doctor with repair hints
- `oqlos-modbus-probe` — direct Modbus RTU probe outside the running gateway
- `oqlos-server` — API server
- `oqlos-events` — event server

### Hardware Doctor Quick Check

Use `doctor` before executing real scenarios. It compares what the host can
see with `oqlos.yaml` and with the firmware bridge, then reports actionable
issues such as mock mode, missing device mounts, a busy serial port, stale
HTTP driver services, or a Modbus port/baud mismatch.

```bash
# Human-readable report
oqlctl doctor

# Machine-readable report for scripts
oqlctl doctor --json

# Local host detection only
oqlctl detect

# Direct Modbus RTU probe outside the running gateway
oqlos-modbus-probe --serial /dev/serial/by-id/usb-1a86_USB_Single_Serial_5958006895-if00 \
  --baud 19200 --parity N --device-id 1 --function read_coils --address 0 --count 1 --timeout 2.5

# Backward-compatible aliases
oqlctl --status
oqlctl --identify

# Apply safe repairs only (currently: update detected Modbus params in oqlos.yaml)
oqlctl doctor --fix

# Example operator workflow
bash examples/hardware/doctor-workflow.sh
```

If `oqlctl --help` shows only legacy Click subcommands such as `run`, `cmd`,
and `scenarios`, activate this repository virtualenv or call `.venv/bin/oqlctl`
directly. The smart `detect`/`doctor` and hardware preflight paths live in the
current repository CLI.

Current expected Modbus RTU defaults for the Waveshare 8CH IO controller are
`19200 8N1`; prefer a stable `/dev/serial/by-id/...` path in `oqlos.yaml`
instead of relying on changing `/dev/ttyACM*` numbering. `doctor` resolves
those symlinks, so it can still report the real busy device, e.g.
`/dev/ttyACM0`, when another process owns the configured `by-id` path. If the
hardware is moved to another port, run `oqlctl doctor --fix` after confirming
the detected device is correct.
Runtime changes such as switching firmware from `mock` to `real`, restarting
containers, or mounting `/dev/ttyACM*`/`/dev/ttyUSB*` are reported as
manual/unsafe repairs and are not applied automatically.

## Requirements

- Python 3.10+
- FastAPI, Uvicorn (for API server)
- Modbus support (for hardware communication)

## Quick Start

### Start the API Server

```bash
# Start with real hardware
HARDWARE_MODE=real oqlos-server --host 0.0.0.0 --port 8200

# Run with mock hardware (development/testing)
OQLOS_HARDWARE_MODE=mock oqlos-server --port 8200
```

`oqlos-server` supports `--host` and `--port` flags.  Environment-based
defaults are still respected when flags are omitted.

### Hardware node (Raspberry Pi) — deploy, test, run

The physical rig runs on a dedicated Raspberry Pi (`pi@boardnet.local`,
192.168.188.122). The Pi owns all devices and runs the **OQL-over-MQTT agent**;
a controller can use MQTT for OQL-over-MQTT flows. The current c2004 GUI path
from DisplayNet/pi109 uses direct HTTP to `http://192.168.188.122:8202`. What is
deployed and running on the node:

| Usługa (systemd `--user`) | Port | Rola |
|---|---|---|
| `mosquitto` | `:1883` | broker MQTT (auth, `allow_anonymous false`) |
| `oqlos-hardware-api` | `:8202` (LAN) | OqlOS API/UI, `HARDWARE_MODE=real`, HUI + OQL-over-MQTT agent/controller |
| `dri0050-motor-api` | `:8203` | sidecar DFRobot DRI0050 (pompa) |
| `hw-tic249` | `:8205` | sidecar Pololu Tic T249 (płuco) |
| `pirtc-api` | `:8125` | sidecar piRTC / WatchDog HAT |

The runtime code lives at `~/oqlos/oqlos/oqlos` (deployed package, **no git** —
synced from this repo). Current BoardNet/DisplayNet status and hardware diagnosis:
`redeploy/122/CURRENT_STATE.md`.

Everything is driven through the **Makefile** (`make help` for the full list):

```bash
make help          # lista celów (PI/NODE/PORT konfigurowalne)

# Test i weryfikacja zdalnego węzła sprzętowego:
make test-hw       # łączność + sha256 integralności + smoke-test osprzętu na Pi
make smoke         # sam smoke-test (assert-hw-node-healthy) na Pi
make verify-rpi    # czy wdrożony pakiet oqlos/ == lokalny (sha256)

# Wdrożenie / utrzymanie:
make checksums     # manifest sha256 pakietu (oqlos/_CHECKSUMS.sha256)
make sync-rpi      # rsync pakietu na Pi + weryfikacja sha256 (bez restartu)
make restart       # restart agenta oqlos-hardware-api na Pi + health
make 122           # pełny redeploy węzła boardnet (redeploy run migration.md)
make pi-hw         # pełny redeploy węzła pi-hw (192.168.188.110)

# Lokalnie:
make serve         # serwer OqlOS na :8202 (panel pod /panel)
make test          # testy jednostkowe (pytest)
```

Override hosta/węzła: `make test-hw PI=pi@inny.local`, `make deploy NODE=122`.

**Co realnie działa:** BoardNet odpowiada w `mode=real`, Tic249 jest
`connected=true` i `energized=false`, DRI0050 jest healthy, Modbus-IO jest
healthy na slave ID `2`, a broker/agent MQTT działają. `modbus-adc` jest
wyłączony, bo adapter ADC nie jest obecny.

**Integralność (suma kontrolna).** `rsync` porównuje rozmiar+mtime, więc nie
wykrywa cichej korupcji treści. `make verify-rpi` (i krok `assert_oqlos_checksum`
w migracji) liczy **sha256** każdego pliku pakietu i porównuje strony — `make
test-hw` przerwie z błędem, gdy wdrożony kod rozjedzie się ze źródłem.

> **Pochodzenie kodu sprzętowego.** UI panelu (`frontend/`, podzbiór sprzętowy)
> i klient (`oqlos/hardware/client/`) zostały **skopiowane** z
> `maskservice/c2004/connect-scenario` (upstream). Źródło **nie zostało
> wyczyszczone** — te fragmenty nadal tam są, więc pilnuj rozjazdu między repo.
> Plan deduplikacji (co i kiedy usunąć z connect-scenario):
> [`docs/DEDUP-connect-scenario.md`](docs/DEDUP-connect-scenario.md).

### Run a Scenario (OQL v3 — flat syntax)

```python
from oqlos.core.interpreter import CqlInterpreter

source = """
SCENARIO: Test
DEVICE_TYPE: BA

GOAL:
  SET NAME 'Check'
  SET 'pompa-1' '5.0 l/min'
  SET WAIT '500 ms'
  GET AI01
  IF AI01 0.5 .. 0.8 V
  CORRECT 'Voltage OK'
  ERROR 'Voltage out of range'
  SAVE high-voltage
"""

interp = CqlInterpreter(mode="dry-run")
result = interp.run(source, "test.oql")
print(result.ok)  # True if successful
```

OQL v3 is a flat, quote-free syntax with 12 base commands
(`SET`, `GET`, `WAIT`, `SAVE`, `CHECK`, `MIN`, `MAX`, `SAMPLE`, `LOG`,
`ERROR`, `CALL`, `INCLUDE`).  See `docs/oql-spec.md` for the full
specification and `scenarios/OQL-CHEATSHEET.md` for a quick
reference.  The interpreter still parses legacy v1/v2 scripts with
quoted identifiers for backward compatibility.

### Motor control via OQL

Motors are actuated with `SET`. Two motors are wired through the hardware
gateway: the **pump** (DFRobot DRI0050, sidecar `:8203`) and the **artificial
lung** stepper (Pololu Tic T249, sidecar `:8205`).

```text
GOAL: Motor control
  # Pump (DRI0050) — quote the value when it carries a unit:
  SET 'pompa-1' '5.0 l/min'      # run pump at 5 l/min
  SET WAIT '2 s'
  SET 'pompa-1' '0'              # stop pump

  # Artificial lung (Tic T249) — reciprocating stepper:
  SET 'Pojemność płuca' '2.5l'   # stroke volume
  SET 'Ilość cykli płuca' '20'   # cycle count
  SET 'Płuco' 'Start'            # energize + reciprocate
  SET WAIT '5 s'
  SET 'Płuco' 'Stop'             # halt + de-energize
```

Notes (verified):

- **Quote unit-bearing values.** `SET 'pompa-1' '5.0 l/min'` parses; the
  bare form `SET pompa-1 5 l/min` is currently rejected as `unrecognized`.
- **`dry-run` / mock** parses and dispatches every motor `SET` without touching
  hardware. **`execute`** sends real HTTP to the motor sidecars — if they are
  down you get `[Errno 111] Connection refused`; physical actuation also needs
  USB access to the device (udev rule / device-group membership on the Pi).
- Shipped examples: `scenarios/test-pompy.oql` (pump),
  `scenarios/hardware-lung-smoke.oql` (lung).

### API examples (curl)

Hardware control routes take **query params** (not a JSON body); the OQL routes
take JSON. A runnable, mock-safe script lives at `examples/curl-quickstart.sh`
(read-only by default; `OQL_ACTUATE=1` also exercises the motors).

```bash
# Start a sandbox first:
OQLOS_HARDWARE_MODE=mock oqlos-server --host 127.0.0.1 --port 8202

BASE=http://127.0.0.1:8202

# --- read-only ---
curl -s $BASE/api/v1/health
curl -s $BASE/api/v1/hardware/identify
curl -s $BASE/api/v1/hardware/sensor/AI01          # {"sensor_id":"AI01","value":...}

# --- direct hardware control (query params) ---
curl -s -X POST "$BASE/api/v1/hardware/pump?power_pct=50"      # pump 50 %
curl -s -X POST "$BASE/api/v1/hardware/valve/V1?value=true"   # open valve V1
curl -s -X POST "$BASE/api/v1/hardware/lung?steps=500&speed=1000&cycles=3&pause=0.5"
curl -s -X POST "$BASE/api/v1/hardware/lung/stop"

# --- OQL over MQTT (needs OQLOS_OQL_TRANSPORT_ROLE=controller + broker) ---
curl -s -X POST "$BASE/api/v1/oql/execute" -H 'Content-Type: application/json' \
  -d '{"oql":"SET \"pompa-1\" \"5.0 l/min\"","kind":"command","mode":"execute"}'
curl -s -X POST "$BASE/api/v1/oql/manage" -H 'Content-Type: application/json' \
  -d '{"verb":"identify","args":{"scan":"never"}}'
# On a non-controller node these return: {"detail":"OQL MQTT transport is disabled (role=off)"}
```

Or just run the script:

```bash
bash examples/curl-quickstart.sh                 # read-only probes
OQL_ACTUATE=1 bash examples/curl-quickstart.sh   # also actuate (mock-safe)
```

## Package Structure

```
oqlos/
├── core/
│   ├── interpreter.py   # CqlInterpreter — main execution engine
│   ├── oql_parser.py    # OQL v3 flat parser (12 base commands)
│   ├── _oql_adapter.py  # v3 AST → legacy CqlDocument bridge (+ INCLUDE/MACRO)
│   ├── cql_parser.py    # Legacy v1/v2 parser (dispatches to v3 on detection)
│   └── …
├── models/              # Data models (dsl_models, scenario, execution, peripheral)
├── hardware/            # Hardware abstraction (Modbus, HTTP adapters, …)
├── api/                 # FastAPI REST server and routes
├── executor/            # Scenario execution helpers
├── scenarios/           # Scenario files (.oql) — all in v3 flat syntax
│   ├── lib/             # Macro libraries (hardware.oql, peripherals.oql)
│   └── examples/        # Didactic examples
└── shared/              # Utilities (logger, config, version)
```

## Core Components

### CqlInterpreter

The main execution engine for OQL scenarios:

```python
from oqlos.core.interpreter import CqlInterpreter

# Modes: "dry-run", "execute", "validate"
interp = CqlInterpreter(
    mode="dry-run",
    firmware_url="http://localhost:8202",
    quiet=False
)

result = interp.run(source_code, filename)
# result.ok: bool — execution success
# result.events: list — execution trace
# result.variables: dict — captured variables
```

### Parser

Auto-detecting parser pipeline:

1. `parse_cql(source, filename)` first checks the source with
   `is_flat_oql()`.
2. If the source uses v3 flat grammar (`GOAL:` + `SET NAME`, no quotes,
   `INCLUDE "..."`), it dispatches to `parse_flat_oql()` which returns a
   legacy `CqlDocument` via `oqlos/core/_oql_adapter.py`
   (`INCLUDE` + `MACRO`/`CALL` expansion happens here).
3. Otherwise the legacy state-machine parser handles it.

```python
from oqlos.core.cql_parser import parse_cql
from oqlos.core.oql_parser import parse_oql

doc = parse_cql(source, "test.oql")      # either path
raw = parse_oql(source, "test.oql")      # just the v3 AST (OqlDoc)
```

## API Endpoints

When running `oqlos-server`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/hardware/peripherals` | GET | List connected hardware |
| `/api/scenarios` | GET | List available scenarios |
| `/api/scenarios/{id}/run` | POST | Execute a scenario |
| `/health` | GET | Health check |

## OQL Scenario Format (v3 Flat Syntax)

OQL scenarios describe hardware tests with a minimal set of **12 base
commands**: `SET`, `GET`, `WAIT`, `SAVE`, `CHECK`, `MIN`, `MAX`, `SAMPLE`,
`LOG`, `ERROR`, `CALL`, `INCLUDE` — plus block headers `GOAL`, `CONFIG`
and `MACRO`.  Full specification: `docs/oql-spec.md`.

```oql
SCENARIO: PSS 7000 Mask Test
DEVICE_TYPE: BA
DEVICE_MODEL: PSS 7000
MANUFACTURER: Dräger

INCLUDE "lib/peripherals.oql"

CONFIG reset:
  CALL init-all

GOAL:
  SET NAME 'Visual inspection'
  SET valve-nc 1
  SET WAIT '2 s'
  GET AI01
  IF AI01 0.60 .. 0.67 V
  CORRECT 'NC voltage in range'
  ERROR 'NC voltage out of range'
  SAVE nc-voltage-reading
```

Key rules:

- **SET uses single-quoted target and value** in canonical OQL:
  `SET 'pompa głównego obiegu' '5 l/min'`.
  Legacy bare/bracketed forms are still accepted while older scenarios are migrated.
- **GOAL name set via SET NAME** — use `GOAL:` followed by `SET NAME 'nazwa'`
  inside the block. Legacy `GOAL name:` still works for backward compatibility.
- **No `IF/ELSE/ENDIF`** — use `IF min .. max unit` with `CORRECT`/`ERROR` messages
  for range assertions, or split into multiple `GOAL` blocks for sequencing.
- **Unicode is welcome** — `ciśnienie-NC`, `°C`, `%RH`, `μV`, `m³/h` …

### CONFIG Blocks

`CONFIG` blocks are semantically identical to `GOAL` but marked
`[CONFIG]` in logs — convention for initialization and cleanup:

```oql
SCENARIO: System Startup
DEVICE_TYPE: BA

INCLUDE "lib/peripherals.oql"

CONFIG safety-initialization:
  CALL init-pump
  CALL init-valves-main
  SET WAIT '500 ms'

CONFIG pump-calibration:
  # 10 l/min corresponds to 100% PWM by default
  SET PUMP_FLOW_FULL_SCALE_LPM 10.0

GOAL:
  SET NAME 'Voltage test'
  SET valve-nc 1
  SET WAIT '1 s'
  GET AI01
  SAVE voltage-test
```

### Macros and INCLUDE

Reusable sequences live in `scenarios/lib/` and are pulled in with
`INCLUDE`.  Positional arguments use `$1`, `$2`, … placeholders:

```oql
INCLUDE "lib/hardware.oql"

MACRO pump-ramp:
  SET pump-main $1 l/min
  SET WAIT '$2'
  SET pump-main 0

GOAL:
  SET NAME 'Smoke'
  CALL pump-ramp 5 2s
  CALL hw-valves-smoke
  CALL hw-sensors-baseline
```

### Running Scenarios

```bash
# Dry-run (validate and simulate)
oqlctl scenarios/config-peripherals.oql --mode dry-run
oqlctl run scenarios/config-peripherals.oql --mode dry-run

# Execute on real hardware
oqlctl scenarios/config-peripherals.oql --mode execute
oqlctl run scenarios/config-peripherals.oql --mode execute

# Execute with custom firmware URL
oqlctl scenarios/config-peripherals.oql \
  --firmware-url http://localhost:8202 \
  --mode execute

# Run a scenario directly from a raw .oql URL or JSON source endpoint
oqlctl run "http://localhost:9000/scenarios/maskleaktest-nadcisnieniestatyczne.oql" \
  --mode dry-run

# Fastest single-command hardware execution (v3 syntax)
oqlctl cmd "SET pompa-1 0"

# Single command without touching hardware
oqlctl cmd "SET pompa-1 0" --mode dry-run

# Parseable single-command dry-run output
oqlctl cmd "SET pompa-1 0" --mode dry-run --json -q

# Validate every .oql in a directory tree
oqlctl --validate-dir scenarios
```

For URL runs, the response must be raw OQL/CQL text or JSON with one of
`code`, `dsl`, `source`, or `content`. Editor/browser routes such as
`http://localhost:8096/scenarios?scenario=...` return HTML and are rejected.

Use `cmd` when you want to send a single OQL line to the firmware;
use a file path when the action requires multiple steps.

### Scenario Sync (DB <-> local)

This repo includes scripts for synchronizing scenario DSL between database rows and local `.oql` files.

#### 1) DB -> local files

Export all scenarios from DB API to a ZIP archive:

```bash
python3 scripts/scenarios_export.py \
  --base "http://localhost:8096" \
  --all \
  --out scenarios.zip
```

Unpack to a local directory:

```bash
mkdir -p scenarios
unzip -o scenarios.zip -d scenarios
```

The archive includes one `<id>.oql` file per scenario and `manifest.json`.

Export a single scenario (id or UI URL with `?scenario=`):

```bash
python3 scripts/scenarios_export.py \
  --base "http://localhost:8096" \
  --scenario "ts-temp-wilgotnosc" \
  --out ts-temp-wilgotnosc.oql.bash
```

#### 2) local files -> DB (Import)

Import all `.oql` files from a local directory into the database, overwriting existing scenarios:

```bash
python3 scripts/scenarios_export.py --import --dir ./scenarios
```

With custom API base and validation disabled:

```bash
python3 scripts/scenarios_export.py \
  --base "http://localhost:8096" \
  --import \
  --dir ./scenarios \
  --no-validate
```

Each file named `<id>.oql` updates the scenario `<id>` via PATCH. 
Files are validated against OQL v4 by default before import.

**Alternative: Use the migration/sync script** for more control:

Dry-run preview (no write):

```bash
python3 scripts/oql_v2_to_v4_migrate_db.py \
  --source-url "http://localhost:8100/connect-data/test-scenarios" \
  --prefer-local \
  --pretty
```

Apply updates to DB:

```bash
python3 scripts/oql_v2_to_v4_migrate_db.py \
  --source-url "http://localhost:8100/connect-data/test-scenarios" \
  --prefer-local \
  --apply \
  --write-method PATCH \
  --write-url "http://localhost:8101/api/v1/data/test_scenarios/{id}" \
  --pretty
```

Notes:

- `--prefer-local` reads local files from `scenarios/<id>.oql`.
- DB row `id` must match local filename (without `.oql`).
- Run without `--apply` first to verify changes and runtime validation output.

#### CLI Output Example

```
📋 CQL: Konfiguracja Peryferii
🔧 Device: BA / PSS 7000
🎯 GOAL: [CONFIG] init-pompa
  ⚙️ SET 'pump-main' '0'
  ⚙️ SET 'pompa-1' '0'
  ⏳ WAIT 0.5s
  ✅ [passed] [CONFIG] init-pompa
🎯 GOAL: [CONFIG] init-zawory-nc
  ⚙️ SET 'valve-nc' '0'
  ...
✅ Konfiguracja Peryferii: 10/10 passed
```

## Supported Hardware

- **Valves**: valve-1 through valve-14, valve-nc, valve-sc, valve-wc (Modbus RTU via `/dev/serial/by-id/...` or `/dev/ttyACM*` @ 19200 8N1)
- **Pump**: pump-main (DRI0050 PWM motor driver via HTTP :49055)
- **Artificial lung**: lung-main (Tic T249 stepper via HTTP :8205)
- **Sensors**: AI01 (NC), AI02 (SC), AI03 (WC) (piADC ADS1115 via HTTP :8204; raw ADC voltage)

### Hardware Adapters

| Adapter | Class | Protocol | Default URL |
|---------|-------|----------|-------------|
| Motor (pump) | `_DRI0050MotorAdapter` | HTTP POST /api/speed | http://localhost:49055 |
| Lung (artificial lung) | `_Tic249LungAdapter` | HTTP POST /api/lung | http://localhost:8205 |
| Valves | `_ModbusAdapter` | Modbus RTU (pymodbus) | /dev/ttyACM1 serial |
| Sensors | `_PiAdcAdapter` | HTTP GET /api/v1/hardware/sensor/{id} | http://localhost:8204 |

### Hardware Identification & Diagnostics

Preferred operator commands:

```bash
oqlctl detect              # local USB/serial/I2C/Modbus probe
oqlctl doctor              # detect runtime/config problems
oqlctl doctor --json       # parseable report
oqlctl doctor --fix        # safe config repair for detected Modbus settings
```

The `/api/v1/hardware/identify` endpoint returns the adapter registry, live probe
status, and a diagnostics block with:

- USB device inventory
- Serial port inventory (`ttyACM*` and `ttyUSB*`)
- I2C bus inventory (`/dev/i2c-*`)
- Best-effort bridge health snapshot for `piadc`, `motor`, `lung`, and `modbus`

The current valve calibration flow uses raw `piADC` voltage windows in the test scenario
`scenarios/test-zaworu.oql`, while `hardware-valves-smoke.oql` only verifies
basic open/close actuation.

### Recent Fixes (2026-05-05)

- **Motor disable path fixed**: `POST /api/v1/hardware/lung/disable` now consistently de-energizes Tic T249.
- **Identify endpoint acceleration**: `/api/v1/hardware/identify` supports conditional scan mode (`scan=auto|always|never`) and skips expensive live scan when plugin health is already compatible.
- **False-success prevention for lung start**: lung command path now returns structured failure (`ok=false` + `error` + `data.runtime_status`) when motion is blocked.
- **Pre-checks before reciprocate**: lung startup validates blocker conditions first (both limit switches active, low VIN, driver fault, disconnected controller).
- **Modbus diagnostics quality**: when adapter is open but device is silent, diagnostics report no-response context instead of misleading lock/access-only signals.

Quick verification commands:

```bash
curl -sS 'http://127.0.0.1:8202/api/v1/hardware/identify?scan=auto' | jq '.diagnostics.scan_performed, .diagnostics.scan_skip_reason'
curl -sS -X POST 'http://127.0.0.1:8202/api/v1/hardware/lung/disable' | jq
curl -sS -X POST 'http://127.0.0.1:8202/api/v1/hardware/lung?steps=500&speed=10000000&cycles=1&pause=0.5' | jq
```

Expected behavior for blocked hardware cases:

- both limits active: `error="Both limit switches are active; movement is blocked"`
- low supply voltage: `error="Motor supply voltage is too low"`

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OQLOS_HARDWARE_MODE` | `mock` | `mock` or `real` |
| `OQLOS_MOTOR_URL` | `http://localhost:49055` | DRI0050 motor service |
| `OQLOS_LUNG_MOTOR_URL` | `http://localhost:8205` | Tic T249 lung service |
| `OQLOS_PIADC_URL` | `http://localhost:8080` | piADC sensor service |
| `OQLOS_MODBUS_SERIAL_PORT` | `/dev/ttyACM1` | Modbus RTU serial port |
| `OQLOS_MODBUS_BAUD` | `19200` | Modbus baud rate |
| `OQLOS_PUMP_FLOW_FULL_SCALE_LPM` | `10` | Flow rate that maps to 100% PWM for `pompa 1` |

Notes:

- Both prefixed and legacy env names are accepted (for easier rollout):
  `OQLOS_HARDWARE_MODE` or `HARDWARE_MODE`, `OQLOS_FIRMWARE_PORT` or
  `FIRMWARE_PORT`, etc.
- Prefer the `OQLOS_*` namespace in new deployments to avoid collisions
  with other services.

## Docker Deployment

### Run locally (mock hardware)

The reliable single-service path — exposes the API directly on `:8200`, no
reverse proxy, no port-80 conflict:

```bash
# build + start just the API in mock mode
docker compose -f docker/docker-compose.dev.yml up -d --build oqlos-api

# smoke test
curl -s http://127.0.0.1:8200/api/v1/health
curl -s -X POST "http://127.0.0.1:8200/api/v1/hardware/pump?power_pct=50"
bash examples/curl-quickstart.sh          # full read-only sweep against :8200

# stop
docker compose -f docker/docker-compose.dev.yml down
```

Full stack (adds a `traefik` reverse proxy on `:80`, routing
`Host: api.oqlos.localhost` → the API):

```bash
docker compose -f docker/docker-compose.dev.yml up -d --build
curl -s -H 'Host: api.oqlos.localhost' http://127.0.0.1/api/v1/health
```

> If `:80` is already taken on the host, traefik fails with *"port is already
> allocated"* — either free `:80`, remap the traefik `ports:` entry, or just use
> the single-service `oqlos-api` form above.

Production image (real hardware mode, `:8200`):

```bash
docker compose -f docker/docker-compose.prod.yml up -d --build
```

> The image installs `pip install -e .` only; the external `pimodbus` library is
> **not** bundled. Mock mode and the HTTP/OQL API run without it; real Modbus
> probing needs `pimodbus` on `PYTHONPATH` (hardware nodes add it at deploy).

### What Docker emulates (and what it does not)

The `dev` compose is a **single-node, mock-hardware emulation** of the runtime:
`traefik` exposes the HTTP/REST/web UI on port `80`, and `oqlos-api` runs with
`OQLOS_HARDWARE_MODE=mock` — every peripheral is simulated, so motor/valve/sensor
`SET`/`GET` succeed without any physical device. Good for developing scenarios
and exercising the API/web panel.

It does **not** emulate the production Raspberry Pi 3 topology:

- no MQTT broker (mosquitto) and no **OQL-over-MQTT agent/controller** split — the
  compose runs the runtime directly over HTTP, not the distributed transport;
- no real Modbus / Tic249 / DRI0050 / RTC devices (mock only).

For the real distributed deployment onto a dedicated RPi3 hardware node
(mosquitto `:1883` + agent on loopback `:8202` + sidecars), use the redeploy
runbooks: `redeploy/122/migration.md` (boardnet, 192.168.188.122) or
`redeploy/pi-hw/migration.md` (192.168.188.110). See **Ports** in those RUNBOOKs.

## Testing

```bash
# Run all tests
pytest -q

# Run with coverage
pytest --cov=oqlos

# Run specific test file
pytest tests/test_interpreter.py -v

# Run OQL scenarios (dry-run)
python -m oqlos.core.interpreter scenarios/test-pompy.oql --mode dry-run
```

**Status:** current local verification: `356 passed`.

## Documentation

- [OQL Language Specification](docs/oql-spec.md) — Complete language reference
- [Hardware Diagnostics](docs/HARDWARE_DIAGNOSTICS.md) — Smart detect, doctor, calibration, and troubleshooting
- [Docs Index](docs/README.md) — Project documentation overview

## License

Licensed under Apache-2.0.
