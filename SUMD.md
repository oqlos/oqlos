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
- [Code Analysis](#code-analysis)
- [Source Map](#source-map)
- [Call Graph](#call-graph)
- [API Stubs](#api-stubs)
- [Test Contracts](#test-contracts)
- [Intent](#intent)

## Metadata

- **name**: `oqlos`
- **version**: `0.1.13`
- **python_requires**: `>=3.10`
- **license**: {'text': 'Apache-2.0'}
- **ai_model**: `openrouter/qwen/qwen3-coder-next`
- **ecosystem**: SUMD + DOQL + testql + taskfile
- **openapi_title**: oqlos API v1.0.0
- **generated_from**: pyproject.toml, Taskfile.yml, testql(6), openapi(49 ep), app.doql.less, pyqual.yaml, goal.yaml, .env.example, Dockerfile, docker-compose.dev.yml, src(1 mod), project/(2 analysis files)

## Architecture

```
SUMD (description) → DOQL/source (code) → taskfile (automation) → testql (verification)
```

### DOQL Application Declaration (`app.doql.less`)

```less markpact:doql path=app.doql.less
// LESS format — define @variables here as needed

app {
  name: oqlos;
  version: 0.1.13;
}

dependencies {
  runtime: "fastapi>=0.110, uvicorn>=0.28, pydantic>=2.0, pydantic-settings>=2.2.0, pyserial>=3.5, pymodbus>=3.6, httpx>=0.25, nfo>=0.2.3, goal>=2.1.0, costs>=0.1.20, pfix>=0.1.60, paho-mqtt>=1.6.1, pluggy>=1.4, PyYAML>=6.0, testql>=0.2.0";
  dev: "pytest, pytest-asyncio, httpx, websockets>=13.0, goal>=2.1.0, costs>=0.1.20, pfix>=0.1.60, paho-mqtt>=1.6.1";
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

}

integration[name="modbus"] {
  type: hardware;
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

workflow[name="test"] {
  trigger: manual;
  step-1: run cmd=pytest -q;
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

deploy {
  target: docker-compose;
  compose_file: docker/docker-compose.dev.yml;
}

environment[name="local"] {
  runtime: docker-compose;
  env_file: .env;
  python_version: >=3.10;
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
  version: 0.1.13
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

- **base image**: `python:3.11-slim`
- **expose**: `8200`
- **entrypoint**: `["oqlos-server", "--host", "0.0.0.0", "--port", "8200"]`

### Docker Compose (`docker-compose.dev.yml`)

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

## Code Analysis

### `project/map.toon.yaml`

```toon markpact:analysis path=project/map.toon.yaml
# oqlos | 149f 26789L | python:144,shell:3,css:1,less:1 | 2026-05-06
# stats: 711 func | 157 cls | 149 mod | CC̄=4.5 | critical:66 | cycles:0
# alerts[5]: CC migrate_v2_to_v4=55; CC parse_oql=49; CC _cmd_to_actions=37; CC _analyze_firmware_access=25; CC hardware_identify=24
# hotspots[5]: main fan=26; parse_oql fan=23; migrate_v2_to_v4 fan=23; main fan=22; hardware_identify fan=19
# evolution: baseline
# Keys: M=modules, D=details, i=imports, e=exports, c=classes, f=functions, m=methods
M[149]:
  app.doql.css,165
  app.doql.less,223
  examples/hardware/doctor-workflow.sh,53
  oqlos/__init__.py,4
  oqlos/api/__init__.py,18
  oqlos/api/editor.py,127
  oqlos/api/execution.py,355
  oqlos/api/hardware.py,616
  oqlos/api/logs.py,46
  oqlos/api/main.py,224
  oqlos/api/peripherals.py,71
  oqlos/api/plugins.py,145
  oqlos/api/scenarios.py,252
  oqlos/api/state.py,371
  oqlos/api/utils/__init__.py,1
  oqlos/api/utils/execution_ctrl.py,63
  oqlos/api/version.py,25
  oqlos/config.py,116
  oqlos/core/__init__.py,1
  oqlos/core/_compare.py,41
  oqlos/core/_cql_tokenizer.py,404
  oqlos/core/_cql_tree_builder.py,162
  oqlos/core/_dsl_helpers.py,133
  oqlos/core/_firmware_executor.py,202
  oqlos/core/_func_resolver.py,97
  oqlos/core/_interpreter_actions.py,772
  oqlos/core/_line_parsers.py,247
  oqlos/core/_oql_adapter.py,490
  oqlos/core/_sensor_evaluator.py,146
  oqlos/core/_value_normalizers.py,127
  oqlos/core/base.py,321
  oqlos/core/cql_parser.py,478
  oqlos/core/executor.py,384
  oqlos/core/interpreter.py,666
  oqlos/core/oql_parser.py,667
  oqlos/core/oql_versioning.py,73
  oqlos/core/parser.py,184
  oqlos/core/safe_eval.py,139
  oqlos/core/state.py,125
  oqlos/dsl/__init__.py,19
  oqlos/dsl/schema.py,296
  oqlos/hardware/__init__.py,18
  oqlos/hardware/config_paths.py,42
  oqlos/hardware/config_schema.py,146
  oqlos/hardware/control_proxy.py,529
  oqlos/hardware/discovery.py,233
  oqlos/hardware/drivers/__init__.py,6
  oqlos/hardware/drivers/gpio.py,90
  oqlos/hardware/drivers/mqtt.py,120
  oqlos/hardware/drivers/spi.py,93
  oqlos/hardware/firmware_adapter.py,468
  oqlos/hardware/gateway.py,416
  oqlos/hardware/peripheral_mapping.py,139
  oqlos/hardware/plugin_gateway.py,372
  oqlos/hardware/plugins/__init__.py,48
  oqlos/hardware/plugins/_shared.py,62
  oqlos/hardware/plugins/base.py,371
  oqlos/hardware/plugins/lung.py,338
  oqlos/hardware/plugins/modbus.py,302
  oqlos/hardware/plugins/motor.py,397
  oqlos/hardware/plugins/piadc.py,273
  oqlos/hardware/plugins/registry.py,333
  oqlos/hardware/protocol.py,61
  oqlos/hardware/registry.py,50
  oqlos/ide/__init__.py,1
  oqlos/models/__init__.py,1
  oqlos/models/dsl_models.py,88
  oqlos/models/execution.py,23
  oqlos/models/peripheral.py,34
  oqlos/models/scenario.py,36
  oqlos/reporters/__init__.py,7
  oqlos/reporters/html_report.py,267
  oqlos/reporters/json_reporter.py,131
  oqlos/reporters/junit.py,87
  oqlos/shared/__init__.py,1
  oqlos/shared/_endpoint_helpers.py,34
  oqlos/shared/config_factory.py,85
  oqlos/shared/event_server.py,172
  oqlos/shared/event_store.py,78
  oqlos/shared/file_ops.py,109
  oqlos/shared/logger.py,24
  oqlos/shared/logs_query.py,146
  oqlos/shared/release_version.py,126
  oqlos/shared/version_endpoint.py,67
  oqlos/tools/__init__.py,1
  oqlos/tools/cql_cli/__init__.py,61
  oqlos/tools/cql_cli/commands.py,179
  oqlos/tools/cql_cli/main.py,385
  oqlos/tools/cql_cli/preflight.py,329
  oqlos/tools/cql_cli/utils.py,150
  oqlos/tools/cql_cli.py,58
  oqlos/tools/hardware_diagnose/__init__.py,74
  oqlos/tools/hardware_diagnose/__main__.py,169
  oqlos/tools/hardware_diagnose/benchmark.py,56
  oqlos/tools/hardware_diagnose/calibration.py,93
  oqlos/tools/hardware_diagnose/discovery.py,100
  oqlos/tools/hardware_diagnose/doctor.py,765
  oqlos/tools/hardware_diagnose/health.py,109
  oqlos/tools/hardware_diagnose/modbus_probe.py,260
  oqlos/tools/hardware_diagnose/report.py,64
  oqlos/tools/hardware_diagnose/shell.py,139
  oqlos/tools/hardware_diagnose.py,37
  oqlos/tools/plugin_cli.py,344
  oqlos/tools/xml_import/__init__.py,18
  oqlos/tools/xml_import/_utils.py,102
  oqlos/tools/xml_import/generators.py,443
  oqlos/tools/xml_import/models.py,91
  oqlos/tools/xml_import/parser.py,176
  oqlos/utils/__init__.py,4
  oqlos/utils/sample_data.py,74
  project.sh,43
  scripts/fix_brackets_to_v4.py,96
  scripts/hardware-check.sh,341
  scripts/migrate_to_v4.py,342
  scripts/oql_v2_to_v4_migrate_db.py,629
  scripts/oql_v2_validator.py,317
  scripts/oql_v4_validator.py,363
  scripts/scenarios_export.py,297
  setup_hardware_and_run_oql.py,334
  tests/firmware/test_control_proxy.py,130
  tests/firmware/test_dsl_parser_runtime.py,144
  tests/firmware/test_firmware.py,10
  tests/firmware/test_hardware_discovery.py,32
  tests/firmware/test_hardware_doctor.py,287
  tests/firmware/test_hardware_health.py,44
  tests/firmware/test_hardware_identify.py,145
  tests/firmware/test_lung_integration.py,282
  tests/firmware/test_lung_plugin_reciprocate.py,76
  tests/firmware/test_modbus_discovery.py,90
  tests/firmware/test_modbus_probe_cli.py,130
  tests/firmware/test_motor_plugin.py,74
  tests/firmware/test_normalize_scenario.py,200
  tests/firmware/test_parser_cycle.py,53
  tests/firmware/test_plugin_gateway_env.py,65
  tests/firmware/test_plugin_health.py,248
  tests/firmware/test_runtime_command_payload.py,16
  tests/firmware/test_safe_eval.py,244
  tests/firmware/test_tokenizer_extended.py,194
  tests/test_core.py,552
  tests/test_cql_cli.py,371
  tests/test_cql_inline_regressions.py,74
  tests/test_cql_scenarios.py,88
  tests/test_dsl_schema.py,20
  tests/test_oql_dry_run_regressions.py,62
  tests/test_oql_parser_v3.py,427
  tests/test_oql_scenarios.py,74
  tests/test_reporting.py,46
  tests/verify_block_if.py,61
  tests/verify_loops.py,34
D:
  oqlos/__init__.py:
  oqlos/api/__init__.py:
  oqlos/api/editor.py:
    e: _safe_path,list_files,read_file_endpoint,write_file_endpoint,execute_scenario,FileInfo,FileContent,ExecutionRequest
    FileInfo:
    FileContent:
    ExecutionRequest:
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
    e: _read_text_file,_board_model,_is_raspberry_pi_host,_os_release,_in_container,_selected_hardware_platform,_selected_piadc_platform,_detect_runtime_platform,_local_ads1115_probe_allowed,_scan_usb_devices,_probe_tic249,_probe_dri0050,_probe_i2c_ads1115,_probe_modbus_rtu,_probe_all_hardware,_collect_hardware_diagnostics,_is_plugin_compatible,_needs_live_scan,_unhealthy_plugin_ids,_modbus_health_is_no_response,_probe_selected_hardware,set_hardware_gateway,_gw,hardware_health,hardware_identify,set_valve,set_pump,read_sensor,set_lung,stop_lung,disable_lung
    _read_text_file(path)
    _board_model()
    _is_raspberry_pi_host()
    _os_release()
    _in_container()
    _selected_hardware_platform()
    _selected_piadc_platform()
    _detect_runtime_platform()
    _local_ads1115_probe_allowed()
    _scan_usb_devices()
    _probe_tic249(usb_devices)
    _probe_dri0050(usb_devices)
    _probe_i2c_ads1115()
    _probe_modbus_rtu()
    _probe_all_hardware(ids)
    _collect_hardware_diagnostics()
    _is_plugin_compatible(health_entry)
    _needs_live_scan(health)
    _unhealthy_plugin_ids(health)
    _modbus_health_is_no_response(health_entry)
    _probe_selected_hardware(ids)
    set_hardware_gateway(gw)
    _gw()
    hardware_health()
    hardware_identify(scan)
    set_valve(valve_id;value)
    set_pump(power_pct)
    read_sensor(sensor_id)
    set_lung(steps;speed;cycles;pause)
    stop_lung()
    disable_lung()
  oqlos/api/logs.py:
    e: _get_service,get_logs,get_log_stats
    _get_service()
    get_logs(level;function;module;q;environment;limit;offset)
    get_log_stats()
  oqlos/api/main.py:
    e: _app_lifespan,_initialize_runtime_dependencies,index_page,editor_page,health_check,status,websocket_endpoint,_parse_server_args,run
    _app_lifespan(_)
    _initialize_runtime_dependencies()
    index_page()
    editor_page()
    health_check()
    status()
    websocket_endpoint(websocket)
    _parse_server_args()
    run()
  oqlos/api/peripherals.py:
    e: get_peripheral,update_peripheral,set_peripheral,reset_peripherals
    get_peripheral(peripheral_id)
    update_peripheral(peripheral_id;update_data)
    set_peripheral(peripheral_id;value;mode)
    reset_peripherals()
  oqlos/api/plugins.py:
    e: ensure_plugins_initialized,list_plugins,get_plugin_status,get_plugin_info,get_plugin_health,connect_plugin,disconnect_plugin,execute_plugin_command,validate_plugin_configs
    ensure_plugins_initialized()
    list_plugins()
    get_plugin_status()
    get_plugin_info(plugin_id)
    get_plugin_health(plugin_id)
    connect_plugin(plugin_id;config)
    disconnect_plugin(plugin_id)
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
  oqlos/core/_compare.py:
    e: resolve_compare,resolve_compare_chain
    resolve_compare(left;op;right)
    resolve_compare_chain(node;resolve_value)
  oqlos/core/_cql_tokenizer.py:
    e: _make_args_parser,_make_keyword_parser,_make_method_parser,_match_first,_parse_condition_value,_try_arrow_action,_try_task,_try_save,_try_set,_try_condition_range,_try_condition_cmp,_try_if_else,_try_if_block,_try_if_fail_block,_try_if_standalone,_try_else_standalone,_try_min_max,_try_val,_try_loop_start,_try_repeat_start,_try_repeat_stop,_try_var,_try_func,_try_sample,_try_api,_try_goto,_try_save_ws
    _make_args_parser(regex;kind)
    _make_keyword_parser(regex;kind)
    _make_method_parser(regex;kind)
    _match_first(line)
    _parse_condition_value(raw_value)
    _try_arrow_action(line;stripped)
    _try_task(line;stripped)
    _try_save(line;stripped)
    _try_set(line;stripped)
    _try_condition_range(line;stripped)
    _try_condition_cmp(line;stripped)
    _try_if_else(line;stripped)
    _try_if_block(line;stripped)
    _try_if_fail_block(line;stripped)
    _try_if_standalone(line;stripped)
    _try_else_standalone(line;stripped)
    _try_min_max(line;stripped)
    _try_val(line;stripped)
    _try_loop_start(line;stripped)
    _try_repeat_start(line;stripped)
    _try_repeat_stop(line;stripped)
    _try_var(line;stripped)
    _try_func(line;stripped)
    _try_sample(line;stripped)
    _try_api(line;stripped)
    _try_goto(line;stripped)
    _try_save_ws(line;stripped)
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
    FirmwareExecutor: __init__(6),_get_firmware(0),resolve_peripheral_id(1),normalize_peripheral_value(2),refresh_sensors_from_firmware(1),execute_firmware_action(2),_execute_plugin_action(2),_execute_legacy_firmware_action(2),exec_set_peripheral(2)  # Executes hardware actions via plugin gateway or legacy firmw
  oqlos/core/_func_resolver.py:
    e: _collect_function_definitions,_extract_func_name,_guard_recursion,_parse_func_call
    _collect_function_definitions(lines)
    _extract_func_name(line;indent)
    _guard_recursion(func_name;call_stack)
    _parse_func_call(line;step_counter;steps;func_defs;indent;call_stack;parse_line_fn)
  oqlos/core/_interpreter_actions.py:
    e: _extract_action_tokens,_drop_command_token,_coerce_expected_value,_compare_values,_get_nested_value,_record_failure,_mark_success,_normalize_bool,_lookup_peripheral_state,_mock_api_response,exec_action_task,exec_action_save,parse_wait_secs,exec_action_wait,_do_sleep,exec_action_min_max,exec_action_val,exec_action_log,exec_action_error,exec_action_else,exec_action_sample,_resolve_numeric_token,_func_avg,_func_sum,_func_min,_func_max,_func_sub,_func_div,_func_mul,_func_add,exec_action_func,exec_action_goto,exec_action_api,exec_action_expect,_assert_status,_assert_json,_assert_sensor,_assert_valve,exec_action_assert,exec_action_shell,exec_action_var_set,exec_action_condition,exec_action_if_fail_block,exec_action_if_block,exec_action_loop_block,exec_action_set,_exec_set_wait,exec_action_action
    _extract_action_tokens(text)
    _drop_command_token(act)
    _coerce_expected_value(value)
    _compare_values(actual;operator;expected)
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
    _func_min(values)
    _func_max(values)
    _func_sub(values)
    _func_div(values;interp;target)
    _func_mul(values)
    _func_add(values)
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
    exec_action_set(interp;act)
    _exec_set_wait(interp;act;value)
    exec_action_action(interp;act)
  oqlos/core/_line_parsers.py:
    e: _parse_task_part,_parse_pump_line,_set_valve_step,_set_pump_step,_set_lung_step,_parse_set_line,_parse_inline_task,_parse_action_line,_parse_if_condition
    _parse_task_part(part;step_counter)
    _parse_pump_line(line;step_counter)
    _set_valve_step(peripheral;value_raw;step_counter;line)
    _set_pump_step(peripheral;value_raw;step_counter;line)
    _set_lung_step(peripheral;value_raw;step_counter;line)
    _parse_set_line(line;step_counter)
    _parse_inline_task(line;step_counter;steps)
    _parse_action_line(line;step_counter;steps)
    _parse_if_condition(line;step_counter;steps)
  oqlos/core/_oql_adapter.py:
    e: _fmt_value,_scenarios_root,_resolve_include,_substitute_args,_load_includes,_cmd_to_actions,_parse_macro_line,is_flat_oql,oql_doc_to_cql,_split_device_field,parse_flat_oql,_MacroRegistry
    _MacroRegistry: __init__(0),register(1),get(1)  # Collect ``MACRO`` definitions (raw body lines) from the root
    _fmt_value(value;unit)
    _scenarios_root()
    _resolve_include(path;base)
    _substitute_args(raw;args)
    _load_includes(doc;macros;base;seen)
    _cmd_to_actions(cmd;macros;visiting)
    _parse_macro_line(raw_line;ln;args)
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
    InterpreterOutput: __init__(3),emit(2),_broadcast_event(2),info(1),ok(1),fail(1),warn(1),error(1),step(2),output_yaml(0)  # Collects interpreter output lines for display or testing, an
    BaseInterpreter: __init__(4),parse(2),execute(1),run(2),run_file(1),strip_comments(1)  # Abstract base for language interpreters.
    EventBridge: __init__(1),connect(0),disconnect(0),send_event(2),connected(0)  # Optional WebSocket bridge to DSL Event Server (port 8104).
  oqlos/core/cql_parser.py:
    e: parse_cql,_collect_all_goals,_validate_intervals,validate_cql,_ParseState
    _ParseState: __init__(2),parse(0),_peek_next_significant_indent(0),_flush_pending_inline_if(0),_attach_pending_inline_if(2),_get_line_info(0),_process_line(0),_try_skip_block(2),_try_intervals_block(3),_try_top_level(3),_handle_scenario(1),_handle_scenario_attrs(1),_handle_goal(3),_handle_goal_attrs(1),_handle_step(1),_init_block_stack(0),_add_action_to_parent(1),_append_nested_action(1),_append_loop_action(1),_pop_block_with_warning(2),_handle_block_control(1),_handle_else_block(0),_try_handle_structure_levels(3),_handle_inline_if_logic(2),_handle_action_dispatch(2),_try_hierarchy(3)  # Encapsulates the parsing state to simplify the main loop.
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
    CqlInterpreter: __init__(10),sensor_values(0),sensor_values(1),_firmware(0),_firmware(1),_firmware_url(0),_firmware_url(1),_coerce_float(1),_resolve_peripheral_id(1),_get_pump_flow_full_scale_lpm(0),_normalize_pump_power(1),_normalize_valve_value(1),_normalize_lung_value(1),parse(2),_print_header(2),_collect_warnings(2),_run_validation_mode(3),_collect_all_goals(1),_execute_single_goal(2),_execute_all_goals(1),_build_script_result(2),execute(1),_execute_step(2),_execute_action(1),_exec_flat_action(1),_do_sleep(2),_normalize_peripheral_value(2),_coerce_generic_peripheral_value(1),_exec_set_peripheral(2),_get_firmware(0),_execute_firmware_action(2),_execute_plugin_action(2),_execute_legacy_firmware_action(2),_refresh_sensors_from_firmware(0),_auto_mock_sensor(3),_compare_sensor(3),_resolve_sensor_value(1),_resolve_delta_sensor_value(1),_resolve_windowed_delta_sensor_value(2),_extract_window_seconds(1),_resolve_condition_rhs(3),_evaluate_resolved_condition(0),_eval_condition_clause(2),_evaluate_inline_condition_expression(1),_tokenize_condition_expression(1),_aggregate_condition_results(2),_apply_connector(3),_finalize_condition_result(4),_evaluate_condition(1)  # CQL interpreter with three modes:
  oqlos/core/oql_parser.py:
    e: to_num,parse_duration,duration_to_ms,_unescape,tokenize,_require,_split_value_unit,parse_SET,parse_GET,parse_WAIT,parse_IF_DELTA,parse_SAVE,parse_CHECK,parse_IF,parse_MIN,parse_MAX,parse_SAMPLE,parse_LOG,parse_ERROR,parse_CORRECT,parse_CALL,parse_INCLUDE,parse_FUNC_CALL,parse_REPEAT,parse_oql,format_doc,OqlCmd,OqlBlock,OqlDoc
    OqlCmd: __repr__(0)  # A single command line inside a block.
    OqlBlock:  # A named block: ``GOAL``, ``CONFIG``, or ``MACRO``.
    OqlDoc: goals(0),configs(0),macros(0),funcs(0)  # Parsed OQL document.
    to_num(raw)
    parse_duration(token)
    duration_to_ms(token)
    _unescape(text)
    tokenize(rest)
    _require(tokens;minimum;cmd;ln;shape)
    _split_value_unit(tokens)
    parse_SET(tokens;ln;raw)
    parse_GET(tokens;ln;raw)
    parse_WAIT(tokens;ln;raw)
    parse_IF_DELTA(tokens;ln;raw)
    parse_SAVE(tokens;ln;raw)
    parse_CHECK(rest;ln;raw)
    parse_IF(rest;ln;raw)
    parse_MIN(tokens;ln;raw)
    parse_MAX(tokens;ln;raw)
    parse_SAMPLE(tokens;ln;raw)
    parse_LOG(tokens;ln;raw)
    parse_ERROR(tokens;ln;raw)
    parse_CORRECT(tokens;ln;raw)
    parse_CALL(tokens;ln;raw)
    parse_INCLUDE(tokens;ln;raw)
    parse_FUNC_CALL(tokens;ln;raw)
    parse_REPEAT(tokens;ln;raw)
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
    e: _normalize_name_list,_build_inferred_object_function_map,_build_inferred_param_unit_map,_merge_object_function_map,_merge_param_unit_map,get_default_dsl_schema,DslDialect,DslItem,DslFunctionBinding,DslParamUnitBinding,DslSchema
    DslDialect:  # Supported DSL dialect metadata.
    DslItem:  # A reusable schema item visible to editor clients.
    DslFunctionBinding:  # Object to function relationship used by visual builders.
    DslParamUnitBinding:  # Param to unit relationship used by visual builders.
    DslSchema:  # Complete editor schema shared by GUI and runtime tooling.
    _normalize_name_list(values)
    _build_inferred_object_function_map(objects;functions)
    _build_inferred_param_unit_map(params;units)
    _merge_object_function_map(explicit_map;inferred_map)
    _merge_param_unit_map(explicit_map;inferred_map)
    get_default_dsl_schema()
  oqlos/hardware/__init__.py:
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
    e: _float_from_env,candidate_oqlos_bases,is_oqlos_unavailable,oqlos_error_detail,normalize_modbus_valve_id,resolve_modbus_target,resolve_pump_target,resolve_lung_target,resolve_piadc_target,resolve_diagnostic_target,extract_command_failure,OqlosHardwareProxyConfig,HardwareProxyError,OqlosHardwareProxy
    OqlosHardwareProxyConfig: __post_init__(0),from_env(2)
    HardwareProxyError: __init__(2)  # Error raised by the OqlOS hardware proxy layer.
    OqlosHardwareProxy: __init__(1),candidate_bases(0),proxy_info(0),close(0),_get_client(0),_proxy_oqlos(1),_proxy_oqlos_request(2),health(0),identify(0),peripheral_status(1),diagnostic_command(3),_load_peripheral_status(1),_execute_diagnostic_command(5),_unavailable_health_payload(2),_unavailable_identify_payload(1),_unavailable_peripheral_payload(3),_unavailable_command_payload(6)  # Proxy and command mapper for runtime hardware control via Oq
    _float_from_env(env;key;default)
    candidate_oqlos_bases(api_base)
    is_oqlos_unavailable(exc)
    oqlos_error_detail(exc)
    normalize_modbus_valve_id(raw)
    resolve_modbus_target(command;args)
    resolve_pump_target(command;args)
    resolve_lung_target(command;args)
    resolve_piadc_target(command;args)
    resolve_diagnostic_target(peripheral;command;args)
    extract_command_failure(result)
  oqlos/hardware/discovery.py:
    e: _unique_preserving_order,list_serial_ports,_build_probe_candidates,_make_pymodbus_fallback_result,_make_probe_success_result,_make_probe_failure_result,_try_modbus_connection,probe_waveshare_modbus
    _unique_preserving_order(values)
    list_serial_ports()
    _build_probe_candidates(ports;preferred_port;preferred_baud;preferred_parity)
    _make_pymodbus_fallback_result(first_port)
    _make_probe_success_result(port_meta;serial_port;baudrate;parity)
    _make_probe_failure_result(first_port;last_error)
    _try_modbus_connection(serial_port;baudrate;parity;timeout)
    probe_waveshare_modbus(preferred_port;preferred_baud;preferred_parity;timeout)
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
    e: _parse_numeric,FirmwareAdapter
    FirmwareAdapter: __init__(3),_get_client(0),close(0),_get_lung_motor_url(0),is_available(0),_resolve_peripheral(1),_raise_if_rejected(2),set_peripheral(2),pump_off(1),pump_set(2),valve_open(1),valve_close(1),reset_peripherals(0),read_state(0),read_sensor(1),read_all_sensors(0),_resolve_dispatch_target(3),_handle_lung_action(4),_handle_valve_action(4),_handle_pump_action(4),_handle_common_action(3),_execute_method(4),dispatch_action(3)  # HTTP bridge between CQL interpreter and firmware simulator.
    _parse_numeric(s)
  oqlos/hardware/gateway.py:
    e: _PiAdcAdapter,_DRI0050MotorAdapter,_Tic249LungAdapter,_ModbusAdapter,HardwareGateway
    _PiAdcAdapter: __init__(1),read_channel(1),read_sensor(1)  # Reads pressure / analog sensors via piadc REST API (ADS1115)
    _DRI0050MotorAdapter: __init__(1),set_speed(1),_stop(0),status(0)  # Controls the pump motor via rpi-motor-DRI0050 REST API (DFRo
    _Tic249LungAdapter: __init__(1),reciprocate(4),stop(0),move(2),energize(1),status(0)  # Controls the artificial lung stepper motor via rpi-motor-tic
    _ModbusAdapter: __init__(5),set_coil(2),_set_coil_rtu(3),_set_coil_tcp(2),set_valve(2)  # Controls valves via Modbus RTU over RS485 (Waveshare Modbus 
    HardwareGateway: __init__(1),is_real(0),set_valve(2),set_pump(1),read_sensor(1),set_lung(4),stop_lung(0),health(0)  # Single entry-point for all physical hardware I/O.
  oqlos/hardware/peripheral_mapping.py:
    e: resolve_target_to_plugin,register_custom_mapping,get_all_mappings,generate_dynamic_valve_mappings
    resolve_target_to_plugin(target)
    register_custom_mapping(target;plugin_id)
    get_all_mappings()
    generate_dynamic_valve_mappings(max_valve_count)
  oqlos/hardware/plugin_gateway.py:
    e: PluginHardwareGateway
    PluginHardwareGateway: __init__(2),_load_hardware_schema(1),_parse_plugin_configs(1),_apply_env_overrides(0),ensure_initialized(0),_initialize_plugins(0),is_real(0),set_valve(2),set_pump(1),read_sensor(1),set_lung_result(4),set_lung(4),stop_lung(0),disable_lung(0),reload_configs(1),health(0)  # Simplified hardware gateway using plugin architecture.
  oqlos/hardware/plugins/__init__.py:
  oqlos/hardware/plugins/_shared.py:
    e: http_health_check,not_connected_health,health_check_exception,http_disconnect
    http_health_check(client;base_url;label)
    not_connected_health(label)
    health_check_exception(exc)
    http_disconnect(client;label)
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
    LungPlugin: __init__(1),validate_config(0),connect(0),disconnect(0),health_check(0),_runtime_status(0),_runtime_block_reason(1),_handle_reciprocate_http(1),_handle_reciprocate_usb(1),_handle_stop_http(0),_handle_stop_usb(0),_handle_move_http(1),_handle_move_usb(1),_handle_energize_http(1),_handle_energize_usb(1),_handle_status_http(0),_handle_status_usb(0),execute_command(2),get_capabilities(1)  # Plugin for Pololu Tic T249 stepper motor (artificial lung).
  oqlos/hardware/plugins/modbus.py:
    e: ModbusPlugin
    ModbusPlugin: __init__(1),validate_config(0),connect(0),disconnect(0),health_check(0),execute_command(2),_rtu_timeout(0),_device_id(0),get_capabilities(1)  # Plugin for Waveshare Modbus RTU IO 8CH valve controller.
  oqlos/hardware/plugins/motor.py:
    e: MotorPlugin
    MotorPlugin: __init__(1),validate_config(0),connect(0),disconnect(0),health_check(0),_base_url_is_local(0),_validate_power_pct(1),_handle_set_speed_http(2),_handle_set_speed_cli(2),_handle_set_speed_modbus(2),_handle_stop_http(1),_handle_stop_cli(1),_handle_stop_modbus(1),_handle_status_http(1),_handle_status_cli(1),_handle_status_modbus(1),execute_command(2),get_capabilities(1)  # Plugin for DFRobot DRI0050 PWM motor driver.
  oqlos/hardware/plugins/piadc.py:
    e: _read_text_file,_is_raspberry_pi_host,_requires_remote_rpi_hint,_resolve_sensor_channel,PiadcPlugin
    PiadcPlugin: __init__(1),validate_config(0),connect(0),disconnect(0),health_check(0),_read_blocker(0),execute_command(2),get_capabilities(1)  # Plugin for piADC (ADS1115) 16-bit ADC sensor.
    _read_text_file(path)
    _is_raspberry_pi_host()
    _requires_remote_rpi_hint(base_url;exc)
    _resolve_sensor_channel(sensor_id)
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
    e: _step_to_dict,report_json
    _step_to_dict(step)
    report_json(result)
  oqlos/reporters/junit.py:
    e: report_junit,JUnitReporter
    JUnitReporter: generate(2),_add_testcase(3)  # Generate JUnit XML from a ScriptResult.
    report_junit(result;suite_name)
  oqlos/shared/__init__.py:
  oqlos/shared/_endpoint_helpers.py:
    e: serve_html_page,make_collection_route
    serve_html_page(file_path)
    make_collection_route(route_name;get_collection)
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
    e: _ensure_safe_path,list_files,iter_entries,read_file,write_file,PathEscapeError
    PathEscapeError:  # Raised when a resolved path would escape the base directory.
    _ensure_safe_path(base;rel)
    list_files(base;pattern;recursive)
    iter_entries(base)
    read_file(base;rel)
    write_file(base;rel;content)
  oqlos/shared/logger.py:
    e: get_logger
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
    e: run_source,run_single_command,handle_list_command,execute_command_with_cleanup,_run_continuous_mode
    run_source(source;filename)
    run_single_command(command)
    handle_list_command(argv)
    execute_command_with_cleanup(args;result;yaml_output;quiet)
    _run_continuous_mode(args;quiet)
  oqlos/tools/cql_cli/main.py:
    e: create_file_parser,create_run_parser,create_hardware_parser,create_cmd_parser,run_file_mode,_create_interpreter,_run_interpreter_target,_fetch_scenario_source,_extract_scenario_source,_looks_like_html,_print_cli_error,_run_hardware_flags,run_hardware_mode,run_cmd_mode,_dispatch_to_mode,main,ScenarioFetchError
    ScenarioFetchError:  # Raised when an HTTP scenario target is not runnable OQL/CQL 
    create_file_parser()
    create_run_parser()
    create_hardware_parser(action)
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
    _dispatch_to_mode(argv)
    main()
  oqlos/tools/cql_cli/preflight.py:
    e: ensure_firmware_running,_is_firmware_running,_start_firmware_service,check_firmware_state,check_required_adapter,check_required_adapter_health,_health_status_is_ok,_emit_preflight_error,emit_preflight_success,_emit_yaml_preflight,_emit_text_preflight,preflight_hardware
    ensure_firmware_running(firmware_url)
    _is_firmware_running(firmware_url)
    _start_firmware_service(firmware_url)
    check_firmware_state(firmware_url;yaml_output;quiet)
    check_required_adapter(command;adapters;yaml_output;quiet)
    check_required_adapter_health(required_adapter;health;yaml_output;quiet)
    _health_status_is_ok(raw_status)
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
  oqlos/tools/cql_cli.py:
  oqlos/tools/hardware_diagnose/__init__.py:
    e: main
    main()
  oqlos/tools/hardware_diagnose/__main__.py:
    e: _print_list,_print_health,_print_calibrate,_print_benchmark,_print_detect,_print_doctor,_print_modbus_probe,main
    _print_list(url;as_json)
    _print_health(url;as_json)
    _print_calibrate(url;as_json)
    _print_benchmark(url;duration;as_json)
    _print_detect(url;as_json;config_path)
    _print_doctor(url;as_json;config_path;fix)
    _print_modbus_probe(_as_json;args)
    main()
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
    e: _usb_serial_only,_load_config_summary,_probe_modbus,_serial_port_owners,_canonical_device_path,_owners_for_configured_port,_extract_pids,_describe_pid,detect_hardware,_firmware_hostname,_add_issue,_modbus_config,_expected_modbus_params,_analyze_modbus_config,_analyze_firmware_access,_adapter_health_status,_health_status_is_ok,_analyze_serial_port_owners,_collect_repairs,build_doctor_report,apply_safe_fixes,_update_modbus_config,format_detection,_firmware_modbus_health_ok,_firmware_is_remote,_firmware_adapter_status,format_doctor
    _usb_serial_only(devices)
    _load_config_summary(config_path)
    _probe_modbus(probe_timeout)
    _serial_port_owners(devices)
    _canonical_device_path(device)
    _owners_for_configured_port(owners;configured_port)
    _extract_pids(text)
    _describe_pid(pid)
    detect_hardware(firmware_url)
    _firmware_hostname(firmware_url)
    _add_issue(issues)
    _modbus_config(config)
    _expected_modbus_params(modbus_probe)
    _analyze_modbus_config(detection;issues)
    _analyze_firmware_access(detection;issues)
    _adapter_health_status(health;adapter_id)
    _health_status_is_ok(raw_status)
    _analyze_serial_port_owners(detection;issues)
    _collect_repairs(issues)
    build_doctor_report(firmware_url)
    apply_safe_fixes(detection;repairs)
    _update_modbus_config(config_path;detected)
    format_detection(detection)
    _firmware_modbus_health_ok(detection)
    _firmware_is_remote(detection)
    _firmware_adapter_status(detection;adapter_id)
    format_doctor(report)
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
    e: _env_int,_env_int_list,_env_count_list,_env_str_list,_env_float,_split_values,_arg_str_list,_arg_int_list,_arg_count_list,_serials_from_env,add_modbus_probe_arguments,probe_options_from_args,run_modbus_probe_from_args,run_modbus_probe_from_env,run_modbus_probe,main
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
    e: _mode_symbol,_format_range,_mode_action,_emit_cql_output,_emit_cql_param,_emit_cql_sensor_param,_emit_dsl_output,_emit_dsl_param,_build_steps_from_op,_append_sensor_assertion,_build_validation_criteria,generate_dsl,_emit_dsl_test_run,_emit_dsl_sensors,_emit_dsl_metadata,generate_cql,_generate_cql_for_goal,generate_goals_json
    _mode_symbol(mode)
    _format_range(p)
    _mode_action(mode)
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
  oqlos/utils/sample_data.py:
    e: load_sample_scenarios
    load_sample_scenarios(state_manager)
  scripts/fix_brackets_to_v4.py:
    e: needs_migration,main
    needs_migration(text)
    main()
  scripts/migrate_to_v4.py:
    e: find_oql_files,has_version_header,extract_version,migrate_content,main,check_database
    find_oql_files(root_dir)
    has_version_header(content)
    extract_version(content)
    migrate_content(content;filename)
    main()
    check_database()
  scripts/oql_v2_to_v4_migrate_db.py:
    e: _fetch_json,_send_json,_extract_rows,_normalize_bracket_tokens,_to_v4_token,_bracket_tokens,_join_value_unit,_quote,_extract_num_unit,_merge_minmax_to_if,_rewrite_legacy_if,migrate_v2_to_v4,_validate_runtime,_pick_code,_build_write_payload,_build_write_url,main,MigrationResult
    MigrationResult:
    _fetch_json(url;timeout)
    _send_json(url;method;payload;timeout)
    _extract_rows(payload)
    _normalize_bracket_tokens(text)
    _to_v4_token(text)
    _bracket_tokens(text)
    _join_value_unit(value)
    _quote(value)
    _extract_num_unit(value)
    _merge_minmax_to_if(lines)
    _rewrite_legacy_if(lines)
    migrate_v2_to_v4(text)
    _validate_runtime(text;filename)
    _pick_code(row)
    _build_write_payload(row;migrated_code)
    _build_write_url(template;scenario_id)
    main()
  scripts/oql_v2_validator.py:
    e: _looks_like_html,_fetch_url,_extract_code_from_json,_build_api_fallback_urls,_load_source,_line_number,_validate_v2_structure,validate_oql_v2_legacy,main,Issue
    Issue:
    _looks_like_html(text)
    _fetch_url(url;timeout)
    _extract_code_from_json(data)
    _build_api_fallback_urls(url)
    _load_source(file_path;url)
    _line_number(idx)
    _validate_v2_structure(text)
    validate_oql_v2_legacy(text;source)
    main()
  scripts/oql_v4_validator.py:
    e: _looks_like_html,_fetch_url,_extract_code_from_json,_build_api_fallback_urls,_load_source,_line_number,_validate_structure,_validate_runtime,validate_oql_v4,main,Issue
    Issue:
    _looks_like_html(text)
    _fetch_url(url;timeout)
    _extract_code_from_json(data)
    _build_api_fallback_urls(url)
    _load_source(file_path;url)
    _line_number(lines;idx)
    _validate_structure(text)
    _validate_runtime(text;filename)
    validate_oql_v4(text;source)
    main()
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
  tests/firmware/test_control_proxy.py:
    e: run,proxy_with_client,test_health_falls_back_to_alternate_oqlos_port,test_identify_returns_unavailable_payload_after_connection_failures,test_diagnostic_command_returns_structured_failure_payload,test_peripheral_status_proxies_plugin_health,test_resolve_diagnostic_target_rejects_invalid_modbus_valve_id,FakeOqlosResponse
    FakeOqlosResponse: __init__(2),raise_for_status(0),json(0)
    run(coro)
    proxy_with_client(client)
    test_health_falls_back_to_alternate_oqlos_port()
    test_identify_returns_unavailable_payload_after_connection_failures()
    test_diagnostic_command_returns_structured_failure_payload()
    test_peripheral_status_proxies_plugin_health()
    test_resolve_diagnostic_target_rejects_invalid_modbus_valve_id()
  tests/firmware/test_dsl_parser_runtime.py:
    e: TestDslParserRuntime
    TestDslParserRuntime: test_parses_bracketed_task_lines_for_valve_14(0),test_parses_wait_step_from_builder_serialization(0),test_parses_dedicated_pump_command(0),test_parses_set_lines_for_valve_and_compressor(0),test_parses_if_condition_with_operator_between_brackets(0),test_expands_func_call_into_runtime_steps(0),test_reports_invalid_runtime_line_for_pompx_typo(0),test_accepts_pompa_with_suffix_as_real_pump_reference(0),test_accepts_set_pompa_alias(0)
  tests/firmware/test_firmware.py:
    e: test_placeholder,test_import
    test_placeholder()
    test_import()
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
  tests/firmware/test_hardware_identify.py:
    e: test_collect_hardware_diagnostics_exposes_ports,test_piadc_local_probe_is_skipped_on_non_rpi,test_platform_selection_can_force_generic_linux_probe,test_hardware_identify_includes_diagnostics,test_hardware_identify_reports_modbus_timeout_as_adapter_only,_FakeGateway,_ModbusTimeoutGateway
    _FakeGateway: health(0)
    _ModbusTimeoutGateway: health(0)
    test_collect_hardware_diagnostics_exposes_ports(monkeypatch)
    test_piadc_local_probe_is_skipped_on_non_rpi(monkeypatch)
    test_platform_selection_can_force_generic_linux_probe(monkeypatch)
    test_hardware_identify_includes_diagnostics(monkeypatch)
    test_hardware_identify_reports_modbus_timeout_as_adapter_only(monkeypatch)
  tests/firmware/test_lung_integration.py:
    e: TestLungDslHelpers,TestLungDslParser,TestLungExecutor,TestFirmwareAdapterLung,TestHardwareGatewayLung,TestCqlInterpreterLung
    TestLungDslHelpers: test_looks_like_lung_object(1),test_not_lung_object(0),test_map_peripheral_lung(0),test_map_lung_action_start(0),test_map_lung_action_stop(0),test_map_lung_action_default_cycles(0),test_map_action_value_lung(0)
    TestLungDslParser: test_parses_lung_set_command(0),test_parses_lung_task_command(0),test_parses_lung_stop(0)
    TestLungExecutor: _make_orchestrator(0),test_execute_lung_step_reciprocate(0),test_execute_lung_step_stop(0),test_execute_step_dispatches_set_lung(0)
    TestFirmwareAdapterLung: test_peripheral_map_lung(0),test_resolve_peripheral_lung(0),test_dispatch_lung_start(0),test_dispatch_lung_stop(0),test_set_peripheral_lung_start(0),test_set_peripheral_lung_stop(0)
    TestHardwareGatewayLung: test_set_lung_mock(0),test_stop_lung_mock(0)
    TestCqlInterpreterLung: test_dry_run_lung_action(0)
  tests/firmware/test_lung_plugin_reciprocate.py:
    e: _plugin_with_client,test_ready_false_does_not_block_reciprocate_start,_JsonResponse,_ReadyFalseClient
    _JsonResponse: __init__(2),json(0)
    _ReadyFalseClient: __init__(0),get(1),post(2)
    _plugin_with_client(client)
    test_ready_false_does_not_block_reciprocate_start()
  tests/firmware/test_modbus_discovery.py:
    e: _install_fake_pymodbus,test_probe_waveshare_modbus_detects_working_port,test_probe_waveshare_modbus_reports_adapter_only_when_no_response,_OkResponse,_ErrorResponse
    _OkResponse: isError(0)
    _ErrorResponse: isError(0)
    _install_fake_pymodbus(monkeypatch;responsive_port;responsive_baud;responsive_parity)
    test_probe_waveshare_modbus_detects_working_port(monkeypatch)
    test_probe_waveshare_modbus_reports_adapter_only_when_no_response(monkeypatch)
  tests/firmware/test_modbus_probe_cli.py:
    e: _install_fake_pymodbus,test_run_modbus_probe_returns_successful_read,test_run_modbus_probe_reports_unsupported_function,test_probe_options_from_args_override_environment,_OkResponse,_ErrorResponse
    _OkResponse: isError(0),__str__(0)
    _ErrorResponse: isError(0)
    _install_fake_pymodbus(monkeypatch)
    test_run_modbus_probe_returns_successful_read(monkeypatch)
    test_run_modbus_probe_reports_unsupported_function(monkeypatch)
    test_probe_options_from_args_override_environment(monkeypatch)
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
  tests/firmware/test_parser_cycle.py:
    e: TestParserCycleDetection
    TestParserCycleDetection: test_direct_circular_func_raises(0),test_self_referencing_func_raises(0),test_valid_func_call_works(0),test_max_func_depth_constant(0)
  tests/firmware/test_plugin_gateway_env.py:
    e: test_plugin_gateway_env_overrides_service_urls,test_plugin_gateway_env_overrides_modbus_params
    test_plugin_gateway_env_overrides_service_urls(monkeypatch)
    test_plugin_gateway_env_overrides_modbus_params(monkeypatch)
  tests/firmware/test_plugin_health.py:
    e: test_piadc_health_rejects_mock_mode,test_piadc_health_includes_uninitialized_service_reason,test_piadc_health_points_non_rpi_hosts_to_remote_service,test_lung_health_rejects_uninitialized_runtime,test_modbus_rtu_health_timeout_does_not_block_event_loop,test_modbus_rtu_uses_configured_device_id_for_health_and_writes,test_plugin_registry_health_checks_run_concurrently_with_timeout,_JsonResponse,_PiadcClient,_UninitializedPiadcClient,_FailingPiadcClient,_LungClient,_BlockingModbusClient,_OkModbusResult,_CapturingModbusClient
    _JsonResponse: __init__(2),json(0)
    _PiadcClient: get(1)
    _UninitializedPiadcClient: get(1)
    _FailingPiadcClient: get(1)
    _LungClient: get(1)
    _BlockingModbusClient: read_coils(0)
    _OkModbusResult: isError(0)
    _CapturingModbusClient: __init__(0),read_coils(0),write_coil(0)
    test_piadc_health_rejects_mock_mode()
    test_piadc_health_includes_uninitialized_service_reason()
    test_piadc_health_points_non_rpi_hosts_to_remote_service(monkeypatch)
    test_lung_health_rejects_uninitialized_runtime()
    test_modbus_rtu_health_timeout_does_not_block_event_loop()
    test_modbus_rtu_uses_configured_device_id_for_health_and_writes()
    test_plugin_registry_health_checks_run_concurrently_with_timeout(monkeypatch)
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
  tests/test_core.py:
    e: TestVariableStore,TestCqlParser,TestCqlValidator,TestCqlInterpreter,TestCqlExecuteMode,TestFirmwareAdapterUnit,TestEventStore
    TestVariableStore: test_set_get(0),test_interpolate_dollar(0),test_interpolate_braces(0),test_interpolate_missing(0)
    TestCqlParser: test_simple_metadata(0),test_parses_set_as_pump(0),test_parses_set_command_for_valve_and_compressor(0),test_simple_goals(0),test_simple_actions(0),test_connectgo_metadata(0),test_connectgo_intervals(0),test_connectgo_scenario(0),test_connectgo_goals(0),test_connectgo_steps(0),test_connectgo_arrow_action(0),test_connectgo_condition(0)
    TestCqlValidator: test_valid_document(0),test_empty_document(0),test_invalid_interval_ref(0)
    TestCqlInterpreter: test_dry_run_simple(0),test_dry_run_with_sensors(0),test_validate_mode(0),test_set_actions_store_variables(0),test_variables_saved(0)
    TestCqlExecuteMode: test_execute_mode_initializes_firmware(0),test_pump_flow_uses_env_scale(1),test_pump_flow_scale_can_be_overridden_in_config_block(1),test_dry_run_does_not_use_firmware(0),test_auto_mock_seeds_default_sensors(0),test_auto_mock_range_condition_passes(0),test_auto_mock_disabled(0)
    TestFirmwareAdapterUnit: _firmware_with_post_response(1),test_peripheral_map_completeness(0),test_sensor_map(0),test_parse_numeric(0),test_resolve_peripheral(0),test_dispatch_confirm_no_http(0),test_set_peripheral_pump_rejects_nested_failed_response(0),test_dispatch_pump_reports_hardware_rejection(0),test_dispatch_lung_falls_back_to_direct_service_on_404(1)
    TestEventStore: test_append_and_get(0),test_get_recent(0),test_get_by_correlation(0),test_clear(0),test_json_roundtrip(0),test_persistence(1)
  tests/test_cql_cli.py:
    e: test_cmd_executes_single_command,test_cmd_execute_aborts_when_hardware_is_unavailable,test_file_mode_still_executes_scenario,test_run_subcommand_executes_scenario_file,test_run_subcommand_fetches_scenario_url,test_fetch_scenario_source_rejects_editor_html,test_run_subcommand_reports_url_fetch_error,test_cmd_execute_mock_mode_error_suggests_dry_run_and_doctor,test_cmd_execute_blocks_when_required_adapter_health_is_bad,test_oqlctl_doctor_subcommand_dispatches_to_hardware_flags,test_oqlctl_status_flag_dispatches_without_file,test_result_payload_is_json_safe,_FakeInterpreter
    _FakeInterpreter: __init__(0),run(2)
    test_cmd_executes_single_command(monkeypatch)
    test_cmd_execute_aborts_when_hardware_is_unavailable(monkeypatch;capsys)
    test_file_mode_still_executes_scenario(monkeypatch;tmp_path)
    test_run_subcommand_executes_scenario_file(monkeypatch;tmp_path)
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
    e: test_tokenize_simple,test_tokenize_brackets_allow_spaces,test_tokenize_double_quoted_string,test_tokenize_single_quoted_string,test_tokenize_unclosed_quote_raises,test_tokenize_unclosed_bracket_raises,test_duration_to_ms,test_parse_minimal_goal,test_parse_metadata,test_parse_check_range,test_parse_check_negative_values,test_parse_sample_with_interval,test_parse_if_delta_signed_threshold,test_parse_unicode_identifiers,test_parse_bracketed_target_with_spaces,test_parse_bracketed_block_name,test_parse_rejects_unindented_command,test_parse_rejects_unknown_command,test_parse_v4_goal_requires_set_name,test_parse_v4_rejects_inline_goal_name,test_parse_v4_goal_name_from_set_name,test_parse_rejects_unsupported_oql_version,test_base_commands_list_matches_dispatcher,test_is_flat_oql_detects_new_syntax,test_is_flat_oql_rejects_legacy,test_adapter_produces_cql_goals,test_adapter_config_prefix,test_macro_call_expansion,test_unknown_macro_becomes_error_action,test_include_resolves_from_scenarios_root,test_include_missing_file_yields_error,test_check_with_correct_message,test_check_with_error_message,test_check_with_both_messages,test_correct_without_check_is_error,test_adapter_uses_custom_messages,test_adapter_if_delta_uses_custom_messages_and_delta_sensor
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
  tests/verify_block_if.py:
    e: test_block_if
    test_block_if()
  tests/verify_loops.py:
    e: test_loops
    test_loops()
```

## Source Map

*Top 1 modules by symbol density — signatures for LLM orientation.*

### `oqlos.config` (`oqlos/config.py`)

```python
def get_settings()  # CC=1, fan=0
class Settings:  # Application settings loaded from environment variables and .
```

## Call Graph

*440 nodes · 500 edges · 61 modules · CC̄=4.1*

### Hubs (by degree)

| Function | CC | in | out | total |
|----------|----|----|-----|-------|
| `print` *(in examples.hardware.doctor-workflow)* | 0 | 228 | 0 | **228** |
| `parse_oql` *(in oqlos.core.oql_parser)* | 49 ⚠ | 3 | 75 | **78** |
| `_cmd_to_actions` *(in oqlos.core._oql_adapter)* | 37 ⚠ | 3 | 58 | **61** |
| `format_doctor` *(in oqlos.tools.hardware_diagnose.doctor)* | 20 ⚠ | 2 | 44 | **46** |
| `format_detection` *(in oqlos.tools.hardware_diagnose.doctor)* | 16 ⚠ | 3 | 38 | **41** |
| `_analyze_firmware_access` *(in oqlos.tools.hardware_diagnose.doctor)* | 25 ⚠ | 1 | 34 | **35** |
| `oql_doc_to_cql` *(in oqlos.core._oql_adapter)* | 12 ⚠ | 2 | 30 | **32** |
| `probe_options_from_args` *(in oqlos.tools.hardware_diagnose.modbus_probe)* | 2 | 1 | 27 | **28** |

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/oqlos/oqlos
# generated in 0.20s
# nodes: 440 | edges: 500 | modules: 61
# CC̄=4.1

HUBS[20]:
  examples.hardware.doctor-workflow.print
    CC=0  in:228  out:0  total:228
  oqlos.core.oql_parser.parse_oql
    CC=49  in:3  out:75  total:78
  oqlos.core._oql_adapter._cmd_to_actions
    CC=37  in:3  out:58  total:61
  oqlos.tools.hardware_diagnose.doctor.format_doctor
    CC=20  in:2  out:44  total:46
  oqlos.tools.hardware_diagnose.doctor.format_detection
    CC=16  in:3  out:38  total:41
  oqlos.tools.hardware_diagnose.doctor._analyze_firmware_access
    CC=25  in:1  out:34  total:35
  oqlos.core._oql_adapter.oql_doc_to_cql
    CC=12  in:2  out:30  total:32
  oqlos.tools.hardware_diagnose.modbus_probe.probe_options_from_args
    CC=2  in:1  out:27  total:28
  oqlos.core.executor._safe_resolve
    CC=14  in:7  out:21  total:28
  oqlos.api.state._handle_start
    CC=13  in:0  out:27  total:27
  oqlos.api.hardware._probe_i2c_ads1115
    CC=14  in:1  out:25  total:26
  setup_hardware_and_run_oql.run_oql_scenario
    CC=8  in:1  out:24  total:25
  oqlos.shared.event_server.EventServer._handle_message
    CC=6  in:0  out:24  total:24
  oqlos.core.parser.parse_dsl_to_goal_with_issues
    CC=13  in:3  out:21  total:24
  oqlos.core._line_parsers._parse_if_condition
    CC=9  in:1  out:22  total:23
  oqlos.api.hardware._detect_runtime_platform
    CC=18  in:3  out:20  total:23
  oqlos.tools.hardware_diagnose.health.cmd_diagnose
    CC=6  in:2  out:20  total:22
  oqlos.api.hardware._scan_usb_devices
    CC=9  in:2  out:20  total:22
  oqlos.tools.cql_cli.commands.handle_list_command
    CC=7  in:1  out:21  total:22
  oqlos.tools.hardware_diagnose.shell._dispatch_command
    CC=6  in:1  out:21  total:22

MODULES:
  examples.hardware.doctor-workflow  [1 funcs]
    print  CC=0  out:0
  oqlos.api.execution  [9 funcs]
    _build_step_labels  CC=6  out:2
    _current_projection  CC=5  out:3
    _register_dsl_scenario  CC=3  out:4
    _resolve_current_index  CC=10  out:1
    _resolve_step_label  CC=11  out:2
    execution_logs_stream  CC=1  out:14
    execution_stream  CC=1  out:9
    get_execution_projection  CC=1  out:2
    start_execution  CC=4  out:6
  oqlos.api.hardware  [21 funcs]
    _board_model  CC=1  out:5
    _collect_hardware_diagnostics  CC=1  out:5
    _detect_runtime_platform  CC=18  out:20
    _in_container  CC=3  out:4
    _is_plugin_compatible  CC=2  out:3
    _is_raspberry_pi_host  CC=1  out:2
    _local_ads1115_probe_allowed  CC=4  out:4
    _needs_live_scan  CC=3  out:2
    _os_release  CC=3  out:6
    _probe_all_hardware  CC=11  out:5
  oqlos.api.scenarios  [16 funcs]
    _collect_dsl_strings  CC=5  out:10
    _compute_slug  CC=9  out:10
    _ensure_list  CC=3  out:1
    _extract_display_fields  CC=11  out:15
    _extract_goals  CC=2  out:2
    _extract_id  CC=3  out:3
    _fetch_raw_from_sources  CC=8  out:5
    _merge_goals_into_scenario  CC=7  out:10
    _normalize_dsl_payload  CC=5  out:4
    _normalize_scenario_row  CC=2  out:4
  oqlos.api.state  [12 funcs]
    _compose_named_state  CC=2  out:3
    _compose_sim_state_list  CC=3  out:5
    _extract_inline_dsl  CC=8  out:9
    _extract_scenario_id  CC=4  out:7
    _generate_sinusoidal_values  CC=2  out:10
    _handle_start  CC=13  out:27
    _maybe_register_dsl_from_content  CC=5  out:9
    fetch_variables  CC=7  out:6
    get_sim_state  CC=1  out:3
    get_state  CC=1  out:2
  oqlos.config  [1 funcs]
    get_settings  CC=1  out:0
  oqlos.core._compare  [2 funcs]
    resolve_compare  CC=2  out:5
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
  oqlos.core._cql_tree_builder  [9 funcs]
    _ensure_goal_for_step  CC=4  out:3
    _ensure_step_for_actions  CC=3  out:2
    _parse_action_line  CC=4  out:3
    _parse_goal_attrs  CC=4  out:7
    _parse_goal_line  CC=9  out:16
    _parse_metadata_kv  CC=6  out:5
    _parse_scenario_attrs  CC=4  out:6
    _parse_scenario_line  CC=3  out:6
    _parse_step_line  CC=3  out:5
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
  oqlos.core._interpreter_actions  [28 funcs]
    _assert_json  CC=6  out:9
    _assert_sensor  CC=4  out:9
    _assert_status  CC=5  out:7
    _assert_valve  CC=5  out:8
    _coerce_expected_value  CC=7  out:8
    _compare_values  CC=10  out:8
    _do_sleep  CC=3  out:10
    _drop_command_token  CC=6  out:5
    _exec_set_wait  CC=3  out:4
    _extract_action_tokens  CC=5  out:4
  oqlos.core._line_parsers  [9 funcs]
    _parse_action_line  CC=10  out:18
    _parse_if_condition  CC=9  out:22
    _parse_inline_task  CC=5  out:7
    _parse_pump_line  CC=6  out:8
    _parse_set_line  CC=12  out:21
    _parse_task_part  CC=10  out:14
    _set_lung_step  CC=4  out:3
    _set_pump_step  CC=4  out:3
    _set_valve_step  CC=4  out:4
  oqlos.core._oql_adapter  [10 funcs]
    _cmd_to_actions  CC=37  out:58
    _fmt_value  CC=2  out:1
    _load_includes  CC=12  out:15
    _parse_macro_line  CC=8  out:10
    _resolve_include  CC=6  out:8
    _scenarios_root  CC=1  out:2
    _substitute_args  CC=3  out:2
    is_flat_oql  CC=6  out:10
    oql_doc_to_cql  CC=12  out:30
    parse_flat_oql  CC=1  out:2
  oqlos.core._value_normalizers  [1 funcs]
    coerce_float  CC=5  out:9
  oqlos.core.base  [4 funcs]
    emit  CC=5  out:3
    output_yaml  CC=4  out:2
    all  CC=3  out:3
    set  CC=4  out:2
  oqlos.core.cql_parser  [11 funcs]
    _handle_goal  CC=3  out:5
    _handle_goal_attrs  CC=3  out:1
    _handle_scenario  CC=2  out:3
    _handle_scenario_attrs  CC=3  out:1
    _handle_step  CC=2  out:4
    _try_hierarchy  CC=7  out:6
    _try_top_level  CC=2  out:1
    _collect_all_goals  CC=2  out:2
    _validate_intervals  CC=6  out:1
    parse_cql  CC=2  out:6
  oqlos.core.executor  [6 funcs]
    _execute_validate_step  CC=7  out:7
    validate_goal  CC=5  out:3
    _resolve_compare  CC=1  out:2
    _resolve_name_or_attr  CC=4  out:6
    _safe_resolve  CC=14  out:21
    safe_eval_condition  CC=2  out:5
  oqlos.core.interpreter  [4 funcs]
    _build_script_result  CC=2  out:7
    _exec_flat_action  CC=6  out:6
    execute  CC=4  out:9
    parse  CC=2  out:4
  oqlos.core.oql_parser  [20 funcs]
    _require  CC=2  out:2
    _split_value_unit  CC=2  out:2
    duration_to_ms  CC=1  out:2
    parse_CALL  CC=1  out:2
    parse_CHECK  CC=2  out:10
    parse_FUNC_CALL  CC=1  out:2
    parse_GET  CC=1  out:2
    parse_IF  CC=2  out:10
    parse_IF_DELTA  CC=6  out:16
    parse_INCLUDE  CC=1  out:2
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
  oqlos.core.safe_eval  [8 funcs]
    _eval_bin_op  CC=2  out:7
    _eval_bool_op  CC=4  out:7
    _eval_call  CC=4  out:4
    _eval_compare  CC=1  out:2
    _eval_if_exp  CC=2  out:3
    _eval_node  CC=2  out:5
    _eval_unary_op  CC=3  out:5
    safe_eval  CC=3  out:4
  oqlos.hardware.config_paths  [1 funcs]
    resolve_oqlos_config_path  CC=6  out:13
  oqlos.hardware.config_schema  [2 funcs]
    build_dynamic_schema_models  CC=2  out:4
    get_hardware_config  CC=2  out:4
  oqlos.hardware.control_proxy  [17 funcs]
    _unavailable_command_payload  CC=2  out:1
    _unavailable_health_payload  CC=1  out:2
    _unavailable_peripheral_payload  CC=1  out:1
    candidate_bases  CC=1  out:1
    diagnostic_command  CC=6  out:9
    health  CC=3  out:3
    identify  CC=3  out:3
    peripheral_status  CC=7  out:8
    from_env  CC=2  out:5
    _float_from_env  CC=3  out:2
  oqlos.hardware.discovery  [8 funcs]
    _build_probe_candidates  CC=9  out:7
    _make_probe_failure_result  CC=4  out:4
    _make_probe_success_result  CC=3  out:4
    _make_pymodbus_fallback_result  CC=3  out:4
    _try_modbus_connection  CC=8  out:7
    _unique_preserving_order  CC=4  out:3
    list_serial_ports  CC=12  out:16
    probe_waveshare_modbus  CC=7  out:11
  oqlos.hardware.firmware_adapter  [5 funcs]
    __init__  CC=1  out:3
    _get_lung_motor_url  CC=3  out:5
    _handle_lung_action  CC=3  out:5
    _handle_pump_action  CC=3  out:4
    _parse_numeric  CC=2  out:3
  oqlos.hardware.gateway  [1 funcs]
    __init__  CC=6  out:13
  oqlos.hardware.plugin_gateway  [3 funcs]
    __init__  CC=4  out:9
    _load_hardware_schema  CC=3  out:8
    reload_configs  CC=5  out:11
  oqlos.hardware.plugins._shared  [4 funcs]
    health_check_exception  CC=1  out:1
    http_disconnect  CC=2  out:2
    http_health_check  CC=2  out:5
    not_connected_health  CC=1  out:1
  oqlos.hardware.plugins.base  [3 funcs]
    dynamic_peripheral_model  CC=5  out:8
    dynamic_plugin_schema_models  CC=2  out:7
    get_pluggy_manager  CC=1  out:0
  oqlos.hardware.plugins.lung  [2 funcs]
    disconnect  CC=1  out:1
    health_check  CC=15  out:17
  oqlos.hardware.plugins.motor  [2 funcs]
    disconnect  CC=1  out:1
    health_check  CC=10  out:11
  oqlos.hardware.plugins.piadc  [8 funcs]
    _read_blocker  CC=7  out:6
    disconnect  CC=1  out:1
    execute_command  CC=11  out:11
    health_check  CC=8  out:12
    _is_raspberry_pi_host  CC=1  out:5
    _read_text_file  CC=2  out:3
    _requires_remote_rpi_hint  CC=5  out:4
    _resolve_sensor_channel  CC=2  out:6
  oqlos.hardware.plugins.registry  [1 funcs]
    discover_entry_point_plugins  CC=6  out:12
  oqlos.reporters.html_report  [3 funcs]
    _render_goal  CC=10  out:13
    _render_step  CC=7  out:19
    _render_thresholds_table  CC=2  out:12
  oqlos.shared.config_factory  [1 funcs]
    create_nfo_setup  CC=1  out:10
  oqlos.shared.event_server  [4 funcs]
    __init__  CC=1  out:1
    _handle_message  CC=6  out:24
    start  CC=2  out:5
    main  CC=2  out:8
  oqlos.shared.file_ops  [3 funcs]
    _ensure_safe_path  CC=2  out:6
    read_file  CC=3  out:6
    write_file  CC=1  out:3
  oqlos.shared.release_version  [7 funcs]
    _read_version_from_package_json  CC=4  out:5
    _read_version_from_text  CC=4  out:4
    _run_git  CC=4  out:3
    _version_candidates  CC=1  out:0
    clean_version  CC=6  out:5
    main  CC=1  out:2
    resolve_release_version  CC=11  out:12
  oqlos.shared.version_endpoint  [2 funcs]
    build_version_payload  CC=3  out:2
    create_version_router  CC=2  out:4
  oqlos.tools.cql_cli  [2 funcs]
    _sync_compat_symbols  CC=1  out:0
    main  CC=1  out:2
  oqlos.tools.cql_cli.commands  [5 funcs]
    _run_continuous_mode  CC=4  out:20
    execute_command_with_cleanup  CC=8  out:7
    handle_list_command  CC=7  out:21
    run_single_command  CC=1  out:2
    run_source  CC=2  out:3
  oqlos.tools.cql_cli.main  [16 funcs]
    _create_interpreter  CC=1  out:1
    _dispatch_to_mode  CC=7  out:12
    _extract_scenario_source  CC=9  out:9
    _fetch_scenario_source  CC=7  out:13
    _looks_like_html  CC=3  out:5
    _print_cli_error  CC=2  out:3
    _run_hardware_flags  CC=9  out:14
    _run_interpreter_target  CC=2  out:4
    create_cmd_parser  CC=1  out:13
    create_file_parser  CC=1  out:16
  oqlos.tools.cql_cli.preflight  [12 funcs]
    _emit_preflight_error  CC=2  out:2
    _emit_text_preflight  CC=7  out:16
    _emit_yaml_preflight  CC=6  out:8
    _health_status_is_ok  CC=11  out:9
    _is_firmware_running  CC=5  out:3
    _start_firmware_service  CC=13  out:11
    check_firmware_state  CC=8  out:14
    check_required_adapter  CC=8  out:5
    check_required_adapter_health  CC=5  out:4
    emit_preflight_success  CC=3  out:2
  oqlos.tools.cql_cli.utils  [10 funcs]
    _extract_first_action  CC=5  out:2
    _resolve_peripheral_adapter  CC=4  out:4
    _resolve_sensor_target  CC=3  out:0
    build_result_payload  CC=2  out:2
    build_single_command_scenario  CC=2  out:3
    normalize_target_name  CC=1  out:4
    output_yaml  CC=2  out:2
    parse_sensor_overrides  CC=3  out:4
    resolve_required_adapter  CC=8  out:3
    validate_directory  CC=5  out:15
  oqlos.tools.hardware_diagnose.__main__  [7 funcs]
    _print_benchmark  CC=3  out:11
    _print_calibrate  CC=6  out:9
    _print_detect  CC=2  out:4
    _print_doctor  CC=2  out:4
    _print_health  CC=2  out:5
    _print_list  CC=3  out:8
    _print_modbus_probe  CC=2  out:5
  oqlos.tools.hardware_diagnose.benchmark  [1 funcs]
    run_benchmark  CC=6  out:15
  oqlos.tools.hardware_diagnose.calibration  [4 funcs]
    _calibrate_pump  CC=3  out:8
    _calibrate_sensors  CC=5  out:8
    _calibrate_valves  CC=4  out:6
    run_calibration_test  CC=2  out:8
  oqlos.tools.hardware_diagnose.discovery  [4 funcs]
    _run_shell_command  CC=2  out:2
    detect_chips_on_i2c  CC=8  out:10
    list_i2c_buses  CC=1  out:2
    list_usb_serial_devices  CC=7  out:9
  oqlos.tools.hardware_diagnose.doctor  [26 funcs]
    _adapter_health_status  CC=3  out:1
    _add_issue  CC=2  out:1
    _analyze_firmware_access  CC=25  out:34
    _analyze_modbus_config  CC=11  out:20
    _analyze_serial_port_owners  CC=13  out:19
    _canonical_device_path  CC=2  out:3
    _collect_repairs  CC=5  out:7
    _describe_pid  CC=4  out:4
    _expected_modbus_params  CC=5  out:6
    _extract_pids  CC=4  out:4
  oqlos.tools.hardware_diagnose.health  [7 funcs]
    _format_health_value  CC=8  out:9
    _is_health_ok  CC=5  out:6
    _request_firmware_json  CC=3  out:3
    check_firmware_health  CC=1  out:1
    check_firmware_identify  CC=1  out:1
    cmd_diagnose  CC=6  out:20
    cmd_health  CC=5  out:10
  oqlos.tools.hardware_diagnose.modbus_probe  [16 funcs]
    _arg_count_list  CC=3  out:2
    _arg_int_list  CC=3  out:2
    _arg_str_list  CC=2  out:1
    _env_count_list  CC=2  out:2
    _env_float  CC=2  out:2
    _env_int  CC=2  out:2
    _env_int_list  CC=5  out:5
    _env_str_list  CC=3  out:2
    _serials_from_env  CC=3  out:4
    _split_values  CC=5  out:5
  oqlos.tools.hardware_diagnose.report  [2 funcs]
    format_peripheral_table  CC=12  out:3
    save_diagnostic_report  CC=3  out:13
  oqlos.tools.hardware_diagnose.shell  [5 funcs]
    _cmd_benchmark  CC=4  out:8
    _cmd_calibrate  CC=4  out:5
    _cmd_list  CC=5  out:11
    _dispatch_command  CC=6  out:21
    interactive_shell  CC=6  out:8
  oqlos.tools.plugin_cli  [12 funcs]
    _default_config_path  CC=1  out:2
    _load_config_file  CC=4  out:16
    cmd_capabilities  CC=2  out:6
    cmd_connect  CC=4  out:6
    cmd_disconnect  CC=2  out:4
    cmd_execute  CC=3  out:7
    cmd_health  CC=3  out:8
    cmd_list  CC=3  out:9
    cmd_peripherals  CC=8  out:16
    cmd_reload  CC=4  out:10
  oqlos.tools.xml_import._utils  [3 funcs]
    is_compressor_output  CC=5  out:2
    is_pump_output  CC=4  out:2
    normalize_output_name  CC=11  out:12
  oqlos.tools.xml_import.generators  [13 funcs]
    _append_sensor_assertion  CC=6  out:3
    _build_steps_from_op  CC=10  out:14
    _build_validation_criteria  CC=14  out:3
    _emit_cql_output  CC=5  out:15
    _emit_cql_param  CC=7  out:5
    _emit_cql_sensor_param  CC=13  out:11
    _emit_dsl_param  CC=10  out:13
    _emit_dsl_sensors  CC=8  out:7
    _format_range  CC=9  out:0
    _generate_cql_for_goal  CC=4  out:3
  oqlos.tools.xml_import.parser  [6 funcs]
    _parse_intervals  CC=4  out:7
    _parse_operation  CC=6  out:18
    _parse_operation_params  CC=9  out:21
    _parse_test_run  CC=7  out:19
    _populate_report_fields  CC=1  out:16
    parse_xml  CC=6  out:16
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
  oqlos.core.base.InterpreterOutput.emit → examples.hardware.doctor-workflow.print
  oqlos.core.base.InterpreterOutput.output_yaml → examples.hardware.doctor-workflow.print
  oqlos.core._dsl_helpers._map_peripheral → oqlos.core._dsl_helpers._looks_like_valve_object
  oqlos.core._dsl_helpers._map_peripheral → oqlos.core._dsl_helpers._looks_like_pump_object
  oqlos.core._dsl_helpers._map_peripheral → oqlos.core._dsl_helpers._looks_like_lung_object
  oqlos.core._dsl_helpers._map_peripheral → oqlos.core._dsl_helpers._looks_like_sensor_object
  oqlos.core._dsl_helpers._map_pump_action → oqlos.core._dsl_helpers._parse_numeric_value
  oqlos.core._dsl_helpers._map_lung_action → oqlos.core._dsl_helpers._parse_numeric_value
  oqlos.core._dsl_helpers._map_action_value → oqlos.core._dsl_helpers._looks_like_valve_object
  oqlos.core._dsl_helpers._map_action_value → oqlos.core._dsl_helpers._looks_like_pump_object
  oqlos.core._dsl_helpers._map_action_value → oqlos.core._dsl_helpers._looks_like_lung_object
  oqlos.core._dsl_helpers._map_action_value → oqlos.core._dsl_helpers._map_valve_action
  oqlos.core._dsl_helpers._map_action_value → oqlos.core._dsl_helpers._map_pump_action
  oqlos.core._dsl_helpers._map_action_value → oqlos.core._dsl_helpers._map_lung_action
  oqlos.core._dsl_helpers._map_action_value → oqlos.core._dsl_helpers._looks_like_sensor_object
  oqlos.core._dsl_helpers._map_action_value → oqlos.core._dsl_helpers._map_wait_action
  oqlos.core._interpreter_actions._drop_command_token → oqlos.core._interpreter_actions._extract_action_tokens
  oqlos.core._interpreter_actions._compare_values → oqlos.core._interpreter_actions._coerce_expected_value
  oqlos.core._interpreter_actions.exec_action_wait → oqlos.core._interpreter_actions.parse_wait_secs
  oqlos.core._interpreter_actions.exec_action_wait → oqlos.core._interpreter_actions._do_sleep
  oqlos.core._interpreter_actions.exec_action_func → oqlos.core._interpreter_actions._resolve_numeric_token
  oqlos.core._interpreter_actions.exec_action_api → oqlos.core._interpreter_actions._mock_api_response
  oqlos.core._interpreter_actions.exec_action_expect → oqlos.core._interpreter_actions._drop_command_token
  oqlos.core._interpreter_actions.exec_action_expect → oqlos.core._interpreter_actions._mark_success
  oqlos.core._interpreter_actions._assert_status → oqlos.core._interpreter_actions._record_failure
  oqlos.core._interpreter_actions._assert_status → oqlos.core._interpreter_actions._coerce_expected_value
  oqlos.core._interpreter_actions._assert_json → oqlos.core._interpreter_actions._get_nested_value
  oqlos.core._interpreter_actions._assert_json → oqlos.core._interpreter_actions._record_failure
  oqlos.core._interpreter_actions._assert_json → oqlos.core._interpreter_actions._compare_values
  oqlos.core._interpreter_actions._assert_sensor → oqlos.core._interpreter_actions._record_failure
  oqlos.core._interpreter_actions._assert_sensor → oqlos.core._interpreter_actions._mark_success
  oqlos.core._interpreter_actions._assert_valve → oqlos.core._interpreter_actions._lookup_peripheral_state
  oqlos.core._interpreter_actions._assert_valve → oqlos.core._interpreter_actions._normalize_bool
  oqlos.core._interpreter_actions._assert_valve → oqlos.core._interpreter_actions._mark_success
  oqlos.core._interpreter_actions._assert_valve → oqlos.core._interpreter_actions._record_failure
  oqlos.core._interpreter_actions.exec_action_assert → oqlos.core._interpreter_actions._drop_command_token
  oqlos.core._interpreter_actions.exec_action_assert → oqlos.core._interpreter_actions._record_failure
  oqlos.core._interpreter_actions.exec_action_shell → oqlos.core._interpreter_actions._drop_command_token
  oqlos.core._interpreter_actions.exec_action_shell → oqlos.core._interpreter_actions._record_failure
  oqlos.core._interpreter_actions.exec_action_set → oqlos.core._interpreter_actions._exec_set_wait
  oqlos.core._interpreter_actions._exec_set_wait → oqlos.core._interpreter_actions.parse_wait_secs
  oqlos.core._interpreter_actions._exec_set_wait → oqlos.core._interpreter_actions._do_sleep
  oqlos.core.oql_parser.parse_duration → oqlos.core.oql_parser.to_num
  oqlos.core.oql_parser.duration_to_ms → oqlos.core.oql_parser.parse_duration
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
