"""Regression: /api/v1/hardware/diagnosis and /recover."""

from __future__ import annotations

import asyncio

from oqlos.hardware.diagnosis import build_diagnosis_report, report_to_dict


def test_build_diagnosis_report_motors_error():
    identify = {
        "platform": {"modbus_topology": "separate-adapters"},
        "diagnostics": {
            "health": {
                "modbus-io": {"status": "connected", "compatible": True, "message": "ok"},
                "modbus-adc": {"status": "connected", "compatible": True, "message": "ok"},
                "motor-tic249": {
                    "status": "error",
                    "compatible": False,
                    "message": "[Errno 19] No such device",
                },
                "motor-dri0050": {
                    "status": "error",
                    "compatible": False,
                    "message": "HTTP 503",
                },
            },
        },
        "adapters": [],
    }
    report = build_diagnosis_report(identify)
    payload = report_to_dict(report)
    assert payload["ok"] is False
    assert payload["devices"]["motor-tic249"]["status"] == "error"
    host_actions = [
        a for dev in payload["devices"].values() for a in dev["recommended_actions"] if a.get("scope") == "host"
    ]
    assert any(a["kind"] == "docker" for a in host_actions)
