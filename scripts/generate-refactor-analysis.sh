#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_dir="${1:-$repo_root/project}"
analysis_tmp="$(mktemp -d /tmp/oqlos-refactor-analysis.XXXXXX)"

cleanup() {
  case "$analysis_tmp" in
    /tmp/oqlos-refactor-analysis.*) rm -rf -- "$analysis_tmp" ;;
    *) echo "Refusing to clean unexpected path: $analysis_tmp" >&2 ;;
  esac
}
trap cleanup EXIT

mkdir -p "$output_dir"
code2llm "$repo_root" \
  -m hybrid \
  -f toon,map \
  --strategy standard \
  --toon-yaml \
  --no-png \
  --no-cache \
  --no-chunk \
  -o "$analysis_tmp"

install -m 0644 "$analysis_tmp/analysis.toon.yaml" "$output_dir/analysis.toon.yaml"
install -m 0644 "$analysis_tmp/map.toon.yaml" "$output_dir/map.toon.yaml"
sed -i 's/[[:space:]]\+$//' \
  "$output_dir/analysis.toon.yaml" \
  "$output_dir/map.toon.yaml"
python "$repo_root/scripts/refactor_audit.py" \
  --root "$repo_root" \
  --output "$output_dir/refactor-audit.json"
