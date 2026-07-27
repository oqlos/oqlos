# Plan dalszej refaktoryzacji OqlOS/C2004

Data bazowa: 2026-07-27. Plan obejmuje OqlOS na BoardNet oraz integrację z
C2004/DisplayNet.

## Zweryfikowany punkt startowy

- OqlOS firmware: 493 testy przechodzą.
- OqlOS frontend: 142 testy przechodzą, build Vite poprawny.
- Mapowanie katalogu błędów C2004/OqlOS: 3 testy kontraktowe przechodzą.
- BoardNet: `mode=real`, `overall_ok=true`, `degraded=false`.
- Modbus-IO: `9600/N/8/1`, slave ID `1`, DO1–DO8 pozostają OFF po testach
  odrzucanych requestów.
- `get_throttled=0x0`; brak aktywnego undervoltage podczas weryfikacji.
- DisplayNet → BoardNet: `up`; BoardNet → DisplayNet: jeszcze `unknown`.
- W buforze replikacji diagnostyki pozostaje backlog.

## Docelowe zasady architektury

1. Każda komenda ma typowany kontrakt przed warstwą adaptera.
2. Każdy przewidywalny błąd ma domenowy `C2004-*`; `SYS-0000` pozostaje tylko
   dla nieznanych defektów.
3. OQL jest źródłem logiki i mapowań, a konfiguracja host/runtime ma jawny,
   wersjonowany kontrakt oraz równoważne kodeki OQL/YAML/JSON.
4. Operacje fizyczne są fail-closed i wymagają zdrowego power/hardware gate.
5. Monitoring działa bez UI i obserwuje połączenie w obu kierunkach.
6. Deploy zawsze pochodzi z przypiętego commita oraz kończy się checksumem,
   smoke-testem i raportem stanu.

## Kolejność realizacji

### RF-01 — Power telemetry i safety gate

Priorytet: P0. Zależności: brak.

Zakres:

- wydzielić parser maski `get_throttled` z polami active/historical;
- emitować `C2004-HW-0014` tylko dla aktywnego bitu undervoltage;
- historyczny undervoltage raportować jako WARN;
- dołączyć stan power do health, startup diagnostics i event streamu;
- przed aktuacją sprawdzać wspólny power gate;
- zaprojektować opcjonalny provider INA219/INA260 dla `voltage_v/current_a/power_w`.

Testy i acceptance:

- maski `0x0`, `0x1`, `0x10000`, `0x10001` mają jednoznaczne wyniki;
- aktywny bit 0 blokuje mockowaną aktuację bez wywołania adaptera;
- stan historyczny nie blokuje operacji;
- live BoardNet raportuje `0x0` bez ERROR.

### RF-02 — Typowane modele wszystkich komend sprzętowych

Priorytet: P0. Zależności: RF-01 dla pól power gate.

Zakres:

- zastąpić `dict[str, Any]` modelami Pydantic w API v3;
- ujednolicić zakresy, enumy, jednostki i semantykę wartości domyślnych;
- odrzucać `"false"` jako boolean i `true` jako integer;
- wygenerować zgodny OpenAPI i klient frontendowy.

Kolejność endpointów: Modbus wizard → coils/HUI → silniki → RTC → runtime
control.

Acceptance: każdy błędny request zwraca 422/C2004-DATA-0002 i nie dociera do
adaptera; pełny firmware suite pozostaje zielony.

### RF-03 — Pełne semantyczne pokrycie ERROR

Priorytet: P0. Zależności: RF-02.

Zakres:

- zinwentaryzować `HTTPException`, `ValueError`, `RuntimeError` i odpowiedzi
  `ok=false`;
- dla przewidywalnych sytuacji użyć `OqlosError` z wygenerowanym mapowaniem;
- dodać CI wykrywające osierocone publiczne kody i lokalne issue;
- dodać test, że odpowiedzi 5xx nie ujawniają tracebacków ani sekretów;
- raportować liczbę `C2004-SYS-0000` jako metrykę regresji.

Acceptance: wszystkie endpointy sprzętowe mają macierz status → public code →
issue code; znane błędy nie kończą jako `SYS-0000`.

### RF-04 — Wspólny command trace dla UI

Priorytet: P1. Zależności: RF-02 i RF-03.

Zakres:

- przenieść obsługę `COMMAND/RESULT/HTTP_STATUS/ERRORS` z HardwareCoilTest do
  współdzielonego klienta;
- dodać `REQUEST_ID`, `CORRELATION_ID`, czas start/finish i whitelistę args;
- obsłużyć HUI, silniki, RTC i Modbus wizard;
- zapewnić identyczny stan w iframe child i parent;
- nigdy nie odtwarzać operacji z samych query args.

Acceptance: test E2E sukcesu i błędu dla każdej klasy komendy; URL nie zawiera
sekretów ani pełnych payloadów.

### RF-05 — Dwukierunkowa diagnostyka rozproszona

Priorytet: P1. Zależności: RF-03.

Zakres:

- uruchomić niezależny watcher BoardNet → DisplayNet;
- domknąć deduplikację i flush backlogu po reconnect;
- dodać limit retencji i metryki dropped/pending/last_flush;
- ujednolicić stan `up/degraded/down/unknown` obu kierunków.

Acceptance: oba kierunki mają status `up`; po kontrolowanym outage timeline
odtwarza się po obu stronach, a backlog wraca do zera.

### RF-06 — OQL i konfiguracja: pełne parity formatów

Priorytet: P1. Zależności: RF-02.

Zakres:

- opisać jedno canonical schema dla OQL/YAML/JSON;
- testować round-trip bez utraty pól;
- oddzielić konfigurację logiczną od sekretów i parametrów hosta;
- dodać lint całego bundle warstw, w tym snake_case dla aliasów i zasobów;
- blokować deploy bundle z błędami walidatora.

Acceptance: `AI01/AI02/AI03/PI1` nie wracają jako nazwy deklaracji; wszystkie
kodeki dają równoważny model domenowy.

### RF-07 — Budżety wydajności i polling

Priorytet: P2. Zależności: RF-05 dla metryk sieciowych.

Budżety początkowe:

- `/health`: p95 < 100 ms,
- `/api/v1/hardware/health`: p95 < 500 ms,
- cached sensor poll: p95 < 500 ms,
- pełny probe sprzętu nie może być wykonywany w każdym pollu UI.

Zakres: cache ostatniej próbki, event/WebSocket dla zmian, timeouty per adapter,
metryki p50/p95/p99 i test soak minimum 30 minut.

Acceptance: brak nakładających się polli, brak 503/504 podczas soak przy zdrowym
sprzęcie, jawny stale age danych.

### RF-08 — Jedno źródło kodu i powtarzalny deploy

Priorytet: P2. Zależności: można prowadzić równolegle.

Zakres:

- traktować repo OqlOS jako canonical source, a C2004 wyłącznie jako pin
  submodułu/pakietu;
- usunąć kopiowane implementacje hardware po zakończeniu migracji;
- budować artefakt z commita, zamiast synchronizować zmodyfikowany worktree;
- zapisywać commit, checksum, wersję schema i wynik smoke w CURRENT_STATE;
- CI ma odrzucać deploy z dirty submodule lub rozjazdem checksum.

Acceptance: ten sam commit daje identyczny pakiet na clean checkout i BoardNet;
nie ma ręcznie zmienionych plików runtime poza katalogami state/config.

## Etapy wdrożeniowe

| Etap | Zakres | Warunek przejścia |
| --- | --- | --- |
| A | RF-01–RF-03 | safety gate i pełna macierz błędów |
| B | RF-04–RF-06 | wspólny trace, oba heartbeat-y, parity formatów |
| C | RF-07–RF-08 | spełnione SLO i powtarzalny deploy |

## Definition of done dla każdego ticketu

- test jednostkowy i regresyjny błędu;
- brak nieautoryzowanej aktuacji w testach;
- aktualizacja OpenAPI oraz dokumentacji operatora;
- `pytest -q tests/firmware` bez błędów;
- `npm run test:unit` i `npm run build` bez błędów;
- checksum lokalny i BoardNet zgodny;
- smoke DisplayNet → BoardNet;
- rollback opisany i możliwy przez przypięcie poprzedniego commita.
