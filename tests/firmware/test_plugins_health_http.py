"""HTTP status semantics for /api/v1/plugins/{id}/health."""

from __future__ import annotations

import asyncio

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
    assert caught.value.detail["health"]["status"] == "error"
    assert "timed out" in caught.value.message


def test_plugin_health_returns_503_when_no_active_instance(monkeypatch):
    async def _check(_plugin_id: str):
        return None

    monkeypatch.setattr(plugins.PluginRegistry, "health_check", _check)

    with pytest.raises(OqlosError) as caught:
        asyncio.run(plugins.get_plugin_health("modbus-io"))

    assert caught.value.status_code == 503
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.detail["health"]["compatible"] is False


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
    assert body["metadata"]["diagnostics"]["issue_code"] == (
        "adapter_modbus-io_health_not_ok"
    )
    assert body["metadata"]["context"]["plugin_id"] == "modbus-io"
