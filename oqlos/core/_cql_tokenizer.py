"""CQL tokenizer — regex patterns and individual action parsers."""

from __future__ import annotations

import re

from oqlos.models.dsl_models import CqlAction, CqlCondition

# ═══════════════════════════════════════════════════════════════════════════════
# Regex patterns
# ═══════════════════════════════════════════════════════════════════════════════

RE_METADATA_KV = re.compile(r'^(SCENARIO|DEVICE_TYPE|DEVICE_MODEL|MANUFACTURER)\s*:\s*"?(.+?)"?\s*$', re.IGNORECASE)
RE_INTERVAL = re.compile(r'^\s*-\s+(tt#\d+)\s*:\s*"(.+?)"\s+period\s*:\s*(\d+)\s*months?\s*$', re.IGNORECASE)
RE_SCENARIO = re.compile(r'^@(\w+(?:\.\w+)*)\s*$', re.IGNORECASE)
RE_GOAL_SIMPLE = re.compile(r'^GOAL\s*:\s*(.+)$', re.IGNORECASE)
RE_GOAL_NAMED = re.compile(r'^  (\w[\w\s]*\w)\s*:\s*$')
RE_CONFIG_SIMPLE = re.compile(r'^CONFIG\s*:\s*(.+)$', re.IGNORECASE)
RE_CONFIG_NAMED = re.compile(r'^  CONFIG\s+(\w[\w\s]*\w)\s*:\s*$', re.IGNORECASE)
RE_STEP_NUM = re.compile(r'^\s+(\d+(?:\.\d+)?)\s*[.)]?\s*(.+?):\s*$', re.IGNORECASE)

# Action pattern (Arrow)
RE_ACTION_ARROW = re.compile(r'^\s+→\s+(\w+)\.(\w+)\s*(.*)$')
RE_TASK_BRACKET = re.compile(r'^\s*TASK\s*:\s*(.+)$', re.IGNORECASE)

# Flat DSL Patterns (No arrows)
RE_SAVE = re.compile(r"^\s*SAVE\s+['\"](.+?)['\"](?:\s+['\"](.+?)['\"])?\s*$", re.IGNORECASE)
RE_SAVE_BRACKET = re.compile(r"^\s*SAVE\s+\[([^\]]+)\](?:\s+\[([^\]]+)\])?\s*$", re.IGNORECASE)
RE_WAIT = re.compile(r"^\s*WAIT\s+['\"]?([\d.]+)\s*(?:ms|s)?['\"]?\s*$", re.IGNORECASE)
RE_SET = re.compile(r"^\s*SET\s+['\"](.+?)['\"]\s+['\"](.+?)['\"]\s*$", re.IGNORECASE)
RE_SET_BRACKET = re.compile(r"^\s*SET\s*\[([^\]]+)\]\s*=\s*\[([^\]]+)\]\s*$", re.IGNORECASE)
RE_MIN_MAX = re.compile(r"^\s*(MIN|MAX)\s+['\"](.+?)['\"]\s+['\"](.+?)['\"]\s*$", re.IGNORECASE)
RE_MIN_MAX_BRACKET = re.compile(r"^\s*(MIN|MAX)\s*\[([^\]]+)\]\s*=\s*\[([^\]]+)\]\s*$", re.IGNORECASE)
RE_VAL = re.compile(r"^\s*VAL\s+['\"](.+?)['\"]\s+['\"](.+?)['\"]\s*$", re.IGNORECASE)
RE_VAL_BRACKET = re.compile(r"^\s*VAL\s*\[([^\]]+)\]\s*\[([^\]]+)\]\s*$", re.IGNORECASE)
RE_GOTO = re.compile(r"^\s*GOTO\s+['\"](.+?)['\"]\s*$", re.IGNORECASE)
RE_GOTO_BRACKET = re.compile(r"^\s*GOTO\s*\[([^\]]+)\]\s*$", re.IGNORECASE)
RE_SAVE_WS = re.compile(r"^\s*SAVE:\s*(\w+)\s*$", re.IGNORECASE)
RE_ERROR = re.compile(r"^\s*(?:ELSE\s+)?ERROR\s+['\"](.+?)['\"]\s*$", re.IGNORECASE)
RE_LOG = re.compile(r"^\s*LOG\s+['\"](.+?)['\"]\s*$", re.IGNORECASE)
RE_FUNC = re.compile(r"^\s*FUNC\s+['\"](.+?)['\"]\s*=\s*['\"](.+?)['\"]\s*['\"](.+?)['\"]\s*$", re.IGNORECASE)
RE_SAMPLE = re.compile(r"^\s*SAMPLE\s+['\"](.+?)['\"]\s+['\"](.+?)['\"](?:\s+['\"](.+?)['\"])?\s*$", re.IGNORECASE)
RE_API = re.compile(r"^\s*(API_GET|API_POST|API_PUT|API_DELETE)\s+['\"](.+?)['\"]\s*$", re.IGNORECASE)
RE_ASSERT = re.compile(r"^\s*(ASSERT_STATUS|ASSERT_JSON|ASSERT_VALVE|ASSERT_SENSOR)\s+.*$", re.IGNORECASE)
RE_EXPECT = re.compile(r"^\s*(EXPECT_DEVICE|EXPECT_I2C_BUS|EXPECT_I2C_CHIP)\s+.*$", re.IGNORECASE)
RE_SHELL = re.compile(r"^\s*(SHELL_EXPORT|SAVE_JSON|GET_SENSOR)\s+.*$", re.IGNORECASE)

# Legacy / Specific patterns
RE_CONDITION_RANGE = re.compile(
    r'^\s+(?:Δ?)(AI\d+|Timer|[\w\s-]+)\s*([∈∊])\s*\[([-\d.]+)\s*,\s*([-\d.]+)\]\s*(\w+)?\s*\|\s*(\w+)\s*(?:"(.+?)")?\s*$', re.IGNORECASE
)
RE_CONDITION_CMP = re.compile(
    r'^\s+(?:Δ?)(AI\d+|Timer|[\w\s-]+)\s*([≤≥<>=]+)\s*([-\d.]+)\s*(\w+)?\s*\|\s*(\w+)\s*(?:"(.+?)")?\s*$', re.IGNORECASE
)

# IF / Scoping Patterns
RE_IF_ELSE_SINGLE = re.compile(
    r"^\s*IF\s+['\"](.+?)['\"]\s+([<>=!≤≥]+)\s+['\"](.+?)['\"]\s+ELSE\s+ERROR\s+['\"](.+?)['\"]\s*$", re.IGNORECASE
)
RE_IF_ELSE_SINGLE_BRACKET = re.compile(
    r"^\s*IF\s*\[([^\]]+)\]\s*\[([<>=!≤≥]+)\]\s*\[([^\]]+)\]\s+ELSE\s+ERROR\s+['\"](.+?)['\"]\s*$", re.IGNORECASE
)
RE_IF_BLOCK = re.compile(r"^\s*IF\s+['\"](.+?)['\"]\s+([<>=!≤≥]+)\s+['\"](.+?)['\"]\s*$", re.IGNORECASE)
RE_IF_BLOCK_BRACKET = re.compile(
    r"^\s*IF\s*\[([^\]]+)\]\s*\[([<>=!≤≥]+)\]\s*\[([^\]]+)\]\s*$", re.IGNORECASE
)
RE_IF_FAIL_BLOCK = re.compile(r'^\s*IF_FAIL\s+["\'](.+?)["\']\s+THEN\s*$', re.IGNORECASE)
RE_ELSE_BLOCK = re.compile(r"^\s*ELSE\s*$", re.IGNORECASE)
RE_ENDIF = re.compile(r"^\s*ENDIF\s*$", re.IGNORECASE)
RE_END = re.compile(r"^\s*END\s*$", re.IGNORECASE)

# Loops
RE_LOOP_START = re.compile(r"^\s*LOOP\s+(?:(\d+)\s+TIMES|WHILE\s+['\"](.+?)['\"]\s+([<>=!≤≥]+)\s+['\"](.+?)['\"])\s*$", re.IGNORECASE)
RE_ENDLOOP = re.compile(r"^\s*ENDLOOP\s*$", re.IGNORECASE)

# Variables
RE_VAR = re.compile(r"^\s*VAR\s+(\w+)\s*=\s*['\"](.+?)['\"]\s*$", re.IGNORECASE)

# Meta
RE_DESC = re.compile(r'^\s*description\s*:\s*"(.+?)"\s*$', re.IGNORECASE)
RE_EDITABLE = re.compile(r'^\s*editable\s*:\s*(true|false)\s*$', re.IGNORECASE)
RE_ALARM = re.compile(r'^\s*alarm\s*:\s*"(.+?)"\s*$', re.IGNORECASE)
RE_INTERVALS_REF = re.compile(r'^\s*intervals\s*:\s*\[(.+?)\]\s*$', re.IGNORECASE)
RE_BLOCK_HEADER = re.compile(r'^(OUTPUTS|SENSORS|VALIDATION_MODES|META)\s*:\s*$', re.IGNORECASE)

# ═══════════════════════════════════════════════════════════════════════════════
# Parser factories
# ═══════════════════════════════════════════════════════════════════════════════

def _make_args_parser(regex, kind):
    """Factory: match regex, return CqlAction(kind, args=group(1))."""
    def parser(line, stripped):
        m = regex.match(line)
        if not m:
            return None
        return CqlAction(kind=kind, args=m.group(1), raw=stripped)
    return parser


def _make_keyword_parser(regex, kind):
    """Factory: match regex (no captures), return CqlAction(kind)."""
    def parser(line, stripped):
        if regex.match(line):
            return CqlAction(kind=kind, raw=stripped)
        return None
    return parser


def _make_method_parser(regex, kind):
    """Factory: match regex, return CqlAction(kind, method=group(1), args=stripped)."""
    def parser(line, stripped):
        m = regex.match(line)
        if not m:
            return None
        return CqlAction(kind=kind, method=m.group(1), args=stripped, raw=stripped)
    return parser


def _match_first(line: str, *regexes):
    """Return the first successful regex match for *line*."""
    for regex in regexes:
        match = regex.match(line)
        if match:
            return match
    return None


def _parse_condition_value(raw_value: str, *, keep_unit_tail: bool) -> tuple[float, str]:
    """Parse the leading numeric token and any remaining unit text."""
    parts = raw_value.split()
    try:
        value = float(parts[0])
    except (IndexError, ValueError):
        return 0.0, ""

    if len(parts) <= 1:
        return value, ""
    if keep_unit_tail:
        return value, " ".join(parts[1:])
    return value, parts[1]


# ═══════════════════════════════════════════════════════════════════════════════
# Individual action parsers
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
    m = _match_first(line, RE_SAVE, RE_SAVE_BRACKET)
    if not m:
        return None
    target = m.group(1).strip()
    args = m.group(2).strip() if m.lastindex and m.lastindex >= 2 and m.group(2) else ""
    return CqlAction(kind="save", target=target, args=args, raw=stripped)

_try_wait = _make_args_parser(RE_WAIT, "wait")

def _try_set(line: str, stripped: str) -> CqlAction | None:
    m = _match_first(line, RE_SET, RE_SET_BRACKET)
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
    m = _match_first(line, RE_IF_ELSE_SINGLE, RE_IF_ELSE_SINGLE_BRACKET)
    if not m:
        return None
    raw_val = m.group(3)
    val, unit = _parse_condition_value(raw_val, keep_unit_tail=True)
    cond = CqlCondition(
        sensor=m.group(1), operator=m.group(2),
        value=val, unit=unit,
        on_fail="ERROR", fail_message=m.group(4),
    )
    return CqlAction(kind="if_else", condition=cond, raw=stripped)

def _try_if_block(line: str, stripped: str) -> CqlAction | None:
    m = _match_first(line, RE_IF_BLOCK, RE_IF_BLOCK_BRACKET)
    if not m:
        return None
    raw_val = m.group(3)
    val, unit = _parse_condition_value(raw_val, keep_unit_tail=False)
    cond = CqlCondition(
        sensor=m.group(1), operator=m.group(2),
        value=val, unit=unit,
    )
    return CqlAction(kind="if_block", condition=cond, args=raw_val, raw=stripped)


def _try_if_fail_block(line: str, stripped: str) -> CqlAction | None:
    m = RE_IF_FAIL_BLOCK.match(line)
    if not m:
        return None
    return CqlAction(kind="if_fail_block", target=m.group(1).strip(), raw=stripped)


def _try_if_standalone(line: str, stripped: str) -> CqlAction | None:
    """Backward-compatible helper used by tokenizer tests."""
    action = _try_if_block(line, stripped)
    if action is None:
        return None
    action.kind = "if_else"
    return action


def _try_else_standalone(line: str, stripped: str) -> CqlAction | None:
    """Backward-compatible helper for ELSE ACTION 'message' lines."""
    m = re.match(r"^\s*ELSE\s+(ERROR|INFO|WARNING)\s+['\"](.+?)['\"]\s*$", line, re.IGNORECASE)
    if not m:
        return None
    return CqlAction(
        kind="else",
        condition=CqlCondition(on_fail=m.group(1).upper(), fail_message=m.group(2)),
        raw=stripped,
    )

_try_endif = _make_keyword_parser(RE_ENDIF, "endif")
_try_end = _make_keyword_parser(RE_END, "end")
_try_else_block = _make_keyword_parser(RE_ELSE_BLOCK, "else_block")

def _try_min_max(line: str, stripped: str) -> CqlAction | None:
    m = _match_first(line, RE_MIN_MAX, RE_MIN_MAX_BRACKET)
    if not m:
        return None
    return CqlAction(
        kind=m.group(1).lower(), target=m.group(2),
        args=m.group(3).strip(), raw=stripped,
    )

def _try_val(line: str, stripped: str) -> CqlAction | None:
    m = _match_first(line, RE_VAL, RE_VAL_BRACKET)
    if not m:
        return None
    return CqlAction(kind="val", target=m.group(1), args=m.group(2), raw=stripped)

_try_endloop = _make_keyword_parser(RE_ENDLOOP, "endloop")

def _try_loop_start(line: str, stripped: str) -> CqlAction | None:
    m = RE_LOOP_START.match(line)
    if not m:
        return None
    if m.group(1):
        return CqlAction(kind="loop_block", method="times", args=m.group(1), raw=stripped)
    raw_val = m.group(4)
    parts = raw_val.split()
    try:
        val = float(parts[0])
        unit = parts[1] if len(parts) > 1 else ""
    except ValueError:
        val = 0.0
        unit = ""
    return CqlAction(
        kind="loop_block", method="while",
        condition=CqlCondition(sensor=m.group(2), operator=m.group(3), value=val, unit=unit),
        args=raw_val, raw=stripped
    )

def _try_var(line: str, stripped: str) -> CqlAction | None:
    m = RE_VAR.match(line)
    if not m:
        return None
    return CqlAction(kind="var_set", target=m.group(1), args=m.group(2), raw=stripped)

_try_error = _make_args_parser(RE_ERROR, "error")
_try_log = _make_args_parser(RE_LOG, "log")

def _try_func(line: str, stripped: str) -> CqlAction | None:
    m = RE_FUNC.match(line)
    if not m:
        return None
    return CqlAction(
        kind="func", target=m.group(1), method=m.group(2),
        args=m.group(3), raw=stripped
    )

def _try_sample(line: str, stripped: str) -> CqlAction | None:
    m = RE_SAMPLE.match(line)
    if not m:
        return None
    args = m.group(2)
    if m.group(3):
        args = f"{args} {m.group(3)}"
    return CqlAction(
        kind="sample", target=m.group(1), method=m.group(2),
        args=args, raw=stripped
    )

def _try_api(line: str, stripped: str) -> CqlAction | None:
    m = RE_API.match(line)
    if not m:
        return None
    return CqlAction(kind="api", method=m.group(1), args=m.group(2), raw=stripped)

_try_assert = _make_method_parser(RE_ASSERT, "assert")
_try_expect = _make_method_parser(RE_EXPECT, "expect")
_try_shell = _make_method_parser(RE_SHELL, "shell")

def _try_goto(line: str, stripped: str) -> CqlAction | None:
    m = _match_first(line, RE_GOTO, RE_GOTO_BRACKET)
    if not m:
        return None
    return CqlAction(kind="goto", target=m.group(1).strip(), raw=stripped)

def _try_save_ws(line: str, stripped: str) -> CqlAction | None:
    m = RE_SAVE_WS.match(line)
    if not m:
        return None
    return CqlAction(kind="save", target=m.group(1).strip(), raw=stripped)

_ACTION_PARSERS = [
    _try_if_else,
    _try_if_block,
    _try_if_fail_block,
    _try_else_block,
    _try_endif,
    _try_end,
    _try_loop_start,
    _try_endloop,
    _try_var,
    _try_arrow_action,
    _try_task,
    _try_save,
    _try_wait,
    _try_set,
    _try_condition_range,
    _try_condition_cmp,
    _try_min_max,
    _try_val,
    _try_else_standalone,
    _try_error,
    _try_log,
    _try_func,
    _try_sample,
    _try_api,
    _try_assert,
    _try_expect,
    _try_shell,
    _try_goto,
    _try_save_ws,
]
