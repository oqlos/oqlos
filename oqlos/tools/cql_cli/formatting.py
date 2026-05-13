"""Canonical OQL formatting helpers for the CLI."""

from __future__ import annotations

import re


_SET_BRACKET_EQUALS_RE = re.compile(r"^(\s*)SET\s*\[([^\]]+)\]\s*=\s*\[([^\]]*)\]\s*(.*)$", re.IGNORECASE)
_SET_BARE_EQUALS_RE = re.compile(r"^(\s*)SET\s+([^\s'\"\[]+)\s*=\s*(.+?)\s*$", re.IGNORECASE)
_SET_BRACKET_VALUE_RE = re.compile(r"^(\s*)SET\s*\[([^\]]+)\]\s+(.+?)\s*$", re.IGNORECASE)
_SET_BARE_VALUE_RE = re.compile(r"^(\s*)SET\s+([^\s'\"]+)\s+(.+?)\s*$", re.IGNORECASE)
_SET_QUOTED_RE = re.compile(r"^\s*SET\s+'[^']*'\s+'[^']*'\s*$", re.IGNORECASE)
_SET_NAME_BRACKET_RE = re.compile(r"^(\s*)SET\s+NAME\s+\[([^\]]+)\]\s*$", re.IGNORECASE)


def _quote_oql(value: str) -> str:
    return "'" + str(value or "").strip().replace("\\", "\\\\").replace("'", "\\'") + "'"


def canonicalize_oql_text(text: str) -> str:
    """Return text with legacy SET forms rewritten to canonical OQL v4 style."""
    return "\n".join(canonicalize_oql_line(line) for line in text.splitlines()) + ("\n" if text.endswith("\n") else "")


def canonicalize_oql_line(line: str) -> str:
    """Canonicalize one OQL line while preserving indentation."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or _SET_QUOTED_RE.match(line):
        return line

    match = _SET_NAME_BRACKET_RE.match(line)
    if match:
        indent, name = match.groups()
        return f"{indent}SET NAME {_quote_oql(name)}"

    match = _SET_BRACKET_EQUALS_RE.match(line)
    if match:
        indent, target, value, tail = match.groups()
        tail = tail if tail.strip().startswith("#") else ""
        return f"{indent}SET {_quote_oql(target)} {_quote_oql(value)}{(' ' + tail.strip()) if tail else ''}"

    match = _SET_BARE_EQUALS_RE.match(line)
    if match:
        indent, target, value = match.groups()
        if target.strip().upper() == "NAME":
            return line
        return f"{indent}SET {_quote_oql(target)} {_quote_oql(value)}"

    match = _SET_BRACKET_VALUE_RE.match(line)
    if match:
        indent, target, value = match.groups()
        if target.strip().upper() == "NAME":
            return line
        return f"{indent}SET {_quote_oql(target)} {_quote_oql(value)}"

    match = _SET_BARE_VALUE_RE.match(line)
    if match:
        indent, target, value = match.groups()
        if target.strip().upper() == "NAME":
            return line
        return f"{indent}SET {_quote_oql(target)} {_quote_oql(value)}"

    return line
