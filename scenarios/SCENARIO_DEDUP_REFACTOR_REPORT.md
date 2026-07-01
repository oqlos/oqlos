# Scenario Dedupe / Refactor Report

Checked on 2026-06-30.

## Directory Split

- Canonical OQL scenario root: `scenarios/`.
- Package directory `oqlos/scenarios/` no longer contains `.oql` scenario files.
- `oqlos/scenarios/legacy_aliases.py` is only a compatibility loader.
- Legacy alias data now lives in `scenarios/legacy_aliases.json`.

## Duplicate Analysis

No byte-identical `.oql` duplicates were found under `scenarios/`.

Parser validation:

- `scenarios/` contains 52 `.oql` files in total.
- All 52 files currently parse in `dry-run` validation mode.
- This does not mean every file is current style; the old syntax candidates below
  are accepted for compatibility but should still be normalized.

Semantic / historical duplicates:

| Legacy/archive file | Canonical/current file | Status |
|---|---|---|
| `archive/ts-export-2026-04-30/ts-flow.oql` | `test-przeplywu.oql` | archive-only legacy export |
| `archive/ts-export-2026-04-30/ts-kalibracja-czujnikow.oql` | `kalibracja-czujnikow.oql` | archive-only legacy export |
| `archive/ts-export-2026-04-30/ts-kaskadowy-cisnienie.oql` | `kaskadowy-pomiar-cisnienia-z-przelaczaniem-czujnikow.oql` | archive-only legacy export |
| `archive/ts-export-2026-04-30/ts-pelny-test-cisnieniowy.oql` | `pelny-test-cisnieniowy-z-przelaczaniem-zakresow.oql` | archive-only legacy export |
| `archive/ts-export-2026-04-30/ts-spadek-cisnienia.oql` | `test-spadku-cisnienia-automatu.oql` | archive-only legacy export |
| `archive/ts-export-2026-04-30/ts-wytrzymalosc-mech.oql` | `test-wytrzymalosci-mechanicznej.oql` | archive-only legacy export |
| `drager-fps-7000-pelny-test-maski.oql` | `dragerfps7000-pelnytestmaski.oql` | same subject; keep the flat/sequential file as canonical candidate |

## Old Syntax / Refactor Candidates

High priority:

- `scenarios/archive/ts-export-2026-04-30/*.oql`
  - legacy DB export namespace,
  - several files still use direct `WAIT 1s` style instead of `SET WAIT '1 s'`,
  - some use `PUMP`, `pompa_1`, or unquoted values.
- `scenarios/lib/hardware.oql`
  - unquoted `SET pump-main ...` / `SET valve-nc ...`;
  - should be normalized to quoted `SET 'id' 'value'`.
- `scenarios/lib/peripherals.oql`
  - same unquoted hardware ids;
  - should be normalized before using it as the shared macro library.

Medium priority:

- `drager-fps-7000-pelny-test-maski.oql`
  - overlaps with `dragerfps7000-pelnytestmaski.oql`;
  - choose one canonical filename and move the other to `archive/` or alias it.
- `kalibracja-czujnikow.oql`
- `kaskadowy-pomiar-cisnienia-z-przelaczaniem-czujnikow.oql`
- `pelny-test-cisnieniowy-z-przelaczaniem-zakresow.oql`
- `test-spadku-cisnienia-automatu.oql`
- `test-temperatury-i-wilgotnosci.oql`
  - contain unquoted `SAMPLE` targets or legacy/noncanonical hardware ids.

Hardware-id cleanup candidates:

- `pump-main` should be verified against the current OqlOS mapping; current direct hardware smoke tests use `pompa-1`.
- Polish/free-text device ids such as `pompa-próżniowa`, `pompa-ciśnieniowa`, `zawór-butli-300bar` should either be added to mapping intentionally or rewritten to canonical mapped ids.

## Current Policy

- Root `scenarios/*.oql` and `scenarios/examples/*.oql` are active candidates.
- `scenarios/archive/**` is retained for traceability, not active runtime execution.
- New runtime paths must refer to `scenarios/`, not `oqlos/scenarios/`.
