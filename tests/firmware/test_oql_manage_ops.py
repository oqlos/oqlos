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


def test_diagnostic_command_listed():
    assert "diagnostic-command" in manage_ops.list_manage_verbs()
