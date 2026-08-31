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
                {
                    "module_role": "other",
                    "write_type": "coil",
                    "address": 0,
                    "value": True,
                }
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


def test_read_modbus_profile_channels_raises_when_all_modules_fail(monkeypatch):
    async def _fail_module(role, profile_cfg, health):
        return {"module_role": role, "ok": False, "message": "down", "channels": []}

    class _Gateway:
        async def plugin_readiness(self, plugin_id: str):
            return {"ok": False, "status": "error", "message": f"{plugin_id} down"}

    monkeypatch.setattr(channels, "get_hardware_gateway", lambda: _Gateway())
    monkeypatch.setattr(channels, "_read_module_channels", _fail_module)
    monkeypatch.setattr(
        channels,
        "read_modbus_baud_settings",
        lambda _settings: {
            "profiles": {
                "modbus-io": {
                    "module_roles": ["modbus-io"],
                    "serial_port": "/dev/null",
                },
            }
        },
    )
    monkeypatch.setattr(channels, "MODBUS_PROFILE_IDS", {"modbus-io", "modbus-adc"})

    with pytest.raises(OqlosError) as caught:
        asyncio.run(channels.read_modbus_profile_channels("modbus-io"))
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "hw_modbus_no_response"


def test_read_modbus_profile_channels_returns_disabled_module_without_503(monkeypatch):
    class _Gateway:
        async def plugin_readiness(self, plugin_id: str):
            assert plugin_id == "modbus-adc"
            return {
                "ok": False,
                "status": "disabled",
                "message": "Plugin is disabled in OqlOS configuration",
            }

        async def health(self):
            raise AssertionError(
                "profile channels must not run a full gateway health sweep"
            )

    monkeypatch.setattr(channels, "get_hardware_gateway", lambda: _Gateway())
    monkeypatch.setattr(
        channels,
        "read_modbus_baud_settings",
        lambda _settings: {
            "profiles": {
                "modbus-adc": {
                    "module_roles": ["modbus-adc"],
                    "serial_port": "/dev/null",
                },
            }
        },
    )
    monkeypatch.setattr(channels, "MODBUS_PROFILE_IDS", {"modbus-adc"})

    result = asyncio.run(channels.read_modbus_profile_channels("modbus-adc"))

    assert result["ok"] is False
    assert result["status"] == "disabled"
    assert result["modules"] == [
        {
            "module_role": "modbus-adc",
            "ok": False,
            "status": "disabled",
            "device_id": channels._role_device_id("modbus-adc"),
            "serial_port": None,
            "message": "Plugin is disabled in OqlOS configuration",
            "config_registers": [],
            "channels": [],
        }
    ]
