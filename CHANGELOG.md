# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.9] - 2026-05-05

### Docs
- Update README.md

### Test
- Update tests/firmware/test_hardware_health.py
- Update tests/firmware/test_motor_plugin.py

### Other
- Update oqlos/tools/hardware_diagnose/health.py
- Update uv.lock

## [0.1.8] - 2026-05-05

### Docs
- Update README.md

### Test
- Update tests/test_core.py

### Other
- Update oqlos/hardware/firmware_adapter.py

## [0.1.7] - 2026-05-05

### Docs
- Update README.md

### Other
- Update oqlos/api/editor.py
- Update oqlos/api/static/editor.html
- Update oqlos/config.py
- Update oqlos/hardware/gateway.py

## [0.1.6] - 2026-05-05

### Docs
- Update README.md

### Test
- Update tests/firmware/test_motor_plugin.py

### Other
- Update oqlos/hardware/plugins/motor.py

## [0.1.5] - 2026-05-05

### Docs
- Update README.md
- Update docs/HARDWARE_DIAGNOSTICS.md
- Update docs/OQL_V4_MIGRATION_MANUAL.md
- Update docs/README.md
- Update docs/cql-examples.md
- Update docs/cql-spec.md
- Update docs/oql-spec.md

### Test
- Update tests/firmware/test_hardware_doctor.py
- Update tests/test_cql_cli.py

### Other
- Update examples/hardware/doctor-workflow.sh
- Update examples/plugin-config.yaml
- Update oqlos.yaml
- Update oqlos/api/hardware.py
- Update oqlos/tools/cql_cli/main.py
- Update oqlos/tools/cql_cli/preflight.py
- Update oqlos/tools/cql_cli/utils.py
- Update oqlos/tools/hardware_diagnose/doctor.py

## [0.1.4] - 2026-04-30

### Docs
- Update README.md

## [0.1.3] - 2026-04-30

### Docs
- Update README.md

## [0.1.2] - 2026-04-30

### Docs
- Update README.md

### Other
- Update scripts/oql_v4_validator.py

## [0.1.1] - 2026-04-15

### Added
- testql-scenarios: `generated-api-smoke.testql.toon.yaml` — API smoke tests (31 endpoint commands)
- testql-scenarios: `generated-api-integration.testql.toon.yaml` — API integration flows
- testql-scenarios: `generated-from-pytests.testql.toon.yaml` — scenarios from pytest suite
- testql-scenarios: `generated-from-scenarios.testql.toon.yaml` — hardware type scenario (BA device)
- testql-scenarios: `cross-project-integration.testql.toon.yaml` — cross-project integration checks
- **OQL v3 — Flat Syntax** (`oqlos/core/oql_parser.py`): quote-free DSL
  with 12 base commands (`SET`, `GET`, `WAIT`, `SAVE`, `CHECK`, `MIN`,
  `MAX`, `SAMPLE`, `LOG`, `ERROR`, `CALL`, `INCLUDE`).
- Macro libraries in `oqlos/scenarios/lib/` (`hardware.oql`,
  `peripherals.oql`) + `$1`/`$2` positional placeholders.
- `INCLUDE "path"` directive resolved relative to the including file or
  `oqlos/scenarios/`.
- `CHECK min <= sensor <= max unit` range assertion replaces
  `IF/ENDIF` chains.
- Bracketed identifiers `[nazwa ze spacjami]` for multi-word names.
- Full Unicode support in identifiers (Polish: `ciśnienie-NC`, units
  like `°C`, `%RH`, `m³/h`).
- Adapter `oqlos/core/_oql_adapter.py` bridges v3 AST to the existing
  interpreter — no changes to `_interpreter_actions.py` needed.
- 30 unit tests (`tests/test_oql_parser_v3.py`).
- `docs/oql-grammar-anatomy.html` (visual reference).

### Changed
- All `.oql` scenarios in `oqlos/scenarios/` and
  `oqlos/scenarios/examples/` migrated to v3 flat syntax.
- Documentation rewritten: `README.md`, `docs/oql-spec.md`,
  `docs/cql-spec.md`, `oqlos/scenarios/OQL-CHEATSHEET.md`,
  `oqlos/scenarios/examples/README.md`.
- `parse_cql()` auto-detects flat v3 vs. legacy syntax.

### Removed
- Legacy `IF/ELSE/ENDIF`, `VAL`, `FUNC`, `GOTO` usage from all
  bundled scenarios (parser still accepts legacy sources for
  backward compatibility).
- `TODO/` folder (contents moved to `docs/` and
  `oqlos/core/oql_parser.py`).

## [0.1.1] - 2026-04-15

### Docs
- Update README.md

### Other
- Update oqlos/scenarios/test-zaworu.oql

