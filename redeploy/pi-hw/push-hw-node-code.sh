#!/usr/bin/env bash
#
# Fast code-only redeploy of the OqlOS hardware node (pi-hw).
#
# For pure-Python changes (e.g. systemd_services.py, startup_diagnostics.py,
# new /api/v3/hardware routes) the service uses an editable install
# (`pip install -e .`), so pushing the changed files and restarting the
# --user service is enough — no venv rebuild.
#
# For the full first-time provisioning use:  redeploy run redeploy/pi-hw/migration.md
#
# Usage:
#   redeploy/pi-hw/push-hw-node-code.sh [pi@host]
#   PIHW=pi@192.168.188.110 redeploy/pi-hw/push-hw-node-code.sh
#
set -euo pipefail

PIHW="${1:-${PIHW:-pi@192.168.188.110}}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/"   # /home/tom/github/oqlos/oqlos/
DST="~/oqlos/oqlos/"

echo "==> Pushing OqlOS core to ${PIHW}:${DST}"
rsync -az --delete \
  --exclude '.git' --exclude '.venv/' --exclude 'venv/' \
  --exclude '__pycache__/' --exclude '.pytest_cache/' \
  --exclude 'oql-run-logs/' --exclude 'iql-run-logs/' \
  "${SRC}" "${PIHW}:${DST}"

echo "==> Restarting oqlos-hardware-api (systemctl --user)"
ssh "${PIHW}" 'systemctl --user daemon-reload; systemctl --user restart oqlos-hardware-api.service; sleep 2; systemctl --user is-active oqlos-hardware-api.service'

echo "==> Verifying new endpoints on the node (loopback :8202)"
ssh "${PIHW}" '
  set -e
  echo "-- systemd/services --"
  curl -s -m 6 http://127.0.0.1:8202/api/v3/hardware/systemd/services | head -c 600; echo
  echo "-- startup-diagnostics --"
  curl -s -m 6 http://127.0.0.1:8202/api/v3/hardware/startup-diagnostics | head -c 600; echo
'

echo "==> Done. From pi109/desktop the same routes are reachable via the /api/v3/hardware proxy."
