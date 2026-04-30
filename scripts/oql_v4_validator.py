#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from urllib.error import URLError, HTTPError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen

from oqlos.core.oql_versioning import OQL_VERSION_CURRENT


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

    # keep order, remove duplicates
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


def _line_number(lines: list[str], idx: int) -> int:
    return idx + 1


def _validate_structure(text: str) -> list[Issue]:
    issues: list[Issue] = []
    lines = text.splitlines()

    # VERSION must be present and should be first non-empty/non-comment line
    version_label = f"VERSION: {OQL_VERSION_CURRENT}"
    version_idx: int | None = None
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if re.match(rf"^VERSION\s*:\s*{OQL_VERSION_CURRENT}\s*$", stripped, re.IGNORECASE):
            version_idx = i
        else:
            issues.append(
                Issue(
                    rule="version_first_line",
                    severity="error",
                    line=_line_number(lines, i),
                    message=f"First meaningful line must be '{version_label}'",
                    suggestion=f"Add '{version_label}' as the first non-comment line",
                )
            )
        break

    if version_idx is None:
        issues.append(
            Issue(
                rule="version_present",
                severity="error",
                message=f"Missing '{version_label}'",
                suggestion=f"Set scenario header to {version_label}",
            )
        )

    goal_pattern = re.compile(r"^\s*GOAL\s*:\s*(.+)$", re.IGNORECASE)
    goal_only_pattern = re.compile(r"^\s*GOAL\s*:\s*$", re.IGNORECASE)
    set_name_pattern = re.compile(r"^\s*SET\s+NAME\s+['\"].+['\"]\s*$", re.IGNORECASE)
    loop_pattern = re.compile(r"^\s*LOOP\b", re.IGNORECASE)
    repeats_pattern = re.compile(r"^\s*REPEATS\b", re.IGNORECASE)
    repeat_start_pattern = re.compile(r"^\s*REPEAT\s+\d+\s*:\s*$", re.IGNORECASE)

    for i, raw in enumerate(lines):
        if goal_pattern.match(raw) and not goal_only_pattern.match(raw):
            issues.append(
                Issue(
                    rule="goal_inline_name",
                    severity="error",
                    line=_line_number(lines, i),
                    message="Use GOAL: on its own line, then SET NAME '...'.",
                    suggestion="Replace 'GOAL: <name>' with 'GOAL:' and add next line '  SET NAME '<name>''",
                )
            )

        if loop_pattern.match(raw):
            issues.append(
                Issue(
                    rule="loop_deprecated",
                    severity="error",
                    line=_line_number(lines, i),
                    message="LOOP is deprecated in VERSION: 4",
                    suggestion="Use 'REPEAT X:'",
                )
            )

        if repeats_pattern.match(raw):
            issues.append(
                Issue(
                    rule="repeats_typo",
                    severity="error",
                    line=_line_number(lines, i),
                    message="Use REPEAT, not REPEATS",
                    suggestion="Replace with 'REPEAT X:'",
                )
            )

        if raw.strip().upper() == "REPEAT STOP":
            # valid in v4, no issue
            pass
        elif raw.strip().upper().startswith("REPEAT ") and not repeat_start_pattern.match(raw):
            issues.append(
                Issue(
                    rule="repeat_format",
                    severity="error",
                    line=_line_number(lines, i),
                    message="Invalid REPEAT syntax",
                    suggestion="Use 'REPEAT X:' or 'REPEAT STOP'",
                )
            )

    # GOAL must start with SET NAME
    for i, raw in enumerate(lines):
        if goal_only_pattern.match(raw):
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if not nxt or nxt.startswith("#"):
                    j += 1
                    continue
                if not set_name_pattern.match(lines[j]):
                    issues.append(
                        Issue(
                            rule="goal_set_name",
                            severity="error",
                            line=_line_number(lines, j),
                            message="First command in GOAL should be SET NAME '...'.",
                            suggestion="Add 'SET NAME' as first command after GOAL:",
                        )
                    )
                break

    return issues


def _validate_runtime(text: str, filename: str) -> list[Issue]:
    issues: list[Issue] = []
    try:
        from oqlos.core.interpreter import CqlInterpreter
    except Exception as exc:  # pragma: no cover
        return [
            Issue(
                rule="runtime_import",
                severity="warning",
                message=f"Cannot import runtime interpreter: {exc}",
            )
        ]

    try:
        interp = CqlInterpreter(mode="dry-run", quiet=True)
        result = interp.run(text, filename)
        if not result.ok:
            issues.append(
                Issue(
                    rule="runtime_dry_run",
                    severity="error",
                    message="Interpreter dry-run failed",
                    suggestion="Fix parser/runtime issues reported by interpreter",
                )
            )
        for err in getattr(result, "errors", []) or []:
            issues.append(Issue(rule="runtime_error", severity="error", message=str(err)))
        for warn in getattr(result, "warnings", []) or []:
            issues.append(Issue(rule="runtime_warning", severity="warning", message=str(warn)))
    except Exception as exc:
        issues.append(
            Issue(
                rule="runtime_exception",
                severity="error",
                message=f"Interpreter exception: {exc}",
            )
        )

    return issues


def validate_oql_v4(text: str, source: str = "<input>") -> dict[str, Any]:
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
            "validator": "oql_v4_validator",
            "source": source,
            "valid": False,
            "summary": {
                "errors": 1,
                "warnings": 0,
                "issues_total": 1,
            },
            "issues": [asdict(i) for i in issues],
            "migration_rules": {
                "version": f"VERSION: {OQL_VERSION_CURRENT}",
                "goal_format": "GOAL: + SET NAME '...'",
                "loop_format": "REPEAT X: ... REPEAT STOP",
                "set_format": "SET 'target' 'value' (scenario files)",
            },
        }

    issues = _validate_structure(text)
    issues.extend(_validate_runtime(text, source))

    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]

    return {
        "schema_version": "1.0",
        "validator": "oql_v4_validator",
        "source": source,
        "valid": len(errors) == 0,
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
            "issues_total": len(issues),
        },
        "issues": [asdict(i) for i in issues],
        "migration_rules": {
            "version": f"VERSION: {OQL_VERSION_CURRENT}",
            "goal_format": "GOAL: + SET NAME '...'",
            "loop_format": "REPEAT X: ... REPEAT STOP",
            "set_format": "SET 'target' 'value' (scenario files)",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate OQL VERSION: 4 compatibility")
    parser.add_argument("--file", help="Path to .oql file")
    parser.add_argument("--url", help="HTTP source with scenario content/code")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON report")
    args = parser.parse_args()

    try:
        text, source = _load_source(args.file, args.url)
        report = validate_oql_v4(text, source=source)
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
