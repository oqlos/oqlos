# OQL v3 Cheatsheet

## Kompletny zestaw 12 komend

```oql
SET target value [unit]          # ustaw peryferium/zmienną
GET sensor                       # odczytaj sensor (alias: READ)
SET WAIT 'duration'              # pauza, np. SET WAIT '1 s'
WAIT duration                    # legacy alias, np. 3s, 500ms
SAVE label                       # zapisz wynik do protokołu
CHECK min <= sensor <= max unit  # range assertion
MIN sensor value unit            # dolna granica
MAX sensor value unit            # górna granica
SAMPLE sensor START|STOP [int]   # sampling w tle
LOG "wiadomość"                  # log info
ERROR "wiadomość"                # abort z błędem
CALL macro-name [args...]        # wywołaj makro
INCLUDE "ścieżka.oql"            # dołącz bibliotekę
```

Plus bloki: `GOAL:`, `CONFIG name:`, `MACRO name:`.
Nowa składnia GOAL: nazwa ustawiana przez `SET NAME 'nazwa'` wewnątrz bloku.
Stara składnia `GOAL name:` nadal działa dla kompatybilności wstecznej.

## Anatomia

```
SET   pump-main   5.0   l/min
 │      │         │      │
 CMD   TARGET   VALUE   UNIT(opcjonalny, może zawierać '/' i Unicode)
```

## Metadane (poza blokami)

```oql
SCENARIO: Test szczelności
DEVICE_TYPE: BA
DEVICE_MODEL: PSS 7000
MANUFACTURER: Dräger
DESCRIPTION: Leak test
CATEGORY: env
```

## Podstawowe przykłady

### Pompa

```oql
SET pompa-1 5.0 l/min
SET WAIT '2 s'
SET pompa-1 0
```

### Zawór

```oql
SET valve-nc 1      # otwórz
SET WAIT '500 ms'
SET valve-nc 0      # zamknij
```

### Odczyt + assertion

```oql
GET AI01
SAVE ciśnienie-sc
CHECK 6.0 <= AI01 <= 8.0 bar
```

### Sampling w tle

```oql
SAMPLE ciśnienie START 50ms
SET WAIT '10 s'
SAMPLE ciśnienie STOP
GET ciśnienie
SAVE dp
```

## Spacje w identyfikatorach

Dwie opcje:

```oql
# kebab-case (zalecane)
SET pompa-główna 5 l/min
SAVE ciśnienie-końcowe

# kanoniczny SET dla nazw/wartości ze spacjami
SET 'pompa głównego obiegu' '5 l/min'
SAVE [wynik testu maski]
```

## Polskie znaki i Unicode

Pełny Unicode w identyfikatorach i wartościach:

```oql
SAVE ciśnienie-NC
CHECK 15 <= temperatura <= 25 °C
CHECK 30 <= wilgotność <= 70 %RH
SET multiplekser-μV 1
```

## WAIT

| Składnia | Znaczenie |
|---|---|
| `SET WAIT '500 ms'` | 500 ms |
| `SET WAIT '2 s'` | 2 sekundy |
| `SET WAIT '30 s'` | 30 sekund |
| `SET WAIT '2 m'` | 2 minuty |
| `WAIT 2s` | nadal obsługiwany zapis kompatybilny |

## CONFIG vs GOAL

```oql
# CONFIG — inicjalizacja, setup, kalibracja (wykonuje się pierwsze)
CONFIG reset:
  SET pump-main 0
  SET valve-nc 0
  SET WAIT '500 ms'

# GOAL — właściwy test
GOAL test-pressure:
  SET pompa-1 5 l/min
  SET WAIT '3 s'
  GET AI02
  CHECK 6.0 <= AI02 <= 8.0 bar
```

## Makra

```oql
INCLUDE "lib/hardware.oql"

MACRO pump-ramp:
  SET pump-main $1 l/min
  SET WAIT '$2'
  SET pump-main 0

GOAL test:
  CALL pump-ramp 5 2s
  CALL hw-valves-smoke
```

## Przykład pełny

```oql
SCENARIO: Test szczelności maski
DEVICE_TYPE: BA

INCLUDE "lib/peripherals.oql"

CONFIG reset:
  CALL init-all

GOAL:
  SET NAME 'Podciśnienie'
  SET pompa-1 5.0 l/min
  SET valve-nc 1
  SET WAIT '2 s'
  IF AI01 -11 .. -9 mbar
  CORRECT 'Podciśnienie w normie'
  ERROR 'Podciśnienie poza zakresem'
  SAVE podciśnienie-start

GOAL:
  SET NAME 'Obserwacja 60s'
  SET pompa-1 0
  SET WAIT '60 s'
  IF AI01 -11 .. -9 mbar
  CORRECT 'Podciśnienie stabilne'
  ERROR 'Podciśnienie niestabilne'
  SAVE podciśnienie-koniec
```

## Uruchamianie

```bash
# Dry-run (symulacja)
oqlctl scenariusz.oql --mode dry-run

# Wykonanie na sprzęcie
oqlctl scenariusz.oql --mode execute

# Pojedyncza komenda
oqlctl cmd "SET pompa-1 0"

# Walidacja wszystkich plików w katalogu
oqlctl --validate-dir scenarios
```

## Tryby sprzętu

```bash
# Mock (symulacja bez sprzętu)
export OQLOS_HARDWARE_MODE=mock

# Real (prawdziwy sprzęt)
export OQLOS_HARDWARE_MODE=real
export MOTOR_URL=http://localhost:49055
export PIADC_URL=http://localhost:8080
```

## Dostępne biblioteki makr

- `lib/hardware.oql` — `hw-pump-smoke`, `hw-valves-smoke`, `hw-lung-smoke`, `hw-sensors-baseline`, …
- `lib/peripherals.oql` — `init-pump`, `init-valves-main`, `init-valves-bo`, `init-valves-numbered`, `init-all`, `stop-all`

Pełna lista w `scenarios/lib/README.md`.
