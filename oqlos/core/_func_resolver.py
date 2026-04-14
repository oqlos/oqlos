"""DSL function resolver — FUNC definition collection and call expansion."""

from __future__ import annotations

import re
from typing import Callable

from oqlos.models.scenario import Step
from ._dsl_helpers import _normalize_quote_syntax

MAX_FUNC_DEPTH = 32


def _collect_function_definitions(lines: list[str]) -> dict[str, list[str]]:
    """Collect top-level `FUNC: name` blocks so runtime calls can inline them."""
    func_defs: dict[str, list[str]] = {}
    i = 0
    while i < len(lines):
        raw_line = str(lines[i] or '').rstrip()
        line = raw_line.strip()
        indent = len(raw_line) - len(raw_line.lstrip())
        m_func = re.match(r"FUNC:\s*(.+)$", line, re.IGNORECASE)
        if indent == 0 and m_func:
            func_name = m_func.group(1).strip()
            block: list[str] = []
            i += 1
            while i < len(lines):
                next_raw = str(lines[i] or '').rstrip()
                next_line = next_raw.strip()
                next_indent = len(next_raw) - len(next_raw.lstrip())
                if next_line and next_indent == 0 and re.match(r"(?:SCENARIO:|GOAL:|FUNC:\s*)", next_line, re.IGNORECASE):
                    break
                if next_line:
                    block.append(next_line)
                i += 1
            if func_name and block:
                func_defs[func_name] = block
            continue
        i += 1
    return func_defs


def _parse_func_call(
    line: str,
    step_counter: int,
    steps: list[Step],
    func_defs: dict[str, list[str]],
    indent: int = 0,
    call_stack: tuple[str, ...] = (),
    parse_line_fn: Callable[..., int] | None = None,
) -> tuple[int, bool, bool]:
    """Expand an in-goal FUNC call into its defined runtime steps."""
    normalized_line = _normalize_quote_syntax(line)
    m_quote = re.match(r'FUNC\s*"([^"]*)"(?:\s+.*)?$', normalized_line, re.IGNORECASE)
    m_squote = re.match(r"FUNC\s*'([^']*)'(?:\s+.*)?$", normalized_line, re.IGNORECASE)
    m_bracket = re.match(r"FUNC\s*\[([^\]]+)\](?:\s+.*)?$", normalized_line, re.IGNORECASE)
    m_colon = re.match(r"FUNC:\s*(.+)$", normalized_line, re.IGNORECASE)
    if not m_quote and not m_squote and not m_bracket and not m_colon:
        return step_counter, False, False

    # `FUNC: name` at top level is a definition, not a call.
    if m_colon and indent == 0:
        return step_counter, False, False

    func_name = (m_quote.group(1) if m_quote else m_squote.group(1) if m_squote else m_bracket.group(1) if m_bracket else m_colon.group(1)).strip()
    if not func_name:
        return step_counter, True, True
    if len(call_stack) >= MAX_FUNC_DEPTH:
        raise RecursionError(f"FUNC depth limit ({MAX_FUNC_DEPTH}) exceeded: {' → '.join(call_stack)}")
    if func_name in call_stack:
        raise RecursionError(f"Circular FUNC reference: {' → '.join(call_stack)} → {func_name}")

    func_lines = func_defs.get(func_name)
    if not func_lines:
        return step_counter, True, True

    if parse_line_fn is None:
        return step_counter, True, True

    for func_line in func_lines:
        step_counter = parse_line_fn(func_line, step_counter, steps, func_defs, indent=2, call_stack=call_stack + (func_name,))
    return step_counter, True, False
