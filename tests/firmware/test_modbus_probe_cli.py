"""Tests for the direct Modbus RTU probe CLI helper."""

from __future__ import annotations

import sys
import types
from argparse import Namespace

from oqlos.tools.hardware_diagnose import modbus_probe


class _OkResponse:
    def isError(self) -> bool:
        return False

    def __str__(self) -> str:
        return "ok-response"


class _ErrorResponse:
    def isError(self) -> bool:
        return True


def _install_fake_pymodbus(monkeypatch):
    pymodbus_module = types.ModuleType("pymodbus")
    client_module = types.ModuleType("pymodbus.client")

    class FakeClient:
        instances = []

        def __init__(self, port, baudrate, stopbits, bytesize, parity, timeout):
            self.port = port
            self.baudrate = baudrate
            self.parity = parity
            self.timeout = timeout
            self.read_kwargs = None
            self.closed = False
            FakeClient.instances.append(self)

        def connect(self):
            return True

        def read_holding_registers(self, **kwargs):
            self.read_kwargs = kwargs
            if (
                self.port == "/dev/ttyUSB0"
                and self.baudrate == 9600
                and self.parity == "E"
                and kwargs == {"address": 12, "count": 2, "device_id": 7}
            ):
                return _OkResponse()
            return _ErrorResponse()

        def close(self):
            self.closed = True

    client_module.ModbusSerialClient = FakeClient
    monkeypatch.setitem(sys.modules, "pymodbus", pymodbus_module)
    monkeypatch.setitem(sys.modules, "pymodbus.client", client_module)
    return FakeClient


def test_run_modbus_probe_returns_successful_read(monkeypatch):
    fake_client = _install_fake_pymodbus(monkeypatch)

    result = modbus_probe.run_modbus_probe(
        serials=["/dev/ttyUSB0"],
        baudrates=[9600],
        parities=["E"],
        device_ids=[7],
        functions=["holding_registers"],
        addresses=[12],
        counts=[2],
        timeout=0.25,
    )

    assert result["ok"] is True
    assert result["results"][0]["function"] == "read_holding_registers"
    assert result["results"][0]["response"] == "ok-response"
    assert fake_client.instances[0].read_kwargs == {"address": 12, "count": 2, "device_id": 7}
    assert fake_client.instances[0].closed is True


def test_run_modbus_probe_reports_unsupported_function(monkeypatch):
    _install_fake_pymodbus(monkeypatch)

    result = modbus_probe.run_modbus_probe(
        serials=["/dev/ttyUSB0"],
        baudrates=[9600],
        parities=["N"],
        device_ids=[1],
        functions=["write_coil"],
        addresses=[0],
        counts=[1],
        timeout=0.25,
    )

    assert result["ok"] is False
    assert result["results"][0]["error"] == "unsupported read function"


def test_probe_options_from_args_override_environment(monkeypatch):
    monkeypatch.setenv("MODBUS_SERIAL", "/dev/from-env")
    monkeypatch.setenv("MODBUS_BAUD", "19200")

    options = modbus_probe.probe_options_from_args(
        Namespace(
            serials=["/dev/a,/dev/b"],
            baudrates=["9600,38400"],
            parities=["E"],
            device_ids=["7,8"],
            functions=["holding_registers"],
            addresses=["12"],
            counts=["0,2"],
            timeout=1.25,
        )
    )

    assert options == {
        "serials": ["/dev/a", "/dev/b"],
        "baudrates": [9600, 38400],
        "parities": ["E"],
        "device_ids": [7, 8],
        "functions": ["holding_registers"],
        "addresses": [12],
        "counts": [1, 2],
        "timeout": 1.25,
    }
