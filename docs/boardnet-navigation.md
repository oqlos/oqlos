# BoardNet OqlOS navigation

BoardNet (`192.168.188.122`, `boardnet.local`) serves the OqlOS firmware UI and
API on port `8202`. Human pages use the **`/ui/*`** prefix (React SPA + static HTML).

Primary human entrypoints:

| URL | Purpose |
| --- | --- |
| `http://192.168.188.122:8202/ui/status` | BoardNet status: navigation index, runtime health, adapters, USB/serial/I2C diagnostics |
| `http://192.168.188.122:8202/ui/hardware-modbus` | Modbus autodetect wizard and adapter configuration |
| `http://192.168.188.122:8202/ui/hardware-rtc` | Waveshare DS3231 RTC and watchdog diagnostics (piRTC sidecar) |
| `http://192.168.188.122:8202/ui/motor-services` | Motor diagnostics and manual PWM/stepper tests (Tic249, DRI0050) |
| `http://192.168.188.122:8202/ui/scenario-files` | OQL scenario editor |
| `http://192.168.188.122:8202/ui/func-editor` | Function editor |
| `http://192.168.188.122:8202/ui/panel` | Direct OQL/manage test panel |
| `http://192.168.188.122:8202/docs` | FastAPI Swagger API docs |

Legacy paths without `/ui` (e.g. `/hardware-demo`, `/panel`, `/navigation`) redirect to
the canonical `/ui/*` URLs with query string preserved.

Short aliases (also redirect to `/ui/*`):

| Alias | Target |
| --- | --- |
| `/nav` | `/ui/status` |
| `/navigation` | `/ui/status` |
| `/status` | `/ui/status` |
| `/hardware-status` | `/ui/status` |
| `/restart` | `/ui/hardware-modbus` |
| `/hardware-restart` | `/ui/hardware-modbus` |
| `/modbus` | `/ui/hardware-modbus` |
| `/hardware-rtc` | `/ui/hardware-rtc` |
| `/rtc` | `/ui/hardware-rtc` |
| `/demo` | `/ui/motor-services` |
| `/hardware-demo` | `/ui/motor-services` |
| `/files` | `/ui/scenario-files` |
| `/functions` | `/ui/func-editor` |
| `/oql` | `/ui/panel` |
| `/oql-panel` | `/ui/panel` |
| `/panel` | `/ui/panel` |

Legacy UI paths `/ui/navigation` and `/ui/hardware-status` redirect to `/ui/status`.
Retired MAP paths `/map`, `/map-editor` and `/ui/map-editor` return 404. Hardware
configuration is edited through c2004 `connect-oql-system` using the versioned
`hardware-configuration-v1` API with equivalent OQL/YAML/JSON codecs.

Module-specific API examples (Modbus channels, RTC, motor-only diagnosis) are documented in
[hardware-ui-modules.md](hardware-ui-modules.md).

Machine-readable navigation:

```bash
curl -s http://192.168.188.122:8202/api/v1/navigation
```

Direct OQL/manage examples:

```bash
BASE=http://192.168.188.122:8202

curl -s -X POST "$BASE/api/v1/oql/execute" \
  -H 'Content-Type: application/json' \
  -d '{"kind":"command","mode":"execute","oql":"SET \"pompa-1\" \"0\""}'

curl -s -X POST "$BASE/api/v1/oql/manage" \
  -H 'Content-Type: application/json' \
  -d '{"verb":"health","args":{"scan":"never"}}'

curl -s -X POST "$BASE/api/v1/oql/manage" \
  -H 'Content-Type: application/json' \
  -d '{"verb":"usb-list"}'
```
