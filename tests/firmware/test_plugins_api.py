"""Tests for hardware plugin REST API response semantics."""

from __future__ import annotations

import asyncio

from oqlos.api import plugins


class FakePlugin:
    async def execute_command(self, command, params):
        return {"success": False, "error": "All connection attempts failed", "command": command, "params": params}


def test_execute_plugin_command_returns_operational_failure_payload(monkeypatch):
    monkeypatch.setattr(plugins.PluginRegistry, "get_instance", lambda plugin_id: FakePlugin())

    payload = asyncio.run(
        plugins.execute_plugin_command(
            "motor-dri0050",
            {"command": "status", "params": {"sample": True}},
        )
    )

    assert payload == {
        "success": False,
        "error": "All connection attempts failed",
        "command": "status",
        "params": {"sample": True},
    }
