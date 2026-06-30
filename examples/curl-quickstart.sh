#!/usr/bin/env bash
#
# OqlOS — curl + OQL quickstart.
#
# Exercises the HTTP surface of a running oqlos-server. Read-only probes run by
# default; motor/valve actuation is gated behind OQL_ACTUATE=1 so this script
# never moves real hardware by accident.
#
# Usage:
#   BASE=http://127.0.0.1:8202 bash examples/curl-quickstart.sh        # read-only
#   OQL_ACTUATE=1 bash examples/curl-quickstart.sh                     # also actuate (mock-safe)
#
# Tip: start a mock server first —
#   OQLOS_HARDWARE_MODE=mock oqlos-server --host 127.0.0.1 --port 8202
#
set -uo pipefail

BASE="${BASE:-http://127.0.0.1:8202}"
ACTUATE="${OQL_ACTUATE:-0}"
JQ() { command -v jq >/dev/null 2>&1 && jq -C . || cat; }

hr() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
req() { # METHOD URL [label]
  local m="$1" url="$2" label="${3:-$2}"
  printf '\033[36m%s\033[0m %s\n' "$m" "$label"
  curl -s -X "$m" "$url" | JQ
}

if ! curl -sf "$BASE/health" >/dev/null 2>&1; then
  echo "FATAL: no server at $BASE — start one with:" >&2
  echo "  OQLOS_HARDWARE_MODE=mock oqlos-server --host 127.0.0.1 --port 8202" >&2
  exit 1
fi

hr "Status & identity (read-only)"
req GET "$BASE/api/v1/health"               "/api/v1/health"
req GET "$BASE/api/v1/hardware/identify"    "/api/v1/hardware/identify"
req GET "$BASE/api/v1/hardware/temperature" "/api/v1/hardware/temperature"
req GET "$BASE/api/v1/hardware/diagnose"    "/api/v1/hardware/diagnose"
req GET "$BASE/api/v1/plugins"              "/api/v1/plugins"

hr "Sensors (read-only)"
req GET "$BASE/api/v1/hardware/sensor/AI01" "/api/v1/hardware/sensor/AI01"

hr "OQL over MQTT via REST (needs role=controller + broker)"
echo "# kind: command | script | manage | ping  — body is JSON"
curl -s -X POST "$BASE/api/v1/oql/execute" -H 'Content-Type: application/json' \
  -d '{"oql":"SET \"pompa-1\" \"5.0 l/min\"","kind":"command","mode":"execute"}' | JQ
curl -s -X POST "$BASE/api/v1/oql/manage" -H 'Content-Type: application/json' \
  -d '{"verb":"identify","args":{"scan":"never"}}' | JQ
echo "# (role=off → {\"detail\":\"OQL MQTT transport is disabled (role=off)\"} — expected on an agent/standalone node)"

if [ "$ACTUATE" != "1" ]; then
  hr "Actuation skipped"
  echo "Set OQL_ACTUATE=1 to run pump/valve/lung commands (mock-safe; MOVES real hardware on a real node)."
  exit 0
fi

hr "PUMP (DRI0050) — power %"
req POST "$BASE/api/v1/hardware/pump?power_pct=50" "/api/v1/hardware/pump?power_pct=50"
req POST "$BASE/api/v1/hardware/pump?power_pct=0"  "/api/v1/hardware/pump?power_pct=0"

hr "VALVE (Modbus IO) — value=true|false"
req POST "$BASE/api/v1/hardware/valve/V1?value=true"  "/api/v1/hardware/valve/V1?value=true"
req POST "$BASE/api/v1/hardware/valve/V1?value=false" "/api/v1/hardware/valve/V1?value=false"

hr "LUNG (Tic T249) — reciprocate then stop"
req POST "$BASE/api/v1/hardware/lung?steps=500&speed=1000&cycles=3&pause=0.5" "/api/v1/hardware/lung?steps=500&speed=1000&cycles=3&pause=0.5"
req POST "$BASE/api/v1/hardware/lung/stop"    "/api/v1/hardware/lung/stop"
req POST "$BASE/api/v1/hardware/lung/disable" "/api/v1/hardware/lung/disable   # de-energize"

echo
echo "Done. For the OQL language itself (.oql files), run:"
echo "  oqlctl -m dry-run oqlos/scenarios/test-pompy.oql"
