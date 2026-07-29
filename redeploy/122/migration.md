# OqlOS hardware node — BoardNet deploy (adres z profilu .env)

Deploys the OqlOS **hardware runtime**, the moved hardware UI, and an **MQTT broker** onto
a dedicated Raspberry Pi 3 (`${BOARDNET_SSH_USER}@${BOARDNET_IP}`). This Pi owns all
physical devices (Modbus IO/ADC, Pololu Tic T249, DFRobot DRI0050, RTC HAT) and runs the
OQL-over-MQTT **agent/controller** pair for local and remote OQL requests. It also exposes
the OqlOS hardware UI/API on LAN at `:8202`, so a human can open
`http://boardnet.local:8202/ui/status`, `/ui/motor-services`,
`/ui/scenario-files`, `/ui/func-editor`, and `/ui/hardware-coils` directly
(legacy paths without `/ui` redirect).

Aktualny stan BoardNet/DisplayNet i ostatniej diagnostyki hardware:
`redeploy/122/CURRENT_STATE.md`.

See `RUNBOOK.md` for the one-time bare-metal provisioning (OS, ssh keys, apt, linger) that
must happen **before** the first real `deploy-fleet.sh --only 122` run.

## Uruchomienie

```bash
# From the c2004 repository, after provisioning per RUNBOOK.md:
cp -n env.d/21-boardnet-redeploy.env.example env.d/21-boardnet-redeploy.env
chmod 600 env.d/21-boardnet-redeploy.env
scripts/redeploy/deploy-fleet.sh --only 122

# Allow the node to come up even if some USB devices are missing (bench mode):
PIHW_ALLOW_MISSING_HARDWARE=1 scripts/redeploy/deploy-fleet.sh --only 122

# Render and validate the plan without contacting BoardNet:
scripts/redeploy/deploy-fleet.sh --only 122 --plan-only

# Niezależna weryfikacja src↔Pi po deployu (bez pre-generowania manifestu):
scripts/verify-rpi-checksum.sh ${BOARDNET_SSH_USER}@${BOARDNET_IP}
```

Each step below is also a standalone bash script (the `markpact:ref` blocks), so the
RUNBOOK can run them manually over ssh if the automation needs adjusting.

## Uwagi operacyjne

- Broker runs **on this Pi** (mosquitto, systemd --user, :1883). If pi109 reboots or
  redeploys, the hardware + broker stay up together. OqlOS connects to `127.0.0.1:1883`.
- OqlOS hardware API/UI listens on `0.0.0.0:8202` for LAN access. This intentionally exposes
  hardware controls on the local network; do not publish this port outside the trusted LAN.
- Aktualna ścieżka GUI c2004/DisplayNet używa bezpośredniego HTTP:
  `OQLOS_API_URL=http://${BOARDNET_IP}:${BOARDNET_OQLOS_PORT}`. MQTT zostaje używany dla OQL-over-MQTT
  i lokalnego agenta/controllera na BoardNet.
- `PIHW_ALLOW_MISSING_HARDWARE` (default `1`) turns missing-device failures into warnings so
  the node still boots for bench testing.
- Modbus RTU serial framing stays **local** (oqlos-server ↔ /dev/tty* on this Pi). Only OQL
  request/response crosses the LAN — latency-tolerant.
- USB `by-id` strings differ per Pi; `deploy-oqlos-hw-api` autodetects and rewrites the
  Modbus ports in `oqlos-real.yaml`. Never hardcode-trust the placeholders in `oqlos-hw.yaml`.
- Secrets: create `mosquitto.passwd` and set `OQLOS_OQL_MQTT_PASSWORD` in
  `~/maskservice/config/oql-mqtt.env` on the Pi (never commit them).
- Integralność: `rsync` porównuje rozmiar+mtime (nie wykrywa cichej korupcji treści). Krok
  `assert_oqlos_checksum` robi `sha256sum -c` wdrożonego pakietu względem manifestu
  `oqlos/_CHECKSUMS.sha256` (wygenerowanego na źródle przez `scripts/gen-checksums.sh` i
  dowiezionego przez `sync_oqlos_core`). Brak manifestu = FAIL z instrukcją. Manifest jest
  artefaktem deployu — w `.gitignore`, regeneruj przed każdym `redeploy run`.
- Historyczny stan z 2026-07-07: BoardNet odpowiadał na `:8202` (`mode=real`, wersja firmware w
  `/health`). HTTP HUI katalog (`/api/v1/hardware/hui/actions`) zawiera 7 hold +
  AL (`reverse_on_limit`). Bench może być **degraded**: `modbus-io` timeout RS485
  → `hold/*/start` i `al/stop` zwracają `ok=false` mimo poprawnego mapowania
  kluczy (np. `lp-pwm-minus10` → `valve-6` + pump 100%). UI SPA udostępnia
  `/ui/scenario-files`; konfiguracja urządzeń ma jeden kontrakt
  `hardware-configuration-v1`, a legacy MAP editor zwraca 404.
  Szczegóły: `redeploy/122/CURRENT_STATE.md`, `docs/boardnet-navigation.md`.

## Scripts

```bash markpact:ref mkdir-hw-remote
#!/bin/bash
set -euo pipefail
mkdir -p /home/${BOARDNET_SSH_USER}/oqlos/oqlos \
         /home/${BOARDNET_SSH_USER}/oqlos/oql-scenario \
         /home/${BOARDNET_SSH_USER}/maskservice/config \
         /home/${BOARDNET_SSH_USER}/maskservice/logs \
         /home/${BOARDNET_SSH_USER}/maskservice/mosquitto \
         /home/${BOARDNET_SSH_USER}/maskservice/scripts \
         /home/${BOARDNET_SSH_USER}/.config/systemd/user
echo "PASS: katalogi boardnet utworzone"
```

```bash markpact:ref enable-linger-groups
#!/bin/bash
set -euo pipefail
sudo loginctl enable-linger ${BOARDNET_SSH_USER} 2>/dev/null || true
sudo usermod -aG dialout,plugdev,i2c,gpio ${BOARDNET_SSH_USER} 2>/dev/null || true
sudo timedatectl set-timezone Europe/Warsaw 2>/dev/null || true
if command -v raspi-config >/dev/null 2>&1; then
  sudo raspi-config nonint do_i2c 0 >/dev/null 2>&1 || true
fi
CFG=/boot/firmware/config.txt
[ -f "$CFG" ] || CFG=/boot/config.txt
if [ -f "$CFG" ] && ! grep -Eq '^[[:space:]]*dtparam=i2c_arm=on([[:space:]]|$)' "$CFG"; then
  printf '\n# OqlOS BoardNet piRTC / Waveshare DS3231\n%s\n' 'dtparam=i2c_arm=on' | sudo tee -a "$CFG" >/dev/null
fi
echo "PASS: linger + grupy (dialout,plugdev,i2c,gpio), timezone Europe/Warsaw; I2C wlaczone w config.txt"
```

```bash markpact:ref install-mosquitto
#!/bin/bash
set -euo pipefail
mkdir -p /home/${BOARDNET_SSH_USER}/maskservice/config /home/${BOARDNET_SSH_USER}/maskservice/mosquitto /home/${BOARDNET_SSH_USER}/maskservice/logs
if ! command -v mosquitto >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y git python3-venv mosquitto mosquitto-clients
fi
# Disable the system-wide mosquitto; we run it rootless as systemd --user.
sudo systemctl disable --now mosquitto 2>/dev/null || true

cp /home/${BOARDNET_SSH_USER}/maskservice/boardnet-config/mosquitto.conf /home/${BOARDNET_SSH_USER}/maskservice/config/mosquitto.conf

if [ ! -f /home/${BOARDNET_SSH_USER}/maskservice/config/mosquitto.passwd ]; then
  PW="${OQLOS_OQL_MQTT_PASSWORD:-}"
  if [ -z "$PW" ] && [ -f /home/${BOARDNET_SSH_USER}/maskservice/config/oql-mqtt.env ]; then
    PW=$(grep -E '^OQLOS_OQL_MQTT_PASSWORD=' /home/${BOARDNET_SSH_USER}/maskservice/config/oql-mqtt.env | head -1 | cut -d= -f2-)
  fi
  if [ -z "$PW" ] || [ "$PW" = "CHANGE_ME_ON_PI" ]; then
    echo "FAIL: ustaw OQLOS_OQL_MQTT_PASSWORD w ~/maskservice/config/oql-mqtt.env przed deployem brokera" >&2
    exit 1
  fi
  mosquitto_passwd -b -c /home/${BOARDNET_SSH_USER}/maskservice/config/mosquitto.passwd oqlos "$PW"
  echo "INFO: utworzono mosquitto.passwd dla uzytkownika 'oqlos'"
fi

cat > /home/${BOARDNET_SSH_USER}/.config/systemd/user/mosquitto.service << 'UNIT'
[Unit]
Description=Mosquitto MQTT broker (OqlOS hardware node)
After=network-online.target

[Service]
Type=simple
ExecStart=/usr/sbin/mosquitto -c /home/${BOARDNET_SSH_USER}/maskservice/config/mosquitto.conf
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
mkdir -p /home/${BOARDNET_SSH_USER}/.config/systemd/user /home/${BOARDNET_SSH_USER}/maskservice/logs /home/${BOARDNET_SSH_USER}/maskservice/scripts
cd /home/${BOARDNET_SSH_USER}/maskservice/rpi-motor-tic249
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
if ! .venv/bin/python -c 'import flask, usb, ticlib, dotenv' >/dev/null 2>&1; then
  .venv/bin/pip install -q ticlib pyusb flask python-dotenv
fi
sed -i '/^USB_SERIAL_NUMBER=/d' .env 2>/dev/null || true

cat > /home/${BOARDNET_SSH_USER}/maskservice/scripts/wait-hw-tic249-ready.sh << 'SCRIPT'
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
chmod +x /home/${BOARDNET_SSH_USER}/maskservice/scripts/wait-hw-tic249-ready.sh

cat > /home/${BOARDNET_SSH_USER}/maskservice/scripts/tic249-deenergize-best-effort.sh << 'SCRIPT'
#!/bin/bash
set +e
for url in http://127.0.0.1:8205 http://127.0.0.1:5000; do
  curl -fsS --max-time 2 -X POST "$url/api/stop" >/dev/null 2>&1 || true
  curl -fsS --max-time 2 -H 'Content-Type: application/json' -d '{"enable":false}' "$url/api/energize" >/dev/null 2>&1 || true
done
if command -v ticcmd >/dev/null 2>&1; then
  ticcmd --deenergize >/dev/null 2>&1 || true
fi
if [ -x /home/${BOARDNET_SSH_USER}/maskservice/rpi-motor-tic249/pololu-tic-1.8.1-linux-rpi/ticcmd ]; then
  /home/${BOARDNET_SSH_USER}/maskservice/rpi-motor-tic249/pololu-tic-1.8.1-linux-rpi/ticcmd --deenergize >/dev/null 2>&1 || true
fi
exit 0
SCRIPT
chmod +x /home/${BOARDNET_SSH_USER}/maskservice/scripts/tic249-deenergize-best-effort.sh

cat > /home/${BOARDNET_SSH_USER}/.config/systemd/user/hw-tic249.service << 'UNIT'
[Unit]
Description=Maskservice Pololu Tic T249 hardware adapter
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/${BOARDNET_SSH_USER}/maskservice/rpi-motor-tic249
Environment=PATH=/home/${BOARDNET_SSH_USER}/maskservice/rpi-motor-tic249/.venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=FLASK_HOST=0.0.0.0
Environment=FLASK_PORT=8205
Environment=USB_PRODUCT_ID=0x00c9
Environment=LOG_LEVEL=INFO
ExecStartPre=/home/${BOARDNET_SSH_USER}/maskservice/scripts/tic249-deenergize-best-effort.sh
ExecStart=/home/${BOARDNET_SSH_USER}/maskservice/rpi-motor-tic249/.venv/bin/python web_panel.py
# The web panel starts disconnected even when the USB device is present. Reuse
# the deploy readiness helper after every service start. A missing bench device
# must not create a restart loop, so systemd ignores only the helper's failure.
ExecStartPost=-/home/${BOARDNET_SSH_USER}/maskservice/scripts/wait-hw-tic249-ready.sh
ExecStop=/home/${BOARDNET_SSH_USER}/maskservice/scripts/tic249-deenergize-best-effort.sh
ExecStopPost=/home/${BOARDNET_SSH_USER}/maskservice/scripts/tic249-deenergize-best-effort.sh
Restart=always
RestartSec=3
KillSignal=SIGINT
TimeoutStopSec=20
StandardOutput=append:/home/${BOARDNET_SSH_USER}/maskservice/logs/hw-tic249.log
StandardError=append:/home/${BOARDNET_SSH_USER}/maskservice/logs/hw-tic249.log

[Install]
WantedBy=default.target
UNIT

systemctl --user daemon-reload
systemctl --user enable hw-tic249.service
systemctl --user restart hw-tic249.service
sleep 3
systemctl --user is-active hw-tic249.service
if /home/${BOARDNET_SSH_USER}/maskservice/scripts/wait-hw-tic249-ready.sh; then
  echo "PASS: hw-tic249 aktywny i widzi Pololu Tic"
  /home/${BOARDNET_SSH_USER}/maskservice/scripts/tic249-deenergize-best-effort.sh
  if curl -sf http://localhost:8205/api/status | grep -Eq '"energized"[[:space:]]*:[[:space:]]*false'; then
    echo "PASS: hw-tic249 po starcie jest de-energized"
  elif [ "${PIHW_ALLOW_MISSING_HARDWARE:-1}" = "1" ]; then
    echo "WARN: hw-tic249 nie potwierdzil energized=false — PIHW_ALLOW_MISSING_HARDWARE=1"
  else
    echo "FAIL: hw-tic249 nie potwierdzil energized=false po starcie" >&2
    exit 1
  fi
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
mkdir -p /home/${BOARDNET_SSH_USER}/.config/systemd/user /home/${BOARDNET_SSH_USER}/maskservice/logs /home/${BOARDNET_SSH_USER}/maskservice/scripts
cat > /tmp/99-dri0050-usb-serial.rules << 'RULES'
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", MODE="0666", GROUP="dialout"
SUBSYSTEM=="usb", ATTR{idVendor}=="1a86", MODE="0666", GROUP="dialout"
RULES
sudo install -m 0644 /tmp/99-dri0050-usb-serial.rules /etc/udev/rules.d/99-dri0050-usb-serial.rules
sudo udevadm control --reload-rules || true
sudo udevadm trigger -s tty || true
sudo udevadm trigger -s usb || true

cd /home/${BOARDNET_SSH_USER}/maskservice/rpi-motor-DRI0050
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
.venv/bin/pip install -q fastapi uvicorn
.venv/bin/pip install -q -e .

cat > /home/${BOARDNET_SSH_USER}/maskservice/scripts/start-dri0050-motor-api.sh << 'SH'
#!/bin/bash
set -euo pipefail
cd /home/${BOARDNET_SSH_USER}/maskservice/rpi-motor-DRI0050
DRI_PORT=""
for _ in $(seq 1 30); do
  mapfile -t DRI_CANDIDATES < <(
    for _p in /dev/ttyUSB* /dev/ttyACM*; do
      [ -e "$_p" ] || continue
      _props=$(udevadm info --query=property --name="$_p" 2>/dev/null || true)
      grep -q '^ID_VENDOR_ID=1a86$' <<<"$_props" || continue
      grep -Eq '^ID_MODEL=(USB2\.0-Serial|USB2\.0_Serial)$' <<<"$_props" || continue
      printf '%s\n' "$_p"
    done
  )
  if [ "${#DRI_CANDIDATES[@]}" -gt 1 ]; then
    echo "ERROR: niejednoznaczna tożsamość DRI0050: ${DRI_CANDIDATES[*]}" >&2
    echo "ERROR: skonfiguruj unikalny adapter/serial; nie wybieram pierwszego ttyUSB" >&2
    exit 1
  fi
  if [ "${#DRI_CANDIDATES[@]}" -eq 1 ]; then
    DRI_REAL=$(readlink -f "${DRI_CANDIDATES[0]}")
    for _link in /dev/serial/by-id/usb-1a86_USB2.0-Serial*; do
      [ -e "$_link" ] || continue
      if [ "$(readlink -f "$_link")" = "$DRI_REAL" ]; then
        DRI_PORT="$_link"
        break
      fi
    done
    DRI_PORT="${DRI_PORT:-${DRI_CANDIDATES[0]}}"
  fi
  [ -n "${DRI_PORT:-}" ] && [ -e "$DRI_PORT" ] && break
  sleep 1
done
if [ -z "${DRI_PORT:-}" ] || [ ! -e "$DRI_PORT" ]; then
  echo "ERROR: nie znaleziono jednoznacznego adaptera DRI0050 po 30 s" >&2
  exit 1
fi
echo "INFO: DRI0050 identity resolved to $DRI_PORT -> $(readlink -f "$DRI_PORT")"
export DRI0050_PORT="$DRI_PORT"
export DRI0050_FREQ="${DRI0050_FREQ:-1000}"
exec /home/${BOARDNET_SSH_USER}/maskservice/rpi-motor-DRI0050/.venv/bin/python web_api.py
SH
chmod +x /home/${BOARDNET_SSH_USER}/maskservice/scripts/start-dri0050-motor-api.sh

cat > /home/${BOARDNET_SSH_USER}/.config/systemd/user/dri0050-motor-api.service << 'UNIT'
[Unit]
Description=DFRobot DRI0050 pump motor API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/${BOARDNET_SSH_USER}/maskservice/rpi-motor-DRI0050
Environment=PATH=/home/${BOARDNET_SSH_USER}/maskservice/rpi-motor-DRI0050/.venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=API_PORT=8203
Environment=DRI0050_FREQ=1000
ExecStart=/home/${BOARDNET_SSH_USER}/maskservice/scripts/start-dri0050-motor-api.sh
Restart=always
RestartSec=3
StandardOutput=append:/home/${BOARDNET_SSH_USER}/maskservice/logs/dri0050-motor-api.log
StandardError=append:/home/${BOARDNET_SSH_USER}/maskservice/logs/dri0050-motor-api.log

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
mkdir -p /home/${BOARDNET_SSH_USER}/.config/systemd/user /home/${BOARDNET_SSH_USER}/maskservice/logs
PIRTC_DIR=/home/${BOARDNET_SSH_USER}/maskservice/pirtc
[ -f "$PIRTC_DIR/pyproject.toml" ] || { echo "FAIL: brak $PIRTC_DIR — uruchom sync_pirtc"; exit 1; }
[ -d "$PIRTC_DIR/RTC/python/lib/waveshare_DS3231" ] || { echo "FAIL: brak sterownika $PIRTC_DIR/RTC/python/lib/waveshare_DS3231 — uruchom sync_pirtc_rtc_lib"; exit 1; }
if ! command -v i2cdetect >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y i2c-tools
fi
if ! compgen -G '/dev/i2c-*' >/dev/null; then
  if command -v raspi-config >/dev/null 2>&1; then
    sudo raspi-config nonint do_i2c 0 >/dev/null 2>&1 || true
  fi
  CFG=/boot/firmware/config.txt
  [ -f "$CFG" ] || CFG=/boot/config.txt
  if [ -f "$CFG" ] && ! grep -Eq '^[[:space:]]*dtparam=i2c_arm=on([[:space:]]|$)' "$CFG"; then
    printf '\n# OqlOS BoardNet piRTC / Waveshare DS3231\n%s\n' 'dtparam=i2c_arm=on' | sudo tee -a "$CFG" >/dev/null
  fi
  echo "WARN: /dev/i2c-* nie istnieje — I2C wlaczone w config.txt, wymagany reboot BoardNet"
fi
cd "$PIRTC_DIR"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -e .

cat > /home/${BOARDNET_SSH_USER}/.config/systemd/user/pirtc-api.service << 'UNIT'
[Unit]
Description=piRTC sidecar (Waveshare RTC WatchDog HAT) on :8125
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/${BOARDNET_SSH_USER}/maskservice/pirtc
Environment=PATH=/home/${BOARDNET_SSH_USER}/maskservice/pirtc/.venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=/home/${BOARDNET_SSH_USER}/maskservice/pirtc:/home/${BOARDNET_SSH_USER}/maskservice/pirtc/RTC/python/lib
Environment=API_HOST=0.0.0.0
Environment=API_PORT=8125
Environment=RTC_MOCK=false
Environment=WATCHDOG_MOCK=false
Environment=RTC_I2C_ADDRESS=0x68
Environment=RTC_I2C_BUS=1
Environment=WATCHDOG_I2C_ADDRESS=0x67
Environment=WATCHDOG_GPIO_PIN=4
Environment=LOG_LEVEL=INFO
ExecStart=/home/${BOARDNET_SSH_USER}/maskservice/pirtc/.venv/bin/pirtc-server
Restart=always
RestartSec=3
StandardOutput=append:/home/${BOARDNET_SSH_USER}/maskservice/logs/pirtc-api.log
StandardError=append:/home/${BOARDNET_SSH_USER}/maskservice/logs/pirtc-api.log

[Install]
WantedBy=default.target
UNIT

systemctl --user daemon-reload
systemctl --user enable pirtc-api.service
systemctl --user restart pirtc-api.service
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
if python3 - "$STATUS" <<'PY'
import json
import sys
try:
    data = json.loads(sys.argv[1])
except Exception:
    raise SystemExit(1)
rtc = data.get("rtc", {}) if isinstance(data, dict) else {}
raise SystemExit(0 if rtc.get("available") is True and rtc.get("mock") is False else 1)
PY
then
  if curl -sf -X POST http://127.0.0.1:8125/api/rtc/sync-from-system >/dev/null 2>&1; then
    STATUS=$(curl -sf http://127.0.0.1:8125/api/status 2>/dev/null || true)
  else
    echo "WARN: piRTC dostępny, ale sync-from-system nie powiódł się"
  fi
  echo "PASS: piRTC sidecar :8125 — RTC HAT dostępny (nie mock)"
elif [ "${PIHW_ALLOW_MISSING_HARDWARE:-1}" = "1" ]; then
  echo "WARN: piRTC bez działającego RTC — PIHW_ALLOW_MISSING_HARDWARE=1"
  exit 0
else
  echo "FAIL: piRTC :8125 bez działającego RTC" >&2
  exit 1
fi
```

```bash markpact:ref deploy-usb-adc-stack
#!/bin/bash
set -euo pipefail
ROOT=/home/${BOARDNET_SSH_USER}/oqlos-adapters
MCP_DIR="$ROOT/usb-adc-mcp2221"
DFR_DIR="$ROOT/usb-adc-dfr1184"
mkdir -p "$ROOT" /home/${BOARDNET_SSH_USER}/.config/systemd/user
[ -f "$MCP_DIR/pyproject.toml" ] || { echo "FAIL: brak $MCP_DIR — uruchom sync_usb_adc_mcp2221"; exit 1; }
[ -f "$DFR_DIR/pyproject.toml" ] || { echo "FAIL: brak $DFR_DIR — uruchom sync_usb_adc_dfr1184"; exit 1; }

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  python3 -m venv "$ROOT/.venv"
fi
"$ROOT/.venv/bin/pip" install -q --upgrade pip
"$ROOT/.venv/bin/pip" install -q -e "$MCP_DIR" -e "$DFR_DIR[api]"
install -m 0644 "$DFR_DIR/deploy/systemd/usb-adc-stack.service" \
  /home/${BOARDNET_SSH_USER}/.config/systemd/user/usb-adc-stack.service

systemctl --user daemon-reload
systemctl --user enable usb-adc-stack.service
systemctl --user restart usb-adc-stack.service
for attempt in $(seq 1 30); do
  if curl -sf --max-time 3 http://127.0.0.1:8214/health >/dev/null; then
    echo "PASS: usb-adc-stack aktywny na loopback :8214 (próba $attempt/30)"
    exit 0
  fi
  if ! systemctl --user is-active usb-adc-stack.service >/dev/null 2>&1; then
    systemctl --user status usb-adc-stack.service --no-pager || true
    exit 1
  fi
  sleep 1
done
echo "FAIL: usb-adc-stack nie odpowiada na /health po 30 próbach" >&2
systemctl --user status usb-adc-stack.service --no-pager || true
exit 1
```

```bash markpact:ref deploy-oqlos-hw-api
#!/bin/bash
set -euo pipefail
mkdir -p /home/${BOARDNET_SSH_USER}/.config/systemd/user /home/${BOARDNET_SSH_USER}/maskservice/config /home/${BOARDNET_SSH_USER}/maskservice/logs

_has_modbus_usb() {
  compgen -G '/dev/ttyACM*' >/dev/null \
    || compgen -G '/dev/ttyUSB*' >/dev/null \
    || compgen -G '/dev/serial/by-id/usb-1a86_*' >/dev/null
}
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
cd /home/${BOARDNET_SSH_USER}/oqlos/oqlos
_new_venv=0
if [ ! -x /home/${BOARDNET_SSH_USER}/oqlos/venv/bin/oqlos-server ]; then
  python3 -m venv /home/${BOARDNET_SSH_USER}/oqlos/venv
  /home/${BOARDNET_SSH_USER}/oqlos/venv/bin/pip install -q --upgrade pip
  _new_venv=1
  echo "PASS: utworzono /home/${BOARDNET_SSH_USER}/oqlos/venv"
else
  echo "INFO: odswiezam istniejace /home/${BOARDNET_SSH_USER}/oqlos/venv"
fi
# Install namespace sub-packages first (--no-deps) so pip's resolver sees them
# in the environment when resolving the main package's pinned dependencies.
# pip na SD potrafi paść przejściowo na file:// (I/O w trakcie deployu) —
# retry 3x zamiast wywalać cały deploy.
_pip_retry() {
  local i
  for i in 1 2 3; do
    /home/${BOARDNET_SSH_USER}/oqlos/venv/bin/pip install -q "$@" && return 0
    echo "WARN: pip install $* — próba $i/3 nieudana, retry za 5 s" >&2
    sleep 5
  done
  return 1
}
# Routine fleet updates must not need PyPI/piwheels. Editable local packages
# use the already-provisioned runtime dependencies and disable PEP 517 build
# isolation (which otherwise downloads setuptools even for a local source).
_pip_retry --no-build-isolation --no-deps -e packages/oqlos-models -e packages/oqlos-core
if [ "$_new_venv" = "1" ]; then
  _pip_retry --no-build-isolation -e .
else
  _pip_retry --no-build-isolation --no-deps -e .
fi
/home/${BOARDNET_SSH_USER}/oqlos/venv/bin/python - <<'PY'
import oqlos.api.main
PY
echo "PASS: oqlos editable install OK"
if [ ! -f /home/${BOARDNET_SSH_USER}/oqlos/oqlos/frontend/dist/index.html ]; then
  echo "FAIL: brak /home/${BOARDNET_SSH_USER}/oqlos/oqlos/frontend/dist/index.html — zbuduj frontend i uruchom sync_oqlos_frontend_dist" >&2
  exit 1
fi
# The hardware REST contract is bundled in OqlOS as oqlos.hardware.client.
# Only the external Modbus driver layer remains optional/editable on the Pi.
[ -f /home/${BOARDNET_SSH_USER}/maskservice/pimodbus/pyproject.toml ] && \
  /home/${BOARDNET_SSH_USER}/oqlos/venv/bin/pip install -q --no-build-isolation --no-deps -e /home/${BOARDNET_SSH_USER}/maskservice/pimodbus && \
  echo "PASS: pimodbus zainstalowany" || echo "INFO: pimodbus przez PYTHONPATH"

# Base config from the hardware-node yaml (loopback motor URLs already applied).
cp /home/${BOARDNET_SSH_USER}/maskservice/boardnet-config/oqlos-hw.yaml /home/${BOARDNET_SSH_USER}/maskservice/config/oqlos-real.yaml
ENVF=/home/${BOARDNET_SSH_USER}/maskservice/config/oql-mqtt.env
if [ ! -f "$ENVF" ]; then
  cp /home/${BOARDNET_SSH_USER}/maskservice/boardnet-config/.env.hw "$ENVF"
fi
PW=$(grep -E '^OQLOS_OQL_MQTT_PASSWORD=' "$ENVF" 2>/dev/null | head -1 | cut -d= -f2- || true)
if [ -z "$PW" ] || [ "$PW" = "CHANGE_ME_ON_PI" ]; then
  echo "FAIL: ustaw prawdziwe OQLOS_OQL_MQTT_PASSWORD w $ENVF; deploy nie nadpisuje sekretow" >&2
  exit 1
fi
if grep -qE '^OQLOS_OQL_TRANSPORT_ROLE=' "$ENVF"; then
  sed -i 's/^OQLOS_OQL_TRANSPORT_ROLE=.*/OQLOS_OQL_TRANSPORT_ROLE=both/' "$ENVF"
else
  printf 'OQLOS_OQL_TRANSPORT_ROLE=both\n' >> "$ENVF"
fi

systemctl --user stop oqlos-hardware-api.service 2>/dev/null || true
sleep 2

# --- Autodetect the remaining Modbus valve controller (read-only probe) ---
# Analog inputs no longer use Modbus: MCP2221A (USB) provides AI01 and DFR1184
# (Raspberry Pi UART) provides AI02/AI03 through usb-adc-stack. Exclude both the
# MCP2221 CDC interface and the CH340 DRI0050 pump adapter before probing, so a
# generic serial interface can never be misclassified as a Modbus module.
MB_DETECT=$(timeout 120 /home/${BOARDNET_SSH_USER}/oqlos/venv/bin/python - << 'PY' 2>/dev/null || true
import glob
import os

from pymodbus.client import ModbusSerialClient


def by_id_names(real: str) -> list[str]:
    return [
        os.path.basename(link)
        for link in glob.glob("/dev/serial/by-id/*")
        if os.path.realpath(link) == real
    ]


def reserved_for_non_modbus(real: str) -> bool:
    names = by_id_names(real)
    return any(
        name.startswith("usb-1a86_USB2.0-Serial") or "MCP2221" in name
        for name in names
    )


candidates: list[str] = []
seen = set()
# Stable by-id names are authoritative. The C2004 IO adapter is the CH343
# ``USB_Single_Serial`` device; ttyACM belongs to MCP2221 and ttyUSB numbering
# changes whenever USB devices are reconnected.
links = sorted(glob.glob("/dev/serial/by-id/*"))
if not links:
    links = sorted(glob.glob("/dev/serial/by-path/platform-*"))
if not links:
    links = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
expected_io = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5958006895-if00"
links.sort(key=lambda link: (link != expected_io, link))
for link in links:
    real = os.path.realpath(link)
    if real in seen:
        continue
    seen.add(real)
    if reserved_for_non_modbus(real):
        continue
    candidates.append(link)

matches = []
for port in candidates:
    cli = ModbusSerialClient(
        port=port,
        baudrate=4800,
        parity="N",
        stopbits=1,
        bytesize=8,
        timeout=0.35,
        retries=0,
    )
    try:
        if not cli.connect():
            continue
        # Machine contract is fixed: Waveshare IO must be slave 1.  Scanning
        # and silently adopting another address would hide a wiring/config fault.
        resp = cli.read_coils(address=0, count=1, device_id=1)
        if resp is not None and not resp.isError():
            matches.append(port)
    except Exception:
        pass
    finally:
        try:
            cli.close()
        except Exception:
            pass
if len(matches) == 1:
    print(f"MB_IO_DEV='{matches[0]}' MB_IO_AMBIGUOUS='' ")
elif len(matches) > 1:
    print(f"MB_IO_DEV='' MB_IO_AMBIGUOUS='{','.join(matches)}'")
else:
    print("MB_IO_DEV='' MB_IO_AMBIGUOUS=''")
PY
)
eval "${MB_DETECT:-}"
EXPECTED_IO_DEV=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5958006895-if00
IO_BAUD=4800
IO_ENABLED=true
IO_DEV="${MB_IO_DEV:-$EXPECTED_IO_DEV}"
IO_DEVICE_ID=1
if [ -n "${MB_IO_AMBIGUOUS:-}" ]; then
  echo "ERROR: więcej niż jeden adapter odpowiada jako Waveshare slave 1: $MB_IO_AMBIGUOUS" >&2
  exit 1
fi
if [ -n "${MB_IO_DEV:-}" ] && [ "$MB_IO_DEV" != "$EXPECTED_IO_DEV" ]; then
  echo "ERROR: slave 1 odpowiedział na niezatwierdzonym adapterze $MB_IO_DEV" >&2
  echo "ERROR: oczekiwany adapter maszyny to $EXPECTED_IO_DEV; wymagana jawna zmiana konfiguracji" >&2
  exit 1
fi
if [ -z "${MB_IO_DEV:-}" ]; then
  echo "WARN: Waveshare slave 1 nie odpowiedział podczas deployu; zachowuję stabilną tożsamość $EXPECTED_IO_DEV" >&2
  echo "WARN: preflight przy każdym starcie nie dopuści OqlOS do pracy, dopóki właściwy sprzęt nie odpowie" >&2
fi
# Legacy Modbus ADC is intentionally disabled. usb-adc-stack owns AI01..AI03.
ADC_ENABLED=false
ADC_SERIAL_FOR_CONFIG=/dev/serial/by-id/adc-not-present
ADC_DEVICE_ID=2
DRI_ENABLED=false
if curl -sf --max-time 3 http://127.0.0.1:8203/api/status >/dev/null 2>&1; then
  DRI_ENABLED=true
fi
echo "INFO: modbus-io=$IO_DEV enabled=$IO_ENABLED @$IO_BAUD id=$IO_DEVICE_ID  modbus-adc=$ADC_SERIAL_FOR_CONFIG enabled=$ADC_ENABLED id=$ADC_DEVICE_ID  motor-dri0050=$DRI_ENABLED"

CFG=/home/${BOARDNET_SSH_USER}/maskservice/config/oqlos-real.yaml
python3 - "$CFG" "$IO_DEV" "$ADC_SERIAL_FOR_CONFIG" "$IO_BAUD" "$IO_ENABLED" "$IO_DEVICE_ID" "$ADC_ENABLED" "$ADC_DEVICE_ID" "$DRI_ENABLED" << 'PY'
import re, sys
from pathlib import Path
path = Path(sys.argv[1])
io_dev, adc_dev, io_baud, io_enabled, io_device_id, adc_enabled, adc_device_id, dri_enabled = sys.argv[2:10]
text = path.read_text(encoding="utf-8")
text = re.sub(r"(  motor-dri0050:\n(?:.*\n)*?    enabled: )(true|false)", rf"\g<1>{dri_enabled}", text, count=1)
text = re.sub(r"(  modbus-io:\n(?:.*\n)*?    enabled: )(true|false)", rf"\g<1>{io_enabled}", text, count=1)
text = re.sub(r"(  modbus-io:\n(?:.*\n)*?      serial_port: )[^\n]+", rf"\1{io_dev}", text, count=1)
text = re.sub(r"(  modbus-io:\n(?:.*\n)*?      baudrate: )[0-9]+", rf"\g<1>{io_baud}", text, count=1)
text = re.sub(r"(  modbus-io:\n(?:.*\n)*?      device_id: )[0-9]+", rf"\g<1>{io_device_id}", text, count=1)
text = re.sub(r"(  modbus-adc:\n(?:.*\n)*?      serial_port: )[^\n]+", rf"\1{adc_dev}", text, count=1)
text = re.sub(r"(  modbus-adc:\n(?:.*\n)*?      device_id: )[0-9]+", rf"\g<1>{adc_device_id}", text, count=1)
text = re.sub(r"(  modbus-adc:\n(?:.*\n)*?    enabled: )(true|false)", rf"\g<1>{adc_enabled}", text, count=1)
path.write_text(text, encoding="utf-8")
print(f"PASS: {path} (motor-dri0050={dri_enabled}, modbus-io={io_dev}@{io_baud} enabled={io_enabled}, id={io_device_id}, modbus-adc={adc_dev} enabled={adc_enabled}, id={adc_device_id})")
PY

# Read-only boot gate.  It verifies USB identity and the exact machine RTU
# contract on every service start; it never writes a coil/register.
# Older deployments created this helper as root.  Replace the inode first so
# the unprivileged deploy user can install the canonical version idempotently.
rm -f /home/${BOARDNET_SSH_USER}/maskservice/scripts/verify-boardnet-modbus.sh
cat > /home/${BOARDNET_SSH_USER}/maskservice/scripts/verify-boardnet-modbus.sh << 'SH'
#!/bin/bash
set -euo pipefail
PORT="${OQLOS_MODBUS_SERIAL_PORT:?missing OQLOS_MODBUS_SERIAL_PORT}"
BAUD="${OQLOS_MODBUS_BAUD:-4800}"
PARITY="${OQLOS_MODBUS_PARITY:-N}"
DEVICE_ID="${OQLOS_MODBUS_DEVICE_ID:-1}"
EXPECTED_SERIAL="${OQLOS_MODBUS_EXPECTED_SERIAL:-5958006895}"

if [ "$BAUD" != "4800" ] || [ "$PARITY" != "N" ] || [ "$DEVICE_ID" != "1" ]; then
  echo "ERROR: invalid BoardNet Modbus contract: $PORT@$BAUD 8${PARITY}1 slave=$DEVICE_ID" >&2
  exit 1
fi
if [ ! -e "$PORT" ]; then
  echo "ERROR: expected Modbus adapter is missing: $PORT" >&2
  exit 1
fi
PROPS=$(udevadm info --query=property --name="$(readlink -f "$PORT")" 2>/dev/null || true)
if ! grep -q "^ID_SERIAL_SHORT=${EXPECTED_SERIAL}$" <<<"$PROPS"; then
  echo "ERROR: $PORT is not the expected CH343 serial $EXPECTED_SERIAL" >&2
  exit 1
fi

/home/${BOARDNET_SSH_USER}/oqlos/venv/bin/python - "$PORT" "$BAUD" "$PARITY" "$DEVICE_ID" << 'PY'
import sys
from pymodbus.client import ModbusSerialClient

port, baud, parity, device_id = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4])
client = ModbusSerialClient(
    port=port,
    baudrate=baud,
    parity=parity,
    stopbits=1,
    bytesize=8,
    timeout=0.8,
    retries=0,
)
try:
    if not client.connect():
        raise SystemExit(f"ERROR: cannot open {port}")
    response = client.read_coils(address=0, count=1, device_id=device_id)
    if response is None or response.isError():
        raise SystemExit(f"ERROR: Waveshare slave {device_id} did not answer read_coils: {response}")
except SystemExit:
    raise
except Exception as exc:
    raise SystemExit(
        f"ERROR: Waveshare slave {device_id} read_coils failed on {port}: {exc}"
    ) from None
finally:
    client.close()
print(f"PASS: verified CH343 {port}@{baud} 8{parity}1 slave={device_id} (read-only)")
PY
SH
chmod +x /home/${BOARDNET_SSH_USER}/maskservice/scripts/verify-boardnet-modbus.sh

# Remove the legacy emergency override. The generated unit now carries the
# verified 4800/slave 1 machine contract directly, so no higher-precedence
# drop-in is required.
rm -f /home/${BOARDNET_SSH_USER}/.config/systemd/user/oqlos-hardware-api.service.d/99-modbus-port.conf
rm -f /home/${BOARDNET_SSH_USER}/.config/systemd/user/oqlos-hardware-api.service.d/90-modbus-device-id.conf

# --- systemd unit: oqlos-server with the OQL-over-MQTT agent/controller enabled ---
cat > /home/${BOARDNET_SSH_USER}/.config/systemd/user/oqlos-hardware-api.service << EOF
[Unit]
Description=OqlOS hardware node + UI + OQL-over-MQTT bridge (boardnet)
After=network-online.target mosquitto.service pirtc-api.service dri0050-motor-api.service hw-tic249.service usb-adc-stack.service
Wants=mosquitto.service usb-adc-stack.service

[Service]
Type=simple
WorkingDirectory=/home/${BOARDNET_SSH_USER}/oqlos/oqlos
EnvironmentFile=-/home/${BOARDNET_SSH_USER}/maskservice/config/oql-mqtt.env
Environment=HARDWARE_MODE=real
Environment=OQLOS_HARDWARE_MODE=real
Environment=OQLOS_CONFIG_PATH=/home/${BOARDNET_SSH_USER}/maskservice/config/oqlos-real.yaml
Environment=OQLOS_SCENARIOS_DIR=/home/${BOARDNET_SSH_USER}/oqlos/oql-scenario
Environment=PYTHONPATH=/home/${BOARDNET_SSH_USER}/maskservice/pimodbus
Environment=OQLOS_MODBUS_SERIAL_PORT=${IO_DEV}
Environment=OQLOS_MODBUS_BAUD=${IO_BAUD}
Environment=OQLOS_MODBUS_PARITY=N
Environment=OQLOS_MODBUS_DEVICE_ID=${IO_DEVICE_ID}
Environment=OQLOS_MODBUS_EXPECTED_SERIAL=5958006895
Environment=OQLOS_MODBUS_ADC_SERIAL_PORT=${ADC_SERIAL_FOR_CONFIG}
Environment=OQLOS_MODBUS_ADC_BAUD=4800
Environment=OQLOS_MODBUS_ADC_PARITY=N
Environment=OQLOS_MODBUS_ADC_DEVICE_ID=${ADC_DEVICE_ID}
Environment=OQLOS_ADC_SOURCE=usb-adc-stack
Environment=OQLOS_USB_ADC_STACK_URL=http://127.0.0.1:8214
Environment=OQLOS_MOTOR_URL=http://127.0.0.1:8203
Environment=OQLOS_LUNG_MOTOR_URL=http://127.0.0.1:8205
Environment=OQLOS_ENABLE_RTC=1
Environment=PIRTC_API_URL=http://127.0.0.1:8125
Environment=RTC_MOCK=false
Environment=OQLOS_HARDWARE_EVENTS_FILE=/home/${BOARDNET_SSH_USER}/oqlos/hardware-events.jsonl
Environment=OQLOS_LOG_FILE=/home/${BOARDNET_SSH_USER}/maskservice/logs/oqlos-hardware-api.log
Environment=OQLOS_LOG_MAX_BYTES=10000000
Environment=OQLOS_LOG_BACKUP_COUNT=5
Environment=OQLOS_HTTP_CLIENT_LOG_LEVEL=WARNING
Environment=OQLOS_OQL_TRANSPORT_ROLE=both
Environment=OQLOS_OQL_NODE_ID=boardnet
Environment=OQLOS_OQL_TOPIC_PREFIX=oqlos/c2004
Environment=OQLOS_OQL_MQTT_HOST=127.0.0.1
Environment=OQLOS_OQL_MQTT_PORT=1883
# Verify and log the exact identity/RTU contract before startup, but keep the
# diagnostics API online in degraded mode. Hardware commands remain fail-closed
# in plugin readiness and return 503 while this verification fails.
ExecStartPre=/bin/bash -lc '/bin/bash /home/${BOARDNET_SSH_USER}/maskservice/scripts/verify-boardnet-modbus.sh || { echo "WARN: BoardNet Modbus preflight failed; starting diagnostics-only degraded runtime" >&2; exit 0; }'
ExecStartPre=/bin/bash -lc 'if /home/${BOARDNET_SSH_USER}/maskservice/scripts/wait-hw-tic249-ready.sh; then exit 0; fi; [ "${PIHW_ALLOW_MISSING_HARDWARE:-1}" = "1" ] && exit 0; exit 1'
ExecStartPre=/home/${BOARDNET_SSH_USER}/maskservice/scripts/tic249-deenergize-best-effort.sh
ExecStart=/home/${BOARDNET_SSH_USER}/oqlos/venv/bin/oqlos-server --host 0.0.0.0 --port 8202
ExecStop=/home/${BOARDNET_SSH_USER}/maskservice/scripts/tic249-deenergize-best-effort.sh
ExecStopPost=/home/${BOARDNET_SSH_USER}/maskservice/scripts/tic249-deenergize-best-effort.sh
Restart=always
RestartSec=10
KillSignal=SIGINT
TimeoutStopSec=25
# Application logs use OqlOS RotatingFileHandler. Keeping stdout/stderr in the
# journal avoids two writers racing on the same rotated file.
StandardOutput=journal
StandardError=journal

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
echo "PASS: oqlos-hardware-api uruchomiony (HTTP/UI :8202 LAN, MQTT :1883)"
```

```bash markpact:ref assert-hw-node-healthy
#!/bin/bash
set -euo pipefail
ALLOW_MISSING="${PIHW_ALLOW_MISSING_HARDWARE:-1}"
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT
failures=0
warnings=0

_pass() { echo "PASS: $*"; }
_fail() { echo "FAIL: $*" >&2; failures=$((failures + 1)); }
_warn_or_fail() {
  if [ "$ALLOW_MISSING" = "1" ]; then
    echo "WARN: $*"
    warnings=$((warnings + 1))
  else
    _fail "$*"
  fi
}

_assert_tic_deenergized() {
  local label="$1"
  local status_file="$2"
  if [ ! -f "$status_file" ]; then
    _warn_or_fail "$label — brak pliku status Tic249"
    return 1
  fi
  if python3 - "$status_file" "$ALLOW_MISSING" "$label" <<'PY'
import json, sys
path, allow, label = sys.argv[1], sys.argv[2], sys.argv[3]
data = json.load(open(path, encoding="utf-8"))
connected = data.get("connected")
energized = data.get("energized")
if connected is True and energized is False:
    print(f"PASS: {label} — Tic249 energized=false")
    raise SystemExit(0)
if connected is not True:
    msg = f"{label} — Tic249 niepolaczony (connected={connected!r})"
    if allow == "1":
        print(f"WARN: {msg}")
        raise SystemExit(0)
    print(f"FAIL: {msg}")
    raise SystemExit(1)
print(f"FAIL: {label} — Tic249 nie jest de-energized (energized={energized!r})")
raise SystemExit(1)
PY
  then
    return 0
  fi
  failures=$((failures + 1))
  return 1
}

_check_service() {
  local unit="$1"
  local required="${2:-1}"
  if systemctl --user is-active "$unit" >/dev/null 2>&1; then
    _pass "$unit active"
    return 0
  fi
  systemctl --user status "$unit" --no-pager -n 40 || true
  if [ "$required" = "1" ]; then
    _fail "$unit nieaktywny"
  else
    _warn_or_fail "$unit nieaktywny lub brak jednostki"
  fi
}

_curl_get() {
  local url="$1"
  local out="$2"
  local timeout="${3:-8}"
  curl -sf --max-time "$timeout" "$url" > "$out"
}

_wait_get() {
  local url="$1"
  local out="$2"
  local attempts="${3:-45}"
  local timeout="${4:-8}"
  local i
  for i in $(seq 1 "$attempts"); do
    if _curl_get "$url" "$out" "$timeout"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

_wait_listen() {
  local pattern="$1"
  local attempts="${2:-45}"
  local i
  for i in $(seq 1 "$attempts"); do
    if ss -tlnp 2>/dev/null | grep -q "$pattern"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

_curl_post() {
  local url="$1"
  local out="$2"
  local data="${3:-{}}"
  local timeout="${4:-8}"
  curl -sf --max-time "$timeout" -H 'Content-Type: application/json' -d "$data" "$url" > "$out"
}

_check_service mosquitto.service 1
_check_service hw-tic249.service 0
_check_service dri0050-motor-api.service 0
_check_service pirtc-api.service 0
_check_service oqlos-hardware-api.service 1

if ss -tlnp 2>/dev/null | grep -q ':8200'; then
  _warn_or_fail "stary/duplikowany OqlOS nadal slucha na :8200"
else
  _pass "brak duplikatu OqlOS na :8200"
fi

if _wait_get http://127.0.0.1:8202/health "$TMPDIR/oqlos-health.json" 45 3; then
  if python3 - "$TMPDIR/oqlos-health.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
raise SystemExit(0 if data.get("status") == "ok" else 1)
PY
  then
    _pass "OqlOS HTTP :8202 /health OK"
  else
    _fail "OqlOS /health nie zwrocil status=ok"
  fi
else
  _fail "OqlOS HTTP :8202 nie odpowiada"
fi

if _wait_listen '0\.0\.0\.0:8202' 45; then
  _pass "OqlOS HTTP/UI :8202 slucha na 0.0.0.0 (LAN)"
else
  _fail "OqlOS HTTP/UI :8202 nie slucha na 0.0.0.0"
fi

for page in hardware-status hardware-demo map-editor scenario-files func-editor hardware-coils; do
  page_attempts=30
  [ "$page" = "map-editor" ] && page_attempts=1
  if _wait_get "http://127.0.0.1:8202/ui/${page}" "$TMPDIR/oqlos-ui-${page}.html" "$page_attempts" 8; then
    _pass "OqlOS UI /ui/${page} OK"
  elif [ "$page" = "map-editor" ]; then
    echo "WARN: opcjonalny OqlOS UI /ui/${page} nie jest zbudowany; nie wycofuję sprawnego runtime sprzętowego"
    warnings=$((warnings + 1))
  else
    _fail "OqlOS UI /ui/${page} nie odpowiada"
  fi
  # Legacy redirect (bez /ui) — nadal musi przekierować na kanoniczny SPA.
  if _wait_get "http://127.0.0.1:8202/${page}" "$TMPDIR/oqlos-legacy-${page}.html" 15 4; then
    _pass "OqlOS legacy /${page} redirect OK"
  else
    _warn_or_fail "OqlOS legacy /${page} nie odpowiada (sprawdz recznie /ui/${page})"
  fi
done

UNIT_ENV=$(systemctl --user show oqlos-hardware-api.service --property=Environment --value)
if grep -Fq 'OQLOS_SCENARIOS_DIR=/home/${BOARDNET_SSH_USER}/oqlos/oql-scenario' <<<"$UNIT_ENV"; then
  _pass "OqlOS używa kanonicznego magazynu /home/${BOARDNET_SSH_USER}/oqlos/oql-scenario"
else
  _fail "OqlOS nie ma ustawionego kanonicznego OQLOS_SCENARIOS_DIR"
fi

if _curl_get http://127.0.0.1:8202/api/v1/editor/files "$TMPDIR/oqlos-editor-files.json" 8; then
  if python3 - "$TMPDIR/oqlos-editor-files.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
files = data.get("files") or []
names = {entry.get("name") for entry in files}
required = {"system.oql", "layers"}
missing = sorted(required - names)
oql_count = sum(
    1 for entry in files
    if not entry.get("is_directory") and str(entry.get("name", "")).endswith(".oql")
)
if missing:
    print(f"Brak wymaganych pozycji: {', '.join(missing)}", file=sys.stderr)
    raise SystemExit(1)
if oql_count < 20:
    print(f"Za mało głównych plików OQL: {oql_count}", file=sys.stderr)
    raise SystemExit(1)
print(f"Kanoniczny magazyn zawiera system.oql, layers i {oql_count} głównych plików OQL")
PY
  then
    _pass "OqlOS /api/v1/editor/files udostępnia scenariusze i konfiguracje systemowe"
  else
    _fail "OqlOS editor nie udostępnia kompletnego kanonicznego magazynu OQL"
  fi
else
  _fail "OqlOS /api/v1/editor/files nie odpowiada"
fi

if _curl_get http://127.0.0.1:8202/api/v3/hardware/configuration/schema "$TMPDIR/oqlos-config-schema.json" 8; then
  if python3 - "$TMPDIR/oqlos-config-schema.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
raise SystemExit(0 if data.get("contract") == "hardware-configuration-v1" else 1)
PY
  then
    _pass "OqlOS /api/v3/hardware/configuration/schema OK"
  else
    _fail "OqlOS configuration schema nie zwrocil hardware-configuration-v1"
  fi
else
  _fail "OqlOS /api/v3/hardware/configuration/schema nie odpowiada"
fi

if _curl_get http://127.0.0.1:8202/api/v1/hardware/health "$TMPDIR/oqlos-hardware-health.json" 12; then
  if ! python3 - "$TMPDIR/oqlos-hardware-health.json" "$ALLOW_MISSING" <<'PY'
import json, sys
path, allow = sys.argv[1], sys.argv[2]
data = json.load(open(path, encoding="utf-8"))
failed = 0
if data.get("mode") != "real":
    print(f"FAIL: OqlOS mode={data.get('mode')!r}, oczekiwano real")
    failed += 1
else:
    print("PASS: OqlOS hardware mode=real")

for plugin_id in ("motor-tic249", "motor-dri0050", "modbus-io", "modbus-adc"):
    entry = data.get(plugin_id) or {}
    compatible = bool(entry.get("compatible"))
    status = entry.get("status", "missing")
    message = entry.get("message", "")
    if compatible:
        print(f"PASS: plugin {plugin_id} compatible=true")
    elif allow == "1":
        print(f"WARN: plugin {plugin_id} compatible=false status={status} {message}")
    else:
        print(f"FAIL: plugin {plugin_id} compatible=false status={status} {message}")
        failed += 1
raise SystemExit(1 if failed else 0)
PY
  then
    failures=$((failures + 1))
  fi
else
  _fail "OqlOS /api/v1/hardware/health nie odpowiada"
fi

# Tic249: connect/stop/de-energize sa best-effort; warunkiem jest koncowy status bez ruchu.
if ! _curl_post http://127.0.0.1:8205/api/connect "$TMPDIR/tic-connect.json" '{}' 8 >/dev/null 2>&1; then
  echo "INFO: Tic249 /api/connect nie powiodl sie, kontynuuje przez stop/deenergize/status"
fi
if ! curl -fsS --max-time 4 -X POST http://127.0.0.1:8205/api/stop >/dev/null 2>&1; then
  echo "INFO: Tic249 /api/stop nie powiodl sie, sprawdzam koncowy status"
fi
if ! _curl_post http://127.0.0.1:8205/api/energize "$TMPDIR/tic-deenergize.json" '{"enable":false}' 4 >/dev/null 2>&1; then
  echo "INFO: Tic249 /api/energize(false) nie powiodl sie, sprawdzam koncowy status"
fi
if _curl_get http://127.0.0.1:8205/api/status "$TMPDIR/tic-status.json" 6; then
  if ! python3 - "$TMPDIR/tic-status.json" "$ALLOW_MISSING" <<'PY'
import json, sys
path, allow = sys.argv[1], sys.argv[2]
data = json.load(open(path, encoding="utf-8"))
failed = 0
if data.get("connected") is True:
    print("PASS: Tic249 sidecar connected=true")
elif allow == "1":
    print(f"WARN: Tic249 sidecar connected={data.get('connected')!r}")
else:
    print(f"FAIL: Tic249 sidecar connected={data.get('connected')!r}")
    failed += 1
if data.get("energized") is False:
    print("PASS: Tic249 energized=false")
elif data.get("connected") is not True and allow == "1":
    print(f"WARN: Tic249 energized={data.get('energized')!r} przy braku polaczenia")
else:
    print(f"FAIL: Tic249 nie jest de-energized: energized={data.get('energized')!r}")
    failed += 1
if data.get("low_vin") is True:
    if allow == "1":
        print("WARN: Tic249 low_vin=true")
    else:
        print("FAIL: Tic249 low_vin=true")
        failed += 1
raise SystemExit(1 if failed else 0)
PY
  then
    failures=$((failures + 1))
  fi
else
  _warn_or_fail "Tic249 sidecar :8205 nie zwrocil status po stop/deenergize"
fi

# DRI0050: tylko stop/status; test nie uruchamia pompy.
if curl -fsS --max-time 5 -X POST http://127.0.0.1:8203/api/stop >/dev/null 2>&1 \
   && _curl_get http://127.0.0.1:8203/api/status "$TMPDIR/dri-status.json" 6; then
  if grep -Eq '"enabled"[[:space:]]*:[[:space:]]*false' "$TMPDIR/dri-status.json"; then
    _pass "DRI0050 :8203 stop/status OK, enabled=false"
  else
    _warn_or_fail "DRI0050 :8203 nie potwierdzil enabled=false po stop"
  fi
else
  _warn_or_fail "DRI0050 :8203 nie odpowiada na stop/status"
fi

# piRTC: status bez mocka, jesli HAT jest obecny.
if _curl_get http://127.0.0.1:8125/api/status "$TMPDIR/pirtc-status.json" 6; then
  if python3 - "$TMPDIR/pirtc-status.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
rtc = data.get("rtc", {}) if isinstance(data, dict) else {}
raise SystemExit(0 if rtc.get("available") is True and rtc.get("mock") is False else 1)
PY
  then
    _pass "piRTC :8125 available=true mock=false"
  else
    _warn_or_fail "piRTC :8125 status nie potwierdza available=true mock=false"
  fi
else
  _warn_or_fail "piRTC :8125 nie odpowiada"
fi

# Modbus ADC/sensory: bez zapisu, tylko odczyt diagnostyczny.
if _curl_get http://127.0.0.1:8202/api/v1/hardware/modbus-adc/raw "$TMPDIR/modbus-adc-raw.json" 12; then
  if grep -Eq '"ok"[[:space:]]*:[[:space:]]*true|\"success\"[[:space:]]*:[[:space:]]*true' "$TMPDIR/modbus-adc-raw.json"; then
    _pass "Modbus ADC raw read OK"
  else
    _warn_or_fail "Modbus ADC raw endpoint odpowiedzial, ale bez ok=true"
  fi
else
  _warn_or_fail "Modbus ADC raw read nie odpowiada"
fi

if _curl_get 'http://127.0.0.1:8202/api/v1/hardware/sensors/batch?sensor_ids=ai01,ai02,ai03' "$TMPDIR/sensors.json" 12; then
  if grep -Eq '"ok"[[:space:]]*:[[:space:]]*true' "$TMPDIR/sensors.json"; then
    _pass "Sensory AI01-AI03 batch OK"
  else
    _warn_or_fail "Sensory AI01-AI03 batch bez ok=true"
  fi
else
  _warn_or_fail "Sensory AI01-AI03 batch nie odpowiada"
fi

if _curl_get 'http://127.0.0.1:8202/api/v1/hardware/identify?scan=never' "$TMPDIR/identify.json" 12; then
  _pass "OqlOS identify(scan=never) odpowiada"
else
  _fail "OqlOS identify(scan=never) nie odpowiada"
fi

# HTTP HUI API — ścieżka DisplayNet GUI (bez ruchu AL, tylko katalog + safe stop).
if _curl_get http://127.0.0.1:8202/api/v1/hardware/hui/actions "$TMPDIR/hui-actions.json" 12; then
  if python3 - "$TMPDIR/hui-actions.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
if data.get("ok") is not True:
    print(f"FAIL: hui/actions ok={data.get('ok')!r}")
    raise SystemExit(1)
hold = set(data.get("hold_keys") or [])
al = set(data.get("al_keys") or [])
required = {"head-inflate", "head-deflate", "lp-bleed", "lp-pwm-plus5", "lp-pwm-minus10"}
if not required.issubset(hold) or "al-stop" not in al or "al-start" not in al:
    print(f"FAIL: HUI catalog hold={sorted(hold)} al={sorted(al)}")
    raise SystemExit(1)
# Ctrl+Alt+1..9 (c2004 HUI_TEST_BUTTON_ORDER) — indeksy 1-based.
index_map = {
    1: "head-deflate", 2: "lp-pwm-plus5", 3: "lp-pwm-plus10", 4: "al-start",
    5: "lp-bleed", 6: "head-inflate", 7: "lp-pwm-minus5", 8: "lp-pwm-minus10", 9: "al-stop",
}
for idx, key in index_map.items():
    if key in hold or key in al:
        continue
    print(f"FAIL: Ctrl+Alt+{idx} -> {key} brak w katalogu HUI")
    raise SystemExit(1)
profiles = data.get("profiles") or {}
if profiles.get("lp-pwm-minus10", {}).get("pump_pct") != 100.0:
    print("FAIL: HUI profile lp-pwm-minus10 pump_pct != 100")
    raise SystemExit(1)
lung = ((data.get("artificial_lung") or {}).get("reciprocate_args") or {})
if lung.get("limit_mode") != "reverse_on_limit":
    print(f"FAIL: HUI AL limit_mode={lung.get('limit_mode')!r}")
    raise SystemExit(1)
print("PASS: HTTP HUI action catalog OK")
PY
  then
    _pass "OqlOS HTTP /api/v1/hardware/hui/actions OK"
  else
    failures=$((failures + 1))
  fi
else
  _fail "OqlOS HTTP /api/v1/hardware/hui/actions nie odpowiada"
fi

if _curl_post http://127.0.0.1:8202/api/v1/hardware/hui/al/stop "$TMPDIR/hui-al-stop.json" '{"source":"redeploy-assert"}' 20; then
  if grep -q 'stop_lung' "$TMPDIR/hui-al-stop.json"; then
    _pass "HTTP HUI al/stop osiagalny (lung stop)"
  else
    _warn_or_fail "HTTP HUI al/stop bez potwierdzenia stop_lung"
  fi
  if grep -Eq '"ok"[[:space:]]*:[[:space:]]*true' "$TMPDIR/hui-al-stop.json"; then
    _pass "HTTP HUI al/stop ok=true"
  else
    _warn_or_fail "HTTP HUI al/stop ok=false (typowe przy degraded modbus-io)"
  fi
else
  _warn_or_fail "HTTP HUI al/stop nie odpowiada"
fi

if _curl_post http://127.0.0.1:8202/api/v1/hardware/hui/shutdown "$TMPDIR/hui-shutdown.json" '{"source":"redeploy-assert"}' 25; then
  if grep -Eq '"ok"[[:space:]]*:[[:space:]]*true' "$TMPDIR/hui-shutdown.json"; then
    _pass "HTTP HUI shutdown ok=true"
  else
    _warn_or_fail "HTTP HUI shutdown ok=false (sprawdz modbus-io / pompe)"
  fi
else
  _warn_or_fail "HTTP HUI shutdown nie odpowiada"
fi

# OQL-over-MQTT agent round-trips: ping, health, usb-list, pi-diagnostics, lung-disable.
PW=$(grep -E '^OQLOS_OQL_MQTT_PASSWORD=' /home/${BOARDNET_SSH_USER}/maskservice/config/oql-mqtt.env 2>/dev/null | head -1 | cut -d= -f2- || true)
NODE="${OQLOS_OQL_NODE_ID:-boardnet}"
PREFIX="${OQLOS_OQL_TOPIC_PREFIX:-oqlos/c2004}"
if [ -z "$PW" ] || [ "$PW" = "CHANGE_ME_ON_PI" ]; then
  _fail "brak poprawnego OQLOS_OQL_MQTT_PASSWORD w /home/${BOARDNET_SSH_USER}/maskservice/config/oql-mqtt.env"
else
  _mqtt_rpc() {
    local kind="$1"
    local oql="$2"
    local args_json="${3:-null}"
    local timeout="${4:-10}"
    local corr="assert-$(date +%s)-$RANDOM"
    local out="$TMPDIR/$corr.response.json"
    local req="$TMPDIR/$corr.request.json"
    local err="$TMPDIR/$corr.sub.err"

    python3 - "$corr" "$kind" "$oql" "$args_json" "$PREFIX" "$NODE" <<'PY' > "$req"
import json, sys
corr, kind, oql, args_raw, prefix, node = sys.argv[1:7]
args = json.loads(args_raw)
payload = {
    "correlation_id": corr,
    "kind": kind,
    "oql": oql,
    "reply_to": f"{prefix.rstrip('/')}/{node}/oql/response/{corr}",
}
if args is not None:
    payload["args"] = args
print(json.dumps(payload, ensure_ascii=False))
PY

    mosquitto_sub -h 127.0.0.1 -p 1883 -u oqlos -P "$PW" \
      -t "$PREFIX/$NODE/oql/response/$corr" -C 1 -W "$timeout" > "$out" 2>"$err" &
    local sub=$!
    sleep 1
    mosquitto_pub -h 127.0.0.1 -p 1883 -u oqlos -P "$PW" \
      -t "$PREFIX/$NODE/oql/request" -f "$req"
    if wait "$sub"; then
      cat "$out"
      return 0
    fi
    cat "$err" >&2 || true
    return 1
  }

  _mqtt_envelope_ok() {
    local file="$1"
    local label="$2"
    local required="${3:-1}"
    if python3 - "$file" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
raise SystemExit(0 if data.get("ok") is True else 1)
PY
    then
      _pass "$label"
    elif [ "$required" = "1" ]; then
      _fail "$label zwrocil ok!=true"
    else
      _warn_or_fail "$label zwrocil ok!=true"
    fi
  }

  if _mqtt_rpc ping "" null 10 > "$TMPDIR/mqtt-ping.json"; then
    _mqtt_envelope_ok "$TMPDIR/mqtt-ping.json" "MQTT ping/pong agent OK" 1
  else
    _fail "brak odpowiedzi MQTT ping/pong agenta"
  fi

  if _mqtt_rpc manage health '{}' 12 > "$TMPDIR/mqtt-health.json"; then
    _mqtt_envelope_ok "$TMPDIR/mqtt-health.json" "MQTT manage health OK" 1
  else
    _fail "brak odpowiedzi MQTT manage health"
  fi

  if _mqtt_rpc manage usb-list '{}' 12 > "$TMPDIR/mqtt-usb-list.json"; then
    _mqtt_envelope_ok "$TMPDIR/mqtt-usb-list.json" "MQTT manage usb-list OK" 1
    if ! python3 - "$TMPDIR/mqtt-usb-list.json" "$ALLOW_MISSING" <<'PY'
import json, sys
path, allow = sys.argv[1], sys.argv[2]
data = json.load(open(path, encoding="utf-8"))
devices = (((data.get("result") or {}).get("devices")) or [])
ids = {(str(d.get("vendor_id", "")).lower(), str(d.get("product_id", "")).lower()) for d in devices}
failed = 0
for vid, pid, label in (
    ("1ffb", "00c9", "Pololu Tic T249"),
    ("1a86", "7523", "CH340 Modbus/serial adapter"),
):
    if (vid, pid) in ids:
        print(f"PASS: usb-list widzi {label} ({vid}:{pid})")
    elif allow == "1":
        print(f"WARN: usb-list nie widzi {label} ({vid}:{pid})")
    else:
        print(f"FAIL: usb-list nie widzi {label} ({vid}:{pid})")
        failed += 1
raise SystemExit(1 if failed else 0)
PY
    then
      failures=$((failures + 1))
    fi
  else
    _fail "brak odpowiedzi MQTT manage usb-list"
  fi

  if _mqtt_rpc manage pi-diagnostics '{}' 12 > "$TMPDIR/mqtt-pi-diag.json"; then
    _mqtt_envelope_ok "$TMPDIR/mqtt-pi-diag.json" "MQTT manage pi-diagnostics OK" 1
  else
    _fail "brak odpowiedzi MQTT manage pi-diagnostics"
  fi

  if _mqtt_rpc manage hui-actions '{}' 12 > "$TMPDIR/mqtt-hui-actions.json"; then
    _mqtt_envelope_ok "$TMPDIR/mqtt-hui-actions.json" "MQTT manage hui-actions OK" 1
    if ! python3 - "$TMPDIR/mqtt-hui-actions.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
result = data.get("result") or {}
hold_keys = set(result.get("hold_keys") or [])
al_keys = set(result.get("al_keys") or [])
required = {"head-inflate", "head-deflate", "lp-pwm-plus5", "lp-pwm-minus5"}
missing = sorted(required - hold_keys)
if missing or "al-stop" not in al_keys:
    print(f"FAIL: HUI actions missing hold={missing} al-stop={'al-stop' not in al_keys}")
    raise SystemExit(1)
print("PASS: HUI action catalog exposes expected controls")
PY
    then
      failures=$((failures + 1))
    fi
  else
    _fail "brak odpowiedzi MQTT manage hui-actions"
  fi

  # Safe HUI shutdown paths only: these may return ok=false when optional valve/pump
  # plugins are intentionally absent, but they prove that connect-scenario can drive
  # the HUI surface through OQL-over-MQTT without a direct HTTP hop to boardnet.
  if _mqtt_rpc manage hui-hold-stop '{"key":"head-inflate"}' 18 > "$TMPDIR/mqtt-hui-hold-stop.json"; then
    _mqtt_envelope_ok "$TMPDIR/mqtt-hui-hold-stop.json" "MQTT manage hui-hold-stop safe path OK" 0
  else
    _warn_or_fail "brak odpowiedzi MQTT manage hui-hold-stop"
  fi

  if _mqtt_rpc manage hui-al-stop '{}' 18 > "$TMPDIR/mqtt-hui-al-stop.json"; then
    _mqtt_envelope_ok "$TMPDIR/mqtt-hui-al-stop.json" "MQTT manage hui-al-stop safe path OK" 0
    if _curl_get http://127.0.0.1:8205/api/status "$TMPDIR/tic-after-hui-al-stop.json" 6; then
      _assert_tic_deenergized "Tic249 po MQTT hui-al-stop" "$TMPDIR/tic-after-hui-al-stop.json"
    else
      _warn_or_fail "Tic249 po MQTT hui-al-stop — brak statusu sidecar :8205"
    fi
  else
    _warn_or_fail "brak odpowiedzi MQTT manage hui-al-stop"
  fi

  if _mqtt_rpc manage diagnostic-command '{"peripheral_id":"modbus-io","command":"valve_off","args":{"valve_id":"valve-wc"}}' 18 > "$TMPDIR/mqtt-modbus-valve-off.json"; then
    _mqtt_envelope_ok "$TMPDIR/mqtt-modbus-valve-off.json" "MQTT diagnostic-command modbus-io valve_off accepted" 0
    if ! python3 - "$TMPDIR/mqtt-modbus-valve-off.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
text = json.dumps(data)
if "Unknown command" in text:
    print("FAIL: modbus-io valve_off rejected as Unknown command")
    raise SystemExit(1)
print("PASS: modbus-io valve_off command is understood by OqlOS")
PY
    then
      failures=$((failures + 1))
    fi
  else
    _warn_or_fail "brak odpowiedzi MQTT diagnostic-command modbus-io valve_off"
  fi

  if _mqtt_rpc manage lung-disable '{}' 12 > "$TMPDIR/mqtt-lung-disable.json"; then
    _mqtt_envelope_ok "$TMPDIR/mqtt-lung-disable.json" "MQTT manage lung-disable OK" 0
    if _curl_get http://127.0.0.1:8205/api/status "$TMPDIR/tic-after-mqtt-disable.json" 6; then
      _assert_tic_deenergized "Tic249 po MQTT lung-disable" "$TMPDIR/tic-after-mqtt-disable.json"
    else
      _warn_or_fail "Tic249 po MQTT lung-disable — brak statusu sidecar :8205"
    fi
  else
    _warn_or_fail "brak odpowiedzi MQTT manage lung-disable"
  fi
fi

if [ "$failures" -gt 0 ]; then
  echo "FAIL: smoke-test osprzetu zakonczony bledami: failures=$failures warnings=$warnings" >&2
  exit 1
fi
echo "PASS: pelny smoke-test osprzetu zakonczony (warnings=$warnings, PIHW_ALLOW_MISSING_HARDWARE=$ALLOW_MISSING)"
```

```bash markpact:ref assert-oqlos-checksum
#!/bin/bash
# Weryfikacja sumą kontrolną: czy wdrożony pakiet oqlos/ na Pi jest dokładnie tym,
# co policzono na źródle. Manifest oqlos/_CHECKSUMS.sha256 generuje `scripts/gen-checksums.sh`
# na kontrolerze PRZED deployem; krok sync_oqlos_core dowozi go razem z kodem.
set -euo pipefail
PKG=/home/${BOARDNET_SSH_USER}/oqlos/oqlos/oqlos
MANIFEST="$PKG/_CHECKSUMS.sha256"

if [ ! -f "$MANIFEST" ]; then
  echo "FAIL: brak $MANIFEST — uruchom 'scripts/gen-checksums.sh' na źródle przed 'redeploy run' (sync_oqlos_core go dowiezie)" >&2
  exit 1
fi

cd "$PKG"
# sha256sum -c sprawdza każdy plik z manifestu; dodatkowe pliki na Pi (np. stare artefakty)
# są ignorowane, brakujące/zmienione → niezerowy kod wyjścia.
if sha256sum -c --quiet "$MANIFEST" 2>/tmp/oqlos-checksum.err; then
  echo "PASS: suma kontrolna pakietu oqlos/ zgodna ($(wc -l < "$MANIFEST") plików, sha256)"
else
  echo "FAIL: rozbieżność sumy kontrolnej pakietu oqlos/ (plik uszkodzony/niedosłany w rsync):" >&2
  sed -n '1,20p' /tmp/oqlos-checksum.err >&2
  exit 1
fi
```

```yaml markpact:config
name: "oqlos boardnet deploy"
description: "OqlOS hardware node + mosquitto na ${BOARDNET_SSH_USER}@${BOARDNET_IP} — systemd --user, OQL-over-MQTT agent"
source:
  strategy: systemd
  host: "${BOARDNET_SSH_USER}@${BOARDNET_IP}"
  remote_dir: ~/oqlos
target:
  strategy: systemd
  host: "${BOARDNET_SSH_USER}@${BOARDNET_IP}"
  remote_dir: ~/oqlos
  verify_url: "http://${BOARDNET_IP}:${BOARDNET_OQLOS_PORT}/health"
```

```yaml markpact:steps
extra_steps:

  - id: mkdir_hw_remote
    action: inline_script
    description: "Utwórz katalogi na boardnet"
    command_ref: mkdir-hw-remote

  - id: enable_linger_groups
    action: inline_script
    description: "Linger + grupy urządzeń dla użytkownika ${BOARDNET_SSH_USER}"
    command_ref: enable-linger-groups

  - id: sync_oqlos_core
    action: rsync
    description: "Sync oqlos core na boardnet"
    # `deploy-fleet.sh` starts redeploy from the explicitly selected OqlOS
    # repository. Keep core paths relative so the validated source is exactly
    # the source transferred to BoardNet.
    src: ./
    dst: ~/oqlos/oqlos/
    # `.git` bez ukośnika: submodule oql-scenario/ ma .git jako PLIK (gitdir:) — wzorzec dir-only przepuszczałby go na Pi.
    excludes: [.git, .venv/, venv/, __pycache__/, .pytest_cache/, .ruff_cache/, project/]

  - id: sync_backend_shared_policy
    action: rsync
    description: "Sync kanonicznej wspólnej polityki mapowania z c2004/backend-shared-py"
    src: ${C2004_ROOT}/packages/backend-shared-py/
    dst: ~/oqlos/oqlos/packages/backend-shared-py/
    excludes: [.git, .venv/, venv/, __pycache__/, .pytest_cache/]

  - id: sync_oqlos_frontend_dist
    action: rsync
    description: "Sync zbudowanego OqlOS hardware UI (frontend/dist)"
    src: ./frontend/dist/
    dst: ~/oqlos/oqlos/frontend/dist/
    excludes: []

  - id: sync_oql_scenario
    action: rsync
    description: "Sync kanonicznego magazynu OQL współdzielonego przez całą flotę"
    # One SSOT: OQL scenarios live only in the dedicated oql-scenario repo.
    # Historical c2004/extern/scenarios was removed and must not return as a
    # deployment fallback.
    src: ${OQL_SCENARIOS_DIR}/
    dst: ~/oqlos/oql-scenario/
    excludes: [.git, .venv/, venv/, __pycache__/, .pytest_cache/]

  - id: sync_pihw_config
    action: rsync
    description: "Sync konfiguracji węzła boardnet (mosquitto.conf, oqlos-hw.yaml, .env.hw)"
    src: ./redeploy/122/
    dst: ~/maskservice/boardnet-config/
    excludes: [.git/]

  - id: sync_pimodbus
    action: rsync
    description: "Sync pimodbus (adaptery Modbus)"
    src: ${OQLOS_WORKSPACE_ROOT}/pimodbus/
    dst: ~/maskservice/pimodbus/
    excludes: [.git/, .venv/, venv/, __pycache__/, .pytest_cache/]

  - id: sync_rpi_motor_tic249
    action: rsync
    description: "Sync sterownika Pololu Tic T249"
    src: ${OQLOS_WORKSPACE_ROOT}/rpi-motor-tic249/
    dst: ~/maskservice/rpi-motor-tic249/
    excludes: [.git/, .venv/, venv/, __pycache__/]

  - id: sync_rpi_motor_dri0050
    action: rsync
    description: "Sync sterownika DFRobot DRI0050"
    src: ${OQLOS_WORKSPACE_ROOT}/rpi-motor-DRI0050/
    dst: ~/maskservice/rpi-motor-DRI0050/
    excludes: [.git/, .venv/, venv/, __pycache__/]

  - id: sync_usb_adc_mcp2221
    action: rsync
    description: "Sync adaptera MCP2221A (AI01)"
    src: ${OQLOS_WORKSPACE_ROOT}/usb-adc-mcp2221/
    dst: ~/oqlos-adapters/usb-adc-mcp2221/
    excludes: [.git/, .venv/, venv/, __pycache__/, .pytest_cache/]

  - id: sync_usb_adc_dfr1184
    action: rsync
    description: "Sync adaptera DFR1184 i wspólnego usb-adc-stack (AI01-AI03)"
    src: ${OQLOS_WORKSPACE_ROOT}/usb-adc-dfr1184/
    dst: ~/oqlos-adapters/usb-adc-dfr1184/
    excludes: [.git/, .venv/, venv/, __pycache__/, .pytest_cache/]

  - id: sync_pirtc
    action: rsync
    description: "Sync piRTC sidecar"
    src: ${OQLOS_WORKSPACE_ROOT}/pirtc/
    dst: ~/maskservice/pirtc/
    excludes: [.git/, .venv/, venv/, __pycache__/]

  - id: sync_pirtc_rtc_lib
    action: rsync
    description: "Sync sterownika Waveshare DS3231 dla piRTC (pirtc/.gitignore ignoruje lib/)"
    src: ${OQLOS_WORKSPACE_ROOT}/pirtc/RTC/python/lib/
    dst: ~/maskservice/pirtc/RTC/python/lib/
    excludes: [__pycache__/]

  - id: assert_oqlos_checksum
    action: inline_script
    description: "Weryfikacja sumą kontrolną wdrożonego pakietu oqlos/ (sha256 vs manifest źródła)"
    command_ref: assert-oqlos-checksum

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
    timeout: 300

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

  - id: deploy_usb_adc_stack
    action: inline_script
    description: "Wspólny stos ADC MCP2221A + DFR1184 (:8214 loopback)"
    command_ref: deploy-usb-adc-stack
    timeout: 180

  - id: deploy_oqlos_hw_api
    action: inline_script
    description: "OqlOS hardware API/UI + OQL-over-MQTT bridge (:8202 LAN)"
    command_ref: deploy-oqlos-hw-api
    timeout: 300

  - id: assert_hw_node_healthy
    action: inline_script
    description: "Asercja: pełny smoke-test osprzętu, sidecarów, pluginów i MQTT"
    command_ref: assert-hw-node-healthy
    timeout: 300
```
