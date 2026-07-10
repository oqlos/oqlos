"""Regression: v3 RTC routes proxy piRTC sidecar helpers."""

from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from oqlos.api._hw3_system import sub_router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(sub_router, prefix="/api/v3/hardware")
    return TestClient(app)


def test_v3_rtc_status_route() -> None:
    payload = {"ok": True, "peripheral_id": "rtc", "result": {"data": {"connected": True}}}
    with patch("oqlos.api.hardware_peripherals_routes.build_rtc_peripheral_status", return_value=payload):
        response = _client().get("/api/v3/hardware/rtc/status")
    assert response.status_code == 200
    assert response.json() == payload


def test_v3_rtc_command_route() -> None:
    payload = {"ok": True, "peripheral_id": "rtc", "command": "read_time", "result": {"time": "12:00:00"}}
    with patch("oqlos.api.hardware_peripherals_routes.run_rtc_command", return_value=payload) as run_cmd:
        response = _client().post("/api/v3/hardware/rtc/command", json={"command": "read_time", "args": {}})
    assert response.status_code == 200
    assert response.json() == payload
    run_cmd.assert_called_once_with("read_time", {})
