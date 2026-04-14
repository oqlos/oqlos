# firmware/utils/dsl_parser.py

import re
from typing import Any

from oqlos.models.scenario import Goal, Step

_VALVE_NUM_MAP = {i: f'valve-{i}' for i in range(1, 15)}
_VALVE_ABBREV_MAP = {'nc': 'valve-nc', 'sc': 'valve-sc', 'wc': 'valve-wc'}
_OPEN_ACTIONS = {'włącz', 'wlacz', 'on', 'open', 'otwórz', 'otworz', 'start'}
_CLOSE_ACTIONS = {'wyłącz', 'wylacz', 'off', 'close', 'zamknij', 'stop'}
_WAIT_ACTIONS = {'czekaj', 'wait', 'delay', 'pauza', 'pause', 'timeout'}
_PUMP_OBJECT_RE = re.compile(r'\b(pump|pompa|sprężarka|sprezarka|compressor)\b', re.IGNORECASE)
_SENSOR_OBJECT_RE = re.compile(r'\b(czujnik|sensor)\b', re.IGNORECASE)
_SINGLE_QUOTED_LITERAL_RE = re.compile(r"'([^'\r\n]*)'")


def _normalize_quote_syntax(line: str) -> str:
    """Normalize single-quoted DSL literals to the existing double-quoted parser format."""
    return _SINGLE_QUOTED_LITERAL_RE.sub(lambda match: f'"{match.group(1)}"', str(line or ''))


def _looks_like_valve_object(obj: str) -> bool:
    return bool(re.search(r'\bzaw', obj, re.IGNORECASE) or re.search(r'\bvalve\b', obj, re.IGNORECASE))


def _looks_like_pump_object(obj: str) -> bool:
    return bool(_PUMP_OBJECT_RE.search(obj))


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


def _map_action_value(fn: str, obj: str, obj_raw: str, line: str, step_counter: int) -> tuple[str | None, Any, int | None, Step | None]:
    """Map function and object strings to action, value, duration, or a wait step."""
    if _looks_like_valve_object(obj):
        action = 'SET_VALVE'
        value = True if fn in _OPEN_ACTIONS else False if fn in _CLOSE_ACTIONS else True
        return action, value, None, None

    if _looks_like_pump_object(obj):
        action = 'SET_PUMP'
        numeric = _parse_numeric_value(obj_raw or line)
        value = 100 if fn in _OPEN_ACTIONS else 0 if fn in _CLOSE_ACTIONS else (numeric if numeric is not None else 50)
        return action, value, None, None

    if _looks_like_sensor_object(obj) and fn in ('odczytaj', 'zmierz', 'sprawdź', 'sprawdz', 'read', 'measure'):
        action = 'READ_SENSOR'
        value = None
        return action, value, None, None

    if fn in _WAIT_ACTIONS:
        try:
            num = float(re.findall(r"[-+]?[0-9]*\.?[0-9]+", obj_raw)[0])
            duration = int(num) if 'ms' in obj or 'mil' in obj else int(num * 1000)
        except Exception:
            duration = 1000

        label = re.sub(r'^(→\s*|AND\s*)', '', line).strip()
        step = Step(id=f'step-{step_counter}', action='WAIT', duration=duration, label=label)
        return 'WAIT', None, duration, step

    return None, None, None, None

def _parse_task_part(part: str, step_counter: int) -> Step | None:
    """Parse a single section of an inline TASK line."""
    normalized_part = _normalize_quote_syntax(part)
    mm = re.match(
        r'(?:\[(?P<fn_br>[^\]]+)\]|"(?P<fn_quote>[^"]+)"|(?P<fn_plain>[^\[\"]+?))\s*'
        r'(?:\[(?P<obj_br>[^\]]+)\]|"(?P<obj_quote>[^"]+)")\s*$',
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
    match = re.match(r'PUMP\s*"([^"]*)"\s*$', normalized_line, re.IGNORECASE) or \
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


def _parse_set_line(line: str, step_counter: int) -> Step | None:
    """Parse `SET 'zawór 2' '1'` or legacy `SET [zawór 2] = [1]`."""
    normalized_line = _normalize_quote_syntax(line)
    match = re.match(r'SET\s*"([^"]*)"\s*"([^"]*)"\s*$', normalized_line, re.IGNORECASE) or \
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

    # SET "PUMP" "value" — pump absorbed into SET
    if param in ('pump', 'pompa', 'sprężarka', 'sprezarka', 'compressor'):
        lowered_value = value_raw.lower()
        if lowered_value in _OPEN_ACTIONS:
            pval: Any = 100
        elif lowered_value in _CLOSE_ACTIONS:
            pval = 0
        else:
            pval = _parse_numeric_value(value_raw)
            if pval is None:
                pval = value_raw
        return Step(id=f'step-{step_counter}', action='SET_PUMP', peripheral='pump-main', value=pval, label=line)

    peripheral = _map_peripheral(param)
    if not peripheral:
        return None

    lowered_value = value_raw.lower()
    numeric = _parse_numeric_value(value_raw)

    if peripheral.startswith('valve'):
        if lowered_value in {'1', 'true', 'on', 'open'}:
            value = True
        elif lowered_value in {'0', 'false', 'off', 'close'}:
            value = False
        else:
            value = bool(numeric) if numeric is not None else True
        return Step(id=f'step-{step_counter}', action='SET_VALVE', peripheral=peripheral, value=value, label=line)

    if peripheral == 'pump-main':
        if lowered_value in _OPEN_ACTIONS:
            value = 100
        elif lowered_value in _CLOSE_ACTIONS:
            value = 0
        else:
            value = numeric if numeric is not None else value_raw
        return Step(id=f'step-{step_counter}', action='SET_PUMP', peripheral=peripheral, value=value, label=line)

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
        r'(→|AND)\s+(?:\[(?P<fn_br>[^\]]+)\]|"(?P<fn_quote>[^"]+)"|(?P<fn_plain>[^\[\"]+?))\s*'
        r'(?:\[(?P<obj_br>[^\]]+)\]|"(?P<obj_quote>[^"]+)")\s*$',
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
    m_if = re.match(r'IF\s*"([^"]*)"\s*(>=|<=|>|<|=|!=)\s*"([^"]*)"', normalized_line, re.IGNORECASE) or \
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
) -> tuple[int, bool, bool]:
    """Expand an in-goal FUNC call into its defined runtime steps."""
    normalized_line = _normalize_quote_syntax(line)
    m_quote = re.match(r'FUNC\s*"([^"]*)"(?:\s+.*)?$', normalized_line, re.IGNORECASE)
    m_bracket = re.match(r"FUNC\s*\[([^\]]+)\](?:\s+.*)?$", normalized_line, re.IGNORECASE)
    m_colon = re.match(r"FUNC:\s*(.+)$", normalized_line, re.IGNORECASE)
    if not m_quote and not m_bracket and not m_colon:
        return step_counter, False, False

    # `FUNC: name` at top level is a definition, not a call.
    if m_colon and indent == 0:
        return step_counter, False, False

    func_name = (m_quote.group(1) if m_quote else m_bracket.group(1) if m_bracket else m_colon.group(1)).strip()
    if not func_name:
        return step_counter, True, True
    if func_name in call_stack:
        return step_counter, True, True

    func_lines = func_defs.get(func_name)
    if not func_lines:
        return step_counter, True, True

    for func_line in func_lines:
        step_counter = _parse_runtime_line(func_line, step_counter, steps, func_defs, indent=2, call_stack=call_stack + (func_name,))
    return step_counter, True, False


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

    if re.match(r"TASK(?:\s*:)?\s*(?:\[|\")", normalized_line, re.IGNORECASE):
        next_counter, had_invalid_part = _parse_inline_task(line, step_counter, steps)
        if had_invalid_part:
            record_invalid()
        return next_counter

    if re.match(r'SET\s*["\[]', normalized_line, re.IGNORECASE):
        step = _parse_set_line(line, step_counter)
        if step:
            steps.append(step)
            return step_counter + 1
        record_invalid()
        return step_counter

    if re.match(r'PUMP\s*["\[]', normalized_line, re.IGNORECASE):
        step = _parse_pump_line(line, step_counter)
        if step:
            steps.append(step)
            return step_counter + 1
        record_invalid()
        return step_counter

    if re.match(r'(?:WAIT|DELAY|PAUSE|TIMEOUT)\s*["\[]', normalized_line, re.IGNORECASE):
        step = _parse_task_part(line, step_counter)
        if step:
            steps.append(step)
            return step_counter + 1
        record_invalid()
        return step_counter

    step_counter, parsed, invalid_func = _parse_func_call(line, step_counter, steps, func_defs, indent=indent, call_stack=call_stack)
    if parsed:
        if invalid_func:
            record_invalid()
        return step_counter

    step_counter, parsed = _parse_action_line(line, step_counter, steps)
    if parsed:
        return step_counter
    if re.match(r'(?:AND|→)\s+', normalized_line, re.IGNORECASE):
        record_invalid()
        return step_counter

    step_counter, parsed = _parse_if_condition(line, step_counter, steps)
    if parsed:
        return step_counter
    if re.match(r'IF\s+', normalized_line, re.IGNORECASE):
        record_invalid()
        return step_counter

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

