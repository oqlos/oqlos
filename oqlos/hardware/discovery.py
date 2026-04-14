"""Helpers for discovering the Waveshare Modbus RTU IO module on local serial ports."""

from __future__ import annotations

import glob
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MODBUS_SERIAL = os.getenv("MODBUS_SERIAL_PORT", "/dev/ttyACM1")
DEFAULT_MODBUS_BAUD = int(os.getenv("MODBUS_BAUD", "19200"))
DEFAULT_MODBUS_PARITY = os.getenv("MODBUS_PARITY", "N").upper()
DEFAULT_MODBUS_DEVICE_ID = int(os.getenv("MODBUS_DEVICE_ID", "1"))


def _unique_preserving_order(values: list[Any]) -> list[Any]:
    seen: set[Any] = set()
    ordered: list[Any] = []
    for value in values:
        if value in seen or value in (None, ""):
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def list_serial_ports() -> list[dict[str, Any]]:
    """Return USB serial ports with best-effort metadata."""
    try:
        from serial.tools import list_ports  # type: ignore

        ports: list[dict[str, Any]] = []
        for port in list_ports.comports():
            device = getattr(port, "device", "") or ""
            if not (device.startswith("/dev/ttyACM") or device.startswith("/dev/ttyUSB")):
                continue
            ports.append({
                "device": device,
                "manufacturer": getattr(port, "manufacturer", "") or "",
                "product": getattr(port, "product", "") or getattr(port, "description", "") or "",
                "serial_number": getattr(port, "serial_number", "") or "",
                "vid": getattr(port, "vid", None),
                "pid": getattr(port, "pid", None),
            })
        if ports:
            return sorted(ports, key=lambda item: item["device"])
    except Exception:
        logger.debug("pyserial list_ports unavailable", exc_info=True)

    fallback_ports = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
    return [{"device": device, "manufacturer": "", "product": "", "serial_number": ""} for device in fallback_ports]


def _build_probe_candidates(
    ports: list[dict[str, Any]],
    preferred_port: str | None,
    preferred_baud: int | None,
    preferred_parity: str | None,
) -> tuple[dict[str, Any], list[tuple[str, int, str]]]:
    """Build ordered list of (port, baudrate, parity) candidates to probe."""
    port_by_name = {port["device"]: port for port in ports}
    ordered_ports = _unique_preserving_order([
        preferred_port,
        DEFAULT_MODBUS_SERIAL,
        *[port["device"] for port in ports],
    ])
    baud_candidates = _unique_preserving_order([
        preferred_baud,
        DEFAULT_MODBUS_BAUD,
        19200,
        9600,
    ])
    parity_candidates = _unique_preserving_order([
        (preferred_parity or "").upper() or None,
        DEFAULT_MODBUS_PARITY,
        "N",
        "E",
    ])

    candidates: list[tuple[str, int, str]] = []
    for serial_port in ordered_ports:
        if serial_port not in port_by_name:
            continue
        for baudrate in baud_candidates:
            for parity in parity_candidates:
                candidates.append((serial_port, int(baudrate), str(parity)))

    return port_by_name, candidates


def _make_pymodbus_fallback_result(first_port: dict[str, Any]) -> dict[str, Any]:
    """Return fallback result when pymodbus is not installed."""
    return {
        "connected": True,
        "adapter": first_port.get("product") or first_port.get("manufacturer") or "USB serial adapter",
        "usb_product": first_port.get("product", ""),
        "usb_serial": first_port.get("serial_number", ""),
        "serial_port": first_port["device"],
        "modbus_device_responds": False,
        "reason": "pymodbus not installed",
        "note": "USB serial adapter detected, but pymodbus is unavailable",
    }


def _make_probe_success_result(
    port_meta: dict[str, Any],
    serial_port: str,
    baudrate: int,
    parity: str,
) -> dict[str, Any]:
    """Return success result when Modbus device responds."""
    adapter_name = port_meta.get("product") or port_meta.get("manufacturer") or "USB serial adapter"
    return {
        "connected": True,
        "adapter": adapter_name,
        "usb_product": port_meta.get("product", ""),
        "usb_serial": port_meta.get("serial_number", ""),
        "serial_port": serial_port,
        "baudrate": baudrate,
        "parity": parity,
        "device_id": DEFAULT_MODBUS_DEVICE_ID,
        "modbus_device_responds": True,
        "note": f"Modbus RTU responding on {serial_port} @ {baudrate} 8{parity}1",
    }


def _make_probe_failure_result(
    first_port: dict[str, Any],
    last_error: str,
) -> dict[str, Any]:
    """Return failure result after exhausting all candidates."""
    adapter_name = first_port.get("product") or first_port.get("manufacturer") or "USB serial adapter"
    return {
        "connected": True,
        "adapter": adapter_name,
        "usb_product": first_port.get("product", ""),
        "usb_serial": first_port.get("serial_number", ""),
        "serial_port": first_port["device"],
        "baudrate": DEFAULT_MODBUS_BAUD,
        "parity": DEFAULT_MODBUS_PARITY,
        "device_id": DEFAULT_MODBUS_DEVICE_ID,
        "modbus_device_responds": False,
        "note": "No Modbus RTU response on detected serial ports",
        "reason": last_error or "device did not respond",
    }


def _try_modbus_connection(
    serial_port: str,
    baudrate: int,
    parity: str,
    timeout: float,
) -> tuple[bool, str, Any]:
    """Try a single Modbus connection attempt. Returns (success, error, result)."""
    from pymodbus.client import ModbusSerialClient  # type: ignore

    client: Any = None
    try:
        client = ModbusSerialClient(
            port=serial_port,
            baudrate=baudrate,
            stopbits=1,
            bytesize=8,
            parity=parity,
            timeout=timeout,
        )
        if not client.connect():
            return False, f"{serial_port} busy or unavailable", None

        result = client.read_coils(address=0, count=1, device_id=DEFAULT_MODBUS_DEVICE_ID)
        if result and not result.isError():
            return True, "", result
        return False, str(result), None

    except PermissionError:
        raise  # Re-raise to be handled by caller
    except Exception as exc:
        return False, str(exc), None
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def probe_waveshare_modbus(
    preferred_port: str | None = None,
    preferred_baud: int | None = None,
    preferred_parity: str | None = None,
    timeout: float = 0.35,
) -> dict[str, Any]:
    """Probe serial ports and return the first working Modbus RTU configuration."""
    ports = list_serial_ports()
    if not ports:
        return {"connected": False, "reason": "no USB serial ports detected"}

    port_by_name, candidates = _build_probe_candidates(
        ports, preferred_port, preferred_baud, preferred_parity
    )

    try:
        from pymodbus.client import ModbusSerialClient  # type: ignore
    except Exception:
        first_port = list(port_by_name.values())[0]
        return _make_pymodbus_fallback_result(first_port)

    first_port = list(port_by_name.values())[0]
    last_error = ""

    for serial_port, baudrate, parity in candidates:
        port_meta = port_by_name.get(serial_port)
        if port_meta is None:
            continue

        try:
            success, error, _ = _try_modbus_connection(serial_port, baudrate, parity, timeout)
            if success:
                return _make_probe_success_result(port_meta, serial_port, baudrate, parity)
            last_error = error
        except PermissionError:
            return {
                "connected": False,
                "serial_port": serial_port,
                "baudrate": baudrate,
                "parity": parity,
                "reason": f"permission denied on {serial_port}",
            }

    return _make_probe_failure_result(first_port, last_error)