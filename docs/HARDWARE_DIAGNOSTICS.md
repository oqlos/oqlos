# Hardware Diagnostics DSL

Interaktywne narzędzia do wykrywania i diagnostyki sprzętu przez USB/serial/I2C z interfejsem shell.

## Szybki start

```bash
# Zalecany pierwszy krok przed realnym testem sprzętu
oqlctl doctor

# Tylko inteligentna detekcja hosta i konfiguracji
oqlctl detect

# JSON do CI / skryptów operatora
oqlctl doctor --json
oqlctl detect --json

# Bezpieczna automatyczna naprawa wykrytych parametrów Modbus w oqlos.yaml
oqlctl doctor --fix

# Interaktywny shell diagnostyczny
python -m oqlos.tools.hardware_diagnose --shell

# Lista urządzeń USB
python -m oqlos.tools.hardware_diagnose --list

# Smart detect / doctor przez moduł diagnostyczny
python -m oqlos.tools.hardware_diagnose --detect
python -m oqlos.tools.hardware_diagnose --doctor

# Status health
python -m oqlos.tools.hardware_diagnose --health

# Pełna diagnostyka
python -m oqlos.tools.hardware_diagnose --diagnose

# Test kalibracji sprzętu
python -m oqlos.tools.hardware_diagnose --calibrate

# Benchmark wydajności (10 sekund)
python -m oqlos.tools.hardware_diagnose --benchmark

# Benchmark 5 sekund
python -m oqlos.tools.hardware_diagnose --benchmark 5

# Zapisz raport do pliku
python -m oqlos.tools.hardware_diagnose --report
python -m oqlos.tools.hardware_diagnose --report my_report.json
```

## Smart Detect i Doctor

`detect` zbiera sygnały lokalne i runtime:

- urządzenia USB/serial widoczne na hoście,
- magistrale I2C,
- aktywny Modbus RTU przez `probe_waveshare_modbus()`,
- ścieżkę i parametry `oqlos.yaml`,
- health i identify firmware bridge.

`doctor` analizuje te dane i tworzy listę problemów oraz napraw:

| Kod | Znaczenie | Typowa naprawa |
|-----|-----------|----------------|
| `modbus_config_mismatch` | `oqlos.yaml` wskazuje inny port/baud niż odpowiadające urządzenie Modbus | `oqlctl doctor --fix` |
| `serial_port_busy` | skonfigurowany port Modbus jest już otwarty przez inny proces; działa także dla symlinków `/dev/serial/by-id/...` | zatrzymaj drugi proces albo użyj jego `--firmware-url` |
| `firmware_not_real` | firmware działa w `mock`, więc endpointy aktuatorów nie dotykają sprzętu | uruchom z `HARDWARE_MODE=real` albo `OQLOS_HARDWARE_MODE=real` |
| `firmware_no_serial_access` | host widzi `/dev/ttyACM*`/`/dev/ttyUSB*`, ale firmware nie | podmontuj urządzenia do kontenera albo uruchom firmware na hoście |
| `remote_firmware_no_serial_access` | lokalny host widzi USB, ale zdalne firmware ich nie widzi | podłącz sprzęt do hosta firmware albo uruchom firmware lokalnie |
| `adapter_*_not_ok` / `adapter_*_health_not_ok` | konkretny adapter firmware jest offline/no-access albo health zwraca błąd | sprawdź zasilanie, mounty, URL serwisów i uprawnienia |

Przykład:

```bash
oqlctl doctor
oqlctl doctor --json | jq '.issues[] | {severity, code, message}'
```

`--fix` stosuje tylko naprawy oznaczone jako bezpieczne. Aktualnie oznacza to
aktualizację `plugins.modbus-io.connection_params` w `oqlos.yaml` do wykrytych
wartości `serial_port`, `baudrate` i `parity`. Przed zapisem tworzony jest
backup `oqlos.yaml.bak`.

Zmiany runtime są celowo ręczne: `doctor --fix` nie przełącza firmware z
`mock` na `real`, nie restartuje kontenerów i nie montuje `/dev/ttyACM*` ani
`/dev/ttyUSB*`. W raporcie pojawią się jako `Unapplied repairs` z konkretną
wskazówką, co trzeba zmienić w uruchomieniu firmware.

Domyślne oczekiwane parametry Waveshare Modbus RTU IO 8CH w tej konfiguracji
to `19200 8N1`. W `oqlos.yaml` preferuj stabilną ścieżkę
`/dev/serial/by-id/...`; numeracja `/dev/ttyACM*` może zmienić się po restarcie
USB. `doctor` kanonizuje symlinki i pokaże realny port zajęty przez proces,
np. `/dev/ttyACM0`.

Gotowy przykład workflow operatora znajduje się w
`examples/hardware/doctor-workflow.sh`.

## Co zostało naprawione (2026-05-05)

Poniższe problemy zostały naprawione w runtime i ścieżkach diagnostycznych:

1. `motor_disable` dla Tic T249
- Endpoint `POST /api/v1/hardware/lung/disable` poprawnie de-energizuje cewki.

2. Wolny `identify` i timeouty po stronie klientów
- `GET /api/v1/hardware/identify` działa w trybie warunkowego skanu:
  - `scan=auto` skanuje tylko gdy plugin health nie jest kompatybilny,
  - `scan=always` wymusza skan,
  - `scan=never` pomija skan.
- Dzięki temu standardowy odczyt stanu ma dużo niższą latencję.

3. Fałszywe `ok=true` przy braku ruchu silnika
- Ścieżka uruchamiania lung zwraca teraz jawny błąd (`ok=false`, `error`, `data.runtime_status`) zamiast pozornego sukcesu.

4. Blokada ruchu przez krańcówki
- Dodano pre-check przed ruchem i jasny komunikat gdy aktywne są obie krańcówki:
  - `Both limit switches are active; movement is blocked`

5. Lepsza klasyfikacja błędów Modbus
- Gdy adapter serial jest otwarty, ale urządzenie Modbus nie odpowiada, raport opisuje tryb `no-response` zamiast mylącego samego błędu blokady portu.

6. Diagnoza niskiego zasilania silnika
- Przy zbyt niskim VIN (np. odłączone 24V) zwracany jest czytelny błąd:
  - `Motor supply voltage is too low`

Szybkie sprawdzenie:

```bash
curl -sS 'http://127.0.0.1:8202/api/v1/hardware/identify?scan=auto' | jq '.diagnostics'
curl -sS 'http://127.0.0.1:8205/api/status' | jq '{forward_limit_active,reverse_limit_active,low_vin,vin_voltage}'
curl -sS -X POST 'http://127.0.0.1:8202/api/v1/hardware/lung?steps=500&speed=10000000&cycles=1&pause=0.5' | jq
```

## Komendy w shellu

| Komenda | Opis |
|---------|------|
| `list` | Wykryte urządzenia USB/serial/I2C |
| `health` | Status health firmware bridge |
| `identify` | Szczegółowa identyfikacja sprzętu (JSON) |
| `diagnose` | Pełny raport diagnostyczny |
| `calibrate` | Test kalibracji wszystkich komponentów |
| `benchmark [sec]` | Benchmark wydajności (domyślnie 10s) |
| `save` | Zapisz raport do pliku JSON |
| `json` | Wyjście JSON do parsowania przez skrypty |
| `help` | Pomoc |
| `exit/quit` | Wyjście |

## Wyjście JSON dla skryptów shell

```bash
# Doctor jako JSON
oqlctl doctor --json | jq '.summary, .issues'

# Detect jako JSON
oqlctl detect --json | jq '.probes.modbus'

# Lista urządzeń jako JSON
python -m oqlos.tools.hardware_diagnose --list --json | jq '.usb_devices[] | select(.vid != null)'

# Health jako JSON
python -m oqlos.tools.hardware_diagnose --health --json | jq '.mode'

# Pełna diagnostyka jako JSON
python -m oqlos.tools.hardware_diagnose --diagnose --json > /tmp/hw_report.json
```

## Skrypt shell do automatyzacji

```bash
# Sprawdź czy sprzęt jest dostępny
./scripts/hardware-check.sh

# Szybki health check
./scripts/hardware-check.sh --quick

# Tylko lista USB
./scripts/hardware-check.sh --usb

# Test pompy
./scripts/hardware-check.sh --test-pump

# Zdalny firmware
FIRMWARE_URL=http://192.168.1.100:8202 ./hardware-check.sh
```

## Format DSL OQL dla diagnostyki

```oql
# SCENARIO: Hardware Diagnostics
GOAL: Detect and validate all hardware components
  # Wykrywanie urządzeń
  EXPECT_DEVICE "/dev/ttyACM1" "CH340" "Modbus RTU"
  EXPECT_DEVICE "/dev/ttyUSB0" "FTDI" "Serial"
  
  # Sprawdzenie health
  API_GET "/api/v1/hardware/health"
  ASSERT_STATUS 200
  ASSERT_JSON "mode" "real"
  ASSERT_JSON "piadc" "ok"
  ASSERT_JSON "motor" "ok"
  
  # Test peryferiów
  # piADC zwraca surowe napięcie, więc progi podajemy w voltach.
  SET 'pompa 1' '2.0 l/min'
  WAIT '0.5 s'
  ASSERT_SENSOR 'sc-sensor' '>' '0.73' 'V'
  SET 'pompa 1' '0 l/min'
  
  # Raport dla shell
  SHELL_EXPORT "HARDWARE_OK" "true"
```

## Test kalibracji

Test kalibracji sprawdza:
1. **Pump response** - czas odpowiedzi pompy DRI0050
2. **Valve actuation** - sekwencja otwarcia/zamknięcia zaworów NC/SC/WC
3. **Sensor readings** - surowe odczyty napięcia ADC z NC/SC/WC
4. **Calibrated valve validation** - scenariusz `oqlos/oqlos/scenarios/test-zaworu.oql` z oknami napięć

Do samego potwierdzenia sterowania zaworami użyj `hardware-valves-smoke.oql`; do walidacji progów na realnym sprzęcie użyj `test-zaworu.oql`.

```bash
# Kalibracja z wyjściem JSON
python -m oqlos.tools.hardware_diagnose --calibrate --json | jq '.tests[] | {name, passed, details}'
```

## Benchmark wydajności

Mierzy:
- Liczbę requestów na sekundę (RPS)
- Latencję (min/max/avg/median)
- Błędy połączenia

```bash
# Benchmark 5 sekund
python -m oqlos.tools.hardware_diagnose --benchmark 5

# Wynik JSON
python -m oqlos.tools.hardware_diagnose --benchmark 10 --json | jq '.rps, .latency_avg_ms'
```

## Raportowanie błędów

Automatyczne zapisywanie pełnego raportu diagnostycznego:

```bash
# Auto-generowana nazwa pliku (hw_diagnostic_YYYYMMDD_HHMMSS.json)
python -m oqlos.tools.hardware_diagnose --report

# Własna nazwa pliku
python -m oqlos.tools.hardware_diagnose --report /tmp/hardware_issue.json

# Raport zawiera:
# - Timestamp
# - USB/Serial devices (VID/PID)
# - I2C buses i chipy
# - Firmware health status
# - Kalibracja wyniki
# - Szczegóły identify
```

### Analiza raportu:

```bash
# Sprawdź czy wszystko OK
jq '.calibration.passed' hw_diagnostic_*.json

# Znajdź błędy
jq '.calibration.errors[]' hw_diagnostic_*.json

# Lista urządzeń USB z VID
jq '.usb_devices[] | select(.vid != null) | {device, vid, pid}' hw_diagnostic_*.json
```

## Wykryte urządzenia

Widoczne urządzenia:
- `/dev/ttyUSB0` (1A86:7523) - CH340 USB-to-Serial
- `/dev/ttyACM0` (067B:2323) - Prolific USB-Serial
- `/dev/ttyACM1` (1A86:55D3) - CH340 USB Single Serial

Mapowanie:
- `ttyACM0` → Potencjalnie debug/tty
- `ttyACM1` → Modbus RTU (Waveshare 8CH IO, 19200 8N1)
- `ttyUSB0` → Dodatkowy serial (opcjonalny)

## Tryby pracy

### Tryb interaktywny (shell)
```bash
$ python -m oqlos.tools.hardware_diagnose
hw-diagnose> list
hw-diagnose> health
hw-diagnose> diagnose
hw-diagnose> exit
```

### Tryb JSON (dla skryptów)
```bash
# Parsowanie w bash
MODE=$(python -m oqlos.tools.hardware_diagnose --health --json | jq -r '.mode')
if [ "$MODE" = "real" ]; then
    echo "Sprzęt w trybie rzeczywistym"
fi
```

### Tryb pełny (dla operatora)
```bash
python -m oqlos.tools.hardware_diagnose --diagnose
```

## Troubleshooting

### Brak urządzeń USB
```bash
# Sprawdź uprawnienia
ls -la /dev/ttyACM* /dev/ttyUSB*
sudo usermod -a -G dialout $USER

# Sprawdź kernel modules
lsmod | grep -E "usbserial|ch341|ftdi_sio"
```

### Brak I2C
```bash
# Włącz I2C
sudo modprobe i2c-dev
sudo modprobe i2c-bcm2835  # dla Raspberry Pi

# Sprawdź dostępność
ls /dev/i2c-*
i2cdetect -y 1
```

### Firmware nie odpowiada
```bash
# Sprawdź czy firmware działa
curl -s http://localhost:8202/health

# Zaloguj się do shell firmware
curl -s http://localhost:8202/api/v1/state
```

### Firmware działa, ale doctor zgłasza mock
```bash
oqlctl doctor
HARDWARE_MODE=real oqlos-server --host 0.0.0.0 --port 8202
```

### Health firmware timeoutuje na Modbus RTU
Jeśli `/api/v1/hardware/health` zwraca `Modbus RTU read_coils timed out`,
adapter USB-serial jest widoczny, ale moduł RTU nie odpowiedział. Najczęstsze
przyczyny:

- RS485 A/B zamienione lub brak wspólnej masy,
- brak zasilania modułu Waveshare,
- inny slave id niż `1`,
- inny baud/parity niż oczekiwane `9600 8N1` lub `19200 8N1`,
- port serial jest zajęty przez inny proces.

Health nie powinien blokować całego API dłużej niż timeout pluginu; sprawdź:

```bash
curl --max-time 10 http://localhost:8202/api/v1/hardware/health
oqlctl doctor
```

BoardNet (`192.168.188.122`) — aktualny przypadek po naprawie z 2026-06-30:

- `mode=real`, `overall_ok=true`,
- Tic249 i DRI0050 są zdrowe,
- Tic249 pozostaje `energized=false` gdy nie wykonuje ruchu,
- `modbus-io` jest zdrowy na `9600/N`, slave ID `2`,
- `modbus-adc` jest wyłączony, bo adapter ADC nie jest obecny.

Bezpieczna diagnostyka read-only na BoardNet:

```bash
ssh pi@192.168.188.122
systemctl --user stop oqlos-hardware-api.service
cd ~/maskservice/pimodbus
export PYTHONPATH=/home/pi/maskservice/pimodbus
PY=/home/pi/oqlos/venv/bin/python

for port in \
  /dev/serial/by-id/usb-1a86_USB_Single_Serial_5958006895-if00 \
  /dev/serial/by-id/usb-1a86_USB2.0-Serial-if00-port0
do
  [ -e "$port" ] || continue
  timeout 70 "$PY" -m pimodbus.provision_cli diagnose \
    --single-port \
    --serial-port "$port" \
    --timeout 0.4 \
    --baudrates 9600,19200 \
    --parities N,E \
    --device-ids 1,2,3,4
done

systemctl --user start oqlos-hardware-api.service
```

Nie uruchamiaj `pimodbus.provision_cli repair --yes`, dopóki skan nie znajdzie
odpowiadającego modułu i dopóki nie jest on fizycznie odizolowany. Przy braku
jakiejkolwiek odpowiedzi najpierw sprawdź zasilanie, A/B, GND, adres/baud modułu
oraz czy właściwy moduł jest podłączony do właściwego adaptera RS485.

### piADC jest widoczne, ale nie ma dostępu do I2C
Jeśli identify pokazuje `/dev/i2c-*`, ale `piadc` ma `permission denied` albo
serwis zgłasza `mock_mode`, użytkownik/usługa firmware nie ma realnego dostępu
do magistrali albo piADC działa w trybie symulacji. Sprawdź:

```bash
ls -l /dev/i2c-*
groups
curl http://localhost:8204/health
```

### Firmware nie widzi seriali w kontenerze
```bash
# Host widzi porty
oqlctl detect

# Kontener musi mieć device mount, np.
# devices:
#   - /dev/ttyACM1:/dev/ttyACM1
```
