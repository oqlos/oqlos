# OqlOS monorepo packages

Split distributions installed under the shared `oqlos.*` namespace:

| Package | PyPI name | Contents |
|---------|-----------|----------|
| `oqlos-models/` | `oqlos-models` | `oqlos.models.*` — scenario/peripheral/DSL pydantic models |
| `oqlos-core/` | `oqlos-core` | `oqlos.core.*` — CQL/OQL parser, adapter, safe_eval (no hardware) |

Main package `oqlos` (repo root) keeps runtime + hardware: `interpreter`, `executor`, `api`, `hardware`.

## Local dev

```bash
make install-dev   # pip install -e packages/oqlos-models -e packages/oqlos-core -e .
make test
```

## Consumers (e.g. c2004)

- Today: `oqlos>=0.1.29` (meta package pulls `oqlos-models` + `oqlos-core`).
- Next: `backend/dsl` may depend only on `oqlos-core` once published.
