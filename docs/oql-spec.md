# OQL Language Specification v1.0

## Overview

OQL (Operation Query Language) is a declarative DSL for defining hardware testing procedures. Files use the `.oql` extension (legacy: `.cql`).

## Document Structure

```
SCENARIO: 'Scenario Name'
DEVICE_TYPE: 'BA'
DEVICE_MODEL: 'PSS 7000'
MANUFACTURER: 'Dräger'

@Namespace.ScenarioName
  intervals: [tt#000, tt#001]

  Goal Name:
    1. Step name:
      SET 'pompa 1' '5.0 l/min'
      WAIT '2.0 s'
      IF 'AI01' ≥ '0.0 mbar'
        SAVE 'AI01.value'
      ENDIF
```

## Metadata

```
SCENARIO: 'name'
DEVICE_TYPE: 'type'
DEVICE_MODEL: 'model'
MANUFACTURER: 'manufacturer'
```

## Intervals

```
- tt#000: 'Label' period: 12 months
- tt#001: 'Another' period: 6 months
```

## Goals and Steps

```
GOAL: Goal description

  1. Step description:
    SET 'valve-nc' '1 (open)'
    WAIT '2.0 s'
    VAL 'AI01' 'V'
```

## Actions

```
SET 'target' 'value unit'   # Set peripheral (e.g., 'pompa 1' '5.0 l/min')
SAVE 'description'         # Save measurement
WAIT 'duration unit'       # Wait duration (e.g., '2.0 s')
VAL 'label' 'unit'         # Read sensor value
MIN 'sensor' 'value unit'  # Minimum threshold
MAX 'sensor' 'value unit'  # Maximum threshold
IF 'sensor' [op] 'value'   # Conditional
ENDIF                       # End conditional block
```

Pump flow values written as `l/min` are mapped to PWM using `PUMP_FLOW_FULL_SCALE_LPM`.
The value may come from `.env` or from a `CONFIG` block inside the `.oql` file, for example:

```oql
CONFIG: Pump Calibration
  PUMP_FLOW_FULL_SCALE_LPM=10
```

**Note:** Pump values should always include units, e.g., `5.0 l/min` instead of `5 l/min`.

## Conditions

```
IF 'AI01' ≥ '0.0 mbar'
IF 'AI02' ≤ '10.0 bar'
IF 'Timer' ≤ '60.0 s'
```

Conditional blocks must be closed with `ENDIF`:

```oql
IF 'AI01' ≥ '0.0 mbar'
  SAVE 'AI01.value'
ENDIF
```

Units in conditions follow the underlying measurement source. For the current
piADC-based valve diagnostics, raw sensor values are validated as voltages (`V`)
instead of translated pressure units.

## Min/Max/Val

```
MIN 'sensor' 'value unit'
MAX 'sensor' 'value unit'
VAL 'label' 'unit'
```

## Supported Hardware

- Valves: valve-1 through valve-14, valve-nc, valve-sc, valve-wc
  - Values: `1 (open)` or `0 (closed)`
- Pump: pompa 1, pump-main
  - Values: flow rate in l/min (e.g., `5.0 l/min`), `0 l/min`
- Sensors: AI01 (NC), AI02 (SC), AI03 (WC)
  - Units: V for raw ADC voltage, mbar/bar for pressure
