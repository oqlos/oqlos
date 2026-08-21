"""Regression tests for lung plugin movement pre-checks."""

from __future__ import annotations

import asyncio

from oqlos.hardware.plugins.base import PluginConfig
from oqlos.hardware.client.tic249_extended import _build_reciprocate_params
from oqlos.hardware.client.tic249_command_mapping import map_tic249_command
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


def test_stroke_sequence_posts_human_units_to_zero_dwell_endpoint():
    client = _ReadyFalseClient()
    plugin = _plugin_with_client(client)
    params = {
        "stroke_count": 6,
        "speed_steps_per_second": 1200,
        "boundary_mode": "position",
        "stroke_steps": 500,
        "acceleration_steps_per_second2": 3000,
    }

    result = asyncio.run(plugin.execute_command("stroke_sequence", params))

    assert result["success"] is True
    assert client.posts == [
        ("http://localhost:8205/api/stroke-sequence", params),
    ]


def test_tic249_stroke_sequence_maps_camel_case_without_pause():
    plugin_command, params = map_tic249_command(
        "tic249_stroke_sequence",
        {
            "strokeCount": 4,
            "speedStepsPerSecond": 1000,
            "boundaryMode": "position",
            "strokeSteps": 200,
            "startDirection": "right",
            "accelerationStepsPerSecond2": 2500,
            "pause": 1,
        },
    )

    assert plugin_command == "stroke_sequence"
    assert params == {
        "stroke_count": 4,
        "speed_steps_per_second": 1000,
        "boundary_mode": "position",
        "stroke_steps": 200,
        "start_direction": "right",
        "acceleration_steps_per_second2": 2500,
    }


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

    alert = plugin._position_uncertain_alert(
        {
            "position_uncertain": True,
            "forward_limit_active": False,
            "reverse_limit_active": False,
        }
    )
    assert alert is not None
    assert "mapę pinów OQL/NVM" in alert
    assert "SDA" not in alert and "SCL" not in alert



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


def test_immediate_stop_forwards_explicit_false_to_sidecar():
    client = _StopClient()
    plugin = _plugin_with_client(client)

    result = asyncio.run(
        plugin.execute_command("stop", {"stop_at_limit": False})
    )

    assert result["success"] is True
    assert client.posts == [
        (
            "http://localhost:8205/api/stop",
            {"stop_at_limit": False},
            None,
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


class _AbortsAfterAcceptClient:
    """Sidecar accepts /api/reciprocate, then reports it refused to move."""

    def __init__(self, *, previous_error: str = ""):
        self.posts = []
        self._motion_error = previous_error
        self._accepted = False

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
                    "last_motion_error": self._motion_error,
                },
            )
        return _JsonResponse(404, {})

    async def post(self, url, json=None):
        self.posts.append((url, json))
        self._accepted = True
        self._motion_error = (
            "Unexpected reverse limit active before half-cycle; "
            "aborting instead of reversing direction"
        )
        return _JsonResponse(200, {"success": True, "mode": "reciprocating"})


class _StaleMotionErrorClient(_ReadyFalseClient):
    """A motion error left over from an earlier run must not fail a good START."""

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
                    "last_motion_error": "stale error from an earlier run",
                },
            )
        return _JsonResponse(404, {})


def _reciprocate(plugin):
    return asyncio.run(
        plugin.execute_command(
            "reciprocate",
            {"steps": 500, "speed": 10_000_000, "cycles": 3, "pause": 0.5},
        )
    )


def test_reciprocate_reports_sidecar_abort_instead_of_success():
    client = _AbortsAfterAcceptClient()
    plugin = _plugin_with_client(client)

    result = _reciprocate(plugin)

    assert result["success"] is False
    assert "reverse limit active" in result["reason"]
    assert result["error_code"] == "C2004-HW-0012"
    assert result["stage"] == "adapter.motion"
    assert result["issue_code"] == "hw_tic249_position_uncertain"
    # The command still reached the sidecar; only the verdict changed.
    assert client.posts[0][0] == "http://localhost:8205/api/reciprocate"


def test_reciprocate_ignores_a_stale_motion_error():
    client = _StaleMotionErrorClient()
    plugin = _plugin_with_client(client)

    result = _reciprocate(plugin)

    assert result["success"] is True
