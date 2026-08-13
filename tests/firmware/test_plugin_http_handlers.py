"""Regression tests for plugin HTTP helpers and identify adapter enrichment."""

from __future__ import annotations

import asyncio

from oqlos.hardware.client.identify_enrich_adapters import (
    adapter_status_from_health,
    enrich_adapter_entry,
)
from oqlos.hardware.plugins.plugin_http_handlers import http_get_command, http_post_command


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class _Client:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self._status_code = status_code

    async def post(self, url, json=None):
        return _Response(self._payload, self._status_code)

    async def get(self, url):
        return _Response(self._payload, self._status_code)


class _TimeoutClient(_Client):
    def __init__(self, payload, status_code=200):
        super().__init__(payload, status_code)
        self.posts = []

    async def post(self, url, json=None, timeout=None):
        self.posts.append((url, json, timeout))
        return _Response(self._payload, self._status_code)


def test_http_get_command_success():
    result = asyncio.run(
        http_get_command(_Client({"position": 1}), "http://localhost:8205", "/api/status")
    )
    assert result["success"] is True
    assert result["data"]["position"] == 1


def test_http_command_preserves_c2004_problem_details_from_sidecar():
    problem = {
        "status": 422,
        "detail": "steps must be an integer",
        "code": "C2004-DATA-0002",
        "error_code": "C2004-DATA-0002",
        "architecture": "SOA",
        "component": "motor-tic249",
        "stage": "adapter.execute",
        "correlation_id": "cor-sidecar",
    }

    result = asyncio.run(
        http_post_command(
            _Client(problem, 422),
            "http://localhost:8205",
            "/api/reciprocate",
            json_body={"steps": "bad"},
        )
    )

    assert result["success"] is False
    assert result["status_code"] == 422
    assert result["error"] == "steps must be an integer"
    assert result["error_code"] == "C2004-DATA-0002"
    assert result["correlation_id"] == "cor-sidecar"
    assert result["component"] == "motor-tic249"
    assert result["upstream"] == problem


def test_http_post_command_forwards_an_operation_specific_timeout():
    client = _TimeoutClient({"success": True})

    result = asyncio.run(
        http_post_command(
            client,
            "http://localhost:8205",
            "/api/stop",
            json_body={"stop_mode": "reach_limit"},
            timeout=14.0,
        )
    )

    assert result["success"] is True
    assert client.posts == [
        (
            "http://localhost:8205/api/stop",
            {"stop_mode": "reach_limit"},
            14.0,
        )
    ]


def test_http_command_falls_back_when_upstream_is_not_problem_details():
    result = asyncio.run(
        http_get_command(_Client({}, 503), "http://localhost:8205", "/api/status")
    )

    assert result == {"success": False, "error": "HTTP 503", "status_code": 503}


def test_adapter_status_from_health_marks_serial_stale():
    status, probe = adapter_status_from_health(
        "modbus-io",
        {
            "status": "error",
            "message": "[Errno 5] Input/output error",
            "compatible": False,
        },
    )
    assert status == "serial-stale"
    assert "stale" in probe["diagnosis"]


def test_enrich_adapter_entry_marks_tic249_device_stale():
    adapter = enrich_adapter_entry(
        {
            "id": "motor-tic249",
            "status": "error",
            "probe": {
                "local_probe": {"connected": True},
                "health": {"message": "errno 19 no such device"},
            },
        }
    )
    assert adapter["status"] == "device-stale"
