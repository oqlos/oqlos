"""Modbus RTU helpers for DRI0050 motor plugin (pimodbus shared bus)."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from .base import PluginHealth, PluginStatus

try:
    from pimodbus.client import get_rtu_bus
    from pimodbus.config import RtuBusSettings

    _HAS_PIMODBUS = True
except ImportError:  # pragma: no cover
    get_rtu_bus = None  # type: ignore
    RtuBusSettings = None  # type: ignore
    _HAS_PIMODBUS = False


def duty_pct_to_register(power_pct: float) -> int:
    """Map 0–100% pump power to DRI0050 duty register (0–255)."""
    return int(round(max(0.0, min(100.0, power_pct)) * 2.55))


async def connect_modbus_bus(
    *,
    serial_port: str,
    baudrate: int,
    parity: str,
    timeout: float,
) -> Any | None:
    """Connect to the shared RTU bus; returns bus handle or None."""
    if not _HAS_PIMODBUS:
        return None
    settings = RtuBusSettings(
        serial_port=serial_port,
        baudrate=baudrate,
        parity=parity,
        timeout=timeout,
    )
    bus = get_rtu_bus(settings)
    if await bus.connect():
        return bus
    return None


async def modbus_health_check(
    bus: Any | None,
    *,
    slave: int,
    pid_reg: int,
) -> PluginHealth:
    """Read PID holding register as a Modbus RTU health probe."""
    if bus is None:
        return PluginHealth(
            status=PluginStatus.ERROR,
            message="Motor modbus bus not connected",
            compatible=False,
        )
    try:
        rr = await bus.call(
            "read_holding_registers",
            address=pid_reg,
            count=1,
            device_id=slave,
        )
    except asyncio.TimeoutError:
        return PluginHealth(
            status=PluginStatus.ERROR,
            message=f"Motor (modbus-rtu) PID read timed out (slave={slave}, reg=0x{pid_reg:04X})",
            details={"slave": slave, "register": pid_reg},
            compatible=False,
        )
    if rr is None or (hasattr(rr, "isError") and rr.isError()):
        return PluginHealth(
            status=PluginStatus.ERROR,
            message=f"Motor (modbus-rtu) PID read failed: {rr}",
            details={"slave": slave, "register": pid_reg},
            compatible=False,
        )
    pid = getattr(rr, "registers", [None])[0]
    return PluginHealth(
        status=PluginStatus.CONNECTED,
        message=(
            f"Motor (modbus-rtu) is healthy, PID=0x{pid:04X}"
            if pid is not None
            else "Motor (modbus-rtu) connected (PID unknown)"
        ),
        details={"slave": slave, "pid": pid},
        compatible=True,
    )


async def modbus_set_speed(
    bus: Any | None,
    *,
    slave: int,
    duty_reg: int,
    enable_reg: int,
    power_pct: float,
    start_time: float,
) -> dict[str, Any]:
    """Write duty + enable registers for set_speed."""
    if bus is None:
        return {"success": False, "error": "Motor modbus bus not connected"}
    duty_value = duty_pct_to_register(power_pct)
    try:
        wr_duty = await bus.call(
            "write_register",
            address=duty_reg,
            value=duty_value,
            device_id=slave,
        )
        if hasattr(wr_duty, "isError") and wr_duty.isError():
            return {"success": False, "error": f"write Duty failed: {wr_duty}"}
        wr_en = await bus.call(
            "write_register",
            address=enable_reg,
            value=1,
            device_id=slave,
        )
        if hasattr(wr_en, "isError") and wr_en.isError():
            return {"success": False, "error": f"write Enable failed: {wr_en}"}
    except Exception as exc:
        return {"success": False, "error": f"modbus exception: {exc}"}
    duration_ms = (time.monotonic() - start_time) * 1000
    return {
        "success": True,
        "data": {
            "power_pct": power_pct,
            "pwm_value": duty_value,
            "duty_register": duty_reg,
            "slave": slave,
            "duration_ms": duration_ms,
            "timestamp": time.time(),
        },
    }


async def modbus_stop(
    bus: Any | None,
    *,
    slave: int,
    duty_reg: int,
    enable_reg: int,
    start_time: float,
) -> dict[str, Any]:
    """Write duty=0 and enable=0."""
    if bus is None:
        return {"success": False, "error": "Motor modbus bus not connected"}
    try:
        await bus.call("write_register", address=duty_reg, value=0, device_id=slave)
        await bus.call("write_register", address=enable_reg, value=0, device_id=slave)
    except Exception as exc:
        return {"success": False, "error": f"modbus exception: {exc}"}
    duration_ms = (time.monotonic() - start_time) * 1000
    return {
        "success": True,
        "data": {
            "stopped": True,
            "slave": slave,
            "duration_ms": duration_ms,
            "timestamp": time.time(),
        },
    }


async def modbus_status(
    bus: Any | None,
    *,
    slave: int,
    duty_reg: int,
    start_time: float,
) -> dict[str, Any]:
    """Read duty, frequency, and enable holding registers."""
    if bus is None:
        return {"success": False, "error": "Motor modbus bus not connected"}
    try:
        rr = await bus.call(
            "read_holding_registers",
            address=duty_reg,
            count=3,
            device_id=slave,
        )
        if hasattr(rr, "isError") and rr.isError():
            return {"success": False, "error": f"read failed: {rr}"}
        regs = getattr(rr, "registers", [])
        duty = regs[0] if len(regs) > 0 else 0
        freq = regs[1] if len(regs) > 1 else 0
        enable = regs[2] if len(regs) > 2 else 0
    except Exception as exc:
        return {"success": False, "error": f"modbus exception: {exc}"}
    duration_ms = (time.monotonic() - start_time) * 1000
    return {
        "success": True,
        "data": {
            "duty": duty,
            "power_pct": round(duty / 2.55, 2),
            "frequency_hz": freq,
            "enabled": bool(enable),
            "slave": slave,
            "duration_ms": duration_ms,
            "timestamp": time.time(),
        },
    }
