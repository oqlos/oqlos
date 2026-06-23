# OqlOS hardware node — boardnet (192.168.188.122) deploy

Deploys the OqlOS **hardware runtime** plus an **MQTT broker** onto a dedicated
Raspberry Pi 3 (`pi@boardnet.local`). This Pi owns all physical devices (Modbus IO/ADC,
Pololu Tic T249, DFRobot DRI0050, RTC HAT) and runs the OQL-over-MQTT **agent**: it
subscribes to `oqlos/c2004/boardnet/oql/request`, executes the OQL/manage verb against the
local hardware gateway, and publishes the response. The application Pi (pi109) talks to
this node **only over MQTT** — this Pi's HTTP `:8202` stays loopback-only.

See `RUNBOOK.md` for the one-time bare-metal provisioning (OS, ssh keys, apt, linger) that
must happen **before** the first `redeploy run`.

## Uruchomienie

```bash
# From the oqlos repo root, after provisioning per RUNBOOK.md:
redeploy run redeploy/122/migration.md

# Allow the node to come up even if some USB devices are missing (bench mode):
PIHW_ALLOW_MISSING_HARDWARE=1 redeploy run redeploy/122/migration.md
```

Each step below is also a standalone bash script (the `markpact:ref` blocks), so the
RUNBOOK can run them manually over ssh if the automation needs adjusting.

## Uwagi operacyjne

- Broker runs **on this Pi** (mosquitto, systemd --user, :1883). If pi109 reboots or
  redeploys, the hardware + broker stay up together. The agent connects to `127.0.0.1:1883`.
- `PIHW_ALLOW_MISSING_HARDWARE` (default `1`) turns missing-device failures into warnings so
  the node still boots for bench testing.
- Modbus RTU serial framing stays **local** (oqlos-server ↔ /dev/tty* on this Pi). Only OQL
  request/response crosses the LAN — latency-tolerant.
- USB `by-id` strings differ per Pi; `deploy-oqlos-hw-api` autodetects and rewrites the
  Modbus ports in `oqlos-real.yaml`. Never hardcode-trust the placeholders in `oqlos-hw.yaml`.
- Secrets: create `mosquitto.passwd` and set `OQLOS_OQL_MQTT_PASSWORD` in
  `~/maskservice/config/oql-mqtt.env` on the Pi (never commit them).

## Scripts

```bash markpact:ref mkdir-hw-remote
#!/bin/bash
set -euo pipefail
mkdir -p /home/pi/oqlos/oqlos \
         /home/pi/maskservice/config \
         /home/pi/maskservice/logs \
         /home/pi/maskservice/mosquitto \
         /home/pi/maskservice/scripts \
         /home/pi/.config/systemd/user
echo "PASS: katalogi boardnet utworzone"
```

```bash markpact:ref enable-linger-groups
#!/bin/bash
set -euo pipefail
sudo loginctl enable-linger pi 2>/dev/null || true
sudo usermod -aG dialout,plugdev,i2c,gpio pi 2>/dev/null || true
echo "PASS: linger + grupy (dialout,plugdev,i2c,gpio) ustawione"
```

```bash markpact:ref install-mosquitto
#!/bin/bash
set -euo pipefail
mkdir -p /home/pi/maskservice/config /home/pi/maskservice/mosquitto /home/pi/maskservice/logs
if ! command -v mosquitto >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y git python3-venv mosquitto mosquitto-clients
fi
# Disable the system-wide mosquitto; we run it rootless as systemd --user.
sudo systemctl disable --now mosquitto 2>/dev/null || true

cp /home/pi/maskservice/boardnet-config/mosquitto.conf /home/pi/maskservice/config/mosquitto.conf

if [ ! -f /home/pi/maskservice/config/mosquitto.passwd ]; then
  PW="${OQLOS_OQL_MQTT_PASSWORD:-}"
  if [ -z "$PW" ] && [ -f /home/pi/maskservice/config/oql-mqtt.env ]; then
    PW=$(grep -E '^OQLOS_OQL_MQTT_PASSWORD=' /home/pi/maskservice/config/oql-mqtt.env | head -1 | cut -d= -f2-)
  fi
  if [ -z "$PW" ] || [ "$PW" = "CHANGE_ME_ON_PI" ]; then
    echo "FAIL: ustaw OQLOS_OQL_MQTT_PASSWORD w ~/maskservice/config/oql-mqtt.env przed deployem brokera" >&2
    exit 1
  fi
  mosquitto_passwd -b -c /home/pi/maskservice/config/mosquitto.passwd oqlos "$PW"
  echo "INFO: utworzono mosquitto.passwd dla uzytkownika 'oqlos'"
fi

cat > /home/pi/.config/systemd/user/mosquitto.service << 'UNIT'
[Unit]
Description=Mosquitto MQTT broker (OqlOS hardware node)
After=network-online.target

[Service]
Type=simple
ExecStart=/usr/sbin/mosquitto -c /home/pi/maskservice/config/mosquitto.conf
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
UNIT

systemctl --user daemon-reload
systemctl --user enable --now mosquitto.service
sleep 2
if systemctl --user is-active mosquitto.service >/dev/null 2>&1; then
  echo "PASS: mosquitto aktywny na :1883 (systemd --user)"
else
  systemctl --user status mosquitto.service --no-pager || true
  exit 1
fi
```

```bash markpact:ref deploy-pololu-udev
#!/bin/bash
set -euo pipefail
cat > /tmp/99-pololu-tic.rules << 'RULES'
SUBSYSTEM=="usb", ATTR{idVendor}=="1ffb", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1ffb", ATTRS{idProduct}=="00c9", SYMLINK+="maskservice-tic249", MODE="0666", GROUP="plugdev"
RULES
sudo install -m 0644 /tmp/99-pololu-tic.rules /etc/udev/rules.d/99-pololu-tic.rules
rm -f /tmp/99-pololu-tic.rules
sudo udevadm control --reload-rules || true
sudo udevadm trigger -s usb || true
sudo udevadm trigger -s tty || true
sudo find /dev/bus/usb -type c -exec chmod a+rw {} + 2>/dev/null || true
echo "PASS: udev dla Pololu Tic wdrozony (+ alias maskservice-tic249)"
```

```bash markpact:ref deploy-hw-tic249-service
#!/bin/bash
set -euo pipefail
mkdir -p /home/pi/.config/systemd/user /home/pi/maskservice/logs /home/pi/maskservice/scripts
cd /home/pi/maskservice/rpi-motor-tic249
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q ticlib pyusb flask python-dotenv
sed -i '/^USB_SERIAL_NUMBER=/d' .env 2>/dev/null || true

cat > /home/pi/maskservice/scripts/wait-hw-tic249-ready.sh << 'SCRIPT'
#!/bin/bash
set -euo pipefail
for i in {1..45}; do
  curl -sf -X POST -H 'Content-Type: application/json' -d '{}' http://localhost:8205/api/connect >/dev/null 2>&1 || true
  if curl -sf http://localhost:8205/api/status | grep -Eq '"connected"[[:space:]]*:[[:space:]]*true'; then
    echo "PASS: hw-tic249 connected (attempt $i/45)"
    exit 0
  fi
  sleep 1
done
echo 'FAIL: hw-tic249 brak connected=true po retry' >&2
exit 1
SCRIPT
chmod +x /home/pi/maskservice/scripts/wait-hw-tic249-ready.sh

cat > /home/pi/.config/systemd/user/hw-tic249.service << 'UNIT'
[Unit]
Description=Maskservice Pololu Tic T249 hardware adapter

[Service]
Type=simple
WorkingDirectory=/home/pi/maskservice/rpi-motor-tic249
Environment=PATH=/home/pi/maskservice/rpi-motor-tic249/.venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=FLASK_HOST=0.0.0.0
Environment=FLASK_PORT=8205
Environment=USB_PRODUCT_ID=0x00c9
Environment=LOG_LEVEL=INFO
ExecStart=/home/pi/maskservice/rpi-motor-tic249/.venv/bin/python web_panel.py
Restart=always
RestartSec=3
StandardOutput=append:/home/pi/maskservice/logs/hw-tic249.log
StandardError=append:/home/pi/maskservice/logs/hw-tic249.log

[Install]
WantedBy=default.target
UNIT

systemctl --user daemon-reload
systemctl --user enable --now hw-tic249.service
sleep 3
systemctl --user is-active hw-tic249.service
if /home/pi/maskservice/scripts/wait-hw-tic249-ready.sh; then
  echo "PASS: hw-tic249 aktywny i widzi Pololu Tic"
elif [ "${PIHW_ALLOW_MISSING_HARDWARE:-1}" = "1" ]; then
  echo "WARN: hw-tic249 bez Pololu USB — PIHW_ALLOW_MISSING_HARDWARE=1, pomijam"
  exit 0
else
  echo "FAIL: hw-tic249 brak connected=true (ustaw PIHW_ALLOW_MISSING_HARDWARE=1 aby pominąć)" >&2
  exit 1
fi
```

```bash markpact:ref deploy-dri0050-motor-service
#!/bin/bash
set -euo pipefail
mkdir -p /home/pi/.config/systemd/user /home/pi/maskservice/logs /home/pi/maskservice/scripts
cat > /tmp/99-dri0050-usb-serial.rules << 'RULES'
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", MODE="0666", GROUP="dialout"
SUBSYSTEM=="usb", ATTR{idVendor}=="1a86", MODE="0666", GROUP="dialout"
RULES
sudo install -m 0644 /tmp/99-dri0050-usb-serial.rules /etc/udev/rules.d/99-dri0050-usb-serial.rules
sudo udevadm control --reload-rules || true
sudo udevadm trigger -s tty || true
sudo udevadm trigger -s usb || true

cd /home/pi/maskservice/rpi-motor-DRI0050
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
.venv/bin/pip install -q fastapi uvicorn
.venv/bin/pip install -q -e .

cat > /home/pi/maskservice/scripts/start-dri0050-motor-api.sh << 'SH'
#!/bin/bash
set -euo pipefail
cd /home/pi/maskservice/rpi-motor-DRI0050
for _ in $(seq 1 30); do
  DRI_PORT=$(ls -1 /dev/serial/by-id/usb-1a86_USB2.0-Serial-if00-port0 2>/dev/null | head -1 || true)
  if [ -z "${DRI_PORT:-}" ]; then
    for _p in /dev/ttyUSB*; do [ -e "$_p" ] && DRI_PORT="$_p" && break; done
  fi
  [ -n "${DRI_PORT:-}" ] && [ -e "$DRI_PORT" ] && break
  sleep 1
done
if [ -z "${DRI_PORT:-}" ] || [ ! -e "$DRI_PORT" ]; then
  DRI_PORT=/dev/serial/by-id/usb-1a86_USB2.0-Serial-if00-port0
  echo "WARN: DRI0050 USB serial port not found after boot wait; starting on $DRI_PORT" >&2
fi
export DRI0050_PORT="$DRI_PORT"
export DRI0050_FREQ="${DRI0050_FREQ:-1000}"
exec /home/pi/maskservice/rpi-motor-DRI0050/.venv/bin/python web_api.py
SH
chmod +x /home/pi/maskservice/scripts/start-dri0050-motor-api.sh

cat > /home/pi/.config/systemd/user/dri0050-motor-api.service << 'UNIT'
[Unit]
Description=DFRobot DRI0050 pump motor API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/pi/maskservice/rpi-motor-DRI0050
Environment=PATH=/home/pi/maskservice/rpi-motor-DRI0050/.venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=API_PORT=8203
Environment=DRI0050_FREQ=1000
ExecStart=/home/pi/maskservice/scripts/start-dri0050-motor-api.sh
Restart=always
RestartSec=3
StandardOutput=append:/home/pi/maskservice/logs/dri0050-motor-api.log
StandardError=append:/home/pi/maskservice/logs/dri0050-motor-api.log

[Install]
WantedBy=default.target
UNIT

systemctl --user daemon-reload
systemctl --user enable dri0050-motor-api.service
systemctl --user restart dri0050-motor-api.service
sleep 4
if ! systemctl --user is-active dri0050-motor-api.service >/dev/null 2>&1; then
  if [ "${PIHW_ALLOW_MISSING_HARDWARE:-1}" = "1" ]; then
    echo "WARN: dri0050-motor-api nie wystartował — PIHW_ALLOW_MISSING_HARDWARE=1, pomijam"
    exit 0
  fi
  systemctl --user status dri0050-motor-api.service --no-pager || true
  exit 1
fi
curl -sf -X POST http://localhost:8203/api/stop >/dev/null || true
if curl -sf http://localhost:8203/api/status | grep -Eq '"enabled"[[:space:]]*:[[:space:]]*false'; then
  echo "PASS: DRI0050 API aktywny na :8203 i wyjscie pompy wylaczone"
elif [ "${PIHW_ALLOW_MISSING_HARDWARE:-1}" = "1" ]; then
  echo "WARN: DRI0050 API bez zdrowej pompy — PIHW_ALLOW_MISSING_HARDWARE=1, pomijam"
  exit 0
else
  echo "FAIL: DRI0050 API nie raportuje enabled=false po stop" >&2
  exit 1
fi
```

```bash markpact:ref deploy-pirtc-sidecar
#!/bin/bash
set -euo pipefail
mkdir -p /home/pi/.config/systemd/user /home/pi/maskservice/logs
PIRTC_DIR=/home/pi/maskservice/pirtc
[ -f "$PIRTC_DIR/pyproject.toml" ] || { echo "FAIL: brak $PIRTC_DIR — uruchom sync_pirtc"; exit 1; }
cd "$PIRTC_DIR"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -e .

cat > /home/pi/.config/systemd/user/pirtc-api.service << 'UNIT'
[Unit]
Description=piRTC sidecar (Waveshare RTC WatchDog HAT) on :8125
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/pi/maskservice/pirtc
Environment=PATH=/home/pi/maskservice/pirtc/.venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=API_HOST=0.0.0.0
Environment=API_PORT=8125
Environment=RTC_MOCK=false
Environment=WATCHDOG_MOCK=false
Environment=RTC_I2C_ADDRESS=0x68
Environment=RTC_I2C_BUS=1
Environment=WATCHDOG_I2C_ADDRESS=0x67
Environment=WATCHDOG_GPIO_PIN=4
Environment=LOG_LEVEL=INFO
ExecStart=/home/pi/maskservice/pirtc/.venv/bin/pirtc-server
Restart=always
RestartSec=3
StandardOutput=append:/home/pi/maskservice/logs/pirtc-api.log
StandardError=append:/home/pi/maskservice/logs/pirtc-api.log

[Install]
WantedBy=default.target
UNIT

systemctl --user daemon-reload
systemctl --user enable --now pirtc-api.service
sleep 3
if ! systemctl --user is-active pirtc-api.service >/dev/null 2>&1; then
  if [ "${PIHW_ALLOW_MISSING_HARDWARE:-1}" = "1" ]; then
    echo "WARN: pirtc-api nie wystartował — PIHW_ALLOW_MISSING_HARDWARE=1 (brak HAT / I2C?)"
    exit 0
  fi
  systemctl --user status pirtc-api.service --no-pager || true
  exit 1
fi
STATUS=$(curl -sf http://127.0.0.1:8125/api/status 2>/dev/null || true)
if echo "$STATUS" | grep -Eq '"available"[[:space:]]*:[[:space:]]*true' && echo "$STATUS" | grep -Eq '"mock"[[:space:]]*:[[:space:]]*false'; then
  echo "PASS: piRTC sidecar :8125 — RTC HAT dostępny (nie mock)"
elif [ "${PIHW_ALLOW_MISSING_HARDWARE:-1}" = "1" ]; then
  echo "WARN: piRTC bez działającego RTC — PIHW_ALLOW_MISSING_HARDWARE=1"
  exit 0
else
  echo "FAIL: piRTC :8125 bez działającego RTC" >&2
  exit 1
fi
```

```bash markpact:ref deploy-oqlos-hw-api
#!/bin/bash
set -euo pipefail
mkdir -p /home/pi/.config/systemd/user /home/pi/maskservice/config /home/pi/maskservice/logs

_has_modbus_usb() { ls /dev/ttyACM* /dev/ttyUSB* /dev/serial/by-id/usb-1a86_* 2>/dev/null | head -1 | grep -q .; }
if ! _has_modbus_usb; then
  if [ "${PIHW_ALLOW_MISSING_HARDWARE:-1}" = "1" ]; then
    echo "WARN: brak Modbus USB — pomijam oqlos-hardware-api (PIHW_ALLOW_MISSING_HARDWARE=1)"
    systemctl --user stop oqlos-hardware-api.service 2>/dev/null || true
    exit 0
  fi
  echo "FAIL: brak Modbus USB — podłącz urządzenia lub ustaw PIHW_ALLOW_MISSING_HARDWARE=1" >&2
  exit 1
fi

# Install/refresh the oqlos venv.
cd /home/pi/oqlos/oqlos
if [ ! -x /home/pi/oqlos/venv/bin/oqlos-server ]; then
  python3 -m venv /home/pi/oqlos/venv
  /home/pi/oqlos/venv/bin/pip install -q -e .
  echo "PASS: utworzono /home/pi/oqlos/venv"
else
  echo "INFO: uzywam istniejacego /home/pi/oqlos/venv"
fi

# Base config from the hardware-node yaml (loopback motor URLs already applied).
cp /home/pi/maskservice/boardnet-config/oqlos-hw.yaml /home/pi/maskservice/config/oqlos-real.yaml
cp /home/pi/maskservice/boardnet-config/.env.hw /home/pi/maskservice/config/oql-mqtt.env 2>/dev/null || true

systemctl --user stop oqlos-hardware-api.service 2>/dev/null || true
sleep 2

# --- Autodetect Modbus serial ports (by-id differs per Pi) ---
IO_DEV=$(ls -1 /dev/serial/by-id/usb-1a86_USB_Single_Serial_*-if00 2>/dev/null | head -1 || true)
[ -n "${IO_DEV:-}" ] && [ -e "$IO_DEV" ] || { for _p in /dev/ttyACM*; do [ -e "$_p" ] && IO_DEV="$_p" && break; done; }
[ -n "${IO_DEV:-}" ] && [ -e "$IO_DEV" ] || IO_DEV=/dev/ttyACM0
ADC_DEV=$(ls -1 /dev/serial/by-id/usb-1a86_USB2.0-Serial-if00-port0 2>/dev/null | head -1 || true)
[ -n "${ADC_DEV:-}" ] && [ -e "$ADC_DEV" ] || { for _p in /dev/ttyUSB*; do [ -e "$_p" ] && ADC_DEV="$_p" && break; done; }
[ -n "${ADC_DEV:-}" ] && [ -e "$ADC_DEV" ] || ADC_DEV=/dev/ttyUSB0
IO_BAUD=9600

ADC_ENABLED=true
ADC_DEVICE_ID=2
DETECTED_ADC_DEVICE_ID=$(
  timeout 30 /home/pi/oqlos/venv/bin/python - "$ADC_DEV" << 'PY' 2>/dev/null || true
from pymodbus.client import ModbusSerialClient
import sys
port = sys.argv[1]
for device_id in (2, 1):
    cli = ModbusSerialClient(port=port, baudrate=9600, parity="N", stopbits=1, bytesize=8, timeout=0.35)
    try:
        if not cli.connect():
            continue
        resp = cli.read_input_registers(address=0, count=1, device_id=device_id)
        if resp is not None and not resp.isError():
            print(device_id); raise SystemExit(0)
    except Exception:
        continue
    finally:
        try: cli.close()
        except Exception: pass
print("none")
PY
)
case "$DETECTED_ADC_DEVICE_ID" in
  1|2) ADC_DEVICE_ID="$DETECTED_ADC_DEVICE_ID" ;;
  none) ADC_ENABLED=false ;;
esac
ADC_SERIAL_FOR_CONFIG="$ADC_DEV"
[ "$ADC_ENABLED" = false ] && ADC_SERIAL_FOR_CONFIG=/dev/serial/by-id/adc-not-present
echo "INFO: modbus-io=$IO_DEV@$IO_BAUD  modbus-adc=$ADC_SERIAL_FOR_CONFIG enabled=$ADC_ENABLED id=$ADC_DEVICE_ID"

CFG=/home/pi/maskservice/config/oqlos-real.yaml
python3 - "$CFG" "$IO_DEV" "$ADC_SERIAL_FOR_CONFIG" "$IO_BAUD" "$ADC_ENABLED" "$ADC_DEVICE_ID" << 'PY'
import re, sys
from pathlib import Path
path = Path(sys.argv[1])
io_dev, adc_dev, io_baud, adc_enabled, adc_device_id = sys.argv[2:7]
text = path.read_text(encoding="utf-8")
text = re.sub(r"(  modbus-io:\n(?:.*\n)*?      serial_port: )[^\n]+", rf"\1{io_dev}", text, count=1)
text = re.sub(r"(  modbus-io:\n(?:.*\n)*?      baudrate: )[0-9]+", rf"\g<1>{io_baud}", text, count=1)
text = re.sub(r"(  modbus-adc:\n(?:.*\n)*?      serial_port: )[^\n]+", rf"\1{adc_dev}", text, count=1)
text = re.sub(r"(  modbus-adc:\n(?:.*\n)*?      device_id: )[0-9]+", rf"\g<1>{adc_device_id}", text, count=1)
text = re.sub(r"(  modbus-adc:\n(?:.*\n)*?    enabled: )(true|false)", rf"\g<1>{adc_enabled}", text, count=1)
path.write_text(text, encoding="utf-8")
print(f"PASS: {path} (modbus-io={io_dev}@{io_baud}, modbus-adc={adc_dev}, enabled={adc_enabled}, id={adc_device_id})")
PY

# --- systemd unit: oqlos-server with the OQL-over-MQTT AGENT enabled ---
cat > /home/pi/.config/systemd/user/oqlos-hardware-api.service << EOF
[Unit]
Description=OqlOS hardware node + OQL-over-MQTT agent (boardnet)
After=network-online.target mosquitto.service pirtc-api.service dri0050-motor-api.service hw-tic249.service
Wants=mosquitto.service

[Service]
Type=simple
WorkingDirectory=/home/pi/oqlos/oqlos
EnvironmentFile=-/home/pi/maskservice/config/oql-mqtt.env
Environment=HARDWARE_MODE=real
Environment=OQLOS_HARDWARE_MODE=real
Environment=OQLOS_CONFIG_PATH=/home/pi/maskservice/config/oqlos-real.yaml
Environment=PYTHONPATH=/home/pi/maskservice/pimodbus
Environment=OQLOS_MODBUS_SERIAL_PORT=${IO_DEV}
Environment=OQLOS_MODBUS_BAUD=${IO_BAUD}
Environment=OQLOS_MODBUS_PARITY=N
Environment=OQLOS_MODBUS_DEVICE_ID=1
Environment=OQLOS_MODBUS_ADC_SERIAL_PORT=${ADC_SERIAL_FOR_CONFIG}
Environment=OQLOS_MODBUS_ADC_BAUD=9600
Environment=OQLOS_MODBUS_ADC_PARITY=N
Environment=OQLOS_MODBUS_ADC_DEVICE_ID=${ADC_DEVICE_ID}
Environment=OQLOS_MOTOR_URL=http://127.0.0.1:8203
Environment=OQLOS_LUNG_MOTOR_URL=http://127.0.0.1:8205
Environment=OQLOS_ENABLE_RTC=1
Environment=PIRTC_API_URL=http://127.0.0.1:8125
Environment=RTC_MOCK=false
Environment=OQLOS_OQL_TRANSPORT_ROLE=agent
Environment=OQLOS_OQL_NODE_ID=boardnet
Environment=OQLOS_OQL_TOPIC_PREFIX=oqlos/c2004
Environment=OQLOS_OQL_MQTT_HOST=127.0.0.1
Environment=OQLOS_OQL_MQTT_PORT=1883
ExecStartPre=/bin/bash -lc 'if /home/pi/maskservice/scripts/wait-hw-tic249-ready.sh; then exit 0; fi; [ "${PIHW_ALLOW_MISSING_HARDWARE:-1}" = "1" ] && exit 0; exit 1'
ExecStart=/home/pi/oqlos/venv/bin/oqlos-server --host 127.0.0.1 --port 8202
Restart=always
RestartSec=3
StandardOutput=append:/home/pi/maskservice/logs/oqlos-hardware-api.log
StandardError=append:/home/pi/maskservice/logs/oqlos-hardware-api.log

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now oqlos-hardware-api.service
sleep 2
if ! systemctl --user is-active oqlos-hardware-api.service >/dev/null 2>&1; then
  if [ "${PIHW_ALLOW_MISSING_HARDWARE:-1}" = "1" ]; then
    echo "WARN: oqlos-hardware-api nie wystartował — PIHW_ALLOW_MISSING_HARDWARE=1"
    exit 0
  fi
  systemctl --user status oqlos-hardware-api.service --no-pager || true
  exit 1
fi
echo "PASS: oqlos-hardware-api (agent) uruchomiony (HTTP :8202 loopback, agent na :1883)"
```

```bash markpact:ref assert-hw-node-healthy
#!/bin/bash
set -euo pipefail
# 1) mosquitto up
systemctl --user is-active mosquitto.service >/dev/null 2>&1 || { echo "FAIL: mosquitto nieaktywny"; exit 1; }

# 2) oqlos plugins compatible (local HTTP :8202)
ok=0; streak=0
for i in {1..45}; do
  io=$(curl -sf http://127.0.0.1:8202/api/v1/plugins/modbus-io/health 2>/dev/null || true)
  tic=$(curl -sf http://127.0.0.1:8202/api/v1/plugins/motor-tic249/health 2>/dev/null || true)
  if echo "$io" | grep -Eq '"compatible"[[:space:]]*:[[:space:]]*true' \
     && echo "$tic" | grep -Eq '"compatible"[[:space:]]*:[[:space:]]*true'; then
    streak=$((streak+1)); echo "INFO: modbus-io+tic OK (streak ${streak}/3, $i/45)"
    [ "$streak" -ge 3 ] && { ok=1; break; }
  else streak=0; fi
  sleep 2
done
if [ "$ok" != "1" ]; then
  if [ "${PIHW_ALLOW_MISSING_HARDWARE:-1}" = "1" ]; then
    echo "WARN: plugins nie compatible — PIHW_ALLOW_MISSING_HARDWARE=1"
  else
    echo "FAIL: oqlos plugins nie osiagnely compatible=true"; exit 1
  fi
fi

# 3) MQTT agent round-trip: publish a ping request, expect a response.
PW=$(grep -E '^OQLOS_OQL_MQTT_PASSWORD=' /home/pi/maskservice/config/oql-mqtt.env 2>/dev/null | head -1 | cut -d= -f2- || true)
CORR="assert-$(date +%s)"
REQ="{\"correlation_id\":\"$CORR\",\"oql\":\"\",\"kind\":\"ping\",\"reply_to\":\"oqlos/c2004/boardnet/oql/response/$CORR\"}"
mosquitto_sub -h 127.0.0.1 -p 1883 -u oqlos -P "$PW" \
  -t "oqlos/c2004/boardnet/oql/response/$CORR" -C 1 -W 8 > /tmp/oql_pong.json 2>/dev/null &
SUB=$!
sleep 1
mosquitto_pub -h 127.0.0.1 -p 1883 -u oqlos -P "$PW" -t "oqlos/c2004/boardnet/oql/request" -m "$REQ"
if wait "$SUB" && grep -q '"ok"' /tmp/oql_pong.json; then
  echo "PASS: OQL-over-MQTT agent odpowiedział na ping ($(cat /tmp/oql_pong.json))"
else
  echo "FAIL: brak odpowiedzi agenta OQL-over-MQTT na ping (sprawdź broker auth + rolę agent)"; exit 1
fi
```

```yaml markpact:config
name: "oqlos boardnet deploy"
description: "OqlOS hardware node + mosquitto na pi@boardnet.local — systemd --user, OQL-over-MQTT agent"
source:
  strategy: podman_quadlet
  host: pi@boardnet.local
  remote_dir: ~/oqlos
target:
  strategy: podman_quadlet
  host: pi@boardnet.local
  remote_dir: ~/oqlos
  verify_url: http://192.168.188.122:1883
```

```yaml markpact:steps
extra_steps:

  - id: mkdir_hw_remote
    action: inline_script
    description: "Utwórz katalogi na boardnet"
    command_ref: mkdir-hw-remote

  - id: enable_linger_groups
    action: inline_script
    description: "Linger + grupy urządzeń dla użytkownika pi"
    command_ref: enable-linger-groups

  - id: sync_oqlos_core
    action: rsync
    description: "Sync oqlos core na boardnet"
    src: /home/tom/github/oqlos/oqlos/
    dst: ~/oqlos/oqlos/
    excludes: [.git/, .venv/, venv/, __pycache__/, .pytest_cache/]

  - id: sync_pihw_config
    action: rsync
    description: "Sync konfiguracji węzła boardnet (mosquitto.conf, oqlos-hw.yaml, .env.hw)"
    src: /home/tom/github/oqlos/oqlos/redeploy/122/
    dst: ~/maskservice/boardnet-config/
    excludes: [.git/]

  - id: sync_pimodbus
    action: rsync
    description: "Sync pimodbus (adaptery Modbus)"
    src: /home/tom/github/maskservice/pimodbus/
    dst: ~/maskservice/pimodbus/
    excludes: [.git/, .venv/, venv/, __pycache__/, .pytest_cache/]

  - id: sync_rpi_motor_tic249
    action: rsync
    description: "Sync sterownika Pololu Tic T249"
    src: /home/tom/github/maskservice/rpi-motor-tic249/
    dst: ~/maskservice/rpi-motor-tic249/
    excludes: [.git/, .venv/, venv/, __pycache__/]

  - id: sync_rpi_motor_dri0050
    action: rsync
    description: "Sync sterownika DFRobot DRI0050"
    src: /home/tom/github/maskservice/rpi-motor-DRI0050/
    dst: ~/maskservice/rpi-motor-DRI0050/
    excludes: [.git/, .venv/, venv/, __pycache__/]

  - id: sync_pirtc
    action: rsync
    description: "Sync piRTC sidecar"
    src: /home/tom/github/maskservice/pirtc/
    dst: ~/maskservice/pirtc/
    excludes: [.git/, .venv/, venv/, __pycache__/]

  - id: install_mosquitto
    action: inline_script
    description: "Zainstaluj i uruchom broker mosquitto (systemd --user)"
    command_ref: install-mosquitto

  - id: deploy_pololu_udev
    action: inline_script
    description: "Reguły udev dla Pololu Tic"
    command_ref: deploy-pololu-udev

  - id: deploy_hw_tic249_service
    action: inline_script
    description: "Sidecar Pololu Tic T249 (:8205)"
    command_ref: deploy-hw-tic249-service
    timeout: 180

  - id: deploy_dri0050_motor_service
    action: inline_script
    description: "Sidecar DFRobot DRI0050 (:8203)"
    command_ref: deploy-dri0050-motor-service
    timeout: 180

  - id: deploy_pirtc_sidecar
    action: inline_script
    description: "Sidecar piRTC (:8125)"
    command_ref: deploy-pirtc-sidecar
    timeout: 120

  - id: deploy_oqlos_hw_api
    action: inline_script
    description: "OqlOS hardware API + agent OQL-over-MQTT (:8202 loopback)"
    command_ref: deploy-oqlos-hw-api
    timeout: 300

  - id: assert_hw_node_healthy
    action: inline_script
    description: "Asercja: mosquitto + plugins compatible + agent ping/pong"
    command_ref: assert-hw-node-healthy
    timeout: 180
```
