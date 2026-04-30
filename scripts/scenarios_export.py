#!/usr/bin/env python3
"""Export/import OQL scenarios to/from a running OqlOS instance.

Export modes:

1. Bulk export (all scenarios) into a ZIP archive::

       python3 scripts/scenarios_export.py --all --out scenarios.zip

2. Single scenario export to a self-contained ``.oql.bash`` re-import script::

       python3 scripts/scenarios_export.py --scenario ts-kaskadowy-cisnienie --out ts.oql.bash

Import mode:

3. Import all ``.oql`` files from a directory into the database::

       python3 scripts/scenarios_export.py --import --dir ./scenarios

   Each file named ``<id>.oql`` updates the scenario ``<id>`` via PATCH.
   Files are validated against OQL v4 before import.
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
from urllib.error import HTTPError


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


def _http_patch_json(url: str, payload: dict[str, Any], timeout: float = 20.0) -> tuple[int, dict[str, Any]]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(url, data=data, method="PATCH", headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def _validate_oql_v4(dsl: str, source: str) -> tuple[bool, list[str]]:
    try:
        from oql_v4_validator import validate_oql_v4
        result = validate_oql_v4(dsl, source)
        if not result.get("valid"):
            errors = [f"{i.get('line', '?')}: {i.get('message', '')}" for i in result.get("issues", []) if i.get("severity") == "error"]
            return False, errors
        return True, []
    except Exception as e:
        return True, [f"Validation skipped: {e}"]


def import_scenarios(base: str, dir_path: Path, validate: bool = True) -> dict[str, Any]:
    imported: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    if not dir_path.is_dir():
        raise ValueError(f"Not a directory: {dir_path}")

    oql_files = sorted(dir_path.glob("*.oql"))

    for fpath in oql_files:
        sid = fpath.stem
        dsl = fpath.read_text(encoding="utf-8")
        if not dsl.strip():
            skipped.append({"id": sid, "reason": "empty_file"})
            continue

        if validate:
            valid, errors = _validate_oql_v4(dsl, str(fpath))
            if not valid:
                failed.append({"id": sid, "reason": "validation_failed", "errors": errors})
                continue

        url = _row_url(base, sid)
        try:
            code, resp = _http_patch_json(url, {"dsl": dsl})
            if code in (200, 201):
                imported.append({"id": sid, "status": code})
            else:
                failed.append({"id": sid, "status": code, "response": resp})
        except Exception as exc:
            failed.append({"id": sid, "error": str(exc)})

    return {"imported": imported, "failed": failed, "skipped": skipped, "count": len(imported)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default=DEFAULT_BASE, help=f"API base URL (default {DEFAULT_BASE})")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Export all scenarios to a ZIP archive")
    group.add_argument("--scenario", help="Scenario id or UI URL with ?scenario=<id>")
    group.add_argument("--import", action="store_true", dest="import_mode", help="Import .oql files from --dir")
    parser.add_argument("--dir", type=Path, default=Path("./scenarios"), help="Directory for import (default ./scenarios)")
    parser.add_argument("--no-validate", action="store_true", help="Skip OQL v4 validation during import")
    parser.add_argument("--out", help="Output path (zip for --all, .oql.bash for --scenario)")
    args = parser.parse_args(argv)

    try:
        if args.all:
            out = Path(args.out or "scenarios.zip")
            report = export_all_zip(args.base, out)
        elif args.import_mode:
            report = import_scenarios(args.base, args.dir, validate=not args.no_validate)
        else:
            sid = _resolve_scenario_id(args.scenario)
            out = Path(args.out or f"{_safe_filename(sid)}.oql.bash")
            report = export_one_bash(args.base, sid, out)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2

    print(json.dumps({"ok": True, **report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
