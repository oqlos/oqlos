# OqlOS — Operation Query Language Runtime

![Version](https://img.shields.io/badge/version-0.1.1-blue) ![Python](https://img.shields.io/badge/python-3.10+-blue) ![License](https://img.shields.io/badge/license-Apache--2.0-green)


OqlOS is the core runtime for executing OQL (Operation Query Language) hardware testing scenarios. It provides the execution engine, hardware abstraction layer, and API server for running automated hardware tests.

## Installation

```bash
# Install from source with development dependencies
pip install -e ".[dev]"

# Basic installation
pip install -e .
```

## Requirements

- Python 3.10+
- FastAPI, Uvicorn (for API server)
- Modbus support (for hardware communication)

## Quick Start

### Start the API Server

```bash
# Start with real hardware
oqlos-server --port 8200

# Run with mock hardware (development/testing)
OQLOS_HARDWARE_MODE=mock oqlos-server --port 8200
```

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

# Execute on real hardware
oqlctl scenarios/config-peripherals.oql --mode execute

# Execute with custom firmware URL
oqlctl scenarios/config-peripherals.oql \
  --firmware-url http://localhost:8202 \
  --mode execute

# Fastest single-command hardware execution (v3 syntax)
oqlctl cmd "SET pompa-1 0"

# Single command without touching hardware
oqlctl cmd "SET pompa-1 0" --mode dry-run

# Validate every .oql in a directory tree
oqlctl --validate-dir oqlos/scenarios
```

Use `cmd` when you want to send a single OQL line to the firmware;
use a file path when the action requires multiple steps.

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
| `MOTOR_URL` | `http://localhost:49055` | DRI0050 motor service |
| `LUNG_MOTOR_URL` | `http://localhost:8205` | Tic T249 lung service |
| `PIADC_URL` | `http://localhost:8080` | piADC sensor service |
| `MODBUS_SERIAL_PORT` | `/dev/ttyACM1` | Modbus RTU serial port |
| `MODBUS_BAUD_RATE` | `19200` | Modbus baud rate |
| `PUMP_FLOW_FULL_SCALE_LPM` | `10` | Flow rate that maps to 100% PWM for `pompa 1` |

## Docker Deployment

```bash
# Development
docker-compose -f docker/docker-compose.dev.yml up

# Production
docker-compose -f docker/docker-compose.prod.yml up -d
```

## Testing

```bash
# Run all tests (96 passing)
pytest

# Run with coverage
pytest --cov=oqlos

# Run specific test file
pytest tests/test_interpreter.py -v

# Run OQL scenarios (dry-run)
python -m oqlos.core.interpreter scenarios/test-pompy.oql --mode dry-run
```

**Status:** 96 tests passing, 3 scenarios (12/12 goals), CC̄≤15, 0 violations

## Documentation

- [OQL Language Specification](docs/oql-spec.md) — Complete language reference
- [API Documentation](docs/api.md) — REST API details

## License

Licensed under Apache-2.0.
