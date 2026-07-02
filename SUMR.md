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

*471 nodes · 500 edges · 66 modules · CC̄=3.8*

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
# generated in 0.24s
# nodes: 471 | edges: 500 | modules: 66
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
  oqlos.core._action_motor2._motor2_build_plan
    CC=12  in:1  out:22  total:23
  oqlos.tools.gen_error_docs.generate_markdown
    CC=6  in:1  out:22  total:23
  oqlos.core._action_motor2._try_exec_motor2_set
    CC=13  in:1  out:22  total:23
  oqlos.core._line_parsers._parse_if_condition
    CC=9  in:1  out:22  total:23
  oqlos.tools.hardware_diagnose.doctor_format.format_doctor
    CC=6  in:2  out:21  total:23
  oqlos.core._cql_tree_builder._parse_goal_line
    CC=12  in:1  out:20  total:21
  oqlos.tools.hardware_diagnose.doctor_modbus_analysis.analyze_modbus_config
    CC=11  in:1  out:20  total:21
  oqlos.hardware.config_paths.resolve_oqlos_config_path
    CC=6  in:8  out:13  total:21
  oqlos.core._func_resolver._collect_function_definitions
    CC=13  in:1  out:19  total:20
  frontend.src.api.wsClient.WsCqrsClient.super
    CC=1  in:19  out:1  total:20

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
  oqlos.core._compare  [2 funcs]
    resolve_compare  CC=2  out:5
    resolve_compare_chain  CC=3  out:4
  oqlos.core._cql_tree_builder  [7 funcs]
    _ensure_goal_for_step  CC=4  out:3
    _ensure_step_for_actions  CC=3  out:2
    _parse_action_line  CC=4  out:3
    _parse_goal_line  CC=12  out:20
    _parse_metadata_kv  CC=6  out:5
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
  oqlos.core._line_parsers  [10 funcs]
    _extract_set_params  CC=7  out:13
    _parse_action_line  CC=10  out:18
    _parse_if_condition  CC=9  out:22
    _parse_inline_task  CC=5  out:7
    _parse_pump_line  CC=6  out:8
    _parse_set_line  CC=10  out:15
    _parse_task_part  CC=10  out:14
    _set_lung_step  CC=4  out:3
    _set_pump_step  CC=4  out:3
    _set_valve_step  CC=4  out:4
  oqlos.core._oql_adapter  [3 funcs]
    is_flat_oql  CC=8  out:13
    oql_doc_to_cql  CC=12  out:30
    parse_flat_oql  CC=1  out:2
  oqlos.core._sensor_evaluator  [2 funcs]
    __init__  CC=3  out:2
    collect_sensor_constraints  CC=10  out:5
  oqlos.core._value_normalizers  [1 funcs]
    coerce_float  CC=5  out:9
  oqlos.core.base  [5 funcs]
    send_event  CC=4  out:7
    emit  CC=5  out:3
    output_yaml  CC=4  out:2
    __init__  CC=2  out:1
    all  CC=3  out:3
  oqlos.core.cql_parser  [9 funcs]
    _handle_goal  CC=3  out:5
    _handle_scenario  CC=2  out:3
    _handle_step  CC=2  out:4
    _try_hierarchy  CC=7  out:6
    _try_top_level  CC=2  out:1
    _collect_all_goals  CC=2  out:2
    _validate_intervals  CC=6  out:1
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
  oqlos.core.oql_parser  [1 funcs]
    parse_oql  CC=14  out:21
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
  oqlos.tools.gen_error_docs  [2 funcs]
    generate_markdown  CC=6  out:22
    main  CC=4  out:11
  oqlos.tools.hardware_diagnose.doctor  [1 funcs]
    build_doctor_report  CC=11  out:14
  oqlos.tools.hardware_diagnose.doctor_detection  [1 funcs]
    detect_hardware  CC=4  out:13
  oqlos.tools.hardware_diagnose.doctor_firmware  [3 funcs]
    firmware_adapter_status  CC=7  out:9
    firmware_is_remote  CC=2  out:3
    firmware_modbus_health_ok  CC=10  out:16
  oqlos.tools.hardware_diagnose.doctor_format  [4 funcs]
    _format_doctor_applied_repairs  CC=4  out:5
    _format_doctor_issues  CC=5  out:10
    format_doctor  CC=6  out:21
    format_modbus_status  CC=7  out:11
  oqlos.tools.hardware_diagnose.doctor_modbus_analysis  [3 funcs]
    analyze_modbus_config  CC=11  out:20
    expected_modbus_adc_params  CC=6  out:8
    expected_modbus_params  CC=5  out:6
  oqlos.tools.hardware_diagnose.doctor_repairs  [3 funcs]
    apply_safe_fixes  CC=9  out:14
    update_modbus_adc_config  CC=4  out:18
    update_modbus_config  CC=2  out:17
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
# generated in 0.24s
# nodes: 471 | edges: 500 | modules: 66
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
  oqlos.core._action_motor2._motor2_build_plan
    CC=12  in:1  out:22  total:23
  oqlos.tools.gen_error_docs.generate_markdown
    CC=6  in:1  out:22  total:23
  oqlos.core._action_motor2._try_exec_motor2_set
    CC=13  in:1  out:22  total:23
  oqlos.core._line_parsers._parse_if_condition
    CC=9  in:1  out:22  total:23
  oqlos.tools.hardware_diagnose.doctor_format.format_doctor
    CC=6  in:2  out:21  total:23
  oqlos.core._cql_tree_builder._parse_goal_line
    CC=12  in:1  out:20  total:21
  oqlos.tools.hardware_diagnose.doctor_modbus_analysis.analyze_modbus_config
    CC=11  in:1  out:20  total:21
  oqlos.hardware.config_paths.resolve_oqlos_config_path
    CC=6  in:8  out:13  total:21
  oqlos.core._func_resolver._collect_function_definitions
    CC=13  in:1  out:19  total:20
  frontend.src.api.wsClient.WsCqrsClient.super
    CC=1  in:19  out:1  total:20

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
  oqlos.core._compare  [2 funcs]
    resolve_compare  CC=2  out:5
    resolve_compare_chain  CC=3  out:4
  oqlos.core._cql_tree_builder  [7 funcs]
    _ensure_goal_for_step  CC=4  out:3
    _ensure_step_for_actions  CC=3  out:2
    _parse_action_line  CC=4  out:3
    _parse_goal_line  CC=12  out:20
    _parse_metadata_kv  CC=6  out:5
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
  oqlos.core._line_parsers  [10 funcs]
    _extract_set_params  CC=7  out:13
    _parse_action_line  CC=10  out:18
    _parse_if_condition  CC=9  out:22
    _parse_inline_task  CC=5  out:7
    _parse_pump_line  CC=6  out:8
    _parse_set_line  CC=10  out:15
    _parse_task_part  CC=10  out:14
    _set_lung_step  CC=4  out:3
    _set_pump_step  CC=4  out:3
    _set_valve_step  CC=4  out:4
  oqlos.core._oql_adapter  [3 funcs]
    is_flat_oql  CC=8  out:13
    oql_doc_to_cql  CC=12  out:30
    parse_flat_oql  CC=1  out:2
  oqlos.core._sensor_evaluator  [2 funcs]
    __init__  CC=3  out:2
    collect_sensor_constraints  CC=10  out:5
  oqlos.core._value_normalizers  [1 funcs]
    coerce_float  CC=5  out:9
  oqlos.core.base  [5 funcs]
    send_event  CC=4  out:7
    emit  CC=5  out:3
    output_yaml  CC=4  out:2
    __init__  CC=2  out:1
    all  CC=3  out:3
  oqlos.core.cql_parser  [9 funcs]
    _handle_goal  CC=3  out:5
    _handle_scenario  CC=2  out:3
    _handle_step  CC=2  out:4
    _try_hierarchy  CC=7  out:6
    _try_top_level  CC=2  out:1
    _collect_all_goals  CC=2  out:2
    _validate_intervals  CC=6  out:1
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
  oqlos.core.oql_parser  [1 funcs]
    parse_oql  CC=14  out:21
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
  oqlos.tools.gen_error_docs  [2 funcs]
    generate_markdown  CC=6  out:22
    main  CC=4  out:11
  oqlos.tools.hardware_diagnose.doctor  [1 funcs]
    build_doctor_report  CC=11  out:14
  oqlos.tools.hardware_diagnose.doctor_detection  [1 funcs]
    detect_hardware  CC=4  out:13
  oqlos.tools.hardware_diagnose.doctor_firmware  [3 funcs]
    firmware_adapter_status  CC=7  out:9
    firmware_is_remote  CC=2  out:3
    firmware_modbus_health_ok  CC=10  out:16
  oqlos.tools.hardware_diagnose.doctor_format  [4 funcs]
    _format_doctor_applied_repairs  CC=4  out:5
    _format_doctor_issues  CC=5  out:10
    format_doctor  CC=6  out:21
    format_modbus_status  CC=7  out:11
  oqlos.tools.hardware_diagnose.doctor_modbus_analysis  [3 funcs]
    analyze_modbus_config  CC=11  out:20
    expected_modbus_adc_params  CC=6  out:8
    expected_modbus_params  CC=5  out:6
  oqlos.tools.hardware_diagnose.doctor_repairs  [3 funcs]
    apply_safe_fixes  CC=9  out:14
    update_modbus_adc_config  CC=4  out:18
    update_modbus_config  CC=2  out:17
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

### Code Analysis (`project/analysis.toon.yaml`)

```toon markpact:analysis path=project/analysis.toon.yaml
# code2llm | 357f 60768L | python:203,javascript:90,md:22,yaml:13,shell:9,json:7,yml:4,typescript:3,conf:3,toml:1 | 2026-07-02
# generated in 0.17s
# CC̅=3.8 | critical:0/2404 | dups:0 | cycles:0

HEALTH[0]: ok

REFACTOR[0]: none needed

PIPELINES[1208]:
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
  [7] Src [useMapEditorSidebarAutoCollapse]: useMapEditorSidebarAutoCollapse → applyAutoCollapse
      PURITY: 100% pure
  [8] Src [root]: root
      PURITY: 100% pure
  [9] Src [font]: font
      PURITY: 100% pure
  [10] Src [viewportWidth]: viewportWidth
      PURITY: 100% pure
  [11] Src [denseFont]: denseFont
      PURITY: 100% pure
  [12] Src [minWidth]: minWidth
      PURITY: 100% pure
  [13] Src [observer]: observer
      PURITY: 100% pure
  [14] Src [useMapEditorHardwareEvents]: useMapEditorHardwareEvents
      PURITY: 100% pure
  [15] Src [wsUrl]: wsUrl
      PURITY: 100% pure
  [16] Src [closed]: closed
      PURITY: 100% pure
  [17] Src [socket]: socket
      PURITY: 100% pure
  [18] Src [useUrlConfig]: useUrlConfig → notifyParentChildReady
      PURITY: 100% pure
  [19] Src [onPop]: onPop
      PURITY: 100% pure
  [20] Src [onMessage]: onMessage
      PURITY: 100% pure
  [21] Src [envelope]: envelope
      PURITY: 100% pure
  [22] Src [patch]: patch
      PURITY: 100% pure
  [23] Src [useParentEncoderNavigation]: useParentEncoderNavigation
      PURITY: 100% pure
  [24] Src [controller]: controller
      PURITY: 100% pure
  [25] Src [onMessage]: onMessage
      PURITY: 100% pure
  [26] Src [onWheel]: onWheel
      PURITY: 100% pure
  [27] Src [raw]: raw
      PURITY: 100% pure
  [28] Src [useRailHoverPreview]: useRailHoverPreview → cancelPanelClose
      PURITY: 100% pure
  [29] Src [railOpenTimerRef]: railOpenTimerRef
      PURITY: 100% pure
  [30] Src [panelCloseTimerRef]: panelCloseTimerRef
      PURITY: 100% pure
  [31] Src [previewCollapse]: previewCollapse
      PURITY: 100% pure
  [32] Src [railEnter]: railEnter → cancelPanelClose
      PURITY: 100% pure
  [33] Src [railLeave]: railLeave → cancelRailOpen
      PURITY: 100% pure
  [34] Src [panelEnter]: panelEnter → cancelPanelClose
      PURITY: 100% pure
  [35] Src [panelLeave]: panelLeave → cancelRailOpen
      PURITY: 100% pure
  [36] Src [location]: location
      PURITY: 100% pure
  [37] Src [currentPath]: currentPath
      PURITY: 100% pure
  [38] Src [visibleNavItems]: visibleNavItems
      PURITY: 100% pure
  [39] Src [hasViewTabs]: hasViewTabs
      PURITY: 100% pure
  [40] Src [hostLabel]: hostLabel
      PURITY: 100% pure
  [41] Src [renderNavItem]: renderNavItem
      PURITY: 100% pure
  [42] Src [itemPath]: itemPath
      PURITY: 100% pure
  [43] Src [active]: active
      PURITY: 100% pure
  [44] Src [collapseEnabled]: collapseEnabled
      PURITY: 100% pure
  [45] Src [inPreview]: inPreview
      PURITY: 100% pure
  [46] Src [filtered]: filtered
      PURITY: 100% pure
  [47] Src [handleSelect]: handleSelect
      PURITY: 100% pure
  [48] Src [MapEditorParamConversionPanel]: MapEditorParamConversionPanel
      PURITY: 100% pure
  [49] Src [MapEditorIntegrationMetaPanel]: MapEditorIntegrationMetaPanel
      PURITY: 100% pure
  [50] Src [MapEditorMotorRuntimePanel]: MapEditorMotorRuntimePanel
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
  oqlos/                          CC̄=3.9    ←in:9  →out:0
  │ !! _interpreter_actions       800L  0C   49m  CC=14     ←1
  │ !! oql_parser                 773L  3C   38m  CC=14     ←2
  │ !! interpreter                690L  1C   48m  CC=11     ←0
  │ !! plugin_gateway             634L  1C   22m  CC=14     ←0
  │ !! hardware_modbus_waveshare   624L  0C   16m  CC=11     ←0
  │ !! main                       605L  0C   38m  CC=8      ←0
  │ mqtt_oql_bridge            493L  7C   33m  CC=5      ←0
  │ _oql_adapter               490L  1C   28m  CC=12     ←2
  │ _action_motor2             481L  0C   30m  CC=13     ←1
  │ firmware_adapter           480L  1C   26m  CC=12     ←0
  │ cql_parser                 467L  1C   30m  CC=8      ←2
  │ proxy                      460L  1C   29m  CC=13     ←0
  │ generators                 452L  0C   20m  CC=14     ←0
  │ main                       415L  1C   18m  CC=9      ←2
  │ _cql_tokenizer             410L  0C   23m  CC=5      ←0
  │ motor                      405L  1C   20m  CC=14     ←0
  │ hardware_modbus_wizard     399L  0C    9m  CC=10     ←0
  │ modbus_adc                 392L  1C   18m  CC=12     ←0
  │ gateway                    386L  5C   25m  CC=7      ←0
  │ executor                   383L  1C   21m  CC=14     ←0
  │ base                       370L  9C   21m  CC=5      ←3
  │ state                      370L  0C   16m  CC=13     ←0
  │ execution                  358L  0C   16m  CC=11     ←0
  │ lung                       353L  1C   20m  CC=14     ←0
  │ plugin_cli                 343L  0C   14m  CC=8      ←3
  │ registry                   332L  1C   14m  CC=6      ←0
  │ modbus                     329L  1C   16m  CC=11     ←0
  │ sidecar_control            328L  0C   18m  CC=13     ←0
  │ catalog                    313L  3C    4m  CC=3      ←1
  │ base                       311L  7C   29m  CC=7      ←18
  │ preflight                  309L  0C   11m  CC=13     ←1
  │ schema                     296L  5C    7m  CC=7      ←0
  │ _firmware_executor         266L  1C   11m  CC=11     ←0
  │ html_report                266L  0C    5m  CC=10     ←0
  │ piadc                      262L  1C   11m  CC=11     ←0
  │ _line_parsers              261L  0C   10m  CC=10     ←1
  │ scanner_probe              260L  0C   14m  CC=14     ←1
  │ hui_hold                   256L  0C   17m  CC=12     ←3
  │ doctor_modbus_analysis     252L  0C    5m  CC=13     ←2
  │ scenarios                  251L  0C   16m  CC=11     ←0
  │ diagnosis                  246L  0C   11m  CC=13     ←1
  │ doctor_firmware            226L  0C   10m  CC=11     ←3
  │ diagnosis_device_actions   221L  0C    7m  CC=11     ←1
  │ config                     220L  1C    1m  CC=1      ←5
  │ tic249_extended            215L  0C    7m  CC=10     ←0
  │ motor2_runtime             209L  2C   12m  CC=12     ←1
  │ modbus_probe               208L  0C   17m  CC=5      ←1
  │ motor_modbus_handlers      207L  0C    6m  CC=8      ←1
  │ editor                     200L  3C    9m  CC=10     ←0
  │ rtc_probe                  197L  0C    7m  CC=11     ←1
  │ _hw3_models                194L  9C    7m  CC=14     ←3
  │ commands                   192L  0C    6m  CC=8      ←2
  │ identify_enrich_adapters   190L  0C   10m  CC=13     ←1
  │ hardware_runtime           189L  0C    8m  CC=8      ←0
  │ hardware_probe_devices     188L  0C    7m  CC=14     ←1
  │ usb_diagnostics            185L  0C    5m  CC=13     ←0
  │ parser                     184L  0C    5m  CC=13     ←2
  │ __main__                   184L  0C   11m  CC=6      ←0
  │ tic249_sidecar_client      183L  0C    9m  CC=9      ←1
  │ plugins                    181L  0C   12m  CC=3      ←2
  │ parser                     175L  0C    6m  CC=9      ←0
  │ event_server               171L  2C   11m  CC=7      ←0
  │ hardware_identify          170L  0C    5m  CC=11     ←1
  │ _cql_tree_builder          167L  0C    9m  CC=12     ←2
  │ hardware_platform          165L  0C    8m  CC=9      ←0
  │ modbus_repair              164L  0C    7m  CC=13     ←1
  │ discovery                  163L  0C    4m  CC=5      ←0
  │ artificial_lung            162L  0C   10m  CC=6      ←0
  │ _hw3_mapping               157L  0C   12m  CC=10     ←0
  │ manage_ops                 153L  0C    3m  CC=5      ←3
  │ oql_mqtt                   152L  3C    6m  CC=6      ←2
  │ hardware_mapping_store     152L  1C   13m  CC=8      ←1
  │ utils                      150L  0C   10m  CC=8      ←4
  │ hui_lung_recipe            147L  0C    7m  CC=9      ←2
  │ manage_ops_diagnostic      147L  0C   10m  CC=7      ←0
  │ _sensor_evaluator          145L  1C    6m  CC=10     ←0
  │ logs_query                 145L  1C    5m  CC=11     ←1
  │ config_schema              141L  1C    4m  CC=2      ←0
  │ hardware_probe             139L  0C    9m  CC=11     ←0
  │ safe_eval                  138L  1C   10m  CC=4      ←0
  │ shell                      138L  0C    5m  CC=6      ←1
  │ json_reporter              138L  0C    5m  CC=8      ←0
  │ peripheral_mapping         136L  0C    4m  CC=2      ←0
  │ hardware_events            136L  0C   10m  CC=11     ←3
  │ _hw3_system                134L  0C   19m  CC=6      ←0
  │ autorepair                 133L  0C    8m  CC=12     ←0
  │ _hw3_peripheral            133L  0C    5m  CC=11     ←0
  │ _dsl_helpers               132L  0C   12m  CC=11     ←4
  │ modbus_identify            131L  0C    8m  CC=10     ←1
  │ doctor_detection           130L  0C    8m  CC=5      ←3
  │ file_ops                   130L  1C    7m  CC=4      ←3
  │ resolvers                  128L  0C   10m  CC=10     ←1
  │ tic249_motion_params       127L  0C    6m  CC=13     ←3
  │ _value_normalizers         126L  1C    7m  CC=10     ←0
  │ release_version            125L  0C    7m  CC=11     ←1
  │ state                      124L  1C    3m  CC=4      ←0
  │ doctor_repairs             119L  0C    3m  CC=9      ←1
  │ mqtt                       119L  1C    9m  CC=3      ←0
  │ health                     117L  0C    7m  CC=8      ←6
  │ tic249_error_messages      112L  0C    6m  CC=14     ←3
  │ doctor_format              108L  0C    6m  CC=10     ←2
  │ gen_error_docs             107L  0C    3m  CC=6      ←0
  │ _utils                     101L  0C    6m  CC=12     ←1
  │ __init__                   100L  0C    0m  CC=0.0    ←0
  │ discovery                   99L  1C    5m  CC=8      ←4
  │ _func_resolver              96L  0C    4m  CC=13     ←1
  │ doctor                      93L  0C    1m  CC=11     ←2
  │ calibration                 92L  0C    4m  CC=5      ←3
  │ spi                         92L  1C    7m  CC=4      ←0
  │ hardware_modbus_topology    92L  0C    5m  CC=12     ←0
  │ doctor_serial               90L  0C    5m  CC=6      ←1
  │ hardware_peripherals_routes    90L  0C    3m  CC=7      ←0
  │ models                      90L  5C    0m  CC=0.0    ←0
  │ identify_enrich_modbus_io    89L  0C    4m  CC=13     ←1
  │ gpio                        89L  1C    7m  CC=6      ←0
  │ logger                      89L  0C    2m  CC=12     ←0
  │ stack_snapshot              88L  0C    4m  CC=8      ←1
  │ dsl_models                  87L  8C    0m  CC=0.0    ←0
  │ diagnosis_plugin_health     86L  0C    8m  CC=8      ←3
  │ diagnosis_types             86L  3C    2m  CC=4      ←2
  │ config                      86L  1C    6m  CC=6      ←1
  │ junit                       86L  1C    3m  CC=8      ←0
  │ hui_artificial_lung         85L  0C    3m  CC=6      ←1
  │ hardware_lung               85L  0C    7m  CC=7      ←1
  │ hardware                    85L  0C    0m  CC=0.0    ←0
  │ config_factory              84L  0C    1m  CC=1      ←0
  │ hardware_modbus_routes      80L  0C    4m  CC=8      ←0
  │ identify_enrich             78L  0C    4m  CC=12     ←0
  │ event_store                 77L  1C   10m  CC=3      ←0
  │ __init__                    73L  0C    1m  CC=1      ←0
  │ sample_data                 73L  0C    1m  CC=1      ←1
  │ oql_versioning              72L  1C    4m  CC=4      ←1
  │ constants                   69L  0C    0m  CC=0.0    ←0
  │ control_proxy               68L  1C    1m  CC=1      ←0
  │ peripherals                 68L  0C    4m  CC=5      ←0
  │ motor_http_handlers         67L  0C    2m  CC=4      ←1
  │ doctor_common               66L  0C    5m  CC=5      ←3
  │ __init__                    66L  0C    2m  CC=1      ←0
  │ version_endpoint            66L  0C    2m  CC=3      ←0
  │ _shared                     66L  0C    6m  CC=2      ←3
  │ hui_actions                 65L  0C    1m  CC=2      ←1
  │ tic249_arg_contract         65L  0C    2m  CC=8      ←2
  │ adc                         64L  0C    3m  CC=10     ←2
  │ report                      63L  0C    2m  CC=12     ←3
  │ formatting                  63L  0C    3m  CC=14     ←2
  │ hardware_mapping_contract    63L  1C    3m  CC=6      ←1
  │ execution_ctrl              62L  0C    3m  CC=1      ←0
  │ hardware_hui                61L  0C    8m  CC=2      ←0
  │ hardware_registry           61L  0C    0m  CC=0.0    ←0
  │ protocol                    60L  2C    6m  CC=1      ←0
  │ hardware_v3                 60L  0C    3m  CC=2      ←0
  │ exceptions                  59L  1C    2m  CC=8      ←0
  │ hardware_diagnosis_routes    58L  0C    3m  CC=2      ←0
  │ benchmark                   55L  0C    1m  CC=6      ←2
  │ platform                    50L  0C    3m  CC=6      ←0
  │ registry                    49L  1C    3m  CC=2      ←0
  │ tic249_command_mapping      49L  0C    2m  CC=13     ←2
  │ __init__                    49L  0C    0m  CC=0.0    ←0
  │ hardware_mapping_motor2     48L  0C    5m  CC=10     ←1
  │ _endpoint_helpers           48L  0C    3m  CC=2      ←3
  │ _rtu_serial                 47L  0C    4m  CC=4      ←2
  │ hui_scenario                46L  0C    1m  CC=2      ←1
  │ logs                        45L  0C    3m  CC=1      ←0
  │ tic249_rig_direction        43L  0C    2m  CC=5      ←1
  │ __init__                    43L  0C    0m  CC=0.0    ←0
  │ config_paths                41L  0C    1m  CC=6      ←5
  │ _compare                    40L  0C    2m  CC=3      ←2
  │ repair_commit               40L  0C    2m  CC=2      ←0
  │ legacy_aliases              40L  0C    3m  CC=5      ←0
  │ tic249_units                39L  0C    2m  CC=5      ←2
  │ scenario                    35L  4C    0m  CC=0.0    ←0
  │ manage_ops_usb              33L  0C    3m  CC=1      ←0
  │ peripheral                  33L  4C    0m  CC=0.0    ←0
  │ plugin_http_handlers        32L  0C    2m  CC=3      ←2
  │ health_status               26L  0C    1m  CC=11     ←2
  │ errors                      26L  1C    3m  CC=6      ←2
  │ http_helpers                26L  0C    2m  CC=10     ←1
  │ __init__                    24L  0C    0m  CC=0.0    ←0
  │ version                     24L  0C    0m  CC=0.0    ←0
  │ fastapi_integration         23L  0C    1m  CC=1      ←0
  │ gateway_http                23L  0C    2m  CC=1      ←1
  │ hardware_actuators          23L  0C    2m  CC=1      ←0
  │ hardware_gateway            22L  0C    3m  CC=2      ←11
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
  scripts/                        CC̄=3.7    ←in:0  →out:72  !! split
  │ !! oql_v2_to_v4_migrate_db    662L  1C   45m  CC=14     ←1
  │ migrate_to_v4              341L  0C   20m  CC=11     ←0
  │ hardware-check.sh          340L  0C   11m  CC=0.0    ←0
  │ scenarios_export           296L  0C   13m  CC=8      ←0
  │ oql_v4_validator           281L  1C    8m  CC=8      ←1
  │ oql_v2_validator           224L  1C    6m  CC=9      ←0
  │ oql_validator_common       129L  0C    6m  CC=11     ←2
  │ oql-stack.sh               104L  0C    5m  CC=0.0    ←0
  │ fix_brackets_to_v4          95L  0C    2m  CC=14     ←0
  │ test-hardware.sh            83L  0C    0m  CC=0.0    ←0
  │ verify-rpi-checksum.sh      75L  0C    1m  CC=0.0    ←0
  │ provision-rpi-sudo.sh       67L  0C    0m  CC=0.0    ←0
  │ gen-checksums.sh            27L  0C    0m  CC=0.0    ←0
  │
  frontend/                       CC̄=3.4    ←in:0  →out:0
  │ !! dictionaries.js           2135L  0C    4m  CC=5      ←0
  │ !! mapEditorDefaultMap.js    1953L  0C    3m  CC=1      ←0
  │ !! MapEditor.jsx             1114L  0C   67m  CC=12     ←8
  │ !! hardware-status-presets-translations.js   795L  0C    0m  CC=0.0    ←0
  │ !! HardwareDemo.jsx           556L  0C   37m  CC=10     ←0
  │ HardwareRestart.jsx        470L  0C   44m  CC=10     ←1
  │ SidebarList.jsx            341L  0C    4m  CC=6      ←0
  │ hardware-status-panel-translations.js   327L  0C    0m  CC=0.0    ←0
  │ ScenarioFiles.jsx          315L  0C   18m  CC=9      ←28
  │ hardwareApi.js             257L  0C   23m  CC=14     ←0
  │ HardwareStatus.jsx         239L  0C   15m  CC=2      ←1
  │ url-embed-config.js        193L  0C   43m  CC=12     ←0
  │ hardware-demo-extra-translations.js   183L  0C    0m  CC=0.0    ←0
  │ useSelectionCollapsePanel.js   159L  0C   13m  CC=11     ←0
  │ MotorServices.jsx          154L  0C    8m  CC=9      ←0
  │ encoder-navigation.js      142L  0C   17m  CC=11     ←7
  │ wsClient.js                138L  1C   30m  CC=13     ←11
  │ rbac.policy.js             124L  0C   20m  CC=6      ←0
  │ hardware-wizard-steps.js   101L  0C   17m  CC=11     ←0
  │ hardware-diagnostic-failure.js    97L  0C   19m  CC=14     ←0
  │ url-embed-config.test.js    92L  0C    6m  CC=2      ←0
  │ SharedNav.jsx               87L  0C    8m  CC=5      ←0
  │ hardware-api-log.js         87L  0C    7m  CC=11     ←0
  │ hardware-api-errors.js      87L  0C   12m  CC=13     ←0
  │ useUrlConfig.js             85L  0C    6m  CC=8      ←0
  │ hardware-demo-identify.js    85L  0C   12m  CC=10     ←0
  │ oqlGoals.js                 85L  0C   19m  CC=10     ←0
  │ useRailHoverPreview.js      84L  0C   13m  CC=9      ←0
  │ mapEditorModel.js           83L  0C    9m  CC=14     ←0
  │ mapEditorFuncHardwareSummary.js    83L  0C   18m  CC=12     ←0
  │ hardware-status-log-translations.js    81L  0C    0m  CC=0.0    ←0
  │ mapEditorIntegrationMeta.js    80L  0C   11m  CC=11     ←0
  │ scenarioFilesApi.js         79L  0C   10m  CC=10     ←0
  │ hardware-api-errors.test.js    79L  0C    2m  CC=2      ←0
  │ MapEditorObjectActionPanel.jsx    72L  0C    7m  CC=13     ←0
  │ scenarioFilesUrl.test.js    71L  0C    1m  CC=1      ←0
  │ hardware-restart-configure.js    68L  0C   10m  CC=14     ←1
  │ scenarioFilesUrl.js         67L  0C   16m  CC=12     ←0
  │ I18nProvider.jsx            65L  0C   10m  CC=13     ←26
  │ useMapEditorHardwareEvents.js    61L  0C    6m  CC=14     ←0
  │ collapse-toggle-bridge.js    60L  0C    9m  CC=4      ←0
  │ mapEditorMapShape.js        58L  0C    8m  CC=11     ←0
  │ hardware-diagnostic-failure.test.js    58L  0C    0m  CC=0.0    ←0
  │ oqlGoals.test.js            55L  0C    1m  CC=1      ←0
  │ mapEditorFuncHardwareSummary.test.js    54L  0C    1m  CC=1      ←0
  │ hardwareEventStream.js      52L  0C   22m  CC=10     ←1
  │ hardware-restart-wizard-steps.js    46L  0C    9m  CC=9      ←0
  │ hardware-api-retry.test.js    45L  0C    3m  CC=2      ←0
  │ mapEditorObjectActionEdits.js    44L  0C    8m  CC=13     ←0
  │ hardwareStatusModel.test.js    43L  0C    2m  CC=1      ←0
  │ mapEditorIntegrationMeta.test.js    43L  0C    1m  CC=1      ←0
  │ designRem.js                43L  0C    2m  CC=1      ←0
  │ AppConfigProvider.jsx       42L  0C    5m  CC=2      ←0
  │ MapEditorMotorRuntimePanel.jsx    41L  0C    2m  CC=3      ←0
  │ mapEditorConstants.js       41L  0C    7m  CC=1      ←0
  │ hardware-restart-wizard-helpers.js    41L  0C    7m  CC=14     ←0
  │ hardware-wizard-plan.js     41L  0C    8m  CC=7      ←0
  │ useParentEncoderNavigation.js    39L  0C    7m  CC=9      ←0
  │ MapEditorParamConversionPanel.jsx    39L  0C    2m  CC=4      ←0
  │ parentUrlBridge.js          39L  0C    3m  CC=10     ←0
  │ paths.ts                    39L  0C    4m  CC=2      ←0
  │ hardware-api-retry.js       38L  0C    8m  CC=14     ←1
  │ hui-shell-key.js            38L  0C    5m  CC=5      ←0
  │ hardwareStatusModel.js      38L  0C    7m  CC=11     ←0
  │ hardwareEventStream.test.js    36L  0C    1m  CC=1      ←0
  │ vite.config.ts              36L  0C    0m  CC=0.0    ←0
  │ hardware-tic249-status.js    35L  0C    6m  CC=12     ←0
  │ hardware-activity-log.js    34L  0C    4m  CC=2      ←0
  │ mapEditorObjectActionEdits.test.js    33L  0C    1m  CC=1      ←0
  │ MapEditorIntegrationMetaPanel.jsx    32L  0C    1m  CC=3      ←0
  │ mapEditorModel.test.js      32L  0C    1m  CC=1      ←0
  │ hardware-restart-wizard-steps.test.js    31L  0C    1m  CC=1      ←0
  │ index.ts                    31L  0C    2m  CC=1      ←0
  │ main.jsx                    30L  0C    1m  CC=1      ←0
  │ hardware-restart-configure.test.js    30L  0C    2m  CC=3      ←0
  │ useMapEditorSidebarAutoCollapse.js    29L  0C    8m  CC=9      ←0
  │ hardware-wizard-steps.test.js    29L  0C    1m  CC=1      ←0
  │ hardware-demo-identify.test.js    27L  0C    2m  CC=2      ←0
  │ useWsStatus.js              26L  0C    4m  CC=3      ←0
  │ app-config-document.js      26L  0C    4m  CC=6      ←0
  │ App.jsx                     26L  0C    0m  CC=0.0    ←0
  │ HardwareActivityLog.jsx     24L  0C    0m  CC=0.0    ←0
  │ hardware-restart-step-runner.js    23L  0C    1m  CC=6      ←0
  │ package.json                22L  0C    0m  CC=0.0    ←0
  │ encoder-navigation.test.js    20L  0C    1m  CC=1      ←0
  │ hardware-restart-probe-select.js    19L  0C    5m  CC=10     ←0
  │ hardware-restart-step-runner.test.js    17L  0C    1m  CC=1      ←0
  │ hardware-wizard-plan.test.js    16L  0C    1m  CC=1      ←0
  │ hardware-restart-step-errors.js    15L  0C    3m  CC=4      ←0
  │ mapEditorTic249.test.js     13L  0C    0m  CC=0.0    ←0
  │ hardware-restart-docs.js    11L  0C    2m  CC=2      ←0
  │ mapEditorTic249.js           7L  0C    2m  CC=3      ←0
  │ hardware-restart-step-outcome.js     6L  0C    1m  CC=3      ←0
  │ hardware-time.js             4L  0C    1m  CC=1      ←0
  │
  examples/                       CC̄=0.0    ←in:0  →out:0
  │ plugin-config.yaml         128L  0C    0m  CC=0.0    ←0
  │ curl-quickstart.sh          74L  0C    0m  CC=0.0    ←0
  │ doctor-workflow.sh          52L  0C    1m  CC=0.0    ←18
  │
  docs/                           CC̄=0.0    ←in:0  →out:0
  │ !! README.md                 2362L  0C    0m  CC=0.0    ←0
  │ !! cql-examples.md            588L  0C    0m  CC=0.0    ←0
  │ HARDWARE_DIAGNOSTICS.md    432L  0C    0m  CC=0.0    ←0
  │ HARDWARE_CONTROL_OQL_MQTT.md   319L  0C    0m  CC=0.0    ←0
  │ oql-spec.md                258L  0C    0m  CC=0.0    ←0
  │ OQL_V4_MIGRATION_MANUAL.md   216L  0C    0m  CC=0.0    ←0
  │ refactor-plan.md           116L  0C    0m  CC=0.0    ←0
  │ DEDUP-connect-scenario.md   108L  0C    0m  CC=0.0    ←0
  │ oql_v4_llm_validator.schema.json    93L  0C    0m  CC=0.0    ←0
  │ oql_v2_llm_validator.schema.json    89L  0C    0m  CC=0.0    ←0
  │ cql-spec.md                 77L  0C    0m  CC=0.0    ←0
  │ ERROR_CODES.md              67L  0C    0m  CC=0.0    ←0
  │ boardnet-navigation.md      61L  0C    0m  CC=0.0    ←0
  │
  redeploy/                       CC̄=0.0    ←in:0  →out:0
  │ !! migration.md              1305L  0C    0m  CC=0.0    ←0
  │ !! migration.md               640L  0C    0m  CC=0.0    ←0
  │ RUNBOOK.md                 103L  0C    0m  CC=0.0    ←0
  │ CURRENT_STATE.md            96L  0C    0m  CC=0.0    ←0
  │ RUNBOOK.md                  87L  0C    0m  CC=0.0    ←0
  │ oqlos-hw.yaml               66L  0C    0m  CC=0.0    ←0
  │ oqlos-hw.yaml               66L  0C    0m  CC=0.0    ←0
  │ mosquitto.conf              19L  0C    0m  CC=0.0    ←0
  │ mosquitto.conf              19L  0C    0m  CC=0.0    ←0
  │
  docker/                         CC̄=0.0    ←in:0  →out:0
  │ docker-compose.dev.yml      43L  0C    0m  CC=0.0    ←0
  │ Dockerfile                  22L  0C    0m  CC=0.0    ←0
  │ docker-compose.prod.yml     19L  0C    0m  CC=0.0    ←0
  │ mosquitto.conf               4L  0C    0m  CC=0.0    ←0
  │
  testql-scenarios/               CC̄=0.0    ←in:0  →out:0
  │ generated-api-smoke.testql.toon.yaml    46L  0C    0m  CC=0.0    ←0
  │ generated-from-scenarios.testql.toon.yaml    18L  0C    0m  CC=0.0    ←0
  │ generated-api-integration.testql.toon.yaml    18L  0C    0m  CC=0.0    ←0
  │ generated-from-pytests.testql.toon.yaml    15L  0C    0m  CC=0.0    ←0
  │ cross-project-integration.testql.toon.yaml    11L  0C    0m  CC=0.0    ←0
  │
  scenarios/                      CC̄=0.0    ←in:0  →out:0
  │ OQL-CHEATSHEET.md          211L  0C    0m  CC=0.0    ←0
  │ README.md                  137L  0C    0m  CC=0.0    ←0
  │ manifest.json              134L  0C    0m  CC=0.0    ←0
  │ SCENARIO_DEDUP_REFACTOR_REPORT.md    71L  0C    0m  CC=0.0    ←0
  │ legacy_aliases.json         10L  0C    0m  CC=0.0    ←0
  │
  ── zero ──
     oqlos/core/__init__.py                    0L

COUPLING:
                                             oqlos.tools           examples.hardware                frontend.src              oqlos.hardware                     scripts                   oqlos.api                  oqlos.core  setup_hardware_and_run_oql                oqlos.shared                       oqlos                   oqlos.dsl             oqlos.reporters                 oqlos.utils                oqlos.errors
                 oqlos.tools                          ──                         128                          89                           7                          ←3                                                      10                                                                                                                                                                                                      hub
           examples.hardware                        ←128                          ──                                                                                 ←64                                                      ←2                         ←27                          ←7                                                                                                                                              hub
                frontend.src                         ←89                                                      ──                         ←73                          ←3                         ←23                         ←18                                                      ←4                                                      ←1                          ←2                                                      ←1  hub
              oqlos.hardware                           3                                                      73                          ──                          ←1                           2                           6                                                                                   3                                                                                                                  hub
                     scripts                           3                          64                           3                           1                          ──                                                       1                                                                                                                                                                                                      !! fan-out
                   oqlos.api                                                                                  23                          17                                                      ──                           6                                                      10                           2                                                                                   2                              !! fan-out
                  oqlos.core                         ←10                           2                          18                          ←6                          ←1                          ←6                          ──                                                      ←1                           3                          ←1                                                                                      hub
  setup_hardware_and_run_oql                                                      27                                                                                                                                                                      ──                                                                                                                                                                          !! fan-out
                oqlos.shared                                                       7                           4                                                                                 ←10                           1                                                      ──                           1                                                                                                                  hub
                       oqlos                                                                                                              ←3                                                      ←2                          ←3                                                      ←1                          ──                                                                                                                  hub
                   oqlos.dsl                                                                                   1                                                                                                               1                                                                                                              ──                                                                                    
             oqlos.reporters                                                                                   2                                                                                                                                                                                                                                                          ──                                                        
                 oqlos.utils                                                                                                                                                                      ←2                                                                                                                                                                                                  ──                            
                oqlos.errors                                                                                   1                                                                                                                                                                                                                                                                                                                  ──
  CYCLES: none
  HUB: oqlos.tools/ (fan-in=6)
  HUB: oqlos/ (fan-in=9)
  HUB: examples.hardware/ (fan-in=228)
  HUB: oqlos.shared/ (fan-in=10)
  HUB: oqlos.core/ (fan-in=25)
  HUB: oqlos.hardware/ (fan-in=25)
  HUB: frontend.src/ (fan-in=214)
  SMELL: scripts/ fan-out=72 → split needed
  SMELL: oqlos.tools/ fan-out=234 → split needed
  SMELL: oqlos.api/ fan-out=60 → split needed
  SMELL: oqlos.shared/ fan-out=13 → split needed
  SMELL: setup_hardware_and_run_oql/ fan-out=27 → split needed
  SMELL: oqlos.core/ fan-out=23 → split needed
  SMELL: oqlos.hardware/ fan-out=87 → split needed

EXTERNAL:
  validation: run `vallm batch .` → validation.toon
  duplication: run `redup scan .` → duplication.toon
```

### Duplication (`project/duplication.toon.yaml`)

```toon markpact:analysis path=project/duplication.toon.yaml
# redup/duplication | 35 groups | 209f 33840L | 2026-07-02

SUMMARY:
  files_scanned: 209
  total_lines:   33840
  dup_groups:    35
  dup_fragments: 74
  saved_lines:   170
  scan_ms:       129560

HOTSPOTS[7] (files with most duplication):
  oqlos/core/_cql_tokenizer.py  dup=77L  groups=6  frags=13  (0.2%)
  oqlos/core/interpreter.py  dup=41L  groups=5  frags=11  (0.1%)
  oqlos/core/oql_parser.py  dup=31L  groups=3  frags=6  (0.1%)
  oqlos/hardware/plugins/lung.py  dup=20L  groups=4  frags=6  (0.1%)
  oqlos/hardware/plugins/motor.py  dup=17L  groups=1  frags=2  (0.1%)
  scripts/oql_v2_to_v4_migrate_db.py  dup=15L  groups=1  frags=3  (0.0%)
  oqlos/core/_firmware_executor.py  dup=14L  groups=1  frags=1  (0.0%)

DUPLICATES[35] (ranked by impact):
  [F0027]   FUZZ  _exec_set_peripheral  L=11 N=2 saved=11 sim=0.94
      oqlos/core/interpreter.py:333-343  (_exec_set_peripheral)
      oqlos/core/_firmware_executor.py:253-266  (exec_set_peripheral)
  [F0018]   FUZZ  _try_set  L=5 N=3 saved=10 sim=0.88
      oqlos/core/_cql_tokenizer.py:206-210  (_try_set)
      oqlos/core/_cql_tokenizer.py:305-309  (_try_val)
      oqlos/core/_cql_tokenizer.py:370-374  (_try_goto)
  [F0022]   FUZZ  _mig_goto  L=5 N=3 saved=10 sim=0.85
      scripts/oql_v2_to_v4_migrate_db.py:377-381  (_mig_goto)
      scripts/oql_v2_to_v4_migrate_db.py:391-395  (_mig_else_info)
      scripts/oql_v2_to_v4_migrate_db.py:398-402  (_mig_set_name)
  [F0024]   FUZZ  _make_args_parser  L=8 N=2 saved=8 sim=0.91
      oqlos/core/_cql_tokenizer.py:100-107  (_make_args_parser)
      oqlos/core/_cql_tokenizer.py:119-126  (_make_method_parser)
  [F0026]   FUZZ  _handle_status_modbus  L=8 N=2 saved=8 sim=0.89
      oqlos/hardware/plugins/motor.py:327-334  (_handle_status_modbus)
      oqlos/hardware/plugins/motor.py:286-294  (_handle_stop_modbus)
  [F0025]   FUZZ  _make_stripped_field_parser  L=8 N=2 saved=8 sim=0.89
      oqlos/core/_cql_tokenizer.py:129-136  (_make_stripped_field_parser)
      oqlos/core/_cql_tokenizer.py:139-146  (_make_two_group_parser)
  [528e8d469f4eb20b]   EXAC  modbus_plugins_need_repair  L=6 N=2 saved=6 sim=1.00
      oqlos/hardware/client/autorepair.py:30-35  (modbus_plugins_need_repair)
      oqlos/hardware/diagnosis_plugin_health.py:62-67  (modbus_plugins_need_repair)
  [F0007]   FUZZ  _execute_firmware_action  L=3 N=3 saved=6 sim=0.93
      oqlos/core/interpreter.py:349-351  (_execute_firmware_action)
      oqlos/core/interpreter.py:353-355  (_execute_plugin_action)
      oqlos/core/interpreter.py:357-359  (_execute_legacy_firmware_action)
  [F0023]   FUZZ  _make_single_field_parser  L=6 N=2 saved=6 sim=0.93
      oqlos/core/oql_parser.py:261-266  (_make_single_field_parser)
      oqlos/core/oql_parser.py:407-412  (_make_call_parser)
  [F0004]   FUZZ  _firmware  L=3 N=3 saved=6 sim=0.89
      oqlos/core/interpreter.py:94-96  (_firmware)
      oqlos/core/interpreter.py:104-106  (_firmware_url)
      oqlos/core/interpreter.py:345-347  (_get_firmware)
  [e318d728814958bb]   STRU  _default_path  L=5 N=2 saved=5 sim=1.00
      oqlos/api/hardware_events.py:19-23  (_default_path)
      oqlos/api/hardware_mapping_store.py:23-27  (_default_path)
  [86961d38fa77331f]   STRU  _merge_object_function_map  L=5 N=2 saved=5 sim=1.00
      oqlos/dsl/schema.py:109-113  (_merge_object_function_map)
      oqlos/dsl/schema.py:116-120  (_merge_param_unit_map)
  [F0017]   FUZZ  parser  L=5 N=2 saved=5 sim=0.92
      oqlos/core/_cql_tokenizer.py:131-135  (parser)
      oqlos/core/_cql_tokenizer.py:141-145  (parser)
  [F0020]   FUZZ  parser  L=5 N=2 saved=5 sim=0.91
      oqlos/core/oql_parser.py:363-367  (parser)
      oqlos/core/oql_parser.py:361-368  (_make_minmax_parser)
  [F0016]   FUZZ  parser  L=5 N=2 saved=5 sim=0.91
      oqlos/core/_cql_tokenizer.py:102-106  (parser)
      oqlos/core/_cql_tokenizer.py:121-125  (parser)
  [F0021]   FUZZ  get_json  L=5 N=2 saved=5 sim=0.87
      oqlos/hardware/gateway_http.py:12-16  (get_json)
      oqlos/hardware/gateway_http.py:19-23  (post_json)
  [F0019]   FUZZ  _try_repeat_start  L=5 N=2 saved=5 sim=0.86
      oqlos/core/_cql_tokenizer.py:333-337  (_try_repeat_start)
      oqlos/core/_cql_tokenizer.py:339-343  (_try_repeat_stop)
  [F0014]   FUZZ  __init__  L=4 N=2 saved=4 sim=0.91
      oqlos/hardware/plugins/modbus_adc.py:119-122  (__init__)
      oqlos/hardware/plugins/modbus.py:38-42  (__init__)
  [F0015]   FUZZ  __init__  L=4 N=2 saved=4 sim=0.86
      oqlos/hardware/plugins/piadc.py:98-101  (__init__)
      oqlos/hardware/plugins/lung.py:37-41  (__init__)
  [49732c62e7acd1c6]   STRU  get_execution  L=3 N=2 saved=3 sim=1.00
      oqlos/api/execution.py:200-202  (get_execution)
      oqlos/api/peripherals.py:18-20  (get_peripheral)
  [42b356420cb5d768]   STRU  _resolve_compare  L=3 N=2 saved=3 sim=1.00
      oqlos/core/executor.py:11-13  (_resolve_compare)
      oqlos/core/safe_eval.py:90-92  (_eval_compare)
  [1e99fb45a36e6fcc]   STRU  disconnect  L=3 N=2 saved=3 sim=1.00
      oqlos/hardware/plugins/lung.py:85-87  (disconnect)
      oqlos/hardware/plugins/piadc.py:136-138  (disconnect)
  [af1f7d2eecf9deab]   STRU  check_firmware_health  L=3 N=2 saved=3 sim=1.00
      oqlos/tools/hardware_diagnose/health.py:30-32  (check_firmware_health)
      oqlos/tools/hardware_diagnose/health.py:35-37  (check_firmware_identify)
  [02c469bbb0845b01]   STRU  _migrate_wait_line  L=3 N=2 saved=3 sim=1.00
      scripts/migrate_to_v4.py:124-126  (_migrate_wait_line)
      scripts/migrate_to_v4.py:144-146  (_migrate_save_line)
  [F0008]   FUZZ  parser  L=3 N=2 saved=3 sim=0.94
      oqlos/core/oql_parser.py:263-265  (parser)
      oqlos/core/oql_parser.py:409-411  (parser)
  [F0002]   FUZZ  _oql_quote  L=3 N=2 saved=3 sim=0.94
      oqlos/core/_interpreter_actions.py:96-98  (_oql_quote)
      oqlos/tools/xml_import/generators.py:55-58  (_quote_oql)
  [F0011]   FUZZ  _handle_stop_http  L=3 N=2 saved=3 sim=0.93
      oqlos/hardware/plugins/lung.py:241-243  (_handle_stop_http)
      oqlos/hardware/plugins/lung.py:278-280  (_handle_status_http)
  [F0005]   FUZZ  _firmware  L=3 N=2 saved=3 sim=0.91
      oqlos/core/interpreter.py:99-101  (_firmware)
      oqlos/core/interpreter.py:109-111  (_firmware_url)
  [F0006]   FUZZ  _normalize_valve_value  L=3 N=2 saved=3 sim=0.91
      oqlos/core/interpreter.py:129-131  (_normalize_valve_value)
      oqlos/core/interpreter.py:133-135  (_normalize_lung_value)
  [F0003]   FUZZ  lower  L=3 N=2 saved=3 sim=0.90
      oqlos/core/_oql_adapter.py:204-206  (lower)
      oqlos/core/_oql_adapter.py:202-207  (_make_lower_minmax)
  [F0009]   FUZZ  discover  L=3 N=2 saved=3 sim=0.89
      oqlos/hardware/drivers/mqtt.py:103-105  (discover)
      oqlos/hardware/protocol.py:48-50  (discover)
  [F0012]   FUZZ  _handle_stop_usb  L=3 N=2 saved=3 sim=0.89
      oqlos/hardware/plugins/lung.py:245-247  (_handle_stop_usb)
      oqlos/hardware/plugins/lung.py:282-284  (_handle_status_usb)
  [F0010]   FUZZ  connect  L=3 N=2 saved=3 sim=0.88
      oqlos/hardware/plugins/base.py:292-294  (connect)
      oqlos/hardware/plugins/base.py:297-299  (disconnect)
  [F0013]   FUZZ  get_plugin_class  L=3 N=2 saved=3 sim=0.86
      oqlos/hardware/plugins/registry.py:70-72  (get_plugin_class)
      oqlos/hardware/plugins/registry.py:120-122  (get_instance)
  [F0001]   FUZZ  hardware_modbus_waveshare_diagnose_v3  L=3 N=2 saved=3 sim=0.85
      oqlos/api/_hw3_system.py:67-69  (hardware_modbus_waveshare_diagnose_v3)
      oqlos/api/_hw3_system.py:73-75  (hardware_modbus_wizard_plan_v3)

REFACTOR[35] (ranked by priority):
  [1] ○ extract_function   → oqlos/core/utils/_exec_set_peripheral.py
      WHY: 2 occurrences of 11-line block across 2 files — saves 11 lines
      FILES: oqlos/core/_firmware_executor.py, oqlos/core/interpreter.py
  [2] ○ extract_function   → oqlos/core/utils/_try_set.py
      WHY: 3 occurrences of 5-line block across 1 files — saves 10 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [3] ○ extract_function   → scripts/utils/_mig_goto.py
      WHY: 3 occurrences of 5-line block across 1 files — saves 10 lines
      FILES: scripts/oql_v2_to_v4_migrate_db.py
  [4] ○ extract_function   → oqlos/core/utils/_make_args_parser.py
      WHY: 2 occurrences of 8-line block across 1 files — saves 8 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [5] ○ extract_class      → oqlos/hardware/plugins/utils/_handle_status_modbus.py
      WHY: 2 occurrences of 8-line block across 1 files — saves 8 lines
      FILES: oqlos/hardware/plugins/motor.py
  [6] ○ extract_function   → oqlos/core/utils/_make_stripped_field_parser.py
      WHY: 2 occurrences of 8-line block across 1 files — saves 8 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [7] ○ extract_function   → oqlos/hardware/utils/modbus_plugins_need_repair.py
      WHY: 2 occurrences of 6-line block across 2 files — saves 6 lines
      FILES: oqlos/hardware/client/autorepair.py, oqlos/hardware/diagnosis_plugin_health.py
  [8] ○ extract_class      → oqlos/core/utils/_execute_firmware_action.py
      WHY: 3 occurrences of 3-line block across 1 files — saves 6 lines
      FILES: oqlos/core/interpreter.py
  [9] ○ extract_function   → oqlos/core/utils/_make_single_field_parser.py
      WHY: 2 occurrences of 6-line block across 1 files — saves 6 lines
      FILES: oqlos/core/oql_parser.py
  [10] ○ extract_class      → oqlos/core/utils/_firmware.py
      WHY: 3 occurrences of 3-line block across 1 files — saves 6 lines
      FILES: oqlos/core/interpreter.py
  [11] ○ extract_function   → oqlos/api/utils/_default_path.py
      WHY: 2 occurrences of 5-line block across 2 files — saves 5 lines
      FILES: oqlos/api/hardware_events.py, oqlos/api/hardware_mapping_store.py
  [12] ○ extract_function   → oqlos/dsl/utils/_merge_object_function_map.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/dsl/schema.py
  [13] ○ extract_function   → oqlos/core/utils/parser.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [14] ○ extract_function   → oqlos/core/utils/parser.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/core/oql_parser.py
  [15] ○ extract_function   → oqlos/core/utils/parser.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [16] ○ extract_function   → oqlos/hardware/utils/get_json.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/hardware/gateway_http.py
  [17] ○ extract_function   → oqlos/core/utils/_try_repeat_start.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [18] ○ extract_function   → oqlos/hardware/plugins/utils/__init__.py
      WHY: 2 occurrences of 4-line block across 2 files — saves 4 lines
      FILES: oqlos/hardware/plugins/modbus.py, oqlos/hardware/plugins/modbus_adc.py
  [19] ○ extract_function   → oqlos/hardware/plugins/utils/__init__.py
      WHY: 2 occurrences of 4-line block across 2 files — saves 4 lines
      FILES: oqlos/hardware/plugins/lung.py, oqlos/hardware/plugins/piadc.py
  [20] ○ extract_function   → oqlos/api/utils/get_execution.py
      WHY: 2 occurrences of 3-line block across 2 files — saves 3 lines
      FILES: oqlos/api/execution.py, oqlos/api/peripherals.py
  [21] ○ extract_function   → oqlos/core/utils/_resolve_compare.py
      WHY: 2 occurrences of 3-line block across 2 files — saves 3 lines
      FILES: oqlos/core/executor.py, oqlos/core/safe_eval.py
  [22] ○ extract_function   → oqlos/hardware/plugins/utils/disconnect.py
      WHY: 2 occurrences of 3-line block across 2 files — saves 3 lines
      FILES: oqlos/hardware/plugins/lung.py, oqlos/hardware/plugins/piadc.py
  [23] ○ extract_function   → oqlos/tools/hardware_diagnose/utils/check_firmware_health.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/tools/hardware_diagnose/health.py
  [24] ○ extract_function   → scripts/utils/_migrate_wait_line.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: scripts/migrate_to_v4.py
  [25] ○ extract_function   → oqlos/core/utils/parser.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/core/oql_parser.py
  [26] ○ extract_function   → oqlos/utils/_oql_quote.py
      WHY: 2 occurrences of 3-line block across 2 files — saves 3 lines
      FILES: oqlos/core/_interpreter_actions.py, oqlos/tools/xml_import/generators.py
  [27] ○ extract_class      → oqlos/hardware/plugins/utils/_handle_stop_http.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/hardware/plugins/lung.py
  [28] ○ extract_class      → oqlos/core/utils/_firmware.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/core/interpreter.py
  [29] ○ extract_class      → oqlos/core/utils/_normalize_valve_value.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/core/interpreter.py
  [30] ○ extract_function   → oqlos/core/utils/lower.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/core/_oql_adapter.py
  [31] ○ extract_function   → oqlos/hardware/utils/discover.py
      WHY: 2 occurrences of 3-line block across 2 files — saves 3 lines
      FILES: oqlos/hardware/drivers/mqtt.py, oqlos/hardware/protocol.py
  [32] ○ extract_class      → oqlos/hardware/plugins/utils/_handle_stop_usb.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/hardware/plugins/lung.py
  [33] ○ extract_class      → oqlos/hardware/plugins/utils/connect.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/hardware/plugins/base.py
  [34] ○ extract_class      → oqlos/hardware/plugins/utils/get_plugin_class.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/hardware/plugins/registry.py
  [35] ○ extract_function   → oqlos/api/utils/hardware_modbus_waveshare_diagnose_v3.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/api/_hw3_system.py

QUICK_WINS[10] (low risk, high savings — do first):
  [1] extract_function   saved=11L  → oqlos/core/utils/_exec_set_peripheral.py
      FILES: _firmware_executor.py, interpreter.py
  [2] extract_function   saved=10L  → oqlos/core/utils/_try_set.py
      FILES: _cql_tokenizer.py
  [3] extract_function   saved=10L  → scripts/utils/_mig_goto.py
      FILES: oql_v2_to_v4_migrate_db.py
  [4] extract_function   saved=8L  → oqlos/core/utils/_make_args_parser.py
      FILES: _cql_tokenizer.py
  [5] extract_class      saved=8L  → oqlos/hardware/plugins/utils/_handle_status_modbus.py
      FILES: motor.py
  [6] extract_function   saved=8L  → oqlos/core/utils/_make_stripped_field_parser.py
      FILES: _cql_tokenizer.py
  [7] extract_function   saved=6L  → oqlos/hardware/utils/modbus_plugins_need_repair.py
      FILES: autorepair.py, diagnosis_plugin_health.py
  [8] extract_class      saved=6L  → oqlos/core/utils/_execute_firmware_action.py
      FILES: interpreter.py
  [9] extract_function   saved=6L  → oqlos/core/utils/_make_single_field_parser.py
      FILES: oql_parser.py
  [10] extract_class      saved=6L  → oqlos/core/utils/_firmware.py
      FILES: interpreter.py

EFFORT_ESTIMATE (total ≈ 5.7h):
  easy   _exec_set_peripheral                saved=11L  ~22min
  easy   _try_set                            saved=10L  ~20min
  easy   _mig_goto                           saved=10L  ~20min
  easy   _make_args_parser                   saved=8L  ~16min
  easy   _handle_status_modbus               saved=8L  ~16min
  easy   _make_stripped_field_parser         saved=8L  ~16min
  easy   modbus_plugins_need_repair          saved=6L  ~12min
  easy   _execute_firmware_action            saved=6L  ~12min
  easy   _make_single_field_parser           saved=6L  ~12min
  easy   _firmware                           saved=6L  ~12min
  ... +25 more (~182min)

METRICS-TARGET:
  dup_groups:  35 → 0
  saved_lines: 170 lines recoverable
```

### Evolution / Churn (`project/evolution.toon.yaml`)

```toon markpact:analysis path=project/evolution.toon.yaml
# code2llm/evolution | 2286 func | 258f | 2026-07-02
# generated in 0.01s

NEXT[3] (ranked by impact):
  [1] !! SPLIT           frontend/src/i18n/dictionaries.js
      WHY: 2135L, 0 classes, max CC=5
      EFFORT: ~4h  IMPACT: 10675

  [2] !! SPLIT           frontend/src/pages/mapEditorDefaultMap.js
      WHY: 1953L, 0 classes, max CC=1
      EFFORT: ~4h  IMPACT: 1953

  [3] !! SPLIT           docs/README.md
      WHY: 2362L, 0 classes, max CC=0
      EFFORT: ~4h  IMPACT: 0


RISKS[3]:
  ⚠ Splitting docs/README.md may break 0 import paths
  ⚠ Splitting frontend/src/i18n/dictionaries.js may break 4 import paths
  ⚠ Splitting frontend/src/pages/mapEditorDefaultMap.js may break 3 import paths

METRICS-TARGET:
  CC̄:          3.8 → ≤2.7
  max-CC:      14 → ≤7
  god-modules: 19 → 0
  high-CC(≥15): 0 → ≤0
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
  prev CC̄=3.8 → now CC̄=3.8
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
