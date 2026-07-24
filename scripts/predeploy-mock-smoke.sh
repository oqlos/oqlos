#!/usr/bin/env bash
# Wrapper → c2004 predeploy mock smoke (UI + CLI against local :8202).
set -euo pipefail
C2004_SMOKE="${C2004_ROOT:-/home/tom/github/maskservice/c2004}/scripts/predeploy-mock-smoke.sh"
if [[ ! -x "$C2004_SMOKE" ]]; then
  echo "missing $C2004_SMOKE" >&2
  exit 1
fi
exec bash "$C2004_SMOKE" "$@"
