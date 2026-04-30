#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen


@dataclass
class Issue:
    rule: str
    severity: str
    message: str
    line: int | None = None
    suggestion: str | None = None


def _looks_like_html(text: str) -> bool:
    head = text.lstrip()[:500].lower()
    return head.startswith("<!doctype html") or head.startswith("<html")


def _fetch_url(url: str, timeout: float = 10.0) -> str:
    req = urlopen(url, timeout=timeout)
    payload = req.read().decode("utf-8", errors="replace")

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return payload

    code = _extract_code_from_json(parsed)
    if code is None:
        return payload
    return code


def _extract_code_from_json(data: Any) -> str | None:
    if isinstance(data, str):
        return data

    if isinstance(data, dict):
        if isinstance(data.get("code"), str):
            return data["code"]
        if isinstance(data.get("dsl"), str):
            return data["dsl"]
        scenario = data.get("scenario")
        if isinstance(scenario, dict):
            if isinstance(scenario.get("code"), str):
                return scenario["code"]
            if isinstance(scenario.get("dsl"), str):
                return scenario["dsl"]

    if isinstance(data, list):
        for item in data:
            code = _extract_code_from_json(item)
            if code:
                return code

    return None


def _build_api_fallback_urls(url: str) -> list[str]:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    scenario = (query.get("scenario") or [None])[0]
    if not scenario:
        return []

    base = f"{parsed.scheme}://{parsed.netloc}"
    out: list[str] = [
        f"{base}/api/v1/scenarios/{scenario}",
        f"{base}/api/v1/scenarios/{scenario}?{urlencode({'scenario': scenario})}",
        f"{base}/api/v1/scenarios/fetch?{urlencode({'scenario': scenario})}",
    ]

    dedup: list[str] = []
    seen: set[str] = set()
    for item in out:
        if item in seen:
            continue
        seen.add(item)
        dedup.append(item)
    return dedup


def _load_source(file_path: str | None, url: str | None) -> tuple[str, str]:
    if bool(file_path) == bool(url):
        raise ValueError("Provide exactly one of --file or --url")

    if file_path:
        text = Path(file_path).read_text(encoding="utf-8")
        return text, f"file:{file_path}"

    try:
        source_url = url or ""
        text = _fetch_url(source_url)
        if _looks_like_html(text):
            for candidate in _build_api_fallback_urls(source_url):
                try:
                    candidate_text = _fetch_url(candidate)
                except (HTTPError, URLError):
                    continue
                if _looks_like_html(candidate_text):
                    continue
                return candidate_text, f"url:{candidate} (fallback from {source_url})"
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"Cannot fetch URL {url}: {exc}") from exc
    return text, f"url:{url}"


def _line_number(idx: int) -> int:
    return idx + 1


def _validate_v2_structure(text: str) -> list[Issue]:
    issues: list[Issue] = []
    lines = text.splitlines()

    first_meaningful_idx: int | None = None
    first_meaningful: str | None = None
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        first_meaningful_idx = i
        first_meaningful = stripped
        break

    if first_meaningful and re.match(r"^VERSION\s*:\s*4\s*$", first_meaningful, re.IGNORECASE):
        issues.append(
            Issue(
                rule="already_v4",
                severity="warning",
                line=_line_number(first_meaningful_idx or 0),
                message="Scenario already declares VERSION: 4.",
                suggestion="Use scripts/oql_v4_validator.py for strict v4 checks.",
            )
        )

    goal_inline_pattern = re.compile(r"^\s*GOAL\s*:\s*(.+)$", re.IGNORECASE)
    goal_only_pattern = re.compile(r"^\s*GOAL\s*:\s*$", re.IGNORECASE)
    bracket_pattern = re.compile(r"\[[^\]]+\]")
    task_pattern = re.compile(r"^\s*TASK\s*:\s*", re.IGNORECASE)
    calc_pattern = re.compile(r"^\s*CALC\s+", re.IGNORECASE)
    val_pattern = re.compile(r"^\s*VAL\s+", re.IGNORECASE)
    if_cmp_pattern = re.compile(r"^\s*IF\s+\[[^\]]+\]\s+\[(<|>|<=|>=|=)\]\s+\[[^\]]+\]", re.IGNORECASE)
    else_error_pattern = re.compile(r'^\s*ELSE\s+ERROR\s+\[".+"\]\s*$', re.IGNORECASE)

    for i, raw in enumerate(lines):
        if goal_inline_pattern.match(raw) and not goal_only_pattern.match(raw):
            issues.append(
                Issue(
                    rule="goal_inline_name_legacy",
                    severity="error",
                    line=_line_number(i),
                    message="Legacy GOAL inline name detected.",
                    suggestion="Replace with 'GOAL:' + next line '  SET NAME ...'.",
                )
            )

        if task_pattern.match(raw):
            issues.append(
                Issue(
                    rule="task_legacy",
                    severity="error",
                    line=_line_number(i),
                    message="Legacy TASK command detected.",
                    suggestion="Replace TASK with explicit v4 commands (SET/WAIT/SAVE/LOG).",
                )
            )

        if calc_pattern.match(raw):
            issues.append(
                Issue(
                    rule="calc_legacy",
                    severity="error",
                    line=_line_number(i),
                    message="Legacy CALC command detected.",
                    suggestion="Replace with explicit v4 command flow or pre-defined FUNC/CALL.",
                )
            )

        if val_pattern.match(raw):
            issues.append(
                Issue(
                    rule="val_legacy",
                    severity="error",
                    line=_line_number(i),
                    message="Legacy VAL command detected.",
                    suggestion="Replace with GET/SAVE/LOG according to runtime intent.",
                )
            )

        if if_cmp_pattern.match(raw):
            issues.append(
                Issue(
                    rule="if_cmp_legacy",
                    severity="error",
                    line=_line_number(i),
                    message="Legacy IF comparator syntax detected (IF [x] [<] [y]).",
                    suggestion="Convert to v4 range syntax: IF sensor min .. max [unit] or CHECK ...",
                )
            )

        if else_error_pattern.match(raw):
            issues.append(
                Issue(
                    rule="else_error_legacy",
                    severity="error",
                    line=_line_number(i),
                    message="Legacy 'ELSE ERROR [...]' detected.",
                    suggestion="Use plain ERROR 'message' after CHECK/IF condition.",
                )
            )

        if bracket_pattern.search(raw):
            issues.append(
                Issue(
                    rule="bracket_tokens_legacy",
                    severity="warning",
                    line=_line_number(i),
                    message="Bracket token notation detected ([...]).",
                    suggestion="Normalize tokens to v4 form and keep quotes only for strings/names.",
                )
            )

    return issues


def validate_oql_v2_legacy(text: str, source: str = "<input>") -> dict[str, Any]:
    if _looks_like_html(text):
        issues = [
            Issue(
                rule="non_oql_payload",
                severity="error",
                message="Source returned HTML instead of OQL/JSON scenario payload.",
                suggestion=(
                    "Use an API endpoint returning scenario JSON (with 'code' or 'dsl'), "
                    "e.g. /api/v1/scenarios/{id} or /api/v1/scenarios/fetch."
                ),
            )
        ]
        return {
            "schema_version": "1.0",
            "validator": "oql_v2_validator",
            "source": source,
            "valid": False,
            "summary": {
                "errors": 1,
                "warnings": 0,
                "issues_total": 1,
            },
            "issues": [asdict(i) for i in issues],
            "migration_rules": {
                "target_version": "VERSION: 4",
                "goal_format": "GOAL: + SET NAME '...'; no inline GOAL name",
                "task_format": "Replace TASK with explicit commands",
                "condition_format": "Use IF sensor min .. max [unit] or CHECK min <= sensor <= max [unit]",
            },
        }

    issues = _validate_v2_structure(text)
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]

    return {
        "schema_version": "1.0",
        "validator": "oql_v2_validator",
        "source": source,
        "valid": len(errors) == 0,
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
            "issues_total": len(issues),
        },
        "issues": [asdict(i) for i in issues],
        "migration_rules": {
            "target_version": "VERSION: 4",
            "goal_format": "GOAL: + SET NAME '...'; no inline GOAL name",
            "task_format": "Replace TASK with explicit commands",
            "condition_format": "Use IF sensor min .. max [unit] or CHECK min <= sensor <= max [unit]",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate legacy OQL v2 patterns before migration to VERSION: 4")
    parser.add_argument("--file", help="Path to .oql file")
    parser.add_argument("--url", help="HTTP source with scenario content/code")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON report")
    args = parser.parse_args()

    try:
        text, source = _load_source(args.file, args.url)
        report = validate_oql_v2_legacy(text, source=source)
    except Exception as exc:
        print(json.dumps({"valid": False, "fatal": str(exc)}, ensure_ascii=False))
        return 2

    if args.pretty:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report, ensure_ascii=False))

    return 0 if report.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
