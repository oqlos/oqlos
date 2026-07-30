"""Tests for RTC sidecar enrichment on hardware identify."""

from __future__ import annotations

import asyncio

from oqlos.api import hardware as hardware_api
from oqlos.api import hardware_peripherals_routes as hw_peripherals
from oqlos.hardware.rtc_probe import (
    RTC_PERIPHERAL_ID,
    build_rtc_peripheral_status,
    enrich_rtc_adapter,
    is_rtc_hardware_enabled,
    run_rtc_command,
)


def test_rtc_mock_mode_status(monkeypatch) -> None:
    monkeypatch.delenv("OQLOS_ENABLE_RTC", raising=False)
    monkeypatch.setenv("OQLOS_HARDWARE_MODE", "mock")

    payload = build_rtc_peripheral_status()

    assert payload["ok"] is True
    assert payload["result"]["data"]["mock"] is True
    assert payload["result"]["data"]["connected"] is True


def test_rtc_mock_run_command(monkeypatch) -> None:
    monkeypatch.delenv("OQLOS_ENABLE_RTC", raising=False)
    monkeypatch.setenv("OQLOS_HARDWARE_MODE", "mock")

    payload = run_rtc_command("read_temperature")

    assert payload["ok"] is True
    assert payload["result"]["temperature"] == 23.5


def test_enrich_rtc_adapter_mock_mode(monkeypatch) -> None:
    monkeypatch.delenv("OQLOS_ENABLE_RTC", raising=False)
    monkeypatch.setenv("OQLOS_HARDWARE_MODE", "mock")
    payload = {"adapters": [{"id": "modbus-io", "status": "ok"}], "total": 1, "detected": 1}

    out = enrich_rtc_adapter(payload)

    assert out["total"] == 2
    rtc = next(a for a in out["adapters"] if a["id"] == RTC_PERIPHERAL_ID)
    assert rtc["mock"] is True


def test_enrich_rtc_adapter_skips_when_disabled(monkeypatch) -> None:
    monkeypatch.delenv("OQLOS_ENABLE_RTC", raising=False)
    monkeypatch.delenv("C2004_HARDWARE_ENABLE_RTC", raising=False)
    payload = {"adapters": [{"id": "modbus-io", "status": "ok"}], "total": 1, "detected": 1}
    assert enrich_rtc_adapter(payload) == payload
    assert is_rtc_hardware_enabled() is False


def test_enrich_rtc_adapter_appends_rtc(monkeypatch) -> None:
    monkeypatch.setenv("OQLOS_ENABLE_RTC", "1")
    monkeypatch.setattr(
        "oqlos.hardware.rtc_probe.build_rtc_adapter_entry",
        lambda: {
            "id": RTC_PERIPHERAL_ID,
            "status": "ok",
            "name": "RTC",
            "protocol": "I2C",
        },
    )
    payload = {"adapters": [{"id": "modbus-io", "status": "ok"}], "total": 1, "detected": 1}

    out = enrich_rtc_adapter(payload)

    assert out["total"] == 2
    assert any(a["id"] == RTC_PERIPHERAL_ID for a in out["adapters"])


def test_enrich_rtc_adapter_idempotent() -> None:
    payload = {
        "adapters": [{"id": RTC_PERIPHERAL_ID, "status": "no-access"}],
        "total": 1,
        "detected": 0,
    }

    out = enrich_rtc_adapter(payload)

    assert out["total"] == 1


def test_build_rtc_peripheral_status_reads_sidecar(monkeypatch) -> None:
    monkeypatch.setenv("OQLOS_ENABLE_RTC", "1")
    calls = []

    def fake_request(method, path, *, json_body=None, timeout=2.0):
        calls.append((method, path, json_body))
        if path == "/api/status":
            return True, {
                "rtc": {
                    "available": True,
                    "ready": True,
                    "mock": False,
                    "i2c_address": "0x68",
                    "i2c_bus": 1,
                },
                "watchdog": {
                    "available": False,
                    "ready": True,
                    "enabled": False,
                    "model": "disabled",
                    "i2c_address": "0x67",
                    "gpio_pin": 4,
                    "timeout": 300,
                },
                "timestamp": "2026-05-19T12:00:00Z",
            }, None
        if path == "/api/rtc/time":
            return True, {"time": "12:00:00"}, None
        if path == "/api/rtc/temperature":
            return True, {"temperature": 22.5}, None
        return False, {}, "unexpected"

    monkeypatch.setattr("oqlos.hardware.rtc_probe._pirtc_request_sync", fake_request)

    payload = build_rtc_peripheral_status()

    assert payload["ok"] is True
    assert payload["peripheral_id"] == RTC_PERIPHERAL_ID
    assert payload["command"] == "status"
    assert payload["result"]["data"]["connected"] is True
    assert payload["result"]["data"]["time"] == "12:00:00"
    assert calls[0][1] == "/api/status"


def test_build_rtc_peripheral_status_rejects_false_available(monkeypatch) -> None:
    monkeypatch.setenv("OQLOS_ENABLE_RTC", "1")

    def fake_request(method, path, *, json_body=None, timeout=2.0):
        if path == "/api/status":
            return True, {
                "rtc": {
                    "available": False,
                    "ready": False,
                    "mock": False,
                    "error_code": "C2004-HW-0016",
                    "issue_code": "rtc_i2c_unavailable",
                    "last_error": "read_time: [Errno 121] Remote I/O error",
                },
                "watchdog": {"enabled": False, "ready": True, "available": False},
            }, None
        return False, {}, "hardware unavailable"

    monkeypatch.setattr("oqlos.hardware.rtc_probe._pirtc_request_sync", fake_request)

    payload = build_rtc_peripheral_status()

    assert payload["ok"] is False
    data = payload["result"]["data"]
    assert data["ready"] is False
    assert data["error_code"] == "C2004-HW-0016"
    assert data["issue_code"] == "rtc_i2c_unavailable"


def test_run_rtc_command_posts_to_sidecar(monkeypatch) -> None:
    monkeypatch.setenv("OQLOS_ENABLE_RTC", "1")
    calls = []

    def fake_request(method, path, *, json_body=None, timeout=2.0):
        calls.append((method, path, json_body))
        return True, {"synced": True}, None

    monkeypatch.setattr("oqlos.hardware.rtc_probe._pirtc_request_sync", fake_request)

    payload = run_rtc_command("sync_to_system", {"force": True})

    assert payload["ok"] is True
    assert payload["command"] == "sync_to_system"
    assert payload["result"] == {"synced": True}
    assert calls == [("POST", "/api/rtc/sync-to-system", {"force": True})]


def test_hardware_rtc_status_endpoint_uses_probe(monkeypatch) -> None:
    monkeypatch.setattr(
        hw_peripherals,
        "build_rtc_peripheral_status",
        lambda: {"ok": True, "peripheral_id": RTC_PERIPHERAL_ID, "command": "status"},
    )

    payload = asyncio.run(hardware_api.rtc_status())

    assert payload["ok"] is True
    assert payload["peripheral_id"] == RTC_PERIPHERAL_ID


def test_hardware_rtc_command_endpoint_uses_probe(monkeypatch) -> None:
    calls = []

    def fake_run(command, args=None):
        calls.append((command, args))
        return {"ok": True, "peripheral_id": RTC_PERIPHERAL_ID, "command": command}

    monkeypatch.setattr(hw_peripherals, "run_rtc_command", fake_run)

    payload = asyncio.run(hardware_api.rtc_command({"command": "sync_to_system", "args": {"force": True}}))

    assert payload["ok"] is True
    assert payload["command"] == "sync_to_system"
    assert calls == [("sync_to_system", {"force": True})]
