"""Regression tests for DRI0050 motor Modbus RTU handlers."""

from __future__ import annotations

import asyncio
import time

from oqlos.hardware.plugins.base import PluginStatus
from oqlos.hardware.plugins.motor_modbus_handlers import (
    duty_pct_to_register,
    modbus_health_check,
    modbus_set_speed,
    modbus_status,
    modbus_stop,
)


class _ModbusResult:
    def __init__(self, registers=None, is_error=False):
        self.registers = registers or []
        self._is_error = is_error

    def isError(self):
        return self._is_error


class _Bus:
    def __init__(self, reads=None, write_errors=None):
        self.reads = reads or {}
        self.writes: list[tuple] = []
        self._write_errors = write_errors or {}

    async def call(self, method, **kwargs):
        if method == "read_holding_registers":
            key = (kwargs["address"], kwargs["count"], kwargs["device_id"])
            regs = self.reads.get(key)
            if regs is None:
                return _ModbusResult(is_error=True)
            return _ModbusResult(registers=regs)
        if method == "write_register":
            key = (kwargs["address"], kwargs["value"], kwargs["device_id"])
            self.writes.append(key)
            if key in self._write_errors:
                return _ModbusResult(is_error=True)
            return _ModbusResult()
        raise AssertionError(f"unexpected bus call: {method}")


def test_duty_pct_to_register_scales_percent():
    assert duty_pct_to_register(0) == 0
    assert duty_pct_to_register(100) == 255
    assert duty_pct_to_register(40) == 102


def test_modbus_health_check_reads_pid():
    bus = _Bus(reads={(0x0000, 1, 50): [0x1234]})

    health = asyncio.run(modbus_health_check(bus, slave=50, pid_reg=0x0000))

    assert health.status == PluginStatus.CONNECTED
    assert health.compatible is True
    assert "0x1234" in health.message


def test_modbus_set_speed_writes_duty_and_enable():
    bus = _Bus()
    start = time.monotonic()

    result = asyncio.run(
        modbus_set_speed(
            bus,
            slave=50,
            duty_reg=0x0006,
            enable_reg=0x0008,
            power_pct=40,
            start_time=start,
        )
    )

    assert result["success"] is True
    assert result["data"]["pwm_value"] == 102
    assert (0x0006, 102, 50) in bus.writes
    assert (0x0008, 1, 50) in bus.writes


def test_modbus_stop_zeros_duty_and_enable():
    bus = _Bus()

    result = asyncio.run(
        modbus_stop(bus, slave=50, duty_reg=0x0006, enable_reg=0x0008, start_time=time.monotonic())
    )

    assert result["success"] is True
    assert result["data"]["stopped"] is True
    assert (0x0006, 0, 50) in bus.writes
    assert (0x0008, 0, 50) in bus.writes


def test_modbus_status_maps_registers():
    bus = _Bus(reads={(0x0006, 3, 50): [128, 1000, 1]})

    result = asyncio.run(
        modbus_status(bus, slave=50, duty_reg=0x0006, start_time=time.monotonic())
    )

    assert result["success"] is True
    assert result["data"]["power_pct"] == 50.2
    assert result["data"]["frequency_hz"] == 1000
    assert result["data"]["enabled"] is True
