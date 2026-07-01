"""OqlOS standardized issue/error catalog (OqlIssue).

Single source of truth for every known diagnostic code across the project
(hardware doctor, runtime diagnosis, API, frontend). See
``oqlos/errors/catalog.py`` for the registry and
``oqlos/tools/gen_error_docs.py`` for the generated ``docs/ERROR_CODES.md``.
"""

from __future__ import annotations

from oqlos.errors.catalog import (
    CODE_PATTERNS,
    ISSUE_CATALOG,
    ActuationRisk,
    CodePattern,
    IssueDefinition,
    IssueSeverity,
    RepairTemplate,
    all_codes,
    get_issue_definition,
    matches_known_pattern,
)
from oqlos.errors.exceptions import OqlosError
from oqlos.errors.repair_commit import (
    format_repair_commit_message,
    is_eligible_for_automated_commit,
)

__all__ = [
    "CODE_PATTERNS",
    "ISSUE_CATALOG",
    "ActuationRisk",
    "CodePattern",
    "IssueDefinition",
    "IssueSeverity",
    "OqlosError",
    "RepairTemplate",
    "all_codes",
    "format_repair_commit_message",
    "get_issue_definition",
    "is_eligible_for_automated_commit",
    "matches_known_pattern",
]
