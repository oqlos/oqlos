# System Architecture Analysis
<!-- generated in 0.00s -->

## Overview

- **Project**: /home/tom/github/oqlos/oqlos
- **Primary Language**: python
- **Languages**: python: 143, md: 16, yaml: 13, shell: 6, json: 5
- **Analysis Mode**: static
- **Total Functions**: 1441
- **Total Classes**: 111
- **Modules**: 191
- **Entry Points**: 0

## Architecture by Module

### oqlos.api.hardware
- **Functions**: 89
- **File**: `hardware.py`

### oqlos.core._interpreter_actions
- **Functions**: 85
- **File**: `_interpreter_actions.py`

### oqlos.core.interpreter
- **Functions**: 47
- **Classes**: 1
- **File**: `interpreter.py`

### oqlos.core.oql_parser
- **Functions**: 43
- **Classes**: 3
- **File**: `oql_parser.py`

### scripts.oql_v2_to_v4_migrate_db
- **Functions**: 43
- **Classes**: 1
- **File**: `oql_v2_to_v4_migrate_db.py`

### oqlos.tools.hardware_diagnose.doctor
- **Functions**: 41
- **File**: `doctor.py`

### oqlos.hardware.transport.mqtt_oql_bridge
- **Functions**: 34
- **Classes**: 6
- **File**: `mqtt_oql_bridge.py`

### oqlos.core.cql_parser
- **Functions**: 30
- **Classes**: 1
- **File**: `cql_parser.py`

### oqlos.hardware.client.tic249_extended
- **Functions**: 30
- **File**: `tic249_extended.py`

### oqlos.hardware.client.proxy
- **Functions**: 29
- **Classes**: 1
- **File**: `proxy.py`

### oqlos.core.base
- **Functions**: 28
- **Classes**: 7
- **File**: `base.py`

### oqlos.core._oql_adapter
- **Functions**: 28
- **Classes**: 1
- **File**: `_oql_adapter.py`

### oqlos.core._cql_tokenizer
- **Functions**: 27
- **File**: `_cql_tokenizer.py`

### oqlos.hardware.diagnosis
- **Functions**: 26
- **Classes**: 3
- **File**: `diagnosis.py`

### oqlos.hardware.firmware_adapter
- **Functions**: 26
- **Classes**: 1
- **File**: `firmware_adapter.py`

### oqlos.hardware.gateway
- **Functions**: 25
- **Classes**: 5
- **File**: `gateway.py`

### oqlos.core.executor
- **Functions**: 21
- **Classes**: 1
- **File**: `executor.py`

### oqlos.hardware.plugin_gateway
- **Functions**: 21
- **Classes**: 1
- **File**: `plugin_gateway.py`

### oqlos.hardware.plugins.base
- **Functions**: 21
- **Classes**: 9
- **File**: `base.py`

### oqlos.tools.xml_import.generators
- **Functions**: 20
- **File**: `generators.py`

## Key Entry Points

Main execution flows into the system:

## Process Flows

Key execution flows identified:

## Key Classes

### oqlos.core.interpreter.CqlInterpreter
> CQL interpreter with three modes:
  - validate: parse + check structure
  - dry-run:  simulate execu
- **Methods**: 50
- **Key Methods**: oqlos.core.interpreter.CqlInterpreter.__init__, oqlos.core.interpreter.CqlInterpreter.sensor_values, oqlos.core.interpreter.CqlInterpreter.sensor_values, oqlos.core.interpreter.CqlInterpreter._firmware, oqlos.core.interpreter.CqlInterpreter._firmware, oqlos.core.interpreter.CqlInterpreter._firmware_url, oqlos.core.interpreter.CqlInterpreter._firmware_url, oqlos.core.interpreter.CqlInterpreter._coerce_float, oqlos.core.interpreter.CqlInterpreter._resolve_peripheral_id, oqlos.core.interpreter.CqlInterpreter._get_pump_flow_full_scale_lpm
- **Inherits**: BaseInterpreter

### oqlos.hardware.client.proxy.OqlosHardwareProxy
- **Methods**: 28
- **Key Methods**: oqlos.hardware.client.proxy.OqlosHardwareProxy.__init__, oqlos.hardware.client.proxy.OqlosHardwareProxy.candidate_bases, oqlos.hardware.client.proxy.OqlosHardwareProxy.proxy_info, oqlos.hardware.client.proxy.OqlosHardwareProxy.close, oqlos.hardware.client.proxy.OqlosHardwareProxy._get_client, oqlos.hardware.client.proxy.OqlosHardwareProxy._proxy_oqlos, oqlos.hardware.client.proxy.OqlosHardwareProxy._proxy_oqlos_request, oqlos.hardware.client.proxy.OqlosHardwareProxy._degraded_oqlos_payload, oqlos.hardware.client.proxy.OqlosHardwareProxy.health, oqlos.hardware.client.proxy.OqlosHardwareProxy.identify

### oqlos.core.cql_parser._ParseState
> Encapsulates the parsing state to simplify the main loop.
- **Methods**: 26
- **Key Methods**: oqlos.core.cql_parser._ParseState.__init__, oqlos.core.cql_parser._ParseState.parse, oqlos.core.cql_parser._ParseState._peek_next_significant_indent, oqlos.core.cql_parser._ParseState._flush_pending_inline_if, oqlos.core.cql_parser._ParseState._attach_pending_inline_if, oqlos.core.cql_parser._ParseState._get_line_info, oqlos.core.cql_parser._ParseState._process_line, oqlos.core.cql_parser._ParseState._try_skip_block, oqlos.core.cql_parser._ParseState._try_intervals_block, oqlos.core.cql_parser._ParseState._try_top_level

### oqlos.hardware.firmware_adapter.FirmwareAdapter
> HTTP bridge between CQL interpreter and firmware simulator.
- **Methods**: 23
- **Key Methods**: oqlos.hardware.firmware_adapter.FirmwareAdapter.__init__, oqlos.hardware.firmware_adapter.FirmwareAdapter._get_client, oqlos.hardware.firmware_adapter.FirmwareAdapter.close, oqlos.hardware.firmware_adapter.FirmwareAdapter._get_lung_motor_url, oqlos.hardware.firmware_adapter.FirmwareAdapter.is_available, oqlos.hardware.firmware_adapter.FirmwareAdapter._resolve_peripheral, oqlos.hardware.firmware_adapter.FirmwareAdapter._raise_if_rejected, oqlos.hardware.firmware_adapter.FirmwareAdapter.set_peripheral, oqlos.hardware.firmware_adapter.FirmwareAdapter.pump_off, oqlos.hardware.firmware_adapter.FirmwareAdapter.pump_set

### oqlos.hardware.plugin_gateway.PluginHardwareGateway
> Simplified hardware gateway using plugin architecture.

Instead of hardcoded adapters, this gateway 
- **Methods**: 22
- **Key Methods**: oqlos.hardware.plugin_gateway.PluginHardwareGateway.__init__, oqlos.hardware.plugin_gateway.PluginHardwareGateway._load_hardware_schema, oqlos.hardware.plugin_gateway.PluginHardwareGateway._parse_plugin_configs, oqlos.hardware.plugin_gateway.PluginHardwareGateway._apply_env_overrides, oqlos.hardware.plugin_gateway.PluginHardwareGateway._apply_plugin_enable_env_overrides, oqlos.hardware.plugin_gateway.PluginHardwareGateway._apply_shared_modbus_bus_env_overrides, oqlos.hardware.plugin_gateway.PluginHardwareGateway._apply_modbus_env_overrides, oqlos.hardware.plugin_gateway.PluginHardwareGateway.modbus_preflight_report, oqlos.hardware.plugin_gateway.PluginHardwareGateway._log_modbus_preflight, oqlos.hardware.plugin_gateway.PluginHardwareGateway.ensure_initialized

### oqlos.hardware.plugins.lung.LungPlugin
> Plugin for Pololu Tic T249 stepper motor (artificial lung).

Configuration:
    connection_type: "ht
- **Methods**: 20
- **Key Methods**: oqlos.hardware.plugins.lung.LungPlugin.__init__, oqlos.hardware.plugins.lung.LungPlugin.validate_config, oqlos.hardware.plugins.lung.LungPlugin.connect, oqlos.hardware.plugins.lung.LungPlugin.disconnect, oqlos.hardware.plugins.lung.LungPlugin._health_check_http, oqlos.hardware.plugins.lung.LungPlugin.health_check, oqlos.hardware.plugins.lung.LungPlugin._runtime_status, oqlos.hardware.plugins.lung.LungPlugin._runtime_block_reason, oqlos.hardware.plugins.lung.LungPlugin._handle_reciprocate_http, oqlos.hardware.plugins.lung.LungPlugin._handle_reciprocate_usb
- **Inherits**: HardwarePlugin

### oqlos.hardware.plugins.motor.MotorPlugin
> Plugin for DFRobot DRI0050 PWM motor driver.

Configuration:
    connection_type: "http"
    connect
- **Methods**: 20
- **Key Methods**: oqlos.hardware.plugins.motor.MotorPlugin.__init__, oqlos.hardware.plugins.motor.MotorPlugin.validate_config, oqlos.hardware.plugins.motor.MotorPlugin.connect, oqlos.hardware.plugins.motor.MotorPlugin.disconnect, oqlos.hardware.plugins.motor.MotorPlugin._health_check_http, oqlos.hardware.plugins.motor.MotorPlugin._health_check_modbus_rtu, oqlos.hardware.plugins.motor.MotorPlugin.health_check, oqlos.hardware.plugins.motor.MotorPlugin._base_url_is_local, oqlos.hardware.plugins.motor.MotorPlugin._validate_power_pct, oqlos.hardware.plugins.motor.MotorPlugin._handle_set_speed_http
- **Inherits**: HardwarePlugin

### oqlos.core.executor.ScenarioOrchestrator
- **Methods**: 17
- **Key Methods**: oqlos.core.executor.ScenarioOrchestrator.__init__, oqlos.core.executor.ScenarioOrchestrator._sanitize_identifier, oqlos.core.executor.ScenarioOrchestrator._build_eval_context, oqlos.core.executor.ScenarioOrchestrator._sanitize_expression, oqlos.core.executor.ScenarioOrchestrator._build_step_plan, oqlos.core.executor.ScenarioOrchestrator._execute_goal_steps, oqlos.core.executor.ScenarioOrchestrator.execute_scenario, oqlos.core.executor.ScenarioOrchestrator.execute_step, oqlos.core.executor.ScenarioOrchestrator._execute_lung_step, oqlos.core.executor.ScenarioOrchestrator._execute_valve_step

### oqlos.hardware.plugins.modbus.ModbusPlugin
> Plugin for Waveshare Modbus RTU IO 8CH valve controller.

Configuration:
    connection_type: "modbu
- **Methods**: 16
- **Key Methods**: oqlos.hardware.plugins.modbus.ModbusPlugin.__init__, oqlos.hardware.plugins.modbus.ModbusPlugin._validate_rtu_params, oqlos.hardware.plugins.modbus.ModbusPlugin._validate_tcp_params, oqlos.hardware.plugins.modbus.ModbusPlugin.validate_config, oqlos.hardware.plugins.modbus.ModbusPlugin.connect, oqlos.hardware.plugins.modbus.ModbusPlugin.disconnect, oqlos.hardware.plugins.modbus.ModbusPlugin._health_check_rtu, oqlos.hardware.plugins.modbus.ModbusPlugin._health_check_tcp, oqlos.hardware.plugins.modbus.ModbusPlugin.health_check, oqlos.hardware.plugins.modbus.ModbusPlugin._execute_set_coil
- **Inherits**: HardwarePlugin

### oqlos.hardware.plugins.modbus_adc.ModbusAdcPlugin
> Plugin for Waveshare Modbus RTU Analog Input 8CH.

The module exposes AI1-AI8 through input register
- **Methods**: 15
- **Key Methods**: oqlos.hardware.plugins.modbus_adc.ModbusAdcPlugin.__init__, oqlos.hardware.plugins.modbus_adc.ModbusAdcPlugin.validate_config, oqlos.hardware.plugins.modbus_adc.ModbusAdcPlugin.connect, oqlos.hardware.plugins.modbus_adc.ModbusAdcPlugin.disconnect, oqlos.hardware.plugins.modbus_adc.ModbusAdcPlugin.health_check, oqlos.hardware.plugins.modbus_adc.ModbusAdcPlugin.execute_command, oqlos.hardware.plugins.modbus_adc.ModbusAdcPlugin._read_registers, oqlos.hardware.plugins.modbus_adc.ModbusAdcPlugin._format_channels, oqlos.hardware.plugins.modbus_adc.ModbusAdcPlugin._format_channel, oqlos.hardware.plugins.modbus_adc.ModbusAdcPlugin._peripheral_for_channel
- **Inherits**: HardwarePlugin

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

### oqlos.hardware.transport.mqtt_oql_bridge._PahoAsyncClient
> Wraps a paho client and bridges its network thread to an asyncio loop.

Subclasses override :meth:`_
- **Methods**: 9
- **Key Methods**: oqlos.hardware.transport.mqtt_oql_bridge._PahoAsyncClient.__init__, oqlos.hardware.transport.mqtt_oql_bridge._PahoAsyncClient.start, oqlos.hardware.transport.mqtt_oql_bridge._PahoAsyncClient.stop, oqlos.hardware.transport.mqtt_oql_bridge._PahoAsyncClient._subscriptions, oqlos.hardware.transport.mqtt_oql_bridge._PahoAsyncClient._last_will, oqlos.hardware.transport.mqtt_oql_bridge._PahoAsyncClient._on_payload, oqlos.hardware.transport.mqtt_oql_bridge._PahoAsyncClient._handle_connect, oqlos.hardware.transport.mqtt_oql_bridge._PahoAsyncClient._handle_message, oqlos.hardware.transport.mqtt_oql_bridge._PahoAsyncClient._publish

### oqlos.hardware.transport.mqtt_oql_bridge.OqlMqttController
> Publishes OQL and awaits a correlated response.
- **Methods**: 9
- **Key Methods**: oqlos.hardware.transport.mqtt_oql_bridge.OqlMqttController.__init__, oqlos.hardware.transport.mqtt_oql_bridge.OqlMqttController._subscriptions, oqlos.hardware.transport.mqtt_oql_bridge.OqlMqttController._on_payload, oqlos.hardware.transport.mqtt_oql_bridge.OqlMqttController._resolve_response, oqlos.hardware.transport.mqtt_oql_bridge.OqlMqttController._fan_out_event, oqlos.hardware.transport.mqtt_oql_bridge.OqlMqttController.execute, oqlos.hardware.transport.mqtt_oql_bridge.OqlMqttController.manage, oqlos.hardware.transport.mqtt_oql_bridge.OqlMqttController.subscribe_events, oqlos.hardware.transport.mqtt_oql_bridge.OqlMqttController.unsubscribe_events
- **Inherits**: _PahoAsyncClient

### oqlos.hardware.transport.mqtt_oql_bridge.OqlMqttAgent
> Subscribes to OQL requests, executes them locally, and replies.

``gateway`` MUST be the already-ini
- **Methods**: 9
- **Key Methods**: oqlos.hardware.transport.mqtt_oql_bridge.OqlMqttAgent.__init__, oqlos.hardware.transport.mqtt_oql_bridge.OqlMqttAgent._subscriptions, oqlos.hardware.transport.mqtt_oql_bridge.OqlMqttAgent._last_will, oqlos.hardware.transport.mqtt_oql_bridge.OqlMqttAgent.start, oqlos.hardware.transport.mqtt_oql_bridge.OqlMqttAgent.stop, oqlos.hardware.transport.mqtt_oql_bridge.OqlMqttAgent._on_payload, oqlos.hardware.transport.mqtt_oql_bridge.OqlMqttAgent._handle_request, oqlos.hardware.transport.mqtt_oql_bridge.OqlMqttAgent._run_manage, oqlos.hardware.transport.mqtt_oql_bridge.OqlMqttAgent._run_oql
- **Inherits**: _PahoAsyncClient

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

## Data Transformation Functions

Key functions that process and transform data:

### oqlos.core.base.BaseInterpreter.parse
> Parse source into an AST / structure.

### oqlos.core._dsl_helpers._parse_numeric_value
> Extract a numeric value from DSL snippets like `5 bar` or `7.5l`.
- **Output to**: re.search, float, None.replace, match.group, value.is_integer

### oqlos.core._cql_tree_builder._parse_metadata_kv
> Parse top-level SCENARIO/DEVICE_TYPE/DEVICE_MODEL/MANUFACTURER lines.
- **Output to**: RE_METADATA_KV.match, m.group, None.strip, None.strip, m.group

### oqlos.core._cql_tree_builder._parse_scenario_line
> Parse @Namespace.Name scenario header.
- **Output to**: RE_SCENARIO.match, None.rsplit, CqlScenario, doc.scenarios.append, m.group

### oqlos.core._cql_tree_builder._parse_scenario_attrs
> Parse scenario-level attributes (description, intervals ref).
- **Output to**: RE_DESC.match, RE_INTERVALS_REF.match, m.group, x.strip, None.split

### oqlos.core._cql_tree_builder._parse_goal_line
> Parse GOAL: (simple CQL) or named goal (ConnectGo 2-space indent).
- **Output to**: RE_CONFIG_SIMPLE.match, RE_GOAL_SIMPLE.match, CqlGoal, RE_CONFIG_NAMED.match, CqlGoal

### oqlos.core._cql_tree_builder._parse_goal_attrs
> Parse goal-level attributes (description, editable, alarm).
- **Output to**: RE_DESC.match, RE_EDITABLE.match, RE_ALARM.match, m.group, m.group

### oqlos.core._cql_tree_builder._parse_step_line
> Parse a numbered step line.
- **Output to**: RE_STEP_NUM.match, CqlStep, m.group, None.strip, m.group

### oqlos.core._cql_tree_builder._parse_action_line
> Try to match any action type and append to *actions_list*.
- **Output to**: RE_DESC.match, parser, actions_list.append

### oqlos.core._interpreter_actions._format_set_command
- **Output to**: oqlos.core._interpreter_actions._oql_quote, oqlos.core._interpreter_actions._oql_quote

### oqlos.core._interpreter_actions.parse_wait_secs
> Parse a WAIT value to seconds. Default unit is ms.
- **Output to**: None.strip, re.search, float, low.replace, match.group

### oqlos.core._interpreter_actions._parse_motor2_direction
- **Output to**: re.sub, None.lower, None.strip, str

### oqlos.core._interpreter_actions._parse_motor2_speed_steps
- **Output to**: None.lower, re.search, max, int, None.strip

### oqlos.core._interpreter_actions._parse_motor2_float
- **Output to**: re.search, str, abs, float, None.replace

### oqlos.core._interpreter_actions._parse_motor2_duration_seconds
- **Output to**: None.lower, oqlos.core._interpreter_actions._parse_motor2_float, max, max, max

### oqlos.core._interpreter_actions._parse_motor2_volume_liters
- **Output to**: None.lower, oqlos.core._interpreter_actions._parse_motor2_float, any, None.strip, str

### oqlos.core._interpreter_actions._parse_motor2_acceleration
- **Output to**: None.lower, re.search, max, int, None.strip

### oqlos.core._interpreter_actions._parse_prefixed_motor2_setting
> Parse prefix-based motor2 settings (stroke, volume, duration, etc.).
- **Output to**: normalized.startswith, normalized.startswith, normalized.startswith, normalized.startswith, normalized.startswith

### oqlos.core._interpreter_actions._parse_motor2_reciprocating_setting
- **Output to**: oqlos.core._interpreter_actions._normalize_motor2_value, _MOTOR2_EXACT_MODES.get, oqlos.core._interpreter_actions._parse_prefixed_motor2_setting, dict, oqlos.core._interpreter_actions._parse_motor2_direction

### oqlos.core._interpreter_actions._parse_motor2_steps
- **Output to**: None.lower, re.search, max, int, None.strip

### oqlos.core.oql_parser.parse_duration
> Parse ``3s``, ``500ms``, ``3000`` (bare number defaults to ``ms``).
- **Output to**: DUR_RE.match, ValueError, oqlos.core.oql_parser.to_num, match.group, match.group

### oqlos.core.oql_parser.parse_SET
- **Output to**: oqlos.core.oql_parser._require, oqlos.core.oql_parser._split_set_value_unit, OqlCmd

### oqlos.core.oql_parser.parse_GET
- **Output to**: oqlos.core.oql_parser._require, OqlCmd

### oqlos.core.oql_parser.parse_WAIT
- **Output to**: oqlos.core.oql_parser._require, oqlos.core.oql_parser.parse_duration, oqlos.core.oql_parser.duration_to_ms, OqlCmd

### oqlos.core.oql_parser.parse_IF_DELTA
- **Output to**: oqlos.core.oql_parser._require, None.replace, DELTA_RE.match, oqlos.core.oql_parser.to_num, abs

## Public API Surface

Functions exposed as public API (no underscore prefix):

- `oqlos.dsl.schema.get_default_dsl_schema` - 75 calls
- `oqlos.hardware.firmware_adapter.FirmwareAdapter.set_peripheral` - 60 calls
- `scripts.migrate_to_v4.main` - 46 calls
- `scripts.fix_brackets_to_v4.main` - 42 calls
- `oqlos.tools.plugin_cli.main` - 36 calls
- `oqlos.hardware.usb_diagnostics.list_usb_devices` - 33 calls
- `oqlos.tools.cql_cli.formatting.canonicalize_oql_line` - 31 calls
- `oqlos.core._oql_adapter.oql_doc_to_cql` - 30 calls
- `scripts.oql_v2_to_v4_migrate_db.main` - 30 calls
- `oqlos.core.motor2_runtime.normalize_motor2_runtime_config` - 29 calls
- `oqlos.hardware.diagnosis.build_diagnosis_report` - 28 calls
- `oqlos.hardware.usb_diagnostics.pi_system_diagnostics` - 28 calls
- `oqlos.tools.hardware_diagnose.modbus_probe.probe_options_from_args` - 27 calls
- `oqlos.hardware.rtc_probe.build_rtc_peripheral_status` - 27 calls
- `oqlos.hardware.client.modbus_repair.rewrite_modbus_repair` - 26 calls
- `oqlos.tools.hardware_diagnose.doctor.format_detection` - 25 calls
- `oqlos.hardware.client.resolvers.extract_command_failure` - 25 calls
- `oqlos.hardware.client.identify_enrich.enrich_adapter_entry` - 25 calls
- `oqlos.hardware.client.identify_enrich.enrich_identify_payload` - 25 calls
- `oqlos.reporters.html_report.render_html_report` - 25 calls
- `scripts.scenarios_export.export_all_zip` - 25 calls
- `setup_hardware_and_run_oql.run_oql_scenario` - 24 calls
- `oqlos.shared.logger.configure_oqlos_logging` - 23 calls
- `oqlos.api.hardware.read_modbus_adc_raw` - 23 calls
- `scripts.scenarios_export.main` - 23 calls
- `oqlos.core.oql_parser.parse_oql` - 21 calls
- `oqlos.core.parser.parse_dsl_to_goal_with_issues` - 21 calls
- `oqlos.tools.hardware_diagnose.doctor.format_doctor` - 21 calls
- `oqlos.tools.hardware_diagnose.__main__.main` - 21 calls
- `oqlos.tools.xml_import.generators.generate_dsl` - 21 calls
- `oqlos.tools.cql_cli.commands.handle_list_command` - 21 calls
- `oqlos.api.oql_mqtt.oql_ws` - 21 calls
- `scripts.migrate_to_v4.check_database` - 21 calls
- `scripts.oql_v2_to_v4_migrate_db.migrate_v2_to_v4` - 21 calls
- `scripts.scenarios_export.export_one_bash` - 21 calls
- `oqlos.tools.hardware_diagnose.health.cmd_diagnose` - 20 calls
- `oqlos.hardware.client.autorepair.analyze_repair_needs` - 20 calls
- `oqlos.shared.logs_query.LogsQueryService.query_logs` - 20 calls
- `oqlos.api.execution.execute_step` - 20 calls
- `oqlos.api.hardware.hardware_identify` - 20 calls

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