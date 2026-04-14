"""Tests for extended tokenizer: IF/VAL/MIN/MAX/SAMPLE/GOTO/FUNC/ELSE."""

from __future__ import annotations

from oqlos.core._cql_tokenizer import (
    _try_if_else,
    _try_if_standalone,
    _try_else_standalone,
    _try_min_max,
    _try_val,
    _try_sample,
    _try_goto,
    _try_func,
    _try_save,
    _try_wait,
)


class TestValSingleQuote:
    def test_val_single_quote(self):
        a = _try_val("  VAL 'temperatura' '°C'", "VAL 'temperatura' '°C'")
        assert a is not None
        assert a.kind == "val"
        assert a.target == "temperatura"
        assert a.args == "°C"

    def test_val_double_quote(self):
        a = _try_val('  VAL "wynik" "OK/NOK"', 'VAL "wynik" "OK/NOK"')
        assert a is not None
        assert a.target == "wynik"

    def test_val_bracket(self):
        a = _try_val("  VAL [cn] [mbar]", "VAL [cn] [mbar]")
        assert a is not None
        assert a.target == "cn"


class TestMinMaxSingleQuote:
    def test_min_single_quote(self):
        a = _try_min_max("  MIN 'temperatura' '15 °C'", "MIN 'temperatura' '15 °C'")
        assert a is not None
        assert a.kind == "min"
        assert a.target == "temperatura"
        assert a.args == "15 °C"

    def test_max_single_quote(self):
        a = _try_min_max("  MAX 'AI01' '-9.0 mbar'", "MAX 'AI01' '-9.0 mbar'")
        assert a is not None
        assert a.kind == "max"
        assert a.target == "AI01"
        assert a.args == "-9.0 mbar"

    def test_min_bracket(self):
        a = _try_min_max("  MIN [AI01] = [-10.0 mbar]", "MIN [AI01] = [-10.0 mbar]")
        assert a is not None
        assert a.kind == "min"

    def test_max_double_quote(self):
        a = _try_min_max('  MAX "AI01" "-9.0 mbar"', 'MAX "AI01" "-9.0 mbar"')
        assert a is not None
        assert a.kind == "max"


class TestIfElseSingleQuote:
    def test_if_else_single_quote(self):
        line = "  IF 'AI01' < '-11.0 mbar' ELSE ERROR 'Pressure too low'"
        a = _try_if_else(line, line.strip())
        assert a is not None
        assert a.kind == "if_else"
        assert a.condition.sensor == "AI01"
        assert a.condition.operator == "<"
        assert a.condition.value == -11.0
        assert a.condition.fail_message == "Pressure too low"

    def test_if_else_bracket_single_error(self):
        line = "  IF [NC] [=] [0] ELSE ERROR 'Zawór NC nie zamknięty'"
        a = _try_if_else(line, line.strip())
        assert a is not None
        assert a.condition.sensor == "NC"
        assert a.condition.fail_message == "Zawór NC nie zamknięty"

    def test_if_else_bracket_double_error(self):
        line = '  IF [AI01] [>=] [-15 mbar] ELSE ERROR "Pressure too low"'
        a = _try_if_else(line, line.strip())
        assert a is not None
        assert a.condition.sensor == "AI01"


class TestIfStandalone:
    def test_if_standalone_unicode_op(self):
        line = "  IF 'Timer' ≤ '7.0'"
        a = _try_if_standalone(line, line.strip())
        assert a is not None
        assert a.kind == "if_else"
        assert a.condition.sensor == "Timer"
        assert a.condition.operator == "≤"
        assert a.condition.value == 7.0

    def test_if_standalone_ascii_op(self):
        line = "  IF 'timer' > 'timeout'"
        a = _try_if_standalone(line, line.strip())
        assert a is not None
        assert a.condition.sensor == "timer"
        assert a.condition.operator == ">"

    def test_if_standalone_with_unit(self):
        line = "  IF 'AI01' >= '0.0'"
        a = _try_if_standalone(line, line.strip())
        assert a is not None
        assert a.condition.value == 0.0


class TestElseStandalone:
    def test_else_error(self):
        line = "  ELSE ERROR 'Temperatura poniżej minimum'"
        a = _try_else_standalone(line, line.strip())
        assert a is not None
        assert a.kind == "else"
        assert a.condition.on_fail == "ERROR"
        assert a.condition.fail_message == "Temperatura poniżej minimum"

    def test_else_info(self):
        line = "  ELSE INFO 'Zakończono cykle testowe'"
        a = _try_else_standalone(line, line.strip())
        assert a is not None
        assert a.condition.on_fail == "INFO"


class TestSample:
    def test_sample_with_interval(self):
        line = "  SAMPLE 'czujnik_1' 'START' '500 ms'"
        a = _try_sample(line, line.strip())
        assert a is not None
        assert a.kind == "sample"
        assert a.target == "czujnik_1"
        assert a.args == "START 500 ms"

    def test_sample_stop(self):
        line = "  SAMPLE 'temperatura' 'STOP'"
        a = _try_sample(line, line.strip())
        assert a is not None
        assert a.target == "temperatura"
        assert a.args == "STOP"


class TestGoto:
    def test_goto(self):
        line = "  GOTO 'Pomiar w zakresie wysokim'"
        a = _try_goto(line, line.strip())
        assert a is not None
        assert a.kind == "goto"
        assert a.target == "Pomiar w zakresie wysokim"


class TestFunc:
    def test_func_sub(self):
        line = "  FUNC 'korekta_1' = 'SUB' '0,offset_1'"
        a = _try_func(line, line.strip())
        assert a is not None
        assert a.kind == "func"
        assert a.target == "korekta_1"
        assert a.method == "SUB"
        assert a.args == "0,offset_1"

    def test_func_div(self):
        line = "  FUNC 'wspolczynnik_1' = 'DIV' '100,gain_1'"
        a = _try_func(line, line.strip())
        assert a is not None
        assert a.method == "DIV"


class TestSaveSingleQuote:
    def test_save_single_simple(self):
        line = "  SAVE 'AI01'"
        a = _try_save(line, line.strip())
        assert a is not None
        assert a.kind == "save"
        assert a.target == "AI01"

    def test_save_single_with_namespace(self):
        line = "  SAVE 'korekta_1' 'kalibracja'"
        a = _try_save(line, line.strip())
        assert a is not None
        assert a.target == "korekta_1"
        assert a.args == "kalibracja"


class TestWaitQuoted:
    def test_wait_quoted_seconds(self):
        line = "  WAIT '5 s'"
        a = _try_wait(line, line.strip())
        assert a is not None
        assert a.kind == "wait"
