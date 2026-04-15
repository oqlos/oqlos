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

    # ── Hierarchy Handlers (refactored from monolithic _try_hierarchy) ──

    def _handle_scenario(self, stripped: str) -> bool:
        """Handle scenario line parsing."""
        sc = _parse_scenario_line(self.doc, stripped)
        if sc is None:
            return False
        # Clear block stack on new scenario
        if hasattr(self, 'block_stack'):
            self.block_stack.clear()
        self.current_scenario = sc
        self.current_goal = None
        self.current_step = None
        return True

    def _handle_scenario_attrs(self, line: str) -> bool:
        """Handle scenario attribute lines."""
        if not (self.current_scenario and not self.current_goal):
            return False
        return _parse_scenario_attrs(line, self.current_scenario)

    def _handle_goal(self, stripped: str, line: str, indent: int) -> bool:
        """Handle goal line parsing."""
        goal = _parse_goal_line(stripped, line, indent, self.current_scenario)
        if goal is None:
            return False
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

    def _handle_goal_attrs(self, line: str) -> bool:
        """Handle goal attribute lines."""
        if not (self.current_goal and not self.current_step):
            return False
        return _parse_goal_attrs(line, self.current_goal)

    def _handle_step(self, line: str) -> bool:
        """Handle step line parsing."""
        self.current_goal, self.current_scenario = _ensure_goal_for_step(
            self.current_goal, self.current_scenario, line
        )
        step = _parse_step_line(line, self.current_goal)
        if step is None:
            return False
        self.current_goal.steps.append(step)  # type: ignore[union-attr]
        self.current_step = step
        return True

    def _init_block_stack(self) -> None:
        """Initialize block stack if not present."""
        from oqlos.models.dsl_models import CqlAction
        if not hasattr(self, 'block_stack'):
            self.block_stack: list[tuple[CqlAction, bool]] = []

    def _add_action_to_parent(self, act) -> None:
        """Add action to appropriate parent (step or block)."""
        if self.block_stack:
            parent_act, in_else = self.block_stack[-1]
            if parent_act.kind == "loop_block":
                parent_act.loop_actions.append(act)
            else:
                target_list = parent_act.else_actions if in_else else parent_act.then_actions
                target_list.append(act)
        else:
            self.current_step.actions.append(act)

    def _append_nested_action(self, act) -> None:
        """Append action to appropriate parent in block stack."""
        if len(self.block_stack) <= 1:
            self.current_step.actions.append(act)
            return

        parent_act, in_else = self.block_stack[-2]
        if parent_act.kind == "loop_block":
            parent_act.loop_actions.append(act)
        else:
            target_list = parent_act.else_actions if in_else else parent_act.then_actions
            target_list.append(act)

    def _append_loop_action(self, act) -> None:
        """Append loop action handling special loop-in-loop case."""
        if len(self.block_stack) <= 1:
            self.current_step.actions.append(act)
            return

        parent_act, in_else = self.block_stack[-2]
        if parent_act.kind == "loop_block":
            parent_act.loop_actions.append(act)
        else:
            target_list = parent_act.else_actions if in_else else parent_act.then_actions
            target_list.append(act)

    def _pop_block_with_warning(self, expected_kind: str, warning_msg: str) -> bool:
        """Pop block from stack with validation and warning."""
        if not self.block_stack or self.block_stack[-1][0].kind != expected_kind:
            self.doc.warnings.append(f"L{self.i}: {warning_msg}")
            if not self.block_stack:
                return True  # Handled, but with warning
        self.block_stack.pop()
        return True

    def _handle_block_control(self, act) -> bool:
        """Handle block control keywords (if_block, loop_block, else_block, endif, endloop).

        Refactored from CC=20 to orchestrator calling focused helpers.
        """
        # Block starters
        if act.kind == "if_block":
            self.block_stack.append((act, False))
            self._append_nested_action(act)
            return True

        if act.kind == "loop_block":
            self.block_stack.append((act, False))
            self._append_loop_action(act)
            return True

        # Branch control
        if act.kind == "else_block":
            return self._handle_else_block()

        # Block enders
        if act.kind == "endif":
            return self._pop_block_with_warning("if_block", "ENDIF ohne IF")

        if act.kind == "endloop":
            return self._pop_block_with_warning("loop_block", "ENDLOOP ohne LOOP")

        return False

    def _handle_else_block(self) -> bool:
        """Handle ELSE block control."""
        if not self.block_stack:
            self.doc.warnings.append(f"L{self.i}: ELSE ohne IF")
            return True
        parent_act, _ = self.block_stack.pop()
        if parent_act.kind != "if_block":
            self.doc.warnings.append(f"L{self.i}: ELSE inside LOOP")
        self.block_stack.append((parent_act, True))
        return True

    def _try_hierarchy(self, stripped: str, line: str, indent: int) -> bool:
        """Handle scenario/goal/step/action hierarchy.

        Refactored from monolithic CC=40 function into orchestrator
        calling focused handlers (each CC<10).
        """
        # Scenario level
        if self._handle_scenario(stripped):
            return True
        if self._handle_scenario_attrs(line):
            return True

        # Goal level
        if self._handle_goal(stripped, line, indent):
            return True
        if self._handle_goal_attrs(line):
            return True

        # Step level
        if self._handle_step(line):
            return True

        if not self.current_goal:
            return True

        self.current_step = _ensure_step_for_actions(self.current_step, self.current_goal)
        if self.current_step is None:
            return False

        # Action level
        self._init_block_stack()

        temp_actions = []
        if not _parse_action_line(line, stripped, temp_actions, self.doc, self.i):
            return False
        if not temp_actions:
            return True

        act = temp_actions[0]

        # Try block control first
        if self._handle_block_control(act):
            return True

        # Standard action
        self._add_action_to_parent(act)
        return True


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
