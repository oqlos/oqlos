# OQL Configuration Examples

## Przykłady użycia CONFIG i GOAL

### 1. Podstawowa inicjalizacja (config-basic.oql)

```oql
SCENARIO: 'Basic Init'
DEVICE_TYPE: 'BA'

# CONFIG - zawsze na początku
CONFIG: Reset zaworów
  SET 'valve-nc' 'closed'
  SET 'valve-sc' 'closed'
  WAIT 200

CONFIG: Wyłączenie pompy
  SET 'pump-main' '0'
  WAIT 500

# GOAL - właściwy test
GOAL: Test pompy
  SET 'pompa 1' '3 l/min'
  WAIT 2000
  SET 'pompa 1' '0'
```

Uruchomienie:
```bash
oqlctl run examples/config-basic.oql --mode execute
```

### 2. Kalibracja systemu (config-calibration.oql)

```oql
SCENARIO: 'Kalibracja PSS7000'
DEVICE_TYPE: 'BA'
DEVICE_MODEL: 'PSS 7000'

CONFIG: Otwarcie wszystkich zaworów
  SET 'valve-nc' 'open'
  SET 'valve-sc' 'open'
  SET 'valve-wc' 'open'
  WAIT 2000

CONFIG: Pomiar bazowy
  → Sensor.read AI01
  → Sensor.read AI02
  SAVE: baseline_nc
  SAVE: baseline_sc

CONFIG: Zamknięcie zaworów
  SET 'valve-nc' 'closed'
  SET 'valve-sc' 'closed'
  SET 'valve-wc' 'closed'
  WAIT 1000
  SAVE: kalibracja_zakonczona

GOAL: Weryfikacja szczelności
  WAIT 5000
  → Sensor.read AI01
  SAVE: cisnienie_koncowe
```

### 3. Wzorzec: Prepare → Test → Cleanup

```oql
SCENARIO: 'Test Pattern'
DEVICE_TYPE: 'BA'

# 1. PREPARE - CONFIG
CONFIG: Prepare Environment
  SET 'pump-main' '0'
  SET 'valve-nc' 'closed'
  SET 'valve-sc' 'open'
  WAIT 1000

# 2. TEST - GOAL
GOAL: Execute Test
  SET 'pompa 1' '5 l/min'
  WAIT 3000
  → Sensor.read AI02
  SAVE: test_result

# 3. CLEANUP - CONFIG
CONFIG: Cleanup
  SET 'pompa 1' '0'
  SET 'valve-sc' 'closed'
  WAIT 500
  SAVE: cleanup_done
```

## Szybki start

```bash
# 1. Sprawdź dostępne scenariusze
ls oqlos/oqlos/scenarios/examples/

# 2. Walidacja (dry-run)
oqlctl run oqlos/oqlos/scenarios/examples/config-basic.oql --mode dry-run

# 3. Wykonanie na sprzęcie
oqlctl run oqlos/oqlos/scenarios/examples/config-basic.oql \
  --mode execute \
  --firmware-url http://localhost:8202

# 4. Inicjalizacja wszystkich peryferii
oqlctl run oqlos/oqlos/scenarios/config-peripherals.oql --mode execute
```

## Komendy SET dla peryferii

| Peryferium | Wartości | Przykład |
|------------|----------|----------|
| `pump-main` / `pompa 1` | `'0'`, `'off'`, `'5 l/min'`, `'100'` | `SET 'pompa 1' '5 l/min'` |
| `valve-nc` | `'0'`, `'closed'`, `'1'`, `'open'` | `SET 'valve-nc' 'closed'` |
| `valve-sc` | `'0'`, `'closed'`, `'1'`, `'open'` | `SET 'valve-sc' 'open'` |
| `valve-1` do `valve-8` | `'0'`, `'closed'`, `'1'`, `'open'` | `SET 'valve-3' '0'` |

## Różnica CONFIG vs GOAL

- **CONFIG**: Używaj do inicjalizacji, setupu, kalibracji
- **GOAL**: Używaj do właściwych testów i procedur
- W output widzisz: `🎯 GOAL: [CONFIG] Nazwa` lub `🎯 GOAL: Nazwa`
