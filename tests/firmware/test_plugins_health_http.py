"""HTTP status semantics for /api/v1/plugins/{id}/health."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from oqlos.api import plugins
from oqlos.errors import OqlosError
from oqlos.errors.fastapi_integration import install_oqlos_error_handler
from oqlos.hardware.plugins.base import PluginHealth, PluginStatus


def test_plugin_health_returns_503_when_plugin_reports_error(monkeypatch):
    health = PluginHealth(
        status=PluginStatus.ERROR,
        message="Modbus RTU read_coils timed out",
        compatible=False,
    )

    async def _check(_plugin_id: str):
        return health

    monkeypatch.setattr(plugins.PluginRegistry, "health_check", _check)

    with pytest.raises(OqlosError) as caught:
        asyncio.run(plugins.get_plugin_health("modbus-io"))

    assert caught.value.status_code == 503
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "hw_modbus_no_response"
    assert caught.value.detail["reason"] == "health-not-ok"
    assert caught.value.message == (
        "A required hardware plugin or sensor path is not available for real operation"
    )
    assert "health" not in caught.value.detail


def test_plugin_health_returns_503_when_no_active_instance(monkeypatch):
    async def _check(_plugin_id: str):
        return None

    monkeypatch.setattr(plugins.PluginRegistry, "health_check", _check)

    with pytest.raises(OqlosError) as caught:
        asyncio.run(plugins.get_plugin_health("modbus-io"))

    assert caught.value.status_code == 503
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "hw_modbus_no_response"
    assert caught.value.detail["reason"] == "instance-unavailable"
    assert caught.value.detail["peripheral_id"] == "modbus-io"
    assert "health" not in caught.value.detail


def test_plugin_health_maps_not_connected_modbus_to_no_response(monkeypatch):
    health = PluginHealth(
        status=PluginStatus.ERROR,
        message="Not connected to modbus",
        compatible=False,
    )

    async def _check(_plugin_id: str):
        return health

    monkeypatch.setattr(plugins.PluginRegistry, "health_check", _check)

    with pytest.raises(OqlosError) as caught:
        asyncio.run(plugins.get_plugin_health("modbus-io"))

    assert caught.value.issue_code == "hw_modbus_no_response"
    assert caught.value.detail["reason"] == "health-not-ok"


def test_plugin_health_returns_200_when_plugin_connected(monkeypatch):
    health = PluginHealth(
        status=PluginStatus.CONNECTED,
        message="Modbus RTU is healthy",
        compatible=True,
    )

    async def _check(_plugin_id: str):
        return health

    monkeypatch.setattr(plugins.PluginRegistry, "health_check", _check)

    response = asyncio.run(plugins.get_plugin_health("modbus-io"))

    assert response.status_code == 200


def test_plugin_health_http_failure_is_canonical_problem_details(monkeypatch):
    async def _check(_plugin_id: str):
        return None

    monkeypatch.setattr(plugins.PluginRegistry, "health_check", _check)
    app = FastAPI()
    install_oqlos_error_handler(app)
    app.include_router(plugins.router)

    response = TestClient(app, raise_server_exceptions=False).get(
        "/api/v1/plugins/modbus-io/health",
        headers={"X-Correlation-ID": "cor-plugin-health-test"},
    )

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["x-correlation-id"] == "cor-plugin-health-test"
    body = response.json()
    assert body["code"] == body["error_code"] == "C2004-HW-0012"
    assert body["correlation_id"] == "cor-plugin-health-test"
    assert body["metadata"]["diagnostics"]["issue_code"] == "hw_modbus_no_response"
    assert body["metadata"]["diagnostics"]["repair"]["id"] == "modbus-physical-check"
    assert "plan: 2" not in body["metadata"]["diagnostics"]["repair"]["hint"]
    context = body["metadata"]["context"]
    assert context["component"] == "plugin-registry"
    assert context["stage"] == "plugin.health"
    assert context["operation_id"] == "plugin.health"
    assert context["upstream_target"] == "hardware-plugin://modbus-io"
    assert context["peripheral_id"] == "modbus-io"
    assert context["issue_code"] == "hw_modbus_no_response"
    assert "plugin_id" not in context


def test_plugin_health_http_failure_does_not_publish_adapter_message(monkeypatch):
    health = PluginHealth(
        status=PluginStatus.ERROR,
        message="token=health-secret at /home/operator/private-device",
        compatible=False,
        details={"password": "details-secret"},
    )

    async def _check(_plugin_id: str):
        return health

    monkeypatch.setattr(plugins.PluginRegistry, "health_check", _check)
    app = FastAPI()
    install_oqlos_error_handler(app)
    app.include_router(plugins.router)

    response = TestClient(app, raise_server_exceptions=False).get(
        "/api/v1/plugins/motor-dri0050/health"
    )

    assert response.status_code == 503
    serialized = json.dumps(response.json())
    assert "health-secret" not in serialized
    assert "private-device" not in serialized
    assert "details-secret" not in serialized
