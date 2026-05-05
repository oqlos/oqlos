"""Tests for hardware diagnosis discovery helpers."""

from __future__ import annotations

from oqlos.tools.hardware_diagnose import discovery


def test_list_i2c_buses_uses_glob(monkeypatch):
    monkeypatch.setattr(
        discovery.glob,
        "glob",
        lambda pattern: ["/dev/i2c-2", "/dev/i2c-0"] if pattern == "/dev/i2c-*" else [],
    )

    assert discovery.list_i2c_buses() == ["/dev/i2c-0", "/dev/i2c-2"]


def test_list_usb_serial_devices_uses_glob_fallback(monkeypatch):
    monkeypatch.setattr(discovery, "HAS_SERIAL", False)
    monkeypatch.setattr(
        discovery.glob,
        "glob",
        lambda pattern: {
            "/dev/ttyACM*": ["/dev/ttyACM0"],
            "/dev/ttyUSB*": ["/dev/ttyUSB1"],
        }.get(pattern, []),
    )

    devices = discovery.list_usb_serial_devices()

    assert [device.device for device in devices] == ["/dev/ttyACM0", "/dev/ttyUSB1"]
