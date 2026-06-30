from __future__ import annotations

from typing import Any

from oqlos.hardware.client.errors import HardwareProxyError


def extract_position(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    data = payload.get("data")
    if isinstance(data, dict) and "position" in data:
        return int(data["position"])
    if "position" in payload:
        return int(payload["position"])
    return 0


def command_error_message(result: dict[str, Any]) -> str | None:
    """Collect the best available error string from plugin or sidecar payloads."""
    for key in ("error", "message", "detail"):
        value = result.get(key)
        if value not in (None, ""):
            return str(value)

    data = result.get("data")
    if isinstance(data, dict):
        for key in ("error", "message", "detail"):
            value = data.get(key)
            if value not in (None, ""):
                return str(value)
        if data.get("connected") is False:
            return str(data.get("error") or "Tic249 motor is not connected")

    nested_ok = result.get("ok")
    if isinstance(nested_ok, dict):
        for key in ("error", "message", "detail"):
            value = nested_ok.get(key)
            if value not in (None, ""):
                return str(value)
        if nested_ok.get("success") is False:
            return command_error_message(nested_ok)

    base_url = result.get("base_url")
    path = result.get("path")
    if base_url and path:
        return f"Tic249 command failed ({base_url}{path})"
    return None


def generic_failure_hint(result: dict[str, Any]) -> str:
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    hints: list[str] = []
    for key in ("connected", "status", "energized", "error", "message"):
        if key in result and result[key] not in (None, ""):
            hints.append(f"{key}={result[key]!r}")
        elif key in data and data[key] not in (None, ""):
            hints.append(f"{key}={data[key]!r}")
    if hints:
        return f"Tic249 de-energize failed ({', '.join(hints)})"
    return (
        "Tic249 de-energize failed (no detail from plugin; "
        "check motor-tic249 health, Tic sidecar, and USB device)"
    )


def command_failure(result: Any) -> str | None:
    if not isinstance(result, dict):
        return None
    if result.get("idempotent_success"):
        return None
    if result.get("success") is False or result.get("ok") is False:
        return command_error_message(result) or generic_failure_hint(result)
    data = result.get("data")
    if isinstance(data, dict) and data.get("success") is False:
        return command_error_message(data) or command_error_message(result) or generic_failure_hint(result)
    return None


def plugin_unavailable_error(exc: HardwareProxyError) -> bool:
    if exc.status_code == 404:
        return True
    detail = exc.detail
    if isinstance(detail, str):
        text = detail
    elif isinstance(detail, dict):
        text = str(
            detail.get("error")
            or detail.get("message")
            or detail.get("detail")
            or (detail.get("response") or {}).get("detail")
            or ""
        )
    else:
        text = str(detail or "")
    return "no active instance" in text.lower()


def normalize_target_state(command: str, result: Any) -> Any:
    if not isinstance(result, dict):
        return result
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    status = str(result.get("status") or data.get("status") or "").lower()
    disable_commands = {"motor_disable", "deenergize", "disable", "standby"}
    stop_commands = {"lung_stop", "stop", "emergency_stop"}
    already_deenergized = status in {"de-energized", "disabled"} or data.get("energized") is False
    already_stopped = status in {"stopped", "idle"}
    if command in disable_commands and already_deenergized and not result.get("error"):
        return {**result, "ok": True, "success": True, "idempotent_success": True}
    if command in stop_commands and already_stopped and not result.get("error"):
        return {**result, "ok": True, "success": True, "idempotent_success": True}
    return result
