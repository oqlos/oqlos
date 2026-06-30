#!/usr/bin/env bash
# Generuje manifest sha256 pakietu oqlos/ do weryfikacji integralności po wdrożeniu.
#
# Uruchamiać na ŹRÓDLE (kontroler/pi109) PRZED `redeploy run redeploy/122/migration.md`.
# Wynik trafia do oqlos/_CHECKSUMS.sha256 i jedzie z rsync (krok sync_oqlos_core) na Pi,
# gdzie krok `assert-oqlos-checksum` robi `sha256sum -c` na wdrożonych plikach.
#
# Wykluczenia muszą się zgadzać z rsync w migration.md, inaczej manifest wskaże fałszywe braki.

set -euo pipefail

PKG="$(cd "$(dirname "$0")/.." && pwd)/oqlos"
OUT="$PKG/_CHECKSUMS.sha256"

[ -d "$PKG" ] || { echo "FAIL: brak pakietu $PKG" >&2; exit 2; }

cd "$PKG"
# Ścieżki względne (./...), posortowane → deterministyczny manifest.
# Hashujemy TYLKO kod (.py, .html) — pomijamy scenariusze (.oql), dokumentację (.md),
# konfiguracje (.connectgo, .yaml, .json) i cache. Dzięki temu zmiana konfiguracji
# nie powoduje fałszywego FAIL integralności po wdrożeniu.
find . -type f \( -name '*.py' -o -name '*.html' \) \
  ! -path '*/__pycache__/*' ! -name '*.pyc' ! -name '*.pyo' \
  ! -path '*/.pytest_cache/*' \
  -exec sha256sum {} \; | LC_ALL=C sort -k2 > "$OUT"

echo "PASS: wygenerowano $(wc -l < "$OUT") haszy sha256 -> ${OUT}"
