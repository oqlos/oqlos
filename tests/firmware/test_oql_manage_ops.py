"""manage_ops verb dispatch (unit-level, no MQTT)."""

from __future__ import annotations

import pytest

from oqlos.hardware.transport import manage_ops


@pytest.mark.asyncio
async def test_unknown_verb_raises():
    with pytest.raises(ValueError, match="unknown manage verb"):
        await manage_ops.run_manage_verb("nope", {})


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
    assert calls == [("motor-tic249", {"command": "status", "params": {"x": 1}})]


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
