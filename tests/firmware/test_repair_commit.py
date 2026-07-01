"""Regression: the automated-repair commit gate never accepts physical-actuation
actions, and the commit message convention is stable/greppable.
"""

from __future__ import annotations

from oqlos.errors import format_repair_commit_message, is_eligible_for_automated_commit
from oqlos.hardware.diagnosis_types import DiagnosisAction


def _action(**overrides) -> DiagnosisAction:
    base = dict(
        id="some-action",
        device_id="modbus-adc",
        label="Some action",
        kind="oqlos",
        priority=5,
        auto_executable=True,
        scope="oqlos",
        actuation_risk="config",
    )
    base.update(overrides)
    return DiagnosisAction(**base)


def test_config_risk_auto_executable_action_is_eligible():
    action = _action(actuation_risk="config", auto_executable=True)
    assert is_eligible_for_automated_commit(action) is True


def test_physical_risk_action_is_never_eligible_even_if_auto_executable():
    action = _action(actuation_risk="physical", auto_executable=True)
    assert is_eligible_for_automated_commit(action) is False


def test_none_risk_action_is_not_eligible():
    action = _action(actuation_risk="none", auto_executable=True)
    assert is_eligible_for_automated_commit(action) is False


def test_config_risk_action_not_marked_auto_executable_is_not_eligible():
    action = _action(actuation_risk="config", auto_executable=False)
    assert is_eligible_for_automated_commit(action) is False


def test_missing_actuation_risk_defaults_to_not_eligible():
    action = _action(actuation_risk=None, auto_executable=True)
    assert is_eligible_for_automated_commit(action) is False


def test_commit_message_format_is_greppable_by_issue_trailer():
    message = format_repair_commit_message(
        code="modbus_adc_disabled_but_present",
        summary="enable modbus-adc and fix serial_port in oqlos.yaml",
    )
    assert message.startswith("fix(modbus_adc_disabled_but_present): enable modbus-adc")
    assert "\nOqlOS-Issue: modbus_adc_disabled_but_present\n" in message


def test_commit_message_includes_co_author_when_given():
    message = format_repair_commit_message(
        code="hw_tic249_sidecar_unreachable",
        summary="restart hw-tic249.service",
        co_author="Claude Sonnet 5 <noreply@anthropic.com>",
    )
    assert "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>" in message
