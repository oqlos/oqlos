#!/usr/bin/env python3
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

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


def _line_number(idx: int) -> int:
    return idx + 1


def _validate_version_header_v2(lines: list[str]) -> list[Issue]:
    """Warn if the first meaningful line already declares VERSION: 4 (wrong validator)."""
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
        return [
            Issue(
                rule="already_v4",
                severity="warning",
                line=_line_number(first_meaningful_idx or 0),
                message="Scenario already declares VERSION: 4.",
                suggestion="Use scripts/oql_v4_validator.py for strict v4 checks.",
            )
        ]
    return []


def _validate_line_v2(raw: str, ln: int, patterns: dict) -> list[Issue]:
    """Validate a single line for legacy v2 patterns."""
    issues: list[Issue] = []
    if patterns["goal_inline"].match(raw) and not patterns["goal_only"].match(raw):
        issues.append(
            Issue(
                rule="goal_inline_name_legacy",
                severity="error",
                line=ln,
                message="Legacy GOAL inline name detected.",
                suggestion="Replace with 'GOAL:' + next line '  SET NAME ...'.",
            )
        )
    if patterns["task"].match(raw):
        issues.append(
            Issue(
                rule="task_legacy",
                severity="error",
                line=ln,
                message="Legacy TASK command detected.",
                suggestion="Replace TASK with explicit v4 commands (SET/WAIT/SAVE/LOG).",
            )
        )
    if patterns["calc"].match(raw):
        issues.append(
            Issue(
                rule="calc_legacy",
                severity="error",
                line=ln,
                message="Legacy CALC command detected.",
                suggestion="Replace with explicit v4 command flow or pre-defined FUNC/CALL.",
            )
        )
    if patterns["val"].match(raw):
        issues.append(
            Issue(
                rule="val_legacy",
                severity="error",
                line=ln,
                message="Legacy VAL command detected.",
                suggestion="Replace with GET/SAVE/LOG according to runtime intent.",
            )
        )
    if patterns["if_cmp"].match(raw):
        issues.append(
            Issue(
                rule="if_cmp_legacy",
                severity="error",
                line=ln,
                message="Legacy IF comparator syntax detected (IF [x] [<] [y]).",
                suggestion="Convert to v4 range syntax: IF sensor min .. max [unit] or CHECK ...",
            )
        )
    if patterns["else_error"].match(raw):
        issues.append(
            Issue(
                rule="else_error_legacy",
                severity="error",
                line=ln,
                message="Legacy 'ELSE ERROR [...]' detected.",
                suggestion="Use plain ERROR 'message' after CHECK/IF condition.",
            )
        )
    if patterns["bracket"].search(raw):
        issues.append(
            Issue(
                rule="bracket_tokens_legacy",
                severity="warning",
                line=ln,
                message="Bracket token notation detected ([...]).",
                suggestion="Normalize tokens to v4 form and keep quotes only for strings/names.",
            )
        )
    return issues


def _validate_v2_structure(text: str) -> list[Issue]:
    issues: list[Issue] = []
    lines = text.splitlines()
    issues.extend(_validate_version_header_v2(lines))
    patterns = {
        "goal_inline": re.compile(r"^\s*GOAL\s*:\s*(.+)$", re.IGNORECASE),
        "goal_only": re.compile(r"^\s*GOAL\s*:\s*$", re.IGNORECASE),
        "bracket": re.compile(r"\[[^\]]+\]"),
        "task": re.compile(r"^\s*TASK\s*:\s*", re.IGNORECASE),
        "calc": re.compile(r"^\s*CALC\s+", re.IGNORECASE),
        "val": re.compile(r"^\s*VAL\s+", re.IGNORECASE),
        "if_cmp": re.compile(r"^\s*IF\s+\[[^\]]+\]\s+\[(<|>|<=|>=|=)\]\s+\[[^\]]+\]", re.IGNORECASE),
        "else_error": re.compile(r'^\s*ELSE\s+ERROR\s+\[".+"\]\s*$', re.IGNORECASE),
    }
    for i, raw in enumerate(lines):
        issues.extend(_validate_line_v2(raw, _line_number(i), patterns))
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
    return run_validator_cli(
        "Validate legacy OQL v2 patterns before migration to VERSION: 4",
        validate_oql_v2_legacy,
    )


if __name__ == "__main__":
    raise SystemExit(main())
