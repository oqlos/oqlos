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


def _to_v4_token(text: str) -> str:
    """Convert bracketed/multi-word identifier to v4: spaces replaced with underscores."""
    text = _normalize_bracket_tokens(text.strip())
    if not text:
        return text
    return text.replace(" ", "_")


def _bracket_tokens(text: str) -> list[str]:
    """Return the contents of [...] bracket groups in order; whitespace-stripped."""
    return [m.group(1).strip() for m in re.finditer(r"\[([^\]]+)\]", text)]


def _join_value_unit(value: str) -> str:
    """Collapse a numeric value + optional space-unit (e.g. '500 ms') into '500ms'."""
    cleaned = value.strip()
    # Match: number + space + rest (remove spaces from rest)
    match = re.match(r"^(-?\d+(?:[.,]\d+)?)\s+(.+)$", cleaned)
    if match:
        num = match.group(1)
        unit = match.group(2).strip()
        # Remove all spaces from unit (e.g., 'l/min' -> 'l/min', but '50 mbar' -> '50mbar')
        unit = unit.replace(" ", "")
        return f"{num}{unit}"
    # If no unit match, return as-is
    return cleaned


def _quote(value: str) -> str:
    safe = value.replace("'", "\\'")
    return f"'{safe}'"


def _extract_num_unit(value: str) -> tuple[str, str]:
    """Split '3.5mbar' into ('3.5', 'mbar'), or '100%' into ('100', '%)."""
    m = re.match(r"^(-?\d+(?:[.,]\d+)?)(.*)$", value.strip())
    if m:
        return m.group(1), m.group(2).strip()
    return value.strip(), ""


def _merge_minmax_to_if(lines: list[str]) -> list[str]:
    """
    Merge pairs of:
      __MINMAX__MIN__sensor__val
      __MINMAX__MAX__sensor__val
    into:
      IF sensor 'min .. max unit'
        CORRECT 'sensor w zakresie min..max unit'
        ERROR 'sensor poza zakresem min..max unit'
    If only MIN or only MAX present, emit a standalone IF.
    """
    # Parse marker
    def parse_marker(line: str):
        m = re.match(r"^\s*__MINMAX__(MIN|MAX)__([^_].+?)__(.+)$", line)
        if m:
            return m.group(1), m.group(2), m.group(3)
        return None

    result: list[str] = []
    i = 0
    while i < len(lines):
        p = parse_marker(lines[i])
        if p:
            kind1, sensor1, val1 = p
            # Look ahead for matching opposite on next non-empty line
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            p2 = parse_marker(lines[j]) if j < len(lines) else None
            if p2 and p2[1] == sensor1 and p2[0] != kind1:
                kind2, _, val2 = p2
                # Determine MIN/MAX values
                if kind1 == "MIN":
                    min_val, max_val = val1, val2
                else:
                    min_val, max_val = val2, val1
                num_min, unit_min = _extract_num_unit(min_val)
                num_max, unit_max = _extract_num_unit(max_val)
                unit = unit_min or unit_max
                range_str = f"{num_min} .. {num_max} {unit}".strip() if unit else f"{num_min} .. {num_max}"
                result.append(f"  IF '{sensor1}' '{range_str}'")
                result.append(f"    CORRECT '{sensor1} w zakresie {range_str}'")
                result.append(f"    ERROR '{sensor1} poza zakresem {range_str}'")
                i = j + 1
                continue
            else:
                # Only single MIN or MAX - emit simple IF
                num, unit = _extract_num_unit(val1)
                if kind1 == "MIN":
                    bound = f"{num} .. ∞"
                else:
                    bound = f"-∞ .. {num}"
                label = f"{bound} {unit}".strip() if unit else bound
                result.append(f"  IF '{sensor1}' '{label}'")
                result.append(f"    CORRECT '{sensor1} w zakresie {label}'")
                result.append(f"    ERROR '{sensor1} poza zakresem {label}'")
                i += 1
                continue
        result.append(lines[i])
        i += 1
    return result


def _rewrite_legacy_if(lines: list[str]) -> list[str]:
    """
    Rewrite legacy one-sided IF patterns:
      IF sensor val .. 999999   →  IF 'sensor' 'val .. ∞ unit'
      IF sensor -999999 .. val  →  IF 'sensor' '-∞ .. val unit'
    Also merge consecutive same-sensor pairs into a range IF.
    Skip lines with 'timeout', quoted ranges or ELSE (already v4 or special).
    """
    # Match: IF sensor lo .. hi  (no quotes around sensor, with sentinel 999999)
    pat = re.compile(
        r"^(\s*)IF\s+(['\"]?)(\S+)\2\s+(['\"]?)(-?[\d.]+\w*|-999999)\4\s*\.\.\s+(['\"]?)([\d.]+\w*|999999)\6\s*$",
        re.IGNORECASE,
    )

    def parse_if(line: str):
        m = pat.match(line)
        if not m:
            return None
        indent, _, sensor, _, lo, _, hi = m.groups()
        return indent, sensor, lo, hi

    result: list[str] = []
    i = 0
    while i < len(lines):
        p = parse_if(lines[i])
        if p:
            indent, sensor, lo, hi = p
            # Skip special sensors (already quoted ranges like 'timer')
            if sensor.startswith("'") or "timeout" in lines[i]:
                result.append(lines[i])
                i += 1
                continue

            # Look ahead for complementary IF on same sensor
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            p2 = parse_if(lines[j]) if j < len(lines) else None

            if p2 and p2[1] == sensor:
                # Merge pair into range
                _, _, lo2, hi2 = p2
                # Determine actual min/max
                lo_val = lo if lo != "-999999" else lo2
                hi_val = hi if hi != "999999" else hi2
                num_lo, unit_lo = _extract_num_unit(lo_val)
                num_hi, unit_hi = _extract_num_unit(hi_val)
                unit = unit_lo or unit_hi
                range_str = f"{num_lo} .. {num_hi} {unit}".strip() if unit else f"{num_lo} .. {num_hi}"
                result.append(f"{indent}IF '{sensor}' '{range_str}'")
                result.append(f"{indent}  CORRECT '{sensor} w zakresie {range_str}'")
                result.append(f"{indent}  ERROR '{sensor} poza zakresem {range_str}'")
                i = j + 1
                continue
            else:
                # Single-sided
                num_lo, unit_lo = _extract_num_unit(lo)
                num_hi, unit_hi = _extract_num_unit(hi)
                unit = unit_lo or unit_hi
                if hi in ("999999",) or hi.endswith("999999"):
                    bound = f"{num_lo} .. ∞"
                elif lo in ("-999999",) or lo.endswith("-999999"):
                    bound = f"-∞ .. {num_hi}"
                else:
                    bound = f"{num_lo} .. {num_hi}"
                label = f"{bound} {unit}".strip() if unit else bound
                result.append(f"{indent}IF '{sensor}' '{label}'")
                result.append(f"{indent}  CORRECT '{sensor} w zakresie {label}'")
                result.append(f"{indent}  ERROR '{sensor} poza zakresem {label}'")
                i += 1
                continue
        result.append(lines[i])
        i += 1
    return result


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

        # Keep brackets for multi-word identifiers, normalize for parsing
        normalized = _normalize_bracket_tokens(stripped)

        goal_match = re.match(r"^GOAL\s*:\s*(.+)$", normalized, re.IGNORECASE)
        if goal_match:
            name = goal_match.group(1).strip().strip("\"'")
            out.append("GOAL")
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
            sensor = _to_v4_token(sample_match.group(1))
            direction = sample_match.group(2).upper()
            interval_raw = sample_match.group(3)
            if interval_raw:
                interval = _join_value_unit(interval_raw)
                out.append(f"  SAMPLE {sensor} {direction} {interval}")
            else:
                out.append(f"  SAMPLE {sensor} {direction}")
            continue

        minmax_match = re.match(r"^(MIN|MAX)\s+(.+?)\s*=\s*(.+)$", stripped, re.IGNORECASE)
        if minmax_match:
            kind = minmax_match.group(1).upper()
            sensor = _to_v4_token(_normalize_bracket_tokens(minmax_match.group(2)))
            value = _normalize_bracket_tokens(minmax_match.group(3).strip())
            value_joined = _join_value_unit(value)
            out.append(f"  __MINMAX__{kind}__{sensor}__{value_joined}")
            continue

        # MIN/MAX without = (e.g., MIN przepływ 100 l/min)
        minmax_simple_match = re.match(r"^(MIN|MAX)\s+([^\s]+)\s+(.+)$", normalized, re.IGNORECASE)
        if minmax_simple_match:
            kind = minmax_simple_match.group(1).upper()
            sensor = _to_v4_token(minmax_simple_match.group(2))
            value = _normalize_bracket_tokens(minmax_simple_match.group(3).strip())
            value_joined = _join_value_unit(value)
            out.append(f"  __MINMAX__{kind}__{sensor}__{value_joined}")
            continue

        # Handle DELTA with = (e.g., DELTA ubytek = [0.5 l/min])
        delta_match = re.match(r"^DELTA\s+(.+?)\s*=\s*(.+)$", normalized, re.IGNORECASE)
        if delta_match:
            sensor = delta_match.group(1).strip()
            value = delta_match.group(2).strip()
            # Remove brackets from value if present
            value = _normalize_bracket_tokens(value)
            # Keep brackets for multi-word identifiers
            sensor_v4 = _to_v4_token(sensor)
            # Don't join value if it's already quoted
            if value.startswith("'") or value.startswith('"'):
                value_joined = value
            else:
                value_joined = _join_value_unit(value)
            out.append(f"  DELTA {sensor_v4} = {value_joined}")
            continue

        if re.match(r"^CALC\s+", normalized, re.IGNORECASE):
            out.append(f"  LOG {_quote(normalized)}")
            continue

        if re.match(r"^VAL\s+", normalized, re.IGNORECASE):
            out.append(f"  LOG {_quote(normalized)}")
            continue

        if_match = re.match(
            r"^IF\s+(\S.*?)\s+(<|>|<=|>=|=)\s+(.+)$",
            stripped,
            re.IGNORECASE,
        )
        if if_match:
            sensor = if_match.group(1).strip()
            op = if_match.group(2)
            value = if_match.group(3).strip()
            # Keep brackets for multi-word sensors
            sensor = _to_v4_token(sensor)
            # Remove brackets from value if present
            value = _normalize_bracket_tokens(value)
            # Don't join value if it's already quoted
            if value.startswith("'") or value.startswith('"'):
                value_joined = value
            else:
                value_joined = _join_value_unit(value)
            if op in {"<", "<="}:
                out.append(f"  IF {sensor} -999999 .. {value_joined}")
            elif op in {">", ">="}:
                out.append(f"  IF {sensor} {value_joined} .. 999999")
            else:
                out.append(f"  IF {sensor} {value_joined} .. {value_joined}")
            continue

        else_error_match = re.match(r'^ELSE\s+ERROR\s+"(.+)"$', normalized, re.IGNORECASE)
        if else_error_match:
            out.append(f"  ERROR {_quote(else_error_match.group(1))}")
            continue

        # Handle GOTO (not v4, convert to LOG with warning)
        goto_match = re.match(r"^GOTO\s+(.+)$", normalized, re.IGNORECASE)
        if goto_match:
            target = goto_match.group(1).strip()
            out.append(f"  LOG 'GOTO {target} - NOT SUPPORTED IN V4'")
            continue

        # Handle SAVE with bracketed label
        save_match = re.match(r"^SAVE\s+(.+)$", normalized, re.IGNORECASE)
        if save_match:
            label = save_match.group(1).strip()
            # Remove brackets from label if present
            label = _normalize_bracket_tokens(label)
            out.append(f"  SAVE {label}")
            continue

        # Handle ELSE INFO (not v4, convert to LOG with warning)
        else_info_match = re.match(r'^ELSE\s+INFO\s+"(.+)"$', normalized, re.IGNORECASE)
        if else_info_match:
            message = else_info_match.group(1)
            out.append(f"  LOG 'ELSE INFO: {_quote(message)} - NOT SUPPORTED IN V4'")
            continue

        # Handle SET NAME (special case - keep as-is)
        set_name_match = re.match(r"^SET\s+NAME\s+(.+)$", normalized, re.IGNORECASE)
        if set_name_match:
            value = set_name_match.group(1).strip()
            out.append(f"  SET NAME {value}")
            continue

        # Handle SET with = (e.g., SET [próg] = 50 mbar)
        if "=" in stripped and re.match(r"^SET\s+", stripped, re.IGNORECASE):
            # Split on first = to separate identifier and value
            parts = stripped.split("=", 1)
            if len(parts) == 2:
                identifier = parts[0].replace("SET", "", 1).strip()
                value = parts[1].strip()
                # Remove brackets from identifier if present
                identifier = _normalize_bracket_tokens(identifier)
                # Remove brackets from value if present
                value = _normalize_bracket_tokens(value)
                # Keep brackets for multi-word identifiers
                identifier_v4 = _to_v4_token(identifier)
                # Don't join value if it's already quoted
                if value.startswith("'") or value.startswith('"'):
                    value_joined = value
                else:
                    value_joined = _join_value_unit(value)
                out.append(f"  SET {identifier_v4} = {value_joined}")
                continue

        # Handle SET without = (e.g., SET [czujnik LP] 0, SET pompa 1)
        if re.match(r"^SET\s+", stripped, re.IGNORECASE) and "=" not in stripped:
            rest = re.sub(r"^SET\s+", "", stripped, flags=re.IGNORECASE)
            # Detect bracketed identifier: [foo bar] value
            bm = re.match(r"^\[([^\]]+)\]\s+(.+)$", rest)
            if bm:
                identifier = bm.group(1).strip()
                value = bm.group(2).strip()
            else:
                # Plain identifier: word value
                parts = rest.split(None, 1)
                if len(parts) == 2:
                    identifier = parts[0].strip()
                    value = parts[1].strip()
                else:
                    identifier = rest.strip()
                    value = ""
            # Convert identifier: spaces → underscores
            identifier_v4 = identifier.replace(" ", "_")
            # Remove brackets from value if present
            value = _normalize_bracket_tokens(value)
            # Don't join value if it's already quoted
            if value.startswith("'") or value.startswith('"'):
                value_joined = value
            else:
                value_joined = _join_value_unit(value)
            if value_joined:
                out.append(f"  SET {identifier_v4} {value_joined}")
            else:
                out.append(f"  SET {identifier_v4}")
            continue

        # Handle PUMP: PUMP off → SET PUMP 0, PUMP 10l → SET PUMP 10l
        pump_match = re.match(r"^PUMP\s+\[?([^\]]+)\]?$", normalized, re.IGNORECASE)
        if pump_match:
            value = _normalize_bracket_tokens(pump_match.group(1).strip())
            if value.lower() in {"off", "0"}:
                out.append("  SET PUMP 0")
            else:
                value_joined = _join_value_unit(value)
                out.append(f"  SET PUMP {value_joined}")
            continue

        if re.match(r"^(SCENARIO|VERSION|GOAL:|CONFIG|MACRO|FUNC:)\b", normalized, re.IGNORECASE):
            out.append(normalized)
        else:
            out.append(f"  {normalized}")

    # Post-process: merge adjacent __MINMAX__ markers into IF range + CORRECT/ERROR
    out = _merge_minmax_to_if(out)
    # Post-process: rewrite legacy IF sensor val .. 999999 patterns
    out = _rewrite_legacy_if(out)

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
