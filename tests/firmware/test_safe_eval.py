"""Comprehensive tests for safe_eval_condition — the AST-based expression evaluator.

Covers:
- Basic comparisons (==, !=, <, <=, >, >=)
- Boolean operators (and, or, not)
- Chained comparisons (a < b < c)
- Negative numbers and unary operators
- Dotted attribute access (obj.attr)
- Security: rejects dangerous constructs (calls, imports, subscripts, lambdas)
- Edge cases: empty strings, unknown variables, unsupported ops
"""

import sys
import os
import pytest

# Ensure firmware root is on sys.path so we can import the module under test
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.scenario_orchestrator import safe_eval_condition


# ---------------------------------------------------------------------------
# Helper: simple namespace for dotted-attribute tests
# ---------------------------------------------------------------------------
class _Obj:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


# ===== Basic comparisons =====================================================

class TestBasicComparisons:
    def test_eq_true(self):
        assert safe_eval_condition("x == 10", {"x": 10}) is True

    def test_eq_false(self):
        assert safe_eval_condition("x == 10", {"x": 5}) is False

    def test_ne_true(self):
        assert safe_eval_condition("x != 10", {"x": 5}) is True

    def test_ne_false(self):
        assert safe_eval_condition("x != 10", {"x": 10}) is False

    def test_lt(self):
        assert safe_eval_condition("x < 10", {"x": 5}) is True
        assert safe_eval_condition("x < 10", {"x": 10}) is False

    def test_le(self):
        assert safe_eval_condition("x <= 10", {"x": 10}) is True
        assert safe_eval_condition("x <= 10", {"x": 11}) is False

    def test_gt(self):
        assert safe_eval_condition("x > 0", {"x": 1}) is True
        assert safe_eval_condition("x > 0", {"x": 0}) is False

    def test_ge(self):
        assert safe_eval_condition("x >= 0", {"x": 0}) is True
        assert safe_eval_condition("x >= 0", {"x": -1}) is False

    def test_float_comparison(self):
        assert safe_eval_condition("pressure >= -60.5", {"pressure": -60.0}) is True
        assert safe_eval_condition("pressure >= -60.5", {"pressure": -61.0}) is False


# ===== Boolean operators =====================================================

class TestBooleanOps:
    def test_and_true(self):
        assert safe_eval_condition("x > 0 and y > 0", {"x": 1, "y": 2}) is True

    def test_and_false(self):
        assert safe_eval_condition("x > 0 and y > 0", {"x": 1, "y": -1}) is False

    def test_or_true(self):
        assert safe_eval_condition("x > 0 or y > 0", {"x": -1, "y": 1}) is True

    def test_or_false(self):
        assert safe_eval_condition("x > 0 or y > 0", {"x": -1, "y": -1}) is False

    def test_not_true(self):
        assert safe_eval_condition("not x > 10", {"x": 5}) is True

    def test_not_false(self):
        assert safe_eval_condition("not x > 10", {"x": 15}) is False

    def test_complex_boolean(self):
        ctx = {"a": 5, "b": 10, "c": 15}
        assert safe_eval_condition("a < b and b < c", ctx) is True
        assert safe_eval_condition("a > b or c > b", ctx) is True
        assert safe_eval_condition("a > b and c > b", ctx) is False


# ===== Chained comparisons ===================================================

class TestChainedComparisons:
    def test_chained_lt(self):
        assert safe_eval_condition("0 < x < 100", {"x": 50}) is True
        assert safe_eval_condition("0 < x < 100", {"x": 0}) is False
        assert safe_eval_condition("0 < x < 100", {"x": 100}) is False

    def test_chained_le(self):
        assert safe_eval_condition("0 <= x <= 100", {"x": 0}) is True
        assert safe_eval_condition("0 <= x <= 100", {"x": 100}) is True


# ===== Negative numbers and unary ops ========================================

class TestNegativeNumbers:
    def test_negative_literal(self):
        assert safe_eval_condition("x > -10", {"x": -5}) is True
        assert safe_eval_condition("x > -10", {"x": -15}) is False

    def test_negative_context_value(self):
        assert safe_eval_condition("x < 0", {"x": -60.0}) is True

    def test_unary_plus(self):
        assert safe_eval_condition("x == +5", {"x": 5}) is True


# ===== Dotted attribute access ===============================================

class TestDottedAccess:
    def test_simple_attr(self):
        sensor = _Obj(currentValue=-55.0)
        assert safe_eval_condition("nc_sensor.currentValue < 0", {"nc_sensor": sensor}) is True

    def test_attr_comparison(self):
        sensor = _Obj(currentValue=25.0, unit="bar")
        assert safe_eval_condition("sc_sensor.currentValue >= 20", {"sc_sensor": sensor}) is True

    def test_unknown_attr_raises(self):
        sensor = _Obj(currentValue=10)
        with pytest.raises(ValueError, match="no attribute"):
            safe_eval_condition("sensor.nonexistent > 0", {"sensor": sensor})


# ===== Error handling ========================================================

class TestErrorHandling:
    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="Invalid expression syntax"):
            safe_eval_condition("", {})

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="Invalid expression syntax"):
            safe_eval_condition("   ", {})

    def test_unknown_variable_raises(self):
        with pytest.raises(ValueError, match="Unknown variable"):
            safe_eval_condition("unknown_var > 0", {})

    def test_syntax_error_raises(self):
        with pytest.raises(ValueError, match="Invalid expression syntax"):
            safe_eval_condition("x >>> 5", {"x": 1})

    def test_unsupported_node_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            safe_eval_condition("[1, 2, 3]", {})


# ===== SECURITY: reject dangerous constructs =================================

class TestSecurity:
    """Ensure the evaluator rejects any construct that could execute arbitrary code."""

    def test_reject_function_call(self):
        with pytest.raises(ValueError):
            safe_eval_condition("print('hacked')", {})

    def test_reject_import(self):
        with pytest.raises(ValueError):
            safe_eval_condition("__import__('os')", {})

    def test_reject_lambda(self):
        with pytest.raises(ValueError):
            safe_eval_condition("(lambda: 1)()", {})

    def test_reject_list_comprehension(self):
        with pytest.raises(ValueError):
            safe_eval_condition("[x for x in range(10)]", {})

    def test_reject_dict_literal(self):
        with pytest.raises(ValueError):
            safe_eval_condition("{'key': 'value'}", {})

    def test_reject_subscript(self):
        with pytest.raises(ValueError):
            safe_eval_condition("x[0]", {"x": [1, 2, 3]})

    def test_reject_string_literal(self):
        # String constants are not in the allowed (int, float, bool) set
        with pytest.raises(ValueError):
            safe_eval_condition("x == 'admin'", {"x": "admin"})

    def test_reject_fstring(self):
        with pytest.raises(ValueError):
            safe_eval_condition("f'{__import__(\"os\")}'", {})

    def test_reject_walrus_operator(self):
        with pytest.raises(ValueError):
            safe_eval_condition("(x := 42)", {"x": 0})

    def test_reject_attribute_dunder(self):
        """Even though dotted access is allowed, __class__ etc. should fail
        because the context won't contain such objects naturally."""
        with pytest.raises(ValueError):
            safe_eval_condition("x.__class__.__name__ == 'int'", {"x": 42})

    def test_reject_exec_via_eval(self):
        with pytest.raises(ValueError):
            safe_eval_condition("eval('1+1')", {})

    def test_reject_getattr_builtin(self):
        with pytest.raises(ValueError):
            safe_eval_condition("getattr(x, '__class__')", {"x": 1})


# ===== Real-world firmware scenarios =========================================

class TestFirmwareScenarios:
    """Test expressions that mirror actual firmware validation conditions."""

    def test_valve_pressure_check(self):
        nc_sensor = _Obj(currentValue=-55.0)
        assert safe_eval_condition(
            "nc_sensor.currentValue >= -60 and nc_sensor.currentValue <= -50",
            {"nc_sensor": nc_sensor}
        ) is True

    def test_pump_power_range(self):
        ctx = {"value": 85.0}
        assert safe_eval_condition("value >= 80 and value <= 100", ctx) is True

    def test_leak_rate_validation(self):
        ctx = {"value": 0.3, "leakRate": 0}
        assert safe_eval_condition("value <= 0.5", ctx) is True

    def test_sensor_threshold(self):
        sc_sensor = _Obj(currentValue=25.5)
        assert safe_eval_condition("sc_sensor.currentValue > 20", {"sc_sensor": sc_sensor}) is True

    def test_boolean_context_value(self):
        # Valve open/close state as boolean
        assert safe_eval_condition("valve_open == 1", {"valve_open": True}) is True
        assert safe_eval_condition("valve_open == 0", {"valve_open": False}) is True
