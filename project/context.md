# System Architecture Analysis

## Overview

- **Project**: .
- **Primary Language**: python
- **Languages**: python: 102, shell: 3
- **Analysis Mode**: static
- **Total Functions**: 775
- **Total Classes**: 86
- **Modules**: 105
- **Entry Points**: 0

## Architecture by Module

### oqlos.core._interpreter_actions
- **Functions**: 48
- **File**: `_interpreter_actions.py`

### oqlos.core.interpreter
- **Functions**: 43
- **Classes**: 1
- **File**: `interpreter.py`

### oqlos.core.cql_parser
- **Functions**: 30
- **Classes**: 1
- **File**: `cql_parser.py`

### oqlos.core.oql_parser
- **Functions**: 29
- **Classes**: 3
- **File**: `oql_parser.py`

### oqlos.core.base
- **Functions**: 28
- **Classes**: 7
- **File**: `base.py`

### oqlos.core._cql_tokenizer
- **Functions**: 25
- **File**: `_cql_tokenizer.py`

### oqlos.hardware.gateway
- **Functions**: 25
- **Classes**: 5
- **File**: `gateway.py`

### oqlos.hardware.firmware_adapter
- **Functions**: 23
- **Classes**: 1
- **File**: `firmware_adapter.py`

### oqlos.core.executor
- **Functions**: 21
- **Classes**: 1
- **File**: `executor.py`

### oqlos.hardware.plugins.base
- **Functions**: 19
- **Classes**: 8
- **File**: `base.py`

### oqlos.tools.xml_import.generators
- **Functions**: 18
- **File**: `generators.py`

### oqlos.hardware.plugins.motor
- **Functions**: 17
- **Classes**: 1
- **File**: `motor.py`

### oqlos.hardware.plugins.lung
- **Functions**: 17
- **Classes**: 1
- **File**: `lung.py`

### oqlos.api.state
- **Functions**: 16
- **File**: `state.py`

### oqlos.api.scenarios
- **Functions**: 16
- **File**: `scenarios.py`

### oqlos.api.execution
- **Functions**: 16
- **File**: `execution.py`

### oqlos.api.hardware
- **Functions**: 16
- **File**: `hardware.py`

### oqlos.core._oql_adapter
- **Functions**: 14
- **Classes**: 1
- **File**: `_oql_adapter.py`

### oqlos.hardware.plugin_gateway
- **Functions**: 14
- **Classes**: 1
- **File**: `plugin_gateway.py`

### oqlos.hardware.plugins.registry
- **Functions**: 14
- **Classes**: 1
- **File**: `registry.py`

## Key Entry Points

Main execution flows into the system:

## Process Flows

Key execution flows identified:

## Key Classes

### oqlos.core.interpreter.CqlInterpreter
> CQL interpreter with three modes:
  - validate: parse + check structure
  - dry-run:  simulate execu
- **Methods**: 46
- **Key Methods**: oqlos.core.interpreter.CqlInterpreter.__init__, oqlos.core.interpreter.CqlInterpreter.sensor_values, oqlos.core.interpreter.CqlInterpreter.sensor_values, oqlos.core.interpreter.CqlInterpreter._firmware, oqlos.core.interpreter.CqlInterpreter._firmware, oqlos.core.interpreter.CqlInterpreter._firmware_url, oqlos.core.interpreter.CqlInterpreter._firmware_url, oqlos.core.interpreter.CqlInterpreter._coerce_float, oqlos.core.interpreter.CqlInterpreter._resolve_peripheral_id, oqlos.core.interpreter.CqlInterpreter._get_pump_flow_full_scale_lpm
- **Inherits**: BaseInterpreter

### oqlos.core.cql_parser._ParseState
> Encapsulates the parsing state to simplify the main loop.
- **Methods**: 26
- **Key Methods**: oqlos.core.cql_parser._ParseState.__init__, oqlos.core.cql_parser._ParseState.parse, oqlos.core.cql_parser._ParseState._peek_next_significant_indent, oqlos.core.cql_parser._ParseState._flush_pending_inline_if, oqlos.core.cql_parser._ParseState._attach_pending_inline_if, oqlos.core.cql_parser._ParseState._get_line_info, oqlos.core.cql_parser._ParseState._process_line, oqlos.core.cql_parser._ParseState._try_skip_block, oqlos.core.cql_parser._ParseState._try_intervals_block, oqlos.core.cql_parser._ParseState._try_top_level

### oqlos.hardware.firmware_adapter.FirmwareAdapter
> HTTP bridge between CQL interpreter and firmware simulator.
- **Methods**: 22
- **Key Methods**: oqlos.hardware.firmware_adapter.FirmwareAdapter.__init__, oqlos.hardware.firmware_adapter.FirmwareAdapter._get_client, oqlos.hardware.firmware_adapter.FirmwareAdapter.close, oqlos.hardware.firmware_adapter.FirmwareAdapter._get_lung_motor_url, oqlos.hardware.firmware_adapter.FirmwareAdapter.is_available, oqlos.hardware.firmware_adapter.FirmwareAdapter._resolve_peripheral, oqlos.hardware.firmware_adapter.FirmwareAdapter.set_peripheral, oqlos.hardware.firmware_adapter.FirmwareAdapter.pump_off, oqlos.hardware.firmware_adapter.FirmwareAdapter.pump_set, oqlos.hardware.firmware_adapter.FirmwareAdapter.valve_open

### oqlos.core.executor.ScenarioOrchestrator
- **Methods**: 17
- **Key Methods**: oqlos.core.executor.ScenarioOrchestrator.__init__, oqlos.core.executor.ScenarioOrchestrator._sanitize_identifier, oqlos.core.executor.ScenarioOrchestrator._build_eval_context, oqlos.core.executor.ScenarioOrchestrator._sanitize_expression, oqlos.core.executor.ScenarioOrchestrator._build_step_plan, oqlos.core.executor.ScenarioOrchestrator._execute_goal_steps, oqlos.core.executor.ScenarioOrchestrator.execute_scenario, oqlos.core.executor.ScenarioOrchestrator.execute_step, oqlos.core.executor.ScenarioOrchestrator._execute_lung_step, oqlos.core.executor.ScenarioOrchestrator._execute_valve_step

### oqlos.hardware.plugins.motor.MotorPlugin
> Plugin for DFRobot DRI0050 PWM motor driver.

Configuration:
    connection_type: "http"
    connect
- **Methods**: 17
- **Key Methods**: oqlos.hardware.plugins.motor.MotorPlugin.__init__, oqlos.hardware.plugins.motor.MotorPlugin.validate_config, oqlos.hardware.plugins.motor.MotorPlugin.connect, oqlos.hardware.plugins.motor.MotorPlugin.disconnect, oqlos.hardware.plugins.motor.MotorPlugin.health_check, oqlos.hardware.plugins.motor.MotorPlugin._validate_power_pct, oqlos.hardware.plugins.motor.MotorPlugin._handle_set_speed_http, oqlos.hardware.plugins.motor.MotorPlugin._handle_set_speed_cli, oqlos.hardware.plugins.motor.MotorPlugin._handle_set_speed_modbus, oqlos.hardware.plugins.motor.MotorPlugin._handle_stop_http
- **Inherits**: HardwarePlugin

### oqlos.hardware.plugins.lung.LungPlugin
> Plugin for Pololu Tic T249 stepper motor (artificial lung).

Configuration:
    connection_type: "ht
- **Methods**: 17
- **Key Methods**: oqlos.hardware.plugins.lung.LungPlugin.__init__, oqlos.hardware.plugins.lung.LungPlugin.validate_config, oqlos.hardware.plugins.lung.LungPlugin.connect, oqlos.hardware.plugins.lung.LungPlugin.disconnect, oqlos.hardware.plugins.lung.LungPlugin.health_check, oqlos.hardware.plugins.lung.LungPlugin._handle_reciprocate_http, oqlos.hardware.plugins.lung.LungPlugin._handle_reciprocate_usb, oqlos.hardware.plugins.lung.LungPlugin._handle_stop_http, oqlos.hardware.plugins.lung.LungPlugin._handle_stop_usb, oqlos.hardware.plugins.lung.LungPlugin._handle_move_http
- **Inherits**: HardwarePlugin

### oqlos.hardware.plugin_gateway.PluginHardwareGateway
> Simplified hardware gateway using plugin architecture.

Instead of hardcoded adapters, this gateway 
- **Methods**: 15
- **Key Methods**: oqlos.hardware.plugin_gateway.PluginHardwareGateway.__init__, oqlos.hardware.plugin_gateway.PluginHardwareGateway._load_hardware_schema, oqlos.hardware.plugin_gateway.PluginHardwareGateway._load_plugin_configs, oqlos.hardware.plugin_gateway.PluginHardwareGateway._create_default_configs, oqlos.hardware.plugin_gateway.PluginHardwareGateway._parse_plugin_configs, oqlos.hardware.plugin_gateway.PluginHardwareGateway.ensure_initialized, oqlos.hardware.plugin_gateway.PluginHardwareGateway._initialize_plugins, oqlos.hardware.plugin_gateway.PluginHardwareGateway.is_real, oqlos.hardware.plugin_gateway.PluginHardwareGateway.set_valve, oqlos.hardware.plugin_gateway.PluginHardwareGateway.set_pump

### oqlos.hardware.plugins.registry.PluginRegistry
> Central registry for hardware plugins.

Manages:
- Plugin discovery and registration
- Plugin lifecy
- **Methods**: 14
- **Key Methods**: oqlos.hardware.plugins.registry.PluginRegistry.register, oqlos.hardware.plugins.registry.PluginRegistry.unregister, oqlos.hardware.plugins.registry.PluginRegistry.get_plugin_class, oqlos.hardware.plugins.registry.PluginRegistry.list_plugins, oqlos.hardware.plugins.registry.PluginRegistry.create_instance, oqlos.hardware.plugins.registry.PluginRegistry.get_instance, oqlos.hardware.plugins.registry.PluginRegistry.connect_plugin, oqlos.hardware.plugins.registry.PluginRegistry.disconnect_plugin, oqlos.hardware.plugins.registry.PluginRegistry.health_check, oqlos.hardware.plugins.registry.PluginRegistry.health_check_all

### oqlos.shared.event_store.EventStore
> Append-only event store with optional JSON file persistence.
- **Methods**: 11
- **Key Methods**: oqlos.shared.event_store.EventStore.__init__, oqlos.shared.event_store.EventStore.append, oqlos.shared.event_store.EventStore.get_all, oqlos.shared.event_store.EventStore.get_recent, oqlos.shared.event_store.EventStore.get_by_correlation, oqlos.shared.event_store.EventStore.clear, oqlos.shared.event_store.EventStore.to_json, oqlos.shared.event_store.EventStore.from_json, oqlos.shared.event_store.EventStore.count, oqlos.shared.event_store.EventStore._save

### oqlos.core.base.InterpreterOutput
> Collects interpreter output lines for display or testing, and optionally broadcasts events.
- **Methods**: 10
- **Key Methods**: oqlos.core.base.InterpreterOutput.__init__, oqlos.core.base.InterpreterOutput.emit, oqlos.core.base.InterpreterOutput._broadcast_event, oqlos.core.base.InterpreterOutput.info, oqlos.core.base.InterpreterOutput.ok, oqlos.core.base.InterpreterOutput.fail, oqlos.core.base.InterpreterOutput.warn, oqlos.core.base.InterpreterOutput.error, oqlos.core.base.InterpreterOutput.step, oqlos.core.base.InterpreterOutput.output_yaml

### oqlos.hardware.plugins.base.HardwarePlugin
> Base interface for hardware integration plugins.

Each plugin must:
- Define its configuration schem
- **Methods**: 10
- **Key Methods**: oqlos.hardware.plugins.base.HardwarePlugin.__init__, oqlos.hardware.plugins.base.HardwarePlugin.connect, oqlos.hardware.plugins.base.HardwarePlugin.disconnect, oqlos.hardware.plugins.base.HardwarePlugin.health_check, oqlos.hardware.plugins.base.HardwarePlugin.validate_config, oqlos.hardware.plugins.base.HardwarePlugin.execute_command, oqlos.hardware.plugins.base.HardwarePlugin.get_capabilities, oqlos.hardware.plugins.base.HardwarePlugin.status, oqlos.hardware.plugins.base.HardwarePlugin.is_connected, oqlos.hardware.plugins.base.HardwarePlugin.__repr__
- **Inherits**: ABC

### oqlos.core._firmware_executor.FirmwareExecutor
> Executes hardware actions via plugin gateway or legacy firmware.
- **Methods**: 9
- **Key Methods**: oqlos.core._firmware_executor.FirmwareExecutor.__init__, oqlos.core._firmware_executor.FirmwareExecutor._get_firmware, oqlos.core._firmware_executor.FirmwareExecutor.resolve_peripheral_id, oqlos.core._firmware_executor.FirmwareExecutor.normalize_peripheral_value, oqlos.core._firmware_executor.FirmwareExecutor.refresh_sensors_from_firmware, oqlos.core._firmware_executor.FirmwareExecutor.execute_firmware_action, oqlos.core._firmware_executor.FirmwareExecutor._execute_plugin_action, oqlos.core._firmware_executor.FirmwareExecutor._execute_legacy_firmware_action, oqlos.core._firmware_executor.FirmwareExecutor.exec_set_peripheral

### oqlos.hardware.drivers.mqtt.MqttDriver
> MQTT driver for the Hardware Abstraction Layer.
Mapped to ProtocolType.MQTT.
- **Methods**: 9
- **Key Methods**: oqlos.hardware.drivers.mqtt.MqttDriver.__init__, oqlos.hardware.drivers.mqtt.MqttDriver.connect, oqlos.hardware.drivers.mqtt.MqttDriver._on_connect, oqlos.hardware.drivers.mqtt.MqttDriver._on_message, oqlos.hardware.drivers.mqtt.MqttDriver.read, oqlos.hardware.drivers.mqtt.MqttDriver.write, oqlos.hardware.drivers.mqtt.MqttDriver.discover, oqlos.hardware.drivers.mqtt.MqttDriver.health_check, oqlos.hardware.drivers.mqtt.MqttDriver.disconnect
- **Inherits**: HardwareProtocol

### oqlos.hardware.gateway.HardwareGateway
> Single entry-point for all physical hardware I/O.

In *mock* mode every call is a no-op that logs th
- **Methods**: 8
- **Key Methods**: oqlos.hardware.gateway.HardwareGateway.__init__, oqlos.hardware.gateway.HardwareGateway.is_real, oqlos.hardware.gateway.HardwareGateway.set_valve, oqlos.hardware.gateway.HardwareGateway.set_pump, oqlos.hardware.gateway.HardwareGateway.read_sensor, oqlos.hardware.gateway.HardwareGateway.set_lung, oqlos.hardware.gateway.HardwareGateway.stop_lung, oqlos.hardware.gateway.HardwareGateway.health

### oqlos.core.base.VariableStore
> Hierarchical key-value store with interpolation support.
- **Methods**: 7
- **Key Methods**: oqlos.core.base.VariableStore.__init__, oqlos.core.base.VariableStore.set, oqlos.core.base.VariableStore.get, oqlos.core.base.VariableStore.has, oqlos.core.base.VariableStore.all, oqlos.core.base.VariableStore.clear, oqlos.core.base.VariableStore.interpolate

### oqlos.core._value_normalizers.ValueNormalizer
> Normalizes DSL values to hardware-compatible formats.
- **Methods**: 7
- **Key Methods**: oqlos.core._value_normalizers.ValueNormalizer.__init__, oqlos.core._value_normalizers.ValueNormalizer.coerce_float, oqlos.core._value_normalizers.ValueNormalizer._get_pump_flow_full_scale_lpm, oqlos.core._value_normalizers.ValueNormalizer.normalize_pump_power, oqlos.core._value_normalizers.ValueNormalizer.normalize_valve_value, oqlos.core._value_normalizers.ValueNormalizer.normalize_lung_value, oqlos.core._value_normalizers.ValueNormalizer.coerce_generic_peripheral_value

### oqlos.hardware.plugins.modbus.ModbusPlugin
> Plugin for Waveshare Modbus RTU IO 8CH valve controller.

Configuration:
    connection_type: "modbu
- **Methods**: 7
- **Key Methods**: oqlos.hardware.plugins.modbus.ModbusPlugin.__init__, oqlos.hardware.plugins.modbus.ModbusPlugin.validate_config, oqlos.hardware.plugins.modbus.ModbusPlugin.connect, oqlos.hardware.plugins.modbus.ModbusPlugin.disconnect, oqlos.hardware.plugins.modbus.ModbusPlugin.health_check, oqlos.hardware.plugins.modbus.ModbusPlugin.execute_command, oqlos.hardware.plugins.modbus.ModbusPlugin.get_capabilities
- **Inherits**: HardwarePlugin

### oqlos.hardware.plugins.piadc.PiadcPlugin
> Plugin for piADC (ADS1115) 16-bit ADC sensor.

Configuration:
    connection_type: "http"
    connec
- **Methods**: 7
- **Key Methods**: oqlos.hardware.plugins.piadc.PiadcPlugin.__init__, oqlos.hardware.plugins.piadc.PiadcPlugin.validate_config, oqlos.hardware.plugins.piadc.PiadcPlugin.connect, oqlos.hardware.plugins.piadc.PiadcPlugin.disconnect, oqlos.hardware.plugins.piadc.PiadcPlugin.health_check, oqlos.hardware.plugins.piadc.PiadcPlugin.execute_command, oqlos.hardware.plugins.piadc.PiadcPlugin.get_capabilities
- **Inherits**: HardwarePlugin

### oqlos.hardware.drivers.gpio.GpioDriver
> Driver for direct GPIO control.
Supports basic I/O operations and edge detection.
- **Methods**: 7
- **Key Methods**: oqlos.hardware.drivers.gpio.GpioDriver.__init__, oqlos.hardware.drivers.gpio.GpioDriver.connect, oqlos.hardware.drivers.gpio.GpioDriver.read, oqlos.hardware.drivers.gpio.GpioDriver.write, oqlos.hardware.drivers.gpio.GpioDriver.discover, oqlos.hardware.drivers.gpio.GpioDriver.health_check, oqlos.hardware.drivers.gpio.GpioDriver.disconnect
- **Inherits**: HardwareProtocol

### oqlos.hardware.drivers.spi.SpiDriver
> SPI driver for HAL.
Address format: "bus.device" (e.g. "0.0")
- **Methods**: 7
- **Key Methods**: oqlos.hardware.drivers.spi.SpiDriver.__init__, oqlos.hardware.drivers.spi.SpiDriver.connect, oqlos.hardware.drivers.spi.SpiDriver.read, oqlos.hardware.drivers.spi.SpiDriver.write, oqlos.hardware.drivers.spi.SpiDriver.discover, oqlos.hardware.drivers.spi.SpiDriver.health_check, oqlos.hardware.drivers.spi.SpiDriver.disconnect
- **Inherits**: HardwareProtocol

## Data Transformation Functions

Key functions that process and transform data:

### oqlos.core._dsl_helpers._parse_numeric_value
> Extract a numeric value from DSL snippets like `5 bar` or `7.5l`.
- **Output to**: re.search, float, None.replace, match.group, value.is_integer

### oqlos.core._interpreter_actions.parse_wait_secs
> Parse a WAIT value to seconds. Default unit is ms.
- **Output to**: None.strip, re.search, float, low.replace, match.group

### oqlos.core.oql_parser.parse_duration
> Parse ``3s``, ``500ms``, ``3000`` (bare number defaults to ``ms``).
- **Output to**: DUR_RE.match, ValueError, oqlos.core.oql_parser.to_num, match.group, match.group

### oqlos.core.oql_parser.parse_SET
- **Output to**: oqlos.core.oql_parser._require, oqlos.core.oql_parser._split_value_unit, OqlCmd

### oqlos.core.oql_parser.parse_GET
- **Output to**: oqlos.core.oql_parser._require, OqlCmd

### oqlos.core.oql_parser.parse_WAIT
- **Output to**: oqlos.core.oql_parser._require, oqlos.core.oql_parser.parse_duration, oqlos.core.oql_parser.duration_to_ms, OqlCmd

### oqlos.core.oql_parser.parse_SAVE
- **Output to**: oqlos.core.oql_parser._require, OqlCmd

### oqlos.core.oql_parser.parse_CHECK
- **Output to**: CHECK_RE.match, OqlCmd, rest.strip, ValueError, oqlos.core.oql_parser.to_num

### oqlos.core.oql_parser.parse_IF
- **Output to**: IF_RE.match, OqlCmd, rest.strip, ValueError, match.group

### oqlos.core.oql_parser.parse_MIN
- **Output to**: oqlos.core.oql_parser._require, oqlos.core.oql_parser._split_value_unit, OqlCmd

### oqlos.core.oql_parser.parse_MAX
- **Output to**: oqlos.core.oql_parser._require, oqlos.core.oql_parser._split_value_unit, OqlCmd

### oqlos.core.oql_parser.parse_SAMPLE
- **Output to**: oqlos.core.oql_parser._require, None.upper, OqlCmd, ValueError, len

### oqlos.core.oql_parser.parse_LOG
- **Output to**: None.join, OqlCmd

### oqlos.core.oql_parser.parse_ERROR
- **Output to**: None.join, OqlCmd

### oqlos.core.oql_parser.parse_CORRECT
- **Output to**: None.join, OqlCmd

### oqlos.core.oql_parser.parse_CALL
- **Output to**: oqlos.core.oql_parser._require, OqlCmd

### oqlos.core.oql_parser.parse_INCLUDE
- **Output to**: oqlos.core.oql_parser._require, OqlCmd

### oqlos.core.oql_parser.parse_FUNC_CALL
- **Output to**: oqlos.core.oql_parser._require, OqlCmd

### oqlos.core.oql_parser.parse_oql
> Parse OQL source into an :class:`OqlDoc`.

The parser never raises — all problems are collected in
:
- **Output to**: OqlDoc, enumerate, text.splitlines, raw.strip, BLOCK_RE.match

### oqlos.core.oql_parser.format_doc
> Pretty-print for ad-hoc debugging.
- **Output to**: None.join, lines.append, doc.meta.items, lines.append, lines.append

### oqlos.core.parser._dispatch_simple_parser
> Dispatch to the appropriate simple-line parser.
- **Output to**: oqlos.core._line_parsers._parse_task_part, oqlos.core._line_parsers._parse_set_line, oqlos.core._line_parsers._parse_pump_line

### oqlos.core.parser._parse_runtime_line
> Parse one runtime-relevant DSL line into executable firmware steps.
- **Output to**: oqlos.core._dsl_helpers._normalize_quote_syntax, re.match, re.match, oqlos.core._func_resolver._parse_func_call, oqlos.core.parser._try_action_or_condition

### oqlos.core.parser.parse_dsl_to_goal_with_issues
> Parse DSL and return a runtime goal plus invalid runtime lines.
- **Output to**: oqlos.core._func_resolver._collect_function_definitions, enumerate, Goal, isinstance, None.rstrip

### oqlos.core.parser.parse_dsl_to_goal
> Parse DSL string to a runtime Goal with Steps.

DSL supported forms:
  - GOAL: <name>
  - → <Action>
- **Output to**: oqlos.core.parser.parse_dsl_to_goal_with_issues

### oqlos.core._func_resolver._parse_func_call
> Expand an in-goal FUNC call into its defined runtime steps.
- **Output to**: oqlos.core._func_resolver._extract_func_name, oqlos.core._func_resolver._guard_recursion, func_defs.get, parse_line_fn

## Public API Surface

Functions exposed as public API (no underscore prefix):

- `oqlos.dsl.schema.get_default_dsl_schema` - 75 calls
- `oqlos.core.oql_parser.parse_oql` - 66 calls
- `oqlos.hardware.firmware_adapter.FirmwareAdapter.set_peripheral` - 53 calls
- `oqlos.tools.plugin_cli.main` - 36 calls
- `oqlos.tools.hardware_diagnose.__main__.main` - 34 calls
- `oqlos.reporters.html_report.render_html_report` - 25 calls
- `setup_hardware_and_run_oql.run_oql_scenario` - 24 calls
- `oqlos.core._oql_adapter.oql_doc_to_cql` - 24 calls
- `oqlos.reporters.json_reporter.report_json` - 24 calls
- `oqlos.core.parser.parse_dsl_to_goal_with_issues` - 21 calls
- `oqlos.tools.xml_import.generators.generate_dsl` - 21 calls
- `oqlos.tools.cql_cli.commands.handle_list_command` - 21 calls
- `oqlos.tools.hardware_diagnose.health.cmd_diagnose` - 20 calls
- `oqlos.shared.logs_query.LogsQueryService.query_logs` - 20 calls
- `oqlos.core._interpreter_actions.exec_action_shell` - 19 calls
- `oqlos.tools.xml_import.generators.generate_cql` - 19 calls
- `setup_hardware_and_run_oql.main` - 18 calls
- `oqlos.tools.plugin_cli.cmd_peripherals` - 18 calls
- `oqlos.utils.sample_data.load_sample_scenarios` - 18 calls
- `oqlos.tools.xml_import._utils.normalize_set_value` - 17 calls
- `oqlos.tools.xml_import.generators.generate_goals_json` - 17 calls
- `setup_hardware_and_run_oql.setup_env_file` - 16 calls
- `oqlos.tools.xml_import.parser.parse_xml` - 16 calls
- `oqlos.hardware.discovery.list_serial_ports` - 16 calls
- `oqlos.core._interpreter_actions.exec_action_func` - 15 calls
- `oqlos.tools.hardware_diagnose.benchmark.run_benchmark` - 15 calls
- `oqlos.tools.cql_cli.utils.validate_directory` - 15 calls
- `oqlos.hardware.firmware_adapter.FirmwareAdapter.read_sensor` - 15 calls
- `oqlos.hardware.plugins.modbus.ModbusPlugin.connect` - 15 calls
- `oqlos.api.scenarios.fetch_scenarios` - 15 calls
- `oqlos.api.hardware.hardware_identify` - 15 calls
- `oqlos.reporters.junit.JUnitReporter.generate` - 15 calls
- `oqlos.core.oql_parser.tokenize` - 14 calls
- `oqlos.tools.xml_import._utils.normalize_flow_value` - 14 calls
- `oqlos.tools.cql_cli.preflight.check_firmware_state` - 14 calls
- `oqlos.core.executor.ScenarioOrchestrator.execute_scenario` - 14 calls
- `oqlos.hardware.plugins.modbus.ModbusPlugin.execute_command` - 14 calls
- `oqlos.api.execution.execute_step` - 14 calls
- `oqlos.api.execution.execution_logs_stream` - 14 calls
- `oqlos.tools.hardware_diagnose.report.save_diagnostic_report` - 13 calls

## System Interactions

How components interact:

```mermaid
graph TD
```

## Reverse Engineering Guidelines

1. **Entry Points**: Start analysis from the entry points listed above
2. **Core Logic**: Focus on classes with many methods
3. **Data Flow**: Follow data transformation functions
4. **Process Flows**: Use the flow diagrams for execution paths
5. **API Surface**: Public API functions reveal the interface

## Context for LLM

Maintain the identified architectural patterns and public API surface when suggesting changes.