"""CQL tokenizer — regex patterns and individual action parsers."""

from __future__ import annotations

import re

from oqlos.models.dsl_models import CqlAction, CqlCondition

# ═══════════════════════════════════════════════════════════════════════════════
# Regex patterns
# ═══════════════════════════════════════════════════════════════════════════════

RE_METADATA_KV = re.compile(r'^(SCENARIO|DEVICE_TYPE|DEVICE_MODEL|MANUFACTURER)\s*:\s*"?(.+?)"?\s*$')
RE_INTERVAL = re.compile(r'^\s*-\s+(tt#\d+)\s*:\s*"(.+?)"\s+period\s*:\s*(\d+)\s*months?\s*$')
RE_SCENARIO = re.compile(r'^@(\w+(?:\.\w+)*)\s*$')
RE_GOAL_SIMPLE = re.compile(r'^GOAL\s*:\s*(.+)$')
RE_GOAL_NAMED = re.compile(r'^  (\w[\w\s]*\w)\s*:\s*$')
RE_STEP_NUM = re.compile(r'^\s+(\d+(?:\.\d+)?)\s*[.)]?\s*(.+?):\s*$')
RE_ACTION_ARROW = re.compile(r'^\s+→\s+(\w+)\.(\w+)\s*(.*)$')
RE_TASK_BRACKET = re.compile(r'^\s+TASK\s*:\s*(.+)$')
RE_SAVE_COLON = re.compile(r'^\s+SAVE\s*:\s*(\S+)\s*$')
RE_SAVE_BRACKET = re.compile(r'^\s+SAVE\s+\[(.+?)\]\s*$')
RE_SAVE_QUOTED = re.compile(r'^\s+SAVE\s+"(.+?)"\s*$')
RE_WAIT = re.compile(r'^\s+WAIT\s+\[?([\d.]+)\s*(?:ms|s)?\]?\s*$')
RE_SET = re.compile(r'^\s+SET\s+\[(.+?)\]\s*=\s*\[(.+?)\]\s*$')
RE_SET_QUOTED = re.compile(r'^\s+SET\s+"(.+?)"\s+"(.+?)"\s*$')
RE_SET_SINGLE = re.compile(r"^\s+SET\s+'(.+?)'\s+'(.+?)'\s*$")
RE_CONDITION_RANGE = re.compile(
    r'^\s+(?:Δ?)(AI\d+|Timer)\s*([∈∊])\s*\[([-\d.]+)\s*,\s*([-\d.]+)\]\s*(\w+)?\s*\|\s*(\w+)\s*(?:"(.+?)")?\s*$'
)
RE_CONDITION_CMP = re.compile(
    r'^\s+(?:Δ?)(AI\d+|Timer)\s*([≤≥<>=]+)\s*([-\d.]+)\s*(\w+)?\s*\|\s*(\w+)\s*(?:"(.+?)")?\s*$'
)
RE_IF_ELSE = re.compile(
    r'^\s+IF\s+\[(.+?)\]\s+\[([<>=!]+)\]\s+\[([-\d.]+)\s*(\w+)?\]\s+ELSE\s+ERROR\s+"(.+?)"\s*$'
)
RE_IF_ELSE_QUOTED = re.compile(
    r'^\s+IF\s+"(.+?)"\s+([<>=!]+)\s+"([-\d.]+)\s*(\w+)?"\s+ELSE\s+ERROR\s+"(.+?)"\s*$'
)
RE_MIN_MAX = re.compile(r'^\s+(MIN|MAX)\s+\[(.+?)\]\s*=\s*\[([-\d.]+)\s*(\w+)?\]\s*$')
RE_MIN_MAX_QUOTED = re.compile(r'^\s+(MIN|MAX)\s+"(.+?)"\s+"([-\d.]+)\s*(\w+)?"\s*$')
RE_VAL = re.compile(r'^\s+VAL\s+\[(.+?)\]\s+\[(.+?)\]\s*$')
RE_VAL_QUOTED = re.compile(r'^\s+VAL\s+"(.+?)"\s+"(.+?)"\s*$')
RE_DESC = re.compile(r'^\s+description\s*:\s*"(.+?)"\s*$')
RE_EDITABLE = re.compile(r'^\s+editable\s*:\s*(true|false)\s*$', re.IGNORECASE)
RE_ALARM = re.compile(r'^\s+alarm\s*:\s*"(.+?)"\s*$')
RE_INTERVALS_REF = re.compile(r'^\s+intervals\s*:\s*\[(.+?)\]\s*$')
RE_BLOCK_HEADER = re.compile(r'^(OUTPUTS|SENSORS|VALIDATION_MODES|META)\s*:\s*$')


# ═══════════════════════════════════════════════════════════════════════════════
# Individual action parsers (each returns CqlAction | None)
# ═══════════════════════════════════════════════════════════════════════════════

def _try_arrow_action(line: str, stripped: str) -> CqlAction | None:
    m = RE_ACTION_ARROW.match(line)
    if not m:
        return None
    return CqlAction(
        kind="action", target=m.group(1), method=m.group(2),
        args=m.group(3).strip().strip('"'), raw=stripped,
    )


def _try_task(line: str, stripped: str) -> CqlAction | None:
    m = RE_TASK_BRACKET.match(line)
    if not m:
        return None
    return CqlAction(kind="task", args=m.group(1).strip(), raw=stripped)


def _try_save(line: str, stripped: str) -> CqlAction | None:
    m = RE_SAVE_COLON.match(line) or RE_SAVE_BRACKET.match(line) or RE_SAVE_QUOTED.match(line)
    if not m:
        return None
    return CqlAction(kind="save", target=m.group(1).strip(), raw=stripped)


def _try_wait(line: str, stripped: str) -> CqlAction | None:
    m = RE_WAIT.match(line)
    if not m:
        return None
    return CqlAction(kind="wait", args=m.group(1), raw=stripped)


def _try_set(line: str, stripped: str) -> CqlAction | None:
    m = RE_SET.match(line) or RE_SET_QUOTED.match(line) or RE_SET_SINGLE.match(line)
    if not m:
        return None
    return CqlAction(kind="set", target=m.group(1).strip(), args=m.group(2).strip(), raw=stripped)


def _try_condition_range(line: str, stripped: str) -> CqlAction | None:
    m = RE_CONDITION_RANGE.match(line)
    if not m:
        return None
    cond = CqlCondition(
        sensor=m.group(1), operator="∈",
        value_min=float(m.group(3)), value_max=float(m.group(4)),
        unit=m.group(5) or "", on_fail=m.group(6) or "",
        fail_message=m.group(7) or "",
    )
    return CqlAction(kind="condition", condition=cond, raw=stripped)


def _try_condition_cmp(line: str, stripped: str) -> CqlAction | None:
    m = RE_CONDITION_CMP.match(line)
    if not m:
        return None
    cond = CqlCondition(
        sensor=m.group(1), operator=m.group(2),
        value=float(m.group(3)), unit=m.group(4) or "",
        on_fail=m.group(5) or "", fail_message=m.group(6) or "",
    )
    return CqlAction(kind="condition", condition=cond, raw=stripped)


def _try_if_else(line: str, stripped: str) -> CqlAction | None:
    m = RE_IF_ELSE.match(line) or RE_IF_ELSE_QUOTED.match(line)
    if not m:
        return None
    cond = CqlCondition(
        sensor=m.group(1), operator=m.group(2),
        value=float(m.group(3)), unit=m.group(4) or "",
        on_fail="ERROR", fail_message=m.group(5),
    )
    return CqlAction(kind="if_else", condition=cond, raw=stripped)


def _try_min_max(line: str, stripped: str) -> CqlAction | None:
    m = RE_MIN_MAX.match(line) or RE_MIN_MAX_QUOTED.match(line)
    if not m:
        return None
    return CqlAction(
        kind=m.group(1).lower(), target=m.group(2),
        args=f"{m.group(3)} {m.group(4) or ''}".strip(), raw=stripped,
    )


def _try_val(line: str, stripped: str) -> CqlAction | None:
    m = RE_VAL.match(line) or RE_VAL_QUOTED.match(line)
    if not m:
        return None
    return CqlAction(kind="val", target=m.group(1), args=m.group(2), raw=stripped)


_ACTION_PARSERS = [
    _try_arrow_action,
    _try_task,
    _try_save,
    _try_wait,
    _try_set,
    _try_condition_range,
    _try_condition_cmp,
    _try_if_else,
    _try_min_max,
    _try_val,
]
