#!/usr/bin/env bash
# End-to-end test wdrożonego węzła sprzętowego (Raspberry Pi) z kontrolera/dev-hosta.
#
# Sprawdza po kolei:
#   1. łączność (ping + ssh) z Pi,
#   2. usługi węzła (mosquitto :1883, agent oqlos :8202, sidecar Tic :8205),
#   3. integralność wdrożonego pakietu oqlos/ (sha256, przez verify-rpi-checksum.sh),
#   4. pełny smoke-test osprzętu (blok `assert-hw-node-healthy` z migration.md, odpalany NA Pi:
#      /health, hardware/health, identify, Modbus ADC, oraz round-tripy OQL-over-MQTT:
#      ping, health, usb-list, pi-diagnostics, hui-actions, lung-disable).
#
# Bezpieczeństwo: test jest read-only + de-energize (lung-disable / hui-al-stop). NIE rusza
# pompą ani zaworami. Tic249 po teście pozostaje energized=false.
#
# Użycie:
#   scripts/test-hardware.sh [pi@host]
#   PIHW_ALLOW_MISSING_HARDWARE=0 scripts/test-hardware.sh   # twardo wymagaj wszystkich peryferiów
#
# Exit 0 = wszystko OK; 1 = wykryto błędy; 2 = problem środowiska (brak ssh / katalogu).

set -uo pipefail

PI="${1:-${OQL_PI:-pi@boardnet.local}}"
HOST="${PI#*@}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
MIGRATION="$ROOT/redeploy/122/migration.md"
ALLOW_MISSING="${PIHW_ALLOW_MISSING_HARDWARE:-1}"
SSH=(ssh -o ConnectTimeout=10 -o BatchMode=yes "$PI")

bold(){ printf '\033[1m%s\033[0m\n' "$*"; }
say(){  printf '\033[36m▸ %s\033[0m\n' "$*"; }
ok(){   printf '\033[32m✓ %s\033[0m\n' "$*"; }
warn(){ printf '\033[33m! %s\033[0m\n' "$*"; }
err(){  printf '\033[31m✗ %s\033[0m\n' "$*" >&2; }

rc=0

# --- 1. łączność -----------------------------------------------------------
bold "[1/4] Łączność z $PI"
if ping -c1 -W2 "$HOST" >/dev/null 2>&1; then ok "ping $HOST"; else err "ping $HOST nieosiągalny"; exit 2; fi
if "${SSH[@]}" true 2>/dev/null; then ok "ssh $PI"; else err "ssh $PI nie działa (klucz?)"; exit 2; fi

# --- 2. usługi -------------------------------------------------------------
bold "[2/4] Usługi węzła"
ports_out="$("${SSH[@]}" '
  for P in 1883 8202 8205; do
    ss -ltn "sport = :$P" 2>/dev/null | grep -q ":$P" && echo "$P up" || echo "$P down"
  done' 2>/dev/null)"
while read -r port state; do
  case "$port:$state" in
    1883:up) ok "broker mosquitto :1883";;
    8202:up) ok "agent oqlos :8202 (loopback)";;
    8205:up) ok "sidecar Tic T249 :8205";;
    *:down)  warn "port :$port nieaktywny";;
  esac
done <<< "$ports_out"

# --- 3. integralność (sha256) ----------------------------------------------
bold "[3/4] Integralność pakietu oqlos/ (sha256)"
if "$HERE/verify-rpi-checksum.sh" "$PI" >/tmp/test-hw-checksum.log 2>&1; then
  ok "$(grep -E 'PASS|identyczny|zgodna' /tmp/test-hw-checksum.log | tail -1)"
else
  err "weryfikacja sumy kontrolnej NIE przeszła:"; sed -n '1,15p' /tmp/test-hw-checksum.log >&2; rc=1
fi

# --- 4. smoke-test osprzętu ------------------------------------------------
bold "[4/4] Smoke-test osprzętu (assert-hw-node-healthy @ $PI)"
[ -f "$MIGRATION" ] || { err "brak $MIGRATION"; exit 2; }
SMOKE=/tmp/test-hw-smoke.sh
awk '/```bash markpact:ref assert-hw-node-healthy/{f=1;next} f&&/^```/{f=0} f' "$MIGRATION" > "$SMOKE"
[ -s "$SMOKE" ] || { err "nie udało się wyciągnąć bloku assert-hw-node-healthy z migracji"; exit 2; }
if scp -q -o ConnectTimeout=10 -o BatchMode=yes "$SMOKE" "$PI:/tmp/oqlos-smoke.sh"; then
  "${SSH[@]}" "export XDG_RUNTIME_DIR=/run/user/\$(id -u); PIHW_ALLOW_MISSING_HARDWARE=$ALLOW_MISSING bash /tmp/oqlos-smoke.sh"
  smoke_rc=$?
  if [ "$smoke_rc" -eq 0 ]; then ok "smoke-test PASS"; else err "smoke-test FAIL (rc=$smoke_rc)"; rc=1; fi
else
  err "nie udało się wysłać smoke-testu na $PI"; rc=1
fi

echo "----"
if [ "$rc" -eq 0 ]; then ok "WĘZEŁ SPRZĘTOWY OK ($PI)"; else err "WĘZEŁ SPRZĘTOWY: wykryto problemy ($PI)"; fi
exit "$rc"
