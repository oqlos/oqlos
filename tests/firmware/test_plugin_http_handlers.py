"""Regression tests for plugin HTTP helpers and identify adapter enrichment."""

from __future__ import annotations

import asyncio

from oqlos.hardware.client.identify_enrich_adapters import (
    adapter_status_from_health,
    enrich_adapter_entry,
)
from oqlos.hardware.plugins.plugin_http_handlers import http_get_command, http_post_command


class _Response:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _Client:
    def __init__(self, payload):
        self._payload = payload

    async def post(self, url, json=None):
        return _Response(self._payload)

    async def get(self, url):
        return _Response(self._payload)


def test_http_get_command_success():
    result = asyncio.run(
        http_get_command(_Client({"position": 1}), "http://localhost:8205", "/api/status")
    )
    assert result["success"] is True
    assert result["data"]["position"] == 1


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
