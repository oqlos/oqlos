# OqlOS TODO

## P0 — Critical

- [ ] `_cmd_to_actions` CC=24 in `oqlos/core/_interpreter_actions.py` — split into per-command handlers with dispatch table
- [ ] pytest coverage not collected — add `pytest-cov` + `.coveragerc`

## P1 — Quality

- [ ] `oql_parser.py` — `parse_flat_syntax` CC>15 — split per-construct parsers
- [ ] `_oql_adapter.py` — god adapter (maps all 12 commands) — extract per-command adapters
- [ ] API routes in `oqlos/api/` lack request validation — add Pydantic models

## P2 — Features / Backlog

- [ ] WebSocket support for real-time sensor streaming
- [ ] `INCLUDE` directive — add circular-include detection
- [ ] `CHECK` assertion — structured failure reporting (expected vs. actual)
- [ ] Hardware mock server for testql CI runs (currently requires live device)

## Tests

- [ ] Run `testql run testql-scenarios/generated-api-smoke.testql.toon.yaml` (needs running OqlOS server)
- [ ] Run `testql run testql-scenarios/generated-from-scenarios.testql.toon.yaml`
- [ ] Run `testql run testql-scenarios/cross-project-integration.testql.toon.yaml`

## ✅ Done

- [x] OQL v3 flat syntax parser with 12 base commands
- [x] Macro libraries (`hardware.oql`, `peripherals.oql`) with `$1`/`$2` placeholders
- [x] `INCLUDE` directive with relative path resolution
- [x] `CHECK min <= sensor <= max unit` range assertion
- [x] Bracketed identifiers for multi-word names
- [x] Full Unicode support in identifiers and units
- [x] 30 unit tests for OQL v3 parser
- [x] testql-scenarios generated (5 files)
