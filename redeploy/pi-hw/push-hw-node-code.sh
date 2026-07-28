#!/usr/bin/env bash
#
# Fast code-only redeploy of the OqlOS hardware node (pi-hw).
#
# For pure-Python changes (e.g. systemd_services.py, startup_diagnostics.py,
# new /api/v3/hardware routes) the service uses an editable install
# (`pip install -e .`), so pushing the changed files and restarting the
# --user service is enough — no venv rebuild.
#
# For full provisioning use the canonical c2004 deploy-fleet BoardNet wrapper.
#
# Usage:
#   redeploy/pi-hw/push-hw-node-code.sh [pi@host]
#   C2004_ROOT=/path/to/c2004 redeploy/pi-hw/push-hw-node-code.sh
#
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/"
C2004_ROOT="${C2004_ROOT:-$(cd "${SRC}/../.." && pwd)}"
BOARDNET_DEPLOY_ENV_FILE="${BOARDNET_DEPLOY_ENV_FILE:-${C2004_ROOT}/env.d/21-boardnet-redeploy.env}"

if [ -z "${1:-${PIHW:-}}" ]; then
  if [ ! -f "$BOARDNET_DEPLOY_ENV_FILE" ]; then
    echo "FAIL: pass pi@host or create ${BOARDNET_DEPLOY_ENV_FILE}" >&2
    exit 2
  fi
  set -a
  # shellcheck disable=SC1090
  . "$BOARDNET_DEPLOY_ENV_FILE"
  set +a
fi
unset BOARDNET_SSH_PASSWORD

PIHW="${1:-${PIHW:-${BOARDNET_SSH_USER:-pi}@${BOARDNET_IP:?BOARDNET_IP is required}}}"
BOARDNET_SSH_PORT="${BOARDNET_SSH_PORT:-22}"
BOARDNET_SSH_KEY="${BOARDNET_SSH_KEY:-$HOME/.ssh/id_ed25519}"
SSH=(ssh -p "$BOARDNET_SSH_PORT" -i "$BOARDNET_SSH_KEY" -o BatchMode=yes)
export RSYNC_RSH="ssh -p ${BOARDNET_SSH_PORT} -i ${BOARDNET_SSH_KEY} -o BatchMode=yes"
DST="~/oqlos/oqlos/"

echo "==> Pushing OqlOS core to ${PIHW}:${DST}"
rsync -az --delete \
  --exclude '.git' --exclude '.venv/' --exclude 'venv/' \
  --exclude '__pycache__/' --exclude '.pytest_cache/' \
  --exclude 'oql-run-logs/' --exclude 'iql-run-logs/' \
  "${SRC}" "${PIHW}:${DST}"

echo "==> Restarting oqlos-hardware-api (systemctl --user)"
"${SSH[@]}" "${PIHW}" 'systemctl --user daemon-reload; systemctl --user restart oqlos-hardware-api.service; sleep 2; systemctl --user is-active oqlos-hardware-api.service'

echo "==> Verifying new endpoints on the node (loopback :8202)"
"${SSH[@]}" "${PIHW}" '
  set -e
  echo "-- systemd/services --"
  curl -s -m 6 http://127.0.0.1:8202/api/v3/hardware/systemd/services | head -c 600; echo
  echo "-- startup-diagnostics --"
  curl -s -m 6 http://127.0.0.1:8202/api/v3/hardware/startup-diagnostics | head -c 600; echo
'

echo "==> Done. From pi109/desktop the same routes are reachable via the /api/v3/hardware proxy."
