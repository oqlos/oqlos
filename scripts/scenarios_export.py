#!/usr/bin/env python3
"""Export OQL scenarios from a running OqlOS instance.

Two modes:

1. Bulk export (all scenarios) into a ZIP archive::

       python3 scripts/scenarios_export.py --all --out scenarios.zip

   The archive contains one ``<scenario_id>.oql`` file per scenario plus a
   ``manifest.json`` with ``id``, ``title`` and basic metadata.

2. Single scenario export to a self-contained ``.oql.bash`` re-import script::

       python3 scripts/scenarios_export.py \
           --scenario ts-kaskadowy-cisnienie \
           --out ts-kaskadowy-cisnienie.oql.bash

   ``--scenario`` accepts either a scenario id or a UI URL like
   ``http://localhost:8096/scenarios?scenario=ts-kaskadowy-cisnienie``.

The generated ``.oql.bash`` is an executable bash script that, when run,
re-imports the scenario via ``PATCH /api/v3/data/test_scenarios/<id>``.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen


DEFAULT_BASE = "http://localhost:8096"
LIST_PATH = "/api/v3/data/test_scenarios"


def _list_url(base: str, limit: int = 10000) -> str:
    return f"{base.rstrip('/')}{LIST_PATH}?skip=0&limit={limit}"


def _row_url(base: str, sid: str) -> str:
    return f"{base.rstrip('/')}{LIST_PATH}/{sid}"


def _http_get_json(url: str, timeout: float = 20.0) -> dict[str, Any]:
    with urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _resolve_scenario_id(value: str) -> str:
    """Accept either a bare id or a UI URL with ``?scenario=<id>``."""
    if "://" not in value:
        return value.strip()
    parsed = urlparse(value)
    qs = parse_qs(parsed.query)
    if "scenario" in qs and qs["scenario"]:
        return qs["scenario"][0].strip()
    tail = parsed.path.rsplit("/", 1)[-1].strip()
    if tail:
        return tail
    raise ValueError(f"Cannot extract scenario id from URL: {value}")


def _fetch_all(base: str) -> list[dict[str, Any]]:
    payload = _http_get_json(_list_url(base))
    rows = payload.get("rows") or []
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


def _fetch_one(base: str, sid: str) -> dict[str, Any]:
    payload = _http_get_json(_row_url(base, sid))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected response for {sid}")
    if not payload.get("success", True):
        raise RuntimeError(f"API error for {sid}: {payload}")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    return data or {}


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(sid: str) -> str:
    name = _SAFE_NAME_RE.sub("-", sid).strip("-")
    return name or "scenario"


def export_all_zip(base: str, out_path: Path) -> dict[str, Any]:
    rows = _fetch_all(base)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for row in rows:
            sid = str(row.get("id") or "").strip()
            if not sid:
                skipped.append({"reason": "missing_id", "row": row})
                continue
            dsl = row.get("dsl")
            if not isinstance(dsl, str) or not dsl.strip():
                skipped.append({"id": sid, "reason": "no_dsl"})
                continue
            fname = f"{_safe_filename(sid)}.oql"
            zf.writestr(fname, dsl)
            written.append({
                "id": sid,
                "file": fname,
                "title": row.get("title"),
                "bytes": len(dsl.encode("utf-8")),
            })

        manifest = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "source": base.rstrip("/") + LIST_PATH,
            "scenarios": written,
            "skipped": skipped,
            "count": len(written),
        }
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    return {"out": str(out_path), "count": len(written), "skipped": skipped}


_BASH_TEMPLATE = """#!/usr/bin/env bash
# Auto-generated OQL scenario re-import script.
# Source : {source}
# Created: {created_at}
# Scenario: {sid}
# Title   : {title}
#
# Usage:
#   bash {filename}                 # re-import to default base
#   API_BASE=http://host:port bash {filename}
#   DRY_RUN=1 bash {filename}       # only print payload
set -euo pipefail

API_BASE="${{API_BASE:-{base}}}"
SCENARIO_ID="{sid}"
DRY_RUN="${{DRY_RUN:-0}}"

IFS= read -r -d '' OQL_DSL <<'__OQL_EOF__' || true
{dsl}
__OQL_EOF__
export OQL_DSL

PAYLOAD=$(python3 - <<'__PY__'
import json, os
print(json.dumps({{"dsl": os.environ.get("OQL_DSL", "")}}, ensure_ascii=False))
__PY__
)

if [ "$DRY_RUN" = "1" ]; then
  echo "$PAYLOAD"
  exit 0
fi

URL="$API_BASE/api/v3/data/test_scenarios/$SCENARIO_ID"
echo "PATCH $URL"
HTTP_CODE=$(curl -sS -o /tmp/oql_import_$$.json -w "%{{http_code}}" \\
    -X PATCH "$URL" \\
    -H 'Content-Type: application/json' \\
    --data-binary "$PAYLOAD")
echo "HTTP $HTTP_CODE"
cat /tmp/oql_import_$$.json
echo
rm -f /tmp/oql_import_$$.json
[ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]
"""


def export_one_bash(base: str, sid: str, out_path: Path) -> dict[str, Any]:
    data = _fetch_one(base, sid)
    dsl = data.get("dsl")
    if not isinstance(dsl, str) or not dsl.strip():
        raise RuntimeError(f"Scenario '{sid}' has no DSL to export")

    if "__OQL_EOF__" in dsl:
        raise RuntimeError("DSL contains the bash heredoc sentinel; refusing to embed")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = _BASH_TEMPLATE.format(
        source=_row_url(base, sid),
        created_at=datetime.now(timezone.utc).isoformat(),
        sid=sid,
        title=str(data.get("title") or "").replace("\n", " "),
        filename=out_path.name,
        base=base.rstrip("/"),
        dsl=dsl.rstrip() + "\n",
    )
    out_path.write_text(rendered, encoding="utf-8")
    try:
        os.chmod(out_path, 0o755)
    except OSError:
        pass
    return {"out": str(out_path), "id": sid, "bytes": len(rendered.encode("utf-8"))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default=DEFAULT_BASE, help=f"API base URL (default {DEFAULT_BASE})")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Export all scenarios to a ZIP archive")
    group.add_argument("--scenario", help="Scenario id or UI URL with ?scenario=<id>")
    parser.add_argument("--out", help="Output path (zip for --all, .oql.bash for --scenario)")
    args = parser.parse_args(argv)

    try:
        if args.all:
            out = Path(args.out or "scenarios.zip")
            report = export_all_zip(args.base, out)
        else:
            sid = _resolve_scenario_id(args.scenario)
            out = Path(args.out or f"{_safe_filename(sid)}.oql.bash")
            report = export_one_bash(args.base, sid, out)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2

    print(json.dumps({"ok": True, **report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
