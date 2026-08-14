"""Guards for the M5Stack 4In8Out valve output plugin."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from oqlos.hardware.plugins import M54In8OutPlugin, PluginConfig, PluginStatus

_DRIVER_SRC = Path(__file__).resolve().parents[3] / "m5-4in8out" / "src"
if _DRIVER_SRC.is_dir() and str(_DRIVER_SRC) not in sys.path:
    sys.path.insert(0, str(_DRIVER_SRC))

pytest.importorskip("m5_4in8out", reason="m5-4in8out driver package not installed")


def _config(**params) -> PluginConfig:
    return PluginConfig(
        plugin_id="io-m5-4in8out",
        connection_type="i2c",
        connection_params={"backend": "mock", "address": 0x45, **params},
        timeout=1.0,
    )


async def _connected() -> M54In8OutPlugin:
    instance = M54In8OutPlugin(_config())
    assert await instance.connect() is True
    return instance


def test_plugin_identity_matches_registry_entry() -> None:
    assert M54In8OutPlugin.PLUGIN_ID == "io-m5-4in8out"
    assert M54In8OutPlugin.SUPPORTED_PROTOCOLS == ["i2c"]


def test_validate_config_rejects_non_i2c_connection() -> None:
    config = _config()
    config.connection_type = "modbus-rtu"

    errors = M54In8OutPlugin(config).validate_config()

    assert any("i2c" in error for error in errors)


@pytest.mark.parametrize(
    "params, fragment",
    [
        ({"backend": "spi"}, "backend"),
        ({"address": 0x80}, "address"),
        ({"bus": -1, "backend": "smbus"}, "bus"),
    ],
)
def test_validate_config_reports_bad_params(params: dict, fragment: str) -> None:
    errors = M54In8OutPlugin(_config(**params)).validate_config()

    assert any(fragment in error for error in errors)


@pytest.mark.asyncio
async def test_connect_probes_module_and_reports_connected() -> None:
    instance = M54In8OutPlugin(_config())

    assert await instance.connect() is True
    assert instance.status is PluginStatus.CONNECTED

    health = await instance.health_check()
    assert health.compatible is True
    assert health.details["backend"] == "mock"


@pytest.mark.asyncio
async def test_set_coil_writes_single_output() -> None:
    plugin = await _connected()
    result = await plugin.execute_command("set_coil", {"coil": 2, "value": True})

    assert result["success"] is True
    snapshot = await plugin.execute_command("read_io_snapshot", {})
    assert snapshot["data"]["coils"][2] is True


@pytest.mark.asyncio
async def test_set_valve_uses_canonical_valve_catalogue() -> None:
    plugin = await _connected()
    result = await plugin.execute_command(
        "set_valve", {"valve_id": "valve-wc", "value": True}
    )

    assert result["success"] is True
    # valve-wc is coil 2 in the shared modbus_io_catalog mapping
    assert result["data"]["coil"] == 2
    # …which is the third physical output, labelled OUT3 on the module.
    assert result["data"]["output"] == 3


@pytest.mark.asyncio
async def test_zero_based_coils_map_to_one_based_module_outputs() -> None:
    plugin = await _connected()

    result = await plugin.execute_command("set_coil", {"coil": 0, "value": True})

    assert result["data"] == {"coil": 0, "value": True, "output": 1}
    # The module numbers outputs OUT1..OUT8 (vendor set_load_state(1..8)); an
    # off-by-one here would silently drive the neighbouring valve.
    snapshot = await plugin.execute_command("read_io_snapshot", {})
    assert snapshot["data"]["coils"][0] is True
    assert snapshot["data"]["coils"][1] is False


@pytest.mark.asyncio
async def test_unknown_valve_id_is_rejected() -> None:
    plugin = await _connected()
    result = await plugin.execute_command("set_valve", {"valve_id": "valve-zz"})

    assert result["success"] is False
    assert "Unknown valve_id" in result["error"]


@pytest.mark.asyncio
async def test_coil_outside_module_range_is_rejected() -> None:
    plugin = await _connected()
    result = await plugin.execute_command("set_coil", {"coil": 9, "value": True})

    assert result["success"] is False
    assert "0..7" in result["error"]


@pytest.mark.asyncio
async def test_all_outputs_off_clears_every_channel() -> None:
    plugin = await _connected()
    for coil in range(8):
        await plugin.execute_command("set_coil", {"coil": coil, "value": True})

    result = await plugin.execute_command("all_outputs_off", {})

    assert result["success"] is True
    assert result["data"]["outputs"] == [False] * 8


@pytest.mark.asyncio
async def test_waveshare_all_outputs_address_is_honoured() -> None:
    plugin = await _connected()
    await plugin.execute_command("set_coil", {"coil": 0, "value": True})

    result = await plugin.execute_command(
        "set_coil", {"coil": M54In8OutPlugin.ALL_OUTPUTS_COIL_ADDRESS, "value": False}
    )

    assert result["success"] is True
    assert result["data"]["all_outputs"] is True
    snapshot = await plugin.execute_command("read_io_snapshot", {})
    assert snapshot["data"]["coils"] == [False] * 8


@pytest.mark.asyncio
async def test_snapshot_keeps_modbus_io_wire_shape() -> None:
    plugin = await _connected()
    snapshot = await plugin.execute_command("read_io_snapshot", {})

    data = snapshot["data"]
    assert len(data["coils"]) == 8
    assert len(data["discrete_inputs"]) == 4
    assert data["address"] == "0x45"


@pytest.mark.asyncio
async def test_disconnected_health_names_expected_i2c_address() -> None:
    instance = M54In8OutPlugin(_config())

    health = await instance.health_check()

    assert health.compatible is False
    assert "0x45" in health.message
    assert "i2cdetect -y 1" in health.message


@pytest.mark.asyncio
async def test_commands_fail_cleanly_when_disconnected() -> None:
    instance = M54In8OutPlugin(_config())

    result = await instance.execute_command("set_coil", {"coil": 0, "value": True})

    assert result == {"success": False, "error": "Not connected to 4In8Out"}


@pytest.mark.asyncio
async def test_unknown_command_is_reported() -> None:
    plugin = await _connected()
    result = await plugin.execute_command("open_sesame", {})

    assert result["success"] is False
    assert "Unknown command" in result["error"]


def test_capabilities_mirror_modbus_io_command_surface() -> None:
    from oqlos.hardware.plugins.modbus import ModbusPlugin

    m5_commands = set(M54In8OutPlugin.get_capabilities()["supported_commands"])
    modbus_commands = set(ModbusPlugin.get_capabilities()["supported_commands"])

    # The gateway drives valves through either plugin, so the valve-facing
    # commands must exist on both.
    assert {"set_coil", "set_valve", "all_outputs_off", "read_io_snapshot"} <= m5_commands
    assert m5_commands <= modbus_commands
