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


def test_piadc_local_probe_is_skipped_on_non_rpi(monkeypatch):
    monkeypatch.setenv("ADS1115_ALLOW_NON_RPI", "false")
    monkeypatch.setenv("PIADC_URL", "http://rpi.local:8204")
    monkeypatch.setattr(hw, "_is_raspberry_pi_host", lambda: False)

    result = hw._probe_i2c_ads1115()

    assert result["connected"] is False
    assert result["skipped"] is True
    assert result["remote_url"] == "http://rpi.local:8204"
    assert "Raspberry Pi" in result["reason"]


def test_platform_selection_can_force_generic_linux_probe(monkeypatch):
    monkeypatch.setenv("PIADC_PLATFORM", "generic-linux")
    monkeypatch.setenv("ADS1115_ALLOW_NON_RPI", "false")
    monkeypatch.setattr(hw, "_is_raspberry_pi_host", lambda: False)

    platform = hw._detect_runtime_platform()

    assert platform["piadc_selected"] == "generic-linux"
    assert platform["piadc_driver_role"] == "generic-linux-smbus"
    assert platform["piadc_local_probe_allowed"] is True


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
    assert "platform" in result
    assert any(adapter["id"] == "motor-dri0050" for adapter in result["adapters"])


class _ModbusTimeoutGateway:
    async def health(self) -> dict[str, object]:
        return {
            "mode": "real",
            "piadc": {"status": "connected", "compatible": True},
            "motor-tic249": {"status": "connected", "compatible": True},
            "motor-dri0050": {"status": "connected", "compatible": True},
            "modbus-io": {
                "status": "error",
                "message": "Modbus RTU read_coils timed out after 2.0s",
                "compatible": False,
            },
        }


def test_hardware_identify_reports_modbus_timeout_as_adapter_only(monkeypatch):
    monkeypatch.setattr(hw, "_gateway", _ModbusTimeoutGateway())

    def _unexpected_live_probe(*_args):
        raise AssertionError("modbus timeout should use plugin health, not a second serial probe")

    monkeypatch.setattr(hw, "_probe_all_hardware", _unexpected_live_probe)
    monkeypatch.setattr(hw, "_collect_hardware_diagnostics", lambda: {})

    result = asyncio.run(hw.hardware_identify())
    modbus = next(adapter for adapter in result["adapters"] if adapter["id"] == "modbus-io")

    assert modbus["status"] == "adapter-only"
    assert "did not answer" in modbus["probe"]["diagnosis"]
