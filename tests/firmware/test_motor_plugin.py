"""Tests for the DRI0050 motor plugin."""

from __future__ import annotations

import asyncio

from oqlos.hardware.plugins.base import PluginConfig
from oqlos.hardware.plugins.motor import MotorPlugin


class _Response:
    status_code = 200

    def json(self):
        return {"pwm_value": 0, "voltage": 0.0, "current": 0.0}


class _Client:
    async def post(self, url):
        assert url.endswith("/api/stop")
        return _Response()


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
