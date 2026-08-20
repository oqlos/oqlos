"""Tests for deterministic hardware plugin initialization."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from oqlos.hardware.plugin_gateway import PluginHardwareGateway
from oqlos.hardware.plugins import PluginConfig


def test_health_awaits_ensure_initialized_before_checks(monkeypatch) -> None:
    gateway = PluginHardwareGateway(mode="mock")
    gateway.mode = "real"
    gateway._init_done = True
    calls: list[str] = []

    async def _track_ensure() -> None:
        calls.append("ensure")

    async def _fake_health_all(*, timeout=None):
        calls.append("health_all")
        return {}

    monkeypatch.setattr(gateway, "ensure_initialized", _track_ensure)
    monkeypatch.setattr(
        "oqlos.hardware.plugins.registry.PluginRegistry.health_check_all",
        AsyncMock(side_effect=_fake_health_all),
    )
    gateway._plugin_configs = {}

    asyncio.run(gateway.health())

    assert calls == ["ensure", "health_all"]


def test_initialize_plugins_records_summary(monkeypatch) -> None:
    gateway = PluginHardwareGateway(mode="mock")
    gateway.mode = "real"
    gateway._init_done = False
    gateway._plugin_configs = {
        "modbus-io": PluginConfig(
            plugin_id="modbus-io",
            enabled=True,
            connection_type="modbus-rtu",
            connection_params={
                "serial_port": "/dev/ttyTEST",
                "baudrate": 4800,
                "device_id": 2,
            },
        ),
    }

    class _FakeModbus:
        async def connect(self) -> bool:
            return True

    async def _fake_create(plugin_id: str, config: PluginConfig):
        return _FakeModbus()

    monkeypatch.setattr(
        "oqlos.hardware.plugins.registry.PluginRegistry.create_instance",
        _fake_create,
    )

    asyncio.run(gateway._initialize_plugins())

    assert gateway._init_done is True
    assert "modbus-io" in gateway.last_init_summary.get("connected", [])
    assert gateway._plugins.get("modbus-io") is not None


def test_apply_modbus_user_settings_reconnects_selected_plugin(monkeypatch) -> None:
    gateway = PluginHardwareGateway(mode="mock")
    gateway.mode = "real"
    gateway._init_done = True
    gateway._plugin_configs = {
        "modbus-io": PluginConfig(
            plugin_id="modbus-io",
            enabled=True,
            connection_type="modbus-rtu",
            connection_params={
                "serial_port": "/dev/ttyACM0",
                "baudrate": 9600,
                "device_id": 1,
            },
        ),
    }
    gateway._plugins["modbus-io"] = object()
    monkeypatch.setattr(
        gateway,
        "_apply_persisted_modbus_settings",
        lambda: {
            "modbus-io": {
                "serial_port": "/dev/ttyUSB0",
                "baudrate": 4800,
                "parity": "N",
                "device_id": 2,
            }
        },
    )
    disconnect = AsyncMock(return_value=True)
    connect = AsyncMock(return_value=True)
    instance = object()
    monkeypatch.setattr(
        "oqlos.hardware.plugins.registry.PluginRegistry.disconnect_plugin",
        disconnect,
    )
    monkeypatch.setattr(
        "oqlos.hardware.plugins.registry.PluginRegistry.connect_plugin",
        connect,
    )
    monkeypatch.setattr(
        "oqlos.hardware.plugins.registry.PluginRegistry.get_instance",
        lambda _plugin_id: instance,
    )

    result = asyncio.run(gateway.apply_modbus_user_settings({"modbus-io"}))

    assert result["ok"] is True
    assert result["actuation"] is False
    disconnect.assert_awaited_once_with("modbus-io")
    connect.assert_awaited_once()
    assert gateway._plugins["modbus-io"] is instance


def test_stop_lung_releases_coils_for_deenergized_idle(monkeypatch) -> None:
    monkeypatch.setattr(
        "oqlos.hardware.hui_lung_recipe.get_hui_lung_stop_at_limit",
        lambda *, fallback: fallback,
    )
    gateway = PluginHardwareGateway(mode="mock")
    gateway.mode = "real"
    gateway._motor2_runtime = {
        "idleState": "deenergized",
        "deenergizeOnStop": True,
        "stopAtLimit": True,
    }
    calls: list[tuple[str, dict]] = []

    async def _execute(command: str, params: dict, **_kwargs) -> bool:
        calls.append((command, params))
        return True

    monkeypatch.setattr(gateway, "_execute_lung_bool_command", _execute)
    assert asyncio.run(gateway.stop_lung()) is True
    assert calls == [("stop", {"stop_mode": "reach_limit"})]


def test_stop_lung_immediate_stop_still_deenergizes_when_configured(monkeypatch) -> None:
    monkeypatch.setattr(
        "oqlos.hardware.hui_lung_recipe.get_hui_lung_stop_at_limit",
        lambda *, fallback: fallback,
    )
    gateway = PluginHardwareGateway(mode="mock")
    gateway.mode = "real"
    gateway._motor2_runtime = {
        "idleState": "deenergized",
        "deenergizeOnStop": True,
        "stopAtLimit": False,
    }
    calls: list[tuple[str, dict]] = []

    async def _execute(command: str, params: dict, **_kwargs) -> bool:
        calls.append((command, params))
        return True

    monkeypatch.setattr(gateway, "_execute_lung_bool_command", _execute)
    assert asyncio.run(gateway.stop_lung()) is True
    assert calls == [("stop", {}), ("energize", {"enable": False})]


def test_stop_lung_oql_profile_overrides_yaml_reach_limit(monkeypatch) -> None:
    monkeypatch.setattr(
        "oqlos.hardware.hui_lung_recipe.get_hui_lung_stop_at_limit",
        lambda *, fallback: False,
    )
    gateway = PluginHardwareGateway(mode="mock")
    gateway.mode = "real"
    gateway._motor2_runtime = {
        "idleState": "deenergized",
        "deenergizeOnStop": True,
        "stopAtLimit": True,
    }
    calls: list[tuple[str, dict]] = []

    async def _execute(command: str, params: dict, **_kwargs) -> bool:
        calls.append((command, params))
        return True

    monkeypatch.setattr(gateway, "_execute_lung_bool_command", _execute)
    assert asyncio.run(gateway.stop_lung()) is True
    assert calls == [("stop", {}), ("energize", {"enable": False})]


def test_stop_lung_can_preserve_explicit_holding_current(monkeypatch) -> None:
    monkeypatch.setattr(
        "oqlos.hardware.hui_lung_recipe.get_hui_lung_stop_at_limit",
        lambda *, fallback: fallback,
    )
    gateway = PluginHardwareGateway(mode="mock")
    gateway.mode = "real"
    gateway._motor2_runtime = {"idleState": "holding", "deenergizeOnStop": False}
    calls: list[tuple[str, dict]] = []

    async def _execute(command: str, params: dict, **_kwargs) -> bool:
        calls.append((command, params))
        return True

    monkeypatch.setattr(gateway, "_execute_lung_bool_command", _execute)
    assert asyncio.run(gateway.stop_lung()) is True
    assert calls == [("stop", {"stop_mode": "reach_limit"})]


def test_startup_idle_policy_deenergizes_tic249(monkeypatch) -> None:
    gateway = PluginHardwareGateway(mode="mock")
    gateway._motor2_runtime = {"idleState": "deenergized", "deenergizeOnStartup": True}
    disable = AsyncMock(return_value=True)
    monkeypatch.setattr(gateway, "disable_lung", disable)

    assert asyncio.run(gateway.enforce_motor2_startup_idle_state()) is True
    disable.assert_awaited_once_with()


def test_suspended_plugin_cannot_reconnect_until_resumed(monkeypatch) -> None:
    gateway = PluginHardwareGateway(mode="mock")
    gateway.mode = "real"
    gateway._init_done = True
    gateway._plugin_configs = {
        "modbus-io": PluginConfig(
            plugin_id="modbus-io",
            enabled=True,
            connection_type="modbus-rtu",
            connection_params={"serial_port": "/dev/ttyACM0", "baudrate": 4800},
        ),
    }
    gateway._plugins["modbus-io"] = object()
    disconnect = AsyncMock(return_value=True)
    connect = AsyncMock(return_value=True)
    instance = object()
    monkeypatch.setattr(
        "oqlos.hardware.plugins.registry.PluginRegistry.disconnect_plugin",
        disconnect,
    )
    monkeypatch.setattr(
        "oqlos.hardware.plugins.registry.PluginRegistry.connect_plugin",
        connect,
    )
    monkeypatch.setattr(
        "oqlos.hardware.plugins.registry.PluginRegistry.get_instance",
        lambda _plugin_id: instance,
    )
    monkeypatch.setattr(
        gateway,
        "_apply_persisted_modbus_settings",
        lambda: {"modbus-io": {"baudrate": 4800}},
    )

    async def _exercise() -> tuple[object | None, dict[str, object]]:
        suspended = await gateway.suspend_plugins({"modbus-io"})
        assert suspended == {"modbus-io"}
        blocked = await gateway._get_or_connect_plugin("modbus-io")
        resumed = await gateway.resume_modbus_plugins({"modbus-io"})
        return blocked, resumed

    blocked, resumed = asyncio.run(_exercise())

    assert blocked is None
    assert resumed["ok"] is True
    assert resumed["actuation"] is False
    assert "modbus-io" not in gateway._suspended_plugins
    connect.assert_awaited_once()
    assert gateway._plugins["modbus-io"] is instance


def test_plugin_readiness_can_fail_fast_without_reconnect(monkeypatch) -> None:
    gateway = PluginHardwareGateway(mode="mock")
    gateway.mode = "real"
    gateway._init_done = True
    gateway._plugin_configs = {
        "modbus-io": PluginConfig(
            plugin_id="modbus-io",
            enabled=True,
            connection_type="modbus-rtu",
            connection_params={"serial_port": "/dev/ttyACM0", "baudrate": 4800},
        ),
    }
    reconnect = AsyncMock()
    monkeypatch.setattr(gateway, "_get_or_connect_plugin", reconnect)

    result = asyncio.run(gateway.plugin_readiness("modbus-io", reconnect=False))

    assert result == {
        "ok": False,
        "plugin_id": "modbus-io",
        "status": "unavailable",
        "message": "Plugin modbus-io is not connected",
    }
    reconnect.assert_not_awaited()
