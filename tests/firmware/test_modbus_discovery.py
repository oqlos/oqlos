"""Tests for Waveshare Modbus serial autodiscovery."""

import os
import sys
import types

_firmware_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _firmware_root)

from services import modbus_discovery


class _OkResponse:
    def isError(self) -> bool:
        return False


class _ErrorResponse:
    def isError(self) -> bool:
        return True


def _install_fake_pymodbus(monkeypatch, responsive_port=None, responsive_baud=None, responsive_parity="N"):
    pymodbus_module = types.ModuleType("pymodbus")
    client_module = types.ModuleType("pymodbus.client")

    class FakeClient:
        def __init__(self, port, baudrate, stopbits, bytesize, parity, timeout):
            self.port = port
            self.baudrate = baudrate
            self.parity = parity

        def connect(self):
            return True

        def read_coils(self, address, count, device_id):
            if (
                self.port == responsive_port
                and self.baudrate == responsive_baud
                and self.parity == responsive_parity
                and address == 0
                and count == 1
                and device_id == modbus_discovery.DEFAULT_MODBUS_DEVICE_ID
            ):
                return _OkResponse()
            return _ErrorResponse()

        def close(self):
            return None

    client_module.ModbusSerialClient = FakeClient
    monkeypatch.setitem(sys.modules, "pymodbus", pymodbus_module)
    monkeypatch.setitem(sys.modules, "pymodbus.client", client_module)


def test_probe_waveshare_modbus_detects_working_port(monkeypatch):
    monkeypatch.setattr(
        modbus_discovery,
        "list_serial_ports",
        lambda: [
            {"device": "/dev/ttyACM0", "product": "USB Serial A", "manufacturer": "Vendor A", "serial_number": "A1"},
            {"device": "/dev/ttyACM1", "product": "USB Single Serial", "manufacturer": "QinHeng", "serial_number": "5958006895"},
        ],
    )
    _install_fake_pymodbus(monkeypatch, responsive_port="/dev/ttyACM1", responsive_baud=19200)

    result = modbus_discovery.probe_waveshare_modbus()

    assert result["connected"] is True
    assert result["modbus_device_responds"] is True
    assert result["serial_port"] == "/dev/ttyACM1"
    assert result["baudrate"] == 19200
    assert result["parity"] == "N"
    assert result["adapter"] == "USB Single Serial"


def test_probe_waveshare_modbus_reports_adapter_only_when_no_response(monkeypatch):
    monkeypatch.setattr(
        modbus_discovery,
        "list_serial_ports",
        lambda: [
            {"device": "/dev/ttyACM1", "product": "USB Single Serial", "manufacturer": "QinHeng", "serial_number": "5958006895"},
        ],
    )
    _install_fake_pymodbus(monkeypatch)

    result = modbus_discovery.probe_waveshare_modbus()

    assert result["connected"] is True
    assert result["modbus_device_responds"] is False
    assert result["serial_port"] == "/dev/ttyACM1"
    assert result["baudrate"] == 19200
    assert result["parity"] == "N"
    assert "No Modbus RTU response" in result["note"]