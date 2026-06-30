#!/usr/bin/env bash
# Weryfikacja sumą kontrolną (sha256): czy wdrożony pakiet oqlos/ na Pi sprzętowym
# jest identyczny z lokalnym źródłem. Projekt domyślnie syncuje przez rsync (rozmiar+mtime),
# co NIE wykrywa cichej korupcji treści — ten skrypt liczy i porównuje hasze obu stron.
#
# Użycie:
#   scripts/verify-rpi-checksum.sh [pi@host] [remote_pkg_dir]
# Domyślne:
#   pi@host        = $OQL_PI lub pi@boardnet.local
#   remote_pkg_dir = /home/pi/oqlos/oqlos/oqlos
#
# Exit 0 = identyczne; Exit 1 = wykryto rozbieżności (zmienione/brakujące/nadmiarowe pliki).

set -uo pipefail

PI="${1:-${OQL_PI:-pi@boardnet.local}}"
REMOTE_PKG="${2:-/home/pi/oqlos/oqlos/oqlos}"
SRC_PKG="$(cd "$(dirname "$0")/.." && pwd)/oqlos"

# Ten sam zestaw wykluczeń co rsync w migration.md (+ sam plik manifestu).
FIND_EXCL=(! -path '*/__pycache__/*' ! -name '*.pyc' ! -name '*.pyo'
           ! -path '*/.pytest_cache/*' ! -name '*.log' ! -name '_CHECKSUMS.sha256')

say(){ printf '\033[36m▸ %s\033[0m\n' "$*"; }
ok(){  printf '\033[32m✓ %s\033[0m\n' "$*"; }
err(){ printf '\033[31m✗ %s\033[0m\n' "$*" >&2; }

[ -d "$SRC_PKG" ] || { err "brak lokalnego pakietu: $SRC_PKG"; exit 2; }

say "lokalne źródło: $SRC_PKG"
say "zdalny pakiet:  $PI:$REMOTE_PKG"

local_manifest(){ ( cd "$SRC_PKG" && find . -type f "${FIND_EXCL[@]}" -exec sha256sum {} \; | sort -k2 ); }
remote_manifest(){
  ssh -o ConnectTimeout=10 -o BatchMode=yes "$PI" \
    "cd '$REMOTE_PKG' 2>/dev/null && find . -type f ! -path '*/__pycache__/*' ! -name '*.pyc' ! -name '*.pyo' ! -path '*/.pytest_cache/*' ! -name '*.log' ! -name '_CHECKSUMS.sha256' -exec sha256sum {} \\; | sort -k2"
}

LOCAL="$(local_manifest)"
REMOTE="$(remote_manifest)" || { err "nie udało się policzyć haszy na $PI (ssh / katalog?)"; exit 2; }

# Indeksy: ścieżka -> hash, dla precyzyjnej klasyfikacji rozbieżności.
declare -A LH RH
while read -r h p; do [ -n "${p:-}" ] && LH["$p"]="$h"; done <<< "$LOCAL"
while read -r h p; do [ -n "${p:-}" ] && RH["$p"]="$h"; done <<< "$REMOTE"

changed=0 missing=0 extra=0
for p in "${!LH[@]}"; do
  if [ -z "${RH[$p]:-}" ]; then
    echo "  BRAK na Pi:     ${p#./}"; missing=$((missing+1))
  elif [ "${LH[$p]}" != "${RH[$p]}" ]; then
    echo "  RÓŻNI SIĘ:      ${p#./}"; changed=$((changed+1))
  fi
done
for p in "${!RH[@]}"; do
  if [ -z "${LH[$p]:-}" ]; then
    echo "  NADMIAR na Pi:  ${p#./}"; extra=$((extra+1))
  fi
done

total_local=$(printf '%s\n' "$LOCAL" | grep -c . || true)
echo "----"
echo "plików lokalnie: $total_local · różni się: $changed · brak na Pi: $missing · nadmiar na Pi: $extra"

if [ "$changed" -eq 0 ] && [ "$missing" -eq 0 ]; then
  if [ "$extra" -gt 0 ]; then
    ok "PASS (z uwagą): treść wdrożonych plików zgodna; na Pi jest $extra dodatkowych plików (np. stare artefakty)."
  else
    ok "PASS: wdrożony pakiet oqlos/ jest identyczny ze źródłem (sha256)."
  fi
  exit 0
fi

err "FAIL: wykryto rozbieżność sumy kontrolnej (różni się=$changed, brak=$missing)."
exit 1
