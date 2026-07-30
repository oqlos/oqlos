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

Kolejny test dynamiczny wykrył negatywny envelope zwracany przez zmienną w
`/api/v1/editor/execute`, którego konserwatywna metryka literalnego `return`
nie obejmuje. Zdalny błąd edytora korzysta teraz ze wspólnego kontraktu MQTT i
nie zwraca HTTP 200. Nieotypowane HTTP 5xx zostały jednocześnie objęte centralną
sanityzacją, dzięki czemu surowe wyjątki starszych tras nie trafiają do body.

Druga grupa przeglądu szerokich handlerów `NEXT-04` sklasyfikowała wszystkie
sześć trafień w `hardware_modbus_waveshare.py`. Granice importu, transportu,
odczytu konfiguracji i cleanup nie łapią już dowolnego `Exception`; oczekiwane
awarie mają stabilny kod i powód, a defekty programu trafiają do centralnej
granicy 500. Raport diagnostyczny nie kopiuje komunikatów wyjątku ani plugin
health i jawnie publikuje `overall_status`. Bieżąca metryka OqlOS spadła z 228
do 222 szerokich handlerów, a moduł Waveshare z 656 do 640 linii bez wzrostu
maksymalnej złożoności CC=11.

Trzecia grupa przeglądu `NEXT-04` sklasyfikowała wszystkie sześć trafień w
`hardware_runtime.py`, `hardware_modbus_routes.py`,
`hardware_modbus_settings.py`, `hardware_probe.py` i `hardware_lung.py`.
Przewidywalne awarie I/O/runtime nie publikują tekstu wyjątku, a defekty
programu nie są maskowane jako problem sprzętowy. Programowanie Modbus zawsze
wznawia pluginy, a błąd rozszerzonego adaptera płuca nie powtarza aktuacji.
Bieżąca metryka spadła z 222 do 216 szerokich handlerów; Modbus routes ma
CC=14 zamiast 18, a lung CC=8 zamiast 10.

Czwarta grupa przeglądu usunęła po jednym szerokim handlerze z
`plugins.py` i `update_status.py`. API pluginów nie ufa już statusowi,
komunikatowi ani `correlation_id` zwróconym przez adapter: normalizuje znany kod
do katalogowego HTTP i problem details, a surowy wynik oraz parametry komendy
nie trafiają do odpowiedzi. Sondy statusu aktualizacji łapią tylko oczekiwane
błędy HTTP/JSON, zwracają stabilny kod diagnostyczny bez URL i tekstu wyjątku,
a self-probe ignoruje nagłówek `Host`. Błędy programu pozostają widoczne dla
centralnej sanitizowanej granicy 500. Zregenerowany snapshot workspace wskazuje
214 szerokich handlerów, 83 surowe wyjątki, 0 negatywnych envelope przy HTTP
200 i 0 błędów parsowania.

Piąta grupa przeglądu usunęła sześć szerokich handlerów z
`hardware_peripherals_routes.py`, `scenarios.py`, `ui_prefs_routes.py` i
`ui_prefs_store.py`. Błędy transportu/runtime Modbus ADC, brak parsera oraz
błędy pliku, kodowania i JSON/YAML nadal mają stabilny kontrakt domenowy.
Nieoczekiwany `AttributeError` nie jest już maskowany jako awaria sprzętu,
parsera albo magazynu, lecz trafia do centralnego 500 bez komunikatu wyjątku.
Odpowiedź sukcesu preferencji nie ujawnia ścieżki serwera. Snapshot wskazuje
208 szerokich handlerów, 83 surowe wyjątki, 0 negatywnych envelope przy HTTP
200 i 0 błędów parsowania; bramka to 1059 testów backendowych oraz 149
frontendowych, build Vite i Ruff.

Szósta grupa przeglądu usunęła wszystkie 13 szerokich handlerów z
`plugin_gateway.py`. Inicjalizacja, reconnect, readiness, komendy aktuatorów i
reload konfiguracji łapią wyłącznie oczekiwane błędy konfiguracji, transportu i
runtime. Zwracane wyniki mają stabilne powody, nie kopiują komunikatu wyjątku,
surowego health, surowego powodu init ani negatywnego body pluginu, a zewnętrzny
kod C2004 musi istnieć w katalogu. `AttributeError` przechodzi do nadrzędnej
granicy zamiast udawać niedostępny sprzęt. Wspólna normalizacja i bezpieczne
logowanie są w małym `plugin_gateway_boundary.py`, bez nowego hotspotu.
Snapshot wskazuje 195 szerokich handlerów, 83 surowe wyjątki i 0 błędów
parsowania; bramka to 1072 testy backendowe, 149 frontendowych, build Vite i
Ruff.

Siódma grupa przeglądu objęła `mqtt_oql_bridge.py` oraz `mqtt_protocol.py`.
Pięć przewidywalnych handlerów bridge'u i szeroki import guard protokołu
zastąpiono jawnymi błędami JSON/envelope oraz sieciowego cleanup. Envelope
odrzuca nieobsługiwaną wersję, a defekt parsera pozostaje widoczny zamiast być
uznany za błędne dane. Dwie szerokie granice wykonania agenta pozostają celowo:
chronią pętlę przed awarią komendy/pluginu, lecz publikują tylko katalogowy
komunikat C2004, korelację i typ wyjątku. Test potwierdza brak surowego
komunikatu, ścieżki, sekretu i tracebacku także w logu. Snapshot wskazuje 189
szerokich handlerów, 83 surowe wyjątki i 0 błędów parsowania; bramka to 1080
testów backendowych, 149 frontendowych, build Vite, Ruff i `uv lock --check`.

Ósma grupa przeglądu objęła `firmware_adapter.py`. Sześć szerokich handlerów
zastąpiono jawnymi błędami transportu, zależności, payloadu i odrzucenia
komendy. Oczekiwana awaria publikuje wyłącznie stabilny envelope
503/`C2004-HW-0012`; testy potwierdzają brak komunikatu upstream, ścieżki i
sekretu w wyniku oraz logu, a także przepuszczenie defektu programu do
sanitizowanej granicy 500. Snapshot wskazuje 183 szerokie handlery, 81
surowych wyjątków i 0 błędów parsowania. Polityka granicy jest w osobnym
module 103-liniowym, a adapter ma 511 linii zamiast przejściowych 607. Bramka
to 1090 testów backendowych, 149 frontendowych, build Vite, Ruff i
`uv lock --check`.

Dziewiąta grupa przeglądu objęła `plugins/registry.py`. Trzy surowe wyjątki
lookup/walidacji zastąpiono typowanymi błędami, a trzy handlery lifecycle
zawężono do oczekiwanych błędów zależności, I/O, HTTP, runtime i walidacji.
Defekt programu przechodzi do bezpiecznej granicy 500. Jedyny szeroki handler
pozostaje celową izolacją importu kodu zewnętrznego entry pointu i publikuje w
logu wyłącznie typ wyjątku. Health ma stabilny komunikat i nie kopiuje sekretu,
ścieżki ani tekstu wyjątku. Snapshot wskazuje 180 szerokich handlerów, 78
surowych wyjątków i 0 błędów parsowania; bramka to 1098 testów backendowych,
149 frontendowych, build Vite, Ruff i `uv lock --check`.

Dziesiąta grupa przeglądu objęła `plugins/lung.py` i współdzielony dekoder
odpowiedzi pluginów HTTP. Siedem szerokich handlerów zastąpiono oczekiwanymi
błędami transportu, runtime i payloadu. Connect, health oraz komendy zwracają
stabilne, katalogowe wyniki bez tekstu wyjątku, ścieżki, sekretu i wejściowej
komendy. Błędny JSON statusu runtime blokuje ruch, a `AttributeError` nie jest
maskowany jako awaria urządzenia. Snapshot wskazuje 173 szerokie handlery, 78
surowych wyjątków, 30 dużych modułów i 0 błędów parsowania; `lung.py` ma 395
linii. Bramka to 1107 testów backendowych, 149 frontendowych, build Vite, Ruff
i `uv lock --check`.

### Przegląd istniejących logów wykonawczych

Logi w `iql-run-logs/` i `oql-run-logs/` pochodzą z 2026-04-15, więc nie są
telemetrią bieżących usług. W 137 logach IQL jest 129 plików z zielonym
podsumowaniem oraz 6 z porażką. Porażki dotyczą health/auth/CRUD uruchomionych
w `dry-run`: asercje otrzymały pusty status, brak tokenu albo pustą kolekcję;
nie potwierdzają awarii live targetu. Dwa inne przebiegi były zielone jako
`0/0`, co wymaga nowej blokady bramki. 128 logów OQL nie zawiera `ERROR`,
tracebacku ani znacznika porażki. Backlog `NEXT-10` obejmuje deterministyczny
mock/live acceptance oraz odrzucanie suite bez wykonanych kroków.

Logi `.redeploy/logs/` z 2026-07-27 potwierdzają cztery kolejne ukończone
przebiegi 25/25. Próby z 2026-07-28 zatrzymały się na checkpointach 20/25 lub
22/25 z powodu timeoutu SSH, `Broken pipe`, braku trasy do hosta albo błędu DNS
przy dostępie do piwheels. Jest to zgodne z `redeploy/122/CURRENT_STATE.md`:
nie należy uruchamiać aktuacji ani ponawiać migracji przed stabilizacją
zasilania/LAN; potem trzeba wznowić zachowany checkpoint i wykonać bramki
23–25.

### Hotspoty rozmiaru

Największe pliki OqlOS to słownik tłumaczeń (2 150 linii), `Panel.jsx`
(1 519), parser OQL (1 420), gateway pluginów (1 007), akcje interpretera (933),
główny interpreter (778), adapter OQL (744), `oqlos/api/main.py` (684) oraz
Waveshare Modbus (640).

W C2004 największe są widoki connect-menu i connect-test-device (1 761 i
1 713), `Scenarios.jsx` (1 694), konfigurator sitemap/menu (1 644), parser
OQL TypeScript (1 441), inicjalizator frontendu (1 250) i runtime scenariusza
(1 201).

## Wnioski dla backlogu

1. Implementacja `NEXT-03` jest zakończona; przed wdrożeniem nadal wymaga
   fizycznej walidacji zasilania i bezpiecznej aktuacji w `NEXT-12`.
2. Dziesięć grup `NEXT-04` zmniejszyło bieżący zakres OqlOS do 78 surowych
   wyjątków i 173 szerokich handlerów. Następne aktywne hotspoty to pluginy
   `modbus`, `modbus_adc` i `piadc`; legacy `gateway.py`
   wymaga najpierw audytu konsumentów i planu deprecjacji.
3. `NEXT-07` powinno wprowadzić allowlistę settings i blokować nowe odczyty env;
   154/317 trafień to inwentarz migracji, nie założenie, że każde jest błędem.
4. Podział dużych modułów należy prowadzić po odpowiedzialnościach i pokryciu
   testami. Sama liczba linii nie uzasadnia mechanicznego rozcinania słowników
   ani kodu generowanego.
5. Wysoka liczba szerokich handlerów wymaga klasyfikacji w `NEXT-04`; nie wolno
   usuwać handlera bez sprawdzenia granicy procesu, retry i cleanup.
6. Historyczny `dry-run` nie jest dowodem akceptacji live. Bramka musi odrzucać
   `0/0`, a testy zależne od danych powinny używać deterministycznego mocka albo
   jawnie wskazanego targetu i fixture.

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
