"""Tests for hardware health output formatting."""

from __future__ import annotations

from oqlos.tools.hardware_diagnose import health


def test_cmd_health_marks_connected_adapter_dict_as_ok(monkeypatch):
    monkeypatch.setattr(
        health,
        "check_firmware_health",
        lambda url: {
            "mode": "real",
            "motor-dri0050": {
                "status": "connected",
                "message": "Motor is healthy",
                "compatible": True,
            },
        },
    )

    output = health.cmd_health("http://localhost:8202")

    assert "Mode: REAL" in output
    assert "✅ motor-dri0050: connected: Motor is healthy" in output


def test_cmd_health_marks_error_adapter_dict_as_warning(monkeypatch):
    monkeypatch.setattr(
        health,
        "check_firmware_health",
        lambda url: {
            "mode": "real",
            "piadc": {
                "status": "error",
                "message": "permission denied on /dev/i2c-0",
            },
        },
    )

    output = health.cmd_health("http://localhost:8202")

    assert "⚠️ piadc: error: permission denied on /dev/i2c-0" in output
