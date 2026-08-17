"""Tests for hardware plugin REST API response semantics."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from oqlos.api import plugins
from oqlos.errors import OqlosError
from oqlos.errors.fastapi_integration import install_oqlos_error_handler


class FakePlugin:
    async def execute_command(self, command, params):
        return {
            "success": False,
            "error": "steps must be an integer; token=sidecar-secret",
            "error_code": "C2004-DATA-0002",
            "status_code": 503,
            "correlation_id": "cor-sidecar-untrusted",
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


def test_modbus_missing_valve_id_is_request_invalid_not_rs485():
    with pytest.raises(OqlosError) as caught:
        plugins._raise_unhealthy_plugin(
            "modbus-io",
            {"success": False, "error": "valve_id is required"},
            reason="command-rejected",
        )

    assert caught.value.issue_code == "api_diagnostic_command_invalid"
    assert caught.value.public_code == "C2004-DATA-0002"


def test_resolve_execute_params_prefers_params_but_accepts_args():
    assert plugins._resolve_execute_params(
        {"command": "set_valve", "params": {"valve_id": "valve-4"}, "args": {"valve_id": "x"}}
    ) == {"valve_id": "valve-4"}
    assert plugins._resolve_execute_params(
        {"command": "set_valve", "args": {"valve_id": "valve-4", "value": False}}
    ) == {"valve_id": "valve-4", "value": False}
    assert plugins._resolve_execute_params({"command": "status"}) == {}


def test_execute_plugin_command_accepts_args_alias(monkeypatch):
    seen: dict[str, object] = {}

    class RecordingPlugin:
        async def execute_command(self, command, params):
            seen["command"] = command
            seen["params"] = params
            return {"success": True, "data": {"coil": 3, "value": False}}

    async def resolve(_plugin_id):
        return RecordingPlugin()

    monkeypatch.setattr(plugins, "_resolve_plugin_instance", resolve)
    monkeypatch.setattr(
        "oqlos.api.hardware_gateway.try_get_hardware_gateway", lambda: None
    )

    result = asyncio.run(
        plugins.execute_plugin_command(
            "modbus-io",
            {"command": "set_coil", "args": {"coil": 3, "value": False}},
        )
    )

    assert result["success"] is True
    assert seen == {"command": "set_coil", "params": {"coil": 3, "value": False}}


def test_execute_plugin_command_sanitizes_operational_failure_payload(monkeypatch):
    monkeypatch.setattr(plugins.PluginRegistry, "get_instance", lambda plugin_id: FakePlugin())
    app = FastAPI()
    install_oqlos_error_handler(app)
    app.include_router(plugins.router)

    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/v1/plugins/motor-dri0050/execute",
        json={"command": "status", "params": {"token": "request-secret"}},
        headers={"X-Correlation-ID": "cor-plugin-request"},
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["x-correlation-id"] == "cor-plugin-request"
    payload = response.json()
    assert payload["code"] == payload["error_code"] == "C2004-DATA-0002"
    assert payload["detail"] == "One or more fields are invalid"
    assert payload["metadata"]["context"]["reason"] == "command-rejected"
    serialized = json.dumps(payload)
    assert "sidecar-secret" not in serialized
    assert "request-secret" not in serialized
    assert "cor-sidecar-untrusted" not in serialized


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
    assert caught.value.detail["reason"] == "invalid-plugin-response"
    assert "result_type" not in caught.value.detail


def test_resolve_plugin_instance_masks_only_expected_runtime_failures(monkeypatch):
    class ExpectedFailureGateway:
        async def ensure_initialized(self):
            raise RuntimeError("device path /dev/secret is unavailable")

    monkeypatch.setattr(plugins.PluginRegistry, "get_instance", lambda _plugin_id: None)
    import oqlos.api.hardware as hardware

    monkeypatch.setattr(hardware, "_gw", lambda: ExpectedFailureGateway())

    assert asyncio.run(plugins._resolve_plugin_instance("modbus-io")) is None


def test_resolve_plugin_instance_does_not_mask_programming_errors(monkeypatch):
    class BrokenGateway:
        async def ensure_initialized(self):
            raise AttributeError("programming defect")

    monkeypatch.setattr(plugins.PluginRegistry, "get_instance", lambda _plugin_id: None)
    import oqlos.api.hardware as hardware

    monkeypatch.setattr(hardware, "_gw", lambda: BrokenGateway())

    with pytest.raises(AttributeError, match="programming defect"):
        asyncio.run(plugins._resolve_plugin_instance("modbus-io"))
