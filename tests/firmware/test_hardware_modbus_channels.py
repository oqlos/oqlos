from __future__ import annotations

import asyncio

import pytest

from oqlos.api import hardware_modbus_channels as channels
from oqlos.api.hardware_modbus_channels import (
    _adc_channel_rows,
    _io_channel_rows,
    write_modbus_channel_value,
)
from oqlos.errors import OqlosError


def test_io_channel_rows_include_do_di_and_output_modes():
    rows = _io_channel_rows(
        {
            "coils": [True, False],
            "discrete_inputs": [False, True],
            "output_mode_registers": [0, 1],
        }
    )
    ids = [row["id"] for row in rows]
    assert ids[:2] == ["DO1", "DO2"]
    assert ids[2:4] == ["DI1", "DI2"]
    assert ids[4:6] == ["OUT_MODE_1", "OUT_MODE_2"]
    assert rows[0]["write"]["type"] == "coil"
    assert rows[4]["address"] == 0x1000


def test_adc_channel_rows_include_scaled_values():
    rows = _adc_channel_rows(
        {
            "registers": [100, 200],
            "channels": {
                "ai01": {"value": 1.23, "unit": "bar"},
                "ai02": {"value": 4.56, "unit": "bar"},
            },
        },
        read_address=0,
    )
    assert rows[0]["id"] == "AI1"
    assert rows[0]["value"] == 100
    assert rows[0]["value_scaled"] == 1.23
    assert rows[0]["writable"] is False


def test_write_modbus_channel_value_rejects_invalid_role():
    with pytest.raises(OqlosError) as caught:
        asyncio.run(
            write_modbus_channel_value(
                {"module_role": "other", "write_type": "coil", "address": 0, "value": True}
            )
        )
    assert caught.value.public_code == "C2004-DATA-0002"
    assert caught.value.issue_code == "api_modbus_wizard_invalid_request"


def test_write_modbus_channel_value_raises_when_plugin_missing(monkeypatch):
    class _Gateway:
        async def _get_or_connect_plugin(self, plugin_id: str):
            return None

    monkeypatch.setattr(channels, "get_hardware_gateway", lambda: _Gateway())

    with pytest.raises(OqlosError) as caught:
        asyncio.run(
            write_modbus_channel_value(
                {
                    "module_role": "modbus-io",
                    "write_type": "coil",
                    "address": 0,
                    "value": True,
                }
            )
        )
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "hw_modbus_no_response"
