"""HTTP status semantics for /api/v1/plugins/{id}/health."""

from __future__ import annotations

import asyncio

from oqlos.api import plugins
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

    response = asyncio.run(plugins.get_plugin_health("modbus-io"))

    assert response.status_code == 503
    body = response.body.decode("utf-8")
    assert '"status":"error"' in body.replace(" ", "")
    assert "timed out" in body


def test_plugin_health_returns_503_when_no_active_instance(monkeypatch):
    async def _check(_plugin_id: str):
        return None

    monkeypatch.setattr(plugins.PluginRegistry, "health_check", _check)

    response = asyncio.run(plugins.get_plugin_health("modbus-io"))

    assert response.status_code == 503
    body = response.body.decode("utf-8").replace(" ", "")
    assert '"compatible":false' in body


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
