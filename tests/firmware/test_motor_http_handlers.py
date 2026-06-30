"""Regression tests for shared motor HTTP/CLI handlers."""

from __future__ import annotations

import asyncio
import time

from oqlos.hardware.plugins.motor_http_handlers import motor_cli_command, motor_http_request


class _Response:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _Client:
    def __init__(self, payload):
        self._payload = payload
        self.last_url = ""

    async def post(self, url, json=None):
        self.last_url = url
        return _Response(self._payload)

    async def get(self, url):
        self.last_url = url
        return _Response(self._payload)


def test_motor_http_request_maps_response_fields():
    client = _Client({"pwm_value": 42, "voltage": 1.2, "current": 0.3})
    start = time.monotonic()

    result = asyncio.run(
        motor_http_request(
            client,
            "http://localhost:8203",
            method="POST",
            path="/api/stop",
            start_time=start,
            map_data=lambda data: {
                "stopped": True,
                "pwm_value": data.get("pwm_value", 0),
            },
        )
    )

    assert result["success"] is True
    assert result["data"]["stopped"] is True
    assert result["data"]["pwm_value"] == 42
    assert client.last_url.endswith("/api/stop")


def test_motor_cli_command_success(monkeypatch):
    class _Proc:
        returncode = 0

        async def communicate(self):
            return (b"ok", b"")

    async def _fake_exec(*_args, **_kwargs):
        return _Proc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec)

    result = asyncio.run(
        motor_cli_command(
            ["dri", "/dev/ttyUSB0", "--enable", "0"],
            timeout=1.0,
            start_time=time.monotonic(),
            success_payload={"stopped": True},
        )
    )

    assert result["success"] is True
    assert result["data"]["stopped"] is True
