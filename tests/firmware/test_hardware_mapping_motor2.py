"""Regression tests for motor2 MAP contract validation."""

from __future__ import annotations

import pytest

from oqlos.api.hardware_mapping_contract import MappingContractError, validate_mapping_contract
from oqlos.api.hardware_mapping_motor2 import validate_motor2_config


def test_validate_motor2_config_accepts_minimal_object():
    issues: list[str] = []
    validate_motor2_config({"peripheralId": "motor-tic249"}, issues)
    assert issues == []


def test_validate_motor2_config_rejects_default_speed_above_max():
    issues: list[str] = []
    validate_motor2_config(
        {"maxStepsPerSecond": 100, "defaultSpeedStepsPerSecond": 200},
        issues,
    )
    assert any("defaultSpeedStepsPerSecond" in issue for issue in issues)


def test_validate_mapping_contract_wraps_motor2_errors():
    with pytest.raises(MappingContractError) as exc:
        validate_mapping_contract({"runtimeConfig": {"motor2": {"strokeSteps": 0}}})
    assert any("strokeSteps" in issue for issue in exc.value.issues)
