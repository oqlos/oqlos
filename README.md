# OqlOS — Operation Query Language Runtime


## AI Cost Tracking

![PyPI](https://img.shields.io/badge/pypi-costs-blue) ![Version](https://img.shields.io/badge/version-0.1.1-blue) ![Python](https://img.shields.io/badge/python-3.9+-blue) ![License](https://img.shields.io/badge/license-Apache--2.0-green)
![AI Cost](https://img.shields.io/badge/AI%20Cost-$0.75-orange) ![Human Time](https://img.shields.io/badge/Human%20Time-5.5h-blue) ![Model](https://img.shields.io/badge/Model-openrouter%2Fqwen%2Fqwen3--coder--next-lightgrey)

- 🤖 **LLM usage:** $0.7500 (5 commits)
- 👤 **Human dev:** ~$547 (5.5h @ $100/h, 30min dedup)

Generated on 2026-04-15 using [openrouter/qwen/qwen3-coder-next](https://openrouter.ai/qwen/qwen3-coder-next)

---



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

### Run a Scenario

```python
from oqlos.core.interpreter import CqlInterpreter

source = """
SCENARIO: "Test"
DEVICE_TYPE: "BA"
GOAL: Check
  1. Step:
    → Sensor.read AI01
"""

interp = CqlInterpreter(mode="dry-run")
result = interp.run(source, "test.oql")
print(result.ok)  # True if successful
```

## Package Structure

```
oqlos/
├── core/               # Parser, executor, state machine, interpreter
│   ├── interpreter.py  # CqlInterpreter main execution engine
│   ├── parser.py       # OQL language parser
│   └── cql_parser.py   # Legacy CQL parser support
├── models/             # Data models
│   ├── scenario.py     # Scenario definition models
│   ├── execution.py    # Execution state models
│   └── peripheral.py   # Hardware peripheral models
├── hardware/           # Hardware abstraction
│   ├── gateway.py      # Hardware gateway interface
│   ├── modbus/         # Modbus communication
│   └── drivers/        # Device drivers
├── api/                # REST API
│   ├── server.py       # FastAPI application
│   └── routes/         # API endpoints
├── executor/           # Scenario execution logic
├── scenarios/          # Sample .oql scenario files
└── shared/             # Utilities (logger, config, version)
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

Two-phase parsing pipeline:

1. **Raw Parser** — Converts OQL text to structured blocks
2. **CQL Parser** — Processes blocks into executable commands

```python
from oqlos.core.parser import parse_scenario
from oqlos.core.cql_parser import CqlParser

blocks = parse_scenario(source)
parser = CqlParser(blocks)
scenario = parser.parse()
```

## API Endpoints

When running `oqlos-server`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/hardware/peripherals` | GET | List connected hardware |
| `/api/scenarios` | GET | List available scenarios |
| `/api/scenarios/{id}/run` | POST | Execute a scenario |
| `/health` | GET | Health check |

## OQL Scenario Format

OQL scenarios define hardware testing procedures declaratively:

```oql
SCENARIO: "PSS 7000 Mask Test"
DEVICE_TYPE: "BA"
DEVICE_MODEL: "PSS 7000"
MANUFACTURER: "Dräger"

@Namespace.ScenarioName
  intervals: [tt#000, tt#001]

GOAL: Visual Inspection
  1. Check mask surface:
    → Valve.open NC
    WAIT 2000
    → Sensor.read AI01
    IF [AI01] [>=] [0.60 V] ELSE ERROR "NC sensor voltage too low"
    IF [AI01] [<=] [0.67 V] ELSE ERROR "NC sensor voltage too high"
    SAVE: nc_voltage_reading
```

### CONFIG Blocks (Configuration Goals)

Use `CONFIG:` for hardware initialization and setup procedures. CONFIG blocks are semantically identical to GOAL blocks but marked with `[CONFIG]` prefix for clarity in logs and documentation.

#### Basic CONFIG Example

```oql
SCENARIO: "System Startup"
DEVICE_TYPE: "BA"

CONFIG: Safety Initialization
  # Always disable pump on startup
  SET 'pump-main' '0'
  SET 'PUMP' 'off'
  WAIT 500

CONFIG: Valve Reset
  # Close all valves to known state
  SET 'valve-nc' 'closed'
  SET 'valve-sc' 'closed'
  SET 'valve-wc' 'closed'
  WAIT 300

GOAL: Voltage Test
  SET 'valve-nc' 'open'
  WAIT 1000
  → Sensor.read AI01
  SAVE: voltage_test
```

#### Configuration File: config-peripherals.oql

Full peripheral initialization scenario:

```oql
SCENARIO: 'Konfiguracja Peryferii'
DEVICE_TYPE: 'BA'
DEVICE_MODEL: 'PSS 7000'
MANUFACTURER: 'Dräger'

# ============================================
# PUMP INITIALIZATION
# ============================================
CONFIG: INIT Pompa
  SET 'pump-main' '0'
  SET 'pompa 1' '0'
  SET 'PUMP' 'off'
  WAIT 500

# ============================================
# VALVE INITIALIZATION
# ============================================
CONFIG: INIT Zawory NC
  SET 'valve-nc' 'closed'
  SET 'zawór NC' 'closed'
  WAIT 300

CONFIG: INIT Zawory SC
  SET 'valve-sc' 'closed'
  SET 'zawór SC' 'closed'
  WAIT 300

CONFIG: INIT Zawory ogólne
  SET 'valve-1' '0'
  SET 'valve-2' '0'
  SET 'valve-3' '0'
  SET 'valve-4' '0'
  WAIT 500

# ============================================
# SYSTEM READY STATE
# ============================================
CONFIG: STATE Ready
  SAVE: system_ready
  WAIT 1000
```

#### Running Configuration

```bash
# Dry-run (validate and simulate)
oqlctl run scenarios/config-peripherals.oql --mode dry-run

# Execute on real hardware
oqlctl run scenarios/config-peripherals.oql --mode execute

# Execute with custom firmware URL
oqlctl run scenarios/config-peripherals.oql \
  --firmware-url http://localhost:8202 \
  --mode execute
```

#### CLI Output Example

```
📋 CQL: 'Konfiguracja Peryferii'
🔧 Device: 'BA' / 'PSS 7000'
🎯 GOAL: [CONFIG] INIT Pompa
  📌 Step 0: [CONFIG] INIT Pompa
    ⚙️ SET [pump-main] = [0]
    ⚙️ SET [pompa 1] = [0]
    ⏳ WAIT 0.5s
    ✅ [passed] [CONFIG] INIT Pompa
🎯 GOAL: [CONFIG] INIT Zawory NC
  ⚙️ SET [valve-nc] = [closed]
  ...
✅ 'Konfiguracja Peryferii': 11/11 passed
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
