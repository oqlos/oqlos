"""Modbus RS485 topology and serial port resolution."""

from __future__ import annotations

import os
from typing import Any

from oqlos.config import get_settings

_settings = get_settings()

def _parse_csv_ints(raw: str | None, default: list[int]) -> list[int]:
    values: list[int] = []
    for part in str(raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            value = int(part)
        except ValueError:
            continue
        if value > 0 and value not in values:
            values.append(value)
    return values or list(default)


def _modbus_io_device_ids() -> list[int]:
    configured = os.getenv("OQLOS_MODBUS_IO_DEVICE_IDS") or os.getenv("MODBUS_IO_DEVICE_IDS")
    return _parse_csv_ints(configured, [_settings.modbus_device_id])


def _modbus_topology_mode() -> str:
    """How RS485 wiring is interpreted: auto-detect, one adapter, or point-to-point."""
    raw = (os.getenv("OQLOS_MODBUS_TOPOLOGY") or os.getenv("MODBUS_TOPOLOGY") or "auto").strip().lower()
    if raw in {"shared", "shared-bus", "one-bus", "single-adapter", "single"}:
        return "shared-bus"
    if raw in {"separate", "separate-adapters", "p2p", "point-to-point", "dual-adapter", "dual"}:
        return "separate-adapters"
    return "auto"


def _apply_modbus_topology(
    mode: str, bus_port: str, io_port: str, adc_port: str
) -> tuple[str, str, str]:
    """Return (io_port, adc_port, topology) after applying topology-mode rules."""
    if mode == "shared-bus":
        shared = bus_port or io_port or adc_port
        return shared, shared, "shared-bus"
    if mode == "separate-adapters":
        adc_port = adc_port or io_port
        return io_port, adc_port, "separate-adapters"
    if bus_port:
        return bus_port, bus_port, "shared-bus"
    adc_port = adc_port or io_port
    topology = (
        "separate-adapters"
        if (io_port and adc_port and io_port != adc_port)
        else "shared-bus"
    )
    return io_port, adc_port, topology


def _modbus_runtime_serial_ports() -> dict[str, Any]:
    """Resolve IO vs ADC serial ports for shared-bus or separate USB-RS485 adapters."""
    bus_port = (
        os.getenv("OQLOS_MODBUS_BUS_SERIAL_PORT")
        or os.getenv("MODBUS_BUS_SERIAL_PORT")
        or os.getenv("OQLOS_MODBUS_SHARED_SERIAL_PORT")
        or os.getenv("MODBUS_SHARED_SERIAL_PORT")
        or ""
    ).strip()
    io_port = (
        os.getenv("OQLOS_MODBUS_SERIAL_PORT")
        or os.getenv("MODBUS_SERIAL_PORT")
        or str(_settings.modbus_serial_port or "")
    ).strip()
    adc_port = (
        os.getenv("OQLOS_MODBUS_ADC_SERIAL_PORT")
        or os.getenv("MODBUS_ADC_SERIAL_PORT")
        or str(_settings.modbus_adc_serial_port or "")
    ).strip()
    mode = _modbus_topology_mode()

    io_port, adc_port, topology = _apply_modbus_topology(mode, bus_port, io_port, adc_port)

    return {
        "io_serial_port": io_port,
        "adc_serial_port": adc_port,
        "shared_serial_port": io_port if topology == "shared-bus" else "",
        "topology": topology,
        "topology_mode": mode,
    }
