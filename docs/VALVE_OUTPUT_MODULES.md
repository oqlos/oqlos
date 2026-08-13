# Moduły wyjściowe zaworów (OUT)

Zawory na stanowisku C2004 mogą być sterowane przez dwa wymienne moduły mocy.
Wybór modułu jest konfiguracją, nie zmianą kodu scenariuszy — aliasy zaworów
(`valve-1..8`, `valve-nc`, `valve-sc`, `valve-wc`) i komendy OQL pozostają te same.

| Plugin | Moduł | Magistrala | Wyjścia | Uwagi |
|--------|-------|-----------|---------|-------|
| `modbus-io` | Waveshare Modbus RTU IO 8CH | RS485 (USB-serial) | 8 × open-drain, 5–40 V, 500 mA | dotychczasowy domyślny |
| `io-m5-4in8out` | M5Stack Module 4In8Out | I2C (`/dev/i2c-1` lub MCP2221A) | 8 × MOSFET AO3400A, 1 A/kanał, 8 A łącznie | + 4 wejścia stykowe |

Sterownik M5: pakiet `m5-4in8out` (repo `oqlos/m5-4in8out`), plugin
`oqlos/hardware/plugins/m5_4in8out.py`.

## Jak wybierany jest kontroler

`oqlos/hardware/valve_controller.py` rozstrzyga kolejność:

1. `OQLOS_VALVE_CONTROLLER` (override stanowiskowy, np. `modbus-io`),
2. `profiles.hardware.valve_controller` w hardware-configuration-v1
   (pojedyncze id albo lista preferencji),
3. domyślnie: `io-m5-4in8out`, potem `modbus-io`.

Z listy brane są **wyłącznie włączone** pluginy (`enabled: true`). Dlatego
stanowisko, na którym moduł M5 nie jest jeszcze wpięty, dalej pracuje na
`modbus-io` — mimo że M5 stoi wyżej w domyślnej preferencji.

Pozostały kontroler zostaje jako fallback: `set_valve` próbuje kolejnych
modułów, a `all_valves_off` (stan bezpieczny) wykonuje się na **każdym**
włączonym module — stanowisko w trakcie migracji nie może zostawić
zasilonego wyjścia.

Kontroler jest też źródłem prawdy dla:

- gotowości HUI (`hui_hold.py` — readiness przed hold/shutdown),
- opisu wymaganego sprzętu w `GET /api/v1/hardware/hui/actions`,
- mapowania targetów DSL `zawór-*` → plugin (`peripheral_mapping.py`).

## Włączenie modułu M5 4In8Out

1. **Okablowanie** (backend `smbus`): SDA → GPIO2, SCL → GPIO3, GND → GND Pi.
   Zasilanie 9–24 V idzie z osobnego portu modułu (wspólna masa obowiązkowa).
   Wejścia IN1–IN4 przyjmują wyłącznie styk bezpotencjałowy (bez sygnału >5 V).
2. **Sterownik na Pi**: krok deployu `sync_m5_4in8out` + instalacja editable
   w venv OqlOS (patrz `redeploy/122/migration.md`).
3. **Weryfikacja magistrali**: `i2cdetect -y 1` → adres `45`.
   Bez OqlOS: `m5-4in8out status`.
4. **Konfiguracja**: w `hardware-configuration-v1` (`oqlos.yaml` / `oqlos-real.yaml`)

   ```yaml
   io-m5-4in8out:
     enabled: true
     connection_type: i2c
     connection_params:
       backend: smbus      # albo mcp2221
       bus: 1
       address: 0x45
   ```

5. **Restart** usługi hardware i sprawdzenie
   `GET /api/v1/plugins/io-m5-4in8out/health`.
6. Parametry per-device w OQL:
   `layers/hardware/devices/m5-4in8out-boardnet.oql`
   (strona `hardware-coils`, źródło 15).

## Bring-up na BoardNet (kolejność sprawdzona na .131)

Każdy krok musi przejść, zanim ruszysz dalej — inaczej diagnoza kolejnego
błędu jest zgadywanką.

1. **Magistrala hosta** (bez modułu w grze):

   ```bash
   pinctrl get 2-3        # oczekiwane: a0 = SDA1/SCL1, obie linie hi
   ```

   Linia `lo` oznacza zwarcie albo urządzenie trzymające magistralę — wtedy
   nie ma sensu szukać modułu.

2. **Obecność modułu** — read-only, nie rusza wyjść:

   ```bash
   ~/oqlos/venv/bin/python -m m5_4in8out.cli --bus 1 health --json
   ```

   `healthy: true` + `firmware_version` = moduł odpowiada pod `0x45`.
   `Errno 121` / `Errno 5` = brak ACK: sprawdź zasilanie DC IN 9-24 V modułu,
   wspólną masę i SDA/SCL na pinach 3/5.

3. **Test przełączania z weryfikacją** — dopiero gdy do wyjść nic groźnego nie
   jest podpięte albo świadomie na to pozwalasz:

   ```bash
   ~/oqlos/venv/bin/python -m m5_4in8out.cli --bus 1 blink --interval 1 --cycles 5
   ```

   Każda zmiana jest potwierdzana odczytem rejestrów `0x20-0x27`; kod wyjścia 0
   oznacza, że moduł faktycznie przełączył, a wyjścia zostały zgaszone.

4. **Przejęcie zaworów przez OqlOS** — dopiero po kroku 3:
   ustaw `plugins.io-m5-4in8out.enabled: true` w `~/maskservice/config/oqlos-real.yaml`,
   zrestartuj usługę hardware, potem:

   ```bash
   curl -s localhost:8202/api/v1/plugins/io-m5-4in8out/health
   curl -s localhost:8202/api/v1/hardware/hui/readiness   # actions.valves.required_hardware
   ```

   `required_hardware` musi pokazać `io-m5-4in8out` — to potwierdza, że
   resolver kontrolera faktycznie przełączył stanowisko na nowy moduł.

## Powrót na modbus-io

Ustaw `enabled: false` dla `io-m5-4in8out` albo wymuś
`OQLOS_VALVE_CONTROLLER=modbus-io`. Zmiana nie wymaga edycji scenariuszy.

## Mapowanie kanałów

Oba moduły korzystają z jednego katalogu (`oqlos/hardware/modbus_io_catalog.py`):

| Alias | Cewka (kontrakt Modbus, 0-based) | Wyjście M5 (opis na obudowie) |
|-------|----------------------------------|-------------------------------|
| `valve-nc` | 0 | OUT1 |
| `valve-sc` | 1 | OUT2 |
| `valve-wc` | 2 | OUT3 |
| `valve-1..8` | 0..7 | OUT1..OUT8 |

Aliasy zaworów i cewki pozostają 0-based (kontrakt Modbus), a plugin tłumaczy
je na 1-based numerację modułu M5 — `valve-1` to fizyczne `OUT1` na obu
modułach. Sterownik `m5-4in8out` i jego CLI mówią numerami z obudowy (1..8).

Adres „wszystkie wyjścia" Waveshare (`0x00FF`) jest honorowany także przez
plugin M5 i tłumaczony na zapis wszystkich ośmiu kanałów.
