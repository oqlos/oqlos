"""Plugin health interpretation helpers for hardware diagnosis."""

from __future__ import annotations

from typing import Any, Literal

from oqlos.hardware.diagnosis_types import DeviceStatus

# True USB/serial handle death after re-enumeration or I/O on a dead fd.
_STALE_SERIAL_MARKERS = (
    "errno 19",
    "no such device",
    "errno 5",
    "input/output error",
    "serial_handle_stale",
    "serial-stale",
)

# RTU bus open but slave silent (wiring, power, wrong id/baud).
_NO_RESPONSE_MARKERS = (
    "timed out",
    "timeout",
    "no response",
    "write timeout",
    "did not answer",
)

# HTTP sidecar / connect failures (motors etc.).
_SIDECAR_DOWN_MARKERS = (
    "http 503",
    "http 500",
    "connection attempts failed",
    "connect returned false",
)

# Broad set used only to force repair classification (not for "stale serial" label).
_REPAIR_MARKERS = _STALE_SERIAL_MARKERS + _NO_RESPONSE_MARKERS + _SIDECAR_DOWN_MARKERS

# Back-compat alias for older imports that expected a single list.
_STALE_MARKERS = _REPAIR_MARKERS

ModbusFailureKind = Literal[
    "serial_handle_stale",
    "device_no_response",
    "not_connected",
    "unhealthy",
]


def health_map(identify: dict[str, Any]) -> dict[str, Any]:
    diagnostics = identify.get("diagnostics") if isinstance(identify, dict) else {}
    health = diagnostics.get("health") if isinstance(diagnostics, dict) else {}
    return health if isinstance(health, dict) else {}


def message_text(message: Any) -> str:
    return str(message or "").strip()


def message_lower_text(message: Any) -> str:
    return message_text(message).lower()


def is_stale_hardware_message(message: Any) -> bool:
    """True only for dead serial/USB handles — not for RTU device silence."""
    text = message_lower_text(message)
    return any(marker in text for marker in _STALE_SERIAL_MARKERS)


def is_no_response_hardware_message(message: Any) -> bool:
    text = message_lower_text(message)
    return any(marker in text for marker in _NO_RESPONSE_MARKERS)


def is_stale_hardware_entry(entry: dict[str, Any] | None) -> bool:
    if not isinstance(entry, dict):
        return False
    return is_stale_hardware_message(entry.get("message"))


def is_no_response_hardware_entry(entry: dict[str, Any] | None) -> bool:
    if not isinstance(entry, dict):
        return False
    return is_no_response_hardware_message(entry.get("message"))


def classify_modbus_failure(entry: dict[str, Any] | None) -> ModbusFailureKind:
    """Map a modbus plugin health entry to a stable diagnosis kind."""
    if not isinstance(entry, dict):
        return "not_connected"
    msg = message_lower_text(entry.get("message"))
    status = str(entry.get("status") or "").lower()
    if is_stale_hardware_message(msg):
        return "serial_handle_stale"
    if is_no_response_hardware_message(msg):
        return "device_no_response"
    if "not connected" in msg or status in {"offline", "disabled"}:
        return "not_connected"
    if status in {"error", "offline", "disabled", "no-access", "device-stale"}:
        return "unhealthy"
    if entry.get("compatible") is not True:
        return "unhealthy"
    return "unhealthy"


def modbus_issue_code(kind: ModbusFailureKind) -> str:
    return {
        "serial_handle_stale": "hw_modbus_serial_handle_stale",
        "device_no_response": "hw_modbus_device_no_response",
        "not_connected": "hw_modbus_not_connected",
        "unhealthy": "hw_modbus_unhealthy",
    }[kind]


def modbus_issue_text(plugin_id: str, kind: ModbusFailureKind) -> str:
    label = "IO" if plugin_id == "modbus-io" else "ADC" if plugin_id == "modbus-adc" else plugin_id
    if kind == "serial_handle_stale":
        return f"Modbus {label}: martwy handle USB/RS485 (re-enumeracja) — reconnect OqlOS."
    if kind == "device_no_response":
        return (
            f"Modbus {label}: adapter otwarty, urządzenie nie odpowiada na RTU "
            "(zasilanie 7–36 V, A/B/GND, slave id, baud 9600)."
        )
    if kind == "not_connected":
        return f"Modbus {label}: brak połączenia z portem szeregowym."
    return f"Modbus {label}: stan niezdrowy — wymaga naprawy."


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
    message = message_lower_text(entry.get("message"))
    if any(marker in message for marker in _REPAIR_MARKERS):
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
    return message_lower_text(entry.get("message") or entry.get("status"))


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
