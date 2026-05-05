# OqlOS Documentation

## Hardware Operator Entry Points

Before running scenarios in `execute` mode, use the hardware doctor:

```bash
oqlctl doctor
oqlctl detect
oqlctl doctor --json
oqlctl doctor --fix
```

`doctor` combines host-side USB/serial/I2C discovery, Modbus RTU probing,
`oqlos.yaml` validation, and firmware `/api/v1/hardware/health` +
`/api/v1/hardware/identify` checks. It reports concrete issues such as:

- firmware running in `mock` mode,
- firmware/container missing access to `/dev/ttyACM*` or `/dev/ttyUSB*`,
- `modbus-io` port/baud mismatch,
- adapter statuses such as `offline`, `no-access`, or `adapter-only`.

Safe automatic repair is intentionally narrow: `oqlctl doctor --fix` updates
only detected Modbus connection parameters in `oqlos.yaml` and writes
`oqlos.yaml.bak` first. The current default hardware profile expects
`/dev/ttyACM1 @ 19200 8N1` for Waveshare Modbus RTU IO 8CH.
Runtime repairs such as enabling real firmware mode, restarting containers, or
mounting `/dev/ttyACM*`/`/dev/ttyUSB*` remain manual and are reported as
unapplied repairs when `--fix` is requested.

Detailed guide: [Hardware Diagnostics](HARDWARE_DIAGNOSTICS.md).

<!-- code2docs:start --># oqlos

![version](https://img.shields.io/badge/version-0.1.0-blue) ![python](https://img.shields.io/badge/python-%3E%3D3.10-blue) ![coverage](https://img.shields.io/badge/coverage-unknown-lightgrey) ![functions](https://img.shields.io/badge/functions-712-green)
> **712** functions | **82** classes | **100** files | CC̄ = 3.7

> Auto-generated project documentation from source code analysis.

**Author:** Tom Softreck <tom@sapletta.com>  
**License:** Apache-2.0[(LICENSE)](./LICENSE)  
**Repository:** [https://github.com/oqlos/oqlos](https://github.com/oqlos/oqlos)

## Installation

### From PyPI

```bash
pip install oqlos
```

### From Source

```bash
git clone https://github.com/oqlos/oqlos
cd oqlos
pip install -e .
```

### Optional Extras

```bash
pip install oqlos[rpi]    # rpi features
pip install oqlos[server]    # server features
pip install oqlos[dev]    # development tools
pip install oqlos[hardware-services]    # hardware-services features
```

## Quick Start

### CLI Usage

```bash
# Generate full documentation for your project
oqlos ./my-project

# Only regenerate README
oqlos ./my-project --readme-only

# Preview what would be generated (no file writes)
oqlos ./my-project --dry-run

# Check documentation health
oqlos check ./my-project

# Sync — regenerate only changed modules
oqlos sync ./my-project
```

### Python API

```python
from oqlos import generate_readme, generate_docs, Code2DocsConfig

# Quick: generate README
generate_readme("./my-project")

# Full: generate all documentation
config = Code2DocsConfig(project_name="mylib", verbose=True)
docs = generate_docs("./my-project", config=config)
```

## Generated Output

When you run `oqlos`, the following files are produced:

```
<project>/
├── README.md                 # Main project README (auto-generated sections)
├── docs/
│   ├── api.md               # Consolidated API reference
│   ├── modules.md           # Module documentation with metrics
│   ├── architecture.md      # Architecture overview with diagrams
│   ├── dependency-graph.md  # Module dependency graphs
│   ├── coverage.md          # Docstring coverage report
│   ├── getting-started.md   # Getting started guide
│   ├── configuration.md    # Configuration reference
│   └── api-changelog.md    # API change tracking
├── examples/
│   ├── quickstart.py       # Basic usage examples
│   └── advanced_usage.py   # Advanced usage examples
├── CONTRIBUTING.md         # Contribution guidelines
└── mkdocs.yml             # MkDocs site configuration
```

## Configuration

Create `oqlos.yaml` in your project root (or run `oqlos init`):

```yaml
project:
  name: my-project
  source: ./
  output: ./docs/

readme:
  sections:
    - overview
    - install
    - quickstart
    - api
    - structure
  badges:
    - version
    - python
    - coverage
  sync_markers: true

docs:
  api_reference: true
  module_docs: true
  architecture: true
  changelog: true

examples:
  auto_generate: true
  from_entry_points: true

sync:
  strategy: markers    # markers | full | git-diff
  watch: false
  ignore:
    - "tests/"
    - "__pycache__"
```

## Sync Markers

oqlos can update only specific sections of an existing README using HTML comment markers:

```markdown
<!-- oqlos:start -->
# Project Title
... auto-generated content ...
<!-- oqlos:end -->
```

Content outside the markers is preserved when regenerating. Enable this with `sync_markers: true` in your configuration.

## Architecture

```
oqlos/
├── project        ├── state├── setup_hardware_and_run_oql├── oqlos/        ├── _dsl_helpers    ├── core/        ├── parser        ├── _func_resolver        ├── _interpreter_actions        ├── executor        ├── _cql_tokenizer        ├── interpreter        ├── safe_eval        ├── _compare        ├── _line_parsers        ├── _firmware_executor        ├── _value_normalizers        ├── cql_parser        ├── _sensor_evaluator    ├── tools/        ├── hardware_diagnose/        ├── cql_cli/            ├── health            ├── __main__        ├── plugin_cli            ├── shell            ├── benchmark            ├── report            ├── calibration            ├── _utils        ├── xml_import/            ├── parser            ├── generators            ├── models            ├── commands            ├── utils        ├── base            ├── preflight            ├── main            ├── discovery    ├── models/        ├── dsl_models    ├── config        ├── protocol        ├── config_schema        ├── gateway        ├── registry    ├── hardware/        ├── peripheral_mapping        ├── plugin_gateway        ├── discovery        ├── firmware_adapter            ├── base        ├── execution            ├── registry        ├── plugins/            ├── modbus            ├── piadc            ├── lung            ├── _shared            ├── gpio        ├── drivers/            ├── spi            ├── mqtt    ├── reporters/            ├── motor        ├── scenario    ├── utils/        ├── sample_data        ├── _endpoint_helpers        ├── file_ops        ├── logs_query    ├── shared/        ├── config_factory        ├── event_server        ├── version_endpoint        ├── event_store        ├── logger        ├── version        ├── release_version        ├── plugins        ├── state        ├── execution        ├── peripherals    ├── api/        ├── hardware        ├── logs        ├── editor        ├── main        ├── utils/            ├── execution_ctrl    ├── ide/        ├── junit    ├── dsl/    ├── hardware-check        ├── schema        ├── peripheral        ├── scenarios```

## API Overview

### Classes

- **`StateManager`** — —
- **`ScenarioOrchestrator`** — —
- **`CqlInterpreter`** — CQL interpreter with three modes:
- **`SafeEvalError`** — Raised when an expression cannot be safely evaluated.
- **`FirmwareExecutor`** — Executes hardware actions via plugin gateway or legacy firmware.
- **`ValueNormalizer`** — Normalizes DSL values to hardware-compatible formats.
- **`SensorEvaluator`** — Evaluates sensor conditions and manages sensor values.
- **`SensorParam`** — Parameter measurement from an operation.
- **`Output`** — Hardware output setting.
- **`Operation`** — Single test operation (step).
- **`TestRun`** — A test run (scenario) within a device type.
- **`DeviceReport`** — Parsed device test report.
- **`StepStatus`** — —
- **`StepResult`** — —
- **`ScriptResult`** — —
- **`VariableStore`** — Hierarchical key-value store with interpolation support.
- **`InterpreterOutput`** — Collects interpreter output lines for display or testing, and optionally broadcasts events.
- **`BaseInterpreter`** — Abstract base for language interpreters.
- **`EventBridge`** — Optional WebSocket bridge to DSL Event Server (port 8104).
- **`UsbDevice`** — USB device information.
- **`CqlMetadata`** — —
- **`CqlInterval`** — —
- **`CqlCondition`** — Sensor condition: AI01 ∈ [min, max] unit | ACTION 'msg'
- **`CqlAction`** — An action within a step: → Target.method args, TASK, SET, WAIT, or PUMP.
- **`CqlStep`** — A numbered step within a goal: 1. Step name:
- **`CqlGoal`** — A test goal within a scenario.
- **`CqlScenario`** — A named scenario block: @Namespace.Name
- **`CqlDocument`** — Root AST node for a .cql file.
- **`Settings`** — Application settings loaded from environment variables and .env file
- **`ProtocolType`** — Supported hardware communication protocols.
- **`HardwareProtocol`** — Base class for all hardware drivers.
- **`UnitType`** — Standard unit types for hardware parameters.
- **`HardwareGateway`** — Single entry-point for all physical hardware I/O.
- **`DriverRegistry`** — Registry for hardware drivers. Allows mapping ProtocolType to specific HardwareProtocol implementations. 
- **`PluginHardwareGateway`** — Simplified hardware gateway using plugin architecture.
- **`FirmwareAdapter`** — HTTP bridge between CQL interpreter and firmware simulator.
- **`PluginStatus`** — Status of a hardware plugin.
- **`HardwareDriverSpec`** — Pluggy hookspec for hardware drivers.
- **`ScaleConfig`** — Scale / range definition for a peripheral parameter.
- **`ConversionConfig`** — Describes how to convert a logical value to a hardware value.
- **`PeripheralConfig`** — Configuration for a single peripheral (sensor / actuator).
- **`PluginConfig`** — Standardized configuration schema for hardware plugins.
- **`PluginHealth`** — Health check result for a hardware plugin.
- **`HardwarePlugin`** — Base interface for hardware integration plugins.
- **`ExecutionRequest`** — —
- **`ExecutionStatus`** — —
- **`CommandEnvelope`** — —
- **`PluginRegistry`** — Central registry for hardware plugins.
- **`ModbusPlugin`** — Plugin for Waveshare Modbus RTU IO 8CH valve controller.
- **`PiadcPlugin`** — Plugin for piADC (ADS1115) 16-bit ADC sensor.
- **`LungPlugin`** — Plugin for Pololu Tic T249 stepper motor (artificial lung).
- **`GpioDriver`** — Driver for direct GPIO control.
- **`SpiDriver`** — SPI driver for HAL.
- **`MqttDriver`** — MQTT driver for the Hardware Abstraction Layer.
- **`MotorPlugin`** — Plugin for DFRobot DRI0050 PWM motor driver.
- **`Step`** — —
- **`ValidationRule`** — —
- **`Goal`** — —
- **`Scenario`** — —
- **`PathEscapeError`** — Raised when a resolved path would escape the base directory.
- **`LogsQueryService`** — Read-only query service for nfo logs SQLite database.
- **`ConnectionManager`** — Tracks connected WebSocket clients and broadcasts messages.
- **`EventServer`** — WebSocket event broker with persistence.
- **`EventStore`** — Append-only event store with optional JSON file persistence.
- **`FileInfo`** — —
- **`FileContent`** — —
- **`ExecutionRequest`** — —
- **`JUnitReporter`** — Generate JUnit XML from a ScriptResult.
- **`DslDialect`** — Supported DSL dialect metadata.
- **`DslItem`** — A reusable schema item visible to editor clients.
- **`DslFunctionBinding`** — Object to function relationship used by visual builders.
- **`DslParamUnitBinding`** — Param to unit relationship used by visual builders.
- **`DslSchema`** — Complete editor schema shared by GUI and runtime tooling.
- **`PeripheralType`** — —
- **`PeripheralStatus`** — —
- **`PeripheralMode`** — —
- **`Peripheral`** — —

### Functions

- `detect_serial_devices()` — Detect available USB-to-serial devices.
- `suggest_modbus_port(devices)` — Suggest Modbus serial port from detected devices.
- `generate_env_content(hardware_mode, modbus_port, piadc_url, motor_url)` — Generate .env file content.
- `setup_env_file(env_path, hardware_mode, modbus_port, force)` — Setup .env file with hardware configuration.
- `load_env_file(env_path)` — Load .env file into environment variables.
- `run_oql_scenario(scenario_path, mode, firmware_url)` — Run OQL scenario with loaded configuration.
- `main()` — —
- `parse_dsl_to_goal_with_issues(dsl, scenario_id)` — Parse DSL and return a runtime goal plus invalid runtime lines.
- `parse_dsl_to_goal(dsl, scenario_id)` — Parse DSL string to a runtime Goal with Steps.
- `exec_action_task(interp, act)` — Execute TASK action.
- `exec_action_save(interp, act)` — Execute SAVE action.
- `parse_wait_secs(raw)` — Parse a WAIT value to seconds. Default unit is ms.
- `exec_action_wait(interp, act)` — Execute WAIT action.
- `exec_action_min_max(interp, act)` — Execute MIN/MAX action.
- `exec_action_val(interp, act)` — Execute VAL action.
- `exec_action_log(interp, act)` — Execute LOG action.
- `exec_action_error(interp, act)` — Execute ERROR action.
- `exec_action_else(interp, act)` — Execute inline ELSE ERROR/INFO/WARNING action.
- `exec_action_sample(interp, act)` — Execute SAMPLE action as dry-run sampling metadata.
- `exec_action_func(interp, act)` — Execute FUNC action using simple arithmetic over literals and variables.
- `exec_action_goto(interp, act)` — Execute GOTO action by skipping the rest of the current goal.
- `exec_action_api(interp, act)` — Execute API_* action with deterministic dry-run responses.
- `exec_action_expect(interp, act)` — Execute EXPECT_* diagnostics as dry-run discovery checks.
- `exec_action_assert(interp, act)` — Execute ASSERT_* actions for dry-run diagnostics and API checks.
- `exec_action_shell(interp, act)` — Execute shell/export helpers in dry-run mode.
- `exec_action_var_set(interp, act)` — Execute VAR assignment action.
- `exec_action_condition(interp, act)` — Execute condition action.
- `exec_action_if_fail_block(interp, act)` — Execute IF_FAIL block when a tracked diagnostic target has failed.
- `exec_action_if_block(interp, act)` — Execute IF block action.
- `exec_action_loop_block(interp, act)` — Execute LOOP block action.
- `exec_action_set(interp, act)` — Execute SET action with intelligent dispatch.
- `exec_action_action(interp, act)` — Execute generic ACTION.
- `safe_eval_condition(expr, context)` — Evaluate a simple comparison expression without using eval().
- `safe_eval(expr, context)` — Evaluate a simple expression safely without using eval().
- `resolve_compare(left, op, right)` — Evaluate a single comparison: left op right.
- `resolve_compare_chain(node, resolve_value)` — Evaluate a chained comparison using the caller's node resolver.
- `parse_cql(source, filename)` — Parse CQL source into AST.
- `validate_cql(doc)` — Validate a parsed CQL document. Returns list of issues.
- `check_firmware_health(url)` — Check firmware health via HTTP API.
- `check_firmware_identify(url)` — Get detailed hardware identification.
- `cmd_health(url)` — Health command — check firmware health, return formatted string.
- `cmd_diagnose(url)` — Full diagnostic command — combines USB + I2C + health + identify.
- `main()` — —
- `cmd_list(args)` — List all registered plugins.
- `cmd_status(args)` — Show status of all plugins.
- `cmd_capabilities(args)` — Show capabilities of a specific plugin.
- `cmd_validate(args)` — Validate plugin configurations.
- `cmd_connect(args)` — Connect to a hardware plugin.
- `cmd_disconnect(args)` — Disconnect from a hardware plugin.
- `cmd_health(args)` — Check health of plugins.
- `cmd_execute(args)` — Execute a command on a hardware plugin.
- `cmd_reload(args)` — Reload plugin configurations from YAML file.
- `cmd_peripherals(args)` — Show peripheral definitions for a plugin (from loaded config).
- `main()` — —
- `interactive_shell(url)` — Run the interactive hardware diagnostic REPL.
- `run_benchmark(url, duration)` — Run HTTP performance benchmark against firmware health endpoint.
- `format_peripheral_table(devices)` — Format USB devices as an ASCII table.
- `save_diagnostic_report(filename, url)` — Save full diagnostic report as JSON.
- `run_calibration_test(url)` — Run calibration test for all hardware components.
- `slugify(text)` — Create a URL-safe slug from text (handles Polish/German chars).
- `is_pump_output(name)` — Check if output name refers to a pump.
- `is_compressor_output(name)` — Check if output name refers to a compressor.
- `normalize_output_name(name)` — Normalize hardware output name to standard format.
- `normalize_flow_value(raw_value)` — Normalize flow value to standard format (e.g., '5 l/min').
- `normalize_set_value(raw_value)` — Normalize set value to standard format.
- `parse_xml(xml_path)` — Parse c10 XML report file into DeviceReport.
- `generate_dsl(report)` — Generate human-readable DSL text from parsed report.
- `generate_cql(report)` — Generate CQL (Connex Query Language) text from parsed report.
- `generate_goals_json(report)` — Generate JSON goals structure for REST API.
- `run_source(source, filename)` — Execute a CQL source string with a configured interpreter.
- `run_single_command(command)` — Execute one OQL command line by wrapping it in a minimal scenario.
- `handle_list_command(argv)` — Handle the 'cmd list' subcommand.
- `execute_command_with_cleanup(args, result, yaml_output, quiet)` — Execute command with continuous mode and cleanup handling.
- `main()` — —
- `output_yaml(data, quiet)` — Output data as YAML to stdout.
- `parse_sensor_overrides(sensor_args)` — Parse `-s name=value` overrides into a sensor mapping.
- `build_result_payload(result)` — Convert a script result into a JSON-friendly payload.
- `normalize_target_name(target)` — Normalize a target name for consistent lookup.
- `build_single_command_scenario(command)` — Wrap a single OQL command line in a minimal scenario document.
- `resolve_required_adapter(command)` — Infer the hardware adapter required by a single command, if any.
- `validate_directory(d, interpreter_class)` — Validate all .cql and .oql files in a directory tree.
- `ensure_firmware_running(firmware_url)` — Attempt to start firmware service if it's not available.
- `check_firmware_state(firmware_url, yaml_output, quiet)` — Check firmware health and identify state.
- `check_required_adapter(command, adapters, yaml_output, quiet)` — Check if the required adapter for a command is available.
- `emit_preflight_success(firmware_url, health, identify, required_adapter)` — Emit preflight success output in appropriate format.
- `preflight_hardware(command, firmware_url)` — Check whether the requested command can run on real hardware.
- `create_file_parser()` — Create argument parser for file-based execution.
- `create_cmd_parser()` — Create argument parser for single command execution.
- `run_file_mode(args)` — Execute file-based CQL/OQL processing.
- `run_cmd_mode(argv)` — Execute single command mode.
- `main()` — Main entry point - dispatches to appropriate mode.
- `list_usb_serial_devices()` — Detect all USB-to-serial devices.
- `list_i2c_buses()` — List available I2C buses.
- `detect_chips_on_i2c(bus)` — Detect chips on I2C bus using i2cdetect.
- `get_settings()` — Get the application settings instance.
- `get_hardware_config(device_id)` — Return the PluginConfig for *device_id* (loaded from unified YAML).
- `register_hardware_config(config)` — No-op shim — configs live in the unified YAML now.
- `load_config_from_yaml(config_path)` — Load plugin configs from the **unified** YAML format.
- `resolve_target_to_plugin(target)` — Resolve a DSL target name to its plugin ID.
- `register_custom_mapping(target, plugin_id)` — Register a custom peripheral-to-plugin mapping.
- `get_all_mappings()` — Get all peripheral-to-plugin mappings.
- `generate_dynamic_valve_mappings(max_valve_count)` — Generate dynamic valve mappings for numbered valves.
- `list_serial_ports()` — Return USB serial ports with best-effort metadata.
- `probe_waveshare_modbus(preferred_port, preferred_baud, preferred_parity, timeout)` — Probe serial ports and return the first working Modbus RTU configuration.
- `get_pluggy_manager()` — Return the global pluggy PluginManager for third-party drivers.
- `dynamic_peripheral_model(peripheral)` — Generate a runtime Pydantic model from a ``PeripheralConfig``.
- `build_dynamic_schema_models(config_path)` — Build runtime Pydantic schema models for all plugins/peripherals declared in ``oqlos.yaml``.
- `http_health_check(client, base_url, label)` — Shared HTTP health check — GET {base_url}/health.
- `not_connected_health(label)` — Return error health when plugin has no active client.
- `health_check_exception(exc)` — Return error health for unexpected exceptions.
- `http_disconnect(client, label)` — Close an httpx client (if open) and log disconnect.
- `load_sample_scenarios(state_manager)` — Load sample scenarios for testing
- `serve_html_page(file_path)` — Serve a static HTML file when present, else return a small fallback page.
- `make_collection_route(route_name, get_collection)` — Create a trivial list-all route for dict-backed state collections.
- `list_files(base, pattern, recursive)` — List files (not directories) matching *pattern* under *base*.
- `iter_entries(base)` — Iterate over direct children of *base*, yielding info dicts.
- `read_file(base, rel)` — Read a file safely within *base*.
- `write_file(base, rel, content)` — Write *content* to a file safely within *base*.
- `resolve_logs_db_path(project_root_fallback)` — Resolve logs.db path from environment or default.
- `create_nfo_setup()` — Factory that creates a service-specific setup_nfo() function.
- `main()` — —
- `build_version_payload(service_name, version)` — Build a canonical JSON payload for a version endpoint.
- `create_version_router()` — Create a FastAPI router that exposes a single `/version` endpoint.
- `get_logger(name)` — —
- `clean_version(raw)` — Normalize a raw version string to plain semver text.
- `resolve_release_version(project_root)` — Resolve the release version for the given project root.
- `main()` — —
- `list_plugins()` — List all registered hardware plugins.
- `get_plugin_status()` — Get overall status of all plugins.
- `get_plugin_info(plugin_id)` — Get information about a specific plugin.
- `get_plugin_health(plugin_id)` — Get health status of a specific plugin.
- `connect_plugin(plugin_id, config)` — Connect to a hardware plugin.
- `disconnect_plugin(plugin_id)` — Disconnect from a hardware plugin.
- `execute_plugin_command(plugin_id, command)` — Execute a command on a hardware plugin.
- `validate_plugin_configs(configs)` — Validate configurations for multiple plugins.
- `get_state()` — Get current system state
- `stream_values(param, min, max, period)` — SSE endpoint for live value streaming.
- `get_current_value(param)` — Get current value for a parameter (single request, not streaming).
- `get_sim_state()` — Get simulation state in list format
- `get_variables_alias()` — Get variables (alias for fetch)
- `fetch_variables(source)` — Fetch variables (Peripheral State Table) from backend DB; tolerate dev HTML by returning [].
- `fetch_protocol_steps(scenario, source)` — Fetch protocol steps for preview.
- `post_commands(env, background_tasks)` — Command bus endpoint used by frontend.
- `start_execution(request)` — Start scenario execution
- `execute_step(payload)` — Execute a single DSL step within the current (or new) execution.
- `get_execution(execution_id)` — Get execution status
- `get_execution_projection()` — Return a lightweight execution projection used by the frontend polling fallback.
- `get_execution_status()` — Return textual logs and status for polling fallback when SSE is unavailable.
- `get_execution_logs()` — Return execution logs for frontend polling.
- `execution_stream(scenario)` — Stream execution events for frontend polling fallback
- `execution_logs_stream(scenario)` — Stream execution logs for terminal view
- `get_peripheral(peripheral_id)` — Get specific peripheral
- `update_peripheral(peripheral_id, update_data)` — Update peripheral via PUT (for tests)
- `set_peripheral(peripheral_id, value, mode)` — Update peripheral (manual mode)
- `reset_peripherals()` — Reset all peripherals
- `set_hardware_gateway(gw)` — —
- `hardware_health()` — Return connectivity status for all hardware services.
- `hardware_identify()` — Return full hardware identification: registry + live probe results.
- `set_valve(valve_id, value)` — Directly set a valve (for manual testing).
- `set_pump(power_pct)` — Directly set pump power % (for manual testing).
- `read_sensor(sensor_id)` — Read a sensor value directly from hardware.
- `set_lung(steps, speed, cycles, pause)` — Start artificial lung reciprocating motion (tic249 stepper).
- `stop_lung()` — Emergency stop the artificial lung motor.
- `get_logs(level, function, module, q)` — Browse nfo logs from shared SQLite database.
- `get_log_stats()` — Summary statistics from logs database.
- `list_files()` — List all entries in the scenarios directory.
- `read_file_endpoint(file_path)` — Read a file's content.
- `write_file_endpoint(file_path, file_content)` — Write content to a file (creates parent directories as needed).
- `execute_scenario(request)` — Execute a scenario file using oqlos runtime.
- `index_page()` — Serve the firmware UI (index.html) at root
- `editor_page()` — Serve the scenario editor UI
- `health_check()` — Health check endpoint for tests and frontend compatibility probes.
- `status()` — —
- `websocket_endpoint(websocket)` — —
- `run()` — Entry point for ``oqlos-server`` console script.
- `set_dependencies(sm, orch)` — Set state_manager + orchestrator (called once from main.py).
- `report_junit(result, suite_name)` — Convenience function — wraps JUnitReporter().generate().
- `log_info()` — —
- `log_warn()` — —
- `log_error()` — —
- `detect_usb_peripherals()` — —
- `detect_i2c_buses()` — —
- `check_firmware_health()` — —
- `run_smoke_test()` — —
- `run_calibration()` — —
- `generate_report()` — —
- `full_diagnostic()` — —
- `main()` — —
- `get_default_dsl_schema()` — Return the canonical cross-project schema used by editor clients.
- `get_scenario(scenario_id)` — Get specific scenario
- `fetch_scenarios(source)` — Fetch scenarios from backend DB or external JSON and normalize shape.
- `register_dsl(payload)` — Register one or many scenarios defined as DSL strings.


## Project Structure

📦 `oqlos`
📦 `oqlos.api`
📄 `oqlos.api.editor` (5 functions, 3 classes)
📄 `oqlos.api.execution` (16 functions)
📄 `oqlos.api.hardware` (16 functions)
📄 `oqlos.api.logs` (3 functions)
📄 `oqlos.api.main` (6 functions)
📄 `oqlos.api.peripherals` (4 functions)
📄 `oqlos.api.plugins` (8 functions)
📄 `oqlos.api.scenarios` (16 functions)
📄 `oqlos.api.state` (16 functions)
📦 `oqlos.api.utils`
📄 `oqlos.api.utils.execution_ctrl` (3 functions)
📄 `oqlos.api.version`
📄 `oqlos.config` (1 functions, 1 classes)
📦 `oqlos.core`
📄 `oqlos.core._compare` (2 functions)
📄 `oqlos.core._cql_tokenizer` (25 functions)
📄 `oqlos.core._dsl_helpers` (12 functions)
📄 `oqlos.core._firmware_executor` (9 functions, 1 classes)
📄 `oqlos.core._func_resolver` (4 functions)
📄 `oqlos.core._interpreter_actions` (44 functions)
📄 `oqlos.core._line_parsers` (9 functions)
📄 `oqlos.core._sensor_evaluator` (6 functions, 1 classes)
📄 `oqlos.core._value_normalizers` (7 functions, 1 classes)
📄 `oqlos.core.base` (28 functions, 7 classes)
📄 `oqlos.core.cql_parser` (27 functions, 1 classes)
📄 `oqlos.core.executor` (21 functions, 1 classes)
📄 `oqlos.core.interpreter` (38 functions, 1 classes)
📄 `oqlos.core.parser` (5 functions)
📄 `oqlos.core.safe_eval` (10 functions, 1 classes)
📄 `oqlos.core.state` (3 functions, 1 classes)
📦 `oqlos.dsl`
📄 `oqlos.dsl.schema` (6 functions, 5 classes)
📦 `oqlos.hardware`
📄 `oqlos.hardware.config_schema` (3 functions, 1 classes)
📄 `oqlos.hardware.discovery` (8 functions)
📦 `oqlos.hardware.drivers`
📄 `oqlos.hardware.drivers.gpio` (7 functions, 1 classes)
📄 `oqlos.hardware.drivers.mqtt` (9 functions, 1 classes)
📄 `oqlos.hardware.drivers.spi` (7 functions, 1 classes)
📄 `oqlos.hardware.firmware_adapter` (23 functions, 1 classes)
📄 `oqlos.hardware.gateway` (25 functions, 5 classes)
📄 `oqlos.hardware.peripheral_mapping` (4 functions)
📄 `oqlos.hardware.plugin_gateway` (14 functions, 1 classes)
📦 `oqlos.hardware.plugins`
📄 `oqlos.hardware.plugins._shared` (4 functions)
📄 `oqlos.hardware.plugins.base` (19 functions, 8 classes)
📄 `oqlos.hardware.plugins.lung` (17 functions, 1 classes)
📄 `oqlos.hardware.plugins.modbus` (7 functions, 1 classes)
📄 `oqlos.hardware.plugins.motor` (17 functions, 1 classes)
📄 `oqlos.hardware.plugins.piadc` (7 functions, 1 classes)
📄 `oqlos.hardware.plugins.registry` (14 functions, 1 classes)
📄 `oqlos.hardware.protocol` (6 functions, 2 classes)
📄 `oqlos.hardware.registry` (3 functions, 1 classes)
📦 `oqlos.ide`
📦 `oqlos.models`
📄 `oqlos.models.dsl_models` (8 classes)
📄 `oqlos.models.execution` (3 classes)
📄 `oqlos.models.peripheral` (4 classes)
📄 `oqlos.models.scenario` (4 classes)
📦 `oqlos.reporters`
📄 `oqlos.reporters.junit` (3 functions, 1 classes)
📦 `oqlos.shared`
📄 `oqlos.shared._endpoint_helpers` (2 functions)
📄 `oqlos.shared.config_factory` (1 functions)
📄 `oqlos.shared.event_server` (11 functions, 2 classes)
📄 `oqlos.shared.event_store` (10 functions, 1 classes)
📄 `oqlos.shared.file_ops` (5 functions, 1 classes)
📄 `oqlos.shared.logger` (1 functions)
📄 `oqlos.shared.logs_query` (5 functions, 1 classes)
📄 `oqlos.shared.release_version` (7 functions)
📄 `oqlos.shared.version_endpoint` (2 functions)
📦 `oqlos.tools`
📦 `oqlos.tools.cql_cli` (2 functions)
📄 `oqlos.tools.cql_cli.commands` (5 functions)
📄 `oqlos.tools.cql_cli.main` (5 functions)
📄 `oqlos.tools.cql_cli.preflight` (10 functions)
📄 `oqlos.tools.cql_cli.utils` (10 functions)
📦 `oqlos.tools.hardware_diagnose`
📄 `oqlos.tools.hardware_diagnose.__main__` (5 functions)
📄 `oqlos.tools.hardware_diagnose.benchmark` (1 functions)
📄 `oqlos.tools.hardware_diagnose.calibration` (4 functions)
📄 `oqlos.tools.hardware_diagnose.discovery` (5 functions, 1 classes)
📄 `oqlos.tools.hardware_diagnose.health` (5 functions)
📄 `oqlos.tools.hardware_diagnose.report` (2 functions)
📄 `oqlos.tools.hardware_diagnose.shell` (5 functions)
📄 `oqlos.tools.plugin_cli` (13 functions)
📦 `oqlos.tools.xml_import`
📄 `oqlos.tools.xml_import._utils` (6 functions)
📄 `oqlos.tools.xml_import.generators` (18 functions)
📄 `oqlos.tools.xml_import.models` (5 classes)
📄 `oqlos.tools.xml_import.parser` (6 functions)
📦 `oqlos.utils`
📄 `oqlos.utils.sample_data` (1 functions)
📄 `project`
📄 `scripts.hardware-check` (11 functions)
📄 `setup_hardware_and_run_oql` (7 functions)

## Requirements

- Python >= >=3.10
- fastapi >=0.110- uvicorn >=0.28- pydantic >=2.0- pydantic-settings >=2.2.0- pyserial >=3.5- pymodbus >=3.6- httpx >=0.25- nfo >=0.2.3- goal >=2.1.0- costs >=0.1.20- pfix >=0.1.60- paho-mqtt >=1.6.1- pluggy >=1.4- PyYAML >=6.0

## Contributing

**Contributors:**
- Tom Softreck <tom@sapletta.com>
- Tom Sapletta <tom-sapletta-com@users.noreply.github.com>

We welcome contributions! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/oqlos/oqlos
cd oqlos

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest
```

## Documentation

- 📖 [Full Documentation](https://github.com/oqlos/oqlos/tree/main/docs) — API reference, module docs, architecture
- 🚀 [Getting Started](https://github.com/oqlos/oqlos/blob/main/docs/getting-started.md) — Quick start guide
- 📚 [API Reference](https://github.com/oqlos/oqlos/blob/main/docs/api.md) — Complete API documentation
- 🔧 [Configuration](https://github.com/oqlos/oqlos/blob/main/docs/configuration.md) — Configuration options
- 💡 [Examples](./examples) — Usage examples and code samples

### Generated Files

| Output | Description | Link |
|--------|-------------|------|
| `README.md` | Project overview (this file) | — |
| `docs/api.md` | Consolidated API reference | [View](./docs/api.md) |
| `docs/modules.md` | Module reference with metrics | [View](./docs/modules.md) |
| `docs/architecture.md` | Architecture with diagrams | [View](./docs/architecture.md) |
| `docs/dependency-graph.md` | Dependency graphs | [View](./docs/dependency-graph.md) |
| `docs/coverage.md` | Docstring coverage report | [View](./docs/coverage.md) |
| `docs/getting-started.md` | Getting started guide | [View](./docs/getting-started.md) |
| `docs/configuration.md` | Configuration reference | [View](./docs/configuration.md) |
| `docs/api-changelog.md` | API change tracking | [View](./docs/api-changelog.md) |
| `CONTRIBUTING.md` | Contribution guidelines | [View](./CONTRIBUTING.md) |
| `examples/` | Usage examples | [Browse](./examples) |
| `mkdocs.yml` | MkDocs configuration | — |

<!-- code2docs:end -->
