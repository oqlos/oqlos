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

- **Done locally:** `c2004/backend/dsl` depends on `oqlos-models>=0.2.0` + `oqlos-core>=0.2.1` (see `c2004/project/refactor-tasks.yaml` REF-A3).
- Meta package `oqlos>=0.1.29` still pulls models + core for full hardware consumers (`backend/firmware`).
- Publish to PyPI required for clean CI without editable install (REF-A2).
