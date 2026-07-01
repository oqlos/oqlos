"""Git commit convention + eligibility gate for automated OqlIssue repairs.

This module only builds the commit message and checks eligibility — it does
NOT run `git commit` itself. Wiring this into an actual trigger (a CLI
command, a watched endpoint, a scheduled agent) is a deliberate follow-up
decision, not something to run unsupervised by default.

Convention: ``fix(<code>): <short description>`` with a trailing
``OqlOS-Issue: <code>`` line, so ``git log --grep "OqlOS-Issue: <code>"``
finds every commit that fixed a given issue.
"""

from __future__ import annotations

from oqlos.hardware.diagnosis_types import DiagnosisAction

_ELIGIBLE_ACTUATION_RISK = "config"


def is_eligible_for_automated_commit(action: DiagnosisAction) -> bool:
    """True only for in-process-safe, config-only, already-auto_executable actions.

    Never returns True for actuation_risk="physical" (motor/valve movement)
    or "none" (no file changes to commit) — those are never candidates for
    an autonomous git commit.
    """
    return bool(action.auto_executable) and action.actuation_risk == _ELIGIBLE_ACTUATION_RISK


def format_repair_commit_message(
    *,
    code: str,
    summary: str,
    co_author: str | None = None,
) -> str:
    """Build a `fix(<code>): <summary>` commit message with an OqlOS-Issue trailer."""
    lines = [f"fix({code}): {summary}", "", f"OqlOS-Issue: {code}"]
    if co_author:
        lines.append(f"Co-Authored-By: {co_author}")
    return "\n".join(lines) + "\n"
