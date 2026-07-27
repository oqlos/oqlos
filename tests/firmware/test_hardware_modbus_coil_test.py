"""Regression tests for guarded Modbus coil-test pulse validation."""

from __future__ import annotations

import asyncio

import pytest

from oqlos.api.hardware_modbus_coil_test import pulse_coil
from oqlos.errors import OqlosError


def test_pulse_coil_rejects_invalid_address():
    with pytest.raises(OqlosError) as caught:
        asyncio.run(pulse_coil({"address": 99, "confirm": "PULSE_DO100", "duration_ms": 300}))
    assert caught.value.public_code == "C2004-DATA-0002"
    assert caught.value.issue_code == "api_modbus_wizard_invalid_request"
    assert "address" in caught.value.message


def test_pulse_coil_rejects_missing_confirmation():
    with pytest.raises(OqlosError) as caught:
        asyncio.run(pulse_coil({"address": 0, "confirm": "NOPE", "duration_ms": 300}))
    assert caught.value.public_code == "C2004-DATA-0002"
    assert "PULSE_DO1" in caught.value.message


def test_pulse_coil_rejects_out_of_range_duration():
    with pytest.raises(OqlosError) as caught:
        asyncio.run(pulse_coil({"address": 0, "confirm": "PULSE_DO1", "duration_ms": 10}))
    assert caught.value.public_code == "C2004-DATA-0002"
    assert "duration_ms" in caught.value.message
