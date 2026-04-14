# OqlOS — Operation Query Language Runtime

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
    IF [AI01] [>=] [-15 mbar] ELSE ERROR "Pressure too low"
    SAVE: pressure_reading
```

## Supported Hardware

- **Valves**: valve-1 through valve-14, valve-nc, valve-sc, valve-wc (Modbus RTU via /dev/ttyACM1 @ 19200 8N1)
- **Pump**: pump-main (DRI0050 PWM motor driver via HTTP :8203)
- **Sensors**: AI01 (NC), AI02 (SC), AI03 (WC) (piADC ADS1115 via HTTP :8204)

### Hardware Adapters

| Adapter | Class | Protocol | Default URL |
|---------|-------|----------|-------------|
| Motor (pump) | `_DRI0050MotorAdapter` | HTTP POST /api/speed | http://localhost:8203 |
| Valves | `_ModbusAdapter` | Modbus RTU (pymodbus) | /dev/ttyACM1 serial |
| Sensors | `_PiAdcAdapter` | HTTP GET /api/v1/hardware/sensor/{id} | http://localhost:8204 |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OQLOS_HARDWARE_MODE` | `mock` | `mock` or `real` |
| `MOTOR_URL` | `http://localhost:8203` | DRI0050 motor service |
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

Apache-2.0