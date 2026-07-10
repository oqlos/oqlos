#!/bin/bash
# OqlOS BoardNet (.122) hardware test / diagnose / fix procedure.
#
# Selective by design: it probes every peripheral INDIVIDUALLY, so one dead
# device never blocks the rest. When a Modbus peripheral (valves modbus-io /
# analog modbus-adc) is unhealthy it drops to a per-port, per-address bus scan
# to find what actually answers, and can auto-fix the OqlOS config for a device
# it locates (e.g. enable modbus-adc on the port/slave-id where an ADC replies).
#
# Modes:
#   test      (default) read-only per-peripheral health — non-invasive
#   diagnose  test + free the serial ports and scan the RS485 bus (stops OqlOS
#             briefly, then restarts it) — read-only on the bus
#   fix       diagnose + apply safe config fixes for located devices, restart,
#             re-verify
#
# Usage (on .122):  bash ~/oqlos/oqlos/scripts/hardware-diag-fix.sh [test|diagnose|fix]
# Or from nvidia:   ssh pi@192.168.188.122 'bash ~/oqlos/oqlos/scripts/hardware-diag-fix.sh diagnose'
set -uo pipefail

MODE="${1:-test}"
API="${OQLOS_API:-http://127.0.0.1:8202}"
VENV="${OQLOS_VENV:-/home/pi/oqlos/venv/bin/python}"
CFG="${OQLOS_CONFIG:-/home/pi/maskservice/config/oqlos-real.yaml}"
UNIT="${OQLOS_UNIT:-/home/pi/.config/systemd/user/oqlos-hardware-api.service}"
PIMODBUS_DIR="${PIMODBUS_DIR:-/home/pi/maskservice/pimodbus}"
BAUD=9600

ok(){ printf '  \033[32mOK\033[0m   %s\n' "$*"; }
bad(){ printf '  \033[31mFAIL\033[0m %s\n' "$*"; }
warn(){ printf '  \033[33mWARN\033[0m %s\n' "$*"; }
hdr(){ printf '\n== %s ==\n' "$*"; }

# --- helpers ---------------------------------------------------------------
_get(){ curl -s --max-time 6 "$1" 2>/dev/null; }
_field(){ python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('$2',''))" 2>/dev/null <<<"$1"; }

FAILED_MODBUS=0

# --- PHASE 1: per-peripheral health (selective, never blocks) --------------
phase_test(){
  hdr "PHASE 1 — per-peripheral health"

  # Plugins exposed by OqlOS core (valves + analog live on the RS485 bus).
  for pid in modbus-io modbus-adc; do
    body="$(_get "$API/api/v1/plugins/$pid/health")"
    st="$(_field "$body" status)"
    msg="$(_field "$body" message)"
    case "$st" in
      ok|connected) ok "$pid: $st" ;;
      disabled)     warn "$pid: disabled in config — $msg"; [ "$pid" = modbus-adc ] && FAILED_MODBUS=1 ;;
      *)            bad "$pid: ${st:-no-response} — $msg"; FAILED_MODBUS=1 ;;
    esac
  done

  # Sidecars on their own USB adapters (independent of the RS485 bus).
  tic="$(_get http://127.0.0.1:8205/api/status)"
  [ -n "$tic" ] && grep -q '"connected"[[:space:]]*:[[:space:]]*true' <<<"$tic" \
    && ok "motor-tic249 (lung): connected" || bad "motor-tic249 (lung): not connected"
  dri="$(_get http://127.0.0.1:8203/api/status)"
  [ -n "$dri" ] && grep -Eq '"enabled?"' <<<"$dri" \
    && ok "motor-dri0050 (pump): responding" || bad "motor-dri0050 (pump): no response"
  rtc="$(_get http://127.0.0.1:8125/api/status)"
  [ -n "$rtc" ] && grep -q '"available"[[:space:]]*:[[:space:]]*true' <<<"$rtc" \
    && ok "piRTC: available" || warn "piRTC: unavailable/mock (non-critical)"

  return 0
}

# --- discover USB-RS485 serial adapters (by-id, socket-independent) --------
list_serial_adapters(){
  ls -1 /dev/serial/by-id/ 2>/dev/null | grep -iE '1a86|ftdi|ch340|usb-serial' \
    | sed 's#^#/dev/serial/by-id/#'
}

# --- scan one port for Modbus modules (coils=IO, input regs=ADC) -----------
# Emits lines: PORT<TAB>DEVID<TAB>ROLE(io|adc)
scan_port(){
  local port="$1"
  timeout 40 "$VENV" - "$port" "$BAUD" <<'PY' 2>/dev/null
import sys
from pymodbus.client import ModbusSerialClient
port, baud = sys.argv[1], int(sys.argv[2])
for dev in range(1, 9):
    cli = ModbusSerialClient(port=port, baudrate=baud, parity="N", stopbits=1, bytesize=8, timeout=0.4)
    try:
        if not cli.connect():
            continue
        r = cli.read_coils(address=0, count=1, device_id=dev)
        if r is not None and not r.isError():
            print(f"{port}\t{dev}\tio"); continue
        r = cli.read_input_registers(address=0, count=1, device_id=dev)
        if r is not None and not r.isError():
            print(f"{port}\t{dev}\tadc")
    except Exception:
        pass
    finally:
        try: cli.close()
        except Exception: pass
PY
}

# --- PHASE 2: selective bus scan (only when Modbus is unhealthy) -----------
SCAN_RESULTS=""
phase_diagnose(){
  hdr "PHASE 2 — selective RS485 bus scan"
  if [ "$FAILED_MODBUS" != 1 ]; then
    ok "Modbus peripherals healthy — skipping bus scan"; return 0
  fi
  local adapters; adapters="$(list_serial_adapters)"
  echo "  USB-RS485 adapters present (by-id):"; echo "$adapters" | sed 's/^/    /'

  echo "  Freeing serial ports (stop oqlos-hardware-api)…"
  systemctl --user stop oqlos-hardware-api.service 2>/dev/null; sleep 2
  [ -x "$PIMODBUS_DIR" ] || true
  for port in $adapters; do
    echo "  scanning $port @${BAUD} (ids 1-8)…"
    res="$(cd "$PIMODBUS_DIR" 2>/dev/null; scan_port "$port")"
    if [ -n "$res" ]; then
      echo "$res" | while IFS=$'\t' read -r p d role; do ok "responded: $p  slave=$d  role=$role"; done
      SCAN_RESULTS="${SCAN_RESULTS}${res}"$'\n'
    else
      warn "no Modbus module answered on $port"
    fi
  done
  echo "  Restarting oqlos-hardware-api…"
  systemctl --user start oqlos-hardware-api.service 2>/dev/null; sleep 3

  [ -n "$SCAN_RESULTS" ] || bad "RS485 bus is silent on every adapter — check module power (12/24V), A/B polarity, common GND"
  # export for fix phase via temp file (subshell-safe)
  printf '%s' "$SCAN_RESULTS" > /tmp/oqlos-scan-results.txt
  return 0
}

# --- PHASE 3: selective fix (only for located devices) ---------------------
phase_fix(){
  hdr "PHASE 3 — selective config fix"
  local results; results="$(cat /tmp/oqlos-scan-results.txt 2>/dev/null)"
  if [ -z "$results" ]; then
    warn "nothing located on the bus — no safe auto-fix; fix wiring/power then re-run 'diagnose'"
    return 0
  fi
  # Pick the first ADC responder to enable modbus-adc.
  local adc_line; adc_line="$(grep -P '\tadc$' <<<"$results" | head -1)"
  if [ -n "$adc_line" ]; then
    local port dev; port="$(cut -f1 <<<"$adc_line")"; dev="$(cut -f2 <<<"$adc_line")"
    ok "ADC found at $port slave=$dev — enabling modbus-adc"
    "$VENV" - "$CFG" "$port" "$dev" <<'PY'
import re, sys
from pathlib import Path
cfg, port, dev = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
t = cfg.read_text(encoding="utf-8")
t = re.sub(r"(  modbus-adc:\n(?:.*\n)*?      serial_port: )[^\n]+", rf"\1{port}", t, count=1)
t = re.sub(r"(  modbus-adc:\n(?:.*\n)*?      device_id: )[0-9]+", rf"\g<1>{dev}", t, count=1)
t = re.sub(r"(  modbus-adc:\n(?:.*\n)*?    enabled: )(true|false)", r"\g<1>true", t, count=1)
cfg.write_text(t, encoding="utf-8")
print(f"  config: modbus-adc enabled=true serial_port={port} device_id={dev}")
PY
    sed -i "s|^Environment=OQLOS_MODBUS_ADC_SERIAL_PORT=.*|Environment=OQLOS_MODBUS_ADC_SERIAL_PORT=${port}|" "$UNIT" 2>/dev/null
    sed -i "s|^Environment=OQLOS_MODBUS_ADC_DEVICE_ID=.*|Environment=OQLOS_MODBUS_ADC_DEVICE_ID=${dev}|" "$UNIT" 2>/dev/null
  else
    warn "no ADC responder located — leaving modbus-adc disabled"
  fi
  # Fix modbus-io slave id if it answers at a different address than configured.
  local io_line; io_line="$(grep -P '\tio$' <<<"$results" | head -1)"
  if [ -n "$io_line" ]; then
    local iport idev; iport="$(cut -f1 <<<"$io_line")"; idev="$(cut -f2 <<<"$io_line")"
    ok "IO found at $iport slave=$idev — aligning modbus-io"
    "$VENV" - "$CFG" "$iport" "$idev" <<'PY'
import re, sys
from pathlib import Path
cfg, port, dev = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
t = cfg.read_text(encoding="utf-8")
t = re.sub(r"(  modbus-io:\n(?:.*\n)*?      serial_port: )[^\n]+", rf"\1{port}", t, count=1)
t = re.sub(r"(  modbus-io:\n(?:.*\n)*?      device_id: )[0-9]+", rf"\g<1>{dev}", t, count=1)
cfg.write_text(t, encoding="utf-8")
print(f"  config: modbus-io serial_port={port} device_id={dev}")
PY
    sed -i "s|^Environment=OQLOS_MODBUS_SERIAL_PORT=.*|Environment=OQLOS_MODBUS_SERIAL_PORT=${iport}|" "$UNIT" 2>/dev/null
    sed -i "s|^Environment=OQLOS_MODBUS_DEVICE_ID=.*|Environment=OQLOS_MODBUS_DEVICE_ID=${idev}|" "$UNIT" 2>/dev/null
  fi
  echo "  Reloading + restarting oqlos-hardware-api…"
  systemctl --user daemon-reload 2>/dev/null
  systemctl --user restart oqlos-hardware-api.service 2>/dev/null; sleep 4
  hdr "RE-VERIFY"; FAILED_MODBUS=0; phase_test
}

# --- run selected mode -----------------------------------------------------
echo "OqlOS .122 hardware procedure — mode=$MODE  api=$API"
case "$MODE" in
  test)     phase_test ;;
  diagnose) phase_test; phase_diagnose ;;
  fix)      phase_test; phase_diagnose; phase_fix ;;
  *) echo "usage: $0 [test|diagnose|fix]"; exit 2 ;;
esac
echo
[ "$FAILED_MODBUS" = 1 ] && echo "Result: some peripherals need attention (see above)." || echo "Result: all probed peripherals healthy."
exit 0
