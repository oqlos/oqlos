# oqlos/core/parser.py — DSL parser public API + runtime dispatcher

import re

from oqlos.models.dsl_models import OqlAction, OqlGoal
from oqlos.models.scenario import Goal, Step, ValidationRule
from ._dsl_helpers import _normalize_quote_syntax
from ._line_parsers import (
    _parse_action_line,
    _parse_if_condition,
    _parse_inline_task,
    _parse_pump_line,
    _parse_set_line,
    _parse_task_part,
)
from ._func_resolver import (
    MAX_FUNC_DEPTH as MAX_FUNC_DEPTH,
    _collect_function_definitions,
    _parse_func_call,
)


_REGEX_DISPATCH: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"SET\s+(?:WAIT|DELAY|PAUSE|TIMEOUT)\s*['\[]", re.IGNORECASE), "set"),
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


# ── Flat OQL (v3/v4/v5) → runtime Goal ───────────────────────────────
#
# Flat OQL sources are parsed by the canonical document parser and the
# resulting OqlActions are lowered
# onto the same runtime ``Step`` builders used by the legacy dialect, so
# both paths produce identical step structures.

# Valid flat-OQL kinds that have no runtime-step equivalent (logging,
# labels, control-flow markers evaluated elsewhere) — skipped silently.
_FLAT_NON_RUNTIME_KINDS = {
    'log', 'save', 'val', 'sample', 'goto', 'retry',
    'else', 'if_else', 'endloop', 'endif', 'end',
}


def _flat_condition_lines(action: OqlAction) -> list[str]:
    """Render a kind=condition action (CHECK/IF_DELTA) as synthetic IF lines."""
    cond = action.condition
    if cond is None:
        return []
    lines: list[str] = []
    if cond.value_min is not None:
        lines.append(f"IF '{cond.sensor}' >= '{cond.value_min}'")
    if cond.value_max is not None:
        lines.append(f"IF '{cond.sensor}' <= '{cond.value_max}'")
    if not lines and cond.value is not None:
        lines.append(f"IF '{cond.sensor}' {cond.operator or '='} '{cond.value}'")
    return lines


def _flat_action_synthetic_lines(action: OqlAction) -> list[str] | None:
    """Map one flat-OQL action to synthetic legacy lines, or None if unmapped."""
    kind = action.kind
    if kind == 'set':
        return [f"SET '{action.target}' '{action.args}'"]
    if kind in ('wait', 'pump'):
        keyword = 'WAIT' if kind == 'wait' else 'POMPA'
        return [f"SET '{keyword}' '{action.args}'"]
    if kind in ('min', 'max'):
        op = '>=' if kind == 'min' else '<='
        return [f"IF '{action.target}' {op} '{action.args}'"]
    if kind == 'if':
        return [f"IF '{action.target}' {action.method or '='} '{action.args}'"]
    if kind == 'condition':
        return _flat_condition_lines(action)
    return None


def _flat_repeat_count(args: str) -> int:
    """Loop repetition count for REPEAT blocks (clamped to a sane range)."""
    try:
        count = int(float(str(args).strip() or 1))
    except (TypeError, ValueError):
        count = 1
    return max(1, min(count, 100))


def _flat_actions_to_steps(
    actions: list[OqlAction],
    steps: list[Step],
    invalid_lines: list[str],
    goal_meta: dict,
) -> None:
    """Lower flat-OQL actions onto runtime steps via compatibility builders."""
    def record_invalid(raw: str) -> None:
        candidate = str(raw or '').strip()
        if candidate and candidate not in invalid_lines:
            invalid_lines.append(candidate)

    for action in actions:
        kind = action.kind
        if kind == 'else' and action.method == 'INFO':
            # PASS 'msg' — positive-verdict declaration.
            goal_meta['pass_message'] = action.args
            continue
        if kind == 'else' and action.method == 'ERROR':
            # FAIL 'msg' — negative-verdict declaration.
            goal_meta['fail_messages'].append(action.args)
            continue
        if kind == 'loop_block':
            inner: list[OqlAction] = list(action.loop_actions)
            for _ in range(_flat_repeat_count(action.args)):
                _flat_actions_to_steps(inner, steps, invalid_lines, goal_meta)
            continue
        if kind in _FLAT_NON_RUNTIME_KINDS:
            continue

        lines = _flat_action_synthetic_lines(action)
        if lines is None:
            record_invalid(action.raw)
            continue
        for line in lines:
            if line.startswith('IF '):
                _, parsed = _parse_if_condition(line, len(steps), steps)
            else:
                step = _parse_set_line(line, len(steps))
                parsed = step is not None
                if step is not None:
                    steps.append(step)
            if not parsed:
                record_invalid(action.raw)


def _flat_goal_to_runtime(goal: OqlGoal, scenario_id: str) -> tuple[Goal, list[str]]:
    """Convert one flat-OQL task projection into the runtime goal structure."""
    steps: list[Step] = []
    invalid_lines: list[str] = []
    goal_meta: dict = {'pass_message': '', 'fail_messages': []}

    for cql_step in goal.steps:
        _flat_actions_to_steps(cql_step.actions, steps, invalid_lines, goal_meta)

    # FAIL messages are carried as inert validation rules (executor skips
    # rules whose peripheral is unknown) so the verdict text is preserved.
    criteria = [
        ValidationRule(peripheral='', condition='', errorMessage=msg)
        for msg in goal_meta['fail_messages'] if msg
    ]
    runtime_goal = Goal(
        id=f'goal-runtime-{scenario_id}',
        name=goal.name,
        description='Runtime goal from DSL',
        steps=steps,
        expectedResult=goal_meta['pass_message'],
        validationCriteria=criteria,
    )
    return runtime_goal, invalid_lines


def _parse_flat_oql_to_goal(dsl: str, scenario_id: str) -> tuple[Goal | None, list[str]]:
    """Parse flat OQL (v3/v4/v5) through the canonical parser.

    Contract: a single Goal per call (like the legacy path). When the source
    defines several GOAL blocks, the first one is returned and a note is
    appended to the issues list.
    """
    from .oql_document import parse_oql_document

    doc = parse_oql_document(dsl)
    issues: list[str] = list(doc.errors)
    goals = [g for g in doc.goals if not g.name.startswith('[CONFIG]')]
    if not goals:
        return None, issues

    if len(goals) > 1:
        issues.append(
            f"flat OQL: {len(goals)} runnable blocks; only the first "
            f"('{goals[0].name}') was converted to a runtime goal"
        )

    goal, invalid_lines = _flat_goal_to_runtime(goals[0], scenario_id)
    issues.extend(invalid_lines)
    return goal, issues


def parse_dsl_to_goal_with_issues(dsl: str, scenario_id: str) -> tuple[Goal | None, list[str]]:
    """Parse DSL and return a runtime goal plus invalid runtime lines."""
    if not isinstance(dsl, str):
        return None, []

    from ._oql_adapter import is_flat_oql
    if is_flat_oql(dsl):
        return _parse_flat_oql_to_goal(dsl, scenario_id)

    raw_lines = [str(line).rstrip() for line in dsl.split('\n') if str(line).strip()]
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
