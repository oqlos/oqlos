# DSL Examples - Practical Guide

This document contains practical examples of the DSL Event Sourcing system with real output.

## Table of Contents

- [Quick Start](#quick-start)
- [Example 1: Navigation](#example-1-navigation)
- [Example 2: Device Identification](#example-2-device-identification)
- [Example 3: Complete Test Flow](#example-3-complete-test-flow)
- [Example 4: Session Recording](#example-4-session-recording)
- [Interactive Shell](#interactive-shell)
- [Event Statistics](#event-statistics)

---

## Quick Start

### Start the Server

```bash
cd dsl && make server
```

Output:
```
╔═══════════════════════════════════════════════════════════╗
║           🌐 DSL Event Server                               ║
║                                                             ║
║  WebSocket: ws://0.0.0.0:8104                              ║
║                                                             ║
║  Endpoints:                                                 ║
║    /events  - General events                                ║
║    /browser - Browser clients                               ║
║    /cli     - CLI clients                                   ║
╚═══════════════════════════════════════════════════════════╝
✅ Server running on ws://0.0.0.0:8104
```

### Run an Example

```bash
cd dsl && make run-script FILE=examples/quick-navigation.dsl
```

---

## Example 1: Navigation

**File:** `examples/quick-navigation.dsl`

```dsl
# Quick Navigation Example
# Demonstrates basic navigation between modules

# Start from home
NAVIGATE "/"
LOG "Starting navigation demo" {"level": "info"}

# Navigate through main modules
NAVIGATE "/connect-id"
WAIT 300
LOG "Arrived at Connect-ID module"

NAVIGATE "/connect-test"
WAIT 300
LOG "Arrived at Connect-Test module"

NAVIGATE "/connect-data"
WAIT 300
LOG "Arrived at Connect-Data module"

NAVIGATE "/connect-reports"
WAIT 300
LOG "Arrived at Connect-Reports module"

LOG "Navigation demo complete!" {"level": "info"}
```

### Output

```
🔌 Connected to browser: ws://localhost:8104/events
▶️ Executing: examples/quick-navigation.dsl
📍 NAVIGATE /
ℹ️ Starting navigation demo
📍 NAVIGATE /connect-id
⏳ WAIT 300ms
ℹ️ Arrived at Connect-ID module
📍 NAVIGATE /connect-test
⏳ WAIT 300ms
ℹ️ Arrived at Connect-Test module
📍 NAVIGATE /connect-data
⏳ WAIT 300ms
ℹ️ Arrived at Connect-Data module
📍 NAVIGATE /connect-reports
⏳ WAIT 300ms
ℹ️ Arrived at Connect-Reports module
ℹ️ Navigation demo complete!
✅ Completed: examples/quick-navigation.dsl
🔌 Disconnected from browser
```

### Events Generated

| Event Type | Payload |
|------------|---------|
| `navigation.navigated` | `{"route": "/"}` |
| `navigation.navigated` | `{"route": "/connect-id"}` |
| `navigation.navigated` | `{"route": "/connect-test"}` |
| `navigation.navigated` | `{"route": "/connect-data"}` |
| `navigation.navigated` | `{"route": "/connect-reports"}` |

---

## Example 2: Device Identification

**File:** `examples/device-identification.dsl`

```dsl
# Device Identification Example
# Demonstrates the device identification workflow

# Navigate to device RFID scanner
NAVIGATE "/connect-id/device-rfid"
LOG "Ready for device identification" {"level": "info"}

# Simulate RFID scan - device identified
SELECT_DEVICE "d-msa-001" {"type": "MSA_G1", "serial": "AO73138", "customer": "cu-acme-001"}

LOG "Device identified successfully" {"level": "info", "deviceId": "d-msa-001"}

# Show device details
EMIT "ui.device_details_shown" {"deviceId": "d-msa-001", "panel": "device-info"}

# Navigate to test selection
NAVIGATE "/connect-test/testing"
LOG "Ready for test selection" {"level": "info"}
```

### Output

```
🔌 Connected to browser: ws://localhost:8104/events
▶️ Executing: examples/device-identification.dsl
📍 NAVIGATE /connect-id/device-rfid
ℹ️ Ready for device identification
📱 SELECT_DEVICE d-msa-001
ℹ️ Device identified successfully
📣 EMIT ui.device_details_shown
📍 NAVIGATE /connect-test/testing
ℹ️ Ready for test selection
✅ Completed: examples/device-identification.dsl
🔌 Disconnected from browser
```

### Events Generated

| Event Type | Payload |
|------------|---------|
| `navigation.navigated` | `{"route": "/connect-id/device-rfid"}` |
| `test.device_selected` | `{"deviceId": "d-msa-001", "type": "MSA_G1", "serial": "AO73138"}` |
| `ui.device_details_shown` | `{"deviceId": "d-msa-001", "panel": "device-info"}` |
| `navigation.navigated` | `{"route": "/connect-test/testing"}` |

---

## Example 3: Complete Test Flow

**File:** `examples/test-device-flow.dsl`

```dsl
# DSL Example: Complete Device Test Flow
# 
# This script demonstrates a full device testing workflow
# that can be executed from CLI and visualized in browser.

# Start session recording
RECORD_START "operator1"

# Navigate to device identification
NAVIGATE "/connect-id/device-rfid"
LOG "Waiting for RFID scan..." {"level": "info"}

# Simulate device selection
SELECT_DEVICE "d-001" {"type": "MSA_G1", "serial": "AO73138", "customer": "cu-001"}

# Navigate to test setup
NAVIGATE "/connect-test/testing"

# Open interval dialog
EMIT "test.interval_dialog_opened" {"deviceId": "d-001"}

# Select test interval
SELECT_INTERVAL "3m" {"code": "periodic_3m", "description": "3 miesiące"}

# Start the test
START_TEST "ts-c20" {"name": "C20 Standard", "steps": 5}

# Protocol created
PROTOCOL_CREATED "pro-example-001" {"via": "cqrs", "deviceId": "d-001"}

# Navigate to protocol execution
NAVIGATE "/connect-test-protocol?protocol=pro-example-001&step=1"

# Execute test steps
STEP_COMPLETE "step-1" {"name": "Sprawdzenie ciśnienia", "status": "passed", "value": "15.2 mbar"}
WAIT 500

STEP_COMPLETE "step-2" {"name": "Test szczelności", "status": "passed", "value": "OK"}
WAIT 500

STEP_COMPLETE "step-3" {"name": "Kontrola wizualna", "status": "passed", "note": "Brak uszkodzeń"}
WAIT 500

STEP_COMPLETE "step-4" {"name": "Test funkcjonalny", "status": "passed"}
WAIT 500

STEP_COMPLETE "step-5" {"name": "Weryfikacja końcowa", "status": "passed"}

# Finalize protocol
PROTOCOL_FINALIZE "pro-example-001" {"status": "executed", "summary": {"passed": 5, "failed": 0}}

# Navigate to report
NAVIGATE "/connect-test/reports?protocol=pro-example-001"

LOG "Test completed successfully!" {"level": "info"}

# Stop recording
RECORD_STOP
```

### Output

```
🔌 Connected to browser: ws://localhost:8104/events
▶️ Executing: examples/test-device-flow.dsl
🔴 RECORD_START session=evt-19aea21541c-c10c
📍 NAVIGATE /connect-id/device-rfid
ℹ️ Waiting for RFID scan...
📱 SELECT_DEVICE d-001
📍 NAVIGATE /connect-test/testing
📣 EMIT test.interval_dialog_opened
⏱️ SELECT_INTERVAL 3m
🧪 START_TEST ts-c20
📋 PROTOCOL_CREATED pro-example-001
📍 NAVIGATE /connect-test-protocol?protocol=pro-example-001&step=1
✅ STEP_COMPLETE step-1 [passed]
⏳ WAIT 500ms
✅ STEP_COMPLETE step-2 [passed]
⏳ WAIT 500ms
✅ STEP_COMPLETE step-3 [passed]
⏳ WAIT 500ms
✅ STEP_COMPLETE step-4 [passed]
⏳ WAIT 500ms
✅ STEP_COMPLETE step-5 [passed]
✔️ PROTOCOL_FINALIZE pro-example-001
📍 NAVIGATE /connect-test/reports?protocol=pro-example-001
ℹ️ Test completed successfully!
⏹️ RECORD_STOP (16 events)
ℹ️ Session recorded. Replay with: REPLAY session-id
✅ Completed: examples/test-device-flow.dsl
🔌 Disconnected from browser
```

### Events Generated (16 total)

| # | Event Type | Key Payload |
|---|------------|-------------|
| 1 | `session.started` | `{"sessionId": "evt-..."}` |
| 2 | `navigation.navigated` | `{"route": "/connect-id/device-rfid"}` |
| 3 | `test.device_selected` | `{"deviceId": "d-001", "type": "MSA_G1"}` |
| 4 | `navigation.navigated` | `{"route": "/connect-test/testing"}` |
| 5 | `test.interval_dialog_opened` | `{"deviceId": "d-001"}` |
| 6 | `test.interval_selected` | `{"intervalCode": "3m"}` |
| 7 | `test.started` | `{"scenarioId": "ts-c20", "name": "C20 Standard"}` |
| 8 | `protocol.created` | `{"protocolId": "pro-example-001"}` |
| 9 | `navigation.navigated` | `{"route": "/connect-test-protocol?..."}` |
| 10-14 | `test.step_executed` | `{"stepId": "step-N", "status": "passed"}` |
| 15 | `protocol.finalized` | `{"protocolId": "pro-example-001", "status": "executed"}` |
| 16 | `navigation.navigated` | `{"route": "/connect-test/reports?..."}` |

---

## Example 4: Session Recording

**File:** `examples/session-recording.dsl`

```dsl
# Session Recording Example
# Demonstrates how to record and replay user sessions

# Start recording session
RECORD_START "demo-session-001"
LOG "Session recording started" {"level": "info"}

# Perform some actions
NAVIGATE "/connect-id/device-rfid"
SELECT_DEVICE "d-demo-001" {"type": "PSS-7000", "serial": "PS12345"}

NAVIGATE "/connect-test/testing"
SELECT_INTERVAL "3m" {"code": "periodic_3m", "description": "3 miesiące"}

START_TEST "ts-demo" {"name": "Demo Test", "steps": 3}

STEP_COMPLETE "step-1" {"name": "Initialization", "status": "passed"}
WAIT 200
STEP_COMPLETE "step-2" {"name": "Pressure Check", "status": "passed", "value": "15.2 mbar"}
WAIT 200
STEP_COMPLETE "step-3" {"name": "Finalization", "status": "passed"}

# Stop recording
RECORD_STOP
LOG "Session recording stopped - events captured" {"level": "info"}

# The session can now be replayed with:
# REPLAY "session-id" {"variables": {"device_id": "d-other-device"}}
```

### Output

```
🔌 Connected to browser: ws://localhost:8104/events
▶️ Executing: examples/session-recording.dsl
🔴 RECORD_START session=evt-19aea2f3901-8250
ℹ️ Session recording started
📍 NAVIGATE /connect-id/device-rfid
📱 SELECT_DEVICE d-demo-001
📍 NAVIGATE /connect-test/testing
⏱️ SELECT_INTERVAL 3m
🧪 START_TEST ts-demo
✅ STEP_COMPLETE step-1 [passed]
⏳ WAIT 200ms
✅ STEP_COMPLETE step-2 [passed]
⏳ WAIT 200ms
✅ STEP_COMPLETE step-3 [passed]
⏹️ RECORD_STOP (9 events)
ℹ️ Session recording stopped - events captured
✅ Completed: examples/session-recording.dsl
🔌 Disconnected from browser
```

---

## Interactive Shell

Start the shell for interactive commands:

```bash
cd dsl && make shell
```

### Example Session

```
🐚 DSL Shell v2.0 - Event Sourcing Edition
🔌 Connected to browser: ws://localhost:8104/events
Type 'help' for commands, 'exit' to quit.

dsl> NAVIGATE "/connect-test"
📍 NAVIGATE /connect-test

dsl> SELECT_DEVICE "d-001" {"type": "MSA_G1"}
📱 SELECT_DEVICE d-001

dsl> START_TEST "ts-c20" {"name": "C20"}
🧪 START_TEST ts-c20

dsl> STEP_COMPLETE "step-1" {"status": "passed"}
✅ STEP_COMPLETE step-1 [passed]

dsl> help
Available commands:
  NAVIGATE "/route"           - Navigate to route
  SELECT_DEVICE "id" {...}    - Select device
  SELECT_INTERVAL "code" {...} - Select interval
  START_TEST "id" {...}       - Start test
  STEP_COMPLETE "id" {...}    - Complete step
  EMIT "type" {...}           - Emit custom event
  LOG "message" {...}         - Log message
  WAIT ms                     - Wait milliseconds
  RECORD_START "name"         - Start recording
  RECORD_STOP                 - Stop recording
  SET var "value"             - Set variable
  GET var                     - Get variable
  exit                        - Exit shell

dsl> exit
🔌 Disconnected from browser
👋 Goodbye!
```

---

## Event Statistics

After running all examples, the event store contains:

```
📊 Total events in store: 50

Event types summary:
  • navigation.navigated: 18
  • protocol.created: 1
  • protocol.finalized: 2
  • session.ended: 3
  • session.started: 2
  • test.device_selected: 4
  • test.interval_dialog_opened: 1
  • test.interval_selected: 2
  • test.started: 2
  • test.step_executed: 13
  • ui.device_details_shown: 2
```

### Viewing Events

To check event store statistics:

```bash
cd dsl && python3 -c "
import asyncio, websockets, json
async def check():
    async with websockets.connect('ws://localhost:8104/cli') as ws:
        await ws.send('{\"type\": \"stats\"}')
        while True:
            resp = await asyncio.wait_for(ws.recv(), timeout=1)
            data = json.loads(resp)
            if data.get('type') == 'stats':
                print(f'Events: {data.get(\"events_count\", 0)}')
                print(f'Clients: {data.get(\"connected_clients\", 0)}')
                break
asyncio.run(check())
"
```

---

---

## Example 5: Generate Test Reports

**File:** `examples/generate-test-reports.dsl`

This script generates complete test workflows that emit events for the Reports module.

```dsl
# Generate Test Reports Scenario
LOG "Starting test report generation..." {"level": "info"}
RECORD_START "report-generation"

# Test 1: MSA Device - Pressure Test
NAVIGATE "/connect-id/device-rfid"
SELECT_DEVICE "d-msa-7000" {"type": "MSA_G1", "serial": "AO73138"}
NAVIGATE "/connect-test/testing"
SELECT_INTERVAL "3m" {"code": "periodic_3m"}
START_TEST "ts-pressure" {"name": "Test ciśnienia MSA", "steps": 3}
PROTOCOL_CREATED "pro-msa-001" {"device_id": "d-msa-7000", "status": "IN_PROGRESS"}
STEP_COMPLETE "step-1" {"name": "Inicjalizacja", "status": "passed"}
STEP_COMPLETE "step-2" {"name": "Test ciśnienia 15 mbar", "status": "passed", "value": "15.2 mbar"}
STEP_COMPLETE "step-3" {"name": "Weryfikacja", "status": "passed"}
PROTOCOL_FINALIZE "pro-msa-001" {"status": "COMPLETED"}

# Navigate to Reports
NAVIGATE "/connect-reports"
EMIT "reports.refresh_requested" {"view": "week"}
RECORD_STOP
```

### Output

```
ℹ️ Starting test report generation...
🔴 RECORD_START session=evt-19aea33188d-6c99
📍 NAVIGATE /connect-id/device-rfid
📱 SELECT_DEVICE d-msa-7000
📍 NAVIGATE /connect-test/testing
🧪 START_TEST ts-pressure
📋 PROTOCOL_CREATED pro-msa-001
✅ STEP_COMPLETE step-1 [passed]
✅ STEP_COMPLETE step-2 [passed]
✅ STEP_COMPLETE step-3 [passed]
✔️ PROTOCOL_FINALIZE pro-msa-001
📍 NAVIGATE /connect-reports
📣 EMIT reports.refresh_requested
⏹️ RECORD_STOP (36 events)
```

---

## Example 6: API Integration

The DSL shell supports direct API calls to create actual database records:

```dsl
# Create protocol via API
API POST "/api/v3/data/protocols" {"name": "Test DSL", "device_id": "d-001", "status": "COMPLETED", "test_date": "2025-12-04T10:00:00"}

# Get protocols
API GET "/api/v3/data/protocols?limit=5"
```

### Creating Protocols with Today's Date

```bash
# Create protocols for current week view
curl -X POST "http://localhost:8101/api/v3/data/protocols" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test DSL", "device_id": "d-dsl-001", "status": "COMPLETED", "test_date": "2025-12-04T10:00:00"}'
```

---

## Summary

| Example | File | Events | Purpose |
|---------|------|--------|---------|
| Navigation | `quick-navigation.dsl` | 5 | Basic module navigation |
| Device ID | `device-identification.dsl` | 4 | Device identification flow |
| Test Flow | `test-device-flow.dsl` | 16 | Complete test workflow |
| Recording | `session-recording.dsl` | 9 | Session recording demo |
| Reports | `generate-test-reports.dsl` | 36 | Generate test reports |
| Today's | `create-todays-reports.dsl` | 12 | Reports for current week |

All examples are in `dsl/examples/` and can be run with:

```bash
cd dsl && make run-script FILE=examples/<name>.dsl
```

### Viewing Reports

After running examples, open **http://localhost:8100/connect-reports** to see the data.

> **Note:** The Reports module loads data from the API (`/api/v3/data/protocols`). 
> DSL events provide real-time synchronization but actual data must exist in the database.
