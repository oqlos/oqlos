"""Unit tests for Modbus RTU t3.5 turnaround pacing and ADC/IO snapshot caches (PLF-28761)."""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from typing import Any

import pytest

from oqlos.hardware.plugins._rtu_serial import (
    DEFAULT_MODBUS_BAUD_RATE,
    MODBUS_FIXED_T35_US,
    RtuTurnaroundPacer,
    modbus_rtu_t35_us,
)
from oqlos.hardware.plugins.base import PluginConfig
from oqlos.hardware.plugins.modbus import ModbusPlugin
from oqlos.hardware.plugins.modbus_adc import ModbusAdcPlugin


@dataclass
class _FakeResult:
    registers: list[int] | None = None
    bits: list[bool] | None = None
    error: bool = False

    def isError(self) -> bool:
        return self.error


class _FakeClock:
    def __init__(self, start: float = 100.0) -> None:
        self.now = start
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, delay: float) -> None:
        self.sleeps.append(delay)
        self.now += delay


class _FakeAdcBus:
    def __init__(self) -> None:
        self.reads: int = 0
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.registers: list[int] = [100, 200, 300, 400, 500, 600, 700, 800]

    async def read_input_registers(self, **kwargs: Any) -> _FakeResult:
        self.reads += 1
        self.calls.append(("read_input_registers", kwargs))
        return _FakeResult(registers=list(self.registers))

    async def call(self, method_name: str, **kwargs: Any) -> _FakeResult:
        self.calls.append((method_name, kwargs))
        if method_name == "read_holding_registers":
            addr = kwargs.get("address")
            if addr == 0x4000:
                return _FakeResult(registers=[2])
            if addr == 0x2000:
                return _FakeResult(registers=[0x0001])
        return _FakeResult(registers=[0])

    async def close(self) -> None:
        return None


class _FakeIoBus:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def read_coils(self, **kwargs: Any) -> _FakeResult:
        self.calls.append(("read_coils", kwargs))
        return _FakeResult(bits=[True, False, False, False, False, False, False, False])

    async def call(self, method_name: str, **kwargs: Any) -> _FakeResult:
        self.calls.append((method_name, kwargs))
        if method_name == "read_discrete_inputs":
            return _FakeResult(bits=[False] * 8)
        if method_name == "read_holding_registers":
            addr = kwargs.get("address")
            if addr == 0x1000:
                return _FakeResult(registers=[0] * 8)
            if addr == 0x4000:
                return _FakeResult(registers=[1])
            if addr == 0x2000:
                return _FakeResult(registers=[0x0000])
        return _FakeResult(registers=[0])

    async def close(self) -> None:
        return None


def _install_fake_pimodbus(monkeypatch: pytest.MonkeyPatch) -> None:
    pimodbus_pkg = types.ModuleType("pimodbus")
    provisioning_mod = types.ModuleType("pimodbus.provisioning")
    provisioning_mod.decode_uart_register = lambda raw: {"raw": raw, "baudrate": 4800, "parity": "N"}
    pimodbus_pkg.provisioning = provisioning_mod
    monkeypatch.setitem(sys.modules, "pimodbus", pimodbus_pkg)
    monkeypatch.setitem(sys.modules, "pimodbus.provisioning", provisioning_mod)


class TestModbusRtuT35Formula:
    def test_4800_baud_is_exact_8021_us(self) -> None:
        assert DEFAULT_MODBUS_BAUD_RATE == 4_800
        assert modbus_rtu_t35_us(4_800) == 8_021
        assert modbus_rtu_t35_us() == 8_021

    def test_9600_19200_and_high_baud_rates(self) -> None:
        assert modbus_rtu_t35_us(9_600) == 4_011
        assert modbus_rtu_t35_us(19_200) == 2_006
        assert modbus_rtu_t35_us(38_400) == MODBUS_FIXED_T35_US == 1_750
        assert modbus_rtu_t35_us(115_200) == 1_750

    @pytest.mark.parametrize("bad_baud", [0, -4800, True, False])
    def test_rejects_invalid_baudrate(self, bad_baud: Any) -> None:
        with pytest.raises(ValueError):
            modbus_rtu_t35_us(bad_baud)


class TestModbusAdcCache:
    @pytest.mark.asyncio
    async def test_read_sensor_reuses_ttl_cache_and_refreshes_on_expiry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        now = [10.0]
        monkeypatch.setattr("oqlos.hardware.plugins.modbus_adc.time.monotonic", lambda: now[0])

        cfg = PluginConfig(
            plugin_id="modbus-adc",
            connection_type="modbus-rtu",
            connection_params={"serial_port": "/dev/ttyUSB0", "baudrate": 4800, "read_cache_ttl_s": 0.05},
        )
        plugin = ModbusAdcPlugin(cfg)
        bus = _FakeAdcBus()
        plugin._bus = bus
        clock = _FakeClock()
        plugin._rtu_pacer = RtuTurnaroundPacer(clock=clock, sleeper=clock.sleep)

        r1 = await plugin.execute_command("read_sensor", {"sensor_id": "ai01"})
        r2 = await plugin.execute_command("read_sensor", {"sensor_id": "ai02"})
        r3 = await plugin.execute_command("read_channel", {"channel": "ai03"})
        assert r1["success"] and r1["data"] == 100.0
        assert r2["success"] and r2["data"] == 200.0
        assert r3["success"] and r3["data"]["value"] == 300.0
        assert bus.reads == 1

        # Advance past TTL -> triggers a fresh RS-485 read
        now[0] += 0.06
        bus.registers[0] = 155
        r4 = await plugin.execute_command("read_sensor", {"sensor_id": "ai01"})
        assert r4["success"] and r4["data"] == 155.0
        assert bus.reads == 2

        # Explicit force_refresh bypasses fresh cache
        bus.registers[0] = 177
        r5 = await plugin.execute_command("read_sensor", {"sensor_id": "ai01", "force_refresh": True})
        assert r5["success"] and r5["data"] == 177.0
        assert bus.reads == 3

    @pytest.mark.asyncio
    async def test_adc_config_snapshot_cached_until_write(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_pimodbus(monkeypatch)
        cfg = PluginConfig(
            plugin_id="modbus-adc",
            connection_type="modbus-rtu",
            connection_params={"serial_port": "/dev/ttyUSB0", "baudrate": 4800},
        )
        plugin = ModbusAdcPlugin(cfg)
        bus = _FakeAdcBus()
        plugin._bus = bus
        clock = _FakeClock()
        plugin._rtu_pacer = RtuTurnaroundPacer(clock=clock, sleeper=clock.sleep)

        s1 = await plugin.execute_command("read_config_snapshot", {})
        s2 = await plugin.execute_command("read_config_snapshot", {})
        assert s1["success"] and s2["success"]
        assert len(bus.calls) == 2

        w = await plugin.execute_command("write_holding_register", {"address": 0x2000, "value": 1})
        assert w["success"]
        s3 = await plugin.execute_command("read_config_snapshot", {})
        assert s3["success"]
        assert len(bus.calls) == 5


class TestModbusIoSnapshotAndPacing:
    @pytest.mark.asyncio
    async def test_io_snapshot_skips_static_config_reads_and_enforces_4800_t35(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_fake_pimodbus(monkeypatch)
        cfg = PluginConfig(
            plugin_id="modbus-io",
            connection_type="modbus-rtu",
            connection_params={"serial_port": "/dev/ttyACM0", "baudrate": 4800, "device_id": 1},
        )
        plugin = ModbusPlugin(cfg)
        bus = _FakeIoBus()
        plugin._bus = bus
        plugin._mode = "rtu"
        clock = _FakeClock()
        plugin._rtu_pacer = RtuTurnaroundPacer(clock=clock, sleeper=clock.sleep)

        assert plugin.rtu_turnaround_us() == 8_021

        # First snapshot performs 5 RTU transactions (2 dynamic + 3 static config)
        first = await plugin.execute_command("read_io_snapshot", {})
        assert first["success"] is True
        assert len(bus.calls) == 5
        # 4 inter-frame sleeps between 5 sequential frames, each exactly 8021 us
        assert len(clock.sleeps) == 4
        assert all(pytest.approx(0.008021, rel=1e-6) == delay for delay in clock.sleeps)

        # Second snapshot skips static config reads -> only 2 dynamic frames!
        second = await plugin.execute_command("read_io_snapshot", {})
        assert second["success"] is True
        assert len(bus.calls) == 7
        assert [name for name, _ in bus.calls[5:]] == ["read_coils", "read_discrete_inputs"]

        # Writing a holding register invalidates cached static config -> next snapshot re-reads 5 frames
        wr = await plugin.execute_command("write_holding_register", {"address": 0x1000, "value": 0})
        assert wr["success"] is True
        third = await plugin.execute_command("read_io_snapshot", {})
        assert third["success"] is True
        assert len(bus.calls) == 13
