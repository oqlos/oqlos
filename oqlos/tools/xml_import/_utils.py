#!/usr/bin/env python3
"""Utility functions for XML to DSL conversion."""

from __future__ import annotations

import re

FALLBACK_SORT_ORDINAL = 999

# Polish character transliteration
_PL_TRANS = str.maketrans({
    'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n',
    'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
    'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N',
    'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z',
    'ä': 'a', 'ö': 'o', 'ü': 'u', 'ß': 'ss',
    'Ä': 'A', 'Ö': 'O', 'Ü': 'U',
})


def slugify(text: str) -> str:
    """Create a URL-safe slug from text (handles Polish/German chars)."""
    s = text.translate(_PL_TRANS)
    s = re.sub(r'[^a-zA-Z0-9]+', '-', s).strip('-').lower()
    return re.sub(r'-+', '-', s)


def is_pump_output(name: str) -> bool:
    """Check if output name refers to a pump."""
    lowered = (name or '').strip().lower()
    return lowered in {'pump', 'pompa'} or 'pump' in lowered or 'pompa' in lowered


def is_compressor_output(name: str) -> bool:
    """Check if output name refers to a compressor."""
    lowered = (name or '').strip().lower()
    return lowered in {'compressor', 'sprężarka', 'sprezarka'} or 'compressor' in lowered or 'sprężarka' in lowered or 'sprezarka' in lowered


def normalize_output_name(name: str) -> str:
    """Normalize hardware output name to standard format."""
    lowered = (name or '').strip().lower()
    if is_pump_output(lowered):
        return 'pompa'
    if is_compressor_output(lowered):
        return 'sprężarka'
    if re.fullmatch(r'bo\d+', lowered):
        digits = re.search(r'(\d+)', lowered)
        if digits:
            return f'zawór {int(digits.group(1))}'
    if 'valve' in lowered or 'zawór' in lowered or 'zawor' in lowered:
        digits = re.search(r'(\d+)', lowered)
        if digits:
            return f'zawór {int(digits.group(1))}'
        return 'zawór'
    return (name or '').strip()


def normalize_flow_value(raw_value: str) -> str:
    """Normalize flow value to standard format (e.g., '5 l/min')."""
    raw = re.sub(r'\s+', ' ', str(raw_value or '').strip())
    if not raw:
        return '0 l/min'
    if raw.lower() == 'off':
        return '0 l/min'
    compact = re.sub(r'\s+', '', raw)
    match = re.match(r'^([-+]?\d+(?:[\.,]\d+)?)(.*)$', compact)
    if match:
        number = match.group(1).replace(',', '.')
        suffix = re.sub(r'\s+', ' ', match.group(2).strip())
        normalized_suffix = suffix.lower().replace(' ', '')
        if not suffix:
            suffix = 'l/min'
        elif normalized_suffix in {'l', 'l/min', 'lmin', 'lpm'}:
            suffix = 'l/min'
        return f'{number} {suffix}'.strip()
    return raw


def normalize_set_value(raw_value: str, *, default_unit: str | None = None) -> str:
    """Normalize set value to standard format."""
    raw = re.sub(r'\s+', ' ', str(raw_value or '').strip())
    if not raw:
        return f'0 {default_unit}'.strip() if default_unit else '1'

    lowered = raw.lower()
    if lowered in {'on', 'open', 'true', 'yes', 'start', 'włącz', 'wlacz'}:
        return '1' if not default_unit else f'1 {default_unit}'.strip()
    if lowered in {'off', 'close', 'false', 'no', 'stop', 'wyłącz', 'wylacz'}:
        return '0' if not default_unit else f'0 {default_unit}'.strip()

    compact = re.sub(r'\s+', '', raw)
    match = re.match(r'^([-+]?\d+(?:[\.,]\d+)?)(.*)$', compact)
    if match:
        number = match.group(1).replace(',', '.')
        suffix = re.sub(r'\s+', ' ', match.group(2).strip())
        normalized_suffix = suffix.lower().replace(' ', '')
        if default_unit and (not suffix or normalized_suffix in {'l', 'l/min', 'lmin', 'lpm'}):
            suffix = default_unit
        return f'{number} {suffix}'.strip()
    return raw


# ── OQL v5 document/goal emit helpers ──

OQL_V5 = 5
BLOCK_INDENT = '  '


def quote_oql_literal(value: str) -> str:
    text = str(value or '')
    return f'"{text}"' if "'" in text else f"'{text}'"


def scenario_document_header(title: str, version: int = OQL_V5) -> list[str]:
    name = str(title or 'scenario').strip() or 'scenario'
    return [f'VERSION: {version}', f'SCENARIO: {name}', '']


def goal_block_header(name: str) -> list[str]:
    goal_name = str(name or 'GOAL').strip() or 'GOAL'
    return ['TASK:', f'{BLOCK_INDENT}NAME {quote_oql_literal(goal_name)}']


def goal_body_line(line: str) -> str:
    stripped = str(line or '').strip()
    return f'{BLOCK_INDENT}{stripped}' if stripped else ''
