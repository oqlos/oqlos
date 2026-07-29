# OqlOS Error / Issue Codes

Generated from `oqlos/errors/catalog.py` by `python -m oqlos.tools.gen_error_docs`.
Do not hand-edit this file — edit the catalog and regenerate.

Each code is stable and grep-able across logs, API responses, and git commit
trailers (`OqlOS-Issue: <code>`). `actuation_risk` controls whether an
automated repair (e.g. an LLM-driven git commit) may apply the fix on its
own:

- `none` — diagnostic only, or needs a host/infra action no automation should
  attempt.
- `config` — a plain config/YAML edit with no effect until a service
  restart. Safe for an automated commit.
- `physical` — changes whether/how real hardware is actuated. Always
  requires human confirmation.


## api

| Code | Severity | Summary | Repair |
|------|----------|---------|--------|
| `api_diagnostic_command_invalid` | warning | The hardware diagnostic command or its arguments are invalid. | — |
| `api_invalid_recover_scope` | warning | POST /api/v1/hardware/recover was called with an unsupported `scope` query param. | — |
| `api_modbus_wizard_invalid_request` | warning | The isolated Modbus wizard request is incomplete or unsafe. | — |
| `api_oql_transport_disabled` | error | OQL-over-MQTT transport is disabled (OQLOS_OQL_TRANSPORT_ROLE=off); /api/v1/oql/execute and /manage cannot run. | `enable_oql_mqtt_transport` (scope=host, manual, risk=config) |
| `api_systemd_unit_forbidden` | warning | The requested system service is not permitted for this operation. | — |

## config

| Code | Severity | Summary | Repair |
|------|----------|---------|--------|
| `config_unavailable` | error | oqlos.yaml could not be loaded. | — |
| `modbus_adc_config_mismatch` | error | oqlos.yaml Modbus ADC settings do not match the responding device. | `update_modbus_adc_config` (scope=host, auto, risk=config) |
| `modbus_adc_config_missing` | warning | oqlos.yaml does not define the modbus-adc plugin. | — |
| `modbus_adc_disabled_but_present` | warning | Modbus ADC device responds on the serial bus, but modbus-adc is disabled in oqlos.yaml. | `enable_modbus_adc_config` (scope=host, auto, risk=config) |
| `modbus_config_mismatch` | error | oqlos.yaml Modbus (modbus-io) settings do not match the responding device. | `update_modbus_config` (scope=host, auto, risk=config) |
| `modbus_config_missing` | error | oqlos.yaml does not define the modbus-io plugin. | — |
| `pimodbus_unavailable` | error | The shared pimodbus runtime library is unavailable to OqlOS. | `install_pimodbus_runtime` (scope=host, manual, risk=config) |

## firmware

| Code | Severity | Summary | Repair |
|------|----------|---------|--------|
| `firmware_no_serial_access` | warning | Host sees USB serial devices, but firmware identify sees none (likely missing device mounts). | `mount_serial_devices` (scope=host, manual, risk=none) |
| `firmware_not_real` | warning | Firmware is running in mock mode; actuator endpoints will not control real hardware. | `enable_real_mode` (scope=host, manual, risk=physical) |
| `firmware_unreachable` | error | The firmware health endpoint is unavailable. | `start_firmware` (scope=host, manual, risk=none) |
| `identify_unavailable` | warning | The firmware identify endpoint is unavailable. | — |
| `remote_firmware_no_serial_access` | warning | The CLI host sees USB serial devices, but firmware runs elsewhere and cannot access them. | `align_firmware_host` (scope=host, manual, risk=none) |
| `remote_oql_execution_failed` | error | The remote OQL agent rejected or could not complete the requested operation. | — |

## hardware

| Code | Severity | Summary | Repair |
|------|----------|---------|--------|
| `boardnet_power_condition_active` | warning | BoardNet reports an active power, throttling or thermal condition. | — |
| `boardnet_power_condition_historical` | warning | BoardNet reports a power, throttling or thermal condition since boot. | — |
| `boardnet_power_telemetry_unavailable` | warning | Raspberry Pi power telemetry is unavailable on BoardNet. | `restore_boardnet_power_telemetry` (scope=host, manual, risk=none) |
| `boardnet_undervoltage_active` | critical | BoardNet reports active Raspberry Pi supply undervoltage. | `restore_boardnet_power` (scope=host, manual, risk=physical) |
| `hw_dri0050_sidecar_unreachable` | error | dri0050-motor-api sidecar (:8203, pump) is unreachable or unhealthy. | `dri0050-ensure-sidecar` (scope=oqlos, auto, risk=config) |
| `hw_modbus_no_response` | error | Modbus RTU slave did not answer (read timed out / no response) on the configured serial path. | `modbus-physical-check` (scope=host, manual, risk=none) |
| `hw_modbus_serial_handle_stale` | warning | A Modbus RTU plugin (modbus-io/modbus-adc) has a stale USB/RS485 serial handle after device re-enumeration (errno 19). | `modbus-plugin-reconnect` (scope=oqlos, auto, risk=none) |
| `hw_tic249_sidecar_unreachable` | error | hw-tic249 sidecar (:8205, lung motor) is unreachable or not connected to the Pololu Tic USB device. | `tic249-ensure-sidecar` (scope=oqlos, auto, risk=config) |
| `hw_usb_adc_sidecar_unreachable` | error | usb-adc-stack sidecar (:8214, MCP2221A/DFR1184) is unreachable or returned no channels. | `usb-adc-ensure-sidecar` (scope=oqlos, auto, risk=config) |
| `modbus_adapter_only` | warning | USB serial adapter is visible, but the device did not answer. Check RS485 wiring, power, slave address and baudrate. | — |
| `modbus_adc_adapter_only` | warning | USB serial adapter is visible, but the device did not answer. Check RS485 wiring, power, slave address and baudrate. | — |
| `modbus_adc_not_detected` | warning | Modbus ADC device was not detected on any probed serial port. | — |
| `modbus_not_detected` | error | Modbus RTU (modbus-io) device was not detected on any probed serial port. | — |
| `modbus_preflight_exception` | error | The Modbus topology preflight failed before a valid report could be produced. | — |
| `serial_port_busy` | warning | The configured Modbus serial port is already open by another process. | `release_serial_port` (scope=host, manual, risk=none) |

## Dynamic code families

These are not fixed codes but templates — one concrete code exists per runtime value (e.g. per adapter id).

| Pattern | Domain | Severity | Summary |
|---------|--------|----------|---------|
| `adapter_*_not_ok` | hardware | warning | A specific firmware adapter's `status` is not `ok` (e.g. `adapter_modbus-io_not_ok`). |
| `adapter_*_health_not_ok` | hardware | warning | A specific firmware adapter's health check did not report healthy (e.g. `adapter_modbus-io_health_not_ok`). |
