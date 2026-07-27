"""Regression tests for Modbus ADC raw peripheral routes."""

from __future__ import annotations

import asyncio

import pytest

from oqlos.api import hardware_peripherals_routes as peripherals
from oqlos.errors import OqlosError


def test_modbus_adc_raw_raises_typed_error_when_incompatible(monkeypatch):
    class _Gateway:
        async def health(self):
            return {
                "mode": "real",
                "modbus-adc": {"compatible": False, "status": "disabled"},
            }

    monkeypatch.setattr(peripherals, "get_hardware_gateway", lambda: _Gateway())

    with pytest.raises(OqlosError) as caught:
        asyncio.run(peripherals.read_modbus_adc_raw())
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "modbus_adc_not_detected"


def test_modbus_adc_raw_raises_typed_error_when_read_fails(monkeypatch):
    class _Plugin:
        config = type("Cfg", (), {"serial_port": "/dev/null", "baudrate": 4800, "device_id": 1})()

        async def execute_command(self, command: str, params: dict):
            return {"success": False, "error": "read timed out"}

    class _Gateway:
        async def health(self):
            return {
                "mode": "real",
                "modbus-adc": {"compatible": True, "status": "connected"},
            }

        async def _get_or_connect_plugin(self, plugin_id: str):
            assert plugin_id == "modbus-adc"
            return _Plugin()

    monkeypatch.setattr(peripherals, "get_hardware_gateway", lambda: _Gateway())

    with pytest.raises(OqlosError) as caught:
        asyncio.run(peripherals.read_modbus_adc_raw())
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "hw_modbus_no_response"
