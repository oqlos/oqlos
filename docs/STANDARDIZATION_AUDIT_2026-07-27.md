# Audyt standaryzacji OqlOS/C2004

Stan zweryfikowany: 2026-07-27. Audyt obejmuje kod OqlOS, kontrakt środowiska
C2004, OpenAPI, testy firmware/frontendu oraz bezpieczne odczyty live. Nie
wykonywano impulsów cewek, programowania Modbus ani ruchu silników.

## Podsumowanie

System działa funkcjonalnie, ale struktura nie jest jeszcze optymalna ani w
pełni spójna kontraktowo. Największe ryzyka nie wynikają z nazw OQL (te są już
poprawne), lecz z rozproszonych zmiennych środowiskowych, słabo typowanych
endpointów, mieszanej semantyki odpowiedzi i diagnostyki bez informacji o
świeżości.

| Obszar | Wynik audytu | Docelowy standard |
| --- | --- | --- |
| Zmienne | 90 nazw `OQLOS_*` używanych w Pythonie; 78 nieobecnych w centralnym kontrakcie C2004 | jeden rejestr: typ, default, jednostka, owner, secret, scope, deprecated alias |
| Modele wejścia | 18 tras FastAPI przyjmuje `dict[str, Any]` | osobny model Pydantic dla każdej komendy |
| Błędy | 25 lokalnych issue ma mapowanie, ale pozostają surowe wyjątki i odpowiedzi `ok=false` z HTTP 200 | RFC 9457 + `C2004-*` + `issue_code` dla każdego przewidywalnego błędu |
| OpenAPI | 305 operacji; 131 bez jawnego schematu odpowiedzi; 163 z generycznym obiektem | typowane modele odpowiedzi i jawne kody 2xx/4xx/5xx |
| Odpowiedzi | mieszane pola `ok` i `success`; błędy sprzętowe bywają zwracane jako HTTP 200 | jedna koperta i jedna semantyka statusu HTTP |
| Walidacja OQL | 11 warstw przechodzi osobno bez błędów; naiwne sklejenie dokumentów daje fałszywe błędy nagłówków | walidator świadomy warstw i `INCLUDE`, nie konkatenacja dokumentów |
| Testy | firmware 495/495, frontend 142/142 + build; część testów zależy od `PYTHONPATH` | clean checkout, jawne źródło importu, lint i OpenAPI diff w CI |

## 1. Zmienne i konfiguracja

### Zasady nazw

- Kanoniczne zmienne procesu OqlOS mają prefiks `OQLOS_`.
- Jednostka jest częścią nazwy: `_MS`, `_SECONDS`, `_BYTES`, `_V`, `_A`, `_W`.
- Boolean przyjmuje wyłącznie `true/false`, a parser jest wspólny.
- Adresy mają sufiks `_URL`; same hosty `_HOST`; porty `_PORT`.
- Sekrety nie mają wartości domyślnej, nie trafiają do logów ani query args.
- Stara nazwa może być tylko udokumentowanym aliasem z terminem usunięcia.

Każdy wpis centralnego rejestru musi zawierać: `name`, `type`, `default`,
`required`, `unit`, `scope`, `owner`, `secret`, `description`, `aliases` i
`deprecated_after`. Kod nie powinien czytać `os.getenv()` poza wspólną warstwą
settings, z wyjątkiem wąskich adapterów uruchamianych niezależnie.

### Bramka CI

Test statyczny porównuje użycia `OQLOS_*` z rejestrem środowiska. Nowa zmienna
bez wpisu kontraktowego lub nieużywany wpis bez oznaczenia `reserved` blokuje
merge/deploy. W okresie migracji raportuje się również 58 wykrytych nazw legacy.

## 2. Funkcje, endpointy i odpowiedzi

Każda publiczna operacja ma cztery jawne typy: request, success response,
problem response oraz zdarzenie audytowe. Funkcja domenowa nie powinna znać
`HTTPException`; tłumaczenie domena → HTTP należy do jednej warstwy API.

Docelowa semantyka:

- `ok=true` oznacza zakończoną operację lub poprawny odczyt;
- nie wprowadzamy nowych pól `success`; istniejące są migrowane do `ok`;
- błąd walidacji to 422, brak roli 403, konflikt 409, niedostępny wymagany
  sprzęt 503, timeout upstreamu 504;
- odpowiedź HTTP 200 z `ok=false` jest dozwolona wyłącznie dla jawnego raportu
  zbiorczego, który ma osobne pole `overall_status`; nie dla pojedynczej komendy;
- health rozróżnia stan startowy, bieżący i cache’owany.

OpenAPI powinno zawierać schematy odpowiedzi, przykłady kodów `C2004-*`, pola
jednostek i informację, czy endpoint może uruchomić aktuację.

## 3. Błędy i diagnostyka

Publiczny kontrakt błędu opisuje
[ERROR_STANDARDIZATION.md](ERROR_STANDARDIZATION.md). Dalszej standaryzacji
wymagają:

1. Slug publiczny musi odpowiadać domenie. `modbus-io` nie może być opisywany
   slugiem przeznaczonym wyłącznie dla telemetrii ADC.
2. Severity lokalnego issue i publicznego błędu musi mieć jawną, testowaną
   regułę mapowania.
3. `init_summary.connected` opisuje tylko wynik inicjalizacji i nie może być
   interpretowane jako bieżący health. Należy dodać `observed_at`, `age_ms` i
   `source=live|cache|startup`.
4. Startup diagnostics nie może nadpisywać świeżego błędu Modbus starym stanem
   `OK`; przeterminowana próbka ma status `stale`.
5. Znane `ValueError`/`RuntimeError` na granicy API powinny zostać zastąpione
   domenowym `OqlosError` lub jawnie przetłumaczone.

## 4. Walidacja

- Każdy endpoint aktuacyjny używa modelu Pydantic ze ścisłymi typami
  (`StrictBool`, zakresy liczb, enumy, jednostki).
- Walidacja ma nastąpić przed pobraniem locka i przed wywołaniem adaptera.
- OQL jest walidowany per dokument i następnie jako graf warstw/`INCLUDE`.
- Walidator bundle raportuje `file`, `layer`, `line`, `code` i unika fałszywych
  błędów z wielu nagłówków `VERSION/SCENARIO`.
- Format OQL/YAML/JSON korzysta z jednego modelu domenowego i testu round-trip.
- Zasoby i aliasy OQL są `snake_case`; etykiety sprzętowe typu `AI01` mogą
  pozostać wartością wyświetlaną, lecz nie nazwą deklaracji.

## 5. Testy i quality gates

Minimalna macierz dla komendy sprzętowej:

1. poprawny request z mockowanym adapterem;
2. zły typ, zakres, brak pola i dodatkowe pole;
3. brak roli;
4. adapter offline, timeout i częściowa odpowiedź;
5. kod HTTP, `C2004-*`, `issue_code`, `correlation_id` i brak sekretów;
6. potwierdzenie, że odrzucony request nie wywołał adaptera;
7. zgodność modelu z OpenAPI;
8. test UI śladu `COMMAND/RESULT/ERRORS` bez ponowienia komendy po reloadzie.

CI musi uruchamiać testy w czystym checkout z lokalnym pakietem zainstalowanym
editable lub jako wheel. Test startowy sprawdza `Path(oqlos.__file__)`, aby
wykryć przypadkowy import z innego checkoutu. Nie wolno naprawiać tego przez
lokalne, nieudokumentowane ustawienie `PYTHONPATH`.

Lint należy wdrażać z kontrolowanym baseline. Fasady z re-eksportami dostają
jawne `__all__` albo wąskie wyłączenie reguły; nie usuwa się mechanicznie
importów, które są częścią publicznego API.

## 6. Wynik bezpiecznego smoke live

- DisplayNet `/api/v3/health`: 10/10 odpowiedzi, maksimum około 5 ms.
- OQL Store `/system/raw`: 10/10, maksimum około 23 ms.
- BoardNet `/health`: 10/10, maksimum około 12 ms.
- BoardNet `/api/v1/hardware/health`: 10/10, ale maksimum około 2,1 s.
- DisplayNet → BoardNet: `up`; BoardNet → DisplayNet: `unknown`.
- Power: `get_throttled=0x0`; brak aktywnego undervoltage.
- Modbus coil plan: HTTP 200 z `ok=false`; `read_coils` timeout 2 s, a stany
  DO1–DO8 są `unknown` (`null`), nie `OFF`.

Wniosek operatorski: odczyty OQL i host są dostępne, ale Modbus-IO jest obecnie
degraded. Nie wolno przedstawiać nieznanych stanów cewek jako wyłączonych ani
wykonywać testu impulsowego, dopóki bieżący health i safety gate nie są zdrowe.

