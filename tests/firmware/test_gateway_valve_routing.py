"""The gateway must drive valves through the configured output module."""

from __future__ import annotations

from typing import Any

import pytest

from oqlos.hardware import plugin_gateway as gateway_module
from oqlos.hardware.plugin_gateway import PluginHardwareGateway
from oqlos.hardware.plugins import PluginConfig
from oqlos.hardware.valve_controller import M5_VALVE_CONTROLLER, MODBUS_VALVE_CONTROLLER


class _FakePlugin:
    def __init__(self, plugin_id: str, *, succeeds: bool = True) -> None:
        self.plugin_id = plugin_id
        self.succeeds = succeeds
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def execute_command(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((command, params))
        if self.succeeds:
            return {"success": True, "data": {"plugin_id": self.plugin_id}}
        return {"success": False, "error": f"{self.plugin_id} unavailable"}


@pytest.fixture()
def gateway(monkeypatch: pytest.MonkeyPatch) -> PluginHardwareGateway:
    instance = PluginHardwareGateway(mode="mock")
    # Mock mode short-circuits actuation; force the real routing path.
    monkeypatch.setattr(type(instance), "is_real", property(lambda self: True))

    async def _no_power_gate(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(gateway_module, "ensure_power_safe", _no_power_gate)
    return instance


def _enable(gateway: PluginHardwareGateway, **enabled: bool) -> None:
    gateway._plugin_configs = {
        plugin_id: PluginConfig(plugin_id=plugin_id, enabled=state)
        for plugin_id, state in enabled.items()
    }


def _install(
    gateway: PluginHardwareGateway,
    monkeypatch: pytest.MonkeyPatch,
    plugins: dict[str, _FakePlugin],
) -> None:
    async def _get_or_connect(plugin_id: str) -> Any:
        return plugins.get(plugin_id)

    monkeypatch.setattr(gateway, "_get_or_connect_plugin", _get_or_connect)


@pytest.mark.asyncio
async def test_valves_use_modbus_io_when_m5_is_disabled(
    gateway: PluginHardwareGateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable(gateway, **{MODBUS_VALVE_CONTROLLER: True, M5_VALVE_CONTROLLER: False})
    plugins = {plugin_id: _FakePlugin(plugin_id) for plugin_id in (MODBUS_VALVE_CONTROLLER, M5_VALVE_CONTROLLER)}
    _install(gateway, monkeypatch, plugins)

    assert await gateway.set_valve("valve-nc", True) is True
    assert plugins[MODBUS_VALVE_CONTROLLER].calls == [
        ("set_valve", {"valve_id": "valve-nc", "value": True})
    ]
    assert plugins[M5_VALVE_CONTROLLER].calls == []


@pytest.mark.asyncio
async def test_enabling_m5_takes_over_the_valves(
    gateway: PluginHardwareGateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable(gateway, **{MODBUS_VALVE_CONTROLLER: True, M5_VALVE_CONTROLLER: True})
    plugins = {plugin_id: _FakePlugin(plugin_id) for plugin_id in (MODBUS_VALVE_CONTROLLER, M5_VALVE_CONTROLLER)}
    _install(gateway, monkeypatch, plugins)

    assert await gateway.set_valve("valve-nc", True) is True
    assert plugins[M5_VALVE_CONTROLLER].calls == [
        ("set_valve", {"valve_id": "valve-nc", "value": True})
    ]
    assert plugins[MODBUS_VALVE_CONTROLLER].calls == []


@pytest.mark.asyncio
async def test_failed_primary_controller_falls_back(
    gateway: PluginHardwareGateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable(gateway, **{MODBUS_VALVE_CONTROLLER: True, M5_VALVE_CONTROLLER: True})
    plugins = {
        M5_VALVE_CONTROLLER: _FakePlugin(M5_VALVE_CONTROLLER, succeeds=False),
        MODBUS_VALVE_CONTROLLER: _FakePlugin(MODBUS_VALVE_CONTROLLER),
    }
    _install(gateway, monkeypatch, plugins)

    assert await gateway.set_valve("valve-nc", True) is True
    assert plugins[MODBUS_VALVE_CONTROLLER].calls


@pytest.mark.asyncio
async def test_set_valve_fails_when_no_controller_is_enabled(
    gateway: PluginHardwareGateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable(gateway, **{MODBUS_VALVE_CONTROLLER: False, M5_VALVE_CONTROLLER: False})
    _install(gateway, monkeypatch, {})

    assert await gateway.set_valve("valve-nc", True) is False


@pytest.mark.asyncio
async def test_safe_off_reaches_every_enabled_controller(
    gateway: PluginHardwareGateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable(gateway, **{MODBUS_VALVE_CONTROLLER: True, M5_VALVE_CONTROLLER: True})
    plugins = {plugin_id: _FakePlugin(plugin_id) for plugin_id in (MODBUS_VALVE_CONTROLLER, M5_VALVE_CONTROLLER)}
    _install(gateway, monkeypatch, plugins)
    gateway._plugins.update(plugins)

    result = await gateway.all_valves_off()

    assert result["success"] is True
    # A stand mid-migration can have valves on both modules; neither may stay hot.
    assert plugins[M5_VALVE_CONTROLLER].calls == [("all_outputs_off", {})]
    assert plugins[MODBUS_VALVE_CONTROLLER].calls == [("all_outputs_off", {})]
    assert {entry["plugin_id"] for entry in result["controllers"]} == {
        M5_VALVE_CONTROLLER,
        MODBUS_VALVE_CONTROLLER,
    }


@pytest.mark.asyncio
async def test_safe_off_does_not_reconnect_disconnected_fallback(
    gateway: PluginHardwareGateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable(gateway, **{MODBUS_VALVE_CONTROLLER: True, M5_VALVE_CONTROLLER: True})
    m5 = _FakePlugin(M5_VALVE_CONTROLLER)
    gateway._plugins[M5_VALVE_CONTROLLER] = m5
    reconnects: list[str] = []

    async def _unexpected_reconnect(plugin_id: str) -> Any:
        reconnects.append(plugin_id)
        return None

    monkeypatch.setattr(gateway, "_get_or_connect_plugin", _unexpected_reconnect)

    result = await gateway.all_valves_off()

    assert result["success"] is True
    assert m5.calls == [("all_outputs_off", {})]
    assert reconnects == []


@pytest.mark.asyncio
async def test_dead_fallback_is_probed_once_not_once_per_valve(
    gateway: PluginHardwareGateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Safe-off walks eleven valves; a silent RS485 adapter used to be re-opened
    for each one and blew the HUI action budget."""
    _enable(gateway, **{MODBUS_VALVE_CONTROLLER: True, M5_VALVE_CONTROLLER: True})
    m5 = _FakePlugin(M5_VALVE_CONTROLLER, succeeds=False)
    gateway._plugins[M5_VALVE_CONTROLLER] = m5
    attempts: list[str] = []

    async def _dead_connect(plugin_id: str) -> Any:
        attempts.append(plugin_id)
        return None

    monkeypatch.setattr(gateway, "_get_or_connect_plugin", _dead_connect)

    for valve_id in ("valve-1", "valve-2", "valve-3"):
        assert await gateway.set_valve(valve_id, False) is False

    # Failover still runs — the fallback is tried, just not re-probed per valve.
    assert attempts == [MODBUS_VALVE_CONTROLLER]
    assert len(m5.calls) == 3


@pytest.mark.asyncio
async def test_recovered_fallback_is_used_again_after_the_cooldown(
    gateway: PluginHardwareGateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable(gateway, **{MODBUS_VALVE_CONTROLLER: True, M5_VALVE_CONTROLLER: True})
    gateway._plugins[M5_VALVE_CONTROLLER] = _FakePlugin(M5_VALVE_CONTROLLER, succeeds=False)
    modbus = _FakePlugin(MODBUS_VALVE_CONTROLLER)
    available: list[Any] = [None]

    async def _connect(plugin_id: str) -> Any:
        return available[0] if plugin_id == MODBUS_VALVE_CONTROLLER else None

    monkeypatch.setattr(gateway, "_get_or_connect_plugin", _connect)
    assert await gateway.set_valve("valve-1", False) is False

    available[0] = modbus
    gateway._valve_reconnect_blocked_until.clear()

    assert await gateway.set_valve("valve-2", False) is True
    assert modbus.calls == [("set_valve", {"valve_id": "valve-2", "value": False})]
