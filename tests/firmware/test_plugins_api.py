"""Tests for hardware plugin REST API response semantics."""

from __future__ import annotations

import asyncio

import pytest

from oqlos.api import plugins
from oqlos.errors import OqlosError


class FakePlugin:
    async def execute_command(self, command, params):
        return {
            "success": False,
            "error": "steps must be an integer",
            "error_code": "C2004-DATA-0002",
            "status_code": 422,
            "correlation_id": "cor-sidecar",
            "command": command,
            "params": params,
        }


class InvalidPlugin:
    async def execute_command(self, command, params):
        return "invalid"


def test_modbus_timeout_health_uses_standard_hardware_error():
    with pytest.raises(OqlosError) as caught:
        plugins._raise_unhealthy_plugin(
            "modbus-io",
            {"status": "error", "message": "Modbus request timed out"},
        )

    assert caught.value.issue_code == "hw_modbus_no_response"
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.status_code == 503


def test_execute_plugin_command_returns_operational_failure_payload(monkeypatch):
    monkeypatch.setattr(plugins.PluginRegistry, "get_instance", lambda plugin_id: FakePlugin())

    response = asyncio.run(
        plugins.execute_plugin_command(
            "motor-dri0050",
            {"command": "status", "params": {"sample": True}},
        )
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["x-correlation-id"] == "cor-sidecar"
    assert response.body
    import json

    payload = json.loads(response.body)
    assert payload == {
        "success": False,
        "error": "steps must be an integer",
        "error_code": "C2004-DATA-0002",
        "status_code": 422,
        "correlation_id": "cor-sidecar",
        "command": "status",
        "params": {"sample": True},
    }


def test_execute_requires_active_plugin_as_hardware_error(monkeypatch):
    async def missing(_plugin_id):
        return None

    monkeypatch.setattr(plugins, "_resolve_plugin_instance", missing)

    with pytest.raises(OqlosError) as caught:
        asyncio.run(plugins.execute_plugin_command("motor-dri0050", {"command": "status"}))

    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.status_code == 503


def test_invalid_plugin_response_is_canonical_hardware_error(monkeypatch):
    monkeypatch.setattr(plugins.PluginRegistry, "get_instance", lambda _plugin_id: InvalidPlugin())

    with pytest.raises(OqlosError) as caught:
        asyncio.run(plugins.execute_plugin_command("motor-dri0050", {"command": "status"}))

    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.status_code == 503
    assert caught.value.detail["result_type"] == "str"
