#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from oqlos.core.interpreter import CqlInterpreter


@dataclass
class MigrationResult:
    scenario_id: str
    source: str
    changed: bool
    valid_after: bool
    errors_after: list[str]
    warnings_after: list[str]
    used_local_file: bool


def _fetch_json(url: str, timeout: float = 10.0) -> Any:
    req = Request(url, method="GET")
    with urlopen(req, timeout=timeout) as resp:
        payload = resp.read().decode("utf-8", errors="replace")
    return json.loads(payload)


def _send_json(url: str, method: str, payload: dict[str, Any], timeout: float = 10.0) -> Any:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        url,
        data=body,
        method=method.upper(),
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urlopen(req, timeout=timeout) as resp:
        data = resp.read().decode("utf-8", errors="replace")
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return {"raw": data}


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return [x for x in payload["rows"] if isinstance(x, dict)]
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    return []


def _normalize_bracket_tokens(text: str) -> str:
    return re.sub(r"\[([^\]]+)\]", lambda m: m.group(1).strip(), text)


def _bracket_tokens(text: str) -> list[str]:
    """Return the contents of [...] bracket groups in order; whitespace-stripped."""
    return [m.group(1).strip() for m in re.finditer(r"\[([^\]]+)\]", text)]


def _to_v4_token(name: str) -> str:
    """Wrap multi-word identifiers with [...] for v4, otherwise return as-is."""
    name = name.strip()
    if not name:
        return name
    if " " in name:
        return f"[{name}]"
    return name


def _join_value_unit(value: str) -> str:
    """Collapse a numeric value + optional space-unit (e.g. '500 ms') into '500ms'."""
    cleaned = value.strip()
    match = re.match(r"^(-?\d+(?:[.,]\d+)?)\s+([A-Za-z%/°²³µμ]+.*)$", cleaned)
    if match:
        return f"{match.group(1)}{match.group(2).strip()}"
    return cleaned.replace(" ", "")


def _quote(value: str) -> str:
    safe = value.replace("'", "\\'")
    return f"'{safe}'"


def migrate_v2_to_v4(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []

    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            out.append("")
            continue
        if stripped.startswith("#"):
            out.append(raw)
            continue

        normalized = _normalize_bracket_tokens(stripped)

        goal_match = re.match(r"^GOAL\s*:\s*(.+)$", normalized, re.IGNORECASE)
        if goal_match:
            name = goal_match.group(1).strip().strip("\"'")
            out.append("GOAL:")
            out.append(f"  SET NAME {_quote(name)}")
            continue

        if re.match(r"^TASK\s*:\s*", normalized, re.IGNORECASE):
            raw_task = re.sub(r"^TASK\s*:\s*", "", stripped, flags=re.IGNORECASE).strip()
            bracket = _bracket_tokens(raw_task)
            tokens = bracket or raw_task.split()
            verb = tokens[0].lower() if tokens else ""
            rest = tokens[1:]
            if verb in {"włącz", "wlacz", "on", "enable"} and rest:
                out.append(f"  SET {_to_v4_token(rest[0])} 1")
            elif verb in {"wyłącz", "wylacz", "off", "disable"} and rest:
                out.append(f"  SET {_to_v4_token(rest[0])} 0")
            elif verb in {"zapisz", "save"} and rest:
                label = "-".join(t.replace(" ", "_") for t in rest)
                out.append(f"  SAVE {label}")
            else:
                out.append(f"  LOG {_quote('TASK ' + raw_task)}")
            continue

        if re.match(r"^WAIT\s+", normalized, re.IGNORECASE):
            wait_raw = re.sub(r"^WAIT\s+", "", normalized, flags=re.IGNORECASE).strip()
            wait_body = _join_value_unit(wait_raw)
            out.append(f"  WAIT {wait_body}")
            continue

        sample_match = re.match(
            r"^SAMPLE\s+([^\s]+)\s+(START|STOP)(?:\s+(.+))?$",
            normalized,
            re.IGNORECASE,
        )
        if sample_match:
            sensor = sample_match.group(1)
            direction = sample_match.group(2).upper()
            interval_raw = sample_match.group(3)
            if interval_raw:
                interval = _join_value_unit(interval_raw)
                out.append(f"  SAMPLE {sensor} {direction} {interval}")
            else:
                out.append(f"  SAMPLE {sensor} {direction}")
            continue

        minmax_match = re.match(r"^(MIN|MAX)\s+([^\s]+)\s*=\s*(.+)$", normalized, re.IGNORECASE)
        if minmax_match:
            kind = minmax_match.group(1).upper()
            sensor = minmax_match.group(2)
            value = minmax_match.group(3).strip()
            out.append(f"  {kind} {sensor} {value}")
            continue

        if re.match(r"^CALC\s+", normalized, re.IGNORECASE):
            out.append(f"  LOG {_quote(normalized)}")
            continue

        if re.match(r"^VAL\s+", normalized, re.IGNORECASE):
            out.append(f"  LOG {_quote(normalized)}")
            continue

        if_match = re.match(
            r"^IF\s+([^\s]+)\s+(<|>|<=|>=|=)\s+([^\s]+)$",
            normalized,
            re.IGNORECASE,
        )
        if if_match:
            sensor = if_match.group(1)
            op = if_match.group(2)
            value = if_match.group(3)
            if op in {"<", "<="}:
                out.append(f"  IF {sensor} -999999 .. {value}")
            elif op in {">", ">="}:
                out.append(f"  IF {sensor} {value} .. 999999")
            else:
                out.append(f"  IF {sensor} {value} .. {value}")
            continue

        else_error_match = re.match(r'^ELSE\s+ERROR\s+"(.+)"$', normalized, re.IGNORECASE)
        if else_error_match:
            out.append(f"  ERROR {_quote(else_error_match.group(1))}")
            continue

        if re.match(r"^(SCENARIO|VERSION|GOAL:|CONFIG|MACRO|FUNC:)\b", normalized, re.IGNORECASE):
            out.append(normalized)
        else:
            out.append(f"  {normalized}")

    first_meaningful = next((x for x in out if x.strip() and not x.strip().startswith("#")), None)
    if not first_meaningful or not re.match(r"^VERSION\s*:\s*4\s*$", first_meaningful, re.IGNORECASE):
        out.insert(0, "VERSION: 4")

    return "\n".join(out).rstrip() + "\n"


def _validate_runtime(text: str, filename: str) -> tuple[bool, list[str], list[str]]:
    result = CqlInterpreter(mode="dry-run", quiet=True).run(text, filename)
    return bool(result.ok), [str(e) for e in (result.errors or [])], [str(w) for w in (result.warnings or [])]


def _pick_code(row: dict[str, Any]) -> str:
    for key in ("code", "dsl"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _build_write_payload(row: dict[str, Any], migrated_code: str) -> dict[str, Any]:
    payload = dict(row)
    payload["code"] = migrated_code
    return payload


def _build_write_url(template: str, scenario_id: str) -> str:
    if "{id}" in template:
        return template.format(id=scenario_id)
    sep = "&" if "?" in template else "?"
    return f"{template}{sep}{urlencode({'scenario': scenario_id})}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy OQL scenarios from DB payloads to VERSION: 4")
    parser.add_argument("--source-url", default="http://localhost:8100/connect-data/test-scenarios", help="GET endpoint returning rows/list")
    parser.add_argument("--scenario", help="Single scenario id filter (e.g. ts-temp-wilgotnosc)")
    parser.add_argument("--write-url", help="Write endpoint template, e.g. http://localhost:8101/api/v1/data/test_scenarios/{id}")
    parser.add_argument("--write-method", default="PATCH", help="HTTP method for write endpoint")
    parser.add_argument("--apply", action="store_true", help="Actually send updates to write endpoint")
    parser.add_argument("--prefer-local", action="store_true", help="Prefer local oqlos/scenarios/<id>.oql when available")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON report")
    args = parser.parse_args()

    try:
        payload = _fetch_json(args.source_url)
        rows = _extract_rows(payload)
    except (HTTPError, URLError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "fatal": f"Cannot fetch source rows: {exc}"}, ensure_ascii=False))
        return 2

    if args.scenario:
        rows = [r for r in rows if str(r.get("id") or "").strip() == args.scenario]

    base_dir = Path(__file__).resolve().parent.parent
    scenario_dir = base_dir / "oqlos" / "scenarios"

    results: list[MigrationResult] = []
    updates_preview: list[dict[str, Any]] = []
    updated_remote: list[dict[str, Any]] = []

    for row in rows:
        sid = str(row.get("id") or "").strip()
        if not sid:
            continue

        source_code = _pick_code(row)
        local_file = scenario_dir / f"{sid}.oql"

        used_local_file = False
        migrated_code = source_code

        if args.prefer_local and local_file.exists():
            migrated_code = local_file.read_text(encoding="utf-8")
            used_local_file = True
        else:
            migrated_code = migrate_v2_to_v4(source_code)

        changed = (migrated_code != source_code)
        valid_after, errors_after, warnings_after = _validate_runtime(migrated_code, sid)

        results.append(
            MigrationResult(
                scenario_id=sid,
                source="local_file" if used_local_file else "legacy_migration",
                changed=changed,
                valid_after=valid_after,
                errors_after=errors_after,
                warnings_after=warnings_after,
                used_local_file=used_local_file,
            )
        )

        if not changed:
            continue

        updates_preview.append(
            {
                "id": sid,
                "valid_after": valid_after,
                "used_local_file": used_local_file,
                "code_preview": migrated_code[:400],
            }
        )

        if args.apply:
            if not args.write_url:
                print(json.dumps({"ok": False, "fatal": "--apply requires --write-url"}, ensure_ascii=False))
                return 2

            write_url = _build_write_url(args.write_url, sid)
            payload_update = _build_write_payload(row, migrated_code)
            try:
                response = _send_json(write_url, args.write_method, payload_update)
                updated_remote.append({"id": sid, "write_url": write_url, "response": response})
            except (HTTPError, URLError, json.JSONDecodeError) as exc:
                updated_remote.append({"id": sid, "write_url": write_url, "error": str(exc)})

    report = {
        "ok": True,
        "source_url": args.source_url,
        "filtered_scenario": args.scenario,
        "apply": args.apply,
        "summary": {
            "rows_input": len(rows),
            "rows_changed": sum(1 for r in results if r.changed),
            "rows_valid_after": sum(1 for r in results if r.valid_after),
        },
        "results": [asdict(r) for r in results],
        "updates_preview": updates_preview,
        "updated_remote": updated_remote,
    }

    if args.pretty:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report, ensure_ascii=False))

    if any(not r.valid_after for r in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
