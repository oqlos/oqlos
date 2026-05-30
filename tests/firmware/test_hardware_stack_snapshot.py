"""Tests for centralized hardware stack snapshot."""

from __future__ import annotations

from oqlos.hardware.stack_snapshot import build_hardware_stack_snapshot


def test_stack_snapshot_marks_serial_stale(monkeypatch) -> None:
    monkeypatch.setattr(
        "oqlos.api.hardware._detect_runtime_platform",
        lambda: {"modbus_topology": "separate-adapters"},
    )
    monkeypatch.setattr(
        "oqlos.api.hardware._modbus_runtime_serial_ports",
        lambda: {
            "topology": "separate-adapters",
            "io_serial_port": "/dev/ttyACM1",
            "adc_serial_port": "/dev/ttyUSB0",
        },
    )
    monkeypatch.setattr(
        "oqlos.api.hardware._modbus_health_serial_stale",
        lambda _health: True,
    )
    monkeypatch.setattr(
        "oqlos.api.hardware._modbus_wizard_plan",
        lambda: {"ok": True, "steps": []},
    )

    class _Gateway:
        def modbus_preflight_report(self):
            return {"ok": True, "topology": "separate-adapters", "modules": []}

    monkeypatch.setattr("oqlos.api.hardware._gw", lambda: _Gateway())

    payload = build_hardware_stack_snapshot(
        {
            "modbus-io": {"message": "[Errno 5] Input/output error", "compatible": False},
            "modbus-adc": {"message": "[Errno 5] Input/output error", "compatible": False},
        }
    )

    assert payload["serial_handles_stale"] is True
    assert payload["wizard_plan"]["ok"] is True
    assert any(action["code"] == "restart_oqlos" for action in payload["recommended_actions"])
