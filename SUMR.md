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
- **version**: `0.1.13`
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

### Code Analysis (`project/analysis.toon.yaml`)

```toon markpact:analysis path=project/analysis.toon.yaml
# code2llm | 142f 28558L | python:107,md:11,yaml:10,json:5,yml:4,shell:3,toml:1 | 2026-05-06
# generated in 0.04s
# CC̄=4.1 | critical:21/981 | dups:0 | cycles:0

HEALTH[20]:
  🟡 CC    parse_oql CC=49 (limit:15)
  🟡 CC    _cmd_to_actions CC=37 (limit:15)
  🟡 CC    _evaluate_condition CC=17 (limit:15)
  🟡 CC    _analyze_firmware_access CC=25 (limit:15)
  🟡 CC    format_detection CC=16 (limit:15)
  🟡 CC    format_doctor CC=20 (limit:15)
  🟡 CC    main CC=19 (limit:15)
  🟡 CC    run_modbus_probe CC=16 (limit:15)
  🟡 CC    _raise_if_rejected CC=19 (limit:15)
  🟡 CC    validate_config CC=15 (limit:15)
  🟡 CC    health_check CC=15 (limit:15)
  🟡 CC    report_json CC=16 (limit:15)
  🟡 CC    _detect_runtime_platform CC=18 (limit:15)
  🟡 CC    hardware_identify CC=24 (limit:15)
  🟡 CC    _validate_structure CC=20 (limit:15)
  🟡 CC    _validate_v2_structure CC=16 (limit:15)
  🟡 CC    migrate_content CC=19 (limit:15)
  🟡 CC    main CC=21 (limit:15)
  🟡 CC    _rewrite_legacy_if CC=20 (limit:15)
  🟡 CC    migrate_v2_to_v4 CC=55 (limit:15)

REFACTOR[1]:
  1. split 20 high-CC methods  (CC>15)

PIPELINES[521]:
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

LAYERS:
  ./                              CC̄=6.9    ←in:0  →out:0
  │ !! openapi.yaml              1035L  0C    0m  CC=0.0    ←0
  │ !! README.md                  583L  0C    0m  CC=0.0    ←0
  │ !! goal.yaml                  511L  0C    0m  CC=0.0    ←0
  │ hw_diagnostic_20260415_133138.json   340L  0C    0m  CC=0.0    ←0
  │ setup_hardware_and_run_oql   333L  0C    7m  CC=12     ←0
  │ CHANGELOG.md               240L  0C    0m  CC=0.0    ←0
  │ Taskfile.yml               160L  0C    0m  CC=0.0    ←0
  │ sumd.json                  150L  0C    0m  CC=0.0    ←0
  │ pyproject.toml              80L  0C    0m  CC=0.0    ←0
  │ pyqual.yaml                 49L  0C    0m  CC=0.0    ←0
  │ testql-contracts.testql.toon.yaml    49L  0C    0m  CC=0.0    ←0
  │ Taskfile.testql.yml         48L  0C    0m  CC=0.0    ←0
  │ project.sh                  43L  0C    0m  CC=0.0    ←0
  │ TODO.md                     36L  0C    0m  CC=0.0    ←0
  │
  scripts/                        CC̄=6.1    ←in:0  →out:70  !! split
  │ !! oql_v2_to_v4_migrate_db    628L  1C   17m  CC=55     ←1
  │ !! oql_v4_validator           362L  1C   10m  CC=20     ←1
  │ !! migrate_to_v4              341L  0C    6m  CC=21     ←0
  │ hardware-check.sh          340L  0C   11m  CC=0.0    ←0
  │ !! oql_v2_validator           316L  1C    9m  CC=16     ←0
  │ scenarios_export           296L  0C   13m  CC=8      ←0
  │ fix_brackets_to_v4          95L  0C    2m  CC=14     ←0
  │
  oqlos/                          CC̄=4.0    ←in:3  →out:0
  │ !! _interpreter_actions       771L  0C   48m  CC=13     ←1
  │ !! doctor                     764L  0C   27m  CC=25     ←2
  │ !! oql_parser                 666L  3C   31m  CC=49     ←2
  │ !! interpreter                665L  1C   46m  CC=17     ←0
  │ !! hardware                   615L  0C   31m  CC=24     ←1
  │ !! control_proxy              528L  3C   31m  CC=9      ←0
  │ !! _oql_adapter               489L  1C   14m  CC=37     ←2
  │ cql_parser                 477L  1C   30m  CC=8      ←2
  │ !! firmware_adapter           467L  1C   24m  CC=19     ←0
  │ generators                 442L  0C   18m  CC=14     ←0
  │ gateway                    415L  5C   25m  CC=7      ←0
  │ _cql_tokenizer             403L  0C   27m  CC=5      ←0
  │ motor                      396L  1C   18m  CC=14     ←0
  │ main                       384L  1C   16m  CC=9      ←0
  │ executor                   383L  1C   21m  CC=14     ←0
  │ plugin_gateway             371L  1C   15m  CC=13     ←0
  │ base                       370L  9C   21m  CC=5      ←2
  │ state                      370L  0C   16m  CC=13     ←0
  │ execution                  354L  0C   16m  CC=11     ←0
  │ plugin_cli                 343L  0C   14m  CC=8      ←3
  │ !! lung                       337L  1C   19m  CC=15     ←0
  │ registry                   332L  1C   14m  CC=6      ←0
  │ preflight                  328L  0C   12m  CC=13     ←1
  │ base                       320L  7C   28m  CC=7      ←16
  │ !! modbus                     301L  1C    9m  CC=15     ←0
  │ schema                     296L  5C    6m  CC=7      ←0
  │ piadc                      272L  1C   12m  CC=11     ←0
  │ html_report                266L  0C    5m  CC=10     ←0
  │ !! modbus_probe               259L  0C   16m  CC=16     ←1
  │ scenarios                  251L  0C   16m  CC=11     ←0
  │ _line_parsers              246L  0C    9m  CC=12     ←1
  │ discovery                  232L  0C    8m  CC=12     ←3
  │ main                       223L  0C    9m  CC=7      ←0
  │ OQL-CHEATSHEET.md          210L  0C    0m  CC=0.0    ←0
  │ _firmware_executor         201L  1C    9m  CC=11     ←0
  │ parser                     183L  0C    5m  CC=13     ←2
  │ commands                   178L  0C    5m  CC=8      ←1
  │ parser                     175L  0C    6m  CC=9      ←0
  │ event_server               171L  2C   11m  CC=7      ←0
  │ !! __main__                   168L  0C    8m  CC=19     ←0
  │ _cql_tree_builder          161L  0C    9m  CC=9      ←2
  │ utils                      149L  0C   10m  CC=8      ←3
  │ _sensor_evaluator          145L  1C    6m  CC=10     ←0
  │ config_schema              145L  1C    4m  CC=2      ←0
  │ logs_query                 145L  1C    5m  CC=11     ←1
  │ plugins                    144L  0C    9m  CC=3      ←1
  │ README.md                  140L  0C    0m  CC=0.0    ←0
  │ safe_eval                  138L  1C   10m  CC=4      ←0
  │ shell                      138L  0C    5m  CC=6      ←1
  │ peripheral_mapping         138L  0C    4m  CC=2      ←0
  │ _dsl_helpers               132L  0C   12m  CC=11     ←4
  │ !! json_reporter              130L  0C    2m  CC=16     ←0
  │ _value_normalizers         126L  1C    7m  CC=8      ←0
  │ editor                     126L  3C    5m  CC=5      ←0
  │ release_version            125L  0C    7m  CC=11     ←1
  │ state                      124L  1C    3m  CC=4      ←0
  │ mqtt                       119L  1C    9m  CC=3      ←0
  │ config                     115L  1C    1m  CC=1      ←2
  │ health                     108L  0C    7m  CC=8      ←7
  │ file_ops                   108L  1C    5m  CC=4      ←1
  │ _utils                     101L  0C    6m  CC=12     ←1
  │ discovery                   99L  1C    5m  CC=8      ←5
  │ _func_resolver              96L  0C    4m  CC=13     ←1
  │ calibration                 92L  0C    4m  CC=5      ←3
  │ spi                         92L  1C    7m  CC=4      ←0
  │ models                      90L  5C    0m  CC=0.0    ←0
  │ gpio                        89L  1C    7m  CC=6      ←0
  │ dsl_models                  87L  8C    0m  CC=0.0    ←0
  │ junit                       86L  1C    3m  CC=8      ←0
  │ config_factory              84L  0C    1m  CC=1      ←0
  │ event_store                 77L  1C   10m  CC=3      ←0
  │ __init__                    73L  0C    1m  CC=1      ←0
  │ sample_data                 73L  0C    1m  CC=1      ←1
  │ oql_versioning              72L  1C    4m  CC=4      ←1
  │ peripherals                 70L  0C    4m  CC=5      ←0
  │ version_endpoint            66L  0C    2m  CC=3      ←0
  │ report                      63L  0C    2m  CC=12     ←3
  │ execution_ctrl              62L  0C    3m  CC=1      ←0
  │ _shared                     61L  0C    4m  CC=2      ←3
  │ __init__                    60L  0C    2m  CC=1      ←0
  │ protocol                    60L  2C    6m  CC=1      ←0
  │ benchmark                   55L  0C    1m  CC=6      ←2
  │ registry                    49L  1C    3m  CC=2      ←0
  │ __init__                    47L  0C    0m  CC=0.0    ←0
  │ logs                        45L  0C    3m  CC=1      ←0
  │ config_paths                41L  0C    1m  CC=6      ←4
  │ _compare                    40L  0C    2m  CC=3      ←2
  │ scenario                    35L  4C    0m  CC=0.0    ←0
  │ _endpoint_helpers           34L  0C    2m  CC=2      ←1
  │ peripheral                  33L  4C    0m  CC=0.0    ←0
  │ version                     24L  0C    0m  CC=0.0    ←0
  │ logger                      23L  0C    1m  CC=2      ←0
  │ execution                   22L  3C    0m  CC=0.0    ←0
  │ __init__                    19L  0C    0m  CC=0.0    ←0
  │ __init__                    17L  0C    0m  CC=0.0    ←0
  │ __init__                    17L  0C    0m  CC=0.0    ←0
  │ __init__                    17L  0C    0m  CC=0.0    ←0
  │ __init__                     6L  0C    0m  CC=0.0    ←0
  │ __init__                     5L  0C    0m  CC=0.0    ←0
  │ __init__                     3L  0C    0m  CC=0.0    ←0
  │ __init__                     3L  0C    0m  CC=0.0    ←0
  │ __init__                     0L  0C    0m  CC=0.0    ←0
  │
  examples/                       CC̄=0.0    ←in:0  →out:0
  │ plugin-config.yaml         128L  0C    0m  CC=0.0    ←0
  │ doctor-workflow.sh          52L  0C    1m  CC=0.0    ←18
  │
  docs/                           CC̄=0.0    ←in:0  →out:0
  │ !! README.md                  815L  0C    0m  CC=0.0    ←0
  │ !! cql-examples.md            588L  0C    0m  CC=0.0    ←0
  │ HARDWARE_DIAGNOSTICS.md    389L  0C    0m  CC=0.0    ←0
  │ oql-spec.md                258L  0C    0m  CC=0.0    ←0
  │ OQL_V4_MIGRATION_MANUAL.md   216L  0C    0m  CC=0.0    ←0
  │ oql_v4_llm_validator.schema.json    93L  0C    0m  CC=0.0    ←0
  │ oql_v2_llm_validator.schema.json    89L  0C    0m  CC=0.0    ←0
  │ cql-spec.md                 78L  0C    0m  CC=0.0    ←0
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
                                       examples.hardware                 oqlos.tools                     scripts  setup_hardware_and_run_oql                  oqlos.core                oqlos.shared                   oqlos.api              oqlos.hardware                       oqlos                   oqlos.dsl                 oqlos.utils
           examples.hardware                          ──                        ←124                         ←68                         ←27                          ←2                          ←7                                                                                                                                              hub
                 oqlos.tools                         124                          ──                                                                                  10                                                                                   4                                                                                      !! fan-out
                     scripts                          68                                                      ──                                                       2                                                                                                                                                                          !! fan-out
  setup_hardware_and_run_oql                          27                                                                                  ──                                                                                                                                                                                                      !! fan-out
                  oqlos.core                           2                         ←10                          ←2                                                      ──                          ←1                          ←3                          ←2                                                      ←1                              hub
                oqlos.shared                           7                                                                                                               1                          ──                          ←7                                                                                                                  hub
                   oqlos.api                                                                                                                                           3                           7                          ──                           3                                                                                   1  !! fan-out
              oqlos.hardware                                                      ←4                                                                                   2                                                      ←3                          ──                           3                                                          hub
                       oqlos                                                                                                                                                                                                                              ←3                          ──                                                        
                   oqlos.dsl                                                                                                                                           1                                                                                                                                          ──                            
                 oqlos.utils                                                                                                                                                                                                  ←1                                                                                                              ──
  CYCLES: none
  HUB: oqlos.shared/ (fan-in=7)
  HUB: oqlos.core/ (fan-in=19)
  HUB: oqlos.hardware/ (fan-in=7)
  HUB: examples.hardware/ (fan-in=228)
  SMELL: oqlos.shared/ fan-out=8 → split needed
  SMELL: setup_hardware_and_run_oql/ fan-out=27 → split needed
  SMELL: oqlos.api/ fan-out=14 → split needed
  SMELL: oqlos.tools/ fan-out=138 → split needed
  SMELL: scripts/ fan-out=70 → split needed

EXTERNAL:
  validation: run `vallm batch .` → validation.toon
  duplication: run `redup scan .` → duplication.toon
```

### Duplication (`project/duplication.toon.yaml`)

```toon markpact:analysis path=project/duplication.toon.yaml
# redup/duplication | 24 groups | 114f 21580L | 2026-05-06

SUMMARY:
  files_scanned: 114
  total_lines:   21580
  dup_groups:    24
  dup_fragments: 53
  saved_lines:   205
  scan_ms:       5327

HOTSPOTS[7] (files with most duplication):
  scripts/oql_v4_validator.py  dup=105L  groups=6  frags=6  (0.5%)
  scripts/oql_v2_validator.py  dup=104L  groups=6  frags=6  (0.5%)
  oqlos/core/oql_parser.py  dup=39L  groups=4  frags=11  (0.2%)
  oqlos/core/_cql_tokenizer.py  dup=25L  groups=2  frags=5  (0.1%)
  oqlos/dsl/schema.py  dup=20L  groups=1  frags=2  (0.1%)
  oqlos/hardware/plugins/_shared.py  dup=14L  groups=1  frags=2  (0.1%)
  oqlos/api/hardware.py  dup=13L  groups=2  frags=3  (0.1%)

DUPLICATES[24] (ranked by impact):
  [38f02069ea7900c5]   EXAC  _extract_code_from_json  L=23 N=2 saved=23 sim=1.00
      scripts/oql_v2_validator.py:44-66  (_extract_code_from_json)
      scripts/oql_v4_validator.py:47-69  (_extract_code_from_json)
  [afdde28445d6d6b4]   EXAC  _load_source  L=23 N=2 saved=23 sim=1.00
      scripts/oql_v2_validator.py:93-115  (_load_source)
      scripts/oql_v4_validator.py:97-119  (_load_source)
  [d6c31178d5aba62b]   EXAC  _build_api_fallback_urls  L=22 N=2 saved=22 sim=1.00
      scripts/oql_v2_validator.py:69-90  (_build_api_fallback_urls)
      scripts/oql_v4_validator.py:72-94  (_build_api_fallback_urls)
  [cfdd91c38cd306d0]   STRU  main  L=20 N=2 saved=20 sim=1.00
      scripts/oql_v2_validator.py:293-312  (main)
      scripts/oql_v4_validator.py:339-358  (main)
  [853a7ea03d2afa3c]   EXAC  _fetch_url  L=13 N=2 saved=13 sim=1.00
      scripts/oql_v2_validator.py:29-41  (_fetch_url)
      scripts/oql_v4_validator.py:32-44  (_fetch_url)
  [cec388e17126d04a]   STRU  _try_task  L=5 N=3 saved=10 sim=1.00
      oqlos/core/_cql_tokenizer.py:160-164  (_try_task)
      oqlos/core/_cql_tokenizer.py:239-243  (_try_if_fail_block)
      oqlos/core/_cql_tokenizer.py:365-369  (_try_save_ws)
  [e904202e73f30c8e]   STRU  parse_SET  L=5 N=3 saved=10 sim=1.00
      oqlos/core/oql_parser.py:240-244  (parse_SET)
      oqlos/core/oql_parser.py:342-346  (parse_MIN)
      oqlos/core/oql_parser.py:349-353  (parse_MAX)
  [d884e769a616fa58]   STRU  _merge_object_function_map  L=10 N=2 saved=10 sim=1.00
      oqlos/dsl/schema.py:99-108  (_merge_object_function_map)
      oqlos/dsl/schema.py:111-120  (_merge_param_unit_map)
  [43e47beaf70d4a45]   STRU  disconnect  L=5 N=3 saved=10 sim=1.00
      oqlos/hardware/plugins/lung.py:83-87  (disconnect)
      oqlos/hardware/plugins/motor.py:109-113  (disconnect)
      oqlos/hardware/plugins/piadc.py:141-145  (disconnect)
  [8b32652353801ed5]   STRU  not_connected_health  L=7 N=2 saved=7 sim=1.00
      oqlos/hardware/plugins/_shared.py:39-45  (not_connected_health)
      oqlos/hardware/plugins/_shared.py:48-54  (health_check_exception)
  [f2e79a21a9cb963b]   STRU  parse_GET  L=3 N=3 saved=6 sim=1.00
      oqlos/core/oql_parser.py:247-249  (parse_GET)
      oqlos/core/oql_parser.py:299-301  (parse_SAVE)
      oqlos/core/oql_parser.py:395-397  (parse_INCLUDE)
  [e38bd975e24c0e35]   STRU  parse_LOG  L=3 N=3 saved=6 sim=1.00
      oqlos/core/oql_parser.py:375-377  (parse_LOG)
      oqlos/core/oql_parser.py:380-382  (parse_ERROR)
      oqlos/core/oql_parser.py:385-387  (parse_CORRECT)
  [ced4a13b5d82a294]   EXAC  _read_text_file  L=5 N=2 saved=5 sim=1.00
      oqlos/api/hardware.py:77-81  (_read_text_file)
      oqlos/hardware/plugins/piadc.py:46-50  (_read_text_file)
  [c7eda7834116d40a]   EXAC  status  L=5 N=2 saved=5 sim=1.00
      oqlos/hardware/gateway.py:130-134  (status)
      oqlos/hardware/gateway.py:186-190  (status)
  [0620456dd3154e5e]   STRU  get_execution  L=5 N=2 saved=5 sim=1.00
      oqlos/api/execution.py:194-198  (get_execution)
      oqlos/api/peripherals.py:18-22  (get_peripheral)
  [b13c2884a460682f]   STRU  _try_var  L=5 N=2 saved=5 sim=1.00
      oqlos/core/_cql_tokenizer.py:319-323  (_try_var)
      oqlos/core/_cql_tokenizer.py:349-353  (_try_api)
  [9971ed85b248c028]   STRU  stop_lung  L=4 N=2 saved=4 sim=1.00
      oqlos/api/hardware.py:605-608  (stop_lung)
      oqlos/api/hardware.py:612-615  (disable_lung)
  [16bcc3fe9b37ffa3]   EXAC  _looks_like_html  L=3 N=2 saved=3 sim=1.00
      scripts/oql_v2_validator.py:24-26  (_looks_like_html)
      scripts/oql_v4_validator.py:27-29  (_looks_like_html)
  [ad79a9de6949934f]   STRU  _func_sum  L=3 N=2 saved=3 sim=1.00
      oqlos/core/_interpreter_actions.py:347-349  (_func_sum)
      oqlos/core/_interpreter_actions.py:388-390  (_func_add)
  [15bf0901916bbc4e]   STRU  _func_min  L=3 N=2 saved=3 sim=1.00
      oqlos/core/_interpreter_actions.py:352-354  (_func_min)
      oqlos/core/_interpreter_actions.py:357-359  (_func_max)
  [697b748fa91d3f41]   STRU  _resolve_compare  L=3 N=2 saved=3 sim=1.00
      oqlos/core/executor.py:11-13  (_resolve_compare)
      oqlos/core/safe_eval.py:90-92  (_eval_compare)
  [9332a01903afbac2]   STRU  parse_CALL  L=3 N=2 saved=3 sim=1.00
      oqlos/core/oql_parser.py:390-392  (parse_CALL)
      oqlos/core/oql_parser.py:400-402  (parse_FUNC_CALL)
  [a17e1e3392ea6e68]   STRU  check_firmware_health  L=3 N=2 saved=3 sim=1.00
      oqlos/tools/hardware_diagnose/health.py:21-23  (check_firmware_health)
      oqlos/tools/hardware_diagnose/health.py:26-28  (check_firmware_identify)
  [2d86fcaf9ce3978c]   STRU  _env_int  L=3 N=2 saved=3 sim=1.00
      oqlos/tools/hardware_diagnose/modbus_probe.py:23-25  (_env_int)
      oqlos/tools/hardware_diagnose/modbus_probe.py:53-55  (_env_float)

REFACTOR[24] (ranked by priority):
  [1] ○ extract_function   → scripts/utils/_extract_code_from_json.py
      WHY: 2 occurrences of 23-line block across 2 files — saves 23 lines
      FILES: scripts/oql_v2_validator.py, scripts/oql_v4_validator.py
  [2] ○ extract_function   → scripts/utils/_load_source.py
      WHY: 2 occurrences of 23-line block across 2 files — saves 23 lines
      FILES: scripts/oql_v2_validator.py, scripts/oql_v4_validator.py
  [3] ○ extract_function   → scripts/utils/_build_api_fallback_urls.py
      WHY: 2 occurrences of 22-line block across 2 files — saves 22 lines
      FILES: scripts/oql_v2_validator.py, scripts/oql_v4_validator.py
  [4] ○ extract_function   → scripts/utils/main.py
      WHY: 2 occurrences of 20-line block across 2 files — saves 20 lines
      FILES: scripts/oql_v2_validator.py, scripts/oql_v4_validator.py
  [5] ○ extract_function   → scripts/utils/_fetch_url.py
      WHY: 2 occurrences of 13-line block across 2 files — saves 13 lines
      FILES: scripts/oql_v2_validator.py, scripts/oql_v4_validator.py
  [6] ○ extract_function   → oqlos/core/utils/_try_task.py
      WHY: 3 occurrences of 5-line block across 1 files — saves 10 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [7] ○ extract_function   → oqlos/core/utils/parse_SET.py
      WHY: 3 occurrences of 5-line block across 1 files — saves 10 lines
      FILES: oqlos/core/oql_parser.py
  [8] ○ extract_function   → oqlos/dsl/utils/_merge_object_function_map.py
      WHY: 2 occurrences of 10-line block across 1 files — saves 10 lines
      FILES: oqlos/dsl/schema.py
  [9] ○ extract_function   → oqlos/hardware/plugins/utils/disconnect.py
      WHY: 3 occurrences of 5-line block across 3 files — saves 10 lines
      FILES: oqlos/hardware/plugins/lung.py, oqlos/hardware/plugins/motor.py, oqlos/hardware/plugins/piadc.py
  [10] ○ extract_function   → oqlos/hardware/plugins/utils/not_connected_health.py
      WHY: 2 occurrences of 7-line block across 1 files — saves 7 lines
      FILES: oqlos/hardware/plugins/_shared.py
  [11] ○ extract_function   → oqlos/core/utils/parse_GET.py
      WHY: 3 occurrences of 3-line block across 1 files — saves 6 lines
      FILES: oqlos/core/oql_parser.py
  [12] ○ extract_function   → oqlos/core/utils/parse_LOG.py
      WHY: 3 occurrences of 3-line block across 1 files — saves 6 lines
      FILES: oqlos/core/oql_parser.py
  [13] ○ extract_function   → oqlos/utils/_read_text_file.py
      WHY: 2 occurrences of 5-line block across 2 files — saves 5 lines
      FILES: oqlos/api/hardware.py, oqlos/hardware/plugins/piadc.py
  [14] ○ extract_function   → oqlos/hardware/utils/status.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/hardware/gateway.py
  [15] ○ extract_function   → oqlos/api/utils/get_execution.py
      WHY: 2 occurrences of 5-line block across 2 files — saves 5 lines
      FILES: oqlos/api/execution.py, oqlos/api/peripherals.py
  [16] ○ extract_function   → oqlos/core/utils/_try_var.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [17] ○ extract_function   → oqlos/api/utils/stop_lung.py
      WHY: 2 occurrences of 4-line block across 1 files — saves 4 lines
      FILES: oqlos/api/hardware.py
  [18] ○ extract_function   → scripts/utils/_looks_like_html.py
      WHY: 2 occurrences of 3-line block across 2 files — saves 3 lines
      FILES: scripts/oql_v2_validator.py, scripts/oql_v4_validator.py
  [19] ○ extract_function   → oqlos/core/utils/_func_sum.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/core/_interpreter_actions.py
  [20] ○ extract_function   → oqlos/core/utils/_func_min.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/core/_interpreter_actions.py
  [21] ○ extract_function   → oqlos/core/utils/_resolve_compare.py
      WHY: 2 occurrences of 3-line block across 2 files — saves 3 lines
      FILES: oqlos/core/executor.py, oqlos/core/safe_eval.py
  [22] ○ extract_function   → oqlos/core/utils/parse_CALL.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/core/oql_parser.py
  [23] ○ extract_function   → oqlos/tools/hardware_diagnose/utils/check_firmware_health.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/tools/hardware_diagnose/health.py
  [24] ○ extract_function   → oqlos/tools/hardware_diagnose/utils/_env_int.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/tools/hardware_diagnose/modbus_probe.py

QUICK_WINS[12] (low risk, high savings — do first):
  [1] extract_function   saved=23L  → scripts/utils/_extract_code_from_json.py
      FILES: oql_v2_validator.py, oql_v4_validator.py
  [2] extract_function   saved=23L  → scripts/utils/_load_source.py
      FILES: oql_v2_validator.py, oql_v4_validator.py
  [3] extract_function   saved=22L  → scripts/utils/_build_api_fallback_urls.py
      FILES: oql_v2_validator.py, oql_v4_validator.py
  [4] extract_function   saved=20L  → scripts/utils/main.py
      FILES: oql_v2_validator.py, oql_v4_validator.py
  [5] extract_function   saved=13L  → scripts/utils/_fetch_url.py
      FILES: oql_v2_validator.py, oql_v4_validator.py
  [6] extract_function   saved=10L  → oqlos/core/utils/_try_task.py
      FILES: _cql_tokenizer.py
  [7] extract_function   saved=10L  → oqlos/core/utils/parse_SET.py
      FILES: oql_parser.py
  [8] extract_function   saved=10L  → oqlos/dsl/utils/_merge_object_function_map.py
      FILES: schema.py
  [9] extract_function   saved=10L  → oqlos/hardware/plugins/utils/disconnect.py
      FILES: lung.py, motor.py, piadc.py
  [10] extract_function   saved=7L  → oqlos/hardware/plugins/utils/not_connected_health.py
      FILES: _shared.py

EFFORT_ESTIMATE (total ≈ 6.8h):
  medium _extract_code_from_json             saved=23L  ~46min
  medium _load_source                        saved=23L  ~46min
  medium _build_api_fallback_urls            saved=22L  ~44min
  medium main                                saved=20L  ~40min
  easy   _fetch_url                          saved=13L  ~26min
  easy   _try_task                           saved=10L  ~20min
  easy   parse_SET                           saved=10L  ~20min
  easy   _merge_object_function_map          saved=10L  ~20min
  easy   disconnect                          saved=10L  ~20min
  easy   not_connected_health                saved=7L  ~14min
  ... +14 more (~114min)

METRICS-TARGET:
  dup_groups:  24 → 0
  saved_lines: 205 lines recoverable
```

### Evolution / Churn (`project/evolution.toon.yaml`)

```toon markpact:analysis path=project/evolution.toon.yaml
# code2llm/evolution | 912 func | 85f | 2026-05-06
# generated in 0.00s

NEXT[10] (ranked by impact):
  [1] !! SPLIT           oqlos/core/_interpreter_actions.py
      WHY: 771L, 0 classes, max CC=13
      EFFORT: ~4h  IMPACT: 10023

  [2] !! SPLIT-FUNC      parse_oql  CC=49  fan=36
      WHY: CC=49 exceeds 15
      EFFORT: ~1h  IMPACT: 1764

  [3] !  SPLIT-FUNC      hardware_identify  CC=24  fan=23
      WHY: CC=24 exceeds 15
      EFFORT: ~1h  IMPACT: 552

  [4] !! SPLIT-FUNC      _cmd_to_actions  CC=37  fan=13
      WHY: CC=37 exceeds 15
      EFFORT: ~1h  IMPACT: 481

  [5] !  SPLIT-FUNC      main  CC=19  fan=22
      WHY: CC=19 exceeds 15
      EFFORT: ~1h  IMPACT: 418

  [6] !! SPLIT-FUNC      _analyze_firmware_access  CC=25  fan=15
      WHY: CC=25 exceeds 15
      EFFORT: ~1h  IMPACT: 375

  [7] !  SPLIT-FUNC      _detect_runtime_platform  CC=18  fan=17
      WHY: CC=18 exceeds 15
      EFFORT: ~1h  IMPACT: 306

  [8] !  SPLIT-FUNC      report_json  CC=16  fan=17
      WHY: CC=16 exceeds 15
      EFFORT: ~1h  IMPACT: 272

  [9] !  SPLIT-FUNC      format_doctor  CC=20  fan=13
      WHY: CC=20 exceeds 15
      EFFORT: ~1h  IMPACT: 260

  [10] !  SPLIT-FUNC      format_detection  CC=16  fan=14
      WHY: CC=16 exceeds 15
      EFFORT: ~1h  IMPACT: 224


RISKS[3]:
  ⚠ Splitting openapi.yaml may break 0 import paths
  ⚠ Splitting docs/README.md may break 0 import paths
  ⚠ Splitting oqlos/core/_interpreter_actions.py may break 48 import paths

METRICS-TARGET:
  CC̄:          4.0 → ≤2.8
  max-CC:      49 → ≤20
  god-modules: 11 → 0
  high-CC(≥15): 14 → ≤7
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
