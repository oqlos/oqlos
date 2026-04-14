"""CQL tree builder — structure parsers for metadata, scenarios, goals, steps, actions."""

from __future__ import annotations

from oqlos.models.dsl_models import (
    CqlDocument,
    CqlGoal,
    CqlScenario,
    CqlStep,
)
from ._cql_tokenizer import (
    RE_DESC,
    RE_EDITABLE,
    RE_ALARM,
    RE_INTERVALS_REF,
    RE_METADATA_KV,
    RE_SCENARIO,
    RE_GOAL_SIMPLE,
    RE_GOAL_NAMED,
    RE_STEP_NUM,
    _ACTION_PARSERS,
)


def _parse_metadata_kv(doc: CqlDocument, stripped: str) -> bool:
    """Parse top-level SCENARIO/DEVICE_TYPE/DEVICE_MODEL/MANUFACTURER lines."""
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
    """Parse @Namespace.Name scenario header."""
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
    """Parse scenario-level attributes (description, intervals ref)."""
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
    """Parse GOAL: (simple CQL) or named goal (ConnectGo 2-space indent)."""
    m = RE_GOAL_SIMPLE.match(stripped)
    if m:
        return CqlGoal(name=m.group(1).strip())

    if indent == 2 and current_scenario:
        m = RE_GOAL_NAMED.match(line)
        if m:
            return CqlGoal(name=m.group(1).strip())

    return None


def _parse_goal_attrs(line: str, current_goal: CqlGoal) -> bool:
    """Parse goal-level attributes (description, editable, alarm)."""
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
    """Parse a numbered step line."""
    if not current_goal:
        return None
    m = RE_STEP_NUM.match(line)
    if m:
        return CqlStep(number=m.group(1), name=m.group(2).strip())
    return None


def _parse_action_line(
    line: str, stripped: str, actions_list: list, doc: CqlDocument, lineno: int
) -> bool:
    """Try to match any action type and append to *actions_list*."""
    for parser in _ACTION_PARSERS:
        action = parser(line, stripped)
        if action is not None:
            actions_list.append(action)
            return True

    if RE_DESC.match(line):
        return True

    return False


def _ensure_goal_for_step(
    current_goal: CqlGoal | None,
    current_scenario: CqlScenario | None,
    line: str,
) -> tuple[CqlGoal | None, CqlScenario | None]:
    """Auto-create implicit goal if needed when a step is encountered."""
    if not current_goal and current_scenario and RE_STEP_NUM.match(line):
        auto_goal = CqlGoal(name=current_scenario.name, description=current_scenario.description)
        current_scenario.goals.append(auto_goal)
        return auto_goal, current_scenario
    return current_goal, current_scenario


def _ensure_step_for_actions(
    current_step: CqlStep | None,
    current_goal: CqlGoal | None,
) -> CqlStep | None:
    """Auto-create implicit step if actions appear directly under GOAL."""
    if not current_step and current_goal:
        step = CqlStep(number="0", name=current_goal.name)
        current_goal.steps.append(step)
        return step
    return current_step
