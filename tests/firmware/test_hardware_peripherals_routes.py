"""Regression tests for Modbus ADC raw peripheral routes."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
import pytest

from oqlos.api import hardware_peripherals_routes as peripherals
from oqlos.api.main import app
from oqlos.errors import OqlosError


def test_modbus_adc_raw_raises_typed_error_when_incompatible(monkeypatch):
    class _Gateway:
        async def health(self):
            return {
                "mode": "real",
                "modbus-adc": {"compatible": False, "status": "disabled"},
            }

    monkeypatch.setattr(peripherals, "get_hardware_gateway", lambda: _Gateway())

    with pytest.raises(OqlosError) as caught:
        asyncio.run(peripherals.read_modbus_adc_raw())
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "modbus_adc_not_detected"


def test_modbus_adc_raw_raises_typed_error_when_read_fails(monkeypatch):
    class _Plugin:
        config = type("Cfg", (), {"serial_port": "/dev/null", "baudrate": 4800, "device_id": 1})()

        async def execute_command(self, command: str, params: dict):
            return {"success": False, "error": "read timed out"}

    class _Gateway:
        async def health(self):
            return {
                "mode": "real",
                "modbus-adc": {"compatible": True, "status": "connected"},
            }

        async def _get_or_connect_plugin(self, plugin_id: str):
            assert plugin_id == "modbus-adc"
            return _Plugin()

    monkeypatch.setattr(peripherals, "get_hardware_gateway", lambda: _Gateway())

    with pytest.raises(OqlosError) as caught:
        asyncio.run(peripherals.read_modbus_adc_raw())
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "hw_modbus_no_response"


def _assert_safe_problem(
    response,
    *,
    issue_code: str,
    stage: str,
    reason: str,
) -> None:
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "C2004-HW-0012"
    assert body["correlation_id"] == "cor-modbus-adc-raw"
    assert body["component"] == "modbus-adc"
    assert body["stage"] == stage
    assert body["metadata"]["diagnostics"]["issue_code"] == issue_code
    context = body["metadata"]["context"]
    assert context["operation_id"] == "hardware.modbus-adc.raw"
    assert context["upstream_target"] == "hardware-plugin://modbus-adc"
    assert context["reason"] == reason
    assert set(context) == {
        "architecture",
        "layer",
        "component",
        "stage",
        "problem_source",
        "operation_id",
        "upstream_target",
        "reason",
    }
    assert "hunter2" not in response.text
    assert "filesystem root" not in response.text


def test_modbus_adc_raw_gateway_failure_is_sanitized(monkeypatch):
    class _Gateway:
        async def health(self):
            raise RuntimeError("password=hunter2 filesystem root")

    monkeypatch.setattr(peripherals, "get_hardware_gateway", lambda: _Gateway())

    response = TestClient(app, raise_server_exceptions=False).get(
        "/api/v1/hardware/modbus-adc/raw",
        headers={"X-Correlation-ID": "cor-modbus-adc-raw"},
    )

    _assert_safe_problem(
        response,
        issue_code="modbus_adc_not_detected",
        stage="gateway.health",
        reason="gateway_health_unavailable",
    )


def test_modbus_adc_raw_plugin_connection_failure_is_sanitized(monkeypatch):
    class _Gateway:
        async def health(self):
            return {
                "mode": "password=hunter2",
                "secret": "filesystem root",
                "modbus-adc": {
                    "compatible": True,
                    "status": "password=hunter2",
                },
            }

        async def _get_or_connect_plugin(self, _plugin_id: str):
            raise RuntimeError("password=hunter2 filesystem root")

    monkeypatch.setattr(peripherals, "get_hardware_gateway", lambda: _Gateway())

    response = TestClient(app, raise_server_exceptions=False).get(
        "/api/v1/hardware/modbus-adc/raw",
        headers={"X-Correlation-ID": "cor-modbus-adc-raw"},
    )

    _assert_safe_problem(
        response,
        issue_code="modbus_adc_not_detected",
        stage="plugin.connect",
        reason="plugin_connection_failed",
    )


def test_modbus_adc_raw_plugin_read_failure_is_sanitized(monkeypatch):
    class _Plugin:
        async def execute_command(self, _command: str, _params: dict):
            return {
                "success": False,
                "error": "password=hunter2 filesystem root",
                "debug": {"serial_port": "/dev/password=hunter2"},
            }

    class _Gateway:
        async def health(self):
            return {
                "mode": "password=hunter2",
                "modbus-adc": {
                    "compatible": True,
                    "status": "password=hunter2",
                },
            }

        async def _get_or_connect_plugin(self, _plugin_id: str):
            return _Plugin()

    monkeypatch.setattr(peripherals, "get_hardware_gateway", lambda: _Gateway())

    response = TestClient(app, raise_server_exceptions=False).get(
        "/api/v1/hardware/modbus-adc/raw",
        headers={"X-Correlation-ID": "cor-modbus-adc-raw"},
    )

    _assert_safe_problem(
        response,
        issue_code="hw_modbus_no_response",
        stage="plugin.read",
        reason="read_failed",
    )
