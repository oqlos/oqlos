# BoardNet OqlOS navigation

BoardNet (`192.168.188.122`, `boardnet.local`) serves the OqlOS firmware UI and
API on port `8202`. Human pages use the **`/ui/*`** prefix (React SPA + static HTML).

Primary human entrypoints:

| URL | Purpose |
| --- | --- |
| `http://192.168.188.122:8202/ui/navigation` | Operator navigation and curl examples |
| `http://192.168.188.122:8202/ui/hardware-status` | Hardware health and diagnostics |
| `http://192.168.188.122:8202/ui/hardware-restart` | Hardware restart/detection wizard |
| `http://192.168.188.122:8202/ui/hardware-demo` | Manual hardware demo controls |
| `http://192.168.188.122:8202/ui/map-editor` | MAP and hardware binding editor |
| `http://192.168.188.122:8202/ui/scenario-files` | OQL scenario editor |
| `http://192.168.188.122:8202/ui/func-editor` | Function editor |
| `http://192.168.188.122:8202/ui/panel` | Direct OQL/manage test panel |
| `http://192.168.188.122:8202/docs` | FastAPI Swagger API docs |

Legacy paths without `/ui` (e.g. `/hardware-demo`, `/panel`, `/navigation`) redirect to
the canonical `/ui/*` URLs with query string preserved.

Short aliases (also redirect to `/ui/*`):

| Alias | Target |
| --- | --- |
| `/nav` | `/ui/navigation` |
| `/status` | `/ui/hardware-status` |
| `/restart` | `/ui/hardware-restart` |
| `/demo` | `/ui/hardware-demo` |
| `/map` | `/ui/map-editor` |
| `/files` | `/ui/scenario-files` |
| `/functions` | `/ui/func-editor` |
| `/oql` | `/ui/panel` |
| `/oql-panel` | `/ui/panel` |
| `/panel` | `/ui/panel` |
| `/navigation` | `/ui/navigation` |

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
