# Standard błędów i diagnostyki OqlOS/C2004

Stan zweryfikowany: 2026-07-29.

## Dwa poziomy identyfikatorów

Każdy błąd wystawiany przez HTTP ma dwa stabilne poziomy:

1. Publiczny kod systemowy `C2004-*`, używany przez UI, logi, alerty i
   integracje między DisplayNet i BoardNet.
2. Dokładny `issue_code` OqlOS, używany w diagnostyce urządzenia i runbookach.

Przykład:

```json
{
  "type": "http://localhost/api/v3/errors/catalog/C2004-DATA-0002",
  "status": 422,
  "code": "C2004-DATA-0002",
  "error_code": "C2004-DATA-0002",
  "detail": "current_device_id must be an integer",
  "correlation_id": "cor-...",
  "metadata": {
    "context": {
      "field": "current_device_id",
      "value": "not-an-integer",
      "expected": "integer"
    },
    "diagnostics": {
      "issue_code": "api_modbus_wizard_invalid_request"
    }
  }
}
```

Publiczna odpowiedź ma format `application/problem+json` zgodny z RFC 9457.
Nie wolno umieszczać w niej tracebacków, sekretów, pełnych zmiennych
środowiskowych ani danych uwierzytelniających. Szczegóły techniczne trafiają do
logu serwera pod tym samym `correlation_id`.

Źródła prawdy:

- publiczny katalog i mapowanie: generowane artefakty C2004,
- lokalne definicje OqlOS: `oqlos/errors/catalog.py`,
- wygenerowany snapshot: `oqlos/errors/c2004_catalog_generated.py`,
- lokalne opisy issue: [ERROR_CODES.md](ERROR_CODES.md).

`ERROR_CODES.md` jest generowany i nie należy edytować go ręcznie.

## Granice SOA i POA

Pole `architecture` opisuje warstwę, która utworzyła zdarzenie, a nie transport:

- `SOA` — usługa lub adapter wykonujący operację HTTP/USB/Modbus. Odpowiedź
  zawiera co najmniej `error_code`, `status`, `component`, `stage` i
  `correlation_id`;
- `POA` — proces OQL identyfikowany przez stabilne `c2004://...`. Warstwa POA
  zachowuje kod błędu SOA i dodaje `process_uri`, `run_id` oraz etap procesu;
- frontend emituje `HTTP_REQUEST` dla granicy SOA oraz `OQL_ACTION_START` /
  `OQL_ACTION` dla granicy POA. Nie tworzy alternatywnych kodów dla tego samego
  błędu.

Przepływ komendy jest jednokierunkowy:

```text
UI -> POA RUN_URI (c2004://...) -> SOA OqlOS -> SOA adapter sprzętowy
```

### Macierz odpowiedzialności warstw

| Granica | `architecture` | `layer` | Wymagany kontekst |
| --- | --- | --- | --- |
| frontend → API | `SOA` | `frontend` | metoda, URL, status, czas, `correlation_id` |
| frontend → proces OQL | `POA` | `frontend` | event, `process_uri`, tryb, czas, rezultat |
| C2004 process runtime | `POA` | `process-runtime` | `process_uri`, `run_id`, komponent i etap adaptera |
| OqlOS API/plugin gateway | `SOA` | `oqlos` | plugin/komponent, etap API lub adaptera |
| sidecar Tic/DRI/Modbus | `SOA` | `firmware` | fizyczny komponent, etap walidacji/wykonania |
| OQL over MQTT agent | `SOA` | `firmware` | komponent agenta, etap MQTT, publiczny kod |

Każda granica zachowuje przychodzący `X-Correlation-ID` (alternatywnie
`X-Request-ID`) i zwraca go w nagłówku oraz body. Wygenerowanie nowego ID jest
dozwolone tylko na pierwszej granicy, gdy klient nie dostarczył poprawnego
identyfikatora. Błąd ma `Content-Type: application/problem+json`.

Przy propagacji odpowiedzi nie wolno zamieniać domenowego błędu na ogólne
`HTTP 503`, zwracać `200` z `success=false` ani nadpisywać
`C2004-HW-0012`/`C2004-DATA-0002` kodem `C2004-NET-0001`. Granice mogą
dodawać kontekst, lecz `error_code` oraz `correlation_id` pozostają spójne.

## Zasady mapowania

| Sytuacja | HTTP | Kod publiczny | Przykład issue OqlOS |
| --- | ---: | --- | --- |
| Niepoprawny payload | 422 | `C2004-DATA-0002` | `api_modbus_wizard_invalid_request` |
| Niepoprawna składnia/żądanie HTTP | 400 | `C2004-DATA-0004` | błąd granicy HTTP |
| Brak zasobu | 404 | `C2004-DATA-0001` | zależny od domeny |
| Brak roli do aktuacji | 403 | `C2004-AUTH-0002` | kontekst endpointu |
| Wymagany sprzęt niedostępny | 503 | `C2004-HW-0012` | np. `hw_modbus_no_response` |
| Port RS485 zajęty | 409 | `C2004-HW-0013` | `serial_port_busy` |
| Aktywne undervoltage BoardNet | 503 | `C2004-HW-0014` | `boardnet_undervoltage_active` |
| Nieznany błąd programu | 500 | `C2004-SYS-0000` | typ wyjątku tylko w diagnostyce serwera |

`C2004-SYS-0000` jest ostatnią granicą bezpieczeństwa, a nie docelowym kodem
domenowym. Powtarzalny błąd zakończony `SYS-0000` wymaga dodania jawnego
`OqlosError` i testu regresyjnego.

### Zweryfikowana macierz pierwszej partii NEXT-04

| Operacja / awaria | HTTP | Kod | `architecture/layer` | `component` / `stage` | Bezpieczny target |
| --- | ---: | --- | --- | --- | --- |
| OQL MQTT wyłączony | 503 | `C2004-HW-0012` | `SOA/oqlos` | `oqlos-api` / `api.error` | brak transportu |
| OQL MQTT timeout | 504 | `C2004-NET-0003` | `SOA/firmware` | `oql-mqtt-agent` / `mqtt.response` | `mqtt-node://<node>/oql` |
| zdalny błąd sprzętu OQL | status katalogu | zachowany kod `C2004-HW-*` | pola odpowiedzi agenta | bezpieczne etykiety agenta | `mqtt-node://<node>/oql` |
| brak pól komendy CQRS | 422 | `C2004-DATA-0002` | `SOA/firmware` | `hardware-cqrs` / `command.validate` | nie dotyczy |
| nieudana komenda diagnostyczna | 503 | kod urządzenia, np. `C2004-HW-0012` | `SOA/firmware` | `hardware-diagnostics` / `diagnostic.execute` | `hardware-peripheral://<id>` |
| Modbus wizard bez weryfikacji | 503 | `C2004-HW-0012` | `SOA/firmware` | `modbus-wizard` / `program.verify` | `serial-device://<name>` |
| błędna komenda HUI / artificial-lung | 422 | `C2004-DATA-0002` | `SOA/firmware` | komponent sprzętowy / `command.validate` | nie dotyczy |
| niedostępna akcja HUI | status katalogu | kod wyniku, np. `C2004-HW-0012` | `SOA/firmware` | `hardware-hui` / `action.execute` | lokalna akcja sprzętowa |
| niedozwolona akcja systemd | 422 | `C2004-DATA-0002` | `SOA/host` | `systemd-control` / `action.validate` | whitelisted unit |
| jednostka systemd poza whitelistą | 403 | `C2004-AUTH-0002` | `SOA/host` | `systemd-control` / `unit.authorize` | wartość wejściowa nie jest publikowana |
| zapis konfiguracji bez roli systemowej | 403 | `C2004-AUTH-0002` | `SOA/oqlos` | `hardware-configuration` / `role.authorize` | rola wejściowa nie jest publikowana |
| impuls cewki bez roli systemowej | 403 | `C2004-AUTH-0002` | `SOA/firmware` | `modbus-coil-test` / `role.authorize` | rola i payload nie są publikowane |
| ścieżka edytora poza katalogiem scenariuszy | 403 | `C2004-AUTH-0002` | `SOA/oqlos` | `scenario-editor` / `path.authorize` | ścieżka i root systemu plików nie są publikowane |
| brak scenariusza w rejestrze | 404 | `C2004-DATA-0001` | `SOA/oqlos` | `scenario-registry` / `scenario.lookup` | identyfikator wejściowy nie jest publikowany |
| błędny payload rejestracji DSL | 422 | `C2004-DATA-0002` | `SOA/oqlos` | `scenario-registry` / `payload.validate` | publikowane jest tylko pole i oczekiwany typ |
| niedostępny parser scenariuszy | 503 | `C2004-NET-0002` | `SOA/oqlos` | `scenario-parser` / `dependency.load` | tekst wyjątku importu nie jest publikowany |
| niepełny lub błędny request wykonania | 422 | `C2004-DATA-0002` | `SOA/oqlos` | `scenario-execution` / walidacja źródła, DSL lub komendy | publikowany jest wyłącznie stabilny `reason` |
| scenariusz wykonania nie istnieje | 404 | `C2004-DATA-0001` | `SOA/oqlos` | `scenario-execution` / `scenario.lookup` | identyfikator wejściowy nie jest publikowany |
| sterowanie bez aktywnego wykonania | 409 | `C2004-DATA-0003` | `SOA/oqlos` | `scenario-execution` / `state.validate` | brak negatywnego envelope przy HTTP 200 |
| brak pluginu w rejestrze | 404 | `C2004-DATA-0001` | `SOA/firmware` | `plugin-registry` / `plugin.lookup` | identyfikator wejściowy nie jest publikowany |
| brak peryferium w rejestrze | 404 | `C2004-DATA-0001` | `SOA/firmware` | `peripheral-registry` / `peripheral.lookup` | identyfikator wejściowy nie jest publikowany |
| błędny start lub krok execution API | 422 | `C2004-DATA-0002` | `SOA/oqlos` | `scenario-execution` / `dsl.validate` albo `step.validate` | DSL i payload nie są publikowane |
| brak execution ID | 404 | `C2004-DATA-0001` | `SOA/oqlos` | `scenario-execution` / `execution.lookup` | execution ID nie jest publikowane |
| legacy control bez bieżącego wykonania | 409 | `C2004-DATA-0003` | `SOA/oqlos` | `scenario-execution` / `state.validate` | jawny konflikt zamiast mylącego 404 |
| nieznany błąd orkiestratora | 500 | `C2004-SYS-0000` | `SOA/oqlos` | `oqlos-api` / `api.error` | typ wyjątku bez komunikatu i tracebacku |
| błąd wykonania systemd | 503 | `C2004-HW-0012` | `SOA/host` | `systemd-control` / `action.execute` | whitelisted unit |
| zdalne wykonanie scenariusza w editorze | status kodu agenta | zachowany kod MQTT | `SOA/firmware` | agent / etap MQTT | `mqtt-node://<node>/oql` |
| nieotypowany `HTTPException` 5xx | status katalogu | kod wynikający ze statusu | `SOA/oqlos` | `oqlos-api` / `http.exception` | granica API |
| nieznany błąd agenta | 500 | `C2004-SYS-0000` | `SOA/firmware` | etykiety agenta / etap MQTT | target bez hosta i danych dostępowych |

Na granicy `/api/v1/oql/execute` i `/manage` identyfikator z
`X-Correlation-ID` lub `X-Request-ID` jest przekazywany do requestu MQTT,
odpowiedzi MQTT, problem details oraz nagłówka odpowiedzi. Zdalne `ok=false`
nie jest już sukcesem HTTP. Publiczny komunikat pochodzi z katalogu C2004;
surowy komunikat brokera, sidecara lub adaptera nie jest kopiowany do body.
Nieznany wyjątek agenta mapuje się na `C2004-SYS-0000`, nie na bazodanowy
`C2004-SYS-0001`.

### Reguły wykrywania i walidacji kodu

Kod jest ustalany w następującej kolejności:

1. `OqlosError` zachowuje jawny, zarejestrowany kod publiczny przekazany przez
   zaufaną granicę transportową; w pozostałych przypadkach używa mapowania
   lokalnego `issue_code → C2004-*`.
2. Agent MQTT klasyfikuje `TimeoutError` jako `C2004-NET-0003`, `ValueError`
   jako `C2004-DATA-0002`, błąd systemowy urządzenia/portu jako
   `C2004-HW-0012`, a nierozpoznany wyjątek jako `C2004-SYS-0000`.
3. Zewnętrzny problem details jest uznawany wyłącznie wtedy, gdy jego kod
   istnieje w katalogu. Kod nieznany, np. `C2004-HW-9999`, jest odrzucany i
   zastępowany kodem wynikającym ze statusu granicy.
4. Status HTTP jest zawsze normalizowany do `http_status` wpisu katalogowego.
   Nie jest dozwolona odpowiedź z kodem `C2004-NET-0003` i statusem innym niż
   504 ani `C2004-DATA-0002` ze statusem innym niż 422.
5. Niepoprawny `correlation_id` jest zastępowany lokalnym identyfikatorem;
   upstream nie może wstrzyknąć dowolnej wartości do nagłówka odpowiedzi.

Testy katalogu blokują brak mapowania lokalnego issue, kod nieistniejący w
katalogu, rozbieżność mapy statusów HTTP oraz literalny `OqlosError`, którego
status nie odpowiada publicznemu kodowi. Oddzielna macierz testuje klasy
wyjątków MQTT i sanitację problem details z upstream.

Nieotypowany `HTTPException` o statusie 5xx nigdy nie publikuje swojego
`detail` ani kontekstu wejściowego. Granica wybiera komunikat z katalogu,
zapisuje bezpieczny `component=oqlos-api`, `stage=http.exception` oraz zachowuje
identyfikator korelacji. Szczegóły wyjątku mogą pozostać wyłącznie w logu
serwera. Ta zasada obejmuje między innymi operacje plikowe edytora i awarie
parsera DSL.

## Diagnostyka zasilania Raspberry Pi

`vcgencmd get_throttled` zwraca maskę bitową. Najważniejsze bity:

| Bit | Znaczenie |
| ---: | --- |
| 0 | undervoltage aktywne teraz |
| 1 | ograniczenie częstotliwości aktywne teraz |
| 2 | throttling aktywny teraz |
| 3 | soft temperature limit aktywny teraz |
| 16–19 | odpowiednie zdarzenie wystąpiło od uruchomienia systemu |

Polityka systemowa:

- aktywny bit 0 oznacza krytyczny `C2004-HW-0014` i powinien blokować nowe
  operacje wymagające stabilnego zasilania;
- sam bit 16 oznacza zdarzenie historyczne i powinien generować WARN, nie
  aktywny ERROR;
- powrót bitu 0 do zera kończy aktywny alarm, ale zachowuje zdarzenie w historii;
- każda zmiana stanu powinna zawierać `observed_at`, surową maskę, rozkodowane
  flagi i `correlation_id`.

`vcgencmd measure_volts core` mierzy napięcie rdzenia SoC. Nie jest pomiarem
napięcia wejściowego 5 V ani poboru mocy stanowiska. Rzeczywisty pomiar A/W
wymaga zewnętrznego sensora, np. INA219/INA260, miernika USB lub telemetrii
zasilacza. Takie źródło powinno publikować co najmniej `voltage_v`, `current_a`,
`power_w`, `sampled_at` i stan kalibracji.

`pi_system_diagnostics()` zachowuje kompatybilne pola surowe `throttled` i
`core_volt`, a dodatkowo zwraca typowane `power`: `status`, `mask_hex`,
`active`, `historical`, `active_flags`, `historical_flags`, `errors`,
`warnings`, `observed_at`, `age_ms` i `source`. Aktywny bit 0 jest automatycznie
mapowany na `C2004-HW-0014`; historyczny bit 16 pozostaje ostrzeżeniem.

Wspólna bramka `oqlos.hardware.power_safety` działa przed adapterem dla runtime
OQL, REST, MQTT `manage`, surowych komend pluginów i zapisów Modbus. Nie blokuje
odczytów ani komend bezpiecznego STOP/deenergize/OFF. Zmiana maski jest
publikowana jako `hardware.power_state_changed`; identyfikator eventu jest
identyfikatorem tej samodzielnej obserwacji telemetrycznej.

## Standard logowania procesu

- poziom aplikacji: `OQLOS_LOG_LEVEL` (domyślnie `INFO`);
- szczegóły klienta HTTP: `OQLOS_HTTP_CLIENT_LOG_LEVEL` (domyślnie `WARNING`),
  aby polling ADC nie zalewał logu wpisami `httpx INFO`;
- plik: `OQLOS_LOG_FILE`;
- rotacja: `OQLOS_LOG_MAX_BYTES` (domyślnie 10 MB) oraz
  `OQLOS_LOG_BACKUP_COUNT` (domyślnie 5);
- systemd wysyła stdout/stderr do journalu i nie dopisuje równolegle do pliku
  zarządzanego przez `RotatingFileHandler`.

Każdy spodziewany błąd domenowy powinien zawierać `error_code`, `issue_code`,
`severity`, `architecture`, `component`, `stage`, komunikat i identyfikator
korelacji na granicy HTTP. Odczyt
diagnostyczny może mieć `ok=false` przy HTTP 200 tylko jako raport zbiorczy z
jawnym `overall_status`.

## Ślad komendy w URL

Dla operacji operatorskich UI zapisuje bezpieczny, jawny zamiar i rezultat w
query args. Minimalny kontrakt:

```text
COMMAND=coil-test-pulse
COIL=DO1
ADDRESS=0
DURATION_MS=300
REQUEST_ROLE=system
RESULT=ERROR
HTTP_STATUS=503
ERRORS=C2004-HW-0012,HTTP_503,MODBUS_IO_UNAVAILABLE
```

Zasady:

- przed requestem `RESULT=PENDING` i `ERRORS=PENDING`;
- sukces: `RESULT=OK`, `ERRORS=NONE`;
- błąd: stabilna, rozdzielona przecinkami lista kodów;
- wartości opisują zamiar, ale nie uruchamiają komendy po odświeżeniu strony;
- parent iframe otrzymuje ten sam stan przez protokół
  `oqlos-hardware:navigate`;
- w URL nie zapisujemy tokenów, sekretów, surowych nagłówków ani dużych
  payloadów. Dla złożonego requestu zapisujemy identyfikator lub hash.

Obecnie kontrakt jest wdrożony dla testu cewek DO1–DO8. Pozostałe komendy HUI,
silników, RTC i kreatora Modbus wymagają wspólnego middleware.

## Minimalne testy regresyjne endpointu

Każdy endpoint wykonujący operację sprzętową musi testować:

1. poprawny model requestu,
2. błędny typ i brak wymaganej wartości bez wejścia do adaptera,
3. brak roli,
4. niedostępny adapter,
5. stabilny publiczny kod `C2004-*` i lokalny `issue_code`,
6. brak sekretów i tracebacka w odpowiedzi,
7. stan bezpieczny urządzenia po odrzuconym requestcie.

Nieznane pole requestu musi być odrzucone przed użyciem wartości domyślnych.
Jest to wymóg bezpieczeństwa, nie tylko walidacja stylistyczna: literówka w
parametrze ruchu nie może uruchomić komendy z domyślną liczbą kroków, prędkością
ani liczbą cykli. FastAPI używa `extra="forbid"`, a niezależne sidecary Flask
równoważnej jawnej listy dozwolonych pól.

## Weryfikacja wielowarstwowa live

Po wdrożeniu 2026-07-27 ten sam `cor-layer-fixed` został zachowany przez
odpowiedzi C2004 POA, OqlOS SOA oraz firmware Tic/DRI. Bezpieczne przypadki
negatywne zwróciły:

| Warstwa | HTTP | Kod | `architecture/layer` |
| --- | ---: | --- | --- |
| C2004 nieznany `process_uri` | 404 | `C2004-DATA-0001` | `POA/process-runtime` |
| OqlOS brak pluginu | 503 | `C2004-HW-0012` | `SOA/oqlos` |
| Tic nieznane pole komendy | 422 | `C2004-DATA-0002` | `SOA/firmware` |
| DRI nieznane pole komendy | 422 | `C2004-DATA-0002` | `SOA/firmware` |

Po testach Tic miał `energized=false`, `velocity=0`, a DRI `enabled=false`,
`duty=0`.
