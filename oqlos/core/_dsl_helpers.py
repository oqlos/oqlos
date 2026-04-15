"""DSL parser helpers — constants, mapping, and normalization utilities."""

from __future__ import annotations

import re
from typing import Any

from oqlos.models.scenario import Step

_VALVE_NUM_MAP = {i: f'valve-{i}' for i in range(1, 15)}
_VALVE_ABBREV_MAP = {'nc': 'valve-nc', 'sc': 'valve-sc', 'wc': 'valve-wc'}
_OPEN_ACTIONS = {'włącz', 'wlacz', 'on', 'open', 'otwórz', 'otworz', 'start'}
_CLOSE_ACTIONS = {'wyłącz', 'wylacz', 'off', 'close', 'zamknij', 'stop'}
_WAIT_ACTIONS = {'czekaj', 'wait', 'delay', 'pauza', 'pause', 'timeout'}
_PUMP_OBJECT_RE = re.compile(r'\b(pump|pompa|sprężarka|sprezarka|compressor)\b', re.IGNORECASE)
_LUNG_OBJECT_RE = re.compile(r'\b(lung|płuco|pluco|respirator)\b', re.IGNORECASE)
_SENSOR_OBJECT_RE = re.compile(r'\b(czujnik|sensor)\b', re.IGNORECASE)
_DOUBLE_QUOTED_LITERAL_RE = re.compile(r'"([^"\r\n]*)"')


def _normalize_quote_syntax(line: str) -> str:
    """Normalize double-quoted DSL literals to single-quoted parser format."""
    return _DOUBLE_QUOTED_LITERAL_RE.sub(lambda match: f"'{match.group(1)}'", str(line or ''))


def _looks_like_valve_object(obj: str) -> bool:
    return bool(re.search(r'\bzaw', obj, re.IGNORECASE) or re.search(r'\bvalve\b', obj, re.IGNORECASE))


def _looks_like_pump_object(obj: str) -> bool:
    return bool(_PUMP_OBJECT_RE.search(obj))


def _looks_like_lung_object(obj: str) -> bool:
    return bool(_LUNG_OBJECT_RE.search(obj))


def _looks_like_sensor_object(obj: str) -> bool:
    return bool(_SENSOR_OBJECT_RE.search(obj))


def _map_peripheral(obj: str) -> str | None:
    """Map object string to peripheral ID."""
    obj = str(obj or '').strip().lower()

    m_valve = re.match(r"zaw[oó]r\s*(\d+)", obj)
    if m_valve:
        num = int(m_valve.group(1))
        return _VALVE_NUM_MAP.get(num, f'valve-{num}')

    if _looks_like_valve_object(obj):
        for abbrev, valve_id in _VALVE_ABBREV_MAP.items():
            if re.search(rf"\b{re.escape(abbrev)}\b", obj):
                return valve_id

    if _looks_like_pump_object(obj):
        return 'pump-main'

    if _looks_like_lung_object(obj):
        return 'lung-main'

    if _looks_like_sensor_object(obj):
        if 'sc' in obj:
            return 'sc-sensor'
        if 'wc' in obj:
            return 'wc-sensor'
        return 'nc-sensor'

    return None

def _parse_numeric_value(raw: str) -> int | float | None:
    """Extract a numeric value from DSL snippets like `5 bar` or `7.5l`."""
    match = re.search(r"[-+]?\d*\.?\d+", str(raw or "").replace(",", "."))
    if not match:
        return None
    value = float(match.group(0))
    return int(value) if value.is_integer() else value


def _map_valve_action(fn: str) -> tuple[str, bool, None, None]:
    """Map valve action value from function name."""
    value = True if fn in _OPEN_ACTIONS else False if fn in _CLOSE_ACTIONS else True
    return 'SET_VALVE', value, None, None


def _map_pump_action(fn: str, obj_raw: str, line: str) -> tuple[str, Any, None, None]:
    """Map pump action value from function name."""
    numeric = _parse_numeric_value(obj_raw or line)
    value = 100 if fn in _OPEN_ACTIONS else 0 if fn in _CLOSE_ACTIONS else (numeric if numeric is not None else 50)
    return 'SET_PUMP', value, None, None


def _map_wait_action(fn: str, obj: str, obj_raw: str, line: str, step_counter: int) -> tuple[str, None, int, Step]:
    """Map wait action, returning a WAIT step."""
    try:
        num = float(re.findall(r"[-+]?[0-9]*\.?[0-9]+", obj_raw)[0])
        duration = int(num) if 'ms' in obj or 'mil' in obj else int(num * 1000)
    except Exception:
        duration = 1000

    label = re.sub(r'^(→\s*|AND\s*)', '', line).strip()
    step = Step(id=f'step-{step_counter}', action='WAIT', duration=duration, label=label)
    return 'WAIT', None, duration, step


def _map_lung_action(fn: str, obj_raw: str, line: str) -> tuple[str, Any, None, None]:
    """Map lung action value from function name."""
    if fn in _CLOSE_ACTIONS or fn in {'stop'}:
        return 'SET_LUNG', 0, None, None
    numeric = _parse_numeric_value(obj_raw or line)
    value = numeric if numeric is not None else 5  # default 5 cycles
    return 'SET_LUNG', value, None, None


def _map_action_value(fn: str, obj: str, obj_raw: str, line: str, step_counter: int) -> tuple[str | None, Any, int | None, Step | None]:
    """Map function and object strings to action, value, duration, or a wait step."""
    if _looks_like_valve_object(obj):
        return _map_valve_action(fn)

    if _looks_like_pump_object(obj):
        return _map_pump_action(fn, obj_raw, line)

    if _looks_like_lung_object(obj):
        return _map_lung_action(fn, obj_raw, line)

    if _looks_like_sensor_object(obj) and fn in ('odczytaj', 'zmierz', 'sprawdź', 'sprawdz', 'read', 'measure'):
        return 'READ_SENSOR', None, None, None

    if fn in _WAIT_ACTIONS:
        return _map_wait_action(fn, obj, obj_raw, line, step_counter)

    return None, None, None, None
