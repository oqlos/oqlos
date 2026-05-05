"""Tests for the DRI0050 motor plugin."""

from __future__ import annotations

import asyncio

from oqlos.hardware.plugins import motor as motor_module
from oqlos.hardware.plugins.base import PluginConfig
from oqlos.hardware.plugins.base import PluginStatus
from oqlos.hardware.plugins.motor import MotorPlugin


class _Response:
    status_code = 200

    def json(self):
        return {"pwm_value": 0, "voltage": 0.0, "current": 0.0}


class _Client:
    async def post(self, url):
        assert url.endswith("/api/stop")
        return _Response()


class _HealthClient:
    async def get(self, url):
        assert url.endswith("/health")
        response = _Response()
        response.json = lambda: {
            "status": "ok",
            "driver": "DRI0050",
            "port": "/dev/ttyUSB0",
            "freq": 1000,
        }
        return response


def test_motor_plugin_http_stop_uses_global_time_import():
    plugin = MotorPlugin(
        PluginConfig(
            plugin_id="motor-dri0050",
            enabled=True,
            connection_type="http",
            connection_params={"base_url": "http://localhost:8203"},
        )
    )
    plugin._client = _Client()

    result = asyncio.run(plugin.execute_command("stop", {}))

    assert result["success"] is True
    assert result["data"]["stopped"] is True
    assert result["data"]["duration_ms"] >= 0


def test_motor_plugin_health_rejects_missing_local_serial_port(monkeypatch):
    monkeypatch.setattr(motor_module.os.path, "exists", lambda path: False)
    plugin = MotorPlugin(
        PluginConfig(
            plugin_id="motor-dri0050",
            enabled=True,
            connection_type="http",
            connection_params={"base_url": "http://localhost:8203"},
        )
    )
    plugin._client = _HealthClient()

    health = asyncio.run(plugin.health_check())

    assert health.status == PluginStatus.ERROR
    assert health.compatible is False
    assert "/dev/ttyUSB0" in health.message
