"""DSL line parsers — individual statement parsers for SET, PUMP, TASK, IF, actions."""

from __future__ import annotations

import re
from typing import Any

from oqlos.models.scenario import Step
from ._dsl_helpers import (
    _OPEN_ACTIONS,
    _CLOSE_ACTIONS,
    _WAIT_ACTIONS,
    _map_action_value,
    _map_peripheral,
    _normalize_quote_syntax,
    _parse_numeric_value,
)


def _parse_task_part(part: str, step_counter: int) -> Step | None:
    """Parse a single section of an inline TASK line."""
    normalized_part = _normalize_quote_syntax(part)
    mm = re.match(
        r"(?:\[(?P<fn_br>[^\]]+)\]|'(?P<fn_quote>[^']+)'|(?P<fn_plain>[^[\']+?))\s*"
        r"(?:\[(?P<obj_br>[^\]]+)\]|'(?P<obj_quote>[^']+)')\s*$",
        normalized_part,
    )
    if not mm:
        return None

    fn_raw = (mm.group('fn_br') or mm.group('fn_quote') or mm.group('fn_plain') or '').strip()
    obj_raw = (mm.group('obj_br') or mm.group('obj_quote') or '').strip()
    fn, obj = fn_raw.lower(), obj_raw.lower()

    peripheral = _map_peripheral(obj)
    action, value, _, wait_step = _map_action_value(fn, obj, obj_raw, part, step_counter)

    if wait_step:
        return wait_step

    if action is None or peripheral is None:
        return None

    return Step(
        id=f'step-{step_counter}',
        action=action,
        peripheral=peripheral,
        value=value,
        label=part
    )


def _parse_pump_line(line: str, step_counter: int) -> Step | None:
    """Parse dedicated pump control like `PUMP '5 bar'` (legacy: `PUMP [5 bar]`)."""
    normalized_line = _normalize_quote_syntax(line)
    match = re.match(r"PUMP\s*'([^']*)'\s*$", normalized_line, re.IGNORECASE) or \
            re.match(r"PUMP\s*\[([^\]]+)\]\s*$", normalized_line, re.IGNORECASE)
    if not match:
        return None
    raw_value = match.group(1).strip()
    text = raw_value.lower()
    if text in _OPEN_ACTIONS:
        value: Any = 100
    elif text in _CLOSE_ACTIONS:
        value = 0
    else:
        value = _parse_numeric_value(raw_value)
        if value is None:
            value = raw_value
    return Step(
        id=f'step-{step_counter}',
        action='SET_PUMP',
        peripheral='pump-main',
        value=value,
        label=line,
    )


def _set_valve_step(peripheral: str, value_raw: str, step_counter: int, line: str) -> Step:
    """Build a SET_VALVE step from value text."""
    lowered = value_raw.lower()
    numeric = _parse_numeric_value(value_raw)
    if lowered in {'1', 'true', 'on', 'open'}:
        value = True
    elif lowered in {'0', 'false', 'off', 'close'}:
        value = False
    else:
        value = bool(numeric) if numeric is not None else True
    return Step(id=f'step-{step_counter}', action='SET_VALVE', peripheral=peripheral, value=value, label=line)


def _set_pump_step(peripheral: str, value_raw: str, step_counter: int, line: str) -> Step:
    """Build a SET_PUMP step from value text."""
    lowered = value_raw.lower()
    numeric = _parse_numeric_value(value_raw)
    if lowered in _OPEN_ACTIONS:
        value: Any = 100
    elif lowered in _CLOSE_ACTIONS:
        value = 0
    else:
        value = numeric if numeric is not None else value_raw
    return Step(id=f'step-{step_counter}', action='SET_PUMP', peripheral=peripheral, value=value, label=line)


def _set_lung_step(peripheral: str, value_raw: str, step_counter: int, line: str) -> Step:
    """Build a SET_LUNG step from value text."""
    lowered = value_raw.lower()
    if lowered in _CLOSE_ACTIONS or lowered in {'0', 'stop'}:
        value: Any = 0
    else:
        numeric = _parse_numeric_value(value_raw)
        value = numeric if numeric is not None else 5  # default 5 cycles
    return Step(id=f'step-{step_counter}', action='SET_LUNG', peripheral=peripheral, value=value, label=line)


def _parse_set_line(line: str, step_counter: int) -> Step | None:
    """Parse `SET 'zawór 2' '1'` or legacy `SET [zawór 2] = [1]`."""
    normalized_line = _normalize_quote_syntax(line)
    match = re.match(r'SET\s*"([^"]*)"\s*"([^"]*)"\s*$', normalized_line, re.IGNORECASE) or \
            re.match(r"SET\s*'([^']*)'\s*'([^']*)'\s*$", normalized_line, re.IGNORECASE) or \
            re.match(r"SET\s*\[([^\]]+)\]\s*=\s*\[([^\]]+)\]\s*$", normalized_line, re.IGNORECASE)
    if not match:
        return None

    param_raw = match.group(1).strip()
    value_raw = match.group(2).strip()
    param = param_raw.lower()

    if param in _WAIT_ACTIONS:
        numeric = _parse_numeric_value(value_raw)
        if numeric is None:
            numeric = 1
        duration = int(numeric) if 'ms' in value_raw.lower() else int(float(numeric) * 1000)
        return Step(id=f'step-{step_counter}', action='WAIT', duration=duration, label=line)

    if param in ('pump', 'pompa', 'sprężarka', 'sprezarka', 'compressor'):
        return _set_pump_step('pump-main', value_raw, step_counter, line)

    peripheral = _map_peripheral(param)
    if not peripheral:
        return None

    if peripheral.startswith('valve'):
        return _set_valve_step(peripheral, value_raw, step_counter, line)

    if peripheral == 'pump-main':
        return _set_pump_step(peripheral, value_raw, step_counter, line)

    if peripheral == 'lung-main':
        return _set_lung_step(peripheral, value_raw, step_counter, line)

    return None


def _parse_inline_task(line: str, step_counter: int, steps: list[Step]) -> tuple[int, bool]:
    """Parse an inline TASK line with multiple AND segments."""
    m_task = re.match(r"TASK(?:\s*:)?\s*(.+)$", line, re.IGNORECASE)
    if not m_task:
        return step_counter, False
        
    body = m_task.group(1).strip()
    had_invalid_part = False
    for part in re.split(r"\bAND\b", body, flags=re.IGNORECASE):
        part = part.strip()
        if not part:
            continue
            
        step = _parse_task_part(part, step_counter)
        if step:
            steps.append(step)
            step_counter += 1
        else:
            had_invalid_part = True
            
    return step_counter, had_invalid_part

def _parse_action_line(line: str, step_counter: int, steps: list[Step]) -> tuple[int, bool]:
    """Parse a single action line starting with → or AND."""
    normalized_line = _normalize_quote_syntax(line)
    m_act = re.match(
        r"(→|AND)\s+(?:\[(?P<fn_br>[^\]]+)\]|'(?P<fn_quote>[^']+)'|(?P<fn_plain>[^[\']+?))\s*"
        r"(?:\[(?P<obj_br>[^\]]+)\]|'(?P<obj_quote>[^']+)')\s*$",
        normalized_line,
        re.IGNORECASE,
    )
    if not m_act:
        return step_counter, False

    fn_raw = (m_act.group('fn_br') or m_act.group('fn_quote') or m_act.group('fn_plain') or '').strip()
    obj_raw = (m_act.group('obj_br') or m_act.group('obj_quote') or '').strip()
    fn, obj = fn_raw.lower(), obj_raw.lower()

    peripheral = _map_peripheral(obj)
    action, value, _, wait_step = _map_action_value(fn, obj, obj_raw, line, step_counter)
    
    if wait_step:
        steps.append(wait_step)
        return step_counter + 1, True

    if action is None or peripheral is None:
        return step_counter, False

    label_line = re.sub(r'^(→\s*|AND\s*)', '', line).strip()
    steps.append(Step(
        id=f'step-{step_counter}',
        action=action,
        peripheral=peripheral,
        value=value,
        label=label_line
    ))
    return step_counter + 1, True

def _parse_if_condition(line: str, step_counter: int, steps: list[Step]) -> tuple[int, bool]:
    """Parse an IF condition line: `IF 'param' = 'value'` or legacy bracket form."""
    normalized_line = _normalize_quote_syntax(line)
    m_if = re.match(r"IF\s*'([^']*)'\s*(>=|<=|>|<|=|!=)\s*'([^']*)'", normalized_line, re.IGNORECASE) or \
           re.match(r"IF\s*\[([^\]]+)\]\s*(?:\[([^\]]+)\]|([<>!=]=?|=))\s*\[([^\]]+)\]", normalized_line, re.IGNORECASE)
    if not m_if:
        return step_counter, False

    # New quote format: groups 1, 2, 3; legacy bracket format: groups 1, (2|3), 4
    if m_if.lastindex == 3:
        param_raw = m_if.group(1).strip().lower()
        op = m_if.group(2).strip()
        val = m_if.group(3).strip()
    else:
        param_raw = m_if.group(1).strip().lower()
        op = (m_if.group(2) or m_if.group(3) or '=').strip()
        val = m_if.group(4).strip()

    if 'sc' in param_raw: sensor = 'sc-sensor'
    elif 'wc' in param_raw: sensor = 'wc-sensor'
    else: sensor = 'nc-sensor'

    try:
        numeric = float(re.findall(r"[-+]?[0-9]*\.?[0-9]+", val)[0])
    except Exception:
        numeric = 0

    steps.append(Step(
        id=f'step-{step_counter}',
        action='VALIDATE',
        condition=f'{sensor}.currentValue {op} {numeric}',
        label=line
    ))
    return step_counter + 1, True
