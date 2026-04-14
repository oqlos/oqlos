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
RE_CONFIG_SIMPLE = re.compile(r'^CONFIG\s*:\s*(.+)$')
RE_CONFIG_NAMED = re.compile(r'^  CONFIG\s+(\w[\w\s]*\w)\s*:\s*$')
RE_STEP_NUM = re.compile(r'^\s+(\d+(?:\.\d+)?)\s*[.)]?\s*(.+?):\s*$')
RE_ACTION_ARROW = re.compile(r'^\s+→\s+(\w+)\.(\w+)\s*(.*)$')
RE_TASK_BRACKET = re.compile(r'^\s+TASK\s*:\s*(.+)$')
RE_SAVE_COLON = re.compile(r'^\s+SAVE\s*:\s*(\S+)\s*$')
RE_SAVE_BRACKET = re.compile(r'^\s+SAVE\s+\[(.+?)\]\s*$')
RE_SAVE_QUOTED = re.compile(r'^\s+SAVE\s+"(.+?)"\s*$')
RE_SAVE_SINGLE = re.compile(r"^\s+SAVE\s+'(.+?)'(?:\s+[\"'](.+?)[\"'])?\s*$")
RE_WAIT = re.compile(r'^\s+WAIT\s+\[?([\d.]+)\s*(?:ms|s)?\]?\s*$')
RE_WAIT_QUOTED = re.compile(r"^\s+WAIT\s+[\"']([\d.]+)\s*(ms|s)?[\"']\s*$")
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
    r'^\s+IF\s+\[(.+?)\]\s+\[([<>=!]+)\]\s+\[([-\d.]+)\s*(\w+)?\]\s+ELSE\s+ERROR\s+["\'](.+?)["\']\s*$'
)
RE_IF_ELSE_QUOTED = re.compile(
    r'^\s+IF\s+"(.+?)"\s+([<>=!]+)\s+"([-\d.]+)\s*(\w+)?"\s+ELSE\s+ERROR\s+"(.+?)"\s*$'
)
RE_IF_ELSE_SINGLE = re.compile(
    r"^\s+IF\s+'(.+?)'\s+([<>=!≤≥]+)\s+'(.+?)'\s+ELSE\s+ERROR\s+'(.+?)'\s*$"
)
RE_IF_STANDALONE = re.compile(
    r"^\s+IF\s+[\"'](.+?)[\"']\s+([<>=!≤≥]+)\s+[\"'](.+?)[\"']\s*$"
)
RE_ELSE_STANDALONE = re.compile(
    r"^\s+ELSE\s+(ERROR|INFO|WARN)\s+[\"'](.+?)[\"']\s*$"
)
RE_FUNC = re.compile(
    r"^\s+FUNC\s+[\"'](.+?)[\"']\s*=\s*[\"'](.+?)[\"']\s+[\"'](.+?)[\"']\s*$"
)
RE_MIN_MAX = re.compile(r'^\s+(MIN|MAX)\s+\[(.+?)\]\s*=\s*\[([-\d.]+)\s*(\w+)?\]\s*$')
RE_MIN_MAX_QUOTED = re.compile(r'^\s+(MIN|MAX)\s+"(.+?)"\s+"(.+?)"\s*$')
RE_MIN_MAX_SINGLE = re.compile(r"^\s+(MIN|MAX)\s+'(.+?)'\s+'(.+?)'\s*$")
RE_VAL = re.compile(r'^\s+VAL\s+\[(.+?)\]\s+\[(.+?)\]\s*$')
RE_VAL_QUOTED = re.compile(r'^\s+VAL\s+"(.+?)"\s+"(.+?)"\s*$')
RE_VAL_SINGLE = re.compile(r"^\s+VAL\s+'(.+?)'\s+'(.+?)'\s*$")
RE_SAMPLE = re.compile(r"^\s+SAMPLE\s+[\"'](.+?)[\"']\s+[\"'](.+?)[\"'](?:\s+[\"'](.+?)[\"'])?\s*$")
RE_GOTO = re.compile(r"^\s+GOTO\s+[\"'](.+?)[\"']\s*$")
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
    m = (RE_SAVE_COLON.match(line) or RE_SAVE_BRACKET.match(line)
         or RE_SAVE_QUOTED.match(line) or RE_SAVE_SINGLE.match(line))
    if not m:
        return None
    target = m.group(1).strip()
    # optional second group = namespace for SAVE 'var' 'ns'
    args = m.group(2).strip() if m.lastindex and m.lastindex >= 2 and m.group(2) else ""
    return CqlAction(kind="save", target=target, args=args, raw=stripped)


def _try_wait(line: str, stripped: str) -> CqlAction | None:
    m = RE_WAIT.match(line) or RE_WAIT_QUOTED.match(line)
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
    if m:
        val_str = m.group(3).split()[0]
        cond = CqlCondition(
            sensor=m.group(1), operator=m.group(2),
            value=float(val_str), unit=m.group(4) or "",
            on_fail="ERROR", fail_message=m.group(5),
        )
        return CqlAction(kind="if_else", condition=cond, raw=stripped)
    # Single-quote form: IF 'param' op 'value' ELSE ERROR 'msg'
    m = RE_IF_ELSE_SINGLE.match(line)
    if m:
        raw_val = m.group(3)
        parts = raw_val.split()
        try:
            val = float(parts[0])
        except ValueError:
            val = 0.0
        unit = " ".join(parts[1:]) if len(parts) > 1 else ""
        cond = CqlCondition(
            sensor=m.group(1), operator=m.group(2),
            value=val, unit=unit,
            on_fail="ERROR", fail_message=m.group(4),
        )
        return CqlAction(kind="if_else", condition=cond, raw=stripped)
    return None


def _try_if_standalone(line: str, stripped: str) -> CqlAction | None:
    m = RE_IF_STANDALONE.match(line)
    if not m:
        return None
    raw_val = m.group(3)
    # Try to extract numeric value; if not numeric, store as string in args
    parts = raw_val.split()
    try:
        val = float(parts[0])
        unit = parts[1] if len(parts) > 1 else ""
    except ValueError:
        val = 0.0
        unit = ""
    cond = CqlCondition(
        sensor=m.group(1), operator=m.group(2),
        value=val, unit=unit,
    )
    return CqlAction(kind="if_else", condition=cond, args=raw_val, raw=stripped)


def _try_min_max(line: str, stripped: str) -> CqlAction | None:
    m = RE_MIN_MAX.match(line)
    if m:
        return CqlAction(
            kind=m.group(1).lower(), target=m.group(2),
            args=f"{m.group(3)} {m.group(4) or ''}".strip(), raw=stripped,
        )
    m = RE_MIN_MAX_QUOTED.match(line) or RE_MIN_MAX_SINGLE.match(line)
    if m:
        return CqlAction(
            kind=m.group(1).lower(), target=m.group(2),
            args=m.group(3).strip(), raw=stripped,
        )
    return None


def _try_val(line: str, stripped: str) -> CqlAction | None:
    m = RE_VAL.match(line) or RE_VAL_QUOTED.match(line) or RE_VAL_SINGLE.match(line)
    if not m:
        return None
    return CqlAction(kind="val", target=m.group(1), args=m.group(2), raw=stripped)


def _try_sample(line: str, stripped: str) -> CqlAction | None:
    m = RE_SAMPLE.match(line)
    if not m:
        return None
    interval = m.group(3) or ""
    return CqlAction(
        kind="sample", target=m.group(1),
        args=f"{m.group(2)} {interval}".strip(), raw=stripped,
    )


def _try_goto(line: str, stripped: str) -> CqlAction | None:
    m = RE_GOTO.match(line)
    if not m:
        return None
    return CqlAction(kind="goto", target=m.group(1), raw=stripped)


def _try_else_standalone(line: str, stripped: str) -> CqlAction | None:
    m = RE_ELSE_STANDALONE.match(line)
    if not m:
        return None
    cond = CqlCondition(
        on_fail=m.group(1), fail_message=m.group(2),
    )
    return CqlAction(kind="else", condition=cond, raw=stripped)


def _try_func(line: str, stripped: str) -> CqlAction | None:
    m = RE_FUNC.match(line)
    if not m:
        return None
    return CqlAction(
        kind="func", target=m.group(1),
        method=m.group(2), args=m.group(3), raw=stripped,
    )


_ACTION_PARSERS = [
    _try_arrow_action,
    _try_task,
    _try_save,
    _try_wait,
    _try_set,
    _try_condition_range,
    _try_condition_cmp,
    _try_if_else,
    _try_if_standalone,
    _try_else_standalone,
    _try_min_max,
    _try_val,
    _try_sample,
    _try_goto,
    _try_func,
]
