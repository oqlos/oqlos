# Hardware Diagnostics DSL

Interaktywne narzędzia do wykrywania i diagnostyki sprzętu przez USB/serial/I2C z interfejsem shell.

## Szybki start

```bash
# Interaktywny shell diagnostyczny
python -m oqlos.tools.hardware_diagnose --shell

# Lista urządzeń USB
python -m oqlos.tools.hardware_diagnose --list

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
  EXPECT_DEVICE "/dev/ttyACM0" "CH340" "Modbus RTU"
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
- `ttyACM1` → Modbus RTU (Waveshare 8CH IO)
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
