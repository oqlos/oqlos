# OqlOS — Operation Query Language Runtime

OqlOS is the core runtime for executing OQL hardware testing scenarios.

## Installation

```bash
pip install -e ".[dev]"
```

## Usage

```bash
# Start the OqlOS API server
oqlos-server --port 8200

# Run with mock hardware (development)
OQLOS_HARDWARE_MODE=mock oqlos-server --port 8200
```

## Package Structure

- `oqlos/core/` — Parser, executor, state machine, CQL interpreter
- `oqlos/models/` — Scenario, execution, peripheral data models
- `oqlos/hardware/` — Hardware gateway, Modbus discovery, drivers
- `oqlos/api/` — FastAPI REST endpoints
- `oqlos/shared/` — Logger, config, version utilities
- `oqlos/scenarios/` — `.oql` scenario files (renamed from `.cql`)

## Scenarios

OQL scenarios define hardware testing procedures in a declarative DSL:

```
SCENARIO: "PSS 7000 Mask Test"
DEVICE_TYPE: "BA"
DEVICE_MODEL: "PSS 7000"

GOAL: Visual Inspection
  1. Check mask surface:
    → Valve.open NC
    WAIT 2000
    → Sensor.read AI01
    IF [AI01] [>=] [-15 mbar] ELSE ERROR "Pressure too low"
```