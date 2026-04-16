"""Regression tests for flat CQL control flow and helper actions."""

from __future__ import annotations

from oqlos.core.base import StepStatus
from oqlos.core.interpreter import CqlInterpreter


def test_flat_if_with_variable_threshold_and_goto_skips_rest_of_goal() -> None:
    src = """SCENARIO: Inline goto
GOAL: Low range
  SET 'próg_przełączenia' '45 mbar'
  IF 'cn' > 'próg_przełączenia'
  GOTO 'High range'
  SET 'po tym goto' '1'
GOAL: High range
  SET 'done' '1'
"""

    interp = CqlInterpreter(mode="dry-run", quiet=True)
    result = interp.run(src)

    assert result.ok is True
    assert interp.vars.get("last_goto") == "High range"
    assert interp.vars.get("po tym goto") is None
    assert interp.vars.get("done") == "1"


def test_flat_if_else_error_pair_does_not_execute_else_when_condition_passes() -> None:
    src = """SCENARIO: Inline else
GOAL: Demo
  IF 'temperatura' < '15'
  ELSE ERROR 'Temperatura poza zakresem'
  SET 'done' '1'
"""

    interp = CqlInterpreter(mode="dry-run", quiet=True)
    result = interp.run(src)

    assert result.ok is True
    assert result.failed == 0
    assert interp.vars.get("done") == "1"


def test_compound_if_or_expression_is_supported_in_dry_run() -> None:
    src = """SCENARIO: Compound IF
GOAL: Demo
  IF 'cn' < '25' OR 'cn' > '35'
  ELSE ERROR 'Ciśnienie poza zakresem'
  SET 'done' '1'
"""

    interp = CqlInterpreter(mode="dry-run", quiet=True)
    result = interp.run(src)

    assert result.ok is True
    assert interp.vars.get("done") == "1"


def test_func_actions_compute_values_for_following_conditions() -> None:
    src = """SCENARIO: FUNC support
GOAL: Demo
  SET 'gain' '20'
  FUNC 'ratio' = 'DIV' '100,gain'
  MIN 'ratio' '4'
  MAX 'ratio' '6'
"""

    interp = CqlInterpreter(mode="dry-run", quiet=True)
    result = interp.run(src)

    assert result.ok is True
    assert interp.vars.get("ratio") == 5.0
    assert all(step.status in {StepStatus.PASSED, StepStatus.SKIPPED} for step in result.steps)