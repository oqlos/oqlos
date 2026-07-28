"""Regression tests for runtime CQL/DSL parsing used by the firmware API."""

from __future__ import annotations

from oqlos.core.parser import parse_dsl_to_goal, parse_dsl_to_goal_with_issues


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
  SET WAIT '1.5 s'
"""

        goal = parse_dsl_to_goal(dsl, 'parser-wait')

        assert goal is not None
        assert len(goal.steps) == 1
        assert goal.steps[0].action == 'WAIT'
        assert goal.steps[0].duration == 1500

    def test_parses_bare_set_wait_step(self):
        dsl = """SCENARIO: Wait handling
GOAL: Demo
  SET WAIT '1 s'
  SET DELAY '500 ms'
"""

        goal = parse_dsl_to_goal(dsl, 'parser-bare-set-wait')

        assert goal is not None
        assert [step.action for step in goal.steps] == ['WAIT', 'WAIT']
        assert [step.duration for step in goal.steps] == [1000, 500]

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
  SET WAIT '1 s'
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
  SET WAIT '1 s'
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


class TestFlatOqlRuntime:
    """Flat OQL parsed through the canonical parser (parse_cql)."""

    def test_flat_v6_test_step_with_range_pass_fail(self):
        dsl = """VERSION: 6
SCENARIO: Smoke

TEST_STEP:
  NAME 'Test ciśnienia'
  SET 'zawór 2' '1'
  TIMER 500ms
  VAL 'ciśnienie NC' 'bar'
  RANGE 'ciśnienie NC' '0.5 bar' .. '2.0 bar'
  PASS 'Ciśnienie OK'
  FAIL 'Ciśnienie poza zakresem'
"""

        goal, issues = parse_dsl_to_goal_with_issues(dsl, 'flat-v6')

        assert goal is not None
        assert goal.name == 'Test ciśnienia'
        assert goal.id == 'goal-runtime-flat-v6'
        assert issues == []
        assert [step.action for step in goal.steps] == [
            'SET_VALVE', 'WAIT', 'VALIDATE', 'VALIDATE',
        ]
        assert goal.steps[0].peripheral == 'valve-2'
        assert goal.steps[0].value is True
        assert goal.steps[1].duration == 500
        assert goal.steps[2].condition == 'nc-sensor.currentValue >= 0.5'
        assert goal.steps[3].condition == 'nc-sensor.currentValue <= 2.0'
        assert goal.expectedResult == 'Ciśnienie OK'
        assert [rule.errorMessage for rule in goal.validationCriteria] == [
            'Ciśnienie poza zakresem',
        ]

    def test_flat_v3_named_goal_block(self):
        dsl = """VERSION: 3
GOAL test-zaworu:
  SET 'zawór 14' '1'
  MIN 'ciśnienie NC' '0.3 bar'
"""

        goal = parse_dsl_to_goal(dsl, 'flat-v3')

        assert goal is not None
        assert goal.name == 'test-zaworu'
        assert [step.action for step in goal.steps] == ['SET_VALVE', 'VALIDATE']
        assert goal.steps[1].condition == 'nc-sensor.currentValue >= 0.3'

    def test_flat_multiple_goals_returns_first_with_issue(self):
        dsl = """VERSION: 6
TASK:
  NAME 'Pierwszy'
  SET 'zawór 2' '1'

TASK:
  NAME 'Drugi'
  SET 'zawór 2' '0'
"""

        goal, issues = parse_dsl_to_goal_with_issues(dsl, 'flat-multi')

        assert goal is not None
        assert goal.name == 'Pierwszy'
        assert len(goal.steps) == 1
        assert len(issues) == 1
        assert '2 runnable blocks' in issues[0]

    def test_legacy_dialect_not_hijacked_by_flat_detector(self):
        dsl = """SCENARIO: Legacy guard
GOAL: Demo
  TASK: [Otwórz] [zawór 13]
  SET WAIT '1 s'
"""

        goal = parse_dsl_to_goal(dsl, 'legacy-guard')

        assert goal is not None
        assert goal.name == 'Demo'
        assert [step.action for step in goal.steps] == ['SET_VALVE', 'WAIT']
