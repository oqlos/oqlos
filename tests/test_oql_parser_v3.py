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
          SET WAIT '500 ms'
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
          SET WAIT '500 ms'
        """
    )
    doc = parse_oql(src)
    assert any("wymaga 'NAME ...' / 'SET NAME ...'" in e for e in doc.errors)


def test_parse_v4_rejects_inline_goal_name():
    src = textwrap.dedent(
        f"""
        VERSION: {OQL_VERSION_CURRENT}
        GOAL test:
          SET WAIT '500 ms'
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
          SET WAIT '500 ms'
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
          SET WAIT '500 ms'
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
            SET WAIT '3 s'
            SET 'motor 2' 'direction right'
            SET 'motor 2' '500000 steps/s'
            SET WAIT '3 s'
        """
    )

    cdoc = parse_flat_oql(src, "repeat.oql")

    assert cdoc.errors == []
    actions = cdoc.goals[0].steps[0].actions
    assert [(a.kind, a.target, a.args) for a in actions] == [
        ("set", "motor 2", "direction left"),
        ("set", "motor 2", "acceleration 100%/s"),
        ("set", "motor 2", "500000 steps/s"),
        ("wait", "", "3 s"),
        ("set", "motor 2", "direction right"),
        ("set", "motor 2", "500000 steps/s"),
        ("wait", "", "3 s"),
        ("set", "motor 2", "direction left"),
        ("set", "motor 2", "acceleration 100%/s"),
        ("set", "motor 2", "500000 steps/s"),
        ("wait", "", "3 s"),
        ("set", "motor 2", "direction right"),
        ("set", "motor 2", "500000 steps/s"),
        ("wait", "", "3 s"),
    ]


# ── MACRO / CALL / INCLUDE ───────────────────────────────────────


def test_macro_call_expansion():
    src = textwrap.dedent(
        """
        MACRO pulse:
          SET pump-main $1 l/min
          SET WAIT '$2'
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


# ── legacy quoted commands: VAL / IF / ELSE / GOTO ────────────────


def _single_goal_doc(body: str, name: str = "test"):
    src = f"GOAL {name}:\n" + textwrap.indent(textwrap.dedent(body).strip(), "  ") + "\n"
    return parse_oql(src)


def test_parse_val_with_unit():
    doc = _single_goal_doc("VAL 'temperatura' '°C'")
    assert not doc.errors
    cmd = doc.blocks[0].cmds[0]
    assert cmd.cmd == "VAL"
    assert cmd.args == {"param": "temperatura", "unit": "°C"}
    assert cmd.raw == "VAL 'temperatura' '°C'"


def test_parse_val_without_unit():
    doc = _single_goal_doc("VAL 'wynik'")
    assert not doc.errors
    cmd = doc.blocks[0].cmds[0]
    assert cmd.args == {"param": "wynik", "unit": None}


def test_parse_if_legacy_comparison():
    doc = _single_goal_doc("IF 'AI01' ≤ '-10.1'")
    assert not doc.errors
    cmd = doc.blocks[0].cmds[0]
    assert cmd.cmd == "IF"
    assert cmd.args == {"param": "AI01", "operator": "≤", "value": "-10.1"}
    assert cmd.raw == "IF 'AI01' ≤ '-10.1'"


def test_parse_if_legacy_with_unit_value():
    doc = _single_goal_doc("IF 'ciśnienie NC' < '6.5 mbar'")
    assert not doc.errors
    cmd = doc.blocks[0].cmds[0]
    assert cmd.cmd == "IF"
    assert cmd.args["param"] == "ciśnienie NC"
    assert cmd.args["value"] == "6.5 mbar"


def test_parse_if_legacy_with_or():
    doc = _single_goal_doc("IF 'cn' < '25' OR 'cn' > '35'")
    assert not doc.errors
    cmd = doc.blocks[0].cmds[0]
    assert cmd.args["or_param"] == "cn"
    assert cmd.args["or_operator"] == ">"
    assert cmd.args["or_value"] == "35"


def test_parse_if_legacy_with_inline_else():
    raw = "IF 'AI01' < '-11.0 mbar' ELSE ERROR 'Wytworzenie podciśnienia [mbar]'"
    doc = _single_goal_doc(raw)
    assert not doc.errors
    cmd = doc.blocks[0].cmds[0]
    assert cmd.cmd == "IF"
    assert cmd.args["else_clause"] == "ERROR 'Wytworzenie podciśnienia [mbar]'"
    assert cmd.raw == raw


def test_parse_if_range_still_lowers_to_check():
    doc = _single_goal_doc("IF AI02 6.0 .. 8.0 bar")
    assert not doc.errors
    assert doc.blocks[0].cmds[0].cmd == "CHECK"


def test_parse_else_error_and_info():
    doc = _single_goal_doc(
        """
        ELSE ERROR 'Temperatura poniżej minimum'
        ELSE INFO 'Zakończono cykle testowe'
        """
    )
    assert not doc.errors
    first, second = doc.blocks[0].cmds
    assert first.cmd == "ELSE"
    assert first.args == {"action": "ERROR", "message": "Temperatura poniżej minimum"}
    assert second.args == {"action": "INFO", "message": "Zakończono cykle testowe"}


def test_parse_else_rejects_unknown_action():
    doc = _single_goal_doc("ELSE WARN 'x'")
    assert any("ERROR lub INFO" in e for e in doc.errors)


def test_parse_goto():
    doc = _single_goal_doc("GOTO 'Pomiar w zakresie wysokim'")
    assert not doc.errors
    cmd = doc.blocks[0].cmds[0]
    assert cmd.cmd == "GOTO"
    assert cmd.args == {"target": "Pomiar w zakresie wysokim"}


def test_parse_minmax_quoted_combined_value_unit():
    doc = _single_goal_doc(
        """
        MIN 'temperatura' '15 °C'
        MAX 'wilgotnosc' '70 %RH'
        """
    )
    assert not doc.errors
    mn, mx = doc.blocks[0].cmds
    assert mn.args == {"sensor": "temperatura", "value": 15, "unit": "°C"}
    assert mx.args == {"sensor": "wilgotnosc", "value": 70, "unit": "%RH"}


def test_adapter_lowers_legacy_commands_preserving_raw():
    src = textwrap.dedent(
        """
        VERSION: 4
        GOAL:
          SET NAME 'Pomiar'
          VAL 'cn' 'mbar'
          IF 'cn' > 'próg_przełączenia'
          GOTO 'Pomiar w zakresie wysokim'
          ELSE ERROR 'Ciśnienie poza zakresem'
        """
    )
    cdoc = parse_flat_oql(src)
    assert not cdoc.errors
    goal = cdoc.goals[0]
    assert goal.name == "Pomiar"
    actions = goal.steps[0].actions
    kinds = [a.kind for a in actions]
    assert kinds == ["val", "if", "goto", "else"]
    raws = [a.raw for a in actions]
    assert raws == [
        "VAL 'cn' 'mbar'",
        "IF 'cn' > 'próg_przełączenia'",
        "GOTO 'Pomiar w zakresie wysokim'",
        "ELSE ERROR 'Ciśnienie poza zakresem'",
    ]
    val = actions[0]
    assert val.target == "cn" and val.args == "mbar"
    goto = actions[2]
    assert goto.target == "Pomiar w zakresie wysokim"
    els = actions[3]
    assert els.method == "ERROR" and els.args == "Ciśnienie poza zakresem"


# ── OQL v5: RANGE / PASS / FAIL + wersjonowanie ───────────────────


def test_version_constants_v5():
    from oqlos.core.oql_versioning import (
        OQL_VERSION_LEGACY,
        OQL_VERSION_V4,
        SUPPORTED_OQL_VERSIONS,
    )

    assert OQL_VERSION_CURRENT == 5
    assert SUPPORTED_OQL_VERSIONS == (OQL_VERSION_LEGACY, OQL_VERSION_V4, OQL_VERSION_CURRENT)


def test_parse_version5_accepted():
    src = textwrap.dedent(
        """
        VERSION: 5
        GOAL:
          SET NAME 'Test v5'
          SET WAIT '500 ms'
        """
    )
    doc = parse_oql(src)
    assert not doc.errors
    assert doc.oql_version == 5
    assert doc.blocks[0].name == "Test v5"


def test_parse_version4_still_works_unchanged():
    src = textwrap.dedent(
        """
        VERSION: 4
        GOAL:
          SET NAME 'Test v4'
          SET 'PUMP' '5 l'
          MIN 'AI01' '-11.0 mbar'
        """
    )
    doc = parse_oql(src)
    assert not doc.errors
    assert doc.oql_version == 4
    assert doc.blocks[0].name == "Test v4"


def test_parse_version4_goal_rules_still_enforced():
    # v4 nie może stracić swoich reguł po podbiciu current → 5
    doc = parse_oql("VERSION: 4\nGOAL nazwa-inline:\n  SET x 0\n")
    assert any("użyj 'GOAL:'" in e for e in doc.errors)
    doc2 = parse_oql("VERSION: 4\nGOAL:\n  SET x 0\n")
    assert any("wymaga 'NAME ...' / 'SET NAME ...'" in e for e in doc2.errors)


def test_parse_range_with_units():
    doc = _single_goal_doc("RANGE 'ciśnienie NC' '4.2 mbar' .. '6.0 mbar'")
    assert not doc.errors
    cmd = doc.blocks[0].cmds[0]
    assert cmd.cmd == "RANGE"
    assert cmd.args == {
        "sensor": "ciśnienie NC", "min": 4.2, "max": 6.0, "unit": "mbar",
        "min_spec": "4.2 mbar", "max_spec": "6.0 mbar",
    }
    assert cmd.raw == "RANGE 'ciśnienie NC' '4.2 mbar' .. '6.0 mbar'"


def test_parse_range_without_units():
    doc = _single_goal_doc("RANGE 'Timer' '1' .. '3'")
    assert not doc.errors
    cmd = doc.blocks[0].cmds[0]
    assert cmd.args == {
        "sensor": "Timer", "min": 1, "max": 3, "unit": None,
        "min_spec": "1", "max_spec": "3",
    }


def test_parse_range_single_unit_applies():
    doc = _single_goal_doc("RANGE 'AI02' '6.0' .. '8.0 bar'")
    assert not doc.errors
    assert doc.blocks[0].cmds[0].args["unit"] == "bar"


def test_parse_range_bare_tokens():
    doc = _single_goal_doc("RANGE AI02 6.0 bar .. 8.0 bar")
    assert not doc.errors
    cmd = doc.blocks[0].cmds[0]
    assert cmd.args == {
        "sensor": "AI02", "min": 6.0, "max": 8.0, "unit": "bar",
        "min_spec": "6.0 bar", "max_spec": "8.0 bar",
    }


def test_parse_range_mismatched_units_is_error():
    doc = _single_goal_doc("RANGE 'AI01' '4.2 mbar' .. '6.0 bar'")
    assert any("jednostki granic muszą być identyczne" in e for e in doc.errors)


def test_parse_range_missing_separator_is_error():
    doc = _single_goal_doc("RANGE 'AI01' '4.2 mbar' '6.0 mbar' zonk")
    assert any("separatora '..'" in e for e in doc.errors)


def test_parse_pass_message():
    doc = _single_goal_doc("PASS 'Ciśnienie otwarcia w normie'")
    assert not doc.errors
    cmd = doc.blocks[0].cmds[0]
    assert cmd.cmd == "PASS"
    assert cmd.args == {"message": "Ciśnienie otwarcia w normie"}


def test_parse_fail_message():
    doc = _single_goal_doc("FAIL 'Ciśnienie poza zakresem'")
    assert not doc.errors
    cmd = doc.blocks[0].cmds[0]
    assert cmd.cmd == "FAIL"
    assert cmd.args == {"message": "Ciśnienie poza zakresem"}


def test_parse_fail_with_goto_tail():
    doc = _single_goal_doc("FAIL 'Poza zakresem' GOTO 'Pomiar w zakresie wysokim'")
    assert not doc.errors
    cmd = doc.blocks[0].cmds[0]
    assert cmd.args == {"message": "Poza zakresem", "goto": "Pomiar w zakresie wysokim"}


def test_parse_fail_with_retry_tail():
    doc = _single_goal_doc("FAIL 'Poza zakresem' RETRY 3")
    assert not doc.errors
    cmd = doc.blocks[0].cmds[0]
    assert cmd.args == {"message": "Poza zakresem", "retry": 3}


def test_parse_fail_retry_requires_integer():
    doc = _single_goal_doc("FAIL 'msg' RETRY dużo")
    assert any("liczby całkowitej" in e for e in doc.errors)


def test_adapter_range_lowers_to_min_max_with_synthetic_raw():
    src = textwrap.dedent(
        """
        VERSION: 5
        GOAL:
          SET NAME 'Zakres'
          RANGE 'ciśnienie NC' '4.2 mbar' .. '6.0 mbar'
        """
    )
    cdoc = parse_flat_oql(src)
    assert not cdoc.errors
    actions = cdoc.goals[0].steps[0].actions
    # lowering zachowuje oryginalny zapis liczby ('6.0', nie '6')
    assert [(a.kind, a.target, a.args, a.raw) for a in actions] == [
        ("min", "ciśnienie NC", "4.2 mbar", "MIN 'ciśnienie NC' '4.2 mbar'"),
        ("max", "ciśnienie NC", "6.0 mbar", "MAX 'ciśnienie NC' '6.0 mbar'"),
    ]


def test_adapter_pass_and_fail_lowering():
    src = textwrap.dedent(
        """
        VERSION: 5
        GOAL:
          SET NAME 'Werdykt'
          PASS 'OK'
          FAIL 'NOK'
        """
    )
    cdoc = parse_flat_oql(src)
    assert not cdoc.errors
    actions = cdoc.goals[0].steps[0].actions
    # werdykty deklaratywne lowerują się jak ELSE INFO/ERROR (kind=else),
    # nie jako bezwarunkowe log/error
    assert [(a.kind, a.method, a.args, a.raw) for a in actions] == [
        ("else", "INFO", "OK", "PASS 'OK'"),
        ("else", "ERROR", "NOK", "FAIL 'NOK'"),
    ]


def test_adapter_fail_goto_emits_goto_action():
    src = textwrap.dedent(
        """
        VERSION: 5
        GOAL:
          SET NAME 'Skok'
          FAIL 'NOK' GOTO 'Pomiar w zakresie wysokim'
        """
    )
    cdoc = parse_flat_oql(src)
    assert not cdoc.errors
    actions = cdoc.goals[0].steps[0].actions
    # raw akcji error jest syntetyczne (bez ogona) — pełna linia w obu raw
    # podwajałaby kroki w goals_from_cql (c2004).
    assert [(a.kind, a.target, a.raw) for a in actions] == [
        ("else", "", "FAIL 'NOK'"),
        ("goto", "Pomiar w zakresie wysokim", "GOTO 'Pomiar w zakresie wysokim'"),
    ]


def test_adapter_fail_retry_emits_retry_action():
    src = textwrap.dedent(
        """
        VERSION: 5
        GOAL:
          SET NAME 'Powtórka'
          FAIL 'NOK' RETRY 2
        """
    )
    cdoc = parse_flat_oql(src)
    assert not cdoc.errors
    actions = cdoc.goals[0].steps[0].actions
    assert [(a.kind, a.args) for a in actions] == [("else", "NOK"), ("retry", "2")]
    assert actions[0].raw == "FAIL 'NOK'"
    assert actions[1].raw == "RETRY 2"


# ── 2026-07 dialect: TEST:, bare NAME, TIMER ─────────────────────


NEW_DIALECT_SRC = textwrap.dedent(
    """
    VERSION: 5
    SCENARIO: 'Motor Test'
    GOAL:
      NAME 'Kontrola wizualna'
      TIMER '2 s'
      GET 'AI01'
      PASS 'AI01' 'w normie'
    TEST:
      NAME 'Test szczelności'
      SET 'pompa' '5 l'
      RANGE 'AI02' '4.2 mbar' .. '6.0 mbar'
      VAL 'AI02' 'mbar'
    """
)


def test_new_dialect_bare_name_sets_block_name():
    doc = parse_oql(NEW_DIALECT_SRC)
    assert not doc.errors
    assert [b.name for b in doc.blocks] == ["Kontrola wizualna", "Test szczelności"]


def test_new_dialect_test_block_normalizes_to_goal():
    doc = parse_oql(NEW_DIALECT_SRC)
    assert [b.type for b in doc.blocks] == ["GOAL", "GOAL"]


def test_new_dialect_timer_is_wait_alias():
    doc = parse_oql(NEW_DIALECT_SRC)
    waits = [c for c in doc.blocks[0].cmds if c.cmd == "WAIT"]
    assert len(waits) == 1
    assert waits[0].args["ms"] == 2000


def test_new_dialect_is_detected_as_flat_oql():
    assert is_flat_oql(NEW_DIALECT_SRC) is True
    # bez nagłówka VERSION nadal wykrywalny po TEST: + NAME
    headless = "\n".join(
        line for line in NEW_DIALECT_SRC.splitlines() if not line.startswith("VERSION")
    )
    assert is_flat_oql(headless) is True


def test_new_dialect_adapter_yields_named_goals():
    cdoc = parse_flat_oql(NEW_DIALECT_SRC)
    assert not cdoc.errors
    assert [g.name for g in cdoc.goals] == ["Kontrola wizualna", "Test szczelności"]


def test_new_dialect_bare_name_in_func_block():
    src = textwrap.dedent(
        """
        VERSION: 5
        FUNC:
          NAME 'Move Left'
          SET 'motor2' '1000 steps/s'
        GOAL:
          NAME 'Test motor'
          FUNC 'Move Left'
        """
    )
    doc = parse_oql(src)
    assert not doc.errors
    func_blocks = [b for b in doc.blocks if b.type == "FUNC"]
    assert func_blocks and func_blocks[0].name == "Move Left"
