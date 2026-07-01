"""Generate docs/ERROR_CODES.md from oqlos/errors/catalog.py.

The catalog is the single source of truth: edit ``ISSUE_CATALOG``, then
regenerate the doc. Never hand-edit docs/ERROR_CODES.md.

Usage:
    python -m oqlos.tools.gen_error_docs           # write docs/ERROR_CODES.md
    python -m oqlos.tools.gen_error_docs --check    # exit 1 if the doc is stale
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from oqlos.errors.catalog import CODE_PATTERNS, ISSUE_CATALOG, IssueDefinition

DOC_PATH = Path(__file__).resolve().parents[2] / "docs" / "ERROR_CODES.md"

_HEADER = """# OqlOS Error / Issue Codes

Generated from `oqlos/errors/catalog.py` by `python -m oqlos.tools.gen_error_docs`.
Do not hand-edit this file — edit the catalog and regenerate.

Each code is stable and grep-able across logs, API responses, and git commit
trailers (`OqlOS-Issue: <code>`). `actuation_risk` controls whether an
automated repair (e.g. an LLM-driven git commit) may apply the fix on its
own:

- `none` — diagnostic only, or needs a host/infra action no automation should
  attempt.
- `config` — a plain config/YAML edit with no effect until a service
  restart. Safe for an automated commit.
- `physical` — changes whether/how real hardware is actuated. Always
  requires human confirmation.
"""


def _repair_cell(defn: IssueDefinition) -> str:
    if defn.repair is None:
        return "—"
    r = defn.repair
    auto = "auto" if defn.repair.auto_executable else "manual"
    return f"`{r.id}` (scope={r.scope}, {auto}, risk={r.actuation_risk})"


def generate_markdown() -> str:
    lines = [_HEADER, ""]
    by_domain: dict[str, list[IssueDefinition]] = {}
    for defn in ISSUE_CATALOG.values():
        by_domain.setdefault(defn.domain, []).append(defn)

    for domain in sorted(by_domain):
        lines.append(f"## {domain}")
        lines.append("")
        lines.append("| Code | Severity | Summary | Repair |")
        lines.append("|------|----------|---------|--------|")
        for defn in sorted(by_domain[domain], key=lambda d: d.code):
            lines.append(
                f"| `{defn.code}` | {defn.default_severity} | {defn.summary} | {_repair_cell(defn)} |"
            )
        lines.append("")

    if CODE_PATTERNS:
        lines.append("## Dynamic code families")
        lines.append("")
        lines.append(
            "These are not fixed codes but templates — one concrete code exists per "
            "runtime value (e.g. per adapter id)."
        )
        lines.append("")
        lines.append("| Pattern | Domain | Severity | Summary |")
        lines.append("|---------|--------|----------|---------|")
        for pattern in CODE_PATTERNS:
            lines.append(
                f"| `{pattern.prefix}*{pattern.suffix}` | {pattern.domain} | {pattern.default_severity} | {pattern.summary} |"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if docs/ERROR_CODES.md is out of date instead of writing it.",
    )
    args = parser.parse_args()

    content = generate_markdown()
    if args.check:
        current = DOC_PATH.read_text() if DOC_PATH.exists() else ""
        if current != content:
            print(f"{DOC_PATH} is stale — run `python -m oqlos.tools.gen_error_docs`.")
            sys.exit(1)
        print(f"{DOC_PATH} is up to date.")
        return

    DOC_PATH.write_text(content)
    print(f"Wrote {DOC_PATH}")


if __name__ == "__main__":
    main()
