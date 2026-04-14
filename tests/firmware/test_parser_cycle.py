"""Tests for circular FUNC reference and depth limit detection in the DSL parser."""

from __future__ import annotations

import pytest

from oqlos.core.parser import MAX_FUNC_DEPTH, parse_dsl_to_goal


class TestParserCycleDetection:
    def test_direct_circular_func_raises(self):
        dsl = """\
FUNC: alpha
  FUNC "beta"

FUNC: beta
  FUNC "alpha"

SCENARIO: Circular
GOAL: Test
  FUNC "alpha"
"""
        with pytest.raises(RecursionError, match="Circular FUNC reference"):
            parse_dsl_to_goal(dsl, "circular")

    def test_self_referencing_func_raises(self):
        dsl = """\
FUNC: loop
  FUNC "loop"

SCENARIO: Self
GOAL: Test
  FUNC "loop"
"""
        with pytest.raises(RecursionError, match="Circular FUNC reference"):
            parse_dsl_to_goal(dsl, "self-loop")

    def test_valid_func_call_works(self):
        dsl = """\
FUNC: helper
  SET "pump" "on"

SCENARIO: Normal
GOAL: Test
  FUNC "helper"
"""
        goal = parse_dsl_to_goal(dsl, "valid-func")
        assert goal is not None
        assert any(s.action == "SET_PUMP" for s in goal.steps)

    def test_max_func_depth_constant(self):
        assert MAX_FUNC_DEPTH == 32
