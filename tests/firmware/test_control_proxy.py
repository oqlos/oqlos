"""Tests for the reusable OqlOS hardware control proxy."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from oqlos.hardware.control_proxy import (
    FALLBACK_ADAPTERS,
    HardwareProxyError,
    OqlosHardwareProxy,
    OqlosHardwareProxyConfig,
    resolve_diagnostic_target,
)


class FakeOqlosResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "http://oqlos.test")
            response = httpx.Response(self.status_code, request=request, json=self._payload)
            raise httpx.HTTPStatusError("status error", request=request, response=response)

    def json(self):
        return self._payload


def run(coro):
    return asyncio.run(coro)


def proxy_with_client(client):
    return OqlosHardwareProxy(
        OqlosHardwareProxyConfig(
            api_base="http://host.docker.internal:8202",
            timeout_seconds=8,
            identify_timeout_seconds=15,
        ),
        client=client,
    )


def test_health_falls_back_to_alternate_oqlos_port():
    calls = []

    class FakeClient:
        async def request(self, method, target, params=None, json=None, timeout=None):
            calls.append(target)
            if target.endswith(":8202/api/v1/hardware/health"):
                raise httpx.ConnectError("connection refused")
            return FakeOqlosResponse({"mode": "real", "status": "ok"})

    payload = run(proxy_with_client(FakeClient()).health())

    assert payload["status"] == "ok"
    assert calls == [
        "http://host.docker.internal:8202/api/v1/hardware/health",
        "http://host.docker.internal:8200/api/v1/hardware/health",
    ]


def test_identify_returns_unavailable_payload_after_connection_failures():
    class FakeClient:
        async def request(self, method, target, params=None, json=None, timeout=None):
            raise httpx.ConnectError(f"connection refused: {target}")

    payload = run(proxy_with_client(FakeClient()).identify())

    assert payload["mode"] == "unavailable"
    assert payload["detected"] == 0
    assert payload["total"] == len(FALLBACK_ADAPTERS)
    assert {adapter["status"] for adapter in payload["adapters"]} == {"no-access"}
    assert payload["diagnostics"]["health"]["detail"]["timeout_seconds"] == 15


def test_diagnostic_command_returns_structured_failure_payload():
    calls = []

    class FakeClient:
        async def request(self, method, target, params=None, json=None, timeout=None):
            calls.append((method, target, params, json))
            return FakeOqlosResponse({"valve_id": "valve-1", "value": True, "ok": False, "error": "Valve refused"})

    payload = run(
        proxy_with_client(FakeClient()).diagnostic_command(
            "modbus-io",
            "valve_on",
            {"valve_id": "valve-1"},
        )
    )

    assert payload["ok"] is False
    assert payload["error"] == "Valve refused"
    assert payload["target"] == {
        "method": "POST",
        "path": "/api/v1/hardware/valve/valve-1",
        "params": {"value": True},
    }
    assert calls[0][0] == "POST"


def test_peripheral_status_proxies_plugin_health():
    calls = []

    class FakeClient:
        async def request(self, method, target, params=None, json=None, timeout=None):
            calls.append((method, target, params, json))
            return FakeOqlosResponse({"status": "connected", "compatible": True})

    payload = run(proxy_with_client(FakeClient()).peripheral_status("modbus-io"))

    assert payload["ok"] is True
    assert payload["peripheral_id"] == "modbus-io"
    assert payload["command"] == "health"
    assert calls[0][0] == "GET"
    assert calls[0][1].endswith("/api/v1/plugins/modbus-io/health")


def test_peripheral_status_artificial_lung_uses_logical_lung_api():
    calls = []

    class FakeClient:
        async def request(self, method, target, params=None, json=None, timeout=None):
            calls.append((method, target, params, json))
            return FakeOqlosResponse({"success": True, "data": {"connected": True}})

    payload = run(proxy_with_client(FakeClient()).peripheral_status("artificial-lung"))

    assert payload["ok"] is True
    assert payload["peripheral_id"] == "artificial-lung"
    assert payload["command"] == "status"
    assert calls[0][0] == "GET"
    assert calls[0][1].endswith("/api/v1/hardware/artificial-lung/status")


def test_artificial_lung_diagnostic_resolves_to_logical_lung_api():
    method, path, params = resolve_diagnostic_target("artificial-lung", "lung_stop", {})

    assert method == "POST"
    assert path == "/api/v1/hardware/artificial-lung/command"
    assert params == {"command": "lung_stop", "args": {}}


def test_peripheral_status_rtc_uses_hardware_rtc_status():
    calls = []

    class FakeClient:
        async def request(self, method, target, params=None, json=None, timeout=None):
            calls.append((method, target, params, json))
            return FakeOqlosResponse({"ok": True, "peripheral_id": "rtc", "result": {"data": {"connected": True}}})

    payload = run(proxy_with_client(FakeClient()).peripheral_status("rtc"))

    assert payload["ok"] is True
    assert payload["peripheral_id"] == "rtc"
    assert calls[0][0] == "GET"
    assert calls[0][1].endswith("/api/v1/hardware/rtc/status")


def test_rtc_diagnostic_uses_hardware_rtc_command():
    calls = []

    class FakeClient:
        async def request(self, method, target, params=None, json=None, timeout=None):
            calls.append((method, target, params, json))
            return FakeOqlosResponse({"ok": True, "peripheral_id": "rtc", "command": "sync_to_system"})

    payload = run(proxy_with_client(FakeClient()).diagnostic_command("rtc", "sync_to_system", {"force": True}))

    assert payload["ok"] is True
    assert payload["peripheral_id"] == "rtc"
    assert calls[0][0] == "POST"
    assert calls[0][1].endswith("/api/v1/hardware/rtc/command")
    assert calls[0][3] == {"command": "sync_to_system", "args": {"force": True}}


def test_peripheral_status_returns_structured_payload_for_plugin_500():
    class FakeClient:
        async def request(self, method, target, params=None, json=None, timeout=None):
            return FakeOqlosResponse({"detail": "All connection attempts failed"}, status_code=500)

    payload = run(proxy_with_client(FakeClient()).peripheral_status("motor-dri0050"))

    assert payload["ok"] is False
    assert payload["peripheral_id"] == "motor-dri0050"
    assert payload["command"] == "status"
    assert payload["error"] == "All connection attempts failed"
    assert payload["result"]["detail"]["status_code"] == 500
    assert payload["result"]["detail"]["path"] == "/api/v1/plugins/motor-dri0050/execute"


def test_resolve_diagnostic_target_rejects_invalid_modbus_valve_id():
    with pytest.raises(HardwareProxyError) as excinfo:
        resolve_diagnostic_target("modbus-io", "valve_on", {"valve_id": "bad-id"})

    assert excinfo.value.status_code == 400
    assert "Unsupported valve_id" in str(excinfo.value.detail)
