# OqlOS — Operation Query Language Runtime

SUMD - Structured Unified Markdown Descriptor for AI-aware project refactorization

## Contents

- [Metadata](#metadata)
- [Architecture](#architecture)
- [Workflows](#workflows)
- [Quality Pipeline (`pyqual.yaml`)](#quality-pipeline-pyqualyaml)
- [Dependencies](#dependencies)
- [Source Map](#source-map)
- [Call Graph](#call-graph)
- [Test Contracts](#test-contracts)
- [Refactoring Analysis](#refactoring-analysis)
- [Intent](#intent)

## Metadata

- **name**: `oqlos`
- **version**: `0.1.28`
- **python_requires**: `>=3.10`
- **license**: {'text': 'Apache-2.0'}
- **ai_model**: `openrouter/qwen/qwen3-coder-next`
- **ecosystem**: SUMD + DOQL + testql + taskfile
- **openapi_title**: oqlos API v1.0.0
- **generated_from**: pyproject.toml, Taskfile.yml, Makefile, testql(6), openapi(49 ep), app.doql.less, pyqual.yaml, goal.yaml, .env.example, Dockerfile, docker-compose.dev.yml, src(1 mod), project/(6 analysis files)

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

## Source Map

*Top 1 modules by symbol density — signatures for LLM orientation.*

### `oqlos.config` (`oqlos/config.py`)

```python
def get_settings()  # CC=1, fan=0
class Settings:  # Application settings loaded from environment variables and .
```

## Call Graph

*426 nodes · 500 edges · 43 modules · CC̄=4.0*

### Hubs (by degree)

| Function | CC | in | out | total |
|----------|----|----|-----|-------|
| `print` *(in examples.hardware.doctor-workflow)* | 0 | 225 | 0 | **225** |
| `dict` *(in frontend.src.i18n.I18nProvider)* | 8 | 43 | 3 | **46** |
| `list` *(in frontend.src.utils.hardware-wizard-steps)* | 2 | 40 | 0 | **40** |
| `oql_doc_to_cql` *(in oqlos.core._oql_adapter)* | 12 ⚠ | 2 | 30 | **32** |
| `normalize_motor2_runtime_config` *(in oqlos.core.motor2_runtime)* | 12 ⚠ | 1 | 29 | **30** |
| `_safe_resolve` *(in oqlos.core.executor)* | 14 ⚠ | 7 | 21 | **28** |
| `run_oql_scenario` *(in setup_hardware_and_run_oql)* | 8 | 1 | 24 | **25** |
| `applyMapMutation` *(in frontend.src.pages.MapEditor)* | 2 | 16 | 8 | **24** |

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/oqlos/oqlos
# generated in 0.23s
# nodes: 426 | edges: 500 | modules: 43
# CC̄=4.0

HUBS[20]:
  examples.hardware.doctor-workflow.print
    CC=0  in:225  out:0  total:225
  frontend.src.i18n.I18nProvider.dict
    CC=8  in:43  out:3  total:46
  frontend.src.utils.hardware-wizard-steps.list
    CC=2  in:40  out:0  total:40
  oqlos.core._oql_adapter.oql_doc_to_cql
    CC=12  in:2  out:30  total:32
  oqlos.core.motor2_runtime.normalize_motor2_runtime_config
    CC=12  in:1  out:29  total:30
  oqlos.core.executor._safe_resolve
    CC=14  in:7  out:21  total:28
  setup_hardware_and_run_oql.run_oql_scenario
    CC=8  in:1  out:24  total:25
  frontend.src.pages.MapEditor.applyMapMutation
    CC=2  in:16  out:8  total:24
  oqlos.core.oql_parser.parse_oql
    CC=14  in:3  out:21  total:24
  oqlos.core.parser.parse_dsl_to_goal_with_issues
    CC=13  in:3  out:21  total:24
  oqlos.core._line_parsers._parse_if_condition
    CC=9  in:1  out:22  total:23
  oqlos.core._action_motor2._try_exec_motor2_set
    CC=13  in:1  out:22  total:23
  oqlos.core._action_motor2._motor2_build_plan
    CC=12  in:1  out:22  total:23
  oqlos.core._line_parsers._parse_set_line
    CC=12  in:1  out:21  total:22
  frontend.src.utils.useSelectionCollapsePanel.useSelectionCollapsePanel
    CC=33  in:0  out:21  total:21
  frontend.src.utils.useSelectionCollapsePanel.RAIL_HOVER_OPEN_MS
    CC=33  in:0  out:21  total:21
  frontend.src.utils.useSelectionCollapsePanel.RAIL_HOVER_CLOSE_MS
    CC=33  in:0  out:21  total:21
  oqlos.core._func_resolver._collect_function_definitions
    CC=13  in:1  out:19  total:20
  frontend.src.api.wsClient.WsCqrsClient.super
    CC=1  in:18  out:1  total:19
  oqlos.core.oql_parser.tokenize
    CC=13  in:5  out:14  total:19

MODULES:
  examples.hardware.doctor-workflow  [1 funcs]
    print  CC=0  out:0
  frontend.src.api.hardware-api-errors  [4 funcs]
    describeDetail  CC=13  out:6
    extractErrorPayload  CC=4  out:1
    formatHardwareApiError  CC=8  out:2
    tryParseJson  CC=3  out:1
  frontend.src.api.hardware-api-log  [4 funcs]
    isHardwareWizardPath  CC=2  out:3
    keys  CC=2  out:0
    logHardwareApiEvent  CC=6  out:4
    summarizeHardwareApiBody  CC=11  out:5
  frontend.src.api.hardware-diagnostic-failure  [6 funcs]
    extractDiagnosticFailure  CC=13  out:6
    failureFromNestedOk  CC=17  out:5
    failureFromOkFalsePayload  CC=19  out:5
    failureFromSuccessFalse  CC=14  out:3
    firstActionableError  CC=3  out:4
    resultData  CC=4  out:0
  frontend.src.api.hardware-tic249-status  [3 funcs]
    isIdempotentDiagnosticSuccess  CC=3  out:2
    isIdempotentTic249Deenergized  CC=12  out:2
    tic249ResultStatus  CC=8  out:2
  frontend.src.api.hardwareApi  [10 funcs]
    API_BASE  CC=17  out:13
    durationMs  CC=8  out:5
    get  CC=1  out:1
    mode  CC=1  out:1
    normalized  CC=1  out:1
    post  CC=1  out:1
    put  CC=1  out:1
    request  CC=17  out:13
    serialPort  CC=2  out:1
    text  CC=2  out:0
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
  frontend.src.hooks.useParentEncoderNavigation  [14 funcs]
    all  CC=6  out:2
    controller  CC=3  out:2
    createEncoderController  CC=21  out:10
    getInteractiveItems  CC=6  out:4
    handleEncoderCommand  CC=15  out:7
    items  CC=7  out:4
    onKeyDown  CC=7  out:3
    onMessage  CC=3  out:2
    onWheel  CC=6  out:5
    parentEncoderActive  CC=15  out:7
  frontend.src.hooks.useUrlConfig  [2 funcs]
    notifyParentChildReady  CC=4  out:5
    useUrlConfig  CC=8  out:15
  frontend.src.i18n.I18nProvider  [5 funcs]
    I18nProvider  CC=13  out:8
    dict  CC=8  out:3
    getInitialLang  CC=5  out:1
    t  CC=8  out:2
    val  CC=2  out:2
  frontend.src.pages.HardwareDemo  [15 funcs]
    Ctx  CC=2  out:2
    appendLog  CC=1  out:3
    cancelled  CC=16  out:10
    ensureAudioCtx  CC=4  out:4
    fallbackDevice  CC=2  out:5
    fb  CC=2  out:5
    now  CC=1  out:1
    onNoteClick  CC=4  out:9
    playMelody  CC=9  out:11
    playNote  CC=5  out:7
  frontend.src.pages.HardwareRestart  [23 funcs]
    advanceOk  CC=3  out:2
    canRunCurrentStep  CC=1  out:4
    confirmErrorKey  CC=1  out:4
    confirmLabelKey  CC=1  out:4
    currentStep  CC=1  out:4
    isConfigureStep  CC=1  out:4
    isSeparateAdapters  CC=1  out:4
    loadPlan  CC=18  out:11
    log  CC=1  out:3
    message  CC=1  out:1
  frontend.src.pages.MapEditor  [49 funcs]
    addAction  CC=2  out:6
    addFunc  CC=2  out:6
    addObject  CC=2  out:6
    addParam  CC=2  out:4
    applyMapMutation  CC=2  out:8
    clearServerHardwareEvents  CC=8  out:9
    cloneDefaultMap  CC=1  out:2
    cloneValue  CC=1  out:2
    createInitialEditorState  CC=1  out:3
    defaultMotor2  CC=3  out:2
  frontend.src.utils.collapse-toggle-bridge  [2 funcs]
    isInIframe  CC=4  out:0
    postToParent  CC=4  out:8
  frontend.src.utils.hardware-activity-log  [4 funcs]
    createHardwareActivityLogEntry  CC=1  out:2
    loggedRef  CC=2  out:4
    prependHardwareActivityLogEntry  CC=1  out:2
    usePageOpenedLog  CC=2  out:5
  frontend.src.utils.hardware-api-retry  [2 funcs]
    attempt  CC=14  out:9
    sleep  CC=1  out:2
  frontend.src.utils.hardware-restart-wizard-steps  [3 funcs]
    buildWizardProbePayload  CC=10  out:7
    executeConfigureStep  CC=48  out:15
    wizardStepSerialPort  CC=14  out:0
  frontend.src.utils.hardware-wizard-steps  [1 funcs]
    list  CC=2  out:0
  frontend.src.utils.hardwareEventStream  [9 funcs]
    buildHardwareEventsWsUrl  CC=10  out:3
    commandName  CC=3  out:1
    id  CC=3  out:1
    matchesHardwareEventFilters  CC=9  out:4
    normalizeHardwareEvent  CC=21  out:3
    normalizeText  CC=2  out:1
    peripheralId  CC=3  out:1
    result  CC=3  out:1
    timestamp  CC=3  out:1
  frontend.src.utils.mapEditorFuncHardwareSummary  [6 funcs]
    apiBindingHint  CC=12  out:0
    objectMap  CC=3  out:2
    resolveNamedActionHardwareHint  CC=7  out:4
    resolveObjectActionHardwareHint  CC=6  out:2
    summarizeFuncToHardware  CC=17  out:6
    uniqueHints  CC=5  out:5
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
  frontend.src.utils.url-embed-config  [21 funcs]
    applyParentContextPayload  CC=5  out:5
    applyUrlEmbedPatch  CC=7  out:7
    base  CC=3  out:3
    fromUser  CC=4  out:3
    href  CC=4  out:3
    mergeParentContext  CC=7  out:4
    mergeParentSearchIntoChildUrl  CC=6  out:10
    nextHref  CC=1  out:1
    parentSearch  CC=4  out:3
    parseAppearanceParams  CC=9  out:4
  frontend.src.utils.useSelectionCollapsePanel  [16 funcs]
    RAIL_HOVER_CLOSE_MS  CC=33  out:21
    RAIL_HOVER_OPEN_MS  CC=33  out:21
    cancelAutoCollapse  CC=2  out:2
    cancelPanelClose  CC=2  out:2
    cancelRailOpen  CC=2  out:2
    expand  CC=1  out:5
    onMessage  CC=8  out:3
    panelEnter  CC=1  out:2
    panelLeave  CC=4  out:5
    previewCollapse  CC=1  out:2
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
  oqlos.core._cql_tree_builder  [2 funcs]
    _parse_action_line  CC=4  out:3
    _parse_metadata_kv  CC=6  out:5
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
    _parse_action_line  CC=10  out:18
    _parse_if_condition  CC=9  out:22
    _parse_inline_task  CC=5  out:7
    _parse_pump_line  CC=6  out:8
    _parse_set_line  CC=12  out:21
    _parse_task_part  CC=10  out:14
    _set_lung_step  CC=4  out:3
    _set_pump_step  CC=4  out:3
    _set_valve_step  CC=4  out:4
  oqlos.core._oql_adapter  [15 funcs]
    register  CC=1  out:1
    _cmd_to_actions  CC=2  out:3
    _fmt_value  CC=2  out:1
    _load_includes  CC=12  out:15
    _lower_call  CC=6  out:10
    _lower_max  CC=1  out:3
    _lower_min  CC=1  out:3
    _lower_set  CC=1  out:3
    _parse_macro_line  CC=8  out:10
    _resolve_include  CC=6  out:8
  oqlos.core.base  [5 funcs]
    send_event  CC=4  out:7
    emit  CC=5  out:3
    output_yaml  CC=4  out:2
    __init__  CC=2  out:1
    all  CC=3  out:3
  oqlos.core.cql_parser  [3 funcs]
    _try_top_level  CC=2  out:1
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
  oqlos.core.oql_parser  [31 funcs]
    _check_unnamed_goals  CC=5  out:1
    _expand_repeat_block_lines  CC=8  out:16
    _expand_repeat_blocks  CC=2  out:2
    _handle_block_header  CC=8  out:12
    _handle_modifier_cmd  CC=5  out:3
    _handle_set_name  CC=5  out:8
    _handle_top_level_line  CC=6  out:16
    _line_indent  CC=2  out:5
    _parse_and_append_command  CC=5  out:9
    _require  CC=2  out:2
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
  frontend.src.hooks.useUrlConfig.useUrlConfig → frontend.src.hooks.useUrlConfig.notifyParentChildReady
  frontend.src.hooks.useParentEncoderNavigation.createEncoderController → frontend.src.hooks.useParentEncoderNavigation.removeHighlights
  frontend.src.hooks.useParentEncoderNavigation.createEncoderController → frontend.src.hooks.useParentEncoderNavigation.getInteractiveItems
  frontend.src.hooks.useParentEncoderNavigation.createEncoderController → frontend.src.hooks.useParentEncoderNavigation.handleEncoderCommand
  frontend.src.hooks.useParentEncoderNavigation.parentEncoderActive → frontend.src.hooks.useParentEncoderNavigation.removeHighlights
  frontend.src.hooks.useParentEncoderNavigation.parentEncoderActive → frontend.src.hooks.useParentEncoderNavigation.getInteractiveItems
  frontend.src.hooks.useParentEncoderNavigation.handleEncoderCommand → frontend.src.hooks.useParentEncoderNavigation.removeHighlights
  frontend.src.hooks.useParentEncoderNavigation.handleEncoderCommand → frontend.src.hooks.useParentEncoderNavigation.getInteractiveItems
  frontend.src.hooks.useParentEncoderNavigation.items → frontend.src.hooks.useParentEncoderNavigation.removeHighlights
  frontend.src.hooks.useParentEncoderNavigation.onKeyDown → frontend.src.hooks.useParentEncoderNavigation.handleEncoderCommand
  frontend.src.hooks.useParentEncoderNavigation.useParentEncoderNavigation → frontend.src.hooks.useParentEncoderNavigation.createEncoderController
  frontend.src.hooks.useParentEncoderNavigation.useParentEncoderNavigation → frontend.src.hooks.useParentEncoderNavigation.parseParentEncoderEnvelope
  frontend.src.hooks.useParentEncoderNavigation.useParentEncoderNavigation → frontend.src.hooks.useParentEncoderNavigation.handleEncoderCommand
  frontend.src.hooks.useParentEncoderNavigation.controller → frontend.src.hooks.useParentEncoderNavigation.parseParentEncoderEnvelope
  frontend.src.hooks.useParentEncoderNavigation.controller → frontend.src.hooks.useParentEncoderNavigation.handleEncoderCommand
  frontend.src.hooks.useParentEncoderNavigation.onMessage → frontend.src.hooks.useParentEncoderNavigation.parseParentEncoderEnvelope
  frontend.src.hooks.useParentEncoderNavigation.onMessage → frontend.src.hooks.useParentEncoderNavigation.handleEncoderCommand
  frontend.src.hooks.useParentEncoderNavigation.onWheel → frontend.src.hooks.useParentEncoderNavigation.handleEncoderCommand
  frontend.src.hooks.useParentEncoderNavigation.raw → frontend.src.hooks.useParentEncoderNavigation.handleEncoderCommand
  frontend.src.pages.MapEditor.fillMissingFields → frontend.src.pages.MapEditor.isPlainObject
  frontend.src.pages.MapEditor.fillMissingFields → frontend.src.pages.MapEditor.cloneValue
  frontend.src.pages.MapEditor.ensureRequiredDefaultMappings → frontend.src.pages.MapEditor.ensureMapShape
  frontend.src.pages.MapEditor.ensureRequiredDefaultMappings → frontend.src.pages.MapEditor.fillMissingFields
  frontend.src.pages.MapEditor.ensureRequiredDefaultMappings → frontend.src.pages.MapEditor.isPlainObject
  frontend.src.pages.MapEditor.defaultMotor2 → frontend.src.pages.MapEditor.fillMissingFields
  frontend.src.pages.MapEditor.defaultMotor2 → frontend.src.pages.MapEditor.isPlainObject
  frontend.src.pages.MapEditor.defaultParam → frontend.src.pages.MapEditor.fillMissingFields
  frontend.src.pages.MapEditor.defaultParam → frontend.src.pages.MapEditor.isPlainObject
  frontend.src.pages.MapEditor.readIntegrationMeta → frontend.src.pages.MapEditor.firstBindingFromObjectMapping
  frontend.src.pages.MapEditor.ensureMapShape → frontend.src.pages.MapEditor.isPlainObject
  frontend.src.pages.MapEditor.src → frontend.src.pages.MapEditor.isPlainObject
  frontend.src.pages.MapEditor.toPrettyJson → frontend.src.pages.MapEditor.ensureMapShape
  frontend.src.pages.MapEditor.createInitialEditorState → frontend.src.pages.MapEditor.ensureRequiredDefaultMappings
  frontend.src.pages.MapEditor.createInitialEditorState → frontend.src.pages.MapEditor.cloneDefaultMap
  frontend.src.pages.MapEditor.createInitialEditorState → frontend.src.pages.MapEditor.toPrettyJson
  frontend.src.pages.MapEditor.onJsonChange → frontend.src.pages.MapEditor.isPlainObject
  frontend.src.pages.MapEditor.onJsonChange → frontend.src.pages.MapEditor.ensureMapShape
  frontend.src.pages.MapEditor.parsed → frontend.src.pages.MapEditor.isPlainObject
  frontend.src.pages.MapEditor.applyMapMutation → frontend.src.pages.MapEditor.ensureMapShape
  frontend.src.pages.MapEditor.applyMapMutation → frontend.src.pages.MapEditor.toPrettyJson
  frontend.src.pages.MapEditor.addObject → frontend.src.pages.MapEditor.applyMapMutation
  frontend.src.pages.MapEditor.name → frontend.src.pages.MapEditor.applyMapMutation
  frontend.src.pages.MapEditor.addParam → frontend.src.pages.MapEditor.applyMapMutation
  frontend.src.pages.MapEditor.editParamConversionField → frontend.src.pages.MapEditor.applyMapMutation
```

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

## Refactoring Analysis

*Pre-refactoring snapshot — use this section to identify targets. Generated from `project/` toon files.*

### Call Graph & Complexity (`project/calls.toon.yaml`)

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/oqlos/oqlos
# generated in 0.23s
# nodes: 426 | edges: 500 | modules: 43
# CC̄=4.0

HUBS[20]:
  examples.hardware.doctor-workflow.print
    CC=0  in:225  out:0  total:225
  frontend.src.i18n.I18nProvider.dict
    CC=8  in:43  out:3  total:46
  frontend.src.utils.hardware-wizard-steps.list
    CC=2  in:40  out:0  total:40
  oqlos.core._oql_adapter.oql_doc_to_cql
    CC=12  in:2  out:30  total:32
  oqlos.core.motor2_runtime.normalize_motor2_runtime_config
    CC=12  in:1  out:29  total:30
  oqlos.core.executor._safe_resolve
    CC=14  in:7  out:21  total:28
  setup_hardware_and_run_oql.run_oql_scenario
    CC=8  in:1  out:24  total:25
  frontend.src.pages.MapEditor.applyMapMutation
    CC=2  in:16  out:8  total:24
  oqlos.core.oql_parser.parse_oql
    CC=14  in:3  out:21  total:24
  oqlos.core.parser.parse_dsl_to_goal_with_issues
    CC=13  in:3  out:21  total:24
  oqlos.core._line_parsers._parse_if_condition
    CC=9  in:1  out:22  total:23
  oqlos.core._action_motor2._try_exec_motor2_set
    CC=13  in:1  out:22  total:23
  oqlos.core._action_motor2._motor2_build_plan
    CC=12  in:1  out:22  total:23
  oqlos.core._line_parsers._parse_set_line
    CC=12  in:1  out:21  total:22
  frontend.src.utils.useSelectionCollapsePanel.useSelectionCollapsePanel
    CC=33  in:0  out:21  total:21
  frontend.src.utils.useSelectionCollapsePanel.RAIL_HOVER_OPEN_MS
    CC=33  in:0  out:21  total:21
  frontend.src.utils.useSelectionCollapsePanel.RAIL_HOVER_CLOSE_MS
    CC=33  in:0  out:21  total:21
  oqlos.core._func_resolver._collect_function_definitions
    CC=13  in:1  out:19  total:20
  frontend.src.api.wsClient.WsCqrsClient.super
    CC=1  in:18  out:1  total:19
  oqlos.core.oql_parser.tokenize
    CC=13  in:5  out:14  total:19

MODULES:
  examples.hardware.doctor-workflow  [1 funcs]
    print  CC=0  out:0
  frontend.src.api.hardware-api-errors  [4 funcs]
    describeDetail  CC=13  out:6
    extractErrorPayload  CC=4  out:1
    formatHardwareApiError  CC=8  out:2
    tryParseJson  CC=3  out:1
  frontend.src.api.hardware-api-log  [4 funcs]
    isHardwareWizardPath  CC=2  out:3
    keys  CC=2  out:0
    logHardwareApiEvent  CC=6  out:4
    summarizeHardwareApiBody  CC=11  out:5
  frontend.src.api.hardware-diagnostic-failure  [6 funcs]
    extractDiagnosticFailure  CC=13  out:6
    failureFromNestedOk  CC=17  out:5
    failureFromOkFalsePayload  CC=19  out:5
    failureFromSuccessFalse  CC=14  out:3
    firstActionableError  CC=3  out:4
    resultData  CC=4  out:0
  frontend.src.api.hardware-tic249-status  [3 funcs]
    isIdempotentDiagnosticSuccess  CC=3  out:2
    isIdempotentTic249Deenergized  CC=12  out:2
    tic249ResultStatus  CC=8  out:2
  frontend.src.api.hardwareApi  [10 funcs]
    API_BASE  CC=17  out:13
    durationMs  CC=8  out:5
    get  CC=1  out:1
    mode  CC=1  out:1
    normalized  CC=1  out:1
    post  CC=1  out:1
    put  CC=1  out:1
    request  CC=17  out:13
    serialPort  CC=2  out:1
    text  CC=2  out:0
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
  frontend.src.hooks.useParentEncoderNavigation  [14 funcs]
    all  CC=6  out:2
    controller  CC=3  out:2
    createEncoderController  CC=21  out:10
    getInteractiveItems  CC=6  out:4
    handleEncoderCommand  CC=15  out:7
    items  CC=7  out:4
    onKeyDown  CC=7  out:3
    onMessage  CC=3  out:2
    onWheel  CC=6  out:5
    parentEncoderActive  CC=15  out:7
  frontend.src.hooks.useUrlConfig  [2 funcs]
    notifyParentChildReady  CC=4  out:5
    useUrlConfig  CC=8  out:15
  frontend.src.i18n.I18nProvider  [5 funcs]
    I18nProvider  CC=13  out:8
    dict  CC=8  out:3
    getInitialLang  CC=5  out:1
    t  CC=8  out:2
    val  CC=2  out:2
  frontend.src.pages.HardwareDemo  [15 funcs]
    Ctx  CC=2  out:2
    appendLog  CC=1  out:3
    cancelled  CC=16  out:10
    ensureAudioCtx  CC=4  out:4
    fallbackDevice  CC=2  out:5
    fb  CC=2  out:5
    now  CC=1  out:1
    onNoteClick  CC=4  out:9
    playMelody  CC=9  out:11
    playNote  CC=5  out:7
  frontend.src.pages.HardwareRestart  [23 funcs]
    advanceOk  CC=3  out:2
    canRunCurrentStep  CC=1  out:4
    confirmErrorKey  CC=1  out:4
    confirmLabelKey  CC=1  out:4
    currentStep  CC=1  out:4
    isConfigureStep  CC=1  out:4
    isSeparateAdapters  CC=1  out:4
    loadPlan  CC=18  out:11
    log  CC=1  out:3
    message  CC=1  out:1
  frontend.src.pages.MapEditor  [49 funcs]
    addAction  CC=2  out:6
    addFunc  CC=2  out:6
    addObject  CC=2  out:6
    addParam  CC=2  out:4
    applyMapMutation  CC=2  out:8
    clearServerHardwareEvents  CC=8  out:9
    cloneDefaultMap  CC=1  out:2
    cloneValue  CC=1  out:2
    createInitialEditorState  CC=1  out:3
    defaultMotor2  CC=3  out:2
  frontend.src.utils.collapse-toggle-bridge  [2 funcs]
    isInIframe  CC=4  out:0
    postToParent  CC=4  out:8
  frontend.src.utils.hardware-activity-log  [4 funcs]
    createHardwareActivityLogEntry  CC=1  out:2
    loggedRef  CC=2  out:4
    prependHardwareActivityLogEntry  CC=1  out:2
    usePageOpenedLog  CC=2  out:5
  frontend.src.utils.hardware-api-retry  [2 funcs]
    attempt  CC=14  out:9
    sleep  CC=1  out:2
  frontend.src.utils.hardware-restart-wizard-steps  [3 funcs]
    buildWizardProbePayload  CC=10  out:7
    executeConfigureStep  CC=48  out:15
    wizardStepSerialPort  CC=14  out:0
  frontend.src.utils.hardware-wizard-steps  [1 funcs]
    list  CC=2  out:0
  frontend.src.utils.hardwareEventStream  [9 funcs]
    buildHardwareEventsWsUrl  CC=10  out:3
    commandName  CC=3  out:1
    id  CC=3  out:1
    matchesHardwareEventFilters  CC=9  out:4
    normalizeHardwareEvent  CC=21  out:3
    normalizeText  CC=2  out:1
    peripheralId  CC=3  out:1
    result  CC=3  out:1
    timestamp  CC=3  out:1
  frontend.src.utils.mapEditorFuncHardwareSummary  [6 funcs]
    apiBindingHint  CC=12  out:0
    objectMap  CC=3  out:2
    resolveNamedActionHardwareHint  CC=7  out:4
    resolveObjectActionHardwareHint  CC=6  out:2
    summarizeFuncToHardware  CC=17  out:6
    uniqueHints  CC=5  out:5
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
  frontend.src.utils.url-embed-config  [21 funcs]
    applyParentContextPayload  CC=5  out:5
    applyUrlEmbedPatch  CC=7  out:7
    base  CC=3  out:3
    fromUser  CC=4  out:3
    href  CC=4  out:3
    mergeParentContext  CC=7  out:4
    mergeParentSearchIntoChildUrl  CC=6  out:10
    nextHref  CC=1  out:1
    parentSearch  CC=4  out:3
    parseAppearanceParams  CC=9  out:4
  frontend.src.utils.useSelectionCollapsePanel  [16 funcs]
    RAIL_HOVER_CLOSE_MS  CC=33  out:21
    RAIL_HOVER_OPEN_MS  CC=33  out:21
    cancelAutoCollapse  CC=2  out:2
    cancelPanelClose  CC=2  out:2
    cancelRailOpen  CC=2  out:2
    expand  CC=1  out:5
    onMessage  CC=8  out:3
    panelEnter  CC=1  out:2
    panelLeave  CC=4  out:5
    previewCollapse  CC=1  out:2
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
  oqlos.core._cql_tree_builder  [2 funcs]
    _parse_action_line  CC=4  out:3
    _parse_metadata_kv  CC=6  out:5
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
    _parse_action_line  CC=10  out:18
    _parse_if_condition  CC=9  out:22
    _parse_inline_task  CC=5  out:7
    _parse_pump_line  CC=6  out:8
    _parse_set_line  CC=12  out:21
    _parse_task_part  CC=10  out:14
    _set_lung_step  CC=4  out:3
    _set_pump_step  CC=4  out:3
    _set_valve_step  CC=4  out:4
  oqlos.core._oql_adapter  [15 funcs]
    register  CC=1  out:1
    _cmd_to_actions  CC=2  out:3
    _fmt_value  CC=2  out:1
    _load_includes  CC=12  out:15
    _lower_call  CC=6  out:10
    _lower_max  CC=1  out:3
    _lower_min  CC=1  out:3
    _lower_set  CC=1  out:3
    _parse_macro_line  CC=8  out:10
    _resolve_include  CC=6  out:8
  oqlos.core.base  [5 funcs]
    send_event  CC=4  out:7
    emit  CC=5  out:3
    output_yaml  CC=4  out:2
    __init__  CC=2  out:1
    all  CC=3  out:3
  oqlos.core.cql_parser  [3 funcs]
    _try_top_level  CC=2  out:1
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
  oqlos.core.oql_parser  [31 funcs]
    _check_unnamed_goals  CC=5  out:1
    _expand_repeat_block_lines  CC=8  out:16
    _expand_repeat_blocks  CC=2  out:2
    _handle_block_header  CC=8  out:12
    _handle_modifier_cmd  CC=5  out:3
    _handle_set_name  CC=5  out:8
    _handle_top_level_line  CC=6  out:16
    _line_indent  CC=2  out:5
    _parse_and_append_command  CC=5  out:9
    _require  CC=2  out:2
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
  frontend.src.hooks.useUrlConfig.useUrlConfig → frontend.src.hooks.useUrlConfig.notifyParentChildReady
  frontend.src.hooks.useParentEncoderNavigation.createEncoderController → frontend.src.hooks.useParentEncoderNavigation.removeHighlights
  frontend.src.hooks.useParentEncoderNavigation.createEncoderController → frontend.src.hooks.useParentEncoderNavigation.getInteractiveItems
  frontend.src.hooks.useParentEncoderNavigation.createEncoderController → frontend.src.hooks.useParentEncoderNavigation.handleEncoderCommand
  frontend.src.hooks.useParentEncoderNavigation.parentEncoderActive → frontend.src.hooks.useParentEncoderNavigation.removeHighlights
  frontend.src.hooks.useParentEncoderNavigation.parentEncoderActive → frontend.src.hooks.useParentEncoderNavigation.getInteractiveItems
  frontend.src.hooks.useParentEncoderNavigation.handleEncoderCommand → frontend.src.hooks.useParentEncoderNavigation.removeHighlights
  frontend.src.hooks.useParentEncoderNavigation.handleEncoderCommand → frontend.src.hooks.useParentEncoderNavigation.getInteractiveItems
  frontend.src.hooks.useParentEncoderNavigation.items → frontend.src.hooks.useParentEncoderNavigation.removeHighlights
  frontend.src.hooks.useParentEncoderNavigation.onKeyDown → frontend.src.hooks.useParentEncoderNavigation.handleEncoderCommand
  frontend.src.hooks.useParentEncoderNavigation.useParentEncoderNavigation → frontend.src.hooks.useParentEncoderNavigation.createEncoderController
  frontend.src.hooks.useParentEncoderNavigation.useParentEncoderNavigation → frontend.src.hooks.useParentEncoderNavigation.parseParentEncoderEnvelope
  frontend.src.hooks.useParentEncoderNavigation.useParentEncoderNavigation → frontend.src.hooks.useParentEncoderNavigation.handleEncoderCommand
  frontend.src.hooks.useParentEncoderNavigation.controller → frontend.src.hooks.useParentEncoderNavigation.parseParentEncoderEnvelope
  frontend.src.hooks.useParentEncoderNavigation.controller → frontend.src.hooks.useParentEncoderNavigation.handleEncoderCommand
  frontend.src.hooks.useParentEncoderNavigation.onMessage → frontend.src.hooks.useParentEncoderNavigation.parseParentEncoderEnvelope
  frontend.src.hooks.useParentEncoderNavigation.onMessage → frontend.src.hooks.useParentEncoderNavigation.handleEncoderCommand
  frontend.src.hooks.useParentEncoderNavigation.onWheel → frontend.src.hooks.useParentEncoderNavigation.handleEncoderCommand
  frontend.src.hooks.useParentEncoderNavigation.raw → frontend.src.hooks.useParentEncoderNavigation.handleEncoderCommand
  frontend.src.pages.MapEditor.fillMissingFields → frontend.src.pages.MapEditor.isPlainObject
  frontend.src.pages.MapEditor.fillMissingFields → frontend.src.pages.MapEditor.cloneValue
  frontend.src.pages.MapEditor.ensureRequiredDefaultMappings → frontend.src.pages.MapEditor.ensureMapShape
  frontend.src.pages.MapEditor.ensureRequiredDefaultMappings → frontend.src.pages.MapEditor.fillMissingFields
  frontend.src.pages.MapEditor.ensureRequiredDefaultMappings → frontend.src.pages.MapEditor.isPlainObject
  frontend.src.pages.MapEditor.defaultMotor2 → frontend.src.pages.MapEditor.fillMissingFields
  frontend.src.pages.MapEditor.defaultMotor2 → frontend.src.pages.MapEditor.isPlainObject
  frontend.src.pages.MapEditor.defaultParam → frontend.src.pages.MapEditor.fillMissingFields
  frontend.src.pages.MapEditor.defaultParam → frontend.src.pages.MapEditor.isPlainObject
  frontend.src.pages.MapEditor.readIntegrationMeta → frontend.src.pages.MapEditor.firstBindingFromObjectMapping
  frontend.src.pages.MapEditor.ensureMapShape → frontend.src.pages.MapEditor.isPlainObject
  frontend.src.pages.MapEditor.src → frontend.src.pages.MapEditor.isPlainObject
  frontend.src.pages.MapEditor.toPrettyJson → frontend.src.pages.MapEditor.ensureMapShape
  frontend.src.pages.MapEditor.createInitialEditorState → frontend.src.pages.MapEditor.ensureRequiredDefaultMappings
  frontend.src.pages.MapEditor.createInitialEditorState → frontend.src.pages.MapEditor.cloneDefaultMap
  frontend.src.pages.MapEditor.createInitialEditorState → frontend.src.pages.MapEditor.toPrettyJson
  frontend.src.pages.MapEditor.onJsonChange → frontend.src.pages.MapEditor.isPlainObject
  frontend.src.pages.MapEditor.onJsonChange → frontend.src.pages.MapEditor.ensureMapShape
  frontend.src.pages.MapEditor.parsed → frontend.src.pages.MapEditor.isPlainObject
  frontend.src.pages.MapEditor.applyMapMutation → frontend.src.pages.MapEditor.ensureMapShape
  frontend.src.pages.MapEditor.applyMapMutation → frontend.src.pages.MapEditor.toPrettyJson
  frontend.src.pages.MapEditor.addObject → frontend.src.pages.MapEditor.applyMapMutation
  frontend.src.pages.MapEditor.name → frontend.src.pages.MapEditor.applyMapMutation
  frontend.src.pages.MapEditor.addParam → frontend.src.pages.MapEditor.applyMapMutation
  frontend.src.pages.MapEditor.editParamConversionField → frontend.src.pages.MapEditor.applyMapMutation
```

### Code Analysis (`project/analysis.toon.yaml`)

```toon markpact:analysis path=project/analysis.toon.yaml
# code2llm | 267f 55434L | python:161,javascript:47,md:19,yaml:13,shell:9,json:6,yml:4,typescript:3,conf:2,toml:1 | 2026-06-30
# generated in 0.13s
# CC̅=4.0 | critical:23/2128 | dups:0 | cycles:0

HEALTH[20]:
  🟡 CC    createEncoderController CC=21 (limit:15)
  🟡 CC    parentEncoderActive CC=15 (limit:15)
  🟡 CC    handleEncoderCommand CC=15 (limit:15)
  🟡 CC    readIntegrationMeta CC=15 (limit:15)
  🟡 CC    setMetaField CC=24 (limit:15)
  🟡 CC    editObjectActionArg CC=24 (limit:15)
  🟡 CC    renderObjectActionEditor CC=21 (limit:15)
  🟡 CC    loadPlan CC=18 (limit:15)
  🟡 CC    runCurrentStep CC=20 (limit:15)
  🟡 CC    cancelled CC=16 (limit:15)
  🟡 CC    normalizeHardwareEvent CC=21 (limit:15)
  🟡 CC    RAIL_HOVER_OPEN_MS CC=33 (limit:15)
  🟡 CC    RAIL_HOVER_CLOSE_MS CC=33 (limit:15)
  🟡 CC    useSelectionCollapsePanel CC=33 (limit:15)
  🟡 CC    executeConfigureStep CC=48 (limit:15)
  🟡 CC    summarizeFuncToHardware CC=17 (limit:15)
  🟡 CC    selectWizardProbeCandidate CC=22 (limit:15)
  🟡 CC    API_BASE CC=17 (limit:15)
  🟡 CC    request CC=17 (limit:15)
  🟡 CC    failureFromOkFalsePayload CC=19 (limit:15)

REFACTOR[1]:
  1. split 20 high-CC methods  (CC>15)

PIPELINES[1071]:
  [1] Src [main]: main → run_oql_scenario → print
      PURITY: 100% pure
  [2] Src [LocalizedApp]: LocalizedApp
      PURITY: 100% pure
  [3] Src [useWsStatus]: useWsStatus
      PURITY: 100% pure
  [4] Src [client]: client
      PURITY: 100% pure
  [5] Src [onOpen]: onOpen
      PURITY: 100% pure
  [6] Src [onClose]: onClose
      PURITY: 100% pure
  [7] Src [useUrlConfig]: useUrlConfig → notifyParentChildReady
      PURITY: 100% pure
  [8] Src [onPop]: onPop
      PURITY: 100% pure
  [9] Src [onMessage]: onMessage
      PURITY: 100% pure
  [10] Src [envelope]: envelope
      PURITY: 100% pure
  [11] Src [patch]: patch
      PURITY: 100% pure
  [12] Src [parentEncoderActive]: parentEncoderActive → removeHighlights
      PURITY: 100% pure
  [13] Src [items]: items → removeHighlights
      PURITY: 100% pure
  [14] Src [target]: target
      PURITY: 100% pure
  [15] Src [onKeyDown]: onKeyDown → handleEncoderCommand → removeHighlights
      PURITY: 100% pure
  [16] Src [useParentEncoderNavigation]: useParentEncoderNavigation → createEncoderController → removeHighlights
      PURITY: 100% pure
  [17] Src [controller]: controller → parseParentEncoderEnvelope
      PURITY: 100% pure
  [18] Src [onMessage]: onMessage → parseParentEncoderEnvelope
      PURITY: 100% pure
  [19] Src [onWheel]: onWheel → handleEncoderCommand → removeHighlights
      PURITY: 100% pure
  [20] Src [raw]: raw → handleEncoderCommand → removeHighlights
      PURITY: 100% pure
  [21] Src [syncParentUrl]: syncParentUrl
      PURITY: 100% pure
  [22] Src [location]: location
      PURITY: 100% pure
  [23] Src [collapseEnabled]: collapseEnabled
      PURITY: 100% pure
  [24] Src [inPreview]: inPreview
      PURITY: 100% pure
  [25] Src [filtered]: filtered
      PURITY: 100% pure
  [26] Src [handleSelect]: handleSelect
      PURITY: 100% pure
  [27] Src [LIVE_EVENTS_LIMIT]: LIVE_EVENTS_LIMIT
      PURITY: 100% pure
  [28] Src [TIC249_TARGET_VELOCITY_SCALE]: TIC249_TARGET_VELOCITY_SCALE
      PURITY: 100% pure
  [29] Src [GROUP_FOR_TAB]: GROUP_FOR_TAB
      PURITY: 100% pure
  [30] Src [SECTION_DESC_KEY]: SECTION_DESC_KEY
      PURITY: 100% pure
  [31] Src [EMPTY_KEY]: EMPTY_KEY
      PURITY: 100% pure
  [32] Src [META_FIELDS]: META_FIELDS
      PURITY: 100% pure
  [33] Src [PARAM_CONVERSION_ALGORITHMS]: PARAM_CONVERSION_ALGORITHMS
      PURITY: 100% pure
  [34] Src [value]: value
      PURITY: 100% pure
  [35] Src [shaped]: shaped
      PURITY: 100% pure
  [36] Src [defaultMotor2]: defaultMotor2 → fillMissingFields → isPlainObject
      PURITY: 100% pure
  [37] Src [defaultParam]: defaultParam → fillMissingFields → isPlainObject
      PURITY: 100% pure
  [38] Src [readIntegrationMeta]: readIntegrationMeta → firstBindingFromObjectMapping
      PURITY: 100% pure
  [39] Src [src]: src → isPlainObject
      PURITY: 100% pure
  [40] Src [createInitialEditorState]: createInitialEditorState → ensureRequiredDefaultMappings → ensureMapShape → isPlainObject
      PURITY: 100% pure
  [41] Src [seeded]: seeded
      PURITY: 100% pure
  [42] Src [wsOnline]: wsOnline
      PURITY: 100% pure
  [43] Src [initial]: initial
      PURITY: 100% pure
  [44] Src [tab]: tab
      PURITY: 100% pure
  [45] Src [canClearServerEvents]: canClearServerEvents
      PURITY: 100% pure
  [46] Src [canClearPersistentEvents]: canClearPersistentEvents
      PURITY: 100% pure
  [47] Src [isDirty]: isDirty
      PURITY: 100% pure
  [48] Src [setTabAndUrl]: setTabAndUrl
      PURITY: 100% pure
  [49] Src [url]: url
      PURITY: 100% pure
  [50] Src [onJsonChange]: onJsonChange → isPlainObject
      PURITY: 100% pure

LAYERS:
  ./                              CC̄=6.9    ←in:0  →out:0
  │ !! openapi_spec.yaml         1035L  0C    0m  CC=0.0    ←0
  │ !! openapi.yaml              1035L  0C    0m  CC=0.0    ←0
  │ !! README.md                  772L  0C    0m  CC=0.0    ←0
  │ !! goal.yaml                  511L  0C    0m  CC=0.0    ←0
  │ CHANGELOG.md               496L  0C    0m  CC=0.0    ←0
  │ hw_diagnostic_20260415_133138.json   340L  0C    0m  CC=0.0    ←0
  │ setup_hardware_and_run_oql   333L  0C    7m  CC=12     ←0
  │ Taskfile.yml               166L  0C    0m  CC=0.0    ←0
  │ sumd.json                  150L  0C    0m  CC=0.0    ←0
  │ Makefile                    86L  0C    0m  CC=0.0    ←0
  │ pyproject.toml              81L  0C    0m  CC=0.0    ←0
  │ pyqual.yaml                 49L  0C    0m  CC=0.0    ←0
  │ testql-contracts.testql.toon.yaml    49L  0C    0m  CC=0.0    ←0
  │ Taskfile.testql.yml         48L  0C    0m  CC=0.0    ←0
  │ project.sh                  43L  0C    0m  CC=0.0    ←0
  │ TODO.md                     36L  0C    0m  CC=0.0    ←0
  │
  oqlos/                          CC̄=4.0    ←in:8  →out:0
  │ !! hardware                  2266L  0C   93m  CC=14     ←2
  │ !! doctor                     971L  0C   42m  CC=13     ←2
  │ !! _interpreter_actions       800L  0C   49m  CC=14     ←1
  │ !! oql_parser                 762L  3C   43m  CC=14     ←2
  │ !! interpreter                690L  1C   48m  CC=11     ←0
  │ !! plugin_gateway             631L  1C   22m  CC=14     ←0
  │ !! diagnosis                  562L  3C   26m  CC=13     ←1
  │ !! motor                      549L  1C   20m  CC=14     ←0
  │ mqtt_oql_bridge            494L  6C   34m  CC=5      ←0
  │ _oql_adapter               486L  1C   29m  CC=12     ←2
  │ _action_motor2             481L  0C   30m  CC=13     ←1
  │ firmware_adapter           481L  1C   26m  CC=12     ←0
  │ cql_parser                 467L  1C   30m  CC=8      ←2
  │ proxy                      460L  1C   29m  CC=13     ←0
  │ generators                 452L  0C   20m  CC=14     ←0
  │ gateway                    416L  5C   25m  CC=7      ←0
  │ main                       415L  1C   18m  CC=9      ←2
  │ _cql_tokenizer             406L  0C   27m  CC=5      ←0
  │ modbus_adc                 398L  1C   17m  CC=12     ←0
  │ executor                   383L  1C   21m  CC=14     ←0
  │ base                       370L  9C   21m  CC=5      ←3
  │ state                      370L  0C   16m  CC=13     ←0
  │ main                       370L  0C   22m  CC=8      ←0
  │ lung                       361L  1C   20m  CC=14     ←0
  │ execution                  359L  0C   16m  CC=11     ←0
  │ plugin_cli                 343L  0C   14m  CC=8      ←3
  │ modbus                     335L  1C   16m  CC=11     ←0
  │ identify_enrich            333L  0C   18m  CC=13     ←0
  │ registry                   332L  1C   14m  CC=6      ←0
  │ base                       311L  7C   29m  CC=7      ←15
  │ preflight                  309L  0C   11m  CC=13     ←1
  │ schema                     296L  5C    6m  CC=7      ←0
  │ piadc                      272L  1C   12m  CC=11     ←0
  │ html_report                266L  0C    5m  CC=10     ←0
  │ scanner_probe              262L  0C   13m  CC=14     ←1
  │ scenarios                  251L  0C   16m  CC=11     ←0
  │ _line_parsers              246L  0C    9m  CC=12     ←1
  │ sidecar_control            222L  0C    9m  CC=13     ←1
  │ !! manage_ops                 222L  0C    7m  CC=19     ←3
  │ config                     220L  1C    1m  CC=1      ←5
  │ tic249_extended            215L  0C    7m  CC=10     ←0
  │ _firmware_executor         210L  1C    9m  CC=11     ←0
  │ OQL-CHEATSHEET.md          210L  0C    0m  CC=0.0    ←0
  │ motor2_runtime             209L  2C   12m  CC=12     ←1
  │ modbus_probe               205L  0C   16m  CC=5      ←1
  │ rtc_probe                  197L  0C    7m  CC=11     ←1
  │ _hw3_models                194L  9C    7m  CC=14     ←3
  │ commands                   192L  0C    6m  CC=8      ←2
  │ hui_hold                   188L  0C   11m  CC=5      ←2
  │ usb_diagnostics            185L  0C    5m  CC=13     ←0
  │ __main__                   184L  0C   11m  CC=6      ←0
  │ parser                     183L  0C    5m  CC=13     ←2
  │ tic249_sidecar_client      183L  0C    9m  CC=9      ←1
  │ plugins                    181L  0C   12m  CC=3      ←2
  │ parser                     175L  0C    6m  CC=9      ←0
  │ event_server               171L  2C   11m  CC=7      ←0
  │ _cql_tree_builder          167L  0C    9m  CC=12     ←2
  │ modbus_repair              164L  0C    7m  CC=13     ←1
  │ discovery                  163L  0C    4m  CC=5      ←0
  │ artificial_lung            162L  0C   10m  CC=6      ←0
  │ _hw3_mapping               157L  0C   12m  CC=10     ←0
  │ hardware_mapping_store     152L  1C   13m  CC=8      ←1
  │ oql_mqtt                   151L  3C    6m  CC=6      ←1
  │ utils                      150L  0C   10m  CC=8      ←4
  │ _sensor_evaluator          145L  1C    6m  CC=10     ←0
  │ config_schema              145L  1C    4m  CC=2      ←0
  │ logs_query                 145L  1C    5m  CC=11     ←1
  │ editor                     141L  3C    6m  CC=5      ←0
  │ README.md                  140L  0C    0m  CC=0.0    ←0
  │ safe_eval                  138L  1C   10m  CC=4      ←0
  │ shell                      138L  0C    5m  CC=6      ←1
  │ peripheral_mapping         138L  0C    4m  CC=2      ←0
  │ json_reporter              138L  0C    5m  CC=8      ←0
  │ autorepair                 137L  0C    9m  CC=12     ←0
  │ hardware_events            135L  0C   10m  CC=11     ←3
  │ _hw3_peripheral            133L  0C    5m  CC=11     ←0
  │ _hw3_system                133L  0C   19m  CC=6      ←0
  │ _dsl_helpers               132L  0C   12m  CC=11     ←4
  │ modbus_identify            131L  0C    8m  CC=10     ←1
  │ resolvers                  128L  0C   10m  CC=10     ←1
  │ tic249_motion_params       128L  0C    6m  CC=13     ←2
  │ _value_normalizers         126L  1C    7m  CC=10     ←0
  │ release_version            125L  0C    7m  CC=11     ←1
  │ state                      124L  1C    3m  CC=4      ←0
  │ mqtt                       119L  1C    9m  CC=3      ←0
  │ health                     117L  0C    7m  CC=8      ←7
  │ tic249_error_messages      112L  0C    6m  CC=14     ←2
  │ file_ops                   108L  1C    5m  CC=4      ←1
  │ _utils                     101L  0C    6m  CC=12     ←1
  │ __init__                   100L  0C    0m  CC=0.0    ←0
  │ discovery                   99L  1C    5m  CC=8      ←5
  │ _func_resolver              96L  0C    4m  CC=13     ←1
  │ calibration                 92L  0C    4m  CC=5      ←3
  │ spi                         92L  1C    7m  CC=4      ←0
  │ models                      90L  5C    0m  CC=0.0    ←0
  │ gpio                        89L  1C    7m  CC=6      ←0
  │ logger                      89L  0C    2m  CC=12     ←0
  │ !! hardware_mapping_contract    89L  1C    4m  CC=19     ←1
  │ stack_snapshot              88L  0C    4m  CC=8      ←1
  │ dsl_models                  87L  8C    0m  CC=0.0    ←0
  │ config                      86L  1C    6m  CC=6      ←1
  │ junit                       86L  1C    3m  CC=8      ←0
  │ config_factory              84L  0C    1m  CC=1      ←0
  │ hui_artificial_lung         83L  0C    3m  CC=6      ←1
  │ event_store                 77L  1C   10m  CC=3      ←0
  │ __init__                    73L  0C    1m  CC=1      ←0
  │ sample_data                 73L  0C    1m  CC=1      ←1
  │ oql_versioning              72L  1C    4m  CC=4      ←1
  │ peripherals                 70L  0C    4m  CC=5      ←0
  │ constants                   69L  0C    0m  CC=0.0    ←0
  │ control_proxy               68L  1C    1m  CC=1      ←0
  │ __init__                    66L  0C    2m  CC=1      ←0
  │ version_endpoint            66L  0C    2m  CC=3      ←0
  │ tic249_arg_contract         65L  0C    2m  CC=8      ←2
  │ adc                         64L  0C    3m  CC=10     ←2
  │ report                      63L  0C    2m  CC=12     ←3
  │ formatting                  63L  0C    3m  CC=14     ←2
  │ execution_ctrl              62L  0C    3m  CC=1      ←0
  │ protocol                    60L  2C    6m  CC=1      ←0
  │ hardware_v3                 60L  0C    3m  CC=2      ←0
  │ _shared                     59L  0C    5m  CC=2      ←3
  │ hui_actions                 58L  0C    1m  CC=2      ←1
  │ benchmark                   55L  0C    1m  CC=6      ←2
  │ platform                    50L  0C    3m  CC=6      ←0
  │ registry                    49L  1C    3m  CC=2      ←0
  │ tic249_command_mapping      49L  0C    2m  CC=13     ←1
  │ __init__                    49L  0C    0m  CC=0.0    ←0
  │ hui_scenario                46L  0C    1m  CC=2      ←1
  │ logs                        45L  0C    3m  CC=1      ←0
  │ tic249_rig_direction        43L  0C    2m  CC=5      ←1
  │ hui_lung_recipe             42L  0C    1m  CC=1      ←0
  │ config_paths                41L  0C    1m  CC=6      ←4
  │ _compare                    40L  0C    2m  CC=3      ←2
  │ tic249_units                39L  0C    2m  CC=5      ←2
  │ scenario                    35L  4C    0m  CC=0.0    ←0
  │ _endpoint_helpers           34L  0C    2m  CC=2      ←1
  │ _rtu_serial                 33L  0C    2m  CC=4      ←2
  │ peripheral                  33L  4C    0m  CC=0.0    ←0
  │ health_status               26L  0C    1m  CC=11     ←2
  │ errors                      26L  1C    3m  CC=6      ←2
  │ http_helpers                26L  0C    2m  CC=10     ←1
  │ __init__                    24L  0C    0m  CC=0.0    ←0
  │ version                     24L  0C    0m  CC=0.0    ←0
  │ execution                   22L  3C    0m  CC=0.0    ←0
  │ __init__                    19L  0C    0m  CC=0.0    ←0
  │ identify_enrichment         18L  0C    1m  CC=2      ←1
  │ __init__                    17L  0C    0m  CC=0.0    ←0
  │ __init__                    17L  0C    0m  CC=0.0    ←0
  │ __init__                    17L  0C    0m  CC=0.0    ←0
  │ tic249_arg_helpers          11L  0C    1m  CC=4      ←2
  │ __init__                     6L  0C    0m  CC=0.0    ←0
  │ __init__                     5L  0C    0m  CC=0.0    ←0
  │ __init__                     3L  0C    0m  CC=0.0    ←0
  │ __init__                     3L  0C    0m  CC=0.0    ←0
  │ __init__                     0L  0C    0m  CC=0.0    ←0
  │
  frontend/                       CC̄=3.9    ←in:0  →out:0
  │ !! dictionaries.js           1981L  0C    4m  CC=5      ←0
  │ !! mapEditorDefaultMap.js    1763L  0C    3m  CC=1      ←0
  │ !! MapEditor.jsx             1490L  0C  109m  CC=24     ←6
  │ !! hardware-status-presets-translations.js   795L  0C    0m  CC=0.0    ←0
  │ !! HardwareDemo.jsx           585L  0C   41m  CC=16     ←0
  │ !! HardwareRestart.jsx        501L  0C   49m  CC=20     ←2
  │ SidebarList.jsx            316L  0C    4m  CC=6      ←0
  │ hardware-status-panel-translations.js   309L  0C    0m  CC=0.0    ←0
  │ !! hardwareApi.js             256L  0C   21m  CC=17     ←0
  │ !! useSelectionCollapsePanel.js   191L  0C   22m  CC=33     ←0
  │ url-embed-config.js        191L  0C   43m  CC=12     ←0
  │ hardware-demo-extra-translations.js   183L  0C    0m  CC=0.0    ←0
  │ !! useParentEncoderNavigation.js   156L  0C   19m  CC=21     ←6
  │ wsClient.js                138L  1C   30m  CC=13     ←10
  │ rbac.policy.js             118L  0C   20m  CC=6      ←0
  │ !! hardware-wizard-steps.js   111L  0C   16m  CC=22     ←22
  │ !! hardware-restart-wizard-steps.js   109L  0C   24m  CC=48     ←1
  │ !! hardware-diagnostic-failure.js   102L  0C   16m  CC=19     ←0
  │ url-embed-config.test.js    92L  0C    6m  CC=2      ←0
  │ hardware-api-log.js         87L  0C    7m  CC=11     ←0
  │ useUrlConfig.js             85L  0C    6m  CC=8      ←0
  │ SharedNav.jsx               83L  0C    6m  CC=5      ←0
  │ hardware-status-log-translations.js    81L  0C    0m  CC=0.0    ←0
  │ !! mapEditorFuncHardwareSummary.js    80L  0C   16m  CC=17     ←0
  │ I18nProvider.jsx            65L  0C   10m  CC=13     ←23
  │ hardware-api-errors.js      63L  0C   10m  CC=13     ←0
  │ hardware-diagnostic-failure.test.js    58L  0C    0m  CC=0.0    ←0
  │ mapEditorFuncHardwareSummary.test.js    54L  0C    1m  CC=1      ←0
  │ !! hardwareEventStream.js      47L  0C   21m  CC=21     ←1
  │ collapse-toggle-bridge.js    46L  0C    6m  CC=4      ←0
  │ hardware-api-retry.test.js    45L  0C    3m  CC=2      ←0
  │ designRem.js                43L  0C    2m  CC=1      ←0
  │ AppConfigProvider.jsx       42L  0C    5m  CC=2      ←0
  │ parentUrlBridge.js          39L  0C    3m  CC=10     ←0
  │ paths.ts                    39L  0C    4m  CC=2      ←0
  │ hardware-api-retry.js       38L  0C    8m  CC=14     ←1
  │ hui-shell-key.js            38L  0C    5m  CC=5      ←0
  │ vite.config.ts              36L  0C    0m  CC=0.0    ←0
  │ hardware-tic249-status.js    35L  0C    6m  CC=12     ←0
  │ hardware-activity-log.js    34L  0C    4m  CC=2      ←0
  │ index.ts                    31L  0C    2m  CC=1      ←0
  │ main.jsx                    30L  0C    1m  CC=1      ←0
  │ HardwareStatus.jsx          28L  0C    1m  CC=5      ←0
  │ useWsStatus.js              26L  0C    4m  CC=3      ←0
  │ app-config-document.js      26L  0C    4m  CC=6      ←0
  │ HardwareActivityLog.jsx     24L  0C    0m  CC=0.0    ←0
  │ package.json                22L  0C    0m  CC=0.0    ←0
  │ App.jsx                     21L  0C    0m  CC=0.0    ←0
  │ hardware-restart-docs.js    11L  0C    2m  CC=2      ←0
  │ hardware-wizard-plan.js     10L  0C    2m  CC=5      ←0
  │ hardware-time.js             4L  0C    1m  CC=1      ←0
  │
  scripts/                        CC̄=3.8    ←in:0  →out:72  !! split
  │ !! oql_v2_to_v4_migrate_db    662L  1C   43m  CC=14     ←1
  │ hardware-check.sh          340L  0C   11m  CC=0.0    ←0
  │ migrate_to_v4              340L  0C   19m  CC=11     ←0
  │ scenarios_export           296L  0C   13m  CC=8      ←0
  │ oql_v4_validator           281L  1C    8m  CC=8      ←1
  │ oql_v2_validator           224L  1C    6m  CC=9      ←0
  │ oql_validator_common       129L  0C    6m  CC=11     ←2
  │ oql-stack.sh               104L  0C    5m  CC=0.0    ←0
  │ fix_brackets_to_v4          95L  0C    2m  CC=14     ←0
  │ test-hardware.sh            83L  0C    0m  CC=0.0    ←0
  │ verify-rpi-checksum.sh      75L  0C    1m  CC=0.0    ←0
  │ provision-rpi-sudo.sh       67L  0C    0m  CC=0.0    ←0
  │ gen-checksums.sh            24L  0C    0m  CC=0.0    ←0
  │
  examples/                       CC̄=0.0    ←in:0  →out:0
  │ plugin-config.yaml         128L  0C    0m  CC=0.0    ←0
  │ curl-quickstart.sh          74L  0C    0m  CC=0.0    ←0
  │ doctor-workflow.sh          52L  0C    1m  CC=0.0    ←17
  │
  docs/                           CC̄=0.0    ←in:0  →out:0
  │ !! README.md                 1879L  0C    0m  CC=0.0    ←0
  │ !! cql-examples.md            588L  0C    0m  CC=0.0    ←0
  │ HARDWARE_DIAGNOSTICS.md    428L  0C    0m  CC=0.0    ←0
  │ HARDWARE_CONTROL_OQL_MQTT.md   319L  0C    0m  CC=0.0    ←0
  │ oql-spec.md                258L  0C    0m  CC=0.0    ←0
  │ OQL_V4_MIGRATION_MANUAL.md   216L  0C    0m  CC=0.0    ←0
  │ DEDUP-connect-scenario.md   108L  0C    0m  CC=0.0    ←0
  │ oql_v4_llm_validator.schema.json    93L  0C    0m  CC=0.0    ←0
  │ oql_v2_llm_validator.schema.json    89L  0C    0m  CC=0.0    ←0
  │ cql-spec.md                 78L  0C    0m  CC=0.0    ←0
  │ refactor-plan.md            73L  0C    0m  CC=0.0    ←0
  │
  redeploy/                       CC̄=0.0    ←in:0  →out:0
  │ !! migration.md              1207L  0C    0m  CC=0.0    ←0
  │ !! migration.md               639L  0C    0m  CC=0.0    ←0
  │ RUNBOOK.md                 101L  0C    0m  CC=0.0    ←0
  │ RUNBOOK.md                  87L  0C    0m  CC=0.0    ←0
  │ CURRENT_STATE.md            80L  0C    0m  CC=0.0    ←0
  │ oqlos-hw.yaml               66L  0C    0m  CC=0.0    ←0
  │ oqlos-hw.yaml               66L  0C    0m  CC=0.0    ←0
  │ mosquitto.conf              19L  0C    0m  CC=0.0    ←0
  │ mosquitto.conf              19L  0C    0m  CC=0.0    ←0
  │
  docker/                         CC̄=0.0    ←in:0  →out:0
  │ docker-compose.dev.yml      29L  0C    0m  CC=0.0    ←0
  │ docker-compose.prod.yml     19L  0C    0m  CC=0.0    ←0
  │ Dockerfile                  11L  0C    0m  CC=0.0    ←0
  │
  testql-scenarios/               CC̄=0.0    ←in:0  →out:0
  │ generated-api-smoke.testql.toon.yaml    46L  0C    0m  CC=0.0    ←0
  │ generated-from-scenarios.testql.toon.yaml    18L  0C    0m  CC=0.0    ←0
  │ generated-api-integration.testql.toon.yaml    18L  0C    0m  CC=0.0    ←0
  │ generated-from-pytests.testql.toon.yaml    15L  0C    0m  CC=0.0    ←0
  │ cross-project-integration.testql.toon.yaml    11L  0C    0m  CC=0.0    ←0
  │
  scenarios/                      CC̄=0.0    ←in:0  →out:0
  │ manifest.json              182L  0C    0m  CC=0.0    ←0
  │
  ── zero ──
     oqlos/core/__init__.py                    0L

COUPLING:
                                             oqlos.tools           examples.hardware                frontend.src              oqlos.hardware                     scripts                   oqlos.api                  oqlos.core  setup_hardware_and_run_oql                oqlos.shared                       oqlos                   oqlos.dsl             oqlos.reporters                 oqlos.utils
                 oqlos.tools                          ──                         125                          89                           7                          ←3                                                      10                                                                                                                                                                          hub
           examples.hardware                        ←125                          ──                                                                                 ←64                                                      ←2                         ←27                          ←7                                                                                                                  hub
                frontend.src                         ←89                                                      ──                         ←72                          ←3                         ←20                         ←18                                                      ←4                                                      ←2                          ←2                              hub
              oqlos.hardware                           3                                                      72                          ──                          ←1                           1                           6                                                                                   3                                                                                      hub
                     scripts                           3                          64                           3                           1                          ──                                                       1                                                                                                                                                                          !! fan-out
                   oqlos.api                                                                                  20                          17                                                      ──                           6                                                       6                           1                                                                                   2  !! fan-out
                  oqlos.core                         ←10                           2                          18                          ←6                          ←1                          ←6                          ──                                                      ←1                           3                          ←1                                                          hub
  setup_hardware_and_run_oql                                                      27                                                                                                                                                                      ──                                                                                                                                              !! fan-out
                oqlos.shared                                                       7                           4                                                                                  ←6                           1                                                      ──                           1                                                                                      hub
                       oqlos                                                                                                              ←3                                                      ←1                          ←3                                                      ←1                          ──                                                                                      hub
                   oqlos.dsl                                                                                   2                                                                                                               1                                                                                                              ──                                                        
             oqlos.reporters                                                                                   2                                                                                                                                                                                                                                                          ──                            
                 oqlos.utils                                                                                                                                                                      ←2                                                                                                                                                                                                  ──
  CYCLES: none
  HUB: examples.hardware/ (fan-in=225)
  HUB: oqlos.shared/ (fan-in=6)
  HUB: oqlos.core/ (fan-in=25)
  HUB: oqlos.tools/ (fan-in=6)
  HUB: oqlos/ (fan-in=8)
  HUB: frontend.src/ (fan-in=210)
  HUB: oqlos.hardware/ (fan-in=25)
  SMELL: oqlos.shared/ fan-out=13 → split needed
  SMELL: oqlos.core/ fan-out=23 → split needed
  SMELL: oqlos.tools/ fan-out=231 → split needed
  SMELL: setup_hardware_and_run_oql/ fan-out=27 → split needed
  SMELL: oqlos.api/ fan-out=52 → split needed
  SMELL: scripts/ fan-out=72 → split needed
  SMELL: oqlos.hardware/ fan-out=85 → split needed

EXTERNAL:
  validation: run `vallm batch .` → validation.toon
  duplication: run `redup scan .` → duplication.toon
```

### Duplication (`project/duplication.toon.yaml`)

```toon markpact:analysis path=project/duplication.toon.yaml
# redup/duplication | 48 groups | 167f 31756L | 2026-06-30

SUMMARY:
  files_scanned: 167
  total_lines:   31756
  dup_groups:    48
  dup_fragments: 105
  saved_lines:   293
  scan_ms:       124766

HOTSPOTS[7] (files with most duplication):
  oqlos/core/_cql_tokenizer.py  dup=92L  groups=7  frags=16  (0.3%)
  oqlos/hardware/plugins/motor.py  dup=81L  groups=2  frags=4  (0.3%)
  oqlos/core/interpreter.py  dup=41L  groups=5  frags=11  (0.1%)
  oqlos/core/oql_parser.py  dup=39L  groups=4  frags=11  (0.1%)
  scripts/oql_v2_to_v4_migrate_db.py  dup=39L  groups=3  frags=7  (0.1%)
  oqlos/hardware/plugins/lung.py  dup=28L  groups=4  frags=6  (0.1%)
  oqlos/hardware/gateway.py  dup=25L  groups=2  frags=5  (0.1%)

DUPLICATES[48] (ranked by impact):
  [F0024]   FUZZ  _handle_stop_cli  L=21 N=2 saved=21 sim=0.88
      oqlos/hardware/plugins/motor.py:361-381  (_handle_stop_cli)
      oqlos/hardware/plugins/motor.py:278-300  (_handle_set_speed_cli)
  [F0023]   FUZZ  _handle_stop_http  L=18 N=2 saved=18 sim=0.89
      oqlos/hardware/plugins/motor.py:342-359  (_handle_stop_http)
      oqlos/hardware/plugins/motor.py:413-431  (_handle_status_http)
  [F0022]   FUZZ  _exec_set_peripheral  L=11 N=2 saved=11 sim=0.94
      oqlos/core/interpreter.py:333-343  (_exec_set_peripheral)
      oqlos/core/_firmware_executor.py:197-210  (exec_set_peripheral)
  [072bf17442930dfb]   STRU  _try_task  L=5 N=3 saved=10 sim=1.00
      oqlos/core/_cql_tokenizer.py:163-167  (_try_task)
      oqlos/core/_cql_tokenizer.py:242-246  (_try_if_fail_block)
      oqlos/core/_cql_tokenizer.py:368-372  (_try_save_ws)
  [72f2147f8d49b415]   STRU  parse_SET  L=5 N=3 saved=10 sim=1.00
      oqlos/core/oql_parser.py:247-251  (parse_SET)
      oqlos/core/oql_parser.py:349-353  (parse_MIN)
      oqlos/core/oql_parser.py:356-360  (parse_MAX)
  [d884e769a616fa58]   STRU  _merge_object_function_map  L=10 N=2 saved=10 sim=1.00
      oqlos/dsl/schema.py:99-108  (_merge_object_function_map)
      oqlos/dsl/schema.py:111-120  (_merge_param_unit_map)
  [F0013]   FUZZ  _try_set  L=5 N=3 saved=10 sim=0.88
      oqlos/core/_cql_tokenizer.py:179-183  (_try_set)
      oqlos/core/_cql_tokenizer.py:282-286  (_try_val)
      oqlos/core/_cql_tokenizer.py:362-366  (_try_goto)
  [F0015]   FUZZ  read_channel  L=5 N=3 saved=10 sim=0.87
      oqlos/hardware/gateway.py:92-96  (read_channel)
      oqlos/hardware/gateway.py:125-129  (_stop)
      oqlos/hardware/gateway.py:165-169  (stop)
  [F0017]   FUZZ  _mig_goto  L=5 N=3 saved=10 sim=0.85
      scripts/oql_v2_to_v4_migrate_db.py:377-381  (_mig_goto)
      scripts/oql_v2_to_v4_migrate_db.py:391-395  (_mig_else_info)
      scripts/oql_v2_to_v4_migrate_db.py:398-402  (_mig_set_name)
  [F0021]   FUZZ  _mig_minmax_eq  L=8 N=2 saved=8 sim=0.92
      scripts/oql_v2_to_v4_migrate_db.py:313-320  (_mig_minmax_eq)
      scripts/oql_v2_to_v4_migrate_db.py:323-330  (_mig_minmax_simple)
  [F0019]   FUZZ  _make_args_parser  L=8 N=2 saved=8 sim=0.91
      oqlos/core/_cql_tokenizer.py:97-104  (_make_args_parser)
      oqlos/core/_cql_tokenizer.py:116-123  (_make_method_parser)
  [9467529f149d5e22]   STRU  _migrate_wait_line  L=7 N=2 saved=7 sim=1.00
      scripts/migrate_to_v4.py:115-121  (_migrate_wait_line)
      scripts/migrate_to_v4.py:139-145  (_migrate_save_line)
  [F0020]   FUZZ  _try_arrow_action  L=8 N=2 saved=8 sim=0.86
      oqlos/core/_cql_tokenizer.py:154-161  (_try_arrow_action)
      oqlos/core/_cql_tokenizer.py:331-338  (_try_func)
  [b81931e6691429a5]   EXAC  modbus_plugins_need_repair  L=6 N=2 saved=6 sim=1.00
      oqlos/hardware/client/autorepair.py:34-39  (modbus_plugins_need_repair)
      oqlos/hardware/diagnosis.py:114-119  (modbus_plugins_need_repair)
  [9b5d9d160eb47842]   STRU  parse_GET  L=3 N=3 saved=6 sim=1.00
      oqlos/core/oql_parser.py:254-256  (parse_GET)
      oqlos/core/oql_parser.py:306-308  (parse_SAVE)
      oqlos/core/oql_parser.py:402-404  (parse_INCLUDE)
  [c5e35493de881001]   STRU  parse_LOG  L=3 N=3 saved=6 sim=1.00
      oqlos/core/oql_parser.py:382-384  (parse_LOG)
      oqlos/core/oql_parser.py:387-389  (parse_ERROR)
      oqlos/core/oql_parser.py:392-394  (parse_CORRECT)
  [F0018]   FUZZ  _handle_stop_http  L=6 N=2 saved=6 sim=0.97
      oqlos/hardware/plugins/lung.py:242-247  (_handle_stop_http)
      oqlos/hardware/plugins/lung.py:283-288  (_handle_status_http)
  [F0005]   FUZZ  _execute_firmware_action  L=3 N=3 saved=6 sim=0.93
      oqlos/core/interpreter.py:349-351  (_execute_firmware_action)
      oqlos/core/interpreter.py:353-355  (_execute_plugin_action)
      oqlos/core/interpreter.py:357-359  (_execute_legacy_firmware_action)
  [F0002]   FUZZ  _firmware  L=3 N=3 saved=6 sim=0.89
      oqlos/core/interpreter.py:94-96  (_firmware)
      oqlos/core/interpreter.py:104-106  (_firmware_url)
      oqlos/core/interpreter.py:345-347  (_get_firmware)
  [ced4a13b5d82a294]   EXAC  _read_text_file  L=5 N=2 saved=5 sim=1.00
      oqlos/api/hardware.py:104-108  (_read_text_file)
      oqlos/hardware/plugins/piadc.py:46-50  (_read_text_file)
  [c7eda7834116d40a]   EXAC  status  L=5 N=2 saved=5 sim=1.00
      oqlos/hardware/gateway.py:131-135  (status)
      oqlos/hardware/gateway.py:187-191  (status)
  [ebadd0f3390a1c0f]   EXAC  _rtu_timeout  L=5 N=2 saved=5 sim=1.00
      oqlos/hardware/plugins/modbus.py:284-288  (_rtu_timeout)
      oqlos/hardware/plugins/modbus_adc.py:338-342  (_rtu_timeout)
  [a3842246ff983396]   EXAC  _device_id  L=5 N=2 saved=5 sim=1.00
      oqlos/hardware/plugins/modbus.py:299-303  (_device_id)
      oqlos/hardware/plugins/modbus_adc.py:344-348  (_device_id)
  [6ce3ede44946ab4e]   STRU  get_execution  L=5 N=2 saved=5 sim=1.00
      oqlos/api/execution.py:199-203  (get_execution)
      oqlos/api/peripherals.py:18-22  (get_peripheral)
  [b022b8a8c97925d7]   STRU  _default_path  L=5 N=2 saved=5 sim=1.00
      oqlos/api/hardware_events.py:18-22  (_default_path)
      oqlos/api/hardware_mapping_store.py:23-27  (_default_path)
  [604ad2c312cebf88]   STRU  _try_var  L=5 N=2 saved=5 sim=1.00
      oqlos/core/_cql_tokenizer.py:322-326  (_try_var)
      oqlos/core/_cql_tokenizer.py:352-356  (_try_api)
  [43e47beaf70d4a45]   STRU  disconnect  L=5 N=2 saved=5 sim=1.00
      oqlos/hardware/plugins/lung.py:84-88  (disconnect)
      oqlos/hardware/plugins/piadc.py:141-145  (disconnect)
  [60cc1d39480c5789]   STRU  _match_blob  L=5 N=2 saved=5 sim=1.00
      oqlos/hardware/scanner_probe.py:57-61  (_match_blob)
      oqlos/hardware/scanner_probe.py:88-92  (_usb_product_blob)
  [F0012]   FUZZ  parser  L=5 N=2 saved=5 sim=0.91
      oqlos/core/_cql_tokenizer.py:99-103  (parser)
      oqlos/core/_cql_tokenizer.py:118-122  (parser)
  [F0016]   FUZZ  _read_address  L=5 N=2 saved=5 sim=0.90
      oqlos/hardware/plugins/modbus_adc.py:350-354  (_read_address)
      oqlos/hardware/plugins/modbus_adc.py:356-360  (_read_count)
  [F0014]   FUZZ  _try_repeat_start  L=5 N=2 saved=5 sim=0.86
      oqlos/core/_cql_tokenizer.py:310-314  (_try_repeat_start)
      oqlos/core/_cql_tokenizer.py:316-320  (_try_repeat_stop)
  [a7ee155dcd39e476]   EXAC  _health_map  L=4 N=2 saved=4 sim=1.00
      oqlos/hardware/client/autorepair.py:16-19  (_health_map)
      oqlos/hardware/diagnosis.py:69-72  (_health_map)
  [b7e062311606029c]   EXAC  to_json  L=4 N=2 saved=4 sim=1.00
      oqlos/hardware/transport/mqtt_oql_bridge.py:109-112  (to_json)
      oqlos/hardware/transport/mqtt_oql_bridge.py:141-144  (to_json)
  [8fd712f8bc1fd43b]   STRU  _mig_calc  L=4 N=2 saved=4 sim=1.00
      scripts/oql_v2_to_v4_migrate_db.py:343-346  (_mig_calc)
      scripts/oql_v2_to_v4_migrate_db.py:349-352  (_mig_val)
  [F0010]   FUZZ  __init__  L=4 N=2 saved=4 sim=0.91
      oqlos/hardware/plugins/modbus_adc.py:119-122  (__init__)
      oqlos/hardware/plugins/modbus.py:38-42  (__init__)
  [F0011]   FUZZ  __init__  L=4 N=2 saved=4 sim=0.86
      oqlos/hardware/plugins/piadc.py:103-106  (__init__)
      oqlos/hardware/plugins/lung.py:36-40  (__init__)
  [e8b4eed866709149]   STRU  _lower_min  L=3 N=2 saved=3 sim=1.00
      oqlos/core/_oql_adapter.py:200-202  (_lower_min)
      oqlos/core/_oql_adapter.py:205-207  (_lower_max)
  [42b356420cb5d768]   STRU  _resolve_compare  L=3 N=2 saved=3 sim=1.00
      oqlos/core/executor.py:11-13  (_resolve_compare)
      oqlos/core/safe_eval.py:90-92  (_eval_compare)
  [48a7ed090e2f6e93]   STRU  parse_CALL  L=3 N=2 saved=3 sim=1.00
      oqlos/core/oql_parser.py:397-399  (parse_CALL)
      oqlos/core/oql_parser.py:407-409  (parse_FUNC_CALL)
  [af1f7d2eecf9deab]   STRU  check_firmware_health  L=3 N=2 saved=3 sim=1.00
      oqlos/tools/hardware_diagnose/health.py:30-32  (check_firmware_health)
      oqlos/tools/hardware_diagnose/health.py:35-37  (check_firmware_identify)
  [2d86fcaf9ce3978c]   STRU  _env_int  L=3 N=2 saved=3 sim=1.00
      oqlos/tools/hardware_diagnose/modbus_probe.py:31-33  (_env_int)
      oqlos/tools/hardware_diagnose/modbus_probe.py:61-63  (_env_float)
  [F0001]   FUZZ  _oql_quote  L=3 N=2 saved=3 sim=0.94
      oqlos/core/_interpreter_actions.py:96-98  (_oql_quote)
      oqlos/tools/xml_import/generators.py:55-58  (_quote_oql)
  [F0003]   FUZZ  _firmware  L=3 N=2 saved=3 sim=0.91
      oqlos/core/interpreter.py:99-101  (_firmware)
      oqlos/core/interpreter.py:109-111  (_firmware_url)
  [F0004]   FUZZ  _normalize_valve_value  L=3 N=2 saved=3 sim=0.91
      oqlos/core/interpreter.py:129-131  (_normalize_valve_value)
      oqlos/core/interpreter.py:133-135  (_normalize_lung_value)
  [F0006]   FUZZ  discover  L=3 N=2 saved=3 sim=0.89
      oqlos/hardware/drivers/mqtt.py:103-105  (discover)
      oqlos/hardware/protocol.py:48-50  (discover)
  [F0008]   FUZZ  _handle_stop_usb  L=3 N=2 saved=3 sim=0.89
      oqlos/hardware/plugins/lung.py:249-251  (_handle_stop_usb)
      oqlos/hardware/plugins/lung.py:290-292  (_handle_status_usb)
  [F0007]   FUZZ  connect  L=3 N=2 saved=3 sim=0.88
      oqlos/hardware/plugins/base.py:292-294  (connect)
      oqlos/hardware/plugins/base.py:297-299  (disconnect)
  [F0009]   FUZZ  get_plugin_class  L=3 N=2 saved=3 sim=0.86
      oqlos/hardware/plugins/registry.py:70-72  (get_plugin_class)
      oqlos/hardware/plugins/registry.py:120-122  (get_instance)

REFACTOR[48] (ranked by priority):
  [1] ○ extract_class      → oqlos/hardware/plugins/utils/_handle_stop_cli.py
      WHY: 2 occurrences of 21-line block across 1 files — saves 21 lines
      FILES: oqlos/hardware/plugins/motor.py
  [2] ○ extract_class      → oqlos/hardware/plugins/utils/_handle_stop_http.py
      WHY: 2 occurrences of 18-line block across 1 files — saves 18 lines
      FILES: oqlos/hardware/plugins/motor.py
  [3] ○ extract_function   → oqlos/core/utils/_exec_set_peripheral.py
      WHY: 2 occurrences of 11-line block across 2 files — saves 11 lines
      FILES: oqlos/core/_firmware_executor.py, oqlos/core/interpreter.py
  [4] ○ extract_function   → oqlos/core/utils/_try_task.py
      WHY: 3 occurrences of 5-line block across 1 files — saves 10 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [5] ○ extract_function   → oqlos/core/utils/parse_SET.py
      WHY: 3 occurrences of 5-line block across 1 files — saves 10 lines
      FILES: oqlos/core/oql_parser.py
  [6] ○ extract_function   → oqlos/dsl/utils/_merge_object_function_map.py
      WHY: 2 occurrences of 10-line block across 1 files — saves 10 lines
      FILES: oqlos/dsl/schema.py
  [7] ○ extract_function   → oqlos/core/utils/_try_set.py
      WHY: 3 occurrences of 5-line block across 1 files — saves 10 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [8] ○ extract_function   → oqlos/hardware/utils/read_channel.py
      WHY: 3 occurrences of 5-line block across 1 files — saves 10 lines
      FILES: oqlos/hardware/gateway.py
  [9] ○ extract_function   → scripts/utils/_mig_goto.py
      WHY: 3 occurrences of 5-line block across 1 files — saves 10 lines
      FILES: scripts/oql_v2_to_v4_migrate_db.py
  [10] ○ extract_function   → scripts/utils/_mig_minmax_eq.py
      WHY: 2 occurrences of 8-line block across 1 files — saves 8 lines
      FILES: scripts/oql_v2_to_v4_migrate_db.py
  [11] ○ extract_function   → oqlos/core/utils/_make_args_parser.py
      WHY: 2 occurrences of 8-line block across 1 files — saves 8 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [12] ○ extract_function   → scripts/utils/_migrate_wait_line.py
      WHY: 2 occurrences of 7-line block across 1 files — saves 7 lines
      FILES: scripts/migrate_to_v4.py
  [13] ○ extract_function   → oqlos/core/utils/_try_arrow_action.py
      WHY: 2 occurrences of 8-line block across 1 files — saves 8 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [14] ○ extract_function   → oqlos/hardware/utils/modbus_plugins_need_repair.py
      WHY: 2 occurrences of 6-line block across 2 files — saves 6 lines
      FILES: oqlos/hardware/client/autorepair.py, oqlos/hardware/diagnosis.py
  [15] ○ extract_function   → oqlos/core/utils/parse_GET.py
      WHY: 3 occurrences of 3-line block across 1 files — saves 6 lines
      FILES: oqlos/core/oql_parser.py
  [16] ○ extract_function   → oqlos/core/utils/parse_LOG.py
      WHY: 3 occurrences of 3-line block across 1 files — saves 6 lines
      FILES: oqlos/core/oql_parser.py
  [17] ○ extract_class      → oqlos/hardware/plugins/utils/_handle_stop_http.py
      WHY: 2 occurrences of 6-line block across 1 files — saves 6 lines
      FILES: oqlos/hardware/plugins/lung.py
  [18] ○ extract_class      → oqlos/core/utils/_execute_firmware_action.py
      WHY: 3 occurrences of 3-line block across 1 files — saves 6 lines
      FILES: oqlos/core/interpreter.py
  [19] ○ extract_class      → oqlos/core/utils/_firmware.py
      WHY: 3 occurrences of 3-line block across 1 files — saves 6 lines
      FILES: oqlos/core/interpreter.py
  [20] ○ extract_function   → oqlos/utils/_read_text_file.py
      WHY: 2 occurrences of 5-line block across 2 files — saves 5 lines
      FILES: oqlos/api/hardware.py, oqlos/hardware/plugins/piadc.py
  [21] ○ extract_function   → oqlos/hardware/utils/status.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/hardware/gateway.py
  [22] ○ extract_function   → oqlos/hardware/plugins/utils/_rtu_timeout.py
      WHY: 2 occurrences of 5-line block across 2 files — saves 5 lines
      FILES: oqlos/hardware/plugins/modbus.py, oqlos/hardware/plugins/modbus_adc.py
  [23] ○ extract_function   → oqlos/hardware/plugins/utils/_device_id.py
      WHY: 2 occurrences of 5-line block across 2 files — saves 5 lines
      FILES: oqlos/hardware/plugins/modbus.py, oqlos/hardware/plugins/modbus_adc.py
  [24] ○ extract_function   → oqlos/api/utils/get_execution.py
      WHY: 2 occurrences of 5-line block across 2 files — saves 5 lines
      FILES: oqlos/api/execution.py, oqlos/api/peripherals.py
  [25] ○ extract_function   → oqlos/api/utils/_default_path.py
      WHY: 2 occurrences of 5-line block across 2 files — saves 5 lines
      FILES: oqlos/api/hardware_events.py, oqlos/api/hardware_mapping_store.py
  [26] ○ extract_function   → oqlos/core/utils/_try_var.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [27] ○ extract_function   → oqlos/hardware/plugins/utils/disconnect.py
      WHY: 2 occurrences of 5-line block across 2 files — saves 5 lines
      FILES: oqlos/hardware/plugins/lung.py, oqlos/hardware/plugins/piadc.py
  [28] ○ extract_function   → oqlos/hardware/utils/_match_blob.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/hardware/scanner_probe.py
  [29] ○ extract_function   → oqlos/core/utils/parser.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [30] ○ extract_class      → oqlos/hardware/plugins/utils/_read_address.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/hardware/plugins/modbus_adc.py
  [31] ○ extract_function   → oqlos/core/utils/_try_repeat_start.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [32] ○ extract_function   → oqlos/hardware/utils/_health_map.py
      WHY: 2 occurrences of 4-line block across 2 files — saves 4 lines
      FILES: oqlos/hardware/client/autorepair.py, oqlos/hardware/diagnosis.py
  [33] ○ extract_function   → oqlos/hardware/transport/utils/to_json.py
      WHY: 2 occurrences of 4-line block across 1 files — saves 4 lines
      FILES: oqlos/hardware/transport/mqtt_oql_bridge.py
  [34] ○ extract_function   → scripts/utils/_mig_calc.py
      WHY: 2 occurrences of 4-line block across 1 files — saves 4 lines
      FILES: scripts/oql_v2_to_v4_migrate_db.py
  [35] ○ extract_function   → oqlos/hardware/plugins/utils/__init__.py
      WHY: 2 occurrences of 4-line block across 2 files — saves 4 lines
      FILES: oqlos/hardware/plugins/modbus.py, oqlos/hardware/plugins/modbus_adc.py
  [36] ○ extract_function   → oqlos/hardware/plugins/utils/__init__.py
      WHY: 2 occurrences of 4-line block across 2 files — saves 4 lines
      FILES: oqlos/hardware/plugins/lung.py, oqlos/hardware/plugins/piadc.py
  [37] ○ extract_function   → oqlos/core/utils/_lower_min.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/core/_oql_adapter.py
  [38] ○ extract_function   → oqlos/core/utils/_resolve_compare.py
      WHY: 2 occurrences of 3-line block across 2 files — saves 3 lines
      FILES: oqlos/core/executor.py, oqlos/core/safe_eval.py
  [39] ○ extract_function   → oqlos/core/utils/parse_CALL.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/core/oql_parser.py
  [40] ○ extract_function   → oqlos/tools/hardware_diagnose/utils/check_firmware_health.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/tools/hardware_diagnose/health.py
  [41] ○ extract_function   → oqlos/tools/hardware_diagnose/utils/_env_int.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/tools/hardware_diagnose/modbus_probe.py
  [42] ○ extract_function   → oqlos/utils/_oql_quote.py
      WHY: 2 occurrences of 3-line block across 2 files — saves 3 lines
      FILES: oqlos/core/_interpreter_actions.py, oqlos/tools/xml_import/generators.py
  [43] ○ extract_class      → oqlos/core/utils/_firmware.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/core/interpreter.py
  [44] ○ extract_class      → oqlos/core/utils/_normalize_valve_value.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/core/interpreter.py
  [45] ○ extract_function   → oqlos/hardware/utils/discover.py
      WHY: 2 occurrences of 3-line block across 2 files — saves 3 lines
      FILES: oqlos/hardware/drivers/mqtt.py, oqlos/hardware/protocol.py
  [46] ○ extract_class      → oqlos/hardware/plugins/utils/_handle_stop_usb.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/hardware/plugins/lung.py
  [47] ○ extract_class      → oqlos/hardware/plugins/utils/connect.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/hardware/plugins/base.py
  [48] ○ extract_class      → oqlos/hardware/plugins/utils/get_plugin_class.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/hardware/plugins/registry.py

QUICK_WINS[19] (low risk, high savings — do first):
  [1] extract_class      saved=21L  → oqlos/hardware/plugins/utils/_handle_stop_cli.py
      FILES: motor.py
  [2] extract_class      saved=18L  → oqlos/hardware/plugins/utils/_handle_stop_http.py
      FILES: motor.py
  [3] extract_function   saved=11L  → oqlos/core/utils/_exec_set_peripheral.py
      FILES: _firmware_executor.py, interpreter.py
  [4] extract_function   saved=10L  → oqlos/core/utils/_try_task.py
      FILES: _cql_tokenizer.py
  [5] extract_function   saved=10L  → oqlos/core/utils/parse_SET.py
      FILES: oql_parser.py
  [6] extract_function   saved=10L  → oqlos/dsl/utils/_merge_object_function_map.py
      FILES: schema.py
  [7] extract_function   saved=10L  → oqlos/core/utils/_try_set.py
      FILES: _cql_tokenizer.py
  [8] extract_function   saved=10L  → oqlos/hardware/utils/read_channel.py
      FILES: gateway.py
  [9] extract_function   saved=10L  → scripts/utils/_mig_goto.py
      FILES: oql_v2_to_v4_migrate_db.py
  [10] extract_function   saved=8L  → scripts/utils/_mig_minmax_eq.py
      FILES: oql_v2_to_v4_migrate_db.py

EFFORT_ESTIMATE (total ≈ 9.8h):
  medium _handle_stop_cli                    saved=21L  ~42min
  medium _handle_stop_http                   saved=18L  ~36min
  easy   _exec_set_peripheral                saved=11L  ~22min
  easy   _try_task                           saved=10L  ~20min
  easy   parse_SET                           saved=10L  ~20min
  easy   _merge_object_function_map          saved=10L  ~20min
  easy   _try_set                            saved=10L  ~20min
  easy   read_channel                        saved=10L  ~20min
  easy   _mig_goto                           saved=10L  ~20min
  easy   _mig_minmax_eq                      saved=8L  ~16min
  ... +38 more (~350min)

METRICS-TARGET:
  dup_groups:  48 → 0
  saved_lines: 293 lines recoverable
```

### Evolution / Churn (`project/evolution.toon.yaml`)

```toon markpact:analysis path=project/evolution.toon.yaml
# code2llm/evolution | 2013 func | 177f | 2026-06-30
# generated in 0.01s

NEXT[10] (ranked by impact):
  [1] !! SPLIT           oqlos/api/hardware.py
      WHY: 2266L, 0 classes, max CC=14
      EFFORT: ~4h  IMPACT: 31724

  [2] !! SPLIT           frontend/src/i18n/dictionaries.js
      WHY: 1981L, 0 classes, max CC=5
      EFFORT: ~4h  IMPACT: 9905

  [3] !! SPLIT-FUNC      executeConfigureStep  CC=48  fan=15
      WHY: CC=48 exceeds 15
      EFFORT: ~1h  IMPACT: 720

  [4] !! SPLIT-FUNC      RAIL_HOVER_OPEN_MS  CC=33  fan=21
      WHY: CC=33 exceeds 15
      EFFORT: ~1h  IMPACT: 693

  [5] !! SPLIT-FUNC      RAIL_HOVER_CLOSE_MS  CC=33  fan=21
      WHY: CC=33 exceeds 15
      EFFORT: ~1h  IMPACT: 693

  [6] !! SPLIT-FUNC      useSelectionCollapsePanel  CC=33  fan=21
      WHY: CC=33 exceeds 15
      EFFORT: ~1h  IMPACT: 693

  [7] !  SPLIT-FUNC      runCurrentStep  CC=20  fan=18
      WHY: CC=20 exceeds 15
      EFFORT: ~1h  IMPACT: 360

  [8] !  SPLIT-FUNC      API_BASE  CC=17  fan=13
      WHY: CC=17 exceeds 15
      EFFORT: ~1h  IMPACT: 221

  [9] !  SPLIT-FUNC      request  CC=17  fan=13
      WHY: CC=17 exceeds 15
      EFFORT: ~1h  IMPACT: 221

  [10] !  SPLIT-FUNC      editObjectActionArg  CC=24  fan=9
      WHY: CC=24 exceeds 15
      EFFORT: ~1h  IMPACT: 216


RISKS[3]:
  ⚠ Splitting oqlos/api/hardware.py may break 93 import paths
  ⚠ Splitting frontend/src/i18n/dictionaries.js may break 4 import paths
  ⚠ Splitting docs/README.md may break 0 import paths

METRICS-TARGET:
  CC̄:          4.0 → ≤2.8
  max-CC:      48 → ≤20
  god-modules: 22 → 0
  high-CC(≥15): 23 → ≤11
  hub-types:   0 → ≤0

PATTERNS (language parser shared logic):
  _extract_declarations() in base.py — unified extraction for:
    - TypeScript: interfaces, types, classes, functions, arrow funcs
    - PHP: namespaces, traits, classes, functions, includes
    - Ruby: modules, classes, methods, requires
    - C++: classes, structs, functions, #includes
    - C#: classes, interfaces, methods, usings
    - Java: classes, interfaces, methods, imports
    - Go: packages, functions, structs
    - Rust: modules, functions, traits, use statements

  Shared regex patterns per language:
    - import: language-specific import/require/using patterns
    - class: class/struct/trait declarations with inheritance
    - function: function/method signatures with visibility
    - brace_tracking: for C-family languages ({ })
    - end_keyword_tracking: for Ruby (module/class/def...end)

  Benefits:
    - Consistent extraction logic across all languages
    - Reduced code duplication (~70% reduction in parser LOC)
    - Easier maintenance: fix once, apply everywhere
    - Standardized FunctionInfo/ClassInfo models

HISTORY:
  prev CC̄=4.0 → now CC̄=4.0
```

### Validation (`project/validation.toon.yaml`)

```toon markpact:analysis path=project/validation.toon.yaml
# vallm batch | 265f | 0✓ 159⚠ 0✗ | 2026-05-06

SUMMARY:
  scanned: 265  passed: 0 (0.0%)  warnings: 159  errors: 0  unsupported: 0

WARNINGS[159]{path,score}:
  scripts/oql_v2_to_v4_migrate_db.py,0.64
    issues[5]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
      complexity.lizard_cc,warning,_rewrite_legacy_if: CC=20 exceeds limit 15,167
      complexity.lizard_cc,warning,migrate_v2_to_v4: CC=55 exceeds limit 15,243
      complexity.lizard_length,warning,migrate_v2_to_v4: 193 lines exceeds limit 100,243
      complexity.lizard_cc,warning,main: CC=24 exceeds limit 15,517
  oqlos/tools/hardware_diagnose/doctor.py,0.68
    issues[4]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
      complexity.lizard_cc,warning,_analyze_firmware_access: CC=25 exceeds limit 15,329
      complexity.lizard_length,warning,_analyze_firmware_access: 113 lines exceeds limit 100,329
      complexity.lizard_cc,warning,format_doctor: CC=20 exceeds limit 15,716
  oqlos/api/hardware.py,0.71
    issues[3]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
      complexity.lizard_cc,warning,_detect_runtime_platform: CC=18 exceeds limit 15,156
      complexity.lizard_cc,warning,hardware_identify: CC=24 exceeds limit 15,447
  oqlos/core/_oql_adapter.py,0.71
    issues[3]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
      complexity.lizard_cc,warning,_cmd_to_actions: CC=36 exceeds limit 15,152
      complexity.lizard_length,warning,_cmd_to_actions: 178 lines exceeds limit 100,152
  oqlos/core/oql_parser.py,0.71
    issues[3]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
      complexity.lizard_cc,warning,parse_oql: CC=48 exceeds limit 15,443
      complexity.lizard_length,warning,parse_oql: 129 lines exceeds limit 100,443
  scripts/migrate_to_v4.py,0.71
    issues[3]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
      complexity.lizard_cc,warning,migrate_content: CC=19 exceeds limit 15,62
      complexity.lizard_cc,warning,main: CC=21 exceeds limit 15,185
  scripts/oql_v2_validator.py,0.71
    issues[3]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
      complexity.lizard_cc,warning,_validate_v2_structure: CC=16 exceeds limit 15,122
      complexity.lizard_length,warning,_validate_v2_structure: 102 lines exceeds limit 100,122
  oqlos/core/interpreter.py,0.74
    issues[2]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
      complexity.lizard_cc,warning,_evaluate_condition: CC=17 exceeds limit 15,618
  oqlos/dsl/schema.py,0.74
    issues[2]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
      complexity.lizard_length,warning,get_default_dsl_schema: 163 lines exceeds limit 100,123
  oqlos/hardware/firmware_adapter.py,0.74
    issues[2]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
      complexity.lizard_cc,warning,_raise_if_rejected: CC=19 exceeds limit 15,155
  oqlos/reporters/json_reporter.py,0.74
    issues[2]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
      complexity.lizard_cc,warning,report_json: CC=16 exceeds limit 15,48
  oqlos/tools/hardware_diagnose/__main__.py,0.74
    issues[2]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
      complexity.lizard_cc,warning,main: CC=19 exceeds limit 15,100
  oqlos/tools/hardware_diagnose/modbus_probe.py,0.74
    issues[2]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
      complexity.lizard_cc,warning,run_modbus_probe: CC=17 exceeds limit 15,162
  scripts/oql_v4_validator.py,0.74
    issues[2]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
      complexity.lizard_cc,warning,_validate_structure: CC=20 exceeds limit 15,126
  docs/oql_v2_llm_validator.schema.json,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse JSON: Download error: Language 'JSON' not available for download. Available groups: [""all""]",
  docs/oql_v4_llm_validator.schema.json,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse JSON: Download error: Language 'JSON' not available for download. Available groups: [""all""]",
  examples/hardware/doctor-workflow.sh,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse BASH: Download error: Language 'BASH' not available for download. Available groups: [""all""]",
  examples/plugin-config.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  goal.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  hw_diagnostic_20260415_133138.json,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse JSON: Download error: Language 'JSON' not available for download. Available groups: [""all""]",
  openapi.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  oqlos.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  oqlos/__init__.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/api/__init__.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/api/editor.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/api/execution.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/api/logs.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/api/main.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/api/peripherals.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/api/plugins.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/api/scenarios.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/api/state.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/api/utils/__init__.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/api/utils/execution_ctrl.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/api/version.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/config.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/core/__init__.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/core/_compare.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/core/_cql_tokenizer.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/core/_cql_tree_builder.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/core/_dsl_helpers.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/core/_firmware_executor.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/core/_func_resolver.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/core/_interpreter_actions.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/core/_line_parsers.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/core/_sensor_evaluator.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/core/_value_normalizers.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/core/base.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/core/cql_parser.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/core/executor.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/core/oql_versioning.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/core/parser.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/core/safe_eval.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/core/state.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/dsl/__init__.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/hardware/__init__.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/hardware/config_paths.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/hardware/config_schema.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/hardware/control_proxy.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/hardware/discovery.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/hardware/drivers/__init__.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/hardware/drivers/gpio.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/hardware/drivers/mqtt.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/hardware/drivers/spi.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/hardware/gateway.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/hardware/peripheral_mapping.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/hardware/plugin_gateway.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/hardware/plugins/__init__.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/hardware/plugins/_shared.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/hardware/plugins/base.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/hardware/plugins/lung.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/hardware/plugins/modbus.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/hardware/plugins/motor.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/hardware/plugins/piadc.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/hardware/plugins/registry.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/hardware/protocol.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/hardware/registry.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/ide/__init__.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/models/__init__.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/models/dsl_models.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/models/execution.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/models/peripheral.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/models/scenario.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/reporters/__init__.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/reporters/html_report.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/reporters/junit.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/shared/__init__.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/shared/_endpoint_helpers.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/shared/config_factory.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/shared/event_server.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/shared/event_store.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/shared/file_ops.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/shared/logger.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/shared/logs_query.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/shared/release_version.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/shared/version_endpoint.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/tools/__init__.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/tools/cql_cli.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/tools/cql_cli/__init__.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/tools/cql_cli/commands.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/tools/cql_cli/main.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/tools/cql_cli/preflight.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/tools/cql_cli/utils.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/tools/hardware_diagnose.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/tools/hardware_diagnose/__init__.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/tools/hardware_diagnose/benchmark.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/tools/hardware_diagnose/calibration.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/tools/hardware_diagnose/discovery.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/tools/hardware_diagnose/health.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/tools/hardware_diagnose/report.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/tools/hardware_diagnose/shell.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/tools/plugin_cli.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/tools/xml_import/__init__.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/tools/xml_import/_utils.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/tools/xml_import/generators.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/tools/xml_import/models.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/tools/xml_import/parser.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/utils/__init__.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  oqlos/utils/sample_data.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  project.sh,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse BASH: Download error: Language 'BASH' not available for download. Available groups: [""all""]",
  project/calls.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  pyproject.toml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse TOML: Download error: Language 'TOML' not available for download. Available groups: [""all""]",
  pyqual.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  scenarios/manifest.json,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse JSON: Download error: Language 'JSON' not available for download. Available groups: [""all""]",
  scripts/fix_brackets_to_v4.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  scripts/hardware-check.sh,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse BASH: Download error: Language 'BASH' not available for download. Available groups: [""all""]",
  scripts/scenarios_export.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  setup_hardware_and_run_oql.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  sumd.json,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse JSON: Download error: Language 'JSON' not available for download. Available groups: [""all""]",
  tests/firmware/test_control_proxy.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/firmware/test_dsl_parser_runtime.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/firmware/test_firmware.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/firmware/test_hardware_discovery.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/firmware/test_hardware_doctor.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/firmware/test_hardware_health.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/firmware/test_hardware_identify.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/firmware/test_lung_integration.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/firmware/test_lung_plugin_reciprocate.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/firmware/test_modbus_discovery.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/firmware/test_modbus_probe_cli.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/firmware/test_motor_plugin.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/firmware/test_normalize_scenario.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/firmware/test_parser_cycle.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/firmware/test_plugin_gateway_env.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/firmware/test_plugin_health.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/firmware/test_runtime_command_payload.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/firmware/test_safe_eval.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/firmware/test_tokenizer_extended.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/test_core.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/test_cql_cli.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/test_cql_inline_regressions.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/test_cql_scenarios.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/test_dsl_schema.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/test_oql_dry_run_regressions.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/test_oql_parser_v3.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/test_oql_scenarios.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/test_reporting.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/verify_block_if.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/verify_loops.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
```

## Intent

OqlOS — Operation Query Language runtime for hardware testing
