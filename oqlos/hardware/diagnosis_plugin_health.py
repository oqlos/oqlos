"""Plugin health interpretation helpers for hardware diagnosis."""

from __future__ import annotations

from typing import Any

from oqlos.hardware.diagnosis_types import DeviceStatus

_STALE_MARKERS = (
    "errno 19",
    "no such device",
    "errno 5",
    "input/output error",
    "serial_handle_stale",
    "serial-stale",
    "http 503",
    "http 500",
    "timed out",
    "write timeout",
)


def health_map(identify: dict[str, Any]) -> dict[str, Any]:
    diagnostics = identify.get("diagnostics") if isinstance(identify, dict) else {}
    health = diagnostics.get("health") if isinstance(diagnostics, dict) else {}
    return health if isinstance(health, dict) else {}


def is_stale_hardware_message(message: Any) -> bool:
    return any(marker in str(message or "").lower() for marker in _STALE_MARKERS)


def is_stale_hardware_entry(entry: dict[str, Any] | None) -> bool:
    if not isinstance(entry, dict):
        return False
    return is_stale_hardware_message(entry.get("message"))


def plugin_is_healthy(entry: dict[str, Any] | None) -> bool:
    if not isinstance(entry, dict):
        return False
    return entry.get("compatible") is True and str(entry.get("status") or "").lower() in {
        "connected",
        "ok",
    }


def plugin_needs_repair(plugin_id: str, entry: dict[str, Any] | None) -> bool:
    if not isinstance(entry, dict):
        return True
    status = str(entry.get("status") or "").lower()
    message = str(entry.get("message") or "").lower()
    if any(marker in message for marker in _STALE_MARKERS):
        return True
    if entry.get("compatible") is not True:
        return True
    if status in {"error", "offline", "disabled", "no-access", "device-stale"}:
        return True
    return False


def modbus_plugins_need_repair(identify: dict[str, Any] | None) -> bool:
    health = health_map(identify or {})
    for key in ("modbus-io", "modbus-adc"):
        if plugin_needs_repair(key, health.get(key) if isinstance(health.get(key), dict) else {}):
            return True
    return False


def message_lower(entry: dict | None) -> str:
    if not entry:
        return ""
    return str(entry.get("message") or entry.get("status") or "").lower()


def infer_status(plugin_id: str, entry: dict | None, *, present: bool = True) -> DeviceStatus:
    if not present:
        return "not_present"
    if not entry:
        return "unknown"
    if plugin_needs_repair(plugin_id, entry):
        return "error"
    status = str(entry.get("status") or "").lower()
    if status in {"connected", "ok"} and entry.get("compatible") is not False:
        return "ok"
    return "degraded"
