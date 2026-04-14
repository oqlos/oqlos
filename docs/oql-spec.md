# OQL Language Specification v1.0

## Overview

OQL (Operation Query Language) is a declarative DSL for defining hardware testing procedures. Files use the `.oql` extension (legacy: `.cql`).

## Document Structure

```
SCENARIO: "Scenario Name"
DEVICE_TYPE: "BA"
DEVICE_MODEL: "PSS 7000"
MANUFACTURER: "Dräger"

@Namespace.ScenarioName
  intervals: [tt#000, tt#001]

  Goal Name:
    1. Step name:
      → Target.method args
      WAIT 2000
      IF [sensor] [op] [value] ELSE ERROR "message"
      SAVE: variable_name
```

## Metadata

```
SCENARIO: "name"
DEVICE_TYPE: "type"
DEVICE_MODEL: "model"
MANUFACTURER: "manufacturer"
```

## Intervals

```
- tt#000: "Label" period: 12 months
- tt#001: "Another" period: 6 months
```

## Goals and Steps

```
GOAL: Goal description

  1. Step description:
    → Valve.open NC
    WAIT 2000
    → Sensor.read AI01
```

## Actions

```
→ Target.method [args]    # Hardware action
SET [var] = [value]       # Set variable
SAVE: var                 # Save measurement
SAVE [description]        # Save with label
WAIT [ms]                 # Wait duration
PUMP [value]              # Set pump level
```

## Conditions

```
AI01 ∈ [-15, 0] mbar | ERROR "Pressure out of range"
AI02 ≥ 5.0 bar | PASS
Timer ∈ [0, 30000] ms | WAIT "Stabilization"
IF [sensor] [op] [value unit] ELSE ERROR "message"
```

## Min/Max/Val

```
MIN [sensor] = [value unit]
MAX [sensor] = [value unit]
VAL [label] [sensor]
```

## Supported Hardware

- Valves: valve-1 through valve-14, valve-nc, valve-sc, valve-wc
- Pump: pump-main
- Sensors: AI01 (NC), AI02 (SC), AI03 (WC)
