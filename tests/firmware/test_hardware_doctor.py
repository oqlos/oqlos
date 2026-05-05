"""Tests for smart hardware detection and doctor repairs."""

from __future__ import annotations

import yaml

from oqlos.tools.hardware_diagnose import doctor
from oqlos.tools.hardware_diagnose.discovery import UsbDevice


def _write_config(path):
    path.write_text(
        """
plugins:
  modbus-io:
    enabled: true
    connection_type: modbus-rtu
    connection_params:
      serial_port: /dev/ttyACM0
      baudrate: 9600
      parity: N
""".lstrip(),
        encoding="utf-8",
    )


def _patch_detection(monkeypatch):
    monkeypatch.setattr(
        doctor,
        "list_usb_serial_devices",
        lambda: [
            UsbDevice(
                device="/dev/ttyACM1",
                vid=0x1A86,
                pid=0x55D3,
                manufacturer=None,
                product="USB Single Serial",
                serial_number="5958006895",
                description="USB Single Serial",
            )
        ],
    )
    monkeypatch.setattr(doctor, "list_i2c_buses", lambda: [])
    monkeypatch.setattr(
        doctor,
        "probe_waveshare_modbus",
        lambda timeout=0.35: {
            "connected": True,
            "adapter": "USB Single Serial",
            "serial_port": "/dev/ttyACM1",
            "baudrate": 19200,
            "parity": "N",
            "device_id": 1,
            "modbus_device_responds": True,
        },
    )
    monkeypatch.setattr(doctor, "check_firmware_health", lambda url: {"mode": "mock"})
    monkeypatch.setattr(
        doctor,
        "check_firmware_identify",
        lambda url: {
            "mode": "mock",
            "detected": 0,
            "total": 4,
            "adapters": [{"id": "modbus-io", "status": "offline"}],
            "diagnostics": {"serial_ports": []},
        },
    )


def test_doctor_reports_modbus_config_mismatch(monkeypatch, tmp_path):
    config = tmp_path / "oqlos.yaml"
    _write_config(config)
    _patch_detection(monkeypatch)

    report = doctor.build_doctor_report(config_path=config)

    codes = {issue["code"] for issue in report["issues"]}
    assert report["ok"] is False
    assert "modbus_config_mismatch" in codes
    assert "firmware_not_real" in codes
    assert "firmware_no_serial_access" in codes
    assert any(repair["id"] == "update_modbus_config" for repair in report["repairs"])


def test_doctor_fix_updates_modbus_config(monkeypatch, tmp_path):
    config = tmp_path / "oqlos.yaml"
    _write_config(config)
    _patch_detection(monkeypatch)

    report = doctor.build_doctor_report(config_path=config, fix=True)

    data = yaml.safe_load(config.read_text(encoding="utf-8"))
    params = data["plugins"]["modbus-io"]["connection_params"]
    assert params == {
        "serial_port": "/dev/ttyACM1",
        "baudrate": 19200,
        "parity": "N",
    }
    assert report["applied_repairs"][0]["id"] == "update_modbus_config"
    assert (tmp_path / "oqlos.yaml.bak").exists()


def test_detection_filters_real_usb_serial_devices(monkeypatch, tmp_path):
    config = tmp_path / "oqlos.yaml"
    _write_config(config)
    monkeypatch.setattr(
        doctor,
        "list_usb_serial_devices",
        lambda: [
            UsbDevice("/dev/ttyS0", None, None, None, None, None, "n/a"),
            UsbDevice("/dev/ttyUSB0", 0x1A86, 0x7523, None, "USB2.0-Serial", None, "USB2.0-Serial"),
        ],
    )
    monkeypatch.setattr(doctor, "list_i2c_buses", lambda: [])
    monkeypatch.setattr(
        doctor,
        "probe_waveshare_modbus",
        lambda timeout=0.35: {"connected": False, "reason": "no response"},
    )

    detection = doctor.detect_hardware(config_path=config, include_firmware=False)

    assert [dev["device"] for dev in detection["host"]["usb_serial_devices"]] == ["/dev/ttyUSB0"]
