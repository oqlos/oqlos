# Hardware Testing Examples (OQL/CQL)

This section provides practical examples of the hardware testing DSL used for medical device diagnostics.

## Example: Static Pressure Test
Demonstrates standard initialization and sensor validation.

```oql
SCENARIO: 'Static Pressure Check'
DEVICE_TYPE: 'BA'

GOAL: Initialization
  SET 'PUMP' '0 l/min'
  SET 'valve-nc' '0'
  WAIT '500 ms'

GOAL: Pressure Measurement
  SET 'valve-nc' '1'
  WAIT '2.0 s'
  
  IF 'AI01' > '6.0 bar'
    LOG "Pressure OK"
    SAVE 'static_pressure'
  ELSE
    ERROR "Insufficient pressure"
  ENDIF
```

## Example: Continuous Sampling
Using the `SAMPLE` command for background telemetry.

```oql
GOAL: Dynamic Flow Test
  SAMPLE 'AI01' 'START' '100 ms'
  SET 'PUMP' '10.0 l/min'
  WAIT '5.0 s'
  
  VAL 'AI01' 'mbar'
  SAMPLE 'AI01' 'STOP'
  
  IF 'AI01' < '5.0 mbar'
    ERROR "Flow resistance too high"
  ENDIF
```

---

## Technical Reference
For full language details, see [OQL Language Specification v2.0](oql-spec.md).