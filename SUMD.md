# OqlOS — Operation Query Language Runtime

OqlOS — Operation Query Language runtime for hardware testing

## Contents

- [Metadata](#metadata)
- [Architecture](#architecture)
- [Interfaces](#interfaces)
- [Workflows](#workflows)
- [Quality Pipeline (`pyqual.yaml`)](#quality-pipeline-pyqualyaml)
- [Configuration](#configuration)
- [Dependencies](#dependencies)
- [Deployment](#deployment)
- [Environment Variables (`.env.example`)](#environment-variables-envexample)
- [Release Management (`goal.yaml`)](#release-management-goalyaml)
- [Makefile Targets](#makefile-targets)
- [Code Analysis](#code-analysis)
- [Source Map](#source-map)
- [Call Graph](#call-graph)
- [API Stubs](#api-stubs)
- [Test Contracts](#test-contracts)
- [Intent](#intent)

## Metadata

- **name**: `oqlos`
- **version**: `0.1.28`
- **python_requires**: `>=3.10`
- **license**: {'text': 'Apache-2.0'}
- **ai_model**: `openrouter/qwen/qwen3-coder-next`
- **ecosystem**: SUMD + DOQL + testql + taskfile
- **openapi_title**: oqlos API v1.0.0
- **generated_from**: pyproject.toml, Taskfile.yml, Makefile, testql(6), openapi(49 ep), app.doql.less, pyqual.yaml, goal.yaml, .env.example, Dockerfile, docker-compose.dev.yml, src(1 mod), project/(3 analysis files)

## Architecture

```
SUMD (description) → DOQL/source (code) → taskfile (automation) → testql (verification)
```

### DOQL Application Declaration (`app.doql.less`)

```less markpact:doql path=app.doql.less
// LESS format — define @variables here as needed

app {
  name: oqlos;
  version: 0.1.28;
}

dependencies {
  runtime: "fastapi>=0.110, uvicorn>=0.28, pydantic>=2.0, pydantic-settings>=2.2.0, pyserial>=3.5, pymodbus>=3.6, httpx>=0.25, nfo>=0.2.3, goal>=2.1.0, costs>=0.1.20, pfix>=0.1.60, paho-mqtt>=1.6.1, pluggy>=1.4, pytest-asyncio>=0.23, PyYAML>=6.0, testql>=0.2.0";
  rpi: "RPi.GPIO>=0.7, smbus2>=0.4";
  server: websockets>=13.0;
  dev: "pytest, pytest-asyncio, httpx, websockets>=13.0, goal>=2.1.0, costs>=0.1.20, pfix>=0.1.60, paho-mqtt>=1.6.1";
  hardware-services: "dri0050>=1.0.0, piADC>=1.0.0, piRTC>=1.0.0";
}

entity[name="ExecutionStatus"] {
  executionId: string!;
  scenarioId: string!;
  status: string!;
  currentGoal: str | None;
  currentStep: str | None;
  progress: float!;
}

entity[name="CommandEnvelope"] {
  command: string!;
  data: dict[str, Any] | None;
}

entity[name="Step"] {
  id: string!;
  action: string!;
  label: str | None;
  peripheral: str | None;
  value: json!;
  duration: int | None;
  condition: str | None;
}

entity[name="ValidationRule"] {
  peripheral: string!;
  condition: string!;
  errorMessage: string!;
}

entity[name="Goal"] {
  id: string!;
  name: string!;
  description: string!;
  steps: list[Step]!;
  expectedResult: string!;
  validationCriteria: list[ValidationRule]!;
}

entity[name="Scenario"] {
  id: string!;
  name: string!;
  description: string!;
  device: string!;
  protocol: string!;
  code: str | None;
  slug: str | None;
  goals: list[Goal]!;
}

entity[name="Peripheral"] {
  id: string!;
  type: PeripheralType!;
  name: string!;
  currentValue: json!;
  targetValue: json!;
  unit: str | None;
  range: dict[str, float] | None;
  status: PeripheralStatus!;
  mode: PeripheralMode!;
  dependencies: list[str]!;
}

interface[type="api"] {
  type: rest;
  framework: fastapi;
}

interface[type="cli"] {
  framework: argparse;
}
interface[type="cli"] page[name="oqlctl"] {
  entry: oqlos.tools.cql_cli:main;
}
interface[type="cli"] page[name="oqlos-modbus-probe"] {
  entry: oqlos.tools.hardware_diagnose.modbus_probe:main;
}

integration[name="modbus"] {
  type: hardware;
}

workflow[name="test"] {
  trigger: manual;
  step-1: run cmd=$(PYTHON) -m pytest -q;
}

workflow[name="test-hw"] {
  trigger: manual;
  step-1: run cmd=scripts/test-hardware.sh $(PI);
}

workflow[name="smoke"] {
  trigger: manual;
  step-1: run cmd=awk '/```bash markpact:ref assert-hw-node-healthy/{f=1;next} f&&/^```/{f=0} f' \;
  step-2: run cmd=redeploy/$(NODE)/migration.md > /tmp/oqlos-smoke.sh;
  step-3: run cmd=scp -q /tmp/oqlos-smoke.sh $(PI):/tmp/oqlos-smoke.sh;
  step-4: run cmd=ssh $(PI) 'export XDG_RUNTIME_DIR=/run/user/$$(id -u); bash /tmp/oqlos-smoke.sh';
}

workflow[name="checksums"] {
  trigger: manual;
  step-1: run cmd=scripts/gen-checksums.sh;
}

workflow[name="verify-rpi"] {
  trigger: manual;
  step-1: run cmd=scripts/verify-rpi-checksum.sh $(PI);
}

workflow[name="sync-rpi"] {
  trigger: manual;
  step-1: run cmd=rsync -rz --itemize-changes \;
  step-2: run cmd=--exclude='__pycache__/' --exclude='*.pyc' --exclude='*.pyo' \;
  step-3: run cmd=--exclude='.pytest_cache/' --exclude='*.log' \;
  step-4: run cmd=oqlos/ $(PI):/home/pi/oqlos/oqlos/oqlos/;
  step-5: run cmd=$(MAKE) verify-rpi PI=$(PI);
}

workflow[name="restart"] {
  trigger: manual;
  step-1: run cmd=ssh $(PI) 'export XDG_RUNTIME_DIR=/run/user/$$(id -u); \;
  step-2: run cmd=systemctl --user restart oqlos-hardware-api; \;
  step-3: run cmd=for i in $$(seq 1 20); do \;
  step-4: run cmd=curl -sf --max-time 4 http://127.0.0.1:8202/health && { echo "  <- /health OK"; exit 0; }; \;
  step-5: run cmd=sleep 1; \;
  step-6: run cmd=done; \;
  step-7: run cmd=echo "FAIL: agent nie podniosl /health w 20s" >&2; exit 1';
}

workflow[name="deploy"] {
  trigger: manual;
  step-1: run cmd=redeploy run redeploy/$(NODE)/migration.md;
}

workflow[name="redeploy"] {
  trigger: manual;
  step-1: run cmd=echo "Wdrożenie węzła sprzętowego:";
  step-2: run cmd=echo "  make 122                 # boardnet (192.168.188.122)";
  step-3: run cmd=echo "  make pi-hw               # pi-hw    (192.168.188.110)";
  step-4: run cmd=echo "  make deploy NODE=122     # dowolny węzeł z redeploy/<NODE>/migration.md";
}

workflow[name="pi-hw"] {
  trigger: manual;
  step-1: run cmd=$(MAKE) deploy NODE=pi-hw PI=pi@192.168.188.110;
}

workflow[name="serve"] {
  trigger: manual;
  step-1: run cmd=$(PYTHON) -m uvicorn oqlos.api.main:app --host 0.0.0.0 --port $(PORT);
}

workflow[name="panel-url"] {
  trigger: manual;
  step-1: run cmd=echo "http://localhost:$(PORT)/panel";
}

workflow[name="install"] {
  trigger: manual;
  step-1: run cmd=pip install -e .[dev];
}

workflow[name="deps:update"] {
  trigger: manual;
  step-1: run cmd=PIP="pip"
[ -f "{{.PWD}}/.venv/bin/pip" ] && PIP="{{.PWD}}/.venv/bin/pip"
$PIP install --upgrade pip
OUTDATED=$($PIP list --outdated --format=columns 2>/dev/null | tail -n +3 | awk '{print $1}')
if [ -z "$OUTDATED" ]; then
  echo "✅ All packages are up to date."
else
  echo "📦 Upgrading: $OUTDATED"
  echo "$OUTDATED" | xargs $PIP install --upgrade
  echo "✅ Done."
fi;
}

workflow[name="quality"] {
  trigger: manual;
  step-1: run cmd=pyqual run;
}

workflow[name="quality:fix"] {
  trigger: manual;
  step-1: run cmd=pyqual run --fix;
}

workflow[name="quality:report"] {
  trigger: manual;
  step-1: run cmd=pyqual report;
}

workflow[name="test:frontend"] {
  trigger: manual;
  step-1: run cmd=npm run test:unit;
}

workflow[name="lint"] {
  trigger: manual;
  step-1: run cmd=ruff check .;
}

workflow[name="fmt"] {
  trigger: manual;
  step-1: run cmd=ruff format .;
}

workflow[name="build"] {
  trigger: manual;
  step-1: run cmd=python -m build;
}

workflow[name="clean"] {
  trigger: manual;
  step-1: run cmd=rm -rf build/ dist/ *.egg-info;
}

workflow[name="hardware:check"] {
  trigger: manual;
  step-1: run cmd=oqlctl doctor || echo "Hardware doctor reported issues";
}

workflow[name="hardware:identify"] {
  trigger: manual;
  step-1: run cmd=oqlctl identify;
}

workflow[name="doql:adopt"] {
  trigger: manual;
  step-1: run cmd=if ! command -v {{.DOQL_CMD}} >/dev/null 2>&1; then
  echo "⚠️  doql not installed. Install: pip install doql"
  exit 1
fi;
  step-2: run cmd={{.DOQL_CMD}} adopt {{.PWD}} --output app.doql.css --force;
  step-3: run cmd={{.DOQL_CMD}} export --format less -o {{.DOQL_OUTPUT}};
  step-4: run cmd=echo "✅ Project structure captured in {{.DOQL_OUTPUT}}";
}

workflow[name="doql:validate"] {
  trigger: manual;
  step-1: run cmd=if [ ! -f "{{.DOQL_OUTPUT}}" ]; then
  echo "❌ {{.DOQL_OUTPUT}} not found. Run: task doql:adopt"
  exit 1
fi;
  step-2: run cmd={{.DOQL_CMD}} validate;
}

workflow[name="doql:doctor"] {
  trigger: manual;
  step-1: run cmd={{.DOQL_CMD}} doctor;
}

workflow[name="doql:build"] {
  trigger: manual;
  step-1: run cmd=if [ ! -f "{{.DOQL_OUTPUT}}" ]; then
  echo "❌ {{.DOQL_OUTPUT}} not found. Run: task doql:adopt"
  exit 1
fi;
  step-2: run cmd=# Regenerate LESS from CSS if CSS exists
if [ -f "app.doql.css" ]; then
  {{.DOQL_CMD}} export --format less -o {{.DOQL_OUTPUT}}
fi;
  step-3: run cmd={{.DOQL_CMD}} build app.doql.css --out build/;
}

workflow[name="help"] {
  trigger: manual;
  step-1: run cmd=task --list;
}

tests {
  import: ./**/*.testql.toon.yaml;
  import: testql-scenarios/**/*.testql.toon.yaml;
}

env_vars {
  keys: FIRMWARE_PORT, SERVICE_NAME, SERVICE_VERSION, HARDWARE_MODE, MODBUS_SERIAL_PORT, MODBUS_BAUD, MODBUS_PARITY, MODBUS_DEVICE_ID, MODBUS_ADC_SERIAL_PORT, MODBUS_ADC_BAUD, MODBUS_ADC_PARITY, MODBUS_ADC_DEVICE_ID, MODBUS_HOST, MODBUS_PORT, PIADC_URL, MOTOR_URL, LUNG_MOTOR_URL, LOG_LEVEL, CORS_ORIGINS, OQLOS_FIRMWARE_PORT, OQLOS_SERVICE_NAME, OQLOS_SERVICE_VERSION, OQLOS_HARDWARE_MODE, OQLOS_MODBUS_SERIAL_PORT, OQLOS_MODBUS_BAUD, OQLOS_MODBUS_PARITY, OQLOS_MODBUS_DEVICE_ID, OQLOS_MODBUS_HOST, OQLOS_MODBUS_PORT, OQLOS_PIADC_URL, OQLOS_MOTOR_URL, OQLOS_LUNG_MOTOR_URL, OQLOS_PUMP_FLOW_FULL_SCALE_LPM, OQLOS_LOG_LEVEL, OQLOS_CORS_ORIGINS;
}

deploy {
  target: docker-compose;
  compose_file: docker/docker-compose.dev.yml;
}

environment[name="local"] {
  runtime: docker-compose;
  env_file: .env;
  template_file: .env.example;
  python_version: >=3.10;
  vars: CORS_ORIGINS, FIRMWARE_PORT, HARDWARE_MODE, LOG_LEVEL, LUNG_MOTOR_URL, MODBUS_ADC_BAUD, MODBUS_ADC_DEVICE_ID, MODBUS_ADC_PARITY, MODBUS_ADC_SERIAL_PORT, MODBUS_BAUD, MODBUS_DEVICE_ID, MODBUS_HOST, MODBUS_PARITY, MODBUS_PORT, MODBUS_SERIAL_PORT, MOTOR_URL, OQLOS_CORS_ORIGINS, OQLOS_FIRMWARE_PORT, OQLOS_HARDWARE_MODE, OQLOS_LOG_LEVEL, OQLOS_LUNG_MOTOR_URL, OQLOS_MODBUS_BAUD, OQLOS_MODBUS_DEVICE_ID, OQLOS_MODBUS_HOST, OQLOS_MODBUS_PARITY, OQLOS_MODBUS_PORT, OQLOS_MODBUS_SERIAL_PORT, OQLOS_MOTOR_URL, OQLOS_PIADC_URL, OQLOS_PUMP_FLOW_FULL_SCALE_LPM, OQLOS_SERVICE_NAME, OQLOS_SERVICE_VERSION, PIADC_URL, SERVICE_NAME, SERVICE_VERSION;
}

environment[name="dev"] {
  runtime: docker-compose;
}

environment[name="prod"] {
  runtime: docker-compose;
}
```

### Source Modules

- `oqlos.config`

## Interfaces

### CLI Entry Points

- `oqlos-server`
- `oqlctl`
- `oqlos-events`
- `oqlos-modbus-probe`

### REST API (from `openapi.yaml`)

```yaml markpact:openapi path=openapi.yaml
components:
  schemas:
    Error:
      properties:
        code:
          type: integer
        error:
          type: string
        message:
          type: string
      type: object
    HealthCheck:
      properties:
        status:
          enum:
          - ok
          - error
          type: string
        timestamp:
          format: date-time
          type: string
        version:
          type: string
      type: object
info:
  description: Auto-generated OpenAPI spec for oqlos
  title: oqlos API
  version: 1.0.0
openapi: 3.0.3
paths:
  /:
    get:
      operationId: index_page
      responses:
        '200': &id001
          content:
            application/json:
              schema:
                type: object
          description: Success
        '401': &id002
          description: Unauthorized
        '404': &id003
          description: Not Found
        '500': &id004
          description: Internal Server Error
      summary: Serve the firmware UI (index.html) at root
      tags:
      - fastapi
  /api/status:
    get:
      operationId: status
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: GET /api/status
      tags:
      - fastapi
      - status
  /api/v1/commands:
    post:
      operationId: post_commands
      requestBody:
        content:
          application/json:
            schema:
              properties:
                description:
                  type: string
                name:
                  type: string
              type: object
        required: true
      responses:
        '201': &id005
          content:
            application/json:
              schema:
                type: object
          description: Created
        '400': &id006
          content:
            application/json:
              schema:
                properties:
                  detail:
                    type: string
                  error:
                    type: string
                type: object
          description: Bad Request
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Command bus endpoint used by frontend.
      tags:
      - v1
      - fastapi
  /api/v1/editor/execute:
    post:
      operationId: execute_scenario
      requestBody:
        content:
          application/json:
            schema:
              type: object
        required: true
      responses:
        '201': *id005
        '400': *id006
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Execute a scenario file using oqlos runtime.
      tags:
      - v1
      - fastapi
  /api/v1/editor/file/{file_path:path}:
    get:
      operationId: read_file_endpoint
      parameters:
      - in: path
        name: file_path:path
        required: true
        schema:
          type: string
      - in: query
        name: file_path
        required: false
        schema:
          type: str
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Read a file's content.
      tags:
      - v1
      - fastapi
    post:
      operationId: write_file_endpoint
      parameters:
      - in: path
        name: file_path:path
        required: true
        schema:
          type: string
      - in: query
        name: file_path
        required: false
        schema:
          type: str
      requestBody:
        content:
          application/json:
            schema:
              type: object
        required: true
      responses:
        '201': *id005
        '400': *id006
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Write content to a file (creates parent directories as needed).
      tags:
      - v1
      - fastapi
  /api/v1/editor/files:
    get:
      operationId: list_files
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: List all entries in the scenarios directory.
      tags:
      - v1
      - fastapi
  /api/v1/execution/by-id/{execution_id}:
    get:
      operationId: get_execution
      parameters:
      - in: path
        name: execution_id
        required: true
        schema:
          type: string
      - in: query
        name: execution_id
        required: false
        schema:
          type: str
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Get execution status
      tags:
      - v1
      - fastapi
  /api/v1/execution/logs:
    get:
      operationId: get_execution_logs
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Return execution logs for frontend polling.
      tags:
      - v1
      - fastapi
  /api/v1/execution/logs/stream:
    get:
      operationId: execution_logs_stream
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Stream execution logs for terminal view
      tags:
      - v1
      - fastapi
  /api/v1/execution/projection:
    get:
      operationId: get_execution_projection
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Return a lightweight execution projection used by the frontend polling
        fallback.
      tags:
      - v1
      - fastapi
  /api/v1/execution/start:
    post:
      operationId: start_execution
      requestBody:
        content:
          application/json:
            schema:
              type: object
        required: true
      responses:
        '201': *id005
        '400': *id006
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Start scenario execution
      tags:
      - v1
      - fastapi
  /api/v1/execution/status:
    get:
      operationId: get_execution_status
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Return textual logs and status for polling fallback when SSE is unavailable.
      tags:
      - v1
      - fastapi
  /api/v1/execution/step:
    post:
      operationId: execute_step
      requestBody:
        content:
          application/json:
            schema:
              type: object
        required: true
      responses:
        '201': *id005
        '400': *id006
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Execute a single DSL step within the current (or new) execution.
      tags:
      - v1
      - fastapi
  /api/v1/execution/stream:
    get:
      operationId: execution_stream
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Stream execution events for frontend polling fallback
      tags:
      - v1
      - fastapi
  /api/v1/hardware/health:
    get:
      operationId: hardware_health
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Return connectivity status for all hardware services.
      tags:
      - v1
      - fastapi
  /api/v1/hardware/identify:
    get:
      operationId: hardware_identify
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: 'Return full hardware identification: registry + live probe results.'
      tags:
      - v1
      - fastapi
  /api/v1/hardware/lung:
    post:
      operationId: set_lung
      parameters:
      - in: query
        name: steps
        required: false
        schema:
          type: int
      - in: query
        name: speed
        required: false
        schema:
          type: int
      - in: query
        name: cycles
        required: false
        schema:
          type: int
      - in: query
        name: pause
        required: false
        schema:
          type: float
      requestBody:
        content:
          application/json:
            schema:
              type: object
        required: true
      responses:
        '201': *id005
        '400': *id006
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Start artificial lung reciprocating motion (tic249 stepper).
      tags:
      - v1
      - fastapi
  /api/v1/hardware/lung/stop:
    post:
      operationId: stop_lung
      requestBody:
        content:
          application/json:
            schema:
              type: object
        required: true
      responses:
        '201': *id005
        '400': *id006
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Emergency stop the artificial lung motor.
      tags:
      - v1
      - fastapi
  /api/v1/hardware/pump:
    post:
      operationId: set_pump
      parameters:
      - in: query
        name: power_pct
        required: false
        schema:
          type: float
      requestBody:
        content:
          application/json:
            schema:
              type: object
        required: true
      responses:
        '201': *id005
        '400': *id006
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Directly set pump power % (for manual testing).
      tags:
      - v1
      - fastapi
  /api/v1/hardware/sensor/{sensor_id}:
    get:
      operationId: read_sensor
      parameters:
      - in: path
        name: sensor_id
        required: true
        schema:
          type: string
      - in: query
        name: sensor_id
        required: false
        schema:
          type: str
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Read a sensor value directly from hardware.
      tags:
      - v1
      - fastapi
  /api/v1/hardware/valve/{valve_id}:
    post:
      operationId: set_valve
      parameters:
      - in: path
        name: valve_id
        required: true
        schema:
          type: string
      - in: query
        name: valve_id
        required: false
        schema:
          type: str
      - in: query
        name: value
        required: false
        schema:
          type: bool
      requestBody:
        content:
          application/json:
            schema:
              type: object
        required: true
      responses:
        '201': *id005
        '400': *id006
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Directly set a valve (for manual testing).
      tags:
      - v1
      - fastapi
  /api/v1/health:
    get:
      operationId: health_check
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Health check endpoint for tests and frontend compatibility probes.
      tags:
      - v1
      - fastapi
  /api/v1/logs/stats:
    get:
      operationId: get_log_stats
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Summary statistics from logs database.
      tags:
      - v1
      - fastapi
  /api/v1/peripherals/reset:
    post:
      operationId: reset_peripherals
      requestBody:
        content:
          application/json:
            schema:
              type: object
        required: true
      responses:
        '201': *id005
        '400': *id006
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Reset all peripherals
      tags:
      - v1
      - fastapi
  /api/v1/peripherals/{peripheral_id}:
    get:
      operationId: get_peripheral
      parameters:
      - in: path
        name: peripheral_id
        required: true
        schema:
          type: string
      - in: query
        name: peripheral_id
        required: false
        schema:
          type: str
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Get specific peripheral
      tags:
      - v1
      - fastapi
    put:
      operationId: update_peripheral
      parameters:
      - in: path
        name: peripheral_id
        required: true
        schema:
          type: string
      - in: query
        name: peripheral_id
        required: false
        schema:
          type: str
      requestBody:
        content:
          application/json:
            schema:
              properties:
                data:
                  type: object
                id:
                  type: string
                name:
                  type: string
              type: object
        required: true
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Update peripheral via PUT (for tests)
      tags:
      - v1
      - fastapi
  /api/v1/peripherals/{peripheral_id}/set:
    post:
      operationId: set_peripheral
      parameters:
      - in: path
        name: peripheral_id
        required: true
        schema:
          type: string
      - in: query
        name: peripheral_id
        required: false
        schema:
          type: str
      - in: query
        name: mode
        required: false
        schema:
          type: str
      requestBody:
        content:
          application/json:
            schema:
              type: object
        required: true
      responses:
        '201': *id005
        '400': *id006
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Update peripheral (manual mode)
      tags:
      - v1
      - fastapi
  /api/v1/plugins/:
    get:
      operationId: list_plugins
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: List all registered hardware plugins.
      tags:
      - v1
      - fastapi
  /api/v1/plugins/status:
    get:
      operationId: get_plugin_status
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Get overall status of all plugins.
      tags:
      - v1
      - fastapi
  /api/v1/plugins/validate:
    post:
      operationId: validate_plugin_configs
      requestBody:
        content:
          application/json:
            schema:
              type: object
        required: true
      responses:
        '201': *id005
        '400': *id006
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Validate configurations for multiple plugins.
      tags:
      - v1
      - fastapi
  /api/v1/plugins/{plugin_id}:
    get:
      operationId: get_plugin_info
      parameters:
      - in: path
        name: plugin_id
        required: true
        schema:
          type: string
      - in: query
        name: plugin_id
        required: false
        schema:
          type: str
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Get information about a specific plugin.
      tags:
      - v1
      - fastapi
  /api/v1/plugins/{plugin_id}/connect:
    post:
      operationId: connect_plugin
      parameters:
      - in: path
        name: plugin_id
        required: true
        schema:
          type: string
      - in: query
        name: plugin_id
        required: false
        schema:
          type: str
      requestBody:
        content:
          application/json:
            schema:
              type: object
        required: true
      responses:
        '201': *id005
        '400': *id006
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Connect to a hardware plugin.
      tags:
      - v1
      - fastapi
  /api/v1/plugins/{plugin_id}/disconnect:
    post:
      operationId: disconnect_plugin
      parameters:
      - in: path
        name: plugin_id
        required: true
        schema:
          type: string
      - in: query
        name: plugin_id
        required: false
        schema:
          type: str
      requestBody:
        content:
          application/json:
            schema:
              type: object
        required: true
      responses:
        '201': *id005
        '400': *id006
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Disconnect from a hardware plugin.
      tags:
      - v1
      - fastapi
  /api/v1/plugins/{plugin_id}/execute:
    post:
      operationId: execute_plugin_command
      parameters:
      - in: path
        name: plugin_id
        required: true
        schema:
          type: string
      - in: query
        name: plugin_id
        required: false
        schema:
          type: str
      requestBody:
        content:
          application/json:
            schema:
              type: object
        required: true
      responses:
        '201': *id005
        '400': *id006
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Execute a command on a hardware plugin.
      tags:
      - v1
      - fastapi
  /api/v1/plugins/{plugin_id}/health:
    get:
      operationId: get_plugin_health
      parameters:
      - in: path
        name: plugin_id
        required: true
        schema:
          type: string
      - in: query
        name: plugin_id
        required: false
        schema:
          type: str
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Get health status of a specific plugin.
      tags:
      - v1
      - fastapi
  /api/v1/protocol-steps/fetch:
    get:
      operationId: fetch_protocol_steps
      parameters:
      - in: query
        name: scenario
        required: false
        schema:
          type: str
      - in: query
        name: source
        required: false
        schema:
          type: str
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Fetch protocol steps for preview.
      tags:
      - v1
      - fastapi
  /api/v1/scenarios/fetch:
    get:
      operationId: fetch_scenarios
      parameters:
      - in: query
        name: source
        required: false
        schema:
          type: str
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Fetch scenarios from backend DB or external JSON and normalize shape.
      tags:
      - v1
      - fastapi
  /api/v1/scenarios/register-dsl:
    post:
      operationId: register_dsl
      requestBody:
        content:
          application/json:
            schema:
              type: object
        required: true
      responses:
        '201': *id005
        '400': *id006
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Register one or many scenarios defined as DSL strings.
      tags:
      - v1
      - fastapi
  /api/v1/scenarios/{scenario_id}:
    get:
      operationId: get_scenario
      parameters:
      - in: path
        name: scenario_id
        required: true
        schema:
          type: string
      - in: query
        name: scenario_id
        required: false
        schema:
          type: str
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Get specific scenario
      tags:
      - v1
      - fastapi
  /api/v1/sim/state:
    get:
      operationId: get_sim_state
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Get simulation state in list format
      tags:
      - v1
      - fastapi
  /api/v1/state:
    get:
      operationId: get_state
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Get current system state
      tags:
      - v1
      - fastapi
  /api/v1/values/current:
    get:
      operationId: get_current_value
      parameters:
      - in: query
        name: param
        required: false
        schema:
          type: str
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Get current value for a parameter (single request, not streaming).
      tags:
      - v1
      - fastapi
  /api/v1/values/stream:
    get:
      operationId: stream_values
      parameters:
      - in: query
        name: param
        required: false
        schema:
          type: str
      - in: query
        name: min
        required: false
        schema:
          type: float
      - in: query
        name: max
        required: false
        schema:
          type: float
      - in: query
        name: period
        required: false
        schema:
          type: float
      - in: query
        name: interval
        required: false
        schema:
          type: float
      - in: query
        name: demo
        required: false
        schema:
          type: bool
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: SSE endpoint for live value streaming.
      tags:
      - v1
      - fastapi
  /api/v1/variables:
    get:
      operationId: get_variables_alias
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Get variables (alias for fetch)
      tags:
      - v1
      - fastapi
  /api/v1/variables/fetch:
    get:
      operationId: fetch_variables
      parameters:
      - in: query
        name: source
        required: false
        schema:
          type: str
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Fetch variables (Peripheral State Table) from backend DB; tolerate
        dev HTML by returning [].
      tags:
      - v1
      - fastapi
  /editor:
    get:
      operationId: editor_page
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Serve the scenario editor UI
      tags:
      - fastapi
  /firmware/api/v1/health:
    get:
      operationId: health_check
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Health check endpoint for tests and frontend compatibility probes.
      tags:
      - fastapi
      - firmware
  /health:
    get:
      operationId: health_check
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: Health check endpoint for tests and frontend compatibility probes.
      tags:
      - fastapi
  /ws:
    websocket:
      operationId: websocket_endpoint
      responses:
        '200': *id001
        '401': *id002
        '404': *id003
        '500': *id004
      summary: WEBSOCKET /ws
      tags:
      - fastapi
servers:
- description: Local development
  url: http://localhost:8101
- description: Relative
  url: /
```

### testql Scenarios

#### `testql-scenarios/cross-project-integration.testql.toon.yaml`

```toon markpact:testql path=testql-scenarios/cross-project-integration.testql.toon.yaml
# SCENARIO: Cross-Project Integration Tests
# TYPE: integration
# GENERATED: true
# PROJECTS: docs, project

CONFIG[1]{key, value}:
  mode, cross-project

LOG[2]{message}:
  "Project: docs"
  "Project: project"
```

#### `testql-scenarios/generated-api-integration.testql.toon.yaml`

```toon markpact:testql path=testql-scenarios/generated-api-integration.testql.toon.yaml
# SCENARIO: API Integration Tests
# TYPE: api
# GENERATED: true

CONFIG[3]{key, value}:
  base_url, http://localhost:8101
  timeout_ms, 30000
  retry_count, 3

API[4]{method, endpoint, expected_status}:
  GET, /health, 200
  GET, /api/v1/status, 200
  POST, /api/v1/test, 201
  GET, /api/v1/docs, 200

ASSERT[2]{field, operator, expected}:
  status, ==, ok
  response_time, <, 1000
```

#### `testql-scenarios/generated-api-smoke.testql.toon.yaml`

```toon markpact:testql path=testql-scenarios/generated-api-smoke.testql.toon.yaml
# SCENARIO: Auto-generated API Smoke Tests
# TYPE: api
# GENERATED: true
# DETECTORS: FastAPIDetector, OpenAPIDetector, ConfigEndpointDetector

CONFIG[4]{key, value}:
  base_url, http://localhost:8101
  timeout_ms, 10000
  retry_count, 3
  detected_frameworks, FastAPIDetector, OpenAPIDetector, ConfigEndpointDetector

# REST API Endpoints (72 unique)
API[25]{method, endpoint, expected_status}:
  GET, /api/v1/state, 200
  GET, /api/v1/values/stream, 200
  GET, /api/v1/values/current, 200
  GET, /api/v1/sim/state, 200
  GET, /api/v1/variables, 200
  GET, /api/v1/variables/fetch, 200
  GET, /api/v1/protocol-steps/fetch, 200
  POST, /api/v1/commands, 201
  GET, /api/v1/plugins/, 200
  GET, /api/v1/plugins/status, 200
  POST, /api/v1/plugins/validate, 201
  GET, /api/v1/scenarios/fetch, 200
  POST, /api/v1/scenarios/register-dsl, 201
  POST, /api/v1/execution/start, 201
  POST, /api/v1/execution/step, 201
  GET, /api/v1/execution/projection, 200
  GET, /api/v1/execution/status, 200
  GET, /api/v1/execution/logs, 200
  GET, /api/v1/execution/stream, 200
  GET, /api/v1/execution/logs/stream, 200
  POST, /api/v1/peripherals/reset, 201
  GET, /api/v1/hardware/health, 200
  GET, /api/v1/hardware/identify, 200
  POST, /api/v1/hardware/pump, 201
  POST, /api/v1/hardware/lung, 201

ASSERT[2]{field, operator, expected}:
  status, <, 500
  response_time, <, 2000

# Summary by Framework:
#   fastapi: 50 endpoints
#   openapi: 50 endpoints
```

#### `testql-scenarios/generated-from-pytests.testql.toon.yaml`

```toon markpact:testql path=testql-scenarios/generated-from-pytests.testql.toon.yaml
# SCENARIO: Auto-generated from Python Tests
# TYPE: integration
# GENERATED: true

LOG[42]{message}:
  "Test: TestVariableStore_test_interpolate_braces"
  "Test: TestCqlExecuteMode_test_execute_mode_initializes_firmware"
  "Test: TestFirmwareAdapterUnit_test_resolve_peripheral"
  "Test: TestFirmwareAdapterUnit_test_dispatch_confirm_no_http"
  "Test: TestFirmwareAdapterUnit_test_dispatch_lung_falls_back_to_direct_service_on_404"
  "Test: test_interpolate_braces"
  "Test: test_execute_mode_initializes_firmware"
  "Test: test_resolve_peripheral"
  "Test: test_dispatch_confirm_no_http"
  "Test: test_dispatch_lung_falls_back_to_direct_service_on_404"
```

#### `testql-scenarios/generated-from-scenarios.testql.toon.yaml`

```toon markpact:testql path=testql-scenarios/generated-from-scenarios.testql.toon.yaml
# SCENARIO: Auto-generated from OQL/CQL Scenarios
# TYPE: hardware
# GENERATED: true

CONFIG[1]{key, value}:
  generated_from, oql_scenarios

LOG[41]{message}:
  "Scenario: hardware-lung-smoke"
  "Scenario: hardware-diagnostics"
  "Scenario: ts-temp-wilgotnosc"
  "Scenario: maskleaktest-ogledinywizualne"
  "Scenario: pss7000-testprzezadapter"
  "Scenario: test-pompy"
  "Scenario: hardware-valves-smoke"
  "Scenario: kaskadowy-pomiar-cisnienia-z-przelaczaniem-czujnikow"
  "Scenario: test-przeplywu"
  "Scenario: c202-example"
```

#### `testql-contracts.testql.toon.yaml`

```toon markpact:testql path=testql-contracts.testql.toon.yaml
# SCENARIO: API Contract Tests
# Auto-generated from OpenAPI spec
# TYPE: contract

CONFIG[3]{key, value}:
  base_url, ${api_url:-http://localhost:8101}
  timeout_ms, 10000
  strict_validation, true

API[49]{method, endpoint, expected_status}:
  GET, /api/v1/state, 200  # Get current system state
  GET, /api/v1/values/stream, 200  # SSE endpoint for live value streaming.
  GET, /api/v1/values/current, 200  # Get current value for a parameter (single request,
  GET, /api/v1/sim/state, 200  # Get simulation state in list format
  GET, /api/v1/variables, 200  # Get variables (alias for fetch)
  GET, /api/v1/variables/fetch, 200  # Fetch variables (Peripheral State Table) from back
  GET, /api/v1/protocol-steps/fetch, 200  # Fetch protocol steps for preview.
  POST, /api/v1/commands, 201  # Command bus endpoint used by frontend.
  GET, /api/v1/plugins/, 200  # List all registered hardware plugins.
  GET, /api/v1/plugins/status, 200  # Get overall status of all plugins.
  GET, /api/v1/plugins/{plugin_id}, 200  # Get information about a specific plugin.
  GET, /api/v1/plugins/{plugin_id}/health, 200  # Get health status of a specific plugin.
  POST, /api/v1/plugins/{plugin_id}/connect, 201  # Connect to a hardware plugin.
  POST, /api/v1/plugins/{plugin_id}/disconnect, 201  # Disconnect from a hardware plugin.
  POST, /api/v1/plugins/{plugin_id}/execute, 201  # Execute a command on a hardware plugin.
  POST, /api/v1/plugins/validate, 201  # Validate configurations for multiple plugins.
  GET, /api/v1/scenarios/{scenario_id}, 200  # Get specific scenario
  GET, /api/v1/scenarios/fetch, 200  # Fetch scenarios from backend DB or external JSON a
  POST, /api/v1/scenarios/register-dsl, 201  # Register one or many scenarios defined as DSL stri
  POST, /api/v1/execution/start, 201  # Start scenario execution
  POST, /api/v1/execution/step, 201  # Execute a single DSL step within the current (or n
  GET, /api/v1/execution/by-id/{execution_id}, 200  # Get execution status
  GET, /api/v1/execution/projection, 200  # Return a lightweight execution projection used by 
  GET, /api/v1/execution/status, 200  # Return textual logs and status for polling fallbac
  GET, /api/v1/execution/logs, 200  # Return execution logs for frontend polling.
  GET, /api/v1/execution/stream, 200  # Stream execution events for frontend polling fallb
  GET, /api/v1/execution/logs/stream, 200  # Stream execution logs for terminal view
  GET, /api/v1/peripherals/{peripheral_id}, 200  # Get specific peripheral
  PUT, /api/v1/peripherals/{peripheral_id}, 200  # Update peripheral via PUT (for tests)
  POST, /api/v1/peripherals/{peripheral_id}/set, 201  # Update peripheral (manual mode)

# Contract Validation
ASSERT[3]{field, operator, expected}:
  content_type, ==, application/json
  schema_valid, ==, true
  status, <, 500

PERFORMANCE[1]{metric, threshold}:
  response_time_ms, <, 1000
```

## Workflows

### Taskfile Tasks (`Taskfile.yml`)

```yaml markpact:taskfile path=Taskfile.yml
# Taskfile.yml — oqlos (OqlOS Hardware Integration) project runner
# https://taskfile.dev

version: "3"

vars:
  APP_NAME: oqlos
  DOQL_OUTPUT: app.doql.less
  DOQL_CMD: "{{if eq OS \"windows\"}}doql.exe{{else}}doql{{end}}"

env:
  PYTHONPATH: "{{.PWD}}"

tasks:
  # ─────────────────────────────────────────────────────────────────────────────
  # Development
  # ─────────────────────────────────────────────────────────────────────────────

  install:
    desc: Install Python dependencies (editable)
    cmds:
      - pip install -e .[dev]

  deps:update:
    desc: Upgrade all outdated Python packages in the active / project venv
    cmds:
      - |
        PIP="pip"
        [ -f "{{.PWD}}/.venv/bin/pip" ] && PIP="{{.PWD}}/.venv/bin/pip"
        $PIP install --upgrade pip
        OUTDATED=$($PIP list --outdated --format=columns 2>/dev/null | tail -n +3 | awk '{print $1}')
        if [ -z "$OUTDATED" ]; then
          echo "✅ All packages are up to date."
        else
          echo "📦 Upgrading: $OUTDATED"
          echo "$OUTDATED" | xargs $PIP install --upgrade
          echo "✅ Done."
        fi

  quality:
    desc: Run pyqual quality pipeline
    cmds:
      - pyqual run

  quality:fix:
    desc: Run pyqual with auto-fix
    cmds:
      - pyqual run --fix

  quality:report:
    desc: Generate pyqual quality report
    cmds:
      - pyqual report

  test:
    desc: Run pytest suite
    cmds:
      - pytest -q

  test:frontend:
    desc: Run frontend unit tests (node:test)
    dir: frontend
    cmds:
      - npm run test:unit

  lint:
    desc: Run ruff lint check
    cmds:
      - ruff check .

  fmt:
    desc: Auto-format with ruff
    cmds:
      - ruff format .

  build:
    desc: Build wheel + sdist
    cmds:
      - python -m build

  clean:
    desc: Remove build artefacts
    cmds:
      - rm -rf build/ dist/ *.egg-info

  all:
    desc: Run install, quality check
    cmds:
      - task: install
      - task: quality

  # ─────────────────────────────────────────────────────────────────────────────
  # Hardware / oqlctl
  # ─────────────────────────────────────────────────────────────────────────────

  hardware:check:
    desc: Run OqlOS hardware doctor via oqlctl
    cmds:
      - oqlctl doctor || echo "Hardware doctor reported issues"

  hardware:identify:
    desc: Identify connected hardware
    cmds:
      - oqlctl identify

  # ─────────────────────────────────────────────────────────────────────────────
  # Doql Integration
  # ─────────────────────────────────────────────────────────────────────────────

  doql:adopt:
    desc: Reverse-engineer oqlos project structure
    cmds:
      - |
        if ! command -v {{.DOQL_CMD}} >/dev/null 2>&1; then
          echo "⚠️  doql not installed. Install: pip install doql"
          exit 1
        fi
      - "{{.DOQL_CMD}} adopt {{.PWD}} --output app.doql.css --force"
      - "{{.DOQL_CMD}} export --format less -o {{.DOQL_OUTPUT}}"
      - echo "✅ Project structure captured in {{.DOQL_OUTPUT}}"

  doql:validate:
    desc: Validate app.doql.less syntax
    cmds:
      - |
        if [ ! -f "{{.DOQL_OUTPUT}}" ]; then
          echo "❌ {{.DOQL_OUTPUT}} not found. Run: task doql:adopt"
          exit 1
        fi
      - "{{.DOQL_CMD}} validate"

  doql:doctor:
    desc: Run doql health checks
    cmds:
      - "{{.DOQL_CMD}} doctor"

  doql:build:
    desc: Generate code from app.doql.less
    cmds:
      - |
        if [ ! -f "{{.DOQL_OUTPUT}}" ]; then
          echo "❌ {{.DOQL_OUTPUT}} not found. Run: task doql:adopt"
          exit 1
        fi
      - |
        # Regenerate LESS from CSS if CSS exists
        if [ -f "app.doql.css" ]; then
          {{.DOQL_CMD}} export --format less -o {{.DOQL_OUTPUT}}
        fi
      - "{{.DOQL_CMD}} build app.doql.css --out build/"

  analyze:
    desc: Full doql analysis (adopt + validate + doctor)
    cmds:
      - task: doql:adopt
      - task: doql:validate
      - task: doql:doctor

  # ─────────────────────────────────────────────────────────────────────────────
  # Utility
  # ─────────────────────────────────────────────────────────────────────────────

  help:
    desc: Show available tasks
    cmds:
      - task --list
```

## Quality Pipeline (`pyqual.yaml`)

```yaml markpact:pyqual path=pyqual.yaml
pipeline:
  name: oqlos-quality

  metrics:
    cc_max: 15
    vallm_pass_min: 65   # adjust based on actual
    # coverage disabled - pytest_cov reports null

  stages:
    - name: analyze
      tool: code2llm-filtered

    - name: validate
      tool: vallm-filtered

    - name: prefact
      tool: prefact
      optional: true
      when: any_stage_fail
      timeout: 900

    - name: fix
      tool: llx-fix
      optional: true
      when: any_stage_fail
      timeout: 1800

    - name: security
      tool: bandit
      optional: true
      timeout: 120

    - name: test
      tool: pytest
      timeout: 600

    - name: push
      tool: git-push
      optional: true
      timeout: 120

  loop:
    max_iterations: 3
    on_fail: report
    ticket_backends:
      - markdown

  env:
    LLM_MODEL: openrouter/qwen/qwen3-coder-next
```

## Configuration

```yaml
project:
  name: oqlos
  version: 0.1.28
  env: local
```

## Dependencies

### Runtime

```text markpact:deps python
fastapi>=0.110
uvicorn>=0.28
pydantic>=2.0
pydantic-settings>=2.2.0
pyserial>=3.5
pymodbus>=3.6
httpx>=0.25
nfo>=0.2.3
goal>=2.1.0
costs>=0.1.20
pfix>=0.1.60
paho-mqtt>=1.6.1
pluggy>=1.4
pytest-asyncio>=0.23
PyYAML>=6.0
testql>=0.2.0
```

### Development

```text markpact:deps python scope=dev
pytest
pytest-asyncio
httpx
websockets>=13.0
goal>=2.1.0
costs>=0.1.20
pfix>=0.1.60
paho-mqtt>=1.6.1
```

## Deployment

```bash markpact:run
pip install oqlos

# development install
pip install -e .[dev]
```

### Docker

- **base image**: `node:20-alpine AS ui-build`
- **expose**: `8200`
- **entrypoint**: `["oqlos-server", "--host", "0.0.0.0", "--port", "8200"]`

### Docker Compose (`docker-compose.dev.yml`)

- **mqtt** image=`eclipse-mosquitto:2` ports: `1883:1883`
- **traefik** image=`traefik:v3` ports: `80:80`, `8080:8080`
- **oqlos-api** image=`{'context': '..', 'dockerfile': 'docker/Dockerfile'}` ports: `8200:8200`

## Environment Variables (`.env.example`)

| Variable | Default | Description |
|----------|---------|-------------|
| `OQLOS_FIRMWARE_PORT` | `8202` | Server Configuration |
| `OQLOS_SERVICE_NAME` | `firmware-simulator` |  |
| `OQLOS_SERVICE_VERSION` | `0.1.0` |  |
| `OQLOS_HARDWARE_MODE` | `mock` | Hardware Mode (mock \| real) |
| `OQLOS_MODBUS_SERIAL_PORT` | `/dev/ttyACM1` | Modbus RTU Configuration |
| `OQLOS_MODBUS_BAUD` | `19200` |  |
| `OQLOS_MODBUS_PARITY` | `N` |  |
| `OQLOS_MODBUS_DEVICE_ID` | `1` |  |
| `OQLOS_MODBUS_HOST` | `localhost` | Modbus TCP Fallback |
| `OQLOS_MODBUS_PORT` | `502` |  |
| `OQLOS_PIADC_URL` | `http://localhost:8080` | Hardware Service URLs |
| `OQLOS_MOTOR_URL` | `http://localhost:49055` |  |
| `OQLOS_LUNG_MOTOR_URL` | `http://localhost:8205` |  |
| `OQLOS_PUMP_FLOW_FULL_SCALE_LPM` | `10` | Flow rate that maps to 100% PWM for `pompa 1` |
| `OQLOS_LOG_LEVEL` | `INFO` | Logging (DEBUG \| INFO \| WARNING \| ERROR) |
| `OQLOS_CORS_ORIGINS` | `*` | CORS Settings (comma-separated origins or * for all) |

## Release Management (`goal.yaml`)

- **versioning**: `semver`
- **commits**: `conventional` scope=`oqlos`
- **changelog**: `keep-a-changelog`
- **build strategies**: `python`, `nodejs`, `rust`
- **version files**: `VERSION`, `pyproject.toml:version`, `oqlos/__init__.py:__version__`

## Makefile Targets

- `help`
- `test` — --- testy ----------------------------------------------------------------
- `test-hw`
- `smoke`
- `checksums` — --- integralność / sync --------------------------------------------------
- `verify-rpi`
- `sync-rpi`
- `restart`
- `deploy` — --- deploy (redeploy framework) ------------------------------------------
- `redeploy`
- `122`
- `pi-hw`
- `serve` — --- uruchamianie lokalnie -------------------------------------------------
- `panel-url`

## Code Analysis

### `project/map.toon.yaml`

```toon markpact:analysis path=project/map.toon.yaml
# oqlos | 374f 56179L | python:286,javascript:73,shell:9,typescript:3,css:2,less:1 | 2026-07-02
# stats: 1502 func | 215 cls | 374 mod | CC̄=4.1 | critical:120 | cycles:0
# alerts[5]: CC test_hardware_ui_aliases_and_status_page_are_served=22; CC test_navigation_index_and_short_aliases=15; CC _resolve_func_steps=14; CC _probe_i2c_ads1115=14; CC exec_action_loop_block=14
# hotspots[5]: _resolve fan=22; build_diagnosis_report fan=19; hardware_identify fan=18; _build_waveshare_diagnose_report fan=18; _handle_start fan=18
# evolution: baseline
# Keys: M=modules, D=details, i=imports, e=exports, c=classes, f=functions, m=methods
M[374]:
  app.doql.css,165
  app.doql.less,316
  examples/curl-quickstart.sh,75
  examples/hardware/doctor-workflow.sh,53
  frontend/src/api/hardware-api-errors.js,88
  frontend/src/api/hardware-api-errors.test.js,80
  frontend/src/api/hardware-api-log.js,88
  frontend/src/api/hardware-diagnostic-failure.js,98
  frontend/src/api/hardware-diagnostic-failure.test.js,59
  frontend/src/api/hardware-tic249-status.js,36
  frontend/src/api/hardwareApi.js,258
  frontend/src/api/scenarioFilesApi.js,80
  frontend/src/api/wsClient.js,139
  frontend/src/context/app-config-document.js,27
  frontend/src/hooks/useMapEditorHardwareEvents.js,62
  frontend/src/hooks/useMapEditorSidebarAutoCollapse.js,30
  frontend/src/hooks/useParentEncoderNavigation.js,40
  frontend/src/hooks/useRailHoverPreview.js,85
  frontend/src/hooks/useUrlConfig.js,86
  frontend/src/hooks/useWsStatus.js,27
  frontend/src/i18n/dictionaries.js,2136
  frontend/src/i18n/hardware-demo-extra-translations.js,184
  frontend/src/i18n/hardware-status-log-translations.js,82
  frontend/src/i18n/hardware-status-panel-translations.js,328
  frontend/src/i18n/hardware-status-presets-translations.js,796
  frontend/src/pages/mapEditorConstants.js,42
  frontend/src/pages/mapEditorDefaultMap.js,1954
  frontend/src/styles/global.css,2324
  frontend/src/utils/collapse-toggle-bridge.js,61
  frontend/src/utils/designRem.js,44
  frontend/src/utils/encoder-navigation.js,143
  frontend/src/utils/encoder-navigation.test.js,21
  frontend/src/utils/hardware-activity-log.js,35
  frontend/src/utils/hardware-api-retry.js,39
  frontend/src/utils/hardware-api-retry.test.js,46
  frontend/src/utils/hardware-demo-identify.js,86
  frontend/src/utils/hardware-demo-identify.test.js,28
  frontend/src/utils/hardware-restart-configure.js,69
  frontend/src/utils/hardware-restart-configure.test.js,31
  frontend/src/utils/hardware-restart-docs.js,12
  frontend/src/utils/hardware-restart-probe-select.js,20
  frontend/src/utils/hardware-restart-step-errors.js,16
  frontend/src/utils/hardware-restart-step-outcome.js,7
  frontend/src/utils/hardware-restart-step-runner.js,24
  frontend/src/utils/hardware-restart-step-runner.test.js,18
  frontend/src/utils/hardware-restart-wizard-helpers.js,42
  frontend/src/utils/hardware-restart-wizard-steps.js,47
  frontend/src/utils/hardware-restart-wizard-steps.test.js,32
  frontend/src/utils/hardware-time.js,5
  frontend/src/utils/hardware-wizard-plan.js,42
  frontend/src/utils/hardware-wizard-plan.test.js,17
  frontend/src/utils/hardware-wizard-steps.js,102
  frontend/src/utils/hardware-wizard-steps.test.js,30
  frontend/src/utils/hardwareEventStream.js,53
  frontend/src/utils/hardwareEventStream.test.js,37
  frontend/src/utils/hardwareStatusModel.js,39
  frontend/src/utils/hardwareStatusModel.test.js,44
  frontend/src/utils/hui-shell-key.js,39
  frontend/src/utils/mapEditorFuncHardwareSummary.js,84
  frontend/src/utils/mapEditorFuncHardwareSummary.test.js,55
  frontend/src/utils/mapEditorIntegrationMeta.js,81
  frontend/src/utils/mapEditorIntegrationMeta.test.js,44
  frontend/src/utils/mapEditorMapShape.js,59
  frontend/src/utils/mapEditorModel.js,84
  frontend/src/utils/mapEditorModel.test.js,33
  frontend/src/utils/mapEditorObjectActionEdits.js,45
  frontend/src/utils/mapEditorObjectActionEdits.test.js,34
  frontend/src/utils/mapEditorTic249.js,8
  frontend/src/utils/mapEditorTic249.test.js,14
  frontend/src/utils/oqlGoals.js,86
  frontend/src/utils/oqlGoals.test.js,56
  frontend/src/utils/parentUrlBridge.js,40
  frontend/src/utils/rbac.policy.js,125
  frontend/src/utils/scenarioFilesUrl.js,68
  frontend/src/utils/scenarioFilesUrl.test.js,72
  frontend/src/utils/url-embed-config.js,194
  frontend/src/utils/url-embed-config.test.js,93
  frontend/src/utils/useSelectionCollapsePanel.js,160
  frontend/vendor/hardware-client/index.ts,32
  frontend/vendor/hardware-client/paths.ts,40
  frontend/vite.config.ts,37
  oqlos/__init__.py,4
  oqlos/api/__init__.py,18
  oqlos/api/_hw3_mapping.py,158
  oqlos/api/_hw3_models.py,195
  oqlos/api/_hw3_peripheral.py,134
  oqlos/api/_hw3_system.py,135
  oqlos/api/editor.py,201
  oqlos/api/execution.py,359
  oqlos/api/hardware.py,86
  oqlos/api/hardware_actuators.py,24
  oqlos/api/hardware_diagnosis_routes.py,57
  oqlos/api/hardware_events.py,137
  oqlos/api/hardware_gateway.py,35
  oqlos/api/hardware_hui.py,62
  oqlos/api/hardware_identify.py,171
  oqlos/api/hardware_lung.py,86
  oqlos/api/hardware_mapping_contract.py,64
  oqlos/api/hardware_mapping_motor2.py,49
  oqlos/api/hardware_mapping_store.py,153
  oqlos/api/hardware_modbus_routes.py,80
  oqlos/api/hardware_modbus_topology.py,93
  oqlos/api/hardware_modbus_waveshare.py,622
  oqlos/api/hardware_modbus_wizard.py,400
  oqlos/api/hardware_peripherals_routes.py,91
  oqlos/api/hardware_platform.py,166
  oqlos/api/hardware_probe.py,135
  oqlos/api/hardware_probe_devices.py,189
  oqlos/api/hardware_registry.py,62
  oqlos/api/hardware_runtime.py,190
  oqlos/api/hardware_v3.py,61
  oqlos/api/logs.py,46
  oqlos/api/main.py,606
  oqlos/api/oql_mqtt.py,153
  oqlos/api/peripherals.py,69
  oqlos/api/plugins.py,182
  oqlos/api/scenarios.py,252
  oqlos/api/state.py,371
  oqlos/api/utils/__init__.py,1
  oqlos/api/utils/execution_ctrl.py,63
  oqlos/api/version.py,25
  oqlos/config.py,221
  oqlos/core/__init__.py,1
  oqlos/core/_action_motor2.py,482
  oqlos/core/_compare.py,41
  oqlos/core/_cql_tokenizer.py,411
  oqlos/core/_cql_tree_builder.py,168
  oqlos/core/_dsl_helpers.py,133
  oqlos/core/_firmware_executor.py,267
  oqlos/core/_func_resolver.py,97
  oqlos/core/_interpreter_actions.py,801
  oqlos/core/_line_parsers.py,262
  oqlos/core/_oql_adapter.py,491
  oqlos/core/_sensor_evaluator.py,146
  oqlos/core/_value_normalizers.py,127
  oqlos/core/base.py,312
  oqlos/core/cql_parser.py,468
  oqlos/core/executor.py,378
  oqlos/core/interpreter.py,691
  oqlos/core/motor2_runtime.py,210
  oqlos/core/oql_parser.py,774
  oqlos/core/oql_versioning.py,73
  oqlos/core/parser.py,185
  oqlos/core/safe_eval.py,139
  oqlos/core/state.py,125
  oqlos/dsl/__init__.py,19
  oqlos/dsl/schema.py,296
  oqlos/errors/__init__.py,44
  oqlos/errors/catalog.py,314
  oqlos/errors/exceptions.py,60
  oqlos/errors/fastapi_integration.py,24
  oqlos/errors/repair_commit.py,41
  oqlos/hardware/__init__.py,18
  oqlos/hardware/artificial_lung.py,163
  oqlos/hardware/client/__init__.py,101
  oqlos/hardware/client/adc.py,65
  oqlos/hardware/client/autorepair.py,134
  oqlos/hardware/client/config.py,87
  oqlos/hardware/client/constants.py,70
  oqlos/hardware/client/errors.py,27
  oqlos/hardware/client/http_helpers.py,27
  oqlos/hardware/client/identify_enrich.py,79
  oqlos/hardware/client/identify_enrich_adapters.py,191
  oqlos/hardware/client/identify_enrich_modbus_io.py,90
  oqlos/hardware/client/modbus_repair.py,165
  oqlos/hardware/client/platform.py,51
  oqlos/hardware/client/proxy.py,461
  oqlos/hardware/client/resolvers.py,129
  oqlos/hardware/client/tic249_arg_contract.py,66
  oqlos/hardware/client/tic249_arg_helpers.py,12
  oqlos/hardware/client/tic249_command_mapping.py,50
  oqlos/hardware/client/tic249_error_messages.py,113
  oqlos/hardware/client/tic249_extended.py,216
  oqlos/hardware/client/tic249_motion_params.py,128
  oqlos/hardware/client/tic249_rig_direction.py,44
  oqlos/hardware/client/tic249_sidecar_client.py,184
  oqlos/hardware/config_paths.py,42
  oqlos/hardware/config_schema.py,142
  oqlos/hardware/control_proxy.py,69
  oqlos/hardware/diagnosis.py,247
  oqlos/hardware/diagnosis_device_actions.py,222
  oqlos/hardware/diagnosis_plugin_health.py,87
  oqlos/hardware/diagnosis_types.py,87
  oqlos/hardware/discovery.py,164
  oqlos/hardware/drivers/__init__.py,6
  oqlos/hardware/drivers/gpio.py,90
  oqlos/hardware/drivers/mqtt.py,120
  oqlos/hardware/drivers/spi.py,93
  oqlos/hardware/firmware_adapter.py,481
  oqlos/hardware/gateway.py,387
  oqlos/hardware/gateway_http.py,24
  oqlos/hardware/health_status.py,27
  oqlos/hardware/hui_actions.py,66
  oqlos/hardware/hui_artificial_lung.py,86
  oqlos/hardware/hui_hold.py,257
  oqlos/hardware/hui_lung_recipe.py,148
  oqlos/hardware/identify_enrichment.py,19
  oqlos/hardware/modbus_identify.py,132
  oqlos/hardware/peripheral_mapping.py,137
  oqlos/hardware/plugin_gateway.py,635
  oqlos/hardware/plugins/__init__.py,50
  oqlos/hardware/plugins/_rtu_serial.py,48
  oqlos/hardware/plugins/_shared.py,67
  oqlos/hardware/plugins/base.py,371
  oqlos/hardware/plugins/lung.py,354
  oqlos/hardware/plugins/modbus.py,330
  oqlos/hardware/plugins/modbus_adc.py,393
  oqlos/hardware/plugins/motor.py,406
  oqlos/hardware/plugins/motor_http_handlers.py,68
  oqlos/hardware/plugins/motor_modbus_handlers.py,208
  oqlos/hardware/plugins/piadc.py,263
  oqlos/hardware/plugins/plugin_http_handlers.py,33
  oqlos/hardware/plugins/registry.py,333
  oqlos/hardware/protocol.py,61
  oqlos/hardware/registry.py,50
  oqlos/hardware/rtc_probe.py,198
  oqlos/hardware/scanner_probe.py,261
  oqlos/hardware/sidecar_control.py,329
  oqlos/hardware/stack_snapshot.py,89
  oqlos/hardware/tic249_units.py,40
  oqlos/hardware/transport/__init__.py,25
  oqlos/hardware/transport/manage_ops.py,154
  oqlos/hardware/transport/manage_ops_diagnostic.py,148
  oqlos/hardware/transport/manage_ops_usb.py,34
  oqlos/hardware/transport/mqtt_oql_bridge.py,494
  oqlos/hardware/usb_diagnostics.py,186
  oqlos/ide/__init__.py,1
  oqlos/models/__init__.py,1
  oqlos/models/dsl_models.py,88
  oqlos/models/execution.py,23
  oqlos/models/peripheral.py,34
  oqlos/models/scenario.py,36
  oqlos/reporters/__init__.py,7
  oqlos/reporters/html_report.py,267
  oqlos/reporters/json_reporter.py,139
  oqlos/reporters/junit.py,87
  oqlos/scenarios/legacy_aliases.py,41
  oqlos/shared/__init__.py,1
  oqlos/shared/_endpoint_helpers.py,49
  oqlos/shared/config_factory.py,85
  oqlos/shared/event_server.py,172
  oqlos/shared/event_store.py,78
  oqlos/shared/file_ops.py,131
  oqlos/shared/logger.py,90
  oqlos/shared/logs_query.py,146
  oqlos/shared/release_version.py,126
  oqlos/shared/version_endpoint.py,67
  oqlos/tools/__init__.py,1
  oqlos/tools/cql_cli/__init__.py,67
  oqlos/tools/cql_cli/commands.py,193
  oqlos/tools/cql_cli/formatting.py,64
  oqlos/tools/cql_cli/main.py,416
  oqlos/tools/cql_cli/preflight.py,310
  oqlos/tools/cql_cli/utils.py,151
  oqlos/tools/gen_error_docs.py,108
  oqlos/tools/hardware_diagnose/__init__.py,74
  oqlos/tools/hardware_diagnose/__main__.py,185
  oqlos/tools/hardware_diagnose/benchmark.py,56
  oqlos/tools/hardware_diagnose/calibration.py,93
  oqlos/tools/hardware_diagnose/discovery.py,100
  oqlos/tools/hardware_diagnose/doctor.py,94
  oqlos/tools/hardware_diagnose/doctor_common.py,67
  oqlos/tools/hardware_diagnose/doctor_detection.py,131
  oqlos/tools/hardware_diagnose/doctor_firmware.py,227
  oqlos/tools/hardware_diagnose/doctor_format.py,109
  oqlos/tools/hardware_diagnose/doctor_modbus_analysis.py,253
  oqlos/tools/hardware_diagnose/doctor_repairs.py,120
  oqlos/tools/hardware_diagnose/doctor_serial.py,91
  oqlos/tools/hardware_diagnose/health.py,118
  oqlos/tools/hardware_diagnose/modbus_probe.py,209
  oqlos/tools/hardware_diagnose/report.py,64
  oqlos/tools/hardware_diagnose/shell.py,139
  oqlos/tools/hardware_diagnose.py,37
  oqlos/tools/plugin_cli.py,344
  oqlos/tools/xml_import/__init__.py,18
  oqlos/tools/xml_import/_utils.py,102
  oqlos/tools/xml_import/generators.py,453
  oqlos/tools/xml_import/models.py,91
  oqlos/tools/xml_import/parser.py,176
  oqlos/utils/__init__.py,4
  oqlos/utils/hui_scenario.py,47
  oqlos/utils/sample_data.py,74
  project.sh,43
  scripts/fix_brackets_to_v4.py,96
  scripts/gen-checksums.sh,28
  scripts/hardware-check.sh,341
  scripts/migrate_to_v4.py,338
  scripts/oql-stack.sh,105
  scripts/oql_v2_to_v4_migrate_db.py,663
  scripts/oql_v2_validator.py,225
  scripts/oql_v4_validator.py,282
  scripts/oql_validator_common.py,130
  scripts/provision-rpi-sudo.sh,68
  scripts/scenarios_export.py,297
  scripts/test-hardware.sh,84
  scripts/verify-rpi-checksum.sh,76
  setup_hardware_and_run_oql.py,334
  tests/firmware/test_artificial_lung.py,44
  tests/firmware/test_control_proxy.py,204
  tests/firmware/test_dri0050_sidecar_control.py,84
  tests/firmware/test_dsl_parser_runtime.py,157
  tests/firmware/test_error_catalog.py,76
  tests/firmware/test_firmware.py,10
  tests/firmware/test_firmware_executor.py,132
  tests/firmware/test_gateway_http.py,51
  tests/firmware/test_hardware_diagnosis_api.py,114
  tests/firmware/test_hardware_diagnosis_routes.py,40
  tests/firmware/test_hardware_discovery.py,32
  tests/firmware/test_hardware_doctor.py,287
  tests/firmware/test_hardware_health.py,44
  tests/firmware/test_hardware_health_http.py,61
  tests/firmware/test_hardware_hui_routes.py,44
  tests/firmware/test_hardware_identify.py,236
  tests/firmware/test_hardware_identify_routes.py,10
  tests/firmware/test_hardware_lung_routes.py,24
  tests/firmware/test_hardware_mapping_motor2.py,30
  tests/firmware/test_hardware_modbus_routes.py,12
  tests/firmware/test_hardware_modbus_wizard.py,353
  tests/firmware/test_hardware_platform_detect.py,31
  tests/firmware/test_hardware_probe_devices.py,27
  tests/firmware/test_hardware_runtime_routes.py,52
  tests/firmware/test_hardware_stack_snapshot.py,46
  tests/firmware/test_hardware_v3_compat.py,164
  tests/firmware/test_hui_actions.py,201
  tests/firmware/test_hui_scenario.py,12
  tests/firmware/test_identify_enrich_modbus_io.py,24
  tests/firmware/test_lung_integration.py,282
  tests/firmware/test_lung_plugin_reciprocate.py,94
  tests/firmware/test_modbus_adc_aliases.py,9
  tests/firmware/test_modbus_discovery.py,111
  tests/firmware/test_modbus_identify.py,41
  tests/firmware/test_modbus_probe_cli.py,130
  tests/firmware/test_motor_http_handlers.py,82
  tests/firmware/test_motor_modbus_handlers.py,110
  tests/firmware/test_motor_plugin.py,74
  tests/firmware/test_normalize_scenario.py,200
  tests/firmware/test_oql_envelope.py,74
  tests/firmware/test_oql_manage_ops.py,245
  tests/firmware/test_oql_mqtt_bridge.py,258
  tests/firmware/test_oql_route_http.py,140
  tests/firmware/test_oqlos_error.py,91
  tests/firmware/test_oqlos_logging.py,21
  tests/firmware/test_panel_ui.py,250
  tests/firmware/test_parser_cycle.py,53
  tests/firmware/test_plugin_gateway_env.py,243
  tests/firmware/test_plugin_gateway_init.py,67
  tests/firmware/test_plugin_health.py,340
  tests/firmware/test_plugin_http_handlers.py,68
  tests/firmware/test_plugins_api.py,31
  tests/firmware/test_plugins_health_http.py,57
  tests/firmware/test_repair_commit.py,67
  tests/firmware/test_rtc_probe.py,132
  tests/firmware/test_runtime_command_payload.py,16
  tests/firmware/test_safe_eval.py,244
  tests/firmware/test_scanner_probe.py,68
  tests/firmware/test_tic249_sidecar_control.py,69
  tests/firmware/test_tic249_units.py,18
  tests/firmware/test_tokenizer_extended.py,194
  tests/firmware/test_ui_routes_standard.py,49
  tests/firmware/test_usb_diagnostics.py,63
  tests/test_core.py,853
  tests/test_cql_cli.py,417
  tests/test_cql_inline_regressions.py,74
  tests/test_cql_scenarios.py,88
  tests/test_dsl_schema.py,20
  tests/test_oql_dry_run_regressions.py,62
  tests/test_oql_parser_v3.py,492
  tests/test_oql_scenarios.py,74
  tests/test_reporting.py,46
  tests/test_scenarios_dir.py,18
  tests/test_scenarios_legacy_aliases.py,24
  tests/test_xml_import_generators.py,29
  tests/verify_block_if.py,61
  tests/verify_loops.py,34
D:
  oqlos/__init__.py:
  oqlos/api/__init__.py:
  oqlos/api/_hw3_mapping.py:
    e: hardware_runtime_python_resolve_func_v3,hardware_mapping_get_v3,hardware_mapping_schema_v3,hardware_mapping_put_v3,hardware_mapping_import_v3,hardware_mapping_export_v3,hardware_mapping_reset_v3,hardware_oql_mapped_exec_v3,hardware_cqrs_command_v3,hardware_cqrs_events_v3,hardware_cqrs_events_clear_v3,hardware_events_ws
    hardware_runtime_python_resolve_func_v3(req)
    hardware_mapping_get_v3()
    hardware_mapping_schema_v3()
    hardware_mapping_put_v3(req)
    hardware_mapping_import_v3(req)
    hardware_mapping_export_v3(req)
    hardware_mapping_reset_v3(req)
    hardware_oql_mapped_exec_v3(payload)
    hardware_cqrs_command_v3(req)
    hardware_cqrs_events_v3(limit)
    hardware_cqrs_events_clear_v3(req)
    hardware_events_ws(websocket)
  oqlos/api/_hw3_models.py:
    e: normalize_peripheral_id,_ok_from_result,_runtime_control_skipped,_find_adapter,_run_diagnostic,_resolve_func_steps,_hardware_v1_call,DiagnosticCommandRequest,MappingReplaceRequest,MappingImportRequest,MappingExportRequest,MappingResetRequest,RuntimeFuncResolveRequest,CqrsCommandRequest,CqrsEventsClearRequest,ScannerIngestRequest
    DiagnosticCommandRequest:
    MappingReplaceRequest:
    MappingImportRequest:
    MappingExportRequest:
    MappingResetRequest:
    RuntimeFuncResolveRequest:
    CqrsCommandRequest:
    CqrsEventsClearRequest:
    ScannerIngestRequest:
    normalize_peripheral_id(value)
    _ok_from_result(result)
    _runtime_control_skipped(action)
    _find_adapter(identify_payload;peripheral_id)
    _run_diagnostic(peripheral_id;command;args)
    _resolve_func_steps(hardware_map;func_name;environment;usage_mode)
    _hardware_v1_call(name)
  oqlos/api/_hw3_peripheral.py:
    e: hardware_peripheral_status_v3,hardware_diagnostic_command_v3,hardware_scanner_status_v3,hardware_scanner_last_v3,hardware_scanner_ingest_v3
    hardware_peripheral_status_v3(peripheral_id)
    hardware_diagnostic_command_v3(req)
    hardware_scanner_status_v3()
    hardware_scanner_last_v3()
    hardware_scanner_ingest_v3(payload)
  oqlos/api/_hw3_system.py:
    e: hardware_hui_actions_v3,hardware_hui_shutdown_v3,_hardware_hui_hold_v3,hardware_hui_hold_start_v3,hardware_hui_hold_stop_v3,hardware_hui_al_command_v3,hardware_modbus_autoconfigure_v3,hardware_diagnosis_v3,hardware_diagnosis_repair_v3,hardware_modbus_waveshare_diagnose_v3,hardware_modbus_wizard_plan_v3,hardware_stack_snapshot_v3,hardware_runtime_status_v3,hardware_runtime_stop_v3,hardware_runtime_start_v3,hardware_runtime_make_v3,hardware_modbus_wizard_probe_isolated_v3,hardware_modbus_wizard_program_isolated_v3,hardware_runtime_python_v3
    hardware_hui_actions_v3()
    hardware_hui_shutdown_v3(payload)
    _hardware_hui_hold_v3(key;action)
    hardware_hui_hold_start_v3(key;payload)
    hardware_hui_hold_stop_v3(key;payload)
    hardware_hui_al_command_v3(command;payload)
    hardware_modbus_autoconfigure_v3()
    hardware_diagnosis_v3()
    hardware_diagnosis_repair_v3()
    hardware_modbus_waveshare_diagnose_v3(exclusive)
    hardware_modbus_wizard_plan_v3()
    hardware_stack_snapshot_v3()
    hardware_runtime_status_v3(serial_port)
    hardware_runtime_stop_v3(payload)
    hardware_runtime_start_v3(payload)
    hardware_runtime_make_v3(payload)
    hardware_modbus_wizard_probe_isolated_v3(payload)
    hardware_modbus_wizard_program_isolated_v3(payload)
    hardware_runtime_python_v3(payload)
  oqlos/api/editor.py:
    e: _default_scenarios_dir,_normalize_oql_mode,_result_dict,_editor_response_from_oql,_safe_path,list_files,read_file_endpoint,write_file_endpoint,execute_scenario,FileInfo,FileContent,ExecutionRequest
    FileInfo:
    FileContent:
    ExecutionRequest:
    _default_scenarios_dir()
    _normalize_oql_mode(mode)
    _result_dict(result)
    _editor_response_from_oql()
    _safe_path(file_path)
    list_files()
    read_file_endpoint(file_path)
    write_file_endpoint(file_path;file_content)
    execute_scenario(request)
  oqlos/api/execution.py:
    e: _resolve_step_label,_flatten_steps_for_scenario,_build_step_labels,_resolve_current_index,_current_projection,start_execution,execute_step,_register_dsl_scenario,_make_exec_route,get_execution,get_execution_projection,get_execution_status,get_execution_logs,_make_legacy_route,execution_stream,execution_logs_stream
    _resolve_step_label(scenario_id;goal_id;step_id)
    _flatten_steps_for_scenario(scenario_id)
    _build_step_labels(sc)
    _resolve_current_index(exec_obj;sc)
    _current_projection()
    start_execution(request)
    execute_step(payload)
    _register_dsl_scenario(scenario_id;dsl_content)
    _make_exec_route(ctrl_fn)
    get_execution(execution_id)
    get_execution_projection()
    get_execution_status()
    get_execution_logs()
    _make_legacy_route(ctrl_fn)
    execution_stream(scenario)
    execution_logs_stream(scenario)
  oqlos/api/hardware.py:
  oqlos/api/hardware_actuators.py:
    e: set_valve,set_pump
    set_valve(valve_id;value)
    set_pump(power_pct)
  oqlos/api/hardware_diagnosis_routes.py:
    e: hardware_stack_snapshot,hardware_diagnosis_route,hardware_recover_route
    hardware_stack_snapshot()
    hardware_diagnosis_route(scan)
    hardware_recover_route(scope)
  oqlos/api/hardware_events.py:
    e: _default_path,_load_recent_events_from_disk,_append_event_to_disk,_broadcast_event_to_subscribers,publish_hardware_command_event,list_hardware_command_events,clear_hardware_command_events,get_hardware_command_event_store_path,subscribe_hardware_command_events,unsubscribe_hardware_command_events
    _default_path()
    _load_recent_events_from_disk()
    _append_event_to_disk(event)
    _broadcast_event_to_subscribers(event)
    publish_hardware_command_event(command;result)
    list_hardware_command_events(limit)
    clear_hardware_command_events()
    get_hardware_command_event_store_path()
    subscribe_hardware_command_events()
    unsubscribe_hardware_command_events(subscriber_id)
  oqlos/api/hardware_gateway.py:
    e: set_hardware_gateway,get_hardware_gateway,try_get_hardware_gateway,snapshot_via_health,is_plugin_compatible
    set_hardware_gateway(gw)
    get_hardware_gateway()
    try_get_hardware_gateway()
    snapshot_via_health(build_fn)
    is_plugin_compatible(health_entry)
  oqlos/api/hardware_hui.py:
    e: raise_if_hui_failed,start_hui_action,hui_actions,hui_shutdown,hui_hold_start,hui_hold_stop,hui_al_start,hui_al_stop
    raise_if_hui_failed(payload)
    start_hui_action(action)
    hui_actions()
    hui_shutdown()
    hui_hold_start(key)
    hui_hold_stop(key)
    hui_al_start()
    hui_al_stop()
  oqlos/api/hardware_identify.py:
    e: _hardware_health_overall_ok,_determine_scan_set,_map_adapter_identify_status,hardware_health,hardware_identify
    _hardware_health_overall_ok(payload)
    _determine_scan_set(scan_mode;health)
    _map_adapter_identify_status(hw;health;probes)
    hardware_health()
    hardware_identify(scan)
  oqlos/api/hardware_lung.py:
    e: command_payload,lung_state_response,set_lung,stop_lung,disable_lung,artificial_lung_status,artificial_lung_command
    command_payload(payload)
    lung_state_response(action;status)
    set_lung(steps;speed;cycles;pause)
    stop_lung()
    disable_lung()
    artificial_lung_status()
    artificial_lung_command(payload)
  oqlos/api/hardware_mapping_contract.py:
    e: _validate_motor2,validate_mapping_contract,MappingContractError
    MappingContractError: __init__(1)
    _validate_motor2(motor2_raw;issues)
    validate_mapping_contract(mapping)
  oqlos/api/hardware_mapping_motor2.py:
    e: _is_int,_append_peripheral_id_issue,_append_stroke_steps_issue,_append_speed_issues,validate_motor2_config
    _is_int(value)
    _append_peripheral_id_issue(motor2;issues)
    _append_stroke_steps_issue(motor2;issues)
    _append_speed_issues(motor2;issues)
    validate_motor2_config(motor2_raw;issues)
  oqlos/api/hardware_mapping_store.py:
    e: _default_path,empty_mapping,_normalize_motor2_runtime_config,normalize_mapping,MappingStore
    MappingStore: __init__(1),file_path(0),storage_backend(0),_load_from_disk(0),save(0),get(0),replace(1),reset(0),parse_text(2),import_text(2),export_text(1)
    _default_path()
    empty_mapping()
    _normalize_motor2_runtime_config(runtime_config)
    normalize_mapping(value)
  oqlos/api/hardware_modbus_routes.py:
    e: hardware_modbus_waveshare_diagnose,hardware_modbus_wizard_plan,hardware_modbus_wizard_probe_isolated,hardware_modbus_wizard_program_isolated
    hardware_modbus_waveshare_diagnose()
    hardware_modbus_wizard_plan()
    hardware_modbus_wizard_probe_isolated(serial_port;baudrates;parities;device_ids;module_role)
    hardware_modbus_wizard_program_isolated(serial_port;current_device_id;new_device_id;new_baudrate;new_parity;confirm_isolated)
  oqlos/api/hardware_modbus_topology.py:
    e: _parse_csv_ints,_modbus_io_device_ids,_modbus_topology_mode,_apply_modbus_topology,_modbus_runtime_serial_ports
    _parse_csv_ints(raw;default)
    _modbus_io_device_ids()
    _modbus_topology_mode()
    _apply_modbus_topology(mode;bus_port;io_port;adc_port)
    _modbus_runtime_serial_ports()
  oqlos/api/hardware_modbus_waveshare.py:
    e: _diagnose_shared_bus_matrix,_merge_unique_text_list,_merge_waveshare_scan_dicts,_read_output_control_modes,_modbus_plugins_healthy,_modbus_health_serial_stale,_build_waveshare_serial_stale_report,_build_waveshare_from_plugin_health,_probe_waveshare_separate,_probe_waveshare_shared_bus,_read_waveshare_io_slave_config,_read_waveshare_adc_slave_config,_resolve_waveshare_ports,_split_hits_by_role,_build_waveshare_diagnose_report
    _diagnose_shared_bus_matrix()
    _merge_unique_text_list(existing;new_items)
    _merge_waveshare_scan_dicts()
    _read_output_control_modes(serial_port;baudrate;parity;device_id;timeout)
    _modbus_plugins_healthy(health)
    _modbus_health_serial_stale(health)
    _build_waveshare_serial_stale_report(health)
    _build_waveshare_from_plugin_health(health)
    _probe_waveshare_separate(io_port;adc_port;target_baud;target_parity;io_device_id;io_ids;adc_id)
    _probe_waveshare_shared_bus(io_port;target_baud;target_parity;io_device_id;adc_id;target_ids)
    _read_waveshare_io_slave_config(io_id;io_hits;io_port;target_baud;target_parity)
    _read_waveshare_adc_slave_config(adc_id;adc_hits;adc_port;target_baud;target_parity)
    _resolve_waveshare_ports(ports)
    _split_hits_by_role(hits)
    _build_waveshare_diagnose_report(health)
  oqlos/api/hardware_modbus_wizard.py:
    e: _modbus_wizard_target_ids,_modbus_wizard_plan,_collect_wizard_serial_candidates,_modbus_wizard_probe_isolated,_wizard_check_already_configured,_wizard_apply_uart_write,_wizard_verify_config,_wizard_build_result,_modbus_wizard_program_isolated
    _modbus_wizard_target_ids()
    _modbus_wizard_plan()
    _collect_wizard_serial_candidates(serial_port)
    _modbus_wizard_probe_isolated(serial_port;baudrates;parities;device_ids;required_roles)
    _wizard_check_already_configured(existing;new_device_id;new_baudrate;line_parity)
    _wizard_apply_uart_write(bus_settings;cur_id;new_id;uart_target;new_baudrate;line_parity;write_uart_config;write_device_address;_uart_register_value)
    _wizard_verify_config(read_device_config;verify_settings;new_device_id;new_baudrate;line_parity)
    _wizard_build_result(writes;verify;verified;new_device_id;new_baudrate;line_parity;serial_port;verify_error)
    _modbus_wizard_program_isolated()
  oqlos/api/hardware_peripherals_routes.py:
    e: read_modbus_adc_raw,rtc_status,rtc_command
    read_modbus_adc_raw()
    rtc_status()
    rtc_command(payload)
  oqlos/api/hardware_platform.py:
    e: _board_model,_is_raspberry_pi_host,_os_release,_in_container,_selected_hardware_platform,_selected_piadc_platform,_classify_platform_type,_detect_runtime_platform
    _board_model()
    _is_raspberry_pi_host()
    _os_release()
    _in_container()
    _selected_hardware_platform()
    _selected_piadc_platform()
    _classify_platform_type(system;is_rpi;in_container;is_wsl)
    _detect_runtime_platform()
  oqlos/api/hardware_probe.py:
    e: _probe_all_hardware,_collect_hardware_diagnostics,_needs_live_scan,_unhealthy_plugin_ids,_modbus_health_is_no_response,_probe_selected_hardware,_modbus_preflight_report,_modbus_repair_guidance
    _probe_all_hardware(ids)
    _collect_hardware_diagnostics()
    _needs_live_scan(health)
    _unhealthy_plugin_ids(health)
    _modbus_health_is_no_response(health_entry)
    _probe_selected_hardware(ids)
    _modbus_preflight_report()
    _modbus_repair_guidance(health)
  oqlos/api/hardware_probe_devices.py:
    e: _local_ads1115_probe_allowed,_scan_usb_devices,_probe_tic249,_probe_dri0050,_probe_i2c_ads1115,_probe_waveshare_rtu,_probe_configured_waveshare_rtu
    _local_ads1115_probe_allowed()
    _scan_usb_devices()
    _probe_tic249(usb_devices)
    _probe_dri0050(usb_devices)
    _probe_i2c_ads1115()
    _probe_waveshare_rtu(probe_fn)
    _probe_configured_waveshare_rtu(role)
  oqlos/api/hardware_registry.py:
  oqlos/api/hardware_runtime.py:
    e: read_cpu_temperature,modbus_adc_unavailable,unavailable_sensor_entry,read_sensor_values,read_sensor,hardware_temperature,read_sensors_batch,hardware_diagnose
    read_cpu_temperature()
    modbus_adc_unavailable(health)
    unavailable_sensor_entry(sensor_id;modbus_adc_health)
    read_sensor_values(sensor_ids)
    read_sensor(sensor_id)
    hardware_temperature()
    read_sensors_batch(sensor_ids)
    hardware_diagnose()
  oqlos/api/hardware_v3.py:
    e: hardware_health_v3,hardware_identify_v3,hardware_proxy_info_v3
    hardware_health_v3()
    hardware_identify_v3(scan)
    hardware_proxy_info_v3()
  oqlos/api/logs.py:
    e: _get_service,get_logs,get_log_stats
    _get_service()
    get_logs(level;function;module;q;environment;limit;offset)
    get_log_stats()
  oqlos/api/main.py:
    e: _app_lifespan,_initialize_runtime_dependencies,_start_oql_transport,_stop_oql_transport,index_page,_serve_static_html,editor_page,panel_alias,navigation_alias,ui_panel_page,ui_navigation_page,_with_query,_redirect_with_query,hardware_status_page,hardware_demo_alias,hardware_restart_alias,map_editor_alias,scenario_files_alias,func_editor_alias,motor_services_alias,nav_alias,status_alias,restart_alias,demo_alias,map_alias,files_alias,functions_alias,oql_panel_alias,hardware_ui_spa,health_check,navigation_index,status,_forward_websocket,hardware_events_websocket_alias,websocket_endpoint,oql_websocket_alias,_parse_server_args,run
    _app_lifespan(_)
    _initialize_runtime_dependencies()
    _start_oql_transport()
    _stop_oql_transport()
    index_page(request)
    _serve_static_html(relative_path;title;missing_message)
    editor_page(request)
    panel_alias(request)
    navigation_alias(request)
    ui_panel_page()
    ui_navigation_page()
    _with_query(path;request)
    _redirect_with_query(path;request)
    hardware_status_page(request)
    hardware_demo_alias(request)
    hardware_restart_alias(request)
    map_editor_alias(request)
    scenario_files_alias(request)
    func_editor_alias(request)
    motor_services_alias(request)
    nav_alias(request)
    status_alias(request)
    restart_alias(request)
    demo_alias(request)
    map_alias(request)
    files_alias(request)
    functions_alias(request)
    oql_panel_alias(request)
    hardware_ui_spa(full_path)
    health_check()
    navigation_index(request)
    status()
    _forward_websocket(websocket;handler)
    hardware_events_websocket_alias(websocket)
    websocket_endpoint(websocket)
    oql_websocket_alias(websocket)
    _parse_server_args()
    run()
  oqlos/api/oql_mqtt.py:
    e: set_oql_controller,get_oql_controller,execute_oql,manage_hardware,oql_ws,_pump_events,OqlExecuteRequest,OqlManageRequest,OqlExecuteResponse
    OqlExecuteRequest:
    OqlManageRequest:
    OqlExecuteResponse:
    set_oql_controller(controller)
    get_oql_controller()
    execute_oql(req)
    manage_hardware(req)
    oql_ws(websocket)
    _pump_events(websocket;queue)
  oqlos/api/peripherals.py:
    e: get_peripheral,update_peripheral,set_peripheral,reset_peripherals
    get_peripheral(peripheral_id)
    update_peripheral(peripheral_id;update_data)
    set_peripheral(peripheral_id;value;mode)
    reset_peripherals()
  oqlos/api/plugins.py:
    e: ensure_plugins_initialized,_plugin_health_http_status,_plugin_health_body,list_plugins,get_plugin_status,get_plugin_info,get_plugin_health,connect_plugin,disconnect_plugin,_resolve_plugin_instance,execute_plugin_command,validate_plugin_configs
    ensure_plugins_initialized()
    _plugin_health_http_status(health)
    _plugin_health_body(health)
    list_plugins()
    get_plugin_status()
    get_plugin_info(plugin_id)
    get_plugin_health(plugin_id)
    connect_plugin(plugin_id;config)
    disconnect_plugin(plugin_id)
    _resolve_plugin_instance(plugin_id)
    execute_plugin_command(plugin_id;command)
    validate_plugin_configs(configs)
  oqlos/api/scenarios.py:
    e: get_scenario,_fetch_raw_from_sources,_compute_slug,_extract_id,_extract_display_fields,_extract_goals,_normalize_scenario_row,fetch_scenarios,_parse_content_to_goals,_ensure_list,_normalize_dsl_payload,_collect_dsl_strings,_parse_goals_from_dsl,_merge_goals_into_scenario,_register_single_dsl_scenario,register_dsl
    get_scenario(scenario_id)
    _fetch_raw_from_sources(sources)
    _compute_slug(item;display_name;sid)
    _extract_id(item)
    _extract_display_fields(item;sid)
    _extract_goals(item)
    _normalize_scenario_row(item)
    fetch_scenarios(source)
    _parse_content_to_goals(content)
    _ensure_list(x)
    _normalize_dsl_payload(payload)
    _collect_dsl_strings(item)
    _parse_goals_from_dsl(goals_dsl;sid;parse_fn)
    _merge_goals_into_scenario(sid;item;parsed_goals)
    _register_single_dsl_scenario(item;parse_fn)
    register_dsl(payload)
  oqlos/api/state.py:
    e: _compose_named_state,_compose_sim_state_list,get_state,_generate_sinusoidal_values,stream_values,get_current_value,get_sim_state,get_variables_alias,fetch_variables,fetch_protocol_steps,_maybe_register_dsl_from_content,_extract_scenario_id,_extract_inline_dsl,_handle_start,_make_state_handler,post_commands
    _compose_named_state()
    _compose_sim_state_list(named_state)
    get_state()
    _generate_sinusoidal_values(param;min_val;max_val;period;interval)
    stream_values(param;min;max;period;interval;demo)
    get_current_value(param)
    get_sim_state()
    get_variables_alias()
    fetch_variables(source)
    fetch_protocol_steps(scenario;source)
    _maybe_register_dsl_from_content(data;scenario_id)
    _extract_scenario_id(data)
    _extract_inline_dsl(data)
    _handle_start(env)
    _make_state_handler(ctrl_fn)
    post_commands(env;background_tasks)
  oqlos/api/utils/__init__.py:
  oqlos/api/utils/execution_ctrl.py:
    e: set_dependencies,_make_getter,_make_exec_handler
    set_dependencies(sm;orch)
    _make_getter(name;label)
    _make_exec_handler(orch_attr;orch_value;target_status)
  oqlos/api/version.py:
  oqlos/config.py:
    e: get_settings,Settings
    Settings:  # Application settings loaded from environment variables and .
    get_settings()
  oqlos/core/__init__.py:
  oqlos/core/_action_motor2.py:
    e: _normalize_motor2_target,_parse_motor2_direction,_parse_motor2_speed_steps,_parse_motor2_positive_int,_parse_motor2_float,_parse_motor2_duration_seconds,_parse_motor2_volume_liters,_parse_motor2_acceleration,_normalize_motor2_value,_parse_prefixed_motor2_setting,_parse_motor2_reciprocating_setting,_parse_motor2_steps,_motor2_speed_raw,_motor2_max_steps_per_second,_motor2_effective_steps_per_second,_motor2_speed_for_duration,_motor2_acceleration_raw,_post_motor2_move_relative,_post_motor2_reciprocate,_post_motor2_stop,_call_motor2_transport,_motor2_reciprocating_state,_motor2_set_state_value,_motor2_state_handler,_motor2_do_stop,_motor2_build_plan,_motor2_step_label,_motor2_do_start,_handle_motor2_reciprocating_setting,_try_exec_motor2_set
    _normalize_motor2_target(target_lower)
    _parse_motor2_direction(value)
    _parse_motor2_speed_steps(value)
    _parse_motor2_positive_int(value)
    _parse_motor2_float(value)
    _parse_motor2_duration_seconds(value)
    _parse_motor2_volume_liters(value)
    _parse_motor2_acceleration(value)
    _normalize_motor2_value(value)
    _parse_prefixed_motor2_setting(normalized)
    _parse_motor2_reciprocating_setting(value)
    _parse_motor2_steps(value)
    _motor2_speed_raw(steps_per_second)
    _motor2_max_steps_per_second()
    _motor2_effective_steps_per_second(steps_per_second)
    _motor2_speed_for_duration(steps;cycles;duration_seconds)
    _motor2_acceleration_raw(steps_per_second;percent)
    _post_motor2_move_relative(direction;steps;speed_raw;acceleration_raw)
    _post_motor2_reciprocate(direction;steps;speed_raw;acceleration_raw;cycles;pause;limit_mode)
    _post_motor2_stop()
    _call_motor2_transport(name;fallback)
    _motor2_reciprocating_state(interp)
    _motor2_set_state_value(interp;state;key;value;label)
    _motor2_state_handler(key;value_fn;label_fn)
    _motor2_do_stop(interp;setting;state)
    _motor2_build_plan(interp;setting;state)
    _motor2_step_label(plan;mode)
    _motor2_do_start(interp;setting;state)
    _handle_motor2_reciprocating_setting(interp;setting)
    _try_exec_motor2_set(interp;target_lower;value)
  oqlos/core/_compare.py:
    e: resolve_compare,resolve_compare_chain
    resolve_compare(left;op;right)
    resolve_compare_chain(node;resolve_value)
  oqlos/core/_cql_tokenizer.py:
    e: _make_args_parser,_make_keyword_parser,_make_method_parser,_make_stripped_field_parser,_make_two_group_parser,_make_target_method_args_parser,_match_first,_parse_condition_value,_try_save,_try_set,_try_condition_range,_try_condition_cmp,_try_if_else,_try_if_block,_try_if_standalone,_try_else_standalone,_try_min_max,_try_val,_try_loop_start,_try_repeat_start,_try_repeat_stop,_try_sample,_try_goto
    _make_args_parser(regex;kind)
    _make_keyword_parser(regex;kind)
    _make_method_parser(regex;kind)
    _make_stripped_field_parser(regex;kind;field)
    _make_two_group_parser(regex;kind;field)
    _make_target_method_args_parser(regex;kind)
    _match_first(line)
    _parse_condition_value(raw_value)
    _try_save(line;stripped)
    _try_set(line;stripped)
    _try_condition_range(line;stripped)
    _try_condition_cmp(line;stripped)
    _try_if_else(line;stripped)
    _try_if_block(line;stripped)
    _try_if_standalone(line;stripped)
    _try_else_standalone(line;stripped)
    _try_min_max(line;stripped)
    _try_val(line;stripped)
    _try_loop_start(line;stripped)
    _try_repeat_start(line;stripped)
    _try_repeat_stop(line;stripped)
    _try_sample(line;stripped)
    _try_goto(line;stripped)
  oqlos/core/_cql_tree_builder.py:
    e: _parse_metadata_kv,_parse_scenario_line,_parse_scenario_attrs,_parse_goal_line,_parse_goal_attrs,_parse_step_line,_parse_action_line,_ensure_goal_for_step,_ensure_step_for_actions
    _parse_metadata_kv(doc;stripped)
    _parse_scenario_line(doc;stripped)
    _parse_scenario_attrs(line;current_scenario)
    _parse_goal_line(stripped;line;indent;current_scenario)
    _parse_goal_attrs(line;current_goal)
    _parse_step_line(line;current_goal)
    _parse_action_line(line;stripped;actions_list;doc;lineno)
    _ensure_goal_for_step(current_goal;current_scenario;line)
    _ensure_step_for_actions(current_step;current_goal)
  oqlos/core/_dsl_helpers.py:
    e: _normalize_quote_syntax,_looks_like_valve_object,_looks_like_pump_object,_looks_like_lung_object,_looks_like_sensor_object,_map_peripheral,_parse_numeric_value,_map_valve_action,_map_pump_action,_map_wait_action,_map_lung_action,_map_action_value
    _normalize_quote_syntax(line)
    _looks_like_valve_object(obj)
    _looks_like_pump_object(obj)
    _looks_like_lung_object(obj)
    _looks_like_sensor_object(obj)
    _map_peripheral(obj)
    _parse_numeric_value(raw)
    _map_valve_action(fn)
    _map_pump_action(fn;obj_raw;line)
    _map_wait_action(fn;obj;obj_raw;line;step_counter)
    _map_lung_action(fn;obj_raw;line)
    _map_action_value(fn;obj;obj_raw;line;step_counter)
  oqlos/core/_firmware_executor.py:
    e: FirmwareExecutor
    FirmwareExecutor: __init__(7),_get_firmware(0),_resolve_gateway_result(2),_is_success(1),resolve_peripheral_id(1),normalize_peripheral_value(2),refresh_sensors_from_firmware(1),execute_firmware_action(2),_execute_plugin_action(2),_execute_legacy_firmware_action(2),exec_set_peripheral(2)  # Executes hardware actions via plugin gateway or legacy firmw
  oqlos/core/_func_resolver.py:
    e: _collect_function_definitions,_extract_func_name,_guard_recursion,_parse_func_call
    _collect_function_definitions(lines)
    _extract_func_name(line;indent)
    _guard_recursion(func_name;call_stack)
    _parse_func_call(line;step_counter;steps;func_defs;indent;call_stack;parse_line_fn)
  oqlos/core/_interpreter_actions.py:
    e: _extract_action_tokens,_drop_command_token,_coerce_expected_value,_compare_values,_oql_quote,_format_set_command,_get_nested_value,_record_failure,_mark_success,_normalize_bool,_lookup_peripheral_state,_mock_api_response,exec_action_task,exec_action_save,parse_wait_secs,exec_action_wait,_do_sleep,exec_action_min_max,exec_action_val,exec_action_log,exec_action_error,exec_action_else,exec_action_sample,_resolve_numeric_token,_func_avg,_func_sum,_func_reduce_or_zero,_func_sub,_func_div,_func_mul,exec_action_func,exec_action_goto,exec_action_api,exec_action_expect,_assert_status,_assert_json,_assert_sensor,_assert_valve,exec_action_assert,exec_action_shell,exec_action_var_set,exec_action_condition,exec_action_if_fail_block,exec_action_if_block,exec_action_loop_block,exec_action_endloop,exec_action_set,_exec_set_wait,exec_action_action
    _extract_action_tokens(text)
    _drop_command_token(act)
    _coerce_expected_value(value)
    _compare_values(actual;operator;expected)
    _oql_quote(value)
    _format_set_command(target;value)
    _get_nested_value(payload;path)
    _record_failure(interp;key;message)
    _mark_success(interp;key)
    _normalize_bool(value)
    _lookup_peripheral_state(interp;target)
    _mock_api_response(interp;endpoint)
    exec_action_task(interp;act)
    exec_action_save(interp;act)
    parse_wait_secs(raw)
    exec_action_wait(interp;act)
    _do_sleep(interp;secs;label)
    exec_action_min_max(interp;act)
    exec_action_val(interp;act)
    exec_action_log(interp;act)
    exec_action_error(interp;act)
    exec_action_else(interp;act)
    exec_action_sample(interp;act)
    _resolve_numeric_token(interp;token)
    _func_avg(values)
    _func_sum(values)
    _func_reduce_or_zero(values;reducer)
    _func_sub(values)
    _func_div(values;interp;target)
    _func_mul(values)
    exec_action_func(interp;act)
    exec_action_goto(interp;act)
    exec_action_api(interp;act)
    exec_action_expect(interp;act)
    _assert_status(interp;act;tokens)
    _assert_json(interp;act;tokens)
    _assert_sensor(interp;act;tokens)
    _assert_valve(interp;act;tokens)
    exec_action_assert(interp;act)
    exec_action_shell(interp;act)
    exec_action_var_set(interp;act)
    exec_action_condition(interp;act)
    exec_action_if_fail_block(interp;act)
    exec_action_if_block(interp;act)
    exec_action_loop_block(interp;act)
    exec_action_endloop(interp;act)
    exec_action_set(interp;act)
    _exec_set_wait(interp;act;value)
    exec_action_action(interp;act)
  oqlos/core/_line_parsers.py:
    e: _parse_task_part,_parse_pump_line,_set_valve_step,_set_pump_step,_set_lung_step,_extract_set_params,_parse_set_line,_parse_inline_task,_parse_action_line,_parse_if_condition
    _parse_task_part(part;step_counter)
    _parse_pump_line(line;step_counter)
    _set_valve_step(peripheral;value_raw;step_counter;line)
    _set_pump_step(peripheral;value_raw;step_counter;line)
    _set_lung_step(peripheral;value_raw;step_counter;line)
    _extract_set_params(normalized_line)
    _parse_set_line(line;step_counter)
    _parse_inline_task(line;step_counter;steps)
    _parse_action_line(line;step_counter;steps)
    _parse_if_condition(line;step_counter;steps)
  oqlos/core/_oql_adapter.py:
    e: _fmt_value,_scenarios_root,_resolve_include,_substitute_args,_load_includes,_lower_include,_lower_call,_lower_set,_lower_get,_lower_wait,_lower_save,_make_lower_minmax,_lower_check,_lower_if_delta,_lower_sample,_lower_log,_lower_error_cmd,_lower_repeat,_cmd_to_actions,_parse_macro_line,_has_anonymous_named_goal,is_flat_oql,oql_doc_to_cql,_split_device_field,parse_flat_oql,_MacroRegistry
    _MacroRegistry: __init__(0),register(1),get(1)  # Collect ``MACRO`` definitions (raw body lines) from the root
    _fmt_value(value;unit)
    _scenarios_root()
    _resolve_include(path;base)
    _substitute_args(raw;args)
    _load_includes(doc;macros;base;seen)
    _lower_include(cmd;macros;visiting)
    _lower_call(cmd;macros;visiting)
    _lower_set(cmd;macros;visiting)
    _lower_get(cmd;macros;visiting)
    _lower_wait(cmd;macros;visiting)
    _lower_save(cmd;macros;visiting)
    _make_lower_minmax(kind)
    _lower_check(cmd;macros;visiting)
    _lower_if_delta(cmd;macros;visiting)
    _lower_sample(cmd;macros;visiting)
    _lower_log(cmd;macros;visiting)
    _lower_error_cmd(cmd;macros;visiting)
    _lower_repeat(cmd;macros;visiting)
    _cmd_to_actions(cmd;macros;visiting)
    _parse_macro_line(raw_line;ln;args)
    _has_anonymous_named_goal(source)
    is_flat_oql(source)
    oql_doc_to_cql(doc)
    _split_device_field(device;index)
    parse_flat_oql(source;filename)
  oqlos/core/_sensor_evaluator.py:
    e: SensorEvaluator
    SensorEvaluator: __init__(3),collect_sensor_constraints(1),seed_sensors_from_conditions(1),auto_mock_sensor(3),compare_sensor(3),get_sensor_value(1)  # Evaluates sensor conditions and manages sensor values.
  oqlos/core/_value_normalizers.py:
    e: ValueNormalizer
    ValueNormalizer: __init__(1),coerce_float(1),_get_pump_flow_full_scale_lpm(0),normalize_pump_power(1),normalize_valve_value(1),normalize_lung_value(1),coerce_generic_peripheral_value(1)  # Normalizes DSL values to hardware-compatible formats.
  oqlos/core/base.py:
    e: StepStatus,StepResult,ScriptResult,VariableStore,InterpreterOutput,BaseInterpreter,EventBridge
    StepStatus:
    StepResult:
    ScriptResult: passed(0),failed(0),summary(0)
    VariableStore: __init__(2),set(3),get(2),has(1),all(1),clear(0),interpolate(1)  # Hierarchical key-value store with interpolation support.
    InterpreterOutput: __init__(3),emit(2),_broadcast_event(2),_emit_status(1),info(1),ok(1),fail(1),warn(1),error(1),step(2),output_yaml(0)  # Collects interpreter output lines for display or testing, an
    BaseInterpreter: __init__(4),parse(2),execute(1),run(2),run_file(1),strip_comments(1)  # Abstract base for language interpreters.
    EventBridge: __init__(1),connect(0),disconnect(0),send_event(2),connected(0)  # Optional WebSocket bridge to DSL Event Server (port 8104).
  oqlos/core/cql_parser.py:
    e: parse_cql,_collect_all_goals,_validate_intervals,validate_cql,_ParseState
    _ParseState: __init__(2),parse(0),_peek_next_significant_indent(0),_flush_pending_inline_if(0),_attach_pending_inline_if(2),_get_line_info(0),_process_line(0),_try_skip_block(2),_try_intervals_block(3),_try_top_level(3),_handle_scenario(1),_handle_scenario_attrs(1),_handle_goal(3),_handle_goal_attrs(1),_handle_current_attrs(4),_handle_step(1),_init_block_stack(0),_add_action_to_parent(1),_append_parent_stack_action(1),_pop_block_with_warning(2),_handle_block_control(1),_handle_else_block(0),_try_handle_structure_levels(3),_handle_inline_if_logic(2),_handle_action_dispatch(2),_try_hierarchy(3)  # Encapsulates the parsing state to simplify the main loop.
    parse_cql(source;filename)
    _collect_all_goals(doc)
    _validate_intervals(doc)
    validate_cql(doc)
  oqlos/core/executor.py:
    e: _resolve_compare,_resolve_name_or_attr,_safe_resolve,safe_eval_condition,ScenarioOrchestrator
    ScenarioOrchestrator: __init__(2),_sanitize_identifier(1),_build_eval_context(0),_sanitize_expression(1),_build_step_plan(1),_execute_goal_steps(7),execute_scenario(4),execute_step(3),_execute_lung_step(2),_execute_valve_step(2),_execute_pump_step(3),_execute_wait_step(2),_execute_sensor_read_step(1),_execute_validate_step(1),update_dependent_sensors(1),validate_goal(1),log_event(2)
    _resolve_compare(node;context)
    _resolve_name_or_attr(node;context)
    _safe_resolve(node;context)
    safe_eval_condition(expr;context)
  oqlos/core/interpreter.py:
    e: CqlInterpreter
    CqlInterpreter: __init__(11),sensor_values(0),sensor_values(1),_firmware(0),_firmware(1),_firmware_url(0),_firmware_url(1),_coerce_float(1),_resolve_peripheral_id(1),_get_pump_flow_full_scale_lpm(0),_normalize_pump_power(1),_normalize_valve_value(1),_normalize_lung_value(1),parse(2),_print_header(2),_collect_warnings(2),_planned_step_results(1),_run_validation_mode(4),_collect_all_goals(1),_execute_single_goal(2),_execute_all_goals(1),_build_script_result(2),execute(1),_execute_step(2),_execute_action(1),_exec_flat_action(1),_do_sleep(2),_normalize_peripheral_value(2),_coerce_generic_peripheral_value(1),_exec_set_peripheral(2),_get_firmware(0),_execute_firmware_action(2),_execute_plugin_action(2),_execute_legacy_firmware_action(2),_refresh_sensors_from_firmware(0),_auto_mock_sensor(3),_compare_sensor(3),_resolve_sensor_value(1),_resolve_delta_sensor_value(1),_resolve_windowed_delta_sensor_value(2),_extract_window_seconds(1),_resolve_condition_rhs(3),_evaluate_resolved_condition(0),_eval_condition_clause(2),_evaluate_inline_condition_expression(1),_tokenize_condition_expression(1),_aggregate_condition_results(2),_apply_connector(3),_finalize_condition_result(4),_evaluate_range_condition(2),_evaluate_condition(1)  # CQL interpreter with three modes:
  oqlos/core/motor2_runtime.py:
    e: _coerce_int,_coerce_float,_pick,motor2_max_steps_per_second,normalize_motor2_runtime_config,motor2_speed_for_duration,motor2_acceleration_raw,motor2_speed_raw,_normalize_motor2_direction,_compute_motor2_cycles,_compute_motor2_speed,build_motor2_reciprocating_plan,Motor2RuntimeConfig,Motor2ReciprocatingPlan
    Motor2RuntimeConfig:
    Motor2ReciprocatingPlan: speed_was_clamped(0)
    _coerce_int(value;default)
    _coerce_float(value;default)
    _pick(source)
    motor2_max_steps_per_second(default)
    normalize_motor2_runtime_config(source)
    motor2_speed_for_duration(steps;cycles;duration_seconds)
    motor2_acceleration_raw(steps_per_second;percent;max_steps_per_second)
    motor2_speed_raw(steps_per_second;max_steps_per_second)
    _normalize_motor2_direction(direction)
    _compute_motor2_cycles(cycles;volume_liters;cycle_volume)
    _compute_motor2_speed(steps;cycles;speed;duration_seconds;max_speed;default_speed)
    build_motor2_reciprocating_plan(config)
  oqlos/core/oql_parser.py:
    e: to_num,_compact_duration,parse_duration,duration_to_ms,_unescape,tokenize,_require,_split_value_unit,_split_set_value_unit,parse_SET,_make_single_field_parser,parse_WAIT,parse_IF_DELTA,parse_CHECK,parse_IF,_make_minmax_parser,parse_SAMPLE,_make_message_parser,_make_call_parser,parse_REPEAT,_line_indent,_expand_repeat_block_lines,_expand_repeat_blocks,_handle_top_level_line,_handle_block_header,_handle_macro_body_line,_handle_set_name,_handle_modifier_cmd,_parse_and_append_command,_validate_oql_version,_check_unnamed_goals,parse_oql,format_doc,OqlCmd,OqlBlock,OqlDoc
    OqlCmd: __repr__(0)  # A single command line inside a block.
    OqlBlock:  # A named block: ``GOAL``, ``CONFIG``, or ``MACRO``.
    OqlDoc: goals(0),configs(0),macros(0),funcs(0)  # Parsed OQL document.
    to_num(raw)
    _compact_duration(token)
    parse_duration(token)
    duration_to_ms(token)
    _unescape(text)
    tokenize(rest)
    _require(tokens;minimum;cmd;ln;shape)
    _split_value_unit(tokens)
    _split_set_value_unit(tokens)
    parse_SET(tokens;ln;raw)
    _make_single_field_parser(cmd;field;required_desc)
    parse_WAIT(tokens;ln;raw)
    parse_IF_DELTA(tokens;ln;raw)
    parse_CHECK(rest;ln;raw)
    parse_IF(rest;ln;raw)
    _make_minmax_parser(cmd)
    parse_SAMPLE(tokens;ln;raw)
    _make_message_parser(cmd)
    _make_call_parser(cmd;field;required_desc)
    parse_REPEAT(tokens;ln;raw)
    _line_indent(line)
    _expand_repeat_block_lines(lines)
    _expand_repeat_blocks(text)
    _handle_top_level_line(doc;raw;line;ln)
    _handle_block_header(doc;line;ln;version_info)
    _handle_macro_body_line(line;ln;current)
    _handle_set_name(line;current)
    _handle_modifier_cmd(doc;line;ln;cmd;rest;current)
    _parse_and_append_command(doc;line;ln;cmd;rest;current)
    _validate_oql_version(doc;version_info)
    _check_unnamed_goals(doc;version_info)
    parse_oql(text;filename)
    format_doc(doc)
  oqlos/core/oql_versioning.py:
    e: first_meaningful_line,extract_declared_version,resolve_oql_version,is_supported_oql_version,OqlVersionInfo
    OqlVersionInfo: is_current(0)  # Resolved OQL version metadata for a source document.
    first_meaningful_line(text)
    extract_declared_version(text)
    resolve_oql_version(text)
    is_supported_oql_version(version)
  oqlos/core/parser.py:
    e: _dispatch_simple_parser,_try_action_or_condition,_parse_runtime_line,parse_dsl_to_goal_with_issues,parse_dsl_to_goal
    _dispatch_simple_parser(kind;line;step_counter;steps)
    _try_action_or_condition(line;normalized_line;step_counter;steps;record_invalid)
    _parse_runtime_line(line;step_counter;steps;func_defs;indent;call_stack;invalid_lines)
    parse_dsl_to_goal_with_issues(dsl;scenario_id)
    parse_dsl_to_goal(dsl;scenario_id)
  oqlos/core/safe_eval.py:
    e: safe_eval,_eval_constant,_eval_name,_eval_unary_op,_eval_bin_op,_eval_compare,_eval_bool_op,_eval_call,_eval_if_exp,_eval_node,SafeEvalError
    SafeEvalError:  # Raised when an expression cannot be safely evaluated.
    safe_eval(expr;context)
    _eval_constant(node;ctx)
    _eval_name(node;ctx)
    _eval_unary_op(node;ctx)
    _eval_bin_op(node;ctx)
    _eval_compare(node;ctx)
    _eval_bool_op(node;ctx)
    _eval_call(node;ctx)
    _eval_if_exp(node;ctx)
    _eval_node(node;ctx)
  oqlos/core/state.py:
    e: StateManager
    StateManager: __init__(0),initialize_peripherals(0),broadcast_event(1)
  oqlos/dsl/__init__.py:
  oqlos/dsl/schema.py:
    e: _normalize_name_list,_build_inferred_object_function_map,_build_inferred_param_unit_map,_merge_binding_map,_merge_object_function_map,_merge_param_unit_map,get_default_dsl_schema,DslDialect,DslItem,DslFunctionBinding,DslParamUnitBinding,DslSchema
    DslDialect:  # Supported DSL dialect metadata.
    DslItem:  # A reusable schema item visible to editor clients.
    DslFunctionBinding:  # Object to function relationship used by visual builders.
    DslParamUnitBinding:  # Param to unit relationship used by visual builders.
    DslSchema:  # Complete editor schema shared by GUI and runtime tooling.
    _normalize_name_list(values)
    _build_inferred_object_function_map(objects;functions)
    _build_inferred_param_unit_map(params;units)
    _merge_binding_map(explicit_map;inferred_map;binding_cls;field)
    _merge_object_function_map(explicit_map;inferred_map)
    _merge_param_unit_map(explicit_map;inferred_map)
    get_default_dsl_schema()
  oqlos/errors/__init__.py:
  oqlos/errors/catalog.py:
    e: get_issue_definition,matches_known_pattern,all_codes,RepairTemplate,IssueDefinition,CodePattern
    RepairTemplate:
    IssueDefinition:
    CodePattern: matches(1)  # A templated code family (e.g. one code per adapter id), not 
    get_issue_definition(code)
    matches_known_pattern(code)
    all_codes()
  oqlos/errors/exceptions.py:
    e: OqlosError
    OqlosError: __init__(1),to_issue(0)
  oqlos/errors/fastapi_integration.py:
    e: install_oqlos_error_handler
    install_oqlos_error_handler(app)
  oqlos/errors/repair_commit.py:
    e: is_eligible_for_automated_commit,format_repair_commit_message
    is_eligible_for_automated_commit(action)
    format_repair_commit_message()
  oqlos/hardware/__init__.py:
  oqlos/hardware/artificial_lung.py:
    e: _clamp_lpm,_command_response,get_peripheral_status,_lung_cmd_set_lpm,_lung_cmd_lung_start,_lung_cmd_lung_stop,_lung_cmd_lung_status,_lung_cmd_lung_cycle,_lung_cmd_emergency_stop,execute_command
    _clamp_lpm(value)
    _command_response(ok;command;result)
    get_peripheral_status(gateway)
    _lung_cmd_set_lpm(params;gateway)
    _lung_cmd_lung_start(params;gateway)
    _lung_cmd_lung_stop(params;gateway)
    _lung_cmd_lung_status(params;gateway)
    _lung_cmd_lung_cycle(params;gateway)
    _lung_cmd_emergency_stop(params;gateway)
    execute_command(command;args;gateway)
  oqlos/hardware/client/__init__.py:
  oqlos/hardware/client/adc.py:
    e: adc_sensor_alias,normalize_adc_read_result,normalize_adc_read_all_result
    adc_sensor_alias(raw_sensor_id)
    normalize_adc_read_result(result;requested_sensor_id)
    normalize_adc_read_all_result(result)
  oqlos/hardware/client/autorepair.py:
    e: plugin_needs_repair,modbus_plugins_need_repair,_plugin_repair_reasons,_no_response_reasons,analyze_repair_needs,modbus_exclusive_scan_recommended,overall_stack_healthy,build_summary
    plugin_needs_repair(plugin_id;entry)
    modbus_plugins_need_repair(identify)
    _plugin_repair_reasons(health)
    _no_response_reasons(diagnostics)
    analyze_repair_needs(identify)
    modbus_exclusive_scan_recommended(identify)
    overall_stack_healthy(identify)
    build_summary()
  oqlos/hardware/client/config.py:
    e: float_from_env,int_from_env,_value_from_env,candidate_oqlos_bases,OqlosHardwareProxyConfig
    OqlosHardwareProxyConfig: __post_init__(0),from_env(2)
    float_from_env(env;key;default)
    int_from_env(env;key;default)
    _value_from_env(env;key;default;caster)
    candidate_oqlos_bases(api_base)
  oqlos/hardware/client/constants.py:
  oqlos/hardware/client/errors.py:
    e: is_oqlos_unavailable,oqlos_error_detail,HardwareProxyError
    HardwareProxyError: __init__(2)
    is_oqlos_unavailable(exc)
    oqlos_error_detail(exc)
  oqlos/hardware/client/http_helpers.py:
    e: safe_response_payload,response_error_message
    safe_response_payload(response)
    response_error_message(payload)
  oqlos/hardware/client/identify_enrich.py:
    e: _platform_serial_ports,count_detected_adapters,enrich_identify_payload,enrich_hardware_identify
    _platform_serial_ports(platform)
    count_detected_adapters(adapters)
    enrich_identify_payload(payload)
    enrich_hardware_identify(payload)
  oqlos/hardware/client/identify_enrich_adapters.py:
    e: health_message,enrich_disabled,enrich_motor_tic249,enrich_motor_dri0050,enrich_modbus_adapter,enrich_by_device_id,enrich_adapter_entry,adapter_status_modbus,adapter_status_tic249,adapter_status_from_health
    health_message(health;probe)
    enrich_disabled(adapter;message)
    enrich_motor_tic249(adapter;probe;status;lowered;adapter_visible)
    enrich_motor_dri0050(adapter;probe;status;lowered)
    enrich_modbus_adapter(adapter;probe;status;lowered;adapter_visible)
    enrich_by_device_id(hw_id;adapter;probe;status;lowered;adapter_visible)
    enrich_adapter_entry(adapter)
    adapter_status_modbus(hw_id;status;lowered;probe)
    adapter_status_tic249(hw_id;status;lowered;probe)
    adapter_status_from_health(hw_id;health_entry)
  oqlos/hardware/client/identify_enrich_modbus_io.py:
    e: parse_csv_ints,ids_from_preflight,modbus_io_instance_ids,expand_modbus_io_instances
    parse_csv_ints(raw)
    ids_from_preflight(payload)
    modbus_io_instance_ids(payload)
    expand_modbus_io_instances(adapters;payload)
  oqlos/hardware/client/modbus_repair.py:
    e: _env,_is_separate_adapters,_adapter_ports,_augment_no_response_from_health,_build_diagnose_cmd,_build_safety_hints,rewrite_modbus_repair
    _env(name;default)
    _is_separate_adapters(payload)
    _adapter_ports(payload)
    _augment_no_response_from_health(no_response;health)
    _build_diagnose_cmd(target;io_port;adc_port)
    _build_safety_hints(no_response;health;existing_safety)
    rewrite_modbus_repair(payload)
  oqlos/hardware/client/platform.py:
    e: is_raspberry_pi,is_docker,get_default_oqlos_api_base
    is_raspberry_pi()
    is_docker()
    get_default_oqlos_api_base()
  oqlos/hardware/client/proxy.py:
    e: _is_unsuccessful_result,OqlosHardwareProxy
    OqlosHardwareProxy: __init__(1),candidate_bases(0),proxy_info(0),close(0),_get_client(0),_proxy_oqlos(1),_proxy_oqlos_request(2),_degraded_oqlos_payload(1),health(0),identify(0),peripheral_status(1),diagnostic_command(3),_motor_api_bases(0),_fetch_dri0050_motor_health_hint(0),_is_useless_motor_health_hint(1),_should_enrich_motor_dri0050_failure(1),_motor_dri0050_remediation(2),_enrich_motor_dri0050_failure(1),_load_peripheral_status(1),_load_modbus_io_status(1),_load_adc_status(0),_load_simple_hardware_status(1),_load_plugin_status(2),_execute_diagnostic_command(5),_unavailable_health_payload(2),_unavailable_identify_payload(1),_unavailable_peripheral_payload(3),_unavailable_command_payload(6)
    _is_unsuccessful_result(result)
  oqlos/hardware/client/resolvers.py:
    e: normalize_modbus_valve_id,resolve_modbus_target,resolve_pump_target,resolve_artificial_lung_target,resolve_lung_target,resolve_modbus_adc_target,resolve_rtc_target,resolve_diagnostic_target,_coalesce_error_message,extract_command_failure
    normalize_modbus_valve_id(raw)
    resolve_modbus_target(command;args)
    resolve_pump_target(command;args)
    resolve_artificial_lung_target(command;args)
    resolve_lung_target(command;args)
    resolve_modbus_adc_target(command;args)
    resolve_rtc_target(command;args)
    resolve_diagnostic_target(peripheral;command;args)
    _coalesce_error_message()
    extract_command_failure(result)
  oqlos/hardware/client/tic249_arg_contract.py:
    e: canonicalize_motor2_runtime_key,tic249_runtime_args_from_config
    canonicalize_motor2_runtime_key(key)
    tic249_runtime_args_from_config(runtime_config)
  oqlos/hardware/client/tic249_arg_helpers.py:
    e: tic249_arg
    tic249_arg(args;snake;camel;default)
  oqlos/hardware/client/tic249_command_mapping.py:
    e: map_lung_or_reciprocate,map_tic249_command
    map_lung_or_reciprocate(command;args)
    map_tic249_command(command;args)
  oqlos/hardware/client/tic249_error_messages.py:
    e: extract_position,command_error_message,generic_failure_hint,command_failure,plugin_unavailable_error,normalize_target_state
    extract_position(payload)
    command_error_message(result)
    generic_failure_hint(result)
    command_failure(result)
    plugin_unavailable_error(exc)
    normalize_target_state(command;result)
  oqlos/hardware/client/tic249_extended.py:
    e: _plugin_payload,_execute,_handle_move_relative_command,_try_disable_fallback,_try_sidecar_reciprocate,_handle_hardware_proxy_error,run_extended_motor_tic249_command
    _plugin_payload(command;params)
    _execute(proxy;command;params)
    _handle_move_relative_command(hardware_proxy;command_args)
    _try_disable_fallback(hardware_proxy;command)
    _try_sidecar_reciprocate(command;plugin_command;params)
    _handle_hardware_proxy_error(hardware_proxy;command;plugin_command;params;exc)
    run_extended_motor_tic249_command(hardware_proxy;command;args)
  oqlos/hardware/client/tic249_motion_params.py:
    e: normalize_motion_params,stroke_steps,apply_reciprocate_direction,_resolve_reciprocate_speed,_resolve_reciprocate_ramp,build_reciprocate_params
    normalize_motion_params(args)
    stroke_steps(args;default)
    apply_reciprocate_direction(params;args)
    _resolve_reciprocate_speed(args)
    _resolve_reciprocate_ramp(args)
    build_reciprocate_params(args)
  oqlos/hardware/client/tic249_rig_direction.py:
    e: rig_direction_to_plugin,apply_rig_direction_to_plugin_params
    rig_direction_to_plugin(direction)
    apply_rig_direction_to_plugin_params(params;args)
  oqlos/hardware/client/tic249_sidecar_client.py:
    e: tic249_sidecar_base_urls,tic249_sidecar_base_url,sidecar_reciprocate_preferred,sidecar_reports_deenergized,attempt_reciprocate_via_sidecar,direct_sidecar_deenergize,lung_disable_fallback,disable_success_response,attempt_disable_deenergize
    tic249_sidecar_base_urls()
    tic249_sidecar_base_url()
    sidecar_reciprocate_preferred()
    sidecar_reports_deenergized()
    attempt_reciprocate_via_sidecar(params)
    direct_sidecar_deenergize(command)
    lung_disable_fallback(hardware_proxy;command)
    disable_success_response(command;fallback_result;fallback_name)
    attempt_disable_deenergize(hardware_proxy;command)
  oqlos/hardware/config_paths.py:
    e: resolve_oqlos_config_path
    resolve_oqlos_config_path(config_path)
  oqlos/hardware/config_schema.py:
    e: get_hardware_config,register_hardware_config,load_config_from_yaml,build_dynamic_schema_models,UnitType
    UnitType:  # Standard unit types for hardware parameters.
    get_hardware_config(device_id)
    register_hardware_config(config)
    load_config_from_yaml(config_path)
    build_dynamic_schema_models(config_path)
  oqlos/hardware/control_proxy.py:
    e: OqlosHardwareProxy
    OqlosHardwareProxy: __init__(1)  # OqlOS-local proxy label for unavailable identify payloads.
  oqlos/hardware/diagnosis.py:
    e: _report_device_status,_adapter_index,_build_stack_snapshot,_resolve_host_recover,build_diagnosis_report,_should_include_host_action,_host_actions_from_report,_recover_targets,_should_force_sidecar_restart,_repair_sidecar_if_needed,execute_safe_recover
    _report_device_status(report;plugin_id)
    _adapter_index(identify)
    _build_stack_snapshot(health)
    _resolve_host_recover()
    build_diagnosis_report(identify)
    _should_include_host_action(action;seen;saw_make;motor_only;failed)
    _host_actions_from_report(report)
    _recover_targets(report;health)
    _should_force_sidecar_restart(entry)
    _repair_sidecar_if_needed(plugin_id;ensure_sidecar;targets;health_before;repairs)
    execute_safe_recover(gateway;report)
  oqlos/hardware/diagnosis_device_actions.py:
    e: add_modbus_device_actions,_sidecar_recovery_actions,add_tic249_device_actions,add_dri0050_device_actions,diagnose_plugin_devices,diagnose_barcode_scanner,build_report_global_actions
    add_modbus_device_actions(dev;plugin_id;status;msg;platform)
    _sidecar_recovery_actions(device_id)
    add_tic249_device_actions(dev;status;msg;host_recover)
    add_dri0050_device_actions(dev;status;msg;host_recover)
    diagnose_plugin_devices(health;adapters;platform;topology;host_recover)
    diagnose_barcode_scanner(adapters)
    build_report_global_actions(modbus_bad;motors_bad;c2004_root;host_recover)
  oqlos/hardware/diagnosis_plugin_health.py:
    e: health_map,is_stale_hardware_message,is_stale_hardware_entry,plugin_is_healthy,plugin_needs_repair,modbus_plugins_need_repair,message_lower,infer_status
    health_map(identify)
    is_stale_hardware_message(message)
    is_stale_hardware_entry(entry)
    plugin_is_healthy(entry)
    plugin_needs_repair(plugin_id;entry)
    modbus_plugins_need_repair(identify)
    message_lower(entry)
    infer_status(plugin_id;entry)
  oqlos/hardware/diagnosis_types.py:
    e: action_dict,report_to_dict,DiagnosisAction,DeviceDiagnosis,DiagnosisReport
    DiagnosisAction:
    DeviceDiagnosis:
    DiagnosisReport:
    action_dict(action)
    report_to_dict(report)
  oqlos/hardware/discovery.py:
    e: _ensure_local_pimodbus_on_path,_probe_waveshare,_probe_waveshare_role,_build_waveshare_probe
    _ensure_local_pimodbus_on_path()
    _probe_waveshare(probe_fn)
    _probe_waveshare_role(role;preferred_port;preferred_baud;preferred_parity;preferred_device_id;timeout)
    _build_waveshare_probe(role;doc)
  oqlos/hardware/drivers/__init__.py:
  oqlos/hardware/drivers/gpio.py:
    e: GpioDriver
    GpioDriver: __init__(0),connect(1),read(1),write(2),discover(0),health_check(0),disconnect(0)  # Driver for direct GPIO control.
  oqlos/hardware/drivers/mqtt.py:
    e: MqttDriver
    MqttDriver: __init__(0),connect(1),_on_connect(4),_on_message(3),read(1),write(2),discover(0),health_check(0),disconnect(0)  # MQTT driver for the Hardware Abstraction Layer.
  oqlos/hardware/drivers/spi.py:
    e: SpiDriver
    SpiDriver: __init__(0),connect(1),read(1),write(2),discover(0),health_check(0),disconnect(0)  # SPI driver for HAL.
  oqlos/hardware/firmware_adapter.py:
    e: _first_nonempty,_extract_failure_message,_parse_numeric,FirmwareAdapter
    FirmwareAdapter: __init__(3),_get_client(0),close(0),_get_lung_motor_url(0),is_available(0),_resolve_peripheral(1),_raise_if_rejected(2),set_peripheral(2),pump_off(1),pump_set(2),valve_open(1),valve_close(1),reset_peripherals(0),read_state(0),read_sensor(1),read_all_sensors(0),_resolve_dispatch_target(3),_handle_lung_action(4),_handle_valve_action(4),_handle_pump_action(4),_handle_common_action(3),_execute_method(4),dispatch_action(3)  # HTTP bridge between CQL interpreter and firmware simulator.
    _first_nonempty(data)
    _extract_failure_message(data)
    _parse_numeric(s)
  oqlos/hardware/gateway.py:
    e: _PiAdcAdapter,_DRI0050MotorAdapter,_Tic249LungAdapter,_ModbusAdapter,HardwareGateway
    _PiAdcAdapter: __init__(1),read_channel(1),read_sensor(1)  # Reads pressure / analog sensors via piadc REST API (ADS1115)
    _DRI0050MotorAdapter: __init__(1),set_speed(1),_stop(0),status(0)  # Controls the pump motor via rpi-motor-DRI0050 REST API (DFRo
    _Tic249LungAdapter: __init__(1),reciprocate(4),stop(0),move(2),energize(1),status(0)  # Controls the artificial lung stepper motor via rpi-motor-tic
    _ModbusAdapter: __init__(5),set_coil(2),_set_coil_rtu(3),_set_coil_tcp(2),set_valve(2)  # Controls valves via Modbus RTU over RS485 (Waveshare Modbus 
    HardwareGateway: __init__(1),is_real(0),set_valve(2),set_pump(1),read_sensor(1),set_lung(4),stop_lung(0),health(0)  # Single entry-point for all physical hardware I/O.
  oqlos/hardware/gateway_http.py:
    e: get_json,post_json
    get_json(base_url;path)
    post_json(base_url;path;payload)
  oqlos/hardware/health_status.py:
    e: health_status_is_ok
    health_status_is_ok(raw_status)
  oqlos/hardware/hui_actions.py:
    e: list_hui_actions
    list_hui_actions()
  oqlos/hardware/hui_artificial_lung.py:
    e: _run_tic249_reciprocate,start_hui_artificial_lung,stop_hui_artificial_lung
    _run_tic249_reciprocate(gateway)
    start_hui_artificial_lung(gateway)
    stop_hui_artificial_lung(gateway)
  oqlos/hardware/hui_hold.py:
    e: _normalize_hui_profile_key,_coerce_valve_ids,_coerce_float,_profile_from_map_action,_mapped_hui_hold_profiles,get_hui_hold_profiles,_success,_operation,_set_valve,_set_pump,_set_pump_best_effort,shutdown_all_hui_hardware,_hold_start_failure,_engage_hold_valves,_engage_hold_pump_if_needed,start_hui_hold,stop_hui_hold
    _normalize_hui_profile_key(key)
    _coerce_valve_ids(value)
    _coerce_float(value)
    _profile_from_map_action(binding)
    _mapped_hui_hold_profiles()
    get_hui_hold_profiles()
    _success(value)
    _operation(name;ok)
    _set_valve(gateway;valve_id;value)
    _set_pump(gateway;power_pct)
    _set_pump_best_effort(gateway;power_pct)
    shutdown_all_hui_hardware(gateway)
    _hold_start_failure(hold_key)
    _engage_hold_valves(gateway;valve_ids)
    _engage_hold_pump_if_needed(gateway;pump_pct)
    start_hui_hold(gateway;key)
    stop_hui_hold(gateway;key)
  oqlos/hardware/hui_lung_recipe.py:
    e: build_hui_lung_reciprocate_args,_mapped_hui_lung_action_body,_int_from_body,_float_from_body,_text_from_body,get_hui_lung_valve_id,get_hui_lung_reciprocate_args
    build_hui_lung_reciprocate_args()
    _mapped_hui_lung_action_body()
    _int_from_body(body)
    _float_from_body(body)
    _text_from_body(body)
    get_hui_lung_valve_id()
    get_hui_lung_reciprocate_args()
  oqlos/hardware/identify_enrichment.py:
    e: enrich_identify_payload
    enrich_identify_payload(payload)
  oqlos/hardware/modbus_identify.py:
    e: _usb_blob,_is_modbus_candidate,_device_to_candidate,collect_modbus_serial_candidates,_infer_modbus_serial_port,enrich_platform_modbus_ports,enrich_modbus_serial_hints,enrich_modbus_identify
    _usb_blob(device)
    _is_modbus_candidate(device)
    _device_to_candidate(device)
    collect_modbus_serial_candidates(diagnostics)
    _infer_modbus_serial_port(platform)
    enrich_platform_modbus_ports(payload)
    enrich_modbus_serial_hints(payload)
    enrich_modbus_identify(payload)
  oqlos/hardware/peripheral_mapping.py:
    e: resolve_target_to_plugin,register_custom_mapping,get_all_mappings,generate_dynamic_valve_mappings
    resolve_target_to_plugin(target)
    register_custom_mapping(target;plugin_id)
    get_all_mappings()
    generate_dynamic_valve_mappings(max_valve_count)
  oqlos/hardware/plugin_gateway.py:
    e: PluginHardwareGateway
    PluginHardwareGateway: __init__(2),_load_hardware_schema(1),_parse_plugin_configs(1),_apply_env_overrides(0),_apply_plugin_enable_env_overrides(0),_apply_shared_modbus_bus_env_overrides(0),_apply_modbus_env_overrides(2),modbus_preflight_report(0),_log_modbus_preflight(0),ensure_initialized(0),_get_or_connect_plugin(1),_initialize_plugins(0),is_real(0),set_valve(2),set_pump(1),read_sensor(1),set_lung_result(4),set_lung(4),_execute_lung_bool_command(2),stop_lung(0),disable_lung(0),reload_configs(1),health(0)  # Simplified hardware gateway using plugin architecture.
  oqlos/hardware/plugins/__init__.py:
  oqlos/hardware/plugins/_rtu_serial.py:
    e: serial_error_is_stale,reopen_rtu_after_stale,rtu_timeout,rtu_device_id
    serial_error_is_stale(exc)
    reopen_rtu_after_stale(plugin;exc)
    rtu_timeout(config)
    rtu_device_id(config)
  oqlos/hardware/plugins/_shared.py:
    e: http_health_check,not_connected_health,health_check_exception,_error_health,http_disconnect,disconnect_http_plugin
    http_health_check(client;base_url;label)
    not_connected_health(label)
    health_check_exception(exc)
    _error_health(message)
    http_disconnect(client;label)
    disconnect_http_plugin(plugin;label)
  oqlos/hardware/plugins/base.py:
    e: get_pluggy_manager,dynamic_peripheral_model,dynamic_plugin_schema_models,PluginStatus,HardwareDriverSpec,ScaleConfig,ConversionConfig,PeripheralConfig,PluginConfig,OqlosConfigDocument,PluginHealth,HardwarePlugin
    PluginStatus:  # Status of a hardware plugin.
    HardwareDriverSpec: set_peripheral(3),read_sensor(1),get_driver_status(0)  # Pluggy hookspec for hardware drivers.
    ScaleConfig: contains(1),clamp(1)  # Scale / range definition for a peripheral parameter.
    ConversionConfig:  # Describes how to convert a logical value to a hardware value
    PeripheralConfig: validate_value(1),convert_value(1)  # Configuration for a single peripheral (sensor / actuator).
    PluginConfig: validate(0),get_peripheral(1)  # Standardized configuration schema for hardware plugins.
    OqlosConfigDocument: _inject_plugin_ids(2)  # Top-level ``oqlos.yaml`` schema.
    PluginHealth:  # Health check result for a hardware plugin.
    HardwarePlugin: __init__(1),connect(0),disconnect(0),health_check(0),validate_config(0),execute_command(2),get_capabilities(1),status(0),is_connected(0),__repr__(0)  # Base interface for hardware integration plugins.
    get_pluggy_manager()
    dynamic_peripheral_model(peripheral)
    dynamic_plugin_schema_models(config)
  oqlos/hardware/plugins/lung.py:
    e: LungPlugin
    LungPlugin: __init__(1),validate_config(0),connect(0),disconnect(0),_health_check_http(0),health_check(0),_runtime_status(0),_runtime_block_reason(1),_handle_reciprocate_http(1),_handle_reciprocate_usb(1),_handle_stop_http(0),_handle_stop_usb(0),_handle_move_http(1),_handle_move_usb(1),_handle_energize_http(1),_handle_energize_usb(1),_handle_status_http(0),_handle_status_usb(0),execute_command(2),get_capabilities(1)  # Plugin for Pololu Tic T249 stepper motor (artificial lung).
  oqlos/hardware/plugins/modbus.py:
    e: ModbusPlugin
    ModbusPlugin: __init__(1),_validate_rtu_params(1),_validate_tcp_params(1),validate_config(0),connect(0),disconnect(0),_health_check_rtu(0),_health_check_tcp(0),health_check(0),_execute_set_coil(1),_execute_set_valve(1),execute_command(2),_rtu_timeout(0),_rtu_call(1),_device_id(0),get_capabilities(1)  # Plugin for Waveshare Modbus RTU IO 8CH valve controller.
  oqlos/hardware/plugins/modbus_adc.py:
    e: _resolve_channel,_modbus_error,ModbusAdcPlugin
    ModbusAdcPlugin: __init__(1),validate_config(0),connect(0),disconnect(0),health_check(0),execute_command(2),_read_registers(0),_format_channels(1),_format_channel(2),_peripheral_for_channel(1),_rtu_timeout(0),_device_id(0),_config_int(3),_read_address(0),_read_count(0),get_capabilities(1)  # Plugin for Waveshare Modbus RTU Analog Input 8CH.
    _resolve_channel(raw)
    _modbus_error(result)
  oqlos/hardware/plugins/motor.py:
    e: MotorPlugin
    MotorPlugin: __init__(1),validate_config(0),connect(0),disconnect(0),_health_check_http(0),_health_check_modbus_rtu(0),health_check(0),_base_url_is_local(0),_validate_power_pct(1),_handle_set_speed_http(2),_handle_set_speed_cli(2),_handle_set_speed_modbus(2),_handle_stop_http(1),_handle_stop_cli(1),_handle_stop_modbus(1),_handle_status_http(1),_handle_status_cli(1),_handle_status_modbus(1),execute_command(2),get_capabilities(1)  # Plugin for DFRobot DRI0050 PWM motor driver.
  oqlos/hardware/plugins/motor_http_handlers.py:
    e: motor_http_request,motor_cli_command
    motor_http_request(client;base_url)
    motor_cli_command(cmd_args)
  oqlos/hardware/plugins/motor_modbus_handlers.py:
    e: duty_pct_to_register,connect_modbus_bus,modbus_health_check,modbus_set_speed,modbus_stop,modbus_status
    duty_pct_to_register(power_pct)
    connect_modbus_bus()
    modbus_health_check(bus)
    modbus_set_speed(bus)
    modbus_stop(bus)
    modbus_status(bus)
  oqlos/hardware/plugins/piadc.py:
    e: _is_raspberry_pi_host,_requires_remote_rpi_hint,_resolve_sensor_channel,PiadcPlugin
    PiadcPlugin: __init__(1),validate_config(0),connect(0),disconnect(0),health_check(0),_read_blocker(0),execute_command(2),get_capabilities(1)  # Plugin for piADC (ADS1115) 16-bit ADC sensor.
    _is_raspberry_pi_host()
    _requires_remote_rpi_hint(base_url;exc)
    _resolve_sensor_channel(sensor_id)
  oqlos/hardware/plugins/plugin_http_handlers.py:
    e: http_post_command,http_get_command
    http_post_command(client;base_url;path)
    http_get_command(client;base_url;path)
  oqlos/hardware/plugins/registry.py:
    e: PluginRegistry
    PluginRegistry: register(2),unregister(2),get_plugin_class(2),list_plugins(1),create_instance(3),get_instance(2),connect_plugin(3),disconnect_plugin(2),health_check(2),health_check_all(1),validate_all_configurations(2),get_status(1),discover_entry_point_plugins(2),load_configs_from_yaml(2)  # Central registry for hardware plugins.
  oqlos/hardware/protocol.py:
    e: ProtocolType,HardwareProtocol
    ProtocolType:  # Supported hardware communication protocols.
    HardwareProtocol: connect(1),read(1),write(2),discover(0),health_check(0),disconnect(0)  # Base class for all hardware drivers.
  oqlos/hardware/registry.py:
    e: DriverRegistry
    DriverRegistry: register(2),create(2),list_registered(1)  # Registry for hardware drivers. Allows mapping ProtocolType t
  oqlos/hardware/rtc_probe.py:
    e: is_rtc_hardware_enabled,get_pirtc_base_url,_pirtc_request_sync,build_rtc_peripheral_status,run_rtc_command,build_rtc_adapter_entry,enrich_rtc_adapter
    is_rtc_hardware_enabled()
    get_pirtc_base_url()
    _pirtc_request_sync(method;path)
    build_rtc_peripheral_status()
    run_rtc_command(command;args)
    build_rtc_adapter_entry()
    enrich_rtc_adapter(payload)
  oqlos/hardware/scanner_probe.py:
    e: _join_blob,_match_blob,_is_likely_scanner_usb_blob,_is_likely_scanner_input,_usb_product_blob,_canonical_match_key,_match_priority,_merge_matches,_scan_lsusb_matches,_scan_input_matches,_scan_diagnostics_usb_matches,resolve_scanner_presence,build_scanner_adapter_entry,enrich_scanner_adapter
    _join_blob(source;keys)
    _match_blob(item)
    _is_likely_scanner_usb_blob(blob)
    _is_likely_scanner_input(name;handlers)
    _usb_product_blob(device)
    _canonical_match_key(item)
    _match_priority(item)
    _merge_matches()
    _scan_lsusb_matches()
    _scan_input_matches()
    _scan_diagnostics_usb_matches(diagnostics)
    resolve_scanner_presence(diagnostics)
    build_scanner_adapter_entry(diagnostics)
    enrich_scanner_adapter(payload)
  oqlos/hardware/sidecar_control.py:
    e: _modbus_serial_candidates,resolve_dri0050_serial,_dri0050_paths,_poll_until_ok,_dri0050_probe_ok,_http_sidecar_poll,_http_sidecar_listening,_http_sidecar_healthy,_run_cmd,_free_api_port,ensure_dri0050_sidecar,_tic249_status,_tic249_connect,_tic249_listening_ok,_tic249_connected_ok,_http_tic249_listening,_http_tic249_connected,ensure_tic249_sidecar
    _modbus_serial_candidates()
    resolve_dri0050_serial(configured)
    _dri0050_paths()
    _poll_until_ok(check)
    _dri0050_probe_ok()
    _http_sidecar_poll()
    _http_sidecar_listening()
    _http_sidecar_healthy()
    _run_cmd()
    _free_api_port(port)
    ensure_dri0050_sidecar()
    _tic249_status(timeout)
    _tic249_connect(timeout)
    _tic249_listening_ok()
    _tic249_connected_ok()
    _http_tic249_listening()
    _http_tic249_connected()
    ensure_tic249_sidecar()
  oqlos/hardware/stack_snapshot.py:
    e: _lazy_hardware_api,_get_modbus_preflight,_build_recommended_actions,build_hardware_stack_snapshot
    _lazy_hardware_api()
    _get_modbus_preflight(gateway)
    _build_recommended_actions(stale;health_payload)
    build_hardware_stack_snapshot(health)
  oqlos/hardware/tic249_units.py:
    e: steps_per_second_to_raw,raw_acceleration_for_ramp
    steps_per_second_to_raw(value)
    raw_acceleration_for_ramp(raw_speed;ramp_seconds)
  oqlos/hardware/transport/__init__.py:
  oqlos/hardware/transport/manage_ops.py:
    e: run_manage_verb,_resolve,list_manage_verbs
    run_manage_verb(verb;args)
    _resolve(verb)
    list_manage_verbs()
  oqlos/hardware/transport/manage_ops_diagnostic.py:
    e: _success_from_result,run_modbus_io_valve,run_pump_diagnostic,_resolve_move_relative_params,run_motor_tic249_extended,_extract_diagnostic_ids,_extract_params,_route_tic249_lung_command,_route_diagnostic_command,run_diagnostic_command
    _success_from_result(result)
    run_modbus_io_valve(hw;command;params)
    run_pump_diagnostic(command;params)
    _resolve_move_relative_params(params)
    run_motor_tic249_extended(command;params)
    _extract_diagnostic_ids(a)
    _extract_params(a)
    _route_tic249_lung_command(command;hw)
    _route_diagnostic_command(plugin_id;command;params;hw;pl)
    run_diagnostic_command(a)
  oqlos/hardware/transport/manage_ops_usb.py:
    e: usb_list,pi_diagnostics,usb_reset
    usb_list(_a)
    pi_diagnostics(_a)
    usb_reset(a)
  oqlos/hardware/transport/mqtt_oql_bridge.py:
    e: build_topics,_make_client,Topics,_JsonEnvelopeMixin,OqlRequest,OqlResponse,_PahoAsyncClient,OqlMqttController,OqlMqttAgent
    Topics: request(0),response_base(0),response_wildcard(0),events(0),status(0),response_for(1)  # Resolved topic strings for one node.
    _JsonEnvelopeMixin: to_json(0)  # Shared to_json() for versioned MQTT envelope dataclasses.
    OqlRequest: from_json(2)  # A request to execute on a remote node.
    OqlResponse: from_json(2)  # The result of executing OQL on a remote node.
    _PahoAsyncClient: __init__(0),start(0),stop(0),_subscriptions(0),_last_will(0),_on_payload(2),_handle_connect(0),_handle_message(3),_publish(2)  # Wraps a paho client and bridges its network thread to an asy
    OqlMqttController: __init__(0),_subscriptions(0),_on_payload(2),_resolve_response(1),_fan_out_event(1),execute(1),manage(2),subscribe_events(1),unsubscribe_events(1)  # Publishes OQL and awaits a correlated response.
    OqlMqttAgent: __init__(0),_subscriptions(0),_last_will(0),start(0),stop(0),_on_payload(2),_handle_request(1),_run_manage(1),_run_oql(1)  # Subscribes to OQL requests, executes them locally, and repli
    build_topics(prefix;node_id)
    _make_client(client_id)
  oqlos/hardware/usb_diagnostics.py:
    e: _read,_find_tty,list_usb_devices,pi_system_diagnostics,reset_usb_device
    _read(path)
    _find_tty(dev_dir)
    list_usb_devices()
    pi_system_diagnostics()
    reset_usb_device(vendor_id;product_id;dev_node)
  oqlos/ide/__init__.py:
  oqlos/models/__init__.py:
  oqlos/models/dsl_models.py:
    e: CqlMetadata,CqlInterval,CqlCondition,CqlAction,CqlStep,CqlGoal,CqlScenario,CqlDocument
    CqlMetadata:
    CqlInterval:
    CqlCondition:  # Sensor condition: AI01 ∈ [min, max] unit | ACTION 'msg'
    CqlAction:  # An action within a step: → Target.method args, TASK, SET, WA
    CqlStep:  # A numbered step within a goal: 1. Step name:
    CqlGoal:  # A test goal within a scenario.
    CqlScenario:  # A named scenario block: @Namespace.Name
    CqlDocument:  # Root AST node for a .cql file.
  oqlos/models/execution.py:
    e: ExecutionRequest,ExecutionStatus,CommandEnvelope
    ExecutionRequest:
    ExecutionStatus:
    CommandEnvelope:
  oqlos/models/peripheral.py:
    e: PeripheralType,PeripheralStatus,PeripheralMode,Peripheral
    PeripheralType:
    PeripheralStatus:
    PeripheralMode:
    Peripheral:
  oqlos/models/scenario.py:
    e: Step,ValidationRule,Goal,Scenario
    Step:
    ValidationRule:
    Goal:
    Scenario:
  oqlos/reporters/__init__.py:
  oqlos/reporters/html_report.py:
    e: render_html_report,_render_device_meta,_render_goal,_render_thresholds_table,_render_step
    render_html_report(data_json)
    _render_device_meta(meta)
    _render_goal(goal;idx)
    _render_thresholds_table(thresholds)
    _render_step(step;idx)
  oqlos/reporters/json_reporter.py:
    e: _step_to_dict,_group_steps_into_goals,_collect_thresholds,_extract_metadata,report_json
    _step_to_dict(step)
    _group_steps_into_goals(steps)
    _collect_thresholds(goals)
    _extract_metadata(variables)
    report_json(result)
  oqlos/reporters/junit.py:
    e: report_junit,JUnitReporter
    JUnitReporter: generate(2),_add_testcase(3)  # Generate JUnit XML from a ScriptResult.
    report_junit(result;suite_name)
  oqlos/scenarios/legacy_aliases.py:
    e: _repo_scenarios_dir,_load_legacy_aliases,resolve_canonical_scenario_file
    _repo_scenarios_dir()
    _load_legacy_aliases()
    resolve_canonical_scenario_file(scenario_id;scenarios_dir)
  oqlos/shared/__init__.py:
  oqlos/shared/_endpoint_helpers.py:
    e: serve_html_page,make_collection_route,get_or_404
    serve_html_page(file_path)
    make_collection_route(route_name;get_collection)
    get_or_404(collection;key;not_found_detail)
  oqlos/shared/config_factory.py:
    e: create_nfo_setup
    create_nfo_setup()
  oqlos/shared/event_server.py:
    e: main,ConnectionManager,EventServer
    ConnectionManager: __init__(0),connect(2),disconnect(1),broadcast(2),get_stats(0)  # Tracks connected WebSocket clients and broadcasts messages.
    EventServer: __init__(3),handle_client(1),_handle_message(2),_normalize_event(1),start(0)  # WebSocket event broker with persistence.
    main()
  oqlos/shared/event_store.py:
    e: EventStore
    EventStore: __init__(1),append(1),get_all(0),get_recent(1),get_by_correlation(1),clear(0),to_json(0),from_json(1),count(0),_save(0),_load(0)  # Append-only event store with optional JSON file persistence.
  oqlos/shared/file_ops.py:
    e: _ensure_safe_path,list_files,iter_entries,read_file,env_configured_path,read_text_file_or_empty,write_file,PathEscapeError
    PathEscapeError:  # Raised when a resolved path would escape the base directory.
    _ensure_safe_path(base;rel)
    list_files(base;pattern;recursive)
    iter_entries(base)
    read_file(base;rel)
    env_configured_path(env_vars;default)
    read_text_file_or_empty(path)
    write_file(base;rel;content)
  oqlos/shared/logger.py:
    e: configure_oqlos_logging,get_logger
    configure_oqlos_logging()
    get_logger(name)
  oqlos/shared/logs_query.py:
    e: resolve_logs_db_path,LogsQueryService
    LogsQueryService: __init__(1),db_exists(0),_connect(0),query_logs(0),get_stats(0)  # Read-only query service for nfo logs SQLite database.
    resolve_logs_db_path(project_root_fallback)
  oqlos/shared/release_version.py:
    e: clean_version,_run_git,_read_version_from_package_json,_read_version_from_text,_version_candidates,resolve_release_version,main
    clean_version(raw)
    _run_git(project_root)
    _read_version_from_package_json(path)
    _read_version_from_text(path)
    _version_candidates(project_root)
    resolve_release_version(project_root)
    main()
  oqlos/shared/version_endpoint.py:
    e: build_version_payload,create_version_router
    build_version_payload(service_name;version)
    create_version_router()
  oqlos/tools/__init__.py:
  oqlos/tools/cql_cli/__init__.py:
    e: _sync_compat_symbols,main
    _sync_compat_symbols()
    main()
  oqlos/tools/cql_cli/commands.py:
    e: default_firmware_url,run_source,run_single_command,handle_list_command,execute_command_with_cleanup,_run_continuous_mode
    default_firmware_url()
    run_source(source;filename)
    run_single_command(command)
    handle_list_command(argv)
    execute_command_with_cleanup(args;result;yaml_output;quiet)
    _run_continuous_mode(args;quiet)
  oqlos/tools/cql_cli/formatting.py:
    e: _quote_oql,canonicalize_oql_text,canonicalize_oql_line
    _quote_oql(value)
    canonicalize_oql_text(text)
    canonicalize_oql_line(line)
  oqlos/tools/cql_cli/main.py:
    e: create_file_parser,create_run_parser,create_hardware_parser,create_format_parser,create_cmd_parser,run_file_mode,_create_interpreter,_run_interpreter_target,_fetch_scenario_source,_extract_scenario_source,_looks_like_html,_print_cli_error,_run_hardware_flags,run_hardware_mode,run_cmd_mode,run_format_mode,_dispatch_to_mode,main,ScenarioFetchError
    ScenarioFetchError:  # Raised when an HTTP scenario target is not runnable OQL/CQL 
    create_file_parser()
    create_run_parser()
    create_hardware_parser(action)
    create_format_parser()
    create_cmd_parser()
    run_file_mode(args)
    _create_interpreter(args;sensors)
    _run_interpreter_target(interp;target)
    _fetch_scenario_source(url)
    _extract_scenario_source(data)
    _looks_like_html(text;content_type)
    _print_cli_error(message)
    _run_hardware_flags(args)
    run_hardware_mode(action;argv)
    run_cmd_mode(argv)
    run_format_mode(argv)
    _dispatch_to_mode(argv)
    main()
  oqlos/tools/cql_cli/preflight.py:
    e: ensure_firmware_running,_is_firmware_running,_start_firmware_service,check_firmware_state,check_required_adapter,check_required_adapter_health,_emit_preflight_error,emit_preflight_success,_emit_yaml_preflight,_emit_text_preflight,preflight_hardware
    ensure_firmware_running(firmware_url)
    _is_firmware_running(firmware_url)
    _start_firmware_service(firmware_url)
    check_firmware_state(firmware_url;yaml_output;quiet)
    check_required_adapter(command;adapters;yaml_output;quiet)
    check_required_adapter_health(required_adapter;health;yaml_output;quiet)
    _emit_preflight_error(error_msg;yaml_output;quiet)
    emit_preflight_success(firmware_url;health;identify;required_adapter;adapter_status;yaml_output;quiet)
    _emit_yaml_preflight(firmware_url;health;identify;required_adapter;adapter_status)
    _emit_text_preflight(firmware_url;health;identify;required_adapter;adapter_status)
    preflight_hardware(command;firmware_url)
  oqlos/tools/cql_cli/utils.py:
    e: output_yaml,parse_sensor_overrides,build_result_payload,normalize_target_name,build_single_command_scenario,_extract_first_action,_resolve_peripheral_adapter,_resolve_sensor_target,resolve_required_adapter,validate_directory
    output_yaml(data;quiet)
    parse_sensor_overrides(sensor_args)
    build_result_payload(result)
    normalize_target_name(target)
    build_single_command_scenario(command)
    _extract_first_action(command)
    _resolve_peripheral_adapter(target)
    _resolve_sensor_target(action)
    resolve_required_adapter(command)
    validate_directory(d;interpreter_class)
  oqlos/tools/gen_error_docs.py:
    e: _repair_cell,generate_markdown,main
    _repair_cell(defn)
    generate_markdown()
    main()
  oqlos/tools/hardware_diagnose/__init__.py:
    e: main
    main()
  oqlos/tools/hardware_diagnose/__main__.py:
    e: _print_list,_print_health,_print_calibrate,_print_benchmark,_print_detect,_print_doctor,_print_modbus_probe,main,_handle_report_action,_dispatch_action,_print_diagnose
    _print_list(url;as_json)
    _print_health(url;as_json)
    _print_calibrate(url;as_json)
    _print_benchmark(url;duration;as_json)
    _print_detect(url;as_json;config_path)
    _print_doctor(url;as_json;config_path;fix)
    _print_modbus_probe(_as_json;args)
    main()
    _handle_report_action(args;url;jout)
    _dispatch_action(args;url;jout)
    _print_diagnose(url;jout)
  oqlos/tools/hardware_diagnose/benchmark.py:
    e: run_benchmark
    run_benchmark(url;duration)
  oqlos/tools/hardware_diagnose/calibration.py:
    e: run_calibration_test,_calibrate_pump,_calibrate_valves,_calibrate_sensors
    run_calibration_test(url)
    _calibrate_pump(client;url;log)
    _calibrate_valves(client;url;log)
    _calibrate_sensors(client;url;log)
  oqlos/tools/hardware_diagnose/discovery.py:
    e: _run_shell_command,list_usb_serial_devices,list_i2c_buses,detect_chips_on_i2c,UsbDevice
    UsbDevice: to_dict(0)  # USB device information.
    _run_shell_command(cmd)
    list_usb_serial_devices()
    list_i2c_buses()
    detect_chips_on_i2c(bus)
  oqlos/tools/hardware_diagnose/doctor.py:
    e: build_doctor_report
    build_doctor_report(firmware_url)
  oqlos/tools/hardware_diagnose/doctor_common.py:
    e: add_issue,plugin_config,modbus_config,modbus_adc_config,collect_repairs
    add_issue(issues)
    plugin_config(config;plugin_id)
    modbus_config(config)
    modbus_adc_config(config)
    collect_repairs(issues)
  oqlos/tools/hardware_diagnose/doctor_detection.py:
    e: _doctor,usb_serial_only,load_config_summary,run_modbus_probe,probe_modbus,probe_modbus_adc,firmware_hostname,detect_hardware
    _doctor()
    usb_serial_only(devices)
    load_config_summary(config_path)
    run_modbus_probe(probe;probe_timeout)
    probe_modbus(probe_timeout)
    probe_modbus_adc(probe_timeout)
    firmware_hostname(firmware_url)
    detect_hardware(firmware_url)
  oqlos/tools/hardware_diagnose/doctor_firmware.py:
    e: adapter_health_status,firmware_is_remote,firmware_adapter_status,firmware_modbus_health_ok,firmware_modbus_adc_health_ok,check_firmware_health_error,check_firmware_mode,check_firmware_serial_access,check_firmware_adapters,analyze_firmware_access
    adapter_health_status(health;adapter_id)
    firmware_is_remote(detection)
    firmware_adapter_status(detection;adapter_id)
    firmware_modbus_health_ok(detection)
    firmware_modbus_adc_health_ok(detection)
    check_firmware_health_error(firmware;issues)
    check_firmware_mode(health;issues)
    check_firmware_serial_access(firmware;host_serial;issues;identify)
    check_firmware_adapters(identify;health;issues)
    analyze_firmware_access(detection;issues)
  oqlos/tools/hardware_diagnose/doctor_format.py:
    e: format_modbus_status,format_detection,_format_doctor_issues,_format_doctor_applied_repairs,_format_doctor_unapplied,format_doctor
    format_modbus_status(detection)
    format_detection(detection)
    _format_doctor_issues(issues)
    _format_doctor_applied_repairs(applied)
    _format_doctor_unapplied(repairs;applied)
    format_doctor(report)
  oqlos/tools/hardware_diagnose/doctor_modbus_analysis.py:
    e: expected_modbus_params,expected_modbus_adc_params,analyze_modbus_adc_config,analyze_modbus_config,analyze_serial_port_owners
    expected_modbus_params(modbus_probe)
    expected_modbus_adc_params(modbus_adc_probe)
    analyze_modbus_adc_config(detection;issues)
    analyze_modbus_config(detection;issues)
    analyze_serial_port_owners(detection;issues)
  oqlos/tools/hardware_diagnose/doctor_repairs.py:
    e: update_modbus_config,update_modbus_adc_config,apply_safe_fixes
    update_modbus_config(config_path;detected)
    update_modbus_adc_config(config_path;detected)
    apply_safe_fixes(detection;repairs)
  oqlos/tools/hardware_diagnose/doctor_serial.py:
    e: extract_pids,describe_pid,serial_port_owners,canonical_device_path,owners_for_configured_port
    extract_pids(text)
    describe_pid(pid)
    serial_port_owners(devices)
    canonical_device_path(device)
    owners_for_configured_port(owners;configured_port)
  oqlos/tools/hardware_diagnose/health.py:
    e: _request_firmware_json,check_firmware_health,check_firmware_identify,_is_health_ok,_format_health_value,cmd_health,cmd_diagnose
    _request_firmware_json(url;endpoint)
    check_firmware_health(url)
    check_firmware_identify(url)
    _is_health_ok(value)
    _format_health_value(value)
    cmd_health(url)
    cmd_diagnose(url)
  oqlos/tools/hardware_diagnose/modbus_probe.py:
    e: _env_typed,_env_int,_env_int_list,_env_count_list,_env_str_list,_env_float,_split_values,_arg_str_list,_arg_int_list,_arg_count_list,_serials_from_env,add_modbus_probe_arguments,probe_options_from_args,run_modbus_probe_from_args,run_modbus_probe_from_env,run_modbus_probe,main
    _env_typed(name;default;cast)
    _env_int(name;default)
    _env_int_list(name;fallback)
    _env_count_list(name;fallback)
    _env_str_list(name;fallback)
    _env_float(name;default)
    _split_values(values)
    _arg_str_list(values;fallback)
    _arg_int_list(values;fallback)
    _arg_count_list(values;fallback)
    _serials_from_env()
    add_modbus_probe_arguments(parser)
    probe_options_from_args(args)
    run_modbus_probe_from_args(args)
    run_modbus_probe_from_env()
    run_modbus_probe()
    main(argv)
  oqlos/tools/hardware_diagnose/report.py:
    e: format_peripheral_table,save_diagnostic_report
    format_peripheral_table(devices)
    save_diagnostic_report(filename;url)
  oqlos/tools/hardware_diagnose/shell.py:
    e: _cmd_list,_cmd_calibrate,_cmd_benchmark,_dispatch_command,interactive_shell
    _cmd_list()
    _cmd_calibrate(url)
    _cmd_benchmark(parts;url)
    _dispatch_command(cmd;parts;url)
    interactive_shell(url)
  oqlos/tools/hardware_diagnose.py:
  oqlos/tools/plugin_cli.py:
    e: _default_config_path,_load_config_file,_save_config_file,cmd_list,cmd_status,cmd_capabilities,cmd_validate,cmd_connect,cmd_disconnect,cmd_health,cmd_execute,cmd_reload,cmd_peripherals,main
    _default_config_path()
    _load_config_file(path)
    _save_config_file(path;configs)
    cmd_list(args)
    cmd_status(args)
    cmd_capabilities(args)
    cmd_validate(args)
    cmd_connect(args)
    cmd_disconnect(args)
    cmd_health(args)
    cmd_execute(args)
    cmd_reload(args)
    cmd_peripherals(args)
    main()
  oqlos/tools/xml_import/__init__.py:
  oqlos/tools/xml_import/_utils.py:
    e: slugify,is_pump_output,is_compressor_output,normalize_output_name,normalize_flow_value,normalize_set_value
    slugify(text)
    is_pump_output(name)
    is_compressor_output(name)
    normalize_output_name(name)
    normalize_flow_value(raw_value)
    normalize_set_value(raw_value)
  oqlos/tools/xml_import/generators.py:
    e: _mode_symbol,_format_range,_mode_action,_quote_oql,_emit_set,_emit_cql_output,_emit_cql_param,_emit_cql_sensor_param,_emit_dsl_output,_emit_dsl_param,_build_steps_from_op,_append_sensor_assertion,_build_validation_criteria,generate_dsl,_emit_dsl_test_run,_emit_dsl_sensors,_emit_dsl_metadata,generate_cql,_generate_cql_for_goal,generate_goals_json
    _mode_symbol(mode)
    _format_range(p)
    _mode_action(mode)
    _quote_oql(value)
    _emit_set(a;target;value)
    _emit_cql_output(out;a)
    _emit_cql_param(p;a)
    _emit_cql_sensor_param(p;a)
    _emit_dsl_output(out;a)
    _emit_dsl_param(p;a)
    _build_steps_from_op(op)
    _append_sensor_assertion(steps;op;p)
    _build_validation_criteria(ops)
    generate_dsl(report)
    _emit_dsl_test_run(report;tr;a)
    _emit_dsl_sensors(report;a)
    _emit_dsl_metadata(report;a)
    generate_cql(report)
    _generate_cql_for_goal(ops)
    generate_goals_json(report)
  oqlos/tools/xml_import/models.py:
    e: SensorParam,Output,Operation,TestRun,DeviceReport
    SensorParam:  # Parameter measurement from an operation.
    Output:  # Hardware output setting.
    Operation:  # Single test operation (step).
    TestRun:  # A test run (scenario) within a device type.
    DeviceReport:  # Parsed device test report.
  oqlos/tools/xml_import/parser.py:
    e: parse_xml,_populate_report_fields,_parse_intervals,_parse_test_run,_parse_operation,_parse_operation_params
    parse_xml(xml_path)
    _populate_report_fields(report;vars_)
    _parse_intervals(report;vars_)
    _parse_test_run(report;vars_;tr_num)
    _parse_operation(report;vars_;pfx;op_num)
    _parse_operation_params(op;vars_;opfx)
  oqlos/utils/__init__.py:
  oqlos/utils/hui_scenario.py:
    e: register_hui_test_scenario
    register_hui_test_scenario(state_manager)
  oqlos/utils/sample_data.py:
    e: load_sample_scenarios
    load_sample_scenarios(state_manager)
  scripts/fix_brackets_to_v4.py:
    e: needs_migration,main
    needs_migration(text)
    main()
  scripts/migrate_to_v4.py:
    e: find_oql_files,has_version_header,extract_version,_migrate_version_header,_migrate_goal_line,_migrate_loop_line,_migrate_endloop_line,_migrate_set_line,_migrate_simple_quoted_line,_migrate_wait_line,_migrate_minmax_line,_migrate_save_line,_migrate_single_line,migrate_content,_scan_files,_perform_migration,_perform_dry_run,main,check_database
    find_oql_files(root_dir)
    has_version_header(content)
    extract_version(content)
    _migrate_version_header(content)
    _migrate_goal_line(line;stripped)
    _migrate_loop_line(line;stripped)
    _migrate_endloop_line(stripped)
    _migrate_set_line(line;stripped)
    _migrate_simple_quoted_line(stripped;keyword)
    _migrate_wait_line(stripped)
    _migrate_minmax_line(stripped)
    _migrate_save_line(stripped)
    _migrate_single_line(line)
    migrate_content(content;filename)
    _scan_files(files)
    _perform_migration(needs_migration;root)
    _perform_dry_run(needs_migration;root)
    main()
    check_database()
  scripts/oql_v2_to_v4_migrate_db.py:
    e: _fetch_json,_send_json,_extract_rows,_normalize_bracket_tokens,_to_v4_token,_bracket_tokens,_join_value_unit,_quote,_format_set,_strip_outer_quotes,_extract_num_unit,_merge_minmax_to_if,_merge_paired_if,_rewrite_single_sided_if,_rewrite_legacy_if,_mig_goal,_mig_task,_mig_wait,_mig_sample,_mig_minmax,_mig_minmax_eq,_mig_minmax_simple,_mig_delta,_mig_as_log,_mig_calc,_mig_val,_mig_if_comparison,_mig_else_error,_mig_goto,_mig_save,_mig_else_info,_mig_set_name,_mig_set_eq,_mig_set_noeq,_mig_pump,migrate_v2_to_v4,_validate_runtime,_pick_code,_build_write_payload,_build_write_url,_process_row,_apply_row_update,_filter_rows,_build_migration_report,main,MigrationResult
    MigrationResult:
    _fetch_json(url;timeout)
    _send_json(url;method;payload;timeout)
    _extract_rows(payload)
    _normalize_bracket_tokens(text)
    _to_v4_token(text)
    _bracket_tokens(text)
    _join_value_unit(value)
    _quote(value)
    _format_set(target;value)
    _strip_outer_quotes(value)
    _extract_num_unit(value)
    _merge_minmax_to_if(lines)
    _merge_paired_if(indent;sensor;lo;hi;lo2;hi2)
    _rewrite_single_sided_if(indent;sensor;lo;hi)
    _rewrite_legacy_if(lines)
    _mig_goal(stripped;normalized)
    _mig_task(stripped;normalized)
    _mig_wait(stripped;normalized)
    _mig_sample(stripped;normalized)
    _mig_minmax(text;regex)
    _mig_minmax_eq(stripped;normalized)
    _mig_minmax_simple(stripped;normalized)
    _mig_delta(stripped;normalized)
    _mig_as_log(normalized;keyword)
    _mig_calc(stripped;normalized)
    _mig_val(stripped;normalized)
    _mig_if_comparison(stripped;normalized)
    _mig_else_error(stripped;normalized)
    _mig_goto(stripped;normalized)
    _mig_save(stripped;normalized)
    _mig_else_info(stripped;normalized)
    _mig_set_name(stripped;normalized)
    _mig_set_eq(stripped;normalized)
    _mig_set_noeq(stripped;normalized)
    _mig_pump(stripped;normalized)
    migrate_v2_to_v4(text)
    _validate_runtime(text;filename)
    _pick_code(row)
    _build_write_payload(row;migrated_code)
    _build_write_url(template;scenario_id)
    _process_row(row;scenario_dir;prefer_local)
    _apply_row_update(row;migrated_code;write_url_template;method)
    _filter_rows(rows;scenario_id)
    _build_migration_report(rows;results;args;updates_preview;updated_remote)
    main()
  scripts/oql_v2_validator.py:
    e: _line_number,_validate_version_header_v2,_validate_line_v2,_validate_v2_structure,validate_oql_v2_legacy,main,Issue
    Issue:
    _line_number(idx)
    _validate_version_header_v2(lines)
    _validate_line_v2(raw;ln;patterns)
    _validate_v2_structure(text)
    validate_oql_v2_legacy(text;source)
    main()
  scripts/oql_v4_validator.py:
    e: _line_number,_validate_version_header,_validate_line_v4,_validate_goal_set_name,_validate_structure,_validate_runtime,validate_oql_v4,main,Issue
    Issue:
    _line_number(lines;idx)
    _validate_version_header(lines)
    _validate_line_v4(raw;ln;patterns)
    _validate_goal_set_name(lines;patterns)
    _validate_structure(text)
    _validate_runtime(text;filename)
    validate_oql_v4(text;source)
    main()
  scripts/oql_validator_common.py:
    e: looks_like_html,extract_code_from_json,fetch_url,build_api_fallback_urls,load_source,run_validator_cli
    looks_like_html(text)
    extract_code_from_json(data)
    fetch_url(url;timeout)
    build_api_fallback_urls(url)
    load_source(file_path;url)
    run_validator_cli(description;validate;argv)
  scripts/scenarios_export.py:
    e: _list_url,_row_url,_http_get_json,_resolve_scenario_id,_fetch_all,_fetch_one,_safe_filename,export_all_zip,export_one_bash,_http_patch_json,_validate_oql_v4,import_scenarios,main
    _list_url(base;limit)
    _row_url(base;sid)
    _http_get_json(url;timeout)
    _resolve_scenario_id(value)
    _fetch_all(base)
    _fetch_one(base;sid)
    _safe_filename(sid)
    export_all_zip(base;out_path)
    export_one_bash(base;sid;out_path)
    _http_patch_json(url;payload;timeout)
    _validate_oql_v4(dsl;source)
    import_scenarios(base;dir_path;validate)
    main(argv)
  setup_hardware_and_run_oql.py:
    e: detect_serial_devices,suggest_modbus_port,generate_env_content,setup_env_file,load_env_file,run_oql_scenario,main
    detect_serial_devices()
    suggest_modbus_port(devices)
    generate_env_content(hardware_mode;modbus_port;piadc_url;motor_url;lung_motor_url)
    setup_env_file(env_path;hardware_mode;modbus_port;force)
    load_env_file(env_path)
    run_oql_scenario(scenario_path;mode;firmware_url)
    main()
  tests/firmware/test_artificial_lung.py:
    e: _reset_lung_state,test_set_lpm_updates_state,test_emergency_stop_resets_lpm,test_get_peripheral_status_includes_logical_state
    _reset_lung_state()
    test_set_lpm_updates_state()
    test_emergency_stop_resets_lpm()
    test_get_peripheral_status_includes_logical_state()
  tests/firmware/test_control_proxy.py:
    e: run,proxy_with_client,test_health_falls_back_to_alternate_oqlos_port,test_identify_returns_unavailable_payload_after_connection_failures,test_diagnostic_command_returns_structured_failure_payload,test_peripheral_status_proxies_plugin_health,test_peripheral_status_artificial_lung_uses_logical_lung_api,test_artificial_lung_diagnostic_resolves_to_logical_lung_api,test_peripheral_status_rtc_uses_hardware_rtc_status,test_rtc_diagnostic_uses_hardware_rtc_command,test_peripheral_status_returns_structured_payload_for_plugin_500,test_resolve_diagnostic_target_rejects_invalid_modbus_valve_id,FakeOqlosResponse
    FakeOqlosResponse: __init__(2),raise_for_status(0),json(0)
    run(coro)
    proxy_with_client(client)
    test_health_falls_back_to_alternate_oqlos_port()
    test_identify_returns_unavailable_payload_after_connection_failures()
    test_diagnostic_command_returns_structured_failure_payload()
    test_peripheral_status_proxies_plugin_health()
    test_peripheral_status_artificial_lung_uses_logical_lung_api()
    test_artificial_lung_diagnostic_resolves_to_logical_lung_api()
    test_peripheral_status_rtc_uses_hardware_rtc_status()
    test_rtc_diagnostic_uses_hardware_rtc_command()
    test_peripheral_status_returns_structured_payload_for_plugin_500()
    test_resolve_diagnostic_target_rejects_invalid_modbus_valve_id()
  tests/firmware/test_dri0050_sidecar_control.py:
    e: test_ensure_skips_when_already_healthy,test_resolve_dri0050_serial_prefers_existing_by_id,test_ensure_restarts_when_listening_returns_503
    test_ensure_skips_when_already_healthy(monkeypatch;tmp_path)
    test_resolve_dri0050_serial_prefers_existing_by_id(monkeypatch;tmp_path)
    test_ensure_restarts_when_listening_returns_503(monkeypatch;tmp_path)
  tests/firmware/test_dsl_parser_runtime.py:
    e: TestDslParserRuntime
    TestDslParserRuntime: test_parses_bracketed_task_lines_for_valve_14(0),test_parses_wait_step_from_builder_serialization(0),test_parses_bare_set_wait_step(0),test_parses_dedicated_pump_command(0),test_parses_set_lines_for_valve_and_compressor(0),test_parses_if_condition_with_operator_between_brackets(0),test_expands_func_call_into_runtime_steps(0),test_reports_invalid_runtime_line_for_pompx_typo(0),test_accepts_pompa_with_suffix_as_real_pump_reference(0),test_accepts_set_pompa_alias(0)
  tests/firmware/test_error_catalog.py:
    e: _codes_used_in_source,_fstring_code_templates_in_source,test_every_doctor_fstring_code_matches_a_registered_pattern,test_every_source_code_is_registered_in_catalog,test_every_catalog_code_is_still_used_somewhere,test_error_codes_doc_is_up_to_date,test_every_repair_template_has_a_hint_or_is_manual_only
    _codes_used_in_source()
    _fstring_code_templates_in_source()
    test_every_doctor_fstring_code_matches_a_registered_pattern()
    test_every_source_code_is_registered_in_catalog()
    test_every_catalog_code_is_still_used_somewhere()
    test_error_codes_doc_is_up_to_date()
    test_every_repair_template_has_a_hint_or_is_manual_only()
  tests/firmware/test_firmware.py:
    e: test_placeholder,test_import
    test_placeholder()
    test_import()
  tests/firmware/test_firmware_executor.py:
    e: _executor,test_plugin_action_awaits_async_pump_gateway,test_plugin_action_treats_failed_pump_result_as_failure,test_plugin_action_uses_gateway_runtime_loop_from_worker_thread,_Vars,_Out,_Normalizer,_AsyncGateway
    _Vars: __init__(0),interpolate(1),set(2)
    _Out: __init__(0),step(2),error(1),warn(1)
    _Normalizer: normalize_pump_power(1)
    _AsyncGateway: __init__(1),set_pump(1),set_valve(2),set_lung(0)
    _executor(gateway;vars_store;out)
    test_plugin_action_awaits_async_pump_gateway()
    test_plugin_action_treats_failed_pump_result_as_failure()
    test_plugin_action_uses_gateway_runtime_loop_from_worker_thread()
  tests/firmware/test_gateway_http.py:
    e: test_gateway_get_json,_Response,_Client
    _Response: __init__(1),raise_for_status(0),json(0)
    _Client: __init__(0),get(1),post(2)
    test_gateway_get_json(monkeypatch)
  tests/firmware/test_hardware_diagnosis_api.py:
    e: test_build_diagnosis_report_motors_error,test_motors_only_no_global_make_hardware_up,test_recover_targets_skip_devices_ok_in_report,test_host_actions_filtered_motor_only_no_make
    test_build_diagnosis_report_motors_error()
    test_motors_only_no_global_make_hardware_up()
    test_recover_targets_skip_devices_ok_in_report()
    test_host_actions_filtered_motor_only_no_make()
  tests/firmware/test_hardware_diagnosis_routes.py:
    e: test_hardware_diagnosis_route,test_hardware_recover_rejects_unknown_scope
    test_hardware_diagnosis_route(monkeypatch)
    test_hardware_recover_rejects_unknown_scope(monkeypatch)
  tests/firmware/test_hardware_discovery.py:
    e: test_list_i2c_buses_uses_glob,test_list_usb_serial_devices_uses_glob_fallback
    test_list_i2c_buses_uses_glob(monkeypatch)
    test_list_usb_serial_devices_uses_glob_fallback(monkeypatch)
  tests/firmware/test_hardware_doctor.py:
    e: _write_config,_patch_detection,test_doctor_reports_modbus_config_mismatch,test_doctor_fix_updates_modbus_config,test_doctor_fix_reports_unapplied_manual_repairs,test_doctor_reports_busy_configured_serial_port,test_doctor_reports_busy_configured_serial_port_via_by_id_symlink,test_doctor_trusts_firmware_modbus_health_when_local_port_is_busy,test_doctor_explains_remote_firmware_cannot_use_local_usb,test_detection_filters_real_usb_serial_devices
    _write_config(path)
    _patch_detection(monkeypatch)
    test_doctor_reports_modbus_config_mismatch(monkeypatch;tmp_path)
    test_doctor_fix_updates_modbus_config(monkeypatch;tmp_path)
    test_doctor_fix_reports_unapplied_manual_repairs(monkeypatch;tmp_path)
    test_doctor_reports_busy_configured_serial_port(monkeypatch;tmp_path)
    test_doctor_reports_busy_configured_serial_port_via_by_id_symlink(monkeypatch;tmp_path)
    test_doctor_trusts_firmware_modbus_health_when_local_port_is_busy(monkeypatch;tmp_path)
    test_doctor_explains_remote_firmware_cannot_use_local_usb(monkeypatch;tmp_path)
    test_detection_filters_real_usb_serial_devices(monkeypatch;tmp_path)
  tests/firmware/test_hardware_health.py:
    e: test_cmd_health_marks_connected_adapter_dict_as_ok,test_cmd_health_marks_error_adapter_dict_as_warning
    test_cmd_health_marks_connected_adapter_dict_as_ok(monkeypatch)
    test_cmd_health_marks_error_adapter_dict_as_warning(monkeypatch)
  tests/firmware/test_hardware_health_http.py:
    e: test_hardware_health_overall_ok_ignores_disabled_plugins,test_hardware_health_overall_ok_ignores_init_summary,test_hardware_health_overall_ok_false_when_any_plugin_errors,test_hardware_health_endpoint_returns_200_when_degraded,_FakeGateway
    _FakeGateway: health(0)
    test_hardware_health_overall_ok_ignores_disabled_plugins()
    test_hardware_health_overall_ok_ignores_init_summary()
    test_hardware_health_overall_ok_false_when_any_plugin_errors()
    test_hardware_health_endpoint_returns_200_when_degraded(monkeypatch)
  tests/firmware/test_hardware_hui_routes.py:
    e: test_hardware_router_includes_hui_paths,test_raise_if_hui_failed_raises_on_error_payload,test_hui_hold_start_uses_gateway,_FakeGateway
    _FakeGateway: hold(1)
    test_hardware_router_includes_hui_paths()
    test_raise_if_hui_failed_raises_on_error_payload()
    test_hui_hold_start_uses_gateway(monkeypatch)
  tests/firmware/test_hardware_identify.py:
    e: _patch_gateway,_patch_probe,_patch_platform,test_collect_hardware_diagnostics_exposes_ports,test_platform_reports_modbus_adc_as_analog_input,test_hardware_identify_includes_diagnostics,test_hardware_identify_default_skips_live_probe,test_read_sensors_batch_reports_unavailable_modbus_without_503,test_hardware_temperature_returns_compatible_payload,test_hardware_diagnose_keeps_sensor_errors_in_payload,test_modbus_adc_raw_reports_unavailable_health_without_404,test_hardware_identify_reports_modbus_timeout_as_adapter_only,_FakeGateway,_UnavailableAdcGateway,_ModbusTimeoutGateway
    _FakeGateway: health(0)
    _UnavailableAdcGateway: health(0),read_sensor(1)
    _ModbusTimeoutGateway: health(0)
    _patch_gateway(monkeypatch;gateway)
    _patch_probe(monkeypatch;name;value)
    _patch_platform(monkeypatch;name;value)
    test_collect_hardware_diagnostics_exposes_ports(monkeypatch)
    test_platform_reports_modbus_adc_as_analog_input(monkeypatch)
    test_hardware_identify_includes_diagnostics(monkeypatch)
    test_hardware_identify_default_skips_live_probe(monkeypatch)
    test_read_sensors_batch_reports_unavailable_modbus_without_503(monkeypatch)
    test_hardware_temperature_returns_compatible_payload(monkeypatch)
    test_hardware_diagnose_keeps_sensor_errors_in_payload(monkeypatch)
    test_modbus_adc_raw_reports_unavailable_health_without_404(monkeypatch)
    test_hardware_identify_reports_modbus_timeout_as_adapter_only(monkeypatch)
  tests/firmware/test_hardware_identify_routes.py:
    e: test_hardware_router_includes_health_and_identify
    test_hardware_router_includes_health_and_identify()
  tests/firmware/test_hardware_lung_routes.py:
    e: test_hardware_router_includes_actuator_and_lung_paths,test_command_payload_requires_command_name
    test_hardware_router_includes_actuator_and_lung_paths()
    test_command_payload_requires_command_name()
  tests/firmware/test_hardware_mapping_motor2.py:
    e: test_validate_motor2_config_accepts_minimal_object,test_validate_motor2_config_rejects_default_speed_above_max,test_validate_mapping_contract_wraps_motor2_errors
    test_validate_motor2_config_accepts_minimal_object()
    test_validate_motor2_config_rejects_default_speed_above_max()
    test_validate_mapping_contract_wraps_motor2_errors()
  tests/firmware/test_hardware_modbus_routes.py:
    e: test_hardware_router_includes_modbus_paths
    test_hardware_router_includes_modbus_paths()
  tests/firmware/test_hardware_modbus_wizard.py:
    e: _patch_modbus_ports,_patch_modbus_io_ids,_patch_modbus_settings,_patch_diagnose_matrix,test_modbus_wizard_program_writes_uart_before_address_change,test_modbus_wizard_program_skips_when_already_at_target,test_build_waveshare_diagnose_uses_target_baud_fast_path,test_build_waveshare_diagnose_scans_separate_adapters,test_build_waveshare_skips_matrix_when_plugins_healthy,test_build_waveshare_serial_stale_skips_matrix,test_modbus_runtime_ports_auto_detects_separate_adapters,test_modbus_runtime_ports_shared_bus_forced,test_modbus_wizard_plan_exposes_per_adapter_ports
    _patch_modbus_ports(monkeypatch;ports)
    _patch_modbus_io_ids(monkeypatch;ids)
    _patch_modbus_settings(monkeypatch;settings_obj)
    _patch_diagnose_matrix(monkeypatch;fake_matrix)
    test_modbus_wizard_program_writes_uart_before_address_change(monkeypatch)
    test_modbus_wizard_program_skips_when_already_at_target(monkeypatch)
    test_build_waveshare_diagnose_uses_target_baud_fast_path(monkeypatch)
    test_build_waveshare_diagnose_scans_separate_adapters(monkeypatch)
    test_build_waveshare_skips_matrix_when_plugins_healthy(monkeypatch)
    test_build_waveshare_serial_stale_skips_matrix(monkeypatch)
    test_modbus_runtime_ports_auto_detects_separate_adapters(monkeypatch)
    test_modbus_runtime_ports_shared_bus_forced(monkeypatch)
    test_modbus_wizard_plan_exposes_per_adapter_ports(monkeypatch)
  tests/firmware/test_hardware_platform_detect.py:
    e: test_detect_runtime_platform_survives_missing_pimodbus,test_detect_runtime_platform_omits_error_key_on_success
    test_detect_runtime_platform_survives_missing_pimodbus(monkeypatch)
    test_detect_runtime_platform_omits_error_key_on_success(monkeypatch)
  tests/firmware/test_hardware_probe_devices.py:
    e: test_hardware_probe_reexports_device_helpers,test_probe_tic249_detects_vendor_product
    test_hardware_probe_reexports_device_helpers()
    test_probe_tic249_detects_vendor_product()
  tests/firmware/test_hardware_runtime_routes.py:
    e: test_hardware_router_includes_runtime_paths,test_modbus_adc_unavailable_detects_incompatible_adc,test_read_sensor_values_skips_live_reads_when_adc_unavailable,_UnavailableAdcGateway
    _UnavailableAdcGateway: health(0),read_sensor(1)
    test_hardware_router_includes_runtime_paths()
    test_modbus_adc_unavailable_detects_incompatible_adc()
    test_read_sensor_values_skips_live_reads_when_adc_unavailable()
  tests/firmware/test_hardware_stack_snapshot.py:
    e: test_stack_snapshot_marks_serial_stale
    test_stack_snapshot_marks_serial_stale(monkeypatch)
  tests/firmware/test_hardware_v3_compat.py:
    e: _client,test_hardware_v3_mapping_round_trip,test_hardware_v3_mapping_rejects_invalid_contract,test_hardware_v3_cqrs_events_record_diagnostic_failure,test_hardware_ui_aliases_and_status_page_are_served,test_navigation_index_and_short_aliases
    _client()
    test_hardware_v3_mapping_round_trip(monkeypatch;tmp_path)
    test_hardware_v3_mapping_rejects_invalid_contract(monkeypatch;tmp_path)
    test_hardware_v3_cqrs_events_record_diagnostic_failure(monkeypatch)
    test_hardware_ui_aliases_and_status_page_are_served()
    test_navigation_index_and_short_aliases()
  tests/firmware/test_hui_actions.py:
    e: run,test_hui_hold_profile_runs_inside_oqlos,test_hui_hold_profile_can_be_overridden_from_hardware_map,test_hui_actions_list_uses_mapped_profiles,test_hui_artificial_lung_uses_tic249_plugin_recipe,test_hui_artificial_lung_recipe_can_be_overridden_from_hardware_map,test_stop_hui_artificial_lung_closes_the_configured_valve,test_stop_hui_artificial_lung_uses_overridden_valve,test_hui_artificial_lung_start_failure_cleans_up_same_valve_it_opened,test_hui_shutdown_turns_off_pump_and_all_known_valves,FakeGateway,FakeTic249Plugin
    FakeGateway: __init__(0),set_valve(2),set_pump(1),set_lung_result(0),stop_lung(0),_get_or_connect_plugin(1)
    FakeTic249Plugin: __init__(0),execute_command(2)
    run(coro)
    test_hui_hold_profile_runs_inside_oqlos(monkeypatch)
    test_hui_hold_profile_can_be_overridden_from_hardware_map(monkeypatch)
    test_hui_actions_list_uses_mapped_profiles(monkeypatch)
    test_hui_artificial_lung_uses_tic249_plugin_recipe()
    test_hui_artificial_lung_recipe_can_be_overridden_from_hardware_map(monkeypatch)
    test_stop_hui_artificial_lung_closes_the_configured_valve()
    test_stop_hui_artificial_lung_uses_overridden_valve(monkeypatch)
    test_hui_artificial_lung_start_failure_cleans_up_same_valve_it_opened(monkeypatch)
    test_hui_shutdown_turns_off_pump_and_all_known_valves()
  tests/firmware/test_hui_scenario.py:
    e: test_register_hui_test_scenario_adds_ts_c20_once
    test_register_hui_test_scenario_adds_ts_c20_once()
  tests/firmware/test_identify_enrich_modbus_io.py:
    e: test_expand_modbus_io_instances_clones_per_slave_id
    test_expand_modbus_io_instances_clones_per_slave_id(monkeypatch)
  tests/firmware/test_lung_integration.py:
    e: TestLungDslHelpers,TestLungDslParser,TestLungExecutor,TestFirmwareAdapterLung,TestHardwareGatewayLung,TestCqlInterpreterLung
    TestLungDslHelpers: test_looks_like_lung_object(1),test_not_lung_object(0),test_map_peripheral_lung(0),test_map_lung_action_start(0),test_map_lung_action_stop(0),test_map_lung_action_default_cycles(0),test_map_action_value_lung(0)
    TestLungDslParser: test_parses_lung_set_command(0),test_parses_lung_task_command(0),test_parses_lung_stop(0)
    TestLungExecutor: _make_orchestrator(0),test_execute_lung_step_reciprocate(0),test_execute_lung_step_stop(0),test_execute_step_dispatches_set_lung(0)
    TestFirmwareAdapterLung: test_peripheral_map_lung(0),test_resolve_peripheral_lung(0),test_dispatch_lung_start(0),test_dispatch_lung_stop(0),test_set_peripheral_lung_start(0),test_set_peripheral_lung_stop(0)
    TestHardwareGatewayLung: test_set_lung_mock(0),test_stop_lung_mock(0)
    TestCqlInterpreterLung: test_dry_run_lung_action(0)
  tests/firmware/test_lung_plugin_reciprocate.py:
    e: _plugin_with_client,test_ready_false_does_not_block_reciprocate_start,test_tic249_extended_reciprocate_normalizes_ramp_time_alias,_JsonResponse,_ReadyFalseClient
    _JsonResponse: __init__(2),json(0)
    _ReadyFalseClient: __init__(0),get(1),post(2)
    _plugin_with_client(client)
    test_ready_false_does_not_block_reciprocate_start()
    test_tic249_extended_reciprocate_normalizes_ramp_time_alias()
  tests/firmware/test_modbus_adc_aliases.py:
    e: test_resolve_channel_accepts_map_editor_v_inputs
    test_resolve_channel_accepts_map_editor_v_inputs()
  tests/firmware/test_modbus_discovery.py:
    e: _install_fake_pymodbus,test_probe_waveshare_modbus_detects_working_port,test_probe_waveshare_modbus_reports_adapter_only_when_no_response,test_probe_waveshare_modbus_can_scan_high_baud_when_enabled,_OkResponse,_ErrorResponse
    _OkResponse: isError(0)
    _ErrorResponse: isError(0)
    _install_fake_pymodbus(monkeypatch;responsive_port;responsive_baud;responsive_parity)
    test_probe_waveshare_modbus_detects_working_port(monkeypatch)
    test_probe_waveshare_modbus_reports_adapter_only_when_no_response(monkeypatch)
    test_probe_waveshare_modbus_can_scan_high_baud_when_enabled(monkeypatch)
  tests/firmware/test_modbus_identify.py:
    e: test_enrich_platform_modbus_ports_from_serial_list,test_enrich_modbus_serial_hints_on_modbus_io
    test_enrich_platform_modbus_ports_from_serial_list()
    test_enrich_modbus_serial_hints_on_modbus_io()
  tests/firmware/test_modbus_probe_cli.py:
    e: _install_fake_pymodbus,test_run_modbus_probe_returns_successful_read,test_run_modbus_probe_reports_unsupported_function,test_probe_options_from_args_override_environment,_OkResponse,_ErrorResponse
    _OkResponse: isError(0),__str__(0)
    _ErrorResponse: isError(0)
    _install_fake_pymodbus(monkeypatch)
    test_run_modbus_probe_returns_successful_read(monkeypatch)
    test_run_modbus_probe_reports_unsupported_function(monkeypatch)
    test_probe_options_from_args_override_environment(monkeypatch)
  tests/firmware/test_motor_http_handlers.py:
    e: test_motor_http_request_maps_response_fields,test_motor_cli_command_success,_Response,_Client
    _Response: __init__(1),json(0)
    _Client: __init__(1),post(2),get(1)
    test_motor_http_request_maps_response_fields()
    test_motor_cli_command_success(monkeypatch)
  tests/firmware/test_motor_modbus_handlers.py:
    e: test_duty_pct_to_register_scales_percent,test_modbus_health_check_reads_pid,test_modbus_set_speed_writes_duty_and_enable,test_modbus_stop_zeros_duty_and_enable,test_modbus_status_maps_registers,_ModbusResult,_Bus
    _ModbusResult: __init__(2),isError(0)
    _Bus: __init__(2),call(1)
    test_duty_pct_to_register_scales_percent()
    test_modbus_health_check_reads_pid()
    test_modbus_set_speed_writes_duty_and_enable()
    test_modbus_stop_zeros_duty_and_enable()
    test_modbus_status_maps_registers()
  tests/firmware/test_motor_plugin.py:
    e: test_motor_plugin_http_stop_uses_global_time_import,test_motor_plugin_health_rejects_missing_local_serial_port,_Response,_Client,_HealthClient
    _Response: json(0)
    _Client: post(1)
    _HealthClient: get(1)
    test_motor_plugin_http_stop_uses_global_time_import()
    test_motor_plugin_health_rejects_missing_local_serial_port(monkeypatch)
  tests/firmware/test_normalize_scenario.py:
    e: TestExtractId,TestExtractDisplayFields,TestExtractGoals,TestComputeSlug,TestNormalizeScenarioRow
    TestExtractId: test_valid_id(0),test_strips_whitespace(0),test_missing_id_returns_none(0),test_empty_string_returns_none(0),test_none_value_returns_none(0),test_numeric_id_converted_to_str(0)
    TestExtractDisplayFields: test_all_fields_present(0),test_name_fallback_to_title(0),test_name_fallback_to_code(0),test_name_fallback_to_sid(0),test_device_fallback_to_device_id(0),test_protocol_fallback_to_protocol_id(0),test_missing_optional_fields_default_empty(0)
    TestExtractGoals: test_no_content_returns_empty(0),test_none_content_returns_empty(0),test_content_with_goals(0),test_content_without_goals_key(0),test_content_non_dict(0)
    TestComputeSlug: test_explicit_slug(0),test_slug_from_code(0),test_slug_from_display_name(0),test_slug_from_sid(0),test_double_hyphens_collapsed(0),test_strips_leading_trailing_hyphens(0)
    TestNormalizeScenarioRow: test_full_row(0),test_minimal_row(0),test_missing_id_returns_none(0),test_empty_id_returns_none(0),test_fallback_fields(0)
  tests/firmware/test_oql_envelope.py:
    e: test_request_json_roundtrip,test_request_defaults_do_not_skip_waits,test_response_json_roundtrip,test_topics_layout,test_build_result_payload_is_json_serializable
    test_request_json_roundtrip()
    test_request_defaults_do_not_skip_waits()
    test_response_json_roundtrip()
    test_topics_layout()
    test_build_result_payload_is_json_serializable()
  tests/firmware/test_oql_manage_ops.py:
    e: test_unknown_verb_raises,test_hardware_facade_exposes_manage_ops_handlers,test_diagnostic_command_routes_to_plugin_execute,test_diagnostic_command_requires_peripheral_id,test_tic249_disable_diagnostic_uses_lung_disable,test_modbus_io_valve_diagnostic_uses_set_valve,test_modbus_io_valve_diagnostic_preserves_set_valve_failure,test_pump_off_diagnostic_uses_set_pump,test_move_relative_diagnostic_maps_to_plugin_move,test_diagnostic_command_listed,test_hui_manage_verbs_route_to_hui_handlers,test_hui_manage_verbs_listed
    test_unknown_verb_raises()
    test_hardware_facade_exposes_manage_ops_handlers()
    test_diagnostic_command_routes_to_plugin_execute(monkeypatch)
    test_diagnostic_command_requires_peripheral_id()
    test_tic249_disable_diagnostic_uses_lung_disable(monkeypatch)
    test_modbus_io_valve_diagnostic_uses_set_valve(monkeypatch)
    test_modbus_io_valve_diagnostic_preserves_set_valve_failure(monkeypatch)
    test_pump_off_diagnostic_uses_set_pump(monkeypatch)
    test_move_relative_diagnostic_maps_to_plugin_move(monkeypatch)
    test_diagnostic_command_listed()
    test_hui_manage_verbs_route_to_hui_handlers(monkeypatch)
    test_hui_manage_verbs_listed()
  tests/firmware/test_oql_mqtt_bridge.py:
    e: _topic_matches,broker,_make_pair,test_ping_round_trip,test_command_round_trip_executes_oql,test_manage_usb_list_round_trip,test_concurrent_requests_resolve_their_own_correlation,test_timeout_when_no_agent_replies,test_manage_verb_round_trip,test_manage_unknown_verb_is_ok_false,test_agent_run_oql_handles_execution_errors,_FakeMessage,FakeBroker,FakeClient
    _FakeMessage: __init__(2)
    FakeBroker: __init__(0),register(1),publish(4),deliver_retained(2)
    FakeClient: __init__(2),username_pw_set(2),will_set(4),connect(3),loop_start(0),loop_stop(0),disconnect(0),subscribe(2),publish(4)
    _topic_matches(filt;topic)
    broker(monkeypatch)
    _make_pair(broker)
    test_ping_round_trip(broker)
    test_command_round_trip_executes_oql(broker)
    test_manage_usb_list_round_trip(broker)
    test_concurrent_requests_resolve_their_own_correlation(broker)
    test_timeout_when_no_agent_replies(broker)
    test_manage_verb_round_trip(broker)
    test_manage_unknown_verb_is_ok_false(broker)
    test_agent_run_oql_handles_execution_errors(broker;monkeypatch)
  tests/firmware/test_oql_route_http.py:
    e: client,test_execute_returns_503_when_transport_disabled,test_execute_dispatches_to_controller,test_execute_accepts_explicit_skip_waits,test_execute_surfaces_remote_error_as_ok_false,test_manage_returns_503_when_transport_disabled,test_manage_dispatches_verb_and_args,test_manage_surfaces_remote_error,_FakeController
    _FakeController: __init__(1),execute(1),manage(2)
    client()
    test_execute_returns_503_when_transport_disabled(client)
    test_execute_dispatches_to_controller(client)
    test_execute_accepts_explicit_skip_waits(client)
    test_execute_surfaces_remote_error_as_ok_false(client)
    test_manage_returns_503_when_transport_disabled(client)
    test_manage_dispatches_verb_and_args(client)
    test_manage_surfaces_remote_error(client)
  tests/firmware/test_oqlos_error.py:
    e: test_oqlos_error_uses_catalog_defaults_for_known_code,test_oqlos_error_overrides_and_detail,test_oqlos_error_tolerates_unknown_code,test_oqlos_error_fastapi_handler_returns_standard_body,test_oqlos_error_handler_can_be_installed_on_router_only_test_app,test_catalog_lookup_still_available_for_known_code
    test_oqlos_error_uses_catalog_defaults_for_known_code()
    test_oqlos_error_overrides_and_detail()
    test_oqlos_error_tolerates_unknown_code()
    test_oqlos_error_fastapi_handler_returns_standard_body()
    test_oqlos_error_handler_can_be_installed_on_router_only_test_app()
    test_catalog_lookup_still_available_for_known_code()
  tests/firmware/test_oqlos_logging.py:
    e: test_configure_oqlos_logging_writes_to_file
    test_configure_oqlos_logging_writes_to_file(tmp_path;monkeypatch)
  tests/firmware/test_panel_ui.py:
    e: panel_source,_panel_manage_verbs,_panel_endpoints,test_panel_route_serves_html,test_panel_exposes_wait_execution_state_in_payload_and_url,test_health_route_contains_redeploy_probe_token,test_panel_manage_verbs_are_supported,test_panel_only_calls_known_endpoints,test_panel_editor_and_results_use_equal_height_split,test_panel_loads_editor_file_scenarios,client_with_controller,test_panel_single_oql_command_payload_dispatches,test_panel_flow_script_payload_dispatches,test_panel_script_without_version_executes_named_goal,test_panel_script_accepts_set_wait_alias,test_panel_manage_payload_dispatches,_FakeController
    _FakeController: __init__(1),execute(1),manage(2)
    panel_source()
    _panel_manage_verbs(source)
    _panel_endpoints(source)
    test_panel_route_serves_html()
    test_panel_exposes_wait_execution_state_in_payload_and_url(panel_source)
    test_health_route_contains_redeploy_probe_token()
    test_panel_manage_verbs_are_supported(panel_source)
    test_panel_only_calls_known_endpoints(panel_source)
    test_panel_editor_and_results_use_equal_height_split(panel_source)
    test_panel_loads_editor_file_scenarios(panel_source)
    client_with_controller()
    test_panel_single_oql_command_payload_dispatches(client_with_controller)
    test_panel_flow_script_payload_dispatches(client_with_controller)
    test_panel_script_without_version_executes_named_goal()
    test_panel_script_accepts_set_wait_alias()
    test_panel_manage_payload_dispatches(client_with_controller)
  tests/firmware/test_parser_cycle.py:
    e: TestParserCycleDetection
    TestParserCycleDetection: test_direct_circular_func_raises(0),test_self_referencing_func_raises(0),test_valid_func_call_works(0),test_max_func_depth_constant(0)
  tests/firmware/test_plugin_gateway_env.py:
    e: test_plugin_gateway_env_overrides_service_urls,test_plugin_gateway_env_overrides_modbus_params,test_plugin_gateway_env_overrides_modbus_adc_params,test_set_pump_uses_registry_instance_that_recovers_after_startup,test_plugin_gateway_disable_plugins_env,test_plugin_gateway_allow_list_plugins_env,test_health_reports_configured_disabled_plugins,test_health_does_not_poll_configured_disabled_plugins
    test_plugin_gateway_env_overrides_service_urls(monkeypatch)
    test_plugin_gateway_env_overrides_modbus_params(monkeypatch)
    test_plugin_gateway_env_overrides_modbus_adc_params(monkeypatch)
    test_set_pump_uses_registry_instance_that_recovers_after_startup(monkeypatch)
    test_plugin_gateway_disable_plugins_env(monkeypatch)
    test_plugin_gateway_allow_list_plugins_env(monkeypatch)
    test_health_reports_configured_disabled_plugins(monkeypatch)
    test_health_does_not_poll_configured_disabled_plugins(monkeypatch)
  tests/firmware/test_plugin_gateway_init.py:
    e: test_health_awaits_ensure_initialized_before_checks,test_initialize_plugins_records_summary
    test_health_awaits_ensure_initialized_before_checks(monkeypatch)
    test_initialize_plugins_records_summary(monkeypatch)
  tests/firmware/test_plugin_health.py:
    e: test_piadc_health_rejects_mock_mode,test_piadc_health_includes_uninitialized_service_reason,test_piadc_health_points_non_rpi_hosts_to_remote_service,test_lung_health_rejects_uninitialized_runtime,test_modbus_rtu_health_timeout_does_not_block_event_loop,test_modbus_adc_health_reads_input_registers,test_modbus_adc_read_sensor_uses_channel_conversion,test_modbus_rtu_uses_configured_device_id_for_health_and_writes,test_modbus_rtu_health_infers_mode_from_connected_bus,test_plugin_registry_health_checks_run_concurrently_with_timeout,_JsonResponse,_PiadcClient,_UninitializedPiadcClient,_FailingPiadcClient,_LungClient,_BlockingModbusClient,_OkModbusResult,_CapturingModbusClient,_CapturingAsyncModbusBus,_CapturingModbusAdcClient
    _JsonResponse: __init__(2),json(0)
    _PiadcClient: get(1)
    _UninitializedPiadcClient: get(1)
    _FailingPiadcClient: get(1)
    _LungClient: get(1)
    _BlockingModbusClient: read_coils(0)
    _OkModbusResult: isError(0)
    _CapturingModbusClient: __init__(0),read_coils(0),write_coil(0)
    _CapturingAsyncModbusBus: read_coils(0),write_coil(0)
    _CapturingModbusAdcClient: __init__(0),read_input_registers(0)
    test_piadc_health_rejects_mock_mode()
    test_piadc_health_includes_uninitialized_service_reason()
    test_piadc_health_points_non_rpi_hosts_to_remote_service(monkeypatch)
    test_lung_health_rejects_uninitialized_runtime()
    test_modbus_rtu_health_timeout_does_not_block_event_loop()
    test_modbus_adc_health_reads_input_registers()
    test_modbus_adc_read_sensor_uses_channel_conversion()
    test_modbus_rtu_uses_configured_device_id_for_health_and_writes()
    test_modbus_rtu_health_infers_mode_from_connected_bus()
    test_plugin_registry_health_checks_run_concurrently_with_timeout(monkeypatch)
  tests/firmware/test_plugin_http_handlers.py:
    e: test_http_get_command_success,test_adapter_status_from_health_marks_serial_stale,test_enrich_adapter_entry_marks_tic249_device_stale,_Response,_Client
    _Response: __init__(1),json(0)
    _Client: __init__(1),post(2),get(1)
    test_http_get_command_success()
    test_adapter_status_from_health_marks_serial_stale()
    test_enrich_adapter_entry_marks_tic249_device_stale()
  tests/firmware/test_plugins_api.py:
    e: test_execute_plugin_command_returns_operational_failure_payload,FakePlugin
    FakePlugin: execute_command(2)
    test_execute_plugin_command_returns_operational_failure_payload(monkeypatch)
  tests/firmware/test_plugins_health_http.py:
    e: test_plugin_health_returns_503_when_plugin_reports_error,test_plugin_health_returns_503_when_no_active_instance,test_plugin_health_returns_200_when_plugin_connected
    test_plugin_health_returns_503_when_plugin_reports_error(monkeypatch)
    test_plugin_health_returns_503_when_no_active_instance(monkeypatch)
    test_plugin_health_returns_200_when_plugin_connected(monkeypatch)
  tests/firmware/test_repair_commit.py:
    e: _action,test_config_risk_auto_executable_action_is_eligible,test_physical_risk_action_is_never_eligible_even_if_auto_executable,test_none_risk_action_is_not_eligible,test_config_risk_action_not_marked_auto_executable_is_not_eligible,test_missing_actuation_risk_defaults_to_not_eligible,test_commit_message_format_is_greppable_by_issue_trailer,test_commit_message_includes_co_author_when_given
    _action()
    test_config_risk_auto_executable_action_is_eligible()
    test_physical_risk_action_is_never_eligible_even_if_auto_executable()
    test_none_risk_action_is_not_eligible()
    test_config_risk_action_not_marked_auto_executable_is_not_eligible()
    test_missing_actuation_risk_defaults_to_not_eligible()
    test_commit_message_format_is_greppable_by_issue_trailer()
    test_commit_message_includes_co_author_when_given()
  tests/firmware/test_rtc_probe.py:
    e: test_enrich_rtc_adapter_skips_when_disabled,test_enrich_rtc_adapter_appends_rtc,test_enrich_rtc_adapter_idempotent,test_build_rtc_peripheral_status_reads_sidecar,test_run_rtc_command_posts_to_sidecar,test_hardware_rtc_status_endpoint_uses_probe,test_hardware_rtc_command_endpoint_uses_probe
    test_enrich_rtc_adapter_skips_when_disabled(monkeypatch)
    test_enrich_rtc_adapter_appends_rtc(monkeypatch)
    test_enrich_rtc_adapter_idempotent()
    test_build_rtc_peripheral_status_reads_sidecar(monkeypatch)
    test_run_rtc_command_posts_to_sidecar(monkeypatch)
    test_hardware_rtc_status_endpoint_uses_probe(monkeypatch)
    test_hardware_rtc_command_endpoint_uses_probe(monkeypatch)
  tests/firmware/test_runtime_command_payload.py:
    e: test_extract_scenario_id_accepts_frontend_and_cli_keys,test_extract_inline_dsl_accepts_content_and_direct_fields
    test_extract_scenario_id_accepts_frontend_and_cli_keys()
    test_extract_inline_dsl_accepts_content_and_direct_fields()
  tests/firmware/test_safe_eval.py:
    e: _Obj,TestBasicComparisons,TestBooleanOps,TestChainedComparisons,TestNegativeNumbers,TestDottedAccess,TestErrorHandling,TestSecurity,TestFirmwareScenarios
    _Obj: __init__(0)
    TestBasicComparisons: test_eq_true(0),test_eq_false(0),test_ne_true(0),test_ne_false(0),test_lt(0),test_le(0),test_gt(0),test_ge(0),test_float_comparison(0)
    TestBooleanOps: test_and_true(0),test_and_false(0),test_or_true(0),test_or_false(0),test_not_true(0),test_not_false(0),test_complex_boolean(0)
    TestChainedComparisons: test_chained_lt(0),test_chained_le(0)
    TestNegativeNumbers: test_negative_literal(0),test_negative_context_value(0),test_unary_plus(0)
    TestDottedAccess: test_simple_attr(0),test_attr_comparison(0),test_unknown_attr_raises(0)
    TestErrorHandling: test_empty_string_raises(0),test_whitespace_only_raises(0),test_unknown_variable_raises(0),test_syntax_error_raises(0),test_unsupported_node_raises(0)
    TestSecurity: test_reject_function_call(0),test_reject_import(0),test_reject_lambda(0),test_reject_list_comprehension(0),test_reject_dict_literal(0),test_reject_subscript(0),test_reject_string_literal(0),test_reject_fstring(0),test_reject_walrus_operator(0),test_reject_attribute_dunder(0),test_reject_exec_via_eval(0),test_reject_getattr_builtin(0)  # Ensure the evaluator rejects any construct that could execut
    TestFirmwareScenarios: test_valve_pressure_check(0),test_pump_power_range(0),test_leak_rate_validation(0),test_sensor_threshold(0),test_boolean_context_value(0)  # Test expressions that mirror actual firmware validation cond
  tests/firmware/test_scanner_probe.py:
    e: test_scan_diagnostics_usb_ignores_crw_without_barcode_tokens,test_holtek_present_from_diagnostics_usb,test_enrich_scanner_adapter_adds_entry
    test_scan_diagnostics_usb_ignores_crw_without_barcode_tokens(monkeypatch)
    test_holtek_present_from_diagnostics_usb(monkeypatch)
    test_enrich_scanner_adapter_adds_entry(monkeypatch)
  tests/firmware/test_tic249_sidecar_control.py:
    e: test_ensure_skips_when_already_connected,test_ensure_restarts_when_listening_but_not_connected,test_ensure_reports_error_when_service_never_listens
    test_ensure_skips_when_already_connected(monkeypatch)
    test_ensure_restarts_when_listening_but_not_connected(monkeypatch)
    test_ensure_reports_error_when_service_never_listens(monkeypatch)
  tests/firmware/test_tic249_units.py:
    e: test_steps_per_second_to_raw_default_cap,test_raw_acceleration_for_ramp
    test_steps_per_second_to_raw_default_cap()
    test_raw_acceleration_for_ramp()
  tests/firmware/test_tokenizer_extended.py:
    e: TestValSingleQuote,TestMinMaxSingleQuote,TestIfElseSingleQuote,TestIfStandalone,TestElseStandalone,TestSample,TestGoto,TestFunc,TestSaveSingleQuote,TestWaitQuoted
    TestValSingleQuote: test_val_single_quote(0),test_val_double_quote(0),test_val_bracket(0)
    TestMinMaxSingleQuote: test_min_single_quote(0),test_max_single_quote(0),test_min_bracket(0),test_max_double_quote(0)
    TestIfElseSingleQuote: test_if_else_single_quote(0),test_if_else_bracket_single_error(0),test_if_else_bracket_double_error(0)
    TestIfStandalone: test_if_standalone_unicode_op(0),test_if_standalone_ascii_op(0),test_if_standalone_with_unit(0)
    TestElseStandalone: test_else_error(0),test_else_info(0)
    TestSample: test_sample_with_interval(0),test_sample_stop(0)
    TestGoto: test_goto(0)
    TestFunc: test_func_sub(0),test_func_div(0)
    TestSaveSingleQuote: test_save_single_simple(0),test_save_single_with_namespace(0)
    TestWaitQuoted: test_wait_quoted_seconds(0)
  tests/firmware/test_ui_routes_standard.py:
    e: client,test_legacy_panel_and_navigation_redirect_to_ui,test_ui_panel_and_navigation_serve_html,test_navigation_index_lists_ui_prefixed_pages
    client()
    test_legacy_panel_and_navigation_redirect_to_ui(client)
    test_ui_panel_and_navigation_serve_html(client)
    test_navigation_index_lists_ui_prefixed_pages(client)
  tests/firmware/test_usb_diagnostics.py:
    e: test_list_usb_devices_structure_and_no_hang,test_pi_system_diagnostics_has_expected_keys,test_reset_usb_device_not_found_is_clean_failure,test_manage_usb_list,test_manage_pi_diagnostics,test_manage_usb_reset_without_id_fails_cleanly,test_usb_verbs_listed
    test_list_usb_devices_structure_and_no_hang()
    test_pi_system_diagnostics_has_expected_keys()
    test_reset_usb_device_not_found_is_clean_failure()
    test_manage_usb_list()
    test_manage_pi_diagnostics()
    test_manage_usb_reset_without_id_fails_cleanly()
    test_usb_verbs_listed()
  tests/test_core.py:
    e: TestVariableStore,TestCqlParser,TestCqlValidator,TestCqlInterpreter,TestCqlExecuteMode,TestFirmwareAdapterUnit,TestEventStore
    TestVariableStore: test_set_get(0),test_interpolate_dollar(0),test_interpolate_braces(0),test_interpolate_missing(0)
    TestCqlParser: test_simple_metadata(0),test_parses_set_as_pump(0),test_parses_set_command_for_valve_and_compressor(0),test_simple_goals(0),test_simple_actions(0),test_connectgo_metadata(0),test_connectgo_intervals(0),test_connectgo_scenario(0),test_connectgo_goals(0),test_connectgo_steps(0),test_connectgo_arrow_action(0),test_connectgo_condition(0),test_connectgo_example_file(0)
    TestCqlValidator: test_valid_document(0),test_empty_document(0),test_invalid_interval_ref(0)
    TestCqlInterpreter: test_dry_run_simple(0),test_dry_run_with_sensors(0),test_validate_mode(0),test_set_actions_store_variables(0),test_variables_saved(0),test_connectgo_oql_example_file_dry_runs(0)
    TestCqlExecuteMode: test_execute_mode_initializes_firmware(0),test_pump_flow_uses_env_scale(1),test_pump_compact_liter_value_uses_flow_scale(1),test_version4_textual_hardware_set_values_execute(1),test_motor2_reciprocating_oql_execute_uses_reciprocate_not_relative_move(1),test_motor2_runtime_config_builds_volume_duration_plan(0),test_motor2_volume_duration_reciprocating_calculates_cycles_and_speed(1),test_motor2_volume_start_without_direction_defaults_left(1),test_motor2_acceleration_percent_above_100_is_preserved(1),test_repeat_stop_is_accepted_in_expanded_oql_repeat_blocks(0),test_pump_flow_scale_can_be_overridden_in_config_block(1),test_dry_run_does_not_use_firmware(0),test_auto_mock_seeds_default_sensors(0),test_auto_mock_range_condition_passes(0),test_auto_mock_disabled(0)
    TestFirmwareAdapterUnit: _firmware_with_post_response(1),test_peripheral_map_completeness(0),test_sensor_map(0),test_parse_numeric(0),test_resolve_peripheral(0),test_dispatch_confirm_no_http(0),test_set_peripheral_pump_rejects_nested_failed_response(0),test_dispatch_pump_reports_hardware_rejection(0),test_dispatch_lung_falls_back_to_direct_service_on_404(1)
    TestEventStore: test_append_and_get(0),test_get_recent(0),test_get_by_correlation(0),test_clear(0),test_json_roundtrip(0),test_persistence(1)
  tests/test_cql_cli.py:
    e: test_cmd_executes_single_command,test_cmd_parser_uses_oqlos_api_url_env_by_default,test_cmd_execute_aborts_when_hardware_is_unavailable,test_file_mode_still_executes_scenario,test_run_subcommand_executes_scenario_file,test_format_subcommand_prints_canonical_set_syntax,test_format_subcommand_write_updates_file,test_run_subcommand_fetches_scenario_url,test_fetch_scenario_source_rejects_editor_html,test_run_subcommand_reports_url_fetch_error,test_cmd_execute_mock_mode_error_suggests_dry_run_and_doctor,test_cmd_execute_blocks_when_required_adapter_health_is_bad,test_oqlctl_doctor_subcommand_dispatches_to_hardware_flags,test_oqlctl_status_flag_dispatches_without_file,test_result_payload_is_json_safe,_FakeInterpreter
    _FakeInterpreter: __init__(0),run(2)
    test_cmd_executes_single_command(monkeypatch)
    test_cmd_parser_uses_oqlos_api_url_env_by_default(monkeypatch)
    test_cmd_execute_aborts_when_hardware_is_unavailable(monkeypatch;capsys)
    test_file_mode_still_executes_scenario(monkeypatch;tmp_path)
    test_run_subcommand_executes_scenario_file(monkeypatch;tmp_path)
    test_format_subcommand_prints_canonical_set_syntax(monkeypatch;tmp_path;capsys)
    test_format_subcommand_write_updates_file(monkeypatch;tmp_path)
    test_run_subcommand_fetches_scenario_url(monkeypatch)
    test_fetch_scenario_source_rejects_editor_html(monkeypatch)
    test_run_subcommand_reports_url_fetch_error(monkeypatch;capsys)
    test_cmd_execute_mock_mode_error_suggests_dry_run_and_doctor(monkeypatch;capsys)
    test_cmd_execute_blocks_when_required_adapter_health_is_bad(monkeypatch;capsys)
    test_oqlctl_doctor_subcommand_dispatches_to_hardware_flags(monkeypatch)
    test_oqlctl_status_flag_dispatches_without_file(monkeypatch)
    test_result_payload_is_json_safe()
  tests/test_cql_inline_regressions.py:
    e: test_flat_if_with_variable_threshold_and_goto_skips_rest_of_goal,test_flat_if_else_error_pair_does_not_execute_else_when_condition_passes,test_compound_if_or_expression_is_supported_in_dry_run,test_func_actions_compute_values_for_following_conditions
    test_flat_if_with_variable_threshold_and_goto_skips_rest_of_goal()
    test_flat_if_else_error_pair_does_not_execute_else_when_condition_passes()
    test_compound_if_or_expression_is_supported_in_dry_run()
    test_func_actions_compute_values_for_following_conditions()
  tests/test_cql_scenarios.py:
    e: _collect,test_cql_db_scenario_dryrun,test_cql_hw_example_dryrun,test_cql_invalid_example_rejects_unknown_peripheral,test_cql_db_scenario_validate
    _collect(directory;ext)
    test_cql_db_scenario_dryrun(path)
    test_cql_hw_example_dryrun(path)
    test_cql_invalid_example_rejects_unknown_peripheral()
    test_cql_db_scenario_validate(path)
  tests/test_dsl_schema.py:
    e: test_default_schema_exposes_cql_and_oql_dialects,test_explicit_object_and_param_maps_override_inferred_fallbacks
    test_default_schema_exposes_cql_and_oql_dialects()
    test_explicit_object_and_param_maps_override_inferred_fallbacks()
  tests/test_oql_dry_run_regressions.py:
    e: test_block_if_else_error_attaches_to_else_branch,test_comment_only_if_block_does_not_capture_endif,test_oql_dry_run_supports_api_assert_shell_and_if_fail
    test_block_if_else_error_attaches_to_else_branch()
    test_comment_only_if_block_does_not_capture_endif()
    test_oql_dry_run_supports_api_assert_shell_and_if_fail()
  tests/test_oql_parser_v3.py:
    e: test_tokenize_simple,test_tokenize_brackets_allow_spaces,test_tokenize_double_quoted_string,test_tokenize_single_quoted_string,test_tokenize_unclosed_quote_raises,test_tokenize_unclosed_bracket_raises,test_duration_to_ms,test_parse_minimal_goal,test_parse_metadata,test_parse_check_range,test_parse_check_negative_values,test_parse_sample_with_interval,test_parse_if_delta_signed_threshold,test_parse_unicode_identifiers,test_parse_bracketed_target_with_spaces,test_parse_bracketed_block_name,test_parse_rejects_unindented_command,test_parse_rejects_unknown_command,test_parse_v4_goal_requires_set_name,test_parse_v4_rejects_inline_goal_name,test_parse_v4_goal_name_from_set_name,test_parse_rejects_unsupported_oql_version,test_base_commands_list_matches_dispatcher,test_is_flat_oql_detects_new_syntax,test_is_flat_oql_rejects_legacy,test_adapter_produces_cql_goals,test_adapter_config_prefix,test_version4_set_accepts_textual_hardware_values,test_version4_repeat_count_expands_indented_block,test_macro_call_expansion,test_unknown_macro_becomes_error_action,test_include_resolves_from_scenarios_root,test_include_missing_file_yields_error,test_check_with_correct_message,test_check_with_error_message,test_check_with_both_messages,test_correct_without_check_is_error,test_adapter_uses_custom_messages,test_adapter_if_delta_uses_custom_messages_and_delta_sensor
    test_tokenize_simple()
    test_tokenize_brackets_allow_spaces()
    test_tokenize_double_quoted_string()
    test_tokenize_single_quoted_string()
    test_tokenize_unclosed_quote_raises()
    test_tokenize_unclosed_bracket_raises()
    test_duration_to_ms(token;expected)
    test_parse_minimal_goal()
    test_parse_metadata()
    test_parse_check_range()
    test_parse_check_negative_values()
    test_parse_sample_with_interval()
    test_parse_if_delta_signed_threshold()
    test_parse_unicode_identifiers()
    test_parse_bracketed_target_with_spaces()
    test_parse_bracketed_block_name()
    test_parse_rejects_unindented_command()
    test_parse_rejects_unknown_command()
    test_parse_v4_goal_requires_set_name()
    test_parse_v4_rejects_inline_goal_name()
    test_parse_v4_goal_name_from_set_name()
    test_parse_rejects_unsupported_oql_version()
    test_base_commands_list_matches_dispatcher()
    test_is_flat_oql_detects_new_syntax()
    test_is_flat_oql_rejects_legacy()
    test_adapter_produces_cql_goals()
    test_adapter_config_prefix()
    test_version4_set_accepts_textual_hardware_values()
    test_version4_repeat_count_expands_indented_block()
    test_macro_call_expansion()
    test_unknown_macro_becomes_error_action()
    test_include_resolves_from_scenarios_root()
    test_include_missing_file_yields_error()
    test_check_with_correct_message()
    test_check_with_error_message()
    test_check_with_both_messages()
    test_correct_without_check_is_error()
    test_adapter_uses_custom_messages()
    test_adapter_if_delta_uses_custom_messages_and_delta_sensor()
  tests/test_oql_scenarios.py:
    e: _collect,test_oql_scenario_dryrun,test_oql_example_dryrun,test_oql_scenario_validate
    _collect(directory;ext)
    test_oql_scenario_dryrun(path)
    test_oql_example_dryrun(path)
    test_oql_scenario_validate(path)
  tests/test_reporting.py:
    e: test_reporting,MockWS,MockBridge
    MockWS: send(1),close(0)
    MockBridge: __init__(0),send_event(2)
    test_reporting()
  tests/test_scenarios_dir.py:
    e: test_default_scenarios_dir_points_at_repo_root
    test_default_scenarios_dir_points_at_repo_root()
  tests/test_scenarios_legacy_aliases.py:
    e: test_legacy_alias_map_covers_renamed_exports,test_scenarios_root_has_no_ts_prefix_files
    test_legacy_alias_map_covers_renamed_exports()
    test_scenarios_root_has_no_ts_prefix_files()
  tests/test_xml_import_generators.py:
    e: test_generate_cql_uses_canonical_set_syntax
    test_generate_cql_uses_canonical_set_syntax()
  tests/verify_block_if.py:
    e: test_block_if
    test_block_if()
  tests/verify_loops.py:
    e: test_loops
    test_loops()
```

### `project/logic.pl`

```prolog markpact:analysis path=project/logic.pl
% ── Project Metadata ─────────────────────────────────────
project_metadata('oqlos', '0.1.28', 'python').

% ── Project Files ────────────────────────────────────────
project_file('app.doql.css', 165, 'css').
project_file('app.doql.less', 316, 'less').
project_file('examples/curl-quickstart.sh', 75, 'shell').
project_file('examples/hardware/doctor-workflow.sh', 53, 'shell').
project_file('frontend/src/api/hardware-api-errors.js', 88, 'javascript').
project_file('frontend/src/api/hardware-api-errors.test.js', 80, 'javascript').
project_file('frontend/src/api/hardware-api-log.js', 88, 'javascript').
project_file('frontend/src/api/hardware-diagnostic-failure.js', 98, 'javascript').
project_file('frontend/src/api/hardware-diagnostic-failure.test.js', 59, 'javascript').
project_file('frontend/src/api/hardware-tic249-status.js', 36, 'javascript').
project_file('frontend/src/api/hardwareApi.js', 258, 'javascript').
project_file('frontend/src/api/scenarioFilesApi.js', 80, 'javascript').
project_file('frontend/src/api/wsClient.js', 139, 'javascript').
project_file('frontend/src/context/app-config-document.js', 27, 'javascript').
project_file('frontend/src/hooks/useMapEditorHardwareEvents.js', 62, 'javascript').
project_file('frontend/src/hooks/useMapEditorSidebarAutoCollapse.js', 30, 'javascript').
project_file('frontend/src/hooks/useParentEncoderNavigation.js', 40, 'javascript').
project_file('frontend/src/hooks/useRailHoverPreview.js', 85, 'javascript').
project_file('frontend/src/hooks/useUrlConfig.js', 86, 'javascript').
project_file('frontend/src/hooks/useWsStatus.js', 27, 'javascript').
project_file('frontend/src/i18n/dictionaries.js', 2136, 'javascript').
project_file('frontend/src/i18n/hardware-demo-extra-translations.js', 184, 'javascript').
project_file('frontend/src/i18n/hardware-status-log-translations.js', 82, 'javascript').
project_file('frontend/src/i18n/hardware-status-panel-translations.js', 328, 'javascript').
project_file('frontend/src/i18n/hardware-status-presets-translations.js', 796, 'javascript').
project_file('frontend/src/pages/mapEditorConstants.js', 42, 'javascript').
project_file('frontend/src/pages/mapEditorDefaultMap.js', 1954, 'javascript').
project_file('frontend/src/styles/global.css', 2324, 'css').
project_file('frontend/src/utils/collapse-toggle-bridge.js', 61, 'javascript').
project_file('frontend/src/utils/designRem.js', 44, 'javascript').
project_file('frontend/src/utils/encoder-navigation.js', 143, 'javascript').
project_file('frontend/src/utils/encoder-navigation.test.js', 21, 'javascript').
project_file('frontend/src/utils/hardware-activity-log.js', 35, 'javascript').
project_file('frontend/src/utils/hardware-api-retry.js', 39, 'javascript').
project_file('frontend/src/utils/hardware-api-retry.test.js', 46, 'javascript').
project_file('frontend/src/utils/hardware-demo-identify.js', 86, 'javascript').
project_file('frontend/src/utils/hardware-demo-identify.test.js', 28, 'javascript').
project_file('frontend/src/utils/hardware-restart-configure.js', 69, 'javascript').
project_file('frontend/src/utils/hardware-restart-configure.test.js', 31, 'javascript').
project_file('frontend/src/utils/hardware-restart-docs.js', 12, 'javascript').
project_file('frontend/src/utils/hardware-restart-probe-select.js', 20, 'javascript').
project_file('frontend/src/utils/hardware-restart-step-errors.js', 16, 'javascript').
project_file('frontend/src/utils/hardware-restart-step-outcome.js', 7, 'javascript').
project_file('frontend/src/utils/hardware-restart-step-runner.js', 24, 'javascript').
project_file('frontend/src/utils/hardware-restart-step-runner.test.js', 18, 'javascript').
project_file('frontend/src/utils/hardware-restart-wizard-helpers.js', 42, 'javascript').
project_file('frontend/src/utils/hardware-restart-wizard-steps.js', 47, 'javascript').
project_file('frontend/src/utils/hardware-restart-wizard-steps.test.js', 32, 'javascript').
project_file('frontend/src/utils/hardware-time.js', 5, 'javascript').
project_file('frontend/src/utils/hardware-wizard-plan.js', 42, 'javascript').
project_file('frontend/src/utils/hardware-wizard-plan.test.js', 17, 'javascript').
project_file('frontend/src/utils/hardware-wizard-steps.js', 102, 'javascript').
project_file('frontend/src/utils/hardware-wizard-steps.test.js', 30, 'javascript').
project_file('frontend/src/utils/hardwareEventStream.js', 53, 'javascript').
project_file('frontend/src/utils/hardwareEventStream.test.js', 37, 'javascript').
project_file('frontend/src/utils/hardwareStatusModel.js', 39, 'javascript').
project_file('frontend/src/utils/hardwareStatusModel.test.js', 44, 'javascript').
project_file('frontend/src/utils/hui-shell-key.js', 39, 'javascript').
project_file('frontend/src/utils/mapEditorFuncHardwareSummary.js', 84, 'javascript').
project_file('frontend/src/utils/mapEditorFuncHardwareSummary.test.js', 55, 'javascript').
project_file('frontend/src/utils/mapEditorIntegrationMeta.js', 81, 'javascript').
project_file('frontend/src/utils/mapEditorIntegrationMeta.test.js', 44, 'javascript').
project_file('frontend/src/utils/mapEditorMapShape.js', 59, 'javascript').
project_file('frontend/src/utils/mapEditorModel.js', 84, 'javascript').
project_file('frontend/src/utils/mapEditorModel.test.js', 33, 'javascript').
project_file('frontend/src/utils/mapEditorObjectActionEdits.js', 45, 'javascript').
project_file('frontend/src/utils/mapEditorObjectActionEdits.test.js', 34, 'javascript').
project_file('frontend/src/utils/mapEditorTic249.js', 8, 'javascript').
project_file('frontend/src/utils/mapEditorTic249.test.js', 14, 'javascript').
project_file('frontend/src/utils/oqlGoals.js', 86, 'javascript').
project_file('frontend/src/utils/oqlGoals.test.js', 56, 'javascript').
project_file('frontend/src/utils/parentUrlBridge.js', 40, 'javascript').
project_file('frontend/src/utils/rbac.policy.js', 125, 'javascript').
project_file('frontend/src/utils/scenarioFilesUrl.js', 68, 'javascript').
project_file('frontend/src/utils/scenarioFilesUrl.test.js', 72, 'javascript').
project_file('frontend/src/utils/url-embed-config.js', 194, 'javascript').
project_file('frontend/src/utils/url-embed-config.test.js', 93, 'javascript').
project_file('frontend/src/utils/useSelectionCollapsePanel.js', 160, 'javascript').
project_file('frontend/vendor/hardware-client/index.ts', 32, 'typescript').
project_file('frontend/vendor/hardware-client/paths.ts', 40, 'typescript').
project_file('frontend/vite.config.ts', 37, 'typescript').
project_file('oqlos/__init__.py', 4, 'python').
project_file('oqlos/api/__init__.py', 18, 'python').
project_file('oqlos/api/_hw3_mapping.py', 158, 'python').
project_file('oqlos/api/_hw3_models.py', 195, 'python').
project_file('oqlos/api/_hw3_peripheral.py', 134, 'python').
project_file('oqlos/api/_hw3_system.py', 135, 'python').
project_file('oqlos/api/editor.py', 201, 'python').
project_file('oqlos/api/execution.py', 359, 'python').
project_file('oqlos/api/hardware.py', 86, 'python').
project_file('oqlos/api/hardware_actuators.py', 24, 'python').
project_file('oqlos/api/hardware_diagnosis_routes.py', 57, 'python').
project_file('oqlos/api/hardware_events.py', 137, 'python').
project_file('oqlos/api/hardware_gateway.py', 35, 'python').
project_file('oqlos/api/hardware_hui.py', 62, 'python').
project_file('oqlos/api/hardware_identify.py', 171, 'python').
project_file('oqlos/api/hardware_lung.py', 86, 'python').
project_file('oqlos/api/hardware_mapping_contract.py', 64, 'python').
project_file('oqlos/api/hardware_mapping_motor2.py', 49, 'python').
project_file('oqlos/api/hardware_mapping_store.py', 153, 'python').
project_file('oqlos/api/hardware_modbus_routes.py', 80, 'python').
project_file('oqlos/api/hardware_modbus_topology.py', 93, 'python').
project_file('oqlos/api/hardware_modbus_waveshare.py', 622, 'python').
project_file('oqlos/api/hardware_modbus_wizard.py', 400, 'python').
project_file('oqlos/api/hardware_peripherals_routes.py', 91, 'python').
project_file('oqlos/api/hardware_platform.py', 166, 'python').
project_file('oqlos/api/hardware_probe.py', 135, 'python').
project_file('oqlos/api/hardware_probe_devices.py', 189, 'python').
project_file('oqlos/api/hardware_registry.py', 62, 'python').
project_file('oqlos/api/hardware_runtime.py', 190, 'python').
project_file('oqlos/api/hardware_v3.py', 61, 'python').
project_file('oqlos/api/logs.py', 46, 'python').
project_file('oqlos/api/main.py', 606, 'python').
project_file('oqlos/api/oql_mqtt.py', 153, 'python').
project_file('oqlos/api/peripherals.py', 69, 'python').
project_file('oqlos/api/plugins.py', 182, 'python').
project_file('oqlos/api/scenarios.py', 252, 'python').
project_file('oqlos/api/state.py', 371, 'python').
project_file('oqlos/api/utils/__init__.py', 1, 'python').
project_file('oqlos/api/utils/execution_ctrl.py', 63, 'python').
project_file('oqlos/api/version.py', 25, 'python').
project_file('oqlos/config.py', 221, 'python').
project_file('oqlos/core/__init__.py', 1, 'python').
project_file('oqlos/core/_action_motor2.py', 482, 'python').
project_file('oqlos/core/_compare.py', 41, 'python').
project_file('oqlos/core/_cql_tokenizer.py', 411, 'python').
project_file('oqlos/core/_cql_tree_builder.py', 168, 'python').
project_file('oqlos/core/_dsl_helpers.py', 133, 'python').
project_file('oqlos/core/_firmware_executor.py', 267, 'python').
project_file('oqlos/core/_func_resolver.py', 97, 'python').
project_file('oqlos/core/_interpreter_actions.py', 801, 'python').
project_file('oqlos/core/_line_parsers.py', 262, 'python').
project_file('oqlos/core/_oql_adapter.py', 491, 'python').
project_file('oqlos/core/_sensor_evaluator.py', 146, 'python').
project_file('oqlos/core/_value_normalizers.py', 127, 'python').
project_file('oqlos/core/base.py', 312, 'python').
project_file('oqlos/core/cql_parser.py', 468, 'python').
project_file('oqlos/core/executor.py', 378, 'python').
project_file('oqlos/core/interpreter.py', 691, 'python').
project_file('oqlos/core/motor2_runtime.py', 210, 'python').
project_file('oqlos/core/oql_parser.py', 774, 'python').
project_file('oqlos/core/oql_versioning.py', 73, 'python').
project_file('oqlos/core/parser.py', 185, 'python').
project_file('oqlos/core/safe_eval.py', 139, 'python').
project_file('oqlos/core/state.py', 125, 'python').
project_file('oqlos/dsl/__init__.py', 19, 'python').
project_file('oqlos/dsl/schema.py', 296, 'python').
project_file('oqlos/errors/__init__.py', 44, 'python').
project_file('oqlos/errors/catalog.py', 314, 'python').
project_file('oqlos/errors/exceptions.py', 60, 'python').
project_file('oqlos/errors/fastapi_integration.py', 24, 'python').
project_file('oqlos/errors/repair_commit.py', 41, 'python').
project_file('oqlos/hardware/__init__.py', 18, 'python').
project_file('oqlos/hardware/artificial_lung.py', 163, 'python').
project_file('oqlos/hardware/client/__init__.py', 101, 'python').
project_file('oqlos/hardware/client/adc.py', 65, 'python').
project_file('oqlos/hardware/client/autorepair.py', 134, 'python').
project_file('oqlos/hardware/client/config.py', 87, 'python').
project_file('oqlos/hardware/client/constants.py', 70, 'python').
project_file('oqlos/hardware/client/errors.py', 27, 'python').
project_file('oqlos/hardware/client/http_helpers.py', 27, 'python').
project_file('oqlos/hardware/client/identify_enrich.py', 79, 'python').
project_file('oqlos/hardware/client/identify_enrich_adapters.py', 191, 'python').
project_file('oqlos/hardware/client/identify_enrich_modbus_io.py', 90, 'python').
project_file('oqlos/hardware/client/modbus_repair.py', 165, 'python').
project_file('oqlos/hardware/client/platform.py', 51, 'python').
project_file('oqlos/hardware/client/proxy.py', 461, 'python').
project_file('oqlos/hardware/client/resolvers.py', 129, 'python').
project_file('oqlos/hardware/client/tic249_arg_contract.py', 66, 'python').
project_file('oqlos/hardware/client/tic249_arg_helpers.py', 12, 'python').
project_file('oqlos/hardware/client/tic249_command_mapping.py', 50, 'python').
project_file('oqlos/hardware/client/tic249_error_messages.py', 113, 'python').
project_file('oqlos/hardware/client/tic249_extended.py', 216, 'python').
project_file('oqlos/hardware/client/tic249_motion_params.py', 128, 'python').
project_file('oqlos/hardware/client/tic249_rig_direction.py', 44, 'python').
project_file('oqlos/hardware/client/tic249_sidecar_client.py', 184, 'python').
project_file('oqlos/hardware/config_paths.py', 42, 'python').
project_file('oqlos/hardware/config_schema.py', 142, 'python').
project_file('oqlos/hardware/control_proxy.py', 69, 'python').
project_file('oqlos/hardware/diagnosis.py', 247, 'python').
project_file('oqlos/hardware/diagnosis_device_actions.py', 222, 'python').
project_file('oqlos/hardware/diagnosis_plugin_health.py', 87, 'python').
project_file('oqlos/hardware/diagnosis_types.py', 87, 'python').
project_file('oqlos/hardware/discovery.py', 164, 'python').
project_file('oqlos/hardware/drivers/__init__.py', 6, 'python').
project_file('oqlos/hardware/drivers/gpio.py', 90, 'python').
project_file('oqlos/hardware/drivers/mqtt.py', 120, 'python').
project_file('oqlos/hardware/drivers/spi.py', 93, 'python').
project_file('oqlos/hardware/firmware_adapter.py', 481, 'python').
project_file('oqlos/hardware/gateway.py', 387, 'python').
project_file('oqlos/hardware/gateway_http.py', 24, 'python').
project_file('oqlos/hardware/health_status.py', 27, 'python').
project_file('oqlos/hardware/hui_actions.py', 66, 'python').
project_file('oqlos/hardware/hui_artificial_lung.py', 86, 'python').
project_file('oqlos/hardware/hui_hold.py', 257, 'python').
project_file('oqlos/hardware/hui_lung_recipe.py', 148, 'python').
project_file('oqlos/hardware/identify_enrichment.py', 19, 'python').
project_file('oqlos/hardware/modbus_identify.py', 132, 'python').
project_file('oqlos/hardware/peripheral_mapping.py', 137, 'python').
project_file('oqlos/hardware/plugin_gateway.py', 635, 'python').
project_file('oqlos/hardware/plugins/__init__.py', 50, 'python').
project_file('oqlos/hardware/plugins/_rtu_serial.py', 48, 'python').
project_file('oqlos/hardware/plugins/_shared.py', 67, 'python').
project_file('oqlos/hardware/plugins/base.py', 371, 'python').
project_file('oqlos/hardware/plugins/lung.py', 354, 'python').
project_file('oqlos/hardware/plugins/modbus.py', 330, 'python').
project_file('oqlos/hardware/plugins/modbus_adc.py', 393, 'python').
project_file('oqlos/hardware/plugins/motor.py', 406, 'python').
project_file('oqlos/hardware/plugins/motor_http_handlers.py', 68, 'python').
project_file('oqlos/hardware/plugins/motor_modbus_handlers.py', 208, 'python').
project_file('oqlos/hardware/plugins/piadc.py', 263, 'python').
project_file('oqlos/hardware/plugins/plugin_http_handlers.py', 33, 'python').
project_file('oqlos/hardware/plugins/registry.py', 333, 'python').
project_file('oqlos/hardware/protocol.py', 61, 'python').
project_file('oqlos/hardware/registry.py', 50, 'python').
project_file('oqlos/hardware/rtc_probe.py', 198, 'python').
project_file('oqlos/hardware/scanner_probe.py', 261, 'python').
project_file('oqlos/hardware/sidecar_control.py', 329, 'python').
project_file('oqlos/hardware/stack_snapshot.py', 89, 'python').
project_file('oqlos/hardware/tic249_units.py', 40, 'python').
project_file('oqlos/hardware/transport/__init__.py', 25, 'python').
project_file('oqlos/hardware/transport/manage_ops.py', 154, 'python').
project_file('oqlos/hardware/transport/manage_ops_diagnostic.py', 148, 'python').
project_file('oqlos/hardware/transport/manage_ops_usb.py', 34, 'python').
project_file('oqlos/hardware/transport/mqtt_oql_bridge.py', 494, 'python').
project_file('oqlos/hardware/usb_diagnostics.py', 186, 'python').
project_file('oqlos/ide/__init__.py', 1, 'python').
project_file('oqlos/models/__init__.py', 1, 'python').
project_file('oqlos/models/dsl_models.py', 88, 'python').
project_file('oqlos/models/execution.py', 23, 'python').
project_file('oqlos/models/peripheral.py', 34, 'python').
project_file('oqlos/models/scenario.py', 36, 'python').
project_file('oqlos/reporters/__init__.py', 7, 'python').
project_file('oqlos/reporters/html_report.py', 267, 'python').
project_file('oqlos/reporters/json_reporter.py', 139, 'python').
project_file('oqlos/reporters/junit.py', 87, 'python').
project_file('oqlos/scenarios/legacy_aliases.py', 41, 'python').
project_file('oqlos/shared/__init__.py', 1, 'python').
project_file('oqlos/shared/_endpoint_helpers.py', 49, 'python').
project_file('oqlos/shared/config_factory.py', 85, 'python').
project_file('oqlos/shared/event_server.py', 172, 'python').
project_file('oqlos/shared/event_store.py', 78, 'python').
project_file('oqlos/shared/file_ops.py', 131, 'python').
project_file('oqlos/shared/logger.py', 90, 'python').
project_file('oqlos/shared/logs_query.py', 146, 'python').
project_file('oqlos/shared/release_version.py', 126, 'python').
project_file('oqlos/shared/version_endpoint.py', 67, 'python').
project_file('oqlos/tools/__init__.py', 1, 'python').
project_file('oqlos/tools/cql_cli/__init__.py', 67, 'python').
project_file('oqlos/tools/cql_cli/commands.py', 193, 'python').
project_file('oqlos/tools/cql_cli/formatting.py', 64, 'python').
project_file('oqlos/tools/cql_cli/main.py', 416, 'python').
project_file('oqlos/tools/cql_cli/preflight.py', 310, 'python').
project_file('oqlos/tools/cql_cli/utils.py', 151, 'python').
project_file('oqlos/tools/gen_error_docs.py', 108, 'python').
project_file('oqlos/tools/hardware_diagnose/__init__.py', 74, 'python').
project_file('oqlos/tools/hardware_diagnose/__main__.py', 185, 'python').
project_file('oqlos/tools/hardware_diagnose/benchmark.py', 56, 'python').
project_file('oqlos/tools/hardware_diagnose/calibration.py', 93, 'python').
project_file('oqlos/tools/hardware_diagnose/discovery.py', 100, 'python').
project_file('oqlos/tools/hardware_diagnose/doctor.py', 94, 'python').
project_file('oqlos/tools/hardware_diagnose/doctor_common.py', 67, 'python').
project_file('oqlos/tools/hardware_diagnose/doctor_detection.py', 131, 'python').
project_file('oqlos/tools/hardware_diagnose/doctor_firmware.py', 227, 'python').
project_file('oqlos/tools/hardware_diagnose/doctor_format.py', 109, 'python').
project_file('oqlos/tools/hardware_diagnose/doctor_modbus_analysis.py', 253, 'python').
project_file('oqlos/tools/hardware_diagnose/doctor_repairs.py', 120, 'python').
project_file('oqlos/tools/hardware_diagnose/doctor_serial.py', 91, 'python').
project_file('oqlos/tools/hardware_diagnose/health.py', 118, 'python').
project_file('oqlos/tools/hardware_diagnose/modbus_probe.py', 209, 'python').
project_file('oqlos/tools/hardware_diagnose/report.py', 64, 'python').
project_file('oqlos/tools/hardware_diagnose/shell.py', 139, 'python').
project_file('oqlos/tools/hardware_diagnose.py', 37, 'python').
project_file('oqlos/tools/plugin_cli.py', 344, 'python').
project_file('oqlos/tools/xml_import/__init__.py', 18, 'python').
project_file('oqlos/tools/xml_import/_utils.py', 102, 'python').
project_file('oqlos/tools/xml_import/generators.py', 453, 'python').
project_file('oqlos/tools/xml_import/models.py', 91, 'python').
project_file('oqlos/tools/xml_import/parser.py', 176, 'python').
project_file('oqlos/utils/__init__.py', 4, 'python').
project_file('oqlos/utils/hui_scenario.py', 47, 'python').
project_file('oqlos/utils/sample_data.py', 74, 'python').
project_file('project.sh', 43, 'shell').
project_file('scripts/fix_brackets_to_v4.py', 96, 'python').
project_file('scripts/gen-checksums.sh', 28, 'shell').
project_file('scripts/hardware-check.sh', 341, 'shell').
project_file('scripts/migrate_to_v4.py', 338, 'python').
project_file('scripts/oql-stack.sh', 105, 'shell').
project_file('scripts/oql_v2_to_v4_migrate_db.py', 663, 'python').
project_file('scripts/oql_v2_validator.py', 225, 'python').
project_file('scripts/oql_v4_validator.py', 282, 'python').
project_file('scripts/oql_validator_common.py', 130, 'python').
project_file('scripts/provision-rpi-sudo.sh', 68, 'shell').
project_file('scripts/scenarios_export.py', 297, 'python').
project_file('scripts/test-hardware.sh', 84, 'shell').
project_file('scripts/verify-rpi-checksum.sh', 76, 'shell').
project_file('setup_hardware_and_run_oql.py', 334, 'python').
project_file('tests/firmware/test_artificial_lung.py', 44, 'python').
project_file('tests/firmware/test_control_proxy.py', 204, 'python').
project_file('tests/firmware/test_dri0050_sidecar_control.py', 84, 'python').
project_file('tests/firmware/test_dsl_parser_runtime.py', 157, 'python').
project_file('tests/firmware/test_error_catalog.py', 76, 'python').
project_file('tests/firmware/test_firmware.py', 10, 'python').
project_file('tests/firmware/test_firmware_executor.py', 132, 'python').
project_file('tests/firmware/test_gateway_http.py', 51, 'python').
project_file('tests/firmware/test_hardware_diagnosis_api.py', 114, 'python').
project_file('tests/firmware/test_hardware_diagnosis_routes.py', 40, 'python').
project_file('tests/firmware/test_hardware_discovery.py', 32, 'python').
project_file('tests/firmware/test_hardware_doctor.py', 287, 'python').
project_file('tests/firmware/test_hardware_health.py', 44, 'python').
project_file('tests/firmware/test_hardware_health_http.py', 61, 'python').
project_file('tests/firmware/test_hardware_hui_routes.py', 44, 'python').
project_file('tests/firmware/test_hardware_identify.py', 236, 'python').
project_file('tests/firmware/test_hardware_identify_routes.py', 10, 'python').
project_file('tests/firmware/test_hardware_lung_routes.py', 24, 'python').
project_file('tests/firmware/test_hardware_mapping_motor2.py', 30, 'python').
project_file('tests/firmware/test_hardware_modbus_routes.py', 12, 'python').
project_file('tests/firmware/test_hardware_modbus_wizard.py', 353, 'python').
project_file('tests/firmware/test_hardware_platform_detect.py', 31, 'python').
project_file('tests/firmware/test_hardware_probe_devices.py', 27, 'python').
project_file('tests/firmware/test_hardware_runtime_routes.py', 52, 'python').
project_file('tests/firmware/test_hardware_stack_snapshot.py', 46, 'python').
project_file('tests/firmware/test_hardware_v3_compat.py', 164, 'python').
project_file('tests/firmware/test_hui_actions.py', 201, 'python').
project_file('tests/firmware/test_hui_scenario.py', 12, 'python').
project_file('tests/firmware/test_identify_enrich_modbus_io.py', 24, 'python').
project_file('tests/firmware/test_lung_integration.py', 282, 'python').
project_file('tests/firmware/test_lung_plugin_reciprocate.py', 94, 'python').
project_file('tests/firmware/test_modbus_adc_aliases.py', 9, 'python').
project_file('tests/firmware/test_modbus_discovery.py', 111, 'python').
project_file('tests/firmware/test_modbus_identify.py', 41, 'python').
project_file('tests/firmware/test_modbus_probe_cli.py', 130, 'python').
project_file('tests/firmware/test_motor_http_handlers.py', 82, 'python').
project_file('tests/firmware/test_motor_modbus_handlers.py', 110, 'python').
project_file('tests/firmware/test_motor_plugin.py', 74, 'python').
project_file('tests/firmware/test_normalize_scenario.py', 200, 'python').
project_file('tests/firmware/test_oql_envelope.py', 74, 'python').
project_file('tests/firmware/test_oql_manage_ops.py', 245, 'python').
project_file('tests/firmware/test_oql_mqtt_bridge.py', 258, 'python').
project_file('tests/firmware/test_oql_route_http.py', 140, 'python').
project_file('tests/firmware/test_oqlos_error.py', 91, 'python').
project_file('tests/firmware/test_oqlos_logging.py', 21, 'python').
project_file('tests/firmware/test_panel_ui.py', 250, 'python').
project_file('tests/firmware/test_parser_cycle.py', 53, 'python').
project_file('tests/firmware/test_plugin_gateway_env.py', 243, 'python').
project_file('tests/firmware/test_plugin_gateway_init.py', 67, 'python').
project_file('tests/firmware/test_plugin_health.py', 340, 'python').
project_file('tests/firmware/test_plugin_http_handlers.py', 68, 'python').
project_file('tests/firmware/test_plugins_api.py', 31, 'python').
project_file('tests/firmware/test_plugins_health_http.py', 57, 'python').
project_file('tests/firmware/test_repair_commit.py', 67, 'python').
project_file('tests/firmware/test_rtc_probe.py', 132, 'python').
project_file('tests/firmware/test_runtime_command_payload.py', 16, 'python').
project_file('tests/firmware/test_safe_eval.py', 244, 'python').
project_file('tests/firmware/test_scanner_probe.py', 68, 'python').
project_file('tests/firmware/test_tic249_sidecar_control.py', 69, 'python').
project_file('tests/firmware/test_tic249_units.py', 18, 'python').
project_file('tests/firmware/test_tokenizer_extended.py', 194, 'python').
project_file('tests/firmware/test_ui_routes_standard.py', 49, 'python').
project_file('tests/firmware/test_usb_diagnostics.py', 63, 'python').
project_file('tests/test_core.py', 853, 'python').
project_file('tests/test_cql_cli.py', 417, 'python').
project_file('tests/test_cql_inline_regressions.py', 74, 'python').
project_file('tests/test_cql_scenarios.py', 88, 'python').
project_file('tests/test_dsl_schema.py', 20, 'python').
project_file('tests/test_oql_dry_run_regressions.py', 62, 'python').
project_file('tests/test_oql_parser_v3.py', 492, 'python').
project_file('tests/test_oql_scenarios.py', 74, 'python').
project_file('tests/test_reporting.py', 46, 'python').
project_file('tests/test_scenarios_dir.py', 18, 'python').
project_file('tests/test_scenarios_legacy_aliases.py', 24, 'python').
project_file('tests/test_xml_import_generators.py', 29, 'python').
project_file('tests/verify_block_if.py', 61, 'python').
project_file('tests/verify_loops.py', 34, 'python').

% ── Python Functions ─────────────────────────────────────
python_function('oqlos/api/_hw3_mapping.py', 'hardware_runtime_python_resolve_func_v3', 1, 3, 4).
python_function('oqlos/api/_hw3_mapping.py', 'hardware_mapping_get_v3', 0, 1, 1).
python_function('oqlos/api/_hw3_mapping.py', 'hardware_mapping_schema_v3', 0, 1, 1).
python_function('oqlos/api/_hw3_mapping.py', 'hardware_mapping_put_v3', 1, 2, 3).
python_function('oqlos/api/_hw3_mapping.py', 'hardware_mapping_import_v3', 1, 3, 4).
python_function('oqlos/api/_hw3_mapping.py', 'hardware_mapping_export_v3', 1, 2, 4).
python_function('oqlos/api/_hw3_mapping.py', 'hardware_mapping_reset_v3', 1, 1, 2).
python_function('oqlos/api/_hw3_mapping.py', 'hardware_oql_mapped_exec_v3', 1, 3, 6).
python_function('oqlos/api/_hw3_mapping.py', 'hardware_cqrs_command_v3', 1, 10, 8).
python_function('oqlos/api/_hw3_mapping.py', 'hardware_cqrs_events_v3', 1, 1, 5).
python_function('oqlos/api/_hw3_mapping.py', 'hardware_cqrs_events_clear_v3', 1, 1, 3).
python_function('oqlos/api/_hw3_mapping.py', 'hardware_events_ws', 1, 4, 6).
python_function('oqlos/api/_hw3_models.py', 'normalize_peripheral_id', 1, 2, 5).
python_function('oqlos/api/_hw3_models.py', '_ok_from_result', 1, 5, 3).
python_function('oqlos/api/_hw3_models.py', '_runtime_control_skipped', 1, 1, 0).
python_function('oqlos/api/_hw3_models.py', '_find_adapter', 2, 5, 2).
python_function('oqlos/api/_hw3_models.py', '_run_diagnostic', 3, 6, 8).
python_function('oqlos/api/_hw3_models.py', '_resolve_func_steps', 4, 14, 3).
python_function('oqlos/api/_hw3_models.py', '_hardware_v1_call', 1, 1, 1).
python_function('oqlos/api/_hw3_peripheral.py', 'hardware_peripheral_status_v3', 1, 11, 9).
python_function('oqlos/api/_hw3_peripheral.py', 'hardware_diagnostic_command_v3', 1, 3, 5).
python_function('oqlos/api/_hw3_peripheral.py', 'hardware_scanner_status_v3', 0, 5, 5).
python_function('oqlos/api/_hw3_peripheral.py', 'hardware_scanner_last_v3', 0, 1, 1).
python_function('oqlos/api/_hw3_peripheral.py', 'hardware_scanner_ingest_v3', 1, 2, 3).
python_function('oqlos/api/_hw3_system.py', 'hardware_hui_actions_v3', 0, 1, 2).
python_function('oqlos/api/_hw3_system.py', 'hardware_hui_shutdown_v3', 1, 1, 3).
python_function('oqlos/api/_hw3_system.py', '_hardware_hui_hold_v3', 2, 2, 1).
python_function('oqlos/api/_hw3_system.py', 'hardware_hui_hold_start_v3', 2, 1, 3).
python_function('oqlos/api/_hw3_system.py', 'hardware_hui_hold_stop_v3', 2, 1, 3).
python_function('oqlos/api/_hw3_system.py', 'hardware_hui_al_command_v3', 2, 3, 7).
python_function('oqlos/api/_hw3_system.py', 'hardware_modbus_autoconfigure_v3', 0, 1, 2).
python_function('oqlos/api/_hw3_system.py', 'hardware_diagnosis_v3', 0, 1, 2).
python_function('oqlos/api/_hw3_system.py', 'hardware_diagnosis_repair_v3', 0, 1, 2).
python_function('oqlos/api/_hw3_system.py', 'hardware_modbus_waveshare_diagnose_v3', 1, 1, 2).
python_function('oqlos/api/_hw3_system.py', 'hardware_modbus_wizard_plan_v3', 0, 1, 2).
python_function('oqlos/api/_hw3_system.py', 'hardware_stack_snapshot_v3', 0, 1, 2).
python_function('oqlos/api/_hw3_system.py', 'hardware_runtime_status_v3', 1, 1, 2).
python_function('oqlos/api/_hw3_system.py', 'hardware_runtime_stop_v3', 1, 2, 5).
python_function('oqlos/api/_hw3_system.py', 'hardware_runtime_start_v3', 1, 2, 5).
python_function('oqlos/api/_hw3_system.py', 'hardware_runtime_make_v3', 1, 2, 5).
python_function('oqlos/api/_hw3_system.py', 'hardware_modbus_wizard_probe_isolated_v3', 1, 6, 6).
python_function('oqlos/api/_hw3_system.py', 'hardware_modbus_wizard_program_isolated_v3', 1, 6, 7).
python_function('oqlos/api/_hw3_system.py', 'hardware_runtime_python_v3', 1, 1, 2).
python_function('oqlos/api/editor.py', '_default_scenarios_dir', 0, 2, 3).
python_function('oqlos/api/editor.py', '_normalize_oql_mode', 1, 5, 3).
python_function('oqlos/api/editor.py', '_result_dict', 1, 2, 1).
python_function('oqlos/api/editor.py', '_editor_response_from_oql', 0, 10, 9).
python_function('oqlos/api/editor.py', '_safe_path', 1, 2, 3).
python_function('oqlos/api/editor.py', 'list_files', 0, 3, 7).
python_function('oqlos/api/editor.py', 'read_file_endpoint', 1, 4, 6).
python_function('oqlos/api/editor.py', 'write_file_endpoint', 2, 3, 5).
python_function('oqlos/api/editor.py', 'execute_scenario', 1, 6, 16).
python_function('oqlos/api/execution.py', '_resolve_step_label', 3, 11, 2).
python_function('oqlos/api/execution.py', '_flatten_steps_for_scenario', 1, 6, 3).
python_function('oqlos/api/execution.py', '_build_step_labels', 1, 6, 2).
python_function('oqlos/api/execution.py', '_resolve_current_index', 2, 10, 1).
python_function('oqlos/api/execution.py', '_current_projection', 0, 5, 3).
python_function('oqlos/api/execution.py', 'start_execution', 1, 4, 6).
python_function('oqlos/api/execution.py', 'execute_step', 1, 9, 9).
python_function('oqlos/api/execution.py', '_register_dsl_scenario', 2, 3, 4).
python_function('oqlos/api/execution.py', '_make_exec_route', 1, 1, 4).
python_function('oqlos/api/execution.py', 'get_execution', 1, 1, 2).
python_function('oqlos/api/execution.py', 'get_execution_projection', 0, 1, 2).
python_function('oqlos/api/execution.py', 'get_execution_status', 0, 4, 2).
python_function('oqlos/api/execution.py', 'get_execution_logs', 0, 6, 3).
python_function('oqlos/api/execution.py', '_make_legacy_route', 1, 1, 2).
python_function('oqlos/api/execution.py', 'execution_stream', 1, 1, 7).
python_function('oqlos/api/execution.py', 'execution_logs_stream', 1, 1, 7).
python_function('oqlos/api/hardware_actuators.py', 'set_valve', 2, 1, 3).
python_function('oqlos/api/hardware_actuators.py', 'set_pump', 1, 1, 3).
python_function('oqlos/api/hardware_diagnosis_routes.py', 'hardware_stack_snapshot', 0, 1, 2).
python_function('oqlos/api/hardware_diagnosis_routes.py', 'hardware_diagnosis_route', 1, 1, 5).
python_function('oqlos/api/hardware_diagnosis_routes.py', 'hardware_recover_route', 1, 2, 10).
python_function('oqlos/api/hardware_events.py', '_default_path', 0, 1, 2).
python_function('oqlos/api/hardware_events.py', '_load_recent_events_from_disk', 0, 6, 7).
python_function('oqlos/api/hardware_events.py', '_append_event_to_disk', 1, 2, 4).
python_function('oqlos/api/hardware_events.py', '_broadcast_event_to_subscribers', 1, 5, 4).
python_function('oqlos/api/hardware_events.py', 'publish_hardware_command_event', 2, 11, 10).
python_function('oqlos/api/hardware_events.py', 'list_hardware_command_events', 1, 2, 5).
python_function('oqlos/api/hardware_events.py', 'clear_hardware_command_events', 0, 3, 3).
python_function('oqlos/api/hardware_events.py', 'get_hardware_command_event_store_path', 0, 1, 1).
python_function('oqlos/api/hardware_events.py', 'subscribe_hardware_command_events', 0, 1, 4).
python_function('oqlos/api/hardware_events.py', 'unsubscribe_hardware_command_events', 1, 1, 1).
python_function('oqlos/api/hardware_gateway.py', 'set_hardware_gateway', 1, 1, 0).
python_function('oqlos/api/hardware_gateway.py', 'get_hardware_gateway', 0, 2, 1).
python_function('oqlos/api/hardware_gateway.py', 'try_get_hardware_gateway', 0, 1, 0).
python_function('oqlos/api/hardware_gateway.py', 'snapshot_via_health', 1, 1, 3).
python_function('oqlos/api/hardware_gateway.py', 'is_plugin_compatible', 1, 2, 3).
python_function('oqlos/api/hardware_hui.py', 'raise_if_hui_failed', 1, 2, 2).
python_function('oqlos/api/hardware_hui.py', 'start_hui_action', 1, 1, 3).
python_function('oqlos/api/hardware_hui.py', 'hui_actions', 0, 1, 2).
python_function('oqlos/api/hardware_hui.py', 'hui_shutdown', 0, 1, 3).
python_function('oqlos/api/hardware_hui.py', 'hui_hold_start', 1, 1, 2).
python_function('oqlos/api/hardware_hui.py', 'hui_hold_stop', 1, 1, 3).
python_function('oqlos/api/hardware_hui.py', 'hui_al_start', 0, 1, 2).
python_function('oqlos/api/hardware_hui.py', 'hui_al_stop', 0, 1, 3).
python_function('oqlos/api/hardware_identify.py', '_hardware_health_overall_ok', 1, 6, 3).
python_function('oqlos/api/hardware_identify.py', '_determine_scan_set', 2, 11, 7).
python_function('oqlos/api/hardware_identify.py', '_map_adapter_identify_status', 3, 10, 4).
python_function('oqlos/api/hardware_identify.py', 'hardware_health', 0, 4, 6).
python_function('oqlos/api/hardware_identify.py', 'hardware_identify', 1, 8, 18).
python_function('oqlos/api/hardware_lung.py', 'command_payload', 1, 5, 5).
python_function('oqlos/api/hardware_lung.py', 'lung_state_response', 2, 1, 1).
python_function('oqlos/api/hardware_lung.py', 'set_lung', 4, 7, 8).
python_function('oqlos/api/hardware_lung.py', 'stop_lung', 0, 1, 3).
python_function('oqlos/api/hardware_lung.py', 'disable_lung', 0, 1, 3).
python_function('oqlos/api/hardware_lung.py', 'artificial_lung_status', 0, 1, 3).
python_function('oqlos/api/hardware_lung.py', 'artificial_lung_command', 1, 1, 5).
python_function('oqlos/api/hardware_mapping_contract.py', '_validate_motor2', 2, 1, 1).
python_function('oqlos/api/hardware_mapping_contract.py', 'validate_mapping_contract', 1, 6, 5).
python_function('oqlos/api/hardware_mapping_motor2.py', '_is_int', 1, 2, 1).
python_function('oqlos/api/hardware_mapping_motor2.py', '_append_peripheral_id_issue', 2, 4, 4).
python_function('oqlos/api/hardware_mapping_motor2.py', '_append_stroke_steps_issue', 2, 4, 3).
python_function('oqlos/api/hardware_mapping_motor2.py', '_append_speed_issues', 2, 10, 3).
python_function('oqlos/api/hardware_mapping_motor2.py', 'validate_motor2_config', 2, 4, 7).
python_function('oqlos/api/hardware_mapping_store.py', '_default_path', 0, 1, 2).
python_function('oqlos/api/hardware_mapping_store.py', 'empty_mapping', 0, 1, 0).
python_function('oqlos/api/hardware_mapping_store.py', '_normalize_motor2_runtime_config', 1, 7, 4).
python_function('oqlos/api/hardware_mapping_store.py', 'normalize_mapping', 1, 7, 4).
python_function('oqlos/api/hardware_modbus_routes.py', 'hardware_modbus_waveshare_diagnose', 0, 1, 2).
python_function('oqlos/api/hardware_modbus_routes.py', 'hardware_modbus_wizard_plan', 0, 1, 2).
python_function('oqlos/api/hardware_modbus_routes.py', 'hardware_modbus_wizard_probe_isolated', 5, 8, 6).
python_function('oqlos/api/hardware_modbus_routes.py', 'hardware_modbus_wizard_program_isolated', 6, 2, 7).
python_function('oqlos/api/hardware_modbus_topology.py', '_parse_csv_ints', 2, 8, 6).
python_function('oqlos/api/hardware_modbus_topology.py', '_modbus_io_device_ids', 0, 2, 2).
python_function('oqlos/api/hardware_modbus_topology.py', '_modbus_topology_mode', 0, 5, 3).
python_function('oqlos/api/hardware_modbus_topology.py', '_apply_modbus_topology', 4, 11, 0).
python_function('oqlos/api/hardware_modbus_topology.py', '_modbus_runtime_serial_ports', 0, 12, 5).
python_function('oqlos/api/hardware_modbus_waveshare.py', '_diagnose_shared_bus_matrix', 0, 2, 4).
python_function('oqlos/api/hardware_modbus_waveshare.py', '_merge_unique_text_list', 2, 5, 2).
python_function('oqlos/api/hardware_modbus_waveshare.py', '_merge_waveshare_scan_dicts', 0, 11, 9).
python_function('oqlos/api/hardware_modbus_waveshare.py', '_read_output_control_modes', 5, 8, 10).
python_function('oqlos/api/hardware_modbus_waveshare.py', '_modbus_plugins_healthy', 1, 3, 3).
python_function('oqlos/api/hardware_modbus_waveshare.py', '_modbus_health_serial_stale', 1, 7, 4).
python_function('oqlos/api/hardware_modbus_waveshare.py', '_build_waveshare_serial_stale_report', 1, 8, 2).
python_function('oqlos/api/hardware_modbus_waveshare.py', '_build_waveshare_from_plugin_health', 1, 9, 4).
python_function('oqlos/api/hardware_modbus_waveshare.py', '_probe_waveshare_separate', 7, 2, 4).
python_function('oqlos/api/hardware_modbus_waveshare.py', '_probe_waveshare_shared_bus', 6, 1, 3).
python_function('oqlos/api/hardware_modbus_waveshare.py', '_read_waveshare_io_slave_config', 5, 8, 8).
python_function('oqlos/api/hardware_modbus_waveshare.py', '_read_waveshare_adc_slave_config', 5, 8, 7).
python_function('oqlos/api/hardware_modbus_waveshare.py', '_resolve_waveshare_ports', 1, 3, 1).
python_function('oqlos/api/hardware_modbus_waveshare.py', '_split_hits_by_role', 1, 5, 1).
python_function('oqlos/api/hardware_modbus_waveshare.py', '_build_waveshare_diagnose_report', 1, 9, 18).
python_function('oqlos/api/hardware_modbus_wizard.py', '_modbus_wizard_target_ids', 0, 1, 4).
python_function('oqlos/api/hardware_modbus_wizard.py', '_modbus_wizard_plan', 0, 7, 8).
python_function('oqlos/api/hardware_modbus_wizard.py', '_collect_wizard_serial_candidates', 1, 10, 5).
python_function('oqlos/api/hardware_modbus_wizard.py', '_modbus_wizard_probe_isolated', 5, 9, 9).
python_function('oqlos/api/hardware_modbus_wizard.py', '_wizard_check_already_configured', 4, 6, 4).
python_function('oqlos/api/hardware_modbus_wizard.py', '_wizard_apply_uart_write', 9, 10, 7).
python_function('oqlos/api/hardware_modbus_wizard.py', '_wizard_verify_config', 5, 7, 6).
python_function('oqlos/api/hardware_modbus_wizard.py', '_wizard_build_result', 8, 5, 1).
python_function('oqlos/api/hardware_modbus_wizard.py', '_modbus_wizard_program_isolated', 0, 6, 14).
python_function('oqlos/api/hardware_peripherals_routes.py', 'read_modbus_adc_raw', 0, 7, 8).
python_function('oqlos/api/hardware_peripherals_routes.py', 'rtc_status', 0, 1, 2).
python_function('oqlos/api/hardware_peripherals_routes.py', 'rtc_command', 1, 1, 4).
python_function('oqlos/api/hardware_platform.py', '_board_model', 0, 1, 4).
python_function('oqlos/api/hardware_platform.py', '_is_raspberry_pi_host', 0, 1, 2).
python_function('oqlos/api/hardware_platform.py', '_os_release', 0, 3, 5).
python_function('oqlos/api/hardware_platform.py', '_in_container', 0, 3, 4).
python_function('oqlos/api/hardware_platform.py', '_selected_hardware_platform', 0, 5, 5).
python_function('oqlos/api/hardware_platform.py', '_selected_piadc_platform', 0, 3, 6).
python_function('oqlos/api/hardware_platform.py', '_classify_platform_type', 4, 9, 0).
python_function('oqlos/api/hardware_platform.py', '_detect_runtime_platform', 0, 9, 17).
python_function('oqlos/api/hardware_probe.py', '_probe_all_hardware', 1, 11, 4).
python_function('oqlos/api/hardware_probe.py', '_collect_hardware_diagnostics', 0, 1, 6).
python_function('oqlos/api/hardware_probe.py', '_needs_live_scan', 1, 3, 2).
python_function('oqlos/api/hardware_probe.py', '_unhealthy_plugin_ids', 1, 3, 2).
python_function('oqlos/api/hardware_probe.py', '_modbus_health_is_no_response', 1, 5, 2).
python_function('oqlos/api/hardware_probe.py', '_probe_selected_hardware', 1, 2, 3).
python_function('oqlos/api/hardware_probe.py', '_modbus_preflight_report', 0, 5, 5).
python_function('oqlos/api/hardware_probe.py', '_modbus_repair_guidance', 1, 3, 1).
python_function('oqlos/api/hardware_probe_devices.py', '_local_ads1115_probe_allowed', 0, 4, 4).
python_function('oqlos/api/hardware_probe_devices.py', '_scan_usb_devices', 0, 9, 7).
python_function('oqlos/api/hardware_probe_devices.py', '_probe_tic249', 1, 4, 1).
python_function('oqlos/api/hardware_probe_devices.py', '_probe_dri0050', 1, 5, 3).
python_function('oqlos/api/hardware_probe_devices.py', '_probe_i2c_ads1115', 0, 14, 14).
python_function('oqlos/api/hardware_probe_devices.py', '_probe_waveshare_rtu', 1, 4, 2).
python_function('oqlos/api/hardware_probe_devices.py', '_probe_configured_waveshare_rtu', 1, 1, 1).
python_function('oqlos/api/hardware_runtime.py', 'read_cpu_temperature', 0, 8, 12).
python_function('oqlos/api/hardware_runtime.py', 'modbus_adc_unavailable', 1, 3, 2).
python_function('oqlos/api/hardware_runtime.py', 'unavailable_sensor_entry', 2, 1, 0).
python_function('oqlos/api/hardware_runtime.py', 'read_sensor_values', 1, 5, 6).
python_function('oqlos/api/hardware_runtime.py', 'read_sensor', 1, 2, 6).
python_function('oqlos/api/hardware_runtime.py', 'hardware_temperature', 0, 2, 3).
python_function('oqlos/api/hardware_runtime.py', 'read_sensors_batch', 1, 6, 10).
python_function('oqlos/api/hardware_runtime.py', 'hardware_diagnose', 0, 2, 6).
python_function('oqlos/api/hardware_v3.py', 'hardware_health_v3', 0, 2, 4).
python_function('oqlos/api/hardware_v3.py', 'hardware_identify_v3', 1, 2, 2).
python_function('oqlos/api/hardware_v3.py', 'hardware_proxy_info_v3', 0, 1, 1).
python_function('oqlos/api/logs.py', '_get_service', 0, 1, 3).
python_function('oqlos/api/logs.py', 'get_logs', 7, 1, 4).
python_function('oqlos/api/logs.py', 'get_log_stats', 0, 1, 3).
python_function('oqlos/api/main.py', '_app_lifespan', 1, 4, 9).
python_function('oqlos/api/main.py', '_initialize_runtime_dependencies', 0, 4, 9).
python_function('oqlos/api/main.py', '_start_oql_transport', 0, 8, 10).
python_function('oqlos/api/main.py', '_stop_oql_transport', 0, 3, 2).
python_function('oqlos/api/main.py', 'index_page', 1, 1, 3).
python_function('oqlos/api/main.py', '_serve_static_html', 3, 1, 1).
python_function('oqlos/api/main.py', 'editor_page', 1, 1, 3).
python_function('oqlos/api/main.py', 'panel_alias', 1, 1, 2).
python_function('oqlos/api/main.py', 'navigation_alias', 1, 1, 2).
python_function('oqlos/api/main.py', 'ui_panel_page', 0, 1, 2).
python_function('oqlos/api/main.py', 'ui_navigation_page', 0, 1, 2).
python_function('oqlos/api/main.py', '_with_query', 2, 3, 1).
python_function('oqlos/api/main.py', '_redirect_with_query', 2, 1, 2).
python_function('oqlos/api/main.py', 'hardware_status_page', 1, 1, 3).
python_function('oqlos/api/main.py', 'hardware_demo_alias', 1, 1, 3).
python_function('oqlos/api/main.py', 'hardware_restart_alias', 1, 1, 3).
python_function('oqlos/api/main.py', 'map_editor_alias', 1, 1, 3).
python_function('oqlos/api/main.py', 'scenario_files_alias', 1, 1, 3).
python_function('oqlos/api/main.py', 'func_editor_alias', 1, 1, 3).
python_function('oqlos/api/main.py', 'motor_services_alias', 1, 1, 3).
python_function('oqlos/api/main.py', 'nav_alias', 1, 1, 2).
python_function('oqlos/api/main.py', 'status_alias', 1, 1, 2).
python_function('oqlos/api/main.py', 'restart_alias', 1, 1, 2).
python_function('oqlos/api/main.py', 'demo_alias', 1, 1, 2).
python_function('oqlos/api/main.py', 'map_alias', 1, 1, 2).
python_function('oqlos/api/main.py', 'files_alias', 1, 1, 2).
python_function('oqlos/api/main.py', 'functions_alias', 1, 1, 2).
python_function('oqlos/api/main.py', 'oql_panel_alias', 1, 1, 2).
python_function('oqlos/api/main.py', 'hardware_ui_spa', 1, 5, 7).
python_function('oqlos/api/main.py', 'health_check', 0, 1, 1).
python_function('oqlos/api/main.py', 'navigation_index', 1, 1, 4).
python_function('oqlos/api/main.py', 'status', 0, 1, 1).
python_function('oqlos/api/main.py', '_forward_websocket', 2, 1, 1).
python_function('oqlos/api/main.py', 'hardware_events_websocket_alias', 1, 1, 2).
python_function('oqlos/api/main.py', 'websocket_endpoint', 1, 7, 9).
python_function('oqlos/api/main.py', 'oql_websocket_alias', 1, 1, 2).
python_function('oqlos/api/main.py', '_parse_server_args', 0, 1, 3).
python_function('oqlos/api/main.py', 'run', 0, 1, 2).
python_function('oqlos/api/oql_mqtt.py', 'set_oql_controller', 1, 1, 0).
python_function('oqlos/api/oql_mqtt.py', 'get_oql_controller', 0, 1, 0).
python_function('oqlos/api/oql_mqtt.py', 'execute_oql', 1, 3, 4).
python_function('oqlos/api/oql_mqtt.py', 'manage_hardware', 1, 3, 4).
python_function('oqlos/api/oql_mqtt.py', 'oql_ws', 1, 6, 14).
python_function('oqlos/api/oql_mqtt.py', '_pump_events', 2, 4, 3).
python_function('oqlos/api/peripherals.py', 'get_peripheral', 1, 1, 2).
python_function('oqlos/api/peripherals.py', 'update_peripheral', 2, 5, 5).
python_function('oqlos/api/peripherals.py', 'set_peripheral', 3, 2, 5).
python_function('oqlos/api/peripherals.py', 'reset_peripherals', 0, 1, 2).
python_function('oqlos/api/plugins.py', 'ensure_plugins_initialized', 0, 2, 2).
python_function('oqlos/api/plugins.py', '_plugin_health_http_status', 1, 2, 0).
python_function('oqlos/api/plugins.py', '_plugin_health_body', 1, 1, 0).
python_function('oqlos/api/plugins.py', 'list_plugins', 0, 1, 2).
python_function('oqlos/api/plugins.py', 'get_plugin_status', 0, 1, 2).
python_function('oqlos/api/plugins.py', 'get_plugin_info', 1, 2, 4).
python_function('oqlos/api/plugins.py', 'get_plugin_health', 1, 2, 5).
python_function('oqlos/api/plugins.py', 'connect_plugin', 2, 2, 5).
python_function('oqlos/api/plugins.py', 'disconnect_plugin', 1, 2, 3).
python_function('oqlos/api/plugins.py', '_resolve_plugin_instance', 1, 3, 4).
python_function('oqlos/api/plugins.py', 'execute_plugin_command', 2, 3, 6).
python_function('oqlos/api/plugins.py', 'validate_plugin_configs', 1, 3, 5).
python_function('oqlos/api/scenarios.py', 'get_scenario', 1, 3, 3).
python_function('oqlos/api/scenarios.py', '_fetch_raw_from_sources', 1, 8, 4).
python_function('oqlos/api/scenarios.py', '_compute_slug', 3, 9, 7).
python_function('oqlos/api/scenarios.py', '_extract_id', 1, 3, 3).
python_function('oqlos/api/scenarios.py', '_extract_display_fields', 2, 11, 3).
python_function('oqlos/api/scenarios.py', '_extract_goals', 1, 2, 2).
python_function('oqlos/api/scenarios.py', '_normalize_scenario_row', 1, 2, 4).
python_function('oqlos/api/scenarios.py', 'fetch_scenarios', 1, 10, 8).
python_function('oqlos/api/scenarios.py', '_parse_content_to_goals', 1, 6, 6).
python_function('oqlos/api/scenarios.py', '_ensure_list', 1, 3, 1).
python_function('oqlos/api/scenarios.py', '_normalize_dsl_payload', 1, 5, 3).
python_function('oqlos/api/scenarios.py', '_collect_dsl_strings', 1, 5, 5).
python_function('oqlos/api/scenarios.py', '_parse_goals_from_dsl', 3, 4, 2).
python_function('oqlos/api/scenarios.py', '_merge_goals_into_scenario', 3, 7, 3).
python_function('oqlos/api/scenarios.py', '_register_single_dsl_scenario', 2, 6, 6).
python_function('oqlos/api/scenarios.py', 'register_dsl', 1, 4, 6).
python_function('oqlos/api/state.py', '_compose_named_state', 0, 2, 2).
python_function('oqlos/api/state.py', '_compose_sim_state_list', 1, 3, 3).
python_function('oqlos/api/state.py', 'get_state', 0, 1, 2).
python_function('oqlos/api/state.py', '_generate_sinusoidal_values', 5, 2, 8).
python_function('oqlos/api/state.py', 'stream_values', 6, 1, 3).
python_function('oqlos/api/state.py', 'get_current_value', 1, 1, 6).
python_function('oqlos/api/state.py', 'get_sim_state', 0, 1, 3).
python_function('oqlos/api/state.py', 'get_variables_alias', 0, 2, 2).
python_function('oqlos/api/state.py', 'fetch_variables', 1, 7, 4).
python_function('oqlos/api/state.py', 'fetch_protocol_steps', 2, 11, 5).
python_function('oqlos/api/state.py', '_maybe_register_dsl_from_content', 2, 5, 8).
python_function('oqlos/api/state.py', '_extract_scenario_id', 1, 4, 3).
python_function('oqlos/api/state.py', '_extract_inline_dsl', 1, 8, 3).
python_function('oqlos/api/state.py', '_handle_start', 1, 13, 18).
python_function('oqlos/api/state.py', '_make_state_handler', 1, 1, 1).
python_function('oqlos/api/state.py', 'post_commands', 2, 3, 5).
python_function('oqlos/api/utils/execution_ctrl.py', 'set_dependencies', 2, 1, 0).
python_function('oqlos/api/utils/execution_ctrl.py', '_make_getter', 2, 1, 3).
python_function('oqlos/api/utils/execution_ctrl.py', '_make_exec_handler', 3, 1, 3).
python_function('oqlos/config.py', 'get_settings', 0, 1, 0).
python_function('oqlos/core/_action_motor2.py', '_normalize_motor2_target', 1, 1, 2).
python_function('oqlos/core/_action_motor2.py', '_parse_motor2_direction', 1, 6, 4).
python_function('oqlos/core/_action_motor2.py', '_parse_motor2_speed_steps', 1, 4, 4).
python_function('oqlos/core/_action_motor2.py', '_parse_motor2_positive_int', 1, 3, 9).
python_function('oqlos/core/_action_motor2.py', '_parse_motor2_float', 1, 4, 6).
python_function('oqlos/core/_action_motor2.py', '_parse_motor2_duration_seconds', 1, 8, 5).
python_function('oqlos/core/_action_motor2.py', '_parse_motor2_volume_liters', 1, 6, 5).
python_function('oqlos/core/_action_motor2.py', '_parse_motor2_acceleration', 1, 6, 9).
python_function('oqlos/core/_action_motor2.py', '_normalize_motor2_value', 1, 2, 4).
python_function('oqlos/core/_action_motor2.py', '_parse_prefixed_motor2_setting', 1, 13, 5).
python_function('oqlos/core/_action_motor2.py', '_parse_motor2_reciprocating_setting', 1, 6, 5).
python_function('oqlos/core/_action_motor2.py', '_parse_motor2_steps', 1, 1, 1).
python_function('oqlos/core/_action_motor2.py', '_motor2_speed_raw', 1, 1, 2).
python_function('oqlos/core/_action_motor2.py', '_motor2_max_steps_per_second', 0, 1, 1).
python_function('oqlos/core/_action_motor2.py', '_motor2_effective_steps_per_second', 1, 1, 4).
python_function('oqlos/core/_action_motor2.py', '_motor2_speed_for_duration', 3, 1, 1).
python_function('oqlos/core/_action_motor2.py', '_motor2_acceleration_raw', 2, 1, 2).
python_function('oqlos/core/_action_motor2.py', '_post_motor2_move_relative', 4, 6, 11).
python_function('oqlos/core/_action_motor2.py', '_post_motor2_reciprocate', 7, 7, 10).
python_function('oqlos/core/_action_motor2.py', '_post_motor2_stop', 0, 4, 10).
python_function('oqlos/core/_action_motor2.py', '_call_motor2_transport', 2, 4, 4).
python_function('oqlos/core/_action_motor2.py', '_motor2_reciprocating_state', 1, 2, 3).
python_function('oqlos/core/_action_motor2.py', '_motor2_set_state_value', 5, 1, 1).
python_function('oqlos/core/_action_motor2.py', '_motor2_state_handler', 3, 1, 3).
python_function('oqlos/core/_action_motor2.py', '_motor2_do_stop', 3, 4, 3).
python_function('oqlos/core/_action_motor2.py', '_motor2_build_plan', 3, 12, 6).
python_function('oqlos/core/_action_motor2.py', '_motor2_step_label', 2, 4, 1).
python_function('oqlos/core/_action_motor2.py', '_motor2_do_start', 3, 4, 10).
python_function('oqlos/core/_action_motor2.py', '_handle_motor2_reciprocating_setting', 2, 2, 3).
python_function('oqlos/core/_action_motor2.py', '_try_exec_motor2_set', 3, 13, 17).
python_function('oqlos/core/_compare.py', 'resolve_compare', 3, 2, 4).
python_function('oqlos/core/_compare.py', 'resolve_compare_chain', 2, 3, 3).
python_function('oqlos/core/_cql_tokenizer.py', '_make_args_parser', 2, 1, 3).
python_function('oqlos/core/_cql_tokenizer.py', '_make_keyword_parser', 2, 1, 2).
python_function('oqlos/core/_cql_tokenizer.py', '_make_method_parser', 2, 1, 3).
python_function('oqlos/core/_cql_tokenizer.py', '_make_stripped_field_parser', 3, 1, 4).
python_function('oqlos/core/_cql_tokenizer.py', '_make_two_group_parser', 3, 1, 3).
python_function('oqlos/core/_cql_tokenizer.py', '_make_target_method_args_parser', 2, 1, 4).
python_function('oqlos/core/_cql_tokenizer.py', '_match_first', 1, 3, 1).
python_function('oqlos/core/_cql_tokenizer.py', '_parse_condition_value', 1, 4, 4).
python_function('oqlos/core/_cql_tokenizer.py', '_try_save', 2, 5, 4).
python_function('oqlos/core/_cql_tokenizer.py', '_try_set', 2, 2, 4).
python_function('oqlos/core/_cql_tokenizer.py', '_try_condition_range', 2, 5, 5).
python_function('oqlos/core/_cql_tokenizer.py', '_try_condition_cmp', 2, 5, 5).
python_function('oqlos/core/_cql_tokenizer.py', '_try_if_else', 2, 3, 5).
python_function('oqlos/core/_cql_tokenizer.py', '_try_if_block', 2, 4, 7).
python_function('oqlos/core/_cql_tokenizer.py', '_try_if_standalone', 2, 2, 1).
python_function('oqlos/core/_cql_tokenizer.py', '_try_else_standalone', 2, 2, 5).
python_function('oqlos/core/_cql_tokenizer.py', '_try_min_max', 2, 2, 5).
python_function('oqlos/core/_cql_tokenizer.py', '_try_val', 2, 2, 3).
python_function('oqlos/core/_cql_tokenizer.py', '_try_loop_start', 2, 5, 7).
python_function('oqlos/core/_cql_tokenizer.py', '_try_repeat_start', 2, 2, 3).
python_function('oqlos/core/_cql_tokenizer.py', '_try_repeat_stop', 2, 2, 2).
python_function('oqlos/core/_cql_tokenizer.py', '_try_sample', 2, 3, 3).
python_function('oqlos/core/_cql_tokenizer.py', '_try_goto', 2, 2, 4).
python_function('oqlos/core/_cql_tree_builder.py', '_parse_metadata_kv', 2, 6, 3).
python_function('oqlos/core/_cql_tree_builder.py', '_parse_scenario_line', 2, 3, 6).
python_function('oqlos/core/_cql_tree_builder.py', '_parse_scenario_attrs', 2, 4, 4).
python_function('oqlos/core/_cql_tree_builder.py', '_parse_goal_line', 4, 12, 4).
python_function('oqlos/core/_cql_tree_builder.py', '_parse_goal_attrs', 2, 4, 3).
python_function('oqlos/core/_cql_tree_builder.py', '_parse_step_line', 2, 3, 4).
python_function('oqlos/core/_cql_tree_builder.py', '_parse_action_line', 5, 4, 3).
python_function('oqlos/core/_cql_tree_builder.py', '_ensure_goal_for_step', 3, 4, 3).
python_function('oqlos/core/_cql_tree_builder.py', '_ensure_step_for_actions', 2, 3, 2).
python_function('oqlos/core/_dsl_helpers.py', '_normalize_quote_syntax', 1, 2, 3).
python_function('oqlos/core/_dsl_helpers.py', '_looks_like_valve_object', 1, 2, 2).
python_function('oqlos/core/_dsl_helpers.py', '_looks_like_pump_object', 1, 1, 2).
python_function('oqlos/core/_dsl_helpers.py', '_looks_like_lung_object', 1, 1, 2).
python_function('oqlos/core/_dsl_helpers.py', '_looks_like_sensor_object', 1, 1, 2).
python_function('oqlos/core/_dsl_helpers.py', '_map_peripheral', 1, 11, 14).
python_function('oqlos/core/_dsl_helpers.py', '_parse_numeric_value', 1, 4, 7).
python_function('oqlos/core/_dsl_helpers.py', '_map_valve_action', 1, 3, 0).
python_function('oqlos/core/_dsl_helpers.py', '_map_pump_action', 3, 5, 1).
python_function('oqlos/core/_dsl_helpers.py', '_map_wait_action', 5, 4, 6).
python_function('oqlos/core/_dsl_helpers.py', '_map_lung_action', 3, 5, 1).
python_function('oqlos/core/_dsl_helpers.py', '_map_action_value', 5, 7, 8).
python_function('oqlos/core/_func_resolver.py', '_collect_function_definitions', 1, 13, 8).
python_function('oqlos/core/_func_resolver.py', '_extract_func_name', 2, 7, 4).
python_function('oqlos/core/_func_resolver.py', '_guard_recursion', 2, 3, 3).
python_function('oqlos/core/_func_resolver.py', '_parse_func_call', 7, 5, 4).
python_function('oqlos/core/_interpreter_actions.py', '_extract_action_tokens', 1, 5, 4).
python_function('oqlos/core/_interpreter_actions.py', '_drop_command_token', 1, 6, 4).
python_function('oqlos/core/_interpreter_actions.py', '_coerce_expected_value', 1, 7, 8).
python_function('oqlos/core/_interpreter_actions.py', '_compare_values', 3, 10, 5).
python_function('oqlos/core/_interpreter_actions.py', '_oql_quote', 1, 2, 2).
python_function('oqlos/core/_interpreter_actions.py', '_format_set_command', 2, 1, 1).
python_function('oqlos/core/_interpreter_actions.py', '_get_nested_value', 2, 9, 6).
python_function('oqlos/core/_interpreter_actions.py', '_record_failure', 3, 1, 3).
python_function('oqlos/core/_interpreter_actions.py', '_mark_success', 2, 1, 1).
python_function('oqlos/core/_interpreter_actions.py', '_normalize_bool', 1, 5, 4).
python_function('oqlos/core/_interpreter_actions.py', '_lookup_peripheral_state', 2, 5, 5).
python_function('oqlos/core/_interpreter_actions.py', '_mock_api_response', 2, 6, 4).
python_function('oqlos/core/_interpreter_actions.py', 'exec_action_task', 2, 1, 2).
python_function('oqlos/core/_interpreter_actions.py', 'exec_action_save', 2, 4, 4).
python_function('oqlos/core/_interpreter_actions.py', 'parse_wait_secs', 1, 4, 6).
python_function('oqlos/core/_interpreter_actions.py', 'exec_action_wait', 2, 3, 3).
python_function('oqlos/core/_interpreter_actions.py', '_do_sleep', 3, 3, 6).
python_function('oqlos/core/_interpreter_actions.py', 'exec_action_min_max', 2, 3, 5).
python_function('oqlos/core/_interpreter_actions.py', 'exec_action_val', 2, 3, 3).
python_function('oqlos/core/_interpreter_actions.py', 'exec_action_log', 2, 2, 2).
python_function('oqlos/core/_interpreter_actions.py', 'exec_action_error', 2, 2, 3).
python_function('oqlos/core/_interpreter_actions.py', 'exec_action_else', 2, 7, 7).
python_function('oqlos/core/_interpreter_actions.py', 'exec_action_sample', 2, 7, 9).
python_function('oqlos/core/_interpreter_actions.py', '_resolve_numeric_token', 2, 6, 6).
python_function('oqlos/core/_interpreter_actions.py', '_func_avg', 1, 2, 2).
python_function('oqlos/core/_interpreter_actions.py', '_func_sum', 1, 1, 1).
python_function('oqlos/core/_interpreter_actions.py', '_func_reduce_or_zero', 2, 2, 1).
python_function('oqlos/core/_interpreter_actions.py', '_func_sub', 1, 2, 1).
python_function('oqlos/core/_interpreter_actions.py', '_func_div', 3, 4, 1).
python_function('oqlos/core/_interpreter_actions.py', '_func_mul', 1, 2, 0).
python_function('oqlos/core/_interpreter_actions.py', 'exec_action_func', 2, 9, 11).
python_function('oqlos/core/_interpreter_actions.py', 'exec_action_goto', 2, 1, 2).
python_function('oqlos/core/_interpreter_actions.py', 'exec_action_api', 2, 3, 6).
python_function('oqlos/core/_interpreter_actions.py', 'exec_action_expect', 2, 3, 4).
python_function('oqlos/core/_interpreter_actions.py', '_assert_status', 3, 5, 5).
python_function('oqlos/core/_interpreter_actions.py', '_assert_json', 3, 6, 6).
python_function('oqlos/core/_interpreter_actions.py', '_assert_sensor', 3, 4, 8).
python_function('oqlos/core/_interpreter_actions.py', '_assert_valve', 3, 5, 6).
python_function('oqlos/core/_interpreter_actions.py', 'exec_action_assert', 2, 3, 7).
python_function('oqlos/core/_interpreter_actions.py', 'exec_action_shell', 2, 13, 11).
python_function('oqlos/core/_interpreter_actions.py', 'exec_action_var_set', 2, 1, 3).
python_function('oqlos/core/_interpreter_actions.py', 'exec_action_condition', 2, 2, 2).
python_function('oqlos/core/_interpreter_actions.py', 'exec_action_if_fail_block', 2, 4, 3).
python_function('oqlos/core/_interpreter_actions.py', 'exec_action_if_block', 2, 7, 3).
python_function('oqlos/core/_interpreter_actions.py', 'exec_action_loop_block', 2, 14, 11).
python_function('oqlos/core/_interpreter_actions.py', 'exec_action_endloop', 2, 1, 1).
python_function('oqlos/core/_interpreter_actions.py', 'exec_action_set', 2, 9, 10).
python_function('oqlos/core/_interpreter_actions.py', '_exec_set_wait', 3, 3, 4).
python_function('oqlos/core/_interpreter_actions.py', 'exec_action_action', 2, 2, 3).
python_function('oqlos/core/_line_parsers.py', '_parse_task_part', 2, 10, 8).
python_function('oqlos/core/_line_parsers.py', '_parse_pump_line', 2, 6, 7).
python_function('oqlos/core/_line_parsers.py', '_set_valve_step', 4, 4, 4).
python_function('oqlos/core/_line_parsers.py', '_set_pump_step', 4, 4, 3).
python_function('oqlos/core/_line_parsers.py', '_set_lung_step', 4, 4, 3).
python_function('oqlos/core/_line_parsers.py', '_extract_set_params', 1, 7, 3).
python_function('oqlos/core/_line_parsers.py', '_parse_set_line', 2, 10, 12).
python_function('oqlos/core/_line_parsers.py', '_parse_inline_task', 3, 5, 6).
python_function('oqlos/core/_line_parsers.py', '_parse_action_line', 3, 10, 10).
python_function('oqlos/core/_line_parsers.py', '_parse_if_condition', 3, 9, 9).
python_function('oqlos/core/_oql_adapter.py', '_fmt_value', 2, 2, 1).
python_function('oqlos/core/_oql_adapter.py', '_scenarios_root', 0, 1, 2).
python_function('oqlos/core/_oql_adapter.py', '_resolve_include', 2, 6, 6).
python_function('oqlos/core/_oql_adapter.py', '_substitute_args', 2, 3, 2).
python_function('oqlos/core/_oql_adapter.py', '_load_includes', 4, 12, 11).
python_function('oqlos/core/_oql_adapter.py', '_lower_include', 3, 1, 0).
python_function('oqlos/core/_oql_adapter.py', '_lower_call', 3, 6, 7).
python_function('oqlos/core/_oql_adapter.py', '_lower_set', 3, 3, 6).
python_function('oqlos/core/_oql_adapter.py', '_lower_get', 3, 1, 1).
python_function('oqlos/core/_oql_adapter.py', '_lower_wait', 3, 2, 2).
python_function('oqlos/core/_oql_adapter.py', '_lower_save', 3, 1, 1).
python_function('oqlos/core/_oql_adapter.py', '_make_lower_minmax', 1, 1, 3).
python_function('oqlos/core/_oql_adapter.py', '_lower_check', 3, 5, 4).
python_function('oqlos/core/_oql_adapter.py', '_lower_if_delta', 3, 10, 6).
python_function('oqlos/core/_oql_adapter.py', '_lower_sample', 3, 2, 2).
python_function('oqlos/core/_oql_adapter.py', '_lower_log', 3, 1, 2).
python_function('oqlos/core/_oql_adapter.py', '_lower_error_cmd', 3, 1, 2).
python_function('oqlos/core/_oql_adapter.py', '_lower_repeat', 3, 3, 2).
python_function('oqlos/core/_oql_adapter.py', '_cmd_to_actions', 3, 2, 3).
python_function('oqlos/core/_oql_adapter.py', '_parse_macro_line', 3, 8, 10).
python_function('oqlos/core/_oql_adapter.py', '_has_anonymous_named_goal', 1, 8, 5).
python_function('oqlos/core/_oql_adapter.py', 'is_flat_oql', 1, 8, 4).
python_function('oqlos/core/_oql_adapter.py', 'oql_doc_to_cql', 1, 12, 16).
python_function('oqlos/core/_oql_adapter.py', '_split_device_field', 2, 4, 3).
python_function('oqlos/core/_oql_adapter.py', 'parse_flat_oql', 2, 1, 2).
python_function('oqlos/core/cql_parser.py', 'parse_cql', 2, 2, 6).
python_function('oqlos/core/cql_parser.py', '_collect_all_goals', 1, 2, 2).
python_function('oqlos/core/cql_parser.py', '_validate_intervals', 1, 6, 1).
python_function('oqlos/core/cql_parser.py', 'validate_cql', 1, 5, 4).
python_function('oqlos/core/executor.py', '_resolve_compare', 2, 1, 2).
python_function('oqlos/core/executor.py', '_resolve_name_or_attr', 2, 4, 5).
python_function('oqlos/core/executor.py', '_safe_resolve', 2, 14, 8).
python_function('oqlos/core/executor.py', 'safe_eval_condition', 2, 2, 5).
python_function('oqlos/core/motor2_runtime.py', '_coerce_int', 2, 3, 6).
python_function('oqlos/core/motor2_runtime.py', '_coerce_float', 2, 2, 4).
python_function('oqlos/core/motor2_runtime.py', '_pick', 1, 4, 0).
python_function('oqlos/core/motor2_runtime.py', 'motor2_max_steps_per_second', 1, 2, 2).
python_function('oqlos/core/motor2_runtime.py', 'normalize_motor2_runtime_config', 1, 12, 10).
python_function('oqlos/core/motor2_runtime.py', 'motor2_speed_for_duration', 3, 1, 4).
python_function('oqlos/core/motor2_runtime.py', 'motor2_acceleration_raw', 3, 2, 3).
python_function('oqlos/core/motor2_runtime.py', 'motor2_speed_raw', 2, 1, 3).
python_function('oqlos/core/motor2_runtime.py', '_normalize_motor2_direction', 1, 4, 2).
python_function('oqlos/core/motor2_runtime.py', '_compute_motor2_cycles', 3, 3, 4).
python_function('oqlos/core/motor2_runtime.py', '_compute_motor2_speed', 6, 4, 5).
python_function('oqlos/core/motor2_runtime.py', 'build_motor2_reciprocating_plan', 1, 7, 8).
python_function('oqlos/core/oql_parser.py', 'to_num', 1, 2, 4).
python_function('oqlos/core/oql_parser.py', '_compact_duration', 1, 2, 3).
python_function('oqlos/core/oql_parser.py', 'parse_duration', 1, 3, 5).
python_function('oqlos/core/oql_parser.py', 'duration_to_ms', 1, 1, 2).
python_function('oqlos/core/oql_parser.py', '_unescape', 1, 1, 2).
python_function('oqlos/core/oql_parser.py', 'tokenize', 1, 13, 8).
python_function('oqlos/core/oql_parser.py', '_require', 5, 2, 2).
python_function('oqlos/core/oql_parser.py', '_split_value_unit', 1, 2, 2).
python_function('oqlos/core/oql_parser.py', '_split_set_value_unit', 1, 2, 2).
python_function('oqlos/core/oql_parser.py', 'parse_SET', 3, 3, 7).
python_function('oqlos/core/oql_parser.py', '_make_single_field_parser', 3, 1, 2).
python_function('oqlos/core/oql_parser.py', 'parse_WAIT', 3, 2, 7).
python_function('oqlos/core/oql_parser.py', 'parse_IF_DELTA', 3, 6, 12).
python_function('oqlos/core/oql_parser.py', 'parse_CHECK', 3, 2, 6).
python_function('oqlos/core/oql_parser.py', 'parse_IF', 3, 2, 6).
python_function('oqlos/core/oql_parser.py', '_make_minmax_parser', 1, 1, 3).
python_function('oqlos/core/oql_parser.py', 'parse_SAMPLE', 3, 3, 6).
python_function('oqlos/core/oql_parser.py', '_make_message_parser', 1, 1, 2).
python_function('oqlos/core/oql_parser.py', '_make_call_parser', 3, 1, 2).
python_function('oqlos/core/oql_parser.py', 'parse_REPEAT', 3, 3, 2).
python_function('oqlos/core/oql_parser.py', '_line_indent', 1, 2, 4).
python_function('oqlos/core/oql_parser.py', '_expand_repeat_block_lines', 1, 8, 11).
python_function('oqlos/core/oql_parser.py', '_expand_repeat_blocks', 1, 2, 2).
python_function('oqlos/core/oql_parser.py', '_handle_top_level_line', 4, 6, 11).
python_function('oqlos/core/oql_parser.py', '_handle_block_header', 4, 8, 8).
python_function('oqlos/core/oql_parser.py', '_handle_macro_body_line', 3, 4, 5).
python_function('oqlos/core/oql_parser.py', '_handle_set_name', 2, 5, 6).
python_function('oqlos/core/oql_parser.py', '_handle_modifier_cmd', 6, 5, 3).
python_function('oqlos/core/oql_parser.py', '_parse_and_append_command', 6, 5, 7).
python_function('oqlos/core/oql_parser.py', '_validate_oql_version', 2, 8, 4).
python_function('oqlos/core/oql_parser.py', '_check_unnamed_goals', 2, 5, 1).
python_function('oqlos/core/oql_parser.py', 'parse_oql', 2, 14, 18).
python_function('oqlos/core/oql_parser.py', 'format_doc', 1, 9, 3).
python_function('oqlos/core/oql_versioning.py', 'first_meaningful_line', 1, 4, 4).
python_function('oqlos/core/oql_versioning.py', 'extract_declared_version', 1, 3, 4).
python_function('oqlos/core/oql_versioning.py', 'resolve_oql_version', 1, 2, 3).
python_function('oqlos/core/oql_versioning.py', 'is_supported_oql_version', 1, 1, 0).
python_function('oqlos/core/parser.py', '_dispatch_simple_parser', 4, 3, 3).
python_function('oqlos/core/parser.py', '_try_action_or_condition', 5, 5, 4).
python_function('oqlos/core/parser.py', '_parse_runtime_line', 7, 9, 10).
python_function('oqlos/core/parser.py', 'parse_dsl_to_goal_with_issues', 2, 13, 13).
python_function('oqlos/core/parser.py', 'parse_dsl_to_goal', 2, 1, 1).
python_function('oqlos/core/safe_eval.py', 'safe_eval', 2, 3, 4).
python_function('oqlos/core/safe_eval.py', '_eval_constant', 2, 1, 0).
python_function('oqlos/core/safe_eval.py', '_eval_name', 2, 3, 1).
python_function('oqlos/core/safe_eval.py', '_eval_unary_op', 2, 3, 4).
python_function('oqlos/core/safe_eval.py', '_eval_bin_op', 2, 2, 5).
python_function('oqlos/core/safe_eval.py', '_eval_compare', 2, 1, 2).
python_function('oqlos/core/safe_eval.py', '_eval_bool_op', 2, 4, 6).
python_function('oqlos/core/safe_eval.py', '_eval_call', 2, 4, 4).
python_function('oqlos/core/safe_eval.py', '_eval_if_exp', 2, 2, 1).
python_function('oqlos/core/safe_eval.py', '_eval_node', 2, 2, 4).
python_function('oqlos/dsl/schema.py', '_normalize_name_list', 1, 6, 5).
python_function('oqlos/dsl/schema.py', '_build_inferred_object_function_map', 2, 4, 2).
python_function('oqlos/dsl/schema.py', '_build_inferred_param_unit_map', 2, 7, 2).
python_function('oqlos/dsl/schema.py', '_merge_binding_map', 4, 3, 5).
python_function('oqlos/dsl/schema.py', '_merge_object_function_map', 2, 1, 1).
python_function('oqlos/dsl/schema.py', '_merge_param_unit_map', 2, 1, 1).
python_function('oqlos/dsl/schema.py', 'get_default_dsl_schema', 0, 1, 9).
python_function('oqlos/errors/catalog.py', 'get_issue_definition', 1, 1, 1).
python_function('oqlos/errors/catalog.py', 'matches_known_pattern', 1, 2, 2).
python_function('oqlos/errors/catalog.py', 'all_codes', 0, 1, 1).
python_function('oqlos/errors/fastapi_integration.py', 'install_oqlos_error_handler', 1, 1, 3).
python_function('oqlos/errors/repair_commit.py', 'is_eligible_for_automated_commit', 1, 2, 1).
python_function('oqlos/errors/repair_commit.py', 'format_repair_commit_message', 0, 2, 2).
python_function('oqlos/hardware/artificial_lung.py', '_clamp_lpm', 1, 2, 3).
python_function('oqlos/hardware/artificial_lung.py', '_command_response', 3, 2, 1).
python_function('oqlos/hardware/artificial_lung.py', 'get_peripheral_status', 1, 6, 7).
python_function('oqlos/hardware/artificial_lung.py', '_lung_cmd_set_lpm', 2, 1, 3).
python_function('oqlos/hardware/artificial_lung.py', '_lung_cmd_lung_start', 2, 4, 6).
python_function('oqlos/hardware/artificial_lung.py', '_lung_cmd_lung_stop', 2, 3, 3).
python_function('oqlos/hardware/artificial_lung.py', '_lung_cmd_lung_status', 2, 2, 3).
python_function('oqlos/hardware/artificial_lung.py', '_lung_cmd_lung_cycle', 2, 4, 7).
python_function('oqlos/hardware/artificial_lung.py', '_lung_cmd_emergency_stop', 2, 3, 3).
python_function('oqlos/hardware/artificial_lung.py', 'execute_command', 3, 4, 6).
python_function('oqlos/hardware/client/adc.py', 'adc_sensor_alias', 1, 10, 7).
python_function('oqlos/hardware/client/adc.py', 'normalize_adc_read_result', 2, 3, 3).
python_function('oqlos/hardware/client/adc.py', 'normalize_adc_read_all_result', 1, 7, 5).
python_function('oqlos/hardware/client/autorepair.py', 'plugin_needs_repair', 2, 8, 6).
python_function('oqlos/hardware/client/autorepair.py', 'modbus_plugins_need_repair', 1, 5, 4).
python_function('oqlos/hardware/client/autorepair.py', '_plugin_repair_reasons', 1, 6, 6).
python_function('oqlos/hardware/client/autorepair.py', '_no_response_reasons', 1, 5, 3).
python_function('oqlos/hardware/client/autorepair.py', 'analyze_repair_needs', 1, 10, 9).
python_function('oqlos/hardware/client/autorepair.py', 'modbus_exclusive_scan_recommended', 1, 5, 3).
python_function('oqlos/hardware/client/autorepair.py', 'overall_stack_healthy', 1, 11, 8).
python_function('oqlos/hardware/client/autorepair.py', 'build_summary', 0, 12, 5).
python_function('oqlos/hardware/client/config.py', 'float_from_env', 3, 1, 1).
python_function('oqlos/hardware/client/config.py', 'int_from_env', 3, 1, 1).
python_function('oqlos/hardware/client/config.py', '_value_from_env', 4, 3, 2).
python_function('oqlos/hardware/client/config.py', 'candidate_oqlos_bases', 1, 6, 3).
python_function('oqlos/hardware/client/errors.py', 'is_oqlos_unavailable', 1, 1, 0).
python_function('oqlos/hardware/client/errors.py', 'oqlos_error_detail', 1, 6, 3).
python_function('oqlos/hardware/client/http_helpers.py', 'safe_response_payload', 1, 3, 1).
python_function('oqlos/hardware/client/http_helpers.py', 'response_error_message', 1, 10, 3).
python_function('oqlos/hardware/client/identify_enrich.py', '_platform_serial_ports', 1, 5, 3).
python_function('oqlos/hardware/client/identify_enrich.py', 'count_detected_adapters', 1, 4, 3).
python_function('oqlos/hardware/client/identify_enrich.py', 'enrich_identify_payload', 1, 12, 13).
python_function('oqlos/hardware/client/identify_enrich.py', 'enrich_hardware_identify', 1, 1, 2).
python_function('oqlos/hardware/client/identify_enrich_adapters.py', 'health_message', 2, 4, 3).
python_function('oqlos/hardware/client/identify_enrich_adapters.py', 'enrich_disabled', 2, 3, 2).
python_function('oqlos/hardware/client/identify_enrich_adapters.py', 'enrich_motor_tic249', 5, 5, 0).
python_function('oqlos/hardware/client/identify_enrich_adapters.py', 'enrich_motor_dri0050', 4, 5, 0).
python_function('oqlos/hardware/client/identify_enrich_adapters.py', 'enrich_modbus_adapter', 5, 11, 3).
python_function('oqlos/hardware/client/identify_enrich_adapters.py', 'enrich_by_device_id', 6, 4, 3).
python_function('oqlos/hardware/client/identify_enrich_adapters.py', 'enrich_adapter_entry', 1, 13, 10).
python_function('oqlos/hardware/client/identify_enrich_adapters.py', 'adapter_status_modbus', 4, 6, 0).
python_function('oqlos/hardware/client/identify_enrich_adapters.py', 'adapter_status_tic249', 4, 5, 0).
python_function('oqlos/hardware/client/identify_enrich_adapters.py', 'adapter_status_from_health', 2, 10, 7).
python_function('oqlos/hardware/client/identify_enrich_modbus_io.py', 'parse_csv_ints', 1, 5, 5).
python_function('oqlos/hardware/client/identify_enrich_modbus_io.py', 'ids_from_preflight', 1, 10, 5).
python_function('oqlos/hardware/client/identify_enrich_modbus_io.py', 'modbus_io_instance_ids', 1, 6, 5).
python_function('oqlos/hardware/client/identify_enrich_modbus_io.py', 'expand_modbus_io_instances', 2, 13, 11).
python_function('oqlos/hardware/client/modbus_repair.py', '_env', 2, 2, 2).
python_function('oqlos/hardware/client/modbus_repair.py', '_is_separate_adapters', 1, 4, 2).
python_function('oqlos/hardware/client/modbus_repair.py', '_adapter_ports', 1, 9, 3).
python_function('oqlos/hardware/client/modbus_repair.py', '_augment_no_response_from_health', 2, 10, 6).
python_function('oqlos/hardware/client/modbus_repair.py', '_build_diagnose_cmd', 3, 5, 2).
python_function('oqlos/hardware/client/modbus_repair.py', '_build_safety_hints', 3, 13, 6).
python_function('oqlos/hardware/client/modbus_repair.py', 'rewrite_modbus_repair', 1, 11, 9).
python_function('oqlos/hardware/client/platform.py', 'is_raspberry_pi', 0, 6, 5).
python_function('oqlos/hardware/client/platform.py', 'is_docker', 0, 4, 5).
python_function('oqlos/hardware/client/platform.py', 'get_default_oqlos_api_base', 0, 3, 2).
python_function('oqlos/hardware/client/proxy.py', '_is_unsuccessful_result', 1, 2, 2).
python_function('oqlos/hardware/client/resolvers.py', 'normalize_modbus_valve_id', 1, 3, 5).
python_function('oqlos/hardware/client/resolvers.py', 'resolve_modbus_target', 2, 3, 3).
python_function('oqlos/hardware/client/resolvers.py', 'resolve_pump_target', 2, 3, 3).
python_function('oqlos/hardware/client/resolvers.py', 'resolve_artificial_lung_target', 2, 1, 0).
python_function('oqlos/hardware/client/resolvers.py', 'resolve_lung_target', 2, 4, 4).
python_function('oqlos/hardware/client/resolvers.py', 'resolve_modbus_adc_target', 2, 4, 3).
python_function('oqlos/hardware/client/resolvers.py', 'resolve_rtc_target', 2, 1, 0).
python_function('oqlos/hardware/client/resolvers.py', 'resolve_diagnostic_target', 3, 3, 4).
python_function('oqlos/hardware/client/resolvers.py', '_coalesce_error_message', 0, 4, 2).
python_function('oqlos/hardware/client/resolvers.py', 'extract_command_failure', 1, 10, 3).
python_function('oqlos/hardware/client/tic249_arg_contract.py', 'canonicalize_motor2_runtime_key', 1, 2, 5).
python_function('oqlos/hardware/client/tic249_arg_contract.py', 'tic249_runtime_args_from_config', 1, 8, 4).
python_function('oqlos/hardware/client/tic249_arg_helpers.py', 'tic249_arg', 4, 4, 0).
python_function('oqlos/hardware/client/tic249_command_mapping.py', 'map_lung_or_reciprocate', 2, 8, 4).
python_function('oqlos/hardware/client/tic249_command_mapping.py', 'map_tic249_command', 2, 13, 5).
python_function('oqlos/hardware/client/tic249_error_messages.py', 'extract_position', 1, 5, 3).
python_function('oqlos/hardware/client/tic249_error_messages.py', 'command_error_message', 1, 14, 4).
python_function('oqlos/hardware/client/tic249_error_messages.py', 'generic_failure_hint', 1, 8, 4).
python_function('oqlos/hardware/client/tic249_error_messages.py', 'command_failure', 1, 10, 4).
python_function('oqlos/hardware/client/tic249_error_messages.py', 'plugin_unavailable_error', 1, 10, 4).
python_function('oqlos/hardware/client/tic249_error_messages.py', 'normalize_target_state', 2, 12, 4).
python_function('oqlos/hardware/client/tic249_extended.py', '_plugin_payload', 2, 2, 0).
python_function('oqlos/hardware/client/tic249_extended.py', '_execute', 3, 1, 2).
python_function('oqlos/hardware/client/tic249_extended.py', '_handle_move_relative_command', 2, 3, 9).
python_function('oqlos/hardware/client/tic249_extended.py', '_try_disable_fallback', 2, 4, 2).
python_function('oqlos/hardware/client/tic249_extended.py', '_try_sidecar_reciprocate', 3, 5, 2).
python_function('oqlos/hardware/client/tic249_extended.py', '_handle_hardware_proxy_error', 5, 8, 6).
python_function('oqlos/hardware/client/tic249_extended.py', 'run_extended_motor_tic249_command', 3, 10, 9).
python_function('oqlos/hardware/client/tic249_motion_params.py', 'normalize_motion_params', 1, 13, 6).
python_function('oqlos/hardware/client/tic249_motion_params.py', 'stroke_steps', 2, 1, 2).
python_function('oqlos/hardware/client/tic249_motion_params.py', 'apply_reciprocate_direction', 2, 1, 1).
python_function('oqlos/hardware/client/tic249_motion_params.py', '_resolve_reciprocate_speed', 1, 5, 4).
python_function('oqlos/hardware/client/tic249_motion_params.py', '_resolve_reciprocate_ramp', 1, 4, 2).
python_function('oqlos/hardware/client/tic249_motion_params.py', 'build_reciprocate_params', 1, 8, 10).
python_function('oqlos/hardware/client/tic249_rig_direction.py', 'rig_direction_to_plugin', 1, 4, 3).
python_function('oqlos/hardware/client/tic249_rig_direction.py', 'apply_rig_direction_to_plugin_params', 2, 5, 4).
python_function('oqlos/hardware/client/tic249_sidecar_client.py', 'tic249_sidecar_base_urls', 0, 5, 6).
python_function('oqlos/hardware/client/tic249_sidecar_client.py', 'tic249_sidecar_base_url', 0, 1, 1).
python_function('oqlos/hardware/client/tic249_sidecar_client.py', 'sidecar_reciprocate_preferred', 0, 1, 3).
python_function('oqlos/hardware/client/tic249_sidecar_client.py', 'sidecar_reports_deenergized', 0, 7, 5).
python_function('oqlos/hardware/client/tic249_sidecar_client.py', 'attempt_reciprocate_via_sidecar', 1, 9, 8).
python_function('oqlos/hardware/client/tic249_sidecar_client.py', 'direct_sidecar_deenergize', 1, 7, 7).
python_function('oqlos/hardware/client/tic249_sidecar_client.py', 'lung_disable_fallback', 2, 4, 4).
python_function('oqlos/hardware/client/tic249_sidecar_client.py', 'disable_success_response', 3, 3, 1).
python_function('oqlos/hardware/client/tic249_sidecar_client.py', 'attempt_disable_deenergize', 2, 4, 4).
python_function('oqlos/hardware/config_paths.py', 'resolve_oqlos_config_path', 1, 6, 7).
python_function('oqlos/hardware/config_schema.py', 'get_hardware_config', 1, 2, 4).
python_function('oqlos/hardware/config_schema.py', 'register_hardware_config', 1, 1, 1).
python_function('oqlos/hardware/config_schema.py', 'load_config_from_yaml', 1, 1, 2).
python_function('oqlos/hardware/config_schema.py', 'build_dynamic_schema_models', 1, 2, 4).
python_function('oqlos/hardware/diagnosis.py', '_report_device_status', 2, 2, 2).
python_function('oqlos/hardware/diagnosis.py', '_adapter_index', 1, 5, 3).
python_function('oqlos/hardware/diagnosis.py', '_build_stack_snapshot', 1, 2, 1).
python_function('oqlos/hardware/diagnosis.py', '_resolve_host_recover', 0, 4, 3).
python_function('oqlos/hardware/diagnosis.py', 'build_diagnosis_report', 1, 13, 19).
python_function('oqlos/hardware/diagnosis.py', '_should_include_host_action', 5, 10, 3).
python_function('oqlos/hardware/diagnosis.py', '_host_actions_from_report', 1, 7, 12).
python_function('oqlos/hardware/diagnosis.py', '_recover_targets', 2, 6, 6).
python_function('oqlos/hardware/diagnosis.py', '_should_force_sidecar_restart', 1, 4, 4).
python_function('oqlos/hardware/diagnosis.py', '_repair_sidecar_if_needed', 5, 3, 5).
python_function('oqlos/hardware/diagnosis.py', 'execute_safe_recover', 2, 10, 14).
python_function('oqlos/hardware/diagnosis_device_actions.py', 'add_modbus_device_actions', 5, 5, 3).
python_function('oqlos/hardware/diagnosis_device_actions.py', '_sidecar_recovery_actions', 1, 2, 1).
python_function('oqlos/hardware/diagnosis_device_actions.py', 'add_tic249_device_actions', 4, 6, 3).
python_function('oqlos/hardware/diagnosis_device_actions.py', 'add_dri0050_device_actions', 4, 6, 3).
python_function('oqlos/hardware/diagnosis_device_actions.py', 'diagnose_plugin_devices', 5, 11, 10).
python_function('oqlos/hardware/diagnosis_device_actions.py', 'diagnose_barcode_scanner', 1, 9, 5).
python_function('oqlos/hardware/diagnosis_device_actions.py', 'build_report_global_actions', 4, 4, 3).
python_function('oqlos/hardware/diagnosis_plugin_health.py', 'health_map', 1, 4, 2).
python_function('oqlos/hardware/diagnosis_plugin_health.py', 'is_stale_hardware_message', 1, 3, 3).
python_function('oqlos/hardware/diagnosis_plugin_health.py', 'is_stale_hardware_entry', 1, 2, 3).
python_function('oqlos/hardware/diagnosis_plugin_health.py', 'plugin_is_healthy', 1, 4, 4).
python_function('oqlos/hardware/diagnosis_plugin_health.py', 'plugin_needs_repair', 2, 8, 5).
python_function('oqlos/hardware/diagnosis_plugin_health.py', 'modbus_plugins_need_repair', 1, 5, 4).
python_function('oqlos/hardware/diagnosis_plugin_health.py', 'message_lower', 1, 4, 3).
python_function('oqlos/hardware/diagnosis_plugin_health.py', 'infer_status', 2, 7, 4).
python_function('oqlos/hardware/diagnosis_types.py', 'action_dict', 1, 1, 0).
python_function('oqlos/hardware/diagnosis_types.py', 'report_to_dict', 1, 4, 4).
python_function('oqlos/hardware/discovery.py', '_ensure_local_pimodbus_on_path', 0, 5, 5).
python_function('oqlos/hardware/discovery.py', '_probe_waveshare', 1, 5, 2).
python_function('oqlos/hardware/discovery.py', '_probe_waveshare_role', 6, 3, 1).
python_function('oqlos/hardware/discovery.py', '_build_waveshare_probe', 2, 1, 1).
python_function('oqlos/hardware/firmware_adapter.py', '_first_nonempty', 1, 3, 1).
python_function('oqlos/hardware/firmware_adapter.py', '_extract_failure_message', 1, 9, 4).
python_function('oqlos/hardware/firmware_adapter.py', '_parse_numeric', 1, 2, 3).
python_function('oqlos/hardware/gateway_http.py', 'get_json', 2, 1, 5).
python_function('oqlos/hardware/gateway_http.py', 'post_json', 3, 1, 5).
python_function('oqlos/hardware/health_status.py', 'health_status_is_ok', 1, 11, 5).
python_function('oqlos/hardware/hui_actions.py', 'list_hui_actions', 0, 2, 6).
python_function('oqlos/hardware/hui_artificial_lung.py', '_run_tic249_reciprocate', 1, 6, 13).
python_function('oqlos/hardware/hui_artificial_lung.py', 'start_hui_artificial_lung', 1, 5, 7).
python_function('oqlos/hardware/hui_artificial_lung.py', 'stop_hui_artificial_lung', 1, 2, 4).
python_function('oqlos/hardware/hui_hold.py', '_normalize_hui_profile_key', 1, 3, 5).
python_function('oqlos/hardware/hui_hold.py', '_coerce_valve_ids', 1, 7, 5).
python_function('oqlos/hardware/hui_hold.py', '_coerce_float', 1, 2, 1).
python_function('oqlos/hardware/hui_hold.py', '_profile_from_map_action', 1, 12, 8).
python_function('oqlos/hardware/hui_hold.py', '_mapped_hui_hold_profiles', 0, 6, 5).
python_function('oqlos/hardware/hui_hold.py', 'get_hui_hold_profiles', 0, 2, 5).
python_function('oqlos/hardware/hui_hold.py', '_success', 1, 5, 3).
python_function('oqlos/hardware/hui_hold.py', '_operation', 2, 1, 0).
python_function('oqlos/hardware/hui_hold.py', '_set_valve', 3, 1, 3).
python_function('oqlos/hardware/hui_hold.py', '_set_pump', 2, 1, 3).
python_function('oqlos/hardware/hui_hold.py', '_set_pump_best_effort', 2, 2, 3).
python_function('oqlos/hardware/hui_hold.py', 'shutdown_all_hui_hardware', 1, 4, 7).
python_function('oqlos/hardware/hui_hold.py', '_hold_start_failure', 1, 1, 0).
python_function('oqlos/hardware/hui_hold.py', '_engage_hold_valves', 2, 3, 6).
python_function('oqlos/hardware/hui_hold.py', '_engage_hold_pump_if_needed', 2, 3, 4).
python_function('oqlos/hardware/hui_hold.py', 'start_hui_hold', 2, 5, 12).
python_function('oqlos/hardware/hui_hold.py', 'stop_hui_hold', 2, 4, 6).
python_function('oqlos/hardware/hui_lung_recipe.py', 'build_hui_lung_reciprocate_args', 0, 1, 2).
python_function('oqlos/hardware/hui_lung_recipe.py', '_mapped_hui_lung_action_body', 0, 9, 7).
python_function('oqlos/hardware/hui_lung_recipe.py', '_int_from_body', 1, 4, 2).
python_function('oqlos/hardware/hui_lung_recipe.py', '_float_from_body', 1, 4, 1).
python_function('oqlos/hardware/hui_lung_recipe.py', '_text_from_body', 1, 4, 3).
python_function('oqlos/hardware/hui_lung_recipe.py', 'get_hui_lung_valve_id', 0, 1, 2).
python_function('oqlos/hardware/hui_lung_recipe.py', 'get_hui_lung_reciprocate_args', 0, 6, 12).
python_function('oqlos/hardware/identify_enrichment.py', 'enrich_identify_payload', 1, 2, 4).
python_function('oqlos/hardware/modbus_identify.py', '_usb_blob', 1, 3, 4).
python_function('oqlos/hardware/modbus_identify.py', '_is_modbus_candidate', 1, 5, 2).
python_function('oqlos/hardware/modbus_identify.py', '_device_to_candidate', 1, 8, 2).
python_function('oqlos/hardware/modbus_identify.py', 'collect_modbus_serial_candidates', 1, 6, 4).
python_function('oqlos/hardware/modbus_identify.py', '_infer_modbus_serial_port', 1, 10, 4).
python_function('oqlos/hardware/modbus_identify.py', 'enrich_platform_modbus_ports', 1, 10, 5).
python_function('oqlos/hardware/modbus_identify.py', 'enrich_modbus_serial_hints', 1, 10, 4).
python_function('oqlos/hardware/modbus_identify.py', 'enrich_modbus_identify', 1, 1, 2).
python_function('oqlos/hardware/peripheral_mapping.py', 'resolve_target_to_plugin', 1, 1, 1).
python_function('oqlos/hardware/peripheral_mapping.py', 'register_custom_mapping', 2, 1, 0).
python_function('oqlos/hardware/peripheral_mapping.py', 'get_all_mappings', 0, 1, 1).
python_function('oqlos/hardware/peripheral_mapping.py', 'generate_dynamic_valve_mappings', 1, 2, 1).
python_function('oqlos/hardware/plugins/_rtu_serial.py', 'serial_error_is_stale', 1, 4, 2).
python_function('oqlos/hardware/plugins/_rtu_serial.py', 'reopen_rtu_after_stale', 2, 4, 6).
python_function('oqlos/hardware/plugins/_rtu_serial.py', 'rtu_timeout', 1, 2, 2).
python_function('oqlos/hardware/plugins/_rtu_serial.py', 'rtu_device_id', 1, 2, 3).
python_function('oqlos/hardware/plugins/_shared.py', 'http_health_check', 3, 2, 3).
python_function('oqlos/hardware/plugins/_shared.py', 'not_connected_health', 1, 1, 1).
python_function('oqlos/hardware/plugins/_shared.py', 'health_check_exception', 1, 1, 1).
python_function('oqlos/hardware/plugins/_shared.py', '_error_health', 1, 1, 1).
python_function('oqlos/hardware/plugins/_shared.py', 'http_disconnect', 2, 2, 2).
python_function('oqlos/hardware/plugins/_shared.py', 'disconnect_http_plugin', 2, 1, 1).
python_function('oqlos/hardware/plugins/base.py', 'get_pluggy_manager', 0, 1, 0).
python_function('oqlos/hardware/plugins/base.py', 'dynamic_peripheral_model', 1, 5, 6).
python_function('oqlos/hardware/plugins/base.py', 'dynamic_plugin_schema_models', 1, 2, 4).
python_function('oqlos/hardware/plugins/modbus_adc.py', '_resolve_channel', 1, 3, 7).
python_function('oqlos/hardware/plugins/modbus_adc.py', '_modbus_error', 1, 2, 4).
python_function('oqlos/hardware/plugins/motor_http_handlers.py', 'motor_http_request', 2, 4, 8).
python_function('oqlos/hardware/plugins/motor_http_handlers.py', 'motor_cli_command', 1, 3, 8).
python_function('oqlos/hardware/plugins/motor_modbus_handlers.py', 'duty_pct_to_register', 1, 1, 4).
python_function('oqlos/hardware/plugins/motor_modbus_handlers.py', 'connect_modbus_bus', 0, 3, 3).
python_function('oqlos/hardware/plugins/motor_modbus_handlers.py', 'modbus_health_check', 1, 7, 5).
python_function('oqlos/hardware/plugins/motor_modbus_handlers.py', 'modbus_set_speed', 1, 7, 6).
python_function('oqlos/hardware/plugins/motor_modbus_handlers.py', 'modbus_stop', 1, 3, 3).
python_function('oqlos/hardware/plugins/motor_modbus_handlers.py', 'modbus_status', 1, 8, 9).
python_function('oqlos/hardware/plugins/piadc.py', '_is_raspberry_pi_host', 0, 1, 4).
python_function('oqlos/hardware/plugins/piadc.py', '_requires_remote_rpi_hint', 2, 5, 4).
python_function('oqlos/hardware/plugins/piadc.py', '_resolve_sensor_channel', 1, 2, 6).
python_function('oqlos/hardware/plugins/plugin_http_handlers.py', 'http_post_command', 3, 3, 3).
python_function('oqlos/hardware/plugins/plugin_http_handlers.py', 'http_get_command', 3, 2, 3).
python_function('oqlos/hardware/rtc_probe.py', 'is_rtc_hardware_enabled', 0, 3, 3).
python_function('oqlos/hardware/rtc_probe.py', 'get_pirtc_base_url', 0, 1, 2).
python_function('oqlos/hardware/rtc_probe.py', '_pirtc_request_sync', 2, 8, 8).
python_function('oqlos/hardware/rtc_probe.py', 'build_rtc_peripheral_status', 0, 11, 5).
python_function('oqlos/hardware/rtc_probe.py', 'run_rtc_command', 2, 4, 4).
python_function('oqlos/hardware/rtc_probe.py', 'build_rtc_adapter_entry', 0, 8, 5).
python_function('oqlos/hardware/rtc_probe.py', 'enrich_rtc_adapter', 1, 8, 9).
python_function('oqlos/hardware/scanner_probe.py', '_join_blob', 2, 3, 4).
python_function('oqlos/hardware/scanner_probe.py', '_match_blob', 1, 1, 1).
python_function('oqlos/hardware/scanner_probe.py', '_is_likely_scanner_usb_blob', 1, 7, 2).
python_function('oqlos/hardware/scanner_probe.py', '_is_likely_scanner_input', 2, 10, 2).
python_function('oqlos/hardware/scanner_probe.py', '_usb_product_blob', 1, 1, 1).
python_function('oqlos/hardware/scanner_probe.py', '_canonical_match_key', 1, 8, 5).
python_function('oqlos/hardware/scanner_probe.py', '_match_priority', 1, 8, 4).
python_function('oqlos/hardware/scanner_probe.py', '_merge_matches', 0, 6, 5).
python_function('oqlos/hardware/scanner_probe.py', '_scan_lsusb_matches', 0, 5, 7).
python_function('oqlos/hardware/scanner_probe.py', '_scan_input_matches', 0, 8, 9).
python_function('oqlos/hardware/scanner_probe.py', '_scan_diagnostics_usb_matches', 1, 14, 6).
python_function('oqlos/hardware/scanner_probe.py', 'resolve_scanner_presence', 1, 1, 7).
python_function('oqlos/hardware/scanner_probe.py', 'build_scanner_adapter_entry', 1, 12, 5).
python_function('oqlos/hardware/scanner_probe.py', 'enrich_scanner_adapter', 1, 9, 9).
python_function('oqlos/hardware/sidecar_control.py', '_modbus_serial_candidates', 0, 4, 5).
python_function('oqlos/hardware/sidecar_control.py', 'resolve_dri0050_serial', 1, 13, 7).
python_function('oqlos/hardware/sidecar_control.py', '_dri0050_paths', 0, 9, 6).
python_function('oqlos/hardware/sidecar_control.py', '_poll_until_ok', 1, 4, 4).
python_function('oqlos/hardware/sidecar_control.py', '_dri0050_probe_ok', 0, 3, 2).
python_function('oqlos/hardware/sidecar_control.py', '_http_sidecar_poll', 0, 1, 2).
python_function('oqlos/hardware/sidecar_control.py', '_http_sidecar_listening', 0, 1, 1).
python_function('oqlos/hardware/sidecar_control.py', '_http_sidecar_healthy', 0, 1, 1).
python_function('oqlos/hardware/sidecar_control.py', '_run_cmd', 0, 3, 5).
python_function('oqlos/hardware/sidecar_control.py', '_free_api_port', 1, 7, 6).
python_function('oqlos/hardware/sidecar_control.py', 'ensure_dri0050_sidecar', 0, 13, 10).
python_function('oqlos/hardware/sidecar_control.py', '_tic249_status', 1, 3, 3).
python_function('oqlos/hardware/sidecar_control.py', '_tic249_connect', 1, 2, 2).
python_function('oqlos/hardware/sidecar_control.py', '_tic249_listening_ok', 0, 1, 1).
python_function('oqlos/hardware/sidecar_control.py', '_tic249_connected_ok', 0, 2, 4).
python_function('oqlos/hardware/sidecar_control.py', '_http_tic249_listening', 0, 1, 1).
python_function('oqlos/hardware/sidecar_control.py', '_http_tic249_connected', 0, 1, 1).
python_function('oqlos/hardware/sidecar_control.py', 'ensure_tic249_sidecar', 0, 7, 4).
python_function('oqlos/hardware/stack_snapshot.py', '_lazy_hardware_api', 0, 1, 0).
python_function('oqlos/hardware/stack_snapshot.py', '_get_modbus_preflight', 1, 5, 4).
python_function('oqlos/hardware/stack_snapshot.py', '_build_recommended_actions', 2, 8, 5).
python_function('oqlos/hardware/stack_snapshot.py', 'build_hardware_stack_snapshot', 1, 3, 10).
python_function('oqlos/hardware/tic249_units.py', 'steps_per_second_to_raw', 1, 5, 3).
python_function('oqlos/hardware/tic249_units.py', 'raw_acceleration_for_ramp', 2, 2, 1).
python_function('oqlos/hardware/transport/manage_ops.py', 'run_manage_verb', 2, 3, 3).
python_function('oqlos/hardware/transport/manage_ops.py', '_resolve', 1, 5, 22).
python_function('oqlos/hardware/transport/manage_ops.py', 'list_manage_verbs', 0, 1, 1).
python_function('oqlos/hardware/transport/manage_ops_diagnostic.py', '_success_from_result', 1, 4, 3).
python_function('oqlos/hardware/transport/manage_ops_diagnostic.py', 'run_modbus_io_valve', 3, 5, 7).
python_function('oqlos/hardware/transport/manage_ops_diagnostic.py', 'run_pump_diagnostic', 2, 2, 5).
python_function('oqlos/hardware/transport/manage_ops_diagnostic.py', '_resolve_move_relative_params', 1, 3, 9).
python_function('oqlos/hardware/transport/manage_ops_diagnostic.py', 'run_motor_tic249_extended', 2, 2, 4).
python_function('oqlos/hardware/transport/manage_ops_diagnostic.py', '_extract_diagnostic_ids', 1, 5, 4).
python_function('oqlos/hardware/transport/manage_ops_diagnostic.py', '_extract_params', 1, 3, 2).
python_function('oqlos/hardware/transport/manage_ops_diagnostic.py', '_route_tic249_lung_command', 2, 3, 2).
python_function('oqlos/hardware/transport/manage_ops_diagnostic.py', '_route_diagnostic_command', 5, 7, 4).
python_function('oqlos/hardware/transport/manage_ops_diagnostic.py', 'run_diagnostic_command', 1, 3, 4).
python_function('oqlos/hardware/transport/manage_ops_usb.py', 'usb_list', 1, 1, 2).
python_function('oqlos/hardware/transport/manage_ops_usb.py', 'pi_diagnostics', 1, 1, 1).
python_function('oqlos/hardware/transport/manage_ops_usb.py', 'usb_reset', 1, 1, 2).
python_function('oqlos/hardware/transport/mqtt_oql_bridge.py', 'build_topics', 2, 1, 2).
python_function('oqlos/hardware/transport/mqtt_oql_bridge.py', '_make_client', 1, 4, 2).
python_function('oqlos/hardware/usb_diagnostics.py', '_read', 1, 2, 3).
python_function('oqlos/hardware/usb_diagnostics.py', '_find_tty', 1, 5, 8).
python_function('oqlos/hardware/usb_diagnostics.py', 'list_usb_devices', 0, 13, 13).
python_function('oqlos/hardware/usb_diagnostics.py', 'pi_system_diagnostics', 0, 9, 17).
python_function('oqlos/hardware/usb_diagnostics.py', 'reset_usb_device', 3, 12, 5).
python_function('oqlos/reporters/html_report.py', 'render_html_report', 1, 8, 8).
python_function('oqlos/reporters/html_report.py', '_render_device_meta', 1, 6, 4).
python_function('oqlos/reporters/html_report.py', '_render_goal', 2, 10, 8).
python_function('oqlos/reporters/html_report.py', '_render_thresholds_table', 1, 2, 3).
python_function('oqlos/reporters/html_report.py', '_render_step', 2, 7, 5).
python_function('oqlos/reporters/json_reporter.py', '_step_to_dict', 1, 6, 1).
python_function('oqlos/reporters/json_reporter.py', '_group_steps_into_goals', 1, 6, 6).
python_function('oqlos/reporters/json_reporter.py', '_collect_thresholds', 1, 8, 3).
python_function('oqlos/reporters/json_reporter.py', '_extract_metadata', 1, 2, 2).
python_function('oqlos/reporters/json_reporter.py', 'report_json', 1, 2, 8).
python_function('oqlos/reporters/junit.py', 'report_junit', 2, 1, 2).
python_function('oqlos/scenarios/legacy_aliases.py', '_repo_scenarios_dir', 0, 1, 2).
python_function('oqlos/scenarios/legacy_aliases.py', '_load_legacy_aliases', 0, 4, 6).
python_function('oqlos/scenarios/legacy_aliases.py', 'resolve_canonical_scenario_file', 2, 5, 5).
python_function('oqlos/shared/_endpoint_helpers.py', 'serve_html_page', 1, 2, 3).
python_function('oqlos/shared/_endpoint_helpers.py', 'make_collection_route', 2, 1, 3).
python_function('oqlos/shared/_endpoint_helpers.py', 'get_or_404', 3, 2, 1).
python_function('oqlos/shared/config_factory.py', 'create_nfo_setup', 0, 1, 7).
python_function('oqlos/shared/event_server.py', 'main', 0, 2, 6).
python_function('oqlos/shared/file_ops.py', '_ensure_safe_path', 2, 2, 4).
python_function('oqlos/shared/file_ops.py', 'list_files', 3, 4, 5).
python_function('oqlos/shared/file_ops.py', 'iter_entries', 1, 3, 6).
python_function('oqlos/shared/file_ops.py', 'read_file', 2, 3, 6).
python_function('oqlos/shared/file_ops.py', 'env_configured_path', 2, 3, 3).
python_function('oqlos/shared/file_ops.py', 'read_text_file_or_empty', 1, 2, 3).
python_function('oqlos/shared/file_ops.py', 'write_file', 3, 1, 3).
python_function('oqlos/shared/logger.py', 'configure_oqlos_logging', 0, 12, 16).
python_function('oqlos/shared/logger.py', 'get_logger', 1, 4, 3).
python_function('oqlos/shared/logs_query.py', 'resolve_logs_db_path', 1, 2, 5).
python_function('oqlos/shared/release_version.py', 'clean_version', 1, 6, 5).
python_function('oqlos/shared/release_version.py', '_run_git', 1, 4, 3).
python_function('oqlos/shared/release_version.py', '_read_version_from_package_json', 1, 4, 5).
python_function('oqlos/shared/release_version.py', '_read_version_from_text', 1, 4, 4).
python_function('oqlos/shared/release_version.py', '_version_candidates', 1, 1, 0).
python_function('oqlos/shared/release_version.py', 'resolve_release_version', 1, 11, 9).
python_function('oqlos/shared/release_version.py', 'main', 0, 1, 2).
python_function('oqlos/shared/version_endpoint.py', 'build_version_payload', 2, 3, 2).
python_function('oqlos/shared/version_endpoint.py', 'create_version_router', 0, 2, 4).
python_function('oqlos/tools/cql_cli/__init__.py', '_sync_compat_symbols', 0, 1, 0).
python_function('oqlos/tools/cql_cli/__init__.py', 'main', 0, 1, 2).
python_function('oqlos/tools/cql_cli/commands.py', 'default_firmware_url', 0, 3, 2).
python_function('oqlos/tools/cql_cli/commands.py', 'run_source', 2, 2, 3).
python_function('oqlos/tools/cql_cli/commands.py', 'run_single_command', 1, 1, 2).
python_function('oqlos/tools/cql_cli/commands.py', 'handle_list_command', 1, 7, 8).
python_function('oqlos/tools/cql_cli/commands.py', 'execute_command_with_cleanup', 4, 8, 6).
python_function('oqlos/tools/cql_cli/commands.py', '_run_continuous_mode', 2, 4, 13).
python_function('oqlos/tools/cql_cli/formatting.py', '_quote_oql', 1, 2, 3).
python_function('oqlos/tools/cql_cli/formatting.py', 'canonicalize_oql_text', 1, 3, 4).
python_function('oqlos/tools/cql_cli/formatting.py', 'canonicalize_oql_line', 1, 14, 6).
python_function('oqlos/tools/cql_cli/main.py', 'create_file_parser', 0, 1, 3).
python_function('oqlos/tools/cql_cli/main.py', 'create_run_parser', 0, 1, 1).
python_function('oqlos/tools/cql_cli/main.py', 'create_hardware_parser', 1, 2, 3).
python_function('oqlos/tools/cql_cli/main.py', 'create_format_parser', 0, 1, 2).
python_function('oqlos/tools/cql_cli/main.py', 'create_cmd_parser', 0, 1, 3).
python_function('oqlos/tools/cql_cli/main.py', 'run_file_mode', 1, 6, 14).
python_function('oqlos/tools/cql_cli/main.py', '_create_interpreter', 2, 1, 1).
python_function('oqlos/tools/cql_cli/main.py', '_run_interpreter_target', 2, 2, 4).
python_function('oqlos/tools/cql_cli/main.py', '_fetch_scenario_source', 1, 7, 8).
python_function('oqlos/tools/cql_cli/main.py', '_extract_scenario_source', 1, 9, 3).
python_function('oqlos/tools/cql_cli/main.py', '_looks_like_html', 2, 3, 3).
python_function('oqlos/tools/cql_cli/main.py', '_print_cli_error', 1, 2, 2).
python_function('oqlos/tools/cql_cli/main.py', '_run_hardware_flags', 1, 9, 8).
python_function('oqlos/tools/cql_cli/main.py', 'run_hardware_mode', 2, 1, 5).
python_function('oqlos/tools/cql_cli/main.py', 'run_cmd_mode', 1, 4, 7).
python_function('oqlos/tools/cql_cli/main.py', 'run_format_mode', 1, 2, 7).
python_function('oqlos/tools/cql_cli/main.py', '_dispatch_to_mode', 1, 8, 10).
python_function('oqlos/tools/cql_cli/main.py', 'main', 0, 1, 1).
python_function('oqlos/tools/cql_cli/preflight.py', 'ensure_firmware_running', 1, 2, 2).
python_function('oqlos/tools/cql_cli/preflight.py', '_is_firmware_running', 1, 5, 3).
python_function('oqlos/tools/cql_cli/preflight.py', '_start_firmware_service', 1, 13, 7).
python_function('oqlos/tools/cql_cli/preflight.py', 'check_firmware_state', 3, 8, 7).
python_function('oqlos/tools/cql_cli/preflight.py', 'check_required_adapter', 4, 8, 4).
python_function('oqlos/tools/cql_cli/preflight.py', 'check_required_adapter_health', 4, 5, 3).
python_function('oqlos/tools/cql_cli/preflight.py', '_emit_preflight_error', 3, 2, 2).
python_function('oqlos/tools/cql_cli/preflight.py', 'emit_preflight_success', 7, 3, 2).
python_function('oqlos/tools/cql_cli/preflight.py', '_emit_yaml_preflight', 5, 6, 4).
python_function('oqlos/tools/cql_cli/preflight.py', '_emit_text_preflight', 5, 7, 4).
python_function('oqlos/tools/cql_cli/preflight.py', 'preflight_hardware', 2, 5, 6).
python_function('oqlos/tools/cql_cli/utils.py', 'output_yaml', 2, 2, 2).
python_function('oqlos/tools/cql_cli/utils.py', 'parse_sensor_overrides', 1, 3, 3).
python_function('oqlos/tools/cql_cli/utils.py', 'build_result_payload', 1, 2, 2).
python_function('oqlos/tools/cql_cli/utils.py', 'normalize_target_name', 1, 1, 3).
python_function('oqlos/tools/cql_cli/utils.py', 'build_single_command_scenario', 1, 2, 3).
python_function('oqlos/tools/cql_cli/utils.py', '_extract_first_action', 1, 5, 2).
python_function('oqlos/tools/cql_cli/utils.py', '_resolve_peripheral_adapter', 1, 4, 4).
python_function('oqlos/tools/cql_cli/utils.py', '_resolve_sensor_target', 1, 3, 0).
python_function('oqlos/tools/cql_cli/utils.py', 'resolve_required_adapter', 1, 8, 3).
python_function('oqlos/tools/cql_cli/utils.py', 'validate_directory', 2, 5, 9).
python_function('oqlos/tools/gen_error_docs.py', '_repair_cell', 1, 3, 0).
python_function('oqlos/tools/gen_error_docs.py', 'generate_markdown', 0, 6, 7).
python_function('oqlos/tools/gen_error_docs.py', 'main', 0, 4, 9).
python_function('oqlos/tools/hardware_diagnose/__init__.py', 'main', 0, 1, 1).
python_function('oqlos/tools/hardware_diagnose/__main__.py', '_print_list', 2, 3, 6).
python_function('oqlos/tools/hardware_diagnose/__main__.py', '_print_health', 2, 2, 4).
python_function('oqlos/tools/hardware_diagnose/__main__.py', '_print_calibrate', 2, 6, 3).
python_function('oqlos/tools/hardware_diagnose/__main__.py', '_print_benchmark', 3, 3, 3).
python_function('oqlos/tools/hardware_diagnose/__main__.py', '_print_detect', 3, 2, 4).
python_function('oqlos/tools/hardware_diagnose/__main__.py', '_print_doctor', 4, 2, 4).
python_function('oqlos/tools/hardware_diagnose/__main__.py', '_print_modbus_probe', 2, 2, 5).
python_function('oqlos/tools/hardware_diagnose/__main__.py', 'main', 0, 3, 7).
python_function('oqlos/tools/hardware_diagnose/__main__.py', '_handle_report_action', 3, 3, 3).
python_function('oqlos/tools/hardware_diagnose/__main__.py', '_dispatch_action', 3, 3, 2).
python_function('oqlos/tools/hardware_diagnose/__main__.py', '_print_diagnose', 2, 3, 8).
python_function('oqlos/tools/hardware_diagnose/benchmark.py', 'run_benchmark', 2, 6, 11).
python_function('oqlos/tools/hardware_diagnose/calibration.py', 'run_calibration_test', 1, 2, 6).
python_function('oqlos/tools/hardware_diagnose/calibration.py', '_calibrate_pump', 3, 3, 4).
python_function('oqlos/tools/hardware_diagnose/calibration.py', '_calibrate_valves', 3, 4, 3).
python_function('oqlos/tools/hardware_diagnose/calibration.py', '_calibrate_sensors', 3, 5, 5).
python_function('oqlos/tools/hardware_diagnose/discovery.py', '_run_shell_command', 1, 2, 2).
python_function('oqlos/tools/hardware_diagnose/discovery.py', 'list_usb_serial_devices', 0, 7, 6).
python_function('oqlos/tools/hardware_diagnose/discovery.py', 'list_i2c_buses', 0, 1, 2).
python_function('oqlos/tools/hardware_diagnose/discovery.py', 'detect_chips_on_i2c', 1, 8, 9).
python_function('oqlos/tools/hardware_diagnose/doctor.py', 'build_doctor_report', 1, 11, 11).
python_function('oqlos/tools/hardware_diagnose/doctor_common.py', 'add_issue', 1, 2, 1).
python_function('oqlos/tools/hardware_diagnose/doctor_common.py', 'plugin_config', 2, 3, 2).
python_function('oqlos/tools/hardware_diagnose/doctor_common.py', 'modbus_config', 1, 1, 1).
python_function('oqlos/tools/hardware_diagnose/doctor_common.py', 'modbus_adc_config', 1, 1, 1).
python_function('oqlos/tools/hardware_diagnose/doctor_common.py', 'collect_repairs', 1, 5, 6).
python_function('oqlos/tools/hardware_diagnose/doctor_detection.py', '_doctor', 0, 1, 0).
python_function('oqlos/tools/hardware_diagnose/doctor_detection.py', 'usb_serial_only', 1, 3, 1).
python_function('oqlos/tools/hardware_diagnose/doctor_detection.py', 'load_config_summary', 1, 4, 5).
python_function('oqlos/tools/hardware_diagnose/doctor_detection.py', 'run_modbus_probe', 2, 5, 8).
python_function('oqlos/tools/hardware_diagnose/doctor_detection.py', 'probe_modbus', 1, 1, 2).
python_function('oqlos/tools/hardware_diagnose/doctor_detection.py', 'probe_modbus_adc', 1, 1, 2).
python_function('oqlos/tools/hardware_diagnose/doctor_detection.py', 'firmware_hostname', 1, 3, 2).
python_function('oqlos/tools/hardware_diagnose/doctor_detection.py', 'detect_hardware', 1, 4, 12).
python_function('oqlos/tools/hardware_diagnose/doctor_firmware.py', 'adapter_health_status', 2, 3, 1).
python_function('oqlos/tools/hardware_diagnose/doctor_firmware.py', 'firmware_is_remote', 1, 2, 2).
python_function('oqlos/tools/hardware_diagnose/doctor_firmware.py', 'firmware_adapter_status', 2, 7, 3).
python_function('oqlos/tools/hardware_diagnose/doctor_firmware.py', 'firmware_modbus_health_ok', 1, 10, 6).
python_function('oqlos/tools/hardware_diagnose/doctor_firmware.py', 'firmware_modbus_adc_health_ok', 1, 4, 3).
python_function('oqlos/tools/hardware_diagnose/doctor_firmware.py', 'check_firmware_health_error', 2, 3, 2).
python_function('oqlos/tools/hardware_diagnose/doctor_firmware.py', 'check_firmware_mode', 2, 3, 4).
python_function('oqlos/tools/hardware_diagnose/doctor_firmware.py', 'check_firmware_serial_access', 4, 11, 5).
python_function('oqlos/tools/hardware_diagnose/doctor_firmware.py', 'check_firmware_adapters', 3, 7, 5).
python_function('oqlos/tools/hardware_diagnose/doctor_firmware.py', 'analyze_firmware_access', 2, 7, 7).
python_function('oqlos/tools/hardware_diagnose/doctor_format.py', 'format_modbus_status', 1, 7, 4).
python_function('oqlos/tools/hardware_diagnose/doctor_format.py', 'format_detection', 1, 10, 6).
python_function('oqlos/tools/hardware_diagnose/doctor_format.py', '_format_doctor_issues', 1, 5, 5).
python_function('oqlos/tools/hardware_diagnose/doctor_format.py', '_format_doctor_applied_repairs', 1, 4, 2).
python_function('oqlos/tools/hardware_diagnose/doctor_format.py', '_format_doctor_unapplied', 2, 8, 3).
python_function('oqlos/tools/hardware_diagnose/doctor_format.py', 'format_doctor', 1, 6, 9).
python_function('oqlos/tools/hardware_diagnose/doctor_modbus_analysis.py', 'expected_modbus_params', 1, 5, 3).
python_function('oqlos/tools/hardware_diagnose/doctor_modbus_analysis.py', 'expected_modbus_adc_params', 1, 6, 3).
python_function('oqlos/tools/hardware_diagnose/doctor_modbus_analysis.py', 'analyze_modbus_adc_config', 2, 12, 7).
python_function('oqlos/tools/hardware_diagnose/doctor_modbus_analysis.py', 'analyze_modbus_config', 2, 11, 7).
python_function('oqlos/tools/hardware_diagnose/doctor_modbus_analysis.py', 'analyze_serial_port_owners', 2, 13, 8).
python_function('oqlos/tools/hardware_diagnose/doctor_repairs.py', 'update_modbus_config', 2, 2, 10).
python_function('oqlos/tools/hardware_diagnose/doctor_repairs.py', 'update_modbus_adc_config', 2, 4, 10).
python_function('oqlos/tools/hardware_diagnose/doctor_repairs.py', 'apply_safe_fixes', 2, 9, 6).
python_function('oqlos/tools/hardware_diagnose/doctor_serial.py', 'extract_pids', 1, 4, 4).
python_function('oqlos/tools/hardware_diagnose/doctor_serial.py', 'describe_pid', 1, 4, 4).
python_function('oqlos/tools/hardware_diagnose/doctor_serial.py', 'serial_port_owners', 1, 6, 4).
python_function('oqlos/tools/hardware_diagnose/doctor_serial.py', 'canonical_device_path', 1, 3, 4).
python_function('oqlos/tools/hardware_diagnose/doctor_serial.py', 'owners_for_configured_port', 2, 4, 2).
python_function('oqlos/tools/hardware_diagnose/health.py', '_request_firmware_json', 2, 8, 6).
python_function('oqlos/tools/hardware_diagnose/health.py', 'check_firmware_health', 1, 1, 1).
python_function('oqlos/tools/hardware_diagnose/health.py', 'check_firmware_identify', 1, 1, 1).
python_function('oqlos/tools/hardware_diagnose/health.py', '_is_health_ok', 1, 5, 3).
python_function('oqlos/tools/hardware_diagnose/health.py', '_format_health_value', 1, 8, 3).
python_function('oqlos/tools/hardware_diagnose/health.py', 'cmd_health', 1, 5, 8).
python_function('oqlos/tools/hardware_diagnose/health.py', 'cmd_diagnose', 1, 6, 10).
python_function('oqlos/tools/hardware_diagnose/modbus_probe.py', '_env_typed', 3, 2, 2).
python_function('oqlos/tools/hardware_diagnose/modbus_probe.py', '_env_int', 2, 1, 1).
python_function('oqlos/tools/hardware_diagnose/modbus_probe.py', '_env_int_list', 2, 5, 5).
python_function('oqlos/tools/hardware_diagnose/modbus_probe.py', '_env_count_list', 2, 2, 2).
python_function('oqlos/tools/hardware_diagnose/modbus_probe.py', '_env_str_list', 2, 3, 2).
python_function('oqlos/tools/hardware_diagnose/modbus_probe.py', '_env_float', 2, 1, 1).
python_function('oqlos/tools/hardware_diagnose/modbus_probe.py', '_split_values', 1, 5, 4).
python_function('oqlos/tools/hardware_diagnose/modbus_probe.py', '_arg_str_list', 2, 2, 1).
python_function('oqlos/tools/hardware_diagnose/modbus_probe.py', '_arg_int_list', 2, 3, 2).
python_function('oqlos/tools/hardware_diagnose/modbus_probe.py', '_arg_count_list', 2, 3, 2).
python_function('oqlos/tools/hardware_diagnose/modbus_probe.py', '_serials_from_env', 0, 3, 3).
python_function('oqlos/tools/hardware_diagnose/modbus_probe.py', 'add_modbus_probe_arguments', 1, 1, 1).
python_function('oqlos/tools/hardware_diagnose/modbus_probe.py', 'probe_options_from_args', 1, 2, 11).
python_function('oqlos/tools/hardware_diagnose/modbus_probe.py', 'run_modbus_probe_from_args', 1, 1, 2).
python_function('oqlos/tools/hardware_diagnose/modbus_probe.py', 'run_modbus_probe_from_env', 0, 1, 8).
python_function('oqlos/tools/hardware_diagnose/modbus_probe.py', 'run_modbus_probe', 0, 1, 1).
python_function('oqlos/tools/hardware_diagnose/modbus_probe.py', 'main', 1, 2, 7).
python_function('oqlos/tools/hardware_diagnose/report.py', 'format_peripheral_table', 1, 12, 2).
python_function('oqlos/tools/hardware_diagnose/report.py', 'save_diagnostic_report', 2, 3, 12).
python_function('oqlos/tools/hardware_diagnose/shell.py', '_cmd_list', 0, 5, 6).
python_function('oqlos/tools/hardware_diagnose/shell.py', '_cmd_calibrate', 1, 4, 2).
python_function('oqlos/tools/hardware_diagnose/shell.py', '_cmd_benchmark', 2, 4, 4).
python_function('oqlos/tools/hardware_diagnose/shell.py', '_dispatch_command', 3, 6, 9).
python_function('oqlos/tools/hardware_diagnose/shell.py', 'interactive_shell', 1, 6, 6).
python_function('oqlos/tools/plugin_cli.py', '_default_config_path', 0, 1, 2).
python_function('oqlos/tools/plugin_cli.py', '_load_config_file', 1, 4, 9).
python_function('oqlos/tools/plugin_cli.py', '_save_config_file', 2, 3, 5).
python_function('oqlos/tools/plugin_cli.py', 'cmd_list', 1, 3, 3).
python_function('oqlos/tools/plugin_cli.py', 'cmd_status', 1, 2, 2).
python_function('oqlos/tools/plugin_cli.py', 'cmd_capabilities', 1, 2, 5).
python_function('oqlos/tools/plugin_cli.py', 'cmd_validate', 1, 8, 7).
python_function('oqlos/tools/plugin_cli.py', 'cmd_connect', 1, 4, 5).
python_function('oqlos/tools/plugin_cli.py', 'cmd_disconnect', 1, 2, 3).
python_function('oqlos/tools/plugin_cli.py', 'cmd_health', 1, 3, 5).
python_function('oqlos/tools/plugin_cli.py', 'cmd_execute', 1, 3, 6).
python_function('oqlos/tools/plugin_cli.py', 'cmd_reload', 1, 4, 8).
python_function('oqlos/tools/plugin_cli.py', 'cmd_peripherals', 1, 8, 6).
python_function('oqlos/tools/plugin_cli.py', 'main', 0, 3, 11).
python_function('oqlos/tools/xml_import/_utils.py', 'slugify', 1, 1, 4).
python_function('oqlos/tools/xml_import/_utils.py', 'is_pump_output', 1, 4, 2).
python_function('oqlos/tools/xml_import/_utils.py', 'is_compressor_output', 1, 5, 2).
python_function('oqlos/tools/xml_import/_utils.py', 'normalize_output_name', 1, 11, 8).
python_function('oqlos/tools/xml_import/_utils.py', 'normalize_flow_value', 1, 7, 7).
python_function('oqlos/tools/xml_import/_utils.py', 'normalize_set_value', 1, 12, 7).
python_function('oqlos/tools/xml_import/generators.py', '_mode_symbol', 1, 1, 1).
python_function('oqlos/tools/xml_import/generators.py', '_format_range', 1, 9, 0).
python_function('oqlos/tools/xml_import/generators.py', '_mode_action', 1, 3, 1).
python_function('oqlos/tools/xml_import/generators.py', '_quote_oql', 1, 2, 3).
python_function('oqlos/tools/xml_import/generators.py', '_emit_set', 3, 1, 2).
python_function('oqlos/tools/xml_import/generators.py', '_emit_cql_output', 2, 5, 8).
python_function('oqlos/tools/xml_import/generators.py', '_emit_cql_param', 2, 7, 3).
python_function('oqlos/tools/xml_import/generators.py', '_emit_cql_sensor_param', 2, 13, 1).
python_function('oqlos/tools/xml_import/generators.py', '_emit_dsl_output', 2, 5, 3).
python_function('oqlos/tools/xml_import/generators.py', '_emit_dsl_param', 2, 10, 5).
python_function('oqlos/tools/xml_import/generators.py', '_build_steps_from_op', 1, 10, 6).
python_function('oqlos/tools/xml_import/generators.py', '_append_sensor_assertion', 3, 6, 3).
python_function('oqlos/tools/xml_import/generators.py', '_build_validation_criteria', 1, 14, 3).
python_function('oqlos/tools/xml_import/generators.py', 'generate_dsl', 1, 6, 8).
python_function('oqlos/tools/xml_import/generators.py', '_emit_dsl_test_run', 3, 10, 10).
python_function('oqlos/tools/xml_import/generators.py', '_emit_dsl_sensors', 2, 8, 5).
python_function('oqlos/tools/xml_import/generators.py', '_emit_dsl_metadata', 2, 1, 1).
python_function('oqlos/tools/xml_import/generators.py', 'generate_cql', 1, 12, 12).
python_function('oqlos/tools/xml_import/generators.py', '_generate_cql_for_goal', 1, 4, 3).
python_function('oqlos/tools/xml_import/generators.py', 'generate_goals_json', 1, 13, 15).
python_function('oqlos/tools/xml_import/parser.py', 'parse_xml', 1, 6, 15).
python_function('oqlos/tools/xml_import/parser.py', '_populate_report_fields', 2, 1, 1).
python_function('oqlos/tools/xml_import/parser.py', '_parse_intervals', 2, 4, 6).
python_function('oqlos/tools/xml_import/parser.py', '_parse_test_run', 3, 7, 15).
python_function('oqlos/tools/xml_import/parser.py', '_parse_operation', 4, 6, 9).
python_function('oqlos/tools/xml_import/parser.py', '_parse_operation_params', 3, 9, 12).
python_function('oqlos/utils/hui_scenario.py', 'register_hui_test_scenario', 1, 2, 4).
python_function('oqlos/utils/sample_data.py', 'load_sample_scenarios', 1, 1, 4).
python_function('scripts/fix_brackets_to_v4.py', 'needs_migration', 1, 6, 1).
python_function('scripts/fix_brackets_to_v4.py', 'main', 0, 14, 16).
python_function('scripts/migrate_to_v4.py', 'find_oql_files', 1, 6, 6).
python_function('scripts/migrate_to_v4.py', 'has_version_header', 1, 4, 5).
python_function('scripts/migrate_to_v4.py', 'extract_version', 1, 5, 6).
python_function('scripts/migrate_to_v4.py', '_migrate_version_header', 1, 2, 1).
python_function('scripts/migrate_to_v4.py', '_migrate_goal_line', 2, 6, 6).
python_function('scripts/migrate_to_v4.py', '_migrate_loop_line', 2, 3, 2).
python_function('scripts/migrate_to_v4.py', '_migrate_endloop_line', 1, 2, 1).
python_function('scripts/migrate_to_v4.py', '_migrate_set_line', 2, 2, 3).
python_function('scripts/migrate_to_v4.py', '_migrate_simple_quoted_line', 2, 2, 2).
python_function('scripts/migrate_to_v4.py', '_migrate_wait_line', 1, 1, 1).
python_function('scripts/migrate_to_v4.py', '_migrate_minmax_line', 1, 3, 3).
python_function('scripts/migrate_to_v4.py', '_migrate_save_line', 1, 1, 1).
python_function('scripts/migrate_to_v4.py', '_migrate_single_line', 1, 6, 9).
python_function('scripts/migrate_to_v4.py', 'migrate_content', 2, 2, 6).
python_function('scripts/migrate_to_v4.py', '_scan_files', 1, 5, 4).
python_function('scripts/migrate_to_v4.py', '_perform_migration', 2, 4, 7).
python_function('scripts/migrate_to_v4.py', '_perform_dry_run', 2, 3, 5).
python_function('scripts/migrate_to_v4.py', 'main', 0, 11, 13).
python_function('scripts/migrate_to_v4.py', 'check_database', 0, 10, 10).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_fetch_json', 2, 1, 5).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_send_json', 4, 2, 8).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_extract_rows', 1, 8, 2).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_normalize_bracket_tokens', 1, 1, 3).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_to_v4_token', 1, 2, 3).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_bracket_tokens', 1, 2, 3).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_join_value_unit', 1, 2, 4).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_quote', 1, 1, 1).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_format_set', 2, 1, 3).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_strip_outer_quotes', 1, 4, 2).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_extract_num_unit', 1, 2, 3).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_merge_minmax_to_if', 1, 14, 7).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_merge_paired_if', 6, 5, 2).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_rewrite_single_sided_if', 4, 7, 3).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_rewrite_legacy_if', 1, 10, 11).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_mig_goal', 2, 2, 4).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_mig_task', 2, 11, 10).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_mig_wait', 2, 2, 4).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_mig_sample', 2, 3, 5).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_mig_minmax', 2, 2, 8).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_mig_minmax_eq', 2, 1, 1).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_mig_minmax_simple', 2, 1, 1).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_mig_delta', 2, 3, 7).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_mig_as_log', 2, 2, 2).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_mig_calc', 2, 1, 1).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_mig_val', 2, 1, 1).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_mig_if_comparison', 2, 5, 7).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_mig_else_error', 2, 2, 3).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_mig_goto', 2, 2, 3).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_mig_save', 2, 2, 4).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_mig_else_info', 2, 2, 3).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_mig_set_name', 2, 2, 3).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_mig_set_eq', 2, 5, 10).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_mig_set_noeq', 2, 8, 12).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_mig_pump', 2, 3, 7).
python_function('scripts/oql_v2_to_v4_migrate_db.py', 'migrate_v2_to_v4', 1, 13, 14).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_validate_runtime', 2, 5, 4).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_pick_code', 1, 4, 3).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_build_write_payload', 2, 1, 1).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_build_write_url', 2, 3, 2).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_process_row', 3, 6, 9).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_apply_row_update', 4, 3, 6).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_filter_rows', 2, 5, 3).
python_function('scripts/oql_v2_to_v4_migrate_db.py', '_build_migration_report', 5, 6, 3).
python_function('scripts/oql_v2_to_v4_migrate_db.py', 'main', 0, 11, 18).
python_function('scripts/oql_v2_validator.py', '_line_number', 1, 1, 0).
python_function('scripts/oql_v2_validator.py', '_validate_version_header_v2', 1, 7, 6).
python_function('scripts/oql_v2_validator.py', '_validate_line_v2', 3, 9, 4).
python_function('scripts/oql_v2_validator.py', '_validate_v2_structure', 1, 2, 7).
python_function('scripts/oql_v2_validator.py', 'validate_oql_v2_legacy', 2, 8, 5).
python_function('scripts/oql_v2_validator.py', 'main', 0, 1, 1).
python_function('scripts/oql_v4_validator.py', '_line_number', 2, 1, 0).
python_function('scripts/oql_v4_validator.py', '_validate_version_header', 1, 6, 7).
python_function('scripts/oql_v4_validator.py', '_validate_line_v4', 3, 8, 6).
python_function('scripts/oql_v4_validator.py', '_validate_goal_set_name', 2, 7, 8).
python_function('scripts/oql_v4_validator.py', '_validate_structure', 1, 2, 8).
python_function('scripts/oql_v4_validator.py', '_validate_runtime', 2, 8, 6).
python_function('scripts/oql_v4_validator.py', 'validate_oql_v4', 2, 8, 7).
python_function('scripts/oql_v4_validator.py', 'main', 0, 1, 1).
python_function('scripts/oql_validator_common.py', 'looks_like_html', 1, 2, 3).
python_function('scripts/oql_validator_common.py', 'extract_code_from_json', 1, 11, 3).
python_function('scripts/oql_validator_common.py', 'fetch_url', 2, 3, 5).
python_function('scripts/oql_validator_common.py', 'build_api_fallback_urls', 1, 5, 7).
python_function('scripts/oql_validator_common.py', 'load_source', 2, 9, 8).
python_function('scripts/oql_validator_common.py', 'run_validator_cli', 3, 4, 9).
python_function('scripts/scenarios_export.py', '_list_url', 2, 1, 1).
python_function('scripts/scenarios_export.py', '_row_url', 2, 1, 1).
python_function('scripts/scenarios_export.py', '_http_get_json', 2, 1, 4).
python_function('scripts/scenarios_export.py', '_resolve_scenario_id', 1, 5, 5).
python_function('scripts/scenarios_export.py', '_fetch_all', 1, 5, 4).
python_function('scripts/scenarios_export.py', '_fetch_one', 2, 5, 5).
python_function('scripts/scenarios_export.py', '_safe_filename', 1, 2, 2).
python_function('scripts/scenarios_export.py', 'export_all_zip', 2, 6, 16).
python_function('scripts/scenarios_export.py', 'export_one_bash', 3, 6, 17).
python_function('scripts/scenarios_export.py', '_http_patch_json', 3, 2, 8).
python_function('scripts/scenarios_export.py', '_validate_oql_v4', 2, 5, 2).
python_function('scripts/scenarios_export.py', 'import_scenarios', 3, 8, 12).
python_function('scripts/scenarios_export.py', 'main', 1, 6, 13).
python_function('setup_hardware_and_run_oql.py', 'detect_serial_devices', 0, 12, 5).
python_function('setup_hardware_and_run_oql.py', 'suggest_modbus_port', 1, 10, 2).
python_function('setup_hardware_and_run_oql.py', 'generate_env_content', 5, 2, 1).
python_function('setup_hardware_and_run_oql.py', 'setup_env_file', 4, 7, 8).
python_function('setup_hardware_and_run_oql.py', 'load_env_file', 1, 6, 8).
python_function('setup_hardware_and_run_oql.py', 'run_oql_scenario', 3, 8, 6).
python_function('setup_hardware_and_run_oql.py', 'main', 0, 3, 10).
python_function('tests/firmware/test_artificial_lung.py', '_reset_lung_state', 0, 1, 2).
python_function('tests/firmware/test_artificial_lung.py', 'test_set_lpm_updates_state', 0, 4, 1).
python_function('tests/firmware/test_artificial_lung.py', 'test_emergency_stop_resets_lpm', 0, 4, 2).
python_function('tests/firmware/test_artificial_lung.py', 'test_get_peripheral_status_includes_logical_state', 0, 4, 2).
python_function('tests/firmware/test_control_proxy.py', 'run', 1, 1, 1).
python_function('tests/firmware/test_control_proxy.py', 'proxy_with_client', 1, 1, 2).
python_function('tests/firmware/test_control_proxy.py', 'test_health_falls_back_to_alternate_oqlos_port', 0, 3, 8).
python_function('tests/firmware/test_control_proxy.py', 'test_identify_returns_unavailable_payload_after_connection_failures', 0, 6, 6).
python_function('tests/firmware/test_control_proxy.py', 'test_diagnostic_command_returns_structured_failure_payload', 0, 5, 6).
python_function('tests/firmware/test_control_proxy.py', 'test_peripheral_status_proxies_plugin_health', 0, 6, 7).
python_function('tests/firmware/test_control_proxy.py', 'test_peripheral_status_artificial_lung_uses_logical_lung_api', 0, 6, 7).
python_function('tests/firmware/test_control_proxy.py', 'test_artificial_lung_diagnostic_resolves_to_logical_lung_api', 0, 4, 1).
python_function('tests/firmware/test_control_proxy.py', 'test_peripheral_status_rtc_uses_hardware_rtc_status', 0, 5, 7).
python_function('tests/firmware/test_control_proxy.py', 'test_rtc_diagnostic_uses_hardware_rtc_command', 0, 6, 7).
python_function('tests/firmware/test_control_proxy.py', 'test_peripheral_status_returns_structured_payload_for_plugin_500', 0, 7, 5).
python_function('tests/firmware/test_control_proxy.py', 'test_resolve_diagnostic_target_rejects_invalid_modbus_valve_id', 0, 3, 3).
python_function('tests/firmware/test_dri0050_sidecar_control.py', 'test_ensure_skips_when_already_healthy', 2, 3, 7).
python_function('tests/firmware/test_dri0050_sidecar_control.py', 'test_resolve_dri0050_serial_prefers_existing_by_id', 2, 3, 6).
python_function('tests/firmware/test_dri0050_sidecar_control.py', 'test_ensure_restarts_when_listening_returns_503', 2, 3, 10).
python_function('tests/firmware/test_error_catalog.py', '_codes_used_in_source', 0, 2, 4).
python_function('tests/firmware/test_error_catalog.py', '_fstring_code_templates_in_source', 0, 2, 4).
python_function('tests/firmware/test_error_catalog.py', 'test_every_doctor_fstring_code_matches_a_registered_pattern', 0, 3, 3).
python_function('tests/firmware/test_error_catalog.py', 'test_every_source_code_is_registered_in_catalog', 0, 2, 3).
python_function('tests/firmware/test_error_catalog.py', 'test_every_catalog_code_is_still_used_somewhere', 0, 2, 3).
python_function('tests/firmware/test_error_catalog.py', 'test_error_codes_doc_is_up_to_date', 0, 3, 3).
python_function('tests/firmware/test_error_catalog.py', 'test_every_repair_template_has_a_hint_or_is_manual_only', 0, 4, 1).
python_function('tests/firmware/test_firmware.py', 'test_placeholder', 0, 2, 0).
python_function('tests/firmware/test_firmware.py', 'test_import', 0, 1, 0).
python_function('tests/firmware/test_firmware_executor.py', '_executor', 3, 3, 4).
python_function('tests/firmware/test_firmware_executor.py', 'test_plugin_action_awaits_async_pump_gateway', 0, 5, 6).
python_function('tests/firmware/test_firmware_executor.py', 'test_plugin_action_treats_failed_pump_result_as_failure', 0, 4, 5).
python_function('tests/firmware/test_firmware_executor.py', 'test_plugin_action_uses_gateway_runtime_loop_from_worker_thread', 0, 3, 15).
python_function('tests/firmware/test_gateway_http.py', 'test_gateway_get_json', 1, 4, 5).
python_function('tests/firmware/test_hardware_diagnosis_api.py', 'test_build_diagnosis_report_motors_error', 0, 8, 4).
python_function('tests/firmware/test_hardware_diagnosis_api.py', 'test_motors_only_no_global_make_hardware_up', 0, 6, 6).
python_function('tests/firmware/test_hardware_diagnosis_api.py', 'test_recover_targets_skip_devices_ok_in_report', 0, 2, 3).
python_function('tests/firmware/test_hardware_diagnosis_api.py', 'test_host_actions_filtered_motor_only_no_make', 0, 2, 4).
python_function('tests/firmware/test_hardware_diagnosis_routes.py', 'test_hardware_diagnosis_route', 1, 3, 5).
python_function('tests/firmware/test_hardware_diagnosis_routes.py', 'test_hardware_recover_rejects_unknown_scope', 1, 4, 3).
python_function('tests/firmware/test_hardware_discovery.py', 'test_list_i2c_buses_uses_glob', 1, 3, 2).
python_function('tests/firmware/test_hardware_discovery.py', 'test_list_usb_serial_devices_uses_glob_fallback', 1, 2, 3).
python_function('tests/firmware/test_hardware_doctor.py', '_write_config', 1, 1, 2).
python_function('tests/firmware/test_hardware_doctor.py', '_patch_detection', 1, 1, 2).
python_function('tests/firmware/test_hardware_doctor.py', 'test_doctor_reports_modbus_config_mismatch', 2, 7, 4).
python_function('tests/firmware/test_hardware_doctor.py', 'test_doctor_fix_updates_modbus_config', 2, 4, 6).
python_function('tests/firmware/test_hardware_doctor.py', 'test_doctor_fix_reports_unapplied_manual_repairs', 2, 5, 4).
python_function('tests/firmware/test_hardware_doctor.py', 'test_doctor_reports_busy_configured_serial_port', 2, 6, 6).
python_function('tests/firmware/test_hardware_doctor.py', 'test_doctor_reports_busy_configured_serial_port_via_by_id_symlink', 2, 6, 6).
python_function('tests/firmware/test_hardware_doctor.py', 'test_doctor_trusts_firmware_modbus_health_when_local_port_is_busy', 2, 5, 5).
python_function('tests/firmware/test_hardware_doctor.py', 'test_doctor_explains_remote_firmware_cannot_use_local_usb', 2, 7, 5).
python_function('tests/firmware/test_hardware_doctor.py', 'test_detection_filters_real_usb_serial_devices', 2, 2, 4).
python_function('tests/firmware/test_hardware_health.py', 'test_cmd_health_marks_connected_adapter_dict_as_ok', 1, 3, 2).
python_function('tests/firmware/test_hardware_health.py', 'test_cmd_health_marks_error_adapter_dict_as_warning', 1, 2, 2).
python_function('tests/firmware/test_hardware_health_http.py', 'test_hardware_health_overall_ok_ignores_disabled_plugins', 0, 2, 1).
python_function('tests/firmware/test_hardware_health_http.py', 'test_hardware_health_overall_ok_ignores_init_summary', 0, 2, 1).
python_function('tests/firmware/test_hardware_health_http.py', 'test_hardware_health_overall_ok_false_when_any_plugin_errors', 0, 2, 1).
python_function('tests/firmware/test_hardware_health_http.py', 'test_hardware_health_endpoint_returns_200_when_degraded', 1, 5, 6).
python_function('tests/firmware/test_hardware_hui_routes.py', 'test_hardware_router_includes_hui_paths', 0, 4, 0).
python_function('tests/firmware/test_hardware_hui_routes.py', 'test_raise_if_hui_failed_raises_on_error_payload', 0, 2, 2).
python_function('tests/firmware/test_hardware_hui_routes.py', 'test_hui_hold_start_uses_gateway', 1, 3, 5).
python_function('tests/firmware/test_hardware_identify.py', '_patch_gateway', 2, 1, 1).
python_function('tests/firmware/test_hardware_identify.py', '_patch_probe', 3, 2, 2).
python_function('tests/firmware/test_hardware_identify.py', '_patch_platform', 3, 2, 2).
python_function('tests/firmware/test_hardware_identify.py', 'test_collect_hardware_diagnostics_exposes_ports', 1, 5, 3).
python_function('tests/firmware/test_hardware_identify.py', 'test_platform_reports_modbus_adc_as_analog_input', 1, 5, 2).
python_function('tests/firmware/test_hardware_identify.py', 'test_hardware_identify_includes_diagnostics', 1, 12, 9).
python_function('tests/firmware/test_hardware_identify.py', 'test_hardware_identify_default_skips_live_probe', 1, 3, 6).
python_function('tests/firmware/test_hardware_identify.py', 'test_read_sensors_batch_reports_unavailable_modbus_without_503', 1, 5, 4).
python_function('tests/firmware/test_hardware_identify.py', 'test_hardware_temperature_returns_compatible_payload', 1, 4, 3).
python_function('tests/firmware/test_hardware_identify.py', 'test_hardware_diagnose_keeps_sensor_errors_in_payload', 1, 4, 4).
python_function('tests/firmware/test_hardware_identify.py', 'test_modbus_adc_raw_reports_unavailable_health_without_404', 1, 4, 4).
python_function('tests/firmware/test_hardware_identify.py', 'test_hardware_identify_reports_modbus_timeout_as_adapter_only', 1, 5, 7).
python_function('tests/firmware/test_hardware_identify_routes.py', 'test_hardware_router_includes_health_and_identify', 0, 4, 0).
python_function('tests/firmware/test_hardware_lung_routes.py', 'test_hardware_router_includes_actuator_and_lung_paths', 0, 6, 0).
python_function('tests/firmware/test_hardware_lung_routes.py', 'test_command_payload_requires_command_name', 0, 2, 2).
python_function('tests/firmware/test_hardware_mapping_motor2.py', 'test_validate_motor2_config_accepts_minimal_object', 0, 2, 1).
python_function('tests/firmware/test_hardware_mapping_motor2.py', 'test_validate_motor2_config_rejects_default_speed_above_max', 0, 2, 2).
python_function('tests/firmware/test_hardware_mapping_motor2.py', 'test_validate_mapping_contract_wraps_motor2_errors', 0, 2, 3).
python_function('tests/firmware/test_hardware_modbus_routes.py', 'test_hardware_router_includes_modbus_paths', 0, 6, 0).
python_function('tests/firmware/test_hardware_modbus_wizard.py', '_patch_modbus_ports', 2, 1, 1).
python_function('tests/firmware/test_hardware_modbus_wizard.py', '_patch_modbus_io_ids', 2, 1, 1).
python_function('tests/firmware/test_hardware_modbus_wizard.py', '_patch_modbus_settings', 2, 1, 1).
python_function('tests/firmware/test_hardware_modbus_wizard.py', '_patch_diagnose_matrix', 2, 1, 1).
python_function('tests/firmware/test_hardware_modbus_wizard.py', 'test_modbus_wizard_program_writes_uart_before_address_change', 1, 4, 5).
python_function('tests/firmware/test_hardware_modbus_wizard.py', 'test_modbus_wizard_program_skips_when_already_at_target', 1, 3, 3).
python_function('tests/firmware/test_hardware_modbus_wizard.py', 'test_build_waveshare_diagnose_uses_target_baud_fast_path', 1, 5, 9).
python_function('tests/firmware/test_hardware_modbus_wizard.py', 'test_build_waveshare_diagnose_scans_separate_adapters', 1, 5, 10).
python_function('tests/firmware/test_hardware_modbus_wizard.py', 'test_build_waveshare_skips_matrix_when_plugins_healthy', 1, 6, 9).
python_function('tests/firmware/test_hardware_modbus_wizard.py', 'test_build_waveshare_serial_stale_skips_matrix', 1, 4, 8).
python_function('tests/firmware/test_hardware_modbus_wizard.py', 'test_modbus_runtime_ports_auto_detects_separate_adapters', 1, 3, 3).
python_function('tests/firmware/test_hardware_modbus_wizard.py', 'test_modbus_runtime_ports_shared_bus_forced', 1, 4, 2).
python_function('tests/firmware/test_hardware_modbus_wizard.py', 'test_modbus_wizard_plan_exposes_per_adapter_ports', 1, 10, 6).
python_function('tests/firmware/test_hardware_platform_detect.py', 'test_detect_runtime_platform_survives_missing_pimodbus', 1, 3, 3).
python_function('tests/firmware/test_hardware_platform_detect.py', 'test_detect_runtime_platform_omits_error_key_on_success', 1, 3, 2).
python_function('tests/firmware/test_hardware_probe_devices.py', 'test_hardware_probe_reexports_device_helpers', 0, 4, 2).
python_function('tests/firmware/test_hardware_probe_devices.py', 'test_probe_tic249_detects_vendor_product', 0, 3, 1).
python_function('tests/firmware/test_hardware_runtime_routes.py', 'test_hardware_router_includes_runtime_paths', 0, 6, 0).
python_function('tests/firmware/test_hardware_runtime_routes.py', 'test_modbus_adc_unavailable_detects_incompatible_adc', 0, 3, 1).
python_function('tests/firmware/test_hardware_runtime_routes.py', 'test_read_sensor_values_skips_live_reads_when_adc_unavailable', 0, 3, 2).
python_function('tests/firmware/test_hardware_stack_snapshot.py', 'test_stack_snapshot_marks_serial_stale', 1, 4, 4).
python_function('tests/firmware/test_hardware_v3_compat.py', '_client', 0, 1, 3).
python_function('tests/firmware/test_hardware_v3_compat.py', 'test_hardware_v3_mapping_round_trip', 2, 9, 7).
python_function('tests/firmware/test_hardware_v3_compat.py', 'test_hardware_v3_mapping_rejects_invalid_contract', 2, 3, 4).
python_function('tests/firmware/test_hardware_v3_compat.py', 'test_hardware_v3_cqrs_events_record_diagnostic_failure', 1, 7, 6).
python_function('tests/firmware/test_hardware_v3_compat.py', 'test_hardware_ui_aliases_and_status_page_are_served', 0, 22, 2).
python_function('tests/firmware/test_hardware_v3_compat.py', 'test_navigation_index_and_short_aliases', 0, 15, 4).
python_function('tests/firmware/test_hui_actions.py', 'run', 1, 1, 1).
python_function('tests/firmware/test_hui_actions.py', 'test_hui_hold_profile_runs_inside_oqlos', 1, 3, 4).
python_function('tests/firmware/test_hui_actions.py', 'test_hui_hold_profile_can_be_overridden_from_hardware_map', 1, 3, 4).
python_function('tests/firmware/test_hui_actions.py', 'test_hui_actions_list_uses_mapped_profiles', 1, 3, 2).
python_function('tests/firmware/test_hui_actions.py', 'test_hui_artificial_lung_uses_tic249_plugin_recipe', 0, 11, 4).
python_function('tests/firmware/test_hui_actions.py', 'test_hui_artificial_lung_recipe_can_be_overridden_from_hardware_map', 1, 9, 5).
python_function('tests/firmware/test_hui_actions.py', 'test_stop_hui_artificial_lung_closes_the_configured_valve', 0, 4, 3).
python_function('tests/firmware/test_hui_actions.py', 'test_stop_hui_artificial_lung_uses_overridden_valve', 1, 3, 4).
python_function('tests/firmware/test_hui_actions.py', 'test_hui_artificial_lung_start_failure_cleans_up_same_valve_it_opened', 1, 4, 5).
python_function('tests/firmware/test_hui_actions.py', 'test_hui_shutdown_turns_off_pump_and_all_known_valves', 0, 7, 4).
python_function('tests/firmware/test_hui_scenario.py', 'test_register_hui_test_scenario_adds_ts_c20_once', 0, 3, 2).
python_function('tests/firmware/test_identify_enrich_modbus_io.py', 'test_expand_modbus_io_instances_clones_per_slave_id', 1, 3, 3).
python_function('tests/firmware/test_lung_plugin_reciprocate.py', '_plugin_with_client', 1, 1, 2).
python_function('tests/firmware/test_lung_plugin_reciprocate.py', 'test_ready_false_does_not_block_reciprocate_start', 0, 3, 4).
python_function('tests/firmware/test_lung_plugin_reciprocate.py', 'test_tic249_extended_reciprocate_normalizes_ramp_time_alias', 0, 3, 1).
python_function('tests/firmware/test_modbus_adc_aliases.py', 'test_resolve_channel_accepts_map_editor_v_inputs', 0, 5, 1).
python_function('tests/firmware/test_modbus_discovery.py', '_install_fake_pymodbus', 4, 1, 4).
python_function('tests/firmware/test_modbus_discovery.py', 'test_probe_waveshare_modbus_detects_working_port', 1, 7, 3).
python_function('tests/firmware/test_modbus_discovery.py', 'test_probe_waveshare_modbus_reports_adapter_only_when_no_response', 1, 7, 3).
python_function('tests/firmware/test_modbus_discovery.py', 'test_probe_waveshare_modbus_can_scan_high_baud_when_enabled', 1, 6, 4).
python_function('tests/firmware/test_modbus_identify.py', 'test_enrich_platform_modbus_ports_from_serial_list', 0, 2, 1).
python_function('tests/firmware/test_modbus_identify.py', 'test_enrich_modbus_serial_hints_on_modbus_io', 0, 5, 3).
python_function('tests/firmware/test_modbus_probe_cli.py', '_install_fake_pymodbus', 1, 1, 5).
python_function('tests/firmware/test_modbus_probe_cli.py', 'test_run_modbus_probe_returns_successful_read', 1, 6, 2).
python_function('tests/firmware/test_modbus_probe_cli.py', 'test_run_modbus_probe_reports_unsupported_function', 1, 3, 2).
python_function('tests/firmware/test_modbus_probe_cli.py', 'test_probe_options_from_args_override_environment', 1, 2, 3).
python_function('tests/firmware/test_motor_http_handlers.py', 'test_motor_http_request_maps_response_fields', 0, 5, 6).
python_function('tests/firmware/test_motor_http_handlers.py', 'test_motor_cli_command_success', 1, 3, 5).
python_function('tests/firmware/test_motor_modbus_handlers.py', 'test_duty_pct_to_register_scales_percent', 0, 4, 1).
python_function('tests/firmware/test_motor_modbus_handlers.py', 'test_modbus_health_check_reads_pid', 0, 4, 3).
python_function('tests/firmware/test_motor_modbus_handlers.py', 'test_modbus_set_speed_writes_duty_and_enable', 0, 5, 4).
python_function('tests/firmware/test_motor_modbus_handlers.py', 'test_modbus_stop_zeros_duty_and_enable', 0, 5, 4).
python_function('tests/firmware/test_motor_modbus_handlers.py', 'test_modbus_status_maps_registers', 0, 5, 4).
python_function('tests/firmware/test_motor_plugin.py', 'test_motor_plugin_http_stop_uses_global_time_import', 0, 4, 5).
python_function('tests/firmware/test_motor_plugin.py', 'test_motor_plugin_health_rejects_missing_local_serial_port', 1, 4, 6).
python_function('tests/firmware/test_oql_envelope.py', 'test_request_json_roundtrip', 0, 6, 4).
python_function('tests/firmware/test_oql_envelope.py', 'test_request_defaults_do_not_skip_waits', 0, 3, 3).
python_function('tests/firmware/test_oql_envelope.py', 'test_response_json_roundtrip', 0, 5, 3).
python_function('tests/firmware/test_oql_envelope.py', 'test_topics_layout', 0, 6, 2).
python_function('tests/firmware/test_oql_envelope.py', 'test_build_result_payload_is_json_serializable', 0, 2, 4).
python_function('tests/firmware/test_oql_manage_ops.py', 'test_unknown_verb_raises', 0, 1, 2).
python_function('tests/firmware/test_oql_manage_ops.py', 'test_hardware_facade_exposes_manage_ops_handlers', 0, 3, 1).
python_function('tests/firmware/test_oql_manage_ops.py', 'test_diagnostic_command_routes_to_plugin_execute', 1, 3, 3).
python_function('tests/firmware/test_oql_manage_ops.py', 'test_diagnostic_command_requires_peripheral_id', 0, 1, 2).
python_function('tests/firmware/test_oql_manage_ops.py', 'test_tic249_disable_diagnostic_uses_lung_disable', 1, 3, 4).
python_function('tests/firmware/test_oql_manage_ops.py', 'test_modbus_io_valve_diagnostic_uses_set_valve', 1, 6, 4).
python_function('tests/firmware/test_oql_manage_ops.py', 'test_modbus_io_valve_diagnostic_preserves_set_valve_failure', 1, 4, 2).
python_function('tests/firmware/test_oql_manage_ops.py', 'test_pump_off_diagnostic_uses_set_pump', 1, 3, 5).
python_function('tests/firmware/test_oql_manage_ops.py', 'test_move_relative_diagnostic_maps_to_plugin_move', 1, 6, 3).
python_function('tests/firmware/test_oql_manage_ops.py', 'test_diagnostic_command_listed', 0, 2, 1).
python_function('tests/firmware/test_oql_manage_ops.py', 'test_hui_manage_verbs_route_to_hui_handlers', 1, 6, 3).
python_function('tests/firmware/test_oql_manage_ops.py', 'test_hui_manage_verbs_listed', 0, 2, 2).
python_function('tests/firmware/test_oql_mqtt_bridge.py', '_topic_matches', 2, 6, 3).
python_function('tests/firmware/test_oql_mqtt_bridge.py', 'broker', 1, 1, 3).
python_function('tests/firmware/test_oql_mqtt_bridge.py', '_make_pair', 1, 2, 5).
python_function('tests/firmware/test_oql_mqtt_bridge.py', 'test_ping_round_trip', 1, 4, 3).
python_function('tests/firmware/test_oql_mqtt_bridge.py', 'test_command_round_trip_executes_oql', 1, 5, 3).
python_function('tests/firmware/test_oql_mqtt_bridge.py', 'test_manage_usb_list_round_trip', 1, 5, 5).
python_function('tests/firmware/test_oql_mqtt_bridge.py', 'test_concurrent_requests_resolve_their_own_correlation', 1, 4, 6).
python_function('tests/firmware/test_oql_mqtt_bridge.py', 'test_timeout_when_no_agent_replies', 1, 3, 3).
python_function('tests/firmware/test_oql_mqtt_bridge.py', 'test_manage_verb_round_trip', 1, 4, 9).
python_function('tests/firmware/test_oql_mqtt_bridge.py', 'test_manage_unknown_verb_is_ok_false', 1, 3, 8).
python_function('tests/firmware/test_oql_mqtt_bridge.py', 'test_agent_run_oql_handles_execution_errors', 2, 4, 6).
python_function('tests/firmware/test_oql_route_http.py', 'client', 0, 1, 4).
python_function('tests/firmware/test_oql_route_http.py', 'test_execute_returns_503_when_transport_disabled', 1, 3, 3).
python_function('tests/firmware/test_oql_route_http.py', 'test_execute_dispatches_to_controller', 1, 8, 6).
python_function('tests/firmware/test_oql_route_http.py', 'test_execute_accepts_explicit_skip_waits', 1, 3, 4).
python_function('tests/firmware/test_oql_route_http.py', 'test_execute_surfaces_remote_error_as_ok_false', 1, 4, 5).
python_function('tests/firmware/test_oql_route_http.py', 'test_manage_returns_503_when_transport_disabled', 1, 3, 3).
python_function('tests/firmware/test_oql_route_http.py', 'test_manage_dispatches_verb_and_args', 1, 7, 6).
python_function('tests/firmware/test_oql_route_http.py', 'test_manage_surfaces_remote_error', 1, 4, 5).
python_function('tests/firmware/test_oqlos_error.py', 'test_oqlos_error_uses_catalog_defaults_for_known_code', 0, 7, 2).
python_function('tests/firmware/test_oqlos_error.py', 'test_oqlos_error_overrides_and_detail', 0, 4, 2).
python_function('tests/firmware/test_oqlos_error.py', 'test_oqlos_error_tolerates_unknown_code', 0, 5, 2).
python_function('tests/firmware/test_oqlos_error.py', 'test_oqlos_error_fastapi_handler_returns_standard_body', 0, 6, 6).
python_function('tests/firmware/test_oqlos_error.py', 'test_oqlos_error_handler_can_be_installed_on_router_only_test_app', 0, 5, 6).
python_function('tests/firmware/test_oqlos_error.py', 'test_catalog_lookup_still_available_for_known_code', 0, 3, 1).
python_function('tests/firmware/test_oqlos_logging.py', 'test_configure_oqlos_logging_writes_to_file', 2, 3, 7).
python_function('tests/firmware/test_panel_ui.py', 'panel_source', 0, 1, 2).
python_function('tests/firmware/test_panel_ui.py', '_panel_manage_verbs', 1, 1, 2).
python_function('tests/firmware/test_panel_ui.py', '_panel_endpoints', 1, 1, 2).
python_function('tests/firmware/test_panel_ui.py', 'test_panel_route_serves_html', 0, 7, 2).
python_function('tests/firmware/test_panel_ui.py', 'test_panel_exposes_wait_execution_state_in_payload_and_url', 1, 7, 0).
python_function('tests/firmware/test_panel_ui.py', 'test_health_route_contains_redeploy_probe_token', 0, 4, 3).
python_function('tests/firmware/test_panel_ui.py', 'test_panel_manage_verbs_are_supported', 1, 3, 4).
python_function('tests/firmware/test_panel_ui.py', 'test_panel_only_calls_known_endpoints', 1, 5, 1).
python_function('tests/firmware/test_panel_ui.py', 'test_panel_editor_and_results_use_equal_height_split', 1, 8, 1).
python_function('tests/firmware/test_panel_ui.py', 'test_panel_loads_editor_file_scenarios', 1, 7, 0).
python_function('tests/firmware/test_panel_ui.py', 'client_with_controller', 0, 1, 6).
python_function('tests/firmware/test_panel_ui.py', 'test_panel_single_oql_command_payload_dispatches', 1, 4, 2).
python_function('tests/firmware/test_panel_ui.py', 'test_panel_flow_script_payload_dispatches', 1, 4, 1).
python_function('tests/firmware/test_panel_ui.py', 'test_panel_script_without_version_executes_named_goal', 0, 9, 2).
python_function('tests/firmware/test_panel_ui.py', 'test_panel_script_accepts_set_wait_alias', 0, 6, 2).
python_function('tests/firmware/test_panel_ui.py', 'test_panel_manage_payload_dispatches', 1, 4, 1).
python_function('tests/firmware/test_plugin_gateway_env.py', 'test_plugin_gateway_env_overrides_service_urls', 1, 4, 4).
python_function('tests/firmware/test_plugin_gateway_env.py', 'test_plugin_gateway_env_overrides_modbus_params', 1, 2, 4).
python_function('tests/firmware/test_plugin_gateway_env.py', 'test_plugin_gateway_env_overrides_modbus_adc_params', 1, 2, 4).
python_function('tests/firmware/test_plugin_gateway_env.py', 'test_set_pump_uses_registry_instance_that_recovers_after_startup', 1, 4, 8).
python_function('tests/firmware/test_plugin_gateway_env.py', 'test_plugin_gateway_disable_plugins_env', 1, 4, 4).
python_function('tests/firmware/test_plugin_gateway_env.py', 'test_plugin_gateway_allow_list_plugins_env', 1, 4, 4).
python_function('tests/firmware/test_plugin_gateway_env.py', 'test_health_reports_configured_disabled_plugins', 1, 2, 6).
python_function('tests/firmware/test_plugin_gateway_env.py', 'test_health_does_not_poll_configured_disabled_plugins', 1, 4, 8).
python_function('tests/firmware/test_plugin_gateway_init.py', 'test_health_awaits_ensure_initialized_before_checks', 1, 2, 6).
python_function('tests/firmware/test_plugin_gateway_init.py', 'test_initialize_plugins_records_summary', 1, 4, 7).
python_function('tests/firmware/test_plugin_health.py', 'test_piadc_health_rejects_mock_mode', 0, 4, 5).
python_function('tests/firmware/test_plugin_health.py', 'test_piadc_health_includes_uninitialized_service_reason', 0, 6, 6).
python_function('tests/firmware/test_plugin_health.py', 'test_piadc_health_points_non_rpi_hosts_to_remote_service', 1, 7, 8).
python_function('tests/firmware/test_plugin_health.py', 'test_lung_health_rejects_uninitialized_runtime', 0, 4, 5).
python_function('tests/firmware/test_plugin_health.py', 'test_modbus_rtu_health_timeout_does_not_block_event_loop', 0, 4, 7).
python_function('tests/firmware/test_plugin_health.py', 'test_modbus_adc_health_reads_input_registers', 0, 5, 5).
python_function('tests/firmware/test_plugin_health.py', 'test_modbus_adc_read_sensor_uses_channel_conversion', 0, 5, 5).
python_function('tests/firmware/test_plugin_health.py', 'test_modbus_rtu_uses_configured_device_id_for_health_and_writes', 0, 6, 6).
python_function('tests/firmware/test_plugin_health.py', 'test_modbus_rtu_health_infers_mode_from_connected_bus', 0, 6, 6).
python_function('tests/firmware/test_plugin_health.py', 'test_plugin_registry_health_checks_run_concurrently_with_timeout', 1, 4, 7).
python_function('tests/firmware/test_plugin_http_handlers.py', 'test_http_get_command_success', 0, 3, 3).
python_function('tests/firmware/test_plugin_http_handlers.py', 'test_adapter_status_from_health_marks_serial_stale', 0, 3, 1).
python_function('tests/firmware/test_plugin_http_handlers.py', 'test_enrich_adapter_entry_marks_tic249_device_stale', 0, 2, 1).
python_function('tests/firmware/test_plugins_api.py', 'test_execute_plugin_command_returns_operational_failure_payload', 1, 2, 4).
python_function('tests/firmware/test_plugins_health_http.py', 'test_plugin_health_returns_503_when_plugin_reports_error', 1, 4, 6).
python_function('tests/firmware/test_plugins_health_http.py', 'test_plugin_health_returns_503_when_no_active_instance', 1, 3, 5).
python_function('tests/firmware/test_plugins_health_http.py', 'test_plugin_health_returns_200_when_plugin_connected', 1, 2, 4).
python_function('tests/firmware/test_repair_commit.py', '_action', 0, 1, 3).
python_function('tests/firmware/test_repair_commit.py', 'test_config_risk_auto_executable_action_is_eligible', 0, 2, 2).
python_function('tests/firmware/test_repair_commit.py', 'test_physical_risk_action_is_never_eligible_even_if_auto_executable', 0, 2, 2).
python_function('tests/firmware/test_repair_commit.py', 'test_none_risk_action_is_not_eligible', 0, 2, 2).
python_function('tests/firmware/test_repair_commit.py', 'test_config_risk_action_not_marked_auto_executable_is_not_eligible', 0, 2, 2).
python_function('tests/firmware/test_repair_commit.py', 'test_missing_actuation_risk_defaults_to_not_eligible', 0, 2, 2).
python_function('tests/firmware/test_repair_commit.py', 'test_commit_message_format_is_greppable_by_issue_trailer', 0, 3, 2).
python_function('tests/firmware/test_repair_commit.py', 'test_commit_message_includes_co_author_when_given', 0, 2, 1).
python_function('tests/firmware/test_rtc_probe.py', 'test_enrich_rtc_adapter_skips_when_disabled', 1, 3, 3).
python_function('tests/firmware/test_rtc_probe.py', 'test_enrich_rtc_adapter_appends_rtc', 1, 3, 4).
python_function('tests/firmware/test_rtc_probe.py', 'test_enrich_rtc_adapter_idempotent', 0, 2, 1).
python_function('tests/firmware/test_rtc_probe.py', 'test_build_rtc_peripheral_status_reads_sidecar', 1, 7, 4).
python_function('tests/firmware/test_rtc_probe.py', 'test_run_rtc_command_posts_to_sidecar', 1, 5, 4).
python_function('tests/firmware/test_rtc_probe.py', 'test_hardware_rtc_status_endpoint_uses_probe', 1, 3, 3).
python_function('tests/firmware/test_rtc_probe.py', 'test_hardware_rtc_command_endpoint_uses_probe', 1, 4, 4).
python_function('tests/firmware/test_runtime_command_payload.py', 'test_extract_scenario_id_accepts_frontend_and_cli_keys', 0, 4, 1).
python_function('tests/firmware/test_runtime_command_payload.py', 'test_extract_inline_dsl_accepts_content_and_direct_fields', 0, 4, 1).
python_function('tests/firmware/test_scanner_probe.py', 'test_scan_diagnostics_usb_ignores_crw_without_barcode_tokens', 1, 3, 2).
python_function('tests/firmware/test_scanner_probe.py', 'test_holtek_present_from_diagnostics_usb', 1, 3, 2).
python_function('tests/firmware/test_scanner_probe.py', 'test_enrich_scanner_adapter_adds_entry', 1, 5, 3).
python_function('tests/firmware/test_tic249_sidecar_control.py', 'test_ensure_skips_when_already_connected', 1, 3, 2).
python_function('tests/firmware/test_tic249_sidecar_control.py', 'test_ensure_restarts_when_listening_but_not_connected', 1, 4, 5).
python_function('tests/firmware/test_tic249_sidecar_control.py', 'test_ensure_reports_error_when_service_never_listens', 1, 3, 2).
python_function('tests/firmware/test_tic249_units.py', 'test_steps_per_second_to_raw_default_cap', 0, 4, 1).
python_function('tests/firmware/test_tic249_units.py', 'test_raw_acceleration_for_ramp', 0, 2, 1).
python_function('tests/firmware/test_ui_routes_standard.py', 'client', 0, 1, 1).
python_function('tests/firmware/test_ui_routes_standard.py', 'test_legacy_panel_and_navigation_redirect_to_ui', 1, 5, 1).
python_function('tests/firmware/test_ui_routes_standard.py', 'test_ui_panel_and_navigation_serve_html', 1, 5, 1).
python_function('tests/firmware/test_ui_routes_standard.py', 'test_navigation_index_lists_ui_prefixed_pages', 1, 11, 2).
python_function('tests/firmware/test_usb_diagnostics.py', 'test_list_usb_devices_structure_and_no_hang', 0, 7, 4).
python_function('tests/firmware/test_usb_diagnostics.py', 'test_pi_system_diagnostics_has_expected_keys', 0, 5, 2).
python_function('tests/firmware/test_usb_diagnostics.py', 'test_reset_usb_device_not_found_is_clean_failure', 0, 3, 2).
python_function('tests/firmware/test_usb_diagnostics.py', 'test_manage_usb_list', 0, 4, 3).
python_function('tests/firmware/test_usb_diagnostics.py', 'test_manage_pi_diagnostics', 0, 2, 1).
python_function('tests/firmware/test_usb_diagnostics.py', 'test_manage_usb_reset_without_id_fails_cleanly', 0, 2, 1).
python_function('tests/firmware/test_usb_diagnostics.py', 'test_usb_verbs_listed', 0, 2, 2).
python_function('tests/test_cql_cli.py', 'test_cmd_executes_single_command', 1, 8, 7).
python_function('tests/test_cql_cli.py', 'test_cmd_parser_uses_oqlos_api_url_env_by_default', 1, 2, 4).
python_function('tests/test_cql_cli.py', 'test_cmd_execute_aborts_when_hardware_is_unavailable', 2, 3, 6).
python_function('tests/test_cql_cli.py', 'test_file_mode_still_executes_scenario', 2, 3, 7).
python_function('tests/test_cql_cli.py', 'test_run_subcommand_executes_scenario_file', 2, 3, 7).
python_function('tests/test_cql_cli.py', 'test_format_subcommand_prints_canonical_set_syntax', 3, 2, 5).
python_function('tests/test_cql_cli.py', 'test_format_subcommand_write_updates_file', 2, 2, 5).
python_function('tests/test_cql_cli.py', 'test_run_subcommand_fetches_scenario_url', 1, 3, 5).
python_function('tests/test_cql_cli.py', 'test_fetch_scenario_source_rejects_editor_html', 1, 1, 5).
python_function('tests/test_cql_cli.py', 'test_run_subcommand_reports_url_fetch_error', 2, 4, 7).
python_function('tests/test_cql_cli.py', 'test_cmd_execute_mock_mode_error_suggests_dry_run_and_doctor', 2, 4, 6).
python_function('tests/test_cql_cli.py', 'test_cmd_execute_blocks_when_required_adapter_health_is_bad', 2, 4, 5).
python_function('tests/test_cql_cli.py', 'test_oqlctl_doctor_subcommand_dispatches_to_hardware_flags', 1, 6, 3).
python_function('tests/test_cql_cli.py', 'test_oqlctl_status_flag_dispatches_without_file', 1, 2, 5).
python_function('tests/test_cql_cli.py', 'test_result_payload_is_json_safe', 0, 2, 4).
python_function('tests/test_cql_inline_regressions.py', 'test_flat_if_with_variable_threshold_and_goto_skips_rest_of_goal', 0, 5, 3).
python_function('tests/test_cql_inline_regressions.py', 'test_flat_if_else_error_pair_does_not_execute_else_when_condition_passes', 0, 4, 3).
python_function('tests/test_cql_inline_regressions.py', 'test_compound_if_or_expression_is_supported_in_dry_run', 0, 3, 3).
python_function('tests/test_cql_inline_regressions.py', 'test_func_actions_compute_values_for_following_conditions', 0, 4, 4).
python_function('tests/test_cql_scenarios.py', '_collect', 2, 2, 4).
python_function('tests/test_cql_scenarios.py', 'test_cql_db_scenario_dryrun', 1, 3, 4).
python_function('tests/test_cql_scenarios.py', 'test_cql_hw_example_dryrun', 1, 2, 4).
python_function('tests/test_cql_scenarios.py', 'test_cql_invalid_example_rejects_unknown_peripheral', 0, 3, 5).
python_function('tests/test_cql_scenarios.py', 'test_cql_db_scenario_validate', 1, 2, 4).
python_function('tests/test_dsl_schema.py', 'test_default_schema_exposes_cql_and_oql_dialects', 0, 5, 2).
python_function('tests/test_dsl_schema.py', 'test_explicit_object_and_param_maps_override_inferred_fallbacks', 0, 5, 1).
python_function('tests/test_oql_dry_run_regressions.py', 'test_block_if_else_error_attaches_to_else_branch', 0, 4, 1).
python_function('tests/test_oql_dry_run_regressions.py', 'test_comment_only_if_block_does_not_capture_endif', 0, 4, 1).
python_function('tests/test_oql_dry_run_regressions.py', 'test_oql_dry_run_supports_api_assert_shell_and_if_fail', 0, 5, 4).
python_function('tests/test_oql_parser_v3.py', 'test_tokenize_simple', 0, 2, 1).
python_function('tests/test_oql_parser_v3.py', 'test_tokenize_brackets_allow_spaces', 0, 2, 1).
python_function('tests/test_oql_parser_v3.py', 'test_tokenize_double_quoted_string', 0, 2, 1).
python_function('tests/test_oql_parser_v3.py', 'test_tokenize_single_quoted_string', 0, 2, 1).
python_function('tests/test_oql_parser_v3.py', 'test_tokenize_unclosed_quote_raises', 0, 1, 2).
python_function('tests/test_oql_parser_v3.py', 'test_tokenize_unclosed_bracket_raises', 0, 1, 2).
python_function('tests/test_oql_parser_v3.py', 'test_duration_to_ms', 2, 2, 2).
python_function('tests/test_oql_parser_v3.py', 'test_parse_minimal_goal', 0, 6, 3).
python_function('tests/test_oql_parser_v3.py', 'test_parse_metadata', 0, 5, 2).
python_function('tests/test_oql_parser_v3.py', 'test_parse_check_range', 0, 4, 1).
python_function('tests/test_oql_parser_v3.py', 'test_parse_check_negative_values', 0, 2, 1).
python_function('tests/test_oql_parser_v3.py', 'test_parse_sample_with_interval', 0, 4, 1).
python_function('tests/test_oql_parser_v3.py', 'test_parse_if_delta_signed_threshold', 0, 8, 1).
python_function('tests/test_oql_parser_v3.py', 'test_parse_unicode_identifiers', 0, 4, 1).
python_function('tests/test_oql_parser_v3.py', 'test_parse_bracketed_target_with_spaces', 0, 2, 1).
python_function('tests/test_oql_parser_v3.py', 'test_parse_bracketed_block_name', 0, 2, 1).
python_function('tests/test_oql_parser_v3.py', 'test_parse_rejects_unindented_command', 0, 2, 1).
python_function('tests/test_oql_parser_v3.py', 'test_parse_rejects_unknown_command', 0, 2, 2).
python_function('tests/test_oql_parser_v3.py', 'test_parse_v4_goal_requires_set_name', 0, 2, 3).
python_function('tests/test_oql_parser_v3.py', 'test_parse_v4_rejects_inline_goal_name', 0, 2, 3).
python_function('tests/test_oql_parser_v3.py', 'test_parse_v4_goal_name_from_set_name', 0, 3, 2).
python_function('tests/test_oql_parser_v3.py', 'test_parse_rejects_unsupported_oql_version', 0, 2, 2).
python_function('tests/test_oql_parser_v3.py', 'test_base_commands_list_matches_dispatcher', 0, 2, 1).
python_function('tests/test_oql_parser_v3.py', 'test_is_flat_oql_detects_new_syntax', 0, 5, 1).
python_function('tests/test_oql_parser_v3.py', 'test_is_flat_oql_rejects_legacy', 0, 2, 1).
python_function('tests/test_oql_parser_v3.py', 'test_adapter_produces_cql_goals', 0, 4, 2).
python_function('tests/test_oql_parser_v3.py', 'test_adapter_config_prefix', 0, 4, 3).
python_function('tests/test_oql_parser_v3.py', 'test_version4_set_accepts_textual_hardware_values', 0, 3, 2).
python_function('tests/test_oql_parser_v3.py', 'test_version4_repeat_count_expands_indented_block', 0, 3, 2).
python_function('tests/test_oql_parser_v3.py', 'test_macro_call_expansion', 0, 8, 3).
python_function('tests/test_oql_parser_v3.py', 'test_unknown_macro_becomes_error_action', 0, 3, 1).
python_function('tests/test_oql_parser_v3.py', 'test_include_resolves_from_scenarios_root', 0, 3, 2).
python_function('tests/test_oql_parser_v3.py', 'test_include_missing_file_yields_error', 0, 2, 2).
python_function('tests/test_oql_parser_v3.py', 'test_check_with_correct_message', 0, 4, 3).
python_function('tests/test_oql_parser_v3.py', 'test_check_with_error_message', 0, 4, 3).
python_function('tests/test_oql_parser_v3.py', 'test_check_with_both_messages', 0, 4, 3).
python_function('tests/test_oql_parser_v3.py', 'test_correct_without_check_is_error', 0, 2, 3).
python_function('tests/test_oql_parser_v3.py', 'test_adapter_uses_custom_messages', 0, 4, 2).
python_function('tests/test_oql_parser_v3.py', 'test_adapter_if_delta_uses_custom_messages_and_delta_sensor', 0, 8, 2).
python_function('tests/test_oql_scenarios.py', '_collect', 2, 2, 4).
python_function('tests/test_oql_scenarios.py', 'test_oql_scenario_dryrun', 1, 3, 4).
python_function('tests/test_oql_scenarios.py', 'test_oql_example_dryrun', 1, 2, 4).
python_function('tests/test_oql_scenarios.py', 'test_oql_scenario_validate', 1, 2, 4).
python_function('tests/test_reporting.py', 'test_reporting', 0, 3, 6).
python_function('tests/test_scenarios_dir.py', 'test_default_scenarios_dir_points_at_repo_root', 0, 5, 5).
python_function('tests/test_scenarios_legacy_aliases.py', 'test_legacy_alias_map_covers_renamed_exports', 0, 7, 7).
python_function('tests/test_scenarios_legacy_aliases.py', 'test_scenarios_root_has_no_ts_prefix_files', 0, 2, 4).
python_function('tests/test_xml_import_generators.py', 'test_generate_cql_uses_canonical_set_syntax', 0, 6, 7).
python_function('tests/verify_block_if.py', 'test_block_if', 0, 10, 10).
python_function('tests/verify_loops.py', 'test_loops', 0, 3, 8).

% ── Python Classes ───────────────────────────────────────
python_class('oqlos/api/_hw3_models.py', 'DiagnosticCommandRequest').
python_class('oqlos/api/_hw3_models.py', 'MappingReplaceRequest').
python_class('oqlos/api/_hw3_models.py', 'MappingImportRequest').
python_class('oqlos/api/_hw3_models.py', 'MappingExportRequest').
python_class('oqlos/api/_hw3_models.py', 'MappingResetRequest').
python_class('oqlos/api/_hw3_models.py', 'RuntimeFuncResolveRequest').
python_class('oqlos/api/_hw3_models.py', 'CqrsCommandRequest').
python_class('oqlos/api/_hw3_models.py', 'CqrsEventsClearRequest').
python_class('oqlos/api/_hw3_models.py', 'ScannerIngestRequest').
python_class('oqlos/api/editor.py', 'FileInfo').
python_class('oqlos/api/editor.py', 'FileContent').
python_class('oqlos/api/editor.py', 'ExecutionRequest').
python_class('oqlos/api/hardware_mapping_contract.py', 'MappingContractError').
python_method('MappingContractError', '__init__', 1, 1, 3).
python_class('oqlos/api/hardware_mapping_store.py', 'MappingStore').
python_method('MappingStore', '__init__', 1, 2, 5).
python_method('MappingStore', 'file_path', 0, 1, 1).
python_method('MappingStore', 'storage_backend', 0, 1, 0).
python_method('MappingStore', '_load_from_disk', 0, 4, 6).
python_method('MappingStore', 'save', 0, 3, 6).
python_method('MappingStore', 'get', 0, 1, 2).
python_method('MappingStore', 'replace', 1, 2, 3).
python_method('MappingStore', 'reset', 0, 2, 3).
python_method('MappingStore', 'parse_text', 2, 8, 8).
python_method('MappingStore', 'import_text', 2, 1, 2).
python_method('MappingStore', 'export_text', 1, 5, 6).
python_class('oqlos/api/oql_mqtt.py', 'OqlExecuteRequest').
python_class('oqlos/api/oql_mqtt.py', 'OqlManageRequest').
python_class('oqlos/api/oql_mqtt.py', 'OqlExecuteResponse').
python_class('oqlos/config.py', 'Settings').
python_class('oqlos/core/_firmware_executor.py', 'FirmwareExecutor').
python_method('FirmwareExecutor', '__init__', 7, 3, 1).
python_method('FirmwareExecutor', '_get_firmware', 0, 3, 2).
python_method('FirmwareExecutor', '_resolve_gateway_result', 2, 9, 11).
python_method('FirmwareExecutor', '_is_success', 1, 2, 3).
python_method('FirmwareExecutor', 'resolve_peripheral_id', 1, 1, 4).
python_method('FirmwareExecutor', 'normalize_peripheral_value', 2, 6, 4).
python_method('FirmwareExecutor', 'refresh_sensors_from_firmware', 1, 2, 3).
python_method('FirmwareExecutor', 'execute_firmware_action', 2, 3, 2).
python_method('FirmwareExecutor', '_execute_plugin_action', 2, 11, 11).
python_method('FirmwareExecutor', '_execute_legacy_firmware_action', 2, 3, 6).
python_method('FirmwareExecutor', 'exec_set_peripheral', 2, 4, 6).
python_class('oqlos/core/_oql_adapter.py', '_MacroRegistry').
python_method('_MacroRegistry', '__init__', 0, 1, 0).
python_method('_MacroRegistry', 'register', 1, 1, 1).
python_method('_MacroRegistry', 'get', 1, 1, 1).
python_class('oqlos/core/_sensor_evaluator.py', 'SensorEvaluator').
python_method('SensorEvaluator', '__init__', 3, 3, 2).
python_method('SensorEvaluator', 'collect_sensor_constraints', 1, 10, 5).
python_method('SensorEvaluator', 'seed_sensors_from_conditions', 1, 10, 4).
python_method('SensorEvaluator', 'auto_mock_sensor', 3, 8, 2).
python_method('SensorEvaluator', 'compare_sensor', 3, 6, 1).
python_method('SensorEvaluator', 'get_sensor_value', 1, 2, 2).
python_class('oqlos/core/_value_normalizers.py', 'ValueNormalizer').
python_method('ValueNormalizer', '__init__', 1, 1, 0).
python_method('ValueNormalizer', 'coerce_float', 1, 5, 6).
python_method('ValueNormalizer', '_get_pump_flow_full_scale_lpm', 0, 7, 4).
python_method('ValueNormalizer', 'normalize_pump_power', 1, 10, 10).
python_method('ValueNormalizer', 'normalize_valve_value', 1, 7, 8).
python_method('ValueNormalizer', 'normalize_lung_value', 1, 4, 7).
python_method('ValueNormalizer', 'coerce_generic_peripheral_value', 1, 6, 5).
python_class('oqlos/core/base.py', 'StepStatus').
python_class('oqlos/core/base.py', 'StepResult').
python_class('oqlos/core/base.py', 'ScriptResult').
python_method('ScriptResult', 'passed', 0, 3, 1).
python_method('ScriptResult', 'failed', 0, 3, 1).
python_method('ScriptResult', 'summary', 0, 2, 1).
python_class('oqlos/core/base.py', 'VariableStore').
python_method('VariableStore', '__init__', 2, 1, 1).
python_method('VariableStore', 'set', 3, 4, 2).
python_method('VariableStore', 'get', 2, 3, 1).
python_method('VariableStore', 'has', 1, 3, 1).
python_method('VariableStore', 'all', 1, 3, 3).
python_method('VariableStore', 'clear', 0, 1, 1).
python_method('VariableStore', 'interpolate', 1, 1, 4).
python_class('oqlos/core/base.py', 'InterpreterOutput').
python_method('InterpreterOutput', '__init__', 3, 1, 0).
python_method('InterpreterOutput', 'emit', 2, 5, 3).
python_method('InterpreterOutput', '_broadcast_event', 2, 6, 5).
python_method('InterpreterOutput', '_emit_status', 1, 2, 3).
python_method('InterpreterOutput', 'info', 1, 1, 1).
python_method('InterpreterOutput', 'ok', 1, 1, 1).
python_method('InterpreterOutput', 'fail', 1, 1, 1).
python_method('InterpreterOutput', 'warn', 1, 1, 1).
python_method('InterpreterOutput', 'error', 1, 1, 1).
python_method('InterpreterOutput', 'step', 2, 2, 3).
python_method('InterpreterOutput', 'output_yaml', 0, 4, 2).
python_class('oqlos/core/base.py', 'BaseInterpreter').
python_method('BaseInterpreter', '__init__', 4, 1, 3).
python_method('BaseInterpreter', 'parse', 2, 1, 0).
python_method('BaseInterpreter', 'execute', 1, 1, 0).
python_method('BaseInterpreter', 'run', 2, 7, 8).
python_method('BaseInterpreter', 'run_file', 1, 1, 3).
python_method('BaseInterpreter', 'strip_comments', 1, 3, 3).
python_class('oqlos/core/base.py', 'EventBridge').
python_method('EventBridge', '__init__', 1, 1, 0).
python_method('EventBridge', 'connect', 0, 2, 1).
python_method('EventBridge', 'disconnect', 0, 3, 1).
python_method('EventBridge', 'send_event', 2, 4, 7).
python_method('EventBridge', 'connected', 0, 1, 0).
python_class('oqlos/core/cql_parser.py', '_ParseState').
python_method('_ParseState', '__init__', 2, 1, 1).
python_method('_ParseState', 'parse', 0, 2, 2).
python_method('_ParseState', '_peek_next_significant_indent', 0, 4, 4).
python_method('_ParseState', '_flush_pending_inline_if', 0, 5, 1).
python_method('_ParseState', '_attach_pending_inline_if', 2, 8, 2).
python_method('_ParseState', '_get_line_info', 0, 1, 3).
python_method('_ParseState', '_process_line', 0, 8, 7).
python_method('_ParseState', '_try_skip_block', 2, 5, 2).
python_method('_ParseState', '_try_intervals_block', 3, 6, 5).
python_method('_ParseState', '_try_top_level', 3, 2, 1).
python_method('_ParseState', '_handle_scenario', 1, 2, 3).
python_method('_ParseState', '_handle_scenario_attrs', 1, 1, 1).
python_method('_ParseState', '_handle_goal', 3, 3, 4).
python_method('_ParseState', '_handle_goal_attrs', 1, 1, 1).
python_method('_ParseState', '_handle_current_attrs', 4, 3, 1).
python_method('_ParseState', '_handle_step', 1, 2, 4).
python_method('_ParseState', '_init_block_stack', 0, 1, 0).
python_method('_ParseState', '_add_action_to_parent', 1, 7, 1).
python_method('_ParseState', '_append_parent_stack_action', 1, 4, 2).
python_method('_ParseState', '_pop_block_with_warning', 2, 4, 2).
python_method('_ParseState', '_handle_block_control', 1, 7, 4).
python_method('_ParseState', '_handle_else_block', 0, 3, 2).
python_method('_ParseState', '_try_handle_structure_levels', 3, 6, 5).
python_method('_ParseState', '_handle_inline_if_logic', 2, 5, 2).
python_method('_ParseState', '_handle_action_dispatch', 2, 5, 3).
python_method('_ParseState', '_try_hierarchy', 3, 7, 6).
python_class('oqlos/core/executor.py', 'ScenarioOrchestrator').
python_method('ScenarioOrchestrator', '__init__', 2, 2, 1).
python_method('ScenarioOrchestrator', '_sanitize_identifier', 1, 1, 1).
python_method('ScenarioOrchestrator', '_build_eval_context', 0, 5, 2).
python_method('ScenarioOrchestrator', '_sanitize_expression', 1, 3, 3).
python_method('ScenarioOrchestrator', '_build_step_plan', 1, 4, 1).
python_method('ScenarioOrchestrator', '_execute_goal_steps', 7, 6, 5).
python_method('ScenarioOrchestrator', 'execute_scenario', 4, 10, 11).
python_method('ScenarioOrchestrator', 'execute_step', 3, 10, 9).
python_method('ScenarioOrchestrator', '_execute_lung_step', 2, 5, 4).
python_method('ScenarioOrchestrator', '_execute_valve_step', 2, 6, 3).
python_method('ScenarioOrchestrator', '_execute_pump_step', 3, 6, 6).
python_method('ScenarioOrchestrator', '_execute_wait_step', 2, 2, 1).
python_method('ScenarioOrchestrator', '_execute_sensor_read_step', 1, 4, 2).
python_method('ScenarioOrchestrator', '_execute_validate_step', 1, 7, 5).
python_method('ScenarioOrchestrator', 'update_dependent_sensors', 1, 11, 5).
python_method('ScenarioOrchestrator', 'validate_goal', 1, 5, 2).
python_method('ScenarioOrchestrator', 'log_event', 2, 1, 3).
python_class('oqlos/core/interpreter.py', 'CqlInterpreter').
python_method('CqlInterpreter', '__init__', 11, 1, 5).
python_method('CqlInterpreter', 'sensor_values', 0, 1, 0).
python_method('CqlInterpreter', 'sensor_values', 1, 1, 0).
python_method('CqlInterpreter', '_firmware', 0, 1, 0).
python_method('CqlInterpreter', '_firmware', 1, 1, 0).
python_method('CqlInterpreter', '_firmware_url', 0, 1, 0).
python_method('CqlInterpreter', '_firmware_url', 1, 1, 0).
python_method('CqlInterpreter', '_coerce_float', 1, 1, 1).
python_method('CqlInterpreter', '_resolve_peripheral_id', 1, 1, 1).
python_method('CqlInterpreter', '_get_pump_flow_full_scale_lpm', 0, 1, 1).
python_method('CqlInterpreter', '_normalize_pump_power', 1, 1, 1).
python_method('CqlInterpreter', '_normalize_valve_value', 1, 1, 1).
python_method('CqlInterpreter', '_normalize_lung_value', 1, 1, 1).
python_method('CqlInterpreter', 'parse', 2, 3, 5).
python_method('CqlInterpreter', '_print_header', 2, 3, 2).
python_method('CqlInterpreter', '_collect_warnings', 2, 3, 2).
python_method('CqlInterpreter', '_planned_step_results', 1, 3, 2).
python_method('CqlInterpreter', '_run_validation_mode', 4, 1, 5).
python_method('CqlInterpreter', '_collect_all_goals', 1, 4, 1).
python_method('CqlInterpreter', '_execute_single_goal', 2, 4, 4).
python_method('CqlInterpreter', '_execute_all_goals', 1, 2, 1).
python_method('CqlInterpreter', '_build_script_result', 2, 2, 5).
python_method('CqlInterpreter', 'execute', 1, 4, 9).
python_method('CqlInterpreter', '_execute_step', 2, 5, 5).
python_method('CqlInterpreter', '_execute_action', 1, 4, 4).
python_method('CqlInterpreter', '_exec_flat_action', 1, 6, 6).
python_method('CqlInterpreter', '_do_sleep', 2, 1, 1).
python_method('CqlInterpreter', '_normalize_peripheral_value', 2, 1, 1).
python_method('CqlInterpreter', '_coerce_generic_peripheral_value', 1, 1, 1).
python_method('CqlInterpreter', '_exec_set_peripheral', 2, 4, 6).
python_method('CqlInterpreter', '_get_firmware', 0, 1, 1).
python_method('CqlInterpreter', '_execute_firmware_action', 2, 1, 1).
python_method('CqlInterpreter', '_execute_plugin_action', 2, 1, 1).
python_method('CqlInterpreter', '_execute_legacy_firmware_action', 2, 1, 1).
python_method('CqlInterpreter', '_refresh_sensors_from_firmware', 0, 1, 1).
python_method('CqlInterpreter', '_auto_mock_sensor', 3, 1, 1).
python_method('CqlInterpreter', '_compare_sensor', 3, 1, 1).
python_method('CqlInterpreter', '_resolve_sensor_value', 1, 7, 5).
python_method('CqlInterpreter', '_resolve_delta_sensor_value', 1, 6, 5).
python_method('CqlInterpreter', '_resolve_windowed_delta_sensor_value', 2, 11, 8).
python_method('CqlInterpreter', '_extract_window_seconds', 1, 5, 5).
python_method('CqlInterpreter', '_resolve_condition_rhs', 3, 8, 9).
python_method('CqlInterpreter', '_evaluate_resolved_condition', 0, 7, 7).
python_method('CqlInterpreter', '_eval_condition_clause', 2, 11, 9).
python_method('CqlInterpreter', '_evaluate_inline_condition_expression', 1, 4, 3).
python_method('CqlInterpreter', '_tokenize_condition_expression', 1, 4, 3).
python_method('CqlInterpreter', '_aggregate_condition_results', 2, 4, 4).
python_method('CqlInterpreter', '_apply_connector', 3, 5, 0).
python_method('CqlInterpreter', '_finalize_condition_result', 4, 3, 3).
python_method('CqlInterpreter', '_evaluate_range_condition', 2, 7, 5).
python_method('CqlInterpreter', '_evaluate_condition', 1, 11, 7).
python_class('oqlos/core/motor2_runtime.py', 'Motor2RuntimeConfig').
python_class('oqlos/core/motor2_runtime.py', 'Motor2ReciprocatingPlan').
python_method('Motor2ReciprocatingPlan', 'speed_was_clamped', 0, 1, 0).
python_class('oqlos/core/oql_parser.py', 'OqlCmd').
python_method('OqlCmd', '__repr__', 0, 3, 2).
python_class('oqlos/core/oql_parser.py', 'OqlBlock').
python_class('oqlos/core/oql_parser.py', 'OqlDoc').
python_method('OqlDoc', 'goals', 0, 3, 0).
python_method('OqlDoc', 'configs', 0, 3, 0).
python_method('OqlDoc', 'macros', 0, 3, 0).
python_method('OqlDoc', 'funcs', 0, 3, 0).
python_class('oqlos/core/oql_versioning.py', 'OqlVersionInfo').
python_method('OqlVersionInfo', 'is_current', 0, 1, 0).
python_class('oqlos/core/safe_eval.py', 'SafeEvalError').
python_class('oqlos/core/state.py', 'StateManager').
python_method('StateManager', '__init__', 0, 1, 1).
python_method('StateManager', 'initialize_peripherals', 0, 3, 3).
python_method('StateManager', 'broadcast_event', 1, 4, 3).
python_class('oqlos/dsl/schema.py', 'DslDialect').
python_class('oqlos/dsl/schema.py', 'DslItem').
python_class('oqlos/dsl/schema.py', 'DslFunctionBinding').
python_class('oqlos/dsl/schema.py', 'DslParamUnitBinding').
python_class('oqlos/dsl/schema.py', 'DslSchema').
python_class('oqlos/errors/catalog.py', 'RepairTemplate').
python_class('oqlos/errors/catalog.py', 'IssueDefinition').
python_class('oqlos/errors/catalog.py', 'CodePattern').
python_method('CodePattern', 'matches', 1, 3, 3).
python_class('oqlos/errors/exceptions.py', 'OqlosError').
python_method('OqlosError', '__init__', 1, 8, 3).
python_method('OqlosError', 'to_issue', 0, 3, 0).
python_class('oqlos/hardware/client/config.py', 'OqlosHardwareProxyConfig').
python_method('OqlosHardwareProxyConfig', '__post_init__', 0, 3, 2).
python_method('OqlosHardwareProxyConfig', 'from_env', 2, 5, 3).
python_class('oqlos/hardware/client/errors.py', 'HardwareProxyError').
python_method('HardwareProxyError', '__init__', 2, 1, 3).
python_class('oqlos/hardware/client/proxy.py', 'OqlosHardwareProxy').
python_method('OqlosHardwareProxy', '__init__', 1, 2, 1).
python_method('OqlosHardwareProxy', 'candidate_bases', 0, 1, 1).
python_method('OqlosHardwareProxy', 'proxy_info', 0, 1, 1).
python_method('OqlosHardwareProxy', 'close', 0, 3, 2).
python_method('OqlosHardwareProxy', '_get_client', 0, 3, 4).
python_method('OqlosHardwareProxy', '_proxy_oqlos', 1, 1, 1).
python_method('OqlosHardwareProxy', '_proxy_oqlos_request', 2, 13, 16).
python_method('OqlosHardwareProxy', '_degraded_oqlos_payload', 1, 5, 5).
python_method('OqlosHardwareProxy', 'health', 0, 4, 4).
python_method('OqlosHardwareProxy', 'identify', 0, 3, 4).
python_method('OqlosHardwareProxy', 'peripheral_status', 1, 6, 6).
python_method('OqlosHardwareProxy', 'diagnostic_command', 3, 9, 8).
python_method('OqlosHardwareProxy', '_motor_api_bases', 0, 4, 2).
python_method('OqlosHardwareProxy', '_fetch_dri0050_motor_health_hint', 0, 8, 8).
python_method('OqlosHardwareProxy', '_is_useless_motor_health_hint', 1, 2, 3).
python_method('OqlosHardwareProxy', '_should_enrich_motor_dri0050_failure', 1, 7, 4).
python_method('OqlosHardwareProxy', '_motor_dri0050_remediation', 2, 4, 1).
python_method('OqlosHardwareProxy', '_enrich_motor_dri0050_failure', 1, 8, 9).
python_method('OqlosHardwareProxy', '_load_peripheral_status', 1, 5, 5).
python_method('OqlosHardwareProxy', '_load_modbus_io_status', 1, 5, 6).
python_method('OqlosHardwareProxy', '_load_adc_status', 0, 1, 3).
python_method('OqlosHardwareProxy', '_load_simple_hardware_status', 1, 2, 3).
python_method('OqlosHardwareProxy', '_load_plugin_status', 2, 6, 4).
python_method('OqlosHardwareProxy', '_execute_diagnostic_command', 5, 11, 5).
python_method('OqlosHardwareProxy', '_unavailable_health_payload', 2, 1, 2).
python_method('OqlosHardwareProxy', '_unavailable_identify_payload', 1, 2, 2).
python_method('OqlosHardwareProxy', '_unavailable_peripheral_payload', 3, 1, 1).
python_method('OqlosHardwareProxy', '_unavailable_command_payload', 6, 2, 1).
python_class('oqlos/hardware/config_schema.py', 'UnitType').
python_class('oqlos/hardware/control_proxy.py', 'OqlosHardwareProxy').
python_method('OqlosHardwareProxy', '__init__', 1, 1, 2).
python_class('oqlos/hardware/diagnosis_types.py', 'DiagnosisAction').
python_class('oqlos/hardware/diagnosis_types.py', 'DeviceDiagnosis').
python_class('oqlos/hardware/diagnosis_types.py', 'DiagnosisReport').
python_class('oqlos/hardware/drivers/gpio.py', 'GpioDriver').
python_method('GpioDriver', '__init__', 0, 1, 0).
python_method('GpioDriver', 'connect', 1, 1, 2).
python_method('GpioDriver', 'read', 1, 3, 5).
python_method('GpioDriver', 'write', 2, 6, 6).
python_method('GpioDriver', 'discover', 0, 2, 1).
python_method('GpioDriver', 'health_check', 0, 2, 0).
python_method('GpioDriver', 'disconnect', 0, 1, 2).
python_class('oqlos/hardware/drivers/mqtt.py', 'MqttDriver').
python_method('MqttDriver', '__init__', 0, 1, 1).
python_method('MqttDriver', 'connect', 1, 3, 6).
python_method('MqttDriver', '_on_connect', 4, 2, 2).
python_method('MqttDriver', '_on_message', 3, 2, 3).
python_method('MqttDriver', 'read', 1, 2, 3).
python_method('MqttDriver', 'write', 2, 3, 6).
python_method('MqttDriver', 'discover', 0, 1, 0).
python_method('MqttDriver', 'health_check', 0, 3, 1).
python_method('MqttDriver', 'disconnect', 0, 1, 2).
python_class('oqlos/hardware/drivers/spi.py', 'SpiDriver').
python_method('SpiDriver', '__init__', 0, 1, 0).
python_method('SpiDriver', 'connect', 1, 3, 5).
python_method('SpiDriver', 'read', 1, 2, 2).
python_method('SpiDriver', 'write', 2, 4, 3).
python_method('SpiDriver', 'discover', 0, 1, 0).
python_method('SpiDriver', 'health_check', 0, 3, 0).
python_method('SpiDriver', 'disconnect', 0, 2, 1).
python_class('oqlos/hardware/firmware_adapter.py', 'FirmwareAdapter').
python_method('FirmwareAdapter', '__init__', 3, 1, 2).
python_method('FirmwareAdapter', '_get_client', 0, 3, 2).
python_method('FirmwareAdapter', 'close', 0, 2, 1).
python_method('FirmwareAdapter', '_get_lung_motor_url', 0, 3, 4).
python_method('FirmwareAdapter', 'is_available', 0, 2, 2).
python_method('FirmwareAdapter', '_resolve_peripheral', 1, 1, 3).
python_method('FirmwareAdapter', '_raise_if_rejected', 2, 3, 3).
python_method('FirmwareAdapter', 'set_peripheral', 2, 12, 20).
python_method('FirmwareAdapter', 'pump_off', 1, 1, 1).
python_method('FirmwareAdapter', 'pump_set', 2, 1, 1).
python_method('FirmwareAdapter', 'valve_open', 1, 1, 1).
python_method('FirmwareAdapter', 'valve_close', 1, 1, 1).
python_method('FirmwareAdapter', 'reset_peripherals', 0, 1, 4).
python_method('FirmwareAdapter', 'read_state', 0, 1, 4).
python_method('FirmwareAdapter', 'read_sensor', 1, 4, 8).
python_method('FirmwareAdapter', 'read_all_sensors', 0, 3, 6).
python_method('FirmwareAdapter', '_resolve_dispatch_target', 3, 4, 4).
python_method('FirmwareAdapter', '_handle_lung_action', 4, 3, 4).
python_method('FirmwareAdapter', '_handle_valve_action', 4, 3, 2).
python_method('FirmwareAdapter', '_handle_pump_action', 4, 3, 4).
python_method('FirmwareAdapter', '_handle_common_action', 3, 3, 1).
python_method('FirmwareAdapter', '_execute_method', 4, 8, 10).
python_method('FirmwareAdapter', 'dispatch_action', 3, 3, 3).
python_class('oqlos/hardware/gateway.py', '_PiAdcAdapter').
python_method('_PiAdcAdapter', '__init__', 1, 3, 1).
python_method('_PiAdcAdapter', 'read_channel', 1, 1, 1).
python_method('_PiAdcAdapter', 'read_sensor', 1, 3, 3).
python_class('oqlos/hardware/gateway.py', '_DRI0050MotorAdapter').
python_method('_DRI0050MotorAdapter', '__init__', 1, 3, 1).
python_method('_DRI0050MotorAdapter', 'set_speed', 1, 2, 2).
python_method('_DRI0050MotorAdapter', '_stop', 0, 1, 1).
python_method('_DRI0050MotorAdapter', 'status', 0, 1, 1).
python_class('oqlos/hardware/gateway.py', '_Tic249LungAdapter').
python_method('_Tic249LungAdapter', '__init__', 1, 3, 1).
python_method('_Tic249LungAdapter', 'reciprocate', 4, 1, 1).
python_method('_Tic249LungAdapter', 'stop', 0, 1, 1).
python_method('_Tic249LungAdapter', 'move', 2, 2, 1).
python_method('_Tic249LungAdapter', 'energize', 1, 1, 1).
python_method('_Tic249LungAdapter', 'status', 0, 1, 1).
python_class('oqlos/hardware/gateway.py', '_ModbusAdapter').
python_method('_ModbusAdapter', '__init__', 5, 3, 9).
python_method('_ModbusAdapter', 'set_coil', 2, 3, 3).
python_method('_ModbusAdapter', '_set_coil_rtu', 3, 7, 8).
python_method('_ModbusAdapter', '_set_coil_tcp', 2, 2, 5).
python_method('_ModbusAdapter', 'set_valve', 2, 3, 3).
python_class('oqlos/hardware/gateway.py', 'HardwareGateway').
python_method('HardwareGateway', '__init__', 1, 3, 5).
python_method('HardwareGateway', 'is_real', 0, 1, 0).
python_method('HardwareGateway', 'set_valve', 2, 3, 3).
python_method('HardwareGateway', 'set_pump', 1, 3, 3).
python_method('HardwareGateway', 'read_sensor', 1, 3, 3).
python_method('HardwareGateway', 'set_lung', 4, 3, 3).
python_method('HardwareGateway', 'stop_lung', 0, 3, 3).
python_method('HardwareGateway', 'health', 0, 3, 4).
python_class('oqlos/hardware/plugin_gateway.py', 'PluginHardwareGateway').
python_method('PluginHardwareGateway', '__init__', 2, 3, 5).
python_method('PluginHardwareGateway', '_load_hardware_schema', 1, 3, 7).
python_method('PluginHardwareGateway', '_parse_plugin_configs', 1, 2, 4).
python_method('PluginHardwareGateway', '_apply_env_overrides', 0, 6, 9).
python_method('PluginHardwareGateway', '_apply_plugin_enable_env_overrides', 0, 14, 8).
python_method('PluginHardwareGateway', '_apply_shared_modbus_bus_env_overrides', 0, 13, 6).
python_method('PluginHardwareGateway', '_apply_modbus_env_overrides', 2, 8, 6).
python_method('PluginHardwareGateway', 'modbus_preflight_report', 0, 4, 4).
python_method('PluginHardwareGateway', '_log_modbus_preflight', 0, 3, 4).
python_method('PluginHardwareGateway', 'ensure_initialized', 0, 3, 2).
python_method('PluginHardwareGateway', '_get_or_connect_plugin', 1, 10, 9).
python_method('PluginHardwareGateway', '_initialize_plugins', 0, 12, 11).
python_method('PluginHardwareGateway', 'is_real', 0, 1, 0).
python_method('PluginHardwareGateway', 'set_valve', 2, 4, 5).
python_method('PluginHardwareGateway', 'set_pump', 1, 4, 5).
python_method('PluginHardwareGateway', 'read_sensor', 1, 5, 5).
python_method('PluginHardwareGateway', 'set_lung_result', 4, 5, 7).
python_method('PluginHardwareGateway', 'set_lung', 4, 1, 3).
python_method('PluginHardwareGateway', '_execute_lung_bool_command', 2, 4, 5).
python_method('PluginHardwareGateway', 'stop_lung', 0, 1, 1).
python_method('PluginHardwareGateway', 'disable_lung', 0, 1, 1).
python_method('PluginHardwareGateway', 'reload_configs', 1, 5, 9).
python_method('PluginHardwareGateway', 'health', 0, 12, 7).
python_class('oqlos/hardware/plugins/base.py', 'PluginStatus').
python_class('oqlos/hardware/plugins/base.py', 'HardwareDriverSpec').
python_method('HardwareDriverSpec', 'set_peripheral', 3, 1, 0).
python_method('HardwareDriverSpec', 'read_sensor', 1, 1, 0).
python_method('HardwareDriverSpec', 'get_driver_status', 0, 1, 0).
python_class('oqlos/hardware/plugins/base.py', 'ScaleConfig').
python_method('ScaleConfig', 'contains', 1, 1, 0).
python_method('ScaleConfig', 'clamp', 1, 1, 2).
python_class('oqlos/hardware/plugins/base.py', 'ConversionConfig').
python_class('oqlos/hardware/plugins/base.py', 'PeripheralConfig').
python_method('PeripheralConfig', 'validate_value', 1, 4, 1).
python_method('PeripheralConfig', 'convert_value', 1, 4, 3).
python_class('oqlos/hardware/plugins/base.py', 'PluginConfig').
python_method('PluginConfig', 'validate', 0, 4, 1).
python_method('PluginConfig', 'get_peripheral', 1, 1, 1).
python_class('oqlos/hardware/plugins/base.py', 'OqlosConfigDocument').
python_method('OqlosConfigDocument', '_inject_plugin_ids', 2, 5, 3).
python_class('oqlos/hardware/plugins/base.py', 'PluginHealth').
python_class('oqlos/hardware/plugins/base.py', 'HardwarePlugin').
python_method('HardwarePlugin', '__init__', 1, 1, 1).
python_method('HardwarePlugin', 'connect', 0, 1, 0).
python_method('HardwarePlugin', 'disconnect', 0, 1, 0).
python_method('HardwarePlugin', 'health_check', 0, 1, 0).
python_method('HardwarePlugin', 'validate_config', 0, 1, 0).
python_method('HardwarePlugin', 'execute_command', 2, 1, 0).
python_method('HardwarePlugin', 'get_capabilities', 1, 1, 0).
python_method('HardwarePlugin', 'status', 0, 1, 0).
python_method('HardwarePlugin', 'is_connected', 0, 1, 0).
python_method('HardwarePlugin', '__repr__', 0, 1, 0).
python_class('oqlos/hardware/plugins/lung.py', 'LungPlugin').
python_method('LungPlugin', '__init__', 1, 1, 4).
python_method('LungPlugin', 'validate_config', 0, 5, 3).
python_method('LungPlugin', 'connect', 0, 5, 4).
python_method('LungPlugin', 'disconnect', 0, 1, 1).
python_method('LungPlugin', '_health_check_http', 0, 11, 7).
python_method('LungPlugin', 'health_check', 0, 5, 4).
python_method('LungPlugin', '_runtime_status', 0, 6, 3).
python_method('LungPlugin', '_runtime_block_reason', 1, 7, 2).
python_method('LungPlugin', '_handle_reciprocate_http', 1, 4, 4).
python_method('LungPlugin', '_handle_reciprocate_usb', 1, 1, 1).
python_method('LungPlugin', '_handle_stop_http', 0, 1, 1).
python_method('LungPlugin', '_handle_stop_usb', 0, 1, 0).
python_method('LungPlugin', '_handle_move_http', 1, 2, 2).
python_method('LungPlugin', '_handle_move_usb', 1, 1, 1).
python_method('LungPlugin', '_handle_energize_http', 1, 1, 2).
python_method('LungPlugin', '_handle_energize_usb', 1, 1, 1).
python_method('LungPlugin', '_handle_status_http', 0, 1, 1).
python_method('LungPlugin', '_handle_status_usb', 0, 1, 0).
python_method('LungPlugin', 'execute_command', 2, 14, 11).
python_method('LungPlugin', 'get_capabilities', 1, 1, 3).
python_class('oqlos/hardware/plugins/modbus.py', 'ModbusPlugin').
python_method('ModbusPlugin', '__init__', 1, 1, 2).
python_method('ModbusPlugin', '_validate_rtu_params', 1, 7, 3).
python_method('ModbusPlugin', '_validate_tcp_params', 1, 7, 3).
python_method('ModbusPlugin', 'validate_config', 0, 3, 3).
python_method('ModbusPlugin', 'connect', 0, 7, 7).
python_method('ModbusPlugin', 'disconnect', 0, 5, 2).
python_method('ModbusPlugin', '_health_check_rtu', 0, 4, 5).
python_method('ModbusPlugin', '_health_check_tcp', 0, 2, 4).
python_method('ModbusPlugin', 'health_check', 0, 11, 7).
python_method('ModbusPlugin', '_execute_set_coil', 1, 8, 9).
python_method('ModbusPlugin', '_execute_set_valve', 1, 3, 2).
python_method('ModbusPlugin', 'execute_command', 2, 6, 3).
python_method('ModbusPlugin', '_rtu_timeout', 0, 1, 1).
python_method('ModbusPlugin', '_rtu_call', 1, 2, 5).
python_method('ModbusPlugin', '_device_id', 0, 1, 1).
python_method('ModbusPlugin', 'get_capabilities', 1, 1, 3).
python_class('oqlos/hardware/plugins/modbus_adc.py', 'ModbusAdcPlugin').
python_method('ModbusAdcPlugin', '__init__', 1, 1, 2).
python_method('ModbusAdcPlugin', 'validate_config', 0, 12, 4).
python_method('ModbusAdcPlugin', 'connect', 0, 4, 6).
python_method('ModbusAdcPlugin', 'disconnect', 0, 3, 2).
python_method('ModbusAdcPlugin', 'health_check', 0, 8, 11).
python_method('ModbusAdcPlugin', 'execute_command', 2, 10, 8).
python_method('ModbusAdcPlugin', '_read_registers', 0, 6, 11).
python_method('ModbusAdcPlugin', '_format_channels', 1, 2, 2).
python_method('ModbusAdcPlugin', '_format_channel', 2, 3, 4).
python_method('ModbusAdcPlugin', '_peripheral_for_channel', 1, 3, 1).
python_method('ModbusAdcPlugin', '_rtu_timeout', 0, 1, 1).
python_method('ModbusAdcPlugin', '_device_id', 0, 1, 1).
python_method('ModbusAdcPlugin', '_config_int', 3, 2, 3).
python_method('ModbusAdcPlugin', '_read_address', 0, 1, 1).
python_method('ModbusAdcPlugin', '_read_count', 0, 1, 1).
python_method('ModbusAdcPlugin', 'get_capabilities', 1, 2, 5).
python_class('oqlos/hardware/plugins/motor.py', 'MotorPlugin').
python_method('MotorPlugin', '__init__', 1, 1, 6).
python_method('MotorPlugin', 'validate_config', 0, 10, 3).
python_method('MotorPlugin', 'connect', 0, 7, 8).
python_method('MotorPlugin', 'disconnect', 0, 2, 1).
python_method('MotorPlugin', '_health_check_http', 0, 6, 7).
python_method('MotorPlugin', '_health_check_modbus_rtu', 0, 1, 1).
python_method('MotorPlugin', 'health_check', 0, 6, 5).
python_method('MotorPlugin', '_base_url_is_local', 0, 2, 2).
python_method('MotorPlugin', '_validate_power_pct', 1, 3, 1).
python_method('MotorPlugin', '_handle_set_speed_http', 2, 2, 3).
python_method('MotorPlugin', '_handle_set_speed_cli', 2, 1, 2).
python_method('MotorPlugin', '_handle_set_speed_modbus', 2, 1, 1).
python_method('MotorPlugin', '_handle_stop_http', 1, 1, 2).
python_method('MotorPlugin', '_handle_stop_cli', 1, 1, 1).
python_method('MotorPlugin', '_handle_stop_modbus', 1, 1, 1).
python_method('MotorPlugin', '_handle_status_http', 1, 1, 2).
python_method('MotorPlugin', '_handle_status_cli', 1, 1, 2).
python_method('MotorPlugin', '_handle_status_modbus', 1, 1, 1).
python_method('MotorPlugin', 'execute_command', 2, 14, 13).
python_method('MotorPlugin', 'get_capabilities', 1, 1, 3).
python_class('oqlos/hardware/plugins/piadc.py', 'PiadcPlugin').
python_method('PiadcPlugin', '__init__', 1, 1, 4).
python_method('PiadcPlugin', 'validate_config', 0, 4, 3).
python_method('PiadcPlugin', 'connect', 0, 3, 4).
python_method('PiadcPlugin', 'disconnect', 0, 1, 1).
python_method('PiadcPlugin', 'health_check', 0, 8, 7).
python_method('PiadcPlugin', '_read_blocker', 0, 7, 3).
python_method('PiadcPlugin', 'execute_command', 2, 11, 6).
python_method('PiadcPlugin', 'get_capabilities', 1, 1, 3).
python_class('oqlos/hardware/plugins/registry.py', 'PluginRegistry').
python_method('PluginRegistry', 'register', 2, 2, 2).
python_method('PluginRegistry', 'unregister', 2, 3, 1).
python_method('PluginRegistry', 'get_plugin_class', 2, 1, 1).
python_method('PluginRegistry', 'list_plugins', 1, 2, 1).
python_method('PluginRegistry', 'create_instance', 3, 4, 8).
python_method('PluginRegistry', 'get_instance', 2, 1, 1).
python_method('PluginRegistry', 'connect_plugin', 3, 3, 3).
python_method('PluginRegistry', 'disconnect_plugin', 2, 3, 4).
python_method('PluginRegistry', 'health_check', 2, 5, 5).
python_method('PluginRegistry', 'health_check_all', 1, 4, 3).
python_method('PluginRegistry', 'validate_all_configurations', 2, 5, 5).
python_method('PluginRegistry', 'get_status', 1, 2, 2).
python_method('PluginRegistry', 'discover_entry_point_plugins', 2, 6, 10).
python_method('PluginRegistry', 'load_configs_from_yaml', 2, 4, 9).
python_class('oqlos/hardware/protocol.py', 'ProtocolType').
python_class('oqlos/hardware/protocol.py', 'HardwareProtocol').
python_method('HardwareProtocol', 'connect', 1, 1, 0).
python_method('HardwareProtocol', 'read', 1, 1, 0).
python_method('HardwareProtocol', 'write', 2, 1, 0).
python_method('HardwareProtocol', 'discover', 0, 1, 0).
python_method('HardwareProtocol', 'health_check', 0, 1, 0).
python_method('HardwareProtocol', 'disconnect', 0, 1, 0).
python_class('oqlos/hardware/registry.py', 'DriverRegistry').
python_method('DriverRegistry', 'register', 2, 1, 0).
python_method('DriverRegistry', 'create', 2, 2, 3).
python_method('DriverRegistry', 'list_registered', 1, 1, 2).
python_class('oqlos/hardware/transport/mqtt_oql_bridge.py', 'Topics').
python_method('Topics', 'request', 0, 1, 0).
python_method('Topics', 'response_base', 0, 1, 0).
python_method('Topics', 'response_wildcard', 0, 1, 0).
python_method('Topics', 'events', 0, 1, 0).
python_method('Topics', 'status', 0, 1, 0).
python_method('Topics', 'response_for', 1, 1, 0).
python_class('oqlos/hardware/transport/mqtt_oql_bridge.py', '_JsonEnvelopeMixin').
python_method('_JsonEnvelopeMixin', 'to_json', 0, 1, 2).
python_class('oqlos/hardware/transport/mqtt_oql_bridge.py', 'OqlRequest').
python_method('OqlRequest', 'from_json', 2, 1, 6).
python_class('oqlos/hardware/transport/mqtt_oql_bridge.py', 'OqlResponse').
python_method('OqlResponse', 'from_json', 2, 1, 5).
python_class('oqlos/hardware/transport/mqtt_oql_bridge.py', '_PahoAsyncClient').
python_method('_PahoAsyncClient', '__init__', 0, 1, 5).
python_method('_PahoAsyncClient', 'start', 0, 1, 7).
python_method('_PahoAsyncClient', 'stop', 0, 2, 4).
python_method('_PahoAsyncClient', '_subscriptions', 0, 1, 0).
python_method('_PahoAsyncClient', '_last_will', 0, 1, 0).
python_method('_PahoAsyncClient', '_on_payload', 2, 4, 0).
python_method('_PahoAsyncClient', '_handle_connect', 0, 3, 5).
python_method('_PahoAsyncClient', '_handle_message', 3, 2, 1).
python_method('_PahoAsyncClient', '_publish', 2, 1, 1).
python_class('oqlos/hardware/transport/mqtt_oql_bridge.py', 'OqlMqttController').
python_method('OqlMqttController', '__init__', 0, 1, 2).
python_method('OqlMqttController', '_subscriptions', 0, 1, 0).
python_method('OqlMqttController', '_on_payload', 2, 4, 3).
python_method('OqlMqttController', '_resolve_response', 1, 4, 5).
python_method('OqlMqttController', '_fan_out_event', 1, 4, 3).
python_method('OqlMqttController', 'execute', 1, 4, 11).
python_method('OqlMqttController', 'manage', 2, 1, 1).
python_method('OqlMqttController', 'subscribe_events', 1, 1, 2).
python_method('OqlMqttController', 'unsubscribe_events', 1, 2, 1).
python_class('oqlos/hardware/transport/mqtt_oql_bridge.py', 'OqlMqttAgent').
python_method('OqlMqttAgent', '__init__', 0, 1, 3).
python_method('OqlMqttAgent', '_subscriptions', 0, 1, 0).
python_method('OqlMqttAgent', '_last_will', 0, 1, 1).
python_method('OqlMqttAgent', 'start', 0, 1, 4).
python_method('OqlMqttAgent', 'stop', 0, 2, 4).
python_method('OqlMqttAgent', '_on_payload', 2, 4, 4).
python_method('OqlMqttAgent', '_handle_request', 1, 5, 10).
python_method('OqlMqttAgent', '_run_manage', 1, 3, 7).
python_method('OqlMqttAgent', '_run_oql', 1, 5, 9).
python_class('oqlos/models/dsl_models.py', 'CqlMetadata').
python_class('oqlos/models/dsl_models.py', 'CqlInterval').
python_class('oqlos/models/dsl_models.py', 'CqlCondition').
python_class('oqlos/models/dsl_models.py', 'CqlAction').
python_class('oqlos/models/dsl_models.py', 'CqlStep').
python_class('oqlos/models/dsl_models.py', 'CqlGoal').
python_class('oqlos/models/dsl_models.py', 'CqlScenario').
python_class('oqlos/models/dsl_models.py', 'CqlDocument').
python_class('oqlos/models/execution.py', 'ExecutionRequest').
python_class('oqlos/models/execution.py', 'ExecutionStatus').
python_class('oqlos/models/execution.py', 'CommandEnvelope').
python_class('oqlos/models/peripheral.py', 'PeripheralType').
python_class('oqlos/models/peripheral.py', 'PeripheralStatus').
python_class('oqlos/models/peripheral.py', 'PeripheralMode').
python_class('oqlos/models/peripheral.py', 'Peripheral').
python_class('oqlos/models/scenario.py', 'Step').
python_class('oqlos/models/scenario.py', 'ValidationRule').
python_class('oqlos/models/scenario.py', 'Goal').
python_class('oqlos/models/scenario.py', 'Scenario').
python_class('oqlos/reporters/junit.py', 'JUnitReporter').
python_method('JUnitReporter', 'generate', 2, 7, 11).
python_method('JUnitReporter', '_add_testcase', 3, 8, 1).
python_class('oqlos/shared/event_server.py', 'ConnectionManager').
python_method('ConnectionManager', '__init__', 0, 1, 1).
python_method('ConnectionManager', 'connect', 2, 2, 1).
python_method('ConnectionManager', 'disconnect', 1, 1, 2).
python_method('ConnectionManager', 'broadcast', 2, 4, 4).
python_method('ConnectionManager', 'get_stats', 0, 2, 3).
python_class('oqlos/shared/event_server.py', 'EventServer').
python_method('EventServer', '__init__', 3, 1, 2).
python_method('EventServer', 'handle_client', 1, 7, 8).
python_method('EventServer', '_handle_message', 2, 6, 10).
python_method('EventServer', '_normalize_event', 1, 3, 5).
python_method('EventServer', 'start', 0, 2, 4).
python_class('oqlos/shared/event_store.py', 'EventStore').
python_method('EventStore', '__init__', 1, 3, 2).
python_method('EventStore', 'append', 1, 2, 2).
python_method('EventStore', 'get_all', 0, 1, 1).
python_method('EventStore', 'get_recent', 1, 1, 0).
python_method('EventStore', 'get_by_correlation', 1, 3, 1).
python_method('EventStore', 'clear', 0, 2, 1).
python_method('EventStore', 'to_json', 0, 1, 1).
python_method('EventStore', 'from_json', 1, 1, 1).
python_method('EventStore', 'count', 0, 1, 1).
python_method('EventStore', '_save', 0, 2, 2).
python_method('EventStore', '_load', 0, 2, 2).
python_class('oqlos/shared/file_ops.py', 'PathEscapeError').
python_class('oqlos/shared/logs_query.py', 'LogsQueryService').
python_method('LogsQueryService', '__init__', 1, 1, 0).
python_method('LogsQueryService', 'db_exists', 0, 1, 2).
python_method('LogsQueryService', '_connect', 0, 1, 1).
python_method('LogsQueryService', 'query_logs', 0, 11, 11).
python_method('LogsQueryService', 'get_stats', 0, 6, 6).
python_class('oqlos/tools/cql_cli/main.py', 'ScenarioFetchError').
python_class('oqlos/tools/hardware_diagnose/discovery.py', 'UsbDevice').
python_method('UsbDevice', 'to_dict', 0, 3, 0).
python_class('oqlos/tools/xml_import/models.py', 'SensorParam').
python_class('oqlos/tools/xml_import/models.py', 'Output').
python_class('oqlos/tools/xml_import/models.py', 'Operation').
python_class('oqlos/tools/xml_import/models.py', 'TestRun').
python_class('oqlos/tools/xml_import/models.py', 'DeviceReport').
python_class('scripts/oql_v2_to_v4_migrate_db.py', 'MigrationResult').
python_class('scripts/oql_v2_validator.py', 'Issue').
python_class('scripts/oql_v4_validator.py', 'Issue').
python_class('tests/firmware/test_control_proxy.py', 'FakeOqlosResponse').
python_method('FakeOqlosResponse', '__init__', 2, 1, 0).
python_method('FakeOqlosResponse', 'raise_for_status', 0, 2, 3).
python_method('FakeOqlosResponse', 'json', 0, 1, 0).
python_class('tests/firmware/test_dsl_parser_runtime.py', 'TestDslParserRuntime').
python_method('TestDslParserRuntime', 'test_parses_bracketed_task_lines_for_valve_14', 0, 9, 2).
python_method('TestDslParserRuntime', 'test_parses_wait_step_from_builder_serialization', 0, 5, 2).
python_method('TestDslParserRuntime', 'test_parses_bare_set_wait_step', 0, 4, 1).
python_method('TestDslParserRuntime', 'test_parses_dedicated_pump_command', 0, 6, 2).
python_method('TestDslParserRuntime', 'test_parses_set_lines_for_valve_and_compressor', 0, 8, 1).
python_method('TestDslParserRuntime', 'test_parses_if_condition_with_operator_between_brackets', 0, 5, 2).
python_method('TestDslParserRuntime', 'test_expands_func_call_into_runtime_steps', 0, 8, 1).
python_method('TestDslParserRuntime', 'test_reports_invalid_runtime_line_for_pompx_typo', 0, 4, 1).
python_method('TestDslParserRuntime', 'test_accepts_pompa_with_suffix_as_real_pump_reference', 0, 5, 2).
python_method('TestDslParserRuntime', 'test_accepts_set_pompa_alias', 0, 6, 2).
python_class('tests/firmware/test_firmware_executor.py', '_Vars').
python_method('_Vars', '__init__', 0, 2, 0).
python_method('_Vars', 'interpolate', 1, 1, 1).
python_method('_Vars', 'set', 2, 1, 0).
python_class('tests/firmware/test_firmware_executor.py', '_Out').
python_method('_Out', '__init__', 0, 2, 0).
python_method('_Out', 'step', 2, 1, 1).
python_method('_Out', 'error', 1, 1, 1).
python_method('_Out', 'warn', 1, 1, 1).
python_class('tests/firmware/test_firmware_executor.py', '_Normalizer').
python_method('_Normalizer', 'normalize_pump_power', 1, 1, 1).
python_class('tests/firmware/test_firmware_executor.py', '_AsyncGateway').
python_method('_AsyncGateway', '__init__', 1, 2, 0).
python_method('_AsyncGateway', 'set_pump', 1, 1, 1).
python_method('_AsyncGateway', 'set_valve', 2, 1, 1).
python_method('_AsyncGateway', 'set_lung', 0, 1, 1).
python_class('tests/firmware/test_gateway_http.py', '_Response').
python_method('_Response', '__init__', 1, 1, 0).
python_method('_Response', 'raise_for_status', 0, 1, 0).
python_method('_Response', 'json', 0, 1, 0).
python_class('tests/firmware/test_gateway_http.py', '_Client').
python_method('_Client', '__init__', 0, 1, 0).
python_method('_Client', 'get', 1, 1, 2).
python_method('_Client', 'post', 2, 1, 2).
python_class('tests/firmware/test_hardware_health_http.py', '_FakeGateway').
python_method('_FakeGateway', 'health', 0, 1, 0).
python_class('tests/firmware/test_hardware_hui_routes.py', '_FakeGateway').
python_method('_FakeGateway', 'hold', 1, 1, 0).
python_class('tests/firmware/test_hardware_identify.py', '_FakeGateway').
python_method('_FakeGateway', 'health', 0, 1, 0).
python_class('tests/firmware/test_hardware_identify.py', '_UnavailableAdcGateway').
python_method('_UnavailableAdcGateway', 'health', 0, 1, 0).
python_method('_UnavailableAdcGateway', 'read_sensor', 1, 1, 1).
python_class('tests/firmware/test_hardware_identify.py', '_ModbusTimeoutGateway').
python_method('_ModbusTimeoutGateway', 'health', 0, 1, 0).
python_class('tests/firmware/test_hardware_runtime_routes.py', '_UnavailableAdcGateway').
python_method('_UnavailableAdcGateway', 'health', 0, 1, 0).
python_method('_UnavailableAdcGateway', 'read_sensor', 1, 1, 1).
python_class('tests/firmware/test_hui_actions.py', 'FakeGateway').
python_method('FakeGateway', '__init__', 0, 1, 0).
python_method('FakeGateway', 'set_valve', 2, 1, 1).
python_method('FakeGateway', 'set_pump', 1, 1, 1).
python_method('FakeGateway', 'set_lung_result', 0, 1, 1).
python_method('FakeGateway', 'stop_lung', 0, 1, 1).
python_method('FakeGateway', '_get_or_connect_plugin', 1, 1, 1).
python_class('tests/firmware/test_hui_actions.py', 'FakeTic249Plugin').
python_method('FakeTic249Plugin', '__init__', 0, 1, 0).
python_method('FakeTic249Plugin', 'execute_command', 2, 1, 1).
python_class('tests/firmware/test_lung_integration.py', 'TestLungDslHelpers').
python_method('TestLungDslHelpers', 'test_looks_like_lung_object', 1, 2, 2).
python_method('TestLungDslHelpers', 'test_not_lung_object', 0, 3, 1).
python_method('TestLungDslHelpers', 'test_map_peripheral_lung', 0, 5, 1).
python_method('TestLungDslHelpers', 'test_map_lung_action_start', 0, 3, 1).
python_method('TestLungDslHelpers', 'test_map_lung_action_stop', 0, 3, 1).
python_method('TestLungDslHelpers', 'test_map_lung_action_default_cycles', 0, 3, 1).
python_method('TestLungDslHelpers', 'test_map_action_value_lung', 0, 3, 1).
python_class('tests/firmware/test_lung_integration.py', 'TestLungDslParser').
python_method('TestLungDslParser', 'test_parses_lung_set_command', 0, 6, 2).
python_method('TestLungDslParser', 'test_parses_lung_task_command', 0, 5, 2).
python_method('TestLungDslParser', 'test_parses_lung_stop', 0, 5, 2).
python_class('tests/firmware/test_lung_integration.py', 'TestLungExecutor').
python_method('TestLungExecutor', '_make_orchestrator', 0, 1, 3).
python_method('TestLungExecutor', 'test_execute_lung_step_reciprocate', 0, 1, 6).
python_method('TestLungExecutor', 'test_execute_lung_step_stop', 0, 1, 6).
python_method('TestLungExecutor', 'test_execute_step_dispatches_set_lung', 0, 1, 5).
python_class('tests/firmware/test_lung_integration.py', 'TestFirmwareAdapterLung').
python_method('TestFirmwareAdapterLung', 'test_peripheral_map_lung', 0, 5, 0).
python_method('TestFirmwareAdapterLung', 'test_resolve_peripheral_lung', 0, 3, 2).
python_method('TestFirmwareAdapterLung', 'test_dispatch_lung_start', 0, 3, 3).
python_method('TestFirmwareAdapterLung', 'test_dispatch_lung_stop', 0, 3, 4).
python_method('TestFirmwareAdapterLung', 'test_set_peripheral_lung_start', 0, 4, 5).
python_method('TestFirmwareAdapterLung', 'test_set_peripheral_lung_stop', 0, 4, 5).
python_class('tests/firmware/test_lung_integration.py', 'TestHardwareGatewayLung').
python_method('TestHardwareGatewayLung', 'test_set_lung_mock', 0, 2, 3).
python_method('TestHardwareGatewayLung', 'test_stop_lung_mock', 0, 2, 3).
python_class('tests/firmware/test_lung_integration.py', 'TestCqlInterpreterLung').
python_method('TestCqlInterpreterLung', 'test_dry_run_lung_action', 0, 4, 4).
python_class('tests/firmware/test_lung_plugin_reciprocate.py', '_JsonResponse').
python_method('_JsonResponse', '__init__', 2, 1, 0).
python_method('_JsonResponse', 'json', 0, 1, 0).
python_class('tests/firmware/test_lung_plugin_reciprocate.py', '_ReadyFalseClient').
python_method('_ReadyFalseClient', '__init__', 0, 1, 0).
python_method('_ReadyFalseClient', 'get', 1, 2, 2).
python_method('_ReadyFalseClient', 'post', 2, 1, 2).
python_class('tests/firmware/test_modbus_discovery.py', '_OkResponse').
python_method('_OkResponse', 'isError', 0, 1, 0).
python_class('tests/firmware/test_modbus_discovery.py', '_ErrorResponse').
python_method('_ErrorResponse', 'isError', 0, 1, 0).
python_class('tests/firmware/test_modbus_probe_cli.py', '_OkResponse').
python_method('_OkResponse', 'isError', 0, 1, 0).
python_method('_OkResponse', '__str__', 0, 1, 0).
python_class('tests/firmware/test_modbus_probe_cli.py', '_ErrorResponse').
python_method('_ErrorResponse', 'isError', 0, 1, 0).
python_class('tests/firmware/test_motor_http_handlers.py', '_Response').
python_method('_Response', '__init__', 1, 1, 0).
python_method('_Response', 'json', 0, 1, 0).
python_class('tests/firmware/test_motor_http_handlers.py', '_Client').
python_method('_Client', '__init__', 1, 1, 0).
python_method('_Client', 'post', 2, 1, 1).
python_method('_Client', 'get', 1, 1, 1).
python_class('tests/firmware/test_motor_modbus_handlers.py', '_ModbusResult').
python_method('_ModbusResult', '__init__', 2, 3, 0).
python_method('_ModbusResult', 'isError', 0, 1, 0).
python_class('tests/firmware/test_motor_modbus_handlers.py', '_Bus').
python_method('_Bus', '__init__', 2, 3, 0).
python_method('_Bus', 'call', 1, 5, 4).
python_class('tests/firmware/test_motor_plugin.py', '_Response').
python_method('_Response', 'json', 0, 1, 0).
python_class('tests/firmware/test_motor_plugin.py', '_Client').
python_method('_Client', 'post', 1, 2, 2).
python_class('tests/firmware/test_motor_plugin.py', '_HealthClient').
python_method('_HealthClient', 'get', 1, 2, 2).
python_class('tests/firmware/test_normalize_scenario.py', 'TestExtractId').
python_method('TestExtractId', 'test_valid_id', 0, 2, 1).
python_method('TestExtractId', 'test_strips_whitespace', 0, 2, 1).
python_method('TestExtractId', 'test_missing_id_returns_none', 0, 2, 1).
python_method('TestExtractId', 'test_empty_string_returns_none', 0, 2, 1).
python_method('TestExtractId', 'test_none_value_returns_none', 0, 2, 1).
python_method('TestExtractId', 'test_numeric_id_converted_to_str', 0, 2, 1).
python_class('tests/firmware/test_normalize_scenario.py', 'TestExtractDisplayFields').
python_method('TestExtractDisplayFields', 'test_all_fields_present', 0, 7, 1).
python_method('TestExtractDisplayFields', 'test_name_fallback_to_title', 0, 2, 1).
python_method('TestExtractDisplayFields', 'test_name_fallback_to_code', 0, 2, 1).
python_method('TestExtractDisplayFields', 'test_name_fallback_to_sid', 0, 2, 1).
python_method('TestExtractDisplayFields', 'test_device_fallback_to_device_id', 0, 2, 1).
python_method('TestExtractDisplayFields', 'test_protocol_fallback_to_protocol_id', 0, 2, 1).
python_method('TestExtractDisplayFields', 'test_missing_optional_fields_default_empty', 0, 5, 1).
python_class('tests/firmware/test_normalize_scenario.py', 'TestExtractGoals').
python_method('TestExtractGoals', 'test_no_content_returns_empty', 0, 2, 1).
python_method('TestExtractGoals', 'test_none_content_returns_empty', 0, 2, 1).
python_method('TestExtractGoals', 'test_content_with_goals', 0, 6, 2).
python_method('TestExtractGoals', 'test_content_without_goals_key', 0, 2, 1).
python_method('TestExtractGoals', 'test_content_non_dict', 0, 2, 1).
python_class('tests/firmware/test_normalize_scenario.py', 'TestComputeSlug').
python_method('TestComputeSlug', 'test_explicit_slug', 0, 2, 1).
python_method('TestComputeSlug', 'test_slug_from_code', 0, 2, 1).
python_method('TestComputeSlug', 'test_slug_from_display_name', 0, 2, 1).
python_method('TestComputeSlug', 'test_slug_from_sid', 0, 2, 1).
python_method('TestComputeSlug', 'test_double_hyphens_collapsed', 0, 2, 1).
python_method('TestComputeSlug', 'test_strips_leading_trailing_hyphens', 0, 2, 1).
python_class('tests/firmware/test_normalize_scenario.py', 'TestNormalizeScenarioRow').
python_method('TestNormalizeScenarioRow', 'test_full_row', 0, 6, 3).
python_method('TestNormalizeScenarioRow', 'test_minimal_row', 0, 5, 2).
python_method('TestNormalizeScenarioRow', 'test_missing_id_returns_none', 0, 2, 1).
python_method('TestNormalizeScenarioRow', 'test_empty_id_returns_none', 0, 2, 1).
python_method('TestNormalizeScenarioRow', 'test_fallback_fields', 0, 4, 1).
python_class('tests/firmware/test_oql_mqtt_bridge.py', '_FakeMessage').
python_method('_FakeMessage', '__init__', 2, 1, 0).
python_class('tests/firmware/test_oql_mqtt_bridge.py', 'FakeBroker').
python_method('FakeBroker', '__init__', 0, 1, 0).
python_method('FakeBroker', 'register', 1, 1, 1).
python_method('FakeBroker', 'publish', 4, 1, 5).
python_method('FakeBroker', 'deliver_retained', 2, 4, 4).
python_class('tests/firmware/test_oql_mqtt_bridge.py', 'FakeClient').
python_method('FakeClient', '__init__', 2, 1, 2).
python_method('FakeClient', 'username_pw_set', 2, 1, 0).
python_method('FakeClient', 'will_set', 4, 1, 0).
python_method('FakeClient', 'connect', 3, 2, 1).
python_method('FakeClient', 'loop_start', 0, 1, 0).
python_method('FakeClient', 'loop_stop', 0, 1, 0).
python_method('FakeClient', 'disconnect', 0, 1, 0).
python_method('FakeClient', 'subscribe', 2, 1, 2).
python_method('FakeClient', 'publish', 4, 1, 1).
python_class('tests/firmware/test_oql_route_http.py', '_FakeController').
python_method('_FakeController', '__init__', 1, 1, 0).
python_method('_FakeController', 'execute', 1, 1, 1).
python_method('_FakeController', 'manage', 2, 1, 1).
python_class('tests/firmware/test_panel_ui.py', '_FakeController').
python_method('_FakeController', '__init__', 1, 1, 0).
python_method('_FakeController', 'execute', 1, 1, 1).
python_method('_FakeController', 'manage', 2, 1, 1).
python_class('tests/firmware/test_parser_cycle.py', 'TestParserCycleDetection').
python_method('TestParserCycleDetection', 'test_direct_circular_func_raises', 0, 1, 2).
python_method('TestParserCycleDetection', 'test_self_referencing_func_raises', 0, 1, 2).
python_method('TestParserCycleDetection', 'test_valid_func_call_works', 0, 3, 2).
python_method('TestParserCycleDetection', 'test_max_func_depth_constant', 0, 2, 0).
python_class('tests/firmware/test_plugin_health.py', '_JsonResponse').
python_method('_JsonResponse', '__init__', 2, 1, 0).
python_method('_JsonResponse', 'json', 0, 1, 0).
python_class('tests/firmware/test_plugin_health.py', '_PiadcClient').
python_method('_PiadcClient', 'get', 1, 4, 1).
python_class('tests/firmware/test_plugin_health.py', '_UninitializedPiadcClient').
python_method('_UninitializedPiadcClient', 'get', 1, 4, 1).
python_class('tests/firmware/test_plugin_health.py', '_FailingPiadcClient').
python_method('_FailingPiadcClient', 'get', 1, 4, 1).
python_class('tests/firmware/test_plugin_health.py', '_LungClient').
python_method('_LungClient', 'get', 1, 4, 2).
python_class('tests/firmware/test_plugin_health.py', '_BlockingModbusClient').
python_method('_BlockingModbusClient', 'read_coils', 0, 1, 1).
python_class('tests/firmware/test_plugin_health.py', '_OkModbusResult').
python_method('_OkModbusResult', 'isError', 0, 1, 0).
python_class('tests/firmware/test_plugin_health.py', '_CapturingModbusClient').
python_method('_CapturingModbusClient', '__init__', 0, 1, 0).
python_method('_CapturingModbusClient', 'read_coils', 0, 1, 1).
python_method('_CapturingModbusClient', 'write_coil', 0, 1, 1).
python_class('tests/firmware/test_plugin_health.py', '_CapturingAsyncModbusBus').
python_method('_CapturingAsyncModbusBus', 'read_coils', 0, 1, 2).
python_method('_CapturingAsyncModbusBus', 'write_coil', 0, 1, 2).
python_class('tests/firmware/test_plugin_health.py', '_CapturingModbusAdcClient').
python_method('_CapturingModbusAdcClient', '__init__', 0, 1, 0).
python_method('_CapturingModbusAdcClient', 'read_input_registers', 0, 1, 1).
python_class('tests/firmware/test_plugin_http_handlers.py', '_Response').
python_method('_Response', '__init__', 1, 1, 0).
python_method('_Response', 'json', 0, 1, 0).
python_class('tests/firmware/test_plugin_http_handlers.py', '_Client').
python_method('_Client', '__init__', 1, 1, 0).
python_method('_Client', 'post', 2, 1, 1).
python_method('_Client', 'get', 1, 1, 1).
python_class('tests/firmware/test_plugins_api.py', 'FakePlugin').
python_method('FakePlugin', 'execute_command', 2, 1, 0).
python_class('tests/firmware/test_safe_eval.py', '_Obj').
python_method('_Obj', '__init__', 0, 2, 2).
python_class('tests/firmware/test_safe_eval.py', 'TestBasicComparisons').
python_method('TestBasicComparisons', 'test_eq_true', 0, 2, 1).
python_method('TestBasicComparisons', 'test_eq_false', 0, 2, 1).
python_method('TestBasicComparisons', 'test_ne_true', 0, 2, 1).
python_method('TestBasicComparisons', 'test_ne_false', 0, 2, 1).
python_method('TestBasicComparisons', 'test_lt', 0, 3, 1).
python_method('TestBasicComparisons', 'test_le', 0, 3, 1).
python_method('TestBasicComparisons', 'test_gt', 0, 3, 1).
python_method('TestBasicComparisons', 'test_ge', 0, 3, 1).
python_method('TestBasicComparisons', 'test_float_comparison', 0, 3, 1).
python_class('tests/firmware/test_safe_eval.py', 'TestBooleanOps').
python_method('TestBooleanOps', 'test_and_true', 0, 2, 1).
python_method('TestBooleanOps', 'test_and_false', 0, 2, 1).
python_method('TestBooleanOps', 'test_or_true', 0, 2, 1).
python_method('TestBooleanOps', 'test_or_false', 0, 2, 1).
python_method('TestBooleanOps', 'test_not_true', 0, 2, 1).
python_method('TestBooleanOps', 'test_not_false', 0, 2, 1).
python_method('TestBooleanOps', 'test_complex_boolean', 0, 4, 1).
python_class('tests/firmware/test_safe_eval.py', 'TestChainedComparisons').
python_method('TestChainedComparisons', 'test_chained_lt', 0, 4, 1).
python_method('TestChainedComparisons', 'test_chained_le', 0, 3, 1).
python_class('tests/firmware/test_safe_eval.py', 'TestNegativeNumbers').
python_method('TestNegativeNumbers', 'test_negative_literal', 0, 3, 1).
python_method('TestNegativeNumbers', 'test_negative_context_value', 0, 2, 1).
python_method('TestNegativeNumbers', 'test_unary_plus', 0, 2, 1).
python_class('tests/firmware/test_safe_eval.py', 'TestDottedAccess').
python_method('TestDottedAccess', 'test_simple_attr', 0, 2, 2).
python_method('TestDottedAccess', 'test_attr_comparison', 0, 2, 2).
python_method('TestDottedAccess', 'test_unknown_attr_raises', 0, 1, 3).
python_class('tests/firmware/test_safe_eval.py', 'TestErrorHandling').
python_method('TestErrorHandling', 'test_empty_string_raises', 0, 1, 2).
python_method('TestErrorHandling', 'test_whitespace_only_raises', 0, 1, 2).
python_method('TestErrorHandling', 'test_unknown_variable_raises', 0, 1, 2).
python_method('TestErrorHandling', 'test_syntax_error_raises', 0, 1, 2).
python_method('TestErrorHandling', 'test_unsupported_node_raises', 0, 1, 2).
python_class('tests/firmware/test_safe_eval.py', 'TestSecurity').
python_method('TestSecurity', 'test_reject_function_call', 0, 1, 2).
python_method('TestSecurity', 'test_reject_import', 0, 1, 2).
python_method('TestSecurity', 'test_reject_lambda', 0, 1, 2).
python_method('TestSecurity', 'test_reject_list_comprehension', 0, 1, 2).
python_method('TestSecurity', 'test_reject_dict_literal', 0, 1, 2).
python_method('TestSecurity', 'test_reject_subscript', 0, 1, 2).
python_method('TestSecurity', 'test_reject_string_literal', 0, 1, 2).
python_method('TestSecurity', 'test_reject_fstring', 0, 1, 2).
python_method('TestSecurity', 'test_reject_walrus_operator', 0, 1, 2).
python_method('TestSecurity', 'test_reject_attribute_dunder', 0, 1, 2).
python_method('TestSecurity', 'test_reject_exec_via_eval', 0, 1, 2).
python_method('TestSecurity', 'test_reject_getattr_builtin', 0, 1, 2).
python_class('tests/firmware/test_safe_eval.py', 'TestFirmwareScenarios').
python_method('TestFirmwareScenarios', 'test_valve_pressure_check', 0, 2, 2).
python_method('TestFirmwareScenarios', 'test_pump_power_range', 0, 2, 1).
python_method('TestFirmwareScenarios', 'test_leak_rate_validation', 0, 2, 1).
python_method('TestFirmwareScenarios', 'test_sensor_threshold', 0, 2, 2).
python_method('TestFirmwareScenarios', 'test_boolean_context_value', 0, 3, 1).
python_class('tests/firmware/test_tokenizer_extended.py', 'TestValSingleQuote').
python_method('TestValSingleQuote', 'test_val_single_quote', 0, 5, 1).
python_method('TestValSingleQuote', 'test_val_double_quote', 0, 3, 1).
python_method('TestValSingleQuote', 'test_val_bracket', 0, 3, 1).
python_class('tests/firmware/test_tokenizer_extended.py', 'TestMinMaxSingleQuote').
python_method('TestMinMaxSingleQuote', 'test_min_single_quote', 0, 5, 1).
python_method('TestMinMaxSingleQuote', 'test_max_single_quote', 0, 5, 1).
python_method('TestMinMaxSingleQuote', 'test_min_bracket', 0, 3, 1).
python_method('TestMinMaxSingleQuote', 'test_max_double_quote', 0, 3, 1).
python_class('tests/firmware/test_tokenizer_extended.py', 'TestIfElseSingleQuote').
python_method('TestIfElseSingleQuote', 'test_if_else_single_quote', 0, 7, 2).
python_method('TestIfElseSingleQuote', 'test_if_else_bracket_single_error', 0, 4, 2).
python_method('TestIfElseSingleQuote', 'test_if_else_bracket_double_error', 0, 3, 2).
python_class('tests/firmware/test_tokenizer_extended.py', 'TestIfStandalone').
python_method('TestIfStandalone', 'test_if_standalone_unicode_op', 0, 6, 2).
python_method('TestIfStandalone', 'test_if_standalone_ascii_op', 0, 4, 2).
python_method('TestIfStandalone', 'test_if_standalone_with_unit', 0, 3, 2).
python_class('tests/firmware/test_tokenizer_extended.py', 'TestElseStandalone').
python_method('TestElseStandalone', 'test_else_error', 0, 5, 2).
python_method('TestElseStandalone', 'test_else_info', 0, 3, 2).
python_class('tests/firmware/test_tokenizer_extended.py', 'TestSample').
python_method('TestSample', 'test_sample_with_interval', 0, 5, 2).
python_method('TestSample', 'test_sample_stop', 0, 4, 2).
python_class('tests/firmware/test_tokenizer_extended.py', 'TestGoto').
python_method('TestGoto', 'test_goto', 0, 4, 2).
python_class('tests/firmware/test_tokenizer_extended.py', 'TestFunc').
python_method('TestFunc', 'test_func_sub', 0, 6, 2).
python_method('TestFunc', 'test_func_div', 0, 3, 2).
python_class('tests/firmware/test_tokenizer_extended.py', 'TestSaveSingleQuote').
python_method('TestSaveSingleQuote', 'test_save_single_simple', 0, 4, 2).
python_method('TestSaveSingleQuote', 'test_save_single_with_namespace', 0, 4, 2).
python_class('tests/firmware/test_tokenizer_extended.py', 'TestWaitQuoted').
python_method('TestWaitQuoted', 'test_wait_quoted_seconds', 0, 3, 2).
python_class('tests/test_core.py', 'TestVariableStore').
python_method('TestVariableStore', 'test_set_get', 0, 4, 3).
python_method('TestVariableStore', 'test_interpolate_dollar', 0, 2, 2).
python_method('TestVariableStore', 'test_interpolate_braces', 0, 2, 2).
python_method('TestVariableStore', 'test_interpolate_missing', 0, 2, 2).
python_class('tests/test_core.py', 'TestCqlParser').
python_method('TestCqlParser', 'test_simple_metadata', 0, 2, 1).
python_method('TestCqlParser', 'test_parses_set_as_pump', 0, 6, 2).
python_method('TestCqlParser', 'test_parses_set_command_for_valve_and_compressor', 0, 7, 2).
python_method('TestCqlParser', 'test_simple_goals', 0, 4, 2).
python_method('TestCqlParser', 'test_simple_actions', 0, 9, 2).
python_method('TestCqlParser', 'test_connectgo_metadata', 0, 4, 1).
python_method('TestCqlParser', 'test_connectgo_intervals', 0, 5, 2).
python_method('TestCqlParser', 'test_connectgo_scenario', 0, 6, 2).
python_method('TestCqlParser', 'test_connectgo_goals', 0, 5, 2).
python_method('TestCqlParser', 'test_connectgo_steps', 0, 4, 2).
python_method('TestCqlParser', 'test_connectgo_arrow_action', 0, 6, 2).
python_method('TestCqlParser', 'test_connectgo_condition', 0, 9, 2).
python_method('TestCqlParser', 'test_connectgo_example_file', 0, 7, 8).
python_class('tests/test_core.py', 'TestCqlValidator').
python_method('TestCqlValidator', 'test_valid_document', 0, 2, 3).
python_method('TestCqlValidator', 'test_empty_document', 0, 2, 3).
python_method('TestCqlValidator', 'test_invalid_interval_ref', 0, 2, 3).
python_class('tests/test_core.py', 'TestCqlInterpreter').
python_method('TestCqlInterpreter', 'test_dry_run_simple', 0, 3, 3).
python_method('TestCqlInterpreter', 'test_dry_run_with_sensors', 0, 2, 3).
python_method('TestCqlInterpreter', 'test_validate_mode', 0, 2, 2).
python_method('TestCqlInterpreter', 'test_set_actions_store_variables', 0, 4, 3).
python_method('TestCqlInterpreter', 'test_variables_saved', 0, 2, 2).
python_method('TestCqlInterpreter', 'test_connectgo_oql_example_file_dry_runs', 0, 5, 5).
python_class('tests/test_core.py', 'TestCqlExecuteMode').
python_method('TestCqlExecuteMode', 'test_execute_mode_initializes_firmware', 0, 3, 1).
python_method('TestCqlExecuteMode', 'test_pump_flow_uses_env_scale', 1, 3, 6).
python_method('TestCqlExecuteMode', 'test_pump_compact_liter_value_uses_flow_scale', 1, 3, 6).
python_method('TestCqlExecuteMode', 'test_version4_textual_hardware_set_values_execute', 1, 3, 6).
python_method('TestCqlExecuteMode', 'test_motor2_reciprocating_oql_execute_uses_reciprocate_not_relative_move', 1, 4, 5).
python_method('TestCqlExecuteMode', 'test_motor2_runtime_config_builds_volume_duration_plan', 0, 8, 2).
python_method('TestCqlExecuteMode', 'test_motor2_volume_duration_reciprocating_calculates_cycles_and_speed', 1, 3, 4).
python_method('TestCqlExecuteMode', 'test_motor2_volume_start_without_direction_defaults_left', 1, 3, 4).
python_method('TestCqlExecuteMode', 'test_motor2_acceleration_percent_above_100_is_preserved', 1, 3, 4).
python_method('TestCqlExecuteMode', 'test_repeat_stop_is_accepted_in_expanded_oql_repeat_blocks', 0, 3, 2).
python_method('TestCqlExecuteMode', 'test_pump_flow_scale_can_be_overridden_in_config_block', 1, 4, 7).
python_method('TestCqlExecuteMode', 'test_dry_run_does_not_use_firmware', 0, 3, 2).
python_method('TestCqlExecuteMode', 'test_auto_mock_seeds_default_sensors', 0, 3, 1).
python_method('TestCqlExecuteMode', 'test_auto_mock_range_condition_passes', 0, 3, 2).
python_method('TestCqlExecuteMode', 'test_auto_mock_disabled', 0, 2, 2).
python_class('tests/test_core.py', 'TestFirmwareAdapterUnit').
python_method('TestFirmwareAdapterUnit', '_firmware_with_post_response', 1, 1, 4).
python_method('TestFirmwareAdapterUnit', 'test_peripheral_map_completeness', 0, 4, 0).
python_method('TestFirmwareAdapterUnit', 'test_sensor_map', 0, 4, 0).
python_method('TestFirmwareAdapterUnit', 'test_parse_numeric', 0, 6, 1).
python_method('TestFirmwareAdapterUnit', 'test_resolve_peripheral', 0, 6, 2).
python_method('TestFirmwareAdapterUnit', 'test_dispatch_confirm_no_http', 0, 3, 2).
python_method('TestFirmwareAdapterUnit', 'test_set_peripheral_pump_rejects_nested_failed_response', 0, 2, 3).
python_method('TestFirmwareAdapterUnit', 'test_dispatch_pump_reports_hardware_rejection', 0, 3, 2).
python_method('TestFirmwareAdapterUnit', 'test_dispatch_lung_falls_back_to_direct_service_on_404', 1, 4, 11).
python_class('tests/test_core.py', 'TestEventStore').
python_method('TestEventStore', 'test_append_and_get', 0, 3, 3).
python_method('TestEventStore', 'test_get_recent', 0, 4, 5).
python_method('TestEventStore', 'test_get_by_correlation', 0, 2, 4).
python_method('TestEventStore', 'test_clear', 0, 2, 3).
python_method('TestEventStore', 'test_json_roundtrip', 0, 2, 4).
python_method('TestEventStore', 'test_persistence', 1, 3, 4).
python_class('tests/test_cql_cli.py', '_FakeInterpreter').
python_method('_FakeInterpreter', '__init__', 0, 1, 1).
python_method('_FakeInterpreter', 'run', 2, 1, 1).
python_class('tests/test_reporting.py', 'MockWS').
python_method('MockWS', 'send', 1, 1, 0).
python_method('MockWS', 'close', 0, 1, 0).
python_class('tests/test_reporting.py', 'MockBridge').
python_method('MockBridge', '__init__', 0, 1, 3).
python_method('MockBridge', 'send_event', 2, 1, 1).

% ── Dependencies ─────────────────────────────────────────

% ── Makefile Targets ─────────────────────────────────────
makefile_target('help', '').
makefile_target('test', '--- testy ----------------------------------------------------------------').
makefile_target('test-hw', '').
makefile_target('smoke', '').
makefile_target('checksums', '--- integralność / sync --------------------------------------------------').
makefile_target('verify-rpi', '').
makefile_target('sync-rpi', '').
makefile_target('restart', '').
makefile_target('deploy', '--- deploy (redeploy framework) ------------------------------------------').
makefile_target('redeploy', '').
makefile_target('122', '').
makefile_target('pi-hw', '').
makefile_target('serve', '--- uruchamianie lokalnie -------------------------------------------------').
makefile_target('panel-url', '').

% ── Taskfile Tasks ───────────────────────────────────────
taskfile_task('', 'Install Python dependencies (editable)').
taskfile_task('', 'Upgrade all outdated Python packages in the active / project venv').
taskfile_task('', 'Run pyqual quality pipeline').
taskfile_task('', 'Run pyqual with auto-fix').
taskfile_task('', 'Generate pyqual quality report').
taskfile_task('', 'Run pytest suite').
taskfile_task('', 'Run frontend unit tests (node:test)').
taskfile_task('', 'Run ruff lint check').
taskfile_task('', 'Auto-format with ruff').
taskfile_task('', 'Build wheel + sdist').
taskfile_task('', 'Remove build artefacts').
taskfile_task('', 'Run install, quality check').
taskfile_task('', 'Run OqlOS hardware doctor via oqlctl').
taskfile_task('', 'Identify connected hardware').
taskfile_task('', 'Reverse-engineer oqlos project structure').
taskfile_task('', 'Validate app.doql.less syntax').
taskfile_task('', 'Run doql health checks').
taskfile_task('', 'Generate code from app.doql.less').
taskfile_task('', 'Full doql analysis (adopt + validate + doctor)').
taskfile_task('', 'Show available tasks').

% ── Environment Variables ────────────────────────────────
env_variable('OQLOS_FIRMWARE_PORT', '8202', 'Server Configuration').
env_variable('OQLOS_SERVICE_NAME', 'firmware-simulator', '').
env_variable('OQLOS_SERVICE_VERSION', '0.1.0', '').
env_variable('OQLOS_HARDWARE_MODE', 'mock', 'Hardware Mode (mock | real)').
env_variable('OQLOS_MODBUS_SERIAL_PORT', '/dev/ttyACM1', 'Modbus RTU Configuration').
env_variable('OQLOS_MODBUS_BAUD', '19200', '').
env_variable('OQLOS_MODBUS_PARITY', 'N', '').
env_variable('OQLOS_MODBUS_DEVICE_ID', '1', '').
env_variable('OQLOS_MODBUS_HOST', 'localhost', 'Modbus TCP Fallback').
env_variable('OQLOS_MODBUS_PORT', '502', '').
env_variable('OQLOS_PIADC_URL', 'http://localhost:8080', 'Hardware Service URLs').
env_variable('OQLOS_MOTOR_URL', 'http://localhost:49055', '').
env_variable('OQLOS_LUNG_MOTOR_URL', 'http://localhost:8205', '').
env_variable('OQLOS_PUMP_FLOW_FULL_SCALE_LPM', '10', 'Flow rate that maps to 100% PWM for `pompa 1`').
env_variable('OQLOS_LOG_LEVEL', 'INFO', 'Logging (DEBUG | INFO | WARNING | ERROR)').
env_variable('OQLOS_CORS_ORIGINS', '*', 'CORS Settings (comma-separated origins or * for all)').

% ── TestQL Scenarios ─────────────────────────────────────
testql_scenario('cross-project-integration.testql.toon.yaml', 'integration').
testql_scenario('generated-api-integration.testql.toon.yaml', 'api').
testql_scenario('generated-api-smoke.testql.toon.yaml', 'api').
testql_scenario('generated-from-pytests.testql.toon.yaml', 'integration').
testql_scenario('generated-from-scenarios.testql.toon.yaml', 'hardware').
testql_scenario('testql-contracts.testql.toon.yaml', 'contract').

% ── Semantic Facts from SUMD.md ──────────────────────────
sumd_declared_file('app.doql.less', 'doql').
sumd_declared_file('openapi.yaml', 'openapi').
sumd_declared_file('testql-scenarios/cross-project-integration.testql.toon.yaml', 'testql').
sumd_declared_file('testql-scenarios/generated-api-integration.testql.toon.yaml', 'testql').
sumd_declared_file('testql-scenarios/generated-api-smoke.testql.toon.yaml', 'testql').
sumd_declared_file('testql-scenarios/generated-from-pytests.testql.toon.yaml', 'testql').
sumd_declared_file('testql-scenarios/generated-from-scenarios.testql.toon.yaml', 'testql').
sumd_declared_file('testql-contracts.testql.toon.yaml', 'testql').
sumd_declared_file('Taskfile.yml', 'taskfile').
sumd_declared_file('pyqual.yaml', 'pyqual').
sumd_declared_file('project/map.toon.yaml', 'analysis').
sumd_declared_file('project/logic.pl', 'analysis').
sumd_declared_file('project/calls.toon.yaml', 'analysis').
sumd_declared_file('openapi.yaml', 'openapi').
sumd_interface('api', '').
sumd_interface('cli', 'argparse').
sumd_interface('cli', '').
sumd_interface('cli', '').
sumd_workflow('test', 'manual').
sumd_workflow_step('test', 1, '$(PYTHON) -m pytest -q').
sumd_workflow('test-hw', 'manual').
sumd_workflow_step('test-hw', 1, 'scripts/test-hardware.sh $(PI)').
sumd_workflow('smoke', 'manual').
sumd_workflow_step('smoke', 1, 'awk \'/```bash markpact:ref assert-hw-node-healthy/{f=1').
sumd_workflow('checksums', 'manual').
sumd_workflow_step('checksums', 1, 'scripts/gen-checksums.sh').
sumd_workflow('verify-rpi', 'manual').
sumd_workflow_step('verify-rpi', 1, 'scripts/verify-rpi-checksum.sh $(PI)').
sumd_workflow('sync-rpi', 'manual').
sumd_workflow_step('sync-rpi', 1, 'rsync -rz --itemize-changes \').
sumd_workflow_step('sync-rpi', 2, '--exclude=\'__pycache__/\' --exclude=\'*.pyc\' --exclude=\'*.pyo\' \').
sumd_workflow_step('sync-rpi', 3, '--exclude=\'.pytest_cache/\' --exclude=\'*.log\' \').
sumd_workflow_step('sync-rpi', 4, 'oqlos/ $(PI):/home/pi/oqlos/oqlos/oqlos/').
sumd_workflow_step('sync-rpi', 5, '$(MAKE) verify-rpi PI=$(PI)').
sumd_workflow('restart', 'manual').
sumd_workflow_step('restart', 1, 'ssh $(PI) \'export XDG_RUNTIME_DIR=/run/user/$$(id -u)').
sumd_workflow_step('restart', 2, 'systemctl --user restart oqlos-hardware-api').
sumd_workflow_step('restart', 3, 'for i in $$(seq 1 20)').
sumd_workflow_step('restart', 4, 'curl -sf --max-time 4 http://127.0.0.1:8202/health && { echo "  <- /health OK"').
sumd_workflow('deploy', 'manual').
sumd_workflow_step('deploy', 1, 'redeploy run redeploy/$(NODE)/migration.md').
sumd_workflow('redeploy', 'manual').
sumd_workflow_step('redeploy', 1, 'echo "Wdrożenie węzła sprzętowego:"').
sumd_workflow_step('redeploy', 2, 'echo "  make 122                 # boardnet (192.168.188.122)"').
sumd_workflow_step('redeploy', 3, 'echo "  make pi-hw               # pi-hw    (192.168.188.110)"').
sumd_workflow_step('redeploy', 4, 'echo "  make deploy NODE=122     # dowolny węzeł z redeploy/<NODE>/migration.md"').
sumd_workflow('pi-hw', 'manual').
sumd_workflow_step('pi-hw', 1, '$(MAKE) deploy NODE=pi-hw PI=pi@192.168.188.110').
sumd_workflow('serve', 'manual').
sumd_workflow_step('serve', 1, '$(PYTHON) -m uvicorn oqlos.api.main:app --host 0.0.0.0 --port $(PORT)').
sumd_workflow('panel-url', 'manual').
sumd_workflow_step('panel-url', 1, 'echo "http://localhost:$(PORT)/panel"').
sumd_workflow('install', 'manual').
sumd_workflow_step('install', 1, 'pip install -e .[dev]').
sumd_workflow('deps:update', 'manual').
sumd_workflow('quality', 'manual').
sumd_workflow_step('quality', 1, 'pyqual run').
sumd_workflow('quality:fix', 'manual').
sumd_quality_workflow('quality:fix', 'fix').
sumd_workflow_step('quality:fix', 1, 'pyqual run --fix').
sumd_workflow('quality:report', 'manual').
sumd_quality_workflow('quality:report', 'report').
sumd_workflow_step('quality:report', 1, 'pyqual report').
sumd_workflow('test:frontend', 'manual').
sumd_workflow_step('test:frontend', 1, 'npm run test:unit').
sumd_workflow('lint', 'manual').
sumd_workflow_step('lint', 1, 'ruff check .').
sumd_workflow('fmt', 'manual').
sumd_workflow_step('fmt', 1, 'ruff format .').
sumd_workflow('build', 'manual').
sumd_workflow_step('build', 1, 'python -m build').
sumd_workflow('clean', 'manual').
sumd_workflow_step('clean', 1, 'rm -rf build/ dist/ *.egg-info').
sumd_workflow('hardware:check', 'manual').
sumd_workflow_step('hardware:check', 1, 'oqlctl doctor || echo "Hardware doctor reported issues"').
sumd_workflow('hardware:identify', 'manual').
sumd_workflow_step('hardware:identify', 1, 'oqlctl identify').
sumd_workflow('doql:adopt', 'manual').
sumd_workflow('doql:validate', 'manual').
sumd_workflow('doql:doctor', 'manual').
sumd_workflow('doql:build', 'manual').
sumd_workflow('help', 'manual').
sumd_workflow_step('help', 1, 'task --list').
```

## Source Map

*Top 1 modules by symbol density — signatures for LLM orientation.*

### `oqlos.config` (`oqlos/config.py`)

```python
def get_settings()  # CC=1, fan=0
class Settings:  # Application settings loaded from environment variables and .
```

## Call Graph

*463 nodes · 500 edges · 55 modules · CC̄=3.8*

### Hubs (by degree)

| Function | CC | in | out | total |
|----------|----|----|-----|-------|
| `print` *(in examples.hardware.doctor-workflow)* | 0 | 228 | 0 | **228** |
| `dict` *(in frontend.src.i18n.I18nProvider)* | 8 | 43 | 3 | **46** |
| `list` *(in frontend.src.pages.ScenarioFiles)* | 1 | 43 | 0 | **43** |
| `oql_doc_to_cql` *(in oqlos.core._oql_adapter)* | 12 ⚠ | 2 | 30 | **32** |
| `normalize_motor2_runtime_config` *(in oqlos.core.motor2_runtime)* | 12 ⚠ | 1 | 29 | **30** |
| `_safe_resolve` *(in oqlos.core.executor)* | 14 ⚠ | 7 | 21 | **28** |
| `run_oql_scenario` *(in setup_hardware_and_run_oql)* | 8 | 1 | 24 | **25** |
| `applyMapMutation` *(in frontend.src.pages.MapEditor)* | 2 | 17 | 8 | **25** |

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/oqlos/oqlos
# generated in 0.37s
# nodes: 463 | edges: 500 | modules: 55
# CC̄=3.8

HUBS[20]:
  examples.hardware.doctor-workflow.print
    CC=0  in:228  out:0  total:228
  frontend.src.i18n.I18nProvider.dict
    CC=8  in:43  out:3  total:46
  frontend.src.pages.ScenarioFiles.list
    CC=1  in:43  out:0  total:43
  oqlos.core._oql_adapter.oql_doc_to_cql
    CC=12  in:2  out:30  total:32
  oqlos.core.motor2_runtime.normalize_motor2_runtime_config
    CC=12  in:1  out:29  total:30
  oqlos.core.executor._safe_resolve
    CC=14  in:7  out:21  total:28
  setup_hardware_and_run_oql.run_oql_scenario
    CC=8  in:1  out:24  total:25
  frontend.src.pages.MapEditor.applyMapMutation
    CC=2  in:17  out:8  total:25
  oqlos.core.parser.parse_dsl_to_goal_with_issues
    CC=13  in:3  out:21  total:24
  oqlos.core.oql_parser.parse_oql
    CC=14  in:3  out:21  total:24
  oqlos.core._action_motor2._try_exec_motor2_set
    CC=13  in:1  out:22  total:23
  oqlos.core._action_motor2._motor2_build_plan
    CC=12  in:1  out:22  total:23
  oqlos.core._line_parsers._parse_if_condition
    CC=9  in:1  out:22  total:23
  frontend.src.api.wsClient.WsCqrsClient.super
    CC=1  in:19  out:1  total:20
  oqlos.core._func_resolver._collect_function_definitions
    CC=13  in:1  out:19  total:20
  oqlos.core.oql_parser.tokenize
    CC=13  in:5  out:14  total:19
  oqlos.core._interpreter_actions.exec_action_shell
    CC=13  in:0  out:19  total:19
  oqlos.core.oql_parser._expand_repeat_block_lines
    CC=8  in:2  out:16  total:18
  setup_hardware_and_run_oql.main
    CC=3  in:0  out:18  total:18
  frontend.src.utils.url-embed-config.mergeParentSearchIntoChildUrl
    CC=9  in:7  out:11  total:18

MODULES:
  examples.hardware.doctor-workflow  [1 funcs]
    print  CC=0  out:0
  frontend.src.api.hardware-api-errors  [5 funcs]
    describeDetail  CC=13  out:6
    extractErrorPayload  CC=4  out:1
    formatHardwareApiError  CC=9  out:3
    parseOqlError  CC=10  out:1
    tryParseJson  CC=3  out:1
  frontend.src.api.hardware-api-log  [4 funcs]
    isHardwareWizardPath  CC=2  out:3
    keys  CC=2  out:0
    logHardwareApiEvent  CC=6  out:4
    summarizeHardwareApiBody  CC=11  out:5
  frontend.src.api.hardware-diagnostic-failure  [9 funcs]
    _connectionError  CC=3  out:0
    _nestedOkMessage  CC=4  out:2
    _pickNestedObjectError  CC=8  out:4
    extractDiagnosticFailure  CC=13  out:6
    failureFromNestedOk  CC=10  out:4
    failureFromOkFalsePayload  CC=14  out:6
    failureFromSuccessFalse  CC=14  out:3
    firstActionableError  CC=3  out:4
    resultData  CC=4  out:0
  frontend.src.api.hardware-tic249-status  [3 funcs]
    isIdempotentDiagnosticSuccess  CC=3  out:2
    isIdempotentTic249Deenergized  CC=12  out:2
    tic249ResultStatus  CC=8  out:2
  frontend.src.api.hardwareApi  [13 funcs]
    _throwHttpError  CC=1  out:2
    _withCtx  CC=2  out:0
    bodySummary  CC=2  out:2
    durationMs  CC=7  out:6
    get  CC=1  out:1
    mode  CC=1  out:1
    normalized  CC=1  out:1
    post  CC=1  out:1
    put  CC=1  out:1
    request  CC=14  out:14
  frontend.src.api.scenarioFilesApi  [2 funcs]
    fetchScenarioFilesList  CC=2  out:4
    filterListableFiles  CC=3  out:2
  frontend.src.api.wsClient  [15 funcs]
    _handleMessage  CC=13  out:10
    _request  CC=3  out:12
    _scheduleReconnect  CC=3  out:3
    clearTimeout  CC=2  out:0
    command  CC=1  out:1
    connect  CC=5  out:10
    connected  CC=3  out:0
    delay  CC=2  out:2
    pending  CC=4  out:4
    query  CC=1  out:1
  frontend.src.hooks.useMapEditorSidebarAutoCollapse  [2 funcs]
    applyAutoCollapse  CC=9  out:4
    useMapEditorSidebarAutoCollapse  CC=9  out:11
  frontend.src.hooks.useRailHoverPreview  [8 funcs]
    cancelPanelClose  CC=2  out:2
    cancelRailOpen  CC=2  out:2
    panelEnter  CC=1  out:2
    panelLeave  CC=3  out:5
    previewExpand  CC=3  out:2
    railEnter  CC=3  out:4
    railLeave  CC=1  out:2
    useRailHoverPreview  CC=9  out:10
  frontend.src.hooks.useUrlConfig  [2 funcs]
    notifyParentChildReady  CC=4  out:5
    useUrlConfig  CC=8  out:15
  frontend.src.i18n.I18nProvider  [5 funcs]
    I18nProvider  CC=13  out:8
    dict  CC=8  out:3
    getInitialLang  CC=5  out:1
    t  CC=8  out:2
    val  CC=2  out:2
  frontend.src.pages.HardwareDemo  [13 funcs]
    Ctx  CC=2  out:2
    appendLog  CC=1  out:3
    controller  CC=5  out:9
    ensureAudioCtx  CC=4  out:4
    fallbackDevice  CC=2  out:5
    fb  CC=2  out:5
    now  CC=1  out:1
    onNoteClick  CC=4  out:9
    playMelody  CC=9  out:11
    playNote  CC=5  out:7
  frontend.src.pages.HardwareRestart  [20 funcs]
    canRunCurrentStep  CC=1  out:4
    confirmErrorKey  CC=1  out:4
    confirmLabelKey  CC=1  out:4
    currentStep  CC=1  out:4
    isConfigureStep  CC=1  out:4
    isSeparateAdapters  CC=1  out:4
    loadPlan  CC=4  out:10
    log  CC=1  out:3
    port  CC=6  out:9
    refreshRuntimeStatus  CC=3  out:3
  frontend.src.pages.HardwareStatus  [5 funcs]
    adapters  CC=2  out:8
    copyAllJson  CC=2  out:8
    diagnostics  CC=2  out:8
    downloadJson  CC=1  out:5
    summary  CC=2  out:8
  frontend.src.pages.MapEditor  [24 funcs]
    _parseFieldValue  CC=4  out:6
    _setBodyField  CC=8  out:2
    addAction  CC=2  out:6
    addFunc  CC=2  out:6
    addObject  CC=2  out:6
    addParam  CC=2  out:4
    applyMapMutation  CC=2  out:8
    clearServerHardwareEvents  CC=8  out:9
    deleteKey  CC=2  out:4
    editActionBodyField  CC=7  out:6
  frontend.src.pages.MapEditorObjectActionPanel  [2 funcs]
    _MotorRelativeParams  CC=1  out:3
    _motorArgLabel  CC=6  out:0
  frontend.src.pages.ScenarioFiles  [10 funcs]
    appendLog  CC=1  out:4
    cancelled  CC=4  out:4
    formatLogTime  CC=1  out:2
    isDirty  CC=1  out:4
    lastResponse  CC=3  out:5
    list  CC=1  out:0
    loadFiles  CC=2  out:5
    runScenario  CC=9  out:12
    saveFile  CC=4  out:9
    selectFile  CC=3  out:10
  frontend.src.utils.collapse-toggle-bridge  [2 funcs]
    isInIframe  CC=4  out:0
    postToParent  CC=4  out:8
  frontend.src.utils.encoder-navigation  [13 funcs]
    all  CC=6  out:2
    applyScrollToItems  CC=4  out:0
    createEncoderController  CC=11  out:7
    focusEncoderItem  CC=1  out:3
    getInteractiveItems  CC=6  out:4
    handleCancel  CC=1  out:2
    handleClick  CC=3  out:2
    handleEncoderCommand  CC=5  out:4
    handleScroll  CC=4  out:4
    handleSetActive  CC=3  out:1
  frontend.src.utils.hardware-activity-log  [4 funcs]
    createHardwareActivityLogEntry  CC=1  out:2
    loggedRef  CC=2  out:4
    prependHardwareActivityLogEntry  CC=1  out:2
    usePageOpenedLog  CC=2  out:5
  frontend.src.utils.hardware-api-retry  [2 funcs]
    attempt  CC=14  out:9
    sleep  CC=1  out:2
  frontend.src.utils.hardware-demo-identify  [11 funcs]
    adapters  CC=3  out:1
    buildDeviceStatus  CC=4  out:1
    buildStatusDetail  CC=3  out:1
    next  CC=3  out:1
    probeDemoDevices  CC=10  out:7
    probeOk  CC=1  out:1
    probePump  CC=2  out:4
    pumpOk  CC=3  out:1
    res  CC=3  out:1
    resolveFallbackDeviceId  CC=3  out:0
  frontend.src.utils.hardware-wizard-plan  [4 funcs]
    assertPlanData  CC=3  out:1
    extractWizardPlan  CC=1  out:3
    findPlanData  CC=7  out:0
    throwIfStackError  CC=7  out:2
  frontend.src.utils.hardware-wizard-steps  [3 funcs]
    _filterCandidatesByRole  CC=6  out:3
    _findBestCandidate  CC=6  out:3
    selectWizardProbeCandidate  CC=11  out:9
  frontend.src.utils.hardwareEventStream  [14 funcs]
    buildHardwareEventsWsUrl  CC=10  out:3
    commandName  CC=3  out:1
    data  CC=3  out:1
    id  CC=3  out:1
    matchesHardwareEventFilters  CC=9  out:4
    normalizeHardwareEvent  CC=8  out:5
    normalizeText  CC=2  out:1
    payload  CC=3  out:1
    peripheralId  CC=3  out:1
    resolveEventStatus  CC=6  out:0
  frontend.src.utils.mapEditorFuncHardwareSummary  [7 funcs]
    _asMap  CC=3  out:0
    apiBindingHint  CC=12  out:0
    objectMap  CC=3  out:2
    resolveNamedActionHardwareHint  CC=7  out:4
    resolveObjectActionHardwareHint  CC=6  out:2
    summarizeFuncToHardware  CC=11  out:7
    uniqueHints  CC=5  out:5
  frontend.src.utils.mapEditorIntegrationMeta  [10 funcs]
    _resolveHardwareAddress  CC=5  out:0
    _setOrDelete  CC=2  out:0
    firstBindingFromObjectMapping  CC=6  out:1
    nextValue  CC=2  out:2
    readIntegrationMeta  CC=11  out:2
    setApiEndpointField  CC=2  out:0
    setApiServiceField  CC=2  out:0
    setHardwareAddressField  CC=8  out:0
    setMetaField  CC=9  out:6
    source  CC=2  out:1
  frontend.src.utils.mapEditorMapShape  [6 funcs]
    cloneValue  CC=1  out:2
    ensureMapShape  CC=7  out:1
    fillMissingFields  CC=6  out:4
    isPlainObject  CC=3  out:2
    src  CC=2  out:1
    toPrettyJson  CC=1  out:2
  frontend.src.utils.mapEditorModel  [3 funcs]
    cloneDefaultMap  CC=1  out:2
    createInitialEditorState  CC=1  out:3
    ensureRequiredDefaultMappings  CC=14  out:3
  frontend.src.utils.mapEditorObjectActionEdits  [2 funcs]
    applyObjectActionBodyFieldMutation  CC=8  out:1
    parsePromptedFieldValue  CC=5  out:4
  frontend.src.utils.oqlGoals  [8 funcs]
    estimateOqlWaitMs  CC=9  out:8
    firstLineTitle  CC=6  out:2
    goalTitleFromLines  CC=10  out:2
    header  CC=2  out:4
    match  CC=5  out:1
    normalizeSource  CC=2  out:2
    splitOqlIntoGoalScripts  CC=9  out:8
    timeoutMsForOqlScript  CC=3  out:5
  frontend.src.utils.rbac.policy  [13 funcs]
    canConnectRoleAccessPath  CC=2  out:3
    canHostRoleAccessPath  CC=2  out:3
    isAdminConnectRole  CC=1  out:1
    isOperatorConnectRole  CC=4  out:1
    isReadOnlyConnectRole  CC=2  out:1
    matched  CC=5  out:1
    matchesPattern  CC=3  out:3
    normalizeConnectRole  CC=2  out:1
    normalizeHostRole  CC=2  out:1
    normalizePath  CC=6  out:4
  frontend.src.utils.scenarioFilesUrl  [3 funcs]
    _resolveUrlParts  CC=12  out:0
    buildScenarioFilesSearch  CC=5  out:6
    replaceScenarioFilesUrlState  CC=4  out:3
  frontend.src.utils.url-embed-config  [23 funcs]
    IFRAME_ONLY_SEARCH_PARAMS  CC=9  out:11
    applyParentContextPayload  CC=5  out:5
    applyUrlEmbedPatch  CC=7  out:7
    base  CC=3  out:3
    fromUser  CC=4  out:3
    href  CC=4  out:3
    mergeParentContext  CC=7  out:4
    mergeParentSearchIntoChildUrl  CC=9  out:11
    nextHref  CC=1  out:1
    parentSearch  CC=4  out:3
  frontend.src.utils.useSelectionCollapsePanel  [9 funcs]
    _makeCollapseToggleHandler  CC=8  out:3
    _useIframeCollapseToggle  CC=6  out:7
    cancelAutoCollapse  CC=2  out:2
    collapsed  CC=3  out:6
    expand  CC=1  out:5
    onMessage  CC=1  out:1
    scheduleCollapse  CC=3  out:6
    toggleCollapsed  CC=3  out:7
    useSelectionCollapsePanel  CC=11  out:17
  oqlos.config  [1 funcs]
    get_settings  CC=1  out:0
  oqlos.core._action_motor2  [30 funcs]
    _call_motor2_transport  CC=4  out:4
    _handle_motor2_reciprocating_setting  CC=2  out:4
    _motor2_acceleration_raw  CC=1  out:2
    _motor2_build_plan  CC=12  out:22
    _motor2_do_start  CC=4  out:10
    _motor2_do_stop  CC=4  out:3
    _motor2_effective_steps_per_second  CC=1  out:4
    _motor2_max_steps_per_second  CC=1  out:1
    _motor2_reciprocating_state  CC=2  out:3
    _motor2_set_state_value  CC=1  out:1
  oqlos.core._compare  [1 funcs]
    resolve_compare_chain  CC=3  out:4
  oqlos.core._cql_tokenizer  [10 funcs]
    _match_first  CC=3  out:1
    _parse_condition_value  CC=4  out:4
    _try_goto  CC=2  out:4
    _try_if_block  CC=4  out:11
    _try_if_else  CC=3  out:8
    _try_if_standalone  CC=2  out:1
    _try_min_max  CC=2  out:7
    _try_save  CC=5  out:7
    _try_set  CC=2  out:6
    _try_val  CC=2  out:4
  oqlos.core._cql_tree_builder  [1 funcs]
    _parse_action_line  CC=4  out:3
  oqlos.core._dsl_helpers  [12 funcs]
    _looks_like_lung_object  CC=1  out:2
    _looks_like_pump_object  CC=1  out:2
    _looks_like_sensor_object  CC=1  out:2
    _looks_like_valve_object  CC=2  out:3
    _map_action_value  CC=7  out:8
    _map_lung_action  CC=5  out:1
    _map_peripheral  CC=11  out:14
    _map_pump_action  CC=5  out:1
    _map_valve_action  CC=3  out:0
    _map_wait_action  CC=4  out:7
  oqlos.core._func_resolver  [4 funcs]
    _collect_function_definitions  CC=13  out:19
    _extract_func_name  CC=7  out:7
    _guard_recursion  CC=3  out:5
    _parse_func_call  CC=5  out:4
  oqlos.core._interpreter_actions  [30 funcs]
    _assert_json  CC=6  out:9
    _assert_sensor  CC=4  out:9
    _assert_status  CC=5  out:7
    _assert_valve  CC=5  out:8
    _coerce_expected_value  CC=7  out:8
    _compare_values  CC=10  out:8
    _do_sleep  CC=3  out:10
    _drop_command_token  CC=6  out:5
    _exec_set_wait  CC=3  out:7
    _extract_action_tokens  CC=5  out:4
  oqlos.core._line_parsers  [9 funcs]
    _extract_set_params  CC=7  out:13
    _parse_if_condition  CC=9  out:22
    _parse_inline_task  CC=5  out:7
    _parse_pump_line  CC=6  out:8
    _parse_set_line  CC=10  out:15
    _parse_task_part  CC=10  out:14
    _set_lung_step  CC=4  out:3
    _set_pump_step  CC=4  out:3
    _set_valve_step  CC=4  out:4
  oqlos.core._oql_adapter  [14 funcs]
    register  CC=1  out:1
    _cmd_to_actions  CC=2  out:3
    _fmt_value  CC=2  out:1
    _load_includes  CC=12  out:15
    _lower_call  CC=6  out:10
    _lower_set  CC=3  out:7
    _make_lower_minmax  CC=1  out:3
    _parse_macro_line  CC=8  out:10
    _resolve_include  CC=6  out:8
    _scenarios_root  CC=1  out:2
  oqlos.core.base  [5 funcs]
    send_event  CC=4  out:7
    emit  CC=5  out:3
    output_yaml  CC=4  out:2
    __init__  CC=2  out:1
    all  CC=3  out:3
  oqlos.core.cql_parser  [2 funcs]
    parse_cql  CC=2  out:6
    validate_cql  CC=5  out:5
  oqlos.core.executor  [6 funcs]
    _execute_validate_step  CC=7  out:7
    validate_goal  CC=5  out:3
    _resolve_compare  CC=1  out:2
    _resolve_name_or_attr  CC=4  out:6
    _safe_resolve  CC=14  out:21
    safe_eval_condition  CC=2  out:5
  oqlos.core.interpreter  [5 funcs]
    __init__  CC=1  out:5
    _build_script_result  CC=2  out:7
    _exec_flat_action  CC=6  out:6
    execute  CC=4  out:9
    parse  CC=3  out:5
  oqlos.core.motor2_runtime  [11 funcs]
    _coerce_int  CC=3  out:6
    _compute_motor2_cycles  CC=3  out:7
    _compute_motor2_speed  CC=4  out:6
    _normalize_motor2_direction  CC=4  out:2
    _pick  CC=4  out:0
    build_motor2_reciprocating_plan  CC=7  out:8
    motor2_acceleration_raw  CC=2  out:8
    motor2_max_steps_per_second  CC=2  out:3
    motor2_speed_for_duration  CC=1  out:9
    motor2_speed_raw  CC=1  out:5
  oqlos.core.oql_parser  [28 funcs]
    _check_unnamed_goals  CC=5  out:1
    _compact_duration  CC=2  out:3
    _expand_repeat_block_lines  CC=8  out:16
    _expand_repeat_blocks  CC=2  out:2
    _handle_block_header  CC=8  out:12
    _handle_modifier_cmd  CC=5  out:3
    _handle_set_name  CC=5  out:8
    _handle_top_level_line  CC=6  out:16
    _line_indent  CC=2  out:5
    _make_call_parser  CC=1  out:2
  oqlos.core.oql_versioning  [3 funcs]
    extract_declared_version  CC=3  out:4
    first_meaningful_line  CC=4  out:4
    resolve_oql_version  CC=2  out:3
  oqlos.core.parser  [5 funcs]
    _dispatch_simple_parser  CC=3  out:3
    _parse_runtime_line  CC=9  out:15
    _try_action_or_condition  CC=5  out:6
    parse_dsl_to_goal  CC=1  out:1
    parse_dsl_to_goal_with_issues  CC=13  out:21
  setup_hardware_and_run_oql  [6 funcs]
    detect_serial_devices  CC=12  out:7
    generate_env_content  CC=2  out:1
    load_env_file  CC=6  out:11
    main  CC=3  out:18
    run_oql_scenario  CC=8  out:24
    setup_env_file  CC=7  out:16

EDGES:
  setup_hardware_and_run_oql.setup_env_file → setup_hardware_and_run_oql.generate_env_content
  setup_hardware_and_run_oql.setup_env_file → examples.hardware.doctor-workflow.print
  setup_hardware_and_run_oql.setup_env_file → setup_hardware_and_run_oql.detect_serial_devices
  setup_hardware_and_run_oql.load_env_file → examples.hardware.doctor-workflow.print
  setup_hardware_and_run_oql.run_oql_scenario → examples.hardware.doctor-workflow.print
  setup_hardware_and_run_oql.main → setup_hardware_and_run_oql.run_oql_scenario
  frontend.src.hooks.useMapEditorSidebarAutoCollapse.useMapEditorSidebarAutoCollapse → frontend.src.hooks.useMapEditorSidebarAutoCollapse.applyAutoCollapse
  frontend.src.hooks.useUrlConfig.useUrlConfig → frontend.src.hooks.useUrlConfig.notifyParentChildReady
  frontend.src.hooks.useRailHoverPreview.useRailHoverPreview → frontend.src.hooks.useRailHoverPreview.cancelPanelClose
  frontend.src.hooks.useRailHoverPreview.useRailHoverPreview → frontend.src.hooks.useRailHoverPreview.previewExpand
  frontend.src.hooks.useRailHoverPreview.useRailHoverPreview → frontend.src.hooks.useRailHoverPreview.cancelRailOpen
  frontend.src.hooks.useRailHoverPreview.railEnter → frontend.src.hooks.useRailHoverPreview.cancelPanelClose
  frontend.src.hooks.useRailHoverPreview.railEnter → frontend.src.hooks.useRailHoverPreview.previewExpand
  frontend.src.hooks.useRailHoverPreview.railLeave → frontend.src.hooks.useRailHoverPreview.cancelRailOpen
  frontend.src.hooks.useRailHoverPreview.panelEnter → frontend.src.hooks.useRailHoverPreview.cancelPanelClose
  frontend.src.hooks.useRailHoverPreview.panelLeave → frontend.src.hooks.useRailHoverPreview.cancelRailOpen
  frontend.src.pages.MapEditorObjectActionPanel._MotorRelativeParams → frontend.src.pages.MapEditorObjectActionPanel._motorArgLabel
  frontend.src.pages.ScenarioFiles.isDirty → frontend.src.pages.ScenarioFiles.formatLogTime
  frontend.src.pages.ScenarioFiles.appendLog → frontend.src.pages.ScenarioFiles.formatLogTime
  frontend.src.pages.ScenarioFiles.cancelled → frontend.src.pages.ScenarioFiles.loadFiles
  frontend.src.pages.ScenarioFiles.cancelled → frontend.src.pages.ScenarioFiles.selectFile
  frontend.src.pages.ScenarioFiles.saveFile → frontend.src.pages.ScenarioFiles.appendLog
  frontend.src.pages.ScenarioFiles.runScenario → frontend.src.pages.ScenarioFiles.appendLog
  frontend.src.pages.ScenarioFiles.lastResponse → frontend.src.pages.ScenarioFiles.appendLog
  frontend.src.pages.MapEditor._setBodyField → frontend.src.pages.MapEditor._parseFieldValue
  frontend.src.pages.MapEditor.addObject → frontend.src.pages.MapEditor.applyMapMutation
  frontend.src.pages.MapEditor.name → frontend.src.pages.MapEditor.applyMapMutation
  frontend.src.pages.MapEditor.addParam → frontend.src.pages.MapEditor.applyMapMutation
  frontend.src.pages.MapEditor.editParamConversionField → frontend.src.pages.MapEditor.applyMapMutation
  frontend.src.pages.MapEditor.editParamConversionAlgorithm → frontend.src.pages.MapEditor.applyMapMutation
  frontend.src.pages.MapEditor.addAction → frontend.src.pages.MapEditor.applyMapMutation
  frontend.src.pages.MapEditor.addFunc → frontend.src.pages.MapEditor.applyMapMutation
  frontend.src.pages.MapEditor.renameKey → frontend.src.pages.MapEditor.applyMapMutation
  frontend.src.pages.MapEditor.nextName → frontend.src.pages.MapEditor.applyMapMutation
  frontend.src.pages.MapEditor.deleteKey → frontend.src.pages.MapEditor.applyMapMutation
  frontend.src.pages.MapEditor.editJsonField → frontend.src.pages.MapEditor.applyMapMutation
  frontend.src.pages.MapEditor.editObjectActionArg → frontend.src.pages.MapEditor.applyMapMutation
  frontend.src.pages.MapEditor.editObjectActionBodyField → frontend.src.pages.MapEditor.applyMapMutation
  frontend.src.pages.MapEditor.editActionBodyField → frontend.src.pages.MapEditor.applyMapMutation
  frontend.src.pages.MapEditor.editActionBodyField → frontend.src.pages.MapEditor._setBodyField
  frontend.src.pages.MapEditor.editMotorRuntimeConfig → frontend.src.pages.MapEditor.applyMapMutation
  frontend.src.pages.MapEditor.clearServerHardwareEvents → frontend.src.pages.MapEditor.loadRecentHardwareEvents
  frontend.src.pages.MapEditor.integrationMeta → frontend.src.pages.MapEditor.applyMapMutation
  frontend.src.pages.MapEditor.updateIntegrationMeta → frontend.src.pages.MapEditor.applyMapMutation
  frontend.src.pages.MapEditor.runAddForTab → frontend.src.pages.MapEditor.addObject
  frontend.src.pages.MapEditor.runAddForTab → frontend.src.pages.MapEditor.addParam
  frontend.src.pages.MapEditor.runAddForTab → frontend.src.pages.MapEditor.addAction
  frontend.src.pages.MapEditor.runAddForTab → frontend.src.pages.MapEditor.addFunc
  frontend.src.pages.HardwareStatus.summary → frontend.src.pages.HardwareStatus.downloadJson
  frontend.src.pages.HardwareStatus.adapters → frontend.src.pages.HardwareStatus.downloadJson
```

## API Stubs

*oqlos API v1.0.0 — auto-generated stubs from `openapi.yaml`.*

```python markpact:openapi path=openapi.yaml
# fastapi
def index_page() -> Response:  # Serve the firmware UI (index.html) at root
    "GET /"
def status() -> Response:  # GET /api/status
    "GET /api/status"
def editor_page() -> Response:  # Serve the scenario editor UI
    "GET /editor"
def health_check() -> Response:  # Health check endpoint for tests and frontend compatibility probes.
    "GET /firmware/api/v1/health"
def health_check() -> Response:  # Health check endpoint for tests and frontend compatibility probes.
    "GET /health"

# v1
def post_commands() -> Response:  # Command bus endpoint used by frontend.
    "POST /api/v1/commands"
def execute_scenario() -> Response:  # Execute a scenario file using oqlos runtime.
    "POST /api/v1/editor/execute"
def read_file_endpoint() -> Response:  # Read a file's content.
    "GET /api/v1/editor/file/{file_path:path}"
def write_file_endpoint() -> Response:  # Write content to a file (creates parent directories as needed).
    "POST /api/v1/editor/file/{file_path:path}"
def list_files() -> Response:  # List all entries in the scenarios directory.
    "GET /api/v1/editor/files"
def get_execution() -> Response:  # Get execution status
    "GET /api/v1/execution/by-id/{execution_id}"
def get_execution_logs() -> Response:  # Return execution logs for frontend polling.
    "GET /api/v1/execution/logs"
def execution_logs_stream() -> Response:  # Stream execution logs for terminal view
    "GET /api/v1/execution/logs/stream"
def get_execution_projection() -> Response:  # Return a lightweight execution projection used by the frontend polling fallback.
    "GET /api/v1/execution/projection"
def start_execution() -> Response:  # Start scenario execution
    "POST /api/v1/execution/start"
def get_execution_status() -> Response:  # Return textual logs and status for polling fallback when SSE is unavailable.
    "GET /api/v1/execution/status"
def execute_step() -> Response:  # Execute a single DSL step within the current (or new) execution.
    "POST /api/v1/execution/step"
def execution_stream() -> Response:  # Stream execution events for frontend polling fallback
    "GET /api/v1/execution/stream"
def hardware_health() -> Response:  # Return connectivity status for all hardware services.
    "GET /api/v1/hardware/health"
def hardware_identify() -> Response:  # Return full hardware identification: registry + live probe results.
    "GET /api/v1/hardware/identify"
def set_lung() -> Response:  # Start artificial lung reciprocating motion (tic249 stepper).
    "POST /api/v1/hardware/lung"
def stop_lung() -> Response:  # Emergency stop the artificial lung motor.
    "POST /api/v1/hardware/lung/stop"
def set_pump() -> Response:  # Directly set pump power % (for manual testing).
    "POST /api/v1/hardware/pump"
def read_sensor() -> Response:  # Read a sensor value directly from hardware.
    "GET /api/v1/hardware/sensor/{sensor_id}"
def set_valve() -> Response:  # Directly set a valve (for manual testing).
    "POST /api/v1/hardware/valve/{valve_id}"
def health_check() -> Response:  # Health check endpoint for tests and frontend compatibility probes.
    "GET /api/v1/health"
def get_log_stats() -> Response:  # Summary statistics from logs database.
    "GET /api/v1/logs/stats"
def reset_peripherals() -> Response:  # Reset all peripherals
    "POST /api/v1/peripherals/reset"
def get_peripheral() -> Response:  # Get specific peripheral
    "GET /api/v1/peripherals/{peripheral_id}"
def update_peripheral() -> Response:  # Update peripheral via PUT (for tests)
    "PUT /api/v1/peripherals/{peripheral_id}"
def set_peripheral() -> Response:  # Update peripheral (manual mode)
    "POST /api/v1/peripherals/{peripheral_id}/set"
def list_plugins() -> Response:  # List all registered hardware plugins.
    "GET /api/v1/plugins/"
def get_plugin_status() -> Response:  # Get overall status of all plugins.
    "GET /api/v1/plugins/status"
def validate_plugin_configs() -> Response:  # Validate configurations for multiple plugins.
    "POST /api/v1/plugins/validate"
def get_plugin_info() -> Response:  # Get information about a specific plugin.
    "GET /api/v1/plugins/{plugin_id}"
def connect_plugin() -> Response:  # Connect to a hardware plugin.
    "POST /api/v1/plugins/{plugin_id}/connect"
def disconnect_plugin() -> Response:  # Disconnect from a hardware plugin.
    "POST /api/v1/plugins/{plugin_id}/disconnect"
def execute_plugin_command() -> Response:  # Execute a command on a hardware plugin.
    "POST /api/v1/plugins/{plugin_id}/execute"
def get_plugin_health() -> Response:  # Get health status of a specific plugin.
    "GET /api/v1/plugins/{plugin_id}/health"
def fetch_protocol_steps() -> Response:  # Fetch protocol steps for preview.
    "GET /api/v1/protocol-steps/fetch"
def fetch_scenarios() -> Response:  # Fetch scenarios from backend DB or external JSON and normalize shape.
    "GET /api/v1/scenarios/fetch"
def register_dsl() -> Response:  # Register one or many scenarios defined as DSL strings.
    "POST /api/v1/scenarios/register-dsl"
def get_scenario() -> Response:  # Get specific scenario
    "GET /api/v1/scenarios/{scenario_id}"
def get_sim_state() -> Response:  # Get simulation state in list format
    "GET /api/v1/sim/state"
def get_state() -> Response:  # Get current system state
    "GET /api/v1/state"
def get_current_value() -> Response:  # Get current value for a parameter (single request, not streaming).
    "GET /api/v1/values/current"
def stream_values() -> Response:  # SSE endpoint for live value streaming.
    "GET /api/v1/values/stream"
def get_variables_alias() -> Response:  # Get variables (alias for fetch)
    "GET /api/v1/variables"
def fetch_variables() -> Response:  # Fetch variables (Peripheral State Table) from backend DB; tolerate dev HTML by returning [].
    "GET /api/v1/variables/fetch"

```

**Schemas**: `Error`, `HealthCheck`

## Test Contracts

*Scenarios as contract signatures — what the system guarantees.*

### Api (2)

**`API Integration Tests`**
- `GET /health` → `200`
- `GET /api/v1/status` → `200`
- `POST /api/v1/test` → `201`
- assert `status == ok`
- assert `response_time < 1000`

**`Auto-generated API Smoke Tests`**
- `GET /api/v1/state` → `200`
- `GET /api/v1/values/stream` → `200`
- `GET /api/v1/values/current` → `200`
- assert `status < 500`
- assert `response_time < 2000`
- detectors: FastAPIDetector, OpenAPIDetector, ConfigEndpointDetector

### Contract (1)

**`API Contract Tests`**
- `GET /api/v1/state` → `200`
- `GET /api/v1/values/stream` → `200`
- `GET /api/v1/values/current` → `200`
- assert `content_type == application/json`
- assert `schema_valid == true`
- assert `status < 500`
- perf `response_time_ms < <, 1000`

### Hardware (1)

**`Auto-generated from OQL/CQL Scenarios`**

### Integration (2)

**`Cross-Project Integration Tests`**

**`Auto-generated from Python Tests`**

## Intent

OqlOS — Operation Query Language runtime for hardware testing
