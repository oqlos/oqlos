"""Regression tests for runtime CQL/DSL parsing used by the firmware API."""

from __future__ import annotations

import os
import sys

_firmware_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.abspath(_firmware_root))

from utils.dsl_parser import parse_dsl_to_goal, parse_dsl_to_goal_with_issues


class TestDslParserRuntime:
    def test_parses_bracketed_task_lines_for_valve_14(self):
        dsl = """SCENARIO: Valve routing
GOAL: Demo
  TASK: [Otwórz] [zawór 13] AND [Zamknij] [zawór 14]
"""

        goal = parse_dsl_to_goal(dsl, 'parser-valve-14')

        assert goal is not None
        assert len(goal.steps) == 2
        assert goal.steps[0].action == 'SET_VALVE'
        assert goal.steps[0].peripheral == 'valve-13'
        assert goal.steps[0].value is True
        assert goal.steps[1].action == 'SET_VALVE'
        assert goal.steps[1].peripheral == 'valve-14'
        assert goal.steps[1].value is False

    def test_parses_wait_step_from_builder_serialization(self):
        dsl = """SCENARIO: Wait handling
GOAL: Demo
  SET 'wait' '1.5 s'
"""

        goal = parse_dsl_to_goal(dsl, 'parser-wait')

        assert goal is not None
        assert len(goal.steps) == 1
        assert goal.steps[0].action == 'WAIT'
        assert goal.steps[0].duration == 1500

    def test_parses_dedicated_pump_command(self):
        dsl = """SCENARIO: Pump handling
GOAL: Demo
  SET 'POMPA' '5 bar'
"""

        goal = parse_dsl_to_goal(dsl, 'parser-pump')

        assert goal is not None
        assert len(goal.steps) == 1
        assert goal.steps[0].action == 'SET_PUMP'
        assert goal.steps[0].peripheral == 'pump-main'
        assert goal.steps[0].value == 5

    def test_parses_set_lines_for_valve_and_compressor(self):
        dsl = """SCENARIO: SET handling
GOAL: Demo
  SET 'zawór 2' '1'
  SET 'sprężarka' '120 l/min'
  SET 'zawór 2' '0'
"""

        goal = parse_dsl_to_goal(dsl, 'parser-set')

        assert goal is not None
        assert [step.action for step in goal.steps] == ['SET_VALVE', 'SET_PUMP', 'SET_VALVE']
        assert goal.steps[0].peripheral == 'valve-2'
        assert goal.steps[0].value is True
        assert goal.steps[1].peripheral == 'pump-main'
        assert goal.steps[1].value == 120
        assert goal.steps[2].value is False

    def test_parses_if_condition_with_operator_between_brackets(self):
        dsl = """SCENARIO: Validation
GOAL: Demo
  IF 'ciśnienie NC' > '0.5'
"""

        goal = parse_dsl_to_goal(dsl, 'parser-if')

        assert goal is not None
        assert len(goal.steps) == 1
        assert goal.steps[0].action == 'VALIDATE'
        assert goal.steps[0].condition == 'nc-sensor.currentValue > 0.5'

    def test_expands_func_call_into_runtime_steps(self):
        dsl = """SCENARIO: Function expansion
FUNC: helper
  TASK: [Otwórz] [zawór 14]
  SET 'wait' '1 s'
GOAL: Demo
  FUNC 'helper'
  TASK: [Zamknij] [zawór 13]
"""

        goal = parse_dsl_to_goal(dsl, 'parser-func')

        assert goal is not None
        assert [step.action for step in goal.steps] == ['SET_VALVE', 'WAIT', 'SET_VALVE']
        assert goal.steps[0].peripheral == 'valve-14'
        assert goal.steps[0].value is True
        assert goal.steps[1].duration == 1000
        assert goal.steps[2].peripheral == 'valve-13'
        assert goal.steps[2].value is False

    def test_reports_invalid_runtime_line_for_pompx_typo(self):
        dsl = """SCENARIO: Typo rejection
GOAL: Demo
  SET 'zawor 1' 'ON'
  SET 'POMPX' '1l'
  SET 'WAIT' '1s'
"""

        goal, invalid_lines = parse_dsl_to_goal_with_issues(dsl, 'parser-invalid-pompx')

        assert goal is not None
        assert [step.action for step in goal.steps] == ['SET_VALVE', 'WAIT']
        assert invalid_lines == ["SET 'POMPX' '1l'"]

    def test_accepts_pompa_with_suffix_as_real_pump_reference(self):
        dsl = """SCENARIO: Pump alias
GOAL: Demo
  TASK: [Włącz] [pompa 1]
"""

        goal = parse_dsl_to_goal(dsl, 'parser-pompa-1')

        assert goal is not None
        assert len(goal.steps) == 1
        assert goal.steps[0].action == 'SET_PUMP'
        assert goal.steps[0].peripheral == 'pump-main'

    def test_accepts_set_pompa_alias(self):
        dsl = """SCENARIO: Pump alias set
GOAL: Demo
  SET 'POMPA' '5l'
"""

        goal = parse_dsl_to_goal(dsl, 'parser-pompa-set')

        assert goal is not None
        assert len(goal.steps) == 1
        assert goal.steps[0].action == 'SET_PUMP'
        assert goal.steps[0].peripheral == 'pump-main'
        assert goal.steps[0].value == 5
