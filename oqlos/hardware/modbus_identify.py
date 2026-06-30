"""Modbus port inference and USB serial hints for hardware identify."""

from __future__ import annotations

from typing import Any

_MODBUS_SERIAL_HINTS = (
    "prolific",
    "usb-serial",
    "usb serial",
    "usb single serial",
    "ch340",
    "cp210",
    "ft232",
    "rs485",
)
_MODBUS_SERIAL_EXCLUDE = (
    "pololu",
    "tic t249",
    "tic249",
    "holtek",
    "logitech",
    "yubico",
    "hub",
    "keyboard",
    "mouse",
    "audio",
    "nvidia",
)


def _usb_blob(device: dict[str, Any]) -> str:
    return " ".join(
        str(device.get(key) or "")
        for key in ("manufacturer", "product", "vendor_id", "product_id", "path")
    ).lower()


def _is_modbus_candidate(device: "dict[str, Any]") -> bool:
    """Return True if a USB device looks like a Modbus serial adapter."""
    blob = _usb_blob(device)
    if not blob:
        return False
    if any(token in blob for token in _MODBUS_SERIAL_EXCLUDE):
        return False
    return any(token in blob for token in _MODBUS_SERIAL_HINTS)


def _device_to_candidate(device: "dict[str, Any]") -> "dict[str, str]":
    """Convert a USB device dict to a Modbus candidate entry."""
    vendor = str(device.get("vendor_id") or "")
    product_id = str(device.get("product_id") or "")
    return {
        "id": f"{vendor}:{product_id}" if vendor and product_id else "",
        "manufacturer": str(device.get("manufacturer") or ""),
        "product": str(device.get("product") or ""),
        "path": str(device.get("path") or ""),
    }


def collect_modbus_serial_candidates(diagnostics: dict[str, Any] | None) -> list[dict[str, str]]:
    if not isinstance(diagnostics, dict):
        return []
    raw_devices = diagnostics.get("usb_devices")
    if not isinstance(raw_devices, list):
        return []
    return [
        _device_to_candidate(device)
        for device in raw_devices
        if isinstance(device, dict) and _is_modbus_candidate(device)
    ]


def _infer_modbus_serial_port(platform: dict[str, Any]) -> str:
    for key in ("modbus_io_serial_port", "modbus_bus_serial_port", "modbus_adc_serial_port"):
        value = str(platform.get(key) or "").strip()
        if value:
            return value
    serial_ports = platform.get("serial_ports")
    if not isinstance(serial_ports, list):
        return ""
    normalized = [str(port).strip() for port in serial_ports if str(port).strip()]
    for preferred in ("/dev/ttyACM1", "/dev/ttyUSB0"):
        if preferred in normalized:
            return preferred
    return normalized[0] if normalized else ""


def enrich_platform_modbus_ports(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return payload
    platform = payload.get("platform")
    if not isinstance(platform, dict):
        return payload
    inferred = _infer_modbus_serial_port(platform)
    if not inferred:
        return payload
    if not str(platform.get("modbus_bus_serial_port") or "").strip():
        platform["modbus_bus_serial_port"] = inferred
    if not str(platform.get("modbus_io_serial_port") or "").strip():
        platform["modbus_io_serial_port"] = inferred
    if not str(platform.get("modbus_adc_serial_port") or "").strip():
        platform["modbus_adc_serial_port"] = inferred
    return payload


def enrich_modbus_serial_hints(payload: dict[str, Any]) -> dict[str, Any]:
    diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), dict) else None
    candidates = collect_modbus_serial_candidates(diagnostics)
    if not candidates:
        return payload
    for adapter in payload.get("adapters") or []:
        if adapter.get("id") != "modbus-io":
            continue
        probe = adapter.setdefault("probe", {})
        probe["serial_candidates"] = candidates
        if not probe.get("connected") and not probe.get("reason"):
            probe["reason"] = "no USB serial ports detected"
        if not probe.get("connected"):
            primary = candidates[0]
            probe["hint"] = (
                f"USB adapter visible on bus ({primary.get('product') or primary.get('id')}) "
                "but no /dev/ttyUSB* enumerated — check container device passthrough"
            )
        break
    return payload


def enrich_modbus_identify(payload: dict[str, Any]) -> dict[str, Any]:
    payload = enrich_platform_modbus_ports(payload)
    return enrich_modbus_serial_hints(payload)
