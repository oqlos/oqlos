# OQL Language Specification v3.0 (Flat Syntax)

## 1. Filozofia

OQL (Operation Query Language) jest deklaratywnym DSL do testów sprzętu
diagnostycznego (aparaty oddechowe Dräger, piADC, pompy DRI0050, zawory
Modbus, płuca TIC249, itd.).

Wersja 3 radykalnie upraszcza składnię:

- **Bez cudzysłowów** — identyfikatory są gołe (`pump-main`, nie `'pump-main'`).
- **Bez znaku `=`** — każda komenda zna swoją strukturę argumentów, więc
  parser nie musi zgadywać.
- **Płaska struktura** — brak `IF/ELSE/ENDIF`. Warunki to `CHECK min <= sensor <= max unit`.
- **Makra zamiast bogatej gramatyki** — tylko 12 komend bazowych; wszystko
  inne to `MACRO` wywoływane przez `CALL`.
- **Pełny Unicode** — polskie znaki, `°`, `³`, `μ` są legalne w nazwach.

## 2. Anatomia linii

```
SET   pump-main   5.0   l/min
 │         │       │     │
 │         │       │     └─ UNIT   opcjonalny, może zawierać '/'
 │         │       └──────── VALUE liczba (int | float | ujemna)
 │         └──────────────── TARGET identyfikator
 └────────────────────────── CMD    zawsze UPPERCASE
```

## 3. Komendy bazowe (12)

| Komenda | Składnia | Działanie |
|---|---|---|
| `SET`     | `SET target value [unit]`           | Ustaw peryferium lub zmienną |
| `GET`     | `GET sensor`                        | Odczytaj sensor (alias `READ`) |
| `WAIT`    | `WAIT duration`                     | `3s`, `500ms`, `3000` (bare = ms) |
| `SAVE`    | `SAVE label`                        | Zapisz bieżący wynik do protokołu |
| `CHECK`   | `CHECK min <= sensor <= max unit`   | Range assertion |
| `MIN`     | `MIN sensor value unit`             | Dolna granica |
| `MAX`     | `MAX sensor value unit`             | Górna granica |
| `SAMPLE`  | `SAMPLE sensor START\|STOP [interval]` | Sampling w tle |
| `LOG`     | `LOG "wiadomość"`                   | Wiadomość informacyjna |
| `ERROR`   | `ERROR "wiadomość"`                 | Przerwij z błędem |
| `CALL`    | `CALL macro-name [arg1 arg2 …]`     | Wywołanie makra |
| `INCLUDE` | `INCLUDE "ścieżka.oql"`             | Dołącz bibliotekę makr |

### 3.1 Nagłówki bloków

- `GOAL:` — blok wykonawczy (cel testowy). Nazwa ustawiana przez `SET NAME 'nazwa'` wewnątrz bloku.
- `GOAL name:` — stara składnia, nadal obsługiwana dla kompatybilności wstecznej.
- `CONFIG name:` — blok inicjalizacyjny; semantycznie identyczny z `GOAL`,
  ale oznaczony `[CONFIG]` w logach.
- `MACRO name:` — definicja makra (ciało rozwijane przy `CALL`).

Nazwa bloku GOAL może być ustawiona przez `SET NAME 'nazwa'` (nowa składnia) lub
bezpośrednio w nagłówku (stara składnia). Dla nazw ze spacjami użyj `SET NAME 'Nazwa wielowyrazowa'`.

### 3.2 Metadane

Poza blokami można zdefiniować metadane (klucz UPPER_SNAKE, wartość tekstowa):

```oql
SCENARIO: Test szczelności maski
DEVICE_TYPE: BA
DEVICE_MODEL: PSS 7000
MANUFACTURER: Dräger
DESCRIPTION: Pełen test leak-test dla PSS 7000
CATEGORY: env
```

## 4. Reguły tokenizacji

Parser nie zgaduje — każda komenda zna swoją strukturę:

1. **Podział na CMD + reszta** (`split(None, 1)`) — pierwszy token to nazwa
   komendy, reszta idzie do parsera komendy.
2. **`WAIT`** — jedyna komenda, gdzie value i unit mogą być sklejone:
   `3s` → `(3, 's')`, `3000` → `(3000, 'ms')`.
3. **`SET/MIN/MAX`** — unit to wszystko po pierwszej liczbie; może zawierać
   `/` i Unicode: `l/min`, `°C`, `%RH`, `m³/h`.
4. **`CHECK`** — ma własne regex `(NUM) <= (IDENT) <= (NUM) (UNIT)?`.
5. **Dispatch table** — zamiast jednego `if/elif`, każda komenda ma własną
   funkcję parsującą. Dodanie komendy = dopisanie jednej funkcji + wpis
   w słowniku.

## 5. Identyfikatory i wartości

### 5.1 Identyfikatory

Unicode dozwolone. Reguła: identyfikator to token bez białego znaku i
bez znaków składniowych (`#`, `:`, `=`, `"`, `'`, `[`, `]`).

```oql
pump-main         # OK
ciśnienie-NC      # OK (polskie znaki)
valve-bo06        # OK
AI01              # OK
```

Dla nazw ze spacjami użyj nawiasów kwadratowych:

```oql
SET [pompa głównego obiegu] 5 l/min
SAVE [wynik testu maski]
```

### 5.2 Liczby

Int, float, ujemne. Przecinek i kropka obsługiwane:
`0`, `5.0`, `-10.5`, `145`, `3,14`.

### 5.3 Jednostki

Jeden token po liczbie; może zawierać `/`, Unicode, cyfry:
`bar`, `mbar`, `l/min`, `°C`, `%RH`, `m³/h`, `Pa`.

### 5.4 Duration

`3s`, `500ms`, `60s`, `3000` (bare = ms), `2m`, `1h`.

### 5.5 Stringi

Tylko w `LOG`, `ERROR`, `INCLUDE` (wiadomości i ścieżki):

```oql
LOG "Rozpoczynam fazę 2"
ERROR "Ciśnienie poza zakresem"
INCLUDE "lib/hardware.oql"
```

Obsługiwane `"..."` i `'...'`; escape `\"` / `\\`.

## 6. Makra i INCLUDE

### 6.1 Definicja makra

```oql
MACRO hw-pump-smoke:
  SET pump-main 5 l/min
  WAIT 2s
  SET pump-main 0
```

### 6.2 Wywołanie

```oql
GOAL diagnostyka:
  CALL hw-pump-smoke
```

### 6.3 Argumenty pozycjonalne

Makro może używać placeholders `$1`, `$2`, … (tekstowe podstawienie
wykonywane przed tokenizacją):

```oql
MACRO set-pump-lpm:
  SET pump-main $1 l/min
  WAIT $2

GOAL ramp:
  CALL set-pump-lpm 3 500ms
  CALL set-pump-lpm 5 500ms
  CALL set-pump-lpm 0 200ms
```

### 6.4 INCLUDE

`INCLUDE "ścieżka"` rozwiązywane względem:

1. ścieżki absolutnej,
2. katalogu pliku wywołującego,
3. `oqlos/scenarios/` (korzeń).

Makra z włączonych plików stają się dostępne w aktualnym dokumencie.
Definicje lokalne mają pierwszeństwo.

## 7. Aliasy sprzętowe (HAL)

Targety rozwiązywane przez interpreter do adapterów sprzętowych:

- **Zawory**: `valve-nc`, `valve-sc`, `valve-wc`, `valve-1` … `valve-8`,
  `valve-bo04`, `valve-bo05`, `valve-bo06`.
- **Pompy**: `pump-main` (DRI0050), `pompa-1` (alias).
- **Płuco**: `lung-main` (TIC249).
- **Sensory**: `AI01` (NC), `AI02` (SC), `AI03` (WC).

## 8. Pełny przykład

```oql
SCENARIO: PSS 7000 — Test szczelności maski
DEVICE_TYPE: BA
DEVICE_MODEL: PSS 7000
MANUFACTURER: Dräger

INCLUDE "lib/peripherals.oql"

CONFIG reset:
  CALL init-all

GOAL:
  SET NAME 'Test statyczny SC'
  SET pump-main 0
  WAIT 3s
  GET AI02
  SAVE ciśnienie-sc
  IF AI02 6.0 .. 8.0 bar
  CORRECT 'Ciśnienie SC w normie'
  ERROR 'Ciśnienie SC poza zakresem'

GOAL:
  SET NAME 'Ciśnienie otwarcia automatu'
  SET pump-main 5.0 l/min
  SET valve-bo06 1
  WAIT 8s
  GET AI01
  SAVE ciśnienie-nc-min
  IF AI01 -29.0 .. -5.0 mbar
  CORRECT 'Ciśnienie otwarcia w normie'
  ERROR 'Ciśnienie otwarcia poza zakresem'

GOAL:
  SET NAME 'Koniec'
  CALL stop-all
  LOG "Test zakończony"
  SAVE test-done
```

## 9. Kompatybilność

Interpreter detektuje automatycznie składnię:

- **v3 (flat):** `GOAL:` + `SET NAME 'nazwa'` / `CONFIG name:` / `MACRO name:` / `INCLUDE "..."`.
- **v3 (legacy):** `GOAL name:` nadal działa dla kompatybilności wstecznej.
- **v1/v2 (legacy, z cudzysłowami):** `GOAL: Name` + `'target' 'value'`.

Nowa składnia `GOAL:` + `SET NAME 'nazwa'` jest zalecana dla wszystkich nowych
scenariuszy. Pliki v1/v2 działają na starej ścieżce parsera (deprecated).

## 10. Referencje

- Anatomia tokenów: `docs/oql-grammar-anatomy.html`
- Biblioteki makr: `oqlos/scenarios/lib/README.md`
- Cheatsheet: `oqlos/scenarios/OQL-CHEATSHEET.md`
- Parser: `oqlos/core/oql_parser.py`
- Adapter: `oqlos/core/_oql_adapter.py`
