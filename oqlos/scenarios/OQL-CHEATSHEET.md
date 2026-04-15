# OQL Quick Reference

## Podstawowa struktura

```oql
SCENARIO: 'Nazwa'
DEVICE_TYPE: 'BA'
DEVICE_MODEL: 'PSS 7000'
MANUFACTURER: 'Dräger'

CONFIG: Inicjalizacja
  SET 'pompa 1' '0'
  WAIT 500

GOAL: Test
  SET 'pompa 1' '5 l/min'
  WAIT 2000
```

## Komendy SET dla peryferii

| Peryferium | Nazwy | Wartości | Przykład |
|------------|-------|----------|----------|
| **Pompa** | `pump-main`, `pompa 1`, `PUMP` | `'0'`, `'off'`, `'5 l/min'`, `'100'` | `SET 'pompa 1' '5 l/min'` |
| **Zawór NC** | `valve-nc`, `zawór NC` | `'0'`, `'closed'`, `'1'`, `'open'` | `SET 'valve-nc' 'closed'` |
| **Zawór SC** | `valve-sc`, `zawór SC` | `'0'`, `'closed'`, `'1'`, `'open'` | `SET 'valve-sc' 'open'` |
| **Zawór WC** | `valve-wc`, `zawór WC` | `'0'`, `'closed'`, `'1'`, `'open'` | `SET 'valve-wc' 'closed'` |
| **Zawory 1-8** | `valve-1` do `valve-8` | `'0'`, `'closed'`, `'1'`, `'open'` | `SET 'valve-3' '0'` |

## WAIT - czas oczekiwania

| Składnia | Znaczenie | Przykład |
|----------|-----------|----------|
| `WAIT 500` | 500 milisekund | `WAIT 500` |
| `WAIT 2000` | 2000 ms = 2 sekundy | `WAIT 2000` |
| `WAIT '2 s'` | 2 sekundy (jawne) | `WAIT '2 s'` |
| `WAIT '500 ms'` | 500 milisekund (jawne) | `WAIT '500 ms'` |

**Rule**: bare number = zawsze milisekundy

## CONFIG vs GOAL

```oql
# CONFIG - inicjalizacja, setup, kalibracja
CONFIG: Nazwa
  SET ...
  WAIT ...
  SAVE: init_done

# GOAL - właściwy test
GOAL: Nazwa
  SET ...
  → Sensor.read AI01
  SAVE: wynik
```

## Przykłady pełnych scenariuszy

### Minimalny scenariusz
```oql
SCENARIO: 'Test'
DEVICE_TYPE: 'BA'

GOAL: Pompa ON/OFF
  SET 'pompa 1' '5 l/min'
  WAIT 2000
  SET 'pompa 1' '0'
```

### Inicjalizacja + test
```oql
SCENARIO: 'Inicjalizacja i test'
DEVICE_TYPE: 'BA'

CONFIG: Reset
  SET 'pump-main' '0'
  SET 'valve-nc' 'closed'
  WAIT 500

GOAL: Test przepływu
  SET 'valve-nc' 'open'
  WAIT 200
  SET 'pompa 1' '3 l/min'
  WAIT 3000
  SET 'pompa 1' '0'
  SET 'valve-nc' 'closed'
```

## Uruchamianie

```bash
# Dry-run (symulacja)
oqlctl run scenariusz.oql --mode dry-run

# Wykonanie na sprzęcie
oqlctl run scenariusz.oql --mode execute

# Z custom firmware URL
oqlctl run scenariusz.oql \
  --mode execute \
  --firmware-url http://localhost:8202

# Krok po kroku (interaktywnie)
oqlctl run scenariusz.oql --step
```

## Dostępne pliki

```bash
# Pełna konfiguracja peryferii (11 GOALs)
oqlctl run scenarios/config-peripherals.oql

# Przykłady
oqlctl run scenarios/examples/config-basic.oql
oqlctl run scenarios/examples/config-calibration.oql
oqlctl run scenarios/examples/config-test-pattern.oql
```

## Hardware Mode

```bash
# Mock (symulacja bez sprzętu)
export HARDWARE_MODE=mock
oqlctl run scenariusz.oql

# Real (prawdziwy sprzęt)
export HARDWARE_MODE=real
export MOTOR_URL=http://localhost:49055
export PIADC_URL=http://localhost:8080
oqlctl run scenariusz.oql
```
