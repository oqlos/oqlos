# OqlOS — lista zadań

Stan: **2026-07-30**, bazowy `main` `a8059de`, z kolejną partią `NEXT-04`.

Ten plik jest operacyjną checklistą. Szczegółowe uzasadnienie, zależności i
kryteria ukończenia znajdują się w
[kanonicznym roadmapie](docs/refactor-roadmap.md). Po każdym zamkniętym pakiecie
należy zaktualizować oba dokumenty oraz dołączyć wynik testów i commit.

## Bieżące metryki

- 194 publiczne trasy API;
- 83 surowe wyjątki;
- 228 szerokich handlerów `except` (w tym jawne granice storage i adapterów);
- 80 tras zwracających `dict[str, Any]`;
- 182 trasy z generyczną odpowiedzią OpenAPI;
- 154 odczyty zmiennych środowiskowych poza typowaną warstwą settings;
- 30 dużych modułów;
- 0 literalnych negatywnych odpowiedzi przy HTTP 200;
- 0 błędów parsowania w audycie statycznym.

## P0 — błędy SOA, POA i firmware (`NEXT-04`)

### Publiczne granice API

- [x] Sklasyfikować wskazane surowe wyjątki w `execution.py`,
  `hardware_modbus_wizard.py`, `ui_prefs_store.py` i `execution_ctrl.py`.
- [x] Zastąpić surowe `HTTPException` w współdzielonych granicach:
  - `oqlos/shared/_endpoint_helpers.py`;
  - `packages/backend-shared-py/src/shared/cqrs/fastapi_integration.py`;
  - `packages/backend-shared-py/src/shared/cqrs/http_relay.py`;
  - `packages/backend-shared-py/src/shared/module_app_factory.py`;
  - `packages/backend-shared-py/src/shared/sensors_endpoint.py`.

Dowód: współdzielony `SharedHttpError` wiąże status z kodem C2004, ownerem,
retryability i remediation, zachowuje bezpieczny `correlation_id` oraz publikuje
RFC 9457 po instalacji handlera. CQRS, inbox, pliki modułu i sensory mają 9
testów kontraktowych w pakiecie, a lokalny helper OqlOS osobny test 404.
Audyt po partii: 83 surowe wyjątki (spadek o 10), 0 błędów parsowania i 0
negatywnych envelope przy HTTP 200.
- [ ] Przejrzeć i sklasyfikować szerokie handlery w kolejności:
  1. [x] `_hw3_peripheral.py`, `state.py`, `scenarios.py`;
  2. [ ] `hardware_modbus_waveshare.py`;
  3. [ ] `hardware_runtime.py`, `hardware_modbus_routes.py`,
     `hardware_modbus_settings.py`, `hardware_probe.py`, `hardware_lung.py`;
  4. [ ] `plugins.py`, `update_status.py`.

Dowód grupy 1: oczekiwane błędy HTTP/JSON i parsera mają wąskie handlery;
awaria programistyczna przechodzi do sanitizowanej granicy 500. Cztery
pozostawione szerokie handlery są jawnie opisanymi granicami adaptera,
loadera zależności i zadania w tle. Failover statusu oraz zdarzenie błędu
diagnostycznego nie publikują wyjątku, argumentów ani sekretów. Metryka
szerokich handlerów spadła 237 → 228; `state.py` ma 352 linie, a
`_hw3_peripheral.py` spadł z CC=17 do CC=8.
- [ ] Dla każdego przewidywalnego błędu ustalić:
  - lokalny `issue_code` i publiczny `C2004-*`;
  - właściwy HTTP status, severity, retryability i ownera;
  - `architecture`, `layer`, `component`, `stage`, `problem_source` oraz
    `operation_id`;
  - bezpieczny `upstream_target` bez hosta, sekretów i danych dostępowych;
  - remediation i warunki automatycznej naprawy.
- [ ] Dodać test kontraktowy dla każdego zmienionego przypadku:
  - prawidłowy status i `C2004-*`;
  - zachowany `correlation_id`;
  - brak tracebacku, sekretów, pełnego payloadu i surowego HTML;
  - odrzucona komenda nie dociera do adaptera;
  - pojedyncza porażka nie wraca jako HTTP 200.

### Runtime, pluginy i wspólne pakiety

- [ ] Rozdzielić błędy hosta, proxy, pluginu, urządzenia i timeoutu w:
  - `oqlos/hardware/plugin_gateway.py`;
  - `oqlos/hardware/gateway.py`;
  - `oqlos/hardware/transport/mqtt_oql_bridge.py`;
  - `oqlos/hardware/firmware_adapter.py`;
  - `oqlos/hardware/plugins/registry.py`;
  - pluginach `lung`, `modbus`, `modbus_adc` i `piadc`.
- [ ] Oznaczyć szerokie handlery, które są celowymi granicami adaptera, i
  udowodnić testem, że publikują wyłącznie bezpieczny kontekst.
- [ ] Rozdzielić oczekiwane walidacyjne `ValueError` od awarii wykonania w:
  - `packages/oqlos-core/src/oqlos/core/oql_parser.py`;
  - `oqlos/hardware/configuration_models.py`;
  - `oqlos/core/executor.py`;
  - `packages/oqlos-core/src/oqlos/core/_action_motor2.py`.
- [ ] Wykonać analogiczny audyt i testy kontraktowe po stronie C2004/POA.
- [ ] Zapewnić ten sam kod błędu dla tego samego przypadku w SOA, POA i
  firmware.

## P0 — typowane API i OpenAPI (`NEXT-05`)

- [ ] Zastąpić 80 zwrotów `dict[str, Any]` ścisłymi modelami odpowiedzi.
- [ ] Nadać każdej publicznej trasie jawny model sukcesu i problem response.
- [ ] Zmniejszyć 184 generyczne odpowiedzi wykrywane w OpenAPI do zera.
- [ ] Dla komend aktuacyjnych stosować `StrictBool`, enumy, zakresy, jawne
  jednostki oraz `extra="forbid"`.
- [ ] Ujednolicić envelope sukcesu na `ok`; nie dodawać nowych pól `success`.
- [ ] Oznaczyć aliasy v1/v3 jako deprecated i przetestować wygenerowane
  OpenAPI.
- [ ] Realizować migrację w kolejności:
  1. Modbus wizard;
  2. coils i HUI;
  3. motory;
  4. RTC;
  5. runtime control.

## P0 — jedno źródło scenariuszy i OQL v5 (`NEXT-06`)

- [ ] Przenieść wszystkie aktywne scenariusze do repozytorium `oql-scenario`.
- [ ] Dodać kontrolę CI blokującą aktywne pliki `.oql` poza kanonicznym
  magazynem.
- [ ] Utrzymywać wspólny corpus TypeScript/Python z identycznym AST,
  diagnostyką i planem wykonania.
- [ ] Generować HELP i kolorowanie edytora z jednej tabeli składni.
- [ ] Zmigrować `test-cql-nowy-scenariusz.oql` i manifest, zachowując czasowy
  alias starego identyfikatora.
- [ ] Zinwentaryzować konsumentów przed zmianą wewnętrznych ścieżek `cql_*` na
  OQL.
- [ ] Usunąć aliasy `Cql*`, `parse_cql` i stare formy gramatyki dopiero po
  okresie telemetrycznym bez użycia.
- [ ] Dodać jawną diagnostykę cyklicznego `INCLUDE`; obecny `seen` zapobiega
  rekurencji, ale cykl jest pomijany bez czytelnego błędu.
- [ ] Rozszerzyć `CHECK` o strukturalny wynik: wartość oczekiwana, rzeczywista,
  operator, jednostka i lokalizacja w scenariuszu.

## P1 — konfiguracja i rejestr środowiska (`NEXT-07`)

- [ ] Utworzyć kanoniczny rejestr wszystkich `OQLOS_*`.
- [ ] Dla każdej zmiennej zapisać typ, default, jednostkę, scope, ownera,
  informację o sekrecie, alias i termin usunięcia.
- [ ] Zablokować nowe bezpośrednie `os.getenv()` poza typowaną warstwą
  settings.
- [ ] Zmniejszyć 154 odczyty env poza settings do zera lub jawnej allowlisty.
- [ ] Utrzymać jeden model `hardware-configuration-v1` i równoważne kodeki
  OQL/YAML/JSON.
- [ ] Dodać round-trip wszystkich formatów i lint całego grafu konfiguracji.
- [ ] Oddzielić sekrety i ustawienia hosta od logicznej konfiguracji
  scenariusza.

## P1 — command trace i łączność (`NEXT-08`, `NEXT-09`)

- [ ] Ujednolicić `COMMAND`, args, `RESULT`, `HTTP_STATUS` i `ERRORS` dla HUI,
  motorów, RTC i Modbus.
- [ ] Dodać `REQUEST_ID`, `CORRELATION_ID`, start, finish i czas wykonania.
- [ ] Stosować whitelistę argumentów URL; nigdy nie zapisywać sekretów ani
  pełnych payloadów.
- [ ] Zapewnić poprawną walidację origin dla `postMessage` iframe.
- [ ] Zagwarantować, że reload pozostaje read-only i nie ponawia komendy.
- [ ] Uruchomić watcher BoardNet → DisplayNet niezależny od UI.
- [ ] Ujednolicić stany `up/degraded/down/unknown`, timestamp, sequence i
  correlation id.
- [ ] Dodać ograniczony JSONL/ring buffer, `pending_replication`, backoff,
  deduplikację oraz batch flush maksymalnie 50 zdarzeń.
- [ ] Przetestować kontrolowany outage i odtworzenie timeline bez duplikatów.

## P2 — wydajność i utrzymanie (`NEXT-10`)

- [ ] Oddzielić szybki cached sensor read od pełnego probe sprzętu.
- [ ] Zapewnić single-flight, backoff oraz anulowanie polli po zamknięciu
  widoku.
- [ ] Publikować `observed_at`, `age_ms`, `stale` i źródło próbki.
- [ ] Dodać metryki p50/p95/p99 oraz 30-minutowy soak.
- [ ] Utrzymać budżety:
  - `/health` p95 poniżej 100 ms;
  - hardware health p95 poniżej 500 ms;
  - cached sensor read p95 poniżej 500 ms.
- [ ] Podzielić główny frontendowy chunk większy niż 500 kB przez lazy
  loading.
- [ ] Rozbić duże moduły, zaczynając od `plugin_gateway.py`, gateway sprzętu,
  bridge MQTT i `_oql_adapter.py`.
- [ ] Dodać `pytest-cov`, `.coveragerc` oraz raport coverage w CI.
- [ ] Zbudować hardware mock server dla testów TestQL bez fizycznego urządzenia.

## P1/P2 — deploy i fizyczna walidacja (`NEXT-11`, `NEXT-12`)

- [ ] Budować `.122` i `.109` z clean checkout oraz przypiętych commitów.
- [ ] Zapisywać commity OqlOS/OQL Scenario, wersję schema i checksumy w
  `CURRENT_STATE`.
- [ ] Uruchamiać migracje przed restartem i przechowywać pin poprzedniej
  wersji do rollbacku.
- [ ] Wykonać osobne read-only smoke dla:
  - `.122:8202`;
  - `.109`;
  - proxy `/firmware`;
  - OQL API i WebSocket;
  - health, readiness oraz diagnostyki.
- [ ] Nie uznawać 502/503 BoardNet za sukces i nie uruchamiać wtedy aktuacji.
- [ ] Zweryfikować na BoardNet zasilanie Pi i 12 V pola oraz flagi
  undervoltage.
- [ ] Potwierdzić RS485, baud/parity/slave i stabilny `/dev/serial/by-id`.
- [ ] Po zgodzie operatora wykonać kontrolowany test DO1–DO8: jedna cewka,
  krótki impuls i automatyczne OFF.
- [ ] Potwierdzić mapowanie zaworów, pompę DRI0050, Tic249 i krańcówki.
- [ ] Zapisać raport z czasem, operatorem, commitem, wynikiem i kodami błędów.

## P2 — dokumentacja operatorska (`NEXT-13`)

- [ ] Generować HELP wszystkich kodów błędów bezpośrednio z katalogu.
- [ ] Dodać filtrowanie i wydruk wybranego zakresu wraz z remediation.
- [ ] Opisać przepływ SOA → POA → firmware i `correlation_id` jednym
  diagramem.
- [ ] Udokumentować ustawienia i limity Tic249 bez duplikowania wartości w
  scenariuszach.
- [ ] Aktualizować runbook `.122/.109` i procedurę awarii proxy/BoardNet.

## Testy integracyjne TestQL

- [ ] Uruchomić przy działającym OqlOS:
  `testql run testql-scenarios/generated-api-smoke.testql.toon.yaml`.
- [ ] Uruchomić:
  `testql run testql-scenarios/generated-from-scenarios.testql.toon.yaml`.
- [ ] Uruchomić:
  `testql run testql-scenarios/cross-project-integration.testql.toon.yaml`.
- [ ] Zapisać commit serwera, target, czas i wynik każdego przebiegu.

## Definition of done każdego pakietu

- [ ] Test pozytywny, negatywny i regresyjny przechodzi.
- [ ] `pytest -q` przechodzi lokalnie i w CI.
- [ ] Ruff `F821,F811` oraz lint zmienionych plików przechodzą.
- [ ] Dokumentacja, OpenAPI i `oqlos/_CHECKSUMS.sha256` są aktualne.
- [ ] Błąd ma prawidłowy kod, HTTP status, ownera i remediation.
- [ ] Odpowiedź i log nie zawierają sekretów, tracebacków ani pełnych
  payloadów.
- [ ] Zmiana ma rollback i dowód weryfikacji.
- [ ] Commit został wypchnięty bezpośrednio do `main`; bez brancha i bez PR.

## Obowiązkowe komendy kontrolne

```bash
pytest -q
pytest -q tests/test_oql_public_runtime_api.py
ruff check oqlos tests packages/oqlos-core packages/oqlos-models --select F821,F811
task analysis:refresh
cd frontend && npm run test:unit && npm run build
```

Dla `oql-scenario`:

```bash
cd /home/tom/github/oqlos/oql-scenario
pytest -q
find . -type f -name '*.cql'
rg -ni 'cql' --glob '!archive/**'
```
