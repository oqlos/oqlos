# OqlOS Documentation

## Spis treści

- **[Sterowanie sprzętem przez OQL-over-MQTT + Panel testowy](HARDWARE_CONTROL_OQL_MQTT.md)**
  — architektura controller/agent/broker, uruchomienie, panel `/panel`, API `/api/v1/oql/*`,
  pełna lista verbów `manage` (w tym `usb-list`, `pi-diagnostics`, `usb-reset`), wdrożenie, troubleshooting.
- [Hardware Diagnostics](HARDWARE_DIAGNOSTICS.md)
- [OQL v4 Migration Manual](OQL_V4_MIGRATION_MANUAL.md)
- [OQL spec](oql-spec.md) · [CQL spec](cql-spec.md) · [CQL examples](cql-examples.md)

## Hardware Operator Entry Points

Before running scenarios in `execute` mode, use the hardware doctor:

```bash
oqlctl doctor
oqlctl detect
oqlctl doctor --json
oqlctl doctor --fix
```

If a global `oqlctl` shadows the repository CLI and lacks `detect`/`doctor`,
activate `.venv` or call `.venv/bin/oqlctl` explicitly.

`doctor` combines host-side USB/serial/I2C discovery, Modbus RTU probing,
`oqlos.yaml` validation, and firmware `/api/v1/hardware/health` +
`/api/v1/hardware/identify` checks. It reports concrete issues such as:

- firmware running in `mock` mode,
- firmware/container missing access to `/dev/ttyACM*` or `/dev/ttyUSB*`,
- local USB devices connected to a different host than a remote firmware URL,
- a configured Modbus port already owned by another process, including when
  `oqlos.yaml` uses `/dev/serial/by-id/...`,
- `modbus-io` port/baud mismatch,
- adapter statuses such as `offline`, `no-access`, `adapter-only`, mock-mode
  HTTP drivers, and runtime health failures.

Safe automatic repair is intentionally narrow: `oqlctl doctor --fix` updates
only detected Modbus connection parameters in `oqlos.yaml` and writes
`oqlos.yaml.bak` first. The current default hardware profile expects
`19200 8N1` for Waveshare Modbus RTU IO 8CH; prefer stable
`/dev/serial/by-id/...` paths over volatile `/dev/ttyACM*` numbering.
Runtime repairs such as enabling real firmware mode, restarting containers, or
mounting `/dev/ttyACM*`/`/dev/ttyUSB*` remain manual and are reported as
unapplied repairs when `--fix` is requested.

Detailed guide: [Hardware Diagnostics](HARDWARE_DIAGNOSTICS.md).

<!-- code2docs:start --># oqlos

![version](https://img.shields.io/badge/version-0.1.0-blue) ![python](https://img.shields.io/badge/python-%3E%3D3.10-blue) ![coverage](https://img.shields.io/badge/coverage-unknown-lightgrey) ![functions](https://img.shields.io/badge/functions-1988-green)
> **1988** functions | **112** classes | **242** files | CC̄ = 4.2

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




## Architecture

```
oqlos/
├── hw_diagnostic_20260415_133138
├── setup_hardware_and_run_oql
├── goal
├── Makefile
├── oqlos/
├── pyqual
├── sumd
├── pyproject
    ├── testql
├── openapi_spec
        ├── toon
├── TODO
├── CHANGELOG
├── Taskfile
├── openapi
├── project
├── README
        ├── config
    ├── package
        ├── App
        ├── main
            ├── useWsStatus
            ├── useUrlConfig
            ├── HardwareActivityLog
            ├── SharedNav
            ├── SidebarList
            ├── mapEditorDefaultMap
            ├── MapEditor
            ├── HardwareStatus
            ├── HardwareRestart
            ├── HardwareDemo
            ├── dictionaries
            ├── hardware-status-log-translations
            ├── I18nProvider
            ├── hardware-status-panel-translations
            ├── hardware-demo-extra-translations
            ├── hardware-status-presets-translations
            ├── hardwareEventStream
            ├── hardware-time
            ├── useSelectionCollapsePanel
                ├── policy
            ├── hardware-restart-docs
            ├── hui-shell-key
            ├── parentUrlBridge
            ├── mapEditorFuncHardwareSummary
            ├── hardware-activity-log
            ├── hardware-wizard-steps
            ├── hardware-wizard-plan
            ├── designRem
            ├── collapse-toggle-bridge
            ├── AppConfigProvider
            ├── wsClient
            ├── hardwareApi
            ├── hardware-api-log
        ├── hardware-client/
            ├── paths
    ├── cql-spec
        ├── schema
    ├── cql-examples
    ├── oql-spec
        ├── schema
    ├── HARDWARE_DIAGNOSTICS
    ├── OQL_V4_MIGRATION_MANUAL
    ├── HARDWARE_CONTROL_OQL_MQTT
    ├── README
        ├── mosquitto
        ├── oqlos-hw
        ├── migration
        ├── RUNBOOK
        ├── mosquitto
        ├── oqlos-hw
        ├── migration
        ├── RUNBOOK
    ├── plugin-config
    ├── curl-quickstart
        ├── doctor-workflow
        ├── prod
        ├── dev
    ├── Dockerfile
    ├── config
        ├── state
        ├── base
        ├── _dsl_helpers
        ├── _cql_tree_builder
        ├── _interpreter_actions
        ├── oql_parser
        ├── motor2_runtime
    ├── core/
        ├── _action_motor2
        ├── oql_versioning
        ├── parser
        ├── _func_resolver
        ├── executor
        ├── _oql_adapter
        ├── interpreter
        ├── _cql_tokenizer
        ├── _line_parsers
        ├── safe_eval
        ├── _compare
        ├── cql_parser
        ├── _firmware_executor
        ├── _value_normalizers
        ├── _sensor_evaluator
        ├── hardware_diagnose/
        ├── plugin_cli
            ├── doctor
            ├── health
            ├── __main__
            ├── modbus_probe
            ├── shell
            ├── benchmark
            ├── discovery
            ├── report
            ├── calibration
            ├── _utils
        ├── xml_import/
            ├── parser
            ├── generators
            ├── models
            ├── commands
        ├── cql_cli/
            ├── formatting
            ├── utils
            ├── main
            ├── preflight
        ├── execution
        ├── dsl_models
        ├── scenario
        ├── peripheral
        ├── config_paths
        ├── diagnosis
        ├── protocol
        ├── config_schema
        ├── rtc_probe
        ├── gateway
        ├── hui_actions
        ├── registry
        ├── sidecar_control
        ├── control_proxy
        ├── scanner_probe
    ├── hardware/
        ├── peripheral_mapping
        ├── stack_snapshot
        ├── tic249_units
        ├── modbus_identify
        ├── plugin_gateway
        ├── discovery
        ├── firmware_adapter
        ├── identify_enrichment
        ├── artificial_lung
        ├── usb_diagnostics
        ├── transport/
            ├── manage_ops
            ├── mqtt_oql_bridge
            ├── config
            ├── proxy
            ├── tic249_extended
            ├── errors
            ├── autorepair
            ├── http_helpers
        ├── client/
            ├── resolvers
            ├── adc
            ├── modbus_repair
            ├── platform
            ├── tic249_rig_direction
            ├── tic249_arg_contract
            ├── identify_enrich
            ├── constants
            ├── base
            ├── registry
            ├── piadc
        ├── plugins/
            ├── modbus
            ├── lung
            ├── motor
            ├── _shared
            ├── _rtu_serial
            ├── modbus_adc
            ├── gpio
        ├── drivers/
            ├── spi
            ├── mqtt
        ├── html_report
    ├── reporters/
        ├── json_reporter
        ├── junit
        ├── sample_data
    ├── utils/
        ├── hui_scenario
        ├── release_version
        ├── _endpoint_helpers
        ├── file_ops
        ├── logs_query
        ├── config_factory
        ├── event_server
        ├── version_endpoint
        ├── event_store
        ├── logger
        ├── version
        ├── state
        ├── plugins
        ├── scenarios
        ├── execution
        ├── peripherals
    ├── api/
        ├── hardware
        ├── logs
        ├── editor
        ├── main
        ├── oql_mqtt
            ├── execution_ctrl
        ├── OQL-CHEATSHEET
            ├── README
        ├── schema
    ├── dsl/
    ├── oql_validator_common
    ├── gen-checksums
    ├── provision-rpi-sudo
    ├── oql_v4_validator
    ├── verify-rpi-checksum
    ├── hardware-check
    ├── oql-stack
    ├── fix_brackets_to_v4
    ├── oql_v2_validator
    ├── migrate_to_v4
    ├── oql_v2_to_v4_migrate_db
    ├── scenarios_export
    ├── test-hardware
            ├── toon
            ├── toon
            ├── toon
            ├── toon
            ├── toon
    ├── manifest
```

## API Overview

### Classes

- **`WsCqrsClient`** — —
- **`Settings`** — Application settings loaded from environment variables and .env file
- **`StateManager`** — —
- **`StepStatus`** — —
- **`StepResult`** — —
- **`ScriptResult`** — —
- **`VariableStore`** — Hierarchical key-value store with interpolation support.
- **`InterpreterOutput`** — Collects interpreter output lines for display or testing, and optionally broadcasts events.
- **`BaseInterpreter`** — Abstract base for language interpreters.
- **`EventBridge`** — Optional WebSocket bridge to DSL Event Server (port 8104).
- **`OqlCmd`** — A single command line inside a block.
- **`OqlBlock`** — A named block: ``GOAL``, ``CONFIG``, or ``MACRO``.
- **`OqlDoc`** — Parsed OQL document.
- **`Motor2RuntimeConfig`** — —
- **`Motor2ReciprocatingPlan`** — —
- **`OqlVersionInfo`** — Resolved OQL version metadata for a source document.
- **`ScenarioOrchestrator`** — —
- **`CqlInterpreter`** — CQL interpreter with three modes:
- **`SafeEvalError`** — Raised when an expression cannot be safely evaluated.
- **`FirmwareExecutor`** — Executes hardware actions via plugin gateway or legacy firmware.
- **`ValueNormalizer`** — Normalizes DSL values to hardware-compatible formats.
- **`SensorEvaluator`** — Evaluates sensor conditions and manages sensor values.
- **`UsbDevice`** — USB device information.
- **`SensorParam`** — Parameter measurement from an operation.
- **`Output`** — Hardware output setting.
- **`Operation`** — Single test operation (step).
- **`TestRun`** — A test run (scenario) within a device type.
- **`DeviceReport`** — Parsed device test report.
- **`ScenarioFetchError`** — Raised when an HTTP scenario target is not runnable OQL/CQL source.
- **`ExecutionRequest`** — —
- **`ExecutionStatus`** — —
- **`CommandEnvelope`** — —
- **`CqlMetadata`** — —
- **`CqlInterval`** — —
- **`CqlCondition`** — Sensor condition: AI01 ∈ [min, max] unit | ACTION 'msg'
- **`CqlAction`** — An action within a step: → Target.method args, TASK, SET, WAIT, or PUMP.
- **`CqlStep`** — A numbered step within a goal: 1. Step name:
- **`CqlGoal`** — A test goal within a scenario.
- **`CqlScenario`** — A named scenario block: @Namespace.Name
- **`CqlDocument`** — Root AST node for a .cql file.
- **`Step`** — —
- **`ValidationRule`** — —
- **`Goal`** — —
- **`Scenario`** — —
- **`PeripheralType`** — —
- **`PeripheralStatus`** — —
- **`PeripheralMode`** — —
- **`Peripheral`** — —
- **`DiagnosisAction`** — —
- **`DeviceDiagnosis`** — —
- **`DiagnosisReport`** — —
- **`ProtocolType`** — Supported hardware communication protocols.
- **`HardwareProtocol`** — Base class for all hardware drivers.
- **`UnitType`** — Standard unit types for hardware parameters.
- **`HardwareGateway`** — Single entry-point for all physical hardware I/O.
- **`DriverRegistry`** — Registry for hardware drivers. Allows mapping ProtocolType to specific HardwareProtocol implementations. 
- **`OqlosHardwareProxy`** — OqlOS-local proxy label for unavailable identify payloads.
- **`PluginHardwareGateway`** — Simplified hardware gateway using plugin architecture.
- **`FirmwareAdapter`** — HTTP bridge between CQL interpreter and firmware simulator.
- **`Topics`** — Resolved topic strings for one node.
- **`OqlRequest`** — A request to execute on a remote node.
- **`OqlResponse`** — The result of executing OQL on a remote node.
- **`OqlMqttController`** — Publishes OQL and awaits a correlated response.
- **`OqlMqttAgent`** — Subscribes to OQL requests, executes them locally, and replies.
- **`OqlosHardwareProxyConfig`** — —
- **`OqlosHardwareProxy`** — —
- **`HardwareProxyError`** — —
- **`PluginStatus`** — Status of a hardware plugin.
- **`HardwareDriverSpec`** — Pluggy hookspec for hardware drivers.
- **`ScaleConfig`** — Scale / range definition for a peripheral parameter.
- **`ConversionConfig`** — Describes how to convert a logical value to a hardware value.
- **`PeripheralConfig`** — Configuration for a single peripheral (sensor / actuator).
- **`PluginConfig`** — Standardized configuration schema for hardware plugins.
- **`OqlosConfigDocument`** — Top-level ``oqlos.yaml`` schema.
- **`PluginHealth`** — Health check result for a hardware plugin.
- **`HardwarePlugin`** — Base interface for hardware integration plugins.
- **`PluginRegistry`** — Central registry for hardware plugins.
- **`PiadcPlugin`** — Plugin for piADC (ADS1115) 16-bit ADC sensor.
- **`ModbusPlugin`** — Plugin for Waveshare Modbus RTU IO 8CH valve controller.
- **`LungPlugin`** — Plugin for Pololu Tic T249 stepper motor (artificial lung).
- **`MotorPlugin`** — Plugin for DFRobot DRI0050 PWM motor driver.
- **`ModbusAdcPlugin`** — Plugin for Waveshare Modbus RTU Analog Input 8CH.
- **`GpioDriver`** — Driver for direct GPIO control.
- **`SpiDriver`** — SPI driver for HAL.
- **`MqttDriver`** — MQTT driver for the Hardware Abstraction Layer.
- **`JUnitReporter`** — Generate JUnit XML from a ScriptResult.
- **`PathEscapeError`** — Raised when a resolved path would escape the base directory.
- **`LogsQueryService`** — Read-only query service for nfo logs SQLite database.
- **`ConnectionManager`** — Tracks connected WebSocket clients and broadcasts messages.
- **`EventServer`** — WebSocket event broker with persistence.
- **`EventStore`** — Append-only event store with optional JSON file persistence.
- **`FileInfo`** — —
- **`FileContent`** — —
- **`ExecutionRequest`** — —
- **`OqlExecuteRequest`** — —
- **`OqlManageRequest`** — —
- **`OqlExecuteResponse`** — —
- **`DslDialect`** — Supported DSL dialect metadata.
- **`DslItem`** — A reusable schema item visible to editor clients.
- **`DslFunctionBinding`** — Object to function relationship used by visual builders.
- **`DslParamUnitBinding`** — Param to unit relationship used by visual builders.
- **`DslSchema`** — Complete editor schema shared by GUI and runtime tooling.
- **`Issue`** — —
- **`Issue`** — —
- **`MigrationResult`** — —

### Functions

- `detect_serial_devices()` — Detect available USB-to-serial devices.
- `suggest_modbus_port(devices)` — Suggest Modbus serial port from detected devices.
- `generate_env_content(hardware_mode, modbus_port, piadc_url, motor_url)` — Generate .env file content.
- `setup_env_file(env_path, hardware_mode, modbus_port, force)` — Setup .env file with hardware configuration.
- `load_env_file(env_path)` — Load .env file into environment variables.
- `run_oql_scenario(scenario_path, mode, firmware_url)` — Run OQL scenario with loaded configuration.
- `main()` — —
- `LocalizedApp()` — —
- `useWsStatus()` — —
- `client()` — —
- `onOpen()` — —
- `onClose()` — —
- `DEFAULTS()` — —
- `resolveUserIdFromSearchParams()` — —
- `value()` — —
- `resolveUserFromContextPayload()` — —
- `userId()` — —
- `role()` — —
- `resolveViewportWidthPx()` — —
- `n()` — —
- `parseAppearanceParams()` — —
- `font()` — —
- `theme()` — —
- `lang()` — —
- `resolved()` — —
- `parseIdentityParams()` — —
- `parseNavigationParams()` — —
- `scenario()` — —
- `scenarioByFilename()` — —
- `device()` — —
- `deviceName()` — —
- `test()` — —
- `key()` — —
- `parseParams()` — —
- `params()` — —
- `parseUrlEmbedConfig()` — —
- `mergeParentContext()` — —
- `incomingFont()` — —
- `incomingLang()` — —
- `incomingTheme()` — —
- `fromUser()` — —
- `nextUser()` — —
- `roleCandidate()` — —
- `IFRAME_ONLY_SEARCH_PARAMS()` — —
- `mergeParentSearchIntoChildUrl()` — —
- `url()` — —
- `raw()` — —
- `incoming()` — —
- `kept()` — —
- `applyParentContextPayload()` — —
- `search()` — —
- `base()` — —
- `href()` — —
- `useUrlConfig()` — —
- `onPop()` — —
- `onMessage()` — —
- `envelope()` — —
- `ctx()` — —
- `nextHref()` — —
- `patch()` — —
- `param()` — —
- `syncParentUrl()` — —
- `parentSearch()` — —
- `location()` — —
- `currentPath()` — —
- `visibleNavItems()` — —
- `hasViewTabs()` — —
- `collapseEnabled()` — —
- `inPreview()` — —
- `filtered()` — —
- `handleSelect()` — —
- `HW_DIAGNOSTIC()` — —
- `HW_RUNTIME_PYTHON()` — —
- `DEFAULT_MAP()` — —
- `LIVE_EVENTS_LIMIT()` — —
- `TIC249_TARGET_VELOCITY_SCALE()` — —
- `GROUP_FOR_TAB()` — —
- `SECTION_DESC_KEY()` — —
- `EMPTY_KEY()` — —
- `META_FIELDS()` — —
- `PARAM_CONVERSION_ALGORITHMS()` — —
- `cloneDefaultMap()` — —
- `cloneValue()` — —
- `tic249RawTargetVelocity()` — —
- `value()` — —
- `isPlainObject()` — —
- `fillMissingFields()` — —
- `ensureRequiredDefaultMappings()` — —
- `shaped()` — —
- `defaultMotor2()` — —
- `defaultParam()` — —
- `isMapEmpty()` — —
- `firstBindingFromObjectMapping()` — —
- `readIntegrationMeta()` — —
- `setMetaField()` — —
- `nextValue()` — —
- `ensureMapShape()` — —
- `src()` — —
- `ensureParamConversion()` — —
- `toPrettyJson()` — —
- `createInitialEditorState()` — —
- `seeded()` — —
- `pretty()` — —
- `wsOnline()` — —
- `initial()` — —
- `tab()` — —
- `canClearServerEvents()` — —
- `canClearPersistentEvents()` — —
- `isDirty()` — —
- `setTabAndUrl()` — —
- `url()` — —
- `onJsonChange()` — —
- `parsed()` — —
- `applyMapMutation()` — —
- `next()` — —
- `addObject()` — —
- `name()` — —
- `periId()` — —
- `addParam()` — —
- `editParamConversionField()` — —
- `current()` — —
- `target()` — —
- `editParamConversionAlgorithm()` — —
- `normalized()` — —
- `addAction()` — —
- `addFunc()` — —
- `renameKey()` — —
- `nextName()` — —
- `item()` — —
- `deleteKey()` — —
- `editJsonField()` — —
- `editObjectActionArg()` — —
- `binding()` — —
- `direction()` — —
- `steps()` — —
- `editObjectActionBodyField()` — —
- `editMotorRuntimeConfig()` — —
- `renderMotorRuntimeRow()` — —
- `cfg()` — —
- `saveMap()` — —
- `parsedJson()` — —
- `mappingPayload()` — —
- `response()` — —
- `savedMap()` — —
- `restoreDefaultMap()` — —
- `restored()` — —
- `reloadCurrent()` — —
- `payload()` — —
- `shouldSeedBackend()` — —
- `loadRecentHardwareEvents()` — —
- `clearServerHardwareEvents()` — —
- `cancelled()` — —
- `wsUrl()` — —
- `closed()` — —
- `socket()` — —
- `message()` — —
- `mappingGroup()` — —
- `entryKeys()` — —
- `navContext()` — —
- `filteredEntryKeys()` — —
- `q()` — —
- `applyAutoCollapse()` — —
- `root()` — —
- `font()` — —
- `viewportWidth()` — —
- `denseFont()` — —
- `minWidth()` — —
- `observer()` — —
- `handleSelectEntry()` — —
- `integrationMeta()` — —
- `updateIntegrationMeta()` — —
- `objectCfg()` — —
- `resolveSelectedFuncMapping()` — —
- `result()` — —
- `filteredHardwareEvents()` — —
- `renderIntegrationMetaEditor()` — —
- `renderObjectActionEditor()` — —
- `args()` — —
- `body()` — —
- `renderMotorRuntimeConfigEditor()` — —
- `renderParamConversionEditor()` — —
- `view()` — —
- `runAddForTab()` — —
- `search()` — —
- `timestamp()` — —
- `txtDownload()` — —
- `blob()` — —
- `url()` — —
- `a()` — —
- `sleep()` — —
- `wizardStepSerialPort()` — —
- `buildWizardProbePayload()` — —
- `targetBaud()` — —
- `targetParity()` — —
- `targetIds()` — —
- `logPanelRef()` — —
- `refreshRuntimeStatus()` — —
- `status()` — —
- `loadPlan()` — —
- `stack()` — —
- `hint()` — —
- `data()` — —
- `serialPort()` — —
- `startOqlosAndRefreshPlan()` — —
- `port()` — —
- `start()` — —
- `steps()` — —
- `currentStep()` — —
- `isSeparateAdapters()` — —
- `isConfigureStep()` — —
- `requiresStepConfirm()` — —
- `confirmLabelKey()` — —
- `confirmErrorKey()` — —
- `canRunCurrentStep()` — —
- `releaseRs485Port()` — —
- `stop()` — —
- `runCurrentStep()` — —
- `log()` — —
- `payload()` — —
- `ok()` — —
- `runWithRetry()` — —
- `attempt()` — —
- `message()` — —
- `gatewayErr()` — —
- `waitMs()` — —
- `target()` — —
- `stepPort()` — —
- `role()` — —
- `probePayload()` — —
- `probe()` — —
- `candidates()` — —
- `selection()` — —
- `selectedCandidate()` — —
- `currentDeviceId()` — —
- `program()` — —
- `diagnostic()` — —
- `diagnose()` — —
- `diagnosticPayload()` — —
- `optionalStep()` — —
- `advanceOk()` — —
- `optionalSkip()` — —
- `skipPumpOffStep()` — —
- `skipOptionalStep()` — —
- `logText()` — —
- `exportText()` — —
- `stepRunning()` — —
- `copyLogsToClipboard()` — —
- `el()` — —
- `timer()` — —
- `result()` — —
- `skippedOptional()` — —
- `done()` — —
- `failed()` — —
- `isCurrent()` — —
- `playToneOnSpeakers()` — —
- `osc()` — —
- `gain()` — —
- `now()` — —
- `end()` — —
- `deviceMeta()` — —
- `audioCtxRef()` — —
- `stopRequestedRef()` — —
- `lastCmdAtRef()` — —
- `stepperDirectionRef()` — —
- `device()` — —
- `deviceLabel()` — —
- `deviceDescription()` — —
- `melodies()` — —
- `appendLog()` — —
- `ensureAudioCtx()` — —
- `Ctx()` — —
- `cancelled()` — —
- `res()` — —
- `adapters()` — —
- `a()` — —
- `pumpOk()` — —
- `stepperOk()` — —
- `sendDeviceNote()` — —
- `direction()` — —
- `fallbackDevice()` — —
- `fb()` — —
- `sendDeviceStop()` — —
- `playNote()` — —
- `note()` — —
- `ctx()` — —
- `onNoteClick()` — —
- `playMelody()` — —
- `melody()` — —
- `stopMelody()` — —
- `currentBadge()` — —
- `s()` — —
- `sidebarItems()` — —
- `navContext()` — —
- `isActive()` — —
- `isPlaying()` — —
- `buildDictionaries()` — —
- `dictionaries()` — —
- `resolveKey()` — —
- `val()` — —
- `I18nContext()` — —
- `getInitialLang()` — —
- `browser()` — —
- `I18nProvider()` — —
- `setLang()` — —
- `dict()` — —
- `t()` — —
- `val()` — —
- `useI18n()` — —
- `ctx()` — —
- `normalizeText()` — —
- `buildHardwareEventsWsUrl()` — —
- `envValue()` — —
- `clean()` — —
- `location()` — —
- `host()` — —
- `protocol()` — —
- `wsProtocol()` — —
- `normalizeHardwareEvent()` — —
- `source()` — —
- `data()` — —
- `command()` — —
- `payload()` — —
- `result()` — —
- `peripheralId()` — —
- `commandName()` — —
- `timestamp()` — —
- `id()` — —
- `matchesHardwareEventFilters()` — —
- `peripheralQuery()` — —
- `commandQuery()` — —
- `hardwareNowText()` — —
- `RAIL_HOVER_OPEN_MS()` — —
- `RAIL_HOVER_CLOSE_MS()` — —
- `useSelectionCollapsePanel()` — —
- `timerRef()` — —
- `railOpenTimerRef()` — —
- `panelCloseTimerRef()` — —
- `collapsed()` — —
- `cancelAutoCollapse()` — —
- `cancelRailOpen()` — —
- `cancelPanelClose()` — —
- `scheduleCollapse()` — —
- `expand()` — —
- `previewExpand()` — —
- `previewCollapse()` — —
- `railEnter()` — —
- `railLeave()` — —
- `panelEnter()` — —
- `panelLeave()` — —
- `toggleCollapsed()` — —
- `onMessage()` — —
- `envelope()` — —
- `payload()` — —
- `parseConnectRole()` — —
- `key()` — —
- `normalizeConnectRole()` — —
- `normalizeHostRole()` — —
- `normalized()` — —
- `isReadOnlyConnectRole()` — —
- `role()` — —
- `isOperatorConnectRole()` — —
- `isAdminConnectRole()` — —
- `normalizePath()` — —
- `raw()` — —
- `url()` — —
- `matchesPattern()` — —
- `prefix()` — —
- `resolveAllowedRolesForPath()` — —
- `normalizedPath()` — —
- `matched()` — —
- `canConnectRoleAccessPath()` — —
- `allowed()` — —
- `canHostRoleAccessPath()` — —
- `hardwareRestartDocsUrl()` — —
- `base()` — —
- `isValidShellHuiKey()` — —
- `huiKeyForDigit()` — —
- `entry()` — —
- `huiShortcutClass()` — —
- `huiShortcutLabelClass()` — —
- `bridgeSearchToParent()` — —
- `text()` — —
- `search()` — —
- `summarizeFuncToHardware()` — —
- `md()` — —
- `actions()` — —
- `objName()` — —
- `actName()` — —
- `om()` — —
- `b()` — —
- `cmd()` — —
- `peri()` — —
- `seen()` — —
- `createHardwareActivityLogEntry()` — —
- `prependHardwareActivityLogEntry()` — —
- `usePageOpenedLog()` — —
- `loggedRef()` — —
- `wizardStepKind()` — —
- `stepId()` — —
- `isSkippablePumpOffWizardStep()` — —
- `isPumpOffUnavailableError()` — —
- `normalized()` — —
- `selectWizardProbeCandidate()` — —
- `role()` — —
- `pool()` — —
- `list()` — —
- `targetId()` — —
- `atTarget()` — —
- `notAtTarget()` — —
- `alreadyAtTarget()` — —
- `needsProgramming()` — —
- `isOptionalWizardStep()` — —
- `action()` — —
- `isOqlosUnreachableError()` — —
- `normalized()` — —
- `rem()` — —
- `remVar()` — —
- `COLLAPSE_DELAY_MS()` — —
- `COLLAPSE_TOGGLE_IDS()` — —
- `isInIframe()` — —
- `postToParent()` — —
- `readStoredCollapsed()` — —
- `persistStoredCollapsed()` — —
- `FONT_USER_SCALE()` — —
- `AppConfigContext()` — —
- `AppConfigProvider()` — —
- `root()` — —
- `scale()` — —
- `parentEncoderActive()` — —
- `getInteractiveItems()` — —
- `all()` — —
- `style()` — —
- `removeHighlights()` — —
- `handleEncoderCommand()` — —
- `items()` — —
- `delta()` — —
- `target()` — —
- `parseParentEnvelope()` — —
- `onMessage()` — —
- `envelope()` — —
- `detail()` — —
- `onWheel()` — —
- `raw()` — —
- `onKeyDown()` — —
- `value()` — —
- `useAppConfig()` — —
- `ctx()` — —
- `RECONNECT_DELAY_MS()` — —
- `RECONNECT_MAX_ATTEMPTS()` — —
- `REQUEST_TIMEOUT_MS()` — —
- `defaultUrl()` — —
- `fromEnv()` — —
- `loc()` — —
- `proto()` — —
- `API_BASE()` — —
- `tryParseJson()` — —
- `describeDetail()` — —
- `message()` — —
- `issues()` — —
- `lastError()` — —
- `extractErrorPayload()` — —
- `TIC249_DEENERGIZE_COMMANDS()` — —
- `tic249ResultStatus()` — —
- `data()` — —
- `isIdempotentTic249Deenergized()` — —
- `status()` — —
- `formatHardwareApiError()` — —
- `payload()` — —
- `detail()` — —
- `detailMessage()` — —
- `extractDiagnosticFailure()` — —
- `command()` — —
- `result()` — —
- `genericErrors()` — —
- `nested()` — —
- `nestedOk()` — —
- `fromNested()` — —
- `fromPayload()` — —
- `request()` — —
- `startedAt()` — —
- `bodySummary()` — —
- `durationMs()` — —
- `text()` — —
- `err()` — —
- `summary()` — —
- `get()` — —
- `post()` — —
- `put()` — —
- `failure()` — —
- `peripheralId()` — —
- `serialPort()` — —
- `query()` — —
- `mode()` — —
- `normalized()` — —
- `isHardwareWizardPath()` — —
- `normalized()` — —
- `summarizeHardwareApiBody()` — —
- `keys()` — —
- `summarizeHardwareApiResponse()` — —
- `logHardwareApiEvent()` — —
- `isFailure()` — —
- `oqlosArtificialLungCommandPath()` — —
- `oqlosArtificialLungStatusPath()` — —
- `connectPeripheralStatusPath()` — —
- `connectDiagnosticCommandPath()` — —
- `connectCqrsEventsPath()` — —
- `q()` — —
- `print()` — —
- `get_settings()` — Get the application settings instance.
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
- `exec_action_endloop(interp, act)` — Execute REPEAT STOP as a break for the current loop.
- `exec_action_set(interp, act)` — Execute SET action with intelligent dispatch.
- `exec_action_action(interp, act)` — Execute generic ACTION.
- `to_num(raw)` — Convert '6.0' → 6.0, '3' → 3, '-10,5' → -10.5 (accepts comma).
- `parse_duration(token)` — Parse ``3s``, ``500ms``, ``3000`` (bare number defaults to ``ms``).
- `duration_to_ms(token)` — Convert a duration token into integer milliseconds.
- `tokenize(rest)` — Split a command tail into tokens.
- `parse_SET(tokens, ln, raw)` — —
- `parse_GET(tokens, ln, raw)` — —
- `parse_WAIT(tokens, ln, raw)` — —
- `parse_IF_DELTA(tokens, ln, raw)` — —
- `parse_SAVE(tokens, ln, raw)` — —
- `parse_CHECK(rest, ln, raw)` — —
- `parse_IF(rest, ln, raw)` — —
- `parse_MIN(tokens, ln, raw)` — —
- `parse_MAX(tokens, ln, raw)` — —
- `parse_SAMPLE(tokens, ln, raw)` — —
- `parse_LOG(tokens, ln, raw)` — —
- `parse_ERROR(tokens, ln, raw)` — —
- `parse_CORRECT(tokens, ln, raw)` — —
- `parse_CALL(tokens, ln, raw)` — —
- `parse_INCLUDE(tokens, ln, raw)` — —
- `parse_FUNC_CALL(tokens, ln, raw)` — —
- `parse_REPEAT(tokens, ln, raw)` — —
- `parse_oql(text, filename)` — Parse OQL source into an :class:`OqlDoc`.
- `format_doc(doc)` — Pretty-print for ad-hoc debugging.
- `motor2_max_steps_per_second(default)` — —
- `normalize_motor2_runtime_config(source)` — —
- `motor2_speed_for_duration(steps, cycles, duration_seconds)` — —
- `motor2_acceleration_raw(steps_per_second, percent, max_steps_per_second)` — —
- `motor2_speed_raw(steps_per_second, max_steps_per_second)` — —
- `build_motor2_reciprocating_plan(config)` — —
- `first_meaningful_line(text)` — Return first non-empty/non-comment line as (line_no, text).
- `extract_declared_version(text)` — Extract VERSION header value when present on first meaningful line.
- `resolve_oql_version(text)` — Resolve OQL version from source text with backward-compatible default.
- `is_supported_oql_version(version)` — —
- `parse_dsl_to_goal_with_issues(dsl, scenario_id)` — Parse DSL and return a runtime goal plus invalid runtime lines.
- `parse_dsl_to_goal(dsl, scenario_id)` — Parse DSL string to a runtime Goal with Steps.
- `safe_eval_condition(expr, context)` — Evaluate a simple comparison expression without using eval().
- `is_flat_oql(source)` — Heuristic: detect flat OQL source (v3/v4).
- `oql_doc_to_cql(doc)` — Convert a parsed :class:`OqlDoc` into a :class:`CqlDocument`.
- `parse_flat_oql(source, filename)` — Convenience: parse flat OQL directly to a :class:`CqlDocument`.
- `safe_eval(expr, context)` — Evaluate a simple expression safely without using eval().
- `resolve_compare(left, op, right)` — Evaluate a single comparison: left op right.
- `resolve_compare_chain(node, resolve_value)` — Evaluate a chained comparison using the caller's node resolver.
- `parse_cql(source, filename)` — Parse CQL source into AST.
- `validate_cql(doc)` — Validate a parsed CQL document. Returns list of issues.
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
- `detect_hardware(firmware_url)` — Collect local and firmware-side hardware discovery signals.
- `build_doctor_report(firmware_url)` — Run smart detection, analyze problems, and optionally apply safe fixes.
- `apply_safe_fixes(detection, repairs)` — Apply safe doctor repairs. Currently limited to oqlos.yaml Modbus params.
- `format_detection(detection)` — Format smart detection output for operators.
- `format_doctor(report)` — Format a doctor report for operators.
- `main()` — Run the hardware diagnostics CLI without importing __main__ at package import time.
- `check_firmware_health(url)` — Check firmware health via HTTP API.
- `check_firmware_identify(url)` — Get detailed hardware identification.
- `cmd_health(url)` — Health command — check firmware health, return formatted string.
- `cmd_diagnose(url)` — Full diagnostic command — combines USB + I2C + health + identify.
- `main()` — —
- `add_modbus_probe_arguments(parser)` — Add direct probe arguments to an argparse parser.
- `probe_options_from_args(args)` — Build probe options from CLI args, falling back to the legacy MODBUS_* env.
- `run_modbus_probe_from_args(args)` — Run the direct Modbus probe using CLI args with env fallback.
- `run_modbus_probe_from_env()` — Run the direct Modbus probe using the legacy MODBUS_* environment contract.
- `run_modbus_probe()` — Try all requested Modbus RTU read combinations and return JSON-safe results.
- `main(argv)` — —
- `interactive_shell(url)` — Run the interactive hardware diagnostic REPL.
- `run_benchmark(url, duration)` — Run HTTP performance benchmark against firmware health endpoint.
- `list_usb_serial_devices()` — Detect all USB-to-serial devices.
- `list_i2c_buses()` — List available I2C buses.
- `detect_chips_on_i2c(bus)` — Detect chips on I2C bus using i2cdetect.
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
- `canonicalize_oql_text(text)` — Return text with legacy SET forms rewritten to canonical OQL v4 style.
- `canonicalize_oql_line(line)` — Canonicalize one OQL line while preserving indentation.
- `output_yaml(data, quiet)` — Output data as YAML to stdout.
- `parse_sensor_overrides(sensor_args)` — Parse `-s name=value` overrides into a sensor mapping.
- `build_result_payload(result)` — Convert a script result into a JSON-friendly payload.
- `normalize_target_name(target)` — Normalize a target name for consistent lookup.
- `build_single_command_scenario(command)` — Wrap a single OQL command line in a minimal scenario document.
- `resolve_required_adapter(command)` — Infer the hardware adapter required by a single command, if any.
- `validate_directory(d, interpreter_class)` — Validate all .cql and .oql files in a directory tree.
- `create_file_parser()` — Create argument parser for file-based execution.
- `create_run_parser()` — Create parser for explicit `oqlctl run` scenario execution.
- `create_hardware_parser(action)` — Create parser for oqlctl hardware utility subcommands.
- `create_format_parser()` — Create parser for `oqlctl format`.
- `create_cmd_parser()` — Create argument parser for single command execution.
- `run_file_mode(args)` — Execute file-based CQL/OQL processing.
- `run_hardware_mode(action, argv)` — Run oqlctl status/identify/detect/doctor subcommands.
- `run_cmd_mode(argv)` — Execute single command mode.
- `run_format_mode(argv)` — Format a local OQL/CQL file.
- `main()` — Main entry point - delegates to dispatcher.
- `ensure_firmware_running(firmware_url)` — Attempt to start firmware service if it's not available.
- `check_firmware_state(firmware_url, yaml_output, quiet)` — Check firmware health and identify state.
- `check_required_adapter(command, adapters, yaml_output, quiet)` — Check if the required adapter for a command is available.
- `check_required_adapter_health(required_adapter, health, yaml_output, quiet)` — Check required adapter service health when firmware exposes it.
- `emit_preflight_success(firmware_url, health, identify, required_adapter)` — Emit preflight success output in appropriate format.
- `preflight_hardware(command, firmware_url)` — Check whether the requested command can run on real hardware.
- `resolve_oqlos_config_path(config_path)` — Resolve the canonical ``oqlos.yaml`` path.
- `is_stale_hardware_message(message)` — —
- `is_stale_hardware_entry(entry)` — —
- `plugin_is_healthy(entry)` — Stable OK — do not disconnect/reconnect when true.
- `plugin_needs_repair(plugin_id, entry)` — —
- `modbus_plugins_need_repair(identify)` — —
- `report_to_dict(report)` — —
- `build_diagnosis_report(identify)` — Build per-device diagnosis from an identify payload (same shape as GET /identify).
- `execute_safe_recover(gateway, report)` — Reconnect failed plugins inside OqlOS; return host_actions for sidecars.
- `get_hardware_config(device_id)` — Return the PluginConfig for *device_id* (loaded from unified YAML).
- `register_hardware_config(config)` — No-op shim — configs live in the unified YAML now.
- `load_config_from_yaml(config_path)` — Load plugin configs from the **unified** YAML format.
- `build_dynamic_schema_models(config_path)` — Build runtime Pydantic schema models from ``oqlos.yaml``.
- `is_rtc_hardware_enabled()` — RTC is opt-in: production RPi5 with Waveshare HAT (OQLOS_ENABLE_RTC=1).
- `get_pirtc_base_url()` — —
- `build_rtc_peripheral_status()` — Return the runtime status payload for the RTC sidecar.
- `run_rtc_command(command, args)` — Execute a diagnostic command against the RTC sidecar.
- `build_rtc_adapter_entry()` — —
- `enrich_rtc_adapter(payload)` — —
- `shutdown_all_hui_hardware(gateway)` — —
- `list_hui_actions()` — —
- `start_hui_hold(gateway, key)` — —
- `stop_hui_hold(gateway, key)` — —
- `start_hui_artificial_lung(gateway)` — —
- `stop_hui_artificial_lung(gateway)` — —
- `resolve_dri0050_serial(configured)` — Pick pump USB-serial: env, stable by-id, then ttyUSB not used by Modbus.
- `ensure_dri0050_sidecar()` — Start or restart dri0050-motor-api via systemd-run (same as make hardware-up).
- `resolve_scanner_presence(diagnostics)` — —
- `build_scanner_adapter_entry(diagnostics)` — —
- `enrich_scanner_adapter(payload)` — —
- `resolve_target_to_plugin(target)` — Resolve a DSL target name to its plugin ID.
- `register_custom_mapping(target, plugin_id)` — Register a custom peripheral-to-plugin mapping.
- `get_all_mappings()` — Get all peripheral-to-plugin mappings.
- `generate_dynamic_valve_mappings(max_valve_count)` — Generate dynamic valve mappings for numbered valves.
- `build_hardware_stack_snapshot(health)` — Collect platform, plugin health, Modbus preflight, stale-serial state, and wizard plan.
- `collect_modbus_serial_candidates(diagnostics)` — —
- `enrich_platform_modbus_ports(payload)` — —
- `enrich_modbus_serial_hints(payload)` — —
- `enrich_modbus_identify(payload)` — —
- `probe_waveshare_modbus(preferred_port, preferred_baud, preferred_parity, preferred_device_id)` — Probe serial ports and return the first working Modbus IO configuration.
- `probe_waveshare_modbus_adc(preferred_port, preferred_baud, preferred_parity, preferred_device_id)` — Probe serial ports for the Waveshare Modbus RTU Analog Input 8CH module.
- `enrich_identify_payload(payload)` — Apply platform-specific enrichment after core plugin identify.
- `get_peripheral_status(gateway)` — —
- `execute_command(command, args, gateway)` — —
- `list_usb_devices()` — Enumerate connected USB devices (sysfs; no root needed).
- `pi_system_diagnostics()` — Raspberry Pi health snapshot: model, temp, throttling, memory, uptime, ports.
- `reset_usb_device(vendor_id, product_id, dev_node)` — Driver-level reset / re-enumeration of a USB device (needs root or udev rw).
- `run_manage_verb(verb, args)` — Execute a management verb and return a JSON-serializable result dict.
- `list_manage_verbs()` — Return the supported verb names (for discovery/tests).
- `build_topics(prefix, node_id)` — —
- `float_from_env(env, key, default)` — —
- `int_from_env(env, key, default)` — —
- `candidate_oqlos_bases(api_base)` — —
- `run_extended_motor_tic249_command(hardware_proxy, command, args)` — —
- `is_oqlos_unavailable(exc)` — —
- `oqlos_error_detail(exc)` — —
- `plugin_needs_repair(plugin_id, entry)` — —
- `modbus_plugins_need_repair(identify)` — —
- `analyze_repair_needs(identify)` — Return whether host stack restart is recommended and human-readable reasons.
- `modbus_exclusive_scan_recommended(identify)` — —
- `overall_stack_healthy(identify)` — —
- `build_summary()` — —
- `safe_response_payload(response)` — —
- `response_error_message(payload)` — —
- `normalize_modbus_valve_id(raw)` — —
- `resolve_modbus_target(command, args)` — —
- `resolve_pump_target(command, args)` — —
- `resolve_artificial_lung_target(command, args)` — —
- `resolve_lung_target(command, args)` — —
- `resolve_modbus_adc_target(command, args)` — —
- `resolve_rtc_target(command, args)` — —
- `resolve_diagnostic_target(peripheral, command, args)` — —
- `extract_command_failure(result)` — —
- `adc_sensor_alias(raw_sensor_id)` — —
- `normalize_adc_read_result(result, requested_sensor_id)` — —
- `normalize_adc_read_all_result(result)` — —
- `rewrite_modbus_repair(payload)` — Replace upstream docker-gateway commands with the configured host workflow.
- `is_raspberry_pi()` — Return True when running on a Raspberry Pi.
- `is_docker()` — Return True when running inside a Docker container.
- `get_default_oqlos_api_base()` — Return the default OqlOS API base URL for the current platform.
- `rig_direction_to_plugin(direction)` — Map rig/OQL direction token to OqlOS motor-tic249 plugin direction.
- `apply_rig_direction_to_plugin_params(params, args)` — Set ``direction`` and ``start_direction`` on reciprocate params from rig/OQL args.
- `canonicalize_motor2_runtime_key(key)` — —
- `tic249_runtime_args_from_config(runtime_config)` — —
- `enrich_adapter_entry(adapter)` — —
- `adapter_status_from_health(hw_id, health_entry)` — Map plugin health entries to identify adapter status labels.
- `count_detected_adapters(adapters)` — —
- `enrich_identify_payload(payload)` — —
- `enrich_hardware_identify(payload)` — Apply OqlOS identify enrichment and host repair command normalization.
- `get_pluggy_manager()` — Return the global pluggy PluginManager for third-party drivers.
- `dynamic_peripheral_model(peripheral)` — Generate a runtime Pydantic model from a ``PeripheralConfig``.
- `dynamic_plugin_schema_models(config)` — Build runtime Pydantic models for all plugin peripherals.
- `http_health_check(client, base_url, label)` — Shared HTTP health check — GET {base_url}/health.
- `not_connected_health(label)` — Return error health when plugin has no active client.
- `health_check_exception(exc)` — Return error health for unexpected exceptions.
- `http_disconnect(client, label)` — Close an httpx client (if open) and log disconnect.
- `serial_error_is_stale(exc)` — —
- `reopen_rtu_after_stale(plugin, exc)` — Close and reopen the RTU bus after USB tty re-enumeration (EIO).
- `render_html_report(data_json)` — Render a self-contained HTML report from an ``oqlos-report-v1`` JSON string.
- `report_json(result)` — Format a ScriptResult as the canonical ``data.json`` for report rendering.
- `report_junit(result, suite_name)` — Convenience function — wraps JUnitReporter().generate().
- `load_sample_scenarios(state_manager)` — Load sample scenarios for testing
- `register_hui_test_scenario(state_manager)` — Register ts-c20 so POST /api/v1/execution/step accepts test-hui manual actions.
- `clean_version(raw)` — Normalize a raw version string to plain semver text.
- `resolve_release_version(project_root)` — Resolve the release version for the given project root.
- `main()` — —
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
- `configure_oqlos_logging()` — Configure root logging for oqlos-server.
- `get_logger(name)` — —
- `get_state()` — Get current system state
- `stream_values(param, min, max, period)` — SSE endpoint for live value streaming.
- `get_current_value(param)` — Get current value for a parameter (single request, not streaming).
- `get_sim_state()` — Get simulation state in list format
- `get_variables_alias()` — Get variables (alias for fetch)
- `fetch_variables(source)` — Fetch variables (Peripheral State Table) from backend DB; tolerate dev HTML by returning [].
- `fetch_protocol_steps(scenario, source)` — Fetch protocol steps for preview.
- `post_commands(env, background_tasks)` — Command bus endpoint used by frontend.
- `ensure_plugins_initialized()` — Register and discover plugins once per process.
- `list_plugins()` — List all registered hardware plugins.
- `get_plugin_status()` — Get overall status of all plugins.
- `get_plugin_info(plugin_id)` — Get information about a specific plugin.
- `get_plugin_health(plugin_id)` — Get health status of a specific plugin.
- `connect_plugin(plugin_id, config)` — Connect to a hardware plugin.
- `disconnect_plugin(plugin_id)` — Disconnect from a hardware plugin.
- `execute_plugin_command(plugin_id, command)` — Execute a command on a hardware plugin.
- `validate_plugin_configs(configs)` — Validate configurations for multiple plugins.
- `get_scenario(scenario_id)` — Get specific scenario
- `fetch_scenarios(source)` — Fetch scenarios from backend DB or external JSON and normalize shape.
- `register_dsl(payload)` — Register one or many scenarios defined as DSL strings.
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
- `hardware_identify(scan)` — Return hardware identification with conditional live scanning for low latency.
- `set_valve(valve_id, value)` — Directly set a valve (for manual testing).
- `set_pump(power_pct)` — Directly set pump power % (for manual testing).
- `hui_actions()` — Return OqlOS-owned HUI action recipes.
- `hui_shutdown()` — Stop HUI pump/valve actions using the canonical OqlOS recipe.
- `hui_hold_start(key)` — Start a named HUI hold action.
- `hui_hold_stop(key)` — Stop a named HUI hold action and return hardware to a safe state.
- `hui_al_start()` — Start the HUI artificial-lung action.
- `hui_al_stop()` — Stop the HUI artificial-lung action.
- `read_sensor(sensor_id)` — Read a sensor value directly from hardware.
- `hardware_temperature()` — Read CPU temperature, returning an HUI-compatible unavailable payload if absent.
- `read_sensors_batch(sensor_ids)` — Read multiple sensors without making HUI fall back to repeated failing requests.
- `hardware_diagnose()` — Return HUI-friendly hardware diagnostics without failing the request.
- `hardware_modbus_waveshare_diagnose()` — Run Waveshare-focused Modbus scan matrix and per-slave register checks.
- `hardware_stack_snapshot()` — Single autodetect + configuration-cycle snapshot (health, ports, wizard plan).
- `hardware_diagnosis_route(scan)` — Per-device diagnosis plan (environment + recommended actions).
- `hardware_recover_route(scope)` — Safe auto-recovery inside OqlOS; host sidecar steps are returned as host_actions.
- `hardware_modbus_wizard_plan()` — Return guided step-by-step Modbus configuration plan.
- `hardware_modbus_wizard_probe_isolated(serial_port, baudrates, parities, device_ids)` — Probe one isolated module before writing address/UART settings.
- `hardware_modbus_wizard_program_isolated(serial_port, current_device_id, new_device_id, new_baudrate)` — Program one isolated module (address + UART), then verify config.
- `read_modbus_adc_raw()` — Return raw Modbus ADC diagnostics for HUI troubleshooting.
- `set_lung(steps, speed, cycles, pause)` — Start artificial lung reciprocating motion (tic249 stepper).
- `stop_lung()` — Emergency stop the artificial lung motor.
- `disable_lung()` — De-energize the artificial lung motor (release coils).
- `artificial_lung_status()` — Logical lung state merged with motor connectivity hints.
- `artificial_lung_command(payload)` — Execute artificial-lung logical commands (set_lpm, lung_*, emergency_stop).
- `rtc_status()` — Return runtime status for the RTC sidecar.
- `rtc_command(payload)` — Execute a diagnostic command against the RTC sidecar.
- `get_logs(level, function, module, q)` — Browse nfo logs from shared SQLite database.
- `get_log_stats()` — Summary statistics from logs database.
- `list_files()` — List all entries in the scenarios directory.
- `read_file_endpoint(file_path)` — Read a file's content.
- `write_file_endpoint(file_path, file_content)` — Write content to a file (creates parent directories as needed).
- `execute_scenario(request)` — Execute a scenario file using oqlos runtime.
- `index_page()` — Serve the firmware UI (index.html) at root
- `editor_page()` — Serve the scenario editor UI
- `panel_page()` — Serve the test panel UI (predefined command groups, custom + ready-made scenarios).
- `hardware_ui_spa(full_path)` — Serve the moved hardware UI SPA, falling back to index.html for client routes.
- `health_check()` — Health check endpoint for tests and frontend compatibility probes.
- `status()` — —
- `websocket_endpoint(websocket)` — —
- `oql_websocket_alias(websocket)` — Convenience alias for the OQL channel (also at /api/v1/oql/ws).
- `run()` — Entry point for ``oqlos-server`` console script.
- `set_oql_controller(controller)` — Install (or clear) the process-global controller used by the routes.
- `get_oql_controller()` — —
- `execute_oql(req)` — —
- `manage_hardware(req)` — Run a remote management/diagnostic verb over MQTT.
- `oql_ws(websocket)` — Bidirectional OQL channel: client sends OQL frames, receives results.
- `set_dependencies(sm, orch)` — Set state_manager + orchestrator (called once from main.py).
- `get_default_dsl_schema()` — Return the canonical cross-project schema used by editor clients.
- `looks_like_html(text)` — —
- `extract_code_from_json(data)` — —
- `fetch_url(url, timeout)` — —
- `build_api_fallback_urls(url)` — —
- `load_source(file_path, url)` — —
- `run_validator_cli(description, validate, argv)` — —
- `validate_oql_v4(text, source)` — —
- `main()` — —
- `remote_manifest()` — —
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
- `up_broker()` — —
- `up_agent()` — —
- `up_controller()` — —
- `cmd_down()` — —
- `cmd_status()` — —
- `needs_migration(text)` — Check if text contains v2 bracket syntax, legacy MIN/MAX, PUMP, or old IF sentinels.
- `main()` — —
- `validate_oql_v2_legacy(text, source)` — —
- `main()` — —
- `find_oql_files(root_dir)` — Znajdź wszystkie pliki .oql poza venv/.venv.
- `has_version_header(content)` — Sprawdź czy plik ma nagłówek VERSION: X.
- `extract_version(content)` — Wyciągnij numer wersji z pliku.
- `migrate_content(content, filename)` — Zmigruj zawartość pliku do VERSION: 4.
- `main()` — —
- `check_database()` — Sprawdź scenariusze w bazie danych przez API.
- `migrate_v2_to_v4(text)` — —
- `main()` — —
- `export_all_zip(base, out_path)` — —
- `export_one_bash(base, sid, out_path)` — —
- `import_scenarios(base, dir_path, validate)` — —
- `main(argv)` — —


## Project Structure

📄 `CHANGELOG`
📄 `Makefile`
📄 `README`
📄 `TODO`
📄 `Taskfile`
📄 `Taskfile.testql`
📄 `docker.Dockerfile`
📄 `docker.docker-compose.dev`
📄 `docker.docker-compose.prod`
📄 `docs.HARDWARE_CONTROL_OQL_MQTT`
📄 `docs.HARDWARE_DIAGNOSTICS`
📄 `docs.OQL_V4_MIGRATION_MANUAL`
📄 `docs.README`
📄 `docs.cql-examples`
📄 `docs.cql-spec`
📄 `docs.oql-spec`
📄 `docs.oql_v2_llm_validator.schema`
📄 `docs.oql_v4_llm_validator.schema`
📄 `examples.curl-quickstart`
📄 `examples.hardware.doctor-workflow` (3 functions)
📄 `examples.plugin-config`
📄 `frontend.package`
📄 `frontend.src.App`
📄 `frontend.src.api.hardware-api-log` (9 functions)
📄 `frontend.src.api.hardwareApi` (55 functions)
📄 `frontend.src.api.wsClient` (32 functions, 1 classes)
📄 `frontend.src.components.HardwareActivityLog`
📄 `frontend.src.components.SharedNav` (6 functions)
📄 `frontend.src.components.SidebarList` (4 functions)
📄 `frontend.src.context.AppConfigProvider` (25 functions)
📄 `frontend.src.hooks.useUrlConfig` (54 functions)
📄 `frontend.src.hooks.useWsStatus` (4 functions)
📄 `frontend.src.i18n.I18nProvider` (10 functions)
📄 `frontend.src.i18n.dictionaries` (4 functions)
📄 `frontend.src.i18n.hardware-demo-extra-translations`
📄 `frontend.src.i18n.hardware-status-log-translations`
📄 `frontend.src.i18n.hardware-status-panel-translations`
📄 `frontend.src.i18n.hardware-status-presets-translations`
📄 `frontend.src.main` (1 functions)
📄 `frontend.src.pages.HardwareDemo` (46 functions)
📄 `frontend.src.pages.HardwareRestart` (73 functions)
📄 `frontend.src.pages.HardwareStatus` (1 functions)
📄 `frontend.src.pages.MapEditor` (151 functions)
📄 `frontend.src.pages.mapEditorDefaultMap` (3 functions)
📄 `frontend.src.utils.collapse-toggle-bridge` (6 functions)
📄 `frontend.src.utils.designRem` (2 functions)
📄 `frontend.src.utils.hardware-activity-log` (4 functions)
📄 `frontend.src.utils.hardware-restart-docs` (2 functions)
📄 `frontend.src.utils.hardware-time` (1 functions)
📄 `frontend.src.utils.hardware-wizard-plan` (2 functions)
📄 `frontend.src.utils.hardware-wizard-steps` (16 functions)
📄 `frontend.src.utils.hardwareEventStream` (21 functions)
📄 `frontend.src.utils.hui-shell-key` (5 functions)
📄 `frontend.src.utils.mapEditorFuncHardwareSummary` (13 functions)
📄 `frontend.src.utils.parentUrlBridge` (3 functions)
📄 `frontend.src.utils.rbac.policy` (22 functions)
📄 `frontend.src.utils.useSelectionCollapsePanel` (22 functions)
📦 `frontend.vendor.hardware-client` (2 functions)
📄 `frontend.vendor.hardware-client.paths` (4 functions)
📄 `frontend.vite.config`
📄 `goal`
📄 `hw_diagnostic_20260415_133138`
📄 `openapi`
📄 `openapi_spec`
📦 `oqlos`
📦 `oqlos.api`
📄 `oqlos.api.editor` (6 functions, 3 classes)
📄 `oqlos.api.execution` (16 functions)
📄 `oqlos.api.hardware` (89 functions)
📄 `oqlos.api.logs` (3 functions)
📄 `oqlos.api.main` (14 functions)
📄 `oqlos.api.oql_mqtt` (6 functions, 3 classes)
📄 `oqlos.api.peripherals` (4 functions)
📄 `oqlos.api.plugins` (12 functions)
📄 `oqlos.api.scenarios` (16 functions)
📄 `oqlos.api.state` (16 functions)
📄 `oqlos.api.utils.execution_ctrl` (3 functions)
📄 `oqlos.api.version`
📄 `oqlos.config` (1 functions, 1 classes)
📦 `oqlos.core`
📄 `oqlos.core._action_motor2` (34 functions)
📄 `oqlos.core._compare` (2 functions)
📄 `oqlos.core._cql_tokenizer` (27 functions)
📄 `oqlos.core._cql_tree_builder` (9 functions)
📄 `oqlos.core._dsl_helpers` (12 functions)
📄 `oqlos.core._firmware_executor` (9 functions, 1 classes)
📄 `oqlos.core._func_resolver` (4 functions)
📄 `oqlos.core._interpreter_actions` (51 functions)
📄 `oqlos.core._line_parsers` (9 functions)
📄 `oqlos.core._oql_adapter` (28 functions, 1 classes)
📄 `oqlos.core._sensor_evaluator` (6 functions, 1 classes)
📄 `oqlos.core._value_normalizers` (7 functions, 1 classes)
📄 `oqlos.core.base` (28 functions, 7 classes)
📄 `oqlos.core.cql_parser` (30 functions, 1 classes)
📄 `oqlos.core.executor` (21 functions, 1 classes)
📄 `oqlos.core.interpreter` (47 functions, 1 classes)
📄 `oqlos.core.motor2_runtime` (12 functions, 2 classes)
📄 `oqlos.core.oql_parser` (43 functions, 3 classes)
📄 `oqlos.core.oql_versioning` (4 functions, 1 classes)
📄 `oqlos.core.parser` (5 functions)
📄 `oqlos.core.safe_eval` (10 functions, 1 classes)
📄 `oqlos.core.state` (3 functions, 1 classes)
📦 `oqlos.dsl`
📄 `oqlos.dsl.schema` (6 functions, 5 classes)
📦 `oqlos.hardware`
📄 `oqlos.hardware.artificial_lung` (10 functions)
📦 `oqlos.hardware.client`
📄 `oqlos.hardware.client.adc` (3 functions)
📄 `oqlos.hardware.client.autorepair` (9 functions)
📄 `oqlos.hardware.client.config` (5 functions, 1 classes)
📄 `oqlos.hardware.client.constants`
📄 `oqlos.hardware.client.errors` (3 functions, 1 classes)
📄 `oqlos.hardware.client.http_helpers` (2 functions)
📄 `oqlos.hardware.client.identify_enrich` (18 functions)
📄 `oqlos.hardware.client.modbus_repair` (7 functions)
📄 `oqlos.hardware.client.platform` (3 functions)
📄 `oqlos.hardware.client.proxy` (29 functions, 1 classes)
📄 `oqlos.hardware.client.resolvers` (10 functions)
📄 `oqlos.hardware.client.tic249_arg_contract` (2 functions)
📄 `oqlos.hardware.client.tic249_extended` (30 functions)
📄 `oqlos.hardware.client.tic249_rig_direction` (2 functions)
📄 `oqlos.hardware.config_paths` (1 functions)
📄 `oqlos.hardware.config_schema` (4 functions, 1 classes)
📄 `oqlos.hardware.control_proxy` (1 functions, 1 classes)
📄 `oqlos.hardware.diagnosis` (26 functions, 3 classes)
📄 `oqlos.hardware.discovery` (3 functions)
📦 `oqlos.hardware.drivers`
📄 `oqlos.hardware.drivers.gpio` (7 functions, 1 classes)
📄 `oqlos.hardware.drivers.mqtt` (9 functions, 1 classes)
📄 `oqlos.hardware.drivers.spi` (7 functions, 1 classes)
📄 `oqlos.hardware.firmware_adapter` (26 functions, 1 classes)
📄 `oqlos.hardware.gateway` (25 functions, 5 classes)
📄 `oqlos.hardware.hui_actions` (12 functions)
📄 `oqlos.hardware.identify_enrichment` (1 functions)
📄 `oqlos.hardware.modbus_identify` (8 functions)
📄 `oqlos.hardware.peripheral_mapping` (4 functions)
📄 `oqlos.hardware.plugin_gateway` (21 functions, 1 classes)
📦 `oqlos.hardware.plugins`
📄 `oqlos.hardware.plugins._rtu_serial` (2 functions)
📄 `oqlos.hardware.plugins._shared` (4 functions)
📄 `oqlos.hardware.plugins.base` (21 functions, 9 classes)
📄 `oqlos.hardware.plugins.lung` (20 functions, 1 classes)
📄 `oqlos.hardware.plugins.modbus` (16 functions, 1 classes)
📄 `oqlos.hardware.plugins.modbus_adc` (17 functions, 1 classes)
📄 `oqlos.hardware.plugins.motor` (20 functions, 1 classes)
📄 `oqlos.hardware.plugins.piadc` (12 functions, 1 classes)
📄 `oqlos.hardware.plugins.registry` (14 functions, 1 classes)
📄 `oqlos.hardware.protocol` (6 functions, 2 classes)
📄 `oqlos.hardware.registry` (3 functions, 1 classes)
📄 `oqlos.hardware.rtc_probe` (7 functions)
📄 `oqlos.hardware.scanner_probe` (13 functions)
📄 `oqlos.hardware.sidecar_control` (8 functions)
📄 `oqlos.hardware.stack_snapshot` (4 functions)
📄 `oqlos.hardware.tic249_units`
📦 `oqlos.hardware.transport`
📄 `oqlos.hardware.transport.manage_ops` (7 functions)
📄 `oqlos.hardware.transport.mqtt_oql_bridge` (34 functions, 6 classes)
📄 `oqlos.hardware.usb_diagnostics` (5 functions)
📄 `oqlos.models.dsl_models` (8 classes)
📄 `oqlos.models.execution` (3 classes)
📄 `oqlos.models.peripheral` (4 classes)
📄 `oqlos.models.scenario` (4 classes)
📦 `oqlos.reporters`
📄 `oqlos.reporters.html_report` (5 functions)
📄 `oqlos.reporters.json_reporter` (5 functions)
📄 `oqlos.reporters.junit` (3 functions, 1 classes)
📄 `oqlos.scenarios.OQL-CHEATSHEET`
📄 `oqlos.scenarios.examples.README`
📄 `oqlos.shared._endpoint_helpers` (2 functions)
📄 `oqlos.shared.config_factory` (1 functions)
📄 `oqlos.shared.event_server` (11 functions, 2 classes)
📄 `oqlos.shared.event_store` (10 functions, 1 classes)
📄 `oqlos.shared.file_ops` (5 functions, 1 classes)
📄 `oqlos.shared.logger` (2 functions)
📄 `oqlos.shared.logs_query` (5 functions, 1 classes)
📄 `oqlos.shared.release_version` (7 functions)
📄 `oqlos.shared.version_endpoint` (2 functions)
📦 `oqlos.tools.cql_cli` (2 functions)
📄 `oqlos.tools.cql_cli.commands` (5 functions)
📄 `oqlos.tools.cql_cli.formatting` (3 functions)
📄 `oqlos.tools.cql_cli.main` (18 functions, 1 classes)
📄 `oqlos.tools.cql_cli.preflight` (12 functions)
📄 `oqlos.tools.cql_cli.utils` (10 functions)
📦 `oqlos.tools.hardware_diagnose` (1 functions)
📄 `oqlos.tools.hardware_diagnose.__main__` (11 functions)
📄 `oqlos.tools.hardware_diagnose.benchmark` (1 functions)
📄 `oqlos.tools.hardware_diagnose.calibration` (4 functions)
📄 `oqlos.tools.hardware_diagnose.discovery` (5 functions, 1 classes)
📄 `oqlos.tools.hardware_diagnose.doctor` (41 functions)
📄 `oqlos.tools.hardware_diagnose.health` (7 functions)
📄 `oqlos.tools.hardware_diagnose.modbus_probe` (16 functions)
📄 `oqlos.tools.hardware_diagnose.report` (2 functions)
📄 `oqlos.tools.hardware_diagnose.shell` (5 functions)
📄 `oqlos.tools.plugin_cli` (14 functions)
📦 `oqlos.tools.xml_import`
📄 `oqlos.tools.xml_import._utils` (6 functions)
📄 `oqlos.tools.xml_import.generators` (20 functions)
📄 `oqlos.tools.xml_import.models` (5 classes)
📄 `oqlos.tools.xml_import.parser` (6 functions)
📦 `oqlos.utils`
📄 `oqlos.utils.hui_scenario` (1 functions)
📄 `oqlos.utils.sample_data` (1 functions)
📄 `project`
📄 `pyproject`
📄 `pyqual`
📄 `redeploy.122.RUNBOOK`
📄 `redeploy.122.migration`
📄 `redeploy.122.mosquitto`
📄 `redeploy.122.oqlos-hw`
📄 `redeploy.pi-hw.RUNBOOK`
📄 `redeploy.pi-hw.migration`
📄 `redeploy.pi-hw.mosquitto`
📄 `redeploy.pi-hw.oqlos-hw`
📄 `scenarios.manifest`
📄 `scripts.fix_brackets_to_v4` (2 functions)
📄 `scripts.gen-checksums`
📄 `scripts.hardware-check` (11 functions)
📄 `scripts.migrate_to_v4` (19 functions)
📄 `scripts.oql-stack` (5 functions)
📄 `scripts.oql_v2_to_v4_migrate_db` (43 functions, 1 classes)
📄 `scripts.oql_v2_validator` (6 functions, 1 classes)
📄 `scripts.oql_v4_validator` (8 functions, 1 classes)
📄 `scripts.oql_validator_common` (6 functions)
📄 `scripts.provision-rpi-sudo`
📄 `scripts.scenarios_export` (13 functions)
📄 `scripts.test-hardware`
📄 `scripts.verify-rpi-checksum` (1 functions)
📄 `setup_hardware_and_run_oql` (7 functions)
📄 `sumd`
📄 `testql-contracts.testql.toon`
📄 `testql-scenarios.cross-project-integration.testql.toon`
📄 `testql-scenarios.generated-api-integration.testql.toon`
📄 `testql-scenarios.generated-api-smoke.testql.toon`
📄 `testql-scenarios.generated-from-pytests.testql.toon`
📄 `testql-scenarios.generated-from-scenarios.testql.toon`

## Requirements

- Python >= >=3.10
- fastapi >=0.110- uvicorn >=0.28- pydantic >=2.0- pydantic-settings >=2.2.0- pyserial >=3.5- pymodbus >=3.6- httpx >=0.25- nfo >=0.2.3- goal >=2.1.0- costs >=0.1.20- pfix >=0.1.60- paho-mqtt >=1.6.1- pluggy >=1.4- pytest-asyncio >=0.23- PyYAML >=6.0- testql >=0.2.0

## Contributing

**Contributors:**
- Tom Softreck <tom@sapletta.com>
- Tom Sapletta <tom-sapletta-com@users.noreply.github.com>

We welcome contributions! Open an issue or pull request to get started.
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

- 💡 [Examples](./examples) — Usage examples and code samples

### Generated Files

| Output | Description | Link |
|--------|-------------|------|
| `README.md` | Project overview (this file) | — |
| `examples` | Usage examples and code samples | [View](./examples) |

<!-- code2docs:end -->
## Motor 2 / Artificial Lung Runtime Contract

OQL keeps artificial-lung scenarios readable:

```oql
SET 'motor 2' 'volume 50 l'
SET 'motor 2' 'duration 30s'
SET 'motor 2' 'start'
```

The runtime contract is modeled in `oqlos.core.motor2_runtime`. Store physical defaults in the
MAP/UI layer and keep the algorithm in OqlOS/runtime handlers:

```json
{
  "motor2": {
    "peripheralId": "motor-tic249",
    "strokeSteps": 1000,
    "cycleVolumeLiters": 5,
    "maxStepsPerSecond": 1000,
    "defaultSpeedStepsPerSecond": 1000,
    "accelerationPercentPerSecond": 300,
    "limitMode": "reverse_on_limit",
    "startDirection": "left"
  }
}
```

For `volume 50 l` and `cycleVolumeLiters = 5`, the runtime plans 10 cycles. If a duration is
provided, it computes nominal `steps/s` from half-cycles and stroke size, then clamps it to the
configured maximum. Hardware services remain responsible for final safety checks, limits, and
stop/de-energize behavior.
