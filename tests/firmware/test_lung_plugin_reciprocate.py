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


class _StopClient:
    def __init__(self):
        self.posts = []

    async def post(self, url, json=None, timeout=None):
        self.posts.append((url, json, timeout))
        return _JsonResponse(200, {"success": True})


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


def test_active_limits_return_a_canonical_hardware_error_before_post():
    client = _ReadyFalseClient()

    async def blocked_status(_url):
        return _JsonResponse(
            200,
            {
                "connected": True,
                "forward_limit_active": True,
                "reverse_limit_active": True,
            },
        )

    client.get = blocked_status
    plugin = _plugin_with_client(client)

    result = asyncio.run(plugin.execute_command("reciprocate", {"steps": 500}))

    assert result["success"] is False
    assert result["error_code"] == "C2004-HW-0012"
    assert result["status_code"] == 503
    assert result["architecture"] == "SOA"
    assert result["component"] == "motor-tic249"
    assert result["stage"] == "adapter.preflight"
    assert client.posts == []


def test_position_uncertain_without_limits_allows_reciprocate():
    client = _ReadyFalseClient()

    async def uncertain_status(_url):
        return _JsonResponse(
            200,
            {
                "connected": True,
                "position_uncertain": True,
                "energized": False,
                "forward_limit_active": False,
                "reverse_limit_active": False,
                "position": 0,
            },
        )

    client.get = uncertain_status
    plugin = _plugin_with_client(client)

    result = asyncio.run(plugin.execute_command("reciprocate", {"steps": 500}))

    assert result["success"] is True
    assert len(client.posts) == 1



def test_position_uncertain_with_active_limit_alerts_but_does_not_block():
    client = _ReadyFalseClient()

    async def uncertain_at_reverse(_url):
        if _url.endswith("/api/status"):
            return _JsonResponse(
                200,
                {
                    "connected": True,
                    "position_uncertain": True,
                    "energized": False,
                    "forward_limit_active": False,
                    "reverse_limit_active": True,
                    "position": 0,
                },
            )
        return _JsonResponse(200, {"version": "test"})

    client.get = uncertain_at_reverse
    plugin = _plugin_with_client(client)

    health = asyncio.run(plugin.health_check())
    alerts = health.details["operator_alerts"]
    motion = asyncio.run(plugin.execute_command("reciprocate", {"steps": 500}))

    assert health.status.value == "connected"
    assert alerts[0]["issue_code"] == "hw_tic249_position_uncertain"
    assert "homing" in alerts[0]["message"]
    assert motion["success"] is True
    assert client.posts


def test_reach_limit_stop_has_enough_time_for_sidecar_safety_window():
    client = _StopClient()
    plugin = _plugin_with_client(client)
    plugin.config.timeout = 2.0

    result = asyncio.run(
        plugin.execute_command("stop", {"stop_mode": "reach_limit"})
    )

    assert result["success"] is True
    assert client.posts == [
        (
            "http://localhost:8205/api/stop",
            {"stop_mode": "reach_limit"},
            14.0,
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
