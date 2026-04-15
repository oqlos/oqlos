# OQL/CQL Language Specification v2.0 (Flat DSL)

## 1. Overview
OQL (Operation Query Language) and its variant CQL are declarative domain-specific languages designed for hardware testing, medical device diagnostics (e.g., Dräger BA sets), and process automation.

Version 2.0 introduces the **Flat Syntax**, which eliminates rigid block requirements and introduces intelligent hardware dispatch.

### 1.1 Core Principles
- **Case-Insensitivity**: All keywords (`SCENARIO`, `GOAL`, `IF`, `SET`, `VAL`) are case-insensitive.
- **Flat Structure**: Direct action commands can be placed under `GOAL` without prefixed arrows (`→`) or numbered steps.
- **Explicit Scoping**: All multi-line `IF` blocks **MUST** be closed with an `ENDIF` statement.
- **Intelligent Dispatch**: The `SET` command automatically detects if the target is a hardware peripheral (HAL) or a local variable.

---

## 2. Document Structure

### 2.1 Metadata Header
Every script starts with a metadata block to identify the test context.
```oql
SCENARIO: 'Full Mask Test'
DEVICE_TYPE: 'BA'
DEVICE_MODEL: 'PSS 7000'
MANUFACTURER: 'Dräger'
```

### 2.2 Global Configuration (Optional)
Used for calibrating constants and tuning the interpreter.
```oql
CONFIG: Calibration
  PUMP_FLOW_FULL_SCALE_LPM = 10.0
```

---

## 3. Goals and Logic

### 3.1 Goals
A scenario consists of one or more `GOAL` blocks.
```oql
GOAL: Static Pressure Test
  SET 'PUMP' '0 l/min'
  WAIT '5 s'
  VAL 'AI01' 'mbar'
```

### 3.2 Conditional Logic (IF / ELSE / ENDIF)
Conditionals gate the execution of subsequent actions. Multi-line blocks require an explicit `ENDIF`.
```oql
IF 'timer' > 'timeout'
  MIN 'pressure' '6.0 bar'
  MAX 'pressure' '8.0 bar'
  LOG "Threshold reached"
ENDIF
```

*Note: Nested conditionals are supported and encouraged for complex safety "gates".*

---

## 4. Fundamental Actions

| Command | Syntax | Description |
| :--- | :--- | :--- |
| **SET** | `SET 'target' 'value unit'` | Sets hardware state or variable. e.g., `SET 'valve-nc' '1'` |
| **VAL** | `VAL 'sensor' 'unit'` | Reads and validates a sensor value. |
| **SAVE** | `SAVE 'label'` | Persists the current measurement to the test protocol. |
| **WAIT** | `WAIT 'duration'` | Pauses execution (e.g., `500 ms`, `2.0 s`). |
| **MIN / MAX** | `MIN 'sensor' 'value unit'` | Sets threshold validation bounds. |
| **LOG** | `LOG "message"` | Records a diagnostic message in the execution log. |
| **ERROR** | `ERROR "message"` | Aborts execution with a critical failure message. |

---

## 5. Technical Commands (Production)

For advanced diagnostics and API integration:
- **`SAMPLE 'sensor' 'START/STOP' 'interval'`**: Background sensor sampling.
- **`FUNC 'var' = 'METHOD' 'args'`**: Calculations (e.g., `AVG`, `SUM`, `SUB`).
- **`API_GET/POST 'url'`**: Direct integration with the backend API.
- **`ASSERT_STATUS/JSON`**: Validation of API responses.
- **`EXPECT_DEVICE 'path'`**: Hardware discovery validation.
- **`GOTO 'Goal Name'`**: Control flow jump (use sparingly).

---

## 6. Standard Units and Aliases

### 6.1 Units
Value strings should follow the format: `value unit`.
Units are required for proper technical scaling.
- **Pressure**: `bar`, `mbar`
- **Flow**: `l/min`, `cfm`
- **Time**: `s`, `ms`, `min`
- **Voltage**: `V`, `mV`

### 6.2 Target Aliases (HAL)
- `valve-nc`, `valve-sc`, `valve-wc`: Safety valves.
- `pompa 1`, `pump-main`: Suction/pressure pumps.
- `AI01`, `AI02`, `AI03`: Pressure sensor channels.

---

## 7. Example: Production-Grade Script
```oql
GOAL: High Pressure Leak Test
  SET 'zawór butli' '1'
  WAIT '5.0 s'
  
  IF 'AI02' > '280 bar'
    LOG "Pressure stabilized"
    SET 'timer' '0 s'
    WAIT '60 s'
    MIN 'AI02' '270 bar'
    SAVE 'leak_test_result'
  ELSE
    ERROR "Insufficient cylinder pressure for test"
  ENDIF
```
