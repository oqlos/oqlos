#!/usr/bin/env bash
# Example OqlOS hardware operator workflow.
#
# This script is intentionally conservative: it runs detection and doctor first,
# then stops before any scenario execution when doctor reports errors or warnings.

set -euo pipefail

FIRMWARE_URL="${FIRMWARE_URL:-http://localhost:8202}"
CONFIG_PATH="${CONFIG_PATH:-oqlos.yaml}"
SCENARIO="${SCENARIO:-oqlos/oql-scenario/hardware-diagnostics.oql}"
if [[ -z "${OQLCTL:-}" ]]; then
  if [[ -x ".venv/bin/oqlctl" ]]; then
    OQLCTL=".venv/bin/oqlctl"
  else
    OQLCTL="oqlctl"
  fi
fi

echo "== OqlOS smart detect =="
"$OQLCTL" detect --firmware-url "$FIRMWARE_URL" --config "$CONFIG_PATH"

echo
echo "== OqlOS doctor =="
doctor_json="$(mktemp)"
"$OQLCTL" doctor --json --firmware-url "$FIRMWARE_URL" --config "$CONFIG_PATH" > "$doctor_json"

python - "$doctor_json" <<'PY'
import json
import sys

path = sys.argv[1]
report = json.load(open(path, encoding="utf-8"))
summary = report["summary"]
print(f"status={report['status']} errors={summary['errors']} warnings={summary['warnings']}")
for issue in report["issues"]:
    print(f"[{issue['severity']}] {issue['code']}: {issue['message']}")
if summary["errors"]:
    sys.exit(2)
if report["status"] != "ok":
    print("doctor needs attention; keep execute mode disabled until warnings are reviewed")
    sys.exit(3)
PY

echo
echo "== Dry-run scenario =="
"$OQLCTL" "$SCENARIO" --mode dry-run --skip-waits

echo
echo "Doctor reported no blocking errors. Review warnings before execute mode."
echo "To execute manually:"
echo "  HARDWARE_MODE=real $OQLCTL \"$SCENARIO\" --mode execute"
