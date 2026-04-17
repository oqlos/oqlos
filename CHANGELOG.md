# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **OQL v3 — Flat Syntax** (`oqlos/core/oql_parser.py`): quote-free DSL
  with 12 base commands (`SET`, `GET`, `WAIT`, `SAVE`, `CHECK`, `MIN`,
  `MAX`, `SAMPLE`, `LOG`, `ERROR`, `CALL`, `INCLUDE`).
- Macro libraries in `oqlos/scenarios/lib/` (`hardware.oql`,
  `peripherals.oql`) + `$1`/`$2` positional placeholders.
- `INCLUDE "path"` directive resolved relative to the including file or
  `oqlos/scenarios/`.
- `CHECK min <= sensor <= max unit` range assertion replaces
  `IF/ENDIF` chains.
- Bracketed identifiers `[nazwa ze spacjami]` for multi-word names.
- Full Unicode support in identifiers (Polish: `ciśnienie-NC`, units
  like `°C`, `%RH`, `m³/h`).
- Adapter `oqlos/core/_oql_adapter.py` bridges v3 AST to the existing
  interpreter — no changes to `_interpreter_actions.py` needed.
- 30 unit tests (`tests/test_oql_parser_v3.py`).
- `docs/oql-grammar-anatomy.html` (visual reference).

### Changed
- All `.oql` scenarios in `oqlos/scenarios/` and
  `oqlos/scenarios/examples/` migrated to v3 flat syntax.
- Documentation rewritten: `README.md`, `docs/oql-spec.md`,
  `docs/cql-spec.md`, `oqlos/scenarios/OQL-CHEATSHEET.md`,
  `oqlos/scenarios/examples/README.md`.
- `parse_cql()` auto-detects flat v3 vs. legacy syntax.

### Removed
- Legacy `IF/ELSE/ENDIF`, `VAL`, `FUNC`, `GOTO` usage from all
  bundled scenarios (parser still accepts legacy sources for
  backward compatibility).
- `TODO/` folder (contents moved to `docs/` and
  `oqlos/core/oql_parser.py`).

## [0.1.1] - 2026-04-15

### Docs
- Update README.md

### Other
- Update oqlos/scenarios/test-zaworu.oql

