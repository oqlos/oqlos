"""manage_ops verb dispatch (unit-level, no MQTT)."""

from __future__ import annotations

import pytest

from oqlos.api import hardware_gateway
from oqlos.errors import OqlosError
from oqlos.hardware import power_safety
from oqlos.hardware.plugin_gateway import PluginHardwareGateway
from oqlos.hardware.transport import manage_ops
from oqlos.hardware.usb_diagnostics import decode_throttled


@pytest.mark.asyncio
async def test_unknown_verb_raises():
    with pytest.raises(ValueError, match="unknown manage verb"):
        await manage_ops.run_manage_verb("nope", {})


@pytest.mark.asyncio
async def test_mqtt_manage_actuation_is_blocked_before_adapter(monkeypatch):
    gateway = PluginHardwareGateway(mode="mock")
    gateway.mode = "real"
    adapter_calls: list[tuple[str, dict]] = []

    class _Plugin:
        async def execute_command(self, command, params):
            adapter_calls.append((command, params))
            return {"success": True}

    async def _plugin(_plugin_id):
        return _Plugin()

    async def _active_power():
        return decode_throttled("throttled=0x1")

    monkeypatch.setattr(gateway, "_get_or_connect_plugin", _plugin)
    monkeypatch.setattr(hardware_gateway, "_gateway", gateway)
    monkeypatch.setattr(power_safety, "sample_power_telemetry", _active_power)

    with pytest.raises(OqlosError) as caught:
        await manage_ops.run_manage_verb(
            "valve", {"valve_id": "valve-1", "value": True}
        )

    assert caught.value.public_code == "C2004-HW-0014"
    assert adapter_calls == []


@pytest.mark.asyncio
async def test_mqtt_manage_stop_and_deenergize_bypass_power_gate(monkeypatch):
    gateway = PluginHardwareGateway(mode="mock")
    gateway.mode = "real"
    gateway._init_done = True
    adapter_calls: list[tuple[str, dict]] = []

    class _Plugin:
        async def execute_command(self, command, params):
            adapter_calls.append((command, params))
            return {"success": True}

    gateway._plugins["motor-tic249"] = _Plugin()

    async def _unexpected_power():
        raise AssertionError("STOP/deenergize must bypass the power gate")

    monkeypatch.setattr(hardware_gateway, "_gateway", gateway)
    monkeypatch.setattr(power_safety, "sample_power_telemetry", _unexpected_power)

    result = await manage_ops.run_manage_verb("lung-stop")

    assert result == {"ok": True, "status": "stopped"}
    assert adapter_calls == [
        ("stop", {}),
        ("energize", {"enable": False}),
    ]


def test_hardware_facade_exposes_manage_ops_handlers():
    from oqlos.api import hardware as hw

    for name in [
        "hardware_health",
        "hardware_diagnose",
        "hardware_stack_snapshot",
        "hardware_diagnosis_route",
        "hardware_recover_route",
        "rtc_status",
        "rtc_command",
        "TIC249_DEFAULT_TARGET_VELOCITY",
    ]:
        assert hasattr(hw, name), name


@pytest.mark.asyncio
async def test_diagnostic_command_routes_to_plugin_execute(monkeypatch):
    calls: list[tuple[str, dict]] = []

    async def _fake_execute(plugin_id, command):
        calls.append((plugin_id, command))
        return {"success": True, "plugin_id": plugin_id, "echo": command}

    # manage_ops imports oqlos.api.plugins lazily inside the handler.
    monkeypatch.setattr("oqlos.api.plugins.execute_plugin_command", _fake_execute, raising=True)

    result = await manage_ops.run_manage_verb(
        "diagnostic-command",
        {"peripheral_id": "motor-tic249", "command": "status", "args": {"x": 1}},
    )
    assert result["success"] is True
    assert calls == [("motor-tic249", {"command": "status", "params": {}})]


@pytest.mark.asyncio
async def test_diagnostic_command_requires_peripheral_id():
    with pytest.raises(ValueError, match="peripheral_id"):
        await manage_ops.run_manage_verb("diagnostic-command", {"command": "status"})


@pytest.mark.asyncio
async def test_tic249_disable_diagnostic_uses_lung_disable(monkeypatch):
    from oqlos.api import hardware as hw

    calls: list[str] = []

    async def _fake_disable_lung():
        calls.append("disable_lung")
        return {"ok": True, "status": "de-energized"}

    async def _unexpected_execute(*_args, **_kwargs):
        raise AssertionError("motor_disable must not go through plugin execute")

    monkeypatch.setattr(hw, "disable_lung", _fake_disable_lung)
    monkeypatch.setattr("oqlos.api.plugins.execute_plugin_command", _unexpected_execute, raising=True)

    result = await manage_ops.run_manage_verb(
        "diagnostic-command",
        {"peripheral_id": "motor-tic249", "command": "motor_disable", "args": {}},
    )

    assert result == {"ok": True, "status": "de-energized"}
    assert calls == ["disable_lung"]


@pytest.mark.asyncio
async def test_modbus_io_valve_diagnostic_uses_set_valve(monkeypatch):
    from oqlos.api import hardware as hw

    calls: list[tuple[str, bool]] = []

    async def _fake_set_valve(valve_id, value):
        calls.append((valve_id, value))
        return True

    async def _unexpected_execute(*_args, **_kwargs):
        raise AssertionError("valve_on/valve_off must not go through raw plugin execute")

    monkeypatch.setattr(hw, "set_valve", _fake_set_valve)
    monkeypatch.setattr("oqlos.api.plugins.execute_plugin_command", _unexpected_execute, raising=True)

    on = await manage_ops.run_manage_verb(
        "diagnostic-command",
        {"peripheral_id": "modbus-io", "command": "valve_on", "args": {"valve_id": "valve-wc"}},
    )
    off = await manage_ops.run_manage_verb(
        "diagnostic-command",
        {"peripheral_id": "modbus-io", "command": "valve_off", "args": {"valve_id": "valve-wc"}},
    )

    assert on["success"] is True
    assert on["value"] is True
    assert off["success"] is True
    assert off["value"] is False
    assert calls == [("valve-wc", True), ("valve-wc", False)]


@pytest.mark.asyncio
async def test_modbus_io_valve_diagnostic_preserves_set_valve_failure(monkeypatch):
    from oqlos.api import hardware as hw

    async def _fake_set_valve(valve_id, value):
        return {"valve_id": valve_id, "value": value, "ok": False}

    monkeypatch.setattr(hw, "set_valve", _fake_set_valve)

    result = await manage_ops.run_manage_verb(
        "diagnostic-command",
        {"peripheral_id": "modbus-io", "command": "valve_off", "args": {"valve_id": "valve-wc"}},
    )

    assert result["success"] is False
    assert result["ok"] is False
    assert result["result"] == {"valve_id": "valve-wc", "value": False, "ok": False}


@pytest.mark.asyncio
async def test_pump_off_diagnostic_uses_set_pump(monkeypatch):
    calls: list[float] = []

    class _Gateway:
        async def set_pump(self, power_pct: float):
            calls.append(power_pct)
            return {"success": True, "data": {"power_pct": power_pct}}

    monkeypatch.setattr(
        "oqlos.api.hardware_gateway.get_hardware_gateway",
        lambda: _Gateway(),
        raising=True,
    )

    async def _unexpected_execute(*_args, **_kwargs):
        raise AssertionError("pump_off must not go through raw plugin execute")

    monkeypatch.setattr("oqlos.api.plugins.execute_plugin_command", _unexpected_execute, raising=True)

    result = await manage_ops.run_manage_verb(
        "diagnostic-command",
        {"peripheral_id": "motor-dri0050", "command": "pump_off", "args": {}},
    )

    assert result["success"] is True
    assert calls == [0.0]


@pytest.mark.asyncio
async def test_move_relative_diagnostic_maps_to_plugin_move(monkeypatch):
    calls: list[tuple[str, dict]] = []

    async def _fake_execute(plugin_id, command):
        calls.append((plugin_id, command))
        if command["command"] == "status":
            return {"success": True, "data": {"position": 100}}
        return {"success": True, "data": {"position": 120}}

    monkeypatch.setattr("oqlos.api.plugins.execute_plugin_command", _fake_execute, raising=True)

    result = await manage_ops.run_manage_verb(
        "diagnostic-command",
        {
            "peripheral_id": "motor-tic249",
            "command": "move_relative",
            "args": {"direction": "right", "steps": 20, "speed": 100},
        },
    )

    assert result["success"] is True
    assert calls[0] == ("motor-tic249", {"command": "status", "params": {}})
    move_call = calls[1][1]
    assert move_call["command"] == "move"
    assert move_call["params"]["position"] == 120
    assert move_call["params"]["offset"] == 20


def test_diagnostic_command_listed():
    assert "diagnostic-command" in manage_ops.list_manage_verbs()


@pytest.mark.asyncio
async def test_hui_manage_verbs_route_to_hui_handlers(monkeypatch):
    from oqlos.api import hardware as hw

    calls: list[tuple[str, object]] = []

    async def _fake_actions():
        calls.append(("actions", None))
        return {"ok": True, "hold_keys": ["head-inflate"]}

    async def _fake_hold_start(key):
        calls.append(("hold-start", key))
        return {"ok": True, "key": key}

    async def _fake_hold_stop(key):
        calls.append(("hold-stop", key))
        return {"ok": True, "key": key}

    async def _fake_al_stop():
        calls.append(("al-stop", None))
        return {"ok": True, "command": "al-stop"}

    monkeypatch.setattr(hw, "hui_actions", _fake_actions)
    monkeypatch.setattr(hw, "hui_hold_start", _fake_hold_start)
    monkeypatch.setattr(hw, "hui_hold_stop", _fake_hold_stop)
    monkeypatch.setattr(hw, "hui_al_stop", _fake_al_stop)

    assert (await manage_ops.run_manage_verb("hui-actions"))["ok"] is True
    assert (await manage_ops.run_manage_verb("hui-hold-start", {"key": "head-inflate"}))["ok"] is True
    assert (await manage_ops.run_manage_verb("hui-hold-stop", {"key": "head-inflate"}))["ok"] is True
    assert (await manage_ops.run_manage_verb("hui-al-stop"))["ok"] is True

    assert calls == [
        ("actions", None),
        ("hold-start", "head-inflate"),
        ("hold-stop", "head-inflate"),
        ("al-stop", None),
    ]


def test_hui_manage_verbs_listed():
    verbs = set(manage_ops.list_manage_verbs())
    assert {
        "hui-actions",
        "hui-shutdown",
        "hui-hold-start",
        "hui-hold-stop",
        "hui-al-start",
        "hui-al-stop",
    } <= verbs
