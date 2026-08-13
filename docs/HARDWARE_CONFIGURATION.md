# Hardware configuration v1

`hardware-configuration-v1` is the only configuration contract consumed by
the OqlOS hardware plugin runtime. OQL, YAML and JSON are equivalent codecs for
that model; choosing a file extension does not change which settings are
available.

## Configuration scope

| Section | Purpose |
|---|---|
| `metadata` | node identity and descriptive metadata |
| `devices` | physical device inventory |
| `plugins` | drivers, connection parameters, timeouts, retries and peripherals |
| `aliases` | logical names, hardware targets, units and conversions |
| `sensors` | channels, bindings and measurement metadata |
| `processes` | URI, mode, outputs, polling, timeout and retry policy |
| `actions` | logical actions and object bindings |
| `functions` | function/catalog bindings |
| `profiles` | HUI holds, valves, lung recipes and other named profiles |
| `runtime` | driver runtime limits such as `motor2` |
| `variables` | operator/runtime variables |
| `policies` | availability, degraded mode and retry policies |
| `secretRefs` | references to external secrets; never secret values |

Unknown top-level fields, inline secrets and invalid runtime constraints are
rejected. `runtime.motor2`, for example, enforces positive stroke/speed values,
default speed not exceeding maximum speed, valid direction/limit mode and
bounded acceleration.

For the Tic249 artificial-lung drive, idle behavior is explicit:

```yaml
runtime:
  motor2:
    idleState: deenergized
    deenergizeOnStop: true
    deenergizeOnStartup: true
```

`deenergized` is the normal policy for a motor mechanism that does not require
holding torque. A STOP first halts motion and then sends `energize=false`; OqlOS
also releases the coils during startup. Use `idleState: holding` with both
flags disabled only for a mechanism whose safety analysis explicitly requires
holding torque while stationary.

## Files and precedence

OqlOS resolves `OQLOS_CONFIG_PATH` first and otherwise searches the supported
`oqlos.oql`, `oqlos.yaml`, `oqlos.yml` and `oqlos.json` locations. Exactly one
file is active. It is parsed into `HardwareConfiguration` before plugins or HUI
profiles read it.

Environment variables are operational overrides, not another configuration
format. The API exposes configured and effective values plus an auditable diff.
Supported overrides include plugin base URLs and Modbus serial/UART parameters.
Secrets stay outside files and are named through `secretRefs`.

## Safe API

The versioned API is mounted at `/api/v3/hardware/configuration`:

- `GET /`, `/schema`, `/files`, `/source`
- `POST /validate`, `/convert`
- `PUT /source`

Writes require authenticated `system`/administrator authority, validate the
complete document, enforce safe file names and use atomic replacement. A save
does not execute OQL, restart services or actuate hardware. The response marks
the configuration as persisted but not applied and reports that a controlled
restart is required.

## Offline workflow

```bash
oqlos-hardware-config validate oqlos.yaml
oqlos-hardware-config effective oqlos.yaml
oqlos-hardware-config convert oqlos.yaml oqlos.oql
oqlos-hardware-config convert oqlos.oql oqlos.json
oqlos-hardware-config migrate-legacy hardware-map.yaml oqlos.yaml
```

Conversion is deterministic and semantically lossless. The migrator explicitly
maps `runtimeConfig`, `objectActionMap`, `paramSensorMap`,
`funcImplementations` and `operatorVariables`; it does not leave a runtime
fallback to the legacy file.

Complete parity fixtures are in `examples/hardware-configuration/boardnet.*`.

## Removed compatibility surface

The following routes and their stores are retired and return 404:

- `/api/v3/hardware/mapping*`
- `/api/v3/hardware/oql-mapped-exec`
- `/api/v3/hardware/runtime-python/resolve-func`
- `/map`, `/map-editor`, `/ui/map-editor`

Hardware commands continue through explicit OQL/process or CQRS endpoints.
Configuration availability must never be inferred from hardware actuation: a
healthy editor can coexist with a degraded device such as unavailable
`modbus-io`, which remains an explicit 503 diagnostic condition.

## Valve output stage

The valve output module is configurable: `modbus-io` (Waveshare RS485) or
`io-m5-4in8out` (M5Stack 4In8Out, I2C). See
[VALVE_OUTPUT_MODULES.md](VALVE_OUTPUT_MODULES.md) for selection rules, wiring
and the migration path.
