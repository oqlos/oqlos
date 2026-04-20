# OqlOS — Operation Query Language Runtime

SUMD - Structured Unified Markdown Descriptor for AI-aware project refactorization

## Contents

- [Metadata](#metadata)
- [Architecture](#architecture)
- [Workflows](#workflows)
- [Quality Pipeline (`pyqual.yaml`)](#quality-pipeline-pyqualyaml)
- [Dependencies](#dependencies)
- [Source Map](#source-map)
- [Test Contracts](#test-contracts)
- [Refactoring Analysis](#refactoring-analysis)
- [Intent](#intent)

## Metadata

- **name**: `oqlos`
- **version**: `0.1.1`
- **python_requires**: `>=3.10`
- **license**: Apache-2.0
- **ai_model**: `openrouter/qwen/qwen3-coder-next`
- **ecosystem**: SUMD + DOQL + testql + taskfile
- **openapi_title**: oqlos API v1.0.0
- **generated_from**: pyproject.toml, Taskfile.yml, testql(6), openapi(49 ep), app.doql.less, pyqual.yaml, goal.yaml, .env.example, Dockerfile, docker-compose.dev.yml, src(1 mod), project/(5 analysis files)

## Architecture

```
SUMD (description) → DOQL/source (code) → taskfile (automation) → testql (verification)
```

### DOQL Application Declaration (`app.doql.less`)

```less markpact:doql path=app.doql.less
// LESS format — define @variables here as needed

app {
  name: oqlos;
  version: 0.1.1;
}

entity[name="ExecutionStatus"] {

}

entity[name="CommandEnvelope"] {

}

entity[name="Step"] {

}

entity[name="ValidationRule"] {

}

entity[name="Goal"] {

}

entity[name="Scenario"] {

}

entity[name="Peripheral"] {

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
  step-1: run cmd=oqlctl --status || echo "Hardware not available (mock mode)";
}

workflow[name="hardware:identify"] {
  trigger: manual;
  step-1: run cmd=oqlctl --identify;
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
    desc: Check hardware status via oqlctl
    cmds:
      - oqlctl --status || echo "Hardware not available (mock mode)"

  hardware:identify:
    desc: Identify connected hardware
    cmds:
      - oqlctl --identify

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

### Code Analysis (`project/analysis.toon.yaml`)

```toon markpact:analysis path=project/analysis.toon.yaml
# code2llm | 102f 16524L | python:102,shell:3 | 2026-04-18
# CC̄=3.7 | critical:4/775 | dups:0 | cycles:0

HEALTH[4]:
  🟡 CC    parse_oql CC=34 (limit:15)
  🟡 CC    _cmd_to_actions CC=24 (limit:15)
  🟡 CC    report_json CC=16 (limit:15)
  🟡 CC    main CC=15 (limit:15)

REFACTOR[1]:
  1. split 4 high-CC methods  (CC>15)

PIPELINES[471]:
  [1] Src [main]: main → run_oql_scenario
      PURITY: 100% pure
  [2] Src [exec_action_task]: exec_action_task
      PURITY: 100% pure
  [3] Src [exec_action_log]: exec_action_log
      PURITY: 100% pure
  [4] Src [exec_action_error]: exec_action_error
      PURITY: 100% pure
  [5] Src [exec_action_else]: exec_action_else
      PURITY: 100% pure

LAYERS:
  ./                              CC̄=6.9    ←in:0  →out:0
  │ setup_hardware_and_run_oql   333L  0C    7m  CC=12     ←0
  │ project.sh                  35L  0C    0m  CC=0.0    ←0
  │
  oqlos/                          CC̄=3.7    ←in:4  →out:0
  │ !! _interpreter_actions       771L  0C   48m  CC=13     ←1
  │ !! interpreter                583L  1C   43m  CC=13     ←0
  │ !! oql_parser                 571L  3C   29m  CC=34     ←2
  │ cql_parser                 478L  1C   30m  CC=8      ←2
  │ generators                 442L  0C   18m  CC=14     ←0
  │ firmware_adapter           428L  1C   23m  CC=12     ←0
  │ gateway                    415L  5C   25m  CC=7      ←0
  │ !! _oql_adapter               412L  1C   14m  CC=24     ←2
  │ _cql_tokenizer             386L  0C   25m  CC=5      ←0
  │ executor                   383L  1C   21m  CC=14     ←0
  │ motor                      376L  1C   17m  CC=14     ←0
  │ state                      370L  0C   16m  CC=13     ←0
  │ execution                  354L  0C   16m  CC=11     ←0
  │ plugin_gateway             348L  1C   14m  CC=6      ←0
  │ plugin_cli                 342L  0C   13m  CC=8      ←0
  │ base                       326L  8C   19m  CC=5      ←1
  │ base                       320L  7C   28m  CC=7      ←11
  │ registry                   316L  1C   14m  CC=6      ←4
  │ schema                     296L  5C    6m  CC=7      ←0
  │ hardware                   281L  0C   16m  CC=9      ←0
  │ html_report                266L  0C    5m  CC=10     ←0
  │ preflight                  265L  0C   10m  CC=13     ←1
  │ modbus                     258L  1C    7m  CC=12     ←0
  │ scenarios                  251L  0C   16m  CC=11     ←0
  │ _line_parsers              246L  0C    9m  CC=12     ←2
  │ lung                       245L  1C   17m  CC=14     ←0
  │ discovery                  232L  0C    8m  CC=12     ←2
  │ _firmware_executor         201L  1C    9m  CC=11     ←0
  │ main                       195L  0C    6m  CC=5      ←0
  │ parser                     183L  0C    5m  CC=13     ←2
  │ commands                   178L  0C    5m  CC=8      ←1
  │ parser                     175L  0C    6m  CC=9      ←0
  │ event_server               171L  2C   11m  CC=7      ←0
  │ main                       169L  0C    6m  CC=5      ←0
  │ piadc                      150L  1C    7m  CC=9      ←0
  │ utils                      148L  0C   10m  CC=8      ←3
  │ _sensor_evaluator          145L  1C    6m  CC=10     ←0
  │ logs_query                 145L  1C    5m  CC=11     ←1
  │ safe_eval                  138L  1C   10m  CC=4      ←0
  │ shell                      138L  0C    5m  CC=6      ←1
  │ peripheral_mapping         138L  0C    4m  CC=2      ←0
  │ plugins                    137L  0C    8m  CC=3      ←0
  │ !! __main__                   135L  0C    5m  CC=15     ←0
  │ _dsl_helpers               132L  0C   12m  CC=11     ←4
  │ !! json_reporter              130L  0C    2m  CC=16     ←0
  │ _value_normalizers         126L  1C    7m  CC=8      ←0
  │ editor                     126L  3C    5m  CC=6      ←0
  │ config_schema              125L  1C    3m  CC=2      ←0
  │ release_version            125L  0C    7m  CC=11     ←1
  │ state                      124L  1C    3m  CC=4      ←0
  │ mqtt                       119L  1C    9m  CC=3      ←0
  │ discovery                  112L  1C    5m  CC=11     ←4
  │ file_ops                   108L  1C    5m  CC=4      ←1
  │ _utils                     101L  0C    6m  CC=12     ←1
  │ _func_resolver              96L  0C    4m  CC=13     ←1
  │ calibration                 92L  0C    4m  CC=5      ←3
  │ spi                         92L  1C    7m  CC=4      ←0
  │ models                      90L  5C    0m  CC=0.0    ←0
  │ gpio                        89L  1C    7m  CC=6      ←0
  │ dsl_models                  87L  8C    0m  CC=0.0    ←0
  │ junit                       86L  1C    3m  CC=8      ←0
  │ config_factory              84L  0C    1m  CC=1      ←0
  │ health                      80L  0C    5m  CC=6      ←5
  │ event_store                 77L  1C   10m  CC=3      ←0
  │ sample_data                 73L  0C    1m  CC=1      ←0
  │ peripherals                 70L  0C    4m  CC=5      ←0
  │ config                      67L  1C    1m  CC=1      ←2
  │ version_endpoint            66L  0C    2m  CC=3      ←0
  │ report                      63L  0C    2m  CC=12     ←3
  │ execution_ctrl              62L  0C    3m  CC=1      ←0
  │ _shared                     61L  0C    4m  CC=2      ←3
  │ __init__                    60L  0C    2m  CC=1      ←0
  │ protocol                    60L  2C    6m  CC=1      ←0
  │ benchmark                   55L  0C    1m  CC=6      ←2
  │ __init__                    53L  0C    0m  CC=0.0    ←0
  │ registry                    49L  1C    3m  CC=2      ←0
  │ logs                        45L  0C    3m  CC=1      ←0
  │ __init__                    43L  0C    0m  CC=0.0    ←0
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
  │ __init__                     6L  0C    0m  CC=0.0    ←0
  │ __init__                     5L  0C    0m  CC=0.0    ←0
  │ __init__                     3L  0C    0m  CC=0.0    ←0
  │ __init__                     3L  0C    0m  CC=0.0    ←0
  │ __init__                     0L  0C    0m  CC=0.0    ←0
  │ __init__                     0L  0C    0m  CC=0.0    ←0
  │ __init__                     0L  0C    0m  CC=0.0    ←0
  │ __init__                     0L  0C    0m  CC=0.0    ←0
  │ __init__                     0L  0C    0m  CC=0.0    ←0
  │ __init__                     0L  0C    0m  CC=0.0    ←0
  │ __init__                     0L  0C    0m  CC=0.0    ←0
  │
  scripts/                        CC̄=0.0    ←in:0  →out:0
  │ hardware-check.sh          340L  0C   11m  CC=0.0    ←0
  │
  ── zero ──
     oqlos/api/utils/__init__.py               0L
     oqlos/core/__init__.py                    0L
     oqlos/hardware/__init__.py                0L
     oqlos/ide/__init__.py                     0L
     oqlos/models/__init__.py                  0L
     oqlos/shared/__init__.py                  0L
     oqlos/tools/__init__.py                   0L

COUPLING:
                  oqlos.hardware     oqlos.tools       oqlos.api      oqlos.core    oqlos.shared           oqlos       oqlos.dsl
  oqlos.hardware              ──             ←12             ←10               1                               4                  hub
     oqlos.tools              12              ──                               9                                                  !! fan-out
       oqlos.api              10                              ──               2               7                                  !! fan-out
      oqlos.core              ←1              ←9              ←2              ──              ←1                              ←1  hub
    oqlos.shared                                              ←7               1              ──                                  hub
           oqlos              ←4                                                                              ──                
       oqlos.dsl                                                               1                                              ──
  CYCLES: none
  HUB: oqlos.hardware/ (fan-in=22)
  HUB: oqlos.shared/ (fan-in=7)
  HUB: oqlos.core/ (fan-in=14)
  SMELL: oqlos.api/ fan-out=19 → split needed
  SMELL: oqlos.tools/ fan-out=21 → split needed

EXTERNAL:
  validation: run `vallm batch .` → validation.toon
  duplication: run `redup scan .` → duplication.toon
```

### Duplication (`project/duplication.toon.yaml`)

```toon markpact:analysis path=project/duplication.toon.yaml
# redup/duplication | 13 groups | 99f 14917L | 2026-04-16

SUMMARY:
  files_scanned: 99
  total_lines:   14917
  dup_groups:    13
  dup_fragments: 28
  saved_lines:   85
  scan_ms:       9436

HOTSPOTS[7] (files with most duplication):
  oqlos/hardware/plugins/lung.py  dup=26L  groups=3  frags=3  (0.2%)
  oqlos/core/_cql_tokenizer.py  dup=25L  groups=2  frags=5  (0.2%)
  oqlos/hardware/plugins/motor.py  dup=22L  groups=2  frags=2  (0.1%)
  oqlos/dsl/schema.py  dup=20L  groups=1  frags=2  (0.1%)
  oqlos/hardware/plugins/_shared.py  dup=14L  groups=1  frags=2  (0.1%)
  oqlos/core/_interpreter_actions.py  dup=12L  groups=2  frags=4  (0.1%)
  oqlos/hardware/gateway.py  dup=10L  groups=1  frags=2  (0.1%)

DUPLICATES[13] (ranked by impact):
  [f0b3386dd1ca238b]   STRU  health_check  L=17 N=2 saved=17 sim=1.00
      oqlos/hardware/plugins/lung.py:86-102  (health_check)
      oqlos/hardware/plugins/motor.py:112-128  (health_check)
  [cec388e17126d04a]   STRU  _try_task  L=5 N=3 saved=10 sim=1.00
      oqlos/core/_cql_tokenizer.py:157-161  (_try_task)
      oqlos/core/_cql_tokenizer.py:236-240  (_try_if_fail_block)
      oqlos/core/_cql_tokenizer.py:350-354  (_try_save_ws)
  [d884e769a616fa58]   STRU  _merge_object_function_map  L=10 N=2 saved=10 sim=1.00
      oqlos/dsl/schema.py:99-108  (_merge_object_function_map)
      oqlos/dsl/schema.py:111-120  (_merge_param_unit_map)
  [43e47beaf70d4a45]   STRU  disconnect  L=5 N=3 saved=10 sim=1.00
      oqlos/hardware/plugins/lung.py:80-84  (disconnect)
      oqlos/hardware/plugins/motor.py:106-110  (disconnect)
      oqlos/hardware/plugins/piadc.py:73-77  (disconnect)
  [8b32652353801ed5]   STRU  not_connected_health  L=7 N=2 saved=7 sim=1.00
      oqlos/hardware/plugins/_shared.py:39-45  (not_connected_health)
      oqlos/hardware/plugins/_shared.py:48-54  (health_check_exception)
  [c7eda7834116d40a]   EXAC  status  L=5 N=2 saved=5 sim=1.00
      oqlos/hardware/gateway.py:130-134  (status)
      oqlos/hardware/gateway.py:186-190  (status)
  [0620456dd3154e5e]   STRU  get_execution  L=5 N=2 saved=5 sim=1.00
      oqlos/api/execution.py:194-198  (get_execution)
      oqlos/api/peripherals.py:18-22  (get_peripheral)
  [b13c2884a460682f]   STRU  _try_var  L=5 N=2 saved=5 sim=1.00
      oqlos/core/_cql_tokenizer.py:304-308  (_try_var)
      oqlos/core/_cql_tokenizer.py:334-338  (_try_api)
  [137f276b5dc444f9]   STRU  __init__  L=4 N=2 saved=4 sim=1.00
      oqlos/hardware/plugins/lung.py:35-38  (__init__)
      oqlos/hardware/plugins/piadc.py:35-38  (__init__)
  [ad79a9de6949934f]   STRU  _func_sum  L=3 N=2 saved=3 sim=1.00
      oqlos/core/_interpreter_actions.py:347-349  (_func_sum)
      oqlos/core/_interpreter_actions.py:388-390  (_func_add)
  [15bf0901916bbc4e]   STRU  _func_min  L=3 N=2 saved=3 sim=1.00
      oqlos/core/_interpreter_actions.py:352-354  (_func_min)
      oqlos/core/_interpreter_actions.py:357-359  (_func_max)
  [697b748fa91d3f41]   STRU  _resolve_compare  L=3 N=2 saved=3 sim=1.00
      oqlos/core/executor.py:11-13  (_resolve_compare)
      oqlos/core/safe_eval.py:90-92  (_eval_compare)
  [a17e1e3392ea6e68]   STRU  check_firmware_health  L=3 N=2 saved=3 sim=1.00
      oqlos/tools/hardware_diagnose/health.py:19-21  (check_firmware_health)
      oqlos/tools/hardware_diagnose/health.py:24-26  (check_firmware_identify)

REFACTOR[13] (ranked by priority):
  [1] ○ extract_function   → oqlos/hardware/plugins/utils/health_check.py
      WHY: 2 occurrences of 17-line block across 2 files — saves 17 lines
      FILES: oqlos/hardware/plugins/lung.py, oqlos/hardware/plugins/motor.py
  [2] ○ extract_function   → oqlos/core/utils/_try_task.py
      WHY: 3 occurrences of 5-line block across 1 files — saves 10 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [3] ○ extract_function   → oqlos/dsl/utils/_merge_object_function_map.py
      WHY: 2 occurrences of 10-line block across 1 files — saves 10 lines
      FILES: oqlos/dsl/schema.py
  [4] ○ extract_function   → oqlos/hardware/plugins/utils/disconnect.py
      WHY: 3 occurrences of 5-line block across 3 files — saves 10 lines
      FILES: oqlos/hardware/plugins/lung.py, oqlos/hardware/plugins/motor.py, oqlos/hardware/plugins/piadc.py
  [5] ○ extract_function   → oqlos/hardware/plugins/utils/not_connected_health.py
      WHY: 2 occurrences of 7-line block across 1 files — saves 7 lines
      FILES: oqlos/hardware/plugins/_shared.py
  [6] ○ extract_function   → oqlos/hardware/utils/status.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/hardware/gateway.py
  [7] ○ extract_function   → oqlos/api/utils/get_execution.py
      WHY: 2 occurrences of 5-line block across 2 files — saves 5 lines
      FILES: oqlos/api/execution.py, oqlos/api/peripherals.py
  [8] ○ extract_function   → oqlos/core/utils/_try_var.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: oqlos/core/_cql_tokenizer.py
  [9] ○ extract_function   → oqlos/hardware/plugins/utils/__init__.py
      WHY: 2 occurrences of 4-line block across 2 files — saves 4 lines
      FILES: oqlos/hardware/plugins/lung.py, oqlos/hardware/plugins/piadc.py
  [10] ○ extract_function   → oqlos/core/utils/_func_sum.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/core/_interpreter_actions.py
  [11] ○ extract_function   → oqlos/core/utils/_func_min.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/core/_interpreter_actions.py
  [12] ○ extract_function   → oqlos/core/utils/_resolve_compare.py
      WHY: 2 occurrences of 3-line block across 2 files — saves 3 lines
      FILES: oqlos/core/executor.py, oqlos/core/safe_eval.py
  [13] ○ extract_function   → oqlos/tools/hardware_diagnose/utils/check_firmware_health.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: oqlos/tools/hardware_diagnose/health.py

QUICK_WINS[5] (low risk, high savings — do first):
  [1] extract_function   saved=17L  → oqlos/hardware/plugins/utils/health_check.py
      FILES: lung.py, motor.py
  [2] extract_function   saved=10L  → oqlos/core/utils/_try_task.py
      FILES: _cql_tokenizer.py
  [3] extract_function   saved=10L  → oqlos/dsl/utils/_merge_object_function_map.py
      FILES: schema.py
  [4] extract_function   saved=10L  → oqlos/hardware/plugins/utils/disconnect.py
      FILES: lung.py, motor.py, piadc.py
  [5] extract_function   saved=7L  → oqlos/hardware/plugins/utils/not_connected_health.py
      FILES: _shared.py

EFFORT_ESTIMATE (total ≈ 2.8h):
  medium health_check                        saved=17L  ~34min
  easy   _try_task                           saved=10L  ~20min
  easy   _merge_object_function_map          saved=10L  ~20min
  easy   disconnect                          saved=10L  ~20min
  easy   not_connected_health                saved=7L  ~14min
  easy   status                              saved=5L  ~10min
  easy   get_execution                       saved=5L  ~10min
  easy   _try_var                            saved=5L  ~10min
  easy   __init__                            saved=4L  ~8min
  easy   _func_sum                           saved=3L  ~6min
  ... +3 more (~18min)

METRICS-TARGET:
  dup_groups:  13 → 0
  saved_lines: 85 lines recoverable
```

### Evolution / Churn (`project/evolution.toon.yaml`)

```toon markpact:analysis path=project/evolution.toon.yaml
# code2llm/evolution | 693 func | 74f | 2026-04-16

NEXT[7] (ranked by impact):
  [1] !! SPLIT           oqlos/core/_interpreter_actions.py
      WHY: 703L, 0 classes, max CC=23
      EFFORT: ~4h  IMPACT: 16169

  [2] !! SPLIT           oqlos/core/interpreter.py
      WHY: 530L, 1 classes, max CC=24
      EFFORT: ~4h  IMPACT: 12720

  [3] !  SPLIT-FUNC      exec_action_assert  CC=22  fan=20
      WHY: CC=22 exceeds 15
      EFFORT: ~1h  IMPACT: 440

  [4] !  SPLIT-FUNC      CqlInterpreter._evaluate_inline_condition_expression  CC=24  fan=16
      WHY: CC=24 exceeds 15
      EFFORT: ~1h  IMPACT: 384

  [5] !  SPLIT-FUNC      exec_action_func  CC=23  fan=14
      WHY: CC=23 exceeds 15
      EFFORT: ~1h  IMPACT: 322

  [6] !  SPLIT-FUNC      main  CC=15  fan=18
      WHY: CC=15 exceeds 15
      EFFORT: ~1h  IMPACT: 270

  [7] !  SPLIT-FUNC      _ParseState._try_hierarchy  CC=18  fan=13
      WHY: CC=18 exceeds 15
      EFFORT: ~1h  IMPACT: 234


RISKS[2]:
  ⚠ Splitting oqlos/core/_interpreter_actions.py may break 36 import paths
  ⚠ Splitting oqlos/core/interpreter.py may break 38 import paths

METRICS-TARGET:
  CC̄:          3.8 → ≤2.7
  max-CC:      24 → ≤12
  god-modules: 2 → 0
  high-CC(≥15): 5 → ≤2
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
  (first run — no previous data)
```

### Validation (`project/validation.toon.yaml`)

```toon markpact:analysis path=project/validation.toon.yaml
# vallm batch | 203f | 134✓ 9⚠ 0✗ | 2026-04-18

SUMMARY:
  scanned: 203  passed: 134 (66.0%)  warnings: 9  errors: 0  unsupported: 69

WARNINGS[9]{path,score}:
  oqlos/core/_oql_adapter.py,0.93
    issues[3]{rule,severity,message,line}:
      complexity.cyclomatic,warning,_cmd_to_actions has cyclomatic complexity 24 (max: 15),152
      complexity.lizard_cc,warning,_cmd_to_actions: CC=23 exceeds limit 15,152
      complexity.lizard_length,warning,_cmd_to_actions: 136 lines exceeds limit 100,152
  oqlos/core/oql_parser.py,0.97
    issues[2]{rule,severity,message,line}:
      complexity.cyclomatic,warning,parse_oql has cyclomatic complexity 34 (max: 15),389
      complexity.lizard_cc,warning,parse_oql: CC=34 exceeds limit 15,389
  oqlos/dsl/schema.py,0.97
    issues[1]{rule,severity,message,line}:
      complexity.lizard_length,warning,get_default_dsl_schema: 163 lines exceeds limit 100,123
  oqlos/reporters/json_reporter.py,0.97
    issues[2]{rule,severity,message,line}:
      complexity.cyclomatic,warning,report_json has cyclomatic complexity 16 (max: 15),48
      complexity.lizard_cc,warning,report_json: CC=16 exceeds limit 15,48
  oqlos/core/_interpreter_actions.py,0.98
    issues[1]{rule,severity,message,line}:
      complexity.maintainability,warning,Low maintainability index: 1.7 (threshold: 20),
  oqlos/core/interpreter.py,0.98
    issues[1]{rule,severity,message,line}:
      complexity.maintainability,warning,Low maintainability index: 12.8 (threshold: 20),
  oqlos/tools/xml_import/generators.py,0.98
    issues[1]{rule,severity,message,line}:
      complexity.maintainability,warning,Low maintainability index: 13.3 (threshold: 20),
  tests/firmware/test_tokenizer_extended.py,0.98
    issues[1]{rule,severity,message,line}:
      complexity.maintainability,warning,Low maintainability index: 17.4 (threshold: 20),
  tests/test_core.py,0.98
    issues[1]{rule,severity,message,line}:
      complexity.maintainability,warning,Low maintainability index: 11.1 (threshold: 20),

UNSUPPORTED[6]{bucket,count}:
  *.md,12
  Dockerfile*,1
  *.txt,1
  *.yml,4
  *.example,1
  other,50
```

## Intent

OqlOS — Operation Query Language runtime for hardware testing
