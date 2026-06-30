"""Unit tests for the v3 flat OQL parser and its OQL→CQL adapter."""

from __future__ import annotations

import textwrap

import pytest

from oqlos.core._oql_adapter import is_flat_oql, parse_flat_oql
from oqlos.core.oql_parser import (
    BASE_COMMANDS,
    parse_oql,
    duration_to_ms,
    tokenize,
)
from oqlos.core.oql_versioning import OQL_VERSION_CURRENT


# ── tokenize ─────────────────────────────────────────────────────


def test_tokenize_simple():
    assert tokenize("pump-main 5.0 l/min") == ["pump-main", "5.0", "l/min"]


def test_tokenize_brackets_allow_spaces():
    assert tokenize("[pompa głównego obiegu] 5 l/min") == [
        "pompa głównego obiegu",
        "5",
        "l/min",
    ]


def test_tokenize_double_quoted_string():
    assert tokenize('"Hello world" extra') == ["Hello world", "extra"]


def test_tokenize_single_quoted_string():
    assert tokenize("'Ciśnienie NC'") == ["Ciśnienie NC"]


def test_tokenize_unclosed_quote_raises():
    with pytest.raises(ValueError):
        tokenize('"open')


def test_tokenize_unclosed_bracket_raises():
    with pytest.raises(ValueError):
        tokenize("[open")


# ── duration parsing ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "token,expected",
    [
        ("3s", 3000),
        ("500ms", 500),
        ("3000", 3000),
        ("2m", 120_000),
        ("1h", 3_600_000),
    ],
)
def test_duration_to_ms(token, expected):
    assert duration_to_ms(token) == expected


# ── parser smoke ─────────────────────────────────────────────────


def test_parse_minimal_goal():
    src = textwrap.dedent(
        """
        GOAL ping:
          SET pump-main 0
          WAIT 500ms
        """
    )
    doc = parse_oql(src)
    assert not doc.errors
    assert len(doc.blocks) == 1
    goal = doc.blocks[0]
    assert goal.type == "GOAL"
    assert goal.name == "ping"
    assert [c.cmd for c in goal.cmds] == ["SET", "WAIT"]


def test_parse_metadata():
    src = textwrap.dedent(
        """
        SCENARIO: Test smoke
        DEVICE_TYPE: BA
        DEVICE_MODEL: PSS 7000
        MANUFACTURER: Dräger

        GOAL probe:
          SET pump-main 0
        """
    )
    doc = parse_oql(src)
    assert doc.meta["scenario"] == "Test smoke"
    assert doc.meta["device_type"] == "BA"
    assert doc.meta["device_model"] == "PSS 7000"
    assert doc.meta["manufacturer"] == "Dräger"


def test_parse_check_range():
    src = "GOAL c:\n  CHECK 6.0 <= AI02 <= 8.0 bar\n"
    doc = parse_oql(src)
    assert not doc.errors
    check = doc.blocks[0].cmds[0]
    assert check.cmd == "CHECK"
    assert check.args == {"min": 6.0, "sensor": "AI02", "max": 8.0, "unit": "bar"}


def test_parse_check_negative_values():
    src = "GOAL c:\n  CHECK -29.0 <= AI01 <= -5.0 mbar\n"
    doc = parse_oql(src)
    assert not doc.errors


def test_parse_sample_with_interval():
    src = "GOAL s:\n  SAMPLE ciśnienie START 50ms\n"
    doc = parse_oql(src)
    cmd = doc.blocks[0].cmds[0]
    assert cmd.cmd == "SAMPLE"
    assert cmd.args["interval_ms"] == 50
    assert cmd.args["direction"] == "START"


def test_parse_if_delta_signed_threshold():
    src = "GOAL d:\n  IF_DELTA 'AI01' '5 s' '+0.1l/min'\n"
    doc = parse_oql(src)
    assert not doc.errors
    cmd = doc.blocks[0].cmds[0]
    assert cmd.cmd == "IF_DELTA"
    assert cmd.args["sensor"] == "AI01"
    assert cmd.args["window_ms"] == 5000
    assert cmd.args["operator"] == ">"
    assert cmd.args["threshold"] == 0.1
    assert cmd.args["unit"] == "l/min"


def test_parse_unicode_identifiers():
    src = "GOAL u:\n  SAVE ciśnienie-NC\n  CHECK 15 <= temperatura <= 25 °C\n"
    doc = parse_oql(src)
    assert not doc.errors
    assert doc.blocks[0].cmds[0].args["label"] == "ciśnienie-NC"
    assert doc.blocks[0].cmds[1].args["unit"] == "°C"


def test_parse_bracketed_target_with_spaces():
    src = "GOAL b:\n  SET [pompa głównego obiegu] 5 l/min\n"
    doc = parse_oql(src)
    cmd = doc.blocks[0].cmds[0]
    assert cmd.args["target"] == "pompa głównego obiegu"


def test_parse_bracketed_block_name():
    src = "GOAL [nazwa z spacjami]:\n  SET x 0\n"
    doc = parse_oql(src)
    assert doc.blocks[0].name == "nazwa z spacjami"


def test_parse_rejects_unindented_command():
    src = "GOAL g:\nSET pump-main 0\n"
    doc = parse_oql(src)
    assert doc.errors


def test_parse_rejects_unknown_command():
    src = "GOAL g:\n  FOOBAR x 1\n"
    doc = parse_oql(src)
    assert any("nieznana komenda" in e for e in doc.errors)


def test_parse_v4_goal_requires_set_name():
    src = textwrap.dedent(
        f"""
        VERSION: {OQL_VERSION_CURRENT}
        GOAL:
          WAIT 500ms
        """
    )
    doc = parse_oql(src)
    assert any("wymaga 'SET NAME ...'" in e for e in doc.errors)


def test_parse_v4_rejects_inline_goal_name():
    src = textwrap.dedent(
        f"""
        VERSION: {OQL_VERSION_CURRENT}
        GOAL test:
          WAIT 500ms
        """
    )
    doc = parse_oql(src)
    assert any("użyj 'GOAL:'" in e for e in doc.errors)


def test_parse_v4_goal_name_from_set_name():
    src = textwrap.dedent(
        f"""
        VERSION: {OQL_VERSION_CURRENT}
        GOAL:
          SET NAME 'Test ciśnienia'
          WAIT 500ms
        """
    )
    doc = parse_oql(src)
    assert not doc.errors
    assert doc.blocks[0].name == "Test ciśnienia"


def test_parse_rejects_unsupported_oql_version():
    src = "VERSION: 99\nGOAL g:\n  SET x 0\n"
    doc = parse_oql(src)
    assert any("Nieobsługiwana wersja OQL" in e for e in doc.errors)


def test_base_commands_list_matches_dispatcher():
    from oqlos.core.oql_parser import DISPATCHERS
    # All base commands except CHECK must be in DISPATCHERS
    expected_in_dispatch = set(BASE_COMMANDS) - {"CHECK"}
    assert expected_in_dispatch <= set(DISPATCHERS)


# ── adapter + detection ──────────────────────────────────────────


def test_is_flat_oql_detects_new_syntax():
    assert is_flat_oql("GOAL test:\n  SET x 0\n") is True
    assert is_flat_oql('INCLUDE "lib/x.oql"\nGOAL t:\n  SET x 0\n') is True
    assert is_flat_oql(f"VERSION: {OQL_VERSION_CURRENT}\nGOAL:\n  SET NAME 'x'\n") is True
    assert is_flat_oql("SCENARIO: Test\nGOAL:\n  SET NAME 'x'\n  SET 'pump' 25\n") is True


def test_is_flat_oql_rejects_legacy():
    assert is_flat_oql("GOAL: Test\n  SET 'x' '0'\n") is False


def test_adapter_produces_cql_goals():
    src = textwrap.dedent(
        """
        SCENARIO: Ad
        GOAL a:
          SET pump-main 0
          WAIT 500ms
        GOAL b:
          CHECK 6 <= AI02 <= 8 bar
        """
    )
    cdoc = parse_flat_oql(src, "ad.oql")
    assert cdoc.metadata.scenario_name == "Ad"
    names = [g.name for g in cdoc.goals]
    assert "a" in names and "b" in names


def test_adapter_config_prefix():
    src = textwrap.dedent(
        """
        CONFIG init:
          SET pump-main 0
        GOAL test:
          SET pump-main 1
        """
    )
    cdoc = parse_flat_oql(src)
    names = [g.name for g in cdoc.goals]
    # CONFIG blocks come first and are prefixed with [CONFIG]
    assert names[0].startswith("[CONFIG]")
    assert names[-1] == "test"


def test_version4_set_accepts_textual_hardware_values():
    src = textwrap.dedent(
        f"""
        VERSION: {OQL_VERSION_CURRENT}
        GOAL:
          SET NAME 'Hardware smoke'
          SET 'zawor 3' 'ON'
          SET 'PUMP' '5l'
          SET 'WAIT' '1s'
          SET WAIT '1 s'
          SET 'PUMP' 'OFF'
        """
    )

    cdoc = parse_flat_oql(src, "hardware-smoke.oql")

    assert cdoc.errors == []
    actions = cdoc.goals[0].steps[0].actions
    assert [(a.kind, a.target, a.args) for a in actions] == [
        ("set", "zawor 3", "ON"),
        ("set", "PUMP", "5l"),
        ("wait", "", "1s"),
        ("wait", "", "1 s"),
        ("set", "PUMP", "OFF"),
    ]


def test_version4_repeat_count_expands_indented_block():
    src = textwrap.dedent(
        f"""
        VERSION: {OQL_VERSION_CURRENT}
        GOAL:
          REPEAT 2:
            SET NAME 'Test spadku cisnienia automatu'
            SET 'motor 2' 'direction left'
            SET 'motor 2' 'acceleration 100%/s'
            SET 'motor 2' '500000 steps/s'
            WAIT 3s
            SET 'motor 2' 'direction right'
            SET 'motor 2' '500000 steps/s'
            WAIT 3s
        """
    )

    cdoc = parse_flat_oql(src, "repeat.oql")

    assert cdoc.errors == []
    actions = cdoc.goals[0].steps[0].actions
    assert [(a.kind, a.target, a.args) for a in actions] == [
        ("set", "motor 2", "direction left"),
        ("set", "motor 2", "acceleration 100%/s"),
        ("set", "motor 2", "500000 steps/s"),
        ("wait", "", "3s"),
        ("set", "motor 2", "direction right"),
        ("set", "motor 2", "500000 steps/s"),
        ("wait", "", "3s"),
        ("set", "motor 2", "direction left"),
        ("set", "motor 2", "acceleration 100%/s"),
        ("set", "motor 2", "500000 steps/s"),
        ("wait", "", "3s"),
        ("set", "motor 2", "direction right"),
        ("set", "motor 2", "500000 steps/s"),
        ("wait", "", "3s"),
    ]


# ── MACRO / CALL / INCLUDE ───────────────────────────────────────


def test_macro_call_expansion():
    src = textwrap.dedent(
        """
        MACRO pulse:
          SET pump-main $1 l/min
          WAIT $2
          SET pump-main 0

        GOAL ramp:
          CALL pulse 5 500ms
        """
    )
    cdoc = parse_flat_oql(src)
    goal = [g for g in cdoc.goals if g.name == "ramp"][0]
    actions = goal.steps[0].actions
    # Three actions expanded: SET 5 l/min, WAIT 500ms, SET 0
    assert len(actions) == 3
    assert actions[0].kind == "set"
    assert "5 l/min" in actions[0].args
    assert actions[1].kind == "wait"
    assert "500ms" in actions[1].args


def test_unknown_macro_becomes_error_action():
    src = "GOAL g:\n  CALL does-not-exist\n"
    cdoc = parse_flat_oql(src)
    actions = cdoc.goals[0].steps[0].actions
    assert actions[0].kind == "error"
    assert "Nieznane makro" in actions[0].args


def test_include_resolves_from_scenarios_root():
    src = textwrap.dedent(
        """
        INCLUDE "lib/peripherals.oql"

        GOAL reset:
          CALL init-pump
        """
    )
    cdoc = parse_flat_oql(src, "smoke.oql")
    assert not cdoc.errors
    actions = cdoc.goals[0].steps[0].actions
    # init-pump expands to 2×SET + 1×WAIT
    assert [a.kind for a in actions] == ["set", "set", "wait"]


def test_include_missing_file_yields_error():
    src = 'INCLUDE "nonexistent/path.oql"\nGOAL g:\n  SET x 0\n'
    cdoc = parse_flat_oql(src)
    assert any("nie znaleziono" in e for e in cdoc.errors)


# ── CORRECT / ERROR messages after CHECK ─────────────────────────


def test_check_with_correct_message():
    src = textwrap.dedent(
        """
        GOAL test:
          CHECK 6.0 <= AI02 <= 8.0 bar
          CORRECT 'Ciśnienie w normie'
        """
    )
    doc = parse_oql(src)
    assert not doc.errors
    check = doc.blocks[0].cmds[0]
    assert check.cmd == "CHECK"
    assert check.args.get("correct_msg") == "Ciśnienie w normie"


def test_check_with_error_message():
    src = textwrap.dedent(
        """
        GOAL test:
          CHECK 6.0 <= AI02 <= 8.0 bar
          ERROR 'Ciśnienie poza zakresem - sprawdź zawór'
        """
    )
    doc = parse_oql(src)
    assert not doc.errors
    check = doc.blocks[0].cmds[0]
    assert check.cmd == "CHECK"
    assert check.args.get("error_msg") == "Ciśnienie poza zakresem - sprawdź zawór"


def test_check_with_both_messages():
    src = textwrap.dedent(
        """
        GOAL test:
          CHECK 6.0 <= AI02 <= 8.0 bar
          CORRECT 'Ciśnienie w normie'
          ERROR 'Ciśnienie poza zakresem'
        """
    )
    doc = parse_oql(src)
    assert not doc.errors
    check = doc.blocks[0].cmds[0]
    assert check.args.get("correct_msg") == "Ciśnienie w normie"
    assert check.args.get("error_msg") == "Ciśnienie poza zakresem"


def test_correct_without_check_is_error():
    src = textwrap.dedent(
        """
        GOAL test:
          SET pump-main 0
          CORRECT 'Nie powinno działać'
        """
    )
    doc = parse_oql(src)
    assert any("musi występować bezpośrednio po CHECK" in e for e in doc.errors)


def test_adapter_uses_custom_messages():
    src = textwrap.dedent(
        """
        GOAL test:
          CHECK 6.0 <= AI02 <= 8.0 bar
          CORRECT 'Wartość OK'
          ERROR 'Wartość poza zakresem'
        """
    )
    cdoc = parse_flat_oql(src)
    goal = cdoc.goals[0]
    action = goal.steps[0].actions[0]
    assert action.kind == "condition"
    assert action.condition.pass_message == "Wartość OK"
    assert action.condition.fail_message == "Wartość poza zakresem"


def test_adapter_if_delta_uses_custom_messages_and_delta_sensor():
    src = textwrap.dedent(
        """
        GOAL test:
          IF_DELTA 'AI01' '5 s' '-0.1l/min'
          CORRECT 'Delta OK'
          ERROR 'Delta NOK'
        """
    )
    cdoc = parse_flat_oql(src)
    action = cdoc.goals[0].steps[0].actions[0]
    assert action.kind == "condition"
    assert action.condition.sensor == "ΔAI01"
    assert action.condition.operator == "<"
    assert action.condition.value == 0.1
    assert action.condition.unit == "l/min"
    assert action.condition.pass_message == "Delta OK"
    assert action.condition.fail_message == "Delta NOK"
