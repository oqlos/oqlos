# OQL v3 — Przykłady CONFIG / GOAL

## 1. Podstawowa inicjalizacja (`config-basic.oql`)

```oql
SCENARIO: Podstawowy przykład CONFIG + GOAL

CONFIG inicjalizacja:
  SET pump-main 0 l/min
  SET valve-nc 0
  WAIT 500ms

GOAL test-operacyjny:
  SET pompa-1 5.0 l/min
  WAIT 1s
  SET pompa-1 0 l/min
```

```bash
oqlctl oqlos/scenarios/examples/config-basic.oql --mode dry-run
```

## 2. Kalibracja systemu (`config-calibration.oql`)

```oql
SCENARIO: Kalibracja PSS7000
DEVICE_TYPE: BA
DEVICE_MODEL: PSS 7000

CONFIG otwarcie-zaworów:
  SET valve-nc 1
  SET valve-sc 1
  SET valve-wc 1
  WAIT 2s

CONFIG pomiar-bazowy:
  GET AI01
  SAVE baseline-nc
  GET AI02
  SAVE baseline-sc

CONFIG zamknięcie-zaworów:
  SET valve-nc 0
  SET valve-sc 0
  SET valve-wc 0
  WAIT 1s
  SAVE kalibracja-zakończona

GOAL weryfikacja-nc:
  WAIT 5s
  GET AI01
  SAVE ciśnienie-końcowe-nc
```

## 3. Wzorzec Prepare → Test → Cleanup (`config-test-pattern.oql`)

```oql
SCENARIO: Test Pattern — Prepare / Test / Cleanup
DEVICE_TYPE: BA

CONFIG prepare-environment:
  SET pump-main 0
  SET valve-nc 0
  SET valve-sc 1
  WAIT 1s

GOAL execute-pressure-test:
  SET pompa-1 5 l/min
  WAIT 3s
  GET AI02
  SAVE test-result
  SET pompa-1 0

CONFIG cleanup:
  SET pompa-1 0
  SET valve-sc 0
  WAIT 500ms
  SAVE cleanup-done
```

## 4. Biblioteki makr

Dla powtarzających się fragmentów używaj `INCLUDE` + `CALL`:

```oql
SCENARIO: Smoke z makrami
INCLUDE "lib/peripherals.oql"
INCLUDE "lib/hardware.oql"

CONFIG reset:
  CALL init-all

GOAL smoke:
  CALL hw-pump-smoke
  CALL hw-valves-smoke
```

Pełen rejestr makr: `oqlos/scenarios/lib/README.md`.

## Różnica CONFIG vs GOAL

- **CONFIG**: inicjalizacja, setup, kalibracja (oznaczany `[CONFIG]`
  w logach i uruchamiany przed GOAL-ami).
- **GOAL**: właściwe testy i procedury pomiarowe.

W output widzisz:
```
🎯 GOAL: [CONFIG] reset         ← CONFIG
🎯 GOAL: execute-pressure-test   ← GOAL
```

## Szybki start

```bash
ls oqlos/scenarios/examples/
oqlctl oqlos/scenarios/examples/config-basic.oql --mode dry-run
oqlctl oqlos/scenarios/examples/config-basic.oql --mode execute

# Jednorazowa komenda na sprzęt
oqlctl cmd "SET pompa-1 0"
oqlctl cmd "SET valve-nc 1" --mode dry-run

# Walidacja całego katalogu
oqlctl --validate-dir oqlos/scenarios
```

## Peryferia (HAL aliases)

| Peryferium | ID | Przykład |
|---|---|---|
| Pompa główna | `pump-main` / `pompa-1` | `SET pump-main 5 l/min` |
| Zawory NC/SC/WC | `valve-nc`, `valve-sc`, `valve-wc` | `SET valve-nc 1` |
| Zawory numerowane | `valve-1` … `valve-8` | `SET valve-3 0` |
| Zawory BO | `valve-bo04`, `valve-bo05`, `valve-bo06` | `SET valve-bo06 1` |
| Płuco | `lung-main` | `SET lung-main 2` |
| Sensory | `AI01`, `AI02`, `AI03` | `GET AI02` |
