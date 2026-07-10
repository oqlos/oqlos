"""Central OQL language version helpers.

This module defines supported OQL DSL versions and parsing policies,
so parser, adapter, interpreter, and validation tooling share one source
of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

OQL_VERSION_LEGACY = 3
#: First version with flat named-goal rules (``GOAL:`` + ``SET NAME``).
OQL_VERSION_V4 = 4
OQL_VERSION_CURRENT = 5
SUPPORTED_OQL_VERSIONS: tuple[int, ...] = (
    OQL_VERSION_LEGACY,
    OQL_VERSION_V4,
    OQL_VERSION_CURRENT,
)


@dataclass(frozen=True)
class OqlVersionInfo:
    """Resolved OQL version metadata for a source document."""

    declared: int | None
    effective: int
    first_meaningful_line_number: int | None
    first_meaningful_line: str | None

    @property
    def is_current(self) -> bool:
        return self.effective == OQL_VERSION_CURRENT


_VERSION_RE = re.compile(r"^VERSION\s*:\s*(\d+)\s*$", re.IGNORECASE)


def first_meaningful_line(text: str) -> tuple[int | None, str | None]:
    """Return first non-empty/non-comment line as (line_no, text)."""

    for ln, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if stripped and not stripped.startswith("#"):
            return ln, stripped
    return None, None


def extract_declared_version(text: str) -> int | None:
    """Extract VERSION header value when present on first meaningful line."""

    _, line = first_meaningful_line(text)
    if not line:
        return None
    match = _VERSION_RE.match(line)
    if not match:
        return None
    return int(match.group(1))


def resolve_oql_version(text: str, *, default: int = OQL_VERSION_LEGACY) -> OqlVersionInfo:
    """Resolve OQL version from source text with backward-compatible default."""

    line_no, line = first_meaningful_line(text)
    declared = extract_declared_version(text)
    effective = declared if declared is not None else default
    return OqlVersionInfo(
        declared=declared,
        effective=effective,
        first_meaningful_line_number=line_no,
        first_meaningful_line=line,
    )


def is_supported_oql_version(version: int) -> bool:
    return version in SUPPORTED_OQL_VERSIONS
