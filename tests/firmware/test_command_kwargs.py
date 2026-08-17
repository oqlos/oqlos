"""Tests for args/params command kwargs normalization."""

from __future__ import annotations

import pytest

from oqlos.api.command_kwargs import resolve_args_or_params, validate_args_or_params_types
from oqlos.api.hardware_lung import command_payload
from oqlos.errors import OqlosError


def test_resolve_prefers_nonempty_params_by_default():
    assert resolve_args_or_params(
        {"params": {"coil": 3}, "args": {"coil": 1}}
    ) == {"coil": 3}


def test_resolve_falls_back_to_args_when_params_empty():
    assert resolve_args_or_params(
        {"params": {}, "args": {"valve_id": "valve-4"}}
    ) == {"valve_id": "valve-4"}


def test_resolve_prefer_args_for_cqrs_style():
    assert resolve_args_or_params(
        {"params": {"a": 1}, "args": {"b": 2}},
        prefer="args",
    ) == {"b": 2}


def test_validate_rejects_non_object_args():
    with pytest.raises(ValueError, match="args"):
        validate_args_or_params_types({"args": "secret"})


def test_command_payload_accepts_params_alias():
    command, args = command_payload(
        {"command": "sync_to_system", "params": {"force": True}}
    )
    assert command == "sync_to_system"
    assert args == {"force": True}


def test_command_payload_still_rejects_string_args():
    with pytest.raises(OqlosError) as caught:
        command_payload({"command": "set_lpm", "args": "password=hunter2"})
    assert caught.value.detail["field"] == "args"


def test_pick_param_supports_camel_case_aliases():
    from oqlos.api.command_kwargs import pick_param

    assert pick_param({"valveId": "valve-4"}, "valve_id", "valveId") == "valve-4"
    assert pick_param({"powerPct": 40}, "power_pct", "powerPct", default=0) == 40
    assert pick_param({}, "coil", default=None) is None


def test_modbus_set_coil_requires_explicit_coil():
    import asyncio

    from oqlos.hardware.plugins.base import PluginConfig
    from oqlos.hardware.plugins.modbus import ModbusPlugin

    plugin = ModbusPlugin(
        PluginConfig(
            plugin_id="modbus-io",
            enabled=True,
            connection_type="modbus-rtu",
            connection_params={},
        )
    )
    plugin._mode = "rtu"
    plugin._client = object()  # bypass "not connected"
    result = asyncio.run(plugin.execute_command("set_coil", {"value": False}))
    assert result["success"] is False
    assert result["error"] == "coil is required"


def test_modbus_set_valve_accepts_valveId_alias():
    import asyncio

    from oqlos.hardware.plugins.base import PluginConfig
    from oqlos.hardware.plugins.modbus import ModbusPlugin

    class _Plugin(ModbusPlugin):
        async def _execute_set_coil(self, params):
            return {"success": True, "data": dict(params)}

    plugin = _Plugin(
        PluginConfig(
            plugin_id="modbus-io",
            enabled=True,
            connection_type="modbus-rtu",
            connection_params={},
        )
    )
    plugin._mode = "rtu"
    plugin._client = object()
    result = asyncio.run(
        plugin.execute_command("set_valve", {"valveId": "valve-4", "value": True})
    )
    assert result["success"] is True
    assert result["data"]["coil"] == 3
    assert result["data"]["value"] is True



