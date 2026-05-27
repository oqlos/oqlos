# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- `POST /api/v1/hardware/lung/disable` now de-energizes Tic T249 coils reliably (`de-energized` response path).
- `GET /api/v1/hardware/identify` latency reduced by conditional scanning (`scan=auto|always|never`), with fast path when plugin health is compatible.
- `GET /api/v1/hardware/identify` no longer misreports Modbus lock errors when plugin already owns the serial port and the real issue is `read_coils` no-response.
- Restored and stabilized detailed lung error propagation (`ok=false`, `error`, `data.runtime_status`) so callers no longer get false-positive success when movement is blocked.
- Fixed runtime regression that caused proxy diagnostics failures after refactor (`_candidate_oqlos_bases` path in upstream integration).
- Lung startup now performs explicit pre-checks for movement blockers before issuing reciprocate:
  - both limit switches active,
  - low VIN,
  - motor driver fault,
  - disconnected controller.

### Docs
- Clarified hardware diagnostics workflow and failure signatures for:
  - identify timeout/latency,
  - dual active limit switches,
  - low VIN (missing motor supply),
  - Modbus adapter-present but device-silent mode.

## [0.1.23] - 2026-05-27

### Docs
- Update README.md

### Other
- Update uv.lock

## [0.1.22] - 2026-05-27

### Docs
- Update README.md
- Update docs/README.md

### Test
- Update tests/firmware/test_hardware_identify.py
- Update tests/firmware/test_plugin_gateway_env.py
- Update tests/firmware/test_plugin_health.py

### Other
- Update oqlos.yaml
- Update oqlos/api/hardware.py
- Update oqlos/hardware/plugin_gateway.py
- Update oqlos/hardware/plugins/modbus.py
- Update uv.lock

## [0.1.21] - 2026-05-19

### Docs
- Update README.md

### Other
- Update uv.lock

## [0.1.20] - 2026-05-19

### Docs
- Update README.md

### Test
- Update tests/firmware/test_artificial_lung.py
- Update tests/firmware/test_control_proxy.py
- Update tests/firmware/test_hardware_identify.py
- Update tests/firmware/test_modbus_discovery.py
- Update tests/firmware/test_modbus_identify.py
- Update tests/firmware/test_rtc_probe.py
- Update tests/firmware/test_scanner_probe.py

### Other
- Update oqlos.yaml
- Update oqlos/api/hardware.py
- Update oqlos/config.py
- Update oqlos/hardware/artificial_lung.py
- Update oqlos/hardware/control_proxy.py
- Update oqlos/hardware/discovery.py
- Update oqlos/hardware/gateway.py
- Update oqlos/hardware/identify_enrichment.py
- Update oqlos/hardware/modbus_identify.py
- Update oqlos/hardware/plugins/modbus.py
- ... and 5 more files

## [0.1.19] - 2026-05-13

### Docs
- Update README.md
- Update docs/HARDWARE_DIAGNOSTICS.md
- Update docs/README.md
- Update docs/oql-spec.md
- Update oqlos/scenarios/OQL-CHEATSHEET.md

### Test
- Update tests/firmware/test_lung_integration.py
- Update tests/firmware/test_lung_plugin_reciprocate.py
- Update tests/scenarios/test_technical_flat.oql
- Update tests/test_core.py
- Update tests/test_cql_cli.py
- Update tests/test_oql_parser_v3.py
- Update tests/test_xml_import_generators.py

### Other
- Update examples/plugin-config.yaml
- Update oqlos.yaml
- Update oqlos/api/hardware.py
- Update oqlos/core/_interpreter_actions.py
- Update oqlos/core/interpreter.py
- Update oqlos/core/motor2_runtime.py
- Update oqlos/core/oql_parser.py
- Update oqlos/hardware/control_proxy.py
- Update oqlos/hardware/firmware_adapter.py
- Update oqlos/hardware/gateway.py
- ... and 26 more files

## [0.1.18] - 2026-05-10

### Docs
- Update README.md

### Test
- Update tests/firmware/test_hardware_doctor.py
- Update tests/firmware/test_hardware_identify.py
- Update tests/firmware/test_plugin_gateway_env.py
- Update tests/firmware/test_plugin_health.py
- Update tests/test_cql_cli.py

### Other
- Update oqlos.yaml
- Update oqlos/api/editor.py
- Update oqlos/api/hardware.py
- Update oqlos/api/plugins.py
- Update oqlos/config.py
- Update oqlos/core/_interpreter_actions.py
- Update oqlos/hardware/control_proxy.py
- Update oqlos/hardware/discovery.py
- Update oqlos/hardware/peripheral_mapping.py
- Update oqlos/hardware/plugin_gateway.py
- ... and 9 more files

## [0.1.17] - 2026-05-06

### Docs
- Update README.md

### Test
- Update tests/test_core.py
- Update tests/test_oql_parser_v3.py

### Other
- Update oqlos/core/_oql_adapter.py
- Update oqlos/core/interpreter.py
- Update oqlos/core/oql_parser.py
- Update oqlos/scenarios/examples/mask-leak-test.oql
- Update uv.lock

## [0.1.16] - 2026-05-06

### Docs
- Update README.md

### Test
- Update tests/test_core.py

### Other
- Update oqlos/core/_cql_tokenizer.py
- Update oqlos/core/_cql_tree_builder.py
- Update oqlos/core/_oql_adapter.py
- Update oqlos/core/_value_normalizers.py
- Update oqlos/core/cql_parser.py
- Update oqlos/scenarios/examples/drager-fps7000-mask-full.oql
- Update uv.lock

## [0.1.15] - 2026-05-06

### Docs
- Update README.md

### Test
- Update tests/firmware/test_plugin_gateway_env.py

### Other
- Update oqlos/hardware/plugin_gateway.py
- Update uv.lock

## [0.1.14] - 2026-05-06

### Docs
- Update README.md
- Update SUMD.md
- Update SUMR.md
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Test
- Update tests/firmware/test_control_proxy.py
- Update tests/firmware/test_plugins_api.py

### Other
- Update .code2llm_cache/README_1778095411857250255_39701.pkl
- Update .code2llm_cache/README_1778095570351667507_40587.pkl
- Update .code2llm_cache/__init___1778095458075965818_388.pkl
- Update .code2llm_cache/control_proxy_1778095454737928126_18888.pkl
- Update .code2llm_cache/project_1778095988177832301_1318.pkl
- Update .dockerignore
- Update app.doql.less
- Update openapi_spec.yaml
- Update oqlos/api/plugins.py
- Update oqlos/hardware/__init__.py
- ... and 23 more files

## [0.1.13] - 2026-05-06

### Docs
- Update README.md

### Other
- Update uv.lock

## [0.1.12] - 2026-05-06

### Docs
- Update CHANGELOG.md
- Update README.md
- Update docs/HARDWARE_DIAGNOSTICS.md

### Test
- Update tests/firmware/test_hardware_identify.py
- Update tests/firmware/test_lung_plugin_reciprocate.py
- Update tests/firmware/test_modbus_probe_cli.py
- Update tests/firmware/test_plugin_gateway_env.py
- Update tests/firmware/test_plugin_health.py

### Other
- Update oqlos/api/hardware.py
- Update oqlos/hardware/plugin_gateway.py
- Update oqlos/hardware/plugins/lung.py
- Update oqlos/hardware/plugins/modbus.py
- Update oqlos/hardware/plugins/piadc.py
- Update oqlos/tools/hardware_diagnose/__main__.py
- Update oqlos/tools/hardware_diagnose/modbus_probe.py
- Update uv.lock

## [0.1.11] - 2026-05-05

### Docs
- Update README.md

### Test
- Update tests/firmware/test_hardware_identify.py

### Other
- Update oqlos.yaml
- Update oqlos/api/hardware.py
- Update oqlos/hardware/plugin_gateway.py
- Update oqlos/hardware/plugins/lung.py
- Update oqlos/hardware/plugins/motor.py
- Update oqlos/hardware/plugins/piadc.py
- Update uv.lock

## [0.1.10] - 2026-05-05

### Docs
- Update README.md
- Update docs/HARDWARE_DIAGNOSTICS.md
- Update docs/README.md

### Test
- Update tests/firmware/test_hardware_discovery.py
- Update tests/firmware/test_hardware_doctor.py
- Update tests/firmware/test_motor_plugin.py
- Update tests/firmware/test_plugin_health.py

### Other
- Update examples/hardware/doctor-workflow.sh
- Update examples/plugin-config.yaml
- Update oqlos.yaml
- Update oqlos/hardware/plugin_gateway.py
- Update oqlos/hardware/plugins/lung.py
- Update oqlos/hardware/plugins/modbus.py
- Update oqlos/hardware/plugins/motor.py
- Update oqlos/hardware/plugins/piadc.py
- Update oqlos/hardware/plugins/registry.py
- Update oqlos/tools/cql_cli/preflight.py
- ... and 3 more files

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

