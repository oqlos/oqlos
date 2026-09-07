# Workspace reconciliation — 2026-09-07

This review compares legacy local work with OqlOS `4ba6e53` and OQL Scenario
`a88f8ab`. Commit ancestry and `git cherry` alone do not establish whether a
feature is missing: several old patches were incorporated into larger commits.

## CI repair

The September 6 Test workflow failed in `uv lock --check`: the root package in
`uv.lock` still declared `0.1.35`, while `pyproject.toml` declared `0.1.41`.
Commit `9dfd4b2` updates only that locked version. Dependency versions are
unchanged. The preceding workflow's Python, installed-wheel and frontend tests
passed; the failure was the lock validation step.

Local validation then exposed three stale assertions in the optional M5Stack
driver suite: the supported transports now include HTTP, disconnected commands
return structured error metadata, and StackNet offers `replace_valves` beyond the
common Modbus command set. The assertions now check those contracts. Driver
availability is checked only when connecting the mock I2C backend, so eight
driver-independent tests also execute on CI hosts without that optional package.

The hardware-doctor unit tests also left the ADC probe unmocked, causing roughly
17 seconds of host-dependent probing per test. A fixture now isolates that probe;
the tests continue to exercise report generation and the temporary configuration
repairs. No runtime hardware behavior changed in this maintenance pass.

## No-change receipt for issue #3

The two commits named in [issue #3](https://github.com/oqlos/oqlos/issues/3)
do not require replaying onto main:

| Legacy commit | Current implementation | Evidence |
| --- | --- | --- |
| `78a2c73` — load artificial-lung settings from OQL | `398bc0d` | OQL profile parsing, YAML override handling and stop-policy selection are present. The profile tests remain present. Subsequent work adds `params` support and explicitly sends `stop_at_limit=false` for immediate STOP. |
| `6195905` — publish Tic249 device profiles | `4302bea` | All 12 functions in `tic249_profile_source.py` match the legacy implementation by Python AST. Both test files match. The API handler additionally supplies the canonical public error code for an unsafe motor state. |

The legacy objects are retained under
`refs/recovery/oqlos-maintenance-20260907/78a2c73` and
`refs/recovery/oqlos-maintenance-20260907/6195905` in the local repository and in a
verified Git bundle. This receipt resolves the reconciliation requirement without
reintroducing older hardware behavior.

## Other legacy work

| Work item | Disposition and evidence |
| --- | --- |
| `oqlos-publish`, commit `8a1d934` | Superseded by `726ff6a` and later changes. Valve autoconfiguration, transport-specific diagnosis, configuration apply/confirmation, and their regression tests remain on main. Later code also refreshes the control lease after a network rebind. |
| `fix/hui-valve-routing-and-stop-attribution`, commit `ede2678` | Its changed Python functions are present, either identical or subsequently extended. Profile-specific Modbus health checks and disabled-profile handling are identical to main (`ab884f7`); the relevant frontend components and regression tests are retained. |
| `oqlos-bump-0141`, branch `bump-0.1.41` | Clean, and its commit is an ancestor of main. |
| `fix/tic249-dynamic-limit-diagnostic` | Its tip is an ancestor of main. |
| OQL Scenario `feature/unified-oql-network-dhcp`, commit `f864db3` | All three changed settings already match main: StackNet mDNS URL, configuration revision 2, and control API version 3. |
| `oql-scenario-publish` working change | Configuration revision 2 and `network.interface=default` already exist on main. The remaining version bump to 7 conflicts with the corpus test requiring OQL 6. Preserve the snapshot rather than porting that bump or the stale surrounding profile. |
| OQL Scenario `stash@{0}` from July 28 | Its idle-policy additions are already present: `idleState=deenergized`, `deenergizeOnStop=true`, and `deenergizeOnStartup=true`. Main also contains newer scenario metadata and runtime defaults. |

## Recovery and remaining local work

Before cleanup, snapshot `oqlos-maintenance-20260907-080350` captured staged and
unstaged binary patches, modified/untracked files, worktree metadata, the nested
Modbus submodule, and Git bundles for both OqlOS object stores and OQL Scenario.
Complete archives of the three obsolete worktrees were checked file by file
against their source directories. The external snapshot includes an archive
manifest and SHA-256 hashes.

Cleanup removed three archived worktrees (`oqlos-bump-0141`, `oqlos-publish`, and
`oql-scenario-publish`), seven reconciled local branches, and the superseded
motor2 stash. Recovery refs retain every removed branch tip and stash commit.
The active `oqlos-m122-main` worktree remains available. Remote feature branches
were left intact. Clean workspace checkouts of OqlOS, `.github`,
`backend-shared-py`, and `www` were advanced with fast-forward merges.

The following independent working directories still contain local edits and are
preserved for separate implementation reviews:

- `m5-4in8out`: README edits;
- `piadc`: service changes and a new platform module;
- `pimodbus`: client/discovery/repair changes, new repair models and tests, and
  nested `modbus-monitor-waveshare` changes;
- `rpi-motor-TB6560`: controller/server changes and extracted helper modules;
- `rpi-motor-TB6600`: diagnostic/controller/server changes and extracted helpers;
- `usb-adc-mcp2221`: CLI changes.

Backing these up does not validate or publish their implementation.

The July 30 metrics in `TODO.md` remain a historical baseline, not a fresh count
of missing features. This reconciliation does not remeasure the architectural
roadmap or perform hardware validation.

## Validation

- `uv lock --check` passes with uv 0.11.9.
- Full local `pytest -q --durations=5`: **1319 passed in 13.57 seconds**.
- M5Stack tests with the optional driver deliberately unavailable: **8 passed,
  10 skipped**; only connection-dependent tests skip.
- OQL Scenario `pytest -q`: **66 passed**.
- Frontend `npm run test:unit`: **158 passed**; `npm run build` succeeds with the
  existing warning about a JavaScript chunk above 500 kB.
- Ruff undefined/duplicate-definition checks and lint of both changed test files
  pass; `git diff --check` passes.
- [CI for the lock repair](https://github.com/oqlos/oqlos/actions/runs/34089501376)
  passes all four jobs, including static analysis and installed-wheel tests.
