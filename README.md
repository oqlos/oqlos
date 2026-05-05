# OqlOS — Operation Query Language Runtime


## AI Cost Tracking

![PyPI](https://img.shields.io/badge/pypi-costs-blue) ![Version](https://img.shields.io/badge/version-0.1.7-blue) ![Python](https://img.shields.io/badge/python-3.9+-blue) ![License](https://img.shields.io/badge/license-Apache--2.0-green)
![AI Cost](https://img.shields.io/badge/AI%20Cost-$4.50-orange) ![Human Time](https://img.shields.io/badge/Human%20Time-23.9h-blue) ![Model](https://img.shields.io/badge/Model-openrouter%2Fqwen%2Fqwen3--coder--next-lightgrey)

- 🤖 **LLM usage:** $4.5000 (30 commits)
- 👤 **Human dev:** ~$2391 (23.9h @ $100/h, 30min dedup)

Generated on 2026-05-05 using [openrouter/qwen/qwen3-coder-next](https://openrouter.ai/qwen/qwen3-coder-next)

---

![Version](https://img.shields.io/badge/version-0.1.7-blue) ![Python](https://img.shields.io/badge/python-3.10+-blue) ![License](https://img.shields.io/badge/license-Apache--2.0-green)


OqlOS is the core runtime for executing OQL (Operation Query Language) hardware testing scenarios. It provides the execution engine, hardware abstraction layer, and API server for running automated hardware tests.

## Installation

```bash
# Install from source with development dependencies
pip install -e ".[dev]"

# Basic installation
pip install -e .
```

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
- `oqlos-server` — API server
- `oqlos-events` — event server

### Hardware Doctor Quick Check

Use `doctor` before executing real scenarios. It compares what the host can
see with `oqlos.yaml` and with the firmware bridge, then reports actionable
issues such as mock mode, missing device mounts, or a Modbus port/baud mismatch.

```bash
# Human-readable report
oqlctl doctor

# Machine-readable report for scripts
oqlctl doctor --json

# Local host detection only
oqlctl detect

# Backward-compatible aliases
oqlctl --status
oqlctl --identify

# Apply safe repairs only (currently: update detected Modbus params in oqlos.yaml)
oqlctl doctor --fix

# Example operator workflow
bash examples/hardware/doctor-workflow.sh
```

Current expected Modbus RTU defaults for the Waveshare 8CH IO controller:
`/dev/ttyACM1 @ 19200 8N1`. If the hardware is moved to another port, run
`oqlctl doctor --fix` after confirming the detected device is correct.
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

### Run a Scenario (OQL v3 — flat syntax)

```python
from oqlos.core.interpreter import CqlInterpreter

source = """
SCENARIO: Test
DEVICE_TYPE: BA

GOAL:
  SET NAME 'Check'
  SET pompa-1 5.0 l/min
  WAIT 500ms
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
specification and `oqlos/scenarios/OQL-CHEATSHEET.md` for a quick
reference.  The interpreter still parses legacy v1/v2 scripts with
quoted identifiers for backward compatibility.

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
  WAIT 2s
  GET AI01
  IF AI01 0.60 .. 0.67 V
  CORRECT 'NC voltage in range'
  ERROR 'NC voltage out of range'
  SAVE nc-voltage-reading
```

Key rules:

- **Identifiers are bare** — no surrounding quotes
  (`pump-main`, not `'pump-main'`).  For names with spaces use brackets:
  `SET [pompa głównego obiegu] 5 l/min`.
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
  WAIT 500ms

CONFIG pump-calibration:
  # 10 l/min corresponds to 100% PWM by default
  SET PUMP_FLOW_FULL_SCALE_LPM 10.0

GOAL:
  SET NAME 'Voltage test'
  SET valve-nc 1
  WAIT 1s
  GET AI01
  SAVE voltage-test
```

### Macros and INCLUDE

Reusable sequences live in `oqlos/scenarios/lib/` and are pulled in with
`INCLUDE`.  Positional arguments use `$1`, `$2`, … placeholders:

```oql
INCLUDE "lib/hardware.oql"

MACRO pump-ramp:
  SET pump-main $1 l/min
  WAIT $2
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
oqlctl --validate-dir oqlos/scenarios
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

- `--prefer-local` reads local files from `oqlos/scenarios/<id>.oql`.
- DB row `id` must match local filename (without `.oql`).
- Run without `--apply` first to verify changes and runtime validation output.

#### CLI Output Example

```
📋 CQL: Konfiguracja Peryferii
🔧 Device: BA / PSS 7000
🎯 GOAL: [CONFIG] init-pompa
  ⚙️ SET [pump-main] = [0]
  ⚙️ SET [pompa-1] = [0]
  ⏳ WAIT 0.5s
  ✅ [passed] [CONFIG] init-pompa
🎯 GOAL: [CONFIG] init-zawory-nc
  ⚙️ SET [valve-nc] = [0]
  ...
✅ Konfiguracja Peryferii: 10/10 passed
```

## Supported Hardware

- **Valves**: valve-1 through valve-14, valve-nc, valve-sc, valve-wc (Modbus RTU via /dev/ttyACM1 @ 19200 8N1)
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
`oqlos/oqlos/scenarios/test-zaworu.oql`, while `hardware-valves-smoke.oql` only verifies
basic open/close actuation.

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

```bash
# Development
docker-compose -f docker/docker-compose.dev.yml up

# Production
docker-compose -f docker/docker-compose.prod.yml up -d
```

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
