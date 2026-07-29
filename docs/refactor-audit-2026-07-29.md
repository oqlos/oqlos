# Audyt długu refaktoryzacyjnego — 2026-07-29

Ten dokument jest snapshotem pomiarów dla `NEXT-02`. Bieżąca kolejność prac
pozostaje w [kanonicznej roadmapie](refactor-roadmap.md), a pełna lista trafień
OqlOS znajduje się w maszynowym
[`project/refactor-audit.json`](../project/refactor-audit.json).

## Zakres i odtwarzalność

| Repozytorium | Commit | Stan źródeł | Generator |
| --- | --- | --- | --- |
| OqlOS | `86935a0c8adc33a02d4d943d1702f05bdcd2c7ec` | czysty po pominięciu generowanych artefaktów | `code2llm 0.5.168` + `scripts/refactor_audit.py` |
| C2004 | `4af234f6acd9be2523da5c75326c58035b62fa2c` | czysty detached clone z przypiętymi submodułami | `code2llm 0.5.168` + ten sam audyt AST |

Pomiar wykonano 2026-07-29. Robocze repo C2004 zawierało cudze, niezwiązane
zmiany, dlatego nie zostało zmodyfikowane. Analizę wykonano w lokalnym klonie
`--shared`, odłączonym dokładnie na wskazanym commicie, z jego wersjami
submodułów. Katalogi zależności i kopii (`extern`, `vendor`, `node_modules`,
virtualenv, `site-packages`), testy, wygenerowany `project/`, pliki minifikowane
i symlinki są wyłączone z audytu AST.

Kanoniczna komenda OqlOS to:

```bash
task analysis:refresh
# równoważnie: bash scripts/generate-refactor-analysis.sh
```

Job `static-analysis` w GitHub Actions uruchamia tę samą komendę z przypiętym
`code2llm==0.5.168`, sprawdza commit, czystość źródeł, sumy artefaktów i brak
błędów parsowania. Dla czystego checkoutu C2004 użyto:

```bash
code2llm . -m hybrid -f toon,map --strategy standard --toon-yaml \
  --no-png --no-cache --no-chunk -o generated-analysis
python /home/tom/github/oqlos/oqlos/scripts/refactor_audit.py \
  --root . --output refactor-audit.json
```

## Wyniki

| Metryka statyczna | OqlOS | C2004 |
| --- | ---: | ---: |
| Pliki źródłowe audytu AST | 396 | 2 869 |
| Publiczne trasy FastAPI | 194 | 668 |
| Trasy zwracające `dict[str, Any]` | 80 | 186 |
| Kandydaci na generyczną odpowiedź OpenAPI | 184 | 438 |
| `ok=false`/`success=false` możliwe przy HTTP 200 | 3 | 15 |
| Odczyty env poza rozpoznaną warstwą settings | 154 | 317 |
| Surowe `HTTPException`/`ValueError`/`RuntimeError` | 137 | 626 |
| Szerokie `except Exception`/`BaseException`/bare | 242 | 937 |
| Moduły mające co najmniej 400 linii | 30 | 158 |
| Błędy parsowania Pythona | 0 | 0 |

`code2llm` policzył dla OqlOS 517 plików i 80 355 linii, 3 373 funkcje,
średnią złożoność 3,8 oraz 48 funkcji krytycznych. Dla C2004: 5 657 plików,
824 346 linii, 32 683 funkcje, średnią 3,6, 719 funkcji krytycznych i jedną
potencjalną duplikację.

### Najpilniejsze naruszenia kontraktu HTTP

W OqlOS trzy trasy mogą zwrócić negatywny envelope bez jawnego statusu błędu:

- `POST /cqrs/command` — `oqlos/api/_hw3_cqrs.py:29`;
- `POST /diagnostic-command` — `oqlos/api/_hw3_peripheral.py:167`;
- `POST /modbus/wizard/program-isolated` —
  `oqlos/api/hardware_modbus_routes.py:193`.

W C2004 wykryto 15 kandydatów. Skupiają się w konfiguracji sieci, endpointach
kiosku i synchronizacji, safe-state firmware oraz odczytach sesji/template.
Lista obejmuje między innymi `POST /test-network`, operacje `/sync/*`,
`POST /api/v1/hardware/safe-state` i odczyty `/sessions/{session_id}`.

### Weryfikacja kandydatów OqlOS po baseline

Przegląd dynamiczny 2026-07-29 wykazał, że trzy trafienia OqlOS były
fałszywymi alarmami pierwotnej heurystyki: słownik `ok=false` służył do zapisu
zdarzenia lub normalizacji wyniku, po czym trasa rzucała `OqlosError`.
Dodane testy HTTP potwierdzają odpowiednio 422/`C2004-DATA-0002` oraz
503/`C2004-HW-0012`, `application/problem+json`, zachowany `correlation_id` i
brak surowego komunikatu upstream/tracebacka.

Audyt AST sprawdza teraz wyłącznie literalny negatywny słownik w instrukcji
`return`, dzięki czemu nie klasyfikuje wewnętrznych zdarzeń jako odpowiedzi
HTTP. Bieżący wynik OqlOS dla tej metryki wynosi 0. Tabela powyżej pozostaje
niezmienionym snapshotem NEXT-02; różnica jest udokumentowanym wynikiem
pierwszej partii NEXT-04, a nie retroaktywną zmianą pomiaru bazowego.

Następna partia NEXT-04 ustandaryzowała błędy komend HUI, artificial-lung i
systemd. Usunięto pięć surowych `HTTPException`, więc bieżący pomiar OqlOS
wynosi 132 wobec 137 w snapshotcie. Dodatkowo operacyjny błąd sterowania
systemd, wcześniej zwracany jako zmienna `ok=false` przy HTTP 200, daje teraz
503/`C2004-HW-0012`; ta poprawka nie wpływa na metrykę literalnych słowników,
ale jest objęta testem dynamicznym problem details.

### Hotspoty rozmiaru

Największe pliki OqlOS to słownik tłumaczeń (2 150 linii), `Panel.jsx`
(1 519), parser OQL (1 420), gateway pluginów (963), akcje interpretera (933),
główny interpreter (778), adapter OQL (744), `oqlos/api/main.py` (684) oraz
Waveshare Modbus (656).

W C2004 największe są widoki connect-menu i connect-test-device (1 761 i
1 713), `Scenarios.jsx` (1 694), konfigurator sitemap/menu (1 644), parser
OQL TypeScript (1 441), inicjalizator frontendu (1 250) i runtime scenariusza
(1 201).

## Wnioski dla backlogu

1. `NEXT-03` pozostaje pierwszym zadaniem wykonawczym: safety gate ma wpływ na
   fizyczną aktuację i nie może czekać na pełne porządkowanie kontraktów.
2. Pierwsza partia `NEXT-04` potwierdziła typowane błędy trzech tras OqlOS i
   usunęła ich fałszywe alarmy z audytu. Dalszy zakres to 137 surowych wyjątków,
   241 szerokich handlerów, 80 tras `dict[str, Any]` dla `NEXT-05` oraz 15
   kandydatów C2004 wymagających osobnej weryfikacji.
3. `NEXT-07` powinno wprowadzić allowlistę settings i blokować nowe odczyty env;
   154/317 trafień to inwentarz migracji, nie założenie, że każde jest błędem.
4. Podział dużych modułów należy prowadzić po odpowiedzialnościach i pokryciu
   testami. Sama liczba linii nie uzasadnia mechanicznego rozcinania słowników
   ani kodu generowanego.
5. Wysoka liczba szerokich handlerów wymaga klasyfikacji w `NEXT-04`; nie wolno
   usuwać handlera bez sprawdzenia granicy procesu, retry i cleanup.

## Ograniczenia pomiaru

- Audyt jest konserwatywną analizą AST i wzorców tekstowych. Trafienie oznacza
  kandydata do przeglądu, nie potwierdzony defekt.
- „Generyczna odpowiedź” obejmuje trasę bez `response_model`, jeśli typ zwrotny
  jest nieobecny lub słownikowy; FastAPI może część schematu wywnioskować
  dynamicznie.
- Odczyt env w pliku nierozpoznanym jako settings może być zamierzonym adapterem;
  docelowy rejestr `NEXT-07` rozstrzygnie wyjątki.
- `code2llm` stosuje heurystyki dla JavaScript/TypeScript. Jego wyniki służą do
  trendów i hotspotów, natomiast liczby kontraktów pochodzą z audytu AST.
- C2004 zostało zmierzone bez `extern`, więc osadzona kopia OqlOS nie zawyża
  wyniku C2004. Snapshot C2004 ma sumy SHA-256:
  `e55daa120e4f43191b928992bf5e4f11011d4ef07b8d2a547c8b26dfbe9696bd`
  (JSON), `db7b4b51669df4724f98a829a7eb1daf9058c2f2c9b374a847474845f0f93342`
  (analysis) i `f11aa7896e8a037b3ce32faa5fd834f970c7fb47b8928d6115eb9e4a2ad54276`
  (mapa).
