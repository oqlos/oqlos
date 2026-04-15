"""
CQL Parser — parses .cql source into AST nodes + validates structure.

Supports two CQL dialects:
  1. Simple CQL:   GOAL:, TASK:, SAVE, WAIT, IF...ELSE, MIN, MAX, VAL
  2. ConnectGo:    @Namespace.Name, → Action, AI02 ∈ [min, max], SAVE: var
"""

from __future__ import annotations

from oqlos.models.dsl_models import (
    CqlDocument,
    CqlGoal,
    CqlInterval,
    CqlScenario,
    CqlStep,
)
from ._cql_tokenizer import RE_BLOCK_HEADER, RE_INTERVAL, RE_STEP_NUM
from ._cql_tree_builder import (
    _ensure_goal_for_step,
    _ensure_step_for_actions,
    _parse_action_line,
    _parse_goal_attrs,
    _parse_goal_line,
    _parse_metadata_kv,
    _parse_scenario_attrs,
    _parse_scenario_line,
    _parse_step_line,
)


class _ParseState:
    """Encapsulates the parsing state to simplify the main loop."""

    def __init__(self, doc: CqlDocument, lines: list[str]):
        self.doc = doc
        self.lines = lines
        self.n = len(lines)
        self.i = 0
        self.current_scenario: CqlScenario | None = None
        self.current_goal: CqlGoal | None = None
        self.current_step: CqlStep | None = None
        self.in_intervals_block = False
        self.in_skip_block = False

    def parse(self) -> CqlDocument:
        """Parse all lines and return the document."""
        while self.i < self.n:
            self._process_line()
        return self.doc

    def _get_line_info(self) -> tuple[str, str, str, int]:
        """Get raw, line, stripped, and indent for current line."""
        raw = self.lines[self.i]
        line = raw.rstrip()
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        self.i += 1
        return raw, line, stripped, indent

    def _process_line(self) -> None:
        """Process a single line based on current state."""
        _, line, stripped, indent = self._get_line_info()

        if not stripped or stripped.startswith("#"):
            return

        if self._try_skip_block(stripped, indent):
            return

        if self._try_intervals_block(stripped, line, indent):
            return

        if self._try_top_level(stripped, line, indent):
            return

        if self._try_hierarchy(stripped, line, indent):
            return

        if stripped:
            self.doc.warnings.append(f"L{self.i}: unrecognized: {stripped[:80]}")

    def _try_skip_block(self, stripped: str, indent: int) -> bool:
        """Handle OUTPUTS, SENSORS, META, VALIDATION_MODES blocks."""
        m = RE_BLOCK_HEADER.match(stripped)
        if m:
            self.in_skip_block = True
            self.in_intervals_block = False
            return True
        if self.in_skip_block:
            if indent > 0 or stripped.startswith("-"):
                return True
            self.in_skip_block = False
        return False

    def _try_intervals_block(self, stripped: str, line: str, indent: int) -> bool:
        """Handle INTERVALS: block."""
        if stripped == "INTERVALS:":
            self.in_intervals_block = True
            return True

        if self.in_intervals_block:
            m = RE_INTERVAL.match(line)
            if m:
                self.doc.intervals.append(CqlInterval(
                    code=m.group(1), label=m.group(2), period_months=int(m.group(3))
                ))
                return True
            elif indent == 0:
                self.in_intervals_block = False
        return False

    def _try_top_level(self, stripped: str, line: str, indent: int) -> bool:
        """Handle top-level metadata."""
        if _parse_metadata_kv(self.doc, stripped):
            self.in_intervals_block = False
            return True
        return False

    def _try_hierarchy(self, stripped: str, line: str, indent: int) -> bool:
        """Handle scenario/goal/step/action hierarchy."""
        sc = _parse_scenario_line(self.doc, stripped)
        if sc is not None:
            # Clear block stack on new scenario
            if hasattr(self, 'block_stack'):
                self.block_stack.clear()
            self.current_scenario = sc
            self.current_goal = None
            self.current_step = None
            return True

        if self.current_scenario and not self.current_goal:
            if _parse_scenario_attrs(line, self.current_scenario):
                return True

        goal = _parse_goal_line(stripped, line, indent, self.current_scenario)
        if goal is not None:
            # Clear block stack on new goal (implicit ENDIF/ENDLOOP at end of goal)
            if hasattr(self, 'block_stack'):
                self.block_stack.clear()
                
            if self.current_scenario:
                self.current_scenario.goals.append(goal)
            else:
                self.doc.goals.append(goal)
            self.current_goal = goal
            self.current_step = None
            return True
            return True

        if self.current_goal and not self.current_step:
            if _parse_goal_attrs(line, self.current_goal):
                return True

        self.current_goal, self.current_scenario = _ensure_goal_for_step(
            self.current_goal, self.current_scenario, line
        )

        step = _parse_step_line(line, self.current_goal)
        if step is not None:
            self.current_goal.steps.append(step)  # type: ignore[union-attr]
            self.current_step = step
            return True

        if not self.current_goal:
            return True

        self.current_step = _ensure_step_for_actions(self.current_step, self.current_goal)
        if self.current_step is None:
            return False

        # Nested block management
        from oqlos.models.dsl_models import CqlAction
        if not hasattr(self, 'block_stack'):
            self.block_stack: list[tuple[CqlAction, bool]] = []  # (action, in_else_branch)

        # Try to parse as an action
        temp_actions: list[CqlAction] = []
        if _parse_action_line(line, stripped, temp_actions, self.doc, self.i):
            if not temp_actions:
                return True
            
            act = temp_actions[0]
            
            # Handle block control keywords
            if act.kind == "if_block":
                self.block_stack.append((act, False))
                # Add the if_block itself to the parent (step or outer block)
                if len(self.block_stack) > 1:
                    parent_act, in_else = self.block_stack[-2]
                    target_list = parent_act.else_actions if in_else else parent_act.then_actions
                    # If the parent is a loop, things are simpler
                    if parent_act.kind == "loop_block":
                        parent_act.loop_actions.append(act)
                    else:
                        target_list.append(act)
                else:
                    self.current_step.actions.append(act)
                return True
                
            if act.kind == "loop_block":
                self.block_stack.append((act, False)) # loop doesn't havebranches like ELSE
                if len(self.block_stack) > 1:
                    parent_act, in_else = self.block_stack[-2]
                    if parent_act.kind == "loop_block":
                        parent_act.loop_actions.append(act)
                    else:
                        target_list = parent_act.else_actions if in_else else parent_act.then_actions
                        target_list.append(act)
                else:
                    self.current_step.actions.append(act)
                return True

            if act.kind == "else_block":
                if not self.block_stack:
                    self.doc.warnings.append(f"L{self.i}: ELSE ohne IF")
                    return True
                parent_act, _ = self.block_stack.pop()
                if parent_act.kind != "if_block":
                    self.doc.warnings.append(f"L{self.i}: ELSE inside LOOP")
                self.block_stack.append((parent_act, True))
                return True
                
            if act.kind == "endif":
                if not self.block_stack or self.block_stack[-1][0].kind != "if_block":
                    self.doc.warnings.append(f"L{self.i}: ENDIF ohne IF")
                    if not self.block_stack: return True
                self.block_stack.pop()
                return True

            if act.kind == "endloop":
                if not self.block_stack or self.block_stack[-1][0].kind != "loop_block":
                    self.doc.warnings.append(f"L{self.i}: ENDLOOP ohne LOOP")
                    if not self.block_stack: return True
                self.block_stack.pop()
                return True

            # Standard actions & var_set
            if self.block_stack:
                parent_act, in_else = self.block_stack[-1]
                if parent_act.kind == "loop_block":
                    parent_act.loop_actions.append(act)
                else:
                    target_list = parent_act.else_actions if in_else else parent_act.then_actions
                    target_list.append(act)
            else:
                self.current_step.actions.append(act)
            return True

        return False


def parse_cql(source: str, filename: str = "<string>") -> CqlDocument:
    """Parse CQL source into AST."""
    doc = CqlDocument(filename=filename)
    lines = source.split("\n")
    state = _ParseState(doc, lines)
    return state.parse()


def _collect_all_goals(doc: CqlDocument) -> list:
    """Collect goals from both document-level and scenario-level."""
    all_goals = list(doc.goals)
    for sc in doc.scenarios:
        all_goals.extend(sc.goals)
    return all_goals


def _validate_intervals(doc: CqlDocument) -> list[str]:
    """Validate scenario interval references against defined intervals."""
    issues: list[str] = []
    known_intervals = {iv.code for iv in doc.intervals}
    for sc in doc.scenarios:
        for ref in sc.intervals:
            if known_intervals and ref not in known_intervals:
                issues.append(f"Scenario '{sc.name}': unknown interval '{ref}'")
    return issues


def validate_cql(doc: CqlDocument) -> list[str]:
    """Validate a parsed CQL document. Returns list of issues."""
    issues: list[str] = []

    all_goals = _collect_all_goals(doc)

    if not all_goals and not doc.metadata.scenario_name:
        issues.append("No SCENARIO name or GOAL blocks found")

    for g in all_goals:
        if not g.steps:
            issues.append(f"Goal '{g.name}' has no numbered steps")

    issues.extend(_validate_intervals(doc))

    return issues
