# OQL v3 Hardware Testing Examples (Flat Syntax)

Practical examples of the v3 flat OQL used for medical device
diagnostics.  Identifiers are bare; range assertions replace `IF/ENDIF`.

## Operator Preflight

Before running these examples in `execute` mode, verify that the runtime can see
the same hardware as the host:

```bash
oqlctl doctor
oqlctl detect
```

If `doctor` reports a `modbus_config_mismatch`, use:

```bash
oqlctl doctor --fix
```

This only updates detected Modbus connection parameters in `oqlos.yaml` and
creates a backup first.

## Example: Static Pressure Test

```oql
SCENARIO: Static Pressure Check
DEVICE_TYPE: BA

CONFIG initialization:
  SET pump-main 0
  SET valve-nc 0
  SET WAIT '500 ms'
GOAL pressure-measurement:
  SET valve-nc 1
  SET WAIT '2 s'
  GET AI01
  CHECK 6.0 <= AI01 <= 8.0 bar
  SAVE static-pressure
```

## Example: Continuous Sampling

```oql
GOAL dynamic-flow-test:
  SAMPLE AI01 START 100ms
  SET pump-main 10.0 l/min
  SET WAIT '5 s'
  SAMPLE AI01 STOP
  GET AI01
  SAVE flow-reading
  MIN AI01 5.0 mbar
```

## Example: Macro Library Usage

```oql
INCLUDE "lib/hardware.oql"
INCLUDE "lib/peripherals.oql"

CONFIG reset:
  CALL init-all

GOAL smoke:
  CALL hw-pump-smoke
  CALL hw-valves-smoke
  CALL hw-sensors-baseline
```

---

## Technical Reference

- Full language details: [OQL v3 Specification](oql-spec.md).
- Visual anatomy: [`docs/oql-grammar-anatomy.html`](oql-grammar-anatomy.html).
- Quick reference: `oql-scenario/OQL-CHEATSHEET.md`.
