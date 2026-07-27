# Standard błędów i diagnostyki OqlOS/C2004

Stan zweryfikowany: 2026-07-27.

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

## Zasady mapowania

| Sytuacja | HTTP | Kod publiczny | Przykład issue OqlOS |
| --- | ---: | --- | --- |
| Niepoprawny payload | 422 | `C2004-DATA-0002` | `api_modbus_wizard_invalid_request` |
| Brak zasobu | 404 | `C2004-DATA-0001` | zależny od domeny |
| Brak roli do aktuacji | 403 | `C2004-AUTH-0002` | kontekst endpointu |
| Wymagany sprzęt niedostępny | 503 | `C2004-HW-0012` | np. `hw_modbus_no_response` |
| Port RS485 zajęty | 409 | `C2004-HW-0013` | `serial_port_busy` |
| Aktywne undervoltage BoardNet | 503 | `C2004-HW-0014` | docelowo `boardnet_undervoltage_active` |
| Nieznany błąd programu | 500 | `C2004-SYS-0000` | typ wyjątku tylko w diagnostyce serwera |

`C2004-SYS-0000` jest ostatnią granicą bezpieczeństwa, a nie docelowym kodem
domenowym. Powtarzalny błąd zakończony `SYS-0000` wymaga dodania jawnego
`OqlosError` i testu regresyjnego.

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

Aktualna luka: `C2004-HW-0014` istnieje w katalogu, a
`pi_system_diagnostics()` zbiera surowe `throttled` i `core_volt`, lecz aktywny
bit nie jest jeszcze automatycznie zamieniany na zdarzenie ERROR ani safety
gate. Realizacja znajduje się w planie refaktoryzacji.

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
