"""piRTC sidecar probe for hardware identify (Waveshare RTC WatchDog HAT)."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

RTC_PERIPHERAL_ID = "rtc"
PIRTC_DEFAULT_URL = "http://localhost:8125"
_REQUEST_TIMEOUT_SECONDS = 2.0


def get_pirtc_base_url() -> str:
    return os.environ.get("PIRTC_API_URL", PIRTC_DEFAULT_URL).rstrip("/")


_RTC_COMMAND_MAP: dict[str, tuple[str, str]] = {
    "read_status": ("GET", "/api/status"),
    "read_time": ("GET", "/api/rtc/time"),
    "read_date": ("GET", "/api/rtc/date"),
    "read_temperature": ("GET", "/api/rtc/temperature"),
    "read_watchdog": ("GET", "/api/watchdog/status"),
    "sync_to_system": ("POST", "/api/rtc/sync-to-system"),
    "sync_from_system": ("POST", "/api/rtc/sync-from-system"),
    "feed_watchdog": ("POST", "/api/watchdog/feed"),
    "restart": ("POST", "/api/reinit"),
    "reinit": ("POST", "/api/reinit"),
}


def _pirtc_request_sync(
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    timeout: float = _REQUEST_TIMEOUT_SECONDS,
) -> tuple[bool, dict[str, Any], str | None]:
    url = f"{get_pirtc_base_url()}{path}"
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.request(method, url, json=json_body)
        try:
            payload = response.json()
        except ValueError:
            payload = {"raw": response.text}
        if response.status_code >= 400:
            err = (payload.get("detail") if isinstance(payload, dict) else None) or f"HTTP {response.status_code}"
            return False, payload if isinstance(payload, dict) else {"raw": payload}, str(err)
        return True, payload if isinstance(payload, dict) else {"data": payload}, None
    except httpx.HTTPError as exc:
        logger.warning("piRTC request failed: %s %s — %s", method, url, exc)
        return False, {}, f"piRTC unreachable at {url}: {exc}"


def build_rtc_peripheral_status() -> dict[str, Any]:
    """Return the runtime status payload for the RTC sidecar."""
    ok, payload, error = _pirtc_request_sync("GET", "/api/status", timeout=3.0)
    if not ok:
        return {
            "ok": False,
            "peripheral_id": RTC_PERIPHERAL_ID,
            "error": error or "piRTC unreachable",
            "result": {},
        }

    rtc = payload.get("rtc", {}) if isinstance(payload, dict) else {}
    watchdog = payload.get("watchdog", {}) if isinstance(payload, dict) else {}
    time_ok, time_payload, _ = _pirtc_request_sync("GET", "/api/rtc/time", timeout=2.0)
    temp_ok, temp_payload, _ = _pirtc_request_sync("GET", "/api/rtc/temperature", timeout=2.0)

    data: dict[str, Any] = {
        "connected": bool(rtc.get("available")),
        "ready": bool(rtc.get("available")),
        "mock": bool(rtc.get("mock")),
        "rtc_i2c_address": rtc.get("i2c_address"),
        "rtc_i2c_bus": rtc.get("i2c_bus"),
        "watchdog_available": bool(watchdog.get("available")),
        "watchdog_i2c_address": watchdog.get("i2c_address"),
        "watchdog_gpio_pin": watchdog.get("gpio_pin"),
        "watchdog_timeout": watchdog.get("timeout"),
        "timestamp": payload.get("timestamp") if isinstance(payload, dict) else None,
    }
    if time_ok and isinstance(time_payload, dict):
        data["time"] = time_payload.get("time", time_payload)
    if temp_ok and isinstance(temp_payload, dict):
        data["temperature"] = temp_payload.get("temperature", temp_payload)

    return {
        "ok": True,
        "peripheral_id": RTC_PERIPHERAL_ID,
        "command": "status",
        "result": {"data": data},
    }


def run_rtc_command(command: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a diagnostic command against the RTC sidecar."""
    mapping = _RTC_COMMAND_MAP.get(command)
    if not mapping:
        return {
            "ok": False,
            "peripheral_id": RTC_PERIPHERAL_ID,
            "command": command,
            "error": f"unknown rtc command: {command}",
            "result": {"available_commands": sorted(_RTC_COMMAND_MAP)},
        }
    method, path = mapping
    ok, payload, error = _pirtc_request_sync(method, path, json_body=args if method == "POST" else None)
    return {
        "ok": ok,
        "peripheral_id": RTC_PERIPHERAL_ID,
        "command": command,
        "error": error,
        "result": payload,
    }


def build_rtc_adapter_entry() -> dict[str, Any]:
    ok, payload, error = _pirtc_request_sync("GET", "/api/status")
    if not ok:
        return {
            "id": RTC_PERIPHERAL_ID,
            "name": "Waveshare RTC WatchDog HAT (DS3231)",
            "protocol": "I2C (piRTC sidecar HTTP)",
            "status": "no-access",
            "detail": error or "piRTC sidecar unreachable",
            "probe": {"connected": False, "source": "oqlos.hardware.rtc_probe"},
        }

    rtc = payload.get("rtc", {}) if isinstance(payload, dict) else {}
    watchdog = payload.get("watchdog", {}) if isinstance(payload, dict) else {}
    rtc_avail = bool(rtc.get("available"))
    is_mock = bool(rtc.get("mock"))
    status = "ok" if rtc_avail and not is_mock else ("adapter-only" if rtc_avail else "no-access")
    return {
        "id": RTC_PERIPHERAL_ID,
        "name": "Waveshare RTC WatchDog HAT (DS3231)",
        "protocol": "I2C (piRTC sidecar HTTP)",
        "status": status,
        "mock": is_mock,
        "detail": {
            "rtc_i2c_address": rtc.get("i2c_address"),
            "watchdog_i2c_address": watchdog.get("i2c_address"),
            "watchdog_gpio_pin": watchdog.get("gpio_pin"),
        },
        "probe": {
            "connected": rtc_avail,
            "source": "oqlos.hardware.rtc_probe",
            "pirtc_url": get_pirtc_base_url(),
        },
    }


def enrich_rtc_adapter(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return payload
    adapters = list(payload.get("adapters") or [])
    if any(adapter.get("id") == RTC_PERIPHERAL_ID for adapter in adapters):
        return payload
    entry = build_rtc_adapter_entry()
    adapters.append(entry)
    payload["adapters"] = adapters
    payload["total"] = len(adapters)
    healthy = {"ok", "adapter-only"}
    payload["detected"] = sum(1 for adapter in adapters if adapter.get("status") in healthy)
    return payload
