"""Aggregate /api/v1/hardware/health HTTP semantics."""

from __future__ import annotations

import asyncio

from oqlos.api import hardware as hw


def test_hardware_health_overall_ok_ignores_disabled_plugins():
    payload = {
        "mode": "real",
        "modbus-io": {"status": "connected", "compatible": True, "message": "ok"},
        "motor-tic249": {"status": "disabled", "compatible": False, "message": "off"},
    }
    assert hw._hardware_health_overall_ok(payload) is True


def test_hardware_health_overall_ok_ignores_init_summary():
    payload = {
        "mode": "real",
        "init_summary": {
            "connected": ["modbus-io"],
            "failed": [],
            "disabled": ["motor-tic249"],
        },
        "modbus-io": {"status": "connected", "compatible": True, "message": "ok"},
        "motor-tic249": {"status": "disabled", "compatible": False, "message": "off"},
    }
    assert hw._hardware_health_overall_ok(payload) is True


def test_hardware_health_overall_ok_false_when_any_plugin_errors():
    payload = {
        "mode": "real",
        "modbus-io": {"status": "error", "compatible": False, "message": "EIO"},
    }
    assert hw._hardware_health_overall_ok(payload) is False


class _FakeGateway:
    async def health(self):
        return {
            "mode": "real",
            "modbus-io": {"status": "error", "compatible": False, "message": "EIO"},
        }


def test_hardware_health_endpoint_returns_503_when_degraded(monkeypatch):
    monkeypatch.setattr(hw, "_gw", lambda: _FakeGateway())
    monkeypatch.setattr(hw, "_detect_runtime_platform", lambda: {"detected": "desktop-linux"})

    response = asyncio.run(hw.hardware_health())

    assert response.status_code == 503
    assert response.body
    body = response.body.decode("utf-8").replace(" ", "")
    assert '"degraded":true' in body
    assert '"overall_ok":false' in body
