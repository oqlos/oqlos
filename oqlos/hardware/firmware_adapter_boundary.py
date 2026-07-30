"""Typed and sanitized helpers for the legacy firmware HTTP adapter."""

from __future__ import annotations

import re
from typing import Any

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore


class FirmwareAdapterError(RuntimeError):
    """Expected failure at the legacy firmware HTTP boundary."""


class FirmwareDependencyError(FirmwareAdapterError):
    """The HTTP client required by the adapter is unavailable."""


class FirmwarePayloadError(FirmwareAdapterError):
    """A firmware endpoint returned an invalid payload."""


class FirmwareRejectedError(FirmwareAdapterError):
    """A firmware endpoint explicitly rejected a command."""


HTTP_STATUS_ERRORS = (httpx.HTTPStatusError,) if httpx is not None else ()
FIRMWARE_OPERATION_ERRORS = (
    OSError,
    FirmwareAdapterError,
    *((httpx.HTTPError,) if httpx is not None else ()),
)


def response_mapping(response: Any) -> dict[str, Any]:
    """Decode a response without letting malformed JSON masquerade as success."""
    try:
        payload = response.json()
    except (TypeError, ValueError) as exc:
        raise FirmwarePayloadError("invalid firmware JSON response") from exc
    if not isinstance(payload, dict):
        raise FirmwarePayloadError("firmware response must be an object")
    return payload


def sensor_value(payload: dict[str, Any], key: str) -> float:
    try:
        return float(payload.get(key, 0.0))
    except (TypeError, ValueError) as exc:
        raise FirmwarePayloadError("invalid firmware sensor value") from exc


def firmware_failure(reason: str) -> dict[str, Any]:
    """Return the stable internal envelope consumed by the legacy OQL executor."""
    return {
        "ok": False,
        "detail": "Required hardware is unavailable",
        "data": {},
        "status": 503,
        "error_code": "C2004-HW-0012",
        "issue_code": reason,
        "architecture": "SOA",
        "layer": "firmware",
        "component": "firmware-adapter",
        "stage": "command.execute",
        "problem_source": "hardware-runtime://firmware-adapter",
        "operation_id": "firmware.command.dispatch",
        "owner": "owner://domain/hardware",
        "retryable": False,
    }


def extract_failure_message(data: dict[str, Any]) -> Any:
    """Extract a failure message from an API response dict, or None."""

    def first_nonempty(source: dict[str, Any], *keys: str) -> Any:
        return next((source.get(key) for key in keys if source.get(key)), None)

    message: Any = None
    ok = data.get("ok")
    if isinstance(ok, dict) and ok.get("success") is False:
        message = first_nonempty(ok, "error", "message", "detail")
    elif ok is False:
        message = first_nonempty(data, "error", "message", "detail")
    if data.get("success") is False:
        message = first_nonempty(data, "error", "message", "detail") or message
    status = data.get("status")
    if isinstance(status, str) and status.lower() in {"error", "failed", "failure"}:
        message = first_nonempty(data, "error", "message", "detail") or message
    return message


def parse_numeric(value: Any) -> float:
    """Parse the first number from OQL values such as ``7.0 mbar``."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"[-+]?\d*\.?\d+", str(value))
    return float(match.group()) if match else 0.0
