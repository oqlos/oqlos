# OQL VERSION: 4 — Manual migracji, testowania i naprawy

Ten dokument opisuje jak **LLM** i developer mają:
- pobrać scenariusz (np. `http://localhost:8096/scenarios?scenario=maskleaktest-cisnienieotwarciazaworu`),
- wykryć stare wzorce,
- zaktualizować do `VERSION: 4`,
- zweryfikować poprawność parserem/runtime.

Przed testem na realnym sprzęcie uruchom:

```bash
oqlctl doctor
oqlctl detect
```

Migracja syntaktyczna ma przechodzić `dry-run`; `execute` uruchamiaj dopiero,
gdy `doctor` nie zgłasza błędów blokujących, a ostrzeżenia są świadomie
zaakceptowane przez operatora.

## 1) Docelowe reguły VERSION: 4

1. Pierwsza istotna linia: `VERSION: 4`.
2. Nagłówek celu:
   - było: `GOAL: Pełny test maski`
   - ma być:
     - `GOAL:`
     - `  SET NAME 'Pełny test maski'`
3. Pętle:
   - `LOOP ...` -> `REPEAT X:`
   - zakończenie pętli: `REPEAT STOP`
4. Komendy `SET` w scenariuszach biznesowych:
   - preferowane: `SET 'Target' 'Value'`
5. Każda zmiana musi przejść `dry-run` interpretera.

## 2) Procedura LLM: pobierz -> oceń -> popraw -> przetestuj

### Krok A: pobranie scenariusza

```bash
curl -s "http://localhost:8096/scenarios?scenario=maskleaktest-cisnienieotwarciazaworu"
```

Jeśli endpoint zwraca JSON, LLM powinien odczytać pole `code` lub `dsl`.

### Krok B: walidacja automatyczna

```bash
python3 scripts/oql_v4_validator.py \
  --url "http://localhost:8096/scenarios?scenario=maskleaktest-cisnienieotwarciazaworu" \
  --pretty
```

Walidator zwraca raport JSON zgodny z:
- `docs/oql_v4_llm_validator.schema.json`

### Krok C: naprawa scenariusza

LLM stosuje poprawki w kolejności:
1. `VERSION: 4`
2. `GOAL:` + `SET NAME '...'`
3. `LOOP/REPEATS` -> `REPEAT X:`
4. syntaktyka `REPEAT STOP`
5. porządek i czytelność komend

### Krok D: test uruchomieniowy

```bash
python3 scripts/oql_v4_validator.py --file path/to/scenario.oql --pretty
```

oraz (opcjonalnie cały katalog):

```bash
python3 - <<'PY'
import os
from oqlos.core.interpreter import CqlInterpreter
root = 'oqlos/scenarios'
ok = fail = 0
for d, _, fs in os.walk(root):
    for f in fs:
        if f.endswith('.oql'):
            p = os.path.join(d, f)
            r = CqlInterpreter(mode='dry-run', quiet=True).run(open(p, encoding='utf-8').read(), p)
            if r.ok:
                ok += 1
            else:
                fail += 1
                print('FAILED:', p)
print({'ok': ok, 'fail': fail})
PY
```

## 3) Przykład migracji (old -> v4)

### Wejście (stara forma)

```oql
GOAL: Ciśnienie otwarcia zaworu wydechowego: 4.2 – 6.0 mbar
  SET 'Pump' 'set'
  SET 'Valve' 'NC'
  WAIT '1000 ms'
  MIN 'AI01' '4.2 mbar'
  SAVE 'AI01.min'
```

### Wyjście (VERSION: 4)

```oql
VERSION: 4
GOAL:
  SET NAME 'Ciśnienie otwarcia zaworu wydechowego: 4.2 – 6.0 mbar'
  SET 'Pump' 'set'
  SET 'Valve' 'NC'
  WAIT 1000ms
  MIN 'AI01' '4.2 mbar'
  SAVE 'AI01.min'
```

## 4) Kontrakt dla LLM (operacyjny)

LLM powinien produkować:

```json
{
  "input_source": "url|file",
  "input_reference": "...",
  "report_before": {"...": "validator report"},
  "changes": [
    {"rule": "version_present", "action": "set VERSION: 4"},
    {"rule": "goal_inline_name", "action": "split GOAL + SET NAME"}
  ],
  "report_after": {"...": "validator report"},
  "valid": true
}
```

## 5) Uwagi implementacyjne

- Walidator (`scripts/oql_v4_validator.py`) uruchamia:
  1. walidację reguł strukturalnych,
  2. test runtime (`CqlInterpreter`, `dry-run`).
- Jeśli `valid=false`, LLM nie powinien kończyć procesu bez poprawek.
- Przy pracy masowej: walidować każdy plik osobno i raportować listę błędów.

## 6) V2 -> V4 (legacy) — przykład `ts-temp-wilgotnosc`

### Wejście (legacy v2)

```oql
GOAL: Pomiar warunków środowiskowych
  TASK: [Włącz] [czujnik temperatury]
  TASK: [Włącz] [czujnik wilgotności]
  WAIT [3 s]
  SAMPLE [temperatura] [START] [500 ms]
  SAMPLE [wilgotność] [START] [500 ms]
  WAIT [30 s]
  SAMPLE [temperatura] [STOP]
  SAMPLE [wilgotność] [STOP]
  CALC [temp_avg] = [AVG] [temperatura]
  CALC [wilg_avg] = [AVG] [wilgotność]
  VAL [temp_avg] [°C]
  VAL [wilg_avg] [%RH]
  MIN [temp_avg] = [15 °C]
  MAX [temp_avg] = [35 °C]
  MIN [wilg_avg] = [30 %RH]
  MAX [wilg_avg] = [70 %RH]
  IF [temp_avg] [<] [15]
  ELSE ERROR ["Temperatura poniżej minimum"]
  IF [temp_avg] [>] [35]
  ELSE ERROR ["Temperatura powyżej maksimum"]
  TASK: [Zapisz] [warunki] [protokół]
```

### Jak walidować legacy v2

```bash
python3 scripts/oql_v2_validator.py \
  --url "http://localhost:8096/scenarios?scenario=ts-temp-wilgotnosc" \
  --pretty
```

Schemat raportu v2:
- `docs/oql_v2_llm_validator.schema.json`

### Jak migrować i aktualizować rekordy DB do v4

Najpierw uruchom podgląd (`dry-run`, bez zapisu):

```bash
python3 scripts/oql_v2_to_v4_migrate_db.py \
  --source-url "http://localhost:8100/connect-data/test-scenarios" \
  --scenario "ts-temp-wilgotnosc" \
  --prefer-local \
  --pretty
```

Następnie wykonaj zapis do backendu danych (przykładowy endpoint):

```bash
python3 scripts/oql_v2_to_v4_migrate_db.py \
  --source-url "http://localhost:8100/connect-data/test-scenarios" \
  --scenario "ts-temp-wilgotnosc" \
  --prefer-local \
  --apply \
  --write-method PATCH \
  --write-url "http://localhost:8101/api/v1/data/test_scenarios/{id}" \
  --pretty
```

Po migracji uruchom walidację v4:

```bash
python3 scripts/oql_v4_validator.py \
  --url "http://localhost:8096/scenarios?scenario=ts-temp-wilgotnosc" \
  --pretty
```
