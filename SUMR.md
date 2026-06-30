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
- **version**: `0.1.27`
- **python_requires**: `>=3.10`
- **license**: {'text': 'Apache-2.0'}
- **ai_model**: `openrouter/qwen/qwen3-coder-next`
- **ecosystem**: SUMD + DOQL + testql + taskfile
- **openapi_title**: oqlos API v1.0.0
- **generated_from**: pyproject.toml, Taskfile.yml, testql(6), openapi(49 ep), app.doql.less, pyqual.yaml, goal.yaml, .env.example, Dockerfile, docker-compose.dev.yml, src(1 mod), project/(6 analysis files)

## Architecture

```
SUMD (description) → DOQL/source (code) → taskfile (automation) → testql (verification)
```

### DOQL Application Declaration (`app.doql.less`)

```less markpact:doql path=app.doql.less
// LESS format — define @variables here as needed

app {
  name: oqlos;
  version: 0.1.27;
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

*438 nodes · 500 edges · 68 modules · CC̄=4.2*

### Hubs (by degree)

| Function | CC | in | out | total |
|----------|----|----|-----|-------|
| `print` *(in examples.hardware.doctor-workflow)* | 0 | 226 | 0 | **226** |
| `_resolve` *(in oqlos.hardware.transport.manage_ops)* | 5 | 1 | 51 | **52** |
| `list_usb_devices` *(in oqlos.hardware.usb_diagnostics)* | 13 ⚠ | 2 | 33 | **35** |
| `canonicalize_oql_line` *(in oqlos.tools.cql_cli.formatting)* | 14 ⚠ | 1 | 31 | **32** |
| `oql_doc_to_cql` *(in oqlos.core._oql_adapter)* | 12 ⚠ | 2 | 30 | **32** |
| `normalize_motor2_runtime_config` *(in oqlos.core.motor2_runtime)* | 12 ⚠ | 1 | 29 | **30** |
| `_safe_resolve` *(in oqlos.core.executor)* | 14 ⚠ | 7 | 21 | **28** |
| `probe_options_from_args` *(in oqlos.tools.hardware_diagnose.modbus_probe)* | 2 | 1 | 27 | **28** |

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/oqlos/oqlos
# generated in 0.21s
# nodes: 438 | edges: 500 | modules: 68
# CC̄=4.2

HUBS[20]:
  examples.hardware.doctor-workflow.print
    CC=0  in:226  out:0  total:226
  oqlos.hardware.transport.manage_ops._resolve
    CC=5  in:1  out:51  total:52
  oqlos.hardware.usb_diagnostics.list_usb_devices
    CC=13  in:2  out:33  total:35
  oqlos.tools.cql_cli.formatting.canonicalize_oql_line
    CC=14  in:1  out:31  total:32
  oqlos.core._oql_adapter.oql_doc_to_cql
    CC=12  in:2  out:30  total:32
  oqlos.core.motor2_runtime.normalize_motor2_runtime_config
    CC=12  in:1  out:29  total:30
  oqlos.core.executor._safe_resolve
    CC=14  in:7  out:21  total:28
  oqlos.tools.hardware_diagnose.modbus_probe.probe_options_from_args
    CC=2  in:1  out:27  total:28
  oqlos.hardware.usb_diagnostics.pi_system_diagnostics
    CC=9  in:0  out:28  total:28
  oqlos.hardware.rtc_probe.build_rtc_peripheral_status
    CC=11  in:0  out:27  total:27
  setup_hardware_and_run_oql.run_oql_scenario
    CC=8  in:1  out:24  total:25
  oqlos.core.oql_parser.parse_oql
    CC=14  in:3  out:21  total:24
  oqlos.core.parser.parse_dsl_to_goal_with_issues
    CC=13  in:3  out:21  total:24
  oqlos.core._line_parsers._parse_if_condition
    CC=9  in:1  out:22  total:23
  oqlos.tools.hardware_diagnose.doctor._analyze_modbus_adc_config
    CC=12  in:1  out:22  total:23
  oqlos.tools.hardware_diagnose.doctor.format_doctor
    CC=6  in:2  out:21  total:23
  oqlos.core._line_parsers._parse_set_line
    CC=12  in:1  out:21  total:22
  oqlos.tools.hardware_diagnose.shell._dispatch_command
    CC=6  in:1  out:21  total:22
  oqlos.tools.hardware_diagnose.health.cmd_diagnose
    CC=6  in:2  out:20  total:22
  oqlos.tools.cql_cli.commands.handle_list_command
    CC=7  in:1  out:21  total:22

MODULES:
  examples.hardware.doctor-workflow  [1 funcs]
    print  CC=0  out:0
  oqlos.api.plugins  [1 funcs]
    validate_plugin_configs  CC=3  out:11
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
    _parse_goal_line  CC=12  out:20
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
  oqlos.core._interpreter_actions  [5 funcs]
    exec_action_min_max  CC=3  out:5
    exec_action_save  CC=4  out:6
    exec_action_set  CC=9  out:11
    exec_action_val  CC=3  out:4
    exec_action_wait  CC=3  out:4
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
  oqlos.core._oql_adapter  [14 funcs]
    _cmd_to_actions  CC=2  out:3
    _fmt_value  CC=2  out:1
    _load_includes  CC=12  out:15
    _lower_call  CC=6  out:10
    _lower_max  CC=1  out:3
    _lower_min  CC=1  out:3
    _lower_set  CC=1  out:3
    _parse_macro_line  CC=8  out:10
    _resolve_include  CC=6  out:8
    _scenarios_root  CC=1  out:2
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
    parse  CC=3  out:5
  oqlos.core.motor2_runtime  [9 funcs]
    _coerce_int  CC=3  out:6
    _compute_motor2_cycles  CC=3  out:7
    _compute_motor2_speed  CC=4  out:6
    _normalize_motor2_direction  CC=4  out:2
    _pick  CC=4  out:0
    build_motor2_reciprocating_plan  CC=7  out:8
    motor2_max_steps_per_second  CC=2  out:3
    motor2_speed_for_duration  CC=1  out:9
    normalize_motor2_runtime_config  CC=12  out:29
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
  oqlos.hardware.artificial_lung  [10 funcs]
    _clamp_lpm  CC=2  out:3
    _command_response  CC=2  out:1
    _lung_cmd_emergency_stop  CC=3  out:3
    _lung_cmd_lung_cycle  CC=4  out:12
    _lung_cmd_lung_start  CC=4  out:11
    _lung_cmd_lung_status  CC=2  out:3
    _lung_cmd_lung_stop  CC=3  out:3
    _lung_cmd_set_lpm  CC=1  out:3
    execute_command  CC=4  out:6
    get_peripheral_status  CC=6  out:8
  oqlos.hardware.config_paths  [1 funcs]
    resolve_oqlos_config_path  CC=6  out:13
  oqlos.hardware.config_schema  [2 funcs]
    build_dynamic_schema_models  CC=2  out:4
    get_hardware_config  CC=2  out:4
  oqlos.hardware.discovery  [2 funcs]
    probe_waveshare_modbus  CC=5  out:2
    probe_waveshare_modbus_adc  CC=5  out:2
  oqlos.hardware.gateway  [1 funcs]
    __init__  CC=6  out:13
  oqlos.hardware.identify_enrichment  [1 funcs]
    enrich_identify_payload  CC=2  out:4
  oqlos.hardware.modbus_identify  [8 funcs]
    _device_to_candidate  CC=8  out:10
    _infer_modbus_serial_port  CC=10  out:9
    _is_modbus_candidate  CC=5  out:3
    _usb_blob  CC=3  out:4
    collect_modbus_serial_candidates  CC=6  out:6
    enrich_modbus_identify  CC=1  out:2
    enrich_modbus_serial_hints  CC=10  out:12
    enrich_platform_modbus_ports  CC=10  out:13
  oqlos.hardware.plugin_gateway  [4 funcs]
    __init__  CC=3  out:6
    _load_hardware_schema  CC=3  out:8
    modbus_preflight_report  CC=4  out:4
    reload_configs  CC=5  out:11
  oqlos.hardware.plugins._rtu_serial  [2 funcs]
    reopen_rtu_after_stale  CC=4  out:6
    serial_error_is_stale  CC=4  out:2
  oqlos.hardware.plugins._shared  [4 funcs]
    health_check_exception  CC=1  out:1
    http_disconnect  CC=2  out:2
    http_health_check  CC=2  out:5
    not_connected_health  CC=1  out:1
  oqlos.hardware.plugins.base  [3 funcs]
    dynamic_peripheral_model  CC=5  out:8
    dynamic_plugin_schema_models  CC=2  out:7
    get_pluggy_manager  CC=1  out:0
  oqlos.hardware.plugins.lung  [3 funcs]
    _health_check_http  CC=11  out:14
    disconnect  CC=1  out:1
    health_check  CC=5  out:4
  oqlos.hardware.plugins.modbus  [1 funcs]
    health_check  CC=11  out:9
  oqlos.hardware.plugins.modbus_adc  [5 funcs]
    _read_registers  CC=6  out:16
    execute_command  CC=10  out:11
    health_check  CC=8  out:16
    _modbus_error  CC=2  out:4
    _resolve_channel  CC=3  out:8
  oqlos.hardware.plugins.motor  [2 funcs]
    disconnect  CC=2  out:1
    health_check  CC=17  out:19
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
  oqlos.hardware.rtc_probe  [7 funcs]
    _pirtc_request_sync  CC=8  out:10
    build_rtc_adapter_entry  CC=8  out:13
    build_rtc_peripheral_status  CC=11  out:27
    enrich_rtc_adapter  CC=8  out:11
    get_pirtc_base_url  CC=1  out:2
    is_rtc_hardware_enabled  CC=3  out:3
    run_rtc_command  CC=4  out:4
  oqlos.hardware.scanner_probe  [13 funcs]
    _canonical_match_key  CC=8  out:10
    _is_likely_scanner_input  CC=10  out:4
    _is_likely_scanner_usb_blob  CC=7  out:4
    _match_blob  CC=3  out:4
    _match_priority  CC=8  out:4
    _merge_matches  CC=6  out:5
    _scan_diagnostics_usb_matches  CC=14  out:17
    _scan_input_matches  CC=8  out:15
    _scan_lsusb_matches  CC=5  out:8
    _usb_product_blob  CC=3  out:4
  oqlos.hardware.sidecar_control  [7 funcs]
    _dri0050_paths  CC=9  out:16
    _free_api_port  CC=7  out:10
    _http_sidecar_healthy  CC=4  out:4
    _modbus_serial_candidates  CC=4  out:6
    _run_cmd  CC=3  out:6
    ensure_dri0050_sidecar  CC=13  out:15
    resolve_dri0050_serial  CC=13  out:16
  oqlos.hardware.stack_snapshot  [4 funcs]
    _build_recommended_actions  CC=8  out:8
    _get_modbus_preflight  CC=5  out:4
    _lazy_hardware_api  CC=1  out:0
    build_hardware_stack_snapshot  CC=3  out:11
  oqlos.hardware.transport.manage_ops  [2 funcs]
    _resolve  CC=5  out:51
    run_manage_verb  CC=3  out:3
  oqlos.hardware.transport.mqtt_oql_bridge  [5 funcs]
    _run_manage  CC=3  out:8
    _run_oql  CC=5  out:11
    __init__  CC=4  out:5
    _make_client  CC=4  out:3
    build_topics  CC=1  out:2
  oqlos.hardware.usb_diagnostics  [5 funcs]
    _find_tty  CC=5  out:16
    _read  CC=2  out:3
    list_usb_devices  CC=13  out:33
    pi_system_diagnostics  CC=9  out:28
    reset_usb_device  CC=12  out:6
  oqlos.reporters.html_report  [3 funcs]
    _render_goal  CC=10  out:13
    _render_step  CC=7  out:19
    _render_thresholds_table  CC=2  out:12
  oqlos.reporters.json_reporter  [5 funcs]
    _collect_thresholds  CC=8  out:4
    _extract_metadata  CC=2  out:4
    _group_steps_into_goals  CC=6  out:11
    _step_to_dict  CC=6  out:1
    report_json  CC=2  out:8
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
  oqlos.tools.cql_cli  [2 funcs]
    _sync_compat_symbols  CC=1  out:0
    main  CC=1  out:2
  oqlos.tools.cql_cli.commands  [5 funcs]
    _run_continuous_mode  CC=4  out:20
    execute_command_with_cleanup  CC=8  out:7
    handle_list_command  CC=7  out:21
    run_single_command  CC=1  out:2
    run_source  CC=2  out:3
  oqlos.tools.cql_cli.formatting  [2 funcs]
    canonicalize_oql_line  CC=14  out:31
    canonicalize_oql_text  CC=3  out:4
  oqlos.tools.cql_cli.main  [18 funcs]
    _create_interpreter  CC=1  out:1
    _dispatch_to_mode  CC=8  out:13
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
  oqlos.tools.hardware_diagnose.doctor  [39 funcs]
    _adapter_health_status  CC=3  out:1
    _add_issue  CC=2  out:1
    _analyze_firmware_access  CC=7  out:11
    _analyze_modbus_adc_config  CC=12  out:22
    _analyze_modbus_config  CC=11  out:20
    _analyze_serial_port_owners  CC=13  out:19
    _canonical_device_path  CC=2  out:3
    _check_firmware_adapters  CC=7  out:9
    _check_firmware_health_error  CC=3  out:2
    _check_firmware_mode  CC=3  out:4
  oqlos.tools.hardware_diagnose.health  [7 funcs]
    _format_health_value  CC=8  out:9
    _is_health_ok  CC=5  out:6
    _request_firmware_json  CC=8  out:9
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
  oqlos.tools.xml_import.generators  [15 funcs]
    _append_sensor_assertion  CC=6  out:3
    _build_steps_from_op  CC=10  out:14
    _build_validation_criteria  CC=14  out:3
    _emit_cql_output  CC=5  out:15
    _emit_cql_param  CC=7  out:5
    _emit_cql_sensor_param  CC=13  out:11
    _emit_dsl_param  CC=10  out:13
    _emit_dsl_sensors  CC=8  out:7
    _emit_set  CC=1  out:3
    _format_range  CC=9  out:0
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
  oqlos.core.oql_parser.parse_duration → oqlos.core.oql_parser.to_num
  oqlos.core.oql_parser.duration_to_ms → oqlos.core.oql_parser.parse_duration
  oqlos.core.oql_parser._split_value_unit → oqlos.core.oql_parser.to_num
  oqlos.core.oql_parser._split_set_value_unit → oqlos.core.oql_parser._split_value_unit
  oqlos.core.oql_parser.parse_SET → oqlos.core.oql_parser._require
  oqlos.core.oql_parser.parse_SET → oqlos.core.oql_parser._split_set_value_unit
  oqlos.core.oql_parser.parse_GET → oqlos.core.oql_parser._require
  oqlos.core.oql_parser.parse_WAIT → oqlos.core.oql_parser._require
  oqlos.core.oql_parser.parse_WAIT → oqlos.core.oql_parser.parse_duration
  oqlos.core.oql_parser.parse_WAIT → oqlos.core.oql_parser.duration_to_ms
  oqlos.core.oql_parser.parse_IF_DELTA → oqlos.core.oql_parser._require
  oqlos.core.oql_parser.parse_IF_DELTA → oqlos.core.oql_parser.to_num
  oqlos.core.oql_parser.parse_IF_DELTA → oqlos.core.oql_parser.duration_to_ms
  oqlos.core.oql_parser.parse_SAVE → oqlos.core.oql_parser._require
  oqlos.core.oql_parser.parse_CHECK → oqlos.core.oql_parser.to_num
  oqlos.core.oql_parser.parse_IF → oqlos.core.oql_parser.to_num
  oqlos.core.oql_parser.parse_MIN → oqlos.core.oql_parser._require
  oqlos.core.oql_parser.parse_MIN → oqlos.core.oql_parser._split_value_unit
  oqlos.core.oql_parser.parse_MAX → oqlos.core.oql_parser._require
  oqlos.core.oql_parser.parse_MAX → oqlos.core.oql_parser._split_value_unit
  oqlos.core.oql_parser.parse_SAMPLE → oqlos.core.oql_parser._require
  oqlos.core.oql_parser.parse_SAMPLE → oqlos.core.oql_parser.duration_to_ms
  oqlos.core.oql_parser.parse_CALL → oqlos.core.oql_parser._require
  oqlos.core.oql_parser.parse_INCLUDE → oqlos.core.oql_parser._require
  oqlos.core.oql_parser.parse_FUNC_CALL → oqlos.core.oql_parser._require
  oqlos.core.oql_parser._expand_repeat_block_lines → oqlos.core.oql_parser._line_indent
  oqlos.core.oql_parser._expand_repeat_blocks → oqlos.core.oql_parser._expand_repeat_block_lines
  oqlos.core.oql_parser._handle_top_level_line → oqlos.core.oql_parser.tokenize
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
# generated in 0.21s
# nodes: 438 | edges: 500 | modules: 68
# CC̄=4.2

HUBS[20]:
  examples.hardware.doctor-workflow.print
    CC=0  in:226  out:0  total:226
  oqlos.hardware.transport.manage_ops._resolve
    CC=5  in:1  out:51  total:52
  oqlos.hardware.usb_diagnostics.list_usb_devices
    CC=13  in:2  out:33  total:35
  oqlos.tools.cql_cli.formatting.canonicalize_oql_line
    CC=14  in:1  out:31  total:32
  oqlos.core._oql_adapter.oql_doc_to_cql
    CC=12  in:2  out:30  total:32
  oqlos.core.motor2_runtime.normalize_motor2_runtime_config
    CC=12  in:1  out:29  total:30
  oqlos.core.executor._safe_resolve
    CC=14  in:7  out:21  total:28
  oqlos.tools.hardware_diagnose.modbus_probe.probe_options_from_args
    CC=2  in:1  out:27  total:28
  oqlos.hardware.usb_diagnostics.pi_system_diagnostics
    CC=9  in:0  out:28  total:28
  oqlos.hardware.rtc_probe.build_rtc_peripheral_status
    CC=11  in:0  out:27  total:27
  setup_hardware_and_run_oql.run_oql_scenario
    CC=8  in:1  out:24  total:25
  oqlos.core.oql_parser.parse_oql
    CC=14  in:3  out:21  total:24
  oqlos.core.parser.parse_dsl_to_goal_with_issues
    CC=13  in:3  out:21  total:24
  oqlos.core._line_parsers._parse_if_condition
    CC=9  in:1  out:22  total:23
  oqlos.tools.hardware_diagnose.doctor._analyze_modbus_adc_config
    CC=12  in:1  out:22  total:23
  oqlos.tools.hardware_diagnose.doctor.format_doctor
    CC=6  in:2  out:21  total:23
  oqlos.core._line_parsers._parse_set_line
    CC=12  in:1  out:21  total:22
  oqlos.tools.hardware_diagnose.shell._dispatch_command
    CC=6  in:1  out:21  total:22
  oqlos.tools.hardware_diagnose.health.cmd_diagnose
    CC=6  in:2  out:20  total:22
  oqlos.tools.cql_cli.commands.handle_list_command
    CC=7  in:1  out:21  total:22

MODULES:
  examples.hardware.doctor-workflow  [1 funcs]
    print  CC=0  out:0
  oqlos.api.plugins  [1 funcs]
    validate_plugin_configs  CC=3  out:11
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
    _parse_goal_line  CC=12  out:20
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
  oqlos.core._interpreter_actions  [5 funcs]
    exec_action_min_max  CC=3  out:5
    exec_action_save  CC=4  out:6
    exec_action_set  CC=9  out:11
    exec_action_val  CC=3  out:4
    exec_action_wait  CC=3  out:4
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
  oqlos.core._oql_adapter  [14 funcs]
    _cmd_to_actions  CC=2  out:3
    _fmt_value  CC=2  out:1
    _load_includes  CC=12  out:15
    _lower_call  CC=6  out:10
    _lower_max  CC=1  out:3
    _lower_min  CC=1  out:3
    _lower_set  CC=1  out:3
    _parse_macro_line  CC=8  out:10
    _resolve_include  CC=6  out:8
    _scenarios_root  CC=1  out:2
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
    parse  CC=3  out:5
  oqlos.core.motor2_runtime  [9 funcs]
    _coerce_int  CC=3  out:6
    _compute_motor2_cycles  CC=3  out:7
    _compute_motor2_speed  CC=4  out:6
    _normalize_motor2_direction  CC=4  out:2
    _pick  CC=4  out:0
    build_motor2_reciprocating_plan  CC=7  out:8
    motor2_max_steps_per_second  CC=2  out:3
    motor2_speed_for_duration  CC=1  out:9
    normalize_motor2_runtime_config  CC=12  out:29
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
  oqlos.hardware.artificial_lung  [10 funcs]
    _clamp_lpm  CC=2  out:3
    _command_response  CC=2  out:1
    _lung_cmd_emergency_stop  CC=3  out:3
    _lung_cmd_lung_cycle  CC=4  out:12
    _lung_cmd_lung_start  CC=4  out:11
    _lung_cmd_lung_status  CC=2  out:3
    _lung_cmd_lung_stop  CC=3  out:3
    _lung_cmd_set_lpm  CC=1  out:3
    execute_command  CC=4  out:6
    get_peripheral_status  CC=6  out:8
  oqlos.hardware.config_paths  [1 funcs]
    resolve_oqlos_config_path  CC=6  out:13
  oqlos.hardware.config_schema  [2 funcs]
    build_dynamic_schema_models  CC=2  out:4
    get_hardware_config  CC=2  out:4
  oqlos.hardware.discovery  [2 funcs]
    probe_waveshare_modbus  CC=5  out:2
    probe_waveshare_modbus_adc  CC=5  out:2
  oqlos.hardware.gateway  [1 funcs]
    __init__  CC=6  out:13
  oqlos.hardware.identify_enrichment  [1 funcs]
    enrich_identify_payload  CC=2  out:4
  oqlos.hardware.modbus_identify  [8 funcs]
    _device_to_candidate  CC=8  out:10
    _infer_modbus_serial_port  CC=10  out:9
    _is_modbus_candidate  CC=5  out:3
    _usb_blob  CC=3  out:4
    collect_modbus_serial_candidates  CC=6  out:6
    enrich_modbus_identify  CC=1  out:2
    enrich_modbus_serial_hints  CC=10  out:12
    enrich_platform_modbus_ports  CC=10  out:13
  oqlos.hardware.plugin_gateway  [4 funcs]
    __init__  CC=3  out:6
    _load_hardware_schema  CC=3  out:8
    modbus_preflight_report  CC=4  out:4
    reload_configs  CC=5  out:11
  oqlos.hardware.plugins._rtu_serial  [2 funcs]
    reopen_rtu_after_stale  CC=4  out:6
    serial_error_is_stale  CC=4  out:2
  oqlos.hardware.plugins._shared  [4 funcs]
    health_check_exception  CC=1  out:1
    http_disconnect  CC=2  out:2
    http_health_check  CC=2  out:5
    not_connected_health  CC=1  out:1
  oqlos.hardware.plugins.base  [3 funcs]
    dynamic_peripheral_model  CC=5  out:8
    dynamic_plugin_schema_models  CC=2  out:7
    get_pluggy_manager  CC=1  out:0
  oqlos.hardware.plugins.lung  [3 funcs]
    _health_check_http  CC=11  out:14
    disconnect  CC=1  out:1
    health_check  CC=5  out:4
  oqlos.hardware.plugins.modbus  [1 funcs]
    health_check  CC=11  out:9
  oqlos.hardware.plugins.modbus_adc  [5 funcs]
    _read_registers  CC=6  out:16
    execute_command  CC=10  out:11
    health_check  CC=8  out:16
    _modbus_error  CC=2  out:4
    _resolve_channel  CC=3  out:8
  oqlos.hardware.plugins.motor  [2 funcs]
    disconnect  CC=2  out:1
    health_check  CC=17  out:19
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
  oqlos.hardware.rtc_probe  [7 funcs]
    _pirtc_request_sync  CC=8  out:10
    build_rtc_adapter_entry  CC=8  out:13
    build_rtc_peripheral_status  CC=11  out:27
    enrich_rtc_adapter  CC=8  out:11
    get_pirtc_base_url  CC=1  out:2
    is_rtc_hardware_enabled  CC=3  out:3
    run_rtc_command  CC=4  out:4
  oqlos.hardware.scanner_probe  [13 funcs]
    _canonical_match_key  CC=8  out:10
    _is_likely_scanner_input  CC=10  out:4
    _is_likely_scanner_usb_blob  CC=7  out:4
    _match_blob  CC=3  out:4
    _match_priority  CC=8  out:4
    _merge_matches  CC=6  out:5
    _scan_diagnostics_usb_matches  CC=14  out:17
    _scan_input_matches  CC=8  out:15
    _scan_lsusb_matches  CC=5  out:8
    _usb_product_blob  CC=3  out:4
  oqlos.hardware.sidecar_control  [7 funcs]
    _dri0050_paths  CC=9  out:16
    _free_api_port  CC=7  out:10
    _http_sidecar_healthy  CC=4  out:4
    _modbus_serial_candidates  CC=4  out:6
    _run_cmd  CC=3  out:6
    ensure_dri0050_sidecar  CC=13  out:15
    resolve_dri0050_serial  CC=13  out:16
  oqlos.hardware.stack_snapshot  [4 funcs]
    _build_recommended_actions  CC=8  out:8
    _get_modbus_preflight  CC=5  out:4
    _lazy_hardware_api  CC=1  out:0
    build_hardware_stack_snapshot  CC=3  out:11
  oqlos.hardware.transport.manage_ops  [2 funcs]
    _resolve  CC=5  out:51
    run_manage_verb  CC=3  out:3
  oqlos.hardware.transport.mqtt_oql_bridge  [5 funcs]
    _run_manage  CC=3  out:8
    _run_oql  CC=5  out:11
    __init__  CC=4  out:5
    _make_client  CC=4  out:3
    build_topics  CC=1  out:2
  oqlos.hardware.usb_diagnostics  [5 funcs]
    _find_tty  CC=5  out:16
    _read  CC=2  out:3
    list_usb_devices  CC=13  out:33
    pi_system_diagnostics  CC=9  out:28
    reset_usb_device  CC=12  out:6
  oqlos.reporters.html_report  [3 funcs]
    _render_goal  CC=10  out:13
    _render_step  CC=7  out:19
    _render_thresholds_table  CC=2  out:12
  oqlos.reporters.json_reporter  [5 funcs]
    _collect_thresholds  CC=8  out:4
    _extract_metadata  CC=2  out:4
    _group_steps_into_goals  CC=6  out:11
    _step_to_dict  CC=6  out:1
    report_json  CC=2  out:8
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
  oqlos.tools.cql_cli  [2 funcs]
    _sync_compat_symbols  CC=1  out:0
    main  CC=1  out:2
  oqlos.tools.cql_cli.commands  [5 funcs]
    _run_continuous_mode  CC=4  out:20
    execute_command_with_cleanup  CC=8  out:7
    handle_list_command  CC=7  out:21
    run_single_command  CC=1  out:2
    run_source  CC=2  out:3
  oqlos.tools.cql_cli.formatting  [2 funcs]
    canonicalize_oql_line  CC=14  out:31
    canonicalize_oql_text  CC=3  out:4
  oqlos.tools.cql_cli.main  [18 funcs]
    _create_interpreter  CC=1  out:1
    _dispatch_to_mode  CC=8  out:13
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
  oqlos.tools.hardware_diagnose.doctor  [39 funcs]
    _adapter_health_status  CC=3  out:1
    _add_issue  CC=2  out:1
    _analyze_firmware_access  CC=7  out:11
    _analyze_modbus_adc_config  CC=12  out:22
    _analyze_modbus_config  CC=11  out:20
    _analyze_serial_port_owners  CC=13  out:19
    _canonical_device_path  CC=2  out:3
    _check_firmware_adapters  CC=7  out:9
    _check_firmware_health_error  CC=3  out:2
    _check_firmware_mode  CC=3  out:4
  oqlos.tools.hardware_diagnose.health  [7 funcs]
    _format_health_value  CC=8  out:9
    _is_health_ok  CC=5  out:6
    _request_firmware_json  CC=8  out:9
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
  oqlos.tools.xml_import.generators  [15 funcs]
    _append_sensor_assertion  CC=6  out:3
    _build_steps_from_op  CC=10  out:14
    _build_validation_criteria  CC=14  out:3
    _emit_cql_output  CC=5  out:15
    _emit_cql_param  CC=7  out:5
    _emit_cql_sensor_param  CC=13  out:11
    _emit_dsl_param  CC=10  out:13
    _emit_dsl_sensors  CC=8  out:7
    _emit_set  CC=1  out:3
    _format_range  CC=9  out:0
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
  oqlos.core.oql_parser.parse_duration → oqlos.core.oql_parser.to_num
  oqlos.core.oql_parser.duration_to_ms → oqlos.core.oql_parser.parse_duration
  oqlos.core.oql_parser._split_value_unit → oqlos.core.oql_parser.to_num
  oqlos.core.oql_parser._split_set_value_unit → oqlos.core.oql_parser._split_value_unit
  oqlos.core.oql_parser.parse_SET → oqlos.core.oql_parser._require
  oqlos.core.oql_parser.parse_SET → oqlos.core.oql_parser._split_set_value_unit
  oqlos.core.oql_parser.parse_GET → oqlos.core.oql_parser._require
  oqlos.core.oql_parser.parse_WAIT → oqlos.core.oql_parser._require
  oqlos.core.oql_parser.parse_WAIT → oqlos.core.oql_parser.parse_duration
  oqlos.core.oql_parser.parse_WAIT → oqlos.core.oql_parser.duration_to_ms
  oqlos.core.oql_parser.parse_IF_DELTA → oqlos.core.oql_parser._require
  oqlos.core.oql_parser.parse_IF_DELTA → oqlos.core.oql_parser.to_num
  oqlos.core.oql_parser.parse_IF_DELTA → oqlos.core.oql_parser.duration_to_ms
  oqlos.core.oql_parser.parse_SAVE → oqlos.core.oql_parser._require
  oqlos.core.oql_parser.parse_CHECK → oqlos.core.oql_parser.to_num
  oqlos.core.oql_parser.parse_IF → oqlos.core.oql_parser.to_num
  oqlos.core.oql_parser.parse_MIN → oqlos.core.oql_parser._require
  oqlos.core.oql_parser.parse_MIN → oqlos.core.oql_parser._split_value_unit
  oqlos.core.oql_parser.parse_MAX → oqlos.core.oql_parser._require
  oqlos.core.oql_parser.parse_MAX → oqlos.core.oql_parser._split_value_unit
  oqlos.core.oql_parser.parse_SAMPLE → oqlos.core.oql_parser._require
  oqlos.core.oql_parser.parse_SAMPLE → oqlos.core.oql_parser.duration_to_ms
  oqlos.core.oql_parser.parse_CALL → oqlos.core.oql_parser._require
  oqlos.core.oql_parser.parse_INCLUDE → oqlos.core.oql_parser._require
  oqlos.core.oql_parser.parse_FUNC_CALL → oqlos.core.oql_parser._require
  oqlos.core.oql_parser._expand_repeat_block_lines → oqlos.core.oql_parser._line_indent
  oqlos.core.oql_parser._expand_repeat_blocks → oqlos.core.oql_parser._expand_repeat_block_lines
  oqlos.core.oql_parser._handle_top_level_line → oqlos.core.oql_parser.tokenize
```

### Code Analysis (`project/analysis.toon.yaml`)

```toon markpact:analysis path=project/analysis.toon.yaml
# code2llm | 190f 40737L | python:143,md:16,yaml:13,json:5,shell:5,yml:4,conf:2,toml:1 | 2026-06-30
# generated in 0.07s
# CC̅=4.2 | critical:11/1395 | dups:0 | cycles:0

HEALTH[11]:
  🟡 CC    migrate_v2_to_v4 CC=53 (limit:15)
  🟡 CC    enrich_adapter_entry CC=33 (limit:15)
  🟡 CC    _build_waveshare_diagnose_report CC=27 (limit:15)
  🟡 CC    build_diagnosis_report CC=25 (limit:15)
  🟡 CC    main CC=24 (limit:15)
  🟡 CC    _rewrite_legacy_if CC=20 (limit:15)
  🟡 CC    run_extended_motor_tic249_command CC=19 (limit:15)
  🟡 CC    adapter_status_from_health CC=17 (limit:15)
  🟡 CC    health_check CC=17 (limit:15)
  🟡 CC    _modbus_wizard_program_isolated CC=16 (limit:15)
  🟡 CC    _modbus_io_instance_ids CC=15 (limit:15)

REFACTOR[1]:
  1. split 11 high-CC methods  (CC>15)

PIPELINES[661]:
  [1] Src [main]: main → run_oql_scenario → print
      PURITY: 100% pure
  [2] Src [__init__]: __init__
      PURITY: 100% pure
  [3] Src [initialize_peripherals]: initialize_peripherals
      PURITY: 100% pure
  [4] Src [broadcast_event]: broadcast_event
      PURITY: 100% pure
  [5] Src [summary]: summary
      PURITY: 100% pure
  [6] Src [__init__]: __init__
      PURITY: 100% pure
  [7] Src [get]: get
      PURITY: 100% pure
  [8] Src [has]: has
      PURITY: 100% pure
  [9] Src [clear]: clear
      PURITY: 100% pure
  [10] Src [interpolate]: interpolate
      PURITY: 100% pure
  [11] Src [emit]: emit → print
      PURITY: 100% pure
  [12] Src [_broadcast_event]: _broadcast_event
      PURITY: 100% pure
  [13] Src [info]: info
      PURITY: 100% pure
  [14] Src [ok]: ok
      PURITY: 100% pure
  [15] Src [fail]: fail
      PURITY: 100% pure
  [16] Src [warn]: warn
      PURITY: 100% pure
  [17] Src [error]: error
      PURITY: 100% pure
  [18] Src [step]: step
      PURITY: 100% pure
  [19] Src [run]: run
      PURITY: 100% pure
  [20] Src [run_file]: run_file
      PURITY: 100% pure
  [21] Src [strip_comments]: strip_comments
      PURITY: 100% pure
  [22] Src [connect]: connect
      PURITY: 100% pure
  [23] Src [disconnect]: disconnect
      PURITY: 100% pure
  [24] Src [send_event]: send_event
      PURITY: 100% pure
  [25] Src [exec_action_task]: exec_action_task
      PURITY: 100% pure
  [26] Src [exec_action_log]: exec_action_log
      PURITY: 100% pure
  [27] Src [exec_action_error]: exec_action_error
      PURITY: 100% pure
  [28] Src [exec_action_else]: exec_action_else
      PURITY: 100% pure
  [29] Src [exec_action_sample]: exec_action_sample
      PURITY: 100% pure
  [30] Src [_func_avg]: _func_avg
      PURITY: 100% pure
  [31] Src [_func_sum]: _func_sum
      PURITY: 100% pure
  [32] Src [_func_min]: _func_min
      PURITY: 100% pure
  [33] Src [_func_max]: _func_max
      PURITY: 100% pure
  [34] Src [_func_sub]: _func_sub
      PURITY: 100% pure
  [35] Src [_func_div]: _func_div
      PURITY: 100% pure
  [36] Src [_func_add]: _func_add
      PURITY: 100% pure
  [37] Src [exec_action_func]: exec_action_func → _resolve_numeric_token
      PURITY: 100% pure
  [38] Src [exec_action_goto]: exec_action_goto
      PURITY: 100% pure
  [39] Src [exec_action_api]: exec_action_api → _mock_api_response
      PURITY: 100% pure
  [40] Src [exec_action_expect]: exec_action_expect → _drop_command_token → _extract_action_tokens
      PURITY: 100% pure
  [41] Src [_assert_status]: _assert_status → _record_failure
      PURITY: 100% pure
  [42] Src [_assert_json]: _assert_json → _get_nested_value
      PURITY: 100% pure
  [43] Src [_assert_sensor]: _assert_sensor → _record_failure
      PURITY: 100% pure
  [44] Src [_assert_valve]: _assert_valve → _lookup_peripheral_state
      PURITY: 100% pure
  [45] Src [exec_action_assert]: exec_action_assert → _drop_command_token → _extract_action_tokens
      PURITY: 100% pure
  [46] Src [exec_action_shell]: exec_action_shell → _drop_command_token → _extract_action_tokens
      PURITY: 100% pure
  [47] Src [exec_action_var_set]: exec_action_var_set
      PURITY: 100% pure
  [48] Src [exec_action_condition]: exec_action_condition
      PURITY: 100% pure
  [49] Src [exec_action_if_fail_block]: exec_action_if_fail_block
      PURITY: 100% pure
  [50] Src [exec_action_if_block]: exec_action_if_block
      PURITY: 100% pure

LAYERS:
  ./                              CC̄=6.9    ←in:0  →out:0
  │ !! openapi_spec.yaml         1035L  0C    0m  CC=0.0    ←0
  │ !! openapi.yaml              1035L  0C    0m  CC=0.0    ←0
  │ !! README.md                  641L  0C    0m  CC=0.0    ←0
  │ !! goal.yaml                  511L  0C    0m  CC=0.0    ←0
  │ CHANGELOG.md               496L  0C    0m  CC=0.0    ←0
  │ hw_diagnostic_20260415_133138.json   340L  0C    0m  CC=0.0    ←0
  │ setup_hardware_and_run_oql   333L  0C    7m  CC=12     ←0
  │ Taskfile.yml               160L  0C    0m  CC=0.0    ←0
  │ sumd.json                  150L  0C    0m  CC=0.0    ←0
  │ pyproject.toml              81L  0C    0m  CC=0.0    ←0
  │ pyqual.yaml                 49L  0C    0m  CC=0.0    ←0
  │ testql-contracts.testql.toon.yaml    49L  0C    0m  CC=0.0    ←0
  │ Taskfile.testql.yml         48L  0C    0m  CC=0.0    ←0
  │ project.sh                  43L  0C    0m  CC=0.0    ←0
  │ TODO.md                     36L  0C    0m  CC=0.0    ←0
  │
  scripts/                        CC̄=4.6    ←in:0  →out:70  !! split
  │ !! oql_v2_to_v4_migrate_db    627L  1C   19m  CC=53     ←1
  │ hardware-check.sh          340L  0C   11m  CC=0.0    ←0
  │ migrate_to_v4              340L  0C   19m  CC=11     ←0
  │ scenarios_export           296L  0C   13m  CC=8      ←0
  │ oql_v4_validator           281L  1C    8m  CC=8      ←1
  │ oql_v2_validator           224L  1C    6m  CC=9      ←0
  │ oql_validator_common       129L  0C    6m  CC=11     ←2
  │ oql-stack.sh               104L  0C    5m  CC=0.0    ←0
  │ fix_brackets_to_v4          95L  0C    2m  CC=14     ←0
  │
  oqlos/                          CC̄=4.2    ←in:8  →out:0
  │ !! hardware                  2165L  0C   83m  CC=27     ←2
  │ !! _interpreter_actions      1255L  0C   85m  CC=14     ←1
  │ !! doctor                    1003L  0C   41m  CC=13     ←2
  │ !! oql_parser                 762L  3C   43m  CC=14     ←2
  │ !! interpreter                676L  1C   47m  CC=11     ←0
  │ !! plugin_gateway             612L  1C   21m  CC=14     ←0
  │ !! tic249_extended            597L  0C   27m  CC=19     ←0
  │ !! diagnosis                  550L  3C   23m  CC=25     ←1
  │ !! motor                      543L  1C   18m  CC=17     ←0
  │ mqtt_oql_bridge            494L  6C   23m  CC=5      ←0
  │ firmware_adapter           481L  1C   26m  CC=12     ←0
  │ cql_parser                 477L  1C   30m  CC=8      ←2
  │ _oql_adapter               466L  1C   28m  CC=12     ←2
  │ proxy                      460L  1C   29m  CC=13     ←0
  │ generators                 452L  0C   20m  CC=14     ←0
  │ gateway                    416L  5C   18m  CC=7      ←0
  │ main                       412L  1C   18m  CC=9      ←2
  │ _cql_tokenizer             406L  0C   27m  CC=5      ←0
  │ modbus_adc                 398L  1C   17m  CC=12     ←0
  │ executor                   383L  1C   21m  CC=14     ←0
  │ base                       370L  9C   21m  CC=5      ←3
  │ state                      370L  0C   16m  CC=13     ←0
  │ execution                  359L  0C   16m  CC=11     ←0
  │ lung                       353L  1C   20m  CC=14     ←0
  │ plugin_cli                 343L  0C   14m  CC=8      ←3
  │ modbus                     335L  1C   16m  CC=11     ←0
  │ registry                   332L  1C   14m  CC=6      ←0
  │ preflight                  329L  0C   12m  CC=13     ←1
  │ base                       320L  7C   25m  CC=7      ←19
  │ main                       310L  0C   13m  CC=8      ←0
  │ schema                     296L  5C    6m  CC=7      ←0
  │ piadc                      272L  1C   12m  CC=11     ←0
  │ html_report                266L  0C    5m  CC=10     ←0
  │ scanner_probe              262L  0C   13m  CC=14     ←1
  │ !! identify_enrich            260L  0C   10m  CC=33     ←0
  │ scenarios                  251L  0C   16m  CC=11     ←0
  │ hui_actions                247L  0C   12m  CC=7      ←1
  │ _line_parsers              246L  0C    9m  CC=12     ←1
  │ sidecar_control            226L  0C    8m  CC=13     ←1
  │ config                     220L  1C    1m  CC=1      ←5
  │ _firmware_executor         210L  1C    9m  CC=11     ←0
  │ OQL-CHEATSHEET.md          210L  0C    0m  CC=0.0    ←0
  │ motor2_runtime             209L  2C   12m  CC=12     ←1
  │ modbus_probe               205L  0C   16m  CC=5      ←1
  │ rtc_probe                  197L  0C    7m  CC=11     ←1
  │ commands                   186L  0C    5m  CC=8      ←2
  │ usb_diagnostics            185L  0C    5m  CC=13     ←0
  │ __main__                   184L  0C   11m  CC=6      ←0
  │ manage_ops                 184L  0C    7m  CC=6      ←1
  │ parser                     183L  0C    5m  CC=13     ←2
  │ plugins                    181L  0C   12m  CC=3      ←2
  │ parser                     175L  0C    6m  CC=9      ←0
  │ event_server               171L  2C   10m  CC=7      ←0
  │ _cql_tree_builder          167L  0C    9m  CC=12     ←2
  │ modbus_repair              164L  0C    7m  CC=13     ←1
  │ artificial_lung            162L  0C   10m  CC=6      ←0
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
  │ _dsl_helpers               132L  0C   12m  CC=11     ←4
  │ modbus_identify            131L  0C    8m  CC=10     ←1
  │ resolvers                  128L  0C   10m  CC=10     ←1
  │ _value_normalizers         126L  1C    7m  CC=10     ←0
  │ release_version            125L  0C    7m  CC=11     ←1
  │ state                      124L  1C    3m  CC=4      ←0
  │ mqtt                       119L  1C    9m  CC=3      ←0
  │ health                     117L  0C    7m  CC=8      ←7
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
  │ stack_snapshot              88L  0C    4m  CC=8      ←1
  │ config                      88L  1C    5m  CC=6      ←1
  │ dsl_models                  87L  8C    0m  CC=0.0    ←0
  │ junit                       86L  1C    3m  CC=8      ←0
  │ discovery                   85L  0C    3m  CC=5      ←2
  │ config_factory              84L  0C    1m  CC=1      ←0
  │ event_store                 77L  1C   10m  CC=3      ←0
  │ __init__                    73L  0C    1m  CC=1      ←0
  │ sample_data                 73L  0C    1m  CC=1      ←1
  │ oql_versioning              72L  1C    4m  CC=4      ←1
  │ peripherals                 70L  0C    4m  CC=5      ←0
  │ constants                   69L  0C    0m  CC=0.0    ←0
  │ control_proxy               68L  1C    1m  CC=1      ←0
  │ version_endpoint            66L  0C    2m  CC=3      ←0
  │ tic249_arg_contract         65L  0C    2m  CC=8      ←0
  │ adc                         64L  0C    3m  CC=10     ←2
  │ report                      63L  0C    2m  CC=12     ←3
  │ formatting                  63L  0C    3m  CC=14     ←2
  │ execution_ctrl              62L  0C    3m  CC=1      ←0
  │ _shared                     61L  0C    4m  CC=2      ←3
  │ __init__                    60L  0C    2m  CC=1      ←0
  │ protocol                    60L  2C    6m  CC=1      ←0
  │ benchmark                   55L  0C    1m  CC=6      ←2
  │ platform                    50L  0C    3m  CC=6      ←0
  │ registry                    49L  1C    3m  CC=2      ←0
  │ __init__                    49L  0C    0m  CC=0.0    ←0
  │ hui_scenario                46L  0C    1m  CC=2      ←1
  │ logs                        45L  0C    3m  CC=1      ←0
  │ tic249_rig_direction        43L  0C    2m  CC=5      ←1
  │ config_paths                41L  0C    1m  CC=6      ←4
  │ _compare                    40L  0C    2m  CC=3      ←2
  │ scenario                    35L  4C    0m  CC=0.0    ←0
  │ _endpoint_helpers           34L  0C    2m  CC=2      ←1
  │ _rtu_serial                 33L  0C    2m  CC=4      ←2
  │ peripheral                  33L  4C    0m  CC=0.0    ←0
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
  │ __init__                     6L  0C    0m  CC=0.0    ←0
  │ tic249_units                 5L  0C    0m  CC=0.0    ←0
  │ __init__                     5L  0C    0m  CC=0.0    ←0
  │ __init__                     3L  0C    0m  CC=0.0    ←0
  │ __init__                     3L  0C    0m  CC=0.0    ←0
  │ __init__                     0L  0C    0m  CC=0.0    ←0
  │
  examples/                       CC̄=0.0    ←in:0  →out:0
  │ plugin-config.yaml         128L  0C    0m  CC=0.0    ←0
  │ curl-quickstart.sh          74L  0C    0m  CC=0.0    ←0
  │ doctor-workflow.sh          52L  0C    1m  CC=0.0    ←17
  │
  docs/                           CC̄=0.0    ←in:0  →out:0
  │ !! README.md                 1089L  0C    0m  CC=0.0    ←0
  │ !! cql-examples.md            588L  0C    0m  CC=0.0    ←0
  │ HARDWARE_DIAGNOSTICS.md    389L  0C    0m  CC=0.0    ←0
  │ HARDWARE_CONTROL_OQL_MQTT.md   281L  0C    0m  CC=0.0    ←0
  │ oql-spec.md                258L  0C    0m  CC=0.0    ←0
  │ OQL_V4_MIGRATION_MANUAL.md   216L  0C    0m  CC=0.0    ←0
  │ oql_v4_llm_validator.schema.json    93L  0C    0m  CC=0.0    ←0
  │ oql_v2_llm_validator.schema.json    89L  0C    0m  CC=0.0    ←0
  │ cql-spec.md                 78L  0C    0m  CC=0.0    ←0
  │
  redeploy/                       CC̄=0.0    ←in:0  →out:0
  │ !! migration.md               644L  0C    0m  CC=0.0    ←0
  │ !! migration.md               639L  0C    0m  CC=0.0    ←0
  │ RUNBOOK.md                  87L  0C    0m  CC=0.0    ←0
  │ RUNBOOK.md                  87L  0C    0m  CC=0.0    ←0
  │ oqlos-hw.yaml               66L  0C    0m  CC=0.0    ←0
  │ oqlos-hw.yaml               66L  0C    0m  CC=0.0    ←0
  │ mosquitto.conf              19L  0C    0m  CC=0.0    ←0
  │ mosquitto.conf              19L  0C    0m  CC=0.0    ←0
  │
  docker/                         CC̄=0.0    ←in:0  →out:0
  │ docker-compose.dev.yml      30L  0C    0m  CC=0.0    ←0
  │ docker-compose.prod.yml     20L  0C    0m  CC=0.0    ←0
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
                                       examples.hardware                 oqlos.tools                     scripts              oqlos.hardware                   oqlos.api                  oqlos.core  setup_hardware_and_run_oql                oqlos.shared                       oqlos                 oqlos.utils                   oqlos.dsl
           examples.hardware                          ──                        ←125                         ←65                                                                                  ←2                         ←27                          ←7                                                                                      hub
                 oqlos.tools                         125                          ──                          ←3                           6                                                      10                                                                                                                                              hub
                     scripts                          65                           3                          ──                           1                                                       1                                                                                                                                              !! fan-out
              oqlos.hardware                                                       3                          ←1                          ──                           1                           8                                                                                   3                                                          hub
                   oqlos.api                                                                                                              14                          ──                           8                                                       8                           1                           2                              !! fan-out
                  oqlos.core                           2                         ←10                          ←1                          ←8                          ←8                          ──                                                      ←1                           3                                                      ←1  hub
  setup_hardware_and_run_oql                          27                                                                                                                                                                      ──                                                                                                                  !! fan-out
                oqlos.shared                           7                                                                                                              ←8                           1                                                      ──                           1                                                          hub
                       oqlos                                                                                                              ←3                          ←1                          ←3                                                      ←1                          ──                                                          hub
                 oqlos.utils                                                                                                                                          ←2                                                                                                                                          ──                            
                   oqlos.dsl                                                                                                                                                                       1                                                                                                                                          ──
  CYCLES: none
  HUB: oqlos.tools/ (fan-in=6)
  HUB: oqlos/ (fan-in=8)
  HUB: oqlos.hardware/ (fan-in=21)
  HUB: examples.hardware/ (fan-in=226)
  HUB: oqlos.core/ (fan-in=29)
  HUB: oqlos.shared/ (fan-in=8)
  SMELL: oqlos.tools/ fan-out=141 → split needed
  SMELL: oqlos.api/ fan-out=33 → split needed
  SMELL: oqlos.hardware/ fan-out=15 → split needed
  SMELL: scripts/ fan-out=70 → split needed
  SMELL: setup_hardware_and_run_oql/ fan-out=27 → split needed
  SMELL: oqlos.shared/ fan-out=9 → split needed

EXTERNAL:
  validation: run `vallm batch .` → validation.toon
  duplication: run `redup scan .` → duplication.toon
```

### Duplication (`project/duplication.toon.yaml`)

```toon markpact:analysis path=project/duplication.toon.yaml
# redup/duplication | 67 groups | 149f 29992L | 2026-06-30

SUMMARY:
  files_scanned: 149
  total_lines:   29992
  dup_groups:    67
  dup_fragments: 147
  saved_lines:   486
  scan_ms:       90316

HOTSPOTS[7] (files with most duplication):
  oqlos/core/_cql_tokenizer.py  dup=92L  groups=7  frags=16  (0.3%)
  oqlos/hardware/plugins/motor.py  dup=81L  groups=2  frags=4  (0.3%)
  oqlos/api/hardware.py  dup=77L  groups=6  frags=11  (0.3%)
  oqlos/core/_interpreter_actions.py  dup=69L  groups=7  frags=15  (0.2%)
  oqlos/tools/hardware_diagnose/doctor.py  dup=68L  groups=3  frags=5  (0.2%)
  oqlos/core/interpreter.py  dup=41L  groups=5  frags=11  (0.1%)
  oqlos/core/oql_parser.py  dup=39L  groups=4  frags=11  (0.1%)

DUPLICATES[67] (ranked by impact):
  [7d4abed6d875568b]   STRU  _probe_modbus  L=19 N=2 saved=19 sim=1.00
      oqlos/tools/hardware_diagnose/doctor.py:73-91  (_probe_modbus)
      oqlos/tools/hardware_diagnose/doctor.py:94-112  (_probe_modbus_adc)
  [F0033]   FUZZ  _handle_stop_cli  L=21 N=2 saved=21 sim=0.88
      oqlos/hardware/plugins/motor.py:355-375  (_handle_stop_cli)
      oqlos/hardware/plugins/motor.py:272-294  (_handle_set_speed_cli)
  [F0016]   FUZZ  info  L=5 N=5 saved=20 sim=0.91
      oqlos/core/base.py:156-160  (info)
      oqlos/core/base.py:162-166  (ok)
      oqlos/core/base.py:168-172  (fail)
      oqlos/core/base.py:174-178  (warn)
      oqlos/core/base.py:180-184  (error)
  [F0032]   FUZZ  _health_status_is_ok  L=18 N=2 saved=18 sim=1.00
      oqlos/tools/hardware_diagnose/doctor.py:638-655  (_health_status_is_ok)
      oqlos/tools/cql_cli/preflight.py:187-205  (_health_status_is_ok)
  [F0030]   FUZZ  stop_lung  L=18 N=2 saved=18 sim=0.94
      oqlos/hardware/plugin_gateway.py:505-522  (stop_lung)
      oqlos/hardware/plugin_gateway.py:524-541  (disable_lung)
  [F0031]   FUZZ  _handle_stop_http  L=18 N=2 saved=18 sim=0.89
      oqlos/hardware/plugins/motor.py:336-353  (_handle_stop_http)
      oqlos/hardware/plugins/motor.py:407-425  (_handle_status_http)
  [F0029]   FUZZ  probe_waveshare_modbus  L=16 N=2 saved=16 sim=0.90
      oqlos/hardware/discovery.py:50-65  (probe_waveshare_modbus)
      oqlos/hardware/discovery.py:68-85  (probe_waveshare_modbus_adc)
  [c475266f1ca335a8]   STRU  _probe_modbus_rtu  L=12 N=2 saved=12 sim=1.00
      oqlos/api/hardware.py:382-393  (_probe_modbus_rtu)
      oqlos/api/hardware.py:396-407  (_probe_modbus_adc_rtu)
  [F0028]   FUZZ  _append_nested_action  L=12 N=2 saved=12 sim=0.99
      oqlos/core/cql_parser.py:247-258  (_append_nested_action)
      oqlos/core/cql_parser.py:260-271  (_append_loop_action)
  [F0026]   FUZZ  _exec_set_peripheral  L=11 N=2 saved=11 sim=0.94
      oqlos/core/interpreter.py:319-329  (_exec_set_peripheral)
      oqlos/core/_firmware_executor.py:197-210  (exec_set_peripheral)
  [F0027]   FUZZ  _http_sidecar_listening  L=11 N=2 saved=11 sim=0.92
      oqlos/hardware/sidecar_control.py:98-108  (_http_sidecar_listening)
      oqlos/hardware/sidecar_control.py:111-121  (_http_sidecar_healthy)
  [072bf17442930dfb]   STRU  _try_task  L=5 N=3 saved=10 sim=1.00
      oqlos/core/_cql_tokenizer.py:163-167  (_try_task)
      oqlos/core/_cql_tokenizer.py:242-246  (_try_if_fail_block)
      oqlos/core/_cql_tokenizer.py:368-372  (_try_save_ws)
  [7d75abe7ccc177ba]   STRU  _motor2_set_limit  L=5 N=3 saved=10 sim=1.00
      oqlos/core/_interpreter_actions.py:995-999  (_motor2_set_limit)
      oqlos/core/_interpreter_actions.py:1002-1006  (_motor2_set_stroke)
      oqlos/core/_interpreter_actions.py:1030-1034  (_motor2_set_cycles)
  [7b4466372835176e]   STRU  _motor2_set_cycle_volume  L=5 N=3 saved=10 sim=1.00
      oqlos/core/_interpreter_actions.py:1009-1013  (_motor2_set_cycle_volume)
      oqlos/core/_interpreter_actions.py:1016-1020  (_motor2_set_volume)
      oqlos/core/_interpreter_actions.py:1023-1027  (_motor2_set_duration)
  [72f2147f8d49b415]   STRU  parse_SET  L=5 N=3 saved=10 sim=1.00
      oqlos/core/oql_parser.py:247-251  (parse_SET)
      oqlos/core/oql_parser.py:349-353  (parse_MIN)
      oqlos/core/oql_parser.py:356-360  (parse_MAX)
  [d884e769a616fa58]   STRU  _merge_object_function_map  L=10 N=2 saved=10 sim=1.00
      oqlos/dsl/schema.py:99-108  (_merge_object_function_map)
      oqlos/dsl/schema.py:111-120  (_merge_param_unit_map)
  [F0025]   FUZZ  artificial_lung_command  L=11 N=2 saved=11 sim=0.86
      oqlos/api/hardware.py:2135-2145  (artificial_lung_command)
      oqlos/api/hardware.py:2155-2165  (rtc_command)
  [F0013]   FUZZ  _try_set  L=5 N=3 saved=10 sim=0.88
      oqlos/core/_cql_tokenizer.py:179-183  (_try_set)
      oqlos/core/_cql_tokenizer.py:282-286  (_try_val)
      oqlos/core/_cql_tokenizer.py:362-366  (_try_goto)
  [F0018]   FUZZ  read_channel  L=5 N=3 saved=10 sim=0.87
      oqlos/hardware/gateway.py:92-96  (read_channel)
      oqlos/hardware/gateway.py:125-129  (_stop)
      oqlos/hardware/gateway.py:165-169  (stop)
  [d355cbab0dee9921]   STRU  float_from_env  L=8 N=2 saved=8 sim=1.00
      oqlos/hardware/client/config.py:12-19  (float_from_env)
      oqlos/hardware/client/config.py:22-29  (int_from_env)
  [F0023]   FUZZ  _make_args_parser  L=8 N=2 saved=8 sim=0.91
      oqlos/core/_cql_tokenizer.py:97-104  (_make_args_parser)
      oqlos/core/_cql_tokenizer.py:116-123  (_make_method_parser)
  [46f8a3999370b808]   STRU  editor_page  L=7 N=2 saved=7 sim=1.00
      oqlos/api/main.py:210-216  (editor_page)
      oqlos/api/main.py:219-225  (panel_page)
  [09e0dc6f84cb5cfc]   STRU  not_connected_health  L=7 N=2 saved=7 sim=1.00
      oqlos/hardware/plugins/_shared.py:39-45  (not_connected_health)
      oqlos/hardware/plugins/_shared.py:48-54  (health_check_exception)
  [9467529f149d5e22]   STRU  _migrate_wait_line  L=7 N=2 saved=7 sim=1.00
      scripts/migrate_to_v4.py:115-121  (_migrate_wait_line)
      scripts/migrate_to_v4.py:139-145  (_migrate_save_line)
  [F0024]   FUZZ  _try_arrow_action  L=8 N=2 saved=8 sim=0.86
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
  [25c8d2950ffc3336]   STRU  _modbus_config  L=6 N=2 saved=6 sim=1.00
      oqlos/tools/hardware_diagnose/doctor.py:257-262  (_modbus_config)
      oqlos/tools/hardware_diagnose/doctor.py:265-270  (_modbus_adc_config)
  [F0022]   FUZZ  _handle_stop_http  L=6 N=2 saved=6 sim=0.97
      oqlos/hardware/plugins/lung.py:234-239  (_handle_stop_http)
      oqlos/hardware/plugins/lung.py:275-280  (_handle_status_http)
  [F0005]   FUZZ  _execute_firmware_action  L=3 N=3 saved=6 sim=0.93
      oqlos/core/interpreter.py:335-337  (_execute_firmware_action)
      oqlos/core/interpreter.py:339-341  (_execute_plugin_action)
      oqlos/core/interpreter.py:343-345  (_execute_legacy_firmware_action)
  [F0020]   FUZZ  hui_hold_start  L=6 N=2 saved=6 sim=0.91
      oqlos/api/hardware.py:1710-1715  (hui_hold_start)
      oqlos/api/hardware.py:1725-1730  (hui_al_start)
  [F0002]   FUZZ  _firmware  L=3 N=3 saved=6 sim=0.89
      oqlos/core/interpreter.py:94-96  (_firmware)
      oqlos/core/interpreter.py:104-106  (_firmware_url)
      oqlos/core/interpreter.py:331-333  (_get_firmware)
  [F0021]   FUZZ  _parse_motor2_steps  L=6 N=2 saved=6 sim=0.86
      oqlos/core/_interpreter_actions.py:890-895  (_parse_motor2_steps)
      oqlos/core/_interpreter_actions.py:774-781  (_parse_motor2_speed_steps)
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
  [F0019]   FUZZ  _read_address  L=5 N=2 saved=5 sim=0.90
      oqlos/hardware/plugins/modbus_adc.py:350-354  (_read_address)
      oqlos/hardware/plugins/modbus_adc.py:356-360  (_read_count)
  [F0017]   FUZZ  _handle_scenario_attrs  L=5 N=2 saved=5 sim=0.86
      oqlos/core/cql_parser.py:187-191  (_handle_scenario_attrs)
      oqlos/core/cql_parser.py:209-213  (_handle_goal_attrs)
  [F0014]   FUZZ  _try_repeat_start  L=5 N=2 saved=5 sim=0.86
      oqlos/core/_cql_tokenizer.py:310-314  (_try_repeat_start)
      oqlos/core/_cql_tokenizer.py:316-320  (_try_repeat_stop)
  [F0015]   FUZZ  _motor2_set_mode  L=5 N=2 saved=5 sim=0.85
      oqlos/core/_interpreter_actions.py:981-985  (_motor2_set_mode)
      oqlos/core/_interpreter_actions.py:988-992  (_motor2_set_limit_mode)
  [a7ee155dcd39e476]   EXAC  _health_map  L=4 N=2 saved=4 sim=1.00
      oqlos/hardware/client/autorepair.py:16-19  (_health_map)
      oqlos/hardware/diagnosis.py:69-72  (_health_map)
  [b7e062311606029c]   EXAC  to_json  L=4 N=2 saved=4 sim=1.00
      oqlos/hardware/transport/mqtt_oql_bridge.py:109-112  (to_json)
      oqlos/hardware/transport/mqtt_oql_bridge.py:141-144  (to_json)
  [e46400023b9f2fe9]   STRU  stop_lung  L=4 N=2 saved=4 sim=1.00
      oqlos/api/hardware.py:2115-2118  (stop_lung)
      oqlos/api/hardware.py:2122-2125  (disable_lung)
  [F0010]   FUZZ  __init__  L=4 N=2 saved=4 sim=0.91
      oqlos/hardware/plugins/modbus_adc.py:119-122  (__init__)
      oqlos/hardware/plugins/modbus.py:38-42  (__init__)
  [F0011]   FUZZ  __init__  L=4 N=2 saved=4 sim=0.86
      oqlos/hardware/plugins/piadc.py:103-106  (__init__)
      oqlos/hardware/plugins/lung.py:36-40  (__init__)
  [5d5dbdb19a59c8f4]   STRU  hui_shutdown  L=3 N=2 saved=3 sim=1.00
      oqlos/api/hardware.py:1704-1706  (hui_shutdown)
      oqlos/api/hardware.py:1734-1736  (hui_al_stop)
  [7e9c7774bc69259a]   STRU  _func_sum  L=3 N=2 saved=3 sim=1.00
      oqlos/core/_interpreter_actions.py:367-369  (_func_sum)
      oqlos/core/_interpreter_actions.py:408-410  (_func_add)
  [ed2293c21fed4e2d]   STRU  _func_min  L=3 N=2 saved=3 sim=1.00
      oqlos/core/_interpreter_actions.py:372-374  (_func_min)
      oqlos/core/_interpreter_actions.py:377-379  (_func_max)
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
      oqlos/core/_interpreter_actions.py:101-103  (_oql_quote)
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
      oqlos/hardware/plugins/lung.py:241-243  (_handle_stop_usb)
      oqlos/hardware/plugins/lung.py:282-284  (_handle_status_usb)
  [F0007]   FUZZ  connect  L=3 N=2 saved=3 sim=0.88
      oqlos/hardware/plugins/base.py:292-294  (connect)
      oqlos/hardware/plugins/base.py:297-299  (disconnect)
  [F0009]   FUZZ  get_plugin_class  L=3 N=2 saved=3 sim=0.86
      oqlos/hardware/plugins/registry.py:70-72  (get_plugin_class)
      oqlos/hardware/plugins/registry.py:120-122  (get_instance)

REFACTOR[67] (ranked by priority):
  [1] ○ extract_function   → oqlos/tools/hardware_diagnose/utils/_probe_modbus.py
      WHY: 2 occurrences of 19-line block across 1 files — saves 19 lines
      FILES: oqlos/tools/hardware_diagnose/doctor.py
  [2] ○ extract_class      → oqlos/hardware/plugins/utils/_handle_stop_cli.py
      WHY: 2 occurrences of 21-line block across 1 files — saves 21 lines
      FILES: oqlos/hardware/plugins/motor.py
  [3] ○ extract_class      → oqlos/core/utils/info.py
      WHY: 5 occurrences of 5-line block across 1 files — saves 20 lines
      FILES: oqlos/core/base.py
  [4] ○ extract_function   → oqlos/tools/utils/_health_status_is_ok.py
      WHY: 2 occurrences of 18-line block across 2 files — saves 18 lines
      FILES: oqlos/tools/cql_cli/preflight.py, oqlos/tools/hardware_diagnose/doctor.py
  [5] ○ extract_class      → oqlos/hardware/utils/stop_lung.py
      WHY: 2 occurrences of 18-line block across 1 files — saves 18 lines
      FILES: oqlos/hardware/plugin_gateway.py
  [6] ○ extract_class      → oqlos/hardware/plugins/utils/_handle_stop_http.py
      WHY: 2 occurrences of 18-line block across 1 files — saves 18 lines
      FILES: oqlos/hardware/plugins/motor.py
  [7] ○ extract_function   → oqlos/hardware/utils/probe_waveshare_modbus.py
      WHY: 2 occurrences of 16-line block across 1 files — saves 16 lines
      FILES: oqlos/hardware/discovery.py
  [8] ○ extract_function   → oqlos/api/utils/_probe_modbus_rtu.py
      WHY: 2 occurrences of 12-line block across 1 files — saves 12 lines
      FILES: oqlos/api/hardware.py
  [9] ○ extract_class      → oqlos/core/utils/_append_nested_action.py
      WHY: 2 occurrences of 12-line block across 1 files — saves 12 lines
      FILES: oqlos/core/cql_parser.py
  [10] ○ extract_function   → oqlos/core/utils/_exec_set_peripheral.py
      WHY: 2 occurrences of 11-line block across 2 files — saves 11 lines
      FILES: oqlos/core/_firmware_executor.py, oqlos/core/interpreter.py
  [11] ○ extract_function   → oqlos/hardware/utils/_http_sidecar_listening.py
      WHY: 2 occurrences of 11-line block across 1 files — saves 11 lines
      FILES: oqlos/hardware/sidecar_control.py
  [12] ○ extract_function   → oqlos/core/utils/_try_task.py
      WHY: 3 occurrences of 5-line block across 1 files — saves 10 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [13] ○ extract_function   → oqlos/core/utils/_motor2_set_limit.py
      WHY: 3 occurrences of 5-line block across 1 files — saves 10 lines
      FILES: oqlos/core/_interpreter_actions.py
  [14] ○ extract_function   → oqlos/core/utils/_motor2_set_cycle_volume.py
      WHY: 3 occurrences of 5-line block across 1 files — saves 10 lines
      FILES: oqlos/core/_interpreter_actions.py
  [15] ○ extract_function   → oqlos/core/utils/parse_SET.py
      WHY: 3 occurrences of 5-line block across 1 files — saves 10 lines
      FILES: oqlos/core/oql_parser.py
  [16] ○ extract_function   → oqlos/dsl/utils/_merge_object_function_map.py
      WHY: 2 occurrences of 10-line block across 1 files — saves 10 lines
      FILES: oqlos/dsl/schema.py
  [17] ○ extract_function   → oqlos/api/utils/artificial_lung_command.py
      WHY: 2 occurrences of 11-line block across 1 files — saves 11 lines
      FILES: oqlos/api/hardware.py
  [18] ○ extract_function   → oqlos/core/utils/_try_set.py
      WHY: 3 occurrences of 5-line block across 1 files — saves 10 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [19] ○ extract_function   → oqlos/hardware/utils/read_channel.py
      WHY: 3 occurrences of 5-line block across 1 files — saves 10 lines
      FILES: oqlos/hardware/gateway.py
  [20] ○ extract_function   → oqlos/hardware/client/utils/float_from_env.py
      WHY: 2 occurrences of 8-line block across 1 files — saves 8 lines
      FILES: oqlos/hardware/client/config.py
  [21] ○ extract_function   → oqlos/core/utils/_make_args_parser.py
      WHY: 2 occurrences of 8-line block across 1 files — saves 8 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [22] ○ extract_function   → oqlos/api/utils/editor_page.py
      WHY: 2 occurrences of 7-line block across 1 files — saves 7 lines
      FILES: oqlos/api/main.py
  [23] ○ extract_function   → oqlos/hardware/plugins/utils/not_connected_health.py
      WHY: 2 occurrences of 7-line block across 1 files — saves 7 lines
      FILES: oqlos/hardware/plugins/_shared.py
  [24] ○ extract_function   → scripts/utils/_migrate_wait_line.py
      WHY: 2 occurrences of 7-line block across 1 files — saves 7 lines
      FILES: scripts/migrate_to_v4.py
  [25] ○ extract_function   → oqlos/core/utils/_try_arrow_action.py
      WHY: 2 occurrences of 8-line block across 1 files — saves 8 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [26] ○ extract_function   → oqlos/hardware/utils/modbus_plugins_need_repair.py
      WHY: 2 occurrences of 6-line block across 2 files — saves 6 lines
      FILES: oqlos/hardware/client/autorepair.py, oqlos/hardware/diagnosis.py
  [27] ○ extract_function   → oqlos/core/utils/parse_GET.py
      WHY: 3 occurrences of 3-line block across 1 files — saves 6 lines
      FILES: oqlos/core/oql_parser.py
  [28] ○ extract_function   → oqlos/core/utils/parse_LOG.py
      WHY: 3 occurrences of 3-line block across 1 files — saves 6 lines
      FILES: oqlos/core/oql_parser.py
  [29] ○ extract_function   → oqlos/tools/hardware_diagnose/utils/_modbus_config.py
      WHY: 2 occurrences of 6-line block across 1 files — saves 6 lines
      FILES: oqlos/tools/hardware_diagnose/doctor.py
  [30] ○ extract_class      → oqlos/hardware/plugins/utils/_handle_stop_http.py
      WHY: 2 occurrences of 6-line block across 1 files — saves 6 lines
      FILES: oqlos/hardware/plugins/lung.py
  [31] ○ extract_class      → oqlos/core/utils/_execute_firmware_action.py
      WHY: 3 occurrences of 3-line block across 1 files — saves 6 lines
      FILES: oqlos/core/interpreter.py
  [32] ○ extract_function   → oqlos/api/utils/hui_hold_start.py
      WHY: 2 occurrences of 6-line block across 1 files — saves 6 lines
      FILES: oqlos/api/hardware.py
  [33] ○ extract_class      → oqlos/core/utils/_firmware.py
      WHY: 3 occurrences of 3-line block across 1 files — saves 6 lines
      FILES: oqlos/core/interpreter.py
  [34] ○ extract_function   → oqlos/core/utils/_parse_motor2_steps.py
      WHY: 2 occurrences of 6-line block across 1 files — saves 6 lines
      FILES: oqlos/core/_interpreter_actions.py
  [35] ○ extract_function   → oqlos/utils/_read_text_file.py
      WHY: 2 occurrences of 5-line block across 2 files — saves 5 lines
      FILES: oqlos/api/hardware.py, oqlos/hardware/plugins/piadc.py
  [36] ○ extract_function   → oqlos/hardware/utils/status.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/hardware/gateway.py
  [37] ○ extract_function   → oqlos/hardware/plugins/utils/_rtu_timeout.py
      WHY: 2 occurrences of 5-line block across 2 files — saves 5 lines
      FILES: oqlos/hardware/plugins/modbus.py, oqlos/hardware/plugins/modbus_adc.py
  [38] ○ extract_function   → oqlos/hardware/plugins/utils/_device_id.py
      WHY: 2 occurrences of 5-line block across 2 files — saves 5 lines
      FILES: oqlos/hardware/plugins/modbus.py, oqlos/hardware/plugins/modbus_adc.py
  [39] ○ extract_function   → oqlos/api/utils/get_execution.py
      WHY: 2 occurrences of 5-line block across 2 files — saves 5 lines
      FILES: oqlos/api/execution.py, oqlos/api/peripherals.py
  [40] ○ extract_function   → oqlos/core/utils/_try_var.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [41] ○ extract_function   → oqlos/hardware/plugins/utils/disconnect.py
      WHY: 2 occurrences of 5-line block across 2 files — saves 5 lines
      FILES: oqlos/hardware/plugins/lung.py, oqlos/hardware/plugins/piadc.py
  [42] ○ extract_function   → oqlos/hardware/utils/_match_blob.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/hardware/scanner_probe.py
  [43] ○ extract_function   → oqlos/core/utils/parser.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [44] ○ extract_class      → oqlos/hardware/plugins/utils/_read_address.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/hardware/plugins/modbus_adc.py
  [45] ○ extract_class      → oqlos/core/utils/_handle_scenario_attrs.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/core/cql_parser.py
  [46] ○ extract_function   → oqlos/core/utils/_try_repeat_start.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [47] ○ extract_function   → oqlos/core/utils/_motor2_set_mode.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/core/_interpreter_actions.py
  [48] ○ extract_function   → oqlos/hardware/utils/_health_map.py
      WHY: 2 occurrences of 4-line block across 2 files — saves 4 lines
      FILES: oqlos/hardware/client/autorepair.py, oqlos/hardware/diagnosis.py
  [49] ○ extract_function   → oqlos/hardware/transport/utils/to_json.py
      WHY: 2 occurrences of 4-line block across 1 files — saves 4 lines
      FILES: oqlos/hardware/transport/mqtt_oql_bridge.py
  [50] ○ extract_function   → oqlos/api/utils/stop_lung.py
      WHY: 2 occurrences of 4-line block across 1 files — saves 4 lines
      FILES: oqlos/api/hardware.py
  [51] ○ extract_function   → oqlos/hardware/plugins/utils/__init__.py
      WHY: 2 occurrences of 4-line block across 2 files — saves 4 lines
      FILES: oqlos/hardware/plugins/modbus.py, oqlos/hardware/plugins/modbus_adc.py
  [52] ○ extract_function   → oqlos/hardware/plugins/utils/__init__.py
      WHY: 2 occurrences of 4-line block across 2 files — saves 4 lines
      FILES: oqlos/hardware/plugins/lung.py, oqlos/hardware/plugins/piadc.py
  [53] ○ extract_function   → oqlos/api/utils/hui_shutdown.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/api/hardware.py
  [54] ○ extract_function   → oqlos/core/utils/_func_sum.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/core/_interpreter_actions.py
  [55] ○ extract_function   → oqlos/core/utils/_func_min.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/core/_interpreter_actions.py
  [56] ○ extract_function   → oqlos/core/utils/_lower_min.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/core/_oql_adapter.py
  [57] ○ extract_function   → oqlos/core/utils/_resolve_compare.py
      WHY: 2 occurrences of 3-line block across 2 files — saves 3 lines
      FILES: oqlos/core/executor.py, oqlos/core/safe_eval.py
  [58] ○ extract_function   → oqlos/core/utils/parse_CALL.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/core/oql_parser.py
  [59] ○ extract_function   → oqlos/tools/hardware_diagnose/utils/check_firmware_health.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/tools/hardware_diagnose/health.py
  [60] ○ extract_function   → oqlos/tools/hardware_diagnose/utils/_env_int.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/tools/hardware_diagnose/modbus_probe.py
  [61] ○ extract_function   → oqlos/utils/_oql_quote.py
      WHY: 2 occurrences of 3-line block across 2 files — saves 3 lines
      FILES: oqlos/core/_interpreter_actions.py, oqlos/tools/xml_import/generators.py
  [62] ○ extract_class      → oqlos/core/utils/_firmware.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/core/interpreter.py
  [63] ○ extract_class      → oqlos/core/utils/_normalize_valve_value.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/core/interpreter.py
  [64] ○ extract_function   → oqlos/hardware/utils/discover.py
      WHY: 2 occurrences of 3-line block across 2 files — saves 3 lines
      FILES: oqlos/hardware/drivers/mqtt.py, oqlos/hardware/protocol.py
  [65] ○ extract_class      → oqlos/hardware/plugins/utils/_handle_stop_usb.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/hardware/plugins/lung.py
  [66] ○ extract_class      → oqlos/hardware/plugins/utils/connect.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/hardware/plugins/base.py
  [67] ○ extract_class      → oqlos/hardware/plugins/utils/get_plugin_class.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/hardware/plugins/registry.py

QUICK_WINS[34] (low risk, high savings — do first):
  [2] extract_class      saved=21L  → oqlos/hardware/plugins/utils/_handle_stop_cli.py
      FILES: motor.py
  [3] extract_class      saved=20L  → oqlos/core/utils/info.py
      FILES: base.py
  [1] extract_function   saved=19L  → oqlos/tools/hardware_diagnose/utils/_probe_modbus.py
      FILES: doctor.py
  [4] extract_function   saved=18L  → oqlos/tools/utils/_health_status_is_ok.py
      FILES: preflight.py, doctor.py
  [5] extract_class      saved=18L  → oqlos/hardware/utils/stop_lung.py
      FILES: plugin_gateway.py
  [6] extract_class      saved=18L  → oqlos/hardware/plugins/utils/_handle_stop_http.py
      FILES: motor.py
  [7] extract_function   saved=16L  → oqlos/hardware/utils/probe_waveshare_modbus.py
      FILES: discovery.py
  [8] extract_function   saved=12L  → oqlos/api/utils/_probe_modbus_rtu.py
      FILES: hardware.py
  [9] extract_class      saved=12L  → oqlos/core/utils/_append_nested_action.py
      FILES: cql_parser.py
  [10] extract_function   saved=11L  → oqlos/core/utils/_exec_set_peripheral.py
      FILES: _firmware_executor.py, interpreter.py

EFFORT_ESTIMATE (total ≈ 16.2h):
  medium _probe_modbus                       saved=19L  ~38min
  medium _handle_stop_cli                    saved=21L  ~42min
  medium info                                saved=20L  ~40min
  medium _health_status_is_ok                saved=18L  ~36min
  medium stop_lung                           saved=18L  ~36min
  medium _handle_stop_http                   saved=18L  ~36min
  medium probe_waveshare_modbus              saved=16L  ~32min
  easy   _probe_modbus_rtu                   saved=12L  ~24min
  easy   _append_nested_action               saved=12L  ~24min
  easy   _exec_set_peripheral                saved=11L  ~22min
  ... +57 more (~642min)

METRICS-TARGET:
  dup_groups:  67 → 0
  saved_lines: 486 lines recoverable
```

### Evolution / Churn (`project/evolution.toon.yaml`)

```toon markpact:analysis path=project/evolution.toon.yaml
# code2llm/evolution | 1305 func | 116f | 2026-06-30
# generated in 0.00s

NEXT[9] (ranked by impact):
  [1] !! SPLIT           oqlos/api/hardware.py
      WHY: 2165L, 0 classes, max CC=27
      EFFORT: ~4h  IMPACT: 58455

  [2] !! SPLIT           oqlos/core/_interpreter_actions.py
      WHY: 1255L, 0 classes, max CC=14
      EFFORT: ~4h  IMPACT: 17570

  [3] !! SPLIT-FUNC      build_diagnosis_report  CC=25  fan=25
      WHY: CC=25 exceeds 15
      EFFORT: ~1h  IMPACT: 625

  [4] !! SPLIT-FUNC      _build_waveshare_diagnose_report  CC=27  fan=23
      WHY: CC=27 exceeds 15
      EFFORT: ~1h  IMPACT: 621

  [5] !! SPLIT-FUNC      enrich_adapter_entry  CC=33  fan=13
      WHY: CC=33 exceeds 15
      EFFORT: ~1h  IMPACT: 429

  [6] !  SPLIT-FUNC      run_extended_motor_tic249_command  CC=19  fan=18
      WHY: CC=19 exceeds 15
      EFFORT: ~1h  IMPACT: 342

  [7] !  SPLIT-FUNC      _modbus_wizard_program_isolated  CC=16  fan=14
      WHY: CC=16 exceeds 15
      EFFORT: ~1h  IMPACT: 224

  [8] !  SPLIT-FUNC      MotorPlugin.health_check  CC=17  fan=13
      WHY: CC=17 exceeds 15
      EFFORT: ~1h  IMPACT: 221

  [9] !! SPLIT           docs/README.md
      WHY: 1089L, 0 classes, max CC=0
      EFFORT: ~4h  IMPACT: 0


RISKS[3]:
  ⚠ Splitting oqlos/api/hardware.py may break 83 import paths
  ⚠ Splitting oqlos/core/_interpreter_actions.py may break 85 import paths
  ⚠ Splitting docs/README.md may break 0 import paths

METRICS-TARGET:
  CC̄:          4.2 → ≤2.9
  max-CC:      33 → ≤16
  god-modules: 17 → 0
  high-CC(≥15): 8 → ≤4
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
  prev CC̄=4.2 → now CC̄=4.2
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
