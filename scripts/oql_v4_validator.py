#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oqlos.core.oql_versioning import OQL_VERSION_CURRENT

try:
    from .oql_validator_common import (
        build_api_fallback_urls as _build_api_fallback_urls,  # noqa: F401
        extract_code_from_json as _extract_code_from_json,  # noqa: F401
        fetch_url as _fetch_url,  # noqa: F401
        load_source as _load_source,  # noqa: F401
        looks_like_html as _looks_like_html,
        run_validator_cli,
    )
except ImportError:  # pragma: no cover - direct script execution
    from oql_validator_common import (
        build_api_fallback_urls as _build_api_fallback_urls,  # noqa: F401
        extract_code_from_json as _extract_code_from_json,  # noqa: F401
        fetch_url as _fetch_url,  # noqa: F401
        load_source as _load_source,  # noqa: F401
        looks_like_html as _looks_like_html,
        run_validator_cli,
    )


@dataclass
class Issue:
    rule: str
    severity: str
    message: str
    line: int | None = None
    suggestion: str | None = None


def _line_number(lines: list[str], idx: int) -> int:
    return idx + 1


def _validate_version_header(lines: list[str]) -> list[Issue]:
    """Check that the first meaningful line is 'VERSION: <current>'."""
    version_label = f"VERSION: {OQL_VERSION_CURRENT}"
    version_idx: int | None = None
    issues: list[Issue] = []
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
    return issues


def _validate_line_v4(raw: str, ln: int, patterns: dict) -> list[Issue]:
    """Validate a single OQL v4 source line against known anti-patterns."""
    issues: list[Issue] = []
    if patterns["goal"].match(raw) and not patterns["goal_only"].match(raw):
        issues.append(
            Issue(
                rule="goal_inline_name",
                severity="error",
                line=ln,
                message="Use GOAL: on its own line, then SET NAME '...'.",
                suggestion="Replace 'GOAL: <name>' with 'GOAL:' and add next line '  SET NAME '<name>''",
            )
        )
    if patterns["loop"].match(raw):
        issues.append(
            Issue(
                rule="loop_deprecated",
                severity="error",
                line=ln,
                message="LOOP is deprecated in VERSION: 4",
                suggestion="Use 'REPEAT X:'",
            )
        )
    if patterns["repeats"].match(raw):
        issues.append(
            Issue(
                rule="repeats_typo",
                severity="error",
                line=ln,
                message="Use REPEAT, not REPEATS",
                suggestion="Replace with 'REPEAT X:'",
            )
        )
    stripped_upper = raw.strip().upper()
    if (
        stripped_upper != "REPEAT STOP"
        and stripped_upper.startswith("REPEAT ")
        and not patterns["repeat_start"].match(raw)
    ):
        issues.append(
            Issue(
                rule="repeat_format",
                severity="error",
                line=ln,
                message="Invalid REPEAT syntax",
                suggestion="Use 'REPEAT X:' or 'REPEAT STOP'",
            )
        )
    return issues


def _validate_goal_set_name(lines: list[str], patterns: dict) -> list[Issue]:
    """Check that each GOAL: block is followed immediately by SET NAME '...'."""
    issues: list[Issue] = []
    for i, raw in enumerate(lines):
        if not patterns["goal_only"].match(raw):
            continue
        j = i + 1
        while j < len(lines):
            nxt = lines[j].strip()
            if not nxt or nxt.startswith("#"):
                j += 1
                continue
            if not patterns["set_name"].match(lines[j]):
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


def _validate_structure(text: str) -> list[Issue]:
    issues: list[Issue] = []
    lines = text.splitlines()
    patterns = {
        "goal": re.compile(r"^\s*GOAL\s*:\s*(.+)$", re.IGNORECASE),
        "goal_only": re.compile(r"^\s*GOAL\s*:\s*$", re.IGNORECASE),
        "set_name": re.compile(r"^\s*SET\s+NAME\s+['\"].+['\"]\s*$", re.IGNORECASE),
        "loop": re.compile(r"^\s*LOOP\b", re.IGNORECASE),
        "repeats": re.compile(r"^\s*REPEATS\b", re.IGNORECASE),
        "repeat_start": re.compile(r"^\s*REPEAT\s+\d+\s*:\s*$", re.IGNORECASE),
    }
    issues.extend(_validate_version_header(lines))
    for i, raw in enumerate(lines):
        issues.extend(_validate_line_v4(raw, _line_number(lines, i), patterns))
    issues.extend(_validate_goal_set_name(lines, patterns))
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
    return run_validator_cli("Validate OQL VERSION: 4 compatibility", validate_oql_v4)


if __name__ == "__main__":
    raise SystemExit(main())
