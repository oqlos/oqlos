"""Tests for hardware identification diagnostics."""

from __future__ import annotations

import asyncio

from oqlos.api import hardware as hw


class _FakeGateway:
    async def health(self) -> dict[str, str]:
        return {
            "mode": "real",
            "piadc": "ok",
            "motor": "ok",
            "modbus": "ok",
        }


def test_collect_hardware_diagnostics_exposes_ports(monkeypatch):
    monkeypatch.setattr(
        hw,
        "_scan_usb_devices",
        lambda: [
            {
                "vendor_id": "1a86",
                "product_id": "7523",
                "manufacturer": "QinHeng",
                "product": "USB Single Serial",
                "serial": "5958006895",
                "path": "/sys/bus/usb/devices/1-1",
            }
        ],
    )
    monkeypatch.setattr(
        hw,
        "list_serial_ports",
        lambda: [
            {
                "device": "/dev/ttyUSB0",
                "manufacturer": "QinHeng",
                "product": "USB Single Serial",
                "serial_number": "5958006895",
                "vid": 6790,
                "pid": 29987,
            }
        ],
    )
    monkeypatch.setattr(hw.glob, "glob", lambda pattern: ["/dev/i2c-0"] if pattern == "/dev/i2c-*" else [])

    diagnostics = hw._collect_hardware_diagnostics()

    assert diagnostics["usb_devices"][0]["product_id"] == "7523"
    assert diagnostics["serial_ports"][0]["device"] == "/dev/ttyUSB0"
    assert diagnostics["i2c_buses"] == ["/dev/i2c-0"]


def test_hardware_identify_includes_diagnostics(monkeypatch):
    monkeypatch.setattr(hw, "_gateway", _FakeGateway())
    monkeypatch.setattr(
        hw,
        "_probe_all_hardware",
        lambda: {
            "motor-tic249": {"connected": False},
            "motor-dri0050": {"connected": True, "serial_port": "/dev/ttyUSB0"},
            "piadc": {"connected": False},
            "modbus-io": {"connected": False},
        },
    )
    monkeypatch.setattr(
        hw,
        "_collect_hardware_diagnostics",
        lambda: {
            "usb_devices": [{"vendor_id": "1a86", "product_id": "7523"}],
            "serial_ports": [{"device": "/dev/ttyUSB0"}],
            "i2c_buses": ["/dev/i2c-0"],
        },
    )

    result = asyncio.run(hw.hardware_identify())

    assert result["mode"] == "real"
    assert result["detected"] == 1
    assert result["total"] == 4
    assert result["diagnostics"]["health"]["motor"] == "ok"
    assert result["diagnostics"]["serial_ports"][0]["device"] == "/dev/ttyUSB0"
    assert any(adapter["id"] == "motor-dri0050" for adapter in result["adapters"])
