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


def test_health_does_not_invent_an_alternate_oqlos_port(monkeypatch):
    monkeypatch.setenv("OQLOS_TRANSIENT_RETRIES", "0")
    calls = []

    class FakeClient:
        async def request(self, method, target, params=None, json=None, timeout=None, headers=None):
            calls.append(target)
            raise httpx.ConnectError("connection refused")

    payload = run(proxy_with_client(FakeClient()).health())

    assert payload["status"] == "unavailable"
    assert calls == ["http://host.docker.internal:8202/api/v1/hardware/health"]
    assert payload["detail"]["attempted_targets"] == calls


def test_identify_returns_unavailable_payload_after_connection_failures():
    class FakeClient:
        async def request(self, method, target, params=None, json=None, timeout=None, headers=None):
            raise httpx.ConnectError(f"connection refused: {target}")

    payload = run(proxy_with_client(FakeClient()).identify())

    assert payload["mode"] == "unavailable"
    assert payload["detected"] == 0
    assert payload["total"] == len(FALLBACK_ADAPTERS)
    assert {adapter["status"] for adapter in payload["adapters"]} == {"no-access"}
    assert payload["diagnostics"]["health"]["detail"]["timeout_seconds"] == 15


def test_diagnostic_command_raises_typed_failure_instead_of_ok_false():
    calls = []

    class FakeClient:
        async def request(self, method, target, params=None, json=None, timeout=None, headers=None):
            calls.append((method, target, params, json))
            return FakeOqlosResponse({"valve_id": "valve-1", "value": True, "ok": False, "error": "Valve refused"})

    with pytest.raises(HardwareProxyError) as caught:
        run(
            proxy_with_client(FakeClient()).diagnostic_command(
                "modbus-io",
                "valve_on",
                {"valve_id": "valve-1"},
            )
        )

    assert caught.value.status_code == 503
    assert caught.value.detail["error"] == "Valve refused"
    assert caught.value.detail["error_code"] == "C2004-HW-0012"
    assert caught.value.detail["issue_code"] == "hw_modbus_no_response"
    assert caught.value.detail["target"] == {
        "method": "POST",
        "path": "/api/v1/hardware/valve/valve-1",
        "params": {"value": True},
    }
    assert calls[0][0] == "POST"


def test_peripheral_status_proxies_plugin_health():
    calls = []

    class FakeClient:
        async def request(self, method, target, params=None, json=None, timeout=None, headers=None):
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
        async def request(self, method, target, params=None, json=None, timeout=None, headers=None):
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


def test_valve_diagnostic_resolves_for_every_valve_controller():
    """Regression: a stand on io-m5-4in8out used to be rejected by the proxy with
    "Unsupported diagnostic command 'valve_on'" before the request left C2004."""
    for peripheral in ("modbus-io", "io-m5-4in8out"):
        assert resolve_diagnostic_target(peripheral, "valve_on", {"valve_id": "valve-wc"}) == (
            "POST",
            "/api/v1/hardware/valve/valve-wc",
            {"value": True},
        )
        assert resolve_diagnostic_target(peripheral, "valve_off", {"valve_id": "valve-wc"}) == (
            "POST",
            "/api/v1/hardware/valve/valve-wc",
            {"value": False},
        )
        assert resolve_diagnostic_target(
            peripheral, "set_valve", {"valve_id": "valve_wc", "value": True}
        ) == ("POST", "/api/v1/hardware/valve/valve-wc", {"value": True})


def test_unknown_valve_command_names_the_requested_peripheral():
    with pytest.raises(HardwareProxyError) as exc:
        resolve_diagnostic_target("io-m5-4in8out", "spin", {"valve_id": "valve-wc"})

    assert "io-m5-4in8out" in str(exc.value.detail)


def test_status_diagnostic_resolves_to_read_only_canonical_status_api():
    method, path, params = resolve_diagnostic_target("motor-dri0050", "status", {})

    assert method == "GET"
    assert path == "/api/v3/hardware/peripheral-status/motor-dri0050"
    assert params is None


def test_peripheral_status_rtc_uses_hardware_rtc_status():
    calls = []

    class FakeClient:
        async def request(self, method, target, params=None, json=None, timeout=None, headers=None):
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
        async def request(self, method, target, params=None, json=None, timeout=None, headers=None):
            calls.append((method, target, params, json))
            return FakeOqlosResponse({"ok": True, "peripheral_id": "rtc", "command": "sync_to_system"})

    payload = run(proxy_with_client(FakeClient()).diagnostic_command("rtc", "sync_to_system", {"force": True}))

    assert payload["ok"] is True
    assert payload["peripheral_id"] == "rtc"
    assert calls[0][0] == "POST"
    assert calls[0][1].endswith("/api/v1/hardware/rtc/command")
    assert calls[0][3] == {"command": "sync_to_system", "args": {"force": True}}


def test_peripheral_status_preserves_plugin_http_failure():
    class FakeClient:
        async def request(self, method, target, params=None, json=None, timeout=None, headers=None):
            return FakeOqlosResponse({"detail": "All connection attempts failed"}, status_code=500)

    with pytest.raises(HardwareProxyError) as caught:
        run(proxy_with_client(FakeClient()).peripheral_status("motor-dri0050"))

    assert caught.value.status_code == 500
    assert caught.value.detail["error"] == "All connection attempts failed"
    assert caught.value.detail["path"] == "/api/v1/plugins/motor-dri0050/execute"


def test_resolve_diagnostic_target_rejects_invalid_modbus_valve_id():
    with pytest.raises(HardwareProxyError) as excinfo:
        resolve_diagnostic_target("modbus-io", "valve_on", {"valve_id": "bad-id"})

    assert excinfo.value.status_code == 400
    assert "Unsupported valve_id" in str(excinfo.value.detail)
