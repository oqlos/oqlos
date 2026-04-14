# oqlos/core/parser.py — DSL parser public API + runtime dispatcher

import re

from oqlos.models.scenario import Goal, Step
from ._dsl_helpers import _normalize_quote_syntax
from ._line_parsers import (
    _parse_action_line,
    _parse_if_condition,
    _parse_inline_task,
    _parse_pump_line,
    _parse_set_line,
    _parse_task_part,
)
from ._func_resolver import MAX_FUNC_DEPTH, _collect_function_definitions, _parse_func_call


_REGEX_DISPATCH: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"SET\s*['\[]", re.IGNORECASE), "set"),
    (re.compile(r"PUMP\s*['\[]", re.IGNORECASE), "pump"),
    (re.compile(r"(?:WAIT|DELAY|PAUSE|TIMEOUT)\s*['\[]", re.IGNORECASE), "wait"),
]


def _dispatch_simple_parser(
    kind: str, line: str, step_counter: int, steps: list[Step],
) -> Step | None:
    """Dispatch to the appropriate simple-line parser."""
    if kind == "set":
        return _parse_set_line(line, step_counter)
    if kind == "pump":
        return _parse_pump_line(line, step_counter)
    return _parse_task_part(line, step_counter)


def _try_action_or_condition(
    line: str,
    normalized_line: str,
    step_counter: int,
    steps: list[Step],
    record_invalid,
) -> tuple[int, bool]:
    """Try action_line and if_condition parsers. Returns (step_counter, matched)."""
    step_counter, parsed = _parse_action_line(line, step_counter, steps)
    if parsed:
        return step_counter, True
    if re.match(r'(?:AND|→)\s+', normalized_line, re.IGNORECASE):
        record_invalid()
        return step_counter, True

    step_counter, parsed = _parse_if_condition(line, step_counter, steps)
    if parsed:
        return step_counter, True
    if re.match(r'IF\s+', normalized_line, re.IGNORECASE):
        record_invalid()
        return step_counter, True

    return step_counter, False


def _parse_runtime_line(
    line: str,
    step_counter: int,
    steps: list[Step],
    func_defs: dict[str, list[str]],
    indent: int = 0,
    call_stack: tuple[str, ...] = (),
    invalid_lines: list[str] | None = None,
) -> int:
    """Parse one runtime-relevant DSL line into executable firmware steps."""
    def record_invalid() -> None:
        if invalid_lines is None:
            return
        candidate = str(line or '').strip()
        if candidate and candidate not in invalid_lines:
            invalid_lines.append(candidate)

    normalized_line = _normalize_quote_syntax(line)

    if re.match(r"TASK\s+\d+:", normalized_line, re.IGNORECASE):
        return step_counter

    if re.match(r"TASK(?:\s*:)?\s*(?:\[|')", normalized_line, re.IGNORECASE):
        next_counter, had_invalid_part = _parse_inline_task(line, step_counter, steps)
        if had_invalid_part:
            record_invalid()
        return next_counter

    for pattern, kind in _REGEX_DISPATCH:
        if pattern.match(normalized_line):
            step = _dispatch_simple_parser(kind, line, step_counter, steps)
            if step:
                steps.append(step)
                return step_counter + 1
            record_invalid()
            return step_counter

    step_counter, parsed, invalid_func = _parse_func_call(
        line, step_counter, steps, func_defs, indent=indent,
        call_stack=call_stack, parse_line_fn=_parse_runtime_line,
    )
    if parsed:
        if invalid_func:
            record_invalid()
        return step_counter

    step_counter, matched = _try_action_or_condition(
        line, normalized_line, step_counter, steps, record_invalid,
    )
    return step_counter


def parse_dsl_to_goal_with_issues(dsl: str, scenario_id: str) -> tuple[Goal | None, list[str]]:
    """Parse DSL and return a runtime goal plus invalid runtime lines."""
    if not isinstance(dsl, str):
        return None, []

    raw_lines = [str(l).rstrip() for l in dsl.split('\n') if str(l).strip()]
    if not raw_lines:
        return None, []

    func_defs = _collect_function_definitions(raw_lines)

    goal_idx, goal_name = -1, ''
    for idx, raw_line in enumerate(raw_lines):
        line = raw_line.strip()
        mg = re.match(r"GOAL:\s*(.+)", line, re.IGNORECASE)
        if mg:
            goal_idx, goal_name = idx, mg.group(1).strip()
            break

    if goal_idx < 0:
        return None, []

    steps: list[Step] = []
    step_counter = 0
    invalid_lines: list[str] = []

    i = goal_idx + 1
    while i < len(raw_lines):
        raw_line = raw_lines[i]
        line = raw_line.strip()
        indent = len(raw_line) - len(raw_line.lstrip())

        if indent == 0 and re.match(r"GOAL:\s*(.+)", line, re.IGNORECASE):
            break

        if indent == 0 and re.match(r"FUNC:\s*(.+)", line, re.IGNORECASE):
            i += 1
            continue

        step_counter = _parse_runtime_line(
            line,
            step_counter,
            steps,
            func_defs,
            indent=indent,
            invalid_lines=invalid_lines,
        )

        i += 1

    goal = Goal(
        id=f'goal-runtime-{scenario_id}',
        name=goal_name,
        description='Runtime goal from DSL',
        steps=steps,
        expectedResult='',
        validationCriteria=[]
    )
    return goal, invalid_lines

def parse_dsl_to_goal(dsl: str, scenario_id: str) -> Goal | None:
    """Parse DSL string to a runtime Goal with Steps.

    DSL supported forms:
      - GOAL: <name>
      - → <Action> [<Object>]
      - AND <Action> [<Object>]
      - IF [<param>] [<op>] [<value>]
    """
    goal, _invalid_lines = parse_dsl_to_goal_with_issues(dsl, scenario_id)
    return goal
