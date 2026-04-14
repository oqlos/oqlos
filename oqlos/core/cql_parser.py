"""
CQL Parser — parses .cql source into AST nodes + validates structure.

Supports two CQL dialects:
  1. Simple CQL:   GOAL:, TASK:, SAVE, WAIT, IF...ELSE, MIN, MAX, VAL
  2. ConnectGo:    @Namespace.Name, → Action, AI02 ∈ [min, max], SAVE: var
"""

from __future__ import annotations

import re

from oqlos.models.dsl_models import (
    CqlAction,
    CqlCondition,
    CqlDocument,
    CqlGoal,
    CqlInterval,
    CqlMetadata,
    CqlScenario,
    CqlStep,
)

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
# RE_PUMP removed - now handled as SET 'pompa'
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
# Blocks we recognize but skip (metadata sections)
RE_BLOCK_HEADER = re.compile(r'^(OUTPUTS|SENSORS|VALIDATION_MODES|META)\s*:\s*$')


# ═══════════════════════════════════════════════════════════════════════════════
# Private helpers — extracted from parse_cql to reduce cyclomatic complexity
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_metadata_kv(doc: CqlDocument, stripped: str) -> bool:
    """Parse top-level SCENARIO/DEVICE_TYPE/DEVICE_MODEL/MANUFACTURER lines.

    Returns True if the line was consumed.
    """
    m = RE_METADATA_KV.match(stripped)
    if not m:
        return False
    key, val = m.group(1), m.group(2).strip().strip('"')
    if key == "SCENARIO":
        doc.metadata.scenario_name = val
    elif key == "DEVICE_TYPE":
        doc.metadata.device_type = val
    elif key == "DEVICE_MODEL":
        doc.metadata.device_model = val
    elif key == "MANUFACTURER":
        doc.metadata.manufacturer = val
    return True


def _parse_scenario_line(doc: CqlDocument, stripped: str) -> CqlScenario | None:
    """Parse @Namespace.Name scenario header. Appends to doc.scenarios and returns it, or None."""
    m = RE_SCENARIO.match(stripped)
    if not m:
        return None
    parts = m.group(1).rsplit(".", 1)
    ns = parts[0] if len(parts) > 1 else ""
    name = parts[-1]
    sc = CqlScenario(namespace=ns, name=name)
    doc.scenarios.append(sc)
    return sc


def _parse_scenario_attrs(line: str, current_scenario: CqlScenario) -> bool:
    """Parse scenario-level attributes (description, intervals ref).

    Returns True if the line was consumed.
    """
    m = RE_DESC.match(line)
    if m:
        current_scenario.description = m.group(1)
        return True
    m = RE_INTERVALS_REF.match(line)
    if m:
        current_scenario.intervals = [x.strip() for x in m.group(1).split(",")]
        return True
    return False


def _parse_goal_line(
    stripped: str, line: str, indent: int, current_scenario: CqlScenario | None
) -> CqlGoal | None:
    """Parse GOAL: (simple CQL) or named goal (ConnectGo 2-space indent).

    Returns a new CqlGoal, or None if this line is not a goal header.
    """
    # Simple CQL: GOAL: name
    m = RE_GOAL_SIMPLE.match(stripped)
    if m:
        return CqlGoal(name=m.group(1).strip())

    # ConnectGo: 2-space indented "Name:"
    if indent == 2 and current_scenario:
        m = RE_GOAL_NAMED.match(line)
        if m:
            return CqlGoal(name=m.group(1).strip())

    return None


def _parse_goal_attrs(line: str, current_goal: CqlGoal) -> bool:
    """Parse goal-level attributes (description, editable, alarm).

    Returns True if the line was consumed.
    """
    m = RE_DESC.match(line)
    if m:
        current_goal.description = m.group(1)
        return True
    m = RE_EDITABLE.match(line)
    if m:
        current_goal.editable = m.group(1).lower() == "true"
        return True
    m = RE_ALARM.match(line)
    if m:
        current_goal.alarm = m.group(1)
        return True
    return False


def _parse_step_line(line: str, current_goal: CqlGoal | None) -> CqlStep | None:
    """Parse a numbered step line. Returns a new CqlStep or None."""
    if not current_goal:
        return None
    m = RE_STEP_NUM.match(line)
    if m:
        return CqlStep(number=m.group(1), name=m.group(2).strip())
    return None


def _parse_action_line(
    line: str, stripped: str, actions_list: list, doc: CqlDocument, lineno: int
) -> bool:
    """Try to match any action type and append to *actions_list*.

    Returns True if the line was consumed (even if only as a step description).
    """
    # → Arrow action (ConnectGo)
    m = RE_ACTION_ARROW.match(line)
    if m:
        actions_list.append(CqlAction(
            kind="action", target=m.group(1), method=m.group(2),
            args=m.group(3).strip().strip('"'), raw=stripped,
        ))
        return True

    # TASK: [verb] [obj]
    m = RE_TASK_BRACKET.match(line)
    if m:
        actions_list.append(CqlAction(kind="task", args=m.group(1).strip(), raw=stripped))
        return True

    # SAVE: var  or  SAVE [var]  or  SAVE "var"
    m = RE_SAVE_COLON.match(line) or RE_SAVE_BRACKET.match(line) or RE_SAVE_QUOTED.match(line)
    if m:
        actions_list.append(CqlAction(kind="save", target=m.group(1).strip(), raw=stripped))
        return True

    # WAIT [N s]
    m = RE_WAIT.match(line)
    if m:
        actions_list.append(CqlAction(kind="wait", args=m.group(1), raw=stripped))
        return True

    # PUMP command removed - now handled as SET 'pompa'
    # Generic SET [parameter] = [value]  or  SET "parameter" "value"  or  SET 'parameter' 'value'
    m = RE_SET.match(line) or RE_SET_QUOTED.match(line) or RE_SET_SINGLE.match(line)
    if m:
        actions_list.append(CqlAction(kind="set", target=m.group(1).strip(), args=m.group(2).strip(), raw=stripped))
        return True

    # Condition: range  AI01 ∈ [min, max] unit | ACTION
    m = RE_CONDITION_RANGE.match(line)
    if m:
        cond = CqlCondition(
            sensor=m.group(1), operator="∈",
            value_min=float(m.group(3)), value_max=float(m.group(4)),
            unit=m.group(5) or "", on_fail=m.group(6) or "",
            fail_message=m.group(7) or "",
        )
        actions_list.append(CqlAction(kind="condition", condition=cond, raw=stripped))
        return True

    # Condition: comparison  AI01 ≤ val unit | ACTION
    m = RE_CONDITION_CMP.match(line)
    if m:
        cond = CqlCondition(
            sensor=m.group(1), operator=m.group(2),
            value=float(m.group(3)), unit=m.group(4) or "",
            on_fail=m.group(5) or "", fail_message=m.group(6) or "",
        )
        actions_list.append(CqlAction(kind="condition", condition=cond, raw=stripped))
        return True

    # IF [sensor] [op] [val] ELSE ERROR "msg"  or  IF "sensor" op "val" ELSE ERROR "msg"
    m = RE_IF_ELSE.match(line) or RE_IF_ELSE_QUOTED.match(line)
    if m:
        cond = CqlCondition(
            sensor=m.group(1), operator=m.group(2),
            value=float(m.group(3)), unit=m.group(4) or "",
            on_fail="ERROR", fail_message=m.group(5),
        )
        actions_list.append(CqlAction(kind="if_else", condition=cond, raw=stripped))
        return True

    # MIN/MAX [sensor] = [value unit]  or  MIN/MAX "sensor" "value unit"
    m = RE_MIN_MAX.match(line) or RE_MIN_MAX_QUOTED.match(line)
    if m:
        actions_list.append(CqlAction(
            kind=m.group(1).lower(), target=m.group(2),
            args=f"{m.group(3)} {m.group(4) or ''}".strip(), raw=stripped,
        ))
        return True

    # VAL [sensor] [unit]  or  VAL "sensor" "unit"
    m = RE_VAL.match(line) or RE_VAL_QUOTED.match(line)
    if m:
        actions_list.append(CqlAction(kind="val", target=m.group(1), args=m.group(2), raw=stripped))
        return True

    # Step-level description (consumed silently)
    if RE_DESC.match(line):
        return True

    return False


# ═══════════════════════════════════════════════════════════════════════════════
# Parser
# ═══════════════════════════════════════════════════════════════════════════════

def parse_cql(source: str, filename: str = "<string>") -> CqlDocument:
    """Parse CQL source into AST."""
    doc = CqlDocument(filename=filename)
    lines = source.split("\n")
    n = len(lines)
    i = 0

    current_scenario: CqlScenario | None = None
    current_goal: CqlGoal | None = None
    current_step: CqlStep | None = None
    in_intervals_block = False
    in_skip_block = False  # OUTPUTS, SENSORS, META, etc.

    while i < n:
        raw = lines[i]
        line = raw.rstrip()
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        i += 1

        # Skip empty / comment lines
        if not stripped or stripped.startswith("#"):
            continue

        # ── Skip-block (OUTPUTS, SENSORS, META, VALIDATION_MODES) ──
        m = RE_BLOCK_HEADER.match(stripped)
        if m:
            in_skip_block = True
            in_intervals_block = False
            continue
        if in_skip_block:
            # Indented lines belong to the skip block; top-level line ends it
            if indent > 0 or stripped.startswith("-"):
                continue
            in_skip_block = False
            # Fall through to process this top-level line

        # ── Top-level metadata ──
        if _parse_metadata_kv(doc, stripped):
            in_intervals_block = False
            continue

        # ── INTERVALS: block ──
        if stripped == "INTERVALS:":
            in_intervals_block = True
            continue

        if in_intervals_block:
            m = RE_INTERVAL.match(line)
            if m:
                doc.intervals.append(CqlInterval(
                    code=m.group(1), label=m.group(2), period_months=int(m.group(3))
                ))
                continue
            elif indent == 0:
                in_intervals_block = False
                # Fall through to process this line

        # ── @Scenario block ──
        sc = _parse_scenario_line(doc, stripped)
        if sc is not None:
            current_scenario = sc
            current_goal = None
            current_step = None
            continue

        # ── Scenario-level attributes (before first goal) ──
        if current_scenario and not current_goal:
            if _parse_scenario_attrs(line, current_scenario):
                continue

        # ── GOAL / named goal ──
        goal = _parse_goal_line(stripped, line, indent, current_scenario)
        if goal is not None:
            if current_scenario:
                current_scenario.goals.append(goal)
            else:
                doc.goals.append(goal)
            current_goal = goal
            current_step = None
            continue

        # ── Goal-level attributes (before first step) ──
        if current_goal and not current_step:
            if _parse_goal_attrs(line, current_goal):
                continue

        # ── Numbered step ──
        # Auto-create implicit goal from scenario name when steps appear
        # directly under @Scenario without a named goal (e.g. @Namespace.GoalName format)
        if not current_goal and current_scenario and RE_STEP_NUM.match(line):
            auto_goal = CqlGoal(name=current_scenario.name, description=current_scenario.description)
            current_scenario.goals.append(auto_goal)
            current_goal = auto_goal

        step = _parse_step_line(line, current_goal)
        if step is not None:
            current_goal.steps.append(step)  # type: ignore[union-attr]
            current_step = step
            continue

        # ── Actions ──
        if not current_goal:
            continue

        # Auto-create implicit step when actions appear directly under GOAL
        if not current_step and current_goal:
            current_step = CqlStep(number="0", name=current_goal.name)
            current_goal.steps.append(current_step)

        if _parse_action_line(line, stripped, current_step.actions, doc, i):
            continue

        # Unrecognized line — store as warning
        if stripped and not stripped.startswith("#"):
            doc.warnings.append(f"L{i}: unrecognized: {stripped[:80]}")

    return doc


# ═══════════════════════════════════════════════════════════════════════════════
# Validator
# ═══════════════════════════════════════════════════════════════════════════════

def validate_cql(doc: CqlDocument) -> list[str]:
    """Validate a parsed CQL document. Returns list of issues."""
    issues: list[str] = []

    # Must have scenario name or at least one goal
    all_goals = list(doc.goals)
    for sc in doc.scenarios:
        all_goals.extend(sc.goals)

    if not all_goals and not doc.metadata.scenario_name:
        issues.append("No SCENARIO name or GOAL blocks found")

    # Check goals have steps
    for g in all_goals:
        if not g.steps:
            issues.append(f"Goal '{g.name}' has no numbered steps")

    # Check sensor references are consistent
    sensors_seen: set[str] = set()
    for g in all_goals:
        for step in g.steps:
            for act in step.actions:
                if act.condition and act.condition.sensor:
                    sensors_seen.add(act.condition.sensor)
                if act.kind in ("min", "max", "val"):
                    sensors_seen.add(act.target)

    # Check interval references in scenarios
    known_intervals = {iv.code for iv in doc.intervals}
    for sc in doc.scenarios:
        for ref in sc.intervals:
            if known_intervals and ref not in known_intervals:
                issues.append(f"Scenario '{sc.name}': unknown interval '{ref}'")

    return issues
