"""Regression tests for lung plugin movement pre-checks."""

from __future__ import annotations

import asyncio

from oqlos.hardware.plugins.base import PluginConfig
from oqlos.hardware.client.tic249_extended import _build_reciprocate_params
from oqlos.hardware.plugins.lung import LungPlugin


class _JsonResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _ReadyFalseClient:
    def __init__(self):
        self.posts = []

    async def get(self, url):
        if url.endswith("/api/status"):
            return _JsonResponse(
                200,
                {
                    "connected": True,
                    "ready": False,
                    "energized": False,
                    "motor_driver_error": False,
                    "low_vin": False,
                    "forward_limit_active": False,
                    "reverse_limit_active": False,
                },
            )
        return _JsonResponse(404, {})

    async def post(self, url, json=None):
        self.posts.append((url, json))
        return _JsonResponse(200, {"success": True, "mode": "reciprocating"})


def _plugin_with_client(client):
    plugin = LungPlugin(
        PluginConfig(
            plugin_id="motor-tic249",
            enabled=True,
            connection_type="http",
            connection_params={"base_url": "http://localhost:8205"},
        )
    )
    plugin._client = client
    return plugin


def test_ready_false_does_not_block_reciprocate_start():
    client = _ReadyFalseClient()
    plugin = _plugin_with_client(client)

    result = asyncio.run(
        plugin.execute_command(
            "reciprocate",
            {"steps": 500, "speed": 10_000_000, "cycles": 3, "pause": 0.5, "ramp_seconds": 0.5},
        )
    )

    assert result["success"] is True
    assert client.posts == [
        (
            "http://localhost:8205/api/reciprocate",
            {"steps": 500, "speed": 10_000_000, "cycles": 3, "pause": 0.5, "ramp_seconds": 0.5},
        )
    ]


def test_tic249_extended_reciprocate_normalizes_ramp_time_alias():
    params = _build_reciprocate_params(
        {
            "steps": 500,
            "speed": 1000,
            "speed_unit": "steps/s",
            "cycles": 3,
            "pause": 0.5,
            "ramp_time": 0.5,
        },
        default_cycles=1,
    )

    assert params["speed"] == 10_000_000
    assert params["ramp_seconds"] == 0.5
