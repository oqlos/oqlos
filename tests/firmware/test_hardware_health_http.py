"""Aggregate /api/v1/hardware/health HTTP semantics."""

from __future__ import annotations

import asyncio

from oqlos.api import hardware as hw
from oqlos.api import hardware_identify as hw_identify


def test_hardware_health_overall_ok_ignores_disabled_plugins():
    payload = {
        "mode": "real",
        "modbus-io": {"status": "connected", "compatible": True, "message": "ok"},
        "motor-tic249": {"status": "disabled", "compatible": False, "message": "off"},
    }
    assert hw._hardware_health_overall_ok(payload) is True


def test_hardware_health_overall_ok_rejects_disabled_required_plugin():
    payload = {
        "mode": "real",
        "modbus-io": {
            "status": "disabled",
            "compatible": False,
            "required": True,
            "message": "off",
        },
    }
    assert hw._hardware_health_overall_ok(payload) is False


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


def test_hardware_health_endpoint_returns_200_when_degraded(monkeypatch):
    monkeypatch.setattr(hw, "_gw", lambda: _FakeGateway())
    monkeypatch.setattr(hw_identify, "get_hardware_gateway", lambda: _FakeGateway())
    monkeypatch.setattr(hw_identify.platform, "_detect_runtime_platform", lambda: {"detected": "desktop-linux"})

    payload = asyncio.run(hw.hardware_health())

    assert isinstance(payload, dict)
    assert payload.get("degraded") is True
    assert payload.get("overall_ok") is False
    assert payload.get("status") == "degraded"


def test_hardware_health_exposes_active_undervoltage_as_coded_degraded_state(monkeypatch):
    class HealthyGateway:
        async def health(self):
            return {
                "mode": "real",
                "modbus-io": {"status": "connected", "compatible": True},
            }

    monkeypatch.setattr(hw_identify, "get_hardware_gateway", lambda: HealthyGateway())
    monkeypatch.setattr(hw_identify.platform, "_detect_runtime_platform", lambda: {})
    async def _active_power():
        return {
            "status": "critical",
            "errors": [
                {
                    "error_code": "C2004-HW-0014",
                    "issue_code": "boardnet_undervoltage_active",
                }
            ],
        }

    monkeypatch.setattr(hw_identify, "sample_power_telemetry", _active_power)

    payload = asyncio.run(hw.hardware_health())

    assert payload["overall_ok"] is False
    assert payload["degraded"] is True
    assert payload["status"] == "degraded"
    assert payload["errors"][0]["error_code"] == "C2004-HW-0014"
