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


def test_doctor_fix_reports_unapplied_manual_repairs(monkeypatch, tmp_path):
    config = tmp_path / "oqlos.yaml"
    _write_config(config)
    _patch_detection(monkeypatch)

    report = doctor.build_doctor_report(config_path=config, fix=True)
    output = doctor.format_doctor(report)

    assert report["fix_requested"] is True
    assert "Unapplied repairs:" in output
    assert "skipped manual/unsafe: enable_real_mode" in output
    assert "skipped manual/unsafe: mount_serial_devices" in output


def test_doctor_reports_busy_configured_serial_port(monkeypatch, tmp_path):
    config = tmp_path / "oqlos.yaml"
    _write_config(config)
    _patch_detection(monkeypatch)
    monkeypatch.setattr(
        doctor,
        "_serial_port_owners",
        lambda devices: {
            "/dev/ttyACM0": [
                {"pid": "1234", "command": "oqlos-server", "args": "oqlos-server --port 8210"}
            ]
        },
    )

    report = doctor.build_doctor_report(config_path=config)

    issue = next(item for item in report["issues"] if item["code"] == "serial_port_busy")
    assert "/dev/ttyACM0" in issue["message"]
    assert "oqlos-server[1234]" in issue["message"]
    assert any(repair["id"] == "release_serial_port" for repair in report["repairs"])


def test_doctor_reports_busy_configured_serial_port_via_by_id_symlink(monkeypatch, tmp_path):
    config = tmp_path / "oqlos.yaml"
    config.write_text(
        """
plugins:
  modbus-io:
    enabled: true
    connection_type: modbus-rtu
    connection_params:
      serial_port: /dev/serial/by-id/usb-Modbus
      baudrate: 9600
      parity: N
""".lstrip(),
        encoding="utf-8",
    )
    _patch_detection(monkeypatch)
    monkeypatch.setattr(
        doctor,
        "_canonical_device_path",
        lambda path: "/dev/ttyACM0" if path in {"/dev/serial/by-id/usb-Modbus", "/dev/ttyACM0"} else path,
    )
    monkeypatch.setattr(
        doctor,
        "_serial_port_owners",
        lambda devices: {
            "/dev/ttyACM0": [
                {"pid": "1234", "command": "oqlos-server", "args": "oqlos-server --port 8210"}
            ]
        },
    )

    report = doctor.build_doctor_report(config_path=config)

    issue = next(item for item in report["issues"] if item["code"] == "serial_port_busy")
    assert "/dev/serial/by-id/usb-Modbus (/dev/ttyACM0)" in issue["message"]
    assert "oqlos-server[1234]" in issue["message"]


def test_doctor_trusts_firmware_modbus_health_when_local_port_is_busy(monkeypatch, tmp_path):
    config = tmp_path / "oqlos.yaml"
    _write_config(config)
    _patch_detection(monkeypatch)
    monkeypatch.setattr(
        doctor,
        "probe_waveshare_modbus",
        lambda timeout=0.35: {
            "connected": True,
            "serial_port": "/dev/ttyACM1",
            "modbus_device_responds": False,
            "reason": "/dev/ttyACM1 busy or unavailable",
        },
    )
    monkeypatch.setattr(
        doctor,
        "check_firmware_health",
        lambda url: {"mode": "real", "modbus-io": {"status": "connected", "compatible": True}},
    )
    monkeypatch.setattr(
        doctor,
        "check_firmware_identify",
        lambda url: {
            "mode": "real",
            "detected": 0,
            "total": 4,
            "adapters": [{"id": "modbus-io", "status": "adapter-only"}],
            "diagnostics": {"serial_ports": ["/dev/ttyACM1"]},
        },
    )

    report = doctor.build_doctor_report(config_path=config)
    output = doctor.format_doctor(report)
    codes = {item["code"] for item in report["issues"]}

    assert "modbus_adapter_only" not in codes
    assert "adapter_modbus-io_not_ok" not in codes
    assert "Modbus: OK via firmware" in output


def test_doctor_explains_remote_firmware_cannot_use_local_usb(monkeypatch, tmp_path):
    config = tmp_path / "oqlos.yaml"
    _write_config(config)
    _patch_detection(monkeypatch)
    monkeypatch.setattr(
        doctor,
        "probe_waveshare_modbus",
        lambda timeout=0.35: {
            "connected": False,
            "reason": "local probe skipped",
            "modbus_device_responds": False,
        },
    )
    monkeypatch.setattr(
        doctor,
        "check_firmware_health",
        lambda url: {"mode": "real", "modbus": "/dev/ttyACM1@19200 8N1 (mode=rtu)"},
    )
    monkeypatch.setattr(
        doctor,
        "check_firmware_identify",
        lambda url: {
            "mode": "real",
            "detected": 0,
            "total": 4,
            "adapters": [
                {"id": "modbus-adc", "status": "no-access"},
                {"id": "motor-dri0050", "status": "offline"},
                {"id": "modbus-io", "status": "no-access"},
            ],
            "diagnostics": {"serial_ports": []},
        },
    )

    report = doctor.build_doctor_report(
        firmware_url="http://192.168.188.109:8202",
        config_path=config,
    )
    output = doctor.format_doctor(report)
    codes = {item["code"] for item in report["issues"]}

    assert "remote_firmware_no_serial_access" in codes
    assert "firmware_no_serial_access" not in codes
    assert "modbus_not_detected" not in codes
    assert "Firmware: http://192.168.188.109:8202 (remote host 192.168.188.109)" in output
    assert "Modbus: remote firmware status no-access" in output


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
