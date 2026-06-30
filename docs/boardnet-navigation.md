# BoardNet OqlOS navigation

BoardNet (`192.168.188.122`, `boardnet.local`) serves the OqlOS firmware UI and
API on port `8202`.

Primary human entrypoints:

| URL | Purpose |
| --- | --- |
| `http://192.168.188.122:8202/navigation` | Operator navigation and curl examples |
| `http://192.168.188.122:8202/hardware-status` | Hardware health and diagnostics |
| `http://192.168.188.122:8202/hardware-restart` | Hardware restart/detection wizard |
| `http://192.168.188.122:8202/hardware-demo` | Manual hardware demo controls |
| `http://192.168.188.122:8202/map-editor` | MAP and hardware binding editor |
| `http://192.168.188.122:8202/scenario-files` | OQL scenario editor |
| `http://192.168.188.122:8202/func-editor` | Function editor |
| `http://192.168.188.122:8202/panel` | Direct OQL/manage test panel |
| `http://192.168.188.122:8202/docs` | FastAPI Swagger API docs |

Short aliases:

| Alias | Target |
| --- | --- |
| `/nav` | `/navigation` |
| `/status` | `/hardware-status` |
| `/restart` | `/hardware-restart` |
| `/demo` | `/hardware-demo` |
| `/map` | `/map-editor` |
| `/files` | `/scenario-files` |
| `/functions` | `/func-editor` |
| `/oql` | `/panel` |
| `/oql-panel` | `/panel` |

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
