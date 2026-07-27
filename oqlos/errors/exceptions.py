"""OqlosError: the standard exception shape for OqlIssue-backed errors.

Raise ``OqlosError(code=...)`` anywhere a known catalog code applies; the
FastAPI handler in ``oqlos.api.main`` turns it into a consistent JSON body.
Unknown codes are still accepted (domain/severity fall back to sane
defaults) so this can be adopted incrementally without a central migration.
"""

from __future__ import annotations

from typing import Any

from oqlos.errors.catalog import (
    IssueSeverity,
    RepairTemplate,
    get_issue_definition,
)
from oqlos.errors.c2004_catalog_generated import c2004_code_for_issue


class OqlosError(Exception):
    def __init__(
        self,
        code: str,
        *,
        message: str | None = None,
        detail: dict[str, Any] | None = None,
        status_code: int = 500,
        severity: IssueSeverity | None = None,
    ) -> None:
        definition = get_issue_definition(code)
        self.code = code
        # ``code`` remains the granular OqlOS diagnostic identifier for
        # internal callers.  HTTP responses expose only this generated public
        # C2004 code; the local identifier is nested under diagnostics.
        self.issue_code = code
        self.public_code = c2004_code_for_issue(code)
        self.domain = definition.domain if definition else "unknown"
        self.severity: IssueSeverity = severity or (
            definition.default_severity if definition else "error"
        )
        self.message = message or (definition.summary if definition else code)
        self.detail = detail or {}
        self.status_code = status_code
        self.repair: RepairTemplate | None = definition.repair if definition else None
        super().__init__(self.message)

    def to_issue(self) -> dict[str, Any]:
        issue: dict[str, Any] = {
            "code": self.code,
            "domain": self.domain,
            "severity": self.severity,
            "message": self.message,
        }
        if self.detail:
            issue["detail"] = self.detail
        if self.repair is not None:
            issue["repair"] = {
                "id": self.repair.id,
                "scope": self.repair.scope,
                "auto_executable": self.repair.auto_executable,
                "actuation_risk": self.repair.actuation_risk,
                "hint": self.repair.hint,
            }
        return issue
