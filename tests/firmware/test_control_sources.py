import asyncio
from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from oqlos.api import control_source_routes as api
from oqlos.hardware import control_sources as store
from oqlos.hardware.plugins import stacknet_motor
from oqlos.hardware.plugins.base import PluginConfig
from oqlos.hardware.plugins.motor import MotorPlugin
from oqlos.hardware.valve_controller import valve_controller_preference


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("OQLOS_CONTROL_SOURCES_PATH", str(tmp_path / "sources.json"))
    monkeypatch.setattr(store, "LOCK", asyncio.Lock())


@pytest.mark.asyncio
async def test_settings_persist_and_detect_conflicts(monkeypatch):
    idle = AsyncMock()
    monkeypatch.setattr(api, "ensure_idle", idle)
    initial = await api.get_sources()
    selected = {**initial["sources"], "pump": "stacknet", "valves": "boardnet"}
    saved = await api.update_sources(api.ControlSourceUpdate(sources=selected, revision=initial["revision"]))
    assert (await api.get_sources()) == saved
    assert saved["sources"] == selected
    assert saved["revision"] != initial["revision"]
    assert idle.await_count == 2
    with pytest.raises(HTTPException) as error:
        await api.update_sources(api.ControlSourceUpdate(sources=store.DEFAULTS, revision=initial["revision"]))
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_active_device_prevents_all_changes(monkeypatch):
    monkeypatch.setattr(api, "ensure_idle", AsyncMock(side_effect=HTTPException(409, "active")))
    initial = await api.get_sources()
    with pytest.raises(HTTPException):
        await api.update_sources(api.ControlSourceUpdate(
            sources={**store.DEFAULTS, "stepper": "stacknet"}, revision=initial["revision"]))
    assert await api.get_sources() == initial
    assert not store.config_path().exists()


@pytest.mark.parametrize("sources", [{}, {**store.DEFAULTS, "extra": "boardnet"}, {**store.DEFAULTS, "pump": "auto"}])
@pytest.mark.asyncio
async def test_invalid_selection_rejected(sources):
    with pytest.raises(HTTPException) as error:
        await api.update_sources(api.ControlSourceUpdate(sources=sources, revision="anything"))
    assert error.value.status_code == 422


def test_explicit_valve_selection_has_no_automatic_fallback(monkeypatch):
    monkeypatch.setenv("OQLOS_VALVE_CONTROLLER", "io-m5-4in8out")
    store.save({**store.DEFAULTS, "valves": "boardnet"})
    assert valve_controller_preference() == ["modbus-io"]
    store.save({**store.DEFAULTS, "valves": "stacknet"})
    assert valve_controller_preference() == ["io-m5-4in8out"]


@pytest.mark.asyncio
async def test_motor_routes_every_command_and_can_return_to_boardnet(monkeypatch):
    plugin = MotorPlugin(PluginConfig(plugin_id="motor-dri0050", connection_type="http", connection_params={"base_url": "http://localhost:8203"}))
    plugin._execute_boardnet_command = AsyncMock(return_value={"success": True, "node": "boardnet"})
    remote = AsyncMock(return_value={"success": True, "node": "stacknet"})
    monkeypatch.setattr(stacknet_motor, "execute", remote)
    assert (await plugin.execute_command("stop", {}))["node"] == "boardnet"
    store.save({**store.DEFAULTS, "pump": "stacknet"})
    assert (await plugin.execute_command("stop", {}))["node"] == "stacknet"
    store.save(store.DEFAULTS)
    assert (await plugin.execute_command("stop", {}))["node"] == "boardnet"
    assert plugin._execute_boardnet_command.await_count == 2
    remote.assert_awaited_once_with("pump", "stop", {})


@pytest.mark.asyncio
async def test_corrupt_settings_do_not_fall_back_to_boardnet():
    store.config_path().write_text("broken")
    plugin = MotorPlugin(PluginConfig(plugin_id="motor-dri0050", connection_type="http"))
    plugin._execute_boardnet_command = AsyncMock()
    assert (await plugin.execute_command("set_speed", {"power_pct": 50}))["success"] is False
    plugin._execute_boardnet_command.assert_not_awaited()


@pytest.mark.asyncio
async def test_stacknet_pwm_scaling_and_stop(monkeypatch):
    request = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(stacknet_motor, "request", request)
    assert (await stacknet_motor.execute("pump", "set_speed", {"power_pct": 100}))["success"]
    assert request.await_args_list[0].args == ("pump", {"action": "set_duty", "duty_raw": 255})
    assert request.await_args_list[1].args == ("pump", {"action": "enable"})
    request.reset_mock()
    await stacknet_motor.execute("pump", "set_speed", {"power_pct": 0})
    request.assert_awaited_once_with("pump", {"action": "stop"})


@pytest.mark.asyncio
async def test_stacknet_stepper_stop_and_unsupported_cycles(monkeypatch):
    request = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(stacknet_motor, "request", request)
    assert (await stacknet_motor.execute("stepper", "stop", {}))["success"]
    assert [call.args[1]["action"] for call in request.await_args_list] == ["halt", "deenergize"]
    request.reset_mock()
    result = await stacknet_motor.execute("stepper", "reciprocate", {"steps": 500})
    assert result["success"] is False
    assert "BoardNet" in result["error"]
    request.assert_not_awaited()


@pytest.mark.parametrize("power", [-1, 101, float("nan"), True])
@pytest.mark.asyncio
async def test_invalid_pump_power_never_writes(monkeypatch, power):
    request = AsyncMock()
    monkeypatch.setattr(stacknet_motor, "request", request)
    assert (await stacknet_motor.execute("pump", "set_speed", {"power_pct": power}))["success"] is False
    request.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_credentials_prevent_stacknet_writes(monkeypatch):
    monkeypatch.delenv("STACKNET_OQL_TOKEN", raising=False)
    with pytest.raises(ValueError, match="poświadczeń"):
        await stacknet_motor.request("pump", {"action": "enable"})


@pytest.mark.parametrize("device,data,allowed", [
    ("pump", {"enabled": False, "duty": 0, "duty_raw": 0}, True),
    ("pump", {"enabled": False}, False),
    ("pump", {"enabled": True, "duty_raw": 0}, False),
    ("pump", {"enabled": False, "power_pct": 0, "duty_raw": 100}, False),
    ("stepper", {"energized": False, "velocity": 0}, True),
    ("stepper", {"energized": False, "velocity": 100}, False),
    ("stepper", {"energized": False, "reciprocating_active": True}, False),
    ("stepper", {}, False),
])
@pytest.mark.asyncio
async def test_switch_checks_real_boardnet_status(monkeypatch, device, data, allowed):
    import httpx
    from oqlos.api import hardware_gateway
    response = httpx.Response(200, json=data, request=httpx.Request("GET", "http://boardnet/api/status"))
    plugin = SimpleNamespace(
        config=SimpleNamespace(connection_type="http"),
        _client=SimpleNamespace(get=AsyncMock(return_value=response)),
        _base_url="http://boardnet",
    )
    gateway = SimpleNamespace(is_real=True, _get_or_connect_plugin=AsyncMock(return_value=plugin))
    monkeypatch.setattr(hardware_gateway, "get_hardware_gateway", lambda: gateway)
    if allowed:
        await api.ensure_idle(device, {"boardnet"})
    else:
        with pytest.raises(HTTPException):
            await api.ensure_idle(device, {"boardnet"})


@pytest.mark.asyncio
async def test_explicit_boardnet_disables_stacknet_exact_replace_but_keeps_emergency_off(monkeypatch):
    from oqlos.hardware import plugin_gateway as module
    gateway = module.PluginHardwareGateway(mode="mock")
    monkeypatch.setattr(type(gateway), "is_real", property(lambda self: True))
    monkeypatch.setattr(module, "ensure_power_safe", AsyncMock())
    gateway._plugin_configs = {key: PluginConfig(plugin_id=key) for key in ("modbus-io", "io-m5-4in8out")}
    gateway._plugins = {key: SimpleNamespace(execute_command=AsyncMock(return_value={"success": True})) for key in gateway._plugin_configs}
    store.save({**store.DEFAULTS, "valves": "boardnet"})
    assert gateway.supports_exact_valve_replace() is False
    assert await gateway.replace_valves_exact(("valve-nc",)) is None
    await gateway.set_valve("valve-nc", True)
    gateway._plugins["io-m5-4in8out"].execute_command.assert_not_awaited()
    await gateway.all_valves_off()
    gateway._plugins["io-m5-4in8out"].execute_command.assert_awaited_once_with("all_outputs_off", {})


@pytest.mark.asyncio
async def test_stacknet_http_transport_uses_device_path_and_existing_auth(monkeypatch):
    import httpx
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={"ok": True})
    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(stacknet_motor.httpx, "AsyncClient", lambda **kwargs: client)
    monkeypatch.setenv("STACKNET_RUNTIME_URL", "http://stacknet.test:8080")
    monkeypatch.setenv("STACKNET_OQL_TOKEN", "test-token")
    await stacknet_motor.request("stepper", {"action": "halt"})
    assert str(calls[0].url) == "http://stacknet.test:8080/api/v1/motor"
    assert calls[0].headers["X-OQL-Token"] == "test-token"
    assert calls[0].method == "POST"


@pytest.mark.asyncio
async def test_corrupt_settings_still_attempt_stop_on_both_motors(monkeypatch):
    store.config_path().write_text("broken")
    plugin = MotorPlugin(PluginConfig(plugin_id="motor-dri0050", connection_type="http"))
    plugin._execute_boardnet_command = AsyncMock(return_value={"success": True})
    remote = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(stacknet_motor, "execute", remote)
    assert (await plugin.execute_command("stop", {}))["success"] is True
    plugin._execute_boardnet_command.assert_awaited_once_with("stop", {"stop_at_limit": False})
    remote.assert_awaited_once_with("pump", "stop", {})


@pytest.mark.asyncio
async def test_returning_to_boardnet_reconnects_modbus_transport():
    plugin = MotorPlugin(PluginConfig(plugin_id="motor-dri0050", connection_type="modbus-rtu"))
    plugin.connect = AsyncMock(return_value=True)
    plugin._execute_boardnet_command = AsyncMock(return_value={"success": True})
    assert (await plugin.execute_command("stop", {}))["success"]
    plugin.connect.assert_awaited_once()
